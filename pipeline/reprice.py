"""Mark down the listings that are live, old, and not selling (D94).

WHAT THIS IS, AND WHY IT DID NOT EXIST. `join` picks a price at the moment it lists a card and
`emit` writes it once, so "change the price of something already live" was, in
`docs/DECISIONS.md`'s own words from the Someday entry this discharges, *"a concept this
product does not have rather than a feature it is missing"*. That entry deferred the push half
and named the shape it would have to take if it were ever built: *"a free preflight showing
exactly which prices would change and by how much, and a confirm that is not a default"*,
because *"an unattended loop that moves live marketplace prices is the one thing in this
product that could lose money while nobody is looking."* Both halves of that sentence are
built here — this module decides and computes, and it writes nothing at all.

IT ADDS NO COPIES, AND THAT IS THE WHOLE SAFETY ARGUMENT. Every row this builds carries
`Add to Quantity` = 0, which is the byte TCGplayer's OWN export writes on all 21,502 rows
across the four fixtures. So a markdown updates a price in place, matched on `TCGplayer Id`,
and CANNOT breach the live cap — D86's failure mode, where three separate emits spent a global
cap three times and pushed two SKUs to 6 against a cap of 4, is unreachable from here because
there is no quantity to spend. `rows()` asserts it rather than trusting it, in both directions:
an input row that is not already at zero refuses the whole file, and the output row is
re-checked against its export original the way `join.import_rows` re-checks its own.

IT NEVER RAISES A PRICE. `not_a_markdown` is the refusal, per SKU, and it is not a nicety: a
market that has risen under `--basis market`, a mistyped `markup:`, or a listing already
sitting on the $0.40 floor all produce a "new" price at or above the old one, and writing that
row would move a live marketplace price in the direction nobody asked for.

THE BASIS ENUM IS LOCAL AND MUST STAY LOCAL. `pipeline/pricing.py:BASES` is bound by
`cli/__main__.py` to `--basis` on `join` AND `emit`, so widening it there would offer `listed`
on the NEW-LISTING path — where `tcgcsv.set_writable`'s `is not None` guard would leave
`TCG Marketplace Price` exactly as the export had it, blank on 7,787 of 7,802 rows in the wide
Pokemon export, with nothing raising anywhere. `pipeline/corpus.py` would accept it as a
store-wide standing policy on top of that. Three lines of local dispatch buy immunity from
both; `Rule`, `list_price`, `round_money`, `clamp_floor` and `FLOOR` are reused verbatim.

PRICES ARE COMPARED AS `Decimal` AND NEVER AS STRINGS. A live export writes four decimals
(`"0.6600"`) and this writer emits two (`"0.66"`). `Decimal("0.6600") == Decimal("0.66")` is
True, so the numeric comparison correctly reports "no change"; a string comparison would call
every row in the file changed and mark down the entire store by a rounding artefact.

NO I/O AND NO `store` IMPORT. `livecheck.compare`'s shape, for its reason: plain mappings in,
so this module never learns the card schema and the harness can drive it without a store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import (
    AbstractSet,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
)

from pipeline import pricing, tcgcsv

# --------------------------------------------------------------------------------- basis

#: The operator's own asking price, out of the export's `TCG Marketplace Price`. The default,
#: because "mark my prices down" is a statement about what the operator is asking, not about
#: what the market is doing.
BASIS_LISTED = "listed"

#: Local, and deliberately NOT `pricing.BASES` — see the module header. `market` and `low`
#: are re-exported by value so `--basis market` means here exactly what it means to `join`.
BASES = (BASIS_LISTED, pricing.BASIS_MARKET, pricing.BASIS_LOW)


def basis_price(row: tcgcsv.Row, basis: str) -> Optional[Decimal]:
    """The price the rule is applied to. None when the cell is blank.

    `pricing.basis_price` raises `UnknownBasis` on anything outside its own two, which is the
    refusal a mistyped `--basis` should get, so the fall-through is the validation.
    """
    if basis == BASIS_LISTED:
        return tcgcsv.parse_price(row.get(tcgcsv.PRICE_COLUMN, ""))
    return pricing.basis_price(row, basis)


def listed_price(row: tcgcsv.Row) -> Optional[Decimal]:
    """What the operator is currently asking. The number a markdown is measured against."""
    return tcgcsv.parse_price(row.get(tcgcsv.PRICE_COLUMN, ""))


def live_quantity(row: tcgcsv.Row) -> int:
    """Copies TCGplayer says it holds. `Total Quantity`, which is never written."""
    return tcgcsv.parse_quantity(row.get(tcgcsv.LIVE_QUANTITY_COLUMN, ""))


# ------------------------------------------------------------------------------- reasons

#: A price, but no copies for sale. THE MAJORITY POPULATION IN EVERY FIXTURE — 96 of the 109
#: priced rows across the four real exports — and it gets a name rather than silence because
#: the operator thinks of these as "listed" and would read their absence as a broken sweep.
REASON_SOLD_OUT = "sold_out"
#: Live, but the operator has never set an asking price this document can read.
REASON_NO_LISTED_PRICE = "no_listed_price"
#: Live at TCGplayer, and no card in this store carries the SKU. Left alone — `livecheck`'s
#: posture and D87's: this pipeline did not put it there.
REASON_NOT_THIS_STORE = "not_this_store"
#: A copy sold inside the window. It is working; leave the price alone.
REASON_SOLD_RECENTLY = "sold_recently"
#: Held less than the window. It has not had time to sell, and marking it down would be
#: pricing impatience rather than staleness.
REASON_TOO_YOUNG = "too_young"
#: Withheld in the corpus (D49). The operator said "not this one".
REASON_HELD = "held"
#: Already marked down inside the window. THE RATCHET GUARD — see `select`.
REASON_MARKED_DOWN_RECENTLY = "marked_down_recently"
#: The rule does not lower the price. Never written, never raised.
REASON_NOT_A_MARKDOWN = "not_a_markdown"
#: The basis column is blank, so the rule has nothing to apply to.
REASON_NO_BASIS_PRICE = "no_basis_price"
#: Priced within `--above-market` of the market. The price is not the problem.
REASON_NOT_DRIFTED = "not_drifted"
#: The export row already carries a quantity. Reported here, and refused outright by `rows()`.
REASON_QUANTITY_NOT_ZERO = "add_to_quantity_not_zero"

#: Report order. Populations the operator is most likely to go looking for come first.
REASON_ORDER = (
    REASON_SOLD_OUT,
    REASON_SOLD_RECENTLY,
    REASON_TOO_YOUNG,
    REASON_NOT_DRIFTED,
    REASON_HELD,
    REASON_MARKED_DOWN_RECENTLY,
    REASON_NOT_A_MARKDOWN,
    REASON_NO_LISTED_PRICE,
    REASON_NO_BASIS_PRICE,
    REASON_QUANTITY_NOT_ZERO,
    REASON_NOT_THIS_STORE,
)

REASON_HEADING = {
    REASON_SOLD_OUT: "sold out",
    REASON_SOLD_RECENTLY: "sold recently",
    REASON_TOO_YOUNG: "too young",
    REASON_NOT_DRIFTED: "priced near market",
    REASON_HELD: "held back",
    REASON_MARKED_DOWN_RECENTLY: "marked down already",
    REASON_NOT_A_MARKDOWN: "not a markdown",
    REASON_NO_LISTED_PRICE: "no asking price",
    REASON_NO_BASIS_PRICE: "no basis price",
    REASON_QUANTITY_NOT_ZERO: "carries a quantity",
    REASON_NOT_THIS_STORE: "not this store",
}


class NotAdditive(Exception):
    """An export row carries a quantity, so this file would add copies as well as reprice.

    Raised by `rows()` and never by `select()`: the selection reports it as one more skipped
    population, and the WRITE refuses the whole file, because a partially-additive import is
    exactly the thing this module's zero-quantity invariant exists to make impossible.
    """


# ------------------------------------------------------------------------------ the rows


@dataclass(frozen=True)
class Candidate:
    """One listing that will be marked down, and every number that justifies it."""

    sku: str
    row: tcgcsv.Row
    listed: Decimal
    new: Decimal
    live: int
    on_hand: int
    room: int
    market: Optional[Decimal] = None
    oldest: Optional[str] = None
    age_days: Optional[int] = None
    last_sold: Optional[str] = None

    @property
    def name(self) -> str:
        return self.row.get(tcgcsv.NAME_COLUMN, "")

    @property
    def condition(self) -> str:
        return self.row.get(tcgcsv.CONDITION_COLUMN, "")

    @property
    def cut(self) -> Decimal:
        """Per copy."""
        return self.listed - self.new

    @property
    def off(self) -> Decimal:
        """Across every live copy. What the markdown actually gives up."""
        return self.cut * self.live

    @property
    def drift_pct(self) -> Optional[Decimal]:
        """How far above market the CURRENT asking price sits, as a percentage.

        The number the Someday entry asked for by name — *"these 23 have moved more than 10%
        since you listed them"*. Age says a card is old; this says the price is wrong, and
        they are different claims about different cards.
        """
        if self.market is None or self.market <= 0:
            return None
        return ((self.listed - self.market) / self.market * 100).quantize(Decimal("0.1"))


@dataclass(frozen=True)
class Skipped:
    """One listing that will not be, and which population it fell into."""

    sku: str
    reason: str
    row: tcgcsv.Row
    listed: Optional[Decimal] = None
    new: Optional[Decimal] = None
    detail: str = ""

    @property
    def name(self) -> str:
        return self.row.get(tcgcsv.NAME_COLUMN, "")

    @property
    def live(self) -> int:
        return live_quantity(self.row)


@dataclass
class Plan:
    """What a write would do, computed whole before any file handle opens (D54)."""

    candidates: List[Candidate] = field(default_factory=list)
    #: Dropped by `--limit`. NAMED, never merely counted — a silently shortened list is
    #: `CLAUDE.md`'s "never silently drop a card" wearing a different hat.
    truncated: List[Candidate] = field(default_factory=list)
    skipped: Dict[str, List[Skipped]] = field(default_factory=dict)
    scanned: int = 0
    live_rows: int = 0

    @property
    def copies(self) -> int:
        return sum(row.live for row in self.candidates)

    @property
    def off(self) -> Decimal:
        """Total given up across every copy this would reprice."""
        return sum((row.off for row in self.candidates), Decimal("0"))

    @property
    def at_risk(self) -> List[Candidate]:
        """Candidates a later `emit` could re-push at the rule price.

        Only a SKU with room under the cap AND backstock behind it can be written again by
        `join.import_rows`, whose `add_to_quantity` is `min(cap - copies_out, uncommitted)`.
        Measured on the owner's store: 14 of 378 live SKUs. They are named in the report so
        the operator is not surprised by a markdown that comes back up.
        """
        return [row for row in self.candidates if row.room > 0 and row.on_hand > row.live]


# -------------------------------------------------------------------------- the selection


def _stamp(value: Optional[str]) -> Optional[datetime]:
    """An ISO stamp as an aware datetime, or None if it will not parse.

    Naive stamps are read as UTC. `store/master.py:now` writes offsets and `captured_at` on
    the owner's store carries them, but a hand-edited record must not take the whole command
    down — an unreadable stamp reads as "no information", which every caller here already
    has a branch for.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _age_days(stamp: Optional[str], now: datetime) -> Optional[int]:
    moment = _stamp(stamp)
    if moment is None:
        return None
    return (now - moment).days


