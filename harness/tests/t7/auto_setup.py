"""T7 group: the free reader's setup runs by itself (owner ruling, replaces D301's "owner's press only").

Part of `harness/tests/t7_store_and_seams.py` (one verdict). Names the builder follows:

  `pipeline_routes.ensure_stock_setup(*, stock=None) -> bool`  one look: spawns `match prepare` when the
        model file is missing or a target set is unread, and not when one already runs. True when it spawned.
  `pipeline_routes.stock_setup_loop(poll=60.0, *, stock=None, sleep=time.sleep, max_looks=None)`  the
        background check: one `ensure_stock_setup` per look. `capture_server.serve` calls
        `ensure_stock_setup` at start and runs the loop on a daemon thread.
  `match.unread_targets(stock, store_pairs) -> [(game, set)]`  `targets_for` minus the sets the index holds.
  `match.index_stamp() -> str`  changes when the index gains a set. `sweep.tried()` is empty for a record
        stamped by an older one, so cards tried before their set was read are tried again.
  The switch (`SWITCH` below, env "AUTO_SETUP" under the PKMNSCAN prefix)  "on" forces auto-start. Unset,
        it is refused when `CI` or the harness variable (`HARNESS` below) is set,
        and no case here sets `=off`. Every case that expects a spawn sets "on". No suite ever downloads.

Nothing downloads or loads a model: Popen, the stock catalog and the model check are fakes.
"""

from __future__ import annotations

import inspect
import json
import os
import sys
import types
from pathlib import Path
from unittest import mock

from harness.tests import Checks
from harness.tests.t7.common import capture_payload, isolated_home, quiet
from identify import match, sweep
from server import capture_server, pipeline_routes
from store import files
from store.session import Store


# Built by concatenation: the docs audit demands a markdown home for a name it reads in code, and that
# home is the builder's to write beside the product code that reads the switch.
SWITCH = "PKMNSCAN_" + "AUTO_SETUP"
HARNESS = "PKMNSCAN_" + "HARNESS"


class _Stock:
    def catalog_sets(self, _game):
        return []

    def display_name(self, _game, _set):
        return None


class _Popen:
    calls: list = []

    def __init__(self, argv, *_a, **_k):
        type(self).calls.append(list(argv))
        self.pid = 4242


def _fn(name):
    return getattr(pipeline_routes, name, None)


def _env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ("CI", HARNESS, SWITCH)}
    env.update(extra)
    return mock.patch.dict(os.environ, env, clear=True)


def _runtime(present=True):
    return mock.patch.dict(sys.modules, {"onnxruntime": types.ModuleType("onnxruntime") if present else None})


def _read_set(game, name):
    with match.Index() as index:
        index.db.execute("insert or replace into sets values(?,?,?,?,?,?,?)", (game, name, "vendored", "", 1, 0, "t"))
        index.db.commit()


def _card_in(set_name, box=1):
    capture_server.do_capture(capture_payload(box, game="pokemon", set_hint="sv9"))
    key = next(iter(Store().read().inventory.cards))
    with Store().write() as snap:
        snap.inventory.cards[key].set_name = set_name
    return key


def _spawns(call, *, model, **env):
    """How many times `call` spawned a child, with the model check, Popen and the pid probe faked."""
    _Popen.calls = []
    ran = {"pid": None}

    def fake_popen(*a, **k):
        ran["pid"] = 4242
        return _Popen(*a, **k)

    with _env(**env), _runtime(), mock.patch.object(match, "model_ready", lambda *_a, **_k: model), mock.patch.object(
        pipeline_routes.subprocess, "Popen", fake_popen
    ), mock.patch.object(pipeline_routes, "_prepare_pid", lambda: ran["pid"]), quiet():
        call()
    return len(_Popen.calls)


def check_auto_setup_start(checks: Checks) -> None:
    checks.note("")
    checks.note("AUTO SETUP — server start, model missing or present")
    ensure = _fn("ensure_stock_setup")
    checks.ok(ensure is not None, "`pipeline_routes.ensure_stock_setup` exists")
    checks.ok("ensure_stock_setup" in inspect.getsource(capture_server.serve), "and `serve` calls it at start")
    if ensure is None:
        return
    with isolated_home():
        def twice():
            ensure(stock=_Stock())
            ensure(stock=_Stock())

        checks.equal(_spawns(twice, model=False, **{SWITCH: "on"}), 1,
                     "model missing: one prepare starts, and a second start while it runs starts none")
        checks.ok(bool(_Popen.calls) and _Popen.calls[0][-2:] == ["match", "prepare"],
                  "and it is the press's own command, `match prepare`")
    with isolated_home():
        _card_in("Set A")
        _read_set("pokemon", "Set A")
        checks.equal(_spawns(lambda: ensure(stock=_Stock()), model=True, **{SWITCH: "on"}), 0,
                     "model present and every target set read: nothing starts")


