"""The owner's investment roster, valued at Banchi's own prices (D324, `docs/specs/holdings-roster.md`).

WHY THIS SITS BESIDE `pipeline/holdings.py` AND NOT IN IT. That module values the store's OWN
stock: rows of the `cards` table, a quantity per SKU, a series over time. This one values a CSV
roster the owner exports from a marketplace, which the store has never seen, by joining each
purchase line to a product on its product id and pricing it from the price archive.
The two share no input, so neither imports the other. The report is a one-off, read-only.

PURE. `read_roster` takes a file object; `build_roster_report` takes lines, SKUs and an archive. Nothing here opens a store, reaches the network or writes. The verb
(`cli/cmd_holdingsroster.py`) is the one place that touches the disk.

PRIVACY. `read_roster` keeps seven columns and drops the rest at read, so a seller, buyer,
account, order id or URL never reaches a dataclass. The rendered report names no product or
set: product ids, counts and money only.

NO LINE IS DROPPED. Every kept line lands in exactly one bucket: priced, unpriced or
unmatched. Excluded rows are counted by reason, never skipped silently.

THE JOIN KEY IS THE PRODUCT ID. The roster's `Vendor Product Id` is looked up in a crosswalk
read from the archive alone: each `price_history` row's `product_id` maps to its SKU key, from
every range. Id 0 (a row the archive had no id for) is never a key. One id is one product, so
there is no ambiguous bucket. `pipeline.join`'s `normalize_set` and `name_index_key` survive only
as a cross-check: a line they price that the id join leaves unmatched or unpriced is listed
store side. Prices come only from `store.pricearchive.PriceArchive.for_sku`.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, List, NamedTuple, Optional, Set, Tuple

from pipeline.join import name_index_key, normalize_set
from pipeline.tcgcsv import SEALED_CONDITION
from store.pricearchive import PriceArchive

#: The reasons a row is excluded, in report order.
EXCLUDE_REASONS = ("sale", "not_tcg", "canceled", "other_type")
#: Why a matched line has no price, in report order.
UNPRICED_REASONS = ("no_price", "printing", "no_sku_row")

# The seven columns a kept line carries. Every other column is dropped at read.
_COLUMNS = (
    "Type", "Vendor", "Shipping Status", "Vendor Product Id", "Set Name", "Product Name",
    "Condition", "Finish", "Quantity", "Total Amount",
)
_NEAR_MINT = "Near Mint"
_NON_FOIL = "non-foil"


@dataclass(frozen=True)
class RosterLine:
    product_id: str
    set_name: str
    product_name: str
    condition: str
    finish: str
    quantity: int
    paid: Decimal


@dataclass
class Roster:
    lines: List[RosterLine] = field(default_factory=list)
    excluded: Dict[str, int] = field(default_factory=dict)


class SkuRow(NamedTuple):
    """The store's `skus` columns this report reads. `condition` is the whole cell
    (`Near Mint Holofoil`); `printing` is its suffix, or `None` for plain Near Mint."""

    key: str
    set_name: str
    product_name: str
    number: str
    condition: str
    printing: Optional[str]


def _money(text: str) -> Decimal:
    """A finite, non-negative amount. Blank after cleanup (`$`, `,`) raises, never reads as 0."""
    value = Decimal(str(text).strip().replace("$", "").replace(",", ""))
    if not value.is_finite() or value < 0:
        raise ValueError(f"amount {text!r} is not a non-negative number")
    return value


def read_roster(fileobj) -> Roster:
    """Kept lines and excluded counts from a roster CSV. The `csv` module only.

    A kept row is `Type` purchase, `Vendor` TCG, `Shipping Status` not canceled. A row that
    fails one test is counted under the first reason that applies, and is never parsed for
    amount or quantity. A column missing from the header, or a kept row that is short, has an
    amount that is blank, unreadable or negative, or a quantity that is unreadable or not above
    zero, raises `ValueError` and names its file line (`reader.line_num`, so a quoted newline
    earlier in the file does not shift it): guessing would hide a line.
    """
    reader = csv.DictReader(fileobj)
    missing = [c for c in _COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"roster is missing column(s): {', '.join(missing)}")
    roster = Roster(excluded={reason: 0 for reason in EXCLUDE_REASONS})
    for row in reader:
        n = reader.line_num
        kind = (row["Type"] or "").strip().lower()
        if kind != "purchase":
            roster.excluded["sale" if kind == "sale" else "other_type"] += 1
        elif (row["Vendor"] or "").strip() != "TCG":
            roster.excluded["not_tcg"] += 1
        elif (row["Shipping Status"] or "").strip().lower() == "canceled":
            roster.excluded["canceled"] += 1
        else:
            if any(row[c] is None for c in _COLUMNS):
                raise ValueError(f"roster line {n}: the row is too short for its columns")
            try:
                quantity = int(row["Quantity"].strip())
                paid = _money(row["Total Amount"])
            except (ValueError, InvalidOperation) as exc:
                raise ValueError(f"roster line {n}: unreadable quantity or amount") from exc
            if quantity <= 0:
                raise ValueError(f"roster line {n}: quantity must be above zero")
            roster.lines.append(RosterLine(
                row["Vendor Product Id"].strip(), row["Set Name"], row["Product Name"],
                row["Condition"], row["Finish"].strip(), quantity, paid,
            ))
    return roster


# ------------------------------------------------------------------------------- the report


@dataclass
class PricedRow:
    product_id: str
    lines: int = 0
    units: int = 0
    paid: Decimal = Decimal(0)
    market_total: Decimal = Decimal(0)

    @property
    def market_each(self) -> Decimal:
        # Weighted: one product id can carry two finishes at two prices.
        return self.market_total / self.units if self.units else Decimal(0)

    @property
    def gain(self) -> Decimal:
        return self.market_total - self.paid


@dataclass
class CountRow:
    product_id: str
    lines: int = 0
    units: int = 0


@dataclass
class RosterReport:
    excluded: Dict[str, int]
    base_lines: int
    priced: List[PricedRow]
    unpriced: Dict[str, int]
    unmatched: List[CountRow]
    store_side: Tuple[str, ...]
    price_date: Optional[str]

    @property
    def priced_lines(self) -> int:
        return sum(r.lines for r in self.priced)

    @property
    def priced_units(self) -> int:
        return sum(r.units for r in self.priced)

    @property
    def priced_paid(self) -> Decimal:
        return sum((r.paid for r in self.priced), Decimal(0))

    @property
    def market_total(self) -> Decimal:
        return sum((r.market_total for r in self.priced), Decimal(0))

    @property
    def gain(self) -> Decimal:
        return self.market_total - self.priced_paid

    def render(self) -> str:
        out = ["units received unknown", "units sold unknown",
               "Units held are units bought until both are answered.", ""]
        out.append("Excluded rows: " + ", ".join(
            f"{r} {self.excluded.get(r, 0)}" for r in EXCLUDE_REASONS)
            + f". Base lines: {self.base_lines}.")
        out.append("")
        out.append("Unmatched, roster side (product id, lines, units):")
        out += [f"  {r.product_id}  {r.lines}  {r.units}" for r in self.unmatched] or ["  none"]
        out.append("Unmatched, store side (name join prices, id join does not): "
                   + (", ".join(self.store_side) or "none") + f" ({len(self.store_side)})")
        out.append("Unpriced lines: " + ", ".join(
            f"{r} {self.unpriced.get(r, 0)}" for r in UNPRICED_REASONS))
        out.append("")
        out.append("Priced (product id, units, paid, market each, market total, gain):")
        out += [f"  {r.product_id}  {r.units}  {r.paid:.2f}  {r.market_each:.2f}  "
                f"{r.market_total:.2f}  {r.gain:.2f}" for r in self.priced] or ["  none"]
        out.append("")
        out.append(f"Totals: paid {self.priced_paid:.2f}, market {self.market_total:.2f}, "
                   f"gain {self.gain:.2f}, price date {self.price_date or 'none'}")
        pct = 100 * self.priced_lines / self.base_lines if self.base_lines else 0
        out.append(f"Coverage: priced {self.priced_lines} of {self.base_lines} lines "
                   f"({pct:.1f}%), {self.priced_units} units, paid {self.priced_paid:.2f}")
        return "\n".join(out)


def _finish_agrees(finish: str, condition: str, printing: Optional[str]) -> bool:
    """`non-foil` keeps a SKU with no foil in its condition or printing (`Holofoil` and
    `Reverse Holofoil` carry the word). Any other finish keeps a SKU with foil in either."""
    foil = "foil" in f"{condition} {printing or ''}".lower()
    return not foil if finish.lower() == _NON_FOIL else foil


def _unit_price(finish: str, skus: Iterable[SkuRow], archive: PriceArchive):
    """`(price, start, None)` or `(None, None, reason)` for one product's SKUs."""
    skus = list(skus)
    # Sealed product has no Near Mint SKU and no finish: price its Unopened SKU.
    sealed = bool(skus) and all(s.condition == SEALED_CONDITION for s in skus)
    found = []
    for sku in skus:
        if not sealed and (not sku.condition.startswith(_NEAR_MINT)
                           or not _finish_agrees(finish, sku.condition, sku.printing)):
            continue
        priced = [b for b in archive.for_sku(sku.key) if b.range == "month" and b.market]
        if priced:
            newest = max(priced, key=lambda b: b.start)
            found.append((Decimal(str(newest.market)), newest.start))
    if len(found) == 1:
        return found[0][0], found[0][1], None
    return None, None, "printing" if found else "no_price"


