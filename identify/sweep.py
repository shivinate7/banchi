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
a card the reader cannot accept is remembered as tried and waits for a press.

THE QUEUE is every card in state `captured`, in a game the matcher serves, with no identifications
row, other than an unhinted Pokemon card (D170: its pool is the whole category) and a card already
tried against this photograph and this model.

GAPS ONLY: the worker starts only when the newest capture is `quiet` seconds old (3 by default),
and the watcher stops it the moment a newer capture arrives. The capture-speed gate
(`scripts/capture-gate.py`) has no pass mark yet, so this stays the rule until the owner sets one.

THE SWITCH is a row in the store's `meta` table (`db.MATCH_SWEEP`), set from the Capture screen's
Setup. The watcher exits when it reads "off". Nothing here downloads: with no model file or no
index the queue is never worked.
"""

from __future__ import annotations

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

QUIET_SECONDS = 3.0
POLL_SECONDS = 5.0
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


def tried_path() -> Path:
    """Cards the reader looked at and did not accept, keyed by position and the photograph's id."""
    return inventory_dir() / "match-sweep-tried.json"


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
    seen = tried()
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


def running_pid() -> Optional[int]:
    """The pid of a live watcher, or None. A stale file whose pid is gone does not count."""
    record = _read_json(state_path())
    pid = record.get("pid") if isinstance(record, dict) else None
    if not isinstance(pid, int) or pid == os.getpid():
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    return pid


def _write_state(**values) -> None:
    _write_json(state_path(), {"pid": os.getpid(), "at": time.time(), **values})


def _spawn_worker() -> "subprocess.Popen":
    return subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "cli", "match", "--sweep-worker"],
        cwd=str(REPO_ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _stop(worker) -> None:
    worker.send_signal(signal.SIGTERM)
    try:
        worker.wait(timeout=STOP_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        worker.kill()
        worker.wait()


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
    if running_pid() is not None:
        return 1
    _write_state(worker=None)
    polls = 0
    backoff_until = 0.0
    while max_polls is None or polls < max_polls:
        polls += 1
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
            _write_state(worker=worker.pid)
            while worker.poll() is None:
                sleep(WATCH_WORKER_SECONDS)
                conn = open_store()
                if conn is None:
                    continue
                try:
                    interrupted = newest_capture(conn) > started or not switched_on(conn)
                finally:
                    conn.close()
                if interrupted:
                    _stop(worker)
                    break
            if worker.returncode == EXIT_NOT_READY:
                backoff_until = now() + NOT_READY_BACKOFF_SECONDS
            _write_state(worker=None)
            continue
        sleep(poll)
    _write_state(worker=None, stopped=True)
    return 0


def watch_main(argv: Sequence[str]) -> int:
    """`match --sweep [--quiet SECONDS]`: the fast path in `cli/__main__.py`, before any heavy import."""
    quiet = QUIET_SECONDS
    if "--quiet" in argv:
        quiet = float(argv[list(argv).index("--quiet") + 1])
    return watch(quiet=quiet)
