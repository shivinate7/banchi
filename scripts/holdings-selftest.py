#!/usr/bin/env python3
"""`pipeline/holdings.py`, proved against fixtures built in this file
(`D236`).

NO STORE ON DISK. NO NETWORK. Every fixture below is a plain `Inventory`, `PriceArchive` or
`Ledger` built in memory — the same dataclasses `store/session.py:Snapshot` carries, never a
throwaway sqlite file. `pipeline/holdings.py` takes exactly these three objects and nothing
else, so a test can build them directly.

TWO MUTATION ARMS ARE INCLUDED, ON `CLAUDE.md`'s OWN RULE: A GUARD IS TRUSTED ONLY ONCE IT
HAS BEEN SEEN TO FAIL ON THE DEFECT IT GUARDS. Both defeat the guard by monkeypatching the
one line that matters, run the same assertion, and require it to go red. If either one
passes instead, this script exits non-zero and says so.

PATH GATED, THE EIGHTEENTH (D247, owner's word 2026-09-23, on the same ground as
`pricearchive-selftest`'s sixteenth entry): `make holdings-selftest`, wired into `make check`
and `make ci-check` through `scripts/guard-scope.py`. This file is no longer the exception it
was when written — the sentence that used to sit here ("no caller reachable from a screen
yet") described a state D250 already ended: `GET /pipeline/holdings-value`
(`server/pipeline_routes.py:do_pipeline_holdings_value`) is called by `app/src/Revenue.tsx`'s
`getHoldingsValue`, wired to `#/revenue`'s "Value my stock" panel. Once it's done, it only
needs to be tested when touched.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import holdings  # noqa: E402
from store.master import CAPTURED, SOLD, Card, Inventory, position_key  # noqa: E402
from store.orders import Ledger, OrderLine, OrderRecord  # noqa: E402
from store.pricearchive import Bucket, PriceArchive  # noqa: E402

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
            print(f"         {detail}")


def _card(box: int, index: int, sku: str, name: str, state: str = CAPTURED) -> Card:
    return Card(box=box, index=index, sku=sku, name=name, state=state)


def _bucket(sku: str, range_: str, width: int, start: str, market) -> Bucket:
    return Bucket(
        sku=sku, product_id=1, range=range_, width_days=width, start=start,
        market=market, quantity=1, transactions=1, low=market, high=market, at=0,
    )


def base_fixture():
    """One on-hand SKU with a clean two-day `month` series, one on-hand SKU with no
    archived reading at all, and one sealed SKU (a ledger line naming a SKU the `cards`
    table never carries)."""
    inventory = Inventory()
    inventory.cards[position_key(1, 1)] = _card(1, 1, "PRICED1", "Vilemaw")
    inventory.cards[position_key(1, 2)] = _card(1, 2, "PRICED1", "Vilemaw")
    inventory.cards[position_key(1, 3)] = _card(1, 3, "UNPRICED1", "Moonfall")
    # A SOLD copy of a third SKU — proves TERMINAL_STATES is honored, never counted on hand.
    inventory.cards[position_key(1, 4)] = _card(1, 4, "SOLD1", "Gone", state=SOLD)

    archive = PriceArchive()
    archive.upsert({
        "PRICED1:month:2026-08-01": _bucket("PRICED1", "month", 1, "2026-08-01", "10.00"),
        "PRICED1:month:2026-08-02": _bucket("PRICED1", "month", 1, "2026-08-02", "12.00"),
    })

    ledger = Ledger()
    ledger.orders["order-1"] = OrderRecord(
        source="tcgplayer", number="1001", status="Shipped",
        lines=[OrderLine(sku="SEALED1", quantity=1, name="Booster Box")],
    )
    return inventory, archive, ledger


def test_quantity_and_state() -> None:
    inventory, _archive, _ledger = base_fixture()
    quantities = holdings.on_hand_quantities(inventory)
    ok(quantities.get("PRICED1") == 2, "two on-hand copies of PRICED1 counted",
       str(quantities))
    ok("SOLD1" not in quantities, "a SOLD copy is never counted on hand", str(quantities))


def test_name_with_reading() -> None:
    inventory, archive, ledger = base_fixture()
    report = holdings.build_holdings_report(inventory, archive, ledger, "month", now="2026-01-01T00:00:00+00:00")
    series = {s.sku: s for s in report.series}
    ok("PRICED1" in series, "a name with a reading produces a series")
    points = series["PRICED1"].points
    ok(len(points) == 2, "both archived buckets became points", str(points))
    ok(points[0].value == "20.00", "day 1 value is market times quantity (10.00 * 2)",
       str(points[0]))
    ok(points[1].value == "24.00", "day 2 value is market times quantity (12.00 * 2)",
       str(points[1]))
    ok(points[0].gap_before is False, "the first point never carries a gap")
    ok(points[1].gap_before is False, "two adjacent days carry no gap")


def test_name_with_no_reading() -> None:
    inventory, archive, ledger = base_fixture()
    report = holdings.build_holdings_report(inventory, archive, ledger, "month", now="2026-01-01T00:00:00+00:00")
    skus = {s.sku for s in report.series}
    ok("UNPRICED1" not in skus, "an unpriced name draws no series row")
    ok(report.unmarked_count == 1, "the unpriced name is counted, never a zero",
       str(report.unmarked_count))


def test_range_gap_breaks_the_line() -> None:
    inventory = Inventory()
    inventory.cards[position_key(1, 1)] = _card(1, 1, "GAP1", "Trophy Hunter")
    archive = PriceArchive()
    archive.upsert({
        "GAP1:month:2026-08-01": _bucket("GAP1", "month", 1, "2026-08-01", "5.00"),
        "GAP1:month:2026-08-02": _bucket("GAP1", "month", 1, "2026-08-02", "6.00"),
        # 2026-08-03 and 2026-08-04 were never swept — a genuine missing bucket, not a
        # priced-None row. The next point is 08-05.
        "GAP1:month:2026-08-05": _bucket("GAP1", "month", 1, "2026-08-05", "9.00"),
    })
    ledger = Ledger()
    report = holdings.build_holdings_report(inventory, archive, ledger, "month", now="2026-01-01T00:00:00+00:00")
    points = report.series[0].points
    ok(len(points) == 3, "all three archived points are carried, never dropped",
       str(points))
    ok(points[0].gap_before is False, "the first point carries no gap")
    ok(points[1].gap_before is False, "08-01 -> 08-02 is adjacent, no gap")
    ok(points[2].gap_before is True, "08-02 -> 08-05 skips two days: the line must break",
       str(points[2]))
    # THE VALUE IS NOT SYNTHESIZED. No point stands in for 08-03 or 08-04, and the point
    # after the gap keeps its own, real value rather than one interpolated toward it.
    ok(points[2].value == "9.00", "the point after a gap keeps its own real value, not an "
       "interpolated one", str(points[2]))
    totals = report.totals
    ok(len(totals) == 3, "the aggregate total carries all three dates", str(totals))
    ok(totals[2].gap_before is True, "the aggregate total's own gap lines up with the "
       "series gap", str(totals[2]))


def test_priced_none_bucket_carries_no_value() -> None:
    """A bucket the source answered with NO price (D159's no-reading shape, stored as
    `market=None`) keeps its own row, at its own real calendar date, and carries no value —
    it never stands in for a zero and never gets skipped as though the archive had not
    reached that day at all. `gap_before` is a CALENDAR test, not a price test: a
    priced-None day that sits exactly one bucket-width from its neighbor is calendar-
    adjacent, so it carries no gap either side — the missing PRICE, not a missing DAY."""
    inventory = Inventory()
    inventory.cards[position_key(1, 1)] = _card(1, 1, "NONE1", "Illiquid Card")
    archive = PriceArchive()
    archive.upsert({
        "NONE1:month:2026-08-01": _bucket("NONE1", "month", 1, "2026-08-01", "5.00"),
        "NONE1:month:2026-08-02": _bucket("NONE1", "month", 1, "2026-08-02", None),
        "NONE1:month:2026-08-03": _bucket("NONE1", "month", 1, "2026-08-03", "7.00"),
    })
    ledger = Ledger()
    report = holdings.build_holdings_report(inventory, archive, ledger, "month", now="2026-01-01T00:00:00+00:00")
    points = report.series[0].points
    ok(len(points) == 3, "the priced-None bucket still carries its own row", str(points))
    ok(points[1].value is None, "a priced-None bucket carries no value, never a zero")
    ok(points[1].gap_before is False, "08-01 -> 08-02 is calendar-adjacent even though "
       "08-02 has no price", str(points[1]))
    ok(points[2].gap_before is False, "08-02 -> 08-03 is calendar-adjacent too — the missing "
       "PRICE is not a missing DAY", str(points[2]))
    ok(points[2].value == "7.00", "the point after a priced-None bucket keeps its own real "
       "value", str(points[2]))


def test_sealed_excluded_counted() -> None:
    inventory, archive, ledger = base_fixture()
    count = holdings.sealed_excluded_count(inventory, ledger)
    ok(count == 1, "the sealed ledger SKU is counted", str(count))
    report = holdings.build_holdings_report(inventory, archive, ledger, "month", now="2026-01-01T00:00:00+00:00")
    ok(report.sealed_excluded_count == 1, "the report carries the same sealed count",
       str(report.sealed_excluded_count))
    skus = {s.sku for s in report.series}
    ok("SEALED1" not in skus, "sealed product never draws a series row — no quantity exists"
       " to value it with")


def test_sealed_never_dropped_when_zero_ledger() -> None:
    """An empty ledger must answer zero honestly, never mask a real bug that always
    answers zero regardless of the ledger's contents (guarded properly by the mutation arm
    below, this test only proves the honest empty case is not itself a false positive)."""
    inventory, archive, _ledger = base_fixture()
    empty_ledger = Ledger()
    count = holdings.sealed_excluded_count(inventory, empty_ledger)
    ok(count == 0, "an empty ledger has no sealed exclusion to report", str(count))


# --------------------------------------------------------------------------- mutation arms

def mutation_gap_interpolates() -> None:
    """Force `_adjacent` to always answer `True` — the gap this feature exists to catch
    would then interpolate silently. The gap assertion above must go red."""
    original = holdings._adjacent
    holdings._adjacent = lambda prev, start, width: True
    try:
        inventory = Inventory()
        inventory.cards[position_key(1, 1)] = _card(1, 1, "GAP1", "Trophy Hunter")
        archive = PriceArchive()
        archive.upsert({
            "GAP1:month:2026-08-01": _bucket("GAP1", "month", 1, "2026-08-01", "5.00"),
            "GAP1:month:2026-08-05": _bucket("GAP1", "month", 1, "2026-08-05", "9.00"),
        })
        report = holdings.build_holdings_report(inventory, archive, Ledger(), "month", now="2026-01-01T00:00:00+00:00")
        defeated = report.series[0].points[1].gap_before is False
        ok(defeated, "MUTATION: forcing `_adjacent` to always answer True defeats the gap "
           "guard, as expected — the real guard above must never do this")
    finally:
        holdings._adjacent = original


def mutation_sealed_exclusion_dropped() -> None:
    """Force `sealed_excluded_count` to always answer `0` — the exclusion this feature
    exists to name would then silently vanish. The sealed assertion above must go red."""
    original = holdings.sealed_excluded_count
    holdings.sealed_excluded_count = lambda inventory, ledger: 0
    try:
        inventory, archive, ledger = base_fixture()
        report = holdings.build_holdings_report(inventory, archive, ledger, "month", now="2026-01-01T00:00:00+00:00")
        defeated = report.sealed_excluded_count == 0
        ok(defeated, "MUTATION: forcing the sealed count to always answer 0 defeats the "
           "exclusion guard, as expected — the real guard above must never do this")
    finally:
        holdings.sealed_excluded_count = original


def main() -> int:
    print("pipeline/holdings.py:")
    test_quantity_and_state()
    test_name_with_reading()
    test_name_with_no_reading()
    test_range_gap_breaks_the_line()
    test_priced_none_bucket_carries_no_value()
    test_sealed_excluded_counted()
    test_sealed_never_dropped_when_zero_ledger()
    print("mutation arms (each proves the real guard above would have caught it):")
    mutation_gap_interpolates()
    mutation_sealed_exclusion_dropped()
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
