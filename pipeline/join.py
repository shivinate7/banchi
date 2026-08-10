"""Catalog join — identified cards to TCGplayer SKU rows.

Join key is `zfill(3)(number) + "/" + printedTotal`. The shape follows pokemontcg.io's
schema — `printedTotal` is their field name — but at runtime both values come from the
identification, matched against the export's `Number` column. Nothing here calls that API;
`harness/eval/fixtures.py` is the only caller, for T1's labelled fixtures.

Secret rares exceed the denominator in the same format (`161/159`) and are ordinary, not
invalid. Product Name is NEVER a join key — it inconsistently embeds the number
("Accelgor" in one row, "Black Belt's Training - 143/159" in another). Name matching
exists only as a fallback for the rare catalog rows whose `Number` is blank.

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

A card leaves `unmatched_cards` in exactly one way: by being routed into `queued`, which is
what the standing review and parked queues are written from. That is the amended GATES.md
T3 criterion expressed structurally — reviews no longer suppress output (v2 §5.6, holding
400 good cards hostage to 7 ambiguous ones is the wrong trade), but a card may leave this
pipeline unlisted and never unrecorded. Pass a `router` to get that behaviour; without one
the older, stricter shape is unchanged, and the harness exercises both.

It refuses on one more thing: sub-threshold cards with no disposition. What happens to a
card under the D9 threshold is the owner's call each run — flat at the floor, flat at a
number set for the run, or a per-SKU decision — so the pipeline surfaces the bucket with
its price distribution intact and waits. `SubThresholdBucket` bands it rather than lumping it,
because "everything under $0.40" hides which of those cards are worth a bulk lot.

MULTI-SET KEYING (v2 §5.1). The join key is unique only *within* a set, and multi-set runs
are required. Collisions are computed once at catalog build — cheap, deterministic, and
known before a single card is joined — and reported, so the real exposure is visible rather
than assumed. A colliding key is disambiguated by the capture sidecar's set hint; no hint,
or a hint naming none of the candidate sets, reviews as `set_ambiguous`. Never guessed.
This deliberately does not make the set hint authoritative everywhere: D2 and the prompt
both call it optional and possibly wrong, so it is consulted only where the number alone
has already failed to decide.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from pipeline import pricing, routing, tcgcsv, variant

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
    """One physical card after identification. `photo` is what the review queue shows.

    `set_hint` is the capture sidecar's stack label (D2: an optional accelerator, possibly
    wrong). It is read only to break a multi-set key collision — see `Catalog.candidates`.

    `confidence` is the model's own read of how legible the title and number were, and is
    the only signal that a card was guessed at. `pipeline.routing` acts on it.
    """

    position: Position
    name: str
    number: Optional[str] = None
    printed_total: Optional[str] = None
    metadata_finish: Optional[str] = None
    detected_finish: Optional[str] = None
    photo: Optional[str] = None
    set_hint: Optional[str] = None
    confidence: Optional[str] = None


def join_key(number, printed_total) -> str:
    """zfill(3)(number) + "/" + printedTotal. `161/159` is a secret rare, not an error."""
    return f"{str(number).strip().zfill(3)}/{str(printed_total).strip()}"


def normalize_set(name: str) -> str:
    """Fold a set label to something two sources can agree on.

    The export writes `SV09: Journey Together`; a capture sidecar's hint is whatever the
    divider was labelled — `sv9`, `SV09`, `Journey Together`. Lowercase, drop everything
    that is not a letter or digit, and strip leading zeros from each digit run, so `sv09`
    and `sv9` fold to one string. pokemontcg.io uses the unpadded form and TCGplayer the
    padded one; without this they never compare equal.
    """
    text = str(name or "").strip().lower()
    out: List[str] = []
    digits: List[str] = []
    for char in text:
        if char.isdigit():
            digits.append(char)
            continue
        if digits:
            out.append(str(int("".join(digits))))
            digits = []
        if char.isalnum():
            out.append(char)
    if digits:
        out.append(str(int("".join(digits))))
    return "".join(out)


def set_matches(hint: Optional[str], set_name: str) -> bool:
    """Does this hint name this set?

    Matched against the whole label and against each side of the colon, so `sv9`,
    `SV09`, `Journey Together` and the full `SV09: Journey Together` all hit. Deliberately
    exact after folding, with no substring fallback: `sv1` is a substring of `sv19`, and a
    hint that quietly matches the wrong set is worse than one that matches nothing — the
    latter reviews, which is what D2's "possibly wrong" hint has earned.
    """
    folded = normalize_set(hint)
    if not folded:
        return False
    parts = [set_name] + set_name.split(":")
    return any(normalize_set(part) == folded for part in parts)


@dataclass(frozen=True)
class Candidates:
    """The rows a card could be, how they were found, and whether that was decisive."""

    rows: Tuple[tcgcsv.Row, ...]
    lookup: str
    set_ambiguous: bool = False
    candidate_sets: Tuple[str, ...] = ()

    @property
    def market_prices(self) -> Tuple[Optional[Decimal], ...]:
        return tuple(
            tcgcsv.parse_price(row[tcgcsv.MARKET_PRICE_COLUMN]) for row in self.rows
        )


class Catalog:
    """A TCGplayer export indexed for joining.

    Built from the export and nothing else (v2 §5.1). Collisions — one join key reaching
    rows in more than one `Set Name` — are computed here, once, before any card is joined.
    """

    def __init__(self, export: tcgcsv.Export):
        self.export = export
        self._by_number: Dict[str, List[tcgcsv.Row]] = {}
        self._blank_number_by_name: Dict[str, List[tcgcsv.Row]] = {}
        self._order: Dict[str, int] = {}
        self._sets_by_key: Dict[str, List[str]] = {}

        for index, row in enumerate(export.rows):
            self._order[row[tcgcsv.SKU_COLUMN]] = index
            number = row[tcgcsv.NUMBER_COLUMN].strip()
            set_name = row.get(tcgcsv.SET_COLUMN, "")
            if number:
                self._by_number.setdefault(number, []).append(row)
                key = number
            else:
                name = row[tcgcsv.NAME_COLUMN].strip()
                self._blank_number_by_name.setdefault(name, []).append(row)
                key = f"name:{name}"
            seen = self._sets_by_key.setdefault(key, [])
            if set_name not in seen:
                seen.append(set_name)

    @property
    def header(self) -> Tuple[str, ...]:
        return self.export.header

    @property
    def set_names(self) -> List[str]:
        names: List[str] = []
        for row in self.export.rows:
            name = row.get(tcgcsv.SET_COLUMN, "")
            if name not in names:
                names.append(name)
        return names

    @property
    def colliding_keys(self) -> List[str]:
        """Keys reaching rows in more than one set. Reported at catalog build so the real
        exposure is a number, not an assumption."""
        return sorted(k for k, sets in self._sets_by_key.items() if len(sets) > 1)

    def sets_for_key(self, key: str) -> List[str]:
        return list(self._sets_by_key.get(key, ()))

    def rows_for_key(self, key: str) -> List[tcgcsv.Row]:
        return list(self._by_number.get(key, ()))

    def rows_for_blank_number_name(self, name: str) -> List[tcgcsv.Row]:
        return list(self._blank_number_by_name.get(name.strip(), ()))

    def candidates(self, card: IdentifiedCard) -> Candidates:
        """Rows this card could be, and how they were found."""
        if card.number is not None and card.printed_total is not None:
            key = join_key(card.number, card.printed_total)
            rows = self.rows_for_key(key)
            lookup = f"number:{key}"
        else:
            # No collector number on the product (code cards, some promos). These are
            # exactly the rows whose `Number` is blank, so the name fallback stays scoped
            # to them.
            rows = self.rows_for_blank_number_name(card.name)
            lookup = f"name:{card.name}"

        sets: List[str] = []
        for row in rows:
            name = row.get(tcgcsv.SET_COLUMN, "")
            if name not in sets:
                sets.append(name)

        if len(sets) <= 1:
            return Candidates(rows=tuple(rows), lookup=lookup)

        # Rung 3 of §5.1 — a colliding key, disambiguated by the sidecar set hint.
        if card.set_hint:
            narrowed = [
                row
                for row in rows
                if set_matches(card.set_hint, row.get(tcgcsv.SET_COLUMN, ""))
            ]
            if narrowed:
                return Candidates(
                    rows=tuple(narrowed), lookup=f"{lookup} set:{card.set_hint}"
                )

        # Rung 4 — no hint, or a hint naming none of the candidates.
        return Candidates(
            rows=tuple(rows),
            lookup=lookup,
            set_ambiguous=True,
            candidate_sets=tuple(sets),
        )

    def catalog_index(self, sku: str) -> int:
        return self._order[sku]


@dataclass
class SkuMatch:
    """Every copy of one card+variant, collapsed to the single row the import will carry.

    `rule` and `basis` are the run's pricing choice (v2 §6). They default to the D9 match
    rule against Market, which is what every caller before batch script v2 assumed.
    """

    sku: str
    row: tcgcsv.Row
    positions: List[Position] = field(default_factory=list)
    stages: List[str] = field(default_factory=list)
    live_cap: int = LIVE_QUANTITY_CAP
    rule: pricing.Rule = pricing.MATCH
    basis: str = pricing.BASIS_MARKET

    @property
    def condition(self) -> str:
        return self.row[tcgcsv.CONDITION_COLUMN]

    @property
    def set_name(self) -> str:
        return self.row.get(tcgcsv.SET_COLUMN, "")

    @property
    def market_price(self) -> Optional[Decimal]:
        """What the D9 threshold reads, always, whatever `--basis` is set to."""
        return tcgcsv.parse_price(self.row[tcgcsv.MARKET_PRICE_COLUMN])

    @property
    def basis_price(self) -> Optional[Decimal]:
        """What the pricing rule is applied to."""
        return pricing.basis_price(self.row, self.basis)

    @property
    def has_market_data(self) -> bool:
        """False means the price is UNKNOWN, not low — never sub-threshold (D9)."""
        return pricing.has_market_data(self.market_price)

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
        """`clamp_floor(round(rule(basis)))`. None when the basis cell is blank."""
        basis = self.basis_price
        if basis is None:
            return None
        return pricing.list_price(basis, rule=self.rule)

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


@dataclass(frozen=True)
class QueuedCard:
    """A card the router sent to a standing queue instead of to the import file.

    Distinct from `UnmatchedCard`, and the distinction is the whole point: an unmatched
    card is unrecorded and blocks output; a queued one has been written down at a known
    position and does not. A card moves from the first category to the second only by being
    routed, never by being tolerated.
    """

    card: IdentifiedCard
    destination: routing.Destination
    lookup: str
    resolution_reason: str
    candidates: Tuple[tcgcsv.Row, ...] = ()

    @property
    def queue(self) -> str:
        return self.destination.queue

    @property
    def describe(self) -> str:
        return (
            f"{self.card.name} [{self.lookup}] -> {self.destination.describe} "
            f"at {self.card.position.label}"
        )


@dataclass
class JoinReport:
    matches: "OrderedDict[str, SkuMatch]" = field(default_factory=OrderedDict)
    unmatched_cards: List[UnmatchedCard] = field(default_factory=list)
    queued: List[QueuedCard] = field(default_factory=list)
    below_threshold: SubThresholdBucket = field(default_factory=SubThresholdBucket)
    cards_in: int = 0
    collisions: int = 0

    def queue(self, name: str) -> List[QueuedCard]:
        """One standing queue's cards, in the order they should be worked.

        Main-queue order is priced-and-ambiguous first, descending by price, unpriced last
        (v2 §5.4). Position breaks ties so two runs of the same box agree.
        """
        return sorted(
            (q for q in self.queued if q.queue == name),
            key=lambda q: (
                q.destination.sort_key,
                q.card.position.box,
                q.card.position.index,
            ),
        )

    @property
    def no_market_data(self) -> List[SkuMatch]:
        """Matched, but the catalog row carries no price. Never auto-priced (D9)."""
        return [m for m in self.matches.values() if m.copies and not m.has_market_data]

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
        return (
            sum(m.copies for m in self.matches.values())
            + len(self.unmatched_cards)
            + len(self.queued)
        )

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
        for name in (routing.MAIN, routing.PARKED):
            cards = self.queue(name)
            if cards:
                lines.append(f"routed to {name}: {len(cards)}")
                lines += [f"    {q.describe}" for q in cards]
        if self.no_market_data:
            lines.append(
                f"no market data (hand-price or leave unlisted): {len(self.no_market_data)}"
            )
            lines += [
                f"    {m.sku} {m.row[tcgcsv.NAME_COLUMN]} {m.condition} x{m.copies}"
                for m in self.no_market_data
            ]
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


Router = Callable[[IdentifiedCard, Candidates, variant.Resolution], routing.Destination]


def default_router(
    threshold: Decimal = pricing.THRESHOLD,
    review_below: str = routing.CONFIDENCE_LOW,
) -> Router:
    """The v2 §5.4 routing table, bound to this run's threshold and confidence gate."""
    routing.check_review_below(review_below)

    def route(
        card: IdentifiedCard,
        found: Candidates,
        resolution: variant.Resolution,
    ) -> routing.Destination:
        resolved = not resolution.needs_review and resolution.row is not None
        return routing.route(
            resolved=resolved,
            reason=resolution.reason,
            confidence=card.confidence,
            price=resolution.market_price,
            candidate_prices=found.market_prices,
            threshold=threshold,
            review_below=review_below,
        )

    return route


