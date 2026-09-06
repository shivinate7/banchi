"""Which live listings are not selling, and what each would be re-priced to (D100).

THE OPERATOR'S SENTENCE: *"export my live inventory back out (for cards I have listed and
aren't selling) and be able to mass re-edit the prices down (and then reupload it back)."*
This module is the decision half of that, and it is pure — no I/O, no `store` import, no
network. `cli/cmd_reprice.py` is what reads a file and writes one.

WHAT A RE-UPLOAD DOES, MEASURED RATHER THAN ASSUMED, because getting it wrong doubles a live
inventory. `Add to Quantity` is a DELTA added to the listing TCGplayer already holds, and
`TCG Marketplace Price` SETS that listing's price. Both halves are measured on the owner's
own data, and the second half is measured as a defect that already happened:

  * 72,701 real export rows — four fixtures plus twelve exports recorded into run
    directories — carry `Add to Quantity` = "0". So do all 649 of the rows on which
    TCGplayer simultaneously reported live copies. It is TCGplayer's own byte on a row it
    knows is live, which it could not be if the column meant *set the quantity to*.
  * 282 of the 288 live SKUs in the 2026-09-02 export carry exactly the price this pipeline
    last wrote into an import CSV. The price column edits the live listing in place.
  * Ten live SKUs held MORE copies than this pipeline ever pushed, and nine of them sit at
    exactly `2 x pushed - sold`. One import file was uploaded twice and every quantity on it
    was added twice. That is the defect this module is shaped to make unreachable.

SO NOTHING IS EVER DELETED AT TCGPLAYER TO LOWER A PRICE, and this module never proposes a
quantity. `Total Quantity` is not a writable column — there is no CSV route to lowering a
quantity even for a caller that wanted one — and every row every command here writes carries
`Add to Quantity` = 0. The rule is not "remember to write zero"; it is that the quantity is
not a variable in this module at all.

WHAT "NOT SELLING" CAN HONESTLY MEAN HERE, and it is less than it sounds. Three facts are
available and one is a proxy:

  1. LIVE NOW — `Total Quantity > 0` in the operator's My Pricing export. A fact, from
     TCGplayer, at the moment the file was downloaded.
  2. NO SALE HERE INSIDE THE WINDOW — `cards.state == "sold"` with its `state_at`, per SKU.
     A fact about THIS store's copies. Read from the card records and never from the event
     log: one of the 193 `sold` events on the owner's store carries no `sku` key, so a query
     over the log silently loses it, while all 186 sold CARD rows carry both a SKU and a
     `state_at`.
  3. OWNED LONGER THAN THE WINDOW — the oldest `captured_at` of any card that ever carried
     the SKU. **This is a proxy and it is the weak term.** It measures how long the card has
     been OWNED, not how long the listing has been live. The store cannot measure the
     second: `Listing` has no `first_listed_at`, and `live_as_of` is absent from all 443
     stored listing payloads, while `Listing.at` means "last touched" and 346 of those 443
     carry one timestamp — the D87 store-wide settlement. Every report this module produces
     prints the substitution in its own header, because a proxy nobody is told about is a
     lie.

  Term 3 counts every card that ever carried the SKU, departed ones included. A floor taken
  over on-hand copies alone moves FORWARD as the oldest copy sells, so a listing would get
  younger the longer it sat.

AND ONE AXIS THAT IS NOT A PROXY AT ALL. The export carries the operator's asking price and
TCGplayer's own `TCG Market Price` on the same row at the same instant, so "I am asking more
than the market" is readable from the file with no history and no inference. `--above-market`
is that filter, and it is the only term here that says anything about WHY a card is not
selling rather than merely that it has not.

WHAT NO AMOUNT OF WORK HERE CAN KNOW. The export carries no sales window, no sample size, no
last-sold date, no view or watcher count, and TCGplayer publishes none of those anywhere —
the `tcgplayer-csv` skill says so and D8 rests on it. There is no sales-velocity figure in
this product and this module does not invent one.

THE FLOOR IS D9's $0.40 AND IT BINDS HARD. Measured on the owner's real My Pricing export of
2026-09-01: 115 of the 441 live rows are already at or under it, and an undercut of 20% would
put 319 of them there. A row that cannot go lower is refused by name (`at_floor`) rather than
written as a no-op, because a no-op row in an upload is a press that did nothing and reads
like a press that did something.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from pipeline import pricing, tcgcsv

#: The price a markdown starts from. `pricing.BASES` is deliberately NOT widened to include
#: it. `basis` reaches `join` and `emit` through `cli/__main__.py`'s `choices=`, and there the
#: asking-price column is blank on 7,787 of the 7,802 rows in
#: `fixtures/pokemon_wide_export_untouched.csv` — a basis that reads it would leave
#: `TCG Marketplace Price` untouched on a listing run with nothing anywhere raising. It is
#: meaningful on exactly the rows this module looks at: a row TCGplayer reports LIVE, where
#: the cell is populated on 441 of 441 in the owner's real export.
BASIS_ASKING = "asking"

BASES: Tuple[str, ...] = (BASIS_ASKING, pricing.BASIS_MARKET, pricing.BASIS_LOW)

#: Every row this module ever puts in a file. Not a default, not a parameter, not reachable
#: from a flag — see the module header.
ADD_TO_QUANTITY = 0

# ------------------------------------------------------------------- why a row is not moved
#
# Named rather than counted, because "134 rows skipped" is the report that made the operator
# open the CSV to find out what happened.

SOLD_OUT = "sold_out"                    # the export carries the row with no live copies
NOT_THIS_STORE = "not_this_store"        # live at TCGplayer, no card here ever carried it
HELD = "held"                            # withheld in the corpus, and live (D49)
SOLD_RECENTLY = "sold_recently"          # a copy sold here inside the window
TOO_YOUNG = "too_young"                  # owned for less than the window
PRICED_RECENTLY = "priced_recently"      # this store answered this SKU's price in the window
NO_ASKING_PRICE = "no_asking_price"      # live with a blank `TCG Marketplace Price`
NO_BASIS = "no_basis"                    # the chosen basis column is blank or zero
NEAR_MARKET = "near_market"              # not far enough above `TCG Market Price`
AT_FLOOR = "at_floor"                    # already at $0.40; there is nowhere down to go
NOT_A_MARKDOWN = "not_a_markdown"        # the rule would raise the price, or leave it

SKIP_ORDER: Tuple[str, ...] = (
    HELD,
    SOLD_RECENTLY,
    TOO_YOUNG,
    PRICED_RECENTLY,
    NEAR_MARKET,
    AT_FLOOR,
    NOT_A_MARKDOWN,
    NO_ASKING_PRICE,
    NO_BASIS,
    NOT_THIS_STORE,
    SOLD_OUT,
)

SKIP_SENTENCE: Dict[str, str] = {
    SOLD_OUT: "TCGplayer holds no copies",
    NOT_THIS_STORE: "live at TCGplayer, never held here",
    HELD: "held back on purpose",
    SOLD_RECENTLY: "a copy sold inside the window",
    TOO_YOUNG: "owned for less than the window",
    PRICED_RECENTLY: "this store set the price inside the window",
    NO_ASKING_PRICE: "live with no asking price in the export",
    NO_BASIS: "the chosen basis column is blank",
    NEAR_MARKET: "not far enough above market",
    AT_FLOOR: "already at the floor",
    NOT_A_MARKDOWN: "the rule would not lower it",
}


class UnknownBasis(ValueError):
    """A basis this module does not offer. `pricing.UnknownBasis`'s local sibling."""


