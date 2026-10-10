"""T7 group: the free card reader's background sweep (`docs/specs/identify-engine-pick.md`, section 8).

Part of `harness/tests/t7_store_and_seams.py` (one verdict). Nothing here loads the model, spawns a
process of the sweep's own or sleeps: the model, the clock, the sleep and the spawn are fakes, and the
server is a throwaway one on 127.0.0.1 with an ephemeral port.
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
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
SAID = {"name": "Card", "number": "1", "printed_total": "9", "finish": "normal", "confidence": "high"}
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


@contextlib.contextmanager
def _tree():
    """A throwaway tree for `sweep.REPO_ROOT`: `.serve/` (the pid file, the owner mark, the log) lands
    here and never in the checkout. `scripts/` links to the real one so the reap mark can import."""
    if sweep.REPO_ROOT != REPO_ROOT:  # already inside one: nested uses share it
        yield sweep.REPO_ROOT
        return
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "scripts").symlink_to(REPO_ROOT / "scripts")
        with mock.patch.object(sweep, "REPO_ROOT", root):
            yield root


def _watch(*, last, clock, workers, polls, sleeper=None, poll=5.0, quiet_s=3.0):
    """`sweep.watch` on a fake clock, sleep and spawn. Returns (result, the workers it spawned).
    `quiet_s="default"` leaves the quiet time to the watcher's own default."""
    spawned = []

    def spawn():
        spawned.append(workers.pop(0) if workers else _Worker())
        spawned[-1].at = clock[0]
        return spawned[-1]

    def sleep(seconds):
        clock[0] += seconds
        if sleeper:
            sleeper()

    quiet_arg = {} if quiet_s == "default" else {"quiet": quiet_s}
    with _tree(), mock.patch.object(sweep, "files_present", lambda: True), mock.patch.object(
        sweep, "newest_capture", lambda _conn: last[0]
    ):
        result = sweep.watch(poll=poll, **quiet_arg, sleep=sleep, now=lambda: clock[0], spawn=spawn, max_polls=polls)
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

        held = sweep.acquire_lock()
        try:
            result, spawned = _watch(last=[0.0], clock=[1000.0], workers=[], polls=1)
        finally:
            held.close()
        checks.equal((result, len(spawned)), (1, 0), "a held lock means a watcher runs: exit 1, nothing spawned")
        sweep._write_json(sweep.state_path(), {"pid": os.getppid()})
        result, _ = _watch(last=[0.0], clock=[1000.0], workers=[], polls=1)
        checks.equal(result, 0, "a state file naming a live pid does not block, only the lock does")


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
                checks.equal(sorted(answer), ["aside", "blocked", "matched", "on", "running"], "GET answers on, running, matched, blocked and aside")
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


# ------------------------------------------------------------ 2b. backoff, quiet, lock, crash, guard


def check_sweep_backoff(checks: Checks) -> None:
    checks.note("")
    checks.note("SWEEP BACKOFF — exit 1 waits 30, 60, 120 s up to 1800 s; 0 resets; 3 waits 300 s; a stop is no failure")
    with isolated_home():
        _capture(game="pokemon", set_hint="sv9")
        _switch(True)

        def gaps(codes, polls):
            _, spawned = _watch(last=[0.0], clock=[1000.0], workers=[_Worker(c) for c in codes], polls=polls, poll=10.0)
            times = [w.at for w in spawned]
            return [t2 - t1 for t1, t2 in zip(times, times[1:])]

        checks.equal(
            gaps([1] * 9, 700)[:8], [30, 60, 120, 240, 480, 960, 1800, 1800],
            "exit 1 doubles the wait from 30 s and caps it at 1800 s",
        )
        checks.equal(gaps([1, 1, 0, 1, 1], 40)[:4], [30, 60, 0, 30], "exit 0 resets it, so the next failure waits 30 s again")
        checks.equal(gaps([3, 0], 40)[:1], [300], "exit 3 waits 300 s")

        newer, slow = [1000.0], _Worker(polls=300)
        _, spawned = _watch(
            last=newer, clock=[1010.0], workers=[slow], polls=3, quiet_s=1.0,
            sleeper=lambda: None if slow.returncode else newer.__setitem__(0, 1010.2),
        )
        checks.equal(len(spawned), 2, "a worker the watcher stopped is no failure: the next one starts with no backoff")


