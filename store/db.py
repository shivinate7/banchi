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

import contextlib
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
MIGRATIONS_DIRNAME = "migrations"
BOX_ID_RECEIPT = "box-ids.json"
CARD_ID_RECEIPT = "card-ids.json"
# The `meta` key holding `Inventory.box_ids_issued` (D145).
BOX_IDS_ISSUED = "box_ids_issued"
# D172's three `meta` keys. `CARD_IDS_SEEDED` is how a reader tells "this store has been
# through the naming" from "this store has no names yet", which is the distinction a bare
# count of NULLs cannot make. `CARD_ID_SOURCES` is the census — which rung of the ladder
# named how many cards — and it is the field that keeps `disk: 0` from ever reading as "no
# photograph needed hashing". `PHOTOS_RELOCATED` is the gate on the legacy photograph
# address: while it is unset `store/photos.find` still looks there, and once it is set the
# old address is never consulted again.
CARD_IDS_SEEDED = "card_ids_seeded"
CARD_ID_SOURCES = "card_id_sources"
PHOTOS_RELOCATED = "photos_relocated"
# FOUR, AND THE JUMP FROM 3 IS THE MERGE THIS FUNCTION WAS WARNED ABOUT.
# `docs/specs/stable-card-id.md` §5 predicted it in as many words: "Two concurrent 2→3 steps
# in `_upgrade` is a conflict in the one function where taking either side silently loses a
# migration. Whichever merges first is 2→3 and the second is 3→4." D174's `submissions`
# table merged first (PR #312) and took 3, so the naming is 4. THE RESOLUTION WAS TO ADD A
# STEP, NEVER TO TAKE A SIDE — both `if` arms below are live, and the owner's real store had
# already been stamped 3 by the main checkout's own supervisor before this branch merged.
SCHEMA_VERSION = 4

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
        "set_hint", "run", "captured_at", "state_at", "cid",
    ),
    "boxes": ("box", "bid", "name", "state"),
    "listings": ("condition", "pushed", "staged", "live"),
    "identifications": ("photo_sha256", "cleared_by_human", "at"),
    "queues": ("box", "idx", "reason", "cleared_by_human", "first_seen"),
    "orders": ("source", "number", "status"),
    "fulfilment": (),
    # D174: the cards a live run has claimed and is about to pay to read.
    # `keys` is the claim itself and is NOT a column — it is a set, and a column holds one
    # value; the intersection is computed in Python over the handful of live rows, which is
    # what `Submissions.live` keeps small by filtering on the `state` column first.
    "submissions": ("pid", "state", "started_at", "run"),
}

_INTEGER = {"box", "bid", "idx", "pushed", "staged", "live", "cleared_by_human", "pid"}

_INDEXES = (
    ("cards", "box"), ("cards", "sku"), ("cards", "capture_id"), ("cards", "state"),
    ("cards", "idx"),
    ("queues", "box"),
    ("events", "position"),
    ("boxes", "bid"),
    ("submissions", "state"),
)

# D172'S TWO INDEXES, DELIBERATELY NOT IN `_INDEXES` BECAUSE NEITHER IS A PLAIN ONE.
#
# `cards_cid` is UNIQUE, and that uniqueness is what makes the photograph's path safe: the
# path is a pure function of the name (`store/photos.py`), so two cards being unable to hold
# one name is two cards being unable to compose one filename. It is also what makes a
# `cid -> (box, idx)` lookup an index probe — measured at 4.0 us, `EXPLAIN` reporting
# `SEARCH cards USING INDEX cards_cid (cid=?)`.
#
# `cards_cid_missing` is PARTIAL, and the `WHERE` clause is the whole point: it indexes only
# the rows that have lost their name, so it holds NOTHING on a healthy store and "is anything
# unnamed?" costs one empty probe rather than a scan of every card. That is what lets
# `_repair` run on every open without the cost `_ensure_schema`'s docstring warns about.
_CID_INDEXES = (
    "CREATE UNIQUE INDEX IF NOT EXISTS cards_cid ON cards(cid)",
    "CREATE INDEX IF NOT EXISTS cards_cid_missing ON cards(key) WHERE cid IS NULL",
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


def _stored_version(conn: sqlite3.Connection) -> Optional[int]:
    """The schema version this file was last stamped with, or None for an empty file.

    None and 0 are different answers: None is "no tables here yet, create them", and any
    integer is "these tables exist and may need an upgrade". An unreadable stamp reads as
    version 0, which routes it through every upgrade step — the safe direction, since each
    step below is written to be a no-op against a file that already has its column.
    """
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'meta'"
    ).fetchone()
    if row is None:
        return None
    stored = conn.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()
    if stored is None:
        return 0
    try:
        return int(stored[0])
    except (TypeError, ValueError):
        return 0


