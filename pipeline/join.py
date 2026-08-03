"""Catalog join — identified cards to TCGplayer SKU rows.

Join key is `zfill(3)(number) + "/" + printedTotal`, built from pokemontcg.io data and
matched against the export's `Number` column. Secret rares exceed the denominator in the
same format (`161/159`) and are ordinary, not invalid. Product Name is NEVER a join key —
it inconsistently embeds the number ("Accelgor" in one row, "Black Belt's Training -
143/159" in another). Name matching exists only as a fallback for the rare catalog rows
whose `Number` is blank.

Duplicates aggregate by SKU at join time (D7): multiple copies collapse into ONE row with
`Add to Quantity` = copies, live quantity capped at 4, the remainder held as backstock at
known positions. Two rows with the same `TCGplayer Id` in one import file is undefined
behavior, so the emitter walks catalog order and can only produce each SKU once.

Bidirectional reporting, in both pairings this pipeline performs:

  cards <-> catalog     `join_batch`. Cards that resolved to no row go to the review queue
                        with their photo. The reverse direction is a closure check: every
                        card in equals one matched position or one review item out, and
                        no matched SKU may hold zero positions. That is v1 bug #5 stated
                        as an invariant — it silently skipped identified cards.

  file  <-> inventory   `reconcile_import`. Rows in a CSV whose SKU is in no inventory
                        position, and inventory cards the file never mentions.

`emit_import` refuses to write while either direction is non-empty, so "report unmatched
before any output is written" is a property of the code and not of the caller's
discipline.

It refuses on one more thing: sub-threshold cards with no disposition. What happens to a
card under the D9 threshold is the owner's call each run — flat at the floor, flat at a
number set for the run, or a per-SKU decision — so the pipeline surfaces the bucket with
its price distribution intact and waits. `SubThresholdBucket` bands it rather than lumping it,
because "everything under $0.40" hides which of those cards are worth a bulk lot.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from pipeline import pricing, tcgcsv, variant

# D7 — a playset. Configurable, but never guessed at.
LIVE_QUANTITY_CAP = 4

# D10 — 25 cards per divider. Configurable.
CARDS_PER_SECTION = 25


class OutputSuppressed(Exception):
    """emit_import refused: something was unmatched and has not been reported yet."""


@dataclass(frozen=True)
class Position:
    """D10 — sequential, assigned at capture. Sold cards leave permanent gaps; positions
    are never renumbered."""

    box: int
    index: int

    @property
    def section(self) -> int:
        return (self.index - 1) // CARDS_PER_SECTION + 1

    @property
    def card(self) -> int:
        return (self.index - 1) % CARDS_PER_SECTION + 1

    @property
    def label(self) -> str:
        return f"Box {self.box} · Section {self.section} · Card {self.card}"


@dataclass(frozen=True)
class IdentifiedCard:
    """One physical card after identification. `photo` is what the review queue shows."""

    position: Position
    name: str
    number: Optional[str] = None
    printed_total: Optional[str] = None
    metadata_finish: Optional[str] = None
    detected_finish: Optional[str] = None
    photo: Optional[str] = None


def join_key(number, printed_total) -> str:
    """zfill(3)(number) + "/" + printedTotal. `161/159` is a secret rare, not an error."""
    return f"{str(number).strip().zfill(3)}/{str(printed_total).strip()}"


class Catalog:
    """A TCGplayer export indexed for joining."""

    def __init__(self, export: tcgcsv.Export):
        self.export = export
        self._by_number: Dict[str, List[tcgcsv.Row]] = {}
        self._blank_number_by_name: Dict[str, List[tcgcsv.Row]] = {}
        self._order: Dict[str, int] = {}

        for index, row in enumerate(export.rows):
            self._order[row[tcgcsv.SKU_COLUMN]] = index
            number = row[tcgcsv.NUMBER_COLUMN].strip()
            if number:
                self._by_number.setdefault(number, []).append(row)
            else:
                self._blank_number_by_name.setdefault(
                    row[tcgcsv.NAME_COLUMN].strip(), []
                ).append(row)

    @property
    def header(self) -> Tuple[str, ...]:
        return self.export.header

    def rows_for_key(self, key: str) -> List[tcgcsv.Row]:
        return list(self._by_number.get(key, ()))

    def rows_for_blank_number_name(self, name: str) -> List[tcgcsv.Row]:
        return list(self._blank_number_by_name.get(name.strip(), ()))

    def candidates(self, card: IdentifiedCard) -> Tuple[List[tcgcsv.Row], str]:
        """Rows this card could be, and how they were found."""
        if card.number is not None and card.printed_total is not None:
            key = join_key(card.number, card.printed_total)
            return self.rows_for_key(key), f"number:{key}"
        # No collector number on the product (code cards, some promos). These are exactly
        # the rows whose `Number` is blank, so the name fallback stays scoped to them.
        return self.rows_for_blank_number_name(card.name), f"name:{card.name}"

    def catalog_index(self, sku: str) -> int:
        return self._order[sku]


@dataclass
class SkuMatch:
    """Every copy of one card+variant, collapsed to the single row the import will carry."""

    sku: str
    row: tcgcsv.Row
    positions: List[Position] = field(default_factory=list)
    stages: List[str] = field(default_factory=list)
    live_cap: int = LIVE_QUANTITY_CAP

    @property
    def condition(self) -> str:
        return self.row[tcgcsv.CONDITION_COLUMN]

    @property
    def market_price(self) -> Optional[Decimal]:
        return tcgcsv.parse_price(self.row[tcgcsv.MARKET_PRICE_COLUMN])

    @property
    def live_before(self) -> int:
        """Quantity already live, read from the export's `Total Quantity` (D7 refill)."""
        return tcgcsv.parse_quantity(self.row[tcgcsv.LIVE_QUANTITY_COLUMN])

    @property
    def copies(self) -> int:
        return len(self.positions)

    @property
    def add_to_quantity(self) -> int:
        return max(0, min(self.live_cap - self.live_before, self.copies))

    @property
    def backstock(self) -> int:
        return self.copies - self.add_to_quantity

    @property
    def live_positions(self) -> List[Position]:
        return self.positions[: self.add_to_quantity]

    @property
    def backstock_positions(self) -> List[Position]:
        return self.positions[self.add_to_quantity :]

    @property
    def list_price(self) -> Optional[Decimal]:
        market = self.market_price
        return None if market is None else pricing.list_price(market)

    @property
    def listable(self) -> bool:
        return pricing.is_listable(self.market_price)


