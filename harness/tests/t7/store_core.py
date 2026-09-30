"""T7 group: allocator, store, read-only open, store of record, server routes, drain.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import base64
import json
import hashlib
import inspect
import os
import sqlite3
import subprocess
import sys
import threading
import time

from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import Dict, List, Optional
from harness.tests import Checks
from cli import cmd_cards, resolve
from pipeline import join
# `pipeline.skus`, aliased — this module's own `skus` name would collide with
# `store.skus`'s `Skus`/`SkuRow` classes imported right below, and both are used by
# `_seed_sku_table` (identity-follows-sku.md §4.2's review round: a review answer now
# refuses a SKU the `skus` table does not already hold, so fixtures that answer a
# hand-built candidate seed the table first, through the real fold).
from pipeline import skus as sku_pipeline
from server import capture_server
from store import db, files, master
from store.session import Store
from scripts import serve
from harness.tests.t7.common import (
    _SERVE_ROOT,
    REPO_ROOT,
    answers,
    capture_payload,
    entry,
    events_for,
    fake_cid,
    isolated_home,
    photo_of,
    refusal,
    sent_image,
    stored_label,
    stored_payloads,
)

# --------------------------------------------------------------------------- the allocator


def check_next_index_sql(checks: Checks) -> None:
    """`next_index` answered by an indexed read must equal the walk, box by box (D192).

    Two stores: a hand-built one (every state, sections, a gap, an empty registered box, a
    string-typed record) and the demo seed. On a read snapshot the fast path answers; the
    walk (`_next_index_walk`) is the oracle. A record that will not coerce must still
    refuse by name, and a write session must still answer by the walk.
    """
    checks.note("")
    checks.note("NEXT INDEX, INDEXED READ — store/master.py:next_index")

    def compare(inventory, boxes, label):
        bad = [
            (b, inventory.next_index(b), inventory._next_index_walk(b))
            for b in boxes
            if inventory.next_index(b) != inventory._next_index_walk(b)
        ]
        checks.ok(not bad, f"{label}: fast path equals the walk in {len(boxes)} boxes", str(bad))

    with isolated_home():
        with Store().write() as snapshot:
            inv = snapshot.inventory
            for _ in range(5):
                inv.allocate_capture(1, cid=fake_cid(f"nx-{len(inv.cards)}"))
            inv.set_state("1/2", master.SOLD)
            inv.retire("1/3", "lost")
            inv.set_state("1/5", master.MOVED)
            inv.allocate_capture(2, cid=fake_cid("nx-b2"))
            inv.open_section(2)
            inv.allocate_capture(2, cid=fake_cid("nx-b2s"))
            inv.ensure_box(9)
            del inv.cards["2/1"]
            inv.cards["4/1"] = master.Card(box="4", index="1")
            inv.cards["8/0"] = master.Card(box=8, index=0)
            inv.cards["10/-3"] = master.Card(box=10, index=-3)
        read = Store().read().inventory
        compare(read, [0, 1, 2, 3, 4, 8, 9, 10, 77], "hand-built")
        checks.equal(
            (read.next_index(8), read.next_index(10)), (1, 1),
            "a box holding only idx <= 0 starts at 1, as the walk does",
        )
        checks.equal(read.next_index(1), 6, "sold, retired and moved cards still hold the mark")
        checks.equal(read.next_index(9), 1, "a registered empty box starts at 1")
        checks.equal(read.next_index(77), 1, "an unknown box starts at 1")
        checks.equal(read.next_index(2), 3, "a deleted low index leaves the mark on the end")
        checks.equal(read.next_index(4), 2, "a string-typed record still counts")
        with Store().write() as snapshot:
            snapshot.inventory.allocate_capture(3, cid=fake_cid("nx-w"))
            checks.equal(snapshot.inventory.next_index(3), 2, "a write session answers by the walk")
            # IN-PLACE MUTATION, the one shape the source's index cannot see: a write session
            # must answer from the live object, never from the stale column.
            snapshot.inventory.cards["3/1"].index = 8
            checks.equal(
                snapshot.inventory.next_index(3), 9,
                "a card moved in place inside a write session is seen (no fast path there)",
            )
            snapshot.inventory.cards["3/1"].index = 1
            snapshot.inventory.cards["6/1"] = master.Card(box="six", index=1)
        checks.raises(
            master.BadPosition, lambda: Store().read().inventory.next_index(1),
            "a record that will not coerce refuses in EVERY box, by the walk",
        )

    with isolated_home() as home:
        seed = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "demo-seed.py"),
             "--force"],
            capture_output=True, text=True, env={**os.environ, files.HOME_ENV: str(home)},
        )
        checks.ok(seed.returncode == 0, "the demo seed builds", seed.stderr[-300:])
        read = Store().read().inventory
        boxes = sorted({int(b) for b in read.boxes} | {int(c.box) for c in read.cards.values()})
        compare(read, boxes, "demo seed")

def check_allocator(checks: Checks) -> None:
    """The seventeen cases `docs/debts/` enumerates, plus the coercion that caused them.

    `allocate_capture` is the one piece of step-5 logic Gate B exercised 53 times in a
    row on 2026-08-22, and it is the only place in the project that decides where a physical
    card is.
    """
    checks.note("")
    checks.note("ALLOCATOR — store/master.py")

    inventory = master.Inventory()
    checks.equal(inventory.next_index(3), 1, "an empty box starts at index 1")

    first, created = inventory.allocate_capture(3, cid=fake_cid("alloc-3-1"))
    checks.ok(created, "the first allocation into an unseen box creates it implicitly")
    checks.equal(first.key, "3/1", "first card is keyed 3/1")

    second, _ = inventory.allocate_capture(3, cid=fake_cid("alloc-3-2"))
    checks.equal(second.key, "3/2", "allocation is sequential")

    other, _ = inventory.allocate_capture(7, cid=fake_cid("alloc-7-1"))
    checks.equal(other.key, "7/1", "boxes are independent — box 7 starts over at 1")
    checks.equal(inventory.next_index(3), 3, "and allocating into 7 left box 3 untouched")

    # D10: sold cards leave permanent gaps. The high-water mark counts every state, so a
    # sale does not hand its slot to the next card — which is what makes a printed position
    # label worth trusting a year later.
    checks.ok(
        inventory.set_state("3/2", master.SOLD),
        "a card can be marked sold",
    )
    checks.equal(
        inventory.next_index(3),
        3,
        "D10: a sold card keeps its position — the next index steps past it, not into it",
    )
    checks.ok(
        inventory.get("3/2") is not None,
        "and the sold card keeps its record: sold is a state, never a removal",
    )

    # The behaviour undo inherits (D10, settled 2026-08-12). Deleting the newest record
    # releases its index; this is asserted because step 7's undo is built on it, and a
    # refactor that changed it would silently change what undo does.
    scratch = master.Inventory()
    scratch.allocate_capture(1, cid=fake_cid("scratch-1"))
    newest, _ = scratch.allocate_capture(1, cid=fake_cid("scratch-2"))
    checks.equal(scratch.next_index(1), 3, "two cards in box 1, next index is 3")
    del scratch.cards[newest.key]
    checks.equal(
        scratch.next_index(1),
        2,
        "deleting the NEWEST record releases its index — what undo inherits (D10)",
    )

    # The measured bug. A record whose box and index arrived as JSON strings must be
    # COUNTED, not skipped: skipping it returns an index that collides later, and the
    # collision surfaces as one physical card overwriting another.
    stringy = master.Inventory()
    stringy.cards["4/1"] = master.Card(box="4", index="1")
    checks.equal(
        stringy.next_index(4),
        2,
        "a string-typed record is counted, not silently skipped past",
    )
    checks.equal(
        stringy.next_index("4"),
        2,
        "and a string-typed box argument coerces the same way",
    )

    unparsable = master.Inventory()
    unparsable.cards["5/1"] = master.Card(box="five", index=1)
    caught = checks.raises(
        master.BadPosition,
        lambda: unparsable.next_index(5),
        "an unparsable box refuses rather than guessing",
    )
    if caught is not None:
        checks.ok(
            "5/1" in str(caught),
            "and the refusal names the offending card",
            f"message was: {caught}",
        )

    # The retry guard. A response lost between commit and client makes the app repost; the
    # capture_id is what stops that from burning a second index for one physical card.
    replay = master.Inventory()
    # ONE NAME ACROSS BOTH CALLS, WHICH IS THE TRUTHFUL FIXTURE HERE (D172). A repost is the
    # same photograph arriving twice, so `do_capture` hashes the same bytes to the same
    # `cid` — and the replay branch returns before `record_capture`, so the second call
    # never reaches the name at all. Two distinct names would describe two physical cards,
    # which is the thing this guard exists to stop happening.
    reposted = fake_cid("replay-2-1")
    original, first_created = replay.allocate_capture(2, capture_id="abc", cid=reposted)
    again, second_created = replay.allocate_capture(2, capture_id="abc", cid=reposted)
    checks.ok(first_created and not second_created, "a replayed capture_id reports created=False")
    checks.equal(again.key, original.key, "and returns the original card")
    checks.equal(replay.next_index(2), 2, "and burns no second index")

    duplicated = master.Inventory()
    duplicated.cards["1/1"] = master.Card(box=1, index=1, capture_id="dup")
    duplicated.cards["1/2"] = master.Card(box=1, index=2, capture_id="dup")
    caught = checks.raises(
        master.DuplicateCaptureId,
        lambda: duplicated.card_by_capture_id("dup"),
        "one capture_id on two cards refuses rather than picking one",
    )
    if caught is not None:
        checks.ok(
            "1/1" in str(caught) and "1/2" in str(caught),
            "and the refusal names both positions",
            f"message was: {caught}",
        )

    # A field not declared on Card is dropped by `parse`, which is why the retry guard could
    # not live in the sidecar alone. Asserted so that stays true.
    round_trip = master.Inventory.parse(replay.to_payload())
    checks.equal(
        round_trip.cards[original.key].capture_id,
        "abc",
        "capture_id survives a JSON round trip through to_payload and parse",
    )

    events = master.Inventory()
    events.allocate_capture(9, cid=fake_cid("events-9-1"))
    captured = [e for e in events.events if e.get("event") == master.CAPTURED]
    checks.equal(len(captured), 1, "allocation logs exactly one captured event")
    checks.equal(captured[0].get("position"), "9/1", "and the event carries the position")

    checks.equal(
        master.position_key(3, 17), "3/17", "position_key renders box/index"
    )
    checks.raises(
        master.UnknownState,
        lambda: master.check_state("nearly-sold"),
        "a state outside the enum is refused, never coerced",
    )
    checks.ok(
        not master.Inventory().set_state("99/99", master.IDENTIFIED),
        "set_state on an unknown position returns False rather than pretending (v1 bug 5)",
    )

# ------------------------------------------------------------------------------- the store


def check_store(checks: Checks) -> None:
    """The session: isolation, the re-read inside the lock, and nothing written on error."""
    checks.note("")
    checks.note("STORE SESSION — store/files.py, store/session.py")

    with isolated_home() as home:
        checks.equal(
            files.home(),
            home.resolve(),
            "files.home() reads PKMNSCAN_HOME per call — the whole test rests on this",
        )

        with Store().write() as snapshot:
            snapshot.inventory.allocate_capture(3, cid=fake_cid("committed"))
        checks.equal(
            Store().read().inventory.next_index(3), 2, "a committed write is visible to a later read"
        )

        # Nothing is written when an exception escapes the block. The writes happen after
        # the yield, so a crash halfway through a transition leaves the store as it was.
        try:
            with Store().write() as snapshot:
                snapshot.inventory.allocate_capture(3, cid=fake_cid("abandoned"))
                raise RuntimeError("deliberate")
        except RuntimeError:
            pass
        checks.equal(
            Store().read().inventory.next_index(3),
            2,
            "an exception inside write() commits nothing — the store is as it was",
        )

        history = Store().history()
        checks.equal(
            len([e for e in history if e.get("event") == master.CAPTURED]),
            1,
            "and the abandoned capture left no history event either",
        )

        checks.ok(
            not list(Store().directory.glob(".*.tmp")),
            "and nothing is staged beside the database — the transaction is the atomicity",
        )

def check_set_and_rarity(checks: Checks) -> None:
    """D213: the schema migration
    (`store/db.py:_add_set_columns`) and the backfill, which is `cards identity --write`
    since identity-follows-sku.md retired `cards variants` (§4.2).

    THE MIGRATION HALF: an old store, stamped 7, gains `set_name` and `rarity` with every
    row preserved and the 99 `UNL` rows swept to `Unleashed` in the same pass — built by
    hand from `db.TABLES`/`db._INDEXES` minus the two new members, the same shape
    `store/db.py`'s own docstring for `_add_search_index` argues an upgrade must be additive
    against.

    THE BACKFILL HALF: `./pkmnscan cards variants --write` refuses, names `cards identity`,
    and writes nothing. That is the arm a restored direct `card.set_name = ...` turns red.
    Then the replacement, over its own code path: `skus adopt`'s fill, then
    `./pkmnscan cards identity --write`. A SKU the table holds gets a real set and rarity
    through `bind_sku`. A SKU the table lacks keeps a null set and its own record — never
    guessed, never dropped.
    """
    checks.note("")
    checks.note("SET + RARITY — store/db.py schema 8, cli/cmd_cards.py `identity`")

    # ---------------------------------------------------------------- the migration itself
    with isolated_home():
        directory = files.inventory_dir()
        directory.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db.path(directory)))
        for table, columns in db.TABLES.items():
            cols = [c for c in columns if c not in ("set_name", "rarity")]
            conn.execute(db._ddl(table, cols))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "at TEXT, event TEXT, position TEXT, payload TEXT NOT NULL)"
        )
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        for table, column in db._INDEXES:
            if column == "set_name":
                continue
            conn.execute(f"CREATE INDEX IF NOT EXISTS {table}_{column} ON {table}({column})")
        for statement in db._CID_INDEXES:
            conn.execute(statement)
        db._add_search_index(conn)
        conn.execute("INSERT INTO meta (key, value) VALUES ('schema', '7')")
        conn.execute(
            "INSERT INTO cards (key, box, idx, state, sku, condition, set_hint, name, "
            "number, game, payload) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "1/1", 1, 1, master.IDENTIFIED, "SKU1", "Near Mint", "UNL", "Calm Rune",
                "045", "riftbound", json.dumps({"box": 1, "index": 1}),
            ),
        )
        conn.commit()

        before = {row[1] for row in conn.execute("PRAGMA table_info(cards)").fetchall()}
        checks.ok(
            "set_name" not in before and "rarity" not in before,
            "the fixture really starts on schema 7, with neither column",
        )

        db._upgrade(conn, 7, directory=directory, locked=True)

        after = {row[1] for row in conn.execute("PRAGMA table_info(cards)").fetchall()}
        checks.ok(
            {"set_name", "rarity"} <= after,
            "the upgrade adds both columns",
            f"columns: {sorted(after)}",
        )
        checks.equal(
            conn.execute("SELECT count(*) FROM cards").fetchone()[0],
            1,
            "and preserves every row — an upgrade is additive and never drops one",
        )
        checks.equal(
            conn.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()[0],
            str(db.SCHEMA_VERSION),
            "stamped at the new version",
        )
        checks.equal(
            conn.execute("SELECT set_hint FROM cards WHERE key = '1/1'").fetchone()[0],
            "Unleashed",
            "and the 99 `UNL` rows from 2026-08-29 are swept to `Unleashed` in the same "
            "migration",
        )
        checks.equal(
            conn.execute("SELECT set_name, rarity FROM cards WHERE key = '1/1'").fetchone(),
            (None, None),
            "while the two new columns stay null — the migration is schema only, and the "
            "backfill below is the separate, re-runnable step that fills them",
        )
        conn.close()

    # ------------------------------------------------------------------- the backfill itself
    with isolated_home() as home:
        exports = home / "inventory" / ".exports" / "riftbound"
        exports.mkdir(parents=True)
        # A STAMPED NAME, `_keep_export`'s own shape: `skus adopt` skips a file whose name
        # carries no stamp (pipeline/skus.py:stamp_of), and the old `export.csv` has none.
        (exports / "export-tcgplayer-20260901-120000-0123abcd.csv").write_text(
            "TCGplayer Id,Product Line,Set Name,Product Name,Number,Rarity,Condition,"
            "TCG Market Price,Total Quantity\r\n"
            "CR-VEN-001,Riftbound League of Legends Trading Card Game,Vendetta,"
            "Mind Rune,R03a,Showcase,Near Mint Foil,1.00,0\r\n",
            encoding="utf-8",
        )
        with Store().write() as snapshot:
            inv = snapshot.inventory
            resolvable, _ = inv.allocate_capture(1, game="riftbound", cid=fake_cid("resolvable"))
            resolvable_key = resolvable.key
            card = inv.cards[resolvable_key]
            card.name, card.number = "Mind Rune", "R03a"
            card.sku, card.condition = "CR-VEN-001", "Near Mint Foil"
            card.state = master.IDENTIFIED

            unresolvable, _ = inv.allocate_capture(
                1, game="riftbound", cid=fake_cid("unresolvable")
            )
            unresolvable_key = unresolvable.key
            card2 = inv.cards[unresolvable_key]
            card2.name, card2.number = "Mind Rune", "R03a"
            card2.sku, card2.condition = "CR-GHOST-999", "Near Mint Foil"
            card2.state = master.IDENTIFIED

        class Args:
            def __init__(self, action: str, write: bool):
                self.cards_action = action
                self.write = write

        say_lines: List[str] = []
        code = cmd_cards.run(Args("variants", write=True), say_lines.append)
        checks.equal(code, 2, "`cards variants --write` is retired, and refuses with exit 2")
        checks.ok(
            any("cards identity" in line for line in say_lines),
            "and its one line names `cards identity`, the press that replaced it",
            f"said: {say_lines!r}",
        )
        retired = Store().read().inventory.cards[resolvable_key]
        checks.equal(
            (retired.set_name, retired.rarity),
            (None, None),
            "and it writes nothing — no card field is assigned outside the one writer "
            "(identity-follows-sku.md §4.1)",
        )

        # A READ SNAPSHOT HELD OPEN ACROSS THE FILL AND THE PRESS, ON PURPOSE. An open
        # connection stops SQLite from checkpointing the WAL on close, so the fill's commit
        # stays in `store.sqlite-wal`. The live rig is always in this state, because the
        # capture server holds connections. `cmd_cards._read_only` once opened the store
        # `immutable=1`, which never reads the WAL: it saw an empty `skus` table and bound
        # nothing. CI caught it only when garbage collection happened to leave the read
        # above open. Holding one here makes the case run every time, on every platform.
        open_reader = Store().read()
        open_reader.inventory.cards.get(resolvable_key)
        with Store().write() as snapshot:
            sku_pipeline.fill(snapshot.skus, snapshot.inventory.events)
        say_lines = []
        code = cmd_cards.run(Args("identity", write=True), say_lines.append)
        checks.equal(code, 0, "`cards identity --write` runs over the same store")
        del open_reader

        after_inv = Store().read().inventory
        resolved = after_inv.cards[resolvable_key]
        checks.equal(
            (resolved.set_name, resolved.rarity, resolved.identity_source, resolved.bound_by),
            ("Vendetta", "Showcase", master.IDENTITY_SKU, "migration"),
            "the replacement fills a real SKU's set and rarity from the SKU table, through "
            "bind_sku",
        )
        ghost = after_inv.cards[unresolvable_key]
        checks.ok(
            ghost.set_name is None and ghost.rarity is None and ghost.sku == "CR-GHOST-999"
            and ghost.identity_source != master.IDENTITY_SKU,
            "and a SKU the table lacks keeps a null set and its own record — "
            "never guessed and never dropped",
            f"card: sku={ghost.sku!r} set_name={ghost.set_name!r} "
            f"identity_source={ghost.identity_source!r}",
        )

    # ------------------------------------------------------- the real collision, on the wire
    # D213's own worked example: two SKUs
    # identical in name, number, rarity and condition, differing only by set, with
    # `set_hint` NULL on both — the exact shape that made the chooser draw two
    # indistinguishable tiles before this item.
    with isolated_home():
        with Store().write() as snapshot:
            inv = snapshot.inventory
            for n, (sku, set_name) in enumerate(
                (("CR-SPI-001", "Spiritforged"), ("CR-UNL-001", "Unleashed")), start=1
            ):
                allocated, _ = inv.allocate_capture(1, game="riftbound", cid=fake_cid(f"collision-{n}"))
                card = inv.cards[allocated.key]
                card.name, card.number = "Mind Rune", "R03a"
                card.sku, card.condition = sku, "Near Mint Foil"
                card.set_name, card.rarity = set_name, "Showcase"
                card.state = master.IDENTIFIED

        result = capture_server.do_search("Mind Rune")
        checks.equal(len(result["groups"]), 2, "two SKUs, two groups")
        sets = sorted(str(g["set"]) for g in result["groups"])
        checks.equal(
            sets,
            ["Spiritforged", "Unleashed"],
            "the two groups disagree on `set` although `set_hint`, `condition` and "
            "`rarity` all agree — the one field a chooser tile can key its distinctness "
            "off, which is the whole of what this item was built to restore",
        )
        checks.ok(
            all(g["set_hint"] is None for g in result["groups"]),
            "and `set_hint` stays null on both — the real collision this was measured "
            "against, not a fixture that quietly gives the chooser an easier field",
        )

@contextmanager
def _no_new_files_in(directory: Path):
    """Strips write permission from `directory` for the block, restoring it in `finally` so
    `isolated_home`'s own `TemporaryDirectory` cleanup can still remove it afterward.

    THE REAL CAUSE, MEASURED, NOT THE FIRST GUESS: a cold, fully-checkpointed WAL store (no
    `-wal`/`-shm`) makes a plain `mode=ro` open FAIL on this Mac's SQLite 3.54, with the
    directory left writable throughout — measured directly, same directory, same missing
    side files, same connection string, both with and without this context manager wrapped
    around it. So `open_read_only`'s fallback path is reached here regardless of directory
    permission, and the coordinator's first reading (a writable directory is what lets a
    cold `mode=ro` open succeed) does not hold on this platform. What DOES hold, on every
    SQLite build this repo could find a citation for: `-shm` is a file the WAL locking
    machinery creates on first touch, and creating any file needs write permission on its
    directory — a `mode=ro` connection has never been documented promising to skip that need,
    only to refuse writes to the database's own contents once open. A CI runner's bundled
    SQLite (Ubuntu 24.04's `actions/setup-python@v5` 3.11 build) may simply create `-shm` on
    a read-only-mode open where this Mac's refuses to — that is a real, plausible version
    difference this repo cannot reproduce locally (no second Python build, no container
    runtime on this checkout) — but EITHER WAY, taking directory write permission away is
    the one condition no SQLite version can route around: `-shm` cannot be created without
    it, so the plain `mode=ro` attempt fails for the same underlying reason on every
    platform, and `open_read_only`'s fallback is what this fixture is FOR.
    """
    directory = Path(directory)
    mode = directory.stat().st_mode
    directory.chmod(0o555)
    try:
        yield
    finally:
        directory.chmod(mode)

def check_open_read_only(checks: Checks) -> None:
    """`store/db.py:open_read_only`, the one read-only door: it never migrates, and it sees
    every commit, including one still in the WAL.

    THE CASE THAT BROKE: one connection holds a read snapshot open, so SQLite cannot
    checkpoint on close, and a second connection's commit stays in `store.sqlite-wal`. An
    always-immutable open never reads the WAL. The fixture proves it builds that state (the
    old open misses the commit) before it asks the door, so a green here is not a fixture
    that never made the case.
    """
    checks.note("")
    checks.note("READ-ONLY DOOR — store/db.py open_read_only")
    with isolated_home():
        directory = files.inventory_dir()
        directory.mkdir(parents=True, exist_ok=True)
        db.connect(directory).close()
        target = db.path(directory)

        holder = sqlite3.connect(str(target), isolation_level=None)
        holder.execute("BEGIN")
        holder.execute("SELECT count(*) FROM meta").fetchone()
        writer = sqlite3.connect(str(target), isolation_level=None)
        writer.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('door', 'seen')")
        writer.close()

        old = sqlite3.connect(f"file:{target}?mode=ro&immutable=1", uri=True)
        checks.equal(
            old.execute("SELECT value FROM meta WHERE key = 'door'").fetchone(),
            None,
            "the fixture really leaves the commit in the WAL: an always-immutable open "
            "misses it",
        )
        old.close()

        door = db.open_read_only(target)
        checks.equal(
            door.execute("SELECT value FROM meta WHERE key = 'door'").fetchone(),
            ("seen",),
            "the door sees a commit still in the WAL, while another connection holds a "
            "snapshot open",
        )
        refused = False
        try:
            door.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('door', 'wrote')")
        except sqlite3.OperationalError:
            refused = True
        checks.ok(refused, "and it refuses a write")
        door.close()
        holder.execute("ROLLBACK")
        holder.close()

        # THE COLD STATE, BUILT BY HAND. Whether SQLite deletes the side files on the last
        # close varies by build (this Mac's keeps them), so the fixture checkpoints the WAL
        # empty and removes both, `db.py`'s own import step's shape.
        folder = sqlite3.connect(str(target), isolation_level=None)
        folder.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        folder.close()
        for side in ("-wal", "-shm"):
            Path(f"{target}{side}").unlink(missing_ok=True)
        with _no_new_files_in(directory):
            # PROBE THE PLAIN OPEN'S OWN REFUSAL FIRST, SEPARATELY, SO THE PASS LINE BELOW
            # NAMES THE REAL BUILD'S CODE — this is the harness's own answer to guessing a
            # build's error code twice and being wrong twice (PR #463): never guess again,
            # measure and print it. `open_read_only` below makes its own, separate attempt
            # right after — same file, same permission state, so the shape it sees is the
            # same one this probe just recorded.
            probe = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
            errorname: Optional[str] = None
            errormessage: Optional[str] = None
            try:
                probe.execute("PRAGMA schema_version")
            except sqlite3.OperationalError as exc:
                errorname = getattr(exc, "sqlite_errorname", None)
                errormessage = str(exc)
            finally:
                probe.close()

            cold = db.open_read_only(target)
            checks.equal(
                cold.execute("SELECT value FROM meta WHERE key = 'door'").fetchone(),
                ("seen",),
                "and the door still opens a WAL store with no side files, and reads the "
                "commit from the main file — this build's plain open refused with "
                f"sqlite_errorname={errorname!r} message={errormessage!r}",
            )
            cold.close()
            checks.ok(
                not any(Path(f"{target}{side}").exists() for side in ("-wal", "-shm")),
                "and opening it cold created no side file",
            )

def check_open_read_only_race(checks: Checks) -> None:
    """`open_read_only` checks the WAL, then opens, in two steps — and a commit that lands
    between them sends it down the `immutable=1` path anyway, then misses that exact commit.
    SQLite's own docs for `immutable`: a file that changes under an immutable connection
    "might return incorrect query results and/or SQLITE_CORRUPT errors".

    FORCED DETERMINISTICALLY, NO THREAD AND NO SLEEP. `sqlite3.connect` is monkeypatched to
    land a commit the instant `open_read_only` asks for the `immutable=1` connection — the
    race landing on purpose, every run, in the exact gap between the failed plain `mode=ro`
    open and the immutable fallback, rather than the small chance a real thread interleaving
    would give it.

    THE COMMIT MUST STAY IN THE WAL, NOT AUTO-CHECKPOINT AWAY ON ITS OWN WRITER'S CLOSE — a
    plain "open, write, close" with nothing else holding the file open lets SQLite checkpoint
    it into the main file right there, which would prove nothing: an `immutable=1` open right
    after would read it from the main file regardless, race or no race. `check_open_read_only`
    above already holds the WAL open the same way — a `holder` connection with a `SELECT`
    inside an open transaction — for exactly this reason, and this reuses it.
    """
    checks.note("")
    checks.note("READ-ONLY DOOR RACE — a commit lands between the check and the open")
    with isolated_home():
        directory = files.inventory_dir()
        directory.mkdir(parents=True, exist_ok=True)
        db.connect(directory).close()
        target = db.path(directory)

        # THE COLD STATE, `check_open_read_only`'s own recipe: no side files, so
        # `open_read_only`'s plain `mode=ro` attempt is guaranteed to refuse and reach the
        # immutable fallback this test targets.
        folder = sqlite3.connect(str(target), isolation_level=None)
        folder.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        folder.close()
        for side in ("-wal", "-shm"):
            Path(f"{target}{side}").unlink(missing_ok=True)

        real_connect = sqlite3.connect
        fired = {"n": 0}
        state: Dict[str, Optional[sqlite3.Connection]] = {"holder": None}
        original_mode = directory.stat().st_mode

        def racing_connect(database, *args, **kwargs):
            if fired["n"] == 0 and "immutable=1" in str(database):
                fired["n"] += 1
                # `_no_new_files_in`'s own restriction is lifted HERE, before the simulated
                # external writer below — that writer needs directory write permission to
                # create its OWN `-wal`/`-shm` too, the same requirement this whole fixture
                # is built on. Only the plain `mode=ro` attempt above this needed to be
                # denied; the race it races against never did.
                directory.chmod(original_mode)
                # A live connection that keeps a read snapshot open through the rest of
                # this test — the thing that stops the writer's own close from
                # auto-checkpointing its commit into the main file. Closed in `finally`
                # below, never leaked.
                holder = real_connect(str(target), isolation_level=None)
                holder.execute("BEGIN")
                holder.execute("SELECT count(*) FROM meta").fetchone()
                state["holder"] = holder
                writer = real_connect(str(target), isolation_level=None)
                writer.execute(
                    "INSERT OR REPLACE INTO meta (key, value) VALUES ('race', 'landed')"
                )
                writer.close()
            return real_connect(database, *args, **kwargs)

        directory.chmod(0o555)  # `_no_new_files_in`'s own reason: forces the plain `mode=ro`
        # attempt below to refuse on every platform, never only on the one this was measured
        # on — see that context manager's docstring, above `check_open_read_only`.
        sqlite3.connect = racing_connect
        try:
            door = db.open_read_only(target)
        finally:
            sqlite3.connect = real_connect
            directory.chmod(original_mode)

        try:
            checks.equal(fired["n"], 1, "the race actually fired once, at the immutable open")
            checks.ok(
                Path(f"{target}-wal").stat().st_size > 0,
                "and the fixture really left the commit stranded in the WAL, unchecked "
                "against a version that never reaches the immutable branch at all",
            )
            checks.equal(
                door.execute("SELECT value FROM meta WHERE key = 'race'").fetchone(),
                ("landed",),
                "a commit landing between the failed plain open and the immutable fallback "
                "is still seen, never served from a stale immutable connection that missed "
                "it",
            )
            door.close()
        finally:
            holder = state["holder"]
            if holder is not None:
                holder.execute("ROLLBACK")
                holder.close()

def check_open_read_only_wal_present_never_falls_back(checks: Checks) -> None:
    """`open_read_only`'s fallback is keyed on what makes `immutable=1` SAFE — an absent or
    empty `-wal` — never on which error the plain open raised (PR #463: two builds raised
    two different codes for the identical fixture, and naming each one in turn was tried
    twice and was wrong twice). This proves the other half of that rule: a plain-open
    failure while `-wal` genuinely holds a commit the main file does not yet have is RAISED,
    never swallowed, whatever shape the failure takes — falling back there would silently
    serve a stale snapshot.

    FORCED DETERMINISTICALLY, no thread: `sqlite3.connect` is monkeypatched so the plain
    `mode=ro` open's own forced statement raises, while a real `holder` connection —
    `check_open_read_only`'s own trick — keeps a genuine, uncheckpointed commit stranded in
    `-wal` throughout.
    """
    checks.note("")
    checks.note("READ-ONLY DOOR — a real WAL is never traded for a stale immutable snapshot")
    with isolated_home():
        directory = files.inventory_dir()
        directory.mkdir(parents=True, exist_ok=True)
        db.connect(directory).close()
        target = db.path(directory)

        # A REAL commit stranded in the WAL — `check_open_read_only`'s own recipe: `holder`
        # keeps a read snapshot open so nothing auto-checkpoints `writer`'s commit away.
        holder = sqlite3.connect(str(target), isolation_level=None)
        holder.execute("BEGIN")
        holder.execute("SELECT count(*) FROM meta").fetchone()
        writer = sqlite3.connect(str(target), isolation_level=None)
        writer.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('door', 'stranded')")
        writer.close()

        try:
            checks.ok(
                Path(f"{target}-wal").stat().st_size > 0,
                "the fixture really left a commit in the WAL before the plain open is even "
                "asked to fail",
            )

            real_connect = sqlite3.connect

            class _AlwaysFailsPlainOpen:
                """Stands in for the plain `mode=ro` connection and refuses its forced
                statement outright — the SHAPE of the refusal is deliberately generic
                (`disk I/O error`, no `sqlite_errorname` at all), because this property
                must hold whatever a real build's own refusal looks like."""

                def execute(self, *_args, **_kwargs):
                    raise sqlite3.OperationalError("disk I/O error")

                def close(self) -> None:
                    pass

            def failing_plain_connect(database, *args, **kwargs):
                if "immutable=1" not in str(database) and "mode=ro" in str(database):
                    return _AlwaysFailsPlainOpen()
                return real_connect(database, *args, **kwargs)

            sqlite3.connect = failing_plain_connect
            try:
                checks.raises(
                    sqlite3.OperationalError,
                    lambda: db.open_read_only(target),
                    "a plain-open failure while the WAL genuinely holds a commit raises, "
                    "never falls back to a stale immutable snapshot",
                )
            finally:
                sqlite3.connect = real_connect
        finally:
            holder.execute("ROLLBACK")
            holder.close()

def check_open_read_only_corrupt_main_file(checks: Checks) -> None:
    """The immutable fallback forces ITS OWN open too (`PRAGMA schema_version`, the same
    reason the plain open forces its own), so a genuinely corrupt or unreadable main file
    raises there and is never handed back as a connection that looks fine until its first
    real query — `open_read_only` never falls back a second time to paper over a bad file.
    """
    checks.note("")
    checks.note("READ-ONLY DOOR — a corrupt main file is refused, never served")
    with isolated_home():
        directory = files.inventory_dir()
        directory.mkdir(parents=True, exist_ok=True)
        target = db.path(directory)
        target.write_bytes(b"not a sqlite database, not even close")
        # `sqlite3.DatabaseError`, THE BROADER CLASS, NOT `OperationalError`: "file is not a
        # database" is SQLite's own `SQLITE_NOTADB`, and Python's sqlite3 module raises it as
        # a plain `DatabaseError` rather than the narrower `OperationalError` subclass the
        # cold-store refusal above raises. `open_read_only` only ever catches
        # `OperationalError`, so this one was never going to be caught either way — this
        # proves that, rather than assuming it.
        checks.raises(
            sqlite3.DatabaseError,
            lambda: db.open_read_only(target),
            "a garbage main file raises rather than returning a connection — corruption is "
            "never mistaken for the cold-store state the fallback exists for",
        )

def check_store_of_record(checks: Checks) -> None:
    """D88: one transaction over every table, a session that loads only what it names, and
    a legacy JSON store imported whole on the first open and moved aside rather than read.

    THE TORN-SET CASE IS THE ONE THIS ENTRY EXISTS FOR. `store/session.py`'s header spent
    a week saying a kill between two `write_json` calls left the inventory saying one thing
    and a queue that was meant to move with it saying another. It is simulated here by the
    only means that reaches it: the queue table's write raises after the cards table's has
    run, inside one session, and NEITHER lands.
    """
    checks.note("")
    checks.note("STORE OF RECORD — store/db.py, store/rows.py (D88)")

    with isolated_home():
        with Store().write() as snapshot:
            snapshot.inventory.allocate_capture(3, capture_id="seed", cid=fake_cid("seed"))
        checks.ok(
            db.path(files.inventory_dir()).is_file(),
            "a fresh store is one SQLite file",
        )

        # --------------------------------------------------- one transaction, or nothing
        real_upsert = db.SqliteSource.upsert

        def torn(self, key, columns, payload):
            if self.table == "queues":
                raise RuntimeError("deliberate: the queue write fails after the card write")
            return real_upsert(self, key, columns, payload)

        db.SqliteSource.upsert = torn
        try:
            with Store().write() as snapshot:
                snapshot.inventory.allocate_capture(3, capture_id="torn", cid=fake_cid("torn"))
                snapshot.review.upsert(entry(3, 2))
        except RuntimeError:
            pass
        finally:
            db.SqliteSource.upsert = real_upsert
        after = Store().read()
        checks.equal(
            after.inventory.next_index(3),
            2,
            "a write that fails on the SECOND table commits the FIRST table's rows either — "
            "the five-file torn set is unrepresentable",
        )
        checks.ok(
            after.review.entries.get("3/2") is None,
            "and the queue entry that was meant to move with the card is not there alone",
        )
        checks.equal(
            len([e for e in Store().history() if e.get("event") == master.CAPTURED]),
            1,
            "and the history rows commit with the change rather than after it",
        )

        # ----------------------------------------------------------- a session is lazy
        for at in range(2, 41):
            capture_server.do_capture(capture_payload(3, capture_id=f"c{at}", set_hint="sv9"))
        for at in range(1, 21):
            capture_server.do_capture(capture_payload(4, capture_id=f"d{at}", set_hint="sv9"))
        with Store().write() as snapshot:
            card, created = snapshot.inventory.allocate_capture(
                3, capture_id="lazy", cid=fake_cid("lazy")
            )
            built = snapshot.inventory.cards.loaded_count
            complete = snapshot.inventory.cards.complete
        checks.ok(created and card.key == "3/41", "a capture lands at the high-water mark")
        checks.ok(
            not complete and built <= 2,
            f"and built {built} card object(s) to do it, not the store's 60 — the box is a "
            f"column query and the replay lookup is an index, so a capture's cost stops "
            f"growing with the store (D88)",
        )
        checks.equal(
            len(Store().read().inventory.cards),
            61,
            "while a whole-store read still sees every card",
        )
        checks.equal(
            Store().read().inventory.next_index(4),
            21,
            "and the other box's high-water mark was untouched",
        )
        with Store().write() as snapshot:
            snapshot.inventory.cards["3/41"].box = "three"
        caught = checks.raises(
            master.BadPosition,
            lambda: Store().read().inventory.next_index(3),
            "a record whose box will not coerce still refuses the scan — found by its "
            "NULL column rather than by walking every row",
        )
        if caught is not None:
            checks.ok("3/41" in str(caught), "and the refusal still names the card")
        with Store().write() as snapshot:
            snapshot.inventory.cards["3/41"].box = 3
        checks.equal(
            Store().read().inventory.positions_for_sku("none") , [],
            "a SKU nothing carries answers an empty list through the index",
        )
        with Store().write() as snapshot:
            row_4040 = snapshot.inventory.listing("4040", condition="Near Mint")
            row_4040.observe_live(3, "2026-09-01T12:00:00+00:00")
            row_4040.sale()
        back = Store().read().inventory.listing_for("4040")
        checks.equal(
            (back.live, back.live_as_of),
            (3, "2026-09-01T12:00:00+00:00"),
            "`live_as_of` round-trips through the listings table — it rides the payload "
            "column, and `Inventory.parse` filters on `Listing.__annotations__`, so a new "
            "field needs no schema bump (D88)",
        )
        checks.equal(
            (back.sold_here, back.sold_here_at is not None, back.live_estimate),
            (1, True, 2),
            "AND SO DOES D115's COUNTER, ON THE SAME GUARANTEE — this is the assertion that "
            "proves the field cost no migration. `store/db.py:TABLES` names four listing "
            "columns and neither new field is among them; a COLUMN would have needed one, "
            "because `_ensure_schema` short-circuits on an existing table and there is no "
            "`ALTER` path in the tree. The estimate is derived on the way out, so it is the "
            "two stored numbers that have to survive, not the answer",
        )
        parsed = master.Inventory.parse(
            {"version": master.VERSION, "cards": {},
             "listings": {
                 "111": {"sku": "111", "pushed": 2, "live": 1, "at": "2026-09-01T12:00:00+00:00"},
                 "222": {"sku": "222", "pushed": 2, "live": 1},
             }}
        ).listings
        checks.equal(
            (parsed["111"].live_as_of, parsed["222"].live_as_of),
            ("2026-09-01T12:00:00+00:00", None),
            "and a payload written before the field existed parses its `at` INTO it — the "
            "settlement time on D87's rows — and one with no `at` either parses to None, "
            "the stampless case where the export keeps its authority",
        )

    # ------------------------------------------------ the legacy import, whole and aside
    with isolated_home():
        legacy_inventory = {
            "version": 2,
            "cards": {
                "2/1": {"box": 2, "index": 1, "state": master.IDENTIFIED, "sku": "111",
                        "name": "Moonfall", "capture_id": "old-1", "metadata_finish": "foil"},
                "2/2": {"box": 2, "index": 2, "state": master.SOLD, "sku": "111",
                        "capture_id": "old-2", "extra_field_nobody_declared": True},
            },
            "boxes": {"2": {"box": 2, "name": "Epics", "sections": [1], "state": "open"}},
            "listings": {"111": {"sku": "111", "pushed": 2, "live": 1}},
        }
        directory = files.inventory_dir()
        directory.mkdir(parents=True, exist_ok=True)
        files.write_json(directory / db.LEGACY_INVENTORY, legacy_inventory)
        files.write_json(
            directory / db.LEGACY_CACHE,
            {"2/1": {"identification": {"name": "Moonfall", "confidence": "high"},
                     "photo_sha256": "abc", "prompt_fingerprint": "p1", "at": "2026-08-01"}},
        )
        files.write_json(
            directory / db.LEGACY_REVIEW,
            # THE LEGACY ADDRESS, NAMED RATHER THAN DERIVED. This file is a review queue
            # written before cards had names, beside an `inventory.json` written the same
            # day, and the whole case is what the first open makes of them — so the entry
            # has to carry the path such a file actually carried, and asking the store for
            # one would migrate the store this line is still seeding.
            {"2/1": asdict_entry(
                entry(2, 1, photo=str(capture_server.legacy_photo_path(2, 1)))
            )},
        )
        files.write_json(directory / db.LEGACY_PARKED, {})
        files.write_json(
            directory / db.LEGACY_ORDERS,
            {"version": 1, "orders": {}, "fulfilment": {"tcgplayer:A": {"111": {"fulfilled": 1, "copies": ["old-2"]}}}},
        )
        for event in (
            {"at": "2026-08-01T00:00:00+00:00", "event": master.CAPTURED, "position": "2/1"},
            {"at": "2026-08-02T00:00:00+00:00", "event": master.SOLD, "position": "2/2"},
        ):
            files.append_jsonl(directory / db.LEGACY_HISTORY, event)
        expected = master.Inventory.parse(legacy_inventory).to_payload()

        imported = Store().read()
        # THE IMPORT IS LOSSLESS AND IT IS NO LONGER IDENTICAL (D145). It ADDS a
        # `bid` to every box and records the mark it issued them against, which is a migration
        # rather than a loss — so the assertion is stated as "everything the file said, plus
        # exactly this", and the two added facts are asserted BY NAME below rather than
        # swallowed by a looser comparison. Loosening it to ignore unknown keys is what would
        # make this test stop being about losslessness.
        added = imported.inventory.to_payload()
        checks.equal(
            added["box_ids_issued"],
            1,
            "the legacy import issues a true index to the one box the file declared, and "
            "records the high-water mark it issued it against (D145)",
        )
        checks.equal(
            added["boxes"]["2"]["bid"],
            1,
            "and the box wears it — assigned in ascending box number, the order "
            "`store/db.py:_number_legacy_boxes` states, because a legacy box's `created_at` "
            "is optional and would put every unstamped box in an arbitrary bucket",
        )
        checks.equal(
            [added["cards"]["2/1"]["cid"], added["cards"]["2/2"]["cid"]],
            ["abc", "nophoto:2/2@"],
            "AND IT NAMES EVERY CARD (D172), by the ladder `store/db.py:_name_one_card` "
            "walks rather than by one rule. 2/1 takes rung 3 — the digest the paid ANSWER "
            "recorded, which is the fact D89's reclaim leaves behind — and 2/2 reaches no "
            "rung at all and gets shape 4, `nophoto:<key>@<captured_at>`, a NAME and never "
            "a null so that `cards_cid` can be UNIQUE over every row. The trailing `@` is "
            "the empty `captured_at` this legacy record carries, which is the shape a file "
            "written before that field existed actually has",
        )
        restored = json.loads(json.dumps(added))
        restored["box_ids_issued"] = expected["box_ids_issued"]
        for key, box in restored["boxes"].items():
            box["bid"] = expected["boxes"][key]["bid"]
        for key, card in restored["cards"].items():
            card["cid"] = expected["cards"][key]["cid"]
        checks.equal(
            restored,
            expected,
            "and NOTHING ELSE MOVED: with those THREE facts put back the way the file had "
            "them, the legacy inventory.json reads back through the database EXACTLY as "
            "`Inventory.parse` read it — a lossless import, undeclared field dropped by the "
            "same filter",
        )
        checks.equal(
            imported.inventory.cards["2/1"].metadata_finish,
            "foil",
            "a bare-string finish claim survives as the bare string (D3: both shapes legal)",
        )
        checks.ok(
            imported.cache.get("2/1") is not None and imported.cache.get("2/1").photo_sha256 == "abc",
            "the paid answers came across",
        )
        checks.ok(
            imported.review.entries.get("2/1") is not None,
            "so did the review queue",
        )
        checks.equal(
            imported.ledger.fulfilled("tcgplayer:A", "111"),
            1,
            "and the ledger's fulfilment map, which `ingest` cannot name",
        )
        checks.equal(
            [e["event"] for e in Store().history()],
            [master.CAPTURED, master.SOLD, "card_ids_reissued"],
            "and history.jsonl became the events table, in order — with the naming pass's "
            "own line appended after it. A migration that gave every card a name and wrote "
            "nothing down would be the one class of change this store cannot answer a "
            "question about afterwards, so it leaves a line like every other write",
        )
        checks.equal(
            sorted(p.name for p in db.legacy_dir(directory).iterdir()),
            sorted(list(db.LEGACY_FILES) + [db.RECEIPT_NAME]),
            "every legacy file moved to legacy-json/ with a receipt beside it",
        )
        checks.equal(
            db.legacy_present(directory),
            [],
            "and none is left where a reader could mistake it for the store",
        )
        receipt = json.loads((db.legacy_dir(directory) / db.RECEIPT_NAME).read_text("utf-8"))
        checks.equal(
            receipt["counts"]["cards"],
            2,
            "the receipt counts what was imported",
        )
        # A legacy file put back BESIDE the database is never read (D86's rule, D88's).
        files.write_json(directory / db.LEGACY_INVENTORY, {"version": 2, "cards": {"9/9": {"box": 9, "index": 9}}})
        checks.ok(
            Store().read().inventory.get("9/9") is None,
            "a legacy file beside a live database is not a fallback — it is read by nothing",
        )
        (directory / db.LEGACY_INVENTORY).unlink()
        checks.equal(
            Store().read().inventory.next_index(2),
            3,
            "and the store is what it was",
        )

def check_skus_photos_limit(checks: Checks) -> None:
    """Round 2 review finding: `GET /skus/photos` (`do_skus_photos`, D298)
    had no server-side bound of its own — only `Revenue.tsx:PHOTO_LOOKUP_CAP` bounded what
    the client SENDS, and a hand-typed query string could ask for any number of SKUs.
    `SKUS_PHOTOS_LIMIT` is that same value, kept in step by hand (no shared constant
    reaches across the TS/Python boundary here, `ORDER_NAMES_LIMIT`'s own precedent has
    the same gap).
    """
    checks.note("")
    checks.note("SKU PHOTO LOOKUP CAP — GET /skus/photos (D298, round 2 review)")

    with isolated_home():
        at_limit = [f"sku-{n}" for n in range(capture_server.SKUS_PHOTOS_LIMIT)]
        answer = answers(
            checks,
            lambda: capture_server.do_skus_photos(at_limit),
            "exactly the limit answers",
        )
        if answer is not None:
            checks.equal(answer["photos"], {}, "none of these SKUs exist, so none photograph")

        refusal(
            checks,
            lambda: capture_server.do_skus_photos(at_limit + ["one-more"]),
            "too_many_skus",
            "one SKU over the limit refuses",
        )

def check_photo_reclaim(checks: Checks) -> None:
    """D89: a sold card's photograph is reclaimed, the record stays, the digest stays.

    The third shape between D10's undo (record and photograph both go) and D26's terminal
    states (both stay): record kept, photograph gone, digest on the record. Refusal for
    refusal like the release beside it — `confirm` required, nothing to reclaim is a
    conflict — and the store's own boundary refuses a card that has not sold, so a caller
    bypassing the route cannot reclaim a photograph the pull preview still needs.
    """
    checks.note("")
    checks.note("PHOTO RECLAMATION — GET /boxes/<box>/photos, POST /boxes/<box>/photos/reclaim (D89)")

    with isolated_home():
        # DISTINGUISHABLE BYTES PER PHOTOGRAPH — `check_photo_cache`'s rule, and here it is
        # what makes the D36 case at the bottom meaningful: four identical photographs are
        # one digest at four slots, which the realign rightly refuses as ambiguous.
        for at in range(1, 5):
            capture_server.do_capture(capture_payload(
                3, capture_id=f"r{at}", set_hint="sv9",
                image=base64.b64encode(b"\xff\xd8\xff" + bytes([at]) * 64).decode("ascii"),
            ))
        with Store().write() as snapshot:
            for at in (1, 3):
                snapshot.inventory.set_state(f"3/{at}", master.SOLD)
            snapshot.inventory.retire("3/2", "damaged")
        before = photo_of(3, 1).read_bytes()
        expected_digest = hashlib.sha256(before).hexdigest()

        plan = answers(checks, lambda: capture_server.do_box_photos(3), "the free count answers")
        if plan is not None:
            checks.equal(
                (plan["reclaimable"]["cards"], plan["reclaimable"]["indices"]),
                (2, [1, 3]),
                "it counts the SOLD cards whose photograph is on disk and nothing else — not "
                "the retired one (D26 keeps that photograph) and not the two on hand",
            )
            checks.equal(plan["reclaimable"]["bytes"], 2 * len(before), "and the bytes they hold")
            checks.equal(
                plan["on_hand_photos"], 1,
                "and says what the box keeps afterwards — the one card still on hand; the "
                "retired card is neither reclaimable nor on hand",
            )

        refusal(
            checks,
            lambda: capture_server.do_reclaim_box_photos(3, {}),
            "confirm_required",
            "the reclaim refuses without `confirm: true`",
        )
        checks.ok(
            photo_of(3, 1).is_file(),
            "and the refusal deleted nothing",
        )
        refusal(
            checks,
            lambda: capture_server.do_reclaim_box_photos(3, {"confirm": True, "extra": 1}),
            "field_not_settable",
            "an unknown field refuses",
        )
        refusal(
            checks,
            lambda: capture_server.do_reclaim_box_photos(99, {"confirm": True}),
            "box_not_found",
            "a box nothing names refuses",
        )

        receipt = answers(
            checks,
            lambda: capture_server.do_reclaim_box_photos(3, {"confirm": True}),
            "the reclaim answers",
        )
        if receipt is not None:
            checks.equal(
                (receipt["reclaimed"], receipt["keys"], receipt["bytes"]),
                (2, ["3/1", "3/3"], 2 * len(before)),
                "and reports what went, by key and by byte",
            )
        checks.ok(
            not photo_of(3, 1).is_file()
            and not photo_of(3, 3).is_file(),
            "the two sold cards' photographs are gone",
        )
        checks.ok(
            photo_of(3, 2).is_file() and photo_of(3, 4).is_file(),
            "the retired card's and the on-hand card's are not",
        )
        checks.ok(
            capture_server.sidecar_path(photo_of(3, 1)).is_file(),
            "the sidecar stays — it is the operator's claims, a few hundred bytes, and inert "
            "without a photograph beside it",
        )
        after = Store().read().inventory
        card = after.get("3/1")
        checks.equal(
            (card.state, card.photo_sha256, bool(card.photo_reclaimed_at), card.photo is not None),
            (master.SOLD, expected_digest, True, True),
            "THE RECORD STAYS, sold, with the digest of the photograph that was there and "
            "when it went — the path it had is kept too, so `photo: null` still means 'never "
            "photographed' and not 'reclaimed'",
        )
        checks.equal(
            after.get("3/4").photo_reclaimed_at,
            None,
            "and a card on hand carries neither field",
        )
        checks.equal(
            [e for e in events_for("3/1") if e["event"] == master.PHOTO_RECLAIMED][-1]["sha256"],
            expected_digest,
            "the history line carries the digest",
        )
        checks.equal(
            [e for e in events_for("3/1") if e["event"] == master.PHOTO_RECLAIMED][-1]["bytes"],
            len(before),
            "and the bytes freed",
        )
        checks.ok(
            master.PHOTO_RECLAIMED not in master.STATES,
            "and the event is not a state, so a sale's reversal cannot restore to it (D26)",
        )

        # The second press.
        refusal(
            checks,
            lambda: capture_server.do_reclaim_box_photos(3, {"confirm": True}),
            "nothing_to_reclaim",
            "a second press finds nothing left and says so — the operation is idempotent by "
            "refusal rather than by a silent zero",
        )
        plan = answers(checks, lambda: capture_server.do_box_photos(3), "the count after")
        if plan is not None:
            checks.equal(
                (plan["reclaimable"]["cards"], plan["reclaimed"]["cards"], plan["reclaimed"]["indices"]),
                (0, 2, [1, 3]),
                "reports the two as reclaimed, by index",
            )
        checks.ok(
            capture_server.do_inventory()["cards"]["3/1"].get("photo_reclaimed_at"),
            "GET /inventory carries the stamp, which is what a screen draws 'reclaimed' from "
            "rather than 'missing'",
        )

        # The store's own boundary.
        with Store().write() as snapshot:
            checks.raises(
                master.CardNotSold,
                lambda: snapshot.inventory.record_photo_reclaimed("3/4", sha256="x", size=1),
                "the store refuses to mark a card that has not sold, whatever route asked",
            )
            checks.ok(
                not snapshot.inventory.record_photo_reclaimed("3/99", sha256="x", size=1),
                "and answers False for a position holding no record (v1 bug 5's shape)",
            )

        # D36: a reclaimed photograph reads as a DEPARTED card to the realign, which is the
        # truth — it sold — and not as an unverified box.
        payload = {"cards": {
            "3/1": {"box": 3, "index": 1, "photo_sha256": expected_digest},
            "3/4": {"box": 3, "index": 4,
                    "photo_sha256": hashlib.sha256(photo_of(3, 4).read_bytes()).hexdigest()},
        }}
        _, moved, departed, unverified = resolve.realign(payload)
        checks.equal(
            (moved, departed, unverified),
            ({}, ["3/1"], []),
            "D36's realign reads the reclaimed card as departed — the digest on the record is "
            "still comparable, and the box's other photographs are still there to check",
        )

def asdict_entry(entry) -> dict:
    from dataclasses import asdict

    return asdict(entry)

# ------------------------------------------------------------------- the server, in-process


def check_server_routes(checks: Checks) -> None:
    """The route surface and every refusal, called directly rather than over a socket.

    In-process because the handler is a thin dispatch over these functions: what is worth
    asserting is that each anticipated condition answers in its own code, and a socket adds
    nothing to that. Concurrency is the exception and gets a real server below.
    """
    checks.note("")
    checks.note("SERVER ROUTES — server/capture_server.py")

    with isolated_home():
        # HELD, because the bytes are the assertion below and every capture now carries its
        # own — the card is NAMED by the sha256 of its photograph (D172), so no two captures
        # in one store may send the same blob and no constant can stand in for one.
        first_payload = capture_payload(3)
        status, body = capture_server.do_capture(first_payload)
        checks.equal(status, HTTPStatus.CREATED, "a first capture answers 201")
        checks.equal(body["key"], "3/1", "and reports the position it allocated")
        checks.ok(body["new_box"], "and flags the box as new")
        checks.equal(
            body["label"],
            stored_label(3, 1),
            "the rendered label matches pipeline/join.py's — one renderer, not two",
        )

        _, second = capture_server.do_capture(capture_payload(3))
        checks.equal(second["key"], "3/2", "captures into one box are contiguous")
        checks.ok(not second["new_box"], "and only the first is flagged new_box")

        status, replayed = capture_server.do_capture(
            capture_payload(3, capture_id="retry-1")
        )
        status_again, replayed_again = capture_server.do_capture(
            capture_payload(3, capture_id="retry-1")
        )
        checks.equal(status_again, HTTPStatus.OK, "a replayed capture answers 200, not 201")
        checks.ok(not replayed_again["created"], "and reports created=False")
        checks.equal(
            replayed_again["key"], replayed["key"], "and returns the original position"
        )

        photo = photo_of(3, 1)
        checks.ok(
            photo.is_file(),
            "the photo is on disk at the path derived from the CARD'S NAME — not from its "
            "position, which is a lookup in front of that path now (D172)",
        )
        served, tag = capture_server.do_photo(3, 1)
        checks.equal(
            served, sent_image(first_payload), "GET /photo returns the stored bytes"
        )
        checks.ok(
            tag.startswith('"') and tag.endswith('"') and len(tag) == 34,
            "and a quoted strong ETag beside them — the validator that lets a browser find "
            "out a slot's occupant changed under a URL that did not",
        )

        refusal(
            checks, lambda: capture_server.do_photo(3, 99), "photo_not_found",
            "an absent photo refuses as photo_not_found",
        )
        refusal(
            checks, lambda: capture_server.do_capture({"image": "x"}), "box_required",
            "a capture with no box refuses as box_required",
        )
        refusal(
            checks,
            lambda: capture_server.do_capture(capture_payload(0)), "box_invalid",
            "box 0 refuses as box_invalid — boxes start at 1",
        )
        refusal(
            checks,
            lambda: capture_server.do_capture({"box": "three", "image": "x"}),
            "box_invalid",
            "a non-numeric box refuses as box_invalid",
        )
        refusal(
            checks, lambda: capture_server.do_capture({"box": 3}), "image_required",
            "a capture with no image refuses as image_required",
        )
        refusal(
            checks,
            lambda: capture_server.do_capture({"box": 3, "image": "not base64!"}),
            "image_invalid",
            "a non-base64 image refuses as image_invalid",
        )
        refusal(
            checks,
            lambda: capture_server.do_capture(
                {"box": 3, "image": base64.b64encode(b"\x89PNG\r\n\x1a\n").decode("ascii")}
            ),
            "image_not_jpeg",
            "a PNG is REFUSED, never silently converted",
        )
        refusal(
            checks,
            lambda: capture_server.do_capture(capture_payload(3, variant="foil")),
            "variant_invalid",
            "a finish outside the enum refuses as variant_invalid",
        )
        # D3 rung 1's claim is a SET (amended 2026-08-23), and these are the route's half of
        # it. `variant="foil"` above is unchanged and stays first: the bare string is what
        # every client in the tree sends and what all 682 live records carry, so the wire
        # keeps accepting one forever — the read-side backfill, not a deprecation.
        refusal(
            checks,
            lambda: capture_server.do_capture(
                capture_payload(3, variant=["normal", "foil"])
            ),
            "variant_invalid",
            "ONE bad member refuses the WHOLE claim, in the same code and with no new one — "
            "a silently shortened claim is a claim the operator did not make, and a "
            "two-member claim quietly cut to one stops filtering and starts DETERMINING",
        )
        refusal(
            checks,
            lambda: capture_server.do_capture(capture_payload(3, variant=["normal", 7])),
            "variant_invalid",
            "and a member that is not a string refuses on shape, before any vocabulary is "
            "consulted — the split `_variant_shape`/`_check_variant_members` exists for",
        )
        refusal(
            checks,
            lambda: capture_server.do_capture(capture_payload(3, variant={"a": 1})),
            "variant_invalid",
            "as does a claim that is neither a string nor a list — it used to be COERCED, "
            "`str(raw).strip()`, which is how a JSON list became the literal \"['normal', "
            "'holo']\" and made a set-valued claim unmakeable over this wire",
        )
        refusal(
            checks,
            lambda: capture_server.do_capture(
                capture_payload(3, game="misc", variant=["normal"])
            ),
            "variant_invalid",
            "and the vocabulary is THIS GAME's: `misc` authors no finishes, so every member "
            "refuses — the capture screen draws no Finish field for it, so a finish arriving "
            "under one did not come from the control",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_card(9, 9, {"set_hint": "sv9"}),
            "card_not_found",
            "a PUT naming an absent position refuses — this route corrects, never creates",
        )
        refusal(
            checks,
            lambda: capture_server.do_put_card(3, 1, {"state": "sold"}),
            "field_not_settable",
            "a PUT naming `state` is refused: listing transitions are not settable here",
        )

        # `product` JOINED THIS TUPLE ON 2026-08-30 (D70, C10), and the assertion stays an
        # exact ordered match rather than a membership test. The order is
        # `master.CAPTURE_CLAIM_FIELDS`'s, because `PUT_FIELDS` is DERIVED from it — so this
        # check is what notices a claim that reached the record and not the wire, which is
        # the drift the derivation exists to make impossible and this line exists to prove
        # still holds.
        checks.equal(
            capture_server.PUT_FIELDS,
            ("set_hint", "variant", "game", "rarity_claim", "product", "note"),
            "and the settable set is every capture claim, in the order the store names them",
        )

        # Three captures reached this box, not four: the replay above returned the third
        # card rather than creating one. Counting it here is the mistake the retry guard
        # exists to prevent, so the count is the assertion.
        report = capture_server.do_status()
        checks.equal(report["cards"], 3, "GET /status counts every card, and a replay is not one")
        checks.equal(report["next_index"]["3"], 4, "and reports the next index per box")
        checks.ok("problem" not in report, "and reports no problem on a healthy store")

        # WHICH PROCESS IS ANSWERING. `scripts/serve.py` restarts this server whenever a
        # watched Python file changes, and the app tells a restart from a reload by watching
        # this value — the failure it exists for is docs/GATES.md's box 95, where whole-second
        # timestamps were written two hours after the millisecond fix landed because the
        # process predated it and nothing on any screen could say so.
        checks.ok(
            isinstance(report.get("boot_id"), str) and report["boot_id"],
            "GET /status names the process answering it, so a stale server can be seen",
        )
        checks.equal(
            report["boot_id"],
            capture_server.BOOT_ID,
            "and it is this process's own id rather than a value recomputed per request",
        )

        # GET /inventory decorates every row with its rendered position. Asserted against
        # `join.Position` itself and never against a literal string: the whole point of the
        # decoration is that ONE renderer draws a position label, and a literal here would
        # go on passing while the app and the pipeline disagreed about where a card is.
        inventory = capture_server.do_inventory()
        checks.equal(
            sorted(inventory["cards"]),
            ["3/1", "3/2", "3/3"],
            "GET /inventory returns every card, keyed by position",
        )
        row = inventory["cards"]["3/2"]
        checks.equal(
            row["label"],
            stored_label(3, 2),
            "and each row carries the label pipeline/join.py renders — not a second copy of "
            "D10's divider rule living in the app",
        )
        checks.equal(
            row["section"], join.Position(3, 2).section, "with the section it sits in"
        )
        checks.equal(
            row["card"], join.Position(3, 2).card, "and its card within that section"
        )

        # WIRE-ONLY, which is the constraint that makes the decoration safe. The stored
        # payload is the on-disk format and `Inventory.parse` filters on
        # `Card.__annotations__`, so a label written into it would be silently dropped on
        # the next reload — a field that exists only until something re-reads it is worse
        # than no field at all.
        on_disk = stored_payloads("cards")
        checks.ok(
            on_disk and all("label" not in record for record in on_disk.values()),
            "and the decoration never reaches the stored row — to_payload is untouched",
        )

        # A corrupt record must not take down the one route you reach for when something is
        # wrong. It reports the finding instead.
        with Store().write() as snapshot:
            snapshot.inventory.cards["3/1"].box = "three"
        broken = capture_server.do_status()
        checks.ok(broken["next_index"] is None, "a corrupt record leaves next_index null")
        checks.ok(
            "problem" in broken,
            "and /status still answers, reporting the problem rather than raising",
        )

        broken_inventory = capture_server.do_inventory()
        checks.ok(
            "label" not in broken_inventory["cards"]["3/1"],
            "a record whose box will not coerce is left UNLABELLED — a placeholder label "
            "names a position that does not exist, which is the one thing a label may never "
            "do (D10)",
        )
        # THIS CASE SAID THE OPPOSITE UNTIL D58 AND THE REVERSAL IS THE POINT. It read
        # "one bad record does not take the route down: every other row keeps its label",
        # on the stated ground that "a label needs only this record's own two integers and
        # the box's layout". That ground is exactly what D58 removed: a card's number is
        # now its place among the cards ON HAND in its box, so rendering one means counting
        # the whole box, and a record nobody can place might be in this box and might be on
        # hand. Answering the old index-space label instead would put a SECOND NUMBERING
        # SYSTEM on the screen with nothing saying which one it is — a person sent to
        # `Card 40` in a box that has sold three would open the wrong slot and see nothing
        # wrong. No label is the honest answer, and it is the same call `view` already
        # makes for a layout that will not validate.
        #
        # WHAT IT COSTS IS REAL AND IS RECORDED RATHER THAN DESIGNED AWAY: the walk
        # degrades store-wide, so one unreadable record now blanks every label in the
        # inventory rather than only the decoration. Narrowing it per box is the fix to
        # reach for if that ever bites — a record whose INDEX will not read could be
        # attributed to its box and poison only that one, where a record whose BOX will
        # not read could be in any of them. Not done here, because it would be an
        # untested branch added to make a case go green.
        checks.ok(
            "label" not in broken_inventory["cards"]["3/2"],
            "and its NEIGHBOURS lose their labels too, because the number is a count of "
            "the cards in the box and one of them cannot be counted (D58) — a card that "
            "cannot be placed might be in this box and might be on hand",
        )
        checks.equal(
            broken_inventory["cards"]["3/2"]["place"]["box_total"],
            0,
            "and the denominator goes with it rather than standing alone: the count and "
            "the numbers drawn against it come off one walk",
        )

def check_boxes_and_listings(checks: Checks) -> None:
    """D20's box object, D7's fungible copies, and the v1 -> v2 migration between them.

    THE MIGRATION CASE IS THE LOAD-BEARING ONE. Every label this repo rendered before D20 was
    computed from a global `CARDS_PER_SECTION`; sections became per-box, and on 2026-08-29 that
    global was deleted outright. If the migration gets this wrong, every position label in a
    real inventory shifts at once and the only symptom is a person opening the wrong slot weeks
    later. So it is asserted against the literal strings, not against the formula that produced
    them — and the strings it pins moved once, deliberately, which the case itself explains.
    """
    checks.note("")
    checks.note("BOXES AND LISTINGS — store/master.py")

    # --- the v1 -> v2 migration ------------------------------------------------------
    legacy = {
        "version": 1,
        "cards": {
            "1/1": {"box": 1, "index": 1, "sku": "888", "condition": "Near Mint",
                    "state": "staged", "state_at": "2026-08-01T00:00:00+00:00"},
            "1/26": {"box": 1, "index": 26, "sku": "888", "condition": "Near Mint",
                     "state": "live", "state_at": "2026-08-01T00:00:00+00:00"},
            "1/53": {"box": 1, "index": 53, "sku": "999", "condition": "Near Mint",
                     "state": "sold", "state_at": "2026-08-01T00:00:00+00:00"},
            "2/4": {"box": 2, "index": 4, "state": "captured"},
        },
    }
    migrated = master.Inventory.parse(legacy)

    checks.equal(
        [migrated.cards[k].state for k in ("1/1", "1/26", "1/53", "2/4")],
        ["identified", "identified", "sold", "captured"],
        "a card wearing a listing stage migrates to `identified`; sold and captured stand",
    )
    checks.equal(
        (migrated.listings["888"].staged, migrated.listings["888"].live),
        (1, 1),
        "and hands its stage to the SKU as a count (D7 amended)",
    )
    checks.ok(
        "999" not in migrated.listings,
        "a sold card starts no listing — it left inventory, it was never a quantity",
    )
    checks.equal(
        sorted(migrated.boxes), ["1", "2"],
        "every box a card names gets a registry entry",
    )
    checks.equal(
        migrated.boxes["1"].sections, [],
        "MIGRATED BOXES DECLARE NO LAYOUT — which is what preserves every existing label",
    )
    checks.ok(
        not hasattr(migrated.boxes["1"], "capacity"),
        "and no capacity: a box has none since `D299`",
    )

    # THE LABELS THEMSELVES. Literal strings, because a formula asserted against itself
    # proves nothing about the cards already on a shelf.
    #
    # THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-08-29 AND THE REVERSAL IS THE POINT. It
    # read "a migrated box renders every label byte-identical to before the migration", and
    # the labels it pinned were `Section 2 · Card 1` at index 26 and `Section 3 · Card 3` at
    # index 53 — dividers `CARDS_PER_SECTION = 25` cut into a box nobody had divided. The
    # owner's instruction was to delete automatic sectioning, so those labels are exactly
    # what had to move, and a test that pinned them is the test that had to change.
    #
    # WHAT IT IS STILL FOR is what its docstring says: the migration is load-bearing because
    # a wrong one shifts every position label in a real inventory at once, and the only
    # symptom is somebody opening the wrong slot weeks later. That risk did not go away — it
    # was REALISED, deliberately and once, and box 1 of the owner's own store is the
    # measurement (133 cards that read as six sections and are now the one section the box
    # physically is). Pinning the new strings is what keeps the next shift accidental.
    checks.equal(
        [join.Position(1, i, migrated.sections_for(1)).label for i in (1, 25, 26, 53)],
        [
            "Box 1, Section 1, Card 1",
            "Box 1, Section 1, Card 25",
            "Box 1, Section 1, Card 26",
            "Box 1, Section 1, Card 53",
        ],
        "AN UNDECLARED BOX IS ONE SECTION, and `card` is the index: no divider exists "
        "until somebody puts one in (D10, amended 2026-08-29)",
    )
    checks.equal(
        [
            join.Position(1, 53, migrated.sections_for(1)).section_start,
            join.Position(1, 53, migrated.sections_for(1)).section_end,
        ],
        [1, None],
        "its one section starts at card 1 and has no end of its own — it runs to wherever "
        "the box stops, which is D20's answer for a final section and not a new rule",
    )

    # --- declared layouts --------------------------------------------------------------
    inventory = master.Inventory()
    inventory.ensure_box(1, name="ME01 commons")
    checks.equal(inventory.box(1).name, "ME01 commons", "a box can be created and named")

    inventory.set_sections(1, [1, 31, 56])
    checks.equal(
        [join.Position(1, i, inventory.sections_for(1)).label for i in (30, 31, 55, 56)],
        [
            "Box 1, Section 1, Card 30",
            "Box 1, Section 2, Card 1",
            "Box 1, Section 2, Card 25",
            "Box 1, Section 3, Card 1",
        ],
        "a declared layout puts the divider exactly where it was declared",
    )
    checks.equal(
        join.Position(1, 90, inventory.sections_for(1)).section_end,
        None,
        "the FINAL section has no end until a capacity says where the box stops (D20)",
    )

    # A boundary edit relabels what is behind it and touches no index. D10 (amended)
    # accepts this deliberately, so it is asserted rather than guarded against.
    before = join.Position(1, 40, inventory.sections_for(1)).label
    inventory.set_sections(1, [1, 41, 56])
    after = join.Position(1, 40, inventory.sections_for(1)).label
    checks.equal(
        (before, after),
        ("Box 1, Section 2, Card 10", "Box 1, Section 1, Card 40"),
        "moving a divider RELABELS the cards behind it — the label is a view (D10 amended)",
    )
    checks.ok(
        any(e.get("event") == "resectioned" for e in inventory.events),
        "and it leaves a `resectioned` event, which is the whole mitigation",
    )
    checks.equal(
        [e for e in inventory.events if e.get("event") == "resectioned"][-1]["sections_to"],
        [1, 41, 56],
        "carrying the layout it moved to, so the change is reconstructable",
    )
    checks.ok(
        "position" not in [e for e in inventory.events if e.get("event") == "resectioned"][-1],
        "and no position: a box is not at one, and a null would read as a lost card",
    )

    for bad, why in (
        ([2, 30], "a layout not starting at index 1"),
        ([1, 30, 20], "an unsorted layout"),
        ([1, 30, 30], "two dividers in one slot"),
        (["x"], "a layout that is not integers"),
    ):
        checks.raises(
            master.BadSections,
            lambda bad=bad: inventory.set_sections(1, bad),
            f"{why} is REFUSED, never quietly repaired",
        )

    # --- the lifecycle -----------------------------------------------------------------
    with isolated_home():
        for _ in range(4):
            capture_server.do_capture(capture_payload(5))
        with Store().write() as snapshot:
            checks.equal(snapshot.inventory.box_fill(5), 4, "fill is the high-water mark")
            card, created = snapshot.inventory.allocate_capture(5, cid=fake_cid("reopened"))
            checks.ok(
                created and card.index == 5,
                "and the box takes the next card: a box has no lid (`D299`)",
            )

    # --- listings are quantities, never addresses --------------------------------------
    inventory = master.Inventory()
    for index in range(1, 8):
        inventory.record_capture(
            master.Card(box=9, index=index, sku="777", cid=fake_cid(f"playset-{index}"))
        )
    listing = inventory.listing("777", condition="Near Mint")
    listing.live = 4

    checks.equal(
        len(inventory.copies_on_hand("777")), 7,
        "EVERY unsold copy is on hand — none is designated backstock (D7 amended)",
    )
    inventory.set_state("9/3", master.SOLD)
    checks.equal(
        len(inventory.copies_on_hand("777")), 6,
        "and a sale takes exactly one copy out of the sellable set",
    )
    checks.equal(
        [c.key for c in inventory.copies_on_hand("777")],
        ["9/1", "9/2", "9/4", "9/5", "9/6", "9/7"],
        "in box-walk order, with the sold position left as a permanent gap (D10)",
    )
    # INVERTED AT D115, AND THE FIGURES SURVIVE. These read `listing.bump(master.LIVE, -1)
    # == 3` and "a sale decrements the SKU's live count", which was the mechanism rather than
    # the rule. The rule — a sale takes the count down at once, and it never goes negative —
    # is what the 3 and the 0 assert, and both still hold. What moved is WHERE: the reading is
    # left alone and the sale is counted beside it.
    checks.equal(
        [listing.sale(), listing.live, listing.live_estimate], [1, 4, 3],
        "a sale takes the count down AT ONCE (D7's ordering, unchanged) — and does it by "
        "counting against the reading rather than editing it, so `live` still reads 4",
    )
    checks.equal(
        [listing.sale(), listing.sale(), listing.sale(), listing.live_estimate], [2, 3, 4, 0],
        "which floors at zero rather than going negative — the floor is on the DERIVED "
        "figure now, which is what makes an undo exact where `bump`'s stored floor lost it",
    )
    checks.equal(
        [listing.sale(undone=True), listing.live_estimate], [3, 1],
        "and a reversal is exact: the counter carries the full count under the floor, so "
        "sell-past-zero then undo returns to where it was rather than drifting UP by one — "
        "the edge `server/capture_server.py` accepted rather than paid for, now closed",
    )
    for _ in range(3):
        listing.sale(undone=True)
    checks.equal(
        [listing.sold_here, listing.sold_here_at, listing.live_estimate], [0, None, 4],
        "and the stamp clears when the counter empties — nothing is pending, so no file "
        "needs to be arbitrated against a sale that is no longer counted",
    )
    checks.raises(
        master.UnknownState,
        lambda: listing.bump(master.LIVE, -1),
        "`bump` REFUSES `live` outright (D115). Its one caller was the sale, and leaving the "
        "expression callable with a docstring explaining how to move `live` with it is how "
        "the next session puts the double-subtraction back",
    )
    checks.raises(
        master.UnknownState,
        lambda: listing.bump("sold_here"),
        "and the counter is NOT a stage — `set`, `release`, `listing_counts` and "
        "`_stages_held` all walk `LISTING_STAGES`, so a fourth member would be surrendered "
        "by a box delete and drawn as a listing stage on three screens",
    )
    checks.raises(
        master.UnknownState,
        lambda: listing.bump("captured"),
        "and a position state is not a listing stage — bump refuses it",
    )

    # --- `live` is a DATED observation, and an older reading cannot overwrite it ---------
    # D87 amended, 2026-09-02. `live_as_of` is when the reading was taken, `at` is when the
    # record was last touched, and the two are separate so that no other write can forge a
    # fresher live observation than anything made. Its own record, because the round trip
    # below asserts `listing` as the bumps above left it.
    listing = master.Listing(sku="dated")
    checks.equal(
        listing.live_observed_at, None,
        "a record nothing has read `live` for has NO observation time — `at` is not one, "
        "and a fresh record given `at` as a fallback outranked every export older than "
        "its own creation",
    )
    listing.set(master.LIVE, 4)
    stamped = listing.live_as_of
    checks.ok(
        stamped is not None and stamped == listing.at,
        "`set(LIVE)` dates the reading now — an observation this process made",
    )
    listing.set(master.STAGED, 1)
    checks.equal(
        listing.live_as_of, stamped,
        "and `set(STAGED)` leaves it alone: `at` moved, the reading's stamp did not",
    )
    checks.equal(
        listing.observe_live(4, "2999-01-01T00:00:00+00:00"), master.UNCHANGED,
        "a reading equal to the stored figure is UNCHANGED whatever its age — nothing to "
        "arbitrate, nothing touched, which is what keeps `reconcile --live` idempotent",
    )
    checks.equal(
        (listing.observe_live(2, "2000-01-01T00:00:00+00:00"), listing.live, listing.live_as_of),
        (master.KEPT, 4, stamped),
        "an OLDER reading is KEPT out: the store's figure and its stamp both stand",
    )
    checks.equal(
        (listing.observe_live(2, "2999-01-01T00:00:00+00:00"), listing.live, listing.live_as_of),
        (master.ADOPTED, 2, "2999-01-01T00:00:00+00:00"),
        "a NEWER one is ADOPTED and `live_as_of` takes the FILE'S time, never now — dating "
        "an export's reading to the moment it was copied in would forge a fresher "
        "observation than the file made",
    )
    checks.equal(
        listing.live_reading(None, None), 2,
        "no export row at all keeps the stored number — the SKU a run's export does not cover",
    )
    checks.equal(
        listing.live_reading(7, "2999-01-01T00:00:00+00:00"), 2,
        "and a tie goes to the store: an equal-second reading cannot be shown newer",
    )
    # THE ASSERTION D115 INVERTS, AND IT IS THE CHANGE STATED AS A TEST. This read
    # "`bump(LIVE)` — a sale's ±1 — dates the reading now, so the store then knows more than
    # any export fetched before the sale". That restamp was the category error: a sale claimed
    # to be a fresh READING of TCGplayer, which is how one copy came to be subtracted twice —
    # once by an export that already knew, once by the sale. The protection it bought is not
    # lost, it MOVED: `sold_here_at` dates the sale, and `sales_pending` is what keeps an
    # older file from cancelling it. Both halves flip, and the shape is kept so the two
    # readings sit side by side.
    before_stamp = listing.live_as_of
    listing.sale()
    checks.ok(
        listing.live_as_of == before_stamp
        and listing.live_as_of == "2999-01-01T00:00:00+00:00",
        "A SALE DOES NOT DATE A READING. It observed nothing about TCGplayer, so "
        "`live_as_of` stands exactly where the export left it",
    )
    checks.ok(
        listing.sold_here_at is not None and listing.at != before_stamp,
        "what a sale DOES date is its own counter, and `at` — the record was touched, and "
        "the sale can be told apart from the reading it is counted against",
    )
    checks.equal(
        listing.sales_pending("2026-01-01T00:00:00+00:00"), 1,
        "AND AN EXPORT FETCHED BEFORE THE SALE CANNOT CANCEL IT — the protection the restamp "
        "used to buy, now carried by the counter's own stamp. This is the ordinary `Join "
        "again` press: a run's recorded export is fetched before the sale and read after it",
    )
    checks.equal(
        listing.sales_pending("2999-06-01T00:00:00+00:00"), 0,
        "while a file taken after the sale supersedes it — all or nothing, because one stamp "
        "cannot split a file that landed between two sales",
    )
    listing.sale(undone=True)
    legacy = master.Listing.from_record(
        {"sku": "legacy", "live": 3, "at": "2026-09-01T12:00:00+00:00"}
    )
    checks.equal(
        legacy.live_observed_at, legacy.at,
        "a STORED record written before `live_as_of` existed reads `at` as its observation "
        "time, materialised at the parse — D87's settlement rows, whose `at` IS the "
        "settlement time",
    )
    checks.equal(
        master.Listing.from_record(
            {"sku": "unread", "live": 0, "at": "2026-09-01T12:00:00+00:00", "live_as_of": None}
        ).live_observed_at,
        None,
        "while one that carries the key as null is read as written: absent is legacy, null "
        "is unread, and the parse is the one place that tells them apart",
    )
    checks.equal(
        legacy.live_reading(0, "2026-09-01T11:45:00+00:00"), 3,
        "so a file fetched fifteen minutes before that settlement loses to it — the measured "
        "defect, at the size it occurred",
    )
    checks.equal(
        legacy.live_reading(0, "2026-09-01T12:15:00+00:00"), 0,
        "and one fetched after it wins",
    )
    stampless = master.Listing(sku="stampless", live=3)
    checks.equal(
        stampless.live_reading(0, "2026-09-01T12:00:00+00:00"), 0,
        "no stamp on the store's side is the stampless case, and the export keeps the "
        "authority it always had — T3's hand-built fixtures",
    )
    releasing = master.Listing(
        sku="releasing", pushed=2, live=2,
        at="2020-01-01T00:00:00+00:00", live_as_of="2020-01-01T00:00:00+00:00",
    )
    releasing.release(1)
    checks.equal(
        releasing.live_as_of, "2020-01-01T00:00:00+00:00",
        "a D34 release that stopped at `pushed` learned nothing about `live` and leaves its "
        "stamp where the last reading put it",
    )
    releasing.release(3)
    checks.ok(
        releasing.live == 0 and releasing.live_as_of == releasing.at
        and releasing.live_as_of != "2020-01-01T00:00:00+00:00",
        "and one that reached `live` dates the reading now — an observation like a sale",
    )
    checks.raises(
        master.UnknownState,
        lambda: master.check_state(master.LIVE),
        "`live` IS NOT A CARD STATE any more — check_state refuses it, which is the guard "
        "that stops a caller reaching for the old per-position flag",
    )

    # --- the round trip ----------------------------------------------------------------
    inventory.ensure_box(9, name="round trip")
    inventory.set_sections(9, [1, 4])
    reloaded = master.Inventory.parse(inventory.to_payload())
    checks.equal(reloaded.to_payload()["version"], master.VERSION, "to_payload stamps v2")
    checks.equal(
        reloaded.boxes["9"].sections, [1, 4], "boxes survive a JSON round trip"
    )
    checks.equal(
        (reloaded.listings["777"].sku, reloaded.listings["777"].live),
        ("777", 4),
        "and so do listings — the READING, which is 4 because the sales above were counted "
        "beside it rather than subtracted from it (D115). This expected 0 while `bump` "
        "floored the stored figure on every sale",
    )
    checks.equal(
        (reloaded.listings["777"].sold_here, reloaded.listings["777"].sold_here_at),
        (0, None),
        "and the counter round-trips beside it — D88's rule that a new field costs no schema "
        "bump is the whole reason it could be added rather than overloading the reading",
    )
    checks.equal(
        [c.state for c in reloaded.copies_on_hand("777")],
        ["captured"] * 6,
        "and a v2 payload is NOT re-migrated on read — the stages stay where they are",
    )

def check_drain(checks: Checks) -> None:
    """The shutdown seam `scripts/serve.py` restarts through.

    Its own block and not part of `check_server_routes`, because it asserts nothing about a
    route: it is about what happens to a request that is ALREADY RUNNING when the process is
    told to stop. `store/session.py:Store.write()` replaces four JSON files in sequence — each
    atomic alone, none atomic as a set — so a kill landing between them leaves a torn store.
    That risk exists at Ctrl-C frequency today and the supervisor multiplies it, which is what
    makes this seam worth an assertion rather than a comment.

    THE OBVIOUS IMPLEMENTATION CANNOT WORK AND THAT IS WHY THIS IS TESTED. `ThreadingHTTPServer`
    sets `daemon_threads = True`, and `socketserver._Threads.append` discards a daemon thread —
    so the join inside `server_close()` is already a no-op and looks exactly like a drain that
    works. A version that counted threads would pass a smoke test and lose requests in
    production.
    """
    checks.note("")
    checks.note("GRACEFUL DRAIN — server/capture_server.py")

    checks.equal(capture_server.inflight(), 0, "nothing is in flight at rest")
    checks.ok(capture_server.drain(0.2), "and a drain over an idle server returns at once")

    # DERIVED, NOT A LITERAL. A capture posted while `./pkmnscan identify` holds the store lock
    # legitimately waits `LOCK_TIMEOUT_SECONDS` before answering `store_busy`, so a drain
    # shorter than that would cut a request that was behaving correctly. Asserting the
    # arithmetic rather than the number means it moves the day the lock timeout does.
    checks.equal(
        capture_server.DRAIN_SECONDS,
        files.LOCK_TIMEOUT_SECONDS + 5,
        "the drain outlasts the store lock, so a legitimate store_busy is never cut short",
    )

    entered = threading.Event()
    release = threading.Event()

    def occupy() -> None:
        capture_server._inflight_enter()
        entered.set()
        release.wait(10)
        capture_server._inflight_leave()

    worker = threading.Thread(target=occupy, daemon=True)
    worker.start()
    entered.wait(5)

    checks.equal(capture_server.inflight(), 1, "a request in flight is counted")
    checks.ok(
        not capture_server.drain(0.3),
        "and a drain REFUSES to return while it is still running — the whole point",
    )

    release.set()
    worker.join(5)
    checks.equal(capture_server.inflight(), 0, "the counter falls when the request finishes")
    checks.ok(capture_server.drain(0.5), "and the drain then returns true")

def check_supervisor_recovery(checks: Checks) -> None:
    """`scripts/serve.py` counts a FAST failure, and confirms a recovery it did not choose.

    Its own block for `check_drain`'s reason: it asserts nothing about a route. It is about
    the supervisor `make launch-agent` keeps alive across days, and both halves were found on
    the owner's own rig on 2026-09-06 rather than reasoned about.

    THE COUNTER'S NAME WAS THE SPECIFICATION AND NOTHING IMPLEMENTED IT. `FAST_FAILURE_SECONDS`
    was declared in that file from the day it was written and read by nothing anywhere in
    `scripts/`, so `_note_exit` counted every exit alike. A supervisor started at login and
    alive for days therefore accumulates unrelated deaths: two clean exits nineteen minutes
    apart had already spent 2 of the 5, and only editing a watched Python file gives them
    back. At 5 it stops respawning a server that is fine, logging that it "failed to stay up".

    This asserts the RULE and not a scenario, because the scenario takes nineteen minutes.
    """
    checks.note("")
    checks.note("SUPERVISOR RECOVERY — scripts/serve.py")

    sup = serve.Supervisor(root=_SERVE_ROOT, watch=False)

    # A child that never got going is what the limit is for.
    sup.capture_started = time.time() - 0.5
    sup._note_exit()
    checks.equal(sup.fast_failures, 1, "a death inside the window counts")
    sup.capture_started = time.time() - 0.5
    sup._note_exit()
    checks.equal(sup.fast_failures, 2, "and they accumulate while they stay fast")

    # A child that served, then died, is not in a crash loop — and this is the assertion the
    # missing reader cost: before it, this said 3.
    sup.capture_started = time.time() - (serve.FAST_FAILURE_SECONDS + 1)
    sup._note_exit()
    checks.equal(
        sup.fast_failures, 1,
        "a death AFTER the window resets the count — the owner's rig spent 2 of 5 on two "
        "healthy days' exits",
    )
    checks.ok(not sup.giving_up, "and the supervisor is still respawning")

    # The limit still fires on a real loop, which is the behaviour being preserved.
    loop = serve.Supervisor(root=_SERVE_ROOT, watch=False)
    for _ in range(serve.FAST_FAILURE_LIMIT):
        loop.capture_started = time.time() - 0.1
        loop._note_exit()
    checks.ok(
        loop.giving_up,
        f"{serve.FAST_FAILURE_LIMIT} deaths inside the window still stops the respawn",
    )

    # DERIVED, NOT A LITERAL, in `check_drain`'s idiom: the window has to be shorter than the
    # shortest backoff, or a child could never be observed living longer than one.
    checks.ok(
        serve.RESTART_BACKOFF[0] < serve.FAST_FAILURE_SECONDS,
        "the window outlasts the shortest backoff, so a respawn is not counted as its own "
        "fast failure",
    )

    # The recovery path confirms itself. It used to end at `spawn_capture` with no probe and
    # no line, so the log's last word on a recovery was "restarting in 4s" and a healthy rig
    # read exactly like a wedged one.
    checks.ok(
        hasattr(sup, "_await_capture"),
        "the crash-recovery respawn has a probe-and-log step",
    )
    source = inspect.getsource(serve.Supervisor._reap)
    checks.ok(
        "_await_capture" in source,
        "and `_reap` calls it, so a recovery says whether it worked",
    )
    checks.ok(
        "_await_capture" in inspect.getsource(serve.Supervisor._restart_for),
        "and the watcher path goes through the same one, so the two cannot drift",
    )


CHECKS = (
    check_allocator,
    check_next_index_sql,
    check_boxes_and_listings,
    check_store,
    check_set_and_rarity,
    check_open_read_only,
    check_open_read_only_race,
    check_open_read_only_wal_present_never_falls_back,
    check_open_read_only_corrupt_main_file,
    check_store_of_record,
    check_photo_reclaim,
    check_skus_photos_limit,
    check_server_routes,
    check_drain,
    check_supervisor_recovery,
)