def _ensure_schema(
    conn: sqlite3.Connection,
    *,
    directory: Optional[Path] = None,
    locked: bool = False,
) -> None:
    """Create the tables once, and upgrade them when this build's schema has moved on.

    A READ-ONLY CHECK ON EVERY LATER OPEN, and that matters: `Store(snapshot.directory)
    .history()` opens a second connection inside a write session, and a DDL or an
    `INSERT OR IGNORE` here would be a second writer waiting on the first until
    `busy_timeout` — measured as a 30-second stall on the first sale T7 recorded after D88.
    So the version check comes first and every other statement is behind it.

    AN UPGRADE TAKES THE STORE LOCK, exactly as `_import_legacy` does and for the same
    reason: it is a write, it can be reached from `Store.read()` — the first read after a
    `git pull` is the ordinary case — and two processes discovering the same pending upgrade
    at once must not both run it. `locked=True` says the caller already holds it.
    """
    stored = _stored_version(conn)
    if stored is not None and stored > SCHEMA_VERSION:
        # A NEWER BUILD WROTE THIS FILE, AND WITHOUT THIS THE OLDER BUILD WINS SILENTLY.
        # Measured on a copy stamped 3 and opened with a build that knew 2: the read
        # SUCCEEDED — 2,535 cards — and the stamp was rewritten DOWN to 2 on the way
        # through, by the two statements below (`stored != SCHEMA_VERSION` reaches
        # `_upgrade`, whose every `if stored < n` is false, and whose last statement is an
        # unconditional `INSERT OR REPLACE` of the stamp). From that moment the file is a
        # schema-2 store carrying schema-3 columns, and every ordinary write STRIPS the
        # fields this build does not declare — one row at a time, with no error, because
        # `Inventory.parse` filters on `__annotations__` and `upsert` names only this
        # build's `column_names`. Measured: 2535 → 2534 cards carrying a `cid` after one
        # `set_state`, and a UNIQUE index does not object because SQLite NULLs are never
        # duplicates.
        #
        # THE REFUSAL IS AT THE OPEN AND NOT AT THE WRITE, which is a deliberate choice and
        # `docs/specs/stable-card-id.md` §0.6 hazard 2 is the argument: once per process,
        # loud, before any card exists — rather than once per capture, where a refusal is a
        # 500 on `POST /capture` with the physical card already in the drawer.
        raise files.StoreError(
            f"{path(directory) if directory is not None else DB_NAME} is stamped schema "
            f"{stored} and this build knows {SCHEMA_VERSION}. A newer build wrote it; an "
            "older one opening it rewrites the stamp DOWN and then strips every field it "
            "does not declare, one row per write, silently. Update the checkout — `git "
            "pull` in the main tree, then `make hooks`."
        )
    if stored == SCHEMA_VERSION:
        _repair(conn, directory=directory, locked=locked)
        return
    if stored is not None:
        _upgrade(conn, stored, directory=directory, locked=locked)
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
    # THE FRESH PATH CREATES D172'S INDEXES TOO, AND MISSING THIS WOULD HAVE BEEN SILENT.
    # `_upgrade`'s `ALTER` never runs here — this branch stamps `SCHEMA_VERSION` directly —
    # so without these two statements every worktree, the demo seed and all nine harness
    # tests would exercise a schema the owner's store does not have: no UNIQUE on the name,
    # and no partial index for `_repair` to probe.
    for statement in _CID_INDEXES:
        conn.execute(statement)
    conn.execute(
        "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema', ?)", (str(SCHEMA_VERSION),)
    )