@dataclass(frozen=True)
class UnmatchedCard:
    """Direction one: a card no catalog row could be resolved for. Goes to the review
    queue with its photo (D4); the physical card never leaves its box."""

    card: IdentifiedCard
    reason: str
    lookup: str
    candidates: Tuple[tcgcsv.Row, ...] = ()

    @property
    def describe(self) -> str:
        conditions = ", ".join(
            r[tcgcsv.CONDITION_COLUMN] for r in self.candidates
        ) or "none"
        return (
            f"{self.card.name} [{self.lookup}] {self.reason} "
            f"at {self.card.position.label} (candidates: {conditions})"
        )


@dataclass(frozen=True)
class Band:
    """One slice of the sub-threshold price distribution."""

    lower: Decimal  # inclusive
    upper: Decimal  # exclusive
    matches: Tuple[SkuMatch, ...]
    total_copies: int

    @property
    def label(self) -> str:
        return f"${self.lower:.2f}-${self.upper:.2f}"

    @property
    def copies(self) -> int:
        return sum(m.copies for m in self.matches)

    @property
    def share(self) -> Decimal:
        """Share of sub-threshold COPIES, not SKUs — the question is how much of the box
        this is, and seven copies of one card is seven cards to handle."""
        if not self.total_copies:
            return Decimal("0")
        return (
            Decimal(self.copies) / Decimal(self.total_copies) * 100
        ).quantize(Decimal("0.1"))


