#!/usr/bin/env python3
"""`pipeline/productview.py` and `server/pipeline_routes.py:do_product_history`, proved
against a throwaway store (D227).

NO NETWORK CALL for the archive-hit arm — the whole reason this route may answer without
leaving the machine. The live-fallback arm is exercised with a `FakeMarket`, modelled on
`scripts/pricearchive-selftest.py`'s own stand-in, so this file adds no network dependency
either.

THE THREE ARMS THIS FILE PROVES, EACH BY BREAKING WHAT IT GUARDS:
  1. A SKU the store has never carried refuses `sku_unknown` — proved by asking about one.
  2. A SKU the store carries but the archive has swept answers straight off `price_history`,
     with `source: "archive"` and no live call — proved by pointing `do_product_history` at a
     `FakeMarket` that raises if it is ever called at all.
  3. A SKU the archive has never swept falls through to the live reader and answers
     `source: "live"` — proved the opposite way, by NOT seeding the archive and confirming
     the fake market's `reading_for_row` was in fact reached.

PATH GATED, THE TWENTY-FIRST (D247, owner's word 2026-09-23, on the same ground as
`pricearchive-selftest`'s sixteenth entry): `make product-history-selftest`, wired into
`make check` and `make ci-check` through `scripts/guard-scope.py`. This file is no longer
the exception it was when written — `do_product_history` is `#/product`'s own route
(`app/src/App.tsx`'s off-nav `#/product` screen, D226), a real, live, screen-reachable
caller. Once it's done, it only needs to be tested when touched.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

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


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="product-history-selftest-"))
    os.environ["PKMNSCAN_HOME"] = str(tmp)
    (tmp / "inventory").mkdir(parents=True, exist_ok=True)

    from pipeline.pricehistory import Bucket as HistoryBucket  # noqa: E402
    from pipeline.pricehistory import Reading as HistoryReading  # noqa: E402
    from pipeline.pricehistory import Series  # noqa: E402
    from store.master import Card  # noqa: E402
    from store.pricearchive import Bucket, _key  # noqa: E402
    from store.session import Store  # noqa: E402
    import server.pipeline_routes as pr  # noqa: E402

    print("product-history self-test\n")

    with Store().write() as writable:
        writable.inventory.cards["1/1"] = Card(
            box=1, index=1, name="Vilemaw", number="123", set_name="Twilight Masquerade",
            sku="555", condition="Near Mint", game="pokemon",
        )
        writable.inventory.cards["1/2"] = Card(
            box=1, index=2, name="Some Sealed Thing", number=None, set_name=None,
            sku="666", condition=None, game="misc",
        )

    # ---------------------------------------------------------------- 1. unknown SKU
    print("-- a SKU this store has never carried --")
    try:
        pr.do_product_history("999")
        ok(False, "refuses sku_unknown", "no exception raised")
    except pr.PipelineRefusal as exc:
        ok(exc.code == "sku_unknown", "refuses sku_unknown", exc.code)

    # ---------------------------------------------------------------- 2. not catalogued
    print("\n-- a SKU with no product line (misc, D22) --")
    try:
        pr.do_product_history("666")
        ok(False, "refuses not_catalogued", "no exception raised")
    except pr.PipelineRefusal as exc:
        ok(exc.code == "not_catalogued", "refuses not_catalogued", exc.code)

    # ---------------------------------------------------------------- 3. archive hit
    print("\n-- a SKU the archive has already swept: no network reached --")
    with Store().write() as writable:
        writable.archive.upsert({
            _key("555", "month", "2026-08-01"): Bucket(
                sku="555", product_id=42, range="month", width_days=1, start="2026-08-01",
                market="16.33", quantity=2, transactions=2, low="12.54", high="20.35", at=100,
            ),
            _key("555", "annual", "2026-01-01"): Bucket(
                sku="555", product_id=42, range="annual", width_days=7, start="2026-01-01",
                market="14.00", quantity=5, transactions=3, low="10.00", high="18.00", at=100,
            ),
        })

    class ExplodingMarket:
        def reading_for_row(self, row):
            raise AssertionError("archive-hit path must never reach a live Market")

    real_market = pr.pricehistory.Market
    try:
        pr.pricehistory.Market = lambda *a, **k: ExplodingMarket()
        payload = pr.do_product_history("555")
    finally:
        pr.pricehistory.Market = real_market

    ok(payload["source"] == "archive", "archive-hit answers source: archive", payload.get("source"))
    ranges = {r["range"] for r in payload["ranges"]}
    ok(ranges == {"month", "annual"}, "both swept ranges are present", ranges)
    month = next(r for r in payload["ranges"] if r["range"] == "month")
    ok(month["points"][0]["low"] == "12.54" and month["points"][0]["high"] == "20.35",
       "per-bucket spread is carried through untouched, never collapsed to one number",
       month["points"])
    ok(payload["history_begins"] == "2026-01-01",
       "history_begins is the earliest bucket actually read, not a constant",
       payload["history_begins"])

    # ---------------------------------------------------------------- 4. live fallback
    print("\n-- a catalogued SKU the archive has never swept: live fallback --")
    with Store().write() as writable:
        writable.inventory.cards["1/3"] = Card(
            box=1, index=3, name="Moonfall", number="99", set_name="Twilight Masquerade",
            sku="777", condition="Near Mint", game="pokemon",
        )

    reached = {"called": False}
    bucket = HistoryBucket(
        start=date(2026, 8, 1), market=Decimal("9.99"), quantity=1, transactions=1,
        low=Decimal("9.99"), high=Decimal("9.99"),
    )
    series = Series(
        sku="777", product_id=7, range="month", variant="Normal", condition="Near Mint",
        language="English", total_quantity_sold=1, total_transaction_count=1, buckets=(bucket,),
    )

    class FakeMarket:
        def reading_for_row(self, row):
            reached["called"] = True
            return HistoryReading(sku="777", product_id=7, series={"month": series})

    try:
        pr.pricehistory.Market = lambda *a, **k: FakeMarket()
        payload = pr.do_product_history("777")
    finally:
        pr.pricehistory.Market = real_market

    ok(reached["called"], "a SKU the archive has never seen reaches the live reader")
    ok(payload["source"] == "live", "live fallback answers source: live", payload.get("source"))
    ok(len(payload["ranges"]) == 1 and payload["ranges"][0]["range"] == "month",
       "the live Series is carried through", payload["ranges"])

    shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