def _upgrade(
    conn: sqlite3.Connection,
    stored: int,
    *,
    directory: Optional[Path] = None,
    locked: bool = False,
) -> None:
    """Bring a store built by an older build up to `SCHEMA_VERSION`, under the store lock.

    ONE STEP PER VERSION, IN ORDER, AND EVERY STEP IS ADDITIVE. Nothing here drops a column,
    rewrites a payload's existing key or removes a row, so an upgrade cannot lose data and a
    half-applied one is repaired by running it again — which is what a crash between the step
    and the stamp leaves behind, and why each step is written to be a no-op on a file that
    already has its column.

    THE STAMP IS THE LAST STATEMENT IN THE TRANSACTION, never a separate commit. A file
    stamped 2 whose boxes have no ids would be a store this function would then refuse to
    look at again.
    """
    directory = Path(directory) if directory is not None else None
    # THE CORPUS IS HASHED BEFORE THE LOCK IS TAKEN, AND THAT IS THE DESIGN RATHER THAN AN
    # OPTIMISATION. `docs/specs/stable-card-id.md` §0.6 hazard 1: this step runs on the first
    # `Store.read()` after a `git pull`, `make launch-agent` keeps the capture server alive at
    # login over the owner's real store, and 2.68-3.00 s of hashing 4.45 GB with the flock
    # held is ~5 captures arriving against `REQUEST_SLOTS = 4` at the feeder's measured
    # 623 ms cadence. A capture lost mid-feeder leaves a physical card in the drawer with no
    # record, which renumbers every card behind it — silent, and physical. So the reading is
    # taken out here, where it blocks nobody, and re-checked inside the lock.
    prehashed = (
        _prehash_photographs(conn, directory) if (stored or 0) < 4 else {}
    )
    guard = (
        _already_locked()
        if (locked or directory is None)
        else files.exclusive(directory)
    )
    with guard:
        # Re-read inside the lock: another process may have done the whole thing while this
        # one waited for it, which is the ordinary shape when a server and a CLI start together.
        stored = _stored_version(conn) or 0
        if stored == SCHEMA_VERSION:
            return
        conn.execute("BEGIN IMMEDIATE")
        try:
            receipt: Optional[dict] = None
            card_receipt: Optional[dict] = None
            if stored < 2:
                receipt = _add_box_ids(conn)
            if stored < 3:
                _add_submissions(conn)
            if stored < 4:
                card_receipt = _add_card_ids(conn, prehashed, directory)
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema', ?)",
                (str(SCHEMA_VERSION),),
            )
            conn.execute("COMMIT")
        except BaseException:
            with contextlib.suppress(Exception):
                conn.execute("ROLLBACK")
            raise
        if receipt is not None and directory is not None:
            _write_migration_receipt(directory, BOX_ID_RECEIPT, receipt)
        if card_receipt is not None and directory is not None:
            _write_migration_receipt(directory, CARD_ID_RECEIPT, card_receipt)


def _home_for(directory: Optional[Path]) -> Optional[Path]:
    """The store's home, from the directory holding the database.

    `files.inventory_dir()` is `home()/inventory`, so the home is the parent — and taking it
    from the ARGUMENT rather than from `files.home()` is what lets a throwaway store under a
    scratchpad be migrated without reaching for the owner's real photographs. The self-test
    depends on it; so does a `.backup()` copy.
    """
    return None if directory is None else Path(directory).parent


def _card_rows_for_naming(conn: sqlite3.Connection) -> List[Tuple[str, dict]]:
    """`(key, record)` for every card, in ascending `(box, index)`.

    THE ORDER IS `_add_box_ids`' ORDER AND FOR ITS STATED REASON: `captured_at` is the more
    meaningful sequence and it is OPTIONAL on these rows, so ordering on it would make the
    result depend on SQLite's row order. Ascending position is present by construction and
    sorts. It matters here only because the `-<n>` duplicate suffix is order-dependent.
    """
    rows = conn.execute("SELECT key, payload FROM cards").fetchall()
    out = []
    for key, text in rows:
        try:
            record = json.loads(text)
        except (TypeError, ValueError):
            record = {}
        try:
            box = int(record.get("box"))
        except (TypeError, ValueError):
            box = None
        try:
            index = int(record.get("index"))
        except (TypeError, ValueError):
            index = None
        out.append(((box is None, box or 0, index is None, index or 0, str(key)), str(key), record))
    out.sort(key=lambda item: item[0])
    return [(key, record) for _sort, key, record in out]