def check_sweep_quiet(checks: Checks) -> None:
    checks.note("")
    checks.note("SWEEP QUIET — default 0: no gap, a capture never stops a worker. Above 0: both gates apply")
    with isolated_home():
        _capture(game="pokemon", set_hint="sv9")
        _switch(True)
        checks.equal(sweep.QUIET_SECONDS, 0.0, "the default quiet time is 0")
        _, spawned = _watch(last=[1010.0], clock=[1010.0], workers=[], polls=1, quiet_s="default")
        checks.equal(len(spawned), 1, "at the default a worker starts with no gap after the last capture")
        newer, slow = [1000.0], _Worker(polls=300)
        _watch(last=newer, clock=[1010.0], workers=[slow], polls=1, quiet_s="default",
               sleeper=lambda: newer.__setitem__(0, 2000.0))
        checks.equal(slow.signals, [], "at the default a newer capture never stops the worker")
        _, spawned = _watch(last=[1010.0], clock=[1010.0], workers=[], polls=1, quiet_s=3.0)
        checks.equal(len(spawned), 0, "above 0 the gap gate holds a worker back")
        newer, slow = [1000.0], _Worker(polls=300)
        _watch(last=newer, clock=[1010.0], workers=[slow], polls=1, quiet_s=3.0,
               sleeper=lambda: newer.__setitem__(0, 2000.0))
        checks.ok(slow.signals, "and a newer capture stops the worker")


def check_sweep_lock(checks: Checks) -> None:
    checks.note("")
    checks.note("SWEEP LOCK — one flock says running; SIGTERM, gone tree, .serve file and owner mark")
    with isolated_home(), _tree() as root:
        checks.ok(not sweep.running(), "no watcher: running() is false")
        held = sweep.acquire_lock()
        checks.ok(sweep.running() and sweep.acquire_lock() is None, "a held lock reads as running, and a second acquire fails")
        held.close()
        checks.ok(not sweep.running(), "running() is false after release")
        sweep._write_json(sweep.state_path(), {"pid": os.getppid()})
        checks.ok(not sweep.running() and sweep.running_pid() is None, "a state file naming a live pid is not running")

        # stop_watcher_of trusts the lock, never the pid.
        sweep._write_json(root / ".serve" / "match-sweep.json", {"pid": 4242, "lock": str(sweep.lock_path())})
        signaled = []
        with mock.patch.object(sweep.os, "kill", lambda pid, sig: signaled.append((pid, sig))):
            checks.equal((sweep.stop_watcher_of(root), signaled), (None, []), "stop_watcher_of signals nothing while the lock is free")
            held = sweep.acquire_lock()
            try:
                answer = sweep.stop_watcher_of(root)
            finally:
                held.close()
        checks.equal((answer, signaled), (4242, [(4242, signal.SIGTERM)]), "and SIGTERMs the recorded pid while the lock is held")

        # SIGTERM: the handler stops the worker, then exits 0. The handler is captured, not installed.
        _capture(game="pokemon", set_hint="sv9")
        _switch(True)
        handlers, slow, fired = [], _Worker(polls=300), []

        def sleeper():
            if handlers and not fired:
                fired.append(1)
                handlers[0](signal.SIGTERM, None)

        def install(sig, handler):
            if sig == signal.SIGTERM and callable(handler):
                handlers.append(handler)

        with mock.patch.object(sweep.signal, "signal", install):
            try:
                _watch(last=[1000.0], clock=[1010.0], workers=[slow], polls=2, sleeper=sleeper)
                code = "returned"
            except SystemExit as bye:
                code = bye.code
        checks.equal((code, bool(slow.signals)), (0, True), "SIGTERM stops the worker, then the watcher exits 0")

        _watch(last=[1000.0], clock=[1010.0], workers=[], polls=1)
        record = json.loads((root / ".serve" / "match-sweep.json").read_text())
        checks.equal(record, {"pid": os.getpid(), "lock": str(sweep.lock_path())}, ".serve/match-sweep.json names the watcher's pid and its lock")
        checks.ok((root / ".serve" / "owners" / f"{os.getpid()}.json").is_file(), "and the reap owner mark exists")

        # _gone(): a store that no longer exists ends the watcher at once, where a store that is
        # merely unreadable would be waited on (one sleep per poll).
        sleeps = []
        (sweep.inventory_dir() / sweep.DB_FILENAME).unlink()
        result, _ = _watch(last=[1000.0], clock=[1010.0], workers=[], polls=5, sleeper=lambda: sleeps.append(1))
        checks.equal((result, len(sleeps)), (0, 0), "_gone() ends the watcher with exit 0 when the store is gone, with no wait")


