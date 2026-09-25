#!/usr/bin/env python3
"""`make cid-selftest` — the card's stable name and the photograph store, proved by violating them.

WHY THIS EXISTS. D172 gives a card a name and
`D183` files its photograph under that name. Both are
worth exactly what their refusals and their WORK-SAVINGS are worth, and neither can be
exercised against the real thing: the store is the owner's 2,535 real cards and the corpus is
4.45 GB of photographs that cannot be re-taken. So every case here builds its own store under
a temp `PKMNSCAN_HOME`, and the destructive ones run against photographs this script drew.

AN OUTCOME ASSERTION CANNOT SEE A WORK-SAVING, WHICH IS THE TRAP THIS SUITE IS SHAPED
AROUND. PR A's arm 9 recorded it: deleting a hash-first gate left every outcome assertion
green, because hash-first and decode-everything agree on every ANSWER. The same trap is
sharper here, because the whole value of the re-scope is work that no longer happens — a
renumber that renames nothing, a move that moves nothing, a sidecar that is never rewritten.
Every one of those reads as "the cards ended up in the right places", which was ALREADY TRUE
before. So `case_a_renumber_moves_no_file` and `case_a_move_moves_no_file` COUNT SYSCALLS:
they wrap `os.replace`, `os.link`, `Path.unlink` and the two `files` writers and assert the
tallies. Delete the change and those tallies go up while every card stays exactly where it
should be.

AND A COUNT OF ROWS CARRYING A NAME CANNOT PROVE THE NAMING RAN CORRECTLY, which is the same
trap one register along: every row gets a value, so a correct seeding and a seeding nothing
checked print the identical number. The cases assert the SOURCE CENSUS — how many cards were
named from their own bytes rather than from something weaker — and `disk: 0` is named as a
failure rather than read as "no photograph needed hashing".

THREE SHAPES HAVE NEVER FIRED IN PRODUCTION and they are PROVOKED here rather than asserted
about: the `-<n>` duplicate suffix (0 duplicate digests among 2,535 real photographs and 0
among 132 demo pool files), the `moved:` tombstone (0 `state='moved'` rows), and the
`nophoto:` shape. A green suite over zero firings proves nothing.

WHY IT IS NOT IN THE GIT HOOK. D18: it writes temp trees and it forks and kills a process. It
IS in `make check`, which is `submission-selftest`'s and `reap-selftest`'s standing.

IT NEVER TOUCHES THE OPERATOR'S STORE. `PKMNSCAN_HOME` is a fresh temp directory for every
case; the real store is never opened, for reading or for writing, and the real `captures/` is
never named. The one case that kills a process kills one this script forked.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

PASS = 0
FAIL = 0
MADE: List[Path] = []

# A one-pixel JPEG, which is all any of this needs: nothing here decodes an image, and the
# bytes only have to be DISTINCT per card so that two cards do not accidentally share a name
# and make the duplicate case fire where it was not meant to.
JPEG_HEAD = bytes.fromhex("ffd8ffe000104a46494600010100000100010000")


def ok(what: str) -> None:
    global PASS
    PASS += 1
    print(f"  ok     {what}")


def bad(what: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  FAIL   {what}")


def check(condition: bool, what: str) -> bool:
    (ok if condition else bad)(what)
    return bool(condition)


def equal(got, want, what: str) -> bool:
    if got == want:
        return ok(what) or True
    bad(f"{what}\n           got  {got!r}\n           want {want!r}")
    return False


def fresh_home() -> Path:
    """A throwaway `PKMNSCAN_HOME`, and every module that caches a path re-read after it.

    A DIRECTORY PER CASE rather than one reused with its rows deleted. Half of what is
    asserted here is about a store's STAMP and about files on disk, so a leftover from the
    previous case is exactly the thing that would make the next one unreadable — and the
    failure would read as the code misbehaving.
    """
    where = Path(tempfile.mkdtemp(prefix="pkmnscan-cid."))
    MADE.append(where)
    os.environ["PKMNSCAN_HOME"] = str(where)
    (where / "inventory").mkdir(parents=True, exist_ok=True)
    return where


def cleanup() -> None:
    for where in MADE:
        shutil.rmtree(where, ignore_errors=True)


def photo_bytes(seed: str) -> bytes:
    """Distinct bytes per seed, so distinct cards get distinct names by construction."""
    return JPEG_HEAD + hashlib.sha256(seed.encode()).digest() * 4


def legacy_photograph(home: Path, box: int, index: int, seed: Optional[str] = None) -> str:
    """Write one photograph at the LEGACY `(box, index)` address and return its digest.

    Which is how a store that predates the naming looks, and is therefore the input every
    migration case needs. The sidecar goes beside it, because the relocation moves both.
    """
    from store import photos

    blob = photo_bytes(seed or f"{box}/{index}")
    target = photos.legacy_path(box, index, home)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(blob)
    target.with_suffix(photos.SIDECAR_SUFFIX).write_text(
        json.dumps({"box": box, "index": index, "game": "pokemon"})
    )
    return hashlib.sha256(blob).hexdigest()


def raw(home: Path) -> sqlite3.Connection:
    """The store, read-only and WITHOUT `db.connect` — so reading cannot migrate.
    `store/db.py:open_read_only`, the same door `cli/cmd_cards.py` opens."""
    from store import db

    return db.open_read_only(home / "inventory" / "store.sqlite")


def stamp_of(home: Path) -> Optional[int]:
    conn = raw(home)
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()
        return None if row is None else int(row[0])
    finally:
        conn.close()


def has_cid_column(home: Path) -> bool:
    conn = raw(home)
    try:
        return "cid" in {r[1] for r in conn.execute("PRAGMA table_info(cards)")}
    finally:
        conn.close()


def names(home: Path) -> Dict[str, Optional[str]]:
    conn = raw(home)
    try:
        return {str(k): v for k, v in conn.execute("SELECT key, cid FROM cards")}
    finally:
        conn.close()


def table_bytes(home: Path) -> Dict[str, List[tuple]]:
    """Every table's rows, for a byte-exact comparison across a reverse.

    `cards_fts*` IS CARVED OUT (store-scaling item 8), for two independent reasons and
    either alone would be enough. First, a plain `SELECT * FROM cards_fts` cannot even run:
    `note` is a virtual column of the FTS5 table with no matching column on `cards` (the
    external content table), and external-content mode resolves a column's TEXT by reading
    it back from the content table on demand — so `SELECT * FROM cards_fts` raises
    `sqlite3.OperationalError: no such column: T.note` regardless of what data is in it.
    Second, even for a table that could be selected, FTS5's shadow tables
    (`cards_fts_data`, `cards_fts_idx`, `cards_fts_docsize`, `cards_fts_config`) store
    compressed b-tree segment blobs whose internal layout depends on insertion order and
    page-split history, not only on logical content — so an index built once and a
    logically-identical index rebuilt independently are not guaranteed byte-identical, and
    `case_the_reverse_restores_every_table_byte_identically`'s comparison would fail on them
    even when the two stores mean the same thing. `check_index_stays_in_sync_...` (T7, and
    the raw-SQL parity check in the reverse case below) is the semantic check that stands in
    for the byte-exact one on this table.
    """
    conn = raw(home)
    try:
        tables = sorted(
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "AND name NOT LIKE 'cards_fts%'"
            )
        )
        return {name: conn.execute(f"SELECT * FROM {name}").fetchall() for name in tables}
    finally:
        conn.close()


class Tally:
    """Count the filesystem calls a block makes. The work-saving's only honest witness.

    WRAPS THE FIVE WRITERS EVERY PHOTOGRAPH PATH IN THIS REPO GOES THROUGH — `os.replace`,
    `os.link`, `Path.unlink`, `files.write_atomic` and `files.write_json`. It is a count and
    not a mock: the real call still runs, so a case can assert both that the cards ended up
    right AND that getting them there cost nothing.
    """

    def __init__(self):
        self.counts = {
            "replace": 0, "link": 0, "unlink": 0, "write_atomic": 0, "write_json": 0,
        }
        self._saved = {}

    def __enter__(self):
        from store import files as store_files

        real_replace, real_link = os.replace, os.link
        real_unlink = Path.unlink
        real_atomic, real_json = store_files.write_atomic, store_files.write_json
        self._saved = {
            "replace": real_replace, "link": real_link, "unlink": real_unlink,
            "write_atomic": real_atomic, "write_json": real_json, "module": store_files,
        }

        def replace(a, b, *args, **kw):
            self.counts["replace"] += 1
            return real_replace(a, b, *args, **kw)

        def link(a, b, *args, **kw):
            self.counts["link"] += 1
            return real_link(a, b, *args, **kw)

        def unlink(self_path, *args, **kw):
            self.counts["unlink"] += 1
            return real_unlink(self_path, *args, **kw)

        def write_atomic(path, data):
            self.counts["write_atomic"] += 1
            return real_atomic(path, data)

        def write_json(path, payload):
            self.counts["write_json"] += 1
            return real_json(path, payload)

        os.replace, os.link, Path.unlink = replace, link, unlink
        store_files.write_atomic, store_files.write_json = write_atomic, write_json
        return self

    def __exit__(self, *exc):
        os.replace = self._saved["replace"]
        os.link = self._saved["link"]
        Path.unlink = self._saved["unlink"]
        module = self._saved["module"]
        module.write_atomic = self._saved["write_atomic"]
        module.write_json = self._saved["write_json"]
        return False

    @property
    def touched(self) -> int:
        return sum(self.counts.values())


def seed_legacy_store(home: Path, box: int, count: int) -> Dict[str, str]:
    """A store shaped like one written before the naming: records, photographs, no `cid`.

    BUILT BY HAND RATHER THAN THROUGH `allocate_capture`, and that is the point: the
    allocator requires a name now, so the only way to produce the input the migration exists
    for is to write the rows the way the old build did. `cid` is stripped from the column and
    from the payload, and the stamp is set back — which is precisely the state an older build
    leaves behind, and the state probe 2 measured.
    """
    from store import master
    from store.session import Store

    digests: Dict[str, str] = {}
    with Store().write() as snapshot:
        for index in range(1, count + 1):
            digest = legacy_photograph(home, box, index)
            digests[master.position_key(box, index)] = digest
            card, _ = snapshot.inventory.allocate_capture(
                box, capture_id=f"seed-{box}-{index}", cid=digest, game="pokemon"
            )
            snapshot.cache.put(card.key, {"name": f"Card {index}"}, digest, "fp")
    _unname(home)
    return digests


def _unname(home: Path) -> None:
    """Strip every name and set the stamp back, the way an older build leaves a store.

    THE MEASURED HAZARD, REPRODUCED RATHER THAN DESCRIBED. A build that does not declare
    `Card.cid` drops it on any ordinary write — `Inventory.parse` filters on
    `__annotations__` and `upsert` names only that build's `column_names` — so the row comes
    back with the column NULL and the payload key gone, with no error, and a UNIQUE index
    does not object because SQLite NULLs are never duplicates.
    """
    from store import db

    conn = sqlite3.connect(str(db.path(home / "inventory")), isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        for key, text in conn.execute("SELECT key, payload FROM cards").fetchall():
            record = json.loads(text)
            record.pop("cid", None)
            conn.execute(
                "UPDATE cards SET cid = NULL, payload = ? WHERE key = ?",
                (json.dumps(record, sort_keys=True, separators=(",", ":")), key),
            )
        conn.execute("DELETE FROM meta WHERE key IN (?, ?)",
                     (db.CARD_IDS_SEEDED, db.CARD_ID_SOURCES))
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('schema', '3')")
        conn.execute("COMMIT")
    finally:
        conn.close()


def open_store(home: Path):
    """One `db.connect`, which is what performs a pending migration. Returns the receipt."""
    from store import db

    conn = db.connect(home / "inventory")
    conn.close()
    receipt = home / "inventory" / db.MIGRATIONS_DIRNAME / db.CARD_ID_RECEIPT
    if not receipt.is_file():
        return None
    return json.loads(receipt.read_text("utf-8"))


# ------------------------------------------------------------------------------ the cases


def case_the_seeding_names_every_card_from_its_own_bytes() -> None:
    """The migration, and the census that is the only thing which can tell it ran correctly."""
    home = fresh_home()
    digests = seed_legacy_store(home, 3, 12)
    check(not has_cid_column(home) or all(v is None for v in names(home).values()),
          "the input is a store with no names, which is what an older build leaves")

    receipt = open_store(home)
    if not check(receipt is not None, "the naming leaves a receipt"):
        return
    equal(receipt["card_ids_seeded"], 12, "twelve cards were named")
    equal(receipt["card_id_sources"]["disk"], 12,
          "and all twelve were named FROM THEIR OWN BYTES — `disk: 0` would mean every name "
          "came from something weaker, which is the one figure a row count cannot show")
    equal(receipt["verified_against_disk"], 12,
          "`verified_against_disk` counts the rungs that read bytes, and is named that way "
          "so a zero can never read as 'no photograph needed hashing'")
    equal(receipt["card_id_sources"]["identification"], 0,
          "and none was named by an identification row, which `do_reshoot` can leave stale")
    equal(receipt["unnamed"], [], "no card landed a `nophoto:` name")

    stored = names(home)
    equal(len(stored), 12, "twelve rows carry a name")
    equal(sorted(v for v in stored.values() if v), sorted(digests.values()),
          "and every name is the sha256 of that card's own photograph — read, not allocated")
    equal(len(set(stored.values())), 12, "twelve distinct names")

    conn = raw(home)
    try:
        equal(conn.execute("SELECT count(*) FROM cards WHERE cid IS NULL").fetchone()[0], 0,
              "no row is NULL — a NULL cannot tell 'no photograph was found' from 'this "
              "migration did not look', which is this repo's signature defect")
        equal(conn.execute(
            "SELECT count(*) FROM cards WHERE cid IS NOT json_extract(payload,'$.cid')"
        ).fetchone()[0], 0,
              "the column and the payload agree — the query that catches a column roster "
              "having been missed, which `12 names in one transaction` cannot make")
        equal(sorted(r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'cards_cid%'"
        )), ["cards_cid", "cards_cid_missing"],
              "both indexes exist: the UNIQUE one that makes two cards unable to compose one "
              "photograph's path, and the PARTIAL one that makes the heal's probe empty")
    finally:
        conn.close()
    from store import db
    equal(stamp_of(home), db.SCHEMA_VERSION,
          "and the stamp is last, inside the same transaction")


def case_the_four_column_rosters_agree() -> None:
    """The four hand-written rosters that had to learn the name, reconciled.

    NOTHING RECONCILED THEM AND ONE OF THEM HAD NO READER AT ALL, which is how this case came
    to exist: a mutation arm deleted `cid` from `Inventory.CARDS.column_names` and every
    suite stayed green. `grep -rn "\.column_names"` across the whole repo returns nothing —
    `SqliteSource` takes its columns from `db.TABLES[table]`, so that field is a DECLARATION
    with no consumer, on every `TableSpec` in the store and not just this one. D80's rule is
    that a claim with no reader has no way of ever being contradicted; this is the reader.

    WHAT MISSING EACH ONE COSTS, because they fail differently:

      `_card_columns`          every write stores the name in the PAYLOAD and leaves the
                               COLUMN NULL. `cards_cid` never fires, a lookup by name returns
                               nothing for every card, and `TableSpec`'s own promise — that
                               the column and the payload cannot disagree — goes quietly
                               false while an idempotence check reports clean forever.
      `db.TABLES["cards"]`     a FRESH store gets no column at all, because
                               `_ensure_schema`'s fresh path stamps the version directly and
                               `_upgrade`'s `ALTER` never runs. Every worktree, the demo seed
                               and all nine harness tests would then exercise a schema the
                               owner's store does not have.
      `Card.__annotations__`   `Inventory.parse` drops the field on reload, so the name
                               survives one process and no more.
      `CARDS.column_names`     nothing, today — and that is the finding rather than the
                               reassurance.
    """
    from store import db, master

    declared = set(db.TABLES["cards"])
    spec = set(master.Inventory.CARDS.column_names)
    built = set(master._card_columns(master.Card(box=1, index=1, cid="a" * 64)))
    equal(sorted(declared ^ spec), [],
          "`db.TABLES['cards']` and `Inventory.CARDS.column_names` name the same columns")
    equal(sorted(spec ^ built), [],
          "and `_card_columns` builds exactly those keys")
    equal(sorted(built - set(master.Card.__annotations__)),
          ["idx", "number_display", "number_key"],
          "and every other one of them is a declared field on `Card` — `idx` is the one "
          "named alias, for `index`, which is a Python builtin's name in every other "
          "context, and `number_key`/`number_display` (store-scaling item 8) are the two "
          "DERIVED columns `_card_columns` composes from `number`/`printed_total` through "
          "`pipeline/join.py` rather than reading off a `Card` field of their own name — "
          "there is no `Card.number_key`, on purpose, because the composed form has no "
          "reason to round-trip through `Inventory.parse` as its own attribute")
    check("cid" in declared and "cid" in spec and "cid" in built,
          "and the card's name is in all three")


def case_a_rerun_names_nothing_and_changes_no_name() -> None:
    """A re-run after a crash is a no-op, which is `_add_box_ids`' own rule."""
    home = fresh_home()
    seed_legacy_store(home, 2, 8)
    open_store(home)
    before = names(home)

    # Force the step to run again by setting the stamp back WITHOUT stripping the names,
    # which is exactly what a crash between the step and the stamp would leave.
    conn = sqlite3.connect(str(home / "inventory" / "store.sqlite"), isolation_level=None)
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('schema', '3')")
    conn.close()

    receipt = open_store(home)
    equal(receipt["card_id_sources"]["kept"], 8,
          "all eight names were KEPT rather than re-issued — the read-first rung, which is "
          "what makes a re-run a no-op rather than a renumbering of the `-<n>` suffixes")
    equal(receipt["card_id_sources"]["disk"], 0, "and not one photograph was hashed again")
    equal(names(home), before, "every name is byte-identical to the first run's")