def _prehash_photographs(
    conn: sqlite3.Connection, directory: Optional[Path]
) -> Dict[str, Tuple[str, int, int]]:
    """`{key: (digest, size, mtime_ns)}` for every card whose photograph is on disk.

    OUTSIDE THE LOCK, WHICH IS WHY IT RETURNS THE STAT TRIPLE AND NOT JUST THE DIGEST. The
    file can move between this reading and the transaction — `do_reshoot` is the one writer
    that can do it — so `_add_card_ids` re-stats every entry inside the lock and re-hashes
    any whose `(size, mtime_ns)` has changed, reporting the count as `rehashed`. That is a
    positive counter on purpose: "0 re-hashed" and "this never looked" must not be the same
    output.

    IT READS THE LEGACY ADDRESS AND THE CARD'S OWN NAME, IN THAT ORDER OF EXISTENCE. At
    schema 2 no card has a name yet, so in practice this is the legacy address; the other
    branch is for a store part-way through the relocation whose stamp was reversed.
    """
    from store import photos  # local: `store.photos` imports `store.files`, not this module

    home = _home_for(directory)
    if home is None:
        return {}
    out: Dict[str, Tuple[str, int, int]] = {}
    for key, record in _card_rows_for_naming(conn):
        existing = record.get("cid")
        candidate = None
        if photos.is_photo_cid(existing):
            candidate = photos.path(existing, home)
            if not candidate.is_file():
                candidate = None
        if candidate is None:
            try:
                candidate = photos.legacy_path(record.get("box"), record.get("index"), home)
            except (TypeError, ValueError):
                continue
        try:
            stat = candidate.stat()
            out[key] = (photos.sha256_of(candidate), stat.st_size, stat.st_mtime_ns)
        except OSError:
            continue
    return out


def _name_one_card(
    key: str,
    record: dict,
    prehashed: Dict[str, Tuple[str, int, int]],
    identifications: Dict[str, str],
    home: Optional[Path],
    taken: Dict[str, str],
    counters: Dict[str, int],
) -> str:
    """One card's name, off the ladder, with the source counted. Never returns None.

    THE LADDER ORDER IS THE LOAD-BEARING DECISION AND IT IS DELIBERATELY THE OPPOSITE OF THE
    OBVIOUS ONE. `identifications.photo_sha256` answers every card on this store in 19 ms
    with no I/O, and taking it first would make the whole naming free — and would bind all
    2,535 permanent names THROUGH THE POSITION-KEYED LOOKUP THIS DESIGN EXISTS TO REPLACE,
    without ever reading the bytes it is naming. It is also provably stale in a real window:
    `do_reshoot` writes new bytes and touches neither `cards` nor `identifications`, and D26
    forbids archiving the old photograph, so from a re-shoot until the next paid press that
    row is the digest of bytes that exist nowhere on disk and in no backup. It stays in the
    ladder as a WEAKER source for a card whose photograph has vanished without a reclaim,
    and it is reported by name rather than folded into success.
    """
    from store import photos

    existing = record.get("cid")
    if isinstance(existing, str) and existing:
        # RUNG 1 IS WHAT MAKES A RE-RUN AFTER A CRASH A NO-OP, which is `_add_box_ids`' own
        # rule. Under a digest a re-issue would be harmless — it comes back byte-identical —
        # but the read-first line goes in anyway, because the `-<n>` suffix is
        # order-dependent and a re-run must not renumber one.
        counters["kept"] += 1
        return existing

    digest = None
    source = None
    hashed = prehashed.get(key)
    if hashed is not None:
        digest, source = hashed[0], "disk"
    elif isinstance(record.get("photo_sha256"), str) and record["photo_sha256"]:
        # RUNG 3: D89's reclaim. The photograph is gone on purpose and the record kept its
        # digest, which is exactly the fact this name wants.
        digest, source = record["photo_sha256"], "record"
    elif isinstance(identifications.get(key), str) and identifications[key]:
        digest, source = identifications[key], "identification"

    if digest is None:
        counters["nophoto"] += 1
        return f"{photos.NOPHOTO_PREFIX}{key}@{record.get('captured_at') or ''}"

    counters[source] += 1
    cid = digest
    suffix = 1
    while cid in taken:
        # SHAPE 2: the nth card whose bytes are identical to an earlier card's. 0 of 2,535
        # real photographs and 0 of 132 demo pool files collide, so this has never fired —
        # which is why the self-test PROVOKES it rather than asserting over zero firings.
        suffix += 1
        cid = f"{digest}-{suffix}"
    if suffix > 1:
        counters["suffixed"] += 1
    return cid