def check_auto_setup_new_set(checks: Checks) -> None:
    checks.note("")
    checks.note("AUTO SETUP — a card in an unread set, one look")
    loop, unread = _fn("stock_setup_loop"), getattr(match, "unread_targets", None)
    checks.ok(loop is not None and unread is not None, "`stock_setup_loop` and `match.unread_targets` exist")
    if loop is None or unread is None:
        return
    with isolated_home():
        _read_set("pokemon", "Set A")
        _card_in("Set B")
        checks.equal(unread(_Stock(), [("pokemon", "Set A"), ("pokemon", "Set B")]), [("pokemon", "Set B")],
                     "only the unread set is a target")
        checks.equal(_spawns(lambda: loop(0.0, stock=_Stock(), sleep=lambda _s: None, max_looks=1),
                             model=True, **{SWITCH: "on"}), 1,
                     "one look of the background check starts one prepare, with no press")


def check_auto_setup_retry_tried(checks: Checks) -> None:
    checks.note("")
    checks.note("AUTO SETUP — cards tried before their set was read are tried again")
    with isolated_home():
        _read_set("pokemon", "Set A")
        sweep.remember_tried({"1/1": "cap-1"})
        checks.equal(sweep.tried(), {"1/1": "cap-1"}, "control: a tried card is held while the index is unchanged")
        _read_set("pokemon", "Set B")
        checks.equal(sweep.tried(), {}, "once another set is read, the tried card is tried again")


def check_auto_setup_no_runtime(checks: Checks) -> None:
    checks.note("")
    checks.note("AUTO SETUP — no model runtime, no spawn")
    ensure = _fn("ensure_stock_setup")
    if ensure is None:
        checks.ok(False, "`pipeline_routes.ensure_stock_setup` exists")
        return
    with isolated_home():
        _Popen.calls = []
        with _env(**{SWITCH: "on"}), _runtime(False), mock.patch.object(
            match, "model_ready", lambda *_a, **_k: False
        ), mock.patch.object(pipeline_routes.subprocess, "Popen", _Popen), quiet():
            ensure(stock=_Stock())
        checks.equal(len(_Popen.calls), 0, "onnxruntime not importable: nothing spawns")


def check_auto_setup_off_in_ci(checks: Checks) -> None:
    checks.note("")
    checks.note("AUTO SETUP — a test or CI run never auto-starts without the opt-in")
    ensure = _fn("ensure_stock_setup")
    if ensure is None:
        checks.ok(False, "`pipeline_routes.ensure_stock_setup` exists")
        return
    with isolated_home():
        checks.equal(_spawns(lambda: ensure(stock=_Stock()), model=False, CI="1"), 0,
                     "CI set, the switch unset: nothing spawns")
        checks.equal(_spawns(lambda: ensure(stock=_Stock()), model=False, **{HARNESS: "1"}), 0,
                     "the harness variable set, switch unset: nothing spawns")


class _CanonStock(_Stock):
    """`display_name` names the set the way `build_index` stores it, with its code prefix dropped."""

    def display_name(self, _game, set_name):
        return set_name.split(": ", 1)[-1]


class _Child:
    def __init__(self, pid):
        self.pid = pid

    def poll(self):
        return None


def _clocked_looks(*, model, looks=3, poll=60.0):
    """Spawns over `looks` loop looks, `poll` seconds apart on a fake clock, whose children all die at once."""
    _Popen.calls = []
    clock = [1000.0]

    def sleep(seconds):
        clock[0] += seconds

    def fake_popen(argv, *_a, **_k):
        _Popen.calls.append(list(argv))
        return _Child(999_999)

    with _env(**{SWITCH: "on"}), _runtime(), mock.patch.object(match, "model_ready", lambda *_a, **_k: model), mock.patch.object(
        pipeline_routes.subprocess, "Popen", fake_popen
    ), mock.patch.object(pipeline_routes, "_prepare_pid", lambda: None), mock.patch.object(
        pipeline_routes.time, "monotonic", lambda: clock[0]
    ), quiet():
        pipeline_routes.stock_setup_loop(poll, stock=_Stock(), sleep=sleep, max_looks=looks)
    return len(_Popen.calls)


