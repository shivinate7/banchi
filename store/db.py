"""The store of record is one SQLite file, and a session is one transaction (D88).

    inventory/
      store.sqlite          MASTER. Every table below, in one file, written in one
                            transaction per `Store.write()`.
      store.sqlite-wal      SQLite's write-ahead log, beside it. Never touch either by hand
      store.sqlite-shm      while a server is up; both are the database.
      legacy-json/          the five JSON files and history.jsonl this store was migrated
                            FROM, moved here whole on the first open and never read again.
                            They are the reversible export D10's v1->v2 treatment asks for.

WHY A DATABASE, WHEN THE FILES WERE ATOMIC. Each JSON file was replaced atomically on its
own and the SET of five was not one transaction — `store/session.py` said so in its header
for a week and called closing it "a decision nobody has argued". A kill between two
`write_json` calls left the inventory saying one thing and a queue that was meant to move
with it saying another, and the exposure was Ctrl-C frequency rather than theoretical.
`BEGIN IMMEDIATE ... COMMIT` over every table is what closes it, and nothing narrower
does. The write cost D88 measured — every capture re-serialising and fsyncing the whole
store, crossing the feeder's cadence at ~48,000 cards — is the second argument, and it is
second on purpose: write-behind would have fixed that alone, at the cost of durability on
data that names photographs nothing can regenerate.

ONE PAYLOAD COLUMN PER ROW, WITH A FEW INDEXED COLUMNS BESIDE IT. Every record is stored
whole as JSON text in `payload`, exactly the dict `asdict` produces, so the dataclasses
under `store/` gain and lose fields the way they always have — `Inventory.parse` filters
on `__annotations__` and this file never has to learn a field's name. The indexed columns
(`box`, `idx`, `sku`, `capture_id`, `state`...) are DERIVED from the object at write time
by each `TableSpec.columns`, so they cannot disagree with the payload, and they are what
`Rows.where`/`select` filter on and what a person queries with the `sqlite3` CLI:

    sqlite3 inventory/store.sqlite "select key, name, state from cards where box = 3"
    sqlite3 inventory/store.sqlite "select payload from events where position = '3/17'"

THE FLOCK STAYS, AND THE TRANSACTION IS INSIDE IT. `files.exclusive` guards more than these
tables: callers unlink photographs, rename sidecars and upsert `codes.jsonl` inside
`Store.write()` on the strength of that lock, and none of that is in a table. So the lock
is still the store-wide writer's lock, and the transaction is what makes the tables' part
of a session all-or-nothing. `busy_timeout` mirrors `LOCK_TIMEOUT_SECONDS` for the one
contention the flock cannot see, a checkpoint.

WAL, `synchronous=FULL`. Readers never block the writer and the writer never blocks a
reader, which is what lets `Store.read()` stay lock-free; FULL keeps the durability the
per-file fsync had — every commit reaches the disk before the request answers — measured
rather than assumed, and the number is in D88.

THE LEGACY IMPORT RUNS ONCE, ON THE FIRST OPEN, UNDER THE LOCK, AND MOVES THE FILES ASIDE.
It is lossless — `Inventory.parse` (which still carries the v1->v2 card-state migration)
reads the file exactly as `Store.read()` used to, and every record lands as a row — and it
is REVERSIBLE: delete `store.sqlite*` and move `legacy-json/*` back up one level, and the
store is byte-for-byte what it was. A legacy file beside a live database is NEVER read as
a fallback (D86's rule): `make status` reports one, this module ignores it.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from store import files
from store.rows import Rows, payload_text

DB_NAME = "store.sqlite"
LEGACY_DIRNAME = "legacy-json"
RECEIPT_NAME = "MIGRATED.json"
SCHEMA_VERSION = 1

# The six files a legacy store is made of, and the one that is a log rather than a document.
LEGACY_INVENTORY = "inventory.json"
LEGACY_CACHE = "identifications.json"
LEGACY_REVIEW = "review.json"
LEGACY_PARKED = "parked.json"
LEGACY_ORDERS = "orders.json"
LEGACY_HISTORY = "history.jsonl"
LEGACY_FILES = (
    LEGACY_INVENTORY,
    LEGACY_CACHE,
    LEGACY_REVIEW,
    LEGACY_PARKED,
    LEGACY_ORDERS,
    LEGACY_HISTORY,
)

# Table -> indexed columns. The `payload` column and the key are implied. Column VALUES come
# from each dataclass module's `TableSpec.columns`; this is only the DDL's word for them.
TABLES: Dict[str, Tuple[str, ...]] = {
    "cards": (
        "box", "idx", "state", "sku", "condition", "capture_id", "name", "number", "game",
        "set_hint", "run", "captured_at", "state_at",
    ),
    "boxes": ("box", "name", "state"),
    "listings": ("condition", "pushed", "staged", "live"),
    "identifications": ("photo_sha256", "cleared_by_human", "at"),
    "queues": ("box", "idx", "reason", "cleared_by_human", "first_seen"),
    "orders": ("source", "number", "status"),
    "fulfilment": (),
}

_INTEGER = {"box", "idx", "pushed", "staged", "live", "cleared_by_human"}

_INDEXES = (
    ("cards", "box"), ("cards", "sku"), ("cards", "capture_id"), ("cards", "state"),
    ("cards", "idx"),
    ("queues", "box"),
    ("events", "position"),
)


def path(directory: Path) -> Path:
    return Path(directory) / DB_NAME


def legacy_dir(directory: Path) -> Path:
    return Path(directory) / LEGACY_DIRNAME


def legacy_present(directory: Path) -> List[str]:
    """The legacy JSON files sitting in `directory` itself — not in `legacy-json/`."""
    return [name for name in LEGACY_FILES if (Path(directory) / name).is_file()]


# --------------------------------------------------------------------------- schema


def _ddl(table: str, columns: Sequence[str]) -> str:
    typed = ", ".join(
        f"{name} {'INTEGER' if name in _INTEGER else 'TEXT'}" for name in columns
    )
    if table == "queues":
        return (
            f"CREATE TABLE IF NOT EXISTS {table} (queue TEXT NOT NULL, key TEXT NOT NULL, "
            f"{typed}, payload TEXT NOT NULL, PRIMARY KEY (queue, key))"
        )
    body = f"key TEXT PRIMARY KEY, {typed}, " if columns else "key TEXT PRIMARY KEY, "
    return f"CREATE TABLE IF NOT EXISTS {table} ({body}payload TEXT NOT NULL)"


def _schema_present(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'meta'"
    ).fetchone()
    if row is None:
        return False
    stored = conn.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()
    return stored is not None and str(stored[0]) == str(SCHEMA_VERSION)


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the tables once. A READ-ONLY CHECK ON EVERY LATER OPEN, and that matters:
    `Store(snapshot.directory).history()` opens a second connection inside a write
    session, and a DDL or an `INSERT OR IGNORE` here would be a second writer waiting
    on the first until `busy_timeout` — measured as a 30-second stall on the first sale
    T7 recorded after D88."""
    if _schema_present(conn):
        return
    for table, columns in TABLES.items():
        conn.execute(_ddl(table, columns))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "at TEXT, event TEXT, position TEXT, payload TEXT NOT NULL)"
    )
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    for table, column in _INDEXES:
        conn.execute(f"CREATE INDEX IF NOT EXISTS {table}_{column} ON {table}({column})")
    conn.execute(
        "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema', ?)", (str(SCHEMA_VERSION),)
    )


