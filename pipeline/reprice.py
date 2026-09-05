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
    #: the listing has been live — see the module header.
    owned_since: Optional[str] = None
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


def plan(
    export_rows: Sequence[Mapping[str, str]],
    *,
    owned_since: Mapping[str, str],
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

    `owned_since` maps SKU to the oldest `captured_at` of any card that ever carried it —
    a SKU absent from it is one this store has never held, which is a refusal and not a
    default. `last_sold` and `priced_at` map SKU to a stamp; absent means never. `held` is
    the withheld SKUs from the corpus (D49), which are reported and never marked down.

    Nothing here reads a clock unless `now` is None, so a test drives its own window.
    """
    rule = pricing.Rule.parse(rule if rule is not None else pricing.MATCH)
    check_basis(basis)
    when = now or datetime.now(timezone.utc)
    cut_off = when - timedelta(days=days)
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
            last_sold=sold_at.get(sku),
            priced_at=answered_at.get(sku),
        )

        if live <= 0:
            refuse(candidate, SOLD_OUT)
            continue
        if sku not in owned_since:
            refuse(candidate, NOT_THIS_STORE)
            continue
        if sku in withheld:
            refuse(candidate, HELD)
            continue
        if _before(candidate.last_sold, cut_off) is False:
            refuse(candidate, SOLD_RECENTLY)
            continue
        if _before(candidate.owned_since, cut_off) is not True:
            # Not older than the window, or a stamp that does not parse. Both are "this
            # store cannot say it is old", and neither is licence to lower a price.
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


NOT_IN_WORKLIST = "not_in_worklist"      # a SKU the worklist was never written for
DUPLICATE = "duplicate"                  # the same SKU twice in one file (D7)
UNREADABLE = "unreadable"                # the price cell is not a number
BELOW_FLOOR = "below_floor"              # under $0.40, which TCGplayer will not take
RAISED = "raised"                        # above what the export reported. Never on this path.
UNCHANGED = "unchanged"                  # equal to what the export reported

EDIT_SENTENCE: Dict[str, str] = {
    NOT_IN_WORKLIST: "not a row this worklist was written for",
    DUPLICATE: "the same SKU appears twice",
    UNREADABLE: "the price cell is not a number",
    BELOW_FLOOR: "below the $0.40 floor",
    RAISED: "above the live price; this path only lowers",
    UNCHANGED: "the same price it is already listed at",
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
    #: SKUs the worklist was written for that the operator deleted from it. Not a refusal:
    #: deleting a line is how a person says "not this one".
    dropped: List[str] = field(default_factory=list)

    @property
    def copies(self) -> int:
        return sum(edit.live for edit in self.edits)

    @property
    def given_up(self) -> Decimal:
        return sum(
            ((edit.cut or Decimal(0)) * edit.live for edit in self.edits), Decimal(0)
        )

    @property
    def fatal(self) -> List[Edit]:
        """Refusals that stop the whole file rather than one row.

        A duplicate SKU is undefined behaviour in an import (D7) and a raised price is the
        one thing this command promises never to do. Neither is a row to skip past.
        """
        return [e for e in self.refused if e.refusal in (DUPLICATE, RAISED)]


def read_back(
    worklist_rows: Sequence[Mapping[str, str]],
    was: Mapping[str, str],
    *,
    live: Optional[Mapping[str, int]] = None,
    names: Optional[Mapping[str, str]] = None,
    floor: Decimal = pricing.FLOOR,
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
    """
    out = Application()
    seen: Dict[str, Edit] = {}
    quantities = dict(live or {})
    labels = dict(names or {})

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

        try:
            after = tcgcsv.parse_price(raw.get(tcgcsv.PRICE_COLUMN, ""))
        except Exception:  # noqa: BLE001 - a spreadsheet can put anything in a cell
            after = None
        if after is None:
            edit.refusal = UNREADABLE
            out.refused.append(edit)
            continue
        edit.now = after

        if after > before:
            edit.refusal = RAISED
            out.refused.append(edit)
            continue
        if after == before:
            edit.refusal = UNCHANGED
            out.refused.append(edit)
            continue
        if after < floor:
            edit.refusal = BELOW_FLOOR
            out.refused.append(edit)
            continue
        out.edits.append(edit)

    out.dropped = sorted(sku for sku in was if sku not in seen)
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