def check_sweep_crash(checks: Checks) -> None:
    from cli import cmd_match

    checks.note("")
    checks.note("SWEEP CRASH — ImportError is exit 3, any other exception exit 1 with the chunk tried, inflight settled, log")
    with isolated_home(), _tree() as root:
        keys = [_capture(game="pokemon", set_hint="sv9") for _ in range(3)]
        _switch(True)
        ids = {k: Store().read().inventory.cards[k].capture_id for k in keys}

        def run_worker(boom):
            def read(_requests, _index):
                raise boom

            with mock.patch.object(match, "status", lambda: {"ready": True}), mock.patch.object(
                match, "Index", _FakeIndex
            ), mock.patch.object(match, "read", read), mock.patch.object(os, "nice", lambda _n: 0), mock.patch(
                "signal.signal", lambda *_a: None
            ), quiet():
                return cmd_match.sweep_worker(lambda _line: None)

        checks.equal(run_worker(ImportError("no onnxruntime")), sweep.EXIT_NOT_READY, "an ImportError in the worker is exit 3")
        checks.ok(not sweep.inflight_path().exists(), "and leaves no inflight file")
        checks.equal(run_worker(RuntimeError("bad photo")), 1, "any other exception is exit 1")
        checks.equal(sweep.tried(), {}, "a crash marks no card tried: the chunk stays in the free queue")
        checks.equal(sorted(_queue()), sorted(ids), "and every card of the chunk is queued to be read free again")
        checks.ok(not sweep.inflight_path().exists(), "and the inflight file settled")

        sweep.mark_inflight({"9/9": "left-over-1"})
        with mock.patch.object(match, "status", lambda: {"ready": False}), quiet():
            cmd_match.sweep_worker(lambda _line: None)
        checks.ok("9/9" not in sweep.tried(), "a leftover inflight file marks no card tried; it is settled at worker start")
        checks.ok(not sweep.inflight_path().exists(), "and removed")
        sweep.mark_inflight({"9/7": "left-over-0"})
        _watch(last=[1000.0], clock=[1001.0], workers=[], polls=1)  # inside the quiet time: no worker
        checks.ok("9/7" not in sweep.tried(), "a leftover inflight file marks no card tried; it is settled when the watcher starts")
        sweep.mark_inflight({"9/8": "left-over-2"})
        _watch(last=[0.0], clock=[1000.0], workers=[_Worker(1)], polls=1)
        checks.ok("9/8" not in sweep.tried(), "a leftover inflight file marks no card tried; it is settled after a failed worker exit")

        real_popen = subprocess.Popen

        def popen(_argv, **kw):
            real_popen([sys.executable, "-c", "import sys; sys.stderr.write('worker-boom')"],
                       stdout=kw["stdout"], stderr=kw["stderr"]).wait()
            return _Worker()

        with mock.patch.object(sweep.subprocess, "Popen", popen):
            sweep._spawn_worker()
        log = root / ".serve" / "match-sweep.log"
        checks.ok(log.is_file() and "worker-boom" in log.read_text(), "worker stderr lands in .serve/match-sweep.log")


def check_sweep_crash_stays_free(checks: Checks) -> None:
    """OWNER: "crashing should never result in being a reason to move to the paid pile". Only a clean
    read that could not accept a card marks it tried (`check_sweep_worker`'s card B)."""
    checks.note("")
    checks.note("SWEEP CRASH STAYS FREE — a worker that dies mid-batch leaves its cards in the free queue")
    with isolated_home(), _tree():
        keys = [_capture(game="pokemon", set_hint="sv9") for _ in range(2)]
        _switch(True)
        ids = {k: Store().read().inventory.cards[k].capture_id for k in keys}
        for code in (1, -9):  # a non-zero exit, then a kill
            sweep.mark_inflight(dict(ids))
            _watch(last=[0.0], clock=[1000.0], workers=[_Worker(code)], polls=1)
            checks.equal(sweep.tried(), {}, f"after worker exit {code} no card is tried")
            checks.equal(sorted(_queue()), sorted(keys), f"after worker exit {code} both cards are queued for the free read")
        sweep.mark_inflight(dict(ids))
        sweep.settle_inflight()
        checks.equal(sorted(_queue()), sorted(keys), "settle_inflight alone leaves the dead worker's cards queued")


def check_run_route_defaults_free(checks: Checks) -> None:
    """`docs/specs/identify-engine-pick.md` "The wire": `RunSend` engine defaults to `marqo-b`. A direct
    caller that omits `engine` must get the free read, never the CLI's own haiku default."""
    checks.note("")
    checks.note("RUN ROUTE DEFAULTS FREE — no engine on the wire means --engine marqo-b")

    def engine_of(payload):
        flags = pipeline_routes._identify_flags(payload)
        return flags[flags.index("--engine") + 1] if "--engine" in flags else None

    checks.equal(engine_of({}), "marqo-b", "a run request with no engine passes --engine marqo-b")
    checks.equal(engine_of({"crop": True, "max_edge": 1200}), "marqo-b", "so does one that sets only the reading")
    checks.equal(engine_of({"engine": "haiku"}), "haiku", "the composer's explicit paid pick still passes --engine haiku")
    checks.equal(engine_of({"engine": "marqo-b"}), "marqo-b", "and the explicit free pick passes --engine marqo-b")


def check_sweep_cid_guard(checks: Checks) -> None:
    from cli import cmd_match

    checks.note("")
    checks.note("SWEEP GUARD — an answer is skipped when the cid changed and the capture id did not")
    with isolated_home():
        renamed, plain = (_capture(game="pokemon", set_hint="sv9") for _ in range(2))
        _switch(True)
        calls = []

        def fake_read(requests, _index):
            calls.append(1)
            if len(calls) == 1:
                with Store().write() as snap:
                    snap.inventory.cards[renamed].cid = "f" * 64
            else:
                _switch(False)
            return [match.Result(r.key, True, dict(SAID, engine=MATCHER)) for r in requests]

        with mock.patch.object(match, "status", lambda: {"ready": True}), mock.patch.object(
            match, "Index", _FakeIndex
        ), mock.patch.object(match, "read", fake_read), mock.patch.object(os, "nice", lambda _n: 0), mock.patch(
            "signal.signal", lambda *_a: None
        ), quiet():
            cmd_match.sweep_worker(lambda _line: None)
        engines = _engines()
        checks.equal(engines.get(plain), MATCHER, "control: the unchanged card gets its row")
        checks.ok(renamed not in engines, "a card whose cid changed mid-read gets no row from the old answer")