def case_a_stripped_name_heals_byte_identically() -> None:
    """Probe 2, reproduced: the self-heal that is the whole argument against an allocator.

    D172's §6.1 made this a named REFUSAL. §0.6 hazard 3 overrules that: under a digest the
    re-issue is byte-identical, which is the property the design was chosen for, and refusing
    to use it in the one situation it was bought for is giving it away. So it heals — and it
    is LOUD, which is what stops it being the silent re-issue the refusal was guarding
    against.
    """
    home = fresh_home()
    seed_legacy_store(home, 5, 6)
    open_store(home)
    before = names(home)

    # Strip THREE rows, the way an ordinary write under an older build does.
    conn = sqlite3.connect(str(home / "inventory" / "store.sqlite"), isolation_level=None)
    conn.execute("BEGIN IMMEDIATE")
    victims = ["5/2", "5/4", "5/5"]
    for key in victims:
        text = conn.execute("SELECT payload FROM cards WHERE key = ?", (key,)).fetchone()[0]
        record = json.loads(text)
        record.pop("cid", None)
        conn.execute("UPDATE cards SET cid = NULL, payload = ? WHERE key = ?",
                     (json.dumps(record, sort_keys=True, separators=(",", ":")), key))
    conn.execute("COMMIT")
    stripped = conn.execute("SELECT count(*) FROM cards WHERE cid IS NULL").fetchone()[0]
    conn.close()
    equal(stripped, 3, "three rows lost their name, with no error and no index complaint — "
                       "SQLite NULLs are never duplicates, so UNIQUE does not object")
    from store import db
    equal(stamp_of(home), db.SCHEMA_VERSION,
          "and the stamp still says the store has been named, which is "
          "what makes a bare count of NULLs unable to tell this from a "
          "store that was never named at all")

    receipt = open_store(home)
    if not check(receipt is not None, "the heal leaves a receipt"):
        return
    equal(receipt.get("cards_reissued"), 3,
          "exactly three names were re-issued — as many as were stripped, and not one more")
    equal(sorted(receipt.get("keys") or []), victims, "and the receipt NAMES them")
    equal(names(home), before,
          "and every re-issued name is BYTE-IDENTICAL to what it was. An allocator would "
          "have handed each a fresh number and left every reference to the old one pointing "
          "at nothing, reporting success both times")

    conn = raw(home)
    try:
        events = [
            json.loads(r[0]) for r in conn.execute(
                "SELECT payload FROM events WHERE event = 'card_ids_reissued'"
            )
        ]
    finally:
        conn.close()
    equal(len(events), 1, "one history event says it happened — the heal is loud in three "
                          "places, because a silent re-issue is what the refusal it replaced "
                          "was guarding against")
    if events:
        equal(sorted(events[0].get("keys") or []), victims,
              "and the event names every key it touched")