def _id_of(text: str) -> int:
    """The roster's id as an int, or 0 for blank or non-numeric (0 is never a key)."""
    try:
        return int(text)
    except ValueError:
        return 0


def build_roster_report(roster, skus: Iterable[SkuRow], archive: PriceArchive) -> RosterReport:
    by_key: Dict[Tuple[str, str], List[SkuRow]] = defaultdict(list)
    by_sku: Dict[str, SkuRow] = {}
    for sku in skus:
        by_key[(normalize_set(sku.set_name), name_index_key(sku.product_name))].append(sku)
        by_sku[sku.key] = sku
    crosswalk: Dict[int, Set[str]] = defaultdict(set)
    for bucket in archive.entries.values():
        if bucket.product_id:
            crosswalk[bucket.product_id].add(bucket.sku)

    priced: Dict[str, PricedRow] = {}
    unpriced = {reason: 0 for reason in UNPRICED_REASONS}
    unmatched: Dict[str, CountRow] = {}
    store_side: Set[str] = set()
    dates: List[str] = []

    for line in roster.lines:
        keys = crosswalk.get(_id_of(line.product_id))
        candidates = [by_sku[k] for k in sorted(keys or ()) if k in by_sku]
        price = None
        if not keys:
            reason = "unmatched"
        elif not candidates:
            reason = "no_sku_row"
        else:
            price, start, reason = _unit_price(line.finish, candidates, archive)
        if price is not None:
            row = priced.setdefault(line.product_id, PricedRow(line.product_id))
            row.lines += 1
            row.units += line.quantity
            row.paid += line.paid
            row.market_total += price * line.quantity
            dates.append(start)
            continue
        if reason == "unmatched":
            row = unmatched.setdefault(line.product_id, CountRow(line.product_id))
            row.lines += 1
            row.units += line.quantity
        else:
            unpriced[reason] += 1
        named = by_key.get((normalize_set(line.set_name), name_index_key(line.product_name)), [])
        if len({(n.set_name, n.product_name, n.number) for n in named}) == 1 \
                and _unit_price(line.finish, named, archive)[0] is not None:
            store_side.add(line.product_id)

    return RosterReport(
        excluded=dict(roster.excluded),
        base_lines=len(roster.lines),
        priced=sorted(priced.values(), key=lambda r: r.product_id),
        unpriced=unpriced,
        unmatched=sorted(unmatched.values(), key=lambda r: r.product_id),
        store_side=tuple(sorted(store_side)),
        price_date=max(dates) if dates else None,
    )