def check_sweep_runtime_cause(checks: Checks) -> None:
    checks.note("")
    checks.note("SWEEP CAUSE — `blocked` on GET /pipeline/match/sweep is derived from the runtime now, never stored")
    with isolated_home(), _tree():
        _capture(game="pokemon", set_hint="sv9")
        for on in (True, False):  # the switch and the queue do not matter: the answer is the present state
            _switch(on)
            for importable, want in ((False, "runtime_missing"), (True, None)):
                with mock.patch.object(matchconst, "runtime_importable", lambda value=importable: value):
                    checks.equal(
                        pipeline_routes.do_pipeline_match_sweep().get("blocked"), want,
                        f"switch {'on' if on else 'off'}, runtime {'importable' if importable else 'missing'}: blocked is {want!r}",
                    )
        sweep.set_blocked("runtime_missing")  # a value a past worker left behind
        with mock.patch.object(matchconst, "runtime_importable", lambda: True):
            checks.equal(
                pipeline_routes.do_pipeline_match_sweep().get("blocked"), None,
                "a stale stored cause does not show once the runtime is installed",
            )


# ------------------------------------------------------------ 5b. the Capture head's matched counter


def check_sweep_sitting_count(checks: Checks) -> None:
    """THE CONTRACT THE CAPTURE HEAD'S "matched" COUNTER READS (owner ruling), named here for the builder:
    `GET /pipeline/match/sweep?keys=<csv of position keys>` adds `matched_here` (how many named keys carry a
    free-reader row; unknown keys and Haiku rows count zero) and `worker` (the watcher's own state file
    names a worker). The polled path NEVER probes the lock: `sweep.acquire_lock` and `sweep.running` are
    not called, so a poll can never hold the flock a starting watcher needs."""
    checks.note("")
    checks.note("SWEEP SITTING COUNT — keys-scoped matched_here and worker, read with no lock probe")
    with isolated_home():
        mine = [_capture(game="pokemon", set_hint="sv9") for _ in range(3)]
        _put(mine[0], MATCHER)
        _put(mine[1], HAIKU)
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        path = "/pipeline/match/sweep?keys=" + ",".join([*mine, "99/99"])

        def boom(*_a, **_k):
            raise AssertionError("the polled path probed the lock")

        try:
            with mock.patch.object(sweep, "acquire_lock", boom), mock.patch.object(sweep, "running", boom):
                status, body, _ = request(port, "GET", path)
                answer = json.loads(body) if status == 200 else {}
                checks.equal(status, 200, "GET with keys answers with no lock probe")
                checks.equal(answer.get("matched_here"), 1, "matched_here counts the named keys with a free-reader row only")
                checks.equal(answer.get("worker"), False, "worker is false with no state file")
                status, body, _ = request(port, "GET", "/pipeline/match/sweep?keys=")
                checks.equal((status, json.loads(body).get("matched_here")), (200, 0), "an empty keys list counts zero")
                sweep._write_state(worker=4242)
                status, body, _ = request(port, "GET", path)
                checks.equal(json.loads(body).get("worker") if status == 200 else None, True, "worker is true when the state file names one")
            for _ in range(5):
                request(port, "GET", path)
            handle = sweep.acquire_lock()
            checks.ok(handle is not None, "after repeated polls the lock is free: a watcher can still start")
            if handle is not None:
                handle.close()
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)


def check_sweep_band_counts(checks: Checks) -> None:
    """THE CONTRACT THE REVIEW SUMMARY BAND READS (`identify-engine-pick.md` section 8), named here for the builder:
    `GET /pipeline/match/sweep?keys=<csv>` also answers `paid` (named keys that wait for a paid look: captured, no
    identification row, tried by the free reader and not accepted, not set aside) and `unread` (named keys the
    free reader has not looked at: captured, no identification row, not tried, not set aside). A matched key, a
    Haiku-read key and an unknown key count in neither. Same no-lock-probe path as `matched_here`."""
    checks.note("")
    checks.note("SWEEP BAND COUNTS — keys-scoped paid and unread")
    with isolated_home():
        mine = [_capture(game="pokemon", set_hint="sv9") for _ in range(5)]
        matched, tried_one, read_paid, fresh, outside = mine
        _put(matched, MATCHER)
        _put(read_paid, HAIKU)
        capture_id = {key: card.capture_id for key, card in Store().read().inventory.cards.items()}
        sweep.remember_tried({tried_one: capture_id[tried_one] or ""})
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        try:
            path = "/pipeline/match/sweep?keys=" + ",".join([matched, tried_one, read_paid, fresh, "99/99"])
            status, body, _ = request(port, "GET", path)
            answer = json.loads(body) if status == 200 else {}
            checks.equal(status, 200, "GET with keys answers")
            checks.equal(answer.get("matched_here"), 1, "matched_here is unchanged")
            checks.equal(answer.get("paid"), 1, "paid counts the tried, unaccepted, unread-by-Haiku card only")
            checks.equal(answer.get("unread"), 1, "unread counts the card the free reader has not looked at only")
            status, body, _ = request(port, "GET", "/pipeline/match/sweep?keys=" + outside)
            answer = json.loads(body) if status == 200 else {}
            checks.equal((answer.get("paid"), answer.get("unread")), (0, 1), "a key outside the named set is never counted")
            status, body, _ = request(port, "GET", "/pipeline/match/sweep?keys=")
            answer = json.loads(body) if status == 200 else {}
            checks.equal((answer.get("paid"), answer.get("unread")), (0, 0), "an empty keys list counts zero")
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)


