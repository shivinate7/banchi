"""The background reader's watcher: `pkmnscan match --sweep` (`docs/specs/identify-engine-pick.md`, section 8).

THE OWNER'S RULING: the free read may run in the background, and always, if its idle memory is
barely any. So it is two processes.

  the watcher   this module. The standard library and `sqlite3` only: no `store` package (about
                17 MB), no numpy, no Pillow, no onnxruntime. It polls the queue and starts a
                worker only while cards wait.
  the worker    `cli/cmd_match.py:sweep_worker`. It loads the model, reads the queue to empty and
                exits, which is what gives the memory back (freeing the session inside one
                process does not).

It lives outside the capture server and takes no request slot. It reads photographs from disk and
writes one thing: an `identifications` row with engine `marqo-b`, through the cache's own `put`,
which never overwrites a Haiku or a cleared row. It never writes card state and it NEVER SPENDS:
a card the reader cannot accept is remembered as tried and waits for a press. A CRASH IS NOT A READ: it never marks a card tried.

THE QUEUE is every card in state `captured`, in a game the matcher serves, with no identifications
row, other than an unhinted Pokemon card (D170: its pool is the whole category) and a card already
tried against this photograph and this model.

EVEN MID-FEED, on the owner's ruling. The capture gate (`scripts/capture-gate.py`) measured a capture
request's p99 at 30.5 ms with the reader on and 30.6 ms with it off, so `QUIET_SECONDS` is 0: the
worker starts as soon as a card waits and is never stopped for a capture. A `quiet` above 0 still
works (`--quiet`): the worker then starts only when the newest capture is that old, and is stopped
at the next one. The measuring script uses it for its other arms.

IT CANNOT CRASH-LOOP. A worker that exits non-zero is waited out for longer each time (30 s doubling
to 30 minutes) and its stderr goes to `.serve/match-sweep.log`. The cards it was reading stay queued
(a crash never moves a card to the paid pile). The next chunk is half the size. A card that crashes a
chunk of one is SET ASIDE: out of the free queue, never tried, never paid, and counted in
`.serve/match-sweep` state as `aside` until it is re-shot or the model changes.

ONE WATCHER, BY ONE LOCK. The watcher holds an `flock` on `inventory/match-sweep.lock` for its whole
life. A held lock is the only thing that reads as running: a pid is reused and a lock is not. The
watcher also writes `.serve/match-sweep.json` (its pid and the lock's path) so `make down` can stop it
from the tree alone, and a reap owner mark so `make reap` stops it and its worker (D305).
It exits when its store or its tree is gone, and a SIGTERM stops the worker first.

THE SWITCH is a row in the store's `meta` table (`db.MATCH_SWEEP`), set from the Capture screen's
Setup. The watcher exits when it reads "off". Nothing here downloads: with no model file or no
index the queue is never worked.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from identify.matchconst import MODEL_BYTES, MODEL_FILENAME, MODEL_SHA256, REPO_ROOT, SERVED_GAMES, inventory_dir

QUIET_SECONDS = 0.0
POLL_SECONDS = 5.0
# The wait after a worker exits non-zero: this, doubled for each one in a row, up to the cap.
FAILURE_BACKOFF_SECONDS = 30.0
FAILURE_BACKOFF_CAP_SECONDS = 1800.0
# The worker's log is rotated once it passes this.
LOG_MAX_BYTES = 1_000_000
# How long the watcher waits for a stopped worker before it kills it.
STOP_GRACE_SECONDS = 5.0
# How often the watcher looks for a newer capture while a worker runs.
WATCH_WORKER_SECONDS = 0.5
# The worker's exit code for "the model file or the index is not ready", and how long the watcher
# leaves the queue alone after it. The press that prepares the reader is the owner's.
EXIT_NOT_READY = 3
NOT_READY_BACKOFF_SECONDS = 300.0
# `db.MATCH_SWEEP` and `db.DB_NAME`, spelled here because `store.db` cannot be imported (see above).
# `cli/selftest` cases keep the copies equal.
META_KEY = "match_sweep"
DB_FILENAME = "store.sqlite"
INDEX_FILENAME = "fingerprints.sqlite"


def state_path() -> Path:
    """The watcher's pid and last figures. Derived data beside the store, like the index."""
    return inventory_dir() / "match-sweep.json"


