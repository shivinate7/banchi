#!/usr/bin/env python3
"""`store/pricearchive.py` and `pipeline/pricearchive.py`, proved against a throwaway store
(D219).

NO NETWORK CALL. `FakeMarket` below is a stand-in for `pipeline/pricehistory.py:Market`,
duck-typed to the one method `pipeline/pricearchive.py:sweep` calls
(`readings_for_rows(rows, ranges=...)`), and it answers out of canned
`pipeline/pricehistory.py:Bucket`/`Series`/`Reading` objects built in this file — the same
dataclasses the real `Market` returns, never a second, drifting shape.

THE ARM THIS FILE EXISTS FOR proves the D62 argument this branch's own decision entry makes
(D219): archiving the SAME calendar day out of `semiannual` and
`annual` — both seven-day-wide ranges — must leave TWO rows, because the two are independent
observations
even when their bucket happens to start on the same date. A second arm builds the archive's
own key with `width_days` in place of `range` and shows THAT key collapses the two into one
row — the guard is trusted only once it has been seen to fail on the defect it guards
(`CLAUDE.md`'s own rule).

Written, not wired into `make check` — `make catalog-index-selftest`'s own precedent, a fast
self-contained proof of a package with no caller yet reachable from a screen.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import games as games_module  # noqa: E402
from pipeline import join as join_module  # noqa: E402
from pipeline import pricearchive as archive_walk  # noqa: E402
from pipeline import pricehistory  # noqa: E402
from pipeline import tcgcsv as tcgcsv_module  # noqa: E402
from pipeline.pricehistory import Bucket as HistoryBucket  # noqa: E402
from pipeline.pricehistory import Reading as HistoryReading  # noqa: E402
from pipeline.pricehistory import Series  # noqa: E402
from store import files  # noqa: E402
from store.master import Card  # noqa: E402
from store.orders import OrderLine, OrderRecord  # noqa: E402
from store.pricearchive import Bucket, PriceArchive, Source, _key  # noqa: E402
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


class _FakeArchiveForSku:
    """A `store/pricearchive.py:PriceArchive`-shaped stand-in over a plain
    `sku -> productId` dict, for `resolve_by_sku`'s own tier (a) — the one method it calls,
    `for_sku`, answering a single synthetic `Bucket` with everything else zeroed, since
    `resolve_by_sku` reads only `.product_id` off whatever `for_sku` returns."""

    def __init__(self, verified: Dict[str, int]):
        self._verified = verified

    def for_sku(self, sku: str):
        product_id = self._verified.get(sku)
        if not product_id:
            return []
        return [
            Bucket(
                sku=sku, product_id=int(product_id), range="month", width_days=1,
                start="2026-01-01", market=None, quantity=0, transactions=0,
                low=None, high=None, at=0,
            )
        ]


class FakeMarket:
    """Answers `readings_for_rows` out of a fixed script, no network, no `Market` at all.

    `script` maps sku -> {range: Series}. A sku with no entry is a REFUSAL, exactly like the
    real `Market.readings_for_rows` reporting a sku it could not resolve — both directions
    (found and refused) are exercised by every test below that touches this class.
    """

    def __init__(self, script: Dict[str, Dict[str, Series]], refuse: Dict[str, str] = None):
        self.script = script
        self.refuse = refuse or {}

    def readings_for_rows(self, rows, ranges=(), *, product_ids=None):
        readings = {}
        refusals = dict(self.refuse)
        for row in rows:
            sku = row.get("TCGplayer Id", "")
            series_by_range = self.script.get(sku)
            if series_by_range is None:
                refusals.setdefault(sku, "not in the script")
                continue
            wanted = {r: s for r, s in series_by_range.items() if r in ranges}
            readings[sku] = HistoryReading(sku=sku, product_id=42, series=wanted)
        return readings, refusals


class RecordingMarket:
    """Answers every SKU it is asked about out of `script`, and REMEMBERS every SKU it was
    ever asked about — the proof surface for "a resumed sweep must not re-fetch what it
    already holds from this same pass" (D224). A test hands this the
    SKUs a chunk is supposed to skip and asserts they never appear in `.asked`.

    ONE CALL RAISES ON PURPOSE, IF `raise_on` NAMES A SKU. This is the stand-in for a
    dropped connection or a Ctrl-C mid-chunk (D224's other half): the
    exception is a plain `RuntimeError`, never a `pipeline.pricehistory.PriceHistoryError`,
    so it propagates PAST `readings_for_rows`'s own per-product `except` the same way a
    `KeyboardInterrupt` would — this class is not exercising that internal catch, it is
    exercising what happens to a CALLER who chunks the walk instead of a caller who does not.
    """

    def __init__(self, script, raise_on=None):
        self.script = script
        self.raise_on = raise_on or set()
        self.asked = set()

    def readings_for_rows(self, rows, ranges=(), *, product_ids=None):
        readings = {}
        refusals = {}
        for row in rows:
            sku = row.get("TCGplayer Id", "")
            self.asked.add(sku)
            if sku in self.raise_on:
                raise RuntimeError(f"connection dropped reading {sku}")
            series_by_range = self.script.get(sku)
            if series_by_range is None:
                refusals.setdefault(sku, "not in the script")
                continue
            wanted = {r: s for r, s in series_by_range.items() if r in ranges}
            readings[sku] = HistoryReading(sku=sku, product_id=42, series=wanted)
        return readings, refusals


def _series(sku: str, range_: str, start: date, market: str, quantity: int = 1) -> Series:
    bucket = HistoryBucket(
        start=start,
        market=Decimal(market),
        quantity=quantity,
        transactions=quantity,
        low=Decimal(market),
        high=Decimal(market),
    )
    return Series(
        sku=sku, product_id=42, range=range_, variant="Normal", condition="Near Mint",
        language="English", total_quantity_sold=quantity, total_transaction_count=quantity,
        buckets=(bucket,),
    )


def main() -> int:
    print("price-history archive self-test\n")

    # ---------------------------------------------------------------- store-level: the key
    print("-- store/pricearchive.py: the key argument (D62) --")
    archive = PriceArchive()
    same_day = date(2026, 1, 1)
    semiannual = Bucket(
        sku="111", product_id=42, range="semiannual", width_days=7,
        start=same_day.isoformat(), market="5.00", quantity=2, transactions=2,
        low="4.50", high="5.50", at=100,
    )
    annual = Bucket(
        sku="111", product_id=42, range="annual", width_days=7,
        start=same_day.isoformat(), market="6.00", quantity=3, transactions=3,
        low="5.50", high="6.50", at=100,
    )
    archive.upsert({
        _key("111", "semiannual", same_day.isoformat()): semiannual,
        _key("111", "annual", same_day.isoformat()): annual,
    })
    ok(len(archive.entries) == 2,
       "same sku, same start date, different ranges -> two rows, not one",
       dict(archive.entries))
    ranges_seen = {b.range for b in archive.entries.values()}
    ok(ranges_seen == {"semiannual", "annual"},
       "both ranges survive, each carrying its own market figure", ranges_seen)

    # The defect this guards against, PROVEN to fail on it: a WIDTH-only key merges them.
    width_only: Dict[str, Bucket] = {}
    for bucket in (semiannual, annual):
        collision_key = f"{bucket.sku}:{bucket.width_days}:{bucket.start}"
        width_only[collision_key] = bucket
    ok(len(width_only) == 1,
       "a key built from (sku, width_days, start) instead DOES collapse the two ranges into "
       "one row — this is the bug D219's key design avoids",
       width_only)

    # ---------------------------------------------------------------- never-delete
    print("\n-- store/pricearchive.py: a bucket a later pass does not mention survives --")
    archive2 = PriceArchive()
    archive2.upsert({
        _key("222", "month", "2026-01-01"): Bucket(
            sku="222", product_id=1, range="month", width_days=1, start="2026-01-01",
            market="1.00", quantity=1, transactions=1, low="1.00", high="1.00", at=100,
        ),
    })
    # A later pass over a DIFFERENT sku entirely — "222" is not mentioned at all.
    archive2.upsert({
        _key("333", "month", "2026-01-01"): Bucket(
            sku="333", product_id=2, range="month", width_days=1, start="2026-01-01",
            market="2.00", quantity=1, transactions=1, low="2.00", high="2.00", at=200,
        ),
    })
    ok("222:month:2026-01-01" in archive2.entries,
       "a sku no later sweep mentions is never deleted", dict(archive2.entries))
    ok(len(archive2.entries) == 2, "the new sku is ADDED beside it, not instead of it")

    # A later pass over the SAME key, with a corrected reading, replaces just that row.
    archive2.upsert({
        _key("222", "month", "2026-01-01"): Bucket(
            sku="222", product_id=1, range="month", width_days=1, start="2026-01-01",
            market="1.50", quantity=2, transactions=2, low="1.00", high="2.00", at=300,
        ),
    })
    corrected = archive2.entries["222:month:2026-01-01"]
    ok(corrected.market == "1.50" and corrected.at == 300,
       "a re-read of the SAME key with newer data replaces that row", corrected)

    # `record_pass` replaces only the range it names, not the whole sources table.
    archive2.record_pass([Source(range="month", at=100, requested=1, answered=1, refused=0)])
    archive2.record_pass([Source(range="annual", at=200, requested=1, answered=1, refused=0)])
    payload = {s["range"]: s for s in archive2.sources_payload()}
    ok(set(payload) == {"month", "annual"},
       "a pass over one range never erases another range's own accounting row", payload)

    # ---------------------------------------------- pipeline: parse_ledger_name (sealed subjects)
    print("\n-- pipeline/pricearchive.py: parse_ledger_name, pure, no store, no network --")

    def _groups(*names: str) -> Dict[str, dict]:
        return {
            join_module.normalize_set(n): {"name": n, "groupId": i}
            for i, n in enumerate(names)
        }

    POKEMON_GROUPS = _groups("SV09: Journey Together", "SV08: Surging Sparks", "Celebrations")
    ONE_PIECE_GROUPS = _groups("The Azure Sea's Seven")
    RIFTBOUND_GROUPS = _groups("Origins")

    fixture_table = [
        # (label, name, groups, expected (line, set, product_name, number, condition) or None)
        (
            "Pokemon single",
            "Pokemon - SV09: Journey Together: Wailord - 162/159 - #162/159 - "
            "Near Mint Holofoil",
            POKEMON_GROUPS,
            ("Pokemon", "SV09: Journey Together", "Wailord - 162/159", "162/159",
             "Near Mint Holofoil"),
        ),
        (
            "Pokemon sealed (no number)",
            "Pokemon - SV08: Surging Sparks: Surging Sparks Booster Box - Unopened",
            POKEMON_GROUPS,
            ("Pokemon", "SV08: Surging Sparks", "Surging Sparks Booster Box", "", "Unopened"),
        ),
        (
            "One Piece single",
            "One Piece Card Game - The Azure Sea's Seven: Gecko Moria - OP14-104 - "
            "#OP14-104 - Near Mint Foil",
            ONE_PIECE_GROUPS,
            ("One Piece Card Game", "The Azure Sea's Seven", "Gecko Moria - OP14-104",
             "OP14-104", "Near Mint Foil"),
        ),
        (
            "Riftbound single",
            "Riftbound League of Legends Trading Card Game - Origins: Nocturne, "
            "Horrifying - #194/298 - Near Mint Foil",
            RIFTBOUND_GROUPS,
            ("Riftbound League of Legends Trading Card Game", "Origins",
             "Nocturne, Horrifying", "194/298", "Near Mint Foil"),
        ),
        (
            "sealed name with a bracket",
            "Pokemon - Celebrations: Celebrations Mini Tin [Hoenn] - Unopened",
            POKEMON_GROUPS,
            ("Pokemon", "Celebrations", "Celebrations Mini Tin [Hoenn]", "", "Unopened"),
        ),
        (
            "REFUSED: unknown, uncatalogued product line",
            "Magic: The Gathering - Foundations: Some Card - Near Mint",
            POKEMON_GROUPS,
            None,
        ),
        (
            "REFUSED: product line known, group not in the mirror's list",
            "Pokemon - NotARealSet: Some Card - Near Mint",
            POKEMON_GROUPS,
            None,
        ),
        (
            "REFUSED: no ' - ' separator at all",
            "Pokemon SV09 Wailord Near Mint",
            POKEMON_GROUPS,
            None,
        ),
    ]

    for label, name, groups, expected in fixture_table:
        try:
            row = archive_walk.parse_ledger_name(name, groups)
        except archive_walk.UnresolvedLedgerName as exc:
            ok(expected is None, f"{label}: refused ({exc})", (name, exc))
            continue
        ok(expected is not None, f"{label}: resolved when it should have been refused", row)
        if expected is not None:
            line, set_name, product_name, number, condition = expected
            got = (
                row[tcgcsv_module.PRODUCT_LINE_COLUMN], row[tcgcsv_module.SET_COLUMN],
                row[tcgcsv_module.NAME_COLUMN], row[tcgcsv_module.NUMBER_COLUMN],
                row[tcgcsv_module.CONDITION_COLUMN],
            )
            ok(got == expected, f"{label}: parses to the right five cells", (got, expected))

    # THE GUARD, PROVEN TO FAIL ON THE DEFECT IT GUARDS. A naive first-`": "`-split reads
    # "SV09" alone for the group name, which is not in the mirror's own group list — the
    # longest-prefix match is what makes the colon-bearing group name resolve at all.
    naive_candidate = "SV09"
    naive_key = join_module.normalize_set(naive_candidate)
    ok(naive_key not in POKEMON_GROUPS,
       "mutation check: the naive first-colon split's candidate is NOT a real group — "
       "confirms the longest-prefix match, not the naive split, is what resolves "
       "'SV09: Journey Together'", naive_key)
    correct = archive_walk._longest_group_prefix(
        "SV09: Journey Together: Wailord - 162/159 - #162/159 - Near Mint Holofoil",
        POKEMON_GROUPS,
    )
    ok(correct is not None and correct[0] == "SV09: Journey Together",
       "the real (longest-prefix) match resolves the colon-bearing group name", correct)

    # ---------------------------------------------------------------- pipeline: rows_from_store
    print("\n-- pipeline/pricearchive.py: rows_from_store reads only the store --")
    previous = os.environ.get(files.HOME_ENV)
    home = Path(tempfile.mkdtemp(prefix="pricearchive-selftest-"))
    os.environ[files.HOME_ENV] = str(home)
    try:
        with Store().write() as snapshot:
            snapshot.inventory.cards["1:1"] = Card(
                box=1, index=1, sku="444", name="Pikachu", number="25/102",
                set_name="Base Set", game="pokemon", condition="Near Mint",
            )
            snapshot.inventory.cards["1:2"] = Card(
                box=1, index=2, sku="555", name="Bulbasaur", number="44/102",
                set_name="Base Set", game="pokemon", condition="Near Mint", state="sold",
            )
            snapshot.inventory.cards["1:3"] = Card(box=1, index=3, sku=None)

        rows = archive_walk.rows_from_store(Store().read())
        ok(set(rows) == {"444", "555"},
           "every distinct, non-empty sku is a subject — sold or on hand alike", rows)
        ok(rows["444"]["Product Line"] == "Pokemon" and rows["444"]["Product Name"] == "Pikachu",
           "the export-shaped row carries the card's own name and resolved product line",
           rows["444"])

        # ------------------- rows_from_store composes the number, D234
        #
        # THE REAL SHAPE (`Bulbasaur` `001` in `ME01: Mega Evolution`, measured 2026-09-20):
        # `cards.number` is stored bare (542 of 542 Pokemon cards with a SKU carry no `/`),
        # and `store/master.py`'s own write path already composes and stores `number_key`
        # (`join_key(number, printed_total)`) for the search index — this asserts
        # `rows_from_store` actually READS that column rather than leaving `Number` bare.
        with Store().write() as snapshot:
            snapshot.inventory.cards["1:4"] = Card(
                box=1, index=4, sku="9001", name="Bulbasaur", number="001",
                printed_total="132", set_name="ME01: Mega Evolution", game="pokemon",
                condition="Near Mint",
            )
            # A Riftbound card: `printed_total` is never set for this game (no denominator
            # to compose), so `number_key` is empty and the bare, already-verbatim `number`
            # must pass through UNCHANGED.
            snapshot.inventory.cards["1:5"] = Card(
                box=1, index=5, sku="9002", name="Vilemaw", number="060/219",
                set_name="Unleashed", game="riftbound", condition="Near Mint",
            )
        composed_rows = archive_walk.rows_from_store(Store().read())
        ok(composed_rows["9001"][tcgcsv_module.NUMBER_COLUMN] == "001/132",
           "a bare Pokemon number is composed with its own stored `printed_total` before "
           "it ever reaches the mirror's number index — `001` alone can never match a "
           "mirror keyed on `001/132`, by arithmetic (number_index_key strips padding, "
           "it does not invent a denominator)",
           composed_rows["9001"])
        ok(composed_rows["9002"][tcgcsv_module.NUMBER_COLUMN] == "060/219",
           "a Riftbound card (no printed_total, no denominator to compose) passes through "
           "with its stored number unchanged",
           composed_rows["9002"])

        # MUTATION GUARD: select only the OLD column set, dropping `number_key`, and confirm
        # the composed row goes back to bare — proves the fix above, not the fixture, is
        # what composes it.
        old_columns = ("sku", "name", "number", "set_name", "condition", "game")
        mutated_row = None
        for _, values in Store().read().inventory.cards.select(old_columns, sku="9001"):
            name, number, set_name, condition, game = values[1:]
            mutated_row = archive_walk._export_row("9001", name, number, set_name, condition, game)
        ok(mutated_row is not None and mutated_row[tcgcsv_module.NUMBER_COLUMN] == "001",
           "MUTATION: with no number_key handed in, the row goes back to the bare number — "
           "the composition lives in the column read, not in `_export_row`'s own defaults",
           mutated_row)

        # ------------------------------------------ ledger widening: sealed subjects
        print("\n-- pipeline/pricearchive.py: rows_from_store widened to the order ledger "
              "(sealed product) --")

        class GroupMarket:
            """A `_MarketLike` stand-in for `category_id`/`groups` alone — the two hops
            `ledger_subject_rows` calls, no network, no `readings_for_rows`."""

            def __init__(self, category_id: int, groups: Dict[str, dict]):
                self._category_id = category_id
                self._groups = groups
                self.category_id_calls = 0

            def category_id(self, product_line: str) -> int:
                self.category_id_calls += 1
                if product_line != "Pokemon":
                    raise ValueError(f"no category for {product_line!r}")
                return self._category_id

            def groups(self, category_id: int) -> Dict[str, dict]:
                return self._groups

            def readings_for_rows(self, rows, ranges=(), *, product_ids=None):  # unused by this arm
                return {}, {}

        with Store().write() as snapshot:
            # "777" is sealed: no `cards` row, only an order line. "444" is asked for by
            # BOTH a card and an order line with a DIFFERENT name — cards must win.
            snapshot.ledger.orders["ebay:sealed"] = OrderRecord(
                source="ebay", number="sealed", status="Open",
                lines=[
                    OrderLine(
                        sku="777", quantity=1, unit_price="40.00",
                        name="Pokemon - SV08: Surging Sparks: Surging Sparks Booster Box - "
                             "Unopened",
                    ),
                    OrderLine(
                        sku="444", quantity=1, unit_price="9.99",
                        name="Pokemon - SV08: Surging Sparks: A Ledger Name Cards Overrules "
                             "- Near Mint",
                    ),
                    # a sku the grammar cannot parse — reported, never dropped.
                    OrderLine(sku="888", quantity=1, unit_price="5.00", name="junk"),
                ],
            )
        group_market = GroupMarket(3, POKEMON_GROUPS)
        widened_refusals: Dict[str, str] = {}
        widened = archive_walk.rows_from_store(
            Store().read(), market=group_market, refusals=widened_refusals
        )
        ok("777" in widened and widened["777"][tcgcsv_module.NAME_COLUMN] ==
           "Surging Sparks Booster Box",
           "a sealed sku with no `cards` row is resolved from the ledger's own name",
           widened.get("777"))
        ok(widened["444"][tcgcsv_module.NAME_COLUMN] == "Pikachu",
           "a sku `cards` already answers for keeps the CARDS row, even though the ledger "
           "named it too, under a different name", widened["444"])
        ok("888" in widened_refusals,
           "a ledger sku the grammar cannot parse is reported by sku, never silently "
           "dropped", widened_refusals)
        ok(group_market.category_id_calls == 1,
           "Market.category_id/.groups is called once per distinct PRODUCT LINE seen, "
           "never once per sku", group_market.category_id_calls)
        no_market_rows = archive_walk.rows_from_store(Store().read())
        ok("777" not in no_market_rows,
           "with no market given, the subject set is exactly D219's original — cards only",
           no_market_rows)
        # This arm's own order is removed again — later sections in this same run (the
        # revenue/ranking arm below) share this one throwaway store and assert exact
        # totals for "444" that this order would otherwise silently change.
        with Store().write() as snapshot:
            del snapshot.ledger.orders["ebay:sealed"]

        # ---------------- ledger resolution gates on the MIRROR, never on games.py (D231)
        print("\n-- pipeline/pricearchive.py: the ledger parse gates on the MIRROR's own "
              "category list, never pipeline/games.py (D231 amended) --")

        class MirrorOnlyMarket:
            """`category_id`/`groups` answer for whatever THE MIRROR carries, with no
            regard for `pipeline/games.py`'s own registry — `YuGiOh` is real here and
            genuinely absent from `games.py`, checked below rather than assumed."""

            def __init__(self, categories, groups_by_category):
                self._categories = categories
                self._groups = groups_by_category

            def category_id(self, product_line: str) -> int:
                if product_line not in self._categories:
                    raise ValueError(f"no tcgcsv category named {product_line!r}")
                return self._categories[product_line]

            def groups(self, category_id: int) -> Dict[str, dict]:
                return self._groups.get(category_id, {})

            def readings_for_rows(self, rows, ranges=(), *, product_ids=None):  # unused by this arm
                return {}, {}

        class _FakeLedger:
            def __init__(self, orders):
                self.orders = orders

        ok(not any(
            entry.get("product_line") == "YuGiOh" for entry in games_module.GAMES
        ), "sanity: YuGiOh is genuinely absent from pipeline/games.py's own registry — "
           "this arm proves nothing if it is not", games_module.GAMES)

        yugioh_groups = _groups("Legend of Blue Eyes White Dragon")
        mirror_market = MirrorOnlyMarket(
            categories={"YuGiOh": 2}, groups_by_category={2: yugioh_groups},
        )
        gate_ledger = _FakeLedger({
            "ebay:gate": OrderRecord(
                source="ebay", number="gate", status="Open",
                lines=[
                    # A real tcgcsv category `games.py` does not track at all.
                    OrderLine(
                        sku="YU1", quantity=1, unit_price="10.00",
                        name="YuGiOh - Legend of Blue Eyes White Dragon: Blue-Eyes White "
                             "Dragon - Near Mint",
                    ),
                    # A product line the MIRROR itself has no category for either.
                    OrderLine(
                        sku="NO1", quantity=1, unit_price="5.00",
                        name="Digimon - Some Set: Some Card - Near Mint",
                    ),
                ],
            ),
        })
        gate_rows, gate_refusals = archive_walk._ledger_export_rows(
            gate_ledger, ["YU1", "NO1"], mirror_market
        )
        ok("YU1" in gate_rows,
           "a product line absent from games.py but present in the mirror RESOLVES — "
           "this is the D231 amendment: the mirror is the authority, not games.py",
           gate_rows)
        ok("NO1" in gate_refusals and "tcgcsv category list" in gate_refusals["NO1"],
           "a product line the mirror itself does not carry still refuses, with the "
           "mirror's own reason", gate_refusals)

        # MUTATION CHECK: put the old games.py gate back inline and confirm the YuGiOh
        # arm goes red — proves the fix, not the fixture, is what resolves it.
        def _old_gated_parse(name, groups):
            line = name.split(" - ", 1)[0].strip()
            catalogued_lines = frozenset(
                str(entry["product_line"]) for entry in games_module.GAMES
                if entry.get("product_line")
                and games_module.is_catalogued(str(entry["key"]))
            )
            if line not in catalogued_lines:
                raise archive_walk.UnresolvedLedgerName(
                    f"{line!r} is not a known, catalogued product line"
                )
            return archive_walk.parse_ledger_name(name, groups)

        try:
            _old_gated_parse(
                "YuGiOh - Legend of Blue Eyes White Dragon: Blue-Eyes White Dragon - "
                "Near Mint",
                yugioh_groups,
            )
            mutation_raised = False
        except archive_walk.UnresolvedLedgerName:
            mutation_raised = True
        ok(mutation_raised,
           "MUTATION: reinstating the old games.py gate makes the same YuGiOh line "
           "refuse again — confirms the fix above, and not the fixture, is what "
           "resolves it")

        # -------------------------------------------------------- pipeline: sweep (no network)
        print("\n-- pipeline/pricearchive.py: sweep, against a FakeMarket, both directions --")
        script = {
            "444": {
                "semiannual": _series("444", "semiannual", same_day, "3.00"),
                "annual": _series("444", "annual", same_day, "3.20"),
            },
        }
        market = FakeMarket(script)
        buckets, sources, refusals, _resolved = archive_walk.sweep(
            rows, market, ranges=("semiannual", "annual"), now=1_000,
        )
        ok(len(buckets) == 2,
           "one sku swept over two overlapping ranges -> two archived buckets", buckets)
        ok("555" in refusals,
           "a sku the market could not answer for is reported as a refusal, never dropped",
           refusals)
        ok(all(b.at == 1_000 for b in buckets.values()),
           "every bucket this pass wrote carries this pass's own clock")
        answered = {s.range: s.answered for s in sources}
        ok(answered.get("semiannual") == 1 and answered.get("annual") == 1,
           "the accounting counts one answered sku per range", answered)
        refused_count = {s.refused for s in sources}
        ok(refused_count == {1},
           "the accounting's refused count matches the refusal this pass actually saw",
           sources)

        # -------------------------------------------------------- end to end through Store
        print("\n-- end to end: sweep, then Store().write(), then a second sweep --")
        with Store().write() as snapshot:
            snapshot.archive.upsert(buckets)
            snapshot.archive.record_pass(sources)
        stored = dict(Store().read().archive.entries)
        ok(len(stored) == 2, "both buckets landed in the store, keyed by (sku, range, start)")

        # A second sweep over a store where "555" no longer resolves (its only source vanished
        # from the script) must not touch "444"'s already-archived buckets.
        market_narrower = FakeMarket({})
        buckets2, sources2, refusals2, _resolved2 = archive_walk.sweep(
            {"555": rows["555"]}, market_narrower, ranges=("month",), now=2_000,
        )
        ok(not buckets2, "a pass that resolves nothing writes nothing")
        with Store().write() as snapshot:
            snapshot.archive.upsert(buckets2)
            snapshot.archive.record_pass(sources2)
        after = dict(Store().read().archive.entries)
        ok(after == stored,
           "a later pass over a different, narrower selection never deletes what an earlier "
           "pass archived", after)

        # ---------------------------------- card row refuses -> retry the ledger's own row
        print("\n-- pipeline/pricearchive.py: sweep() retries the ledger row when the card "
              "row refuses (D233) --")

        class ResolvingMarket:
            """Resolves EXACTLY the way `pipeline/pricehistory.py:Market.readings_for_rows`
            does — real `ProductIndex.find` over real `join.number_index_key`/
            `name_index_key` — so a bare-number miss and a name-only ambiguity behave
            exactly as the real Market's would, no network, no `category_id`/`groups`
            (this arm feeds `Set Name` straight to the index, sidestepping that hop, which
            `ledger_subject_rows`'s own tests already cover)."""

            def __init__(self, products_by_set: Dict[str, list]):
                self._index_by_set = {
                    set_name: pricehistory.ProductIndex.build(products)
                    for set_name, products in products_by_set.items()
                }

            def readings_for_rows(self, rows, ranges=(), *, product_ids=None):
                readings = {}
                refusals = {}
                known = product_ids or {}
                for row in rows:
                    sku = row.get(tcgcsv_module.SKU_COLUMN, "")
                    verified = known.get(sku)
                    if verified:
                        readings[sku] = HistoryReading(
                            sku=sku, product_id=int(verified), series={}
                        )
                        continue
                    set_name = row.get(tcgcsv_module.SET_COLUMN, "")
                    index = self._index_by_set.get(set_name)
                    if index is None:
                        refusals[sku] = f"no tcgcsv group named {set_name!r}"
                        continue
                    product_id = index.find(
                        row.get(tcgcsv_module.NUMBER_COLUMN, ""),
                        row.get(tcgcsv_module.NAME_COLUMN, ""),
                    )
                    if product_id is None:
                        refusals[sku] = (
                            f"no single tcgcsv product matches "
                            f"{row.get(tcgcsv_module.NAME_COLUMN, '')!r} "
                            f"{row.get(tcgcsv_module.NUMBER_COLUMN, '')!r} in {set_name!r}"
                        )
                        continue
                    readings[sku] = HistoryReading(sku=sku, product_id=product_id, series={})
                return readings, refusals

        def _row(sku, name, number, set_name):
            return {
                tcgcsv_module.PRODUCT_LINE_COLUMN: "Pokemon",
                tcgcsv_module.SET_COLUMN: set_name,
                tcgcsv_module.NUMBER_COLUMN: number,
                tcgcsv_module.NAME_COLUMN: name,
                tcgcsv_module.SKU_COLUMN: sku,
                tcgcsv_module.CONDITION_COLUMN: "Near Mint",
            }

        # Real shape 1: a stored number with no denominator (`Bulbasaur` `001` in `ME01:
        # Mega Evolution`). The mirror carries `001/132` AND a `133/132` secret rare whose
        # NAME also folds to `BULBASAUR` (the number is embedded in the product's own
        # name, D35's `name_index_key`) — the bare `001` misses the number index outright
        # (`number_index_key("001")` is `"1"`, never `"1/132"`) and the name rung then
        # finds two, so the card row genuinely refuses on ambiguity. The mirror also
        # carries the SKU's own order line with the clean number, which resolves alone.
        me01_products = [
            {"productId": 501, "name": "Bulbasaur - 001/132",
             "extendedData": [{"name": "Number", "value": "001/132"}]},
            {"productId": 502, "name": "Bulbasaur - 133/132",
             "extendedData": [{"name": "Number", "value": "133/132"}]},
        ]
        # Real shape 2: a BLANK stored number whose name does not fold to the mirror's own
        # name (`Twisted Fate` in `Origins`, stored with no number at all — an identification
        # that read the name but missed the number). The mirror's own product name carries the
        # printing (`Twisted Fate, Gambler`), which `join.name_index_key` does not fold to
        # `TWISTED FATE` (that fold only strips a trailing `- <number>/<total>`, never a
        # comma-joined suffix), so neither the number rung (nothing to key on) nor the name
        # rung matches the card row's own cells — a genuinely unrepairable-by-shape miss,
        # unlike a glued set code, which `ProductIndex.find`'s own repair step now resolves
        # without any fallback at all (see the direct-resolution arm below).
        origins_products = [
            {"productId": 601, "name": "Twisted Fate, Gambler",
             "extendedData": [{"name": "Number", "value": "200/298"}]},
        ]
        resolving_market = ResolvingMarket({
            "ME01: Mega Evolution": me01_products,
            "Origins": origins_products,
        })

        card_rows = {
            "SKU-A": _row("SKU-A", "Bulbasaur", "001", "ME01: Mega Evolution"),
            "SKU-B": _row(
                "SKU-B", "Twisted Fate", "", "Origins",
            ),
        }
        fallback_rows_fixture = {
            "SKU-A": _row("SKU-A", "Bulbasaur", "001/132", "ME01: Mega Evolution"),
            "SKU-B": _row(
                "SKU-B", "Twisted Fate, Gambler", "200/298", "Origins",
            ),
        }

        # Baseline: with NO fallback offered, both real shapes refuse — proves the fixture
        # itself reproduces the two measured refusals before any fallback logic runs.
        _b, _s, no_fallback_refusals, no_fallback_resolved = archive_walk.sweep(
            card_rows, resolving_market, ranges=("month",), now=1,
        )
        ok(set(no_fallback_refusals) == {"SKU-A", "SKU-B"},
           "with no fallback row offered, the bare-number and the blank-number/name-mismatch "
           "card rows both refuse, exactly as measured on the real store",
           no_fallback_refusals)
        ok(not no_fallback_resolved, "and nothing is reported as fallback-resolved")

        # A DIRECT-RESOLUTION ARM, NOT A FALLBACK ONE (D234): a
        # glued-on set code (`OGN • 200/298`) is repaired by `ProductIndex.find` itself,
        # from the card row alone, with no ledger fallback offered at all — the mechanism
        # this task adds, proven distinct from D233's own fallback.
        glued_row = {
            "SKU-B": _row("SKU-B", "Twisted Fate", "OGN • 200/298", "Origins"),
        }
        _bg, _sg, glued_refusals, _glued_resolved = archive_walk.sweep(
            glued_row, resolving_market, ranges=("month",), now=1,
        )
        ok(not glued_refusals,
           "a glued-on set code resolves straight off the card row, no fallback needed — "
           "`strip_set_code` is reached on a number-index miss before the name rung",
           glued_refusals)

        # The fallback fires: both retry rows are the mirror's own clean cells.
        _b2, _s2, with_fallback_refusals, with_fallback_resolved = archive_walk.sweep(
            card_rows, resolving_market, ranges=("month",), now=1,
            fallback_rows=fallback_rows_fixture,
        )
        ok(not with_fallback_refusals,
           "with the ledger's own row offered as a fallback, both real shapes resolve — "
           "the bare `001` against a mirror holding `001/132`/`133/132`, and the "
           "blank-number/name-mismatch row", with_fallback_refusals)
        ok(set(with_fallback_resolved) == {"SKU-A", "SKU-B"},
           "sweep() reports which SKUs answered via the fallback, so a reader can see "
           "when it fired", with_fallback_resolved)

        # A SKU with a fallback row that ALSO cannot resolve is still a refusal.
        unresolvable_fallback = {
            "SKU-A": _row("SKU-A", "Nobody Here", "999/999", "ME01: Mega Evolution"),
        }
        _b3, _s3, still_refused, still_resolved = archive_walk.sweep(
            {"SKU-A": card_rows["SKU-A"]}, resolving_market, ranges=("month",), now=1,
            fallback_rows=unresolvable_fallback,
        )
        ok("SKU-A" in still_refused and "SKU-A" not in still_resolved,
           "a SKU whose fallback row ALSO fails to resolve is still named as a refusal, "
           "never silently dropped", still_refused)

        # MUTATION CHECK: remove the fallback (call `sweep()` with none) and confirm the
        # two arms this fallback exists for go back to refusing — the guard is trusted
        # only once it is seen to fail on the defect it guards.
        _b4, _s4, mutated_refusals, mutated_resolved = archive_walk.sweep(
            card_rows, resolving_market, ranges=("month",), now=1, fallback_rows=None,
        )
        ok(set(mutated_refusals) == {"SKU-A", "SKU-B"} and not mutated_resolved,
           "MUTATION: with the fallback removed, both real shapes go back to refusing — "
           "proves the fix above, rather than the fixture, is what resolves them",
           mutated_refusals)

        # ---------------------- resolve by the SKU, never by the card's own read fields
        # (D-pricehistory-resolves-by-sku, owner's ruling 2026-09-23, replacing a session's
        # earlier attempt to weigh a card's read name against the number it found). The
        # reviewer's re-measurement found 15 of 20 new refusals from that attempt had a
        # CORRECT old answer, and 1 of 29 flips was WRONG — a Riftbound "Champion, Title"
        # card's READ name is the unreliable field, so the fix is to never ask the card at
        # all: resolve by the SKU, either the archive's own already-verified productId or
        # the SKU's own row in the store's cached Filtered Export.
        print("\n-- pipeline/pricearchive.py: resolve_by_sku (D-pricehistory-resolves-by-sku) --")

        card_row_misread = _row("SKU-M", "Totally Wrong Name", "misread-number", "Origins")
        export_row_correct = _row("SKU-M", "Twisted Fate, Gambler", "200/298", "Origins")

        # (a) an archive-verified productId wins outright — the row is never even looked at.
        resolved_rows_a, verified_a, tiers_a = archive_walk.resolve_by_sku(
            {"SKU-M": card_row_misread},
            archive=_FakeArchiveForSku({"SKU-M": 601}),
        )
        ok(verified_a.get("SKU-M") == 601 and tiers_a["SKU-M"] == archive_walk.TIER_ARCHIVE,
           "tier (a): an archive-verified productId answers before anything else is asked",
           (resolved_rows_a, verified_a, tiers_a))

        # (b) no archive answer, but the SKU has its own row in the cached export — THAT
        # row is what gets resolved with, never the card's misread one.
        resolved_rows_b, verified_b, tiers_b = archive_walk.resolve_by_sku(
            {"SKU-M": card_row_misread},
            archive=_FakeArchiveForSku({}),
            export_rows={"SKU-M": export_row_correct},
        )
        ok(not verified_b and tiers_b["SKU-M"] == archive_walk.TIER_EXPORT
           and resolved_rows_b["SKU-M"] is export_row_correct,
           "tier (b): the SKU's own export row is substituted for the card's misread one",
           (resolved_rows_b, tiers_b))

        # (c) neither answers — today's behaviour, the card's own row, unchanged.
        resolved_rows_c, verified_c, tiers_c = archive_walk.resolve_by_sku(
            {"SKU-M": card_row_misread}, archive=_FakeArchiveForSku({}), export_rows={},
        )
        ok(not verified_c and tiers_c["SKU-M"] == archive_walk.TIER_CARD
           and resolved_rows_c["SKU-M"] is card_row_misread,
           "tier (c): neither the archive nor the export answers — falls back to the "
           "card's own row exactly as sweep() always resolved it",
           (resolved_rows_c, tiers_c))

        # MUTATION GUARD: with NO archive and NO export_rows at all (the function's two
        # defaults), every SKU is tier (c) and the row handed back IS the input row,
        # object-identical — `resolve_by_sku`'s own claim to be `sweep`'s unchanged
        # pre-2026-09-23 shape when given nothing new to work with.
        default_rows, default_verified, default_tiers = archive_walk.resolve_by_sku(
            {"SKU-M": card_row_misread},
        )
        ok(not default_verified and default_tiers["SKU-M"] == archive_walk.TIER_CARD
           and default_rows["SKU-M"] is card_row_misread,
           "MUTATION GUARD: no archive, no export_rows — every SKU still falls to tier (c)",
           default_tiers)

        # ---- end to end through sweep(): the misread card row would resolve WRONG on its
        # own (ResolvingMarket's real ProductIndex.find, fed the misread name/number), but
        # an export row for the same SKU resolves it CORRECTLY once sweep() prefers it.
        origins_products_for_sku_test = {"Origins": origins_products}
        sku_test_market = ResolvingMarket(origins_products_for_sku_test)
        _b5, _s5, refusals5, _resolved5 = archive_walk.sweep(
            {"SKU-M": card_row_misread}, sku_test_market, ranges=("month",), now=1,
        )
        ok("SKU-M" in refusals5,
           "BASELINE: the misread card row alone cannot resolve — proves the fixture is a "
           "genuine misread and not a shape ProductIndex.find would have fixed anyway",
           refusals5)
        _b6, _s6, refusals6, _resolved6 = archive_walk.sweep(
            {"SKU-M": card_row_misread}, sku_test_market, ranges=("month",), now=1,
            export_rows={"SKU-M": export_row_correct},
        )
        ok(not refusals6,
           "a SKU with a misread stored name still resolves to its own product once "
           "sweep() is given the store's cached export — tier (b), through the real "
           "ProductIndex.find over the export's own trustworthy row",
           refusals6)

        # ---- end to end through sweep(): an archive-verified productId wins outright, even
        # over a market that would REFUSE the row it is never asked to resolve.
        class _RefusingMarket:
            """`readings_for_rows` refuses every row it is asked to resolve directly, and
            answers a `product_ids`-verified SKU without looking at its row at all — proof
            that tier (a) is reached without `product_id_for_row`-shaped resolution ever
            running, not merely proof it happens to answer the same id."""

            def readings_for_rows(self, rows, ranges=(), *, product_ids=None):
                known = product_ids or {}
                readings, refusals = {}, {}
                for row in rows:
                    sku = row.get(tcgcsv_module.SKU_COLUMN, "")
                    verified = known.get(sku)
                    if verified:
                        readings[sku] = HistoryReading(
                            sku=sku, product_id=int(verified), series={}
                        )
                    else:
                        refusals[sku] = "MUTATION TRAP: resolved a row tier (a) should skip"
                return readings, refusals

        _b7, _s7, refusals7, _resolved7 = archive_walk.sweep(
            {"SKU-M": card_row_misread}, _RefusingMarket(), ranges=("month",), now=1,
            archive=_FakeArchiveForSku({"SKU-M": 601}),
        )
        ok(not refusals7,
           "an archive-verified productId (tier (a)) resolves through sweep() even against "
           "a market that refuses every row it is actually asked to resolve",
           refusals7)

        # MUTATION GUARD: the SAME market, the SAME SKU, with NO archive offered — the trap
        # fires, proving the guard above is real and not a market that always answers.
        _b8, _s8, refusals8, _resolved8 = archive_walk.sweep(
            {"SKU-M": card_row_misread}, _RefusingMarket(), ranges=("month",), now=1,
        )
        ok("SKU-M" in refusals8 and "MUTATION TRAP" in refusals8["SKU-M"],
           "MUTATION GUARD: with no archive at all, the same market refuses the same "
           "SKU — proves tier (a)'s skip is conditional on a real verified id, not a "
           "market that always answers",
           refusals8)

        # ---------------------------------------- merged_export_rows_by_sku, on real bytes
        print("\n-- pipeline/pricearchive.py: merged_export_rows_by_sku, real files on disk --")
        export_home = Path(tempfile.mkdtemp(prefix="pricearchive-selftest-exports-"))
        previous_home = os.environ.get(files.HOME_ENV)
        os.environ[files.HOME_ENV] = str(export_home)
        try:
            exports_dir = export_home / "inventory" / ".exports" / "riftbound"
            exports_dir.mkdir(parents=True)
            csv_text = (
                "TCGplayer Id,Product Line,Set Name,Product Name,Number,Rarity,Condition,"
                "TCG Market Price,TCG Direct Low,TCG Low Price With Shipping,TCG Low Price,"
                "Total Quantity,Add to Quantity,TCG Marketplace Price,Photo URL\n"
                '"7654321","Riftbound League of Legends Trading Card Game","Origins",'
                '"Twisted Fate, Gambler","200/298","Rare","Near Mint","5.00","","","",'
                '"1","0","",""\n'
            )
            (exports_dir / "export-tcgplayer-20260101-000000-aaaaaaaa.csv").write_text(
                csv_text, "utf-8"
            )
            merged = archive_walk.merged_export_rows_by_sku()
            ok(
                merged.get("7654321", {}).get(tcgcsv_module.NAME_COLUMN)
                == "Twisted Fate, Gambler",
                "a real cached export file, merged by SKU, answers the SKU's own "
                "Product Name — read off disk, no network",
                merged.get("7654321"),
            )
            ok(
                "0000000" not in merged,
                "a SKU never written to any cached export is simply absent, never "
                "guessed at",
            )
        finally:
            if previous_home is None:
                os.environ.pop(files.HOME_ENV, None)
            else:
                os.environ[files.HOME_ENV] = previous_home
            shutil.rmtree(export_home, ignore_errors=True)

        # MUTATION GUARD: no `.exports` directory at all on disk answers an empty map,
        # never an exception — the function's own stated fail-open shape.
        no_exports_home = Path(tempfile.mkdtemp(prefix="pricearchive-selftest-noexports-"))
        previous_home = os.environ.get(files.HOME_ENV)
        os.environ[files.HOME_ENV] = str(no_exports_home)
        try:
            ok(archive_walk.merged_export_rows_by_sku() == {},
               "MUTATION GUARD: no inventory/.exports/ directory at all answers an empty "
               "map rather than raising")
        finally:
            if previous_home is None:
                os.environ.pop(files.HOME_ENV, None)
            else:
                os.environ[files.HOME_ENV] = previous_home
            shutil.rmtree(no_exports_home, ignore_errors=True)

        # ------------------------------------------ every refusal reaches the output
        print("\n-- pipeline/pricearchive.py: format_refusals never truncates --")
        many_refusals = {f"SKU{i:03d}": "a manufactured refusal reason" for i in range(37)}
        formatted = archive_walk.format_refusals(many_refusals)
        joined_lines = "\n".join(formatted)
        ok(all(sku in joined_lines for sku in many_refusals),
           "every one of 37 refused skus appears in the formatted output — none truncated "
           "and no '... and N more' tail", formatted[:3])
        ok(not any("more" in line and "..." in line for line in formatted),
           "no truncating tail line is ever produced")
        two_reasons = dict(many_refusals)
        two_reasons["SKU999"] = "a different, rarer reason"
        formatted_grouped = archive_walk.format_refusals(two_reasons)
        ok(formatted_grouped[0].startswith("37 sku(s):"),
           "grouped output leads with the LARGEST reason group first", formatted_grouped[0])
        ok(any(line.startswith("1 sku(s): a different") for line in formatted_grouped),
           "a lone, different reason still gets its own named group, never folded into "
           "the majority's", formatted_grouped)

        # ---------------------------------------------------- ranking: sold value first
        print("\n-- pipeline/pricearchive.py: revenue_by_sku and rank_by_revenue "
              "(D223) --")
        with Store().write() as snapshot:
            # "444" sells for $10.00 once (a real reading). "555" never sells (already
            # sold=state above, but no ORDER line — on-hand-or-sold is not the same fact as
            # earned revenue). "666" has a CANCELED order and must count as zero.
            snapshot.ledger.orders["ebay:1"] = OrderRecord(
                source="ebay", number="1", status="Open",
                lines=[OrderLine(sku="444", quantity=2, unit_price="5.00")],
            )
            snapshot.ledger.orders["ebay:2"] = OrderRecord(
                source="ebay", number="2", status="Canceled",
                lines=[OrderLine(sku="666", quantity=9, unit_price="99.00")],
            )
        revenue = archive_walk.revenue_by_sku(Store().read().ledger)
        ok(revenue.get("444") == Decimal("10.00"),
           "gross is unit_price * quantity, summed across lines", revenue)
        ok("666" not in revenue,
           "a CANCELED order contributes nothing — app/src/Revenue.tsx's own rule", revenue)
        ok("555" not in revenue,
           "a sku nobody has ever ordered earns nothing, whether or not it is on hand",
           revenue)

        ranked = archive_walk.rank_by_revenue(["555", "444", "999"], revenue)
        ok(ranked == ["444", "555", "999"],
           "sold value first; ties (both zero) break on the sku string", ranked)

        ranked_rows = archive_walk.rows_from_store(Store().read())
        ok(list(ranked_rows)[0] == "444",
           "rows_from_store itself walks sold-value-first, with no second sort needed by "
           "its caller", list(ranked_rows))

        # -------------------------------------- resuming: freshness (D224)
        print("\n-- pipeline/pricearchive.py: freshness_index and split_by_freshness --")
        existing = [
            Bucket(sku="AAA", product_id=1, range="month", width_days=1, start="2026-01-01",
                   market="1.00", quantity=1, transactions=1, low="1.00", high="1.00", at=990),
            Bucket(sku="AAA", product_id=1, range="annual", width_days=7, start="2026-01-01",
                   market="1.00", quantity=1, transactions=1, low="1.00", high="1.00", at=990),
            # "BBB" was read for month only — annual is MISSING, so BBB is not fresh.
            Bucket(sku="BBB", product_id=2, range="month", width_days=1, start="2026-01-01",
                   market="2.00", quantity=1, transactions=1, low="2.00", high="2.00", at=990),
            # "CCC" was read for both, but long enough ago to have aged out of the TTL.
            Bucket(sku="CCC", product_id=3, range="month", width_days=1, start="2026-01-01",
                   market="3.00", quantity=1, transactions=1, low="3.00", high="3.00", at=100),
            Bucket(sku="CCC", product_id=3, range="annual", width_days=7, start="2026-01-01",
                   market="3.00", quantity=1, transactions=1, low="3.00", high="3.00", at=100),
        ]
        index = archive_walk.freshness_index(existing)
        rows_for_resume = {sku: {} for sku in ("AAA", "BBB", "CCC", "DDD")}
        needs, fresh = archive_walk.split_by_freshness(
            rows_for_resume, index, ranges=("month", "annual"), now=1_000, ttl_seconds=100,
        )
        ok(fresh == ["AAA"],
           "only the sku fresh in EVERY requested range is skipped", fresh)
        ok(set(needs) == {"BBB", "CCC", "DDD"},
           "one stale or missing range sends the whole sku back — BBB (missing annual), "
           "CCC (aged past the ttl) and DDD (never read) all need a fetch", needs)
        ok(list(needs) == ["BBB", "CCC", "DDD"],
           "order is preserved from the caller's own ranking, not re-sorted here", needs)

        # -------------------------------------------------------------- chunk_rows
        # ------------------------------------------- resume window (D230)
        print("\n-- pipeline/pricearchive.py: RESUME_TTL_SECONDS, mutation-tested --")
        five_hours_ago = 100_000 - 5 * 3600
        resume_window_existing = [
            Bucket(sku="RRR", product_id=9, range="month", width_days=1,
                   start="2026-01-01", market="1.00", quantity=1, transactions=1,
                   low="1.00", high="1.00", at=five_hours_ago),
        ]
        resume_window_index = archive_walk.freshness_index(resume_window_existing)
        resume_window_rows = {"RRR": {}}

        # THE MUTATION: at the OLD window (`pipeline/pricehistory.py:HISTORY_TTL_SECONDS`,
        # one hour), a SKU read 5 hours ago is stale and goes back to be re-read — this IS
        # the defect this constant fixes, proven to fail before the fix is proven to work.
        needs_old, fresh_old = archive_walk.split_by_freshness(
            resume_window_rows, resume_window_index, ranges=("month",), now=100_000,
            ttl_seconds=pricehistory.HISTORY_TTL_SECONDS,
        )
        ok(fresh_old == [] and list(needs_old) == ["RRR"],
           "mutation check: at the OLD one-hour window, a sku read 5 hours ago is stale "
           "and is sent back to be re-read", (needs_old, fresh_old))

        needs_new, fresh_new = archive_walk.split_by_freshness(
            resume_window_rows, resume_window_index, ranges=("month",), now=100_000,
            ttl_seconds=archive_walk.RESUME_TTL_SECONDS,
        )
        ok(fresh_new == ["RRR"] and not needs_new,
           "at the NEW six-day window, the same sku read 5 hours ago is fresh and is "
           "skipped — a weekly press advances instead of restarting from the top",
           (needs_new, fresh_new))

        # A sku read outside even the new, wider window still needs a fresh read.
        seven_days_ago = 100_000 - 7 * 24 * 3600
        stale_beyond_new_window = archive_walk.freshness_index([
            Bucket(sku="SSS", product_id=9, range="month", width_days=1,
                   start="2026-01-01", market="1.00", quantity=1, transactions=1,
                   low="1.00", high="1.00", at=seven_days_ago),
        ])
        needs_stale, fresh_stale = archive_walk.split_by_freshness(
            {"SSS": {}}, stale_beyond_new_window, ranges=("month",), now=100_000,
            ttl_seconds=archive_walk.RESUME_TTL_SECONDS,
        )
        ok(fresh_stale == [] and list(needs_stale) == ["SSS"],
           "a sku read 7 days ago is stale even under the new, wider window", needs_stale)

        # The printed window string, at the actual multi-day value this constant holds —
        # `cli/cmd_pricearchive.py:_format_window` must never print "8640 minute(s)".
        from cli import cmd_pricearchive as cmd_module  # noqa: E402
        ok(cmd_module._format_window(archive_walk.RESUME_TTL_SECONDS) == "6 day(s)",
           "the resume window prints as days, never a four-figure minute count",
           cmd_module._format_window(archive_walk.RESUME_TTL_SECONDS))
        ok(cmd_module._format_window(pricehistory.HISTORY_TTL_SECONDS) == "1 hour(s)",
           "the live-screen ttl still prints in its own honest unit",
           cmd_module._format_window(pricehistory.HISTORY_TTL_SECONDS))

        print("\n-- pipeline/pricearchive.py: chunk_rows preserves order --")
        five = {str(i): {} for i in range(5)}
        chunks = archive_walk.chunk_rows(five, 2)
        ok([list(c) for c in chunks] == [["0", "1"], ["2", "3"], ["4"]],
           "chunks are ordered pieces, never re-sorted", chunks)

        # ------------------------------------------------- pacing (D222)
        print("\n-- pipeline/pricearchive.py: classify_refusals and measured_pace --")
        blocked_message = (
            "https://infinite-api.tcgplayer.com/price/history/652771/detailed?range=month "
            "answered HTTP 403. That is either an authorization change at the host or its "
            "own defenses declining this client by its request signature — set "
            "PKMNSCAN_TCG_USER_AGENT in .env to the User-Agent your browser sends and try "
            "again."
        )
        refusals_in = {"652771": blocked_message, "other": "not in the script"}

        # THE GUARD, PROVEN TO FAIL WITHOUT THE FIX FIRST: with no evidence of an earlier
        # success, the message is left exactly as `Blocked` phrased it — still pointing at
        # the User-Agent, which is the WRONG remedy once a run has actually throttled.
        unchanged, blocked_count = archive_walk.classify_refusals(
            refusals_in, had_earlier_success=False
        )
        ok(unchanged["652771"] == blocked_message,
           "with no earlier success this pass, a 403 is left exactly as Blocked phrased it "
           "— this function has no evidence yet to call it a throttle", unchanged)
        ok(blocked_count == 1, "exactly one refusal carried the 403 signature", blocked_count)

        # NOW THE FIX: after this pass has already read something successfully, the SAME
        # message is rewritten, and it never repeats the disproved remedy.
        rewritten, blocked_count2 = archive_walk.classify_refusals(
            refusals_in, had_earlier_success=True
        )
        ok("PKMNSCAN_TCG_USER_AGENT" not in rewritten["652771"],
           "after an earlier success this pass, the rewritten message never repeats the "
           "remedy this pass has already disproved", rewritten)
        ok("throttle" in rewritten["652771"].lower(),
           "the rewritten message names what it actually is", rewritten)
        ok(rewritten["other"] == "not in the script",
           "a refusal that never carried the 403 signature is left untouched", rewritten)
        ok(blocked_count2 == 1, "the blocked count is unchanged by the rewrite", blocked_count2)

        ok(archive_walk.measured_pace(0, 0) == archive_walk.DEFAULT_COURTESY_DELAY_SECONDS,
           "no requests measured yet -> the naive default, never a divide-by-zero")
        paced = archive_walk.measured_pace(requests_made=800, elapsed_seconds=80)
        ok(paced == 0.2,
           "800 requests survived over 80s -> 0.1s/request observed, doubled by the "
           "backoff factor -> 0.2s", paced)
        floor_paced = archive_walk.measured_pace(requests_made=1000, elapsed_seconds=1)
        ok(floor_paced == archive_walk.DEFAULT_COURTESY_DELAY_SECONDS,
           "a rate faster than the naive default never paces BELOW it", floor_paced)

        pace_path = home / "throttle-pace.json"
        ok(archive_walk.load_pace(pace_path) == archive_walk.DEFAULT_COURTESY_DELAY_SECONDS,
           "no measurement on disk yet -> the naive default")
        archive_walk.save_pace(
            pace_path, 0.42, requests_made=800, elapsed_seconds=80, at=1_000,
        )
        ok(archive_walk.load_pace(pace_path) == 0.42,
           "a saved measurement is what the next press starts from")
        pace_path.write_text("not json", "utf-8")
        ok(archive_walk.load_pace(pace_path) == archive_walk.DEFAULT_COURTESY_DELAY_SECONDS,
           "a corrupt measurement file is a cache miss, never a refusal — `Market._cached`'s "
           "own rule, applied here")

        # ---------------------------------------- end to end: an interrupted sweep, resumed
        print("\n-- end to end: an interrupted sweep commits what it already read, and a "
              "resumed sweep does not re-fetch it --")
        interrupt_rows = {sku: {"TCGplayer Id": sku} for sku in ("R1", "R2", "R3")}
        script = {
            sku: {"month": _series(sku, "month", same_day, "1.00")}
            for sku in interrupt_rows
        }

        # THE GUARD, PROVEN TO FAIL FIRST: the OLD shape (one `sweep()` call over every row,
        # written once at the end) loses EVERYTHING when the connection drops partway —
        # nothing is committed because nothing was ever written before the raise.
        os.environ[files.HOME_ENV] = str(Path(tempfile.mkdtemp(prefix="pricearchive-old-")))
        try:
            with Store().write() as snapshot:
                pass  # establish an empty store to read back against
            one_shot_market = RecordingMarket(script, raise_on={"R2"})
            raised = False
            try:
                archive_walk.sweep(interrupt_rows, one_shot_market, ranges=("month",))
            except RuntimeError:
                raised = True
            ok(raised, "the one-shot call really does raise on the dropped sku")
            after_old = dict(Store().read().archive.entries)
            ok(after_old == {},
               "the OLD one-transaction-at-the-end shape has nothing to commit when the "
               "call that would have produced it never returned — this is the bug "
               "D224's chunking fixes", after_old)
        finally:
            shutil.rmtree(os.environ[files.HOME_ENV], ignore_errors=True)
            os.environ[files.HOME_ENV] = str(home)

        # THE FIX: chunked, one commit per chunk. R1 lands before R2's chunk raises; R3 is
        # never even reached this pass.
        chunked_market = RecordingMarket(script, raise_on={"R2"})
        chunks_of_one = archive_walk.chunk_rows(interrupt_rows, 1)
        interrupted_at = None
        for idx, chunk in enumerate(chunks_of_one):
            try:
                b, s, r, _r_ = archive_walk.sweep(chunk, chunked_market, ranges=("month",))
            except RuntimeError:
                interrupted_at = idx
                break
            with Store().write() as snapshot:
                snapshot.archive.upsert(b)
        ok(interrupted_at == 1, "the second chunk (R2) is where the drop happens", interrupted_at)
        survived = dict(Store().read().archive.entries)
        ok(any(b.sku == "R1" for b in survived.values()) and
           not any(b.sku in ("R2", "R3") for b in survived.values()),
           "R1's chunk committed before the drop; R2 and R3 never landed", survived)
        ok("R3" not in chunked_market.asked,
           "the pass stopped at the drop rather than pressing on past it", chunked_market.asked)

        # THE RESUME: a fresh pass re-reads the store, sees R1 already fresh, and never asks
        # the market about it again — only R2 and R3 are sent.
        resume_index = archive_walk.freshness_index(
            Store().read().archive.entries.values()
        )
        resume_needs, resume_fresh = archive_walk.split_by_freshness(
            interrupt_rows, resume_index, ranges=("month",), now=100_000, ttl_seconds=3_600,
        )
        ok(resume_fresh == ["R1"], "R1 is skipped on resume — it is already archived", resume_fresh)
        ok(set(resume_needs) == {"R2", "R3"},
           "R2 and R3 still need a read", resume_needs)

        resume_market = RecordingMarket(script)
        for chunk in archive_walk.chunk_rows(resume_needs, 1):
            b, s, r, _r_ = archive_walk.sweep(chunk, resume_market, ranges=("month",))
            with Store().write() as snapshot:
                snapshot.archive.upsert(b)
        ok("R1" not in resume_market.asked,
           "the resumed pass never asks the market about a sku the archive already holds "
           "fresh from this same pass", resume_market.asked)
        ok({"R2", "R3"} <= resume_market.asked,
           "the resumed pass does read what it still owes", resume_market.asked)
        final_skus = {b.sku for b in Store().read().archive.entries.values()}
        ok({"R1", "R2", "R3"} <= final_skus,
           "after the resume, every subject from this pass is archived exactly once",
           final_skus)
    finally:
        if previous is None:
            os.environ.pop(files.HOME_ENV, None)
        else:
            os.environ[files.HOME_ENV] = previous
        shutil.rmtree(home, ignore_errors=True)

    print("\nprice-history archive self-test: {0} passed{1}".format(
        PASS, ", {0} FAILED".format(FAIL) if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