def _add_card_ids(
    conn: sqlite3.Connection,
    prehashed: Dict[str, Tuple[str, int, int]],
    directory: Optional[Path],
) -> dict:
    """Schema 2 -> 3: give every card in an existing store its stable name (D172).

    `_add_box_ids`' shape exactly — additive, no-op on a re-run because it reads the existing
    value first, stamp last inside the transaction, receipt carrying a plain-English
    `reverse` sentence. One column, one payload key, no existing key touched.

    IT CAN NEVER REFUSE, and that is a deliberate choice against an operator-pressed
    migration on two grounds: a migration somebody has to remember to run is a migration
    that does not happen, and `_ensure_schema` raising over one unnameable card would take
    every route and every command down. Shape 4 (`nophoto:`) exists instead of a refusal.
    """
    from store import photos

    home = _home_for(directory)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(cards)").fetchall()}
    if "cid" not in columns:
        conn.execute("ALTER TABLE cards ADD COLUMN cid TEXT")

    identifications: Dict[str, str] = {}
    for key, digest in conn.execute(
        "SELECT key, photo_sha256 FROM identifications"
    ).fetchall():
        if isinstance(digest, str) and digest:
            identifications[str(key)] = digest

    # RE-STAT INSIDE THE LOCK. The file cannot change without its size or mtime changing, so
    # a moved stat is the signal to re-read the bytes rather than to refuse.
    rehashed = 0
    for key, entry in list(prehashed.items()):
        record_digest, size, mtime = entry
        candidate = None
        row = conn.execute("SELECT payload FROM cards WHERE key = ?", (key,)).fetchone()
        if row is None or home is None:
            continue
        try:
            record = json.loads(row[0])
        except (TypeError, ValueError):
            continue
        existing = record.get("cid")
        if photos.is_photo_cid(existing):
            candidate = photos.path(existing, home)
            if not candidate.is_file():
                candidate = None
        if candidate is None:
            candidate = photos.legacy_path(record.get("box"), record.get("index"), home)
        try:
            stat = candidate.stat()
        except OSError:
            del prehashed[key]
            continue
        if (stat.st_size, stat.st_mtime_ns) != (size, mtime):
            prehashed[key] = (photos.sha256_of(candidate), stat.st_size, stat.st_mtime_ns)
            rehashed += 1

    counters = {
        "kept": 0, "disk": 0, "record": 0, "identification": 0, "nophoto": 0, "suffixed": 0,
    }
    taken: Dict[str, str] = {}
    duplicates: List[dict] = []
    unnamed: List[str] = []
    rows = _card_rows_for_naming(conn)
    for key, record in rows:
        cid = _name_one_card(
            key, record, prehashed, identifications, home, taken, counters
        )
        if cid in taken:
            # Unreachable for a photograph cid — the suffix loop guarantees it — and
            # reachable for `nophoto:`, where two cards in one box with the same
            # `captured_at` compose one string. Suffix it the same way rather than letting
            # `cards_cid` refuse the whole migration.
            suffix = 1
            base = cid
            while cid in taken:
                suffix += 1
                cid = f"{base}-{suffix}"
        if photos.digest_of(cid) is not None and photos.digest_of(cid) != cid:
            duplicates.append({"key": key, "cid": cid, "first": taken.get(photos.digest_of(cid))})
        taken[cid] = key
        if not photos.is_photo_cid(cid):
            unnamed.append(key)
        record["cid"] = cid
        conn.execute(
            "UPDATE cards SET cid = ?, payload = ? WHERE key = ?",
            (cid, payload_text(record), key),
        )

    for statement in _CID_INDEXES:
        conn.execute(statement)
    named_from_bytes = counters["disk"] + counters["record"]
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
        (CARD_IDS_SEEDED, str(len(rows))),
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
        (CARD_ID_SOURCES, json.dumps(counters, sort_keys=True)),
    )
    return {
        "migrated_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "schema": {"from": 2, "to": SCHEMA_VERSION},
        "what": (
            "every card gained a `cid`: the sha256 of the photograph the store held when the "
            "id was issued, frozen from that moment and never recomputed, so a name survives "
            "a re-shoot, a reclaim, a move, a renumber and a box deletion (D172)"
        ),
        "order": "ascending (box, index)",
        "card_ids_seeded": len(rows),
        "card_id_sources": counters,
        # `verified_against_disk` counts the rungs that read BYTES, and it is named that way
        # so `disk: 0` can never read as "no photograph needed hashing".
        "verified_against_disk": named_from_bytes,
        "rehashed": rehashed,
        "unnamed": unnamed,
        "duplicate_photographs": duplicates,
        "reverse": (
            "additive only — no column was dropped, no payload key was overwritten, no row "
            "was removed. To undo: `DROP INDEX cards_cid`, `DROP INDEX cards_cid_missing`, "
            "`UPDATE cards SET cid = NULL`, remove the `cid` key from each payload, delete "
            "the `card_ids_seeded` and `card_id_sources` rows from `meta`, and set the "
            "`schema` row back to 2. THE REVERSE IS FOR A STORE YOU ARE ABOUT TO OPEN WITH "
            "AN OLDER CHECKOUT: on a build that still declares the field, the next read "
            "names every card again — and produces the identical names, because the name is "
            "read off the photograph rather than allocated."
        ),
    }