def _open(db_path: Path) -> sqlite3.Connection:
    # `isolation_level=None` is autocommit: this module issues BEGIN/COMMIT itself, so a
    # transaction is exactly as wide as `Store.write()` says and never as wide as the
    # sqlite3 module guesses from the first statement it sees.
    conn = sqlite3.connect(str(db_path), isolation_level=None, timeout=files.LOCK_TIMEOUT_SECONDS)
    conn.execute(f"PRAGMA busy_timeout = {int(files.LOCK_TIMEOUT_SECONDS * 1000)}")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = FULL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def connect(directory: Path, *, locked: bool = False) -> sqlite3.Connection:
    """The store's database, created empty or imported from the legacy files on first open.

    `locked` says the caller already holds `files.exclusive` — `Store.write()` does — and
    the import must not take it again: an flock is held per open file description, so a
    second handle in the same process would wait on the first until the timeout.
    """
    directory = Path(directory)
    db_path = path(directory)
    if not db_path.is_file():
        directory.mkdir(parents=True, exist_ok=True)
        if legacy_present(directory):
            _import_legacy(directory, locked=locked)
    conn = _open(db_path)
    _ensure_schema(conn)
    return conn


# --------------------------------------------------------------------------- source


class SqliteSource:
    """`store/rows.py`'s `Source` over one table. The only thing here that names a table."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        table: str,
        columns: Sequence[str],
        fixed: Optional[Dict[str, Any]] = None,
    ):
        self.conn = conn
        self.table = table
        self.columns = tuple(columns)
        # A composite-keyed table (`queues`) is one `Rows` per fixed value: every query
        # carries `queue = ?` and every write stores it.
        self.fixed = dict(fixed or {})

    def _where(self, equals: Dict[str, Any]) -> Tuple[str, list]:
        clauses, params = [], []
        for name, value in list(self.fixed.items()) + list(equals.items()):
            if name not in self.columns and name not in self.fixed:
                raise KeyError(f"{self.table} has no indexed column {name!r}")
            if value is None:
                clauses.append(f"{name} IS NULL")
            else:
                clauses.append(f"{name} = ?")
                params.append(value)
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params

    def get(self, key: str) -> Optional[str]:
        where, params = self._where({})
        where = (where + " AND " if where else " WHERE ") + "key = ?"
        row = self.conn.execute(
            f"SELECT payload FROM {self.table}{where}", params + [str(key)]
        ).fetchone()
        return None if row is None else row[0]

    def has(self, key: str) -> bool:
        where, params = self._where({})
        where = (where + " AND " if where else " WHERE ") + "key = ?"
        return self.conn.execute(
            f"SELECT 1 FROM {self.table}{where}", params + [str(key)]
        ).fetchone() is not None

    def count(self) -> int:
        where, params = self._where({})
        return int(self.conn.execute(f"SELECT COUNT(*) FROM {self.table}{where}", params).fetchone()[0])

    def all(self) -> Iterable[Tuple[str, str]]:
        where, params = self._where({})
        return self.conn.execute(
            f"SELECT key, payload FROM {self.table}{where} ORDER BY key", params
        ).fetchall()

    def where(self, equals: Dict[str, Any]) -> Iterable[Tuple[str, str]]:
        where, params = self._where(equals)
        return self.conn.execute(
            f"SELECT key, payload FROM {self.table}{where} ORDER BY key", params
        ).fetchall()

    def select(self, columns: Sequence[str], equals: Dict[str, Any]) -> Iterable[Tuple[str, tuple]]:
        for name in columns:
            if name not in self.columns:
                raise KeyError(f"{self.table} has no indexed column {name!r}")
        where, params = self._where(equals)
        wanted = ", ".join(columns)
        rows = self.conn.execute(
            f"SELECT key, {wanted} FROM {self.table}{where} ORDER BY key", params
        ).fetchall()
        return [(row[0], tuple(row[1:])) for row in rows]

    def distinct(self, column: str) -> Iterable[Any]:
        if column not in self.columns:
            raise KeyError(f"{self.table} has no indexed column {column!r}")
        where, params = self._where({})
        return [row[0] for row in self.conn.execute(
            f"SELECT DISTINCT {column} FROM {self.table}{where}", params
        ).fetchall()]

    # ----------------------------------------------------------------- the writes

    def upsert(self, key: str, columns: Dict[str, Any], payload: dict) -> None:
        names = list(self.fixed) + ["key"] + list(self.columns) + ["payload"]
        values = list(self.fixed.values()) + [str(key)]
        values += [columns.get(name) for name in self.columns]
        values.append(payload_text(payload))
        marks = ", ".join("?" for _ in names)
        self.conn.execute(
            f"INSERT OR REPLACE INTO {self.table} ({', '.join(names)}) VALUES ({marks})", values
        )

    def delete(self, key: str) -> None:
        where, params = self._where({})
        where = (where + " AND " if where else " WHERE ") + "key = ?"
        self.conn.execute(f"DELETE FROM {self.table}{where}", params + [str(key)])


def source(conn: sqlite3.Connection, table: str, fixed: Optional[Dict[str, Any]] = None) -> SqliteSource:
    return SqliteSource(conn, table, TABLES[table], fixed)


# ---------------------------------------------------------------------------- flush


def flush_rows(rows: Rows) -> Tuple[int, int]:
    """Write one mapping's diff through its own source. `(deleted, upserted)`."""
    src = rows.source
    if src is None:
        raise files.StoreError(f"{rows.spec.name} is not bound to the database")
    deleted, upserts = rows.changes()
    for key in deleted:
        src.delete(key)
    for key, columns, payload in upserts:
        src.upsert(key, columns, payload)
    rows.flushed(upserts)
    return len(deleted), len(upserts)