class SubThresholdBucket:
    """Matched SKUs whose market price is under the D9 threshold.

    Kept as a distribution, not a lump. "Everything under $0.40" hides the difference
    between a $0.38 rare and a $0.01 code card, and that difference is exactly what
    decides later which of them are worth a bulk lot and which are worth a flat listing.
    The bands preserve it in the report and in the data.
    """

    # Cut points as a fraction of the threshold, so they follow it if it moves. Against
    # the $0.40 default these are $0.30, $0.20 and $0.10.
    BAND_FRACTIONS: Tuple[Decimal, ...] = (
        Decimal("0.75"),
        Decimal("0.50"),
        Decimal("0.25"),
    )

    def __init__(
        self,
        matches: Optional[Sequence[SkuMatch]] = None,
        threshold: Decimal = pricing.THRESHOLD,
        fractions: Optional[Sequence[Decimal]] = None,
    ):
        self.matches: List[SkuMatch] = list(matches or ())
        self.threshold = threshold
        self.fractions = tuple(fractions if fractions is not None else self.BAND_FRACTIONS)

    def __iter__(self):
        return iter(self.matches)

    def __len__(self) -> int:
        return len(self.matches)

    @property
    def skus(self) -> List[str]:
        return [m.sku for m in self.matches]

    @property
    def copies(self) -> int:
        return sum(m.copies for m in self.matches)

    def bands(self) -> List[Band]:
        edges = [self.threshold] + [
            (self.threshold * f).quantize(Decimal("0.01")) for f in self.fractions
        ] + [Decimal("0.00")]
        total = self.copies
        out = []
        for upper, lower in zip(edges, edges[1:]):
            inside = tuple(
                m
                for m in self.matches
                if m.market_price is not None and lower <= m.market_price < upper
            )
            out.append(Band(lower=lower, upper=upper, matches=inside, total_copies=total))
        return out

    def report(self) -> str:
        lines = [
            f"below ${self.threshold} threshold: {len(self.matches)} SKU(s), "
            f"{self.copies} copies — disposition required before output"
        ]
        for band in self.bands():
            lines.append(
                f"    {band.label:>13}  {len(band.matches):>3} SKU(s)  "
                f"{band.copies:>3} copies  {band.share:>5}% of the bulk"
            )
            lines += [
                f"        {m.sku} {m.row[tcgcsv.NAME_COLUMN]} {m.condition} "
                f"market={m.market_price} x{m.copies}"
                for m in band.matches
            ]
        return "\n".join(lines)