def check_basis(basis: str) -> str:
    if basis not in BASES:
        raise UnknownBasis(f"unknown basis: {basis!r}; expected one of {', '.join(BASES)}")
    return basis


def _parse_stamp(stamp: Optional[str]) -> Optional[datetime]:
    """An ISO stamp as an aware datetime; naive reads as UTC, garbage reads as None.

    Duplicated from `store/master.py` on purpose, the way `pipeline/livecheck.py` duplicates
    its own `_int`: this module does not import `store`, so a caller may drive it with plain
    strings and a harness may drive it with no database at all.
    """
    if not stamp:
        return None
    try:
        when = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when


def _before(stamp: Optional[str], cut: datetime) -> Optional[bool]:
    """True when `stamp` is strictly older than `cut`. None when it does not parse."""
    when = _parse_stamp(stamp)
    if when is None:
        return None
    return when < cut


def basis_price(row: tcgcsv.Row, basis: str = BASIS_ASKING) -> Optional[Decimal]:
    """The price a rule is applied to. `asking` here; the other two are `pricing`'s."""
    if check_basis(basis) == BASIS_ASKING:
        return tcgcsv.parse_price(row.get(tcgcsv.PRICE_COLUMN, ""))
    return pricing.basis_price(row, basis)


def asking_price(row: tcgcsv.Row) -> Optional[Decimal]:
    """What the operator is asking right now, per the export. Never a rule's output."""
    return tcgcsv.parse_price(row.get(tcgcsv.PRICE_COLUMN, ""))


