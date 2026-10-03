"""T7 group: the free card reader's background sweep (`docs/specs/identify-engine-pick.md`, section 8).

Part of `harness/tests/t7_store_and_seams.py` (one verdict). Nothing here loads the model, spawns a
process of the sweep's own or sleeps: the model, the clock, the sleep and the spawn are fakes, and the
server is a throwaway one on 127.0.0.1 with an ephemeral port.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
from unittest import mock

from harness.tests import Checks
from harness.tests.t7.common import (
    REPO_ROOT,
    QuietHandler,
    _spawn_server,
    capture_payload,
    error_code,
    isolated_home,
    photograph,
    quiet,
    request,
)
from identify import match, matchconst, sweep
from server import capture_server, pipeline_routes
from store import cache as cache_mod
from store import db as store_db
from store import files, master, photos
from store.session import Store

HAIKU, MATCHER = cache_mod.ENGINE_HAIKU, cache_mod.ENGINE_MATCHER
SAID = {"name": "Card", "number": "1", "printed_total": "9", "confidence": "high"}
_SHOTS = iter(range(1, 10_000))


def _capture(box: int = 3, **extra) -> str:
    """One capture through the real route. Returns the new card's position key."""
    before = set(Store().read().inventory.cards)
    capture_server.do_capture(capture_payload(box, capture_id=f"sweep-c{next(_SHOTS)}", **extra))
    return next(iter(set(Store().read().inventory.cards) - before))


def _reshoot(key: str) -> None:
    box, index = key.split("/")
    capture_server.do_reshoot(
        int(box), int(index),
        {"capture_id": f"sweep-r{next(_SHOTS)}", "image": base64.b64encode(photograph()).decode("ascii")},
    )


def _put(key: str, engine: str, *, cleared: bool = False) -> None:
    with Store().write() as snap:
        snap.cache.put(key, dict(SAID), "sha-x", "fp", engine=engine)
        snap.cache.entries[key].cleared_by_human = cleared


def _switch(on: bool) -> None:
    conn = store_db.connect(files.inventory_dir())
    try:
        store_db.set_match_sweep(conn, on)
    finally:
        conn.close()


def _queue() -> list:
    conn = sweep.open_store()
    try:
        return [key for key, _ in sweep.queue(conn)]
    finally:
        conn.close()


def _engines() -> dict:
    return {key: entry.engine for key, entry in Store().read().cache.entries.items()}


# ------------------------------------------------------------------------------- 1. the queue


def check_sweep_queue(checks: Checks) -> None:
    checks.note("")
    checks.note("SWEEP QUEUE — hinted captured cards of a served game with no row, and no other")
    with isolated_home():
        hinted = _capture(game="pokemon", set_hint="sv9")
        rift_unhinted = _capture(game="riftbound")
        unhinted = _capture(game="pokemon")
        code = _capture(game="pokemon_code")
        misc = _capture(game="misc")
        has_row = _capture(game="pokemon", set_hint="sv9")
        tried = _capture(game="pokemon", set_hint="sv9")
        _put(has_row, HAIKU)
        sweep.remember_tried({tried: Store().read().inventory.cards[tried].capture_id})
        queued = _queue()
        checks.ok(hinted in queued, "a hinted captured Pokemon card with no row is queued")
        checks.ok(rift_unhinted in queued, "an unhinted card of another served game is queued")
        checks.ok(unhinted not in queued, "an unhinted Pokemon card is not (its pool is the whole category)")
        checks.ok(code not in queued and misc not in queued, "a code card and a misc card are not")
        checks.ok(has_row not in queued, "a card that already has a row is not")
        checks.ok(tried not in queued, "a card already tried at the same capture id is not")
        sweep.remember_tried({tried: "another-capture"})
        checks.ok(tried in _queue(), "but a card tried at an older capture id is queued again")


# -------------------------------------------------------------------------------- 2. the watcher


class _Worker:
    """A fake child: runs for `polls` looks, then exits with `code`. Records signals."""

    def __init__(self, code=0, polls=0):
        self.pid, self.returncode, self._left, self._code, self.signals = 4242, None, polls, code, []

    def poll(self):
        if self.returncode is None and self._left <= 0:
            self.returncode = self._code
        self._left -= 1
        return self.returncode

    def send_signal(self, sig):
        self.signals.append(sig)

    def wait(self, timeout=None):
        self.returncode = -15

    def kill(self):
        self.returncode = -9


def _watch(*, last, clock, workers, polls, sleeper=None, poll=5.0, quiet_s=3.0):
    """`sweep.watch` on a fake clock, sleep and spawn. Returns (result, the workers it spawned)."""
    spawned = []

    def spawn():
        spawned.append(workers.pop(0) if workers else _Worker())
        return spawned[-1]

    def sleep(seconds):
        clock[0] += seconds
        if sleeper:
            sleeper()

    with mock.patch.object(sweep, "files_present", lambda: True), mock.patch.object(
        sweep, "newest_capture", lambda _conn: last[0]
    ):
        result = sweep.watch(quiet_s, poll, sleep=sleep, now=lambda: clock[0], spawn=spawn, max_polls=polls)
    return result, spawned