def _repair(
    conn: sqlite3.Connection,
    *,
    directory: Optional[Path] = None,
    locked: bool = False,
) -> None:
    """Re-issue a name an older build stripped. Loud, never a refusal, never a stop (D172).

    THE HAZARD IS MEASURED AND IT IS LIVE ON THIS MACHINE. A build that does not declare
    `Card.cid` strips it on any ordinary write, silently: `Inventory.parse` filters on
    `__annotations__` and `upsert` names only that build's `column_names`, so the row comes
    back with the column NULL and the payload key gone. No error, and a UNIQUE index does not
    object because SQLite NULLs are never duplicates. There are ~30 worktrees on this machine
    and every one that has not pulled is such a build.

    AND THE NAME IS A DIGEST, SO THE NEXT READ HEALS IT — BYTE-IDENTICALLY. That was measured
    before this was written, and it is the entire argument against an allocator, which would
    have handed the stripped row a fresh number and left every reference to its old one
    pointing at nothing. `docs/specs/stable-card-id.md` §6.1 item 2 made this a named
    REFUSAL instead; §0.6 hazard 3 overrules that, because refusing to use the one property
    the design was chosen for, in the one situation it was bought for, is giving it away.

    IT IS LOUD IN THREE PLACES so it can never be the silent re-issue that refusal was
    guarding against: `cards_reissued` in a receipt, a `card_ids_reissued` history event
    naming every key, and a line in `make status`.

    THE PROBE IS AN INDEX PROBE AND NOT A SCAN, which is what lets it run on every open.
    `cards_cid_missing` is PARTIAL — `WHERE cid IS NULL` — so it holds nothing on a healthy
    store and this costs one empty lookup. `_ensure_schema`'s docstring warns against adding
    work to the every-open path and that warning is about a WRITER waiting on `busy_timeout`;
    this is a read, and an empty one.
    """
    if conn.in_transaction:
        # NESTED, AND THIS IS THE DEADLOCK `_ensure_schema`'s DOCSTRING WARNS ABOUT.
        # `Store(snapshot.directory).history()` opens a second connection inside a write
        # session, so a repair reached from there would either wait on the flock the outer
        # session already holds or open a transaction inside one. The repair is idempotent
        # and the next clean open runs it, so the safe answer is to do nothing and say
        # nothing — the NULL is still there and still reported by `cards audit`.
        return
    try:
        missing = [
            str(row[0])
            for row in conn.execute(
                "SELECT key FROM cards WHERE cid IS NULL ORDER BY key"
            ).fetchall()
        ]
    except sqlite3.OperationalError:
        # No `cid` column on a store stamped current: a hand-reversed file, or a stamp
        # written by something other than `_upgrade`. The upgrade path owns that case.
        return
    if not missing:
        return

    directory = Path(directory) if directory is not None else None
    prehashed = _prehash_photographs(conn, directory)
    guard = (
        _already_locked()
        if (locked or directory is None)
        else files.exclusive(directory)
    )
    with guard:
        missing = [
            str(row[0])
            for row in conn.execute(
                "SELECT key FROM cards WHERE cid IS NULL ORDER BY key"
            ).fetchall()
        ]
        if not missing:
            return
        conn.execute("BEGIN IMMEDIATE")
        try:
            receipt = _reissue_card_ids(conn, missing, prehashed, directory)
            conn.execute("COMMIT")
        except BaseException:
            with contextlib.suppress(Exception):
                conn.execute("ROLLBACK")
            raise
    if directory is not None:
        _write_migration_receipt(directory, CARD_ID_RECEIPT, receipt)