def select(
    export_rows: Sequence[tcgcsv.Row],
    *,
    ages: Mapping[str, str],
    last_sold: Mapping[str, str],
    on_hand: Mapping[str, int],
    seen: AbstractSet[str],
    held: AbstractSet[str],
    marked_down: Mapping[str, str],
    rule,
    days: int,
    now: str,
    basis: str = BASIS_LISTED,
    above_market: Optional[Decimal] = None,
    floor: Decimal = pricing.FLOOR,
    live_cap: int = 4,
    limit: Optional[int] = None,
) -> Plan:
    """Which listings to mark down, to what, and why every other one was left alone.

    THE STALENESS PREDICATE IS THREE TERMS AND ALL THREE ARE LOAD-BEARING. Live now, no sale
    inside the window, and held longer than the window. Measured on the owner's store, the
    third term is what makes the first two useful at all: 93% of live SKUs have never sold a
    copy, but half of them were captured two days ago and have had no chance to. Without an
    age term the sweep fires on essentially the whole store.

    `ages` IS `min(captured_at)` OVER EVERY CARD THAT EVER CARRIED THE SKU, not over the ones
    still on hand, and the caller owes that. A floor computed over on-hand copies moves
    FORWARD as the oldest copy sells, so a listing gets younger the longer it sits and drops
    out of the selection at exactly the moment it most deserves to be in it.

    IT IS AN AGE OF OWNERSHIP AND NOT AN AGE OF LISTING, and the report says so rather than
    this docstring keeping it. `store/master.py:Listing` has no `first_listed_at`, and
    `live_as_of` is absent from all 443 payloads on the owner's store, so "days since listed"
    is not answerable from the store as it exists. D94 records what would make it so and why
    that field is not worth adding today.

    `marked_down` IS THE RATCHET GUARD. Nothing else stops `undercut:10` compounding daily to
    −52% in a week, floored only at $0.40, with every individual run justified because the
    card still has not sold and is still old. A SKU marked down inside the window is refused;
    `--again` is the deliberate override, and it is deliberately not a default.
    """
    moment = _stamp(now) or datetime.now(timezone.utc)
    cutoff = moment - timedelta(days=days)
    parsed_rule = pricing.Rule.parse(rule)
    if basis != BASIS_LISTED:
        # Raises `UnknownBasis` here rather than once per row, so a mistyped `--basis` is a
        # sentence before anything is scanned.
        pricing.check_basis(basis)

    plan = Plan(scanned=len(export_rows))
    picked: List[Candidate] = []

    def skip(sku, reason, row, **extra) -> None:
        plan.skipped.setdefault(reason, []).append(
            Skipped(sku=sku, reason=reason, row=row, **extra)
        )

    for row in export_rows:
        sku = row.get(tcgcsv.SKU_COLUMN, "")
        if not sku:
            continue
        live = live_quantity(row)
        listed = listed_price(row)

        # A ROW WITH NEITHER A PRICE NOR A QUANTITY IS NOT A LISTING AT ALL — it is one of the
        # ~21,000 catalogue rows a Filtered Export carries for cards this operator has never
        # touched. Silent by design: naming 21,000 of them would bury the eleven that matter.
        if live <= 0 and listed is None:
            continue

        if live <= 0:
            skip(sku, REASON_SOLD_OUT, row, listed=listed)
            continue
        plan.live_rows += 1

        if listed is None:
            skip(sku, REASON_NO_LISTED_PRICE, row)
            continue
        if sku not in seen:
            skip(sku, REASON_NOT_THIS_STORE, row, listed=listed)
            continue
        if sku in held:
            # NAMED, NOT SILENT. A hold that is live at TCGplayer is a contradiction worth
            # the operator's eye: they said "do not list this" and it is listed.
            skip(sku, REASON_HELD, row, listed=listed)
            continue

        sold_at = _stamp(last_sold.get(sku))
        if sold_at is not None and sold_at >= cutoff:
            skip(sku, REASON_SOLD_RECENTLY, row, listed=listed,
                 detail=str(last_sold.get(sku)))
            continue

        oldest = ages.get(sku)
        born = _stamp(oldest)
        if born is None or born > cutoff:
            skip(sku, REASON_TOO_YOUNG, row, listed=listed, detail=str(oldest or "unknown"))
            continue

        down_at = _stamp(marked_down.get(sku))
        if down_at is not None and down_at >= cutoff:
            skip(sku, REASON_MARKED_DOWN_RECENTLY, row, listed=listed,
                 detail=str(marked_down.get(sku)))
            continue

        market = tcgcsv.parse_price(row.get(tcgcsv.MARKET_PRICE_COLUMN, ""))
        if above_market is not None:
            if market is None or market <= 0:
                skip(sku, REASON_NOT_DRIFTED, row, listed=listed, detail="no market price")
                continue
            drift = (listed - market) / market * 100
            if drift <= above_market:
                skip(sku, REASON_NOT_DRIFTED, row, listed=listed,
                     detail="{0:.1f}% above market".format(drift))
                continue

        # THE QUANTITY CHECK IS ON THE INPUT ROW AND IT IS NOT PARANOIA. Every real export
        # writes "0" here; a document that does not is not the document this command
        # contracts to read, and letting one row through would make the import additive.
        if (row.get(tcgcsv.QUANTITY_COLUMN, "") or "0").strip() not in ("", "0"):
            skip(sku, REASON_QUANTITY_NOT_ZERO, row, listed=listed,
                 detail=row.get(tcgcsv.QUANTITY_COLUMN, ""))
            continue

        base = basis_price(row, basis)
        if base is None or base <= 0:
            skip(sku, REASON_NO_BASIS_PRICE, row, listed=listed, detail=basis)
            continue

        new = pricing.list_price(base, parsed_rule, floor)
        if new >= listed:
            # NEVER RAISES A LIVE PRICE. `>=` and not `>`: rewriting a row to the price it
            # already carries spends a row in the import file and moves nothing.
            skip(sku, REASON_NOT_A_MARKDOWN, row, listed=listed, new=new)
            continue

        hand = int(on_hand.get(sku, 0))
        picked.append(
            Candidate(
                sku=sku,
                row=row,
                listed=listed,
                new=new,
                live=live,
                on_hand=hand,
                room=max(0, live_cap - live),
                market=market,
                oldest=oldest,
                age_days=_age_days(oldest, moment),
                last_sold=last_sold.get(sku),
            )
        )

    # ORDERED BY WHAT THE MARKDOWN GIVES UP, DESCENDING, TIE-BROKEN ON SKU. Deterministic, and
    # it puts the rows worth reading first — which is what makes a `<pre>` of 390 rows usable
    # on the screen and what makes a truncated `--limit` run the N that matter most.
    picked.sort(key=lambda row: (-row.off, -row.listed, row.sku))
    if limit is not None and limit >= 0:
        plan.candidates = picked[:limit]
        plan.truncated = picked[limit:]
    else:
        plan.candidates = picked
    return plan