def case_the_naming_writes_nothing_outside_the_database() -> None:
    """Counted, not asserted about. The property that prices the migration at one transaction."""
    home = fresh_home()
    seed_legacy_store(home, 4, 10)
    with Tally() as tally:
        open_store(home)
    equal(tally.counts["unlink"], 0, "the naming unlinks nothing")
    equal(tally.counts["link"], 0, "and links nothing")
    # THE RECEIPT IS THE ONE FILE IT WRITES, and it is counted rather than excluded: it goes
    # through `write_json`, which goes through `write_atomic`, which lands with `os.replace`.
    # Asserting zero here would have been asserting the wrong thing, and excluding it
    # silently would leave the one write this step makes unwatched.
    equal(tally.counts["write_json"], 1, "and writes exactly one file — the receipt")
    equal((tally.counts["write_atomic"], tally.counts["replace"]), (1, 1),
          "which is the same write seen one and two layers down, so no OTHER file was "
          "touched outside the database")
    equal(len(set(names(home).values())), 10,
          "while still naming all ten, which is why the tallies above are the assertion and "
          "the outcome is not")


def case_two_cards_with_one_photograph_get_a_suffix() -> None:
    """Shape 2, PROVOKED. It has never fired: 0 duplicate digests among 2,535 real
    photographs and 0 among 132 demo pool files, so a green suite over zero firings would
    prove nothing at all."""
    home = fresh_home()
    from store import photos
    from store.session import Store

    blob = photo_bytes("identical")
    digest = hashlib.sha256(blob).hexdigest()
    for index in (1, 2):
        target = photos.legacy_path(7, index, home)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
    with Store().write() as snapshot:
        for index in (1, 2):
            snapshot.inventory.allocate_capture(
                7, capture_id=f"dup-{index}", cid=digest if index == 1 else f"{digest}-2"
            )
    _unname(home)

    receipt = open_store(home)
    stored = names(home)
    equal(sorted(stored.values()), sorted([digest, f"{digest}-2"]),
          "the second card whose bytes match an earlier one's wears `<digest>-2`, so one "
          "photograph's digest can name two cards without either losing its own identity")
    equal(receipt["card_id_sources"]["suffixed"], 1, "and exactly one suffix was issued")
    equal(photos.digest_of(f"{digest}-2"), digest,
          "`digest_of` strips the suffix, which is what keeps the audit from reporting the "
          "second card as a mismatch forever")
    check(photos.is_photo_cid(f"{digest}-2"),
          "and a suffixed name still names a photograph")