def _reissue_card_ids(
    conn: sqlite3.Connection,
    missing: Sequence[str],
    prehashed: Dict[str, Tuple[str, int, int]],
    directory: Optional[Path],
) -> dict:
    """The heal itself: name the stripped rows off the same ladder, and say so in the history."""
    from store import photos

    home = _home_for(directory)
    identifications: Dict[str, str] = {}
    for key, digest in conn.execute(
        "SELECT key, photo_sha256 FROM identifications"
    ).fetchall():
        if isinstance(digest, str) and digest:
            identifications[str(key)] = digest

    taken: Dict[str, str] = {}
    for key, cid in conn.execute(
        "SELECT key, cid FROM cards WHERE cid IS NOT NULL"
    ).fetchall():
        taken[str(cid)] = str(key)

    counters = {
        "kept": 0, "disk": 0, "record": 0, "identification": 0, "nophoto": 0, "suffixed": 0,
    }
    wanted = set(str(key) for key in missing)
    reissued: Dict[str, str] = {}
    for key, record in _card_rows_for_naming(conn):
        if key not in wanted:
            continue
        cid = _name_one_card(
            key, record, prehashed, identifications, home, taken, counters
        )
        suffix = 1
        base = cid
        while cid in taken:
            suffix += 1
            cid = f"{base}-{suffix}"
        taken[cid] = key
        record["cid"] = cid
        reissued[key] = cid
        conn.execute(
            "UPDATE cards SET cid = ?, payload = ? WHERE key = ?",
            (cid, payload_text(record), key),
        )

    at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    conn.execute(
        "INSERT INTO events (at, event, position, payload) VALUES (?, ?, ?, ?)",
        (
            at,
            "card_ids_reissued",
            None,
            payload_text({
                "at": at,
                "event": "card_ids_reissued",
                "keys": sorted(reissued),
                "sources": counters,
                "why": (
                    "these rows carried no name. A build that does not declare `Card.cid` "
                    "strips it on any ordinary write; the name is a digest, so it was read "
                    "again from the same source and came back the same value."
                ),
            }),
        ),
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
        (CARD_IDS_SEEDED, str(conn.execute("SELECT count(*) FROM cards").fetchone()[0])),
    )
    return {
        "migrated_at": at,
        "schema": {"from": SCHEMA_VERSION, "to": SCHEMA_VERSION},
        "what": (
            "re-issued a stable name to every card row that had lost one — the signature of "
            "an older build having written the row, which strips fields it does not declare"
        ),
        "cards_reissued": len(reissued),
        "keys": sorted(reissued),
        "card_id_sources": counters,
        "verified_against_disk": counters["disk"] + counters["record"],
        "reverse": (
            "nothing to reverse — these rows held NULL and now hold the name they held "
            "before the strip. The values are re-derived, not allocated, so this is "
            "idempotent."
        ),
    }


def _add_submissions(conn: sqlite3.Connection) -> None:
    """Schema 3: the `submissions` claim table (D174).

    THE PUREST ADDITIVE STEP THERE IS — a table nothing older has, so there is nothing to
    backfill and nothing to read wrong. It writes no receipt file for that reason: `_add_box_ids`
    leaves one because it DERIVED an id for every existing box and a later question about which
    box got which id has no other answer, and there is no corresponding question here.

    AN EMPTY CLAIM TABLE IS THE CORRECT STATE FOR AN UPGRADED STORE, and it is worth saying why
    it is not a loss. A claim protects a press that is happening NOW; every run that was live
    before this build existed was guarded by `_busy_run` and is either finished or is a run this
    build can see on `#/runs`. There is no past to reconstruct, only presses from here on.
    """
    conn.execute(_ddl("submissions", TABLES["submissions"]))
    conn.execute("CREATE INDEX IF NOT EXISTS submissions_state ON submissions(state)")


