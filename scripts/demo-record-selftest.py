#!/usr/bin/env python3
"""`scripts/demo-record.py`'s `Server`, proved against the hang measured 2026-09-26.

Protects: The demo recorder's child server never hangs on a full output pipe during a long sweep.

WHAT HUNG. `CaptureHandler.log_message` (`server/capture_server.py`) prints one line per
request. `Server.__enter__` piped the child's stdout (`subprocess.PIPE`) but read it only
once, at startup — for the rest of a real sweep (thousands of requests) nothing ever
drained it. Once the OS pipe buffer filled, the child's next `print()` blocked in `write()`
forever, and every OTHER worker thread's next `print()` blocked behind it too (CPython's
stdout stream lock) — measured with `sample <pid>` on the real hung build: one thread in
`write()`, the rest of `REQUEST_SLOTS` in `PyThread_acquire_lock_timed`. `get()`/`post()`
then silently swallowed the resulting client-side timeout into `(None, ...)`, so the sweep
kept issuing doomed requests forever with no visible failure.

TWO THINGS THIS PROVES, EACH BY VIOLATING IT FIRST. `_undrained_pipe_deadlocks` shows the
mechanism is real: a child that prints past the OS pipe buffer with nobody reading it does
not exit in time. `_drain_prevents_it` shows `Server`'s own drain thread is what fixes that,
on the same child. `_loud_on_network_failure` shows `get`/`post` now raise instead of
returning `(None, ...)` when the request never completes at all — a `SystemExit` a test can
catch, never a silent hole in the recorded bundle.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# Hyphenated filename: `import scripts.demo-record` is not valid Python, loaded the way
# `scripts/demo-determinism-selftest.py` loads its own hyphenated sibling.
_SPEC = importlib.util.spec_from_file_location(
    "demo_record", ROOT / "scripts" / "demo-record.py"
)
demo_record = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(demo_record)

PASS = 0
FAIL = 0


def ok(condition: bool, label: str, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok     {label}")
    else:
        FAIL += 1
        print(f"  FAIL   {label}  {detail}")


# A print() per line, well past a 64KB pipe buffer, and never a status the harness waits
# on — the shape of a real sweep's request logging, compressed into one child process.
FLOOD = "for _ in range(20000): print('x' * 60)"


def _undrained_pipe_deadlocks() -> None:
    """Without a reader, the child blocks in `write()` and never exits — the bug itself."""
    proc = subprocess.Popen(
        [sys.executable, "-c", FLOOD], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    try:
        try:
            proc.wait(timeout=3)
            ok(False, "undrained pipe deadlocks (mechanism check)",
               "child exited on its own — this test no longer proves what it claims to")
        except subprocess.TimeoutExpired:
            ok(True, "undrained pipe deadlocks (mechanism check)")
    finally:
        proc.kill()
        proc.wait(timeout=5)


def _drain_prevents_it() -> None:
    """The same flood, through `Server`'s own drain thread, must finish quickly."""
    server = demo_record.Server(home=Path("unused"), port=0)
    server.process = subprocess.Popen(
        [sys.executable, "-c", FLOOD], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    server._drain_thread = threading.Thread(target=server._drain_stdout, daemon=True)
    server._drain_thread.start()
    start = time.time()
    try:
        server.process.wait(timeout=10)
        elapsed = time.time() - start
        ok(True, "Server._drain_stdout lets the same child finish (%.1fs)" % elapsed)
    except subprocess.TimeoutExpired:
        ok(False, "Server._drain_stdout lets the same child finish",
           "still blocked after 10s — the drain thread did not unstick it")
        server.process.kill()
    server._drain_thread.join(timeout=5)
    ok(len(server._log) <= 500, "drained log stays bounded", "len=%d" % len(server._log))


def _loud_on_network_failure() -> None:
    """A request that never completes (timeout, reset, refused) must raise, not vanish."""
    server = demo_record.Server(home=Path("unused"), port=1)  # nothing listens on :1

    def urlopen_raises(*_a, **_k):
        raise demo_record.urllib.error.URLError("connection refused (test)")

    real_urlopen = demo_record.urllib.request.urlopen
    demo_record.urllib.request.urlopen = urlopen_raises
    try:
        try:
            server.get("/status")
            ok(False, "get() raises on a network failure", "returned instead of raising")
        except SystemExit:
            ok(True, "get() raises on a network failure")
        try:
            server.post("/status", {})
            ok(False, "post() raises on a network failure", "returned instead of raising")
        except SystemExit:
            ok(True, "post() raises on a network failure")
    finally:
        demo_record.urllib.request.urlopen = real_urlopen


def main() -> int:
    _undrained_pipe_deadlocks()
    _drain_prevents_it()
    _loud_on_network_failure()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