def case_the_moved_tombstone_names_no_photograph() -> None:
    """Shape 3, PROVOKED — 0 `state='moved'` rows on the owner's store."""
    home = fresh_home()
    from store import master, photos
    from store.session import Store

    digest = legacy_photograph(home, 1, 1, "to-move")
    with Store().write() as snapshot:
        snapshot.inventory.allocate_capture(1, capture_id="mover", cid=digest)
    with Store().write() as snapshot:
        tombstone, transplant = snapshot.inventory.move_card("1/1", 9)
        equal(transplant.cid, digest,
              "the transplant keeps the card's name, because the name is the CARD's and the "
              "card is what moved")
        equal(tombstone.cid, f"{photos.MOVED_PREFIX}{digest}",
              "and the tombstone wears `moved:<name>`, so one name is never on two rows "
              "under a UNIQUE index — cleared to NULL it would be re-issued by the heal")
    check(not photos.is_photo_cid(f"{photos.MOVED_PREFIX}{digest}"),
          "a `moved:` name names no photograph, so nothing composes a path from it")
    equal(master.MOVED_CID_PREFIX, photos.MOVED_PREFIX,
          "and the two spellings of that prefix agree — `store/master.py` imports nothing "
          "from the rest of the package, so the duplication is deliberate and reconciled "
          "here rather than trusted")


def case_a_card_with_no_photograph_anywhere_is_named_and_not_nulled() -> None:
    """Shape 4, PROVOKED. A NULL is never one of the four."""
    home = fresh_home()
    from store import master, photos
    from store.session import Store

    # A record with no photograph, no digest and no identification — `cmd_emit`'s own
    # comment names this case: "a position the store has never seen, a run joined from a
    # recovered identifications file".
    with Store().write() as snapshot:
        snapshot.inventory.record_capture(
            master.Card(box=8, index=1, cid=f"{photos.NOPHOTO_PREFIX}8/1@")
        )
    _unname(home)
    receipt = open_store(home)
    stored = names(home)
    got = stored.get("8/1") or ""
    check(got.startswith(photos.NOPHOTO_PREFIX),
          f"a card with no photograph and no digest gets a `nophoto:` NAME ({got[:32]!r}), "
          "not a NULL — which is why `_ensure_schema` never has to refuse over one card")
    equal(receipt["card_id_sources"]["nophoto"], 1, "and it is counted as such, by name")
    equal(receipt["unnamed"], ["8/1"], "and reported by key rather than as a total")


def case_a_new_card_with_no_name_is_refused_at_its_birth() -> None:
    """The refusal, and where it is NOT.

    §0.6 hazard 2: it is at the BIRTH of a record and not in `_card_columns`, which is the
    single chokepoint every row passes through — because a refusal there is a 500 on
    `POST /capture` mid-feeder, with the physical card already in the drawer and no record
    of it, which renumbers every card behind it.
    """
    fresh_home()
    from store import master
    from store.session import Store

    try:
        with Store().write() as snapshot:
            snapshot.inventory.record_capture(master.Card(box=2, index=1))
        bad("a nameless new card is refused at its birth")
    except master.UnnamedCard as exc:
        ok("a nameless new card is refused at its birth")
        check("2/1" in str(exc), "and the refusal NAMES the key it would have written")

    # And `_card_columns` does NOT refuse, which is the other half of the decision: it is
    # asserted directly, because a refusal quietly added there later would be invisible to
    # every other case in this file.
    columns = master._card_columns(master.Card(box=2, index=1))
    equal(columns.get("cid"), None,
          "`_card_columns` reports a nameless card's column as NULL rather than raising — "
          "the flush is every writer's path including the shutter's, and a refusal there is "
          "a lost capture rather than a caught bug")


def case_the_preview_never_migrates() -> None:
    """`cards name` opens the store read-only, and must never reach `db.connect`."""
    home = fresh_home()
    seed_legacy_store(home, 6, 5)
    before_stamp, before_cid = stamp_of(home), has_cid_column(home)

    from cli import cmd_cards

    lines: List[str] = []
    exit_code = cmd_cards.run(type("A", (), {"cards_action": "name"})(), lines.append)
    equal(exit_code, 0, "the preview answers")
    equal(stamp_of(home), before_stamp, "and the stamp is where it was")
    equal(has_cid_column(home), before_cid,
          "and the `cid` column is still absent — a preview routed through `db.connect` "
          "would PERFORM the migration it claims to be previewing, because that function is "
          "the single entry to the store and always calls `_ensure_schema`")
    check(any("disk=5" in line for line in lines),
          "and it says all five cards would be named from their own bytes")

    # BY SOURCE INSPECTION TOO, because the behavioural check above passes for a preview
    # that reaches `db.connect` on a store which happens to need no migration.
    source = (REPO / "cli" / "cmd_cards.py").read_text()
    preview = source.split("def _name(")[1].split("\ndef ")[0]
    # THE CALL, NOT THE NAME. That function's own closing sentence says it never calls
    # `db.connect`, so a check for the bare string fails on the prose that promises the
    # property — which is the shape of a guard that cannot tell a claim from its subject.
    check("db.connect(" not in preview,
          "and `_name`'s own source never CALLS `db.connect`, which is the only way a "
          "preview could perform the migration it is previewing")