def check_sweep_band_scope(checks: Checks) -> None:
    """THE REST OF THE BAND'S CONTRACT, named for the builder. On `GET /pipeline/match/sweep?keys=`:
    `unread` mirrors `sweep._QUEUE_SQL`: a card in a game the free reader does not serve, and a Pokemon card with an empty
    `set_hint`, are NOT unread (the free reader never queues them). A card in an unserved game is in `paid` and `paid_keys`
    (the paid look reads it, tried or not). A Pokemon card with no set hint is in neither, and `unhinted` counts it.
    `matched_keys` lists the named keys that carry a free-reader row (`matched_here` is its length), so the band can leave out
    a card that also has an open review row. `aside` counts only the named keys that are set aside, never the table's."""
    checks.note("")
    checks.note("SWEEP BAND SCOPE — queue mirror, unhinted, matched_keys, scoped aside")
    with isolated_home():
        served = _capture(game="pokemon", set_hint="sv9")
        unserved = _capture(game="pokemon_code")
        unhinted = _capture(game="pokemon")
        matched = _capture(game="pokemon", set_hint="sv9")
        elsewhere = _capture(game="pokemon", set_hint="sv9")
        crashed = _capture(game="pokemon", set_hint="sv9")
        _put(matched, MATCHER)
        cards = Store().read().inventory.cards
        sweep._write_json(
            sweep.crash_path(),
            {"model": matchconst.MODEL_SHA256, "aside": {elsewhere: cards[elsewhere].capture_id or "", crashed: cards[crashed].capture_id or ""}},
        )
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        try:
            named = [served, unserved, unhinted, matched, crashed]
            status, body, _ = request(port, "GET", "/pipeline/match/sweep?keys=" + ",".join(named))
            answer = json.loads(body) if status == 200 else {}
            checks.equal(status, 200, "GET with keys answers")
            checks.equal(answer.get("unread"), 1, "unread is the served, hinted card only: not the unserved game, not the unhinted Pokemon")
            checks.equal(answer.get("paid_keys"), [unserved], "an unserved-game card is in paid_keys, an unhinted Pokemon card is not")
            checks.equal(answer.get("paid"), 1, "paid counts the unserved-game card")
            checks.equal(answer.get("unhinted"), 1, "unhinted counts the Pokemon card with no set hint")
            checks.equal(answer.get("matched_keys"), [matched], "matched_keys names the card carrying a free-reader row")
            checks.equal(answer.get("aside"), 1, "aside counts only the named card set aside, not the one outside the keys")
            status, body, _ = request(port, "GET", "/pipeline/match/sweep?keys=" + served)
            checks.equal(json.loads(body).get("aside") if status == 200 else None, 0, "aside is 0 when none of the named keys is set aside")
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)


def check_sweep_band_aside_is_current(checks: Checks) -> None:
    """`aside` counts a named key only while the set-aside mark still holds: the card is captured, has no identification,
    and carries the capture id the mark was made on. A card re-photographed after it was set aside is unread, never aside;
    one that later got an identification is neither (it is matched or read)."""
    checks.note("")
    checks.note("SWEEP BAND ASIDE — a stale set-aside mark counts nowhere")
    with isolated_home():
        held = _capture(game="pokemon", set_hint="sv9")
        reshot = _capture(game="pokemon", set_hint="sv9")
        identified = _capture(game="pokemon", set_hint="sv9")
        cards = Store().read().inventory.cards
        marks = {key: cards[key].capture_id or "" for key in (held, reshot, identified)}
        sweep._write_json(sweep.crash_path(), {"model": matchconst.MODEL_SHA256, "aside": marks})
        _reshoot(reshot)
        _put(identified, MATCHER)
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        try:
            status, body, _ = request(port, "GET", "/pipeline/match/sweep?keys=" + ",".join([held, reshot, identified]))
            answer = json.loads(body) if status == 200 else {}
            checks.equal(status, 200, "GET with keys answers")
            checks.equal(answer.get("aside"), 1, "aside counts only the card whose mark still holds")
            checks.equal(answer.get("unread"), 1, "the re-photographed card is unread")
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)