def join_batch(
    cards: Sequence[IdentifiedCard],
    catalog: Catalog,
    live_cap: int = LIVE_QUANTITY_CAP,
    router: Optional[Router] = None,
    rule: pricing.Rule = pricing.MATCH,
    basis: str = pricing.BASIS_MARKET,
) -> JoinReport:
    """Resolve every card to exactly one catalog row, aggregating copies by SKU.

    With a `router`, every card that does not list is written into `report.queued` with the
    queue it belongs in — reviews stop suppressing output, because the card is recorded
    (v2 §5.6). Without one, ladder failures land in `unmatched_cards` and `report.ok` is
    False, which is the pre-v2 behaviour and still what `emit_import` refuses on.
    """
    pricing.check_basis(basis)
    rule = pricing.Rule.parse(rule)
    report = JoinReport(cards_in=len(cards), collisions=len(catalog.colliding_keys))

    for card in cards:
        found = catalog.candidates(card)
        if found.set_ambiguous:
            # A colliding key the set hint could not break. Never guessed (§5.1 rung 4).
            resolution = variant.Resolution(
                stage=variant.REVIEW, reason=routing.SET_AMBIGUOUS
            )
        else:
            resolution = variant.resolve(
                found.rows,
                metadata_finish=card.metadata_finish,
                detected_finish=card.detected_finish,
            )

        if router is not None:
            destination = router(card, found, resolution)
            if destination.queue in (routing.MAIN, routing.PARKED):
                report.queued.append(
                    QueuedCard(
                        card=card,
                        destination=destination,
                        lookup=found.lookup,
                        resolution_reason=resolution.reason,
                        candidates=found.rows,
                    )
                )
                continue

        if resolution.needs_review or resolution.row is None:
            report.unmatched_cards.append(
                UnmatchedCard(
                    card=card,
                    reason=resolution.reason,
                    lookup=found.lookup,
                    candidates=found.rows,
                )
            )
            continue

        sku = resolution.sku
        match = report.matches.get(sku)
        if match is None:
            match = SkuMatch(
                sku=sku,
                row=resolution.row,
                live_cap=live_cap,
                rule=rule,
                basis=basis,
            )
            report.matches[sku] = match
        match.positions.append(card.position)
        match.stages.append(resolution.stage)

    # Deterministic, and equal to the export's own order.
    report.matches = OrderedDict(
        sorted(report.matches.items(), key=lambda kv: catalog.catalog_index(kv[0]))
    )
    for match in report.matches.values():
        match.positions.sort(key=lambda p: (p.box, p.index))

    # A row with no market price is NOT sub-threshold — it is unpriced, which D9 keeps as
    # its own category precisely so it cannot be swept into a flat bulk price.
    report.below_threshold = SubThresholdBucket(
        [m for m in report.matches.values() if m.has_market_data and not m.listable]
    )
    return report