def above_market_percent(
    asking: Optional[Decimal], market: Optional[Decimal]
) -> Optional[Decimal]:
    """How far above `TCG Market Price` the asking price sits, as a percentage.

    None where either side is missing or the market is zero — `pricing.has_market_data`'s
    rule, that a blank or $0.00 cell is UNKNOWN and never CHEAP, restated for a ratio that
    would otherwise divide by it.
    """
    if asking is None or not pricing.has_market_data(market):
        return None
    return (asking - market) * Decimal(100) / market


@dataclass
class Candidate:
    """One live SKU, as the export and this store describe it together."""

    sku: str
    row: tcgcsv.Row
    live: int
    asking: Optional[Decimal] = None
    market: Optional[Decimal] = None
    #: The oldest `captured_at` of any card that ever carried this SKU. A PROXY for how long
    #: the listing has been live — see the module header. `listed_since` supersedes it where
    #: the store has one, and this stays as the fallback for a SKU seen live only once.
    owned_since: Optional[str] = None
    #: `store/master.py:Listing.first_seen_live` — the earliest export that carried this SKU
    #: live. THE REAL TERM the module header's proxy was standing in for, available for a
    #: SKU no card here ever carried as much as for one photographed in a box.
    listed_since: Optional[str] = None
    #: Whether any card here has ever carried this SKU. DRAWN EVIDENCE AND NOT A GATE since
    #: 2026-09-06: it was a terminal refusal (`NOT_THIS_STORE`), and on the owner's store
    #: that refused 28 SKUs carrying 94.5% of the live book's asking value — a $2,000 box
    #: case asking $155 under market among them. What a card record buys is a photograph and
    #: a position, and neither is consulted to decide a price.
    held_here: bool = True
    #: The newest `state_at` of a card of this SKU marked sold here. None means never sold.
    last_sold: Optional[str] = None
    #: When this store last wrote a price answer for this SKU (`corpus.Answer.at`).
    priced_at: Optional[str] = None
    #: What the rule proposes. None on every skipped row.
    proposed: Optional[Decimal] = None
    #: Why this row is not moving, or None when it is.
    skip: Optional[str] = None

    @property
    def name(self) -> str:
        return self.row.get(tcgcsv.NAME_COLUMN, "")

    @property
    def condition(self) -> str:
        return self.row.get(tcgcsv.CONDITION_COLUMN, "")

    @property
    def line(self) -> str:
        return self.row.get(tcgcsv.PRODUCT_LINE_COLUMN, "")

    @property
    def listed_for(self) -> Optional[str]:
        """The stamp staleness is ranked on: the first sighting, else the ownership proxy.

        PREFERRED IN THAT ORDER because they answer different questions. `first_seen_live` is
        when TCGplayer was first observed holding this SKU, which is the thing `--days` claims
        to measure; `owned_since` is when a camera first saw a card, which on the owner's
        store made 184 of 387 live SKUs `too_young` against an oldest capture of 2026-08-23.
        A store with no sightings yet behaves exactly as it did before, proxy and all.
        """
        return self.listed_since or self.owned_since

    @property
    def above_market(self) -> Optional[Decimal]:
        return above_market_percent(self.asking, self.market)

    @property
    def at_risk(self) -> Decimal:
        """What the operator is currently asking for every live copy of this SKU.

        The ranking figure. `--limit` spends its budget on the rows carrying the most money,
        not on the most rows, because a hundred $0.40 commons and one $40 chase card are not
        the same press.
        """
        if self.asking is None:
            return Decimal(0)
        return self.asking * self.live

    @property
    def cut(self) -> Optional[Decimal]:
        """Per copy, what this proposal takes off."""
        if self.asking is None or self.proposed is None:
            return None
        return self.asking - self.proposed

    @property
    def given_up(self) -> Decimal:
        """Across every live copy, the asking value this proposal gives up."""
        cut = self.cut
        return Decimal(0) if cut is None else cut * self.live


