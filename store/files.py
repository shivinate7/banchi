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
from typing import Any, Optional, Sequence

# The store's root. Defaults to the repo, overridable so the inventory and its photos can
# live on a different disk from the code — the same knob D15 gives the image mirror, for
# the same reason: where bulk state lands is the operator's call, not the repo's.
HOME_ENV = "PKMNSCAN_HOME"

INVENTORY_DIRNAME = "inventory"
# The pricing corpus (D86). `prices` and not `pricing`, because `runs/<n>/pricing.json` is
# the join's derived TABLE and this is the operator's ANSWER — two files a session will
# otherwise conflate, and one of them is authoritative.
PRICES_NAME = "prices.json"
RUNS_DIRNAME = "runs"
MARKDOWNS_DIRNAME = "markdowns"
LOCK_NAME = ".lock"

# The code ledger (docs/CODES-DECISIONS.md C8): one line per code card, the transcribed
# code beside the position its photograph is keyed by, so a disputed code is looked up and
# its photo re-read by eye. A LEDGER OF UNREDEEMED CODES IS A FILE OF BEARER INSTRUMENTS —
# C8's own sentence — which is why it lives under `inventory/` beside the master store:
# that directory is gitignored whole, never committed, and already holds the one other
# file that must not leave this machine. The runtime writing codes into this gitignored
# file is the sanctioned path; the commit-time opsec rules exist so nothing here ever
# crosses into a tracked one.
CODES_LEDGER_NAME = "codes.jsonl"

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


def codes_ledger_path() -> Path:
    return inventory_dir() / CODES_LEDGER_NAME


def prices_path() -> Path:
    """The pricing corpus — every listing answer this operator has given, keyed by SKU (D86).

    THREE FILES IN THIS REPO ARE ABOUT PRICE AND THEY ARE NOT THE SAME FILE. `runs/<n>/
    pricing.json` is the TABLE a join wrote — what the export said about the cards in one run,
    and it is derived, rewritten on every join, and read-only to a person. `runs/<n>/
    decisions.json` was the per-run ANSWER file and is legacy: `pkmnscan prices adopt` folds
    it in and retires it, and the per-lot override is `policy.per_run` in THIS file.
    This is the ANSWER, once, for every card the operator has ever priced.

    UNDER `inventory/` AND THEREFORE PER CHECKOUT (D43), beside `inventory.json` and the codes
    ledger, because it is the same kind of fact: something this operator decided about their
    own stock, which a worktree must not inherit and must not write into the main tree.
    """
    return inventory_dir() / PRICES_NAME


def markdowns_dir() -> Path:
    """Where a written markdown leaves its import CSV and its receipt (D94).

    UNDER `inventory/` AND NOT `runs/`, and the two reasons are different. A markdown is
    store-wide — it is scoped by a window and a live export, never by a box — so there is no
    run for it to belong to. And `store/__init__.py` declares a run directory disposable:
    *"Deleting a run directory must never cost money or state."* A markdown receipt IS state:
    it is the record of what a listing was asking before the price moved, and the ratchet
    guard reads the corpus stamps it wrote. Put it under `runs/` and a routine cleanup
    silently re-arms a sweep that compounds.
    """
    return inventory_dir() / MARKDOWNS_DIRNAME


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
    handle = open(path, "a+")  # noqa: SIM115 — the flock lives as long as this fd stays open
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
                    ) from exc
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


def upsert_jsonl(path: Path, records: Sequence, key_fields: Sequence[str]) -> None:
    """Replace-or-append by key, rewriting the file whole through the atomic replace.

    For a JSONL that is an INDEX rather than a log — one line per key, latest write wins —
    where `append_jsonl` would accumulate a history nothing reads and every consumer would
    have to learn "last line per key is the truth". The code ledger is the first consumer:
    a re-identified code card replaces its own line, so "one line per code card" stays
    literally true and a lookup needs no dedup rule.

    Existing lines keep their order; replaced lines keep their place; genuinely new keys
    append in the order given. Callers hold the store lock exactly as they would for any
    other write under `inventory/` — this function does not take it for them, because the
    callers that exist are already inside a locked session.
    """

    def key_of(record: Any):
        return tuple(record.get(field) for field in key_fields)

    fresh = {key_of(record): record for record in records}
    out = []
    for record in read_jsonl(path):
        replacement = fresh.pop(key_of(record), None)
        out.append(record if replacement is None else replacement)
    out.extend(fresh.values())
    write_atomic(
        Path(path),
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in out).encode("utf-8"),
    )


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