def case_the_reverse_restores_every_table_byte_identically() -> None:
    """The reverse is for a store you are about to open with an OLDER checkout."""
    home = fresh_home()
    seed_legacy_store(home, 1, 7)
    baseline = table_bytes(home)
    open_store(home)
    check(has_cid_column(home), "the store is named")

    from store import db

    conn = sqlite3.connect(str(home / "inventory" / "store.sqlite"), isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DROP INDEX IF EXISTS cards_cid")
        conn.execute("DROP INDEX IF EXISTS cards_cid_missing")
        for key, text in conn.execute("SELECT key, payload FROM cards").fetchall():
            record = json.loads(text)
            record.pop("cid", None)
            conn.execute("UPDATE cards SET cid = NULL, payload = ? WHERE key = ?",
                         (json.dumps(record, sort_keys=True, separators=(",", ":")), key))
        conn.execute("DELETE FROM meta WHERE key IN (?, ?)",
                     (db.CARD_IDS_SEEDED, db.CARD_ID_SOURCES))
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('schema', '3')")
        conn.execute("COMMIT")
    finally:
        conn.close()

    after = table_bytes(home)
    identical = []
    for name, rows in baseline.items():
        got = after.get(name)
        if name == "cards":
            # The residue is one empty nullable column, which is invisible to every reader:
            # `Inventory.parse` drops an undeclared field on reload and an all-NULL column
            # changes no query. So the comparison drops it and compares everything else.
            got = [tuple(v for i, v in enumerate(row) if i != len(row) - 1) for row in got]
            rows = [tuple(v for i, v in enumerate(row) if i != len(row) - 1) for row in rows]
        identical.append((name, got == rows))
    equal([name for name, same in identical if not same], [],
          f"all {len(identical)} tables are byte-identical after the reverse, reproducing "
          "`payload_text`'s exact serialization")

    # `cards_fts*` GETS A SEMANTIC CHECK IN PLACE OF THE BYTE-EXACT ONE ABOVE
    # (store-scaling item 8) — the forward migration's raw UPDATE loop, the manual reverse
    # above (also a raw UPDATE), and `_add_search_index`'s own seed all touch `cards_fts`'s
    # shadow tables, whose page layout is not guaranteed byte-stable across an equivalent
    # rebuild even when the logical index is unchanged. What the byte comparison stood in
    # for on every other table — "the reverse didn't corrupt anything" — is a row-count
    # parity check here: every `cards` row has exactly one matching `cards_fts` row, neither
    # more (a stale entry the reverse's raw UPDATE should have retired via the AU trigger)
    # nor fewer (a row the triggers failed to index at all).
    # COUNTED THROUGH THE SHADOW TABLE, NOT THROUGH `cards_fts` ITSELF — a bare
    # `SELECT count(*) FROM cards_fts` fails for the SAME reason a bare `SELECT * FROM
    # cards_fts` does (see `table_bytes`'s docstring): with no `MATCH` constraint SQLite
    # falls back to a full scan that reads every declared column's text back from the
    # content table, and `note` has none there. `cards_fts_docsize` is a REAL table (one row
    # per indexed document, keyed by rowid) rather than the virtual table, so counting it
    # carries none of that restriction.
    conn = raw(home)
    try:
        cards_count = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        fts_count = conn.execute("SELECT COUNT(*) FROM cards_fts_docsize").fetchone()[0]
    finally:
        conn.close()
    equal(fts_count, cards_count,
          "and `cards_fts` holds exactly one row per card after the reverse — the sync "
          "triggers kept the index in step with a raw SQL UPDATE, not only with the ORM's "
          "own write path")


def case_the_forward_version_guard_refuses_a_newer_store() -> None:
    """The silent downgrade, reproduced — and then refused."""
    home = fresh_home()
    seed_legacy_store(home, 3, 4)
    open_store(home)

    conn = sqlite3.connect(str(home / "inventory" / "store.sqlite"), isolation_level=None)
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('schema', '99')")
    conn.close()

    from store import db, files

    try:
        handle = db.connect(home / "inventory")
        handle.close()
        bad("a store stamped ahead of this build is refused at the open")
    except files.StoreError as exc:
        ok("a store stamped ahead of this build is refused at the open")
        check("99" in str(exc) and str(db.SCHEMA_VERSION) in str(exc),
              "and the refusal names both versions")
        check("strips every field" in str(exc),
              "and says what an older build would have done instead: rewritten the stamp "
              "DOWN and then stripped every field it does not declare, one row per write")
    equal(stamp_of(home), 99,
          "and the stamp is UNTOUCHED — the whole defect was that opening rewrote it")


def case_a_renumber_moves_no_file() -> None:
    """THE PAYOFF, COUNTED. Deleting one card used to rename one photograph and rewrite one
    sidecar per higher card — 537 of each on the owner's box 2, 1,608 filesystem operations
    to delete one junk capture. An outcome assertion cannot see that, because the cards end
    up in the right places either way."""
    home = fresh_home()
    from server import capture_server
    from store import photos
    from store.session import Store

    digests = {}
    with Store().write() as snapshot:
        for index in range(1, 11):
            digest = hashlib.sha256(photo_bytes(f"rn-{index}")).hexdigest()
            photos.write(digest, photo_bytes(f"rn-{index}"), home)
            photos.write_sidecar(digest, {"box": 2, "index": index}, home)
            snapshot.inventory.allocate_capture(
                2, capture_id=f"rn-{index}", cid=digest, game="pokemon"
            )
            digests[index] = digest

    with Tally() as tally:
        answer = capture_server.do_remove_card(2, 3, {"capture_id": "rn-3"})
    equal(answer["shifted"], 7, "seven higher cards shifted down one")
    equal(tally.counts["replace"], 0,
          "AND NOT ONE PHOTOGRAPH WAS RENAMED. Under the old layout this was 7 renames; on "
          "the owner's box 2 it was 537. The photographs of the cards behind the target are "
          "not named after their indices, so there is nothing to rename")
    equal(tally.counts["write_json"], 0,
          "and not one sidecar was rewritten — a run's capture directory is a VIEW built "
          "from the store now, so there is nothing on disk left to correct")
    equal(tally.counts["unlink"], 2,
          "the target's own two files went, and nothing else: photo before sidecar, the "
          "money rule")

    # AND THE CARDS REALLY DID MOVE, which is the assertion that would pass on its own and
    # is therefore stated second.
    after = {
        at: card.cid for at, _key, card in Store().read().inventory.records_in(2)
    }
    equal(after.get(3), digests[4],
          "card 4's record is at index 3 now, still wearing its own name — the name did not "
          "move, the record did")
    equal(len(after), 9, "and nine records remain")
    equal(
        sorted(index for index, digest in digests.items()
               if index != 3 and not photos.path(digest, home).is_file()),
        [],
        "and every surviving card's photograph is still at its own name, untouched by the "
        "shift that renumbered its record",
    )


def case_a_move_moves_no_file() -> None:
    """The same measurement for D83's third door, which cost five hand-moved copies."""
    home = fresh_home()
    from server import capture_server
    from store import photos
    from store.session import Store

    digest = hashlib.sha256(photo_bytes("mv")).hexdigest()
    photos.write(digest, photo_bytes("mv"), home)
    photos.write_sidecar(digest, {"box": 1, "index": 1}, home)
    with Store().write() as snapshot:
        snapshot.inventory.allocate_capture(1, capture_id="mv", cid=digest, game="pokemon")

    with Tally() as tally:
        answer = capture_server.do_move_card(1, 1, {"to_box": 4, "capture_id": "mv"})
    equal(tally.touched, 0,
          "A MOVE TOUCHES NO FILE AT ALL — not a rename, not a sidecar rewrite, not an "
          "unlink. It was a rename plus a sidecar write plus a sidecar unlink, ordered "
          "AFTER the store call because the destination index was not knowable before it, "
          "with a crash window this function's docstring conceded in writing")
    check(answer.get("photo_moved") is True,
          "and the route still answers that the photograph travelled with the card, because "
          "it did — that is what filing it under the card's name means")
    check(photos.path(digest, home).is_file(),
          "the photograph is exactly where it was, under the card's own name")
    snapshot = Store().read()
    transplant = snapshot.inventory.cards.get("4/1")
    tombstone = snapshot.inventory.cards.get("1/1")
    equal(transplant.cid if transplant else None, digest,
          "the transplant in box 4 wears the name")
    equal(tombstone.cid if tombstone else None, f"{photos.MOVED_PREFIX}{digest}",
          "and the tombstone wears `moved:` in front of it")


def case_two_captures_cannot_compose_one_photograph_path() -> None:
    """§7 item 3's overwrite of an irreplaceable photograph, ABSENT rather than guarded.

    One remove followed by one capture used to compose a path a live card's photograph still
    occupied — `next_index` allocates off the high-water mark and `files.write_atomic` does
    no existence check. The name is a sha256 that `cards_cid` holds UNIQUE and the path is a
    pure function of it, so the only way to write one name twice is to write the same card
    twice, and the bytes are then the same bytes.
    """
    home = fresh_home()
    from store import photos
    from store.session import Store

    first = hashlib.sha256(photo_bytes("a")).hexdigest()
    photos.write(first, photo_bytes("a"), home)
    with Store().write() as snapshot:
        snapshot.inventory.allocate_capture(1, capture_id="a", cid=first)

    # A second card claiming the SAME name is refused by the index, at the flush.
    try:
        with Store().write() as snapshot:
            snapshot.inventory.allocate_capture(1, capture_id="b", cid=first)
        bad("two cards cannot hold one name")
    except sqlite3.IntegrityError:
        ok("two cards cannot hold one name — `cards_cid` is UNIQUE, and that uniqueness is "
           "what makes two cards unable to compose one photograph's path")
    except Exception as exc:  # noqa: BLE001
        check("UNIQUE" in str(exc) or "unique" in str(exc),
              f"two cards cannot hold one name (refused as {type(exc).__name__})")

    equal(photos.path(first, home), photos.path(first, home),
          "and the path is a pure function of the name, so there is no second input to get "
          "wrong")
    for shape in (f"{photos.MOVED_PREFIX}{first}", f"{photos.NOPHOTO_PREFIX}1/1@", None, ""):
        try:
            photos.path(shape, home)
            bad(f"a path is refused for {shape!r}, which names no photograph")
        except (photos.UnnamedPhotograph, TypeError):
            ok(f"a path is refused for {str(shape)[:18]!r}, which names no photograph")


def case_the_relocation_verifies_every_file_and_resumes() -> None:
    """4.45 GB moves once, per card, checked rather than trusted."""
    home = fresh_home()
    from store import photos

    digests = seed_legacy_store(home, 3, 6)
    open_store(home)

    from cli import cmd_cards

    lines: List[str] = []
    args = type("A", (), {"cards_action": "photos", "write": False, "limit": None})()
    cmd_cards.run(args, lines.append)
    check(any("moved=6" in line for line in lines), "the preview says six would move")
    check(all(photos.legacy_path(3, i, home).is_file() for i in range(1, 7)),
          "and moved none of them — it previews by default, because the corpus cannot be "
          "re-taken")

    with Tally() as tally:
        args = type("A", (), {"cards_action": "photos", "write": True, "limit": None})()
        cmd_cards.run(args, lines.append)
    equal(tally.counts["link"], 12,
          "twelve hard links — a photograph and a sidecar per card. A LINK and not a "
          "rename, because a rename is the one form where the verification happens after "
          "the only other copy is gone")
    equal(tally.counts["unlink"], 12, "and twelve unlinks, each AFTER its destination was "
                                      "re-hashed and found correct")
    check(all(photos.path(d, home).is_file() for d in digests.values()),
          "every photograph is at its card's own name")
    check(not any(photos.legacy_path(3, i, home).is_file() for i in range(1, 7)),
          "and none is left at the address it used to be filed under")

    # RESUMABLE: a leftover source is the footprint of an interrupted run, and a re-run
    # finishes it rather than refusing or duplicating.
    stray = photos.legacy_path(3, 2, home)
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_bytes(photo_bytes("3/2"))
    lines = []
    args = type("A", (), {"cards_action": "photos", "write": True, "limit": None})()
    cmd_cards.run(args, lines.append)
    check(any("already=6" in line for line in lines),
          "a re-run finds all six already at their names and issues no move")
    check(not stray.is_file(),
          "and removes the leftover source, which is step 5 of an interrupted run finishing")

    # AND A SOURCE WHOSE BYTES ARE NOT THE CARD'S IS REFUSED AND LEFT ALONE.
    #
    # THE COUNT IS THE ASSERTION HERE, AND IT HAS TO BE. `adopt` has TWO guards — it hashes
    # the source and refuses before linking, and it re-hashes the DESTINATION and unlinks it
    # if that disagrees — and both end in the same observable outcome: refused, source
    # untouched. So a mutation deleting either one on its own was CAUGHT BY THE OTHER and
    # survived this case, which is exactly the shape a single-arm mutation cannot see. The
    # link tally distinguishes them: with the source check, a bad file is never linked at
    # all; without it, it is linked and then removed. Both are safe, and only one of them
    # touches the destination.
    wrong = photos.legacy_path(3, 4, home)
    wrong.write_bytes(photo_bytes("not-this-card"))
    target = photos.path(digests["3/4"], home)
    target.unlink()
    lines = []
    args = type("A", (), {"cards_action": "photos", "write": True, "limit": None})()
    with Tally() as tally:
        code = cmd_cards.run(args, lines.append)
    check(any("refused=1" in line for line in lines),
          "a file whose bytes do not hash to the card's name is REFUSED")
    equal(tally.counts["link"], 0,
          "and it was never linked in the first place — the source is hashed BEFORE the "
          "destination is touched, so a file that is not the card's costs no write at all")
    check(not target.exists(),
          "and nothing was left at the name it does not have")
    check(wrong.is_file(), "and left exactly where it was, rather than filed under a name "
                           "it does not have")
    check(code != 0, "and the command says so in its exit status")
    check(not any("STAMPED" in line for line in lines),
          "and `photos_relocated` is NOT stamped while a card is unaccounted for, so the "
          "legacy address goes on being read")


def case_a_link_that_did_not_land_the_right_bytes_is_caught() -> None:
    """`adopt`'s SECOND guard, provoked by faking the thing it exists to distrust.

    IT SURVIVED EVERY OTHER MUTATION AND THAT WAS HONEST INFORMATION. `adopt` hashes the
    source and refuses before linking, and it re-hashes the DESTINATION afterwards — so with
    the first guard in place the second can only fire if the link itself did not land the
    bytes that were at the source, which no ordinary test can produce. Deleting it left the
    whole suite green.

    SO THE FILESYSTEM IS FAKED, WHICH IS NOT A CONTRIVANCE — it is the exact fault the guard
    is for. The photographs cannot be re-taken, the move is 2,535 link-and-unlink pairs
    against them, and "the link succeeded so the bytes are right" is an assumption about
    hardware rather than about this program. The guard says: read it back before you drop
    the only other copy. This case makes the link lie and checks that it does.
    """
    home = fresh_home()
    from store import files, photos

    blob = photo_bytes("honest")
    digest = hashlib.sha256(blob).hexdigest()
    source = photos.legacy_path(1, 1, home)
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(blob)

    real_link = os.link

    def lying_link(src, dst, *args, **kw):
        """Land DIFFERENT bytes at the destination, which is the fault under test."""
        Path(dst).write_bytes(photo_bytes("corrupted-in-flight"))

    os.link = lying_link
    try:
        photos.adopt(source, digest, home)
        bad("a link that did not land the right bytes is refused")
    except files.StoreError as exc:
        ok("a link that did not land the right bytes is refused")
        check("did not hash to" in str(exc),
              "and the refusal says the destination disagreed, not that the source did")
    finally:
        os.link = real_link

    check(not photos.path(digest, home).exists(),
          "and the bad destination is REMOVED rather than left under a name it does not "
          "have — a file at the card's name that is not the card's photograph would pass "
          "every existence check in this repo forever")
    check(source.is_file() and source.read_bytes() == blob,
          "and the source is untouched, which is the property the whole link-verify-unlink "
          "order exists for: the only good copy is never dropped on an unverified move")


def case_a_reshoot_is_excused_by_a_recorded_digest_and_never_by_the_fact() -> None:
    """D172 §7 item 1, settled. The excuse must come from a RECORDED digest.

    The one `reshot` event on the owner's store carries two capture ids and NO DIGEST AT ALL,
    so before this the excuse could only ever have been the bare fact of a re-shoot — which
    excuses anything, including a card whose photograph was swapped for another's.
    """
    home = fresh_home()
    import base64

    from cli import cmd_cards
    from server import capture_server
    from store import photos

    first = photo_bytes("shot-one")
    status, body = capture_server.do_capture({
        "box": 1, "image": base64.b64encode(first).decode(), "capture_id": "shot-1",
        "game": "pokemon",
    })
    equal(int(status), 201, "a capture lands")
    name = body["cid"]
    equal(name, hashlib.sha256(first).hexdigest(),
          "and the response carries the card's name, which is the digest of the bytes it "
          "just sent — so the client can address the photograph rather than the slot")

    lines: List[str] = []
    code = cmd_cards.run(
        type("A", (), {"cards_action": "audit", "verbose": False})(), lines.append
    )
    equal(code, 0, "the audit passes on a freshly captured card")

    second = photo_bytes("shot-two")
    capture_server.do_reshoot(1, 1, {
        "image": base64.b64encode(second).decode(), "capture_id": "shot-2",
    })
    check(photos.path(name, home).read_bytes() == second,
          "a re-shoot writes the NEW bytes at the SAME name — the name is frozen, which is "
          "what makes it survive D26 at all")

    lines = []
    code = cmd_cards.run(
        type("A", (), {"cards_action": "audit", "verbose": True})(), lines.append
    )
    equal(code, 0, "and the audit still passes, because the `reshot` event recorded the new "
                   "digest")
    check(any("excused 1" in line for line in lines),
          "and it passes by EXCUSING exactly one card rather than by matching it")
    check(any("re-shot, and the `reshot` line records" in line for line in lines),
          "and the excuse names the recorded digest it came from")

    # NOW MUTATE THE RECORDED DIGEST AND THE AUDIT MUST GO RED. Without this the case proves
    # only that the audit is quiet, not that it is looking.
    conn = sqlite3.connect(str(home / "inventory" / "store.sqlite"), isolation_level=None)
    conn.execute("BEGIN IMMEDIATE")
    for rowid, text in conn.execute(
        "SELECT id, payload FROM events WHERE event = 'reshot'"
    ).fetchall():
        payload = json.loads(text)
        payload["photo_sha256"] = "0" * 64
        conn.execute("UPDATE events SET payload = ? WHERE id = ?", (json.dumps(payload), rowid))
    conn.execute("COMMIT")
    conn.close()

    lines = []
    code = cmd_cards.run(
        type("A", (), {"cards_action": "audit", "verbose": False})(), lines.append
    )
    check(code == 1, "with the recorded digest mutated the audit FAILS — so the excuse is "
                     "drawn from the digest and not from the fact that a re-shoot happened")
    check(any("MISMATCH" in line for line in lines), "and it names the mismatch")


def case_the_audit_says_not_known_rather_than_passing_over_nothing() -> None:
    """Three verdicts, never two. A check over zero rows prints `checked 0, mismatch 0`."""
    home = fresh_home()
    seed_legacy_store(home, 2, 3)

    from cli import cmd_cards

    lines: List[str] = []
    code = cmd_cards.run(
        type("A", (), {"cards_action": "audit", "verbose": False})(), lines.append
    )
    equal(code, 2, "an unnamed store answers `not known`, not `pass`")
    check(any("VERDICT: not known" in line for line in lines), "and says so in as many words")
    check(any("carry no name" in line for line in lines),
          "and says WHICH of the three reasons it is — here, that rows carry no name, which "
          "is a different fact from the column being absent and has a different repair")

    open_store(home)
    lines = []
    code = cmd_cards.run(
        type("A", (), {"cards_action": "audit", "verbose": False})(), lines.append
    )
    equal(code, 0, "and once named, the same store passes")


def case_only_a_store_with_photographs_left_behind_reports_a_residue() -> None:
    """`/status` reports the residue it can SEE, never one inferred from a missing stamp.

    THE FIRST DRAFT CRIED WOLF ON EVERY HEALTHY STORE AND NOTHING COULD SEE IT. `cards
    photos` is what writes `photos_relocated`, so a store that NEVER NEEDED A MOVE never
    carries one — every store created after D172 has its photographs at the card's own name
    from the shutter onward. Treating the missing stamp as evidence made a fresh store
    report a problem on every poll, forever, and a health route that is always complaining
    is one nobody reads.

    THREE SHAPES, AND ONLY THE MIDDLE ONE HAS ANYTHING TO SAY. A test that built only the
    half-moved store would pass against the broken version too, which is why all three are
    here rather than the one the bug was about.
    """
    import base64
    import shutil
    import sqlite3

    from server import capture_server
    from store import photos
    from store.session import Store

    def store_with(tag: str):
        fresh_home()
        for n in range(3):
            capture_server.do_capture({
                "box": 1,
                "image": base64.b64encode(photo_bytes(f"{tag}-{n}")).decode(),
                "capture_id": f"{tag}-{n}",
                "game": "pokemon",
            })

    def says_residue() -> bool:
        return "photographs are still at the legacy" in (
            capture_server.do_status().get("problem") or ""
        )

    store_with("fresh")
    check(not says_residue(),
          "a store born after the naming reports NO residue — it never needed a move, so "
          "the stamp it does not carry is not evidence of one")

    store_with("half")
    card = sorted(Store().read().inventory.cards.values(), key=lambda c: c.index)[0]
    legacy = photos.legacy_path(card.box, card.index)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(photos.path(card.cid), legacy)
    check(says_residue(),
          "a store with a photograph still at the legacy address DOES report one, and names "
          "the command that finishes the move")

    # AND A BOX DIRECTORY THAT IS A SYMLINK IS STILL SEEN, which the first probe was blind to.
    # `pathlib` DELIBERATELY does not follow symlinked directories when it RECURSES, and a
    # throwaway copy of the owner's store is built exactly that way — `captures/cards/box<N>`
    # linked at their real photographs, so 4.45 GB is read without being copied. The route
    # reported NO residue over a full corpus, which is the worst answer a health route has.
    # `photos.first_at_legacy_address` walks the layout it is about instead, one level deep,
    # because an explicit `iterdir` on a symlinked directory DOES follow it.
    store_with("linked")
    card = sorted(Store().read().inventory.cards.values(), key=lambda c: c.index)[0]
    linked_home = Path(os.environ["PKMNSCAN_HOME"])
    real_box = linked_home / "elsewhere" / "box1"
    real_box.mkdir(parents=True, exist_ok=True)
    (real_box / "0001.jpg").write_bytes(photo_bytes("linked-0"))
    legacy_boxes = linked_home / "captures" / "cards"
    legacy_boxes.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(legacy_boxes / "box1", ignore_errors=True)
    (legacy_boxes / "box1").symlink_to(real_box)
    check((legacy_boxes / "box1").is_symlink(),
          "the fixture's box directory really is a symlink, which is the whole subject")
    check(says_residue(),
          "and a photograph behind it is FOUND — a recursive glob skips a symlinked "
          "directory, so the probe walks the layout rather than recursing")

    store_with("done")
    conn = sqlite3.connect(
        str(Path(os.environ["PKMNSCAN_HOME"]) / "inventory" / "store.sqlite"),
        isolation_level=None,
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('photos_relocated', ?)",
        ("2026-09-12T00:00:00.000+00:00",),
    )
    conn.close()
    check(not says_residue(),
          "and a stamped store reports none without looking — the stamp is written only "
          "after a pass that found every card at its name, so it is the authority")
    equal(capture_server.do_status()["photographs_at_legacy_address"], None,
          "which is why the field answers null there rather than false: nothing was asked")


def case_killed_with_minus_nine_leaves_the_store_unchanged() -> None:
    """Proven by doing it, which is `make suite-lock-selftest`'s standard.

    Every write is a row UPDATE or a CREATE INDEX inside one `BEGIN IMMEDIATE … COMMIT`, the
    stamp is the last statement in it, `synchronous = FULL` means the commit reaches disk
    before the call returns, and the operation touches no file outside the database — so
    there is no second half whose ordering against the commit has to be argued. The recovery
    procedure is nothing: the next read runs it again.
    """
    home = fresh_home()
    seed_legacy_store(home, 3, 6)
    baseline = table_bytes(home)

    # A SUBPROCESS RATHER THAN `os.fork`, and the difference is not cosmetic: forking with
    # an open SQLite handle and then killing the child produced SIGSEGV rather than SIGKILL,
    # so the signal the parent observed was 11 and the case was proving "the child died
    # somehow" instead of "the child was killed mid-transaction". A separate process opens
    # its own handle and dies of exactly the signal it was sent.
    import subprocess

    # NO INDENTATION AND NO `textwrap.dedent`: the program is passed to `python3 -c`, where
    # a leading space on the first line is an IndentationError, and a dedent that has to be
    # right about an f-string's own layout is one more thing to get wrong in a test whose
    # whole job is to be trusted.
    store_path = str(home / "inventory" / "store.sqlite")
    program = "\n".join([
        "import sqlite3, sys, time",
        f"conn = sqlite3.connect({store_path!r}, isolation_level=None)",
        "conn.execute('PRAGMA journal_mode = WAL')",
        "conn.execute('PRAGMA synchronous = FULL')",
        "conn.execute('BEGIN IMMEDIATE')",
        "conn.execute('ALTER TABLE cards ADD COLUMN cid_probe TEXT')",
        # DISTINCT PER ROW, because `cards_cid` is UNIQUE and three rows carrying one name
        # is the very thing it refuses — the first draft of this probe wrote `x * 64` three
        # times and was refused, which is the constraint doing its job inside the test that
        # exists to prove the transaction is atomic.
        "for n, row in enumerate(conn.execute('SELECT key FROM cards LIMIT 3').fetchall()):",
        "    conn.execute('UPDATE cards SET cid = ? WHERE key = ?',",
        "                 ('%063x' % n + 'f', row[0]))",
        "sys.stdout.write('mid\\n')",
        "sys.stdout.flush()",
        "time.sleep(30)",
    ])
    child = subprocess.Popen(
        [sys.executable, "-c", program], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True
    )
    first = child.stdout.readline().strip()
    if first != "mid":
        child.kill()
        bad(f"the child reached the middle of an open transaction (said {first!r}, "
            f"stderr {child.stderr.read()[-400:]!r})")
        return
    ok("the child reached the middle of an open transaction")
    child.kill()
    child.wait(timeout=30)
    equal(child.returncode, -9, "and was killed with SIGKILL there")

    after = table_bytes(home)
    equal(sorted(after), sorted(baseline), "no table appeared or vanished")
    equal(after.get("cards"), baseline.get("cards"),
          "and the `cards` table is BYTE-IDENTICAL to the baseline — the DDL is gone too, "
          "because SQLite treats `ALTER TABLE` as transactional")
    conn = raw(home)
    try:
        columns = {r[1] for r in conn.execute("PRAGMA table_info(cards)")}
    finally:
        conn.close()
    check("cid_probe" not in columns, "the added column did not survive either")

    receipt = open_store(home)
    equal(receipt["card_ids_seeded"], 6,
          "and the next read simply runs the naming — the recovery procedure is nothing")


CASES = [
    case_the_seeding_names_every_card_from_its_own_bytes,
    case_the_four_column_rosters_agree,
    case_a_rerun_names_nothing_and_changes_no_name,
    case_a_stripped_name_heals_byte_identically,
    case_the_naming_writes_nothing_outside_the_database,
    case_two_cards_with_one_photograph_get_a_suffix,
    case_the_moved_tombstone_names_no_photograph,
    case_a_card_with_no_photograph_anywhere_is_named_and_not_nulled,
    case_a_new_card_with_no_name_is_refused_at_its_birth,
    case_the_preview_never_migrates,
    case_the_reverse_restores_every_table_byte_identically,
    case_the_forward_version_guard_refuses_a_newer_store,
    case_a_renumber_moves_no_file,
    case_a_move_moves_no_file,
    case_two_captures_cannot_compose_one_photograph_path,
    case_the_relocation_verifies_every_file_and_resumes,
    case_a_link_that_did_not_land_the_right_bytes_is_caught,
    case_a_reshoot_is_excused_by_a_recorded_digest_and_never_by_the_fact,
    case_the_audit_says_not_known_rather_than_passing_over_nothing,
    case_only_a_store_with_photographs_left_behind_reports_a_residue,
    case_killed_with_minus_nine_leaves_the_store_unchanged,
]


def main() -> int:
    print("cid-selftest — the card's name and the photograph store, proved by violating them")
    try:
        for case in CASES:
            print(f"\n{case.__name__}")
            try:
                case()
            except Exception as exc:  # noqa: BLE001 — a raising case is a failing case
                import traceback

                bad(f"{case.__name__} raised {type(exc).__name__}: {exc}")
                traceback.print_exc()
    finally:
        cleanup()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