@dataclass
class Plan:
    """What a markdown would do, before anything is written."""

    #: The rows that move, ranked by `at_risk` descending.
    rows: List[Candidate] = field(default_factory=list)
    #: Rows that qualified but fell below `--limit`. Named, never silently dropped.
    deferred: List[Candidate] = field(default_factory=list)
    #: Every other live row, by refusal code.
    skipped: Dict[str, List[Candidate]] = field(default_factory=dict)
    #: The parameters, echoed back, so a receipt says what it was asked.
    asked: Dict[str, object] = field(default_factory=dict)
    #: How many live rows were dated by each clock — `sighting` is `Listing.first_seen_live`,
    #: `ownership` the `captured_at` proxy, `neither` a row nothing can date. COUNTED SO THE
    #: REPORT CAN STOP GUESSING: the proxy paragraph was printed unconditionally on every
    #: report, and once a store has sightings that paragraph is false for the rows that have
    #: one. D100's rule is that a substitution nobody is told about is a lie; the same rule
    #: says a substitution that is not happening must not be claimed.
    dated: Dict[str, int] = field(default_factory=dict)

    @property
    def copies(self) -> int:
        return sum(row.live for row in self.rows)

    @property
    def asking_before(self) -> Decimal:
        return sum((row.at_risk for row in self.rows), Decimal(0))

    @property
    def asking_after(self) -> Decimal:
        return self.asking_before - sum((row.given_up for row in self.rows), Decimal(0))

    @property
    def considered(self) -> int:
        return len(self.rows) + len(self.deferred) + sum(
            len(group) for group in self.skipped.values()
        )

    def skips(self) -> List[Tuple[str, List[Candidate]]]:
        """Refusals in a fixed order, so two reports of the same store read the same."""
        return [(code, self.skipped[code]) for code in SKIP_ORDER if self.skipped.get(code)]

    def surveyed(self) -> List[Tuple[Candidate, str]]:
        """Every candidate this plan looked at, each with its standing. The lens's whole table.

        THE ORDER IS THE REPORT'S OWN — `rows` by `at_risk` desc, then `deferred`, then the
        refusals walked in `SKIP_ORDER` — so `skips`'s promise that two reports of one store
        read the same extends to the wire, and a screen drawing this top to bottom draws what
        the terminal printed.

        `standing` IS A THIRD STATE THAT `skip` CANNOT EXPRESS, which is the only reason it is
        here rather than derived. A `deferred` row — one that QUALIFIED and fell below
        `--limit` — carries `skip is None` exactly as an offered row does, so without this the
        difference between "the rule proposes this" and "the rule proposes this and you asked
        for fewer" is invisible. It is not a second fact that can disagree with `skip`: both
        are projections of one partition taken in one pass, and `standing == "refused"` is true
        exactly when `skip` is non-None.

        DELIBERATELY NOT A REFUSAL CODE FOR `deferred`. Those rows qualified, which is why
        `plan` keeps them out of `skipped` in the first place, and inventing a `below_limit`
        code would put a non-refusal into `SKIP_ORDER`, `SKIP_SENTENCE` and the report's
        refusal block.
        """
        out: List[Tuple[Candidate, str]] = [(row, "offered") for row in self.rows]
        out.extend((row, "deferred") for row in self.deferred)
        for _code, group in self.skips():
            out.extend((row, "refused") for row in group)
        return out


