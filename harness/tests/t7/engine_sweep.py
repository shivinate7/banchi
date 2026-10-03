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
        checks.equal(sweep.tried(), ids, "with every card of the chunk tried at its capture id")
        checks.ok(not sweep.inflight_path().exists(), "and the inflight file settled")

        sweep.mark_inflight({"9/9": "left-over-1"})
        with mock.patch.object(match, "status", lambda: {"ready": False}), quiet():
            cmd_match.sweep_worker(lambda _line: None)
        checks.equal(sweep.tried().get("9/9"), "left-over-1", "a leftover inflight file is settled as tried at worker start")
        checks.ok(not sweep.inflight_path().exists(), "and removed")
        sweep.mark_inflight({"9/7": "left-over-0"})
        _watch(last=[1000.0], clock=[1001.0], workers=[], polls=1)  # inside the quiet time: no worker
        checks.equal(sweep.tried().get("9/7"), "left-over-0", "a leftover inflight file is settled when the watcher starts")
        sweep.mark_inflight({"9/8": "left-over-2"})
        _watch(last=[0.0], clock=[1000.0], workers=[_Worker(1)], polls=1)
        checks.equal(sweep.tried().get("9/8"), "left-over-2", "a leftover inflight file is settled after a failed worker exit")

        real_popen = subprocess.Popen

        def popen(_argv, **kw):
            real_popen([sys.executable, "-c", "import sys; sys.stderr.write('worker-boom')"],
                       stdout=kw["stdout"], stderr=kw["stderr"]).wait()
            return _Worker()

        with mock.patch.object(sweep.subprocess, "Popen", popen):
            sweep._spawn_worker()
        log = root / ".serve" / "match-sweep.log"
        checks.ok(log.is_file() and "worker-boom" in log.read_text(), "worker stderr lands in .serve/match-sweep.log")


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


CHECKS = (
    check_sweep_queue,
    check_sweep_watcher,
    check_sweep_backoff,
    check_sweep_quiet,
    check_sweep_lock,
    check_sweep_crash,
    check_sweep_cid_guard,
    check_sweep_worker,
    check_reshoot_drops_matcher_row,
    check_sweep_routes,
    check_sweep_imports_light,
)
