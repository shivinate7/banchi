"""T7 group: the owner's realized prices against the archive (DEBT70).

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.

Protects: A sales export's buyer never survives the parse, and a sale joins to the archive by product and date.
Governs: D214, D219

THE FIXTURE IS SYNTHETIC. Every dropped column carries an invented sentinel, so a leak of any
of them anywhere in a payload is a string search. No real export, buyer or order id is here.
"""

from __future__ import annotations

import csv
import json
import os
import tempfile

from harness.tests import Checks
from harness.tests.t7.common import isolated_home
from pipeline import realized
from server import pipeline_routes
from store.pricearchive import Bucket
from store.session import Store

HEADER = [
    "Type", "Vendor", "Account", "Order Id", "Ordered At", "Shipping Amount", "Tax Amount",
    "Item Number", "Product Name", "Set Name", "Set Code", "Condition", "Finish", "Price",
    "Quantity", "Total Amount", "Currency", "Product Line", "Product Type", "Party",
    "Shipping Status", "Url", "Vendor Product Id", "Fee Amount", "Refund Amount",
]
SENTINELS = ["ZORBLAX-BUYER", "QUINTILLE-ACCOUNT", "ORDER-ID-ZZ", "https://example.test/ZZ-URL"]
PID = "424242"


def _row(kind="sale", day="2026-09-10", price="2.00", qty="1", currency="USD", refund="0.00",
         pid=PID) -> dict:
    row = {h: "x" for h in HEADER}
    row.update({
        "Type": kind, "Ordered At": day, "Price": price, "Quantity": qty, "Currency": currency,
        "Refund Amount": refund, "Vendor Product Id": pid, "Condition": "near mint",
        "Finish": "foil", "Party": SENTINELS[0], "Account": SENTINELS[1],
        "Order Id": SENTINELS[2], "Url": SENTINELS[3],
    })
    return row


def _write(directory: str, rows: list) -> str:
    path = os.path.join(directory, "synthetic-sales.csv")
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _bucket(range_, start, width, market) -> Bucket:
    return Bucket("SKU1", int(PID), range_, width, start, market, 5, 2, None, None, 0)


def check_realized_prices(checks: Checks) -> None:
    """Three cases, each seen failing once:
    1. NO BUYER FIELD SURVIVES THE PARSE. A sentinel in every dropped column appears in no
       `Sale`, no comparison and no route payload.
    2. THE JOIN. Sales match on product id, take the finest bucket that holds their date, and
       leave out purchases, refunds and other currencies. Averages are copy-weighted.
    3. A MISSING ARCHIVE DATE is listed with no market and left out of both averages.
    """
    checks.note("")
    checks.note("REALIZED PRICES — buyers dropped at parse, the join, a date with no bucket (DEBT70)")

    rows = [
        _row(day="2026-09-10", price="3.00", qty="2"),            # day bucket 0.50 wins
        _row(day="2026-09-10", price="9.00", kind="purchase"),    # the owner buying
        _row(day="2026-09-10", price="9.00", currency="GBP"),
        _row(day="2026-09-10", price="9.00", refund="9.00"),      # refunded
        _row(day="2026-05-01", price="1.00"),                     # no bucket on that date
        _row(day="2026-09-10", price="5.00", pid="1"),            # another product
        {**_row(day="2026-09-10", price="0.10"), "Condition": "moderately played"},
        {**_row(day="2026-09-10", price="0.10"), "Finish": "non-foil"},
        {**_row(day="2026-09-10", price="0.10"), "Finish": "unknown"},
        _row(price="nan"), _row(price="Infinity"), _row(price="-1.00"), _row(refund="-2"),
    ]
    with tempfile.TemporaryDirectory() as directory, isolated_home():
        path = _write(directory, rows)
        sales, left_out = realized.read_sales(path)

        checks.ok(tuple(realized.Sale._fields) == ("product_id", "day", "price", "quantity", "refund", "condition", "finish"), "a Sale carries only the kept fields")
        checks.ok(not any(s_ in repr(sales) for s_ in SENTINELS), "no dropped column survives the parse")
        checks.ok(left_out == {"not_a_sale": 1, "not_usd": 1, "unreadable": 4} and len(sales) == 7, "purchases and other currencies are counted, never listed")

        buckets = [
            _bucket("month", "2026-09-10", 1, "0.50"),
            _bucket("annual", "2026-09-07", 7, "9.99"),  # holds the date too, never preferred
        ]
        mine = [s for s in sales if s.product_id == int(PID)]
        out = realized.compare(mine, buckets, "Near Mint Foil")
        checks.ok(out["units"] == 2 and out["realized_avg"] == "3.00" and out["market_avg"] == "0.50", "the join takes the finest bucket and weights by copies")
        checks.ok(out["refunded"] == 1 and out["units"] == 2, "a refunded sale is listed and left out of the totals")
        checks.ok(out["other_conditions"] == 3 and out["units"] == 2,
                  "other conditions and finishes are counted, never averaged in")
        checks.ok(realized.compare(mine, buckets, None)["units"] == 0,
                  "a SKU with no known condition matches nothing")
        gap = next(r for r in out["rows"] if r["day"] == "2026-05-01")
        checks.ok(gap["market"] is None and out["no_market"] == 1 and out["units"] == 2, "a date with no archive bucket has no market and is not averaged")

        with Store().write() as snapshot:
            snapshot.archive.upsert({f"SKU1:{b.range}:{b.start}": b for b in buckets})
        os.environ["BANCHI_SALES_EXPORT"] = path
        real = pipeline_routes.productview.row_for_sku
        pipeline_routes.productview.row_for_sku = lambda snap, sku: {"Condition": "Near Mint Foil"}
        try:
            payload = pipeline_routes.do_product_realized("SKU1")
        finally:
            pipeline_routes.productview.row_for_sku = real
            del os.environ["BANCHI_SALES_EXPORT"]
        checks.ok(payload["product_id"] == int(PID) and payload["realized_avg"] == "3.00"
            and payload["file"] == "synthetic-sales.csv", "the route answers by the archive's product id")
        checks.ok(not any(s_ in json.dumps(payload) for s_ in SENTINELS), "no dropped column survives to the route payload")
        checks.ok(pipeline_routes.do_product_realized("SKU1") == {"sku": "SKU1", "configured": False}, "no export chosen answers configured false")


CHECKS = (check_realized_prices,)