def plan(
    export_rows: Sequence[Mapping[str, str]],
    *,
    owned_since: Mapping[str, str],
    listed_since: Optional[Mapping[str, str]] = None,
    last_sold: Optional[Mapping[str, str]] = None,
    priced_at: Optional[Mapping[str, str]] = None,
    held: Optional[Sequence[str]] = None,
    now: Optional[datetime] = None,
    days: int = 7,
    rule: object = None,
    basis: str = BASIS_ASKING,
    above_market: Optional[Decimal] = None,
    limit: Optional[int] = None,
    floor: Decimal = pricing.FLOOR,
) -> Plan:
    """Rank the live listings this store would mark down, and name every row it would not.

    `owned_since` maps SKU to the oldest `captured_at` of any card that ever carried it, and
    `listed_since` to `Listing.first_seen_live` — the earliest export observed holding it.
    STALENESS RANKS ON `listed_since` WHERE THERE IS ONE, because that is the quantity
    `--days` has always claimed to measure; `owned_since` is the proxy it falls back to, and
    every report still names the substitution where one was made. A SKU absent from BOTH is
    one nothing can date, and it is reported `too_young` rather than priced on a guess — but
    a SKU absent from `owned_since` alone is merely one no card here carries, which is drawn
    as evidence and refuses nothing (it was a terminal refusal until 2026-09-06; see
    `Candidate.held_here`). `last_sold` and `priced_at` map SKU to a stamp; absent means
    never. `held` is the withheld SKUs from the corpus (D49), reported and never marked
    down.

    Nothing here reads a clock unless `now` is None, so a test drives its own window.
    """
    rule = pricing.Rule.parse(rule if rule is not None else pricing.MATCH)
    check_basis(basis)
    when = now or datetime.now(timezone.utc)
    cut_off = when - timedelta(days=days)
    listed_at = dict(listed_since or {})
    sold_at = dict(last_sold or {})
    answered_at = dict(priced_at or {})
    withheld = set(held or ())

    out = Plan(
        asked={
            "days": days,
            "rule": str(rule),
            "basis": basis,
            "above_market": None if above_market is None else str(above_market),
            "limit": limit,
            "floor": str(floor),
            "as_of": when.isoformat(timespec="milliseconds"),
            "cut_off": cut_off.isoformat(timespec="milliseconds"),
        }
    )

    def refuse(candidate: Candidate, code: str) -> None:
        candidate.skip = code
        out.skipped.setdefault(code, []).append(candidate)

    qualified: List[Candidate] = []
    for raw in export_rows:
        row = dict(raw)
        sku = str(row.get(tcgcsv.SKU_COLUMN, "")).strip()
        if not sku:
            # A blank SKU cannot be matched by an import and cannot be looked up here.
            # `pipeline/livecheck.py` skips it for the same reason.
            continue
        live = tcgcsv.parse_quantity(row.get(tcgcsv.LIVE_QUANTITY_COLUMN, ""))
        candidate = Candidate(
            sku=sku,
            row=row,
            live=live,
            asking=asking_price(row),
            market=tcgcsv.parse_price(row.get(tcgcsv.MARKET_PRICE_COLUMN, "")),
            owned_since=owned_since.get(sku),
            listed_since=listed_at.get(sku),
            held_here=sku in owned_since,
            last_sold=sold_at.get(sku),
            priced_at=answered_at.get(sku),
        )

        if live <= 0:
            refuse(candidate, SOLD_OUT)
            continue
        clock = (
            "sighting" if candidate.listed_since
            else "ownership" if candidate.owned_since
            else "neither"
        )
        out.dated[clock] = out.dated.get(clock, 0) + 1
        if sku in withheld:
            refuse(candidate, HELD)
            continue
        if _before(candidate.last_sold, cut_off) is False:
            refuse(candidate, SOLD_RECENTLY)
            continue
        if _before(candidate.listed_for, cut_off) is not True:
            # Not older than the window, or a stamp that does not parse. Both are "this
            # store cannot say it is old", and neither is licence to lower a price. READ
            # OFF `listed_for`, which prefers the first sighting to the ownership proxy —
            # so this is a statement about the LISTING wherever the store has seen one.
            refuse(candidate, TOO_YOUNG)
            continue
        if _before(candidate.priced_at, cut_off) is False:
            refuse(candidate, PRICED_RECENTLY)
            continue
        if candidate.asking is None:
            refuse(candidate, NO_ASKING_PRICE)
            continue
        if above_market is not None:
            margin = candidate.above_market
            if margin is None or margin <= above_market:
                refuse(candidate, NEAR_MARKET)
                continue
        if candidate.asking <= floor:
            refuse(candidate, AT_FLOOR)
            continue

        start = basis_price(row, basis)
        if not pricing.has_market_data(start):
            refuse(candidate, NO_BASIS)
            continue
        proposed = pricing.list_price(start, rule, floor)
        if proposed >= candidate.asking:
            refuse(candidate, AT_FLOOR if proposed <= floor else NOT_A_MARKDOWN)
            continue
        candidate.proposed = proposed
        qualified.append(candidate)

    qualified.sort(key=lambda c: (-c.at_risk, c.sku))
    if limit is not None and limit >= 0:
        out.rows = qualified[:limit]
        out.deferred = qualified[limit:]
    else:
        out.rows = qualified
    return out


# ----------------------------------------------------------------- reading the edits back


