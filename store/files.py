"""How this package touches disk: where the store lives, the lock, the atomic replace.

Everything here exists to make one promise true — a crash never leaves a half-written
inventory, and two writers never silently overwrite each other.
"""

from __future__ import annotations

import errno
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

# The store's root. Defaults to the repo, overridable so the inventory and its photos can
# live on a different disk from the code — the same knob D15 gives the image mirror, for
# the same reason: where bulk state lands is the operator's call, not the repo's.
HOME_ENV = "PKMNSCAN_HOME"

INVENTORY_DIRNAME = "inventory"
RUNS_DIRNAME = "runs"
LOCK_NAME = ".lock"

LOCK_TIMEOUT_SECONDS = 30
LOCK_POLL_SECONDS = 0.05

REPO_ROOT = Path(__file__).resolve().parents[1]


class StoreError(RuntimeError):
    """The store could not be read or written."""


class LockTimeout(StoreError):
    """Someone else is holding the store lock. Almost always the capture server."""


def home() -> Path:
    override = os.environ.get(HOME_ENV, "").strip()
    return Path(override).expanduser().resolve() if override else REPO_ROOT


def inventory_dir() -> Path:
    return home() / INVENTORY_DIRNAME


def runs_dir() -> Path:
    return home() / RUNS_DIRNAME


@contextmanager
def exclusive(directory: Path, timeout: float = LOCK_TIMEOUT_SECONDS):
    """Hold the store's exclusive lock, or fail saying who to blame.

    `flock` and not a lock *file whose existence* is the lock: a process that dies holding
    a flock releases it, while a stale lockfile has to be cleaned up by a human who does not
    know whether it is stale.
    """
    import fcntl

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / LOCK_NAME
    handle = open(path, "a+")
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    raise StoreError(f"could not lock {path}: {exc}") from exc
                if time.monotonic() > deadline:
                    raise LockTimeout(
                        f"{path} is locked by another process after {timeout}s — the "
                        f"capture server holds this lock while it writes. Retry, or stop it."
                    )
                time.sleep(LOCK_POLL_SECONDS)
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def write_atomic(path: Path, data: bytes) -> None:
    """Replace `path` whole, or leave the old file entirely intact.

    Temp file in the SAME directory — `os.replace` is only atomic within one filesystem,
    and /tmp is regularly a different one.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with open(temp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except Exception:
        if temp.exists():
            temp.unlink()
        raise


def write_json(path: Path, payload: Any) -> None:
    write_atomic(
        Path(path), (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )


def read_json(path: Path, default: Optional[Any] = None) -> Any:
    path = Path(path)
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError as exc:
        raise StoreError(f"{path} is not valid JSON: {exc}") from exc


def append_jsonl(path: Path, record: Any) -> None:
    """Append one record. Never rewritten, so no atomic dance — just an append and a flush."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: Path):
    path = Path(path)
    if not path.is_file():
        return []
    out = []
    for lineno, line in enumerate(path.read_text("utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise StoreError(f"{path}:{lineno} is not valid JSON: {exc}") from exc
    return out