def _add_box_ids(conn: sqlite3.Connection) -> dict:
    """Schema 1 -> 2: give every box in an existing store its true index (D145).

    IN ASCENDING BOX NUMBER, which is the only stable order available. The rows carry a
    `created_at` and it would be the more meaningful sequence, but it is optional — the v1
    migration in `Inventory.parse` creates a registry entry for every box a card names and
    gives it none — so ordering on it would put every such box in an arbitrary bucket and
    make the result depend on SQLite's row order. The number is present on every row by
    construction, unique by construction, and sorts. Which box got id 3 does not matter; that
    the same store always produces the same answer does.

    IT IS ADDITIVE AND LOSSLESS. One column is added, one key is added to each payload, and
    no existing key is touched — so the reverse is dropping the field, and every reader that
    has not learned about `bid` yet goes on reading these rows unchanged (`Inventory.parse`
    filters on `Box.__annotations__`, so an unknown key was always survivable in the other
    direction too).

    A BOX THAT ALREADY HAS AN ID KEEPS IT, and its id still counts against the high-water
    mark. That is what makes a re-run after a crash a no-op rather than a renumbering.
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(boxes)").fetchall()}
    if "bid" not in columns:
        conn.execute("ALTER TABLE boxes ADD COLUMN bid INTEGER")
    conn.execute("CREATE INDEX IF NOT EXISTS boxes_bid ON boxes(bid)")

    rows = conn.execute("SELECT key, payload FROM boxes").fetchall()
    numbered = []
    for key, text in rows:
        record = json.loads(text)
        try:
            number = int(record.get("box", key))
        except (TypeError, ValueError):
            number = None
        numbered.append((number, str(key), record))
    # A row whose box will not coerce sorts last rather than stopping the migration: it is
    # already unreachable through `Inventory.box`, and refusing to upgrade the store over it
    # would strand every healthy box behind one bad row.
    numbered.sort(key=lambda item: (item[0] is None, item[0] if item[0] is not None else 0, item[1]))

    issued = 0
    for _, (_number, key, record) in enumerate(numbered):
        existing = record.get("bid")
        try:
            existing = None if existing is None else int(existing)
        except (TypeError, ValueError):
            existing = None
        if existing is None:
            issued += 1
            bid = issued
        else:
            bid = existing
            issued = max(issued, existing)
        record["bid"] = bid
        conn.execute(
            "UPDATE boxes SET bid = ?, payload = ? WHERE key = ?",
            (bid, payload_text(record), key),
        )
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
        (BOX_IDS_ISSUED, str(issued)),
    )
    return {
        "migrated_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "schema": {"from": 1, "to": SCHEMA_VERSION},
        "what": (
            "every box gained a `bid`: a true index that is never reused, so a record that "
            "outlives its drawer can say which drawer it meant after the number is handed "
            "out again (D20)"
        ),
        "order": "ascending box number",
        "box_ids_issued": issued,
        "boxes": {key: record["bid"] for _n, key, record in numbered},
        "reverse": (
            "additive only — no column was dropped, no payload key was overwritten, no row "
            "was removed. To undo: `UPDATE boxes SET bid = NULL`, remove the `bid` key from "
            "each payload, delete the `box_ids_issued` row from `meta`, and set the `schema` "
            "row back to 1."
        ),
    }


def _number_legacy_boxes(inventory) -> None:
    """Assign `Box.bid` across a legacy inventory, in ascending box number.

    `_add_box_ids`' rule applied to objects rather than to rows, and it is deliberately a
    second implementation of four lines rather than a shared one: that function edits SQL
    payloads in a database that already exists, this one edits dataclasses on their way into
    a database being created, and the only thing they share is the ORDER — which is stated in
    both docstrings because it is the part a reader has to be able to check.
    """
    def number_of(key, box):
        try:
            return int(box.box)
        except (TypeError, ValueError):
            try:
                return int(key)
            except (TypeError, ValueError):
                return None

    entries = [(number_of(key, box), str(key), box) for key, box in inventory.boxes.items()]
    entries.sort(key=lambda item: (item[0] is None, item[0] if item[0] is not None else 0, item[1]))
    issued = 0
    for _number, key, box in entries:
        if box.bid is None:
            issued += 1
            box.bid = issued
        else:
            issued = max(issued, int(box.bid))
        inventory.boxes[key] = box
    inventory.box_ids_issued = max(inventory.box_ids_issued, issued)


def _write_migration_receipt(directory: Path, name: str, receipt: dict) -> None:
    """The receipt beside the store, in `legacy-json/MIGRATED.json`'s shape and for its
    reason: a later question about what a migration did has an answer that is not a diff of
    two builds. Best effort — a read-only or full disk must not make an already-committed
    upgrade look like a failure."""
    with contextlib.suppress(OSError):
        folder = Path(directory) / MIGRATIONS_DIRNAME
        folder.mkdir(parents=True, exist_ok=True)
        files.write_json(folder / name, receipt)


def box_ids_issued(conn: sqlite3.Connection) -> int:
    """The high-water mark for `Box.bid` (D145). 0 where none has been issued."""
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (BOX_IDS_ISSUED,)).fetchone()
    if row is None:
        return 0
    try:
        return max(0, int(row[0]))
    except (TypeError, ValueError):
        return 0


def set_box_ids_issued(conn: sqlite3.Connection, value: int) -> None:
    """Record the mark. NEVER LOWERED: a caller handing back a smaller figure than the file
    holds is a snapshot that was read before somebody else issued an id, and honouring it
    would hand that id out twice."""
    current = box_ids_issued(conn)
    wanted = max(current, max(0, int(value or 0)))
    if wanted == current:
        return
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (BOX_IDS_ISSUED, str(wanted))
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
    _ensure_schema(conn, directory=directory, locked=locked)
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
    """Every event of one name, newest first. `history`'s narrower sibling (D134).

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
        # THE LEGACY STORE'S BOXES GET THEIR TRUE INDEX HERE (D145), because the
        # staging database is created fresh at the CURRENT schema version and so never passes
        # through `_add_box_ids`. Same rule and same order as that step: ascending box number,
        # additive, and a box that somehow already has an id keeps it.
        _number_legacy_boxes(inventory)
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
            set_box_ids_issued(conn, inventory.box_ids_issued)
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