# A SKU THIS MARKDOWN NEVER SAW. It used to mean "not in the OFFER", and the widening is why
# it does not any more: the docstring's own argument for the refusal is *"there are no bytes to
# build a row from"*, and once `survey.json` carries every live row's bytes, that is no longer
# true of a row the plan merely declined to propose. The lens hands back prices for rows the
# rule refused — `near_market`, `too_young`, `priced_recently` — and every one of them has an
# export row on disk. What is left is what the refusal was always protecting: a typo'd id, or a
# row out of some other export, for which there genuinely are no bytes.
NOT_IN_WORKLIST = "not_in_worklist"      # a SKU this markdown's survey never saw
DUPLICATE = "duplicate"                  # the same SKU twice in one file (D7)
UNREADABLE = "unreadable"                # the price cell is not a number
BELOW_FLOOR = "below_floor"              # under $0.40, which TCGplayer will not take
RAISED = "raised"                        # above the live price. RETIRED as a refusal by D107 —
                                         # `read_back` lets an operator's raise through — and
                                         # kept in the vocabulary because receipts written
                                         # before that date carry it, and `reason_label` is
                                         # what renders them.
UNCHANGED = "unchanged"                  # equal to what the export reported

# THE TWO THE LENS ADDS, AND THEY ARE THE SURVEY'S OWN CODES RATHER THAN NEW VOCABULARY. A row
# the screen draws but must not push is refused here under the name the survey already gave it,
# so the sentence on the row and the sentence in the receipt are one string from one table. See
# `unpriceable=` on `read_back` for who decides membership.
# NARROWED TO ONE CODE ON 2026-09-06, and the removal is the point rather than the arithmetic.
# `SOLD_OUT` stays because there is no live listing for a price to edit — a fact about the
# LISTING, which is what this table is for. `NOT_THIS_STORE` was a fact about this store's
# CARD TABLE, and refusing on it meant the operator could not touch 94.5% of their own live
# book by asking value. What a card record buys is a photograph and a position; a price needs
# neither. The quantity path is untouched and still needs both — `pipeline/join.py`'s cap
# spends `live_cap - copies_out` over real positions, and nothing here writes a quantity
# (`ADD_TO_QUANTITY` is 0 and `check_quantities_zero` asserts it on the way out).
UNPRICEABLE_CODES: Tuple[str, ...] = (SOLD_OUT,)

EDIT_SENTENCE: Dict[str, str] = {
    NOT_IN_WORKLIST: "not a row this markdown's survey saw",
    DUPLICATE: "the same SKU appears twice",
    UNREADABLE: "the price cell is not a number",
    BELOW_FLOOR: "below the $0.40 floor",
    RAISED: "above the live price (a refusal until D107; kept for older receipts)",
    UNCHANGED: "the same price it is already listed at",
    # VERBATIM FROM `SKIP_SENTENCE`, not re-worded, so the survey and the apply cannot drift
    # into two descriptions of one fact.
    NOT_THIS_STORE: SKIP_SENTENCE[NOT_THIS_STORE],
    SOLD_OUT: SKIP_SENTENCE[SOLD_OUT],
}


@dataclass
class Edit:
    """One row of the worklist as the operator handed it back."""

    sku: str
    was: Optional[Decimal] = None
    now: Optional[Decimal] = None
    live: int = 0
    name: str = ""
    refusal: Optional[str] = None

    @property
    def cut(self) -> Optional[Decimal]:
        if self.was is None or self.now is None:
            return None
        return self.was - self.now