class Undecided(Exception):
    """Sub-threshold SKUs are waiting on a disposition that nobody has given."""


def prices_for(
    report: JoinReport,
    sub_threshold: Optional[pricing.Disposition] = None,
    sku_dispositions: Optional[Dict[str, pricing.Disposition]] = None,
    no_market_data: Optional[Dict[str, object]] = None,
) -> "OrderedDict[str, Decimal]":
    """Listed price per SKU, and what decided it.

    Four layers, most specific first:

      1. `sku_dispositions[sku]`  — going under the hood on one SKU. Works on any matched
                                    SKU, above or below the threshold.
      2. `no_market_data[sku]`    — a hand-entered price for a row the catalog has no price
                                    for, or `pricing.UNLISTED` to leave it out of the file.
                                    D9: a missing price is an unknown price, so it gets no
                                    automatic answer of any kind.
      3. `sub_threshold`          — one choice for the whole run's sub-threshold bucket.
      4. the run's pricing rule   — for everything at or above the threshold.

    A sub-threshold SKU with no disposition raises `Undecided`, and so does an unpriced SKU
    with no hand-entered answer. Neither is quietly dropped, and neither is quietly listed.

    SKUs answered `UNLISTED` are absent from the returned mapping — that is how a decision
    to not list something is carried, rather than by a price nobody chose.
    """
    overrides = dict(sku_dispositions or {})
    unpriced = dict(no_market_data or {})
    prices: "OrderedDict[str, Decimal]" = OrderedDict()
    undecided: List[SkuMatch] = []
    unanswered: List[SkuMatch] = []

    for match in report.matches.values():
        disposition = overrides.get(match.sku)
        if disposition is not None:
            prices[match.sku] = disposition.resolve()
            continue
        if not match.has_market_data:
            answer = unpriced.get(match.sku)
            if answer is None:
                unanswered.append(match)
                continue
            if answer == pricing.UNLISTED:
                continue
            prices[match.sku] = pricing.round_money(Decimal(str(answer)))
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

    if unanswered:
        raise Undecided(
            f"{len(unanswered)} SKU(s) have no market price in the catalog and no "
            f"hand-entered answer. A missing price is an unknown price (D9): give each a "
            f"price or {pricing.UNLISTED!r}, never the floor by default.\n"
            + "\n".join(
                f"    {m.sku} {m.row[tcgcsv.NAME_COLUMN]} {m.condition} x{m.copies}"
                for m in unanswered
            )
        )

    unknown = set(overrides) - set(report.matches)
    if unknown:
        raise Undecided(f"sku_dispositions names SKUs not in this batch: {sorted(unknown)}")

    return prices