def check_sweep_watcher(checks: Checks) -> None:
    checks.note("")
    checks.note("SWEEP WATCHER — gaps only, stops on a capture or the switch, backs off, one at a time")
    with isolated_home():
        _capture(game="pokemon", set_hint="sv9")
        _switch(True)

        _, spawned = _watch(last=[1000.0], clock=[1001.0], workers=[], polls=3, poll=0.1)
        checks.equal(len(spawned), 0, "no worker starts while now - last is under the quiet time")
        _, spawned = _watch(last=[1000.0], clock=[1010.0], workers=[], polls=1)
        checks.equal(len(spawned), 1, "one worker starts when the gap is due")

        newer = [1000.0]
        slow = _Worker(polls=300)
        _watch(last=newer, clock=[1010.0], workers=[slow], polls=1, sleeper=lambda: newer.__setitem__(0, 2000.0))
        checks.ok(slow.signals, "a newer capture stops the running worker")
        slow = _Worker(polls=300)
        _watch(last=[1000.0], clock=[1010.0], workers=[slow], polls=1, sleeper=lambda: _switch(False))
        checks.ok(slow.signals, "the switch going off stops the running worker")

        _switch(True)
        _, spawned = _watch(last=[0.0], clock=[1000.0], workers=[_Worker(3)], polls=4, poll=100.0)
        checks.equal(len(spawned), 1, "after exit code 3 no worker starts for 300 s")
        _, spawned = _watch(last=[0.0], clock=[1000.0], workers=[_Worker(3)], polls=5, poll=100.0)
        checks.equal(len(spawned), 2, "and one starts again at 300 s")
        _, spawned = _watch(last=[0.0], clock=[1000.0], workers=[_Worker(0)], polls=2, poll=100.0)
        checks.equal(len(spawned), 2, "control: after exit code 0 the next poll starts one at once")

        sweep._write_json(sweep.state_path(), {"pid": os.getppid()})
        result, spawned = _watch(last=[0.0], clock=[1000.0], workers=[], polls=1)
        checks.equal((result, len(spawned)), (1, 0), "a live watcher already running: exit 1, nothing spawned")
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        sweep._write_json(sweep.state_path(), {"pid": dead.pid})
        result, _ = _watch(last=[0.0], clock=[1000.0], workers=[], polls=1)
        checks.equal(result, 0, "control: a stale pid file does not block")


# --------------------------------------------------------------------------------- 3. the worker


class _FakeIndex:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def check_sweep_worker(checks: Checks) -> None:
    from cli import cmd_match

    checks.note("")
    checks.note("SWEEP WORKER — marqo-b rows only, no overwrite, no card state, skips a changed card")
    with isolated_home():
        keys = {name: _capture(game="pokemon", set_hint="sv9") for name in "ABCDEF"}
        _switch(True)
        inventory = Store().read().inventory
        untouched = {k: repr(inventory.cards[keys[k]]) for k in "AB"}
        old_digest = photos.sha256_of(photos.find(inventory.cards[keys["C"]].cid))
        calls = []

        def fake_read(requests, _index):
            calls.append([r.key for r in requests])
            if len(calls) > 4:  # a queue that never empties must end as a red case, not a hang
                _switch(False)
            if len(calls) == 1:
                _reshoot(keys["C"])
                with Store().write() as snap:
                    snap.inventory.cards[keys["D"]].state = master.RETIRED
                _put(keys["E"], HAIKU)
                _put(keys["F"], HAIKU, cleared=True)
            return [
                match.Result(r.key, True, dict(SAID, engine=MATCHER))
                if r.key != keys["B"]
                else match.Result(r.key, False, None, match.UNREAD_MARGIN)
                for r in requests
            ]

        with mock.patch.object(match, "status", lambda: {"ready": True}), mock.patch.object(
            match, "Index", _FakeIndex
        ), mock.patch.object(match, "read", fake_read), mock.patch.object(os, "nice", lambda _n: 0), mock.patch(
            "signal.signal", lambda *_a: None
        ), quiet():
            code = cmd_match.sweep_worker(lambda _line: None)
        checks.equal(code, 0, "the worker reads the queue and exits 0")
        engines = _engines()
        checks.equal(engines.get(keys["A"]), MATCHER, "an accepted card gets a marqo-b row")
        checks.ok(
            all(e == MATCHER for k, e in engines.items() if k not in (keys["E"], keys["F"])),
            "every row it wrote is marqo-b",
        )
        checks.equal(engines.get(keys["E"]), HAIKU, "a Haiku row that appeared mid-read is not overwritten")
        cache = Store().read().cache
        checks.ok(
            cache.get(keys["F"]).cleared_by_human and cache.get(keys["F"]).engine == HAIKU,
            "a cleared row is not overwritten",
        )
        checks.ok(keys["D"] not in engines, "a card changed mid-read (no longer captured) gets no row")
        now = Store().read().inventory
        row = cache.get(keys["C"])
        new_digest = photos.sha256_of(photos.find(now.cards[keys["C"]].cid))
        checks.ok(
            row is not None and row.photo_sha256 == new_digest != old_digest,
            "a card re-shot mid-read is not written from the old photograph, and is read again from the new one",
        )
        checks.equal(
            sweep.tried().get(keys["B"]), now.cards[keys["B"]].capture_id,
            "an unaccepted card is recorded as tried at its capture id",
        )
        checks.ok(keys["B"] not in engines, "and gets no row")
        checks.equal({k: repr(now.cards[keys[k]]) for k in "AB"}, untouched, "the worker writes no card state")