@dataclass
class Application:
    """What a worklist would upload, and every row it would not."""

    edits: List[Edit] = field(default_factory=list)
    refused: List[Edit] = field(default_factory=list)
    #: SKUs the OFFER was written for that the operator deleted from it. Not a refusal:
    #: deleting a line is how a person says "not this one".
    #:
    #: THE OFFER, NOT EVERY ROW THE MARKDOWN KNOWS ABOUT — see `read_back`'s `offered`. The two
    #: were the same set until the lens made `survey.json` carry every live row, and measured
    #: over the wider one this figure would tell an operator who priced three cards that they
    #: had deleted 438.
    dropped: List[str] = field(default_factory=list)

    @property
    def copies(self) -> int:
        return sum(edit.live for edit in self.edits)

    @property
    def given_up(self) -> Decimal:
        """Asking price surrendered across every copy — LOWERED ROWS ONLY.

        RAISES ARE NOT NETTED IN, and that is the whole point of the figure. It answers "what
        does pressing this cost me", and a raise is not a cost; letting one offset a markdown
        would report a file that cuts $40 and lifts $40 as free, which is the one reading an
        operator must not be given about their own money.
        """
        return sum(
            ((edit.cut or Decimal(0)) * edit.live for edit in self.edits
             if (edit.cut or Decimal(0)) > 0), Decimal(0)
        )

    @property
    def lowered(self) -> List[Edit]:
        return [e for e in self.edits if (e.cut or Decimal(0)) > 0]

    @property
    def raised(self) -> List[Edit]:
        """Rows the operator priced UP (D107). Named separately everywhere it is reported —
        a raise inside a thing called a markdown is exactly the row that must not be silent."""
        return [e for e in self.edits if (e.cut or Decimal(0)) < 0]

    @property
    def taken_on(self) -> Decimal:
        """Asking price added across every raised copy — `given_up`'s mirror."""
        return sum(
            ((-(edit.cut or Decimal(0))) * edit.live for edit in self.edits
             if (edit.cut or Decimal(0)) < 0), Decimal(0)
        )

    @property
    def fatal(self) -> List[Edit]:
        """Refusals that stop the whole file rather than one row.

        A duplicate SKU is undefined behaviour in an import (D7), and that is now the only
        one: a raised price used to be here on the grounds that it was "the one thing this
        command promises never to do", and D107 retired that promise rather than the guard —
        the rule still cannot propose a raise, and an operator still can.
        """
        return [e for e in self.refused if e.refusal == DUPLICATE]


def read_back(
    worklist_rows: Sequence[Mapping[str, str]],
    was: Mapping[str, str],
    *,
    live: Optional[Mapping[str, int]] = None,
    names: Optional[Mapping[str, str]] = None,
    floor: Decimal = pricing.FLOOR,
    offered: Optional[Sequence[str]] = None,
    unpriceable: Optional[Mapping[str, str]] = None,
) -> Application:
    """The operator's edited worklist, judged against what the export reported.

    ONLY TWO CELLS ARE READ: `TCGplayer Id` and `TCG Marketplace Price`. Every other column
    of the file the operator hands back is ignored, and the bytes that go into the upload
    come from the ORIGINAL export row the manifest kept. A spreadsheet reformats cells on
    open and on save — it strips a trailing zero, it re-renders a date, it drops a leading
    zero from a set number — and none of that can reach TCGplayer through this path, because
    the edited file is an instruction sheet and never a source of bytes.

    `was` maps SKU to the price the export reported, as a string. Compared as `Decimal` and
    never as text: a live export writes four decimal places ("0.6600") where this pipeline
    writes two ("0.66"), and those are equal as money and different as bytes. A string
    comparison would read every unedited row as a change and mark down the entire store.

    `offered` NARROWS WHAT COUNTS AS DELETED, AND WITHOUT IT THE LENS MAKES THE RECEIPT LIE.
    `dropped` is "SKUs this file was written for that the operator took out", and it was
    measured over `was` because those were the same set: the worklist and the manifest both
    held exactly the proposal. They are not the same set any more — `was` widens to every live
    row the survey saw so the lens can price one, while the OFFER is still the handful the rule
    proposed. Left alone, a screen handing back three edits out of 441 known rows would report
    438 rows deleted from a worklist that never had them. Absent means "measure it over `was`",
    which is what every caller written before the lens does and what T7 already asserts.

    `unpriceable` MAPS A SKU TO THE SURVEY'S OWN REFUSAL CODE, and a row in it is refused under
    that code however good its price is. It exists because the lens DRAWS rows it must never
    push: the 33 SKUs on the owner's export that TCGplayer lists and this store has never held
    (`not_this_store`), and rows the export carries with no live copies (`sold_out`). Both have
    bytes, so nothing upstream stops them; what stops them is that lowering the first would
    move a listing this pipeline did not create and cannot verify, and the second would edit
    nothing at all. Passing the survey's code rather than a boolean is what keeps one
    vocabulary between the row's sentence and the receipt's.
    """
    out = Application()
    seen: Dict[str, Edit] = {}
    quantities = dict(live or {})
    labels = dict(names or {})
    barred = dict(unpriceable or {})

    for raw in worklist_rows:
        sku = str(raw.get(tcgcsv.SKU_COLUMN, "")).strip()
        if not sku:
            continue
        edit = Edit(
            sku=sku,
            live=int(quantities.get(sku, 0)),
            name=labels.get(sku, str(raw.get(tcgcsv.NAME_COLUMN, ""))),
        )
        if sku in seen:
            edit.refusal = DUPLICATE
            out.refused.append(edit)
            continue
        seen[sku] = edit

        before = tcgcsv.parse_price(was.get(sku, ""))
        if sku not in was or before is None:
            edit.refusal = NOT_IN_WORKLIST
            out.refused.append(edit)
            continue
        edit.was = before

        # BARRED BEFORE THE PRICE IS EVEN READ, because no price makes these pushable. It sits
        # after the bytes check on purpose: "there is no row for this SKU" is a different
        # complaint from "there is a row and you may not move it", and the operator gets the
        # one that is true.
        if sku in barred:
            edit.refusal = barred[sku]
            out.refused.append(edit)
            continue

        try:
            after = tcgcsv.parse_price(raw.get(tcgcsv.PRICE_COLUMN, ""))
        except Exception:  # noqa: BLE001 - a spreadsheet can put anything in a cell
            after = None
        if after is None:
            edit.refusal = UNREADABLE
            out.refused.append(edit)
            continue
        edit.now = after

        # A RAISE GOES THROUGH, AND IT IS THE OPERATOR'S AND NEVER THE RULE'S (D107).
        #
        # `plan` still refuses its own proposal when it is not a markdown (NOT_A_MARKDOWN), so
        # nothing automatic can arrive here pointing up: a price above `was` is a number a
        # person typed, in the worklist or on `#/pricing`. Refusing it made the screen offer a
        # field it would not honour — the operator raised a price, the whole file was refused,
        # and the reason blamed the direction rather than the design.
        #
        # WHAT D100 ACTUALLY PROTECTS IS UNTOUCHED BY DIRECTION: `Add to Quantity` is 0 on
        # every row, nothing is deleted at TCGplayer, and a duplicate SKU is still fatal. Its
        # "safe to upload by accident" argument survives too, and points this way — a file
        # uploaded by mistake that RAISES costs sales until it is noticed, where one that
        # lowers sells stock at the wrong price and cannot be recalled.
        if after == before:
            edit.refusal = UNCHANGED
            out.refused.append(edit)
            continue
        if after < floor:
            edit.refusal = BELOW_FLOOR
            out.refused.append(edit)
            continue
        out.edits.append(edit)

    # OVER THE OFFER WHERE ONE WAS NAMED, AND OVER `was` OTHERWISE. See `offered` above for
    # why the two stopped being the same set, and `Application.dropped` for what the figure
    # means to the person reading the receipt.
    out.dropped = sorted(sku for sku in (was if offered is None else offered) if sku not in seen)
    return out


