#!/usr/bin/env python3
"""`server/pipeline_routes.py:_trends_for_entries` must pass the archive's already-verified
productId per SKU into `Market.readings_for_rows`, and must never resolve a product from
scratch for a SKU the archive already covers.

Protects: The trends route reuses the archive's verified product ids and never resolves a product it already covers.
Governs: D254

WHAT THIS PROVES. Measured 2026-09-27 on a real demo-mirror recording: a
`/pipeline/runs/<name>/trends` request over ~400 SKUs timed out at the client's 30s GET
timeout. Reproduced in isolation: 400 failed `Market.category_id()` calls (the shape of
every row under the recorder's offline network guard, where a fetch NEVER succeeds and so
NEVER gets cached — `Market.get` only stores on success) cost 62.79s, almost all of it the
0.15s courtesy delay repeated before every one of the 400 always-failing attempts.

`do_pipeline_price_now` already reads `store/pricearchive.py:PriceArchive.for_sku` (an O(1)
per-SKU index since the 2026-09-27 review, D254) for exactly this reason — `_trends_for_entries`
just never adopted it. This self-test poisons `Market.category_id` to raise if it is ever
called for a SKU the archive already resolves, and asserts the reading still comes back
correctly, off the archive's id alone — the network-resolution path must never be reached for
a SKU the archive has already answered.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import pricehistory, tcgcsv  # noqa: E402
from server import pipeline_routes  # noqa: E402

PASS = 0
FAIL = 0


def ok(condition: bool, label: str, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok     {label}")
    else:
        FAIL += 1
        print(f"  FAIL   {label}  {detail}")


class _Bucket:
    def __init__(self, product_id: int, range_: str = "month", market: str = "1.00") -> None:
        self.product_id = product_id
        self.range = range_
        self.market = market
        self.start = "2026-09-01"


class _Archive:
    def __init__(self, by_sku: Dict[str, List[_Bucket]]) -> None:
        self._by_sku = by_sku

    def for_sku(self, sku: str) -> List[_Bucket]:
        return self._by_sku.get(sku, [])


class _Snapshot:
    def __init__(self, archive: _Archive) -> None:
        self.archive = archive


class _PoisonedMarket(pricehistory.Market):
    """`category_id`/`group_id` raise if ever called — proving the archive's id short-
    circuited `product_id_for_row` for every SKU it covers."""

    def category_id(self, product_line: str) -> int:  # noqa: D401
        raise AssertionError(
            "category_id() was called — a SKU the archive already resolved fell through "
            "to the slow, network-shaped path anyway"
        )

    def group_id(self, category_id: int, set_name: str) -> int:
        raise AssertionError("group_id() was called — same failure as category_id()")


def main() -> int:
    known_id = 4242
    archive = _Archive({"9999999": [_Bucket(known_id)]})
    snapshot = _Snapshot(archive)

    real_store = pipeline_routes.Store

    class _FakeStore:
        def read(self):
            return snapshot

    pipeline_routes.Store = _FakeStore
    real_market = pipeline_routes.pricehistory.Market
    try:
        # `_trends_for_entries` builds its own `pricehistory.Market(...)`; swap the class so
        # the poisoned one answers `history()` (a real, working history call) but blows up on
        # any attempt to resolve a productId from scratch.
        def _history(self, product_id, range_):
            ok(product_id == known_id, "history() is called with the ARCHIVE's productId",
               "got %r, want %r" % (product_id, known_id))
            return {
                "9999999": pricehistory.Series(
                    sku="9999999", product_id=product_id, range=range_,
                    variant="", condition="", language="",
                    total_quantity_sold=0, total_transaction_count=0, buckets=(),
                )
            }

        _PoisonedMarket.history = _history
        pipeline_routes.pricehistory.Market = _PoisonedMarket

        row = {
            tcgcsv.SKU_COLUMN: "9999999",
            tcgcsv.PRODUCT_LINE_COLUMN: "Pokemon",
            tcgcsv.SET_COLUMN: "Some Set",
            tcgcsv.NUMBER_COLUMN: "1",
            tcgcsv.NAME_COLUMN: "Some Card",
        }
        entries = {"9999999": {"sku": "9999999", "row": row}}
        result = pipeline_routes._trends_for_entries(
            entries, [], {"run": "test"},
            missing="missing {sku}", skip_at_cap=False,
        )
        ok("9999999" in result["skus"], "the SKU is answered",
           "refused=%r" % result.get("refused"))
    finally:
        pipeline_routes.Store = real_store
        pipeline_routes.pricehistory.Market = real_market

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