# ------------------------------------------------------------------------------ 4. the re-shoot


def check_reshoot_drops_matcher_row(checks: Checks) -> None:
    checks.note("")
    checks.note("RE-SHOOT — drops a marqo-b row, leaves a Haiku or cleared row")
    with isolated_home():
        free, paid, cleared = (_capture(game="pokemon", set_hint="sv9") for _ in range(3))
        _put(free, MATCHER)
        _put(paid, HAIKU)
        _put(cleared, MATCHER, cleared=True)
        for key in (free, paid, cleared):
            _reshoot(key)
        engines = _engines()
        kept = Store().read().cache.get(cleared)
        checks.ok(free not in engines, "a re-shoot drops the card's marqo-b row")
        checks.equal(engines.get(paid), HAIKU, "and leaves a Haiku row")
        checks.ok(kept is not None and kept.cleared_by_human, "and leaves a cleared row")


# -------------------------------------------------------------------------------- 5. the routes


def check_sweep_routes(checks: Checks) -> None:
    checks.note("")
    checks.note("SWEEP ROUTES — PUT needs a boolean `on`, GET carries on, running and matched")
    spawned = []
    with isolated_home():
        for engine in (MATCHER, MATCHER, HAIKU):
            _put(_capture(game="pokemon", set_hint="sv9"), engine)
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        try:
            with mock.patch.object(pipeline_routes, "_spawn_sweep_watcher", lambda: spawned.append(1)):
                for bad in ({}, {"on": "yes"}, {"on": 1}, {"on": None}):
                    status, body, _ = request(port, "PUT", "/pipeline/match/sweep", payload=bad)
                    checks.ok(
                        status == 400 and error_code(body) == "on_required",
                        f"PUT with {bad!r} is refused, on_required",
                    )
                status, body, _ = request(port, "PUT", "/pipeline/match/sweep", payload={"on": True})
                checks.equal((status, json.loads(body)["on"]), (200, True), "PUT on true answers the new state, on")
                checks.equal(len(spawned), 1, "and starts the watcher")
                status, body, _ = request(port, "GET", "/pipeline/match/sweep")
                answer = json.loads(body)
                checks.equal(sorted(answer), ["matched", "on", "running"], "GET answers on, running and matched")
                checks.equal(
                    (answer["on"], answer["matched"]), (True, 2),
                    "on is the stored switch, matched counts marqo-b rows only",
                )
                status, body, _ = request(port, "PUT", "/pipeline/match/sweep", payload={"on": False})
                checks.equal(json.loads(body)["on"], False, "PUT on false answers off")
                checks.equal(len(spawned), 1, "and starts nothing")
                status, body, _ = request(port, "GET", "/pipeline/match")
                checks.equal((status, json.loads(body).get("matched")), (200, 2), "GET /pipeline/match carries matched")
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)


# ------------------------------------------------------------------------- 6. the import budget


def check_sweep_imports_light(checks: Checks) -> None:
    checks.note("")
    checks.note("SWEEP IMPORTS — the watcher stays a small idle process")
    probe = (
        "import sys; from identify import sweep; "
        "print(sorted(m for m in ('store','numpy','PIL','onnxruntime') if m in sys.modules))"
    )
    out = subprocess.run([sys.executable, "-c", probe], cwd=str(REPO_ROOT), capture_output=True, text=True)
    checks.equal(out.stdout.strip(), "[]", "importing identify.sweep loads no store, numpy, PIL or onnxruntime")
    with tempfile.TemporaryDirectory() as tmp:
        for value in (None, tmp):
            with mock.patch.dict(os.environ):
                os.environ.pop(files.HOME_ENV, None)
                if value:
                    os.environ[files.HOME_ENV] = value
                checks.equal(
                    matchconst.home(), files.home(),
                    f"matchconst.home() equals store.files.home() ({'override' if value else 'default'})",
                )


CHECKS = (
    check_sweep_queue,
    check_sweep_watcher,
    check_sweep_worker,
    check_reshoot_drops_matcher_row,
    check_sweep_routes,
    check_sweep_imports_light,
)