def import_rows(
    edits: Sequence[Edit], originals: Mapping[str, tcgcsv.Row]
) -> List[tcgcsv.Row]:
    """The rows to upload, built from the export's own bytes.

    `ADD_TO_QUANTITY` is written explicitly on every row rather than left as the export
    found it. The export's own cell is already "0" on all 72,701 rows measured, so this
    changes no byte on any file seen so far — and that is exactly why it is written: a
    column left alone is a column nobody is asserting, and the whole safety of this feature
    is the assertion. `tcgcsv.set_writable` then runs `check_only_writable_changed` on the
    way out, so a row that reached here mangled cannot be written at all.
    """
    rows: List[tcgcsv.Row] = []
    for edit in edits:
        original = originals.get(edit.sku)
        if original is None:
            raise KeyError(f"no export row kept for {edit.sku}")
        if edit.now is None:
            raise ValueError(f"no price decided for {edit.sku}")
        rows.append(
            tcgcsv.set_writable(
                original,
                add_to_quantity=ADD_TO_QUANTITY,
                marketplace_price=edit.now,
            )
        )
    return rows


def check_quantities_zero(rows: Sequence[Mapping[str, str]]) -> List[str]:
    """The SKUs of any rows carrying a non-zero `Add to Quantity`.

    The last gate before bytes reach a file, and the one that matters. A caller runs it over
    what it is about to write and refuses the FILE, not the row: a markdown upload carrying
    a quantity anywhere is not a markdown upload, and the measured cost of getting it wrong
    is nine SKUs on the owner's store sitting at twice what was pushed.
    """
    return [
        str(row.get(tcgcsv.SKU_COLUMN, "")).strip()
        for row in rows
        if tcgcsv.parse_quantity(row.get(tcgcsv.QUANTITY_COLUMN, "")) != 0
    ]