def append_events(conn: sqlite3.Connection, events: Iterable[dict]) -> int:
    count = 0
    for event in events:
        conn.execute(
            "INSERT INTO events (at, event, position, payload) VALUES (?, ?, ?, ?)",
            (
                event.get("at"),
                event.get("event"),
                event.get("position"),
                json.dumps(event, sort_keys=True),
            ),
        )
        count += 1
    return count


def history(conn: sqlite3.Connection) -> List[dict]:
    """Every event, in the order it was written. Refuses the whole log over one bad row.

    `files.read_jsonl`'s rule carried over unchanged: a log with a row that will not parse is
    a log that cannot be trusted about what it does say, and the readers that depend on it
    — the sale and retirement reversals — already degrade to "origin unknown" rather than
    guessing (`server/capture_server.py:_origin`). The message names the row so a person
    with the `sqlite3` CLI can find it.
    """
    out = []
    for row_id, text in conn.execute("SELECT id, payload FROM events ORDER BY id").fetchall():
        try:
            out.append(json.loads(text))
        except ValueError as exc:
            raise files.StoreError(
                f"history event {row_id} in {DB_NAME} is not valid JSON: {exc}"
            ) from exc
    return out


def events_named(conn: sqlite3.Connection, event: str) -> List[dict]:
    """Every event of one name, newest first. `history`'s narrower sibling (D133).

    `#/graveyard` wants only `buried` lines, not a full-table load and filter in Python —
    `history()` stays the reversal readers' full scan (`_state_before_sale` and its twin
    need the whole ordered sequence to find the line just before the one they are asked
    about), and this is the read a screen makes instead. The `event` column already exists
    for `append_events`' own denormalised copy of the payload's `event` key; no new column,
    no new index — the events table has none of its own and this repo has no schema
    migration to add one to a store already on disk, so a `WHERE event = ?` here is an
    unindexed scan, the same shape `history()` already is over the whole table. Same
    one-bad-row refusal as `history()`, for the same reason.
    """
    out = []
    rows = conn.execute(
        "SELECT id, payload FROM events WHERE event = ? ORDER BY id DESC", (event,)
    ).fetchall()
    for row_id, text in rows:
        try:
            out.append(json.loads(text))
        except ValueError as exc:
            raise files.StoreError(
                f"history event {row_id} in {DB_NAME} is not valid JSON: {exc}"
            ) from exc
    return out