@dataclass
class JoinReport:
    matches: "OrderedDict[str, SkuMatch]" = field(default_factory=OrderedDict)
    unmatched_cards: List[UnmatchedCard] = field(default_factory=list)
    below_threshold: SubThresholdBucket = field(default_factory=SubThresholdBucket)
    cards_in: int = 0

    @property
    def unmatched_rows(self) -> List[SkuMatch]:
        """Direction two of the cards<->catalog pairing: a matched SKU holding no card."""
        return [m for m in self.matches.values() if m.copies == 0]

    @property
    def at_cap(self) -> List[SkuMatch]:
        """Matched SKUs already at the live cap, so this run adds nothing. Not written to
        the import file, and reported rather than skipped — the copies are real cards
        sitting at real positions."""
        return [m for m in self.matches.values() if m.copies and m.add_to_quantity == 0]

    @property
    def cards_out(self) -> int:
        return sum(m.copies for m in self.matches.values()) + len(self.unmatched_cards)

    @property
    def dropped(self) -> int:
        """Cards that went in and came out neither matched nor reported. Always 0 unless
        the join has v1 bug #5 again."""
        return self.cards_in - self.cards_out

    @property
    def ok(self) -> bool:
        return (
            not self.unmatched_cards
            and not self.unmatched_rows
            and self.dropped == 0
        )

    @property
    def blocking_reasons(self) -> List[str]:
        reasons = []
        if self.unmatched_cards:
            reasons.append(
                f"{len(self.unmatched_cards)} card(s) matched no catalog row"
            )
        if self.unmatched_rows:
            reasons.append(f"{len(self.unmatched_rows)} matched row(s) hold no card")
        if self.dropped:
            reasons.append(f"{self.dropped} card(s) silently dropped")
        return reasons

    def report(self) -> str:
        """Both directions, always printed before output is written."""
        lines = [
            f"cards in: {self.cards_in} | SKUs matched: {len(self.matches)} | "
            f"copies matched: {sum(m.copies for m in self.matches.values())}",
            f"unmatched cards (-> review queue): {len(self.unmatched_cards)}",
        ]
        lines += [f"    {u.describe}" for u in self.unmatched_cards]
        lines.append(f"unmatched rows (row with no card): {len(self.unmatched_rows)}")
        lines += [f"    {m.sku} {m.row[tcgcsv.NAME_COLUMN]}" for m in self.unmatched_rows]
        lines.append(f"cards dropped: {self.dropped}")
        if self.at_cap:
            lines.append(f"already at the live cap, nothing added: {len(self.at_cap)}")
            lines += [
                f"    {m.sku} {m.row[tcgcsv.NAME_COLUMN]} live={m.live_before} "
                f"copies={m.copies}"
                for m in self.at_cap
            ]
        if self.below_threshold:
            lines.append(self.below_threshold.report())
        return "\n".join(lines)


def join_batch(
    cards: Sequence[IdentifiedCard],
    catalog: Catalog,
    live_cap: int = LIVE_QUANTITY_CAP,
) -> JoinReport:
    """Resolve every card to exactly one catalog row, aggregating copies by SKU."""
    report = JoinReport(cards_in=len(cards))

    for card in cards:
        candidates, lookup = catalog.candidates(card)
        resolution = variant.resolve(
            candidates,
            metadata_finish=card.metadata_finish,
            detected_finish=card.detected_finish,
        )

        if resolution.needs_review or resolution.row is None:
            report.unmatched_cards.append(
                UnmatchedCard(
                    card=card,
                    reason=resolution.reason,
                    lookup=lookup,
                    candidates=tuple(candidates),
                )
            )
            continue

        sku = resolution.sku
        match = report.matches.get(sku)
        if match is None:
            match = SkuMatch(sku=sku, row=resolution.row, live_cap=live_cap)
            report.matches[sku] = match
        match.positions.append(card.position)
        match.stages.append(resolution.stage)

    # Deterministic, and equal to the export's own order.
    report.matches = OrderedDict(
        sorted(report.matches.items(), key=lambda kv: catalog.catalog_index(kv[0]))
    )
    for match in report.matches.values():
        match.positions.sort(key=lambda p: (p.box, p.index))

    report.below_threshold = SubThresholdBucket(
        [m for m in report.matches.values() if not m.listable]
    )
    return report


class Undecided(Exception):
    """Sub-threshold SKUs are waiting on a disposition that nobody has given."""


def prices_for(
    report: JoinReport,
    sub_threshold: Optional[pricing.Disposition] = None,
    sku_dispositions: Optional[Dict[str, pricing.Disposition]] = None,
) -> "OrderedDict[str, Decimal]":
    """Listed price per SKU, and what decided it.

    Three layers, most specific first:

      1. `sku_dispositions[sku]`  — going under the hood on one SKU. Works on any matched
                                    SKU, above or below the threshold.
      2. `sub_threshold`          — one choice for the whole run's sub-threshold bucket.
      3. the D9 match rule        — for everything at or above the threshold.

    A sub-threshold SKU with neither 1 nor 2 raises `Undecided`. It is not quietly
    dropped, and it is not quietly listed.
    """
    overrides = dict(sku_dispositions or {})
    prices: "OrderedDict[str, Decimal]" = OrderedDict()
    undecided: List[SkuMatch] = []

    for match in report.matches.values():
        disposition = overrides.get(match.sku)
        if disposition is not None:
            prices[match.sku] = disposition.resolve()
            continue
        if match.listable:
            prices[match.sku] = match.list_price
            continue
        if sub_threshold is None:
            undecided.append(match)
            continue
        prices[match.sku] = sub_threshold.resolve()

    if undecided:
        raise Undecided(
            f"{len(undecided)} sub-threshold SKU(s) have no disposition. Pass a run "
            "default as sub_threshold=, or name them in sku_dispositions=.\n"
            + report.below_threshold.report()
        )

    unknown = set(overrides) - set(report.matches)
    if unknown:
        raise Undecided(f"sku_dispositions names SKUs not in this batch: {sorted(unknown)}")

    return prices