# ----------------------------------------------------------------------------- the write


def rows(plan: Plan) -> List[tcgcsv.Row]:
    """The rows an import file would carry. One per candidate, `Add to Quantity` forced to 0.

    THE ZERO IS ASSERTED TWICE AND NEITHER ONE IS REDUNDANT. Once against the input, where a
    quantity means the document is not what this command contracts to read and the whole file
    is refused; and once against the output, where `check_only_writable_changed` re-runs
    against the export original the way `join.import_rows` does — so a row that reached here
    by some other path still has to satisfy the single-writable-column rule.
    """
    out: List[tcgcsv.Row] = []
    for candidate in plan.candidates:
        source = candidate.row
        carried = (source.get(tcgcsv.QUANTITY_COLUMN, "") or "0").strip()
        if carried not in ("", "0"):
            raise NotAdditive(
                "{0} carries `{1}` {2!r}; this file would add copies as well as reprice. "
                "Re-download the export.".format(
                    candidate.sku, tcgcsv.QUANTITY_COLUMN, carried
                )
            )
        row = tcgcsv.set_writable(
            source, add_to_quantity=0, marketplace_price=candidate.new
        )
        tcgcsv.check_only_writable_changed(source, row)
        out.append(row)
    return out


def receipt(plan: Plan, source: dict, rule, basis: str, days: int) -> dict:
    """The record a written markdown leaves behind, and what a later run reads back.

    `skus` IS THE PART THAT IS READ AGAIN. It carries what each SKU was asking and what it
    was moved to, which is what makes the write reversible by inspection rather than by
    memory. The corpus carries the same two facts per SKU (D94) and is the ratchet guard's
    actual source, because a receipt directory can be deleted and an answer cannot be
    deleted without also giving the card its rule price back.
    """
    return {
        "export": source,
        "rule": str(rule),
        "basis": basis,
        "days": days,
        "candidates": len(plan.candidates),
        "copies": plan.copies,
        "off": str(plan.off),
        "truncated": len(plan.truncated),
        "skus": {
            row.sku: {
                "from": tcgcsv.format_price(row.listed),
                "to": tcgcsv.format_price(row.new),
                "live": row.live,
            }
            for row in plan.candidates
        },
    }