def lock_path() -> Path:
    return inventory_dir() / "match-sweep.lock"


def inflight_path() -> Path:
    """The cards the worker is reading right now. A worker that dies mid-chunk leaves it behind."""
    return inventory_dir() / "match-sweep-inflight.json"


def serve_dir() -> Path:
    """`.serve/` of the tree this code runs from: the log, the pid file, the reap marks."""
    return REPO_ROOT / ".serve"


def log_path() -> Path:
    return serve_dir() / "match-sweep.log"


def tried_path() -> Path:
    """Cards the reader looked at and did not accept, keyed by position and the photograph's id."""
    return inventory_dir() / "match-sweep-tried.json"


def crash_path() -> Path:
    """The chunk size after a crash, and the cards set aside for crashing a chunk of one."""
    return inventory_dir() / "match-sweep-crash.json"


def _crash_record() -> dict:
    record = _read_json(crash_path())
    if not isinstance(record, dict) or record.get("model") != MODEL_SHA256:
        return {"aside": {}}
    return record


def aside() -> Dict[str, str]:
    keys = _crash_record().get("aside")
    return {str(k): str(v) for k, v in keys.items()} if isinstance(keys, dict) else {}


def chunk_limit(default: int) -> int:
    """The worker's chunk size: `default`, or half the chunk that last crashed."""
    chunk = _crash_record().get("chunk")
    return min(default, chunk) if isinstance(chunk, int) and chunk >= 1 else default


def reset_chunk() -> None:
    record = _crash_record()
    if "chunk" in record:
        record.pop("chunk")
        _write_json(crash_path(), {"model": MODEL_SHA256, **{k: v for k, v in record.items() if k != "model"}})


