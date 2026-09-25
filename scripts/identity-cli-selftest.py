#!/usr/bin/env python3
"""LANE 3B — the CLI writers move onto `Inventory.bind_sku`
(docs/specs/identity-follows-sku.md §4.2, §3.2 item 3).

WHAT THIS PROVES, the lane's own "done when" line (§11's table):

  1. `pkmnscan emit` (the join's commit, D253 comment: "identity is the row's by
     construction") upserts the matched export row into the `skus` table and THEN binds
     through `Inventory.bind_sku` — on a completely fresh store, whose `skus` table starts
     empty, so the only way `bind_sku` can succeed without raising `SkuUnknown` is if the
     upsert ran first, in the same transaction, exactly as `bind_sku`'s own docstring
     requires of every caller.
  2. A re-identification of an already-bound card
     (`Inventory.record_identification`/`cli/cmd_identify.py:_read_disputes_for`) changes
     only `read_name`/`read_number`/`read_printed_total`/`confidence`/`detected_finish` —
     the bound identity (`name`, `number`, `printed_total`) does not move, because it is the
     SKU table's now, not the read's.
  3. `pkmnscan join --export <file>` and `pkmnscan reconcile --live <file>` each fill the
     `skus` table from EVERY row of the file they read, not only the rows a card matched —
     `cli/cmd_join.py` re-reads the file whole for this reason (its own catalog is D137's
     Near-Mint-and-Sealed narrowing, which this table must not inherit).
  4. A two-game merged emit (`pkmnscan emit <pokemon-run> <riftbound-run>`, no
     --split-games) resolves each SKU's `number_strategy` and `product_line` off its OWN
     game — a Pokemon card's number splits at the slash, a Riftbound card's stays whole —
     and every card of the merged send binds: `sku`, `identity_source == 'sku'`,
     `bound_by == 'join'`.
  5. REVIEW FINDING, HIGH, on commit 1b5c90e5. A card re-identified between `join` and
     `emit`, disputing the row `join` already matched, is WITHHELD before anything is
     written for it: absent from `import.csv`, no `pushed` count, no posting, no
     `set_state` — the card is byte-for-byte untouched — and it is routed to the review
     queue under D253's `routing.NAME_DISPUTED` (§4.1's own fallback: Lane 2's own reason,
     if it ever lands on this branch, replaces it). RED on 1b5c90e5 (the position reached
     the CSV and was pushed with no SKU bound); GREEN after `_withhold_disputed`.

NO SQLITE FOR CASE 2 (record_identification/`_read_disputes_for`) — pure `Inventory`/`Skus`
objects in memory, `scripts/identity-store-selftest.py`'s own style, because that is what is
being proved and a store adds nothing to the proof. CASES 1 AND 3 NEED A REAL STORE AND THE
REAL CLI DISPATCH (`cli.__main__.main`), because what is being proved is that the wiring
between `cli/cmd_emit.py`/`cli/cmd_join.py`/`cli/cmd_reconcile.py` and `store/skus.py` is
real, not a restatement of `bind_sku`'s own already-proven behaviour — `harness/tests/
t3_join_coverage.py`'s own `_isolated_home`/`_command` pattern, reused rather than
reinvented, over the same committed fixture (`fixtures/sv09_export_untouched.csv`).

This lane changes no data on disk in the owner's own store, and this script never opens it —
every store here is a `tempfile.TemporaryDirectory()`, destroyed on the way out (D18 does not
even apply: nothing here generates a tracked file).
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli import cmd_identify, runs  # noqa: E402
from pipeline import games, routing, tcgcsv  # noqa: E402
from pipeline.skus import row_from_csv  # noqa: E402
from store import files, master  # noqa: E402
from store.master import Card, Inventory  # noqa: E402
from store.skus import Skus  # noqa: E402
from store.session import Store  # noqa: E402

PASS = 0
FAIL = 0


def ok(condition: bool, label: str, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok     {label}")
    else:
        FAIL += 1
        print(f"  FAIL   {label}")
        if detail:
            for line in str(detail).splitlines()[:8]:
                print(f"         {line}")


SOURCE_FIXTURE = ROOT / "fixtures" / "sv09_export_untouched.csv"
# Dunsparce, 120/159, Near Mint, $2.06 — `harness/tests/t3_join_coverage.py:SEVEN_COPY_SKU`,
# the same real row, reused rather than re-typed.
DUNSPARCE_SKU = "8608459"
DUNSPARCE_NAME = "Dunsparce"
DUNSPARCE_NUMBER = "120"
# A DIFFERENT row in the SAME file, matched to no card this script ever captures — present
# only to prove a whole-file fold rather than a matched-rows one.
# `harness/tests/t3_join_coverage.py:AMPERSAND_NORMAL_SKU`.
UNMATCHED_SKU = "8608674"
BOX = 3

# A second game's real fixture and one real row from it, for the two-game merged-emit case
# (review finding, MEDIUM) — `harness/tests/t3_join_coverage.py:RIFTBOUND_DEFY_SKU`, the
# same row, reused rather than re-typed.
RIFTBOUND_FIXTURE = ROOT / "fixtures" / "riftbound_export_untouched.csv"
RIFTBOUND_SKU = "8925787"
RIFTBOUND_NAME = "Defy"
RIFTBOUND_NUMBER = "045/298"
RIFTBOUND_BOX = 4


# ------------------------------------------------------------------------------ the store


def _isolated_home():
    """`harness/tests/t3_join_coverage.py:_isolated_home`, reused rather than reimplemented
    — a whole store in a throwaway directory, the previous `PKMNSCAN_HOME` restored on the
    way out."""
    from contextlib import contextmanager

    @contextmanager
    def _cm():
        previous = os.environ.get(files.HOME_ENV)
        with tempfile.TemporaryDirectory() as tmp:
            os.environ[files.HOME_ENV] = tmp
            try:
                yield Path(tmp)
            finally:
                if previous is None:
                    os.environ.pop(files.HOME_ENV, None)
                else:
                    os.environ[files.HOME_ENV] = previous

    return _cm()


def _capture(copies: int, box: int = BOX) -> None:
    with Store().write() as snapshot:
        for index in range(1, copies + 1):
            snapshot.inventory.record_capture(
                Card(
                    box=box,
                    index=index,
                    photo=f"captures/box{box}/{index:04d}.jpg",
                    cid=hashlib.sha256(f"{box}/{index}".encode()).hexdigest(),
                )
            )


def _identifications(
    copies: int, name: str, number: str, box: int = BOX, *,
    game: str = "pokemon", printed_total: Optional[str] = "159",
) -> dict:
    """`harness/tests/t3_join_coverage.py:_identifications` — an `identifications.json`
    payload shaped as `cli/cmd_identify.py` writes it. `game`, per card and never per run
    (D21) — `harness/tests/t3_join_coverage.py:_two_game_payload`'s own reason to carry it
    here rather than default it, for the two-game merged-emit case."""
    return {
        "prompt_fingerprint": "identity-cli-selftest",
        "cards": {
            master.position_key(box, index): {
                "photo": f"captures/box{box}/{index:04d}.jpg",
                "box": box,
                "index": index,
                "set_hint": None,
                "metadata_finish": "normal",
                "status": "ok",
                "game": game,
                "identification": {
                    "name": name,
                    "number": number,
                    "printed_total": printed_total,
                    "confidence": "high",
                    "finish": "normal",
                },
            }
            for index in range(1, copies + 1)
        },
    }


def _command(*argv: str) -> str:
    """One `./pkmnscan` subcommand through the real dispatch — `harness/tests/
    t3_join_coverage.py:_command`, minus its `Checks` dependency (a standalone script)."""
    from cli import __main__ as entry

    buffer = StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        code = entry.main(list(argv))
    text = buffer.getvalue()
    if code != 0:
        print(f"  ... `pkmnscan {argv[0]}` exited {code}:\n{text}")
    return text


# --------------------------------------------------------------------------------- case 1


def _case_1_emit_upserts_then_binds() -> None:
    print("\n-- 1. `pkmnscan emit` upserts the matched row, then binds (§4.1, §4.2) --")
    with _isolated_home():
        before = Store().read().skus.entries
        ok(DUNSPARCE_SKU not in before,
           "a fresh store's skus table starts empty — the SKU this case binds is not in it "
           "yet, which is what makes a successful bind proof that the upsert ran first")

        _capture(1)
        run = runs.create("identity-cli-emit")
        run.write_identifications(_identifications(1, DUNSPARCE_NAME, DUNSPARCE_NUMBER))
        export_path = run.path("export.csv")
        export = tcgcsv.read_export(SOURCE_FIXTURE)
        tcgcsv.write_csv(export_path, export.header, export.rows)

        _command("join", str(run.directory), "--export", str(export_path))
        _command("emit", str(run.directory))

        snapshot = Store().read()
        card = snapshot.inventory.cards.get(master.position_key(BOX, 1))
        ok(card is not None, "the card is still on record after emit")
        if card is None:
            return
        ok(card.sku == DUNSPARCE_SKU, "bound to the matched SKU", card.sku)
        ok(card.identity_source == master.IDENTITY_SKU,
           "identity_source is 'sku' — bind_sku's own write, not record_identification's",
           card.identity_source)
        ok(card.bound_by == "join", "bound_by names the act that bound it", card.bound_by)
        ok(card.bound_at is not None, "bound_at is stamped")
        ok(card.name == "Dunsparce", "name composed off the SKU row", card.name)
        ok((card.number, card.printed_total) == ("120", "159"),
           "number/printed_total split off the SKU row's own Number cell",
           f"{card.number!r}/{card.printed_total!r}")
        ok(card.rarity == "Common" and card.set_name == "SV09: Journey Together"
           and card.condition == "Near Mint",
           "rarity/set_name/condition verbatim off the row",
           f"{card.rarity!r} {card.set_name!r} {card.condition!r}")

        row = snapshot.skus.entries.get(DUNSPARCE_SKU)
        ok(row is not None, "the SKU table now holds the matched row — the upsert landed")
        if row is not None:
            ok(row.product_name == "Dunsparce" and row.number == "120/159",
               "and it is the real export row, not a placeholder",
               f"{row.product_name!r} {row.number!r}")


# --------------------------------------------------------------------------------- case 2


def _case_2_reidentify_writes_only_read() -> None:
    print("\n-- 2. a re-identification writes only read_* on a bound card (§3.1, §4.2) --")

    # A card bound to a SKU, exactly as `scripts/identity-store-selftest.py` case 1 binds
    # one — `bind_sku` is already proved there; this case is about what happens AFTER.
    row = row_from_csv(
        {
            tcgcsv.SKU_COLUMN: DUNSPARCE_SKU,
            tcgcsv.PRODUCT_LINE_COLUMN: "Pokemon",
            tcgcsv.SET_COLUMN: "SV09: Journey Together",
            tcgcsv.NAME_COLUMN: DUNSPARCE_NAME,
            tcgcsv.NUMBER_COLUMN: "120/159",
            tcgcsv.RARITY_COLUMN: "Common",
            tcgcsv.CONDITION_COLUMN: "Near Mint",
        },
        at=1,
        source="test-fixture.csv",
    )
    assert row is not None
    sku, sku_row = row
    skus = Skus()
    skus.fold(sku, sku_row)

    inv = Inventory()
    key = "1/1"
    inv.cards[key] = Card(box=1, index=1, game="pokemon", cid="cid-1", state=master.IDENTIFIED)
    inv.bind_sku(
        key, DUNSPARCE_SKU, bound_by="answer", skus=skus,
        number_strategy=games.get("pokemon")["join_key"],
        expected_product_line=games.get("pokemon")["product_line"],
    )
    bound_identity = (
        inv.cards[key].name, inv.cards[key].number, inv.cards[key].printed_total,
        inv.cards[key].rarity, inv.cards[key].set_name, inv.cards[key].condition,
    )

    class _Writable:
        """The one shape `_read_disputes_for` reads — `.inventory` and `.skus` — without
        pulling in `store/session.py:Snapshot` for two attributes."""

        def __init__(self, inventory, skus_table):
            self.inventory = inventory
            self.skus = skus_table

    writable = _Writable(inv, skus)

    # A fresh read that AGREES with the bound name: no dispute.
    agreeing = cmd_identify._read_disputes_for(writable, key, "Dunsparce")
    ok(agreeing is False, "an agreeing re-read: read_disputes is False", agreeing)

    # A fresh read that DISPUTES the bound name outright.
    disputing = cmd_identify._read_disputes_for(writable, key, "Charizard")
    ok(disputing is True, "a disputing re-read: read_disputes is True", disputing)

    # An unbound card has nothing to dispute against.
    inv.cards["1/2"] = Card(box=1, index=2, game="pokemon", cid="cid-2", state=master.IDENTIFIED)
    unbound = cmd_identify._read_disputes_for(writable, "1/2", "Anything")
    ok(unbound is None, "an unbound card: read_disputes is None — nothing to compare", unbound)

    # THE ACTUAL RE-IDENTIFICATION. A fresh read disagreeing with the bound card's identity
    # on every field it could touch.
    inv.record_identification(
        key,
        name="Charizard",
        number="4",
        printed_total="102",
        confidence="high",
        read_disputes=disputing,
    )
    card = inv.cards[key]
    ok((card.read_name, card.read_number, card.read_printed_total) ==
       ("Charizard", "4", "102"),
       "read_name/read_number/read_printed_total take the fresh reading",
       f"{card.read_name!r} {card.read_number!r} {card.read_printed_total!r}")
    ok((card.name, card.number, card.printed_total, card.rarity, card.set_name, card.condition)
       == bound_identity,
       "the BOUND identity is untouched — it is the SKU table's fact, not the read's",
       str((card.name, card.number, card.printed_total, card.rarity, card.set_name,
            card.condition)))
    ok(card.identity_source == master.IDENTITY_SKU,
       "identity_source stays 'sku' across the re-identification", card.identity_source)
    ok(card.read_disputes is True,
       "read_disputes is written from the caller's own recomputed answer", card.read_disputes)


# --------------------------------------------------------------------------------- case 3


def _case_3_join_export_fills_every_row() -> None:
    print("\n-- 3. `pkmnscan join --export` fills the table from EVERY row (§3.2 item 3) --")
    with _isolated_home():
        _capture(1)
        run = runs.create("identity-cli-join-fill")
        run.write_identifications(_identifications(1, DUNSPARCE_NAME, DUNSPARCE_NUMBER))
        export_path = run.path("export.csv")
        export = tcgcsv.read_export(SOURCE_FIXTURE)
        tcgcsv.write_csv(export_path, export.header, export.rows)

        _command("join", str(run.directory), "--export", str(export_path))

        entries = Store().read().skus.entries
        ok(DUNSPARCE_SKU in entries, "the matched SKU landed in the table")
        ok(UNMATCHED_SKU in entries,
           "AND a SKU no card matched ALSO landed — the fold reads the whole file, "
           "not `Catalog`'s D137-narrowed rows or the join's matched set")
        ok(len(entries) == len(export.rows),
           "every row of the fixture is in the table", f"{len(entries)} of {len(export.rows)}")


def _case_3b_reconcile_live_fills_every_row() -> None:
    print("\n-- 3b. `pkmnscan reconcile --live` fills the table too (§3.2 item 3) --")
    with _isolated_home() as home:
        export = tcgcsv.read_export(SOURCE_FIXTURE)
        live_path = Path(home) / "live.csv"
        tcgcsv.write_csv(live_path, export.header, export.rows)

        _command("reconcile", "--live", str(live_path), "--write")

        entries = Store().read().skus.entries
        ok(DUNSPARCE_SKU in entries and UNMATCHED_SKU in entries,
           "both SKUs landed — reconcile --live never narrows to a game or a match")
        ok(len(entries) == len(export.rows),
           "every row of the fixture is in the table", f"{len(entries)} of {len(export.rows)}")


# --------------------------------------------------------------------------------- case 4


def _case_4_two_game_merged_emit() -> None:
    print("\n-- 4. a two-game merged emit, no --split-games (review finding, MEDIUM) --")
    with _isolated_home():
        _capture(1, box=BOX)
        _capture(1, box=RIFTBOUND_BOX)

        pokemon_export = tcgcsv.read_export(SOURCE_FIXTURE)
        riftbound_export = tcgcsv.read_export(RIFTBOUND_FIXTURE)

        run_a = runs.create("identity-cli-merge-pokemon")
        run_a.write_identifications(
            _identifications(1, DUNSPARCE_NAME, DUNSPARCE_NUMBER, box=BOX, game="pokemon")
        )
        pokemon_path = run_a.path("export.csv")
        tcgcsv.write_csv(pokemon_path, pokemon_export.header, pokemon_export.rows)

        run_b = runs.create("identity-cli-merge-riftbound")
        run_b.write_identifications(
            _identifications(
                1, RIFTBOUND_NAME, RIFTBOUND_NUMBER, box=RIFTBOUND_BOX,
                game="riftbound", printed_total=None,
            )
        )
        riftbound_path = run_b.path("export.csv")
        tcgcsv.write_csv(riftbound_path, riftbound_export.header, riftbound_export.rows)

        _command("join", str(run_a.directory), "--export", str(pokemon_path))
        _command("join", str(run_b.directory), "--export", str(riftbound_path))

        output = _command("emit", str(run_a.directory), str(run_b.directory))

        import_path = run_b.path(runs.IMPORT_MERGED)
        ok(import_path.exists(), "one merged file, no --split-games refusal", output)
        if import_path.exists():
            by_sku = tcgcsv.read_export(import_path).by_sku()
            ok(DUNSPARCE_SKU in by_sku and RIFTBOUND_SKU in by_sku,
               "both games' SKUs are in the SAME file", sorted(by_sku))

        snapshot = Store().read()
        pokemon_card = snapshot.inventory.cards[master.position_key(BOX, 1)]
        riftbound_card = snapshot.inventory.cards[master.position_key(RIFTBOUND_BOX, 1)]

        ok(pokemon_card.sku == DUNSPARCE_SKU, "Pokemon card bound to its own SKU",
           pokemon_card.sku)
        ok((pokemon_card.number, pokemon_card.printed_total) == ("120", "159"),
           "Pokemon's number_strategy (number_and_printed_total) split the cell",
           f"{pokemon_card.number!r}/{pokemon_card.printed_total!r}")
        ok(pokemon_card.identity_source == master.IDENTITY_SKU
           and pokemon_card.bound_by == "join",
           "Pokemon card: identity_source='sku', bound_by='join'",
           (pokemon_card.identity_source, pokemon_card.bound_by))

        ok(riftbound_card.sku == RIFTBOUND_SKU, "Riftbound card bound to its own SKU",
           riftbound_card.sku)
        ok((riftbound_card.number, riftbound_card.printed_total) == ("045/298", None),
           "Riftbound's number_strategy (printed_code) kept the cell verbatim",
           f"{riftbound_card.number!r}/{riftbound_card.printed_total!r}")
        ok(riftbound_card.identity_source == master.IDENTITY_SKU
           and riftbound_card.bound_by == "join",
           "Riftbound card: identity_source='sku', bound_by='join'",
           (riftbound_card.identity_source, riftbound_card.bound_by))


# --------------------------------------------------------------------------------- case 5


def _case_5_dispute_withheld_before_write() -> None:
    print("\n-- 5. a card disputed between join and emit is withheld, not written "
          "(review finding, HIGH, on 1b5c90e5) --")
    with _isolated_home():
        _capture(1, box=BOX)
        run = runs.create("identity-cli-dispute")
        run.write_identifications(_identifications(1, DUNSPARCE_NAME, DUNSPARCE_NUMBER))
        export_path = run.path("export.csv")
        export = tcgcsv.read_export(SOURCE_FIXTURE)
        tcgcsv.write_csv(export_path, export.header, export.rows)

        _command("join", str(run.directory), "--export", str(export_path))

        key = master.position_key(BOX, 1)

        # THE PLANT: a re-identification landing BETWEEN join and emit, disagreeing with
        # the row join already matched — this is `pkmnscan identify` running again over
        # the same photograph, the ordinary shape a defensive backstop has to survive.
        with Store().write() as writable:
            writable.inventory.record_identification(
                key, name="Charizard", number="4", printed_total="102", confidence="high",
            )
        before = dict(Store().read().inventory.cards[key].__dict__)

        output = _command("emit", str(run.directory))

        import_path = run.path(runs.IMPORT_MERGED)
        ok(not import_path.exists(),
           "no CSV copy: the only copy of this SKU was the disputed one, so "
           "add_to_quantity is 0 and emit's own D54 guard never opens the file at all",
           output)

        after = dict(Store().read().inventory.cards[key].__dict__)
        ok(before == after,
           "the card is BYTE-FOR-BYTE untouched by emit — no set_state, no bind_sku",
           {k: (before.get(k), after.get(k)) for k in before if before.get(k) != after.get(k)})

        listing = Store().read().inventory.listings.get(DUNSPARCE_SKU)
        ok(listing is None or listing.pushed == 0,
           "no PUSHED count moved for it — no posting either, by the same code path",
           listing)

        ok("disputed" in output and "1 card(s) withheld" in output,
           "the output names it, under its own heading", output)

        entry = Store().read().review.entries.get(key)
        ok(entry is not None, "and it is routed to the review queue", entry)
        if entry is not None:
            ok(entry.reason == routing.NAME_DISPUTED,
               "under D253's routing.NAME_DISPUTED — §4.1's own fallback reason",
               entry.reason)
            ok(entry.read.get("name") == "Charizard",
               "carrying the fresh, disputing read", entry.read)


# ------------------------------------------------------------------------------------- main


def main() -> int:
    print("identity-cli self-test (docs/specs/identity-follows-sku.md §4.2, lane 3b)\n")

    _case_1_emit_upserts_then_binds()
    _case_2_reidentify_writes_only_read()
    _case_3_join_export_fills_every_row()
    _case_3b_reconcile_live_fills_every_row()
    _case_4_two_game_merged_emit()
    _case_5_dispute_withheld_before_write()

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