def _mark_tried(*keys: str) -> None:
    cards = Store().read().inventory.cards
    sweep.remember_tried({k: cards[k].capture_id for k in keys})


def check_claims_correction_requeues(checks: Checks) -> None:
    checks.note("")
    checks.note("CLAIMS CORRECTION — a changed claim puts only that card back in the free queue; a no-op changes nothing")
    with isolated_home():
        a, b = _capture(box=5, game="pokemon", set_hint="sv9"), _capture(box=5, game="pokemon", set_hint="sv9")
        d = _capture(box=5, game="pokemon", set_hint="sv8")
        e, f = _capture(box=6, game="pokemon", set_hint="sv9"), _capture(box=6, game="pokemon", set_hint="sv9")
        _mark_tried(a, b, d, e, f)
        checks.ok(not {a, b, d, e, f} & set(_queue()), "(precondition) all five tried cards are out of the queue")
        box5 = lambda payload: capture_server.do_put_box_claims(5, payload)  # noqa: E731
        box5({"set_hint": "sv8"})  # changes a and b; d already says sv8
        checks.ok(a in _queue() and b in _queue(), "1. box claims route: the corrected cards are queued for the free reader again")
        checks.ok(a not in sweep.tried() and b not in sweep.tried(), "2. and no longer marked tried")
        checks.ok(d not in _queue() and d in sweep.tried(), "3. a card the call did not change stays tried")
        _mark_tried(a, b)
        box5({"set_hint": "sv8"})
        checks.ok(not {a, b, d} & set(_queue()), "4. a no-op claims call (same values) resets nothing")
        i = int(e.split("/")[1])
        capture_server.do_put_card(6, i, {"set_hint": "sv9"})
        checks.ok(e not in _queue(), "5. card route: a restated claim resets nothing")
        capture_server.do_put_card(6, i, {"set_hint": "sv8"})
        checks.ok(e in _queue() and e not in sweep.tried(), "6. card route: a changed claim queues the card again")
        checks.ok(f not in _queue() and f in sweep.tried(), "7. and leaves its neighbour in the box tried")


# ------------------------------------------------------------- the band's sheets (identify-engine-pick.md, 10.5)
# WIRE SHAPE ASSUMED HERE, NAMED FOR THE BUILDER (the spec fixes the fields, not their spellings): `detail=` answers
# `cards`, one row per card of that one count, each `{key, box_name, index, cid, code, candidates}`; a `candidates`
# entry is `{name, set, number}`. `sweep.remember_tried(additions, results)` takes the unaccepted `Result`s second.
# `sweep.why()` is `{key: {code, margin, floor, candidates}}`. `sweep.clear_unexplained()` takes no argument.


def _unaccepted(key: str, code: str = match.UNREAD_MARGIN, n: int = 3) -> "match.Result":
    cands = [{"product_id": 100 + i, "set": "sv9", "number": str(i + 1), "name": f"Cand {i}", "cosine": 0.9 - i / 10} for i in range(n)]
    return match.Result(key, False, None, code, "x", margin=0.01, floor=0.9, candidates=cands)


def _remember(checks: Checks, additions: dict, results: list, label: str) -> bool:
    """`remember_tried` with its new second argument. A TypeError is the red verdict, never an error."""
    try:
        sweep.remember_tried(additions, results)
        return True
    except TypeError as exc:
        sweep.remember_tried(additions)  # the mark itself, so later steps run on the old shape
        return checks.ok(False, label, f"remember_tried takes no reasons yet: {exc}")


def _why():
    fn = getattr(sweep, "why", None)
    return fn() if callable(fn) else None


def _record() -> dict:
    return sweep._read_json(sweep.tried_path()) or {}


@contextlib.contextmanager
def _serving():
    httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
    thread = _spawn_server(httpd)
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _sweep_get(port: int, keys, detail=None) -> dict:
    path = "/pipeline/match/sweep?keys=" + ",".join(keys) + (f"&detail={detail}" if detail else "")
    status, body, _ = request(port, "GET", path)
    return json.loads(body) if status == 200 else {"_status": status}


def _keys_of(answer: dict) -> set:
    return {r.get("key") for r in (answer.get("cards") or [])}