def _read_json(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = path.with_name(path.name + f".{os.getpid()}.tmp")
    scratch.write_text(json.dumps(value, sort_keys=True), "utf-8")
    os.replace(scratch, path)


# ----------------------------------------------------------------------------- the queue


def open_store() -> Optional[sqlite3.Connection]:
    """A read-only connection onto the store, or None when it cannot be opened this moment.

    PLAIN `mode=ro`, and a failure is "try again at the next poll". `store.db.open_read_only` is
    the careful door but lives in the heavy package. A store the capture server is using opens
    here; the cold, fully committed file may not, and a watcher with nothing to do loses nothing."""
    path = inventory_dir() / DB_FILENAME
    if not path.is_file():
        return None
    try:
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return None


def switched_on(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute("select value from meta where key = ?", (META_KEY,)).fetchone()
    except sqlite3.Error:
        return False
    return bool(row) and row[0] == "on"


def tried() -> Dict[str, str]:
    record = _read_json(tried_path())
    if not isinstance(record, dict) or record.get("model") != MODEL_SHA256:
        return {}
    keys = record.get("keys")
    return {str(k): str(v) for k, v in keys.items()} if isinstance(keys, dict) else {}


def remember_tried(additions: Dict[str, str]) -> None:
    if not additions:
        return
    keys = tried()
    keys.update(additions)
    _write_json(tried_path(), {"model": MODEL_SHA256, "keys": keys})


_QUEUE_SQL = (
    "select c.key, coalesce(c.capture_id, '') from cards c "
    "where c.state = 'captured' "
    "and coalesce(c.game, 'pokemon') in ({games}) "
    "and not (coalesce(c.game, 'pokemon') = 'pokemon' and trim(coalesce(c.set_hint, '')) = '') "
    "and not exists (select 1 from identifications i where i.key = c.key) "
    "order by c.captured_at, c.key"
)


def queue(conn: sqlite3.Connection, limit: Optional[int] = None) -> List[Tuple[str, str]]:
    """`(position key, capture id)` of the cards waiting, oldest first, minus those already tried."""
    marks = ",".join("?" for _ in SERVED_GAMES)
    seen = {**aside(), **tried()}
    out: List[Tuple[str, str]] = []
    for key, capture_id in conn.execute(_QUEUE_SQL.format(games=marks), tuple(SERVED_GAMES)):
        if seen.get(key) == capture_id:
            continue
        out.append((key, capture_id))
        if limit is not None and len(out) >= limit:
            break
    return out


def newest_capture(conn: sqlite3.Connection) -> float:
    """The epoch second of the newest capture, 0 when there is none."""
    row = conn.execute("select max(captured_at) from cards").fetchone()
    if not row or not row[0]:
        return 0.0
    try:
        return datetime.fromisoformat(str(row[0])).timestamp()
    except ValueError:
        return 0.0


def files_present() -> bool:
    """A cheap look for the model file and the index, without hashing 372 MB. The worker checks
    the hash and that the index was built by this model, and says so when it fails."""
    model = inventory_dir() / "models" / MODEL_FILENAME
    try:
        return model.stat().st_size == MODEL_BYTES and (inventory_dir() / INDEX_FILENAME).is_file()
    except OSError:
        return False


# --------------------------------------------------------------------------- the watcher


def acquire_lock():
    """The open lock file with `flock` held, or None when another process holds it."""
    import fcntl

    lock_path().parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path(), "a+")  # noqa: SIM115 - held for the watcher's life
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def running() -> bool:
    """Whether a watcher is alive: the lock is held. A reused pid cannot read as running."""
    handle = acquire_lock()
    if handle is None:
        return True
    handle.close()  # closing releases the flock
    return False


def running_pid() -> Optional[int]:
    """The live watcher's pid, from its state file, or None when no lock is held."""
    if not running():
        return None
    record = _read_json(state_path())
    pid = record.get("pid") if isinstance(record, dict) else None
    return pid if isinstance(pid, int) else None


def _write_state(**values) -> None:
    _write_json(state_path(), {"pid": os.getpid(), "at": time.time(), **values})


def _write_serve_file(lock: Path) -> None:
    """`.serve/match-sweep.json`: what `make down` needs to stop this watcher from the tree alone."""
    _write_json(serve_dir() / "match-sweep.json", {"pid": os.getpid(), "lock": str(lock)})


def _mark_for_reap() -> None:
    """The reap owner mark (D305), so `make reap` stops this watcher and, through its descendants,
    its worker. Fails open: a watcher that cannot be marked still runs, untagged."""
    try:
        scripts = str(REPO_ROOT / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        import reap_mark

        reap_mark.write_mark(str(REPO_ROOT), os.getpid(), "match-sweep")
    except Exception:  # noqa: BLE001
        pass


def stop_watcher_of(root: Path) -> Optional[int]:
    """`make down`'s half: SIGTERM the watcher of the tree `root` if its lock is held. The pid it
    stopped, or None. It trusts the lock and not the pid, so a reused pid is never signalled."""
    import fcntl

    record = _read_json(Path(root) / ".serve" / "match-sweep.json")
    if not isinstance(record, dict) or not isinstance(record.get("pid"), int):
        return None
    try:
        handle = open(record["lock"], "a+")  # noqa: SIM115
    except (OSError, KeyError, TypeError):
        return None
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        pid = record["pid"]  # held: this watcher is alive
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return None
        return pid
    finally:
        handle.close()
    return None


def _open_log():
    serve_dir().mkdir(parents=True, exist_ok=True)
    path = log_path()
    try:
        if path.stat().st_size > LOG_MAX_BYTES:
            os.replace(path, path.with_name(path.name + ".1"))
    except OSError:
        pass
    return open(path, "ab")  # noqa: SIM115 - handed to the worker


def _spawn_worker() -> "subprocess.Popen":
    log = _open_log()
    try:
        return subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", "cli", "match", "--sweep-worker"],
            cwd=str(REPO_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    finally:
        log.close()  # the child holds its own copy


def _stop(worker) -> None:
    worker.send_signal(signal.SIGTERM)
    try:
        worker.wait(timeout=STOP_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        worker.kill()
        worker.wait()


def settle_inflight(crashed: bool = False) -> int:
    """Settle the chunk a dead worker was reading. A crash is not a read, so no card is tried.

    ONLY `crashed=True` counts: the watcher saw a worker exit that our own stop did not cause, or the
    worker caught its own exception. The chunk is then halved, and a chunk of one is set aside (see
    `aside`). Any other leftover (our stop, a server restart, a dead watcher) is an interruption: the
    file is removed and the chunk is retried whole.

    The worker writes the chunk it is about to read and clears it afterwards. A file still here
    belongs to a worker that died inside the chunk (a crash, an out-of-memory kill). Returns how
    many cards it settled."""
    record = _read_json(inflight_path())
    if not isinstance(record, dict) or record.get("model") != MODEL_SHA256:
        with_error = inflight_path()
        if with_error.exists():
            with_error.unlink()
        return 0
    keys = record.get("keys")
    settled = {str(k): str(v) for k, v in keys.items()} if isinstance(keys, dict) else {}
    record = _crash_record()
    if not crashed:
        pass
    elif len(settled) == 1:
        record["aside"] = {**aside(), **settled}
        record.pop("chunk", None)
    elif settled:
        record["chunk"] = max(1, len(settled) // 2)
    _write_json(crash_path(), {**record, "model": MODEL_SHA256})
    inflight_path().unlink()
    return len(settled)


def mark_inflight(keys: Dict[str, str]) -> None:
    _write_json(inflight_path(), {"model": MODEL_SHA256, "keys": keys})


def clear_inflight() -> None:
    with contextlib.suppress(OSError):
        inflight_path().unlink()


def _gone() -> bool:
    """Whether the store or the tree this watcher serves is gone."""
    return not REPO_ROOT.exists() or not (inventory_dir() / DB_FILENAME).is_file()


def watch(
    quiet: float = QUIET_SECONDS,
    poll: float = POLL_SECONDS,
    *,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.time,
    spawn: Callable[[], "subprocess.Popen"] = _spawn_worker,
    max_polls: Optional[int] = None,
) -> int:
    """Poll the queue until the switch reads off. Returns 0, or 1 when another watcher runs."""
    lock = acquire_lock()
    if lock is None:
        return 1
    import threading

    current: list = []
    previous = None
    if threading.current_thread() is threading.main_thread():
        def terminate(_signum, _frame):
            # THE WORKER FIRST, then the watcher: a watcher that dies and leaves its worker would
            # leave a 900 MB process that nothing is polling.
            if current and current[0].poll() is None:
                _stop(current[0])
            raise SystemExit(0)

        previous = signal.signal(signal.SIGTERM, terminate)
    try:
        _write_state(worker=None)
        _write_serve_file(lock_path())
        _mark_for_reap()
        settle_inflight()
        polls = 0
        backoff_until = 0.0
        failures = 0
        while max_polls is None or polls < max_polls:
            polls += 1
            if _gone():
                break
            conn = open_store()
            if conn is None:
                sleep(poll)
                continue
            try:
                if not switched_on(conn):
                    break
                waiting = bool(queue(conn, limit=1))
                last = newest_capture(conn)
            finally:
                conn.close()
            if waiting and now() >= backoff_until and now() - last >= quiet and files_present():
                started = now()
                worker = spawn()
                current[:] = [worker]
                _write_state(worker=worker.pid)
                stopped_by_us = False
                while worker.poll() is None:
                    sleep(WATCH_WORKER_SECONDS)
                    conn = open_store()
                    if conn is None:
                        if _gone():
                            _stop(worker)
                            stopped_by_us = True
                            break
                        continue
                    try:
                        interrupted = (quiet > 0 and newest_capture(conn) > started) or not switched_on(conn)
                    finally:
                        conn.close()
                    if interrupted:
                        _stop(worker)
                        stopped_by_us = True
                        break
                current[:] = []
                code = worker.returncode
                if code == EXIT_NOT_READY:
                    backoff_until = now() + NOT_READY_BACKOFF_SECONDS
                elif code != 0 and not stopped_by_us:
                    # EVERY OTHER FAILURE WAITS LONGER EACH TIME, and the next chunk is smaller, so
                    # a bad photograph ends up alone and set aside. Never tried, never paid.
                    settle_inflight(crashed=True)
                    delay = min(FAILURE_BACKOFF_CAP_SECONDS, FAILURE_BACKOFF_SECONDS * (2 ** failures))
                    failures += 1
                    backoff_until = now() + delay
                else:
                    failures = 0
                    if stopped_by_us:
                        clear_inflight()  # our stop is not a crash: retry the chunk whole
                _write_state(worker=None)
                continue
            sleep(poll)
        _write_state(worker=None, stopped=True)
        return 0
    finally:
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)
        lock.close()


def watch_main(argv: Sequence[str]) -> int:
    """`match --sweep [--quiet SECONDS]`: the fast path in `cli/__main__.py`, before any heavy import."""
    quiet = QUIET_SECONDS
    if "--quiet" in argv:
        quiet = float(argv[list(argv).index("--quiet") + 1])
    return watch(quiet=quiet)