def import_rows(
    report: JoinReport,
    sub_threshold: Optional[pricing.Disposition] = None,
    sku_dispositions: Optional[Dict[str, pricing.Disposition]] = None,
    no_market_data: Optional[Dict[str, object]] = None,
    only: Optional[Set[str]] = None,
) -> List[tcgcsv.Row]:
    """The rows an import file would carry. One per SKU, in catalog order.

    `only` selects a subset of SKUs, which is how `emit` splits one join into the listed
    file and the sub-threshold file (v2 §7) without pricing the run twice.
    """
    prices = prices_for(report, sub_threshold, sku_dispositions, no_market_data)
    rows: List[tcgcsv.Row] = []
    for match in report.matches.values():
        if match.sku not in prices:  # answered UNLISTED
            continue
        if only is not None and match.sku not in only:
            continue
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
    no_market_data: Optional[Dict[str, object]] = None,
    only: Optional[Set[str]] = None,
) -> bytes:
    """Write the import file — or refuse, loudly, with both directions reported.

    `report.ok` is the gate, and it is unchanged by v2 §5.6: a routed card is no longer in
    `unmatched_cards`, so a run whose reviews all reached a standing queue passes here,
    while a card nobody recorded still stops the write. That is the amended GATES.md T3
    criterion — reported and queued *before* output, rather than output suppressed.
    """
    if not report.ok:
        raise OutputSuppressed(
            "output suppressed; unmatched must be reported first:\n"
            + "\n".join(f"  - {r}" for r in report.blocking_reasons)
            + "\n"
            + report.report()
        )
    rows = import_rows(report, sub_threshold, sku_dispositions, no_market_data, only)
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