def import_rows(
    report: JoinReport,
    sub_threshold: Optional[pricing.Disposition] = None,
    sku_dispositions: Optional[Dict[str, pricing.Disposition]] = None,
) -> List[tcgcsv.Row]:
    """The rows an import file would carry. One per SKU, in catalog order."""
    prices = prices_for(report, sub_threshold, sku_dispositions)
    rows: List[tcgcsv.Row] = []
    for match in report.matches.values():
        if match.add_to_quantity == 0:  # already at the live cap; report.at_cap has it
            continue
        row = tcgcsv.set_writable(
            match.row,
            add_to_quantity=match.add_to_quantity,
            marketplace_price=prices[match.sku],
        )
        # Again, against the catalog original — a row can only reach the file if the
        # single writable-column rule holds for it.
        tcgcsv.check_only_writable_changed(match.row, row)
        rows.append(row)
    return rows


def emit_import(
    report: JoinReport,
    catalog: Catalog,
    path,
    sub_threshold: Optional[pricing.Disposition] = None,
    sku_dispositions: Optional[Dict[str, pricing.Disposition]] = None,
) -> bytes:
    """Write the import file — or refuse, loudly, with both directions reported."""
    if not report.ok:
        raise OutputSuppressed(
            "output suppressed; unmatched must be reported first:\n"
            + "\n".join(f"  - {r}" for r in report.blocking_reasons)
            + "\n"
            + report.report()
        )
    rows = import_rows(report, sub_threshold, sku_dispositions)
    skus = [r[tcgcsv.SKU_COLUMN] for r in rows]
    if len(skus) != len(set(skus)):
        raise OutputSuppressed("duplicate TCGplayer Id rows in one import file")
    return tcgcsv.write_csv(path, catalog.header, rows)


# ------------------------------------------------- file <-> inventory (v1 bug #5 path)


@dataclass
class ReconcileReport:
    """Pairing a CSV against inventory, in both directions.

    v1 matched by box+position, silently skipped identified cards, and reported nothing
    for unmatched rows. A one-directional check passes on that bug; this does not.
    """

    matched_skus: List[str] = field(default_factory=list)
    rows_without_cards: List[str] = field(default_factory=list)
    cards_without_rows: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.rows_without_cards and not self.cards_without_rows

    def report(self) -> str:
        return "\n".join(
            [
                f"rows matched to inventory: {len(self.matched_skus)}",
                f"rows with no inventory card: {len(self.rows_without_cards)} "
                f"{self.rows_without_cards}",
                f"inventory cards not in file: {len(self.cards_without_rows)} "
                f"{self.cards_without_rows}",
            ]
        )


def reconcile_import(
    rows: Iterable[tcgcsv.Row],
    inventory_skus: Iterable[str],
) -> ReconcileReport:
    inventory = list(inventory_skus)
    inventory_set = set(inventory)
    report = ReconcileReport()
    seen = set()

    for row in rows:
        sku = row[tcgcsv.SKU_COLUMN]
        seen.add(sku)
        if sku in inventory_set:
            report.matched_skus.append(sku)
        else:
            report.rows_without_cards.append(sku)

    report.cards_without_rows = [sku for sku in inventory if sku not in seen]
    return report