def check_why_kept_with_the_mark(checks: Checks) -> None:
    checks.note("")
    checks.note("BAND SHEETS 1-3 — the sweep keeps a why beside each tried mark, stamp-bound, dropped with the mark")
    with isolated_home():
        key = _capture(game="pokemon", set_hint="sv9")
        cid = Store().read().inventory.cards[key].capture_id
        _remember(checks, {key: cid}, [_unaccepted(key)], "1. remember_tried accepts the unaccepted Results")
        checks.equal(
            (_why() or {}).get(key),
            {"code": match.UNREAD_MARGIN, "margin": 0.01, "floor": 0.9,
             "candidates": [{"name": "Cand 0", "set": "sv9", "number": "1"}, {"name": "Cand 1", "set": "sv9", "number": "2"}]},
            "1. why[key] holds the code, margin, floor and at most two candidates as {name, set, number}",
        )
        checks.equal(sweep.tried().get(key), cid, "1. tried keeps its shape")
        raw = _record()
        with mock.patch.object(match, "index_stamp", lambda: "another-index"):
            checks.ok(_why() == {} and bool(raw.get("why")), "2. why is {} against another index stamp, as tried is")
        sweep._write_json(sweep.tried_path(), {**raw, "model": "another-model"})
        checks.ok(_why() == {} and bool(raw.get("why")), "2. why is {} against another model")
        sweep._write_json(sweep.tried_path(), raw)
        sweep.forget_tried([key])
        checks.ok(bool(raw.get("why")) and key not in (_record().get("why") or {}), "3. forget_tried removes the reason from the record with the mark")
        checks.ok(_why() is not None and key not in _why(), "3. and sweep.why no longer answers it")


def check_sweep_detail_reads(checks: Checks) -> None:
    checks.note("")
    checks.note("BAND SHEETS 4-6, 15, 20, 21 — `detail=paid|unread|matched|unhinted` answers `cards` for exactly one count")
    with isolated_home():
        paid_a = _capture(box=3, game="pokemon", set_hint="sv9")
        paid_b = _capture(box=3, game="pokemon", set_hint="sv9")
        legacy = _capture(box=3, game="pokemon", set_hint="sv9")
        unserved = _capture(box=3, game="pokemon_code")
        unread = _capture(box=3, game="pokemon", set_hint="sv9")
        matched = _capture(box=3, game="pokemon", set_hint="sv9")
        unhinted = _capture(box=3, game="pokemon")
        _put(matched, MATCHER)
        cards = Store().read().inventory.cards
        cid = lambda k: cards[k].capture_id or ""  # noqa: E731
        _remember(checks, {paid_a: cid(paid_a), paid_b: cid(paid_b)}, [_unaccepted(paid_a), _unaccepted(paid_b, match.UNREAD_FLOOR)], "4. (precondition) reasons can be stored")
        sweep.remember_tried({legacy: cid(legacy)})  # a mark from before the change: no reason
        named = [paid_a, paid_b, legacy, unserved, unread, matched, unhinted]
        with _serving() as port:
            plain = _sweep_get(port, named)
            checks.ok("cards" not in plain and "_status" not in plain, "4. with no detail the answer has no `cards`")
            checks.equal(sorted(plain.get("paid_keys") or []), sorted([paid_a, paid_b, legacy, unserved]), "4. (precondition) paid_keys is the four paid cards")
            paid = _sweep_get(port, named, "paid")
            checks.equal(_keys_of(paid) if "cards" in paid else None, set(plain.get("paid_keys") or []), "4. detail=paid names exactly paid_keys")
            by = {r.get("key"): r for r in (paid.get("cards") or [])}
            row = by.get(paid_a) or {}
            box_name = Store().read().inventory.boxes[3].name
            checks.ok(
                row.get("box_name") == box_name and row.get("index") == int(paid_a.split("/")[1]) and row.get("cid") == cards[paid_a].cid
                and row.get("code") == match.UNREAD_MARGIN and len(row.get("candidates") or []) == 2,
                "4. a paid row has the box name, the slot, cid, the code and two candidates",
                f"row: {row!r}",
            )
            checks.equal((by.get(unserved) or {}).get("code"), match.UNREAD_GAME, "5. a card of a game the reader does not serve answers game_not_served")
            checks.ok(unserved in by and not by[unserved].get("candidates"), "5. and carries no stored reason")
            checks.ok(legacy in by and by[legacy].get("code") is None, "5. a card with a mark from before the change answers no code")
            lists = {name: _sweep_get(port, named, name) for name in ("unread", "matched", "unhinted")}
            checks.equal(_keys_of(lists["unread"]) if "cards" in lists["unread"] else None, {unread}, "6. unread lists the card the reader has not looked at")
            checks.equal(_keys_of(lists["matched"]) if "cards" in lists["matched"] else None, {matched}, "6. matched lists the card with a free row")
            checks.equal(_keys_of(lists["unhinted"]) if "cards" in lists["unhinted"] else None, {unhinted}, "6. and an unhinted card is only in the unhinted list")
            every = [k for a in (paid, *lists.values()) for k in _keys_of(a)]
            checks.ok(len(every) == len(set(every)) == len(named), "6. every card in scope is in exactly one list")
            checks.equal(
                tuple(len(_keys_of(a)) for a in (paid, lists["unread"], lists["matched"])),
                (plain.get("paid"), plain.get("unread"), plain.get("matched_here")),
                "6. the three list sizes equal the band's three figures",
            )
            hint = lists["unhinted"].get("cards") or []
            checks.equal(plain.get("unhinted"), len(hint), "20. detail=unhinted returns exactly the cards the band counts as unhinted")
            checks.ok(
                bool(hint) and all(r.get("box_name") == box_name and r.get("index") and r.get("cid") and not r.get("code") for r in hint),
                "20. an unhinted row has the box name, the slot and cid, and no reason",
            )
            # 15: a claims write moves a paid card to "not yet looked at". It is the existing requeue, proved over the new read.
            capture_server.do_put_card(3, int(paid_a.split("/")[1]), {"set_hint": "sv8"})
            checks.ok("cards" in _sweep_get(port, named, "paid") and paid_a not in _keys_of(_sweep_get(port, named, "paid")), "15. a claims write takes the card out of the paid sheet")
            checks.ok(paid_a in _keys_of(_sweep_get(port, named, "unread")), "15. and puts it in the not-yet-looked-at sheet")
            # 21: a set hint written takes the card out of the set-named sheet.
            capture_server.do_put_card(3, int(unhinted.split("/")[1]), {"set_hint": "sv9"})
            now = _sweep_get(port, named, "unhinted")
            checks.ok("cards" in now and unhinted not in _keys_of(now), "21. a written set hint takes the card out of the set-named sheet")
            checks.equal(now.get("unhinted"), 0, "21. and the health count drops on the next read")