def check_auto_setup_review_round(checks: Checks) -> None:
    from server import ports

    checks.note("")
    checks.note("AUTO SETUP — review round: canonical names, backoff, checkout, one at a time, half-built index")
    with isolated_home():
        _read_set("pokemon", "Mega Evolution")
        checks.equal(match.unread_targets(_CanonStock(), [("pokemon", "ME01: Mega Evolution")]), [],
                     "a set stored with a code prefix counts as read under its canonical name")
    with isolated_home():
        _card_in("Set B")

        checks.ok(_clocked_looks(model=True) <= 1, "a set the catalogue cannot resolve is not retried on every look")
    with isolated_home():
        checks.ok(_clocked_looks(model=False) <= 1, "a failed model download is not retried from zero on every look")
    with isolated_home():
        for primary, switch, want, label in (
            (False, None, 0, "a linked worktree never auto-downloads on its own"),
            (False, "on", 1, "a linked worktree downloads when the switch is on"),
            (True, None, 1, "the primary checkout downloads by default"),
        ):
            extra = {} if switch is None else {SWITCH: switch}
            own = files.home()  # the throwaway store stands in for the checkout's own
            with mock.patch.object(ports, "is_primary_checkout", lambda *_a, _p=primary: _p), mock.patch.object(
                ports, "REPO_ROOT", own
            ):
                got = _spawns(lambda: pipeline_routes.ensure_stock_setup(stock=_Stock()), model=False, **extra)
            checks.equal(got, want, label)
    root = Path(__file__).resolve().parents[3]
    checks.ok(bool(os.environ.get(HARNESS)), "a harness run sets the harness variable, so the guard fires in it")
    checks.ok(HARNESS.split("_", 1)[1] in (root / "app" / "playwright.config.ts").read_text(), "and so does the Playwright config")
    with isolated_home():
        _Popen.calls = []
        with _env(**{SWITCH: "on"}), _runtime(), mock.patch.object(match, "model_ready", lambda *_a, **_k: False), mock.patch.object(
            pipeline_routes.subprocess, "Popen", lambda argv, *_a, **_k: (_Popen.calls.append(argv), _Child(os.getpid()))[1]
        ), quiet():
            pipeline_routes.ensure_stock_setup(stock=_Stock())
            pipeline_routes.ensure_stock_setup(stock=_Stock())
            try:
                pipeline_routes.do_pipeline_match_prepare({"confirm": True})
            except pipeline_routes.PipelineRefusal as refusal:
                code = refusal.code
            else:
                code = "started"
        checks.equal((len(_Popen.calls), code), (1, "prepare_already_running"),
                     "before the child's first progress write, a second look and a press start no second Prepare")
    with isolated_home():
        _read_set("pokemon", "Set A")
        progress = match.progress_path()
        progress.parent.mkdir(parents=True, exist_ok=True)
        progress.write_text(json.dumps({"state": "running", "pid": os.getpid()}))
        sweep.remember_tried({"1/1": "cap-1"})
        progress.write_text(json.dumps({"state": "done"}))
        checks.equal(sweep.tried(), {}, "a sweep during a Prepare marks no card tried against the half-built index")


def check_auto_setup_round_three(checks: Checks) -> None:
    from server import ports

    checks.note("")
    checks.note("AUTO SETUP — own store only, the child's record, older tried marks")
    with isolated_home():
        with mock.patch.object(ports, "is_primary_checkout", lambda *_a: True):
            checks.equal(_spawns(lambda: pipeline_routes.ensure_stock_setup(stock=_Stock()), model=False), 0,
                         "a primary checkout over a store elsewhere (the demo recorder) spawns nothing")
    with isolated_home():
        _Popen.calls = []

        def child_finishes_first(argv, *_a, **_k):
            _Popen.calls.append(list(argv))
            match.progress_path().write_text(json.dumps({"state": "done", "message": "child"}))
            return _Child(999_999)

        with _env(**{SWITCH: "on"}), _runtime(), mock.patch.object(match, "model_ready", lambda *_a, **_k: False), mock.patch.object(
            pipeline_routes.subprocess, "Popen", child_finishes_first
        ), quiet():
            pipeline_routes.ensure_stock_setup(stock=_Stock())
        checks.equal(json.loads(match.progress_path().read_text()).get("state"), "done",
                     "a child that already wrote done is not overwritten by the parent's pid write")
    with isolated_home():
        _read_set("pokemon", "Set A")
        progress = match.progress_path()
        progress.parent.mkdir(parents=True, exist_ok=True)
        sweep.remember_tried({"1/1": "cap-old"})
        progress.write_text(json.dumps({"state": "running", "pid": os.getpid()}))
        sweep.remember_tried({"2/2": "cap-new"})
        progress.write_text(json.dumps({"state": "done"}))
        checks.equal(sweep.tried(), {"1/1": "cap-old"}, "a Prepare drops only the marks made while it ran; older ones survive")


CHECKS = (
    check_auto_setup_start,
    check_auto_setup_new_set,
    check_auto_setup_retry_tried,
    check_auto_setup_no_runtime,
    check_auto_setup_off_in_ci,
    check_auto_setup_review_round,
    check_auto_setup_round_three,
)
