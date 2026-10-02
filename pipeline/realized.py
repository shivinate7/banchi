"""What this seller got for a product, against what the market did that day (DEBT70).

READ-ONLY DIAGNOSTIC. It lists nothing, prices nothing and writes nothing (D214: gross
only, never profit). A listing rule built on it needs its own decision.

The input is an OrderWand sales export. Every row carries a buyer, so `read_sales` keeps
`Sale._fields` and nothing else: the buyer, account, order id and url are dropped while the
row is parsed, never held and filtered later. The file is read in place from a path the
caller names. No copy of it, and no value from a dropped column, may reach the tree, a
fixture or a log. Nothing here logs a row.

The join is `Vendor Product Id` (a TCGplayer productId) to `store/pricearchive.py`'s
`price_history`, by the date a sale was ordered.
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

from store.pricearchive import RANGE_WIDTH_DAYS, Bucket

#: The only columns this reader looks at. Every other column is never read into a value.
KEPT = ("Vendor Product Id", "Ordered At", "Price", "Quantity", "Condition", "Finish",
        "Refund Amount", "Type", "Currency")

#: Finest bucket first: a sale date is compared with the narrowest window that covers it.
_FINEST_FIRST = sorted(RANGE_WIDTH_DAYS, key=RANGE_WIDTH_DAYS.get)


class Sale(NamedTuple):
    product_id: int
    day: str  # ISO date
    price: Decimal  # per copy
    quantity: int
    refund: Decimal
    condition: str
    finish: str


def read_sales(path: str) -> Tuple[List[Sale], Dict[str, int]]:
    """`(sales, left_out)`. Only `Type == "sale"` rows in USD that parse become a `Sale`.
    `left_out` counts the rest by reason, never by row: purchases (the owner buying),
    other currencies and unreadable rows. A missing kept column raises `ValueError`."""
    sales: List[Sale] = []
    out = {"not_a_sale": 0, "not_usd": 0, "unreadable": 0}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in KEPT if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("The sales export has no column named " + ", ".join(missing) + ".")
        for raw in reader:
            row = {c: raw.get(c) or "" for c in KEPT}  # the rest of `raw` dies here
            if row["Type"].strip().lower() != "sale":
                out["not_a_sale"] += 1
            elif row["Currency"].strip().upper() != "USD":
                out["not_usd"] += 1
            else:
                try:
                    price, refund = Decimal(row["Price"]), Decimal(row["Refund Amount"] or "0")
                    quantity = int(row["Quantity"])
                    # NaN and Infinity parse as Decimals, so refuse them by name.
                    if not (price.is_finite() and refund.is_finite()) or price < 0 or refund < 0 or quantity < 1:
                        raise ValueError
                    sales.append(Sale(
                        int(row["Vendor Product Id"]),
                        # Ordered At is a bare date in the export (counted, not printed): no zone to shift.
                        date.fromisoformat(row["Ordered At"].strip()[:10]).isoformat(),
                        price, quantity, refund,
                        row["Condition"].strip(),
                        row["Finish"].strip(),
                    ))
                except (ValueError, InvalidOperation):
                    out["unreadable"] += 1
    return sales, out


def bucket_on(day: str, buckets: Iterable[Bucket]) -> Optional[Bucket]:
    """The finest archived bucket whose window holds `day`, or `None`."""
    when = date.fromisoformat(day)
    held = [b for b in buckets
            if b.market is not None
            and date.fromisoformat(b.start) <= when < date.fromisoformat(b.start) + timedelta(days=b.width_days)]
    held.sort(key=lambda b: _FINEST_FIRST.index(b.range))
    return held[0] if held else None


_BASIS = {"month": "day", "quarter": "3 days", "semiannual": "week", "annual": "week"}
_FOIL_WORDS = ("holofoil", "foil")


def sku_matches(sale: Sale, sku_condition: Optional[str]) -> bool:
    """True only when the sale's condition and finish are plainly the SKU's. The SKU's
    condition reads like `Near Mint` or `Near Mint Foil`. A finish of `unknown` or any word
    this does not know never matches: it is counted as another condition, never guessed."""
    if not sku_condition:
        return False
    words = sku_condition.strip().lower()
    foil = words.endswith(_FOIL_WORDS)
    for w in _FOIL_WORDS:
        if words.endswith(w):
            words = words[: -len(w)].strip()
            break
    finish = sale.finish.lower()
    if finish in ("foil", "holofoil"):
        sale_foil = True
    elif finish == "non-foil":
        sale_foil = False
    else:
        return False
    return sale.condition.lower() == words and sale_foil == foil


def compare(sales: Iterable[Sale], buckets: List[Bucket], sku_condition: Optional[str] = None) -> dict:
    """Each sale of this SKU's own condition and finish against the market on its date; the
    rest are counted in `other_conditions`, never compared. A refunded sale is listed and left out of
    the totals. A sale with no bucket on its date is listed with `market: None` and left out
    of the totals, so the two averages always cover the same copies."""
    rows, units, got, market, refunded, no_market, other = [], 0, Decimal(0), Decimal(0), 0, 0, 0
    for s in sorted(sales, key=lambda s: s.day):
        if not sku_matches(s, sku_condition):
            other += 1
            continue
        bucket = bucket_on(s.day, buckets)
        rows.append({"day": s.day, "quantity": s.quantity, "price": str(s.price),
                     "market": bucket.market if bucket else None,
                     "basis": _BASIS[bucket.range] if bucket else None,
                     "refunded": s.refund > 0, "condition": s.condition, "finish": s.finish})
        if s.refund > 0:
            refunded += 1
        elif bucket is None:
            no_market += 1
        else:
            units += s.quantity
            got += s.price * s.quantity
            market += Decimal(bucket.market) * s.quantity
    return {
        "rows": rows, "other_conditions": other, "units": units, "refunded": refunded, "no_market": no_market,
        "realized_avg": str((got / units).quantize(Decimal("0.01"))) if units else None,
        "market_avg": str((market / units).quantize(Decimal("0.01"))) if units else None,
    }