def dump_tables(conn: sqlite3.Connection) -> Dict[str, List[tuple]]:
    """Every table's rows, ordered. What T7 compares where it used to compare file bytes."""
    out: Dict[str, List[tuple]] = {}
    for table in list(TABLES) + ["events"]:
        order = "id" if table == "events" else ("queue, key" if table == "queues" else "key")
        out[table] = conn.execute(f"SELECT * FROM {table} ORDER BY {order}").fetchall()
    return out


# ------------------------------------------------------------------ the legacy import


@contextmanager
def _already_locked():
    yield


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _import_legacy(directory: Path, *, locked: bool = False) -> None:
    """Build `store.sqlite` from the legacy JSON files, then move them to `legacy-json/`.

    ORDER IS THE SAFETY. The database is built under a temporary name, filled inside one
    transaction, and renamed into place with `os.replace` BEFORE any legacy file moves; a
    crash at any point before the rename leaves the JSON files exactly where they were and
    a stray `.migrating` file this function deletes on the next attempt. A crash between the
    rename and the move leaves both in place, which `make status` reports and this module
    resolves by never reading the JSON again.

    Deferred imports of the dataclass modules, because `store/master.py` must not be an
    import-time dependency of the module that opens the file it is stored in.
    """
    from store.cache import Cache
    from store.master import Inventory
    from store.orders import Ledger
    from store.queues import MAIN, PARKED, Queue

    directory = Path(directory)
    with (_already_locked() if locked else files.exclusive(directory)):
        db_path = path(directory)
        if db_path.is_file():
            return  # somebody else got here first, under the same lock
        staging = db_path.with_name(db_path.name + ".migrating")
        for stray in (staging, Path(str(staging) + "-wal"), Path(str(staging) + "-shm")):
            if stray.exists():
                stray.unlink()

        sources = {name: directory / name for name in legacy_present(directory)}

        def document(name: str):
            # A store that never had a queue, a cache or an order feed has no such file,
            # and `Store.read()` always read an absent one as empty.
            return files.read_json(sources[name]) if name in sources else None

        inventory = Inventory.parse(document(LEGACY_INVENTORY))
        cache = Cache.parse(document(LEGACY_CACHE))
        review = Queue.parse(MAIN, document(LEGACY_REVIEW))
        parked = Queue.parse(PARKED, document(LEGACY_PARKED))
        ledger = Ledger.parse(document(LEGACY_ORDERS))
        events = files.read_jsonl(sources[LEGACY_HISTORY]) if LEGACY_HISTORY in sources else []

        conn = _open(staging)
        try:
            _ensure_schema(conn)
            conn.execute("BEGIN IMMEDIATE")
            counts: Dict[str, int] = {}
            for name, rows in (
                ("cards", inventory.cards),
                ("boxes", inventory.boxes),
                ("listings", inventory.listings),
                ("identifications", cache.entries),
                ("orders", ledger.orders),
                ("fulfilment", ledger.fulfilment),
            ):
                src = source(conn, name)
                for key, obj in rows.items():
                    src.upsert(key, rows.spec.columns(obj), rows.spec.dump(obj))
                counts[name] = len(rows)
            for queue in (review, parked):
                src = source(conn, "queues", {"queue": queue.name})
                for key, obj in queue.entries.items():
                    src.upsert(key, queue.entries.spec.columns(obj), queue.entries.spec.dump(obj))
                counts[f"queues.{queue.name}"] = len(queue.entries)
            counts["events"] = append_events(conn, events)
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('migrated_at', ?)",
                (datetime.now(timezone.utc).isoformat(timespec="milliseconds"),),
            )
            conn.execute("COMMIT")
            # The WAL must be folded into the file before the rename, or the renamed file
            # is the database as it was before the import and the WAL is orphaned.
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            conn.close()
        for side in (Path(str(staging) + "-wal"), Path(str(staging) + "-shm")):
            if side.exists():
                side.unlink()
        os.replace(staging, db_path)

        # The reversible export: moved, never deleted, and receipted with each file's digest
        # so a later question about what was imported has an answer.
        legacy = legacy_dir(directory)
        legacy.mkdir(parents=True, exist_ok=True)
        receipt = {
            "migrated_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "database": DB_NAME,
            "counts": counts,
            "files": {},
            "reverse": (
                f"delete {DB_NAME}, {DB_NAME}-wal and {DB_NAME}-shm, then move every file "
                f"in {LEGACY_DIRNAME}/ back up one level"
            ),
        }
        for name, src_path in sources.items():
            receipt["files"][name] = {"sha256": _sha256(src_path), "bytes": src_path.stat().st_size}
            shutil.move(str(src_path), str(legacy / name))
        files.write_json(legacy / RECEIPT_NAME, receipt)