def check_clear_unexplained_once(checks: Checks) -> None:
    from cli import cmd_match

    checks.note("")
    checks.note("BAND SHEETS 22 — the sweep drops every mark with no why once, free, and never again")
    with isolated_home():
        old, kept, aside = (_capture(game="pokemon", set_hint="sv9") for _ in range(3))
        cards = Store().read().inventory.cards
        cid = lambda k: cards[k].capture_id or ""  # noqa: E731
        sweep.remember_tried({old: cid(old), kept: cid(kept)})
        # the record as it was before the change: marks, and no `why` field at all
        sweep._write_json(sweep.tried_path(), {k: v for k, v in _record().items() if k != "why"})
        sweep._write_json(sweep.crash_path(), {"model": matchconst.MODEL_SHA256, "aside": {aside: cid(aside)}})
        _switch(False)  # no chunk runs: the clearing alone is under test
        reads = []
        with mock.patch.object(match, "status", lambda: {"ready": True}), mock.patch.object(match, "Index", _FakeIndex), mock.patch.object(
            match, "read", lambda *a, **k: reads.append(a) or []
        ), mock.patch.object(os, "nice", lambda _n: 0), mock.patch("signal.signal", lambda *_a: None), quiet():
            cmd_match.sweep_worker(lambda _line: None)
        checks.ok("why" in _record(), "22. the first run writes the why field, even when empty")
        checks.ok(old not in (_record().get("keys") or {}) and kept not in (_record().get("keys") or {}), "22. the first run drops every tried mark that has no why entry")
        checks.equal(sweep.aside().get(aside), cid(aside), "22. a set-aside mark stays")
        checks.equal(reads, [], "22. the first run reads nothing and so spends nothing")
        # a record that already carries `why` is never cleared: a mark with a why entry stays, and a second run drops nothing
        _remember(checks, {kept: cid(kept)}, [_unaccepted(kept)], "22. (precondition) a mark with a why entry")
        before = dict(_record().get("keys") or {})
        clear = getattr(sweep, "clear_unexplained", None)
        checks.ok(callable(clear), "22. sweep.clear_unexplained exists")
        if callable(clear):
            clear()
        checks.ok(kept in before and _record().get("keys") == before, "22. a second run drops nothing, and a mark with a why entry stays")


def check_unread_codes_have_groups(checks: Checks) -> None:
    checks.note("")
    checks.note("BAND SHEETS 8 — every UNREAD_* code the free reader can emit has a group in app/src/reasons.ts")
    text = (REPO_ROOT / "app" / "src" / "reasons.ts").read_text("utf-8")
    # `pokemon_needs_a_set` is the unhinted card's code: such a card is never read, so it is in no paid group (10.1, sheet 4).
    codes = {v for k, v in vars(match).items() if k.startswith("UNREAD_") and isinstance(v, str)} - {match.UNREAD_NO_HINT}
    checks.ok(len(codes) >= 10, "8. (precondition) the free reader names its codes")
    for code in sorted(codes):
        checks.ok(f"'{code}'" in text or f'"{code}"' in text, f"8. {code} has a group in reasons.ts")


CHECKS = (
    check_why_kept_with_the_mark,
    check_sweep_detail_reads,
    check_clear_unexplained_once,
    check_unread_codes_have_groups,
    check_claims_correction_requeues,
    check_sweep_queue,
    check_sweep_watcher,
    check_sweep_backoff,
    check_sweep_quiet,
    check_sweep_lock,
    check_sweep_crash,
    check_sweep_crash_stays_free,
    check_run_route_defaults_free,
    check_sweep_runtime_cause,
    check_sweep_cid_guard,
    check_sweep_worker,
    check_reshoot_drops_matcher_row,
    check_sweep_routes,
    check_sweep_sitting_count,
    check_sweep_band_counts,
    check_sweep_band_scope,
    check_sweep_band_aside_is_current,
    check_sweep_imports_light,
)
