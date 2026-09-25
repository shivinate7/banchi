"""Catalog join — identified cards to TCGplayer SKU rows.

Join key is `zfill(3)(number) + "/" + printedTotal`. The shape follows pokemontcg.io's
schema — `printedTotal` is their field name — but at runtime both values come from the
identification, matched against the export's `Number` column. Nothing here calls that API;
`harness/eval/fixtures.py` is the only caller, for T1's labelled fixtures.

Secret rares exceed the denominator in the same format (`161/159`) and are ordinary, not
invalid. Product Name is NEVER a join key — it inconsistently embeds the number
("Accelgor" in one row, "Black Belt's Training - 143/159" in another). Name matching
exists only as a fallback for the rare catalog rows whose `Number` is blank.

THAT KEY IS THE FORM A HUMAN READS; MATCHING GOES THROUGH `number_index_key`, ON BOTH SIDES.
The index and the lookup disagreed about padding until 2026-08-23 — verbatim cells one side,
`zfill(3)` the other — which silently missed every card in an unpadded export and reported
it as `no_catalog_row`. That function's docstring holds the measurement and the fold.

WHICH KEY A CARD IS LOOKED UP BY IS PER GAME (D21, D25), dispatched through
`JOIN_KEY_STRATEGIES` below: Pokemon composes two printed halves, Riftbound and One Piece
match one printed identifier verbatim, code cards go by name, and `misc` never joins at all.

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

import bisect
import math
import re
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from decimal import Decimal
from difflib import SequenceMatcher
from typing import (
    Callable, Dict, Iterable, List, Mapping, NamedTuple, Optional, Sequence, Set, Tuple,
)

from pipeline import games, pricing, routing, setnames, tcgcsv, variant
# THE COMPOSITION/SCREEN/STRIP TRIO LIVES IN `store/numbers.py` NOW, RE-EXPORTED HERE UNDER
# THE SAME NAMES (store-scaling item 8, fixing a `store/` -> `pipeline/` cycle a reviewer
# caught). `store/` may not import `pipeline/` (D63: "store/ imports nothing from
# pipeline/, so there is no cycle" — the arrow runs the other way, `pipeline/orders.py` and
# friends import `store`), and `store/master.py`/`store/db.py` both need these three pure
# functions to populate `cards.number_key`/`number_display` without re-deriving the
# zfill/set-code-strip rules a third time. Every existing caller of `join.join_key` /
# `join.display_number` / `join.strip_set_code` is unaffected — the names still resolve on
# this module, they just live one file over.
from store import master
from store.numbers import (  # noqa: F401
    NAME_NUMBER_SUFFIX,
    box_title,
    display_number,
    join_key,
    split_catalog_number,
    strip_set_code,
)
from store.numbers import catalog_number_fields as _catalog_number_fields_by_strategy


def catalog_number_fields(game: str, raw_number) -> Tuple[Optional[str], Optional[str]]:
    """The `(number, printed_total)` pair a CORRECTED card should carry, off a catalog row's
    raw `Number` cell — the reverse of `_key_number_and_printed_total`/`_key_printed_code`
    above, driven by the SAME `games.get(game)["join_key"]` strategy those two dispatch on,
    so a corrected card's stored pair is the pair `identify/prompt.py`'s own writer for that
    game would have produced, and `number_key`/`number_display` come out identical to a
    fresh identification's.

    GAME-AWARE THROUGH THE REGISTRY, NEVER A HAND-TYPED GAME LIST — reading
    `games.get(game)["join_key"]` (this module's own edge into `pipeline/games.py`) and
    handing the STRATEGY NAME, never the game, to `store/numbers.catalog_number_fields`
    (review finding, identity-follows-sku.md lane 1, 2026-09-24 — moved there so
    `store/master.py:bind_sku` can derive the identical pair off a `skus` table row without
    `store/` importing this registry, D63). A THIRD strategy value never falls through
    silently: `store/numbers.catalog_number_fields` lands it in the verbatim branch, the
    safe default for a game this function has never heard of, exactly as
    `_key_printed_code` is the safe fallback shape for one.

    THIS FUNCTION IS NOW A TWO-LINE DELEGATOR. The dispatch rule itself — `number_and_
    printed_total` (Pokemon) reverses `split_catalog_number`; every other strategy
    (`printed_code` for Riftbound/One Piece, `name_only`, `not_joined`, or one this module
    has never heard of) stores the cell verbatim and leaves `printed_total` empty — is
    argued in full on `store/numbers.catalog_number_fields`'s own docstring, not restated
    here. Every existing caller (`identify/prompt.py`, T3, T7) is unaffected: the name, the
    signature and the game-keyed behaviour are all unchanged.
    """
    strategy = games.get(game)["join_key"]
    return _catalog_number_fields_by_strategy(strategy, raw_number)

# D7 — a playset. Configurable, but never guessed at. RE-EXPORTED rather than defined: the
# figure lives in `pipeline/pricing.py`, which both this module and `pipeline/corpus.py`
# import and neither of which imports the other, so the store-wide policy key and this
# default cannot drift apart. Every caller and every document still spells it
# `join.LIVE_QUANTITY_CAP`.
LIVE_QUANTITY_CAP = pricing.LIVE_QUANTITY_CAP

class OutputSuppressed(Exception):
    """emit_import refused: something was unmatched and has not been reported yet."""


class EmptyCatalog(Exception):
    """`Catalog.from_export` filtered a game's rows out of an export and found none.

    THE WRONG FILE, AND THE ONE CASE WHERE STOPPING BEATS CONTINUING (D25). Every other
    join failure is per-card — a card with no row reviews, at a known position, while the
    rest of the run proceeds. Zero rows is not per-card: it says the export handed to this
    game carries none of its product line at all, so every card of the game would queue as
    `no_catalog_row` and the report would point at 53 cards instead of at one flag. The
    remedy is a different file, and a refusal is what says so.
    """


@dataclass(frozen=True)
class Position:
    """D10 — sequential, assigned at capture. Sold cards leave permanent gaps IN THE INDEX;
    indices are never renumbered. Since D58 the LABEL closes over one — see below.

    THE INDEX IS THE IDENTITY; THE LABEL IS A VIEW OF THE BOX'S CURRENT LAYOUT. `sections`
    is the box's divider indices — `(1, 31, 56)` means section 2 starts at card 31 — and
    editing it relabels every card behind the moved divider without touching a single index.
    D10 (amended) accepts that: correcting a wrong layout is the point, and the label was
    never printed on anything, only ever read live off a screen.

    AN UNDECLARED BOX IS ONE SECTION, AND THERE IS NO SUCH THING AS AN AUTOMATIC DIVIDER
    ANY MORE (D10, amended 2026-08-29 by the owner). An empty `sections` used to be rendered
    by `CARDS_PER_SECTION = 25` — a module constant no env var, flag or parameter could
    reach, which cut a divider into every undeclared box every twenty-five cards whether or
    not one was physically there. Box 1 holds 133 cards and no dividers at all, and the app
    drew it as six sections; a person sent to `Section 4 · Card 8` would have been counting
    for a boundary the plastic does not have.

    So the fallback is `(1,)` — the one divider every box really has, at its front — and a
    divider now exists only because somebody put one in and said so (the capture screen's
    `S`, or the dividers editor). `card` is then the index, `section` is 1, and
    `section_end` is None: an undeclared box's one section runs to wherever the box stops,
    which is D20's own reason for that None and not a new rule.

    A CARD'S NUMBER COUNTS THE CARDS IN THE BOX, NOT THE SLOTS (D58, 2026-08-30). `occupied`
    is every ON-HAND index in this box, ascending — the cards a person would count if they
    opened it — and where it is given, every number below is rendered in that space instead
    of in index space. `Card 17` is then the seventeenth card you can count rather than the
    seventeenth slot, which is the distinction `docs/specs/order-flow.md` §10.4 spends its
    length on and D30 was waiting on a physical marker to explain.

    THE INDEX STILL NEVER MOVES, AND THAT IS WHAT MAKES THIS CHEAP. D10 as amended already
    draws this seam — *"positions are never renumbered" governs the INDEX; the label is a
    view* — so nothing here writes anything: no photograph is renamed, no queue entry is
    re-keyed, no history line changes subject. `index` remains the store key, the route
    path and what every write aims by.

    AN EMPTY `occupied` MEANS INDEX SPACE, WHICH IS EXACTLY WHAT THIS CLASS DID BEFORE.
    Every caller that has no inventory to consult — T3, T4 and T5 all build a bare
    `Position(box, index)` — renders byte-identically to the day before this landed. That
    is the compatibility guarantee, and it is also the hazard: a caller that COULD consult
    the store and does not renders a second spelling of one address. T7 asserts the server
    and `cli/resolve.py` agree on the label for one card, which is the only guard against
    it.

    THIS IS THE ONLY LABEL FORMULA IN THE REPO (`docs/specs/capture-server.md` §6.3). The
    TypeScript side receives rendered strings and never computes a section.
    """

    box: int
    index: int
    sections: Tuple[int, ...] = ()
    # Every on-hand index in this box, ascending, or `()` for "render in index space".
    # A TUPLE because this dataclass is frozen, for `IdentifiedCard.metadata_finish`'s
    # reason: a frozen carrier of a mutable member is a hashability bug waiting for its
    # first `set()`.
    #
    # `None` AND `()` ARE OPPOSITE FACTS AND THE SENTINEL HAS TO BE `None`. An empty tuple
    # is a box with nothing on hand — every card in it has sold — and that box's cards must
    # still render as departed rather than reverting to slot numbers. `None` is the caller
    # saying it has no inventory to consult at all.
    occupied: Optional[Tuple[int, ...]] = None
    # The box's terminal indices, ascending — the cards that have LEFT. Only ever read
    # together with `occupied`, and only to tell the part of the box that exists from the
    # part that does not: see `high_water`.
    departed: Tuple[int, ...] = ()
    # THE BOX'S NAME, AS THE REGISTRY HOLDS IT, OR None WHEN THE CALLER HAS NO REGISTRY TO ASK
    # (D259). The owner's ruling, 2026-09-23: a box is shown by its
    # name only, and the number stays inside the store. `box_title` below is what the label
    # says. `compare=False` because a name is a label and never part of the card's identity:
    # a rename must not make two positions of one card unequal.
    box_name: Optional[str] = field(default=None, compare=False)
    # WHERE THE CARD STANDS IN ITS BOX'S ORDER (D265), or None when the order is the index.
    # `(this card's order, occupied in order space, departed in order space)`. `index`,
    # `occupied` and `departed` above stay the STORE's, because callers key writes by them.
    # Every number below is counted in this space instead. `BoxView.at` fills it.
    ordered: Optional[Tuple[int, Optional[Tuple[int, ...]], Tuple[int, ...]]] = field(
        default=None, compare=False
    )

    def _front(self) -> Tuple:
        """The dividers with the front of the box set by the one rule (`master.front_of_box`)."""
        lows = [v[0] for v in (self._occ or (), self._dep or ()) if v]
        return master.front_of_box(self.sections, min(lows) if lows else None)

    @property
    def _i(self) -> int:
        return self.index if self.ordered is None else self.ordered[0]

    @property
    def _occ(self) -> Optional[Tuple[int, ...]]:
        return self.occupied if self.ordered is None else self.ordered[1]

    @property
    def _dep(self) -> Tuple[int, ...]:
        return self.departed if self.ordered is None else self.ordered[2]

    @property
    def consolidated(self) -> bool:
        """Whether this label counts cards (D58) or slots (the shape before it)."""
        return self.occupied is not None

    @property
    def slot(self) -> Optional[int]:
        """This card's number among the cards actually in the box, or None where it has
        none: a card that has left (`sold`, `retired`) is in no slot at all.

        None rather than the slot it used to hold, because that number belongs to the card
        that closed up behind it — handing it to a departed record would send a person to
        the wrong card. `departed_label` is what a screen draws instead, on the same
        argument `pooled_label` makes one paragraph down for a card that never had a slot.

        In index space every card has a slot and it is its index, departed or not, which is
        what keeps the pre-D58 rendering intact.
        """
        if not self.consolidated:
            return self._i
        occupied = self._occ or ()
        at = bisect.bisect_left(occupied, self._i)
        if at < len(occupied) and occupied[at] == self._i:
            return at + 1
        return None

    @property
    def layout(self) -> Tuple[int, ...]:
        """The dividers this label is rendered against, in the same space as `slot`: the
        box's own, or the implicit one at the front of an undeclared box.

        The three properties below all read THIS rather than `sections`, so the undeclared
        case is stated once instead of being re-decided three times — which is what the old
        default was, and two of its three branches did their own arithmetic. `sections`
        stays exactly as it was given, because "has this box declared a layout" is a real
        question with real callers (`BoxOps` draws `undeclared` from it) and normalising it
        here would answer that question wrongly for all of them.

        CONSOLIDATED, EACH DIVIDER MOVES TO THE COUNT OF CARDS IN FRONT OF IT, WHICH IS
        WHAT MAKES `Card M` COUNTABLE TOO (D58). A divider declared at index `s` sits in
        front of the first card still on hand at or above `s`, so its number is the count
        of cards below `s`, plus one. Both `slot` and `section_start` then move by the same
        amount for a departure in an earlier section, and `card` — their difference — does
        not: a sale in section 1 leaves every number in section 3 alone, and only a sale in
        section 3 and in front of the card moves it. That is the whole point of mapping the
        dividers rather than only the cards.

        DUPLICATES ARE KEPT RATHER THAN DEDUPED, so an emptied section keeps its NUMBER.
        Two dividers with no card left between them map to one value, and collapsing them
        would renumber every section behind — sending a person to the wrong divider, which
        is still physically in the box. `section` counts dividers, so the empty one keeps
        its ordinal and simply holds nothing.
        """
        declared = self._front()
        if not self.consolidated:
            return declared
        return tuple(self._divider(start) for start in declared)

    @property
    def high_water(self) -> int:
        """The highest index this box has reached, departed cards included, or 0.

        The seam between the box that EXISTS and the box that does not yet. Below it every
        slot has been allocated, so counting cards is the whole answer; above it nothing has
        been captured, so a declared divider up there is a plan and the slots between are
        waiting to be filled.
        """
        occupied, departed = self._occ, self._dep
        return max(
            occupied[-1] if occupied else 0,
            departed[-1] if departed else 0,
        )

    def _divider(self, start: int) -> int:
        """One declared divider's number, in `slot`'s space.

        THE COUNT OF CARDS THAT WILL BE IN FRONT OF IT, PLUS ONE. Inside the box that is
        the cards on hand below it; past the box's end it is those plus one for each slot
        the operator has declared and not yet filled — which is what keeps a layout typed in
        before the box was filled saying what was typed. `[1, 51]` on a five-card box means
        section 2 starts at the fifty-first CARD, and answering "the fifth" instead would
        quietly delete a plan.

        The two agree everywhere below `high_water`, so this correction is invisible on
        every box that has grown into its own dividers.
        """
        ahead = bisect.bisect_left(self._occ or (), start)
        # `ceil` keeps this a count of slots when the box's keys are fractions (D265). For a
        # whole-number key it is `start - 1 - high_water`, exactly as before.
        unfilled = max(0, math.ceil(start - self.high_water) - 1)
        return ahead + unfilled + 1

    @property
    def section(self) -> int:
        at = self.slot
        if at is None:
            # A DEPARTED CARD IS COUNTED IN INDEX SPACE, AGAINST THE DECLARED DIVIDERS. It is in
            # no slot, so the count-space answer (the slot it would take) is wrong at a
            # section's end: a sold last card of section 1 would take the number section 2's
            # divider maps to, and read as section 2. The declared dividers are indices, and
            # the index never moves (D10), so the section it left is the one whose divider is
            # the last at or before its index.
            count = sum(1 for start in self._front() if start <= self._i)
            return max(1, count)
        count = 0
        for start in self.layout:
            if at >= start:
                count += 1
            else:
                break
        # A number before the first divider cannot happen with a validated layout (it
        # starts at 1), but clamping beats returning 0 for a hand-edited file.
        return max(1, count)

    @property
    def section_start(self) -> int:
        """The number this card's section begins at, in `slot`'s space."""
        return self.layout[self.section - 1]

    @property
    def section_end(self) -> Optional[int]:
        """The last number in this card's section, or None when it is the final one.

        None rather than a guess: the final section runs to wherever the box ends, and only
        the caller holding the box's total knows where that is (D20). An undeclared box has
        exactly one section, so it takes this None on its first card — correctly, and for
        the same reason.
        """
        layout = self.layout
        if self.section < len(layout):
            return layout[self.section] - 1
        return None

    @property
    def card(self) -> Optional[int]:
        """This card's number within its section, or None for a card that has left."""
        at = self.slot
        if at is None:
            return None
        return at - self.section_start + 1

    @property
    def was_card(self) -> Optional[int]:
        """Where a departed card stood, as a number in its section today, or None when the
        card is on hand (`card` answers then).

        THE NUMBER THE CARD WOULD HOLD IF IT WENT BACK WHERE IT WAS: one more than the cards
        on hand in its section in front of it. The owner's ruling, 2026-09-23: a departed
        card's label keeps its place (box name, section, card within the section), and a
        visual mark, not a word, says that it left. D58 still holds for every LIVE number:
        this card is in no slot, and the card that closed up behind it now answers to the same
        number. The screen draws the two apart by the mark, never by the string.
        """
        if self.card is not None:
            return None
        at = bisect.bisect_left(self._occ or (), self._i) + 1
        return max(1, at - self.section_start + 1)

    @property
    def box_title(self) -> str:
        """What the label calls this box: its name, or the default name when it has none."""
        return box_title(self.box_name, self.box)

    @property
    def label(self) -> str:
        """`Mixed Singles, Section 2, Card 17`: the box's NAME, the section, and the card's
        number within its section (D260).

        NO TYPED SEPARATOR (D218). The parts are joined by a comma and a space, which is
        punctuation in a sentence a person reads aloud, so the string is the accessible name
        as it stands. A screen that draws the parts apart reads them with
        `app/src/position.ts:placePartsOf`, which parses from the right end, because a box
        name is free text and may hold a comma of its own.
        """
        at = self.card
        if at is None:
            return departed_label(self.box_title, self.section, self.was_card or 1)
        return place_label(self.box_title, self.section, at)


# `box_title` lives in `store/numbers.py` (imported above), so the store's own refusals and
# every label here share one fallback.


def place_within_section(section: int, card: int) -> str:
    """`Section 2, Card 17`: the section and the card's number within it, with NO box name.

    For a list of many cards from ONE box (`renumber_blocked`, `claim_not_stocked_by_game`,
    `box_not_empty_of_commitments`), where the box's name is already said once in the
    sentence the list sits inside — repeating it on every line would be the box number's
    own defect one word over. `place_within_box` is the caller that reaches this per card.
    """
    return f"Section {int(section)}, Card {int(card)}"


def place_label(box_name: str, section: int, card: int) -> str:
    """The one place label formula (D58, D259): name, section, card."""
    return f"{box_name}, {place_within_section(section, card)}"


def box_view(inventory, box) -> Tuple[str, "BoxView"]:
    """The box's title and its `BoxView` — on-hand indices, departed indices and declared
    sections, scanned ONCE. `said_place` and `place_within_box` both build a `Position`
    through the `BoxView` this returns, so every place a refusal names — the box alone, one
    card, or a whole list of a box's cards — comes from the one scan and the one formula.

    NEVER RAISES. An unreadable index, a layout that will not validate, or a box the
    registry has never seen all degrade to the box's title over an empty `BoxView` — the
    same fallback a caller with nothing to build from gets, never a second exception that
    hides the first (a refusal is already the error path).
    """
    try:
        number = int(box)
    except (TypeError, ValueError):
        return str(box), BoxView()
    try:
        entry = inventory.box(number)
    except Exception:  # noqa: BLE001 — a refusal must not raise a second error
        entry = None
    title = box_title(entry.name if entry is not None else None, number)
    try:
        on_hand: List[int] = []
        gone: List[int] = []
        for _key, (raw_index, raw_game, state) in inventory.cards.select(
            ("idx", "game", "state"), box=number
        ):
            if not is_located(str(raw_game or games.DEFAULT_GAME)):
                continue
            position = int(raw_index)
            (gone if state in master.TERMINAL_STATES else on_hand).append(position)
        try:
            sections = tuple(inventory.sections_for(number))
        except Exception:  # noqa: BLE001 — an unreadable layout reads as one section
            sections = ()
        view = BoxView(
            sections=sections,
            occupied=tuple(sorted(on_hand)),
            departed=tuple(sorted(gone)),
            name=title,
            order=inventory.box_order(number),
        )
    except Exception:  # noqa: BLE001 — a refusal must not raise a second error
        view = BoxView(name=title)
    return title, view


def said_place(inventory, box, index=None) -> str:
    """Where a refusal says a box or a card is: the box's NAME, and for a card its section
    and its card number within the section. THE ONE HELPER every server refusal speaks
    through (the orchestrator's call on the locating review, 2026-09-24).

    THE OWNER'S RULING, 2026-09-23 (D259): the box number and the
    store index stay inside the store. A refusal reaches a screen as a toast, so a message
    that prints `Box 3, card 17` shows the owner both numbers the ruling hides. This builds
    the same `Position` the screens draw, through `box_view`, so the refusal and the card
    row spell one place.

    `index=None` answers the box alone: its name. So does an index that holds no record,
    because a place with no card has no section and no card number to say.

    IT NEVER RAISES. A refusal is already the error path; a store too broken to place the
    card (an unreadable index, a layout that will not validate) degrades to the box's name,
    never to a second exception that hides the first.
    """
    title, view = box_view(inventory, box)
    if index is None:
        return title
    try:
        number = int(box)
        at = int(index)
    except (TypeError, ValueError):
        return title
    if at not in (view.occupied or ()) and at not in (view.departed or ()):
        return title
    try:
        return view.at(number, at).label
    except Exception:  # noqa: BLE001 — a refusal must not raise a second error
        return title


def place_within_box(view: "BoxView", box, index) -> str:
    """`Section 2, Card 17`: the same numbers `said_place` would give this card, with no box
    name — for a caller labelling MANY cards from one already-scanned `box_view`.

    Falls back to `card <index>`, the pre-ruling shape, only where a `Position` cannot be
    built for it — the index is not one `box_view` found, or the layout will not resolve. A
    refusal is already the error path and must not raise a second one over a label.
    """
    try:
        number = int(box)
        at = int(index)
    except (TypeError, ValueError):
        return f"card {index}"
    if at not in (view.occupied or ()) and at not in (view.departed or ()):
        return f"card {index}"
    try:
        position = view.at(number, at)
    except Exception:  # noqa: BLE001 — a refusal must not raise a second error
        return f"card {index}"
    card = position.card
    if card is None:
        card = position.was_card or 1
    return place_within_section(position.section, card)


# --------------------------------------------------------------- pooled, not located
#
# The owner's ruling ("Code cards are pooled inventory, not located", docs/DECISIONS.md):
# a code card has no box, section or card position — it is a count. The index survives as
# a KEY, because the photo and sidecar are named after it, but `Position.label` is never
# rendered for one: a label names a slot somebody carries to a shelf, and there is no slot.
# The seam is `pipeline/games.py`'s `located` flag, and these three helpers are its render
# side. They live beside `Position.label` deliberately — that property's docstring calls
# itself the only label formula in the repo, and the string that REPLACES a label belongs
# next to it for the same reason: a second spelling of the pooled fact, composed ad hoc at
# each surface, is a vocabulary nothing audits.


def is_located(game: str) -> bool:
    """Whether this game's cards have a physical position to render at all.

    True for an unregistered game string, deliberately. An unknown game never survives to
    a report through the join — `lookup_for` refuses it by name first — so the only caller
    that can arrive here holding one is a reporter describing a record that predates the
    registry, and the status-quo rendering (the label) is the answer that changes nothing.
    """
    try:
        return bool(games.get(game)["located"])
    except games.UnknownGame:
        return True


def pooled_label(game: str) -> str:
    """What a screen shows where a position label would have gone, for a pooled card.

    The game's display name and the word `pooled` — never `Box N · Section N · Card N`.
    One composer, reached by `server/capture_server.py` and `cli/resolve.py` both, so the
    capture answer and the queue entry cannot come to spell the pooled fact differently.
    """
    try:
        display = str(games.get(game)["display"])
    except games.UnknownGame:
        display = str(game)
    return f"{display} · pooled"


@dataclass(frozen=True)
class BoxView:
    """One box's label coordinates, and the one way to build a `Position` against them.

    D58 gave `Position` two more inputs, and both are facts about the BOX rather than about
    the card — so a caller rendering a whole box would otherwise pass the same two tuples to
    every position it built, and a caller rendering one card would have to remember that
    they exist at all. This is that pair with a name, and `at()` is the constructor every
    consolidated call site goes through.

    AN EMPTY `BoxView()` IS INDEX SPACE, which is what a caller with no inventory to consult
    gets — and it is `Position`'s own default said once instead of at every call.

    IT IS NOT A CACHE AND HOLDS NO DENOMINATOR. `on_hand` is derived, so a `BoxView` cannot
    come to disagree with the list it was built from; a stored total is exactly the second
    copy D20 refuses to put on the wire.
    """

    sections: Tuple[int, ...] = ()
    occupied: Optional[Tuple[int, ...]] = None
    departed: Tuple[int, ...] = ()
    # The box's registry name, carried to every `Position` built here, so a label says the
    # name (D259). None where the caller has no registry to ask.
    name: Optional[str] = None
    # THE BOX'S ORDER (D265). `occupied` and `departed` stay in INDEX space, because every
    # caller asks "is this index here" of them. `sections` is already in order space (it is
    # `Box.sections`). `at()` hands `Position` orders, so the one label formula counts the
    # cards in the order they stand, and never needs to know an order exists.
    order: master.BoxOrder = field(default=master.BoxOrder(), compare=False)

    @property
    def on_hand(self) -> int:
        """How many cards are in this box — the denominator every number here counts to."""
        return len(self.occupied or ())

    def _ordered(self) -> Tuple[Optional[Tuple[int, ...]], Tuple[int, ...]]:
        """`occupied` and `departed` in order space, computed once per view."""
        cached = self.__dict__.get("_ordered_cache")
        if cached is None:
            of = self.order.of
            occupied = (
                None if self.occupied is None else tuple(sorted(of(i) for i in self.occupied))
            )
            cached = (occupied, tuple(sorted(of(i) for i in self.departed)))
            object.__setattr__(self, "_ordered_cache", cached)
        return cached

    def at(self, box: int, index: int) -> "Position":
        if self.order.identity or self.occupied is None:
            return Position(
                int(box), int(index), self.sections, self.occupied, self.departed,
                box_name=self.name,
            )
        occupied, departed = self._ordered()
        return Position(
            int(box), int(index), self.sections, self.occupied, self.departed,
            box_name=self.name, ordered=(self.order.of(index), occupied, departed),
        )


def divider_index(
    ordinal: int, occupied: Sequence[int], departed: Sequence[int] = ()
) -> int:
    """`Position._divider` run backwards: the index a divider drawn at `ordinal` sits at.

    THE EDITOR SPEAKS THE NUMBERS ON THE SCREEN AND THE STORE KEEPS INDICES (D58). A box's
    dividers are stored in index space and always will be — the same argument the index
    itself gets, and D56's: a layout rewritten every time a card sells is an answer that can
    drift and that nobody can correct. But `sections_detail` renders them in count space, so
    an operator typing "section 3 starts at the 168th card" is typing a number they can see,
    and this is what turns it back into the 171 the store holds.

    IT ANSWERS THE INDEX OF THE CARD THE SECTION STARTS AT, which is what `open_section`
    already stores when the operator presses `S` at the box: that route takes no index and
    writes `next_index`, the slot the next card will land in. So a divider typed into the
    editor and a divider put in at the feeder come out at the same kind of number, and the
    forward map sends both to the same ordinal.

    The forward map is not injective — every index in a run of departed slots counts the
    same cards in front of it — so this picks one, and it picks the one `open_section`
    would have written. **Ordinal 1 is always index 1**, even where card 1 itself has sold:
    `check_sections` requires a layout to start at 1 because there is no card before the
    front of a box, and that is a fact about the box rather than about its contents.

    PAST THE LAST CARD IT COUNTS SLOTS, mirroring `_divider`'s own unfilled-tail term: a
    divider beyond everything captured so far is a plan, and each slot between here and
    there will hold one card.
    """
    if ordinal <= 1:
        # The front of the box: 1, or below it where a section was placed in front of card
        # 1 (D265, the order key).
        lows = [v[0] for v in (occupied, departed) if v]
        return master.front_of_box((), min(lows) if lows else None)[0]
    if ordinal <= len(occupied):
        # THE KEY ITSELF, NEVER `int()` OF IT (the R4 review): a placed card's key is a
        # fraction, and cutting it moved the divider onto the card in front (D265).
        return master.as_order(occupied[ordinal - 1])
    high = max(
        int(occupied[-1]) if occupied else 0,
        int(departed[-1]) if departed else 0,
    )
    # `int` keeps a planned divider on the whole-number keys a capture takes (D265).
    return int(high) + (ordinal - len(occupied))


def departed_label(box_name: str, section: Optional[int], card: int) -> str:
    """What a screen shows for a card that has left its box: the place it left.

    THE OWNER'S RULING, 2026-09-23 (D259), REPLACES D68's FORM. That
    form was `Box 3 · departed · B3 #96`: the box number, the word, and the store key. The
    ruling reads: box NAME, section, and the card's number within the section, so the place
    stays; sold, retired and moved are shown by a visual mark, not by a word. So the string
    has the shape of `place_label`, and it stays a function of its own so that one composer
    answers for departed records (D68's protected outcome: a departed record names itself).

    THE NUMBER IS `Position.was_card`: where the card would go back. D58 is kept for every
    live number. The card behind closed up and holds that number now, and the screen tells
    the two apart by the mark it draws for a departed copy (`Place.slot` is null on the wire,
    which is what every client reads, via `app/src/server.ts:isDeparted`).

    WHAT THE STORE KEY PROTECTED. D68 added `B3 #96` because two sold copies of one card in
    one box drew one identical string. With this form, two departed copies that stood next to
    each other read the same place, which is true: they left the same place. The owner's
    ruling of 2026-09-24 accepts that they may look the same; nothing on screen tells them
    apart. The key stays on the wire (`Place.index`) and in the route path.

    `section` is None only for a caller that could not read the layout, and then the label
    says the box and the card count within the box, which is what `Position` answers there.
    """
    if section is None:
        return f"{box_name}, Card {int(card)}"
    return place_label(box_name, int(section), int(card))


def place_text(game: str, position: Position) -> str:
    """The one line a list prints for where a card is: its label, or the pooled fact.

    The pooled form carries the store key (`5/12`) because it is the only handle left —
    an index is acceptable as a key, it is what the photo and sidecar are named after —
    and because two pooled entries with identical lines would be indistinguishable in the
    report that names them.
    """
    if is_located(game):
        return position.label
    return f"{pooled_label(game)} · {position.box}/{position.index}"


def where_phrase(game: str, position: Position) -> str:
    """`place_text` with its preposition, for a sentence mid-report.

    Two forms rather than one because the preposition differs: a located card is AT a
    slot, a pooled card is IN a pool, and "at Pokémon code cards · pooled" is a sentence
    that has stopped meaning anything.
    """
    if not is_located(game):
        return f"in the {game} pool ({position.box}/{position.index})"
    if position.card is None:
        # D58: a departed card is at nothing now, so the sentence is in the past tense and
        # names the place it left (D259).
        return f"formerly at {position.label}"
    return f"at {position.label}"


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
    # D3 rung 1's claim, read off the capture sidecar by `cli/resolve.py`. A SET since
    # 2026-08-23: one member determines, two or more filter the candidate rows and let
    # rungs 2 and 3 choose within what survives, and an empty set is no claim at all —
    # which is why this is None rather than `()` when nobody claimed anything, exactly as
    # `rarity_claim` below. `variant.resolve` decides all three; nothing here interprets it.
    #
    # A TUPLE, for `rarity_claim`'s reason two fields down: this dataclass is frozen and a
    # frozen carrier of a mutable member is a hashability bug waiting for its first `set()`.
    # `store/master.py:Card.metadata_finish` is a LIST for the opposite reason — that one is
    # not frozen and has to round-trip through `asdict` and JSON unchanged.
    #
    # A BARE STRING STILL RESOLVES IDENTICALLY, which is what makes the amendment additive:
    # `variant._check_claim` reads one as a one-member set, so a hand-made run record and
    # every record written before the amendment walk the path they always did. The annotation
    # names the shape this pipeline WRITES; the ladder accepts both.
    metadata_finish: Optional[Tuple[str, ...]] = None
    # ONE STRING, AND DELIBERATELY NOT A SET beside the claim above. Detection is the model
    # reading one photograph of one card, so it has exactly one answer or none — where the
    # claim describes a STACK, which is the whole reason that one became a set and this did
    # not. Rung 3 cross-checks membership of this in the claim (`detected_finish not in
    # claimed`), which is the identity test it always was when the claim has one member.
    detected_finish: Optional[str] = None
    photo: Optional[str] = None
    set_hint: Optional[str] = None
    confidence: Optional[str] = None

    # D23's multi-select rarity claim: the exact `Rarity` cells the operator said this
    # card's stack holds, read off the capture sidecar by `cli/resolve.py`. A TUPLE, not a
    # list, because this dataclass is frozen and a frozen carrier of a mutable member is a
    # hashability bug waiting for its first `set()`. None or empty narrows nothing —
    # `variant.resolve` treats the two identically, which is the compatibility guarantee
    # that makes the claim strictly additive.
    rarity_claim: Optional[Tuple[str, ...]] = None

    # A human's one-tap answer from the review screen, read off the inventory record by
    # `cli/resolve.py`. When set, `join_batch` resolves to this row before the ladder runs
    # — rung 0, `variant.HUMAN_ANSWERED`. The pair names one TCGplayer row exactly as the
    # answer route validated it; a SKU the current export no longer carries falls through
    # to the ladder rather than being guessed at. Rung 0 deliberately does NOT consult
    # `rarity_claim` above: a human who looked at the photograph beside the candidate rows
    # outranks a claim about the stack it came from, and an answer that could be re-parked
    # by a stack-level claim is the sixteen-cards failure D3 rung 0 exists to prevent.
    answered_sku: Optional[str] = None
    answered_condition: Optional[str] = None

    # TCGplayer already holds this copy: its record is staged, live, or sold. Also read
    # off the inventory by `cli/resolve.py`. A committed copy still matches and still
    # counts in the report — it is a real card at a real position — but it must never be
    # counted into `Add to Quantity`, written into an import file, or re-pushed: the first
    # real post-import re-emit (2026-08-22) did all three, regressing 37 staged copies to
    # `pushed` and writing files that would have doubled them in Staged if imported.
    committed: bool = False

    # WHICH GAME THIS CARD WAS CAPTURED AS (D21), and it decides which key finds its row.
    # Defaulted rather than required, and the default is `games.DEFAULT_GAME` read by name
    # rather than written out: every card built before this field existed is a Pokemon card,
    # which is the read-side backfill D21 sanctions and the reason a run with only Pokemon
    # in it joins byte-identically to the day before this line was added.
    #
    # D21 IS EXPLICIT THAT D3'S NULL-MEANS-NO-CLAIM DOES NOT TRANSFER HERE, and it is worth
    # the sentence because the two fields sit two lines apart and look identical.
    # `metadata_finish=None` is meaningful because there is a LADDER underneath it —
    # `variant.resolve` infers a finish from the catalog, from detection, from a human. There
    # is no ladder that infers a game: a missing game is not "no claim", it is "no export",
    # and every consumer below would have nothing to join against. So this field is never
    # None, and the substitution happens where the record is READ, never where it is written.
    game: str = games.DEFAULT_GAME


def number_index_key(text) -> str:
    """The one fold the number index and every number lookup pass through.

    THIS EXISTS BECAUSE THE TWO SIDES USED TO DISAGREE, AND THE DISAGREEMENT WAS SILENT.
    `Catalog.__init__` indexed on the export's `Number` cell VERBATIM while `join_key`
    composed a `zfill(3)`-padded key, so the two agreed only for exports whose cells happen
    to be three wide. Measured against `fixtures/pokemon_wide_export_untouched.csv`, which
    carries SM Cosmic Eclipse: 99 distinct unpadded cells (`1/236`, `39/236`), 950 rows, and
    ZERO of the composed keys appearing anywhere in the file. Every one of those cards would
    have come back `no_catalog_row` — a miss blamed on the export rather than on the key,
    which is the worst shape a join failure can take because the report points away from the
    bug. D12 scopes the product to SWSH/SV, where every set is padded, which is why nothing
    had ever noticed; Gate B's real 53-card run was ME01, already outside that scope.

    PADDING THE INDEX INSTEAD WOULD HAVE BEEN THE WRONG FIX, and it is the tempting one.
    `zfill(3)` on `066a/298` gives `066a/298` — unchanged, because it is already three wide
    before the suffix — while `66a/298` from another export becomes `066a`... only if the
    padding is applied to the digit run and not to the cell. One rule written twice in two
    dialects is exactly how these two drifted apart in the first place.

    SO: STRIP LEADING ZEROS FROM EVERY DIGIT RUN, KEEP EVERYTHING ELSE, FOLD CASE. Digit
    runs are what padding decorates, and nothing else in these cells is decorative:

        001/236   1/236      -> both `1/236`, which is the whole point
        161/159              -> `161/159`, a secret rare, untouched and still unique
        066a/298  066/298    -> `66A/298` and `66/298`, still two different Riftbound cards
        EB01-009             -> `EB1-9`, and any spelling of it folds the same way
        TG01/TG30            -> `TG1/TG30`, prefixes preserved

    Measured across all four committed exports — SV09, the wide Pokemon export, Riftbound
    and One Piece, 3,600 distinct cells between them — this fold introduces NO collisions: no
    two different `Number` cells anywhere in them land on one key. That is the check to
    re-run before widening it.

    The technique is `normalize_set`'s, applied to a different string for the same reason:
    two sources spell one identity differently and neither is wrong.
    """
    out: List[str] = []
    digits: List[str] = []
    for char in str(text or "").strip():
        if char.isdigit():
            digits.append(char)
            continue
        if digits:
            out.append(str(int("".join(digits))))
            digits = []
        out.append(char)
    if digits:
        out.append(str(int("".join(digits))))
    return "".join(out).upper()


def name_index_key(text) -> str:
    """The one fold the NAME index and every name lookup pass through (D35).

    `number_index_key`'s rule applied to the other column, for the same reason and with the
    same invariant: one function, both sides of the comparison. It exists because
    `Product Name` inconsistently embeds the collector number and `CLAUDE.md` says so in as
    many words — *"Never join on Product Name — it inconsistently embeds numbers."* D35
    narrows that rule rather than repealing it, and this function is the narrowing: the
    embedded number is decoration on an identity, exactly as `zfill` padding is decoration
    on a number, so it is folded away on both sides instead of being matched against.

    THE INCONSISTENCY IS NOT HYPOTHETICAL AND IT COST A MEASUREMENT. Box 2's export writes
    both spellings in one column — `Delibird - 105/132` and `Nickit` — and the first pass at
    D35's measurement matched raw names, scoring 35 of 46. The same measurement through this
    fold scores 45. The eleven it missed were not absent from the export; they were spelled
    with their number attached.

        Nickit                      -> `NICKIT`
        Delibird - 105/132          -> `DELIBIRD`
        Wally's Compassion - 132/132 -> `WALLY'S COMPASSION`
        Ho-Oh                       -> `HO-OH`, the hyphen is not a suffix
        Radiant Greninja - 46/98    -> `RADIANT GRENINJA`

    Case is folded and interior whitespace is collapsed, because the two sides come from a
    model's reading and a marketplace's catalog and neither owns the other's spelling.

    NOT APPLIED TO `Number`, EVER. That column is the primary key and it is folded by
    `number_index_key`, which is a different rule for a different string.
    """
    text = NAME_NUMBER_SUFFIX.sub("", str(text or "").strip())
    return " ".join(text.split()).upper()


# ---------------------------------------------------------------- the name cross-check
#
# THE READ NAME COMPARED AGAINST THE CANDIDATE ROWS' NAMES, WHICH IS A DIFFERENT JOB FROM
# FINDING THEM. `name_index_key` above is a KEY fold: it feeds an index, so it has to be
# exact, and two strings either land in the same bucket or they do not. What follows is a
# COMPARISON, run after the rows are already in hand, and it answers two questions the key
# fold cannot be asked without breaking the index:
#
#   CORROBORATED — the read name and a row's name are the same identity, strongly enough to
#     overrule a contradicting rarity claim. Strict on purpose.
#   DISPUTED     — the read name resembles NO row's name at all, which is what a wrong card
#     looks like when the number found real rows. Lenient on purpose.
#
# THE TWO THRESHOLDS ARE DIFFERENT AND THAT IS THE DESIGN, not an oversight. A partial read
# (`Rell` against `Rell, Magnetic`) is weak evidence: not enough to release a rarity
# contradiction, and far too much to call the card a different one. One predicate serving
# both jobs has to be wrong at one of them, and on this store it would be wrong at the
# expensive end — measured below.
#
# THE CATALOG SIDE CARRIES A TRAILING QUALIFIER THIS FOLD HAS TO DROP, and finding that out
# is what stopped the dispute test shipping broken. Riftbound's export writes
# `Rengar, Unseen (Alternate Art)` and `Chaos Rune (R05a)`. Measured over the owner's whole
# store, 84 of 195 raw disagreements were that suffix and nothing else — a flood of review
# entries for cards nobody had misread. The parenthetical is decoration on an identity, the
# same argument `name_index_key` makes for the embedded number, so it is folded away on the
# CATALOG side only: a model reading a bracket off a card is not a thing this has seen, and
# a read name is not an index key.
#
# ACCENTS ARE FOLDED for the same reason and it is load-bearing on Pokemon, the game this
# rule has the least evidence about: the model reads `Pokemon Center Lady` and the export
# writes `Pokemon Center Lady`, spelled with different bytes.

# A trailing `(...)` qualifier on a CATALOG name. Anchored, and inner parentheses excluded,
# so only a whole trailing group goes.
_NAME_QUALIFIER_SUFFIX = re.compile(r"\s*\([^()]*\)\s*$")

# What a read name and a row name must share for the read to CORROBORATE the row: one
# contains the other, and the shorter covers at least this much of the longer.
#
# MEASURED ON THE OWNER'S STORE, over all 159 `rarity_claim_mismatch` refusals the runs hold.
# 145 of them a claim-released ladder resolves; a human later answered every one of the 145;
# and THREE would have been the wrong row (`3/564`, `1/65`, `1/73`). At 0.6 the corroboration
# releases 136 of the 145 and leaks NONE of the three. Plain containment with no ratio at all
# releases 138 and also leaks none — the ratio is kept anyway, because what it guards against
# is not on this store's record: a three-letter read (`Jax`) corroborating every card whose
# name contains it. Two cards pay for that (`Anivia` against `Anivia, Primal`,
# `Chem-Baroness` against `Renata Glasc, Chem-Baroness`) and stay queued.
NAME_CORROBORATION_COVERAGE = 0.6

# What a read name and a row name must share for the read NOT to be DISPUTED. Containment at
# any length passes first; this catches the rest.
#
# MEASURED THE SAME WAY, over the 2,769 cards the store's runs list without asking anyone.
# Containment alone disputes 61 of them; adding this threshold disputes 38. The 23 it absorbs
# are the model's spelling, one or two characters out — `Corfish` for `Corphish`,
# `Piltrovan Forge` for `Piltovan Forge`, `The Runiation` for `The Ruination`,
# `Steraks Gage` for `Sterak's Gage` — every one of them the right card. None of the five
# wrong cards box 1 holds (`1/51`, `1/223`, `1/262`, `1/310`, `1/311`) is absorbed at this
# threshold, and `1/51` is the one this whole test exists for: read `Irelia, Blade Dancer`,
# number `190/221`, which in that export is `Forgefire Cape`.
NAME_DISPUTE_SIMILARITY = 0.8


def _name_compare_key(text, catalog_side: bool = False) -> str:
    """`name_index_key` plus the two folds a COMPARISON may make and an index may not."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    if catalog_side:
        text = _NAME_QUALIFIER_SUFFIX.sub("", text.strip())
    return name_index_key(text)


def name_corroborates(read_name, rows: Sequence[tcgcsv.Row]) -> bool:
    """Does the model's own reading of the NAME agree with one of the rows the NUMBER found?

    Two independent signals agreeing — one off the photograph, one off the export — which is
    what makes it strong enough to release a rarity claim that contradicts them both.

    A blank read name corroborates NOTHING — the absence of evidence, stated rather than
    left to fall out of the arithmetic. The coverage test below happens to reach the same
    answer today (zero characters cover no fraction of anything), so this line is not the
    only thing holding the behaviour up; it is here so that a later edit to the coverage
    rule cannot quietly make the empty string — a substring of every name — agree with
    every row.
    """
    read = _name_compare_key(read_name)
    if not read:
        return False
    for row in rows:
        row_name = _name_compare_key(row.get(tcgcsv.NAME_COLUMN), catalog_side=True)
        if not row_name:
            continue
        if read == row_name:
            return True
        short, long = sorted((read, row_name), key=len)
        if short in long and len(short) >= NAME_CORROBORATION_COVERAGE * len(long):
            return True
    return False


def name_disputes(read_name, rows: Sequence[tcgcsv.Row]) -> bool:
    """Does the model's reading of the NAME match no row the NUMBER found — at all?

    The mirror of `name_corroborates` and NOT its negation. Between the two sits everything
    the model spelled imperfectly or read in part, which is evidence of neither agreement nor
    disagreement and must raise nothing.

    A blank read name disputes nothing, for `name_corroborates`'s reason turned around: a
    card whose name could not be read is not a card whose name says this is the wrong row.
    """
    read = _name_compare_key(read_name)
    if not read or not rows:
        return False
    for row in rows:
        row_name = _name_compare_key(row.get(tcgcsv.NAME_COLUMN), catalog_side=True)
        if not row_name:
            # A row with no name is evidence of nothing, exactly as a blank `Rarity` cell is
            # to D23's filter. It cannot be disputed with.
            return False
        short, long = sorted((read, row_name), key=len)
        if short in long:
            return False
        if SequenceMatcher(None, read, row_name).ratio() >= NAME_DISPUTE_SIMILARITY:
            return False
    return True


def name_reads_exactly(read_name, row: tcgcsv.Row) -> bool:
    """Is the model's read name BYTE-IDENTICAL to this row's, through the fold?

    THE NARROWER HALF OF `name_corroborates`, split out for D253.
    `name_corroborates` is True on an exact fold match AND on a containment-with-coverage
    near miss (`Corfish` for `Corphish`); this answers only the first half, which is what
    tells `join_batch` whether a resolved card's stored name has anything to correct. A
    blank read matches nothing, for the reason every fold in this module gives a blank one:
    the absence of a reading is not a reading that agrees.
    """
    read = _name_compare_key(read_name)
    if not read:
        return False
    return read == _name_compare_key(row.get(tcgcsv.NAME_COLUMN), catalog_side=True)


# How many rows the NAME may contribute to a disputed card's candidate list.
#
# NINE IS THE SCREEN'S LIMIT, NOT A JUDGEMENT ABOUT NAMES. `app/src/ReviewQueue.tsx` keys
# candidates on the digits and stops at `MAX_KEYED_CANDIDATES = 9`; a row past that draws a
# blank chip and is mouse-only. The number's own row is added after these, so the name is
# capped one below it. A name that reaches this bound is a name that resolves to five or more
# distinct cards, which is not the case this rung is for and is left to `L`.
#
# Measured over the nine disputed cards the owner's store has ever recorded: the name answers
# ONE row on one card, TWO on seven (a card's Near Mint and Near Mint Foil), and THREE on one
# (`Aspirant's Climb`, printed in Origins and again as a promo). Nothing is near the bound.
NAME_ALTERNATIVE_LIMIT = 8


class NameSide(NamedTuple):
    """The rows the name found, and whether the ladder could settle a finish among them.

    TWO FACTS, BECAUSE ONE OF THEM CANNOT BE INFERRED FROM THE OTHER, and a version of this
    that returned only the rows shipped a real hole for an hour. `rows` is a single row in
    two different situations — the ladder narrowed a stack to one, or the name answered a
    card the export stocks in exactly ONE finish and the ladder REFUSED it. A caller
    counting `len(rows) == 1` reads those as the same thing and releases the second, which
    is a card listed on a finish the ladder had just rejected.

    It is reachable on the committed fixture: `Alcremie ex` is one row, `Near Mint
    Holofoil`, and a `normal` claim resolves `metadata_not_stocked` with no row at all.
    `settled` is that answer stated rather than guessed at.

    `resolution` IS THE LADDER'S OWN ANSWER OVER THESE ROWS, carried rather than
    discarded, and `None` unless `settled` is True. D253 needs it: a
    card already queued for a reason of its own — `rarity_claim_mismatch`,
    `ambiguous_no_signal`, `set_ambiguous`, … — has no stage or reason of its own to keep
    once the NAME settles it, because the one it carried was a review reason and the card
    is no longer going to review. `resolution.stage` and `.reason` describe how THIS row's
    finish was actually decided (metadata, catalog-forced, or detection, over the claims
    the card already carried) rather than borrowing the review reason it is replacing.
    """

    rows: Tuple[tcgcsv.Row, ...]
    settled: bool
    resolution: Optional[variant.Resolution] = None


def name_alternatives(
    named: Sequence[tcgcsv.Row],
    card: "IdentifiedCard",
    disputed_row: Optional[tcgcsv.Row],
) -> NameSide:
    """The rows the READ NAME finds, for a card whose NUMBER found something else.

    `disputed_row` IS NONE FOR A CARD THE LADDER NEVER RESOLVED AT ALL, since
    D253 — `rarity_claim_mismatch` and `ambiguous_no_signal` both carry
    no row (`variant.Resolution(stage=REVIEW, reason=...)`, `row` defaulted), and
    `set_ambiguous` is built the same way one level up. The SKU filter below is a no-op in
    that case, not a defect: there is no number's row to exclude the name's rows from.

    THE PIPELINE HAD ALREADY REASONED THE NUMBER'S ROW WAS WRONG AND THEN OFFERED IT ALONE.
    That is the defect this answers, and it is a defect of PRESENTATION rather than of
    resolution: `name_disputes` has flagged the contradiction since D146, and the entry it
    wrote narrowed the candidate list to `resolution.row` — the one card the screen had just
    told the operator was not what the photograph says. Pressing `L` and typing the name the
    model had ALREADY READ was the only way to the right row.

    MEASURED OVER EVERY `name_disputed` ENTRY THE OWNER'S STORE HAS RECORDED — all nine. In
    nine of nine the NAME was right and the NUMBER was wrong; in eight of nine the name
    resolves to exactly one card, and in the ninth to one card printed twice. Seven have since
    been answered by a human, and in SEVEN OF SEVEN the SKU they chose is one of the rows this
    function returns. The two that remain open are the two the owner was looking at when they
    reported this.

    IT DECIDES NOTHING, AND THAT IS WHAT MAKES IT SAFE. The card is queued either way; what
    changes is which rows the human is shown beside the photograph. Nothing here can list a
    card, so D35's ruling that a name-found row `may never list a card on its own` is
    untouched — this rung does not reach listing at all. `CLAUDE.md`'s rule against joining on
    `Product Name` is likewise unweakened: the name is not a key here, it is a second opinion
    offered to a person, and it is folded by `name_index_key` exactly as D35 requires.

    NARROWED BY THE SAME LADDER THAT NARROWED THE NUMBER'S ROWS, so the two sides of the
    disagreement are shown at the same grain. Where the ladder cannot settle the finish,
    every row is offered and the operator settles it — which is the ordinary multi-row entry
    this screen has always drawn.

    `name_corroborated=False`, NOT TRUE — CORRECTED 2026-09-23 (a review finding on
    D253). This call passed `True` from 2026-09-12 until then, on the
    argument that "these rows were found BY the name, so the name agrees with them." That
    argument is circular: `rows_for_name` finding a row BECAUSE its name matches is not a
    SECOND signal independent of the name — D146's release needs two, and this call had
    only one, wearing two names. Measured cost on the owner's store: a card read
    `Pyke, Returned`, claimed `rarity_claim=['Showcase']`, whose NUMBER found `Pyke,
    Returned` (Rare, the base print) — the claim contradicts that row outright and should
    queue. With `True` hardcoded, the waiver fired anyway and released the card onto the
    WRONG print. A rarity or finish claim that contradicts EVERY row the name itself
    found must still queue, exactly as it would over the number's own rows — the name
    finding a row is not a reason to trust an unrelated claim about which ROW that name's
    card is stocked in.

    ONE LINE HERE IS AN INVARIANT RESTATEMENT RATHER THAN A GUARD, AND IT IS KEPT ON
    PURPOSE. The SKU filter cannot fire: a row is in both sets only if one of the rows the
    NUMBER found carries the read name, and `name_disputes` returns False exactly then, so
    this function is never called at all. The sets are disjoint by construction and the
    mutation arm that deletes the filter survives the suite because it is a no-op.

    It stays for `name_corroborates`'s reason two hundred lines up: a later edit loosening
    the dispute test would otherwise draw one row twice, silently, in the function whose
    whole job is to be honest about which reading found what.

    `not narrowed.needs_review` is NOT in that category and reads like it. It is redundant
    against `row is not None` for every resolution `variant.resolve` builds today — but what
    the caller does with the answer turns on `settled`, and that flag is exactly the
    difference between a narrowed row and a fallen-back one. See `NameSide`.
    """
    excluded_sku = (
        str(disputed_row[tcgcsv.SKU_COLUMN]) if disputed_row is not None else None
    )
    rows = [
        row
        for row in named
        if excluded_sku is None or str(row[tcgcsv.SKU_COLUMN]) != excluded_sku
    ]
    if not rows:
        return NameSide((), False)

    narrowed = variant.resolve(
        rows,
        metadata_finish=card.metadata_finish,
        detected_finish=card.detected_finish,
        rarity_claim=card.rarity_claim,
        game=card.game,
        name_corroborated=False,
    )
    if not narrowed.needs_review and narrowed.row is not None:
        return NameSide((narrowed.row,), True, narrowed)

    # RANKED BEFORE THE CUT, AND NO CLAIM MATCH IS EVER CUT — a review finding, D23's
    # amendment applied to its own neighbour. `rows[:NAME_ALTERNATIVE_LIMIT]` used to take
    # the first 8 rows in CATALOG ORDER, blind to the claim. Measured against the real
    # Riftbound export: `Calm Rune` (and five sibling Runes) carries 16 rows; a `Common`
    # claim agrees with 8 of them and only 4 of those 8 happened to land in the first 8
    # catalog rows; a `Showcase` or `Promo` claim agrees with 4 and only 2 survived. A
    # cut that runs before the claim is read is a cut that can silently show half a claim.
    #
    # `rank_by_claims` first, so every agreeing row sorts ahead of every row that is not.
    # EVERY CLAIM-AGREEING ROW IS KEPT, UNCAPPED — the simpler of the two fixes the review
    # named, chosen over widening a second time inside this function: `join_batch`'s own
    # widen (a few hundred lines down) already exists for the total-miss case, and a second
    # widen in here would be the same rule stated twice. `NAME_ALTERNATIVE_LIMIT` still
    # bounds the NON-matching rows only — a card carrying no claim behaves exactly as
    # before, since every row scores zero and `matched` is empty. A row past the ninth
    # keyed slot is still mouse-only (D46/`MAX_KEYED_CANDIDATES`), never dropped — this
    # only ever WIDENS what a claim can keep past the screen's own keyboard limit, it
    # never narrows what a human is offered.
    ranked = rank_by_claims(tuple(rows), card)
    matched = tuple(row for row in ranked if claim_matches(row, card) > 0)
    unmatched = tuple(row for row in ranked if claim_matches(row, card) == 0)
    kept = matched + unmatched[: max(0, NAME_ALTERNATIVE_LIMIT - len(matched))]
    return NameSide(kept, False)


def distinct_cards(rows: Sequence[tcgcsv.Row]) -> int:
    """How many different CARDS these rows are, as opposed to how many rows.

    THE DIFFERENCE BETWEEN A CHOICE AND A FORMALITY, and it is the whole of the release rule
    below. One card stocked in two finishes is two rows and one card: `Deathgrip` at
    `Spiritforged 163/221` has a Near Mint row and a Near Mint Foil row, the ladder picks
    between them from the operator's own claim, and nobody is being asked which card it is.
    Two cards is a question no claim can settle — `Aspirant's Climb` is printed in Origins at
    `276/298` and again as a promo at `276a/298`, and only a person looking at the photograph
    can say which is in the box.

    `(Set Name, folded Number)` IS THE IDENTITY, and neither half is optional. The number
    alone collides across sets — that is what `Catalog.colliding_keys` is about — and the set
    alone is obviously not a card. Condition and finish are deliberately not in the key: they
    are what varies BENEATH one card, which is the distinction this function exists to draw.
    """
    return len(
        {
            (
                str(row.get(tcgcsv.SET_COLUMN, "") or "").strip(),
                number_index_key(row.get(tcgcsv.NUMBER_COLUMN, "")),
            )
            for row in rows
        }
    )


# ------------------------------------------------------------ D23's third job: ranking
#
# THE CLAIM USED TO ONLY CROSS-CHECK AND NARROW. `rarity_filter` (`pipeline/variant.py`)
# is job (a): it refuses a row the claim contradicts. Job (b) narrows the finish chips on
# the capture screen. Neither ever changed the ORDER a human is shown candidates in — a
# card queued `set_ambiguous` or `rarity_claim_mismatch` offered the number's own rows in
# catalog order, whatever the operator had typed about the stack. `4/383` is the case: read
# `Calm Rune` / `R02`, claimed `Showcase`. The number found five `R02` Commons across three
# sets — a `set_ambiguous` collision the claim was never even consulted for, because that
# rung fires before the ladder runs — and the three `Calm Rune (R02a)` Showcase rows the
# claim actually names sat under a different number the same name also answers to, offered
# nowhere. The owner's ruling: a card should be offered a name match and/or a number match;
# where the claim picks out some of them, those come first.
#
# JOB (c): RANK WHAT IS OFFERED. It reorders; it never files a list down and it never
# answers one. `distinct_cards` above is the question "is this one card or two" — this is
# "which of these rows does the evidence favour", and the two stay separate: this function
# never removes a row, so a tie it cannot break is left a tie rather than resolved by
# omission.


def claim_matches(row: tcgcsv.Row, card: Optional["IdentifiedCard"]) -> int:
    """How many of the card's own capture claims — rarity, finish, set hint — this ONE
    row agrees with. 0 to 3.

    A CLAIM THAT IS EMPTY RANKS NOTHING, the same compatibility guarantee D23's filter
    already gives an empty rarity claim: it contributes to no row's score, so a card
    captured with no claim at all ranks every row of its ordinary text match equally, and
    nothing here has a way to move it. `card=None` is the same fact stated for a caller
    that has no card at all — `do_review_catalog`'s own callers before this entry, kept
    working rather than made to invent one.

    REUSES THE LADDER'S OWN TESTS rather than a second copy of either fold: the rarity half
    is `variant.rarity_filter` — one row is "kept" or it is not, exactly the ladder's own
    rung 0 filter run on a list of one — and the set half is `set_matches`, D25's own
    pairwise answer to "does this hint name this set". A blank `Rarity` cell PASSES
    `rarity_filter` (evidence of nothing, D23's own rule) but that is not the SAME as
    matching a claim, so it scores 0 here rather than 1 — ranking rewards agreement, not
    the absence of a contradiction.
    """
    if card is None:
        return 0
    score = 0
    if card.rarity_claim and variant.rarity_filter((row,), card.rarity_claim):
        score += 1
    if card.metadata_finish:
        _stocked, condition_by_finish = variant.vocabulary(card.game)
        claimed = (
            (card.metadata_finish,)
            if isinstance(card.metadata_finish, str)
            else tuple(card.metadata_finish)
        )
        wanted = {condition_by_finish[f] for f in claimed if f in condition_by_finish}
        if wanted and row.get(tcgcsv.CONDITION_COLUMN) in wanted:
            score += 1
    if card.set_hint and set_matches(card.set_hint, row.get(tcgcsv.SET_COLUMN, "")):
        score += 1
    return score


def rank_by_claims(
    rows: Sequence[tcgcsv.Row], card: "IdentifiedCard"
) -> Tuple[tcgcsv.Row, ...]:
    """Rows ranked by `claim_matches`, best first — THE ONE FUNCTION `join_batch`'s
    suggestion-widening and `server/capture_server.py:do_review_catalog`'s search both
    call, so a claim is scored once rather than twice.

    STABLE (Python's own `sorted` guarantee): rows that score equally keep the order they
    arrived in. WHERE THE EVIDENCE FAVOURS NO ONE ROW OVER ANOTHER — every claim empty, or
    every row scoring the same — nothing here breaks the tie, which is the owner's own
    rule stated as code: never guess between rows two agreeing signals do not separate.

    DECIDES NOTHING. It reorders a list a caller already built; it can neither add a row
    nor drop one, and calling it on a `HUMAN_ANSWERED` card's own one-row answer is a
    no-op rather than a rule this function has to enforce — D146's "rung 0 must not
    consult the claim" holds because rung 0 never reaches here with more than one row to
    rank, not because this function checks the stage.
    """
    return tuple(sorted(rows, key=lambda row: -claim_matches(row, card)))


# A GENEROUS BACKSTOP ON THE NAME-WIDEN BELOW, NEVER EXPECTED TO BIND. The widest group
# this game's committed catalogue has for one folded name, Near-Mint-scoped, is 16
# (`Calm Rune`, measured against `fixtures/riftbound_export_untouched.csv` — six Runes tie
# it). A rarity-claim filter over that can only ever shrink it. This exists so one
# degenerate export cannot hand a queue entry an unbounded list, never to drop a row the
# claim actually agrees with in the ordinary case — `rank_by_claims` runs on the matching
# rows before this cuts, so a cut (if it ever fires) drops the ones the OTHER two claims
# agree with least, never an arbitrary one.
#
# ponytail: this slice reports its own truncation nowhere — `found`/`truncated` are
# `do_review_catalog`'s wire fields, and this path writes a queue entry, not a response.
# It cannot bind today: 16 measured against 60. If a future export's real maximum for one
# folded name climbs past 60, raise this constant first (re-measure the comment above), or
# — if the widen itself needs to say "more exist" — give `QueuedCard` a `widen_truncated`
# flag the way the search route already carries one, rather than growing this number
# without a reader.
WIDEN_BY_CLAIM_LIMIT = 60

# THE THREE REASONS THIS WIDEN MAY FIRE FOR, READ RATHER THAN INFERRED FROM
# `resolution.needs_review` ALONE. A review finding: `needs_review` is also true of D35's
# `NUMBER_UNREAD_NAME_MATCHED` — the rung that narrows `found.rows` to exactly the one row
# the name resolved, on purpose, so D29's group-answer eligibility (`len(candidates) == 1`)
# can offer it as a batch. The widen below does not consult that narrowing's own reason —
# it only checked `needs_review` — so a rarity claim that disagreed with that single row
# would have grown the list back past one and silently taken the card out of group
# eligibility, the opposite of what D35 built. Scoped to the three reasons that never carry
# a row of their own (`set_ambiguous`, `rarity_claim_mismatch`, `ambiguous_no_signal`) —
# every other review reason already has a row, or a deliberate reason not to (D253's
# disputed-name block), so widening by name under any of them would be a second opinion
# about a question that reason has already answered.
_WIDEN_BY_NAME_REASONS = (
    routing.SET_AMBIGUOUS,
    variant.RARITY_CLAIM_MISMATCH,
    variant.AMBIGUOUS_NO_SIGNAL,
)


# ------------------------------------------------------------------ per-game dispatch
#
# `pipeline/games.py` says HOW a game's cards find their catalog rows, by name — the
# `number_and_printed_total` key `CLAUDE.md` documents, or the `name_only` fallback that is
# `pokemon_code`'s primary key because a code card carries no collector number at all. The
# registry holds the NAME and this module holds the lookup, because the registry has to stay
# `ast.literal_eval`-safe so the docs audit can read it without importing project code (D22).
#
# A PROTOCOL OR AN ABC PER GAME WAS CONSIDERED AND REJECTED. There is not one in `pipeline/`,
# `identify/` or `geometry/` today, and it would move Pokemon's join key out of this module —
# the one place `CLAUDE.md` points at for it — into a subclass beside three lines of code.
# Names plus a per-module dict is also the only shape `scripts/docs-audit.py` can check: it
# reads both files with `ast` and compares two sets of strings, running neither.
#
# A STRATEGY TAKES `(catalog, card)` AND ANSWERS `(rows, lookup)`, or `(rows, lookup,
# name_inferred)` where it needs the third. `lookup` is the string the run report and the
# queue entry print, so it says which key was tried as well as what it was — `number:031/197`
# and `name:Pikachu` are different questions with different remedies.
#
# `name_inferred` defaults False and is set by exactly one rung today (D35). It is a THIRD
# ELEMENT rather than a prefix sniffed off `lookup`, deliberately: `lookup` is a human-facing
# vocabulary printed on reports, and making a routing decision depend on parsing it would tie
# a rule to a spelling that exists to be read.


class KeyStrategy(NamedTuple):
    """How ONE game builds its catalog key. Everything below the key is shared.

    THIS TYPE IS THE REPAIR FOR A REAL DEFECT, AND THE DEFECT IS WHY IT IS SHAPED THIS WAY.
    Until 2026-08-29 each game had its own `_lookup_*` function, and each of those functions
    re-implemented the SAME four-step ladder — build a key, look it up, try the blank-`Number`
    name, fall back to the name — differing only in step one. D35's name rung was then written
    into the Pokemon copy and not the printed-code copy, so `riftbound` and `one_piece` returned
    zero candidates exactly where `pokemon` recovered. Nothing compared the copies, because
    nothing could: they were three unrelated functions that happened to be parallel.

    Measured cost before it was found: run `2026-08-29-box1-01`, 133 real Riftbound cards, 4
    unusable reads, all 4 landing as zero-candidate `no_catalog_row` — and a zero-candidate
    entry is refused by the answer route as `no_candidates`, so those cards could not be
    answered at all, only skipped. Three of the four hold exactly one row by name, one of them
    above D9's threshold at $2.86.

    So the per-game part is now a VALUE and the ladder is written once. A new rung added to
    `_walk` below cannot land in one game and not another, which is the property the old shape
    could not offer at any level of care.

    `build` returns the key or None. None means "this card gives this game nothing to look up",
    which is a different fact from "the key found no rows" and is why the two take different
    branches below.

    `label` is the lookup string's prefix — `number:`, `code:`, `name:`. It is rendered on the
    run report (D16: the machine string stays greppable), so it names how the row was FOUND and
    must not be prettified.

    `repair` is asked ONLY when a key found no rows, and returns a second key to try before the
    name rung — today, the identifier with a set code the model glued onto the front of it. It
    is deliberately not folded into `build`: a key that MATCHES must never be rewritten, and a
    repair that runs before the lookup cannot promise that. None means this game has no repair,
    which is the case for every game but the two keyed by a printed code.

    `name_rung` is D35's last resort, and `pokemon_code` deliberately switches it OFF. That is
    not an oversight preserved for compatibility: a code card has no collector number at all, it
    lives inside the Pokemon export as a blank-`Number` row, and `rows_for_name` would happily
    match it to the NUMBERED card of the same name — a code card listed as the card it came
    with. The rung exists for "we could not READ the number"; a product that prints none has
    nothing to fall back from.
    """

    build: Callable[["IdentifiedCard"], Optional[str]]
    label: str
    name_rung: bool
    repair: Optional[Callable[[str], Optional[str]]] = None


def _key_number_and_printed_total(card: "IdentifiedCard") -> Optional[str]:
    """Pokemon: two printed halves composed into one key, zero-padded on the left.

    Both halves or nothing. A number without its denominator cannot compose the key the export
    is indexed by, and guessing a denominator would invent half an identity.
    """
    if card.number is None or card.printed_total is None:
        return None
    return join_key(card.number, card.printed_total)


# THE SHAPE ITSELF (`_SET_CODE_PREFIX`, `strip_set_code`) LIVES IN `store/numbers.py` NOW
# (store-scaling item 8) AND IS IMPORTED BACK ABOVE -- `store/` may not import `pipeline/`
# (D63), so the leaf functions moved to where both sides could reach them without crossing
# that edge. `_repair_set_code` below is the LADDER's own reader of the shape and stays
# here: it is candidate-or-None, asked only on a miss, which is a `pipeline/`-specific
# contract that has no reason to live in a leaf module. See `store/numbers.py:strip_set_code`
# for the three-bound argument (letters only, at least two, at most five) and the
# measurement that licenses it.
def _repair_set_code(key: str) -> Optional[str]:
    """`UNL - 150/219` -> `150/219`, or None where there is nothing set-code-shaped to remove.

    THE MODEL WAS TOLD NOT TO DO THIS AND GOES ON DOING IT. `identify/prompt.py`'s Riftbound
    contract says in as many words *"Do not add a set code printed elsewhere on the card"*.
    Run `2026-08-29-box1-01`: 3 of 133 reads glued it on anyway. Run `2026-08-30-box3-01`: **7
    of 39**, an order of magnitude worse, and across THREE different separators in one box —
    bullet, hyphen and slash — including two copies of one card read both ways, `UNL - 198/219`
    at card 31 and `UNL \u2022 198/219` at card 3. The separator is arbitrary, so enumerating
    separators is a losing game and the shape above is what replaces it.

    RECOVERING THE NUMBER IS BETTER THAN FALLING BACK TO THE NAME, which is why this exists even
    though D35's rung already rescues these cards. The number is the field that tells one card
    from another; the name is the field that survives a bad read. A recovered number is an exact
    join and LISTS the card, where the name rung deliberately only ever queues it (the owner's
    ruling). Box 3's four unrepaired reads were $30.81, $23.76, $17.06 and $12.52 of cards
    sitting in a queue that had nothing to ask.

    IT RETURNS A CANDIDATE, NOT AN ANSWER, AND `_walk` ONLY ASKS ON A MISS. That ordering is the
    second safety and it is stronger than the shape bounds: an identifier that already matched a
    row is never handed to this function at all, so no repair can move a card that was joining
    correctly — however a future export's cells are spelled. It is D35's own rule for its own
    rung, applied one step earlier.

    None rather than the unchanged string, so the caller cannot re-look-up a key it has already
    missed on, and so `code~:` is written only where something was actually removed.

    THE SHAPE ITSELF IS `strip_set_code` BELOW, AND THE SPLIT IS D67. This function is the
    LADDER's reader of it — candidate-or-None, asked only on a miss — and the screens are the
    other, which strip unconditionally because there is no catalog to miss against. One regex,
    two contracts; a second spelling of the shape is what D55 spent an entry avoiding.
    """
    out = strip_set_code(key)
    return out if out and out != key.strip() else None


# `strip_set_code` moved to `store/numbers.py` (store-scaling item 8) and is imported back
# above under the same name; every caller here (`_repair_set_code` above) is unaffected.


def _key_printed_code(card: "IdentifiedCard") -> Optional[str]:
    """Riftbound and One Piece: the identifier exactly as printed, matched verbatim.

    THE OPPOSITE SHAPE TO THE ONE ABOVE, and the difference is where the string is built.
    Pokemon prints two halves and this pipeline composes the key — zero-padding the left one,
    because `25` and `025` are the same card and the export writes the padded form. These games
    print ONE identifier and the export's `Number` cell carries that same string, so there is
    nothing to compose and nothing to pad: padding here would turn a code the export holds into
    one it does not.

    THE EXAMPLES ARE THE EXPORTS' OWN CELLS, corrected 2026-08-23. This docstring offered
    `OGN-001` for Riftbound, and no cell anywhere in `fixtures/riftbound_export_untouched.csv`
    looks like that — a set-code-prefixed shape borrowed from One Piece and attributed to the
    wrong game. Riftbound's real cells are `179/298`, `066a/298`, `303*/298`, `SP3/006`, `R04`
    and `T02 // T03`; One Piece's are `OP15-079`, `EB04-042`, `PRB02-014` and `P-105`. The
    invented example mattered more than a docstring usually does: it is what a prompt author
    reads to learn what shape to ask the model for, and asking for `OGN-001` would have put a
    set code into the joined field and matched nothing.

    THAT EXACT FAILURE THEN HAPPENED FROM THE MODEL'S SIDE. Reads come back as `UNL • 140/219`,
    `UNL - 150/219` and `UNL / 120/219` — the set code glued to the identifier, which the
    Riftbound prompt forbids in as many words — at 3 of 133 in one run and 7 of 39 in the next.

    THIS FUNCTION NO LONGER REPAIRS THEM, AND THE MOVE IS THE POINT (2026-08-30). It used to
    call `_strip_set_code` here, which meant every identifier was rewritten on its way to the
    lookup whether or not the raw one would have matched. `_repair_set_code` is now reached from
    `_walk`, on a miss only, so a card that joins cleanly is never touched by it. What is
    returned here is what the model read, verbatim.

    `printed_total` is not consulted at all, in either direction. A game keyed this way has no
    denominator to disagree with.
    """
    if card.number is None:
        return None
    return str(card.number).strip() or None


def _key_none(card: "IdentifiedCard") -> Optional[str]:
    """`pokemon_code`: there is no collector number on this product, so there is no key.

    Deliberately does not consult `card.number` even when one is present: a number read off a
    card of this kind is a number read off the wrong part of it, and matching on it would find
    a row belonging to something else entirely.
    """
    return None


def _walk(catalog: "Catalog", card: "IdentifiedCard", strategy: KeyStrategy):
    """THE LADDER, written once for every game. Only `strategy` varies.

    1. The game's own key, if this card yields one.
    2. A key that missed, repaired once, where the game declares a repair. Today that is the
       set code the model glues onto a Riftbound identifier against its own instructions.
    3. Failing a key at all, the export's blank-`Number` rows by name. Sealed products, promos
       and code cards land here whatever keys the rest of the export.
    4. D35's last resort: the name, for a card that DOES print a number we could not read.

    STEP 4 IS REACHED FROM TWO DIRECTIONS AND NOT FROM A THIRD. A key that found nothing falls
    to it, and so does a card with no key whose blank-`Number` name found nothing. A key that
    MATCHED never reaches it — the rung is a last resort, not a peer, and a number that
    resolves is never second-guessed.

    It cannot mislist anything, which is what makes it safe rather than merely useful: it is
    reached only when the card was bound for `no_catalog_row` regardless, and what it produces
    is a REVIEW entry. That listing ban is enforced in `join_batch`, not here, because listing
    is its decision and not this function's.

    The third element of the return is `name_inferred`. `Catalog.candidates` accepts two
    elements or three, so a strategy that never infers stays a two-tuple.
    """
    key = strategy.build(card)
    if key:
        rows = catalog.rows_for_key(key)
        if rows:
            return rows, f"{strategy.label}:{key}"
        # A KEY THAT MISSED GETS ONE REPAIR BEFORE THE NAME RUNG, where the game declares one.
        # Reached only from here, which is what lets the repair be bolder than it could be at
        # build time: the card is already bound for `no_catalog_row`, and the worst a wrong
        # repair can do is miss again and fall through to exactly where it was going.
        #
        # `~` MARKS IT, AND A SEPARATE LABEL IS THE POINT RATHER THAN A FLOURISH. This is a
        # count of how often the model ignores an explicit instruction in its own prompt — 7 of
        # 39 on box 3 — and a repair that reported itself as an ordinary `code:` match would
        # make its own cause invisible on the run report. Same argument D35 makes for spelling
        # its rung `name?:` rather than `name:`.
        if strategy.repair is not None:
            repaired = strategy.repair(key)
            if repaired:
                rows = catalog.rows_for_key(repaired)
                if rows:
                    return rows, f"{strategy.label}~:{repaired}"
        # A NUMBER THAT FINDS NOTHING IS A NUMBER WE SHOULD STOP BELIEVING (D35). Falling
        # through rather than returning empty is the whole of the rung: box 2's nine
        # confident-wrong reads carried a denominator, so they composed a well-formed key that
        # matched nothing, and box 1's three carried a set code. Stopping here would leave
        # every one of them exactly as stuck as a blank number does.
    else:
        rows = catalog.rows_for_blank_number_name(card.name)
        if rows or not strategy.name_rung:
            # `not name_rung` returns the empty result deliberately — see `KeyStrategy`.
            return rows, f"name:{card.name}"
    # `name?:` and not `name:`. A row found because the product prints no number and a row
    # found because we could not read one are different facts with different remedies, and the
    # run report prints this string (D16 — the machine string stays greppable).
    return catalog.rows_for_name(card.name), f"name?:{card.name}", True


# A game that is never joined at all — `misc`, the occasional Yu-Gi-Oh, Weiss Schwarz,
# foreign-language or Magic card, captured and located and described by hand. The registry
# gives it its own strategy name rather than reusing `name_only` against an empty catalog,
# because "this never joins" and "this joined by name and found nothing" are different facts
# with different remedies, and only the second one is worth looking into.
NOT_JOINED = "not_joined"


class NotJoinable(LookupError):
    """A card whose game names `not_joined` reached the catalog.

    Never raised in the ordinary course: a game that is never joined should be filtered out
    before a catalog is built for the run (D25 partitions by game). If this fires, something
    upstream let the card through, and stopping is better than matching it against whichever
    export happened to be loaded.
    """


JOIN_KEY_STRATEGIES: Dict[str, Optional[KeyStrategy]] = {
    "number_and_printed_total": KeyStrategy(_key_number_and_printed_total, "number", True),
    "printed_code": KeyStrategy(_key_printed_code, "code", True, repair=_repair_set_code),
    # `name_only` keeps its registry name — the strategy is still "match on the name alone" —
    # but it is now expressed as the ABSENCE of a key rather than as a separate ladder.
    "name_only": KeyStrategy(_key_none, "name", False),
    NOT_JOINED: None,
}

# Every strategy name the registry knows must have a lookup here, checked at import for the
# reason `pipeline/variant.py` reconciles its finish enum there: the failure is otherwise a
# `KeyError` raised mid-join, halfway through a run, with a card in hand. The reverse is not
# checked — `not_joined` is authored ahead of the entry that will claim it, and blocking on
# that would mean this file and the registry could only ever change together.
_unrouted = [name for name in games.JOIN_KEY_STRATEGIES if name not in JOIN_KEY_STRATEGIES]
if _unrouted:  # pragma: no cover - import-time contract, not a branch under test
    raise RuntimeError(
        "pipeline/join.py:JOIN_KEY_STRATEGIES has no lookup for "
        + ", ".join(repr(name) for name in _unrouted)
        + ", which pipeline/games.py lists in JOIN_KEY_STRATEGIES. Write the lookup here — "
        "never let a game fall through to another game's key."
    )


def lookup_for(game: str) -> Callable:
    """The lookup one game's cards use, or a refusal naming which kind of refusal it is.

    `games.require` rather than `get` (D22): a game with no authored vocabulary refuses here
    rather than borrowing Pokemon's. Joining is exactly the consumer that rule is written
    for — the vocabulary IS the export, and a game with none has nothing to be joined
    against. `require` raises two DIFFERENT refusals and each already names its own remedy:
    `NotCatalogued` for a game that will never have a catalog (check `games.is_catalogued`
    before the pipeline work), `EmptyVocabulary` for one still waiting on an export.

    `require` RUNS FIRST, SO `NotJoinable` BELOW IS A BACKSTOP AND NOT THE MISC PATH. A misc
    card that got this far refuses as `NotCatalogued`, whose message is the better one — it
    says which predicate the caller skipped. What is left for `NotJoinable` is the case
    those two cannot describe: a game the registry says HAS a catalog and a vocabulary, and
    whose `join_key` is nevertheless `not_joined`. That combination is a registry
    inconsistency rather than a data gap, and it should stop rather than pick a key.
    """
    entry = games.require(game)
    name = str(entry["join_key"])
    strategy = JOIN_KEY_STRATEGIES.get(name)
    if strategy is None:
        raise NotJoinable(
            f"game {game!r} names join key {name!r}, which never joins. A card of this game "
            "is captured, located and described by hand; filter it out of the run before a "
            "catalog is built rather than matching it against an export it has no rows in."
        )
    return lambda catalog, card: _walk(catalog, card, strategy)


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

    ONE NAME AT A TIME, which is why nothing that has to CHOOSE a set calls this any more.
    A pairwise predicate cannot see that four sets answered, and four did: `SV` matched
    `SV: Prismatic Evolutions`, `SV: Paldean Fates`, `SV: Scarlet & Violet 151` and
    `SV: Shrouded Fable`, and the caller below handed all four sets\' rows back as a confident
    narrowing with no `set_ambiguous`. `Catalog.candidates` resolves set-wise now; this
    survives as the yes/no question `harness/tests/t3_join_coverage.py` asks of one pair.

    The rules are `pipeline/setnames.py`\'s, not its own. They used to be its own, and they
    disagreed with the fetch\'s — `sv9` folded to `sv09` here and nowhere else, and the fetch
    had a prefix rule this did not.
    """
    return setnames.resolve(hint, [set_name]) is not None


@dataclass(frozen=True)
class Candidates:
    """The rows a card could be, how they were found, and whether that was decisive."""

    rows: Tuple[tcgcsv.Row, ...]
    lookup: str
    set_ambiguous: bool = False
    candidate_sets: Tuple[str, ...] = ()
    # D35 — these rows were found by name because the collector number could not be read.
    # `join_batch` reads it to keep such a card in front of a human; nothing else may treat
    # it as an ordinary match.
    name_inferred: bool = False

    @property
    def market_prices(self) -> Tuple[Optional[Decimal], ...]:
        return tuple(
            tcgcsv.parse_price(row[tcgcsv.MARKET_PRICE_COLUMN]) for row in self.rows
        )


class Catalog:
    """A TCGplayer export indexed for joining.

    Built from the export and nothing else (v2 §5.1). Collisions — one join key reaching
    rows in more than one `Set Name` — are computed here, once, before any card is joined.

    ONE GAME PER CATALOG, NEVER MERGED (D25). `from_export` is the constructor that
    enforces it; building directly from an export is the pre-D25 shape and remains legal
    for a caller that has already scoped its rows. What may never exist is a single
    `_by_number` spanning two games: it would report a cross-GAME collision through
    `colliding_keys` as though it were the cross-SET collision that report is about —
    different faults with different remedies, since a set hint fixes one and nothing fixes
    the other.
    """

    def __init__(
        self,
        export: tcgcsv.Export,
        *,
        game: Optional[str] = None,
        dropped_rows: int = 0,
        dropped_off_condition: int = 0,
    ):
        # Which game's rows these are (None for a direct, pre-scoped build) and how many
        # rows of the source file the game's filter dropped — reported by the caller, per
        # D25's "reports the drop count".
        #
        # TWO COUNTS, BECAUSE THEY ARE TWO DIFFERENT FACTS AND ONE OF THEM USED TO LIE (D137).
        # `dropped_rows` is other games' rows: zero for a file exported per game, large for a
        # combined file working as intended. `dropped_off_condition` is THIS game's rows in a
        # play grade. `cli/cmd_join.py` reported the first as "row(s) of other product lines
        # dropped", and after D137 that sentence would have covered 8,077 Riftbound rows and
        # called them another product line's. A number nobody can account for is a number the
        # next person deletes the filter to explain.
        self.game = game
        self.dropped_rows = dropped_rows
        self.dropped_off_condition = dropped_off_condition
        self.export = export
        self._by_number: Dict[str, List[tcgcsv.Row]] = {}
        self._blank_number_by_name: Dict[str, List[tcgcsv.Row]] = {}
        # D35's last-resort index: every row that HAS a number, keyed by its folded name.
        # NUMBERED ROWS ONLY, and that is the boundary rather than an optimisation. The rung
        # above this one owns the blank-`Number` rows — code cards, sealed product, promos —
        # and this rung exists for the opposite case: a product that DOES print a number, on
        # a photograph the number could not be read from. Keeping the two sets disjoint is
        # also what makes a name collision between a card and a code card impossible here,
        # which matters because `from_export` deliberately KEEPS code-card rows in the
        # `pokemon` catalog (see its docstring).
        #
        # KEYED BY THE CATALOG-SIDE COMPARE FOLD, NOT THE PLAIN INDEX — CORRECTED
        # 2026-09-23 (a review finding on D253). `name_index_key` alone
        # never strips a trailing qualifier, so `Pyke, Returned (Alternate Art)` indexed
        # under its own full string and `rows_for_name("Pyke, Returned")` never found it —
        # `distinct_cards` then saw one product where the export actually stocks two, and
        # D162's "exactly one card" release fired on the WRONG one. `_name_compare_key(...,
        # catalog_side=True)` is the SAME fold `name_disputes`/`name_corroborates` already
        # compare against; using it here too means one card's every printing shares one
        # bucket, whatever qualifier the export appends to tell them apart on screen.
        self._by_name: Dict[str, List[tcgcsv.Row]] = {}
        self._order: Dict[str, int] = {}
        self._sets_by_key: Dict[str, List[str]] = {}
        # Folded key -> the export's own spelling of it, for anything printed at a human.
        # `colliding_keys` is read off a run report and pasted into a search box, so it has
        # to say `003/159` where the file says `003/159` — the fold is a comparison device
        # and was never meant to be a vocabulary.
        self._cell_by_key: Dict[str, str] = {}

        for index, row in enumerate(export.rows):
            self._order[row[tcgcsv.SKU_COLUMN]] = index
            number = row[tcgcsv.NUMBER_COLUMN].strip()
            set_name = row.get(tcgcsv.SET_COLUMN, "")
            if number:
                # FOLDED, and `rows_for_key` folds what it is handed with the same function.
                # That is the invariant: one rule, applied on both sides of the comparison.
                # It used to be indexed verbatim here and looked up padded, which agreed only
                # for exports whose cells were already three wide — see `number_index_key`.
                key = number_index_key(number)
                self._by_number.setdefault(key, []).append(row)
                self._cell_by_key.setdefault(key, number)
                # Folded by `_name_compare_key(catalog_side=True)`, and `rows_for_name`
                # folds what it is handed with the same function — the invariant this
                # class already keeps for numbers, kept for the other column too.
                self._by_name.setdefault(
                    _name_compare_key(row[tcgcsv.NAME_COLUMN], catalog_side=True), []
                ).append(row)
            else:
                name = row[tcgcsv.NAME_COLUMN].strip()
                self._blank_number_by_name.setdefault(name, []).append(row)
                key = f"name:{name}"
            seen = self._sets_by_key.setdefault(key, [])
            if set_name not in seen:
                seen.append(set_name)

    @classmethod
    def from_export(cls, export: tcgcsv.Export, game: str) -> "Catalog":
        """One game's catalog, cut from an export by the registry's partition pair (D25).

        Keeps the rows whose `Product Line` cell is the game's `product_line` and — when
        the entry sets `product_line_rarities` — whose `Rarity` cell is in that tuple. The
        pair is the whole partition key, and both halves matter in the two games that share
        the `Pokemon` line: `pokemon_code` narrows to its `Code Card` rows, while `pokemon`
        sets no `product_line_rarities` and so KEEPS those same rows — they are the
        blank-`Number` case its name fallback already resolves and T3 already asserts, and
        a `pokemon` filter that dropped them would un-list every code card that sells above
        threshold by the ordinary path.

        `games.require`, not `get`: a game with no vocabulary has nothing to be joined
        against, and `misc` refuses here as `NotCatalogued` — its `product_line` is `None`
        precisely so this comparison could never be true anyway.

        AND THEN NARROWED TO THE CONDITIONS THIS PRODUCT SELLS (D137) — the game's own Near
        Mint strings plus `Unopened`, so sealed product survives and every play grade goes.
        That is a SCOPE and not a partition: the pair above says which game's rows these are,
        this says which reading of a card the product lists, and the block beside the
        predicate carries the argument and the measurements.

        Refuses on zero rows — see `EmptyCatalog`, which now tells the two emptinesses apart:
        the wrong file for this game, and the right file in the wrong grades.

        TWO DROP COUNTS, carried on the catalog for the caller to report. `dropped_rows` is
        other games' rows, per D25's "reports the drop count": zero is the ordinary case for a
        file exported per game, and a large number is a combined file working as intended.
        `dropped_off_condition` is this game's own rows in a grade it does not list — on the
        owner's fetched Riftbound export, 8,077 of 10,191.
        """
        entry = games.require(game)
        line = entry["product_line"]
        rarities = entry.get("product_line_rarities")
        # D137 — THE THIRD AXIS, AND IT IS A SCOPE RATHER THAN A PARTITION.
        #
        # The game's own Near Mint strings, read off the registry exactly as
        # `server/capture_server.py:_near_mint_conditions` reads them for the catalog search,
        # so a game whose finishes move changes in one place. D12 hardcodes Near Mint: every
        # rung of `variant.resolve` resolves to one of THESE strings and to nothing else, so a
        # `Lightly Played Foil` row is a row the ladder would never pick and a row the operator
        # must never be offered.
        #
        # IT WAS ONLY EVER NEAR MINT BY ACCIDENT OF THE FILE. Until 2026-08-31 the operator
        # downloaded the export by hand with the portal's Near Mint filter checked, so the
        # catalog was narrow as a property of the CSV and not as a rule anywhere in this tree.
        # D65's fetch declares `Scope.condition_ids` and has never populated it — `ids()` turns
        # `()` into `["0"]`, the portal's *All Conditions* — and on 2026-09-01 every run was
        # re-joined against a fetched file. The rule lives HERE rather than on the wire (D76's
        # last paragraph, amended) precisely so it cannot depend again on how the file was made.
        #
        # WHAT IT COSTS IS NOTHING, AND THAT IS MEASURED RATHER THAN ARGUED. A play grade is not
        # a finish — D64's own words, and its own measurement: "all 153 numbers read as thinned
        # and not one had lost a finish". Re-measured on the owner's 2026-09-11 export, 0 of
        # 1,246 numbers lose a finish here, because each finish keeps its own Near Mint row.
        # What it RESTORES is D3 rung 2, which the wide file had killed outright: 0 of those
        # 1,246 numbers held a single row as fetched, and 629 do once the grades are gone.
        #
        # SEALED PRODUCT SURVIVES and is not an exception to the rule so much as outside it —
        # see `tcgcsv.SEALED_CONDITION`, which carries the argument and the measurement.
        # `games.near_mint_conditions`, not restated here — see its own docstring
        # (docs/specs/card-variants.md section 3b) for why this expression now lives in
        # exactly one place rather than three.
        conditions = games.near_mint_conditions(game)
        conditions.add(tcgcsv.SEALED_CONDITION)

        def this_game(row) -> bool:
            return row.get(tcgcsv.PRODUCT_LINE_COLUMN) == line and (
                not rarities or row.get(tcgcsv.RARITY_COLUMN) in rarities
            )

        mine = [row for row in export.rows if this_game(row)]
        kept = tuple(
            row for row in mine if row.get(tcgcsv.CONDITION_COLUMN) in conditions
        )
        if not kept:
            lines = ", ".join(repr(v) for v in tcgcsv.product_lines(export)) or "none"
            source = f" {export.source}" if export.source else ""
            # THE CONDITION AXIS IS NAMED HERE OR THE SENTENCE IS FALSE. An export carrying
            # this game's rows in play grades ONLY — a plausible hand-download with the wrong
            # box ticked — used to refuse with a message about `Product Line`, sending the
            # operator to look at the one column that was right. The two cases are told apart
            # rather than blurred: `mine` is what the partition kept.
            if mine:
                offered = ", ".join(
                    sorted({str(r.get(tcgcsv.CONDITION_COLUMN) or "") for r in mine})
                ) or "none"
                raise EmptyCatalog(
                    f"the export{source} holds {len(mine)} row(s) for game {game!r} and not "
                    f"one of them is a condition this product lists (D12 — Near Mint): it "
                    f"offers {offered}, and this join reads {', '.join(sorted(conditions))}. "
                    f"Re-export without the condition filter — nothing was joined and nothing "
                    f"was written."
                )
            raise EmptyCatalog(
                f"the export{source} holds no rows for game {game!r} "
                f"(Product Line {line!r}"
                + (f", Rarity in {rarities!r}" if rarities else "")
                + f"); its own Product Line cells are: {lines}. This is the wrong file "
                f"for this game — nothing was joined and nothing was written."
            )
        return cls(
            tcgcsv.Export(header=export.header, rows=kept, source=export.source),
            game=game,
            dropped_rows=len(export.rows) - len(mine),
            dropped_off_condition=len(mine) - len(kept),
        )

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
        exposure is a number, not an assumption.

        IN THE EXPORT'S OWN SPELLING, not the fold. This list is printed in a run report and
        pasted into a search box, and `3/159` is a string that appears nowhere in the file
        the reader is holding. `sets_for_key` folds what it is given, so a caller can hand
        one of these straight back."""
        return sorted(
            self._cell_by_key.get(key, key)
            for key, sets in self._sets_by_key.items()
            if len(sets) > 1
        )

    def sets_for_key(self, key: str) -> List[str]:
        """The sets a key reaches. Folds a number key; a `name:` key is passed through.

        `_sets_by_key` holds both kinds — folded numbers, and `name:<product name>` for the
        blank-`Number` rows — so folding unconditionally would mangle the second. The prefix
        is the discriminator, and it is a literal here rather than a constant because it is
        built as one two methods up, in the loop this reads back.
        """
        if not key.startswith("name:"):
            key = number_index_key(key)
        return list(self._sets_by_key.get(key, ()))

    def row_for_sku(self, sku: str) -> Optional[tcgcsv.Row]:
        """The one row a SKU names, or None when this export does not carry it.

        For rung 0: a review answer names a SKU, and a SKU is TCGplayer's own identity for
        one row, so the lookup is direct and can never be ambiguous. None is a real answer
        — an answer taken against one export is being joined against another that dropped
        the row — and the caller falls through to the ladder rather than guessing."""
        index = self._order.get(sku)
        return None if index is None else self.export.rows[index]

    def rows_for_key(self, key: str) -> List[tcgcsv.Row]:
        """Rows whose `Number` cell is this one, whatever either side's padding or case.

        THE FOLD IS INSIDE THE ACCESSOR AND NOT AT THE CALL SITES, deliberately. Three
        strategies reach for this — a composed `031/197`, a printed `066a/298`, and whatever
        a future one composes — and asking each of them to remember to fold first is asking
        for the same drift back. One door, one rule.
        """
        return list(self._by_number.get(number_index_key(key), ()))

    def rows_for_blank_number_name(self, name: str) -> List[tcgcsv.Row]:
        return list(self._blank_number_by_name.get(name.strip(), ()))

    def rows_for_name(self, name: str) -> List[tcgcsv.Row]:
        """Every NUMBERED row whose folded name is this one. D35's last resort.

        Answers rows the caller must not list on that basis alone — see
        `_walk` for the rung and `join_batch` for the routing
        that keeps a card found this way in front of a human.

        `_name_compare_key(name)`, CATALOG-SIDE OFF — the query is the MODEL's read, never
        a catalog row, so nothing here strips a trailing qualifier; it is folded through
        the same NFKD/accent pass `_by_name` was built with (`catalog_side=True`), so the
        two sides of the lookup use one fold rather than two that happen to agree today.
        """
        return list(self._by_name.get(_name_compare_key(name), ()))

    def candidates(self, card: IdentifiedCard) -> Candidates:
        """Rows this card could be, and how they were found.

        WHICH KEY IS TRIED IS THE GAME'S CALL (D21/D25), read out of the registry rather
        than decided here. `pokemon` names `number_and_printed_total`, which is the number
        with the blank-`Number` name fallback underneath it — exactly the two branches this
        method used to hold inline — so a Pokemon card takes the same path it always did.
        """
        # A strategy answers two elements or three — see the dispatch block above for why
        # the third is a value rather than a prefix on `lookup`.
        answer = lookup_for(card.game)(self, card)
        rows, lookup, name_inferred = (
            answer if len(answer) == 3 else (answer[0], answer[1], False)
        )

        sets: List[str] = []
        for row in rows:
            name = row.get(tcgcsv.SET_COLUMN, "")
            if name not in sets:
                sets.append(name)

        if len(sets) <= 1:
            return Candidates(
                rows=tuple(rows), lookup=lookup, name_inferred=name_inferred
            )

        # Rung 3 of §5.1 — a colliding key, disambiguated by the sidecar set hint. THE SET IS
        # CHOSEN FIRST AND THE ROWS ARE FILTERED TO IT, rather than every row being asked
        # whether it matches: asked row by row, a hint answering to two of the candidate sets
        # narrowed to BOTH of them and returned that as decisive. `setnames.resolve` answers
        # `None` on a tie, so such a card falls through to rung 4 and faces a human (D2, D3).
        if card.set_hint:
            chosen = setnames.resolve(card.set_hint, sets)
            narrowed = (
                [row for row in rows if row.get(tcgcsv.SET_COLUMN, "") == chosen]
                if chosen is not None
                else []
            )
            if narrowed:
                return Candidates(
                    rows=tuple(narrowed),
                    lookup=f"{lookup} set:{card.set_hint}",
                    name_inferred=name_inferred,
                )

        # Rung 4 — no hint, or a hint naming none of the candidates.
        return Candidates(
            rows=tuple(rows),
            lookup=lookup,
            set_ambiguous=True,
            candidate_sets=tuple(sets),
            name_inferred=name_inferred,
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
    #: The cap this send asked for, or `None` for no bound (D7, rewritten 2026-09-07). `None` is the
    #: ordinary value: the standing cap of four was retired and a cap is now something a send
    #: asks for, through `emit --cap N` and nothing else — the standing `policy.live_cap`
    #: was deleted 2026-09-08. `LIVE_QUANTITY_CAP` survives as a figure a press MAY propose
    #: and as the harness's fixture bound; nothing falls back to it.
    live_cap: Optional[int] = None
    #: THE COPIES THIS SEND ASKED TO LIST FOR THIS CARD, or `None` for every copy that can go
    #: (D7, amended 2026-09-11 on the operator's ruling). A SEND QUANTITY and not a ceiling:
    #: `2` puts two copies in the file whatever TCGplayer already holds, bounded by the copies
    #: on hand that are not already listed. `0` is a real answer — none of this card this
    #: press, without a standing hold. Named per SKU because the ruling was *case by case*:
    #: `emit --quantity SKU=N`, and the Qty field on every `#/pricing` row.
    asked: Optional[int] = None
    rule: pricing.Rule = pricing.MATCH
    basis: str = pricing.BASIS_MARKET
    # The D9 cut-off this match was partitioned against — the operator's stored
    # `policy.threshold` (`pipeline/corpus.py`), or the module constant for a store that has
    # never set one. A FIELD BESIDE `rule` AND `basis` AND NOT A READ OF THE CONSTANT: a
    # match carries the policy it was built under, so a report cannot answer `listable` with
    # a figure that was changed after it was computed.
    #
    # IT IS THE FLOOR TOO, AND THERE IS DELIBERATELY NO SECOND FIELD (D9, amended
    # 2026-09-09). The cut-off is the cheapest price this store lists anything at, so
    # `list_price` clamps at it and `prices_for` resolves a `flat_floor` disposition at it. A
    # `floor` field beside this one would be a figure `pipeline/merge.py` has to carry, a key
    # `_agree_policy` has to compare and a control `#/pricing` has to offer, all so the
    # operator could set two numbers that are incoherent in every arrangement but equal.
    threshold: Decimal = pricing.THRESHOLD
    # Copies TCGplayer already holds, plus the copies that have left inventory — see
    # `IdentifiedCard.committed`. Subset of `positions`; they take nothing from the import
    # file, which is where `cli/cmd_emit.py`'s idempotence actually lives (D54).
    #
    # THEY NO LONGER OCCUPY ROOM UNDER THE CAP, and that clause used to be in this comment.
    # `add_to_quantity` below says why (D59).
    committed_positions: List[Position] = field(default_factory=list)
    # `cli/resolve.py:_copies_out` for this SKU: what TCGplayer holds, live and pending,
    # across EVERY box. `None` for a match built without a store — every synthetic
    # `join_batch` in the harness — and the answer there is `live_before` alone, which is
    # D7's own `min(cap - live, backstock)` and what those cases have always asserted.
    held_out: Optional[int] = None
    # `cli/resolve.py:_copies_out`'s `live_now` for this SKU: the NEWER of the store's own
    # `live` reading and the export's, by `store/master.py:Listing.live_reading` (D87,
    # amended). `None` for a store-less match, where the row alone answers — `live_before`.
    live_out: Optional[int] = None

    @property
    def condition(self) -> str:
        return self.row[tcgcsv.CONDITION_COLUMN]

    @property
    def set_name(self) -> str:
        return self.row.get(tcgcsv.SET_COLUMN, "")

    @property
    def rarity(self) -> str:
        """The catalogue's own rarity for this row (D213).
        Stored beside `set_name` at the same write and for the same reason: both are read off
        the row `sku` already resolved to, not re-derived or asked for."""
        return self.row.get(tcgcsv.RARITY_COLUMN, "")

    @property
    def name(self) -> str:
        """The card's own name, off the export row.

        Added for the pricing surfaces (D49), which name a SKU to a human in three places —
        a watch line, a warning and the per-SKU table — and had `self.row[NAME_COLUMN]`
        written out at each. `set_name` and `condition` above are the same accessor for the
        same reason: the column constant belongs in one place per fact.
        """
        return self.row.get(tcgcsv.NAME_COLUMN, "")

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
    def uncommitted_positions(self) -> List[Position]:
        """The copies this run may still list — everything TCGplayer does not hold yet."""
        held = {(p.box, p.index) for p in self.committed_positions}
        return [p for p in self.positions if (p.box, p.index) not in held]

    @property
    def live_now(self) -> int:
        """The live figure the cap was computed against: the newer of the store's reading
        and this row's, or the row's alone where no store was consulted. What every
        SENTENCE about live quantity reads, so "4 live, at the cap of 4" can never be
        printed off a reading the store has since superseded — D59's own rule about a
        count under a false sentence."""
        if self.live_out is None:
            return self.live_before
        return self.live_out

    @property
    def copies_out(self) -> int:
        """Copies TCGplayer is holding for this SKU right now — live plus pending, per SKU
        and across every box.

        THE FLOOR IS THE NEWEST READING OF `live`, AND `_copies_out` HAS ALREADY APPLIED IT.
        This was `max(self.live_before, self.held_out)` until 2026-09-02, on the argument
        that the export's `Total Quantity` is a floor the store may never argue down. It is
        — for the moment it was read. `max` with the row's own column let an OLDER file
        outrank a newer store observation: with the store newer and lower, `_copies_out`
        answered 2 and the `max` put the file's 4 back, so a stale export closed the cap
        against a reading the store took after it. `held_out` is the arbitrated figure and
        it answers alone."""
        if self.held_out is None:
            return self.live_before
        return self.held_out

    @property
    def add_to_quantity(self) -> int:
        """New copies only: what the cap has room for, bounded by what this run holds.

        `len(self.committed_positions)` used to stand where `copies_out` does, and it was
        wrong in three ways in one expression (D59). It is RUN-SCOPED against a global cap,
        so a SKU split across two boxes was capped once per box — box 1 wrote four rows and
        a run over box 3 wrote two more. It subtracted every departed copy a SECOND time: a
        SOLD one TCGplayer had already decremented and `live_before` had already counted,
        and a RETIRED one whose row is still out there and is therefore inside
        `copies_not_sold`'s ceiling rather than a separate term. Either way a card that had
        left shrank what its SKU could ever list — five copies with four retired and nothing
        ever pushed offered nothing at all. And it read `pushed`, which has no drawdown, so
        once the import landed the same copies were subtracted twice.

        `committed_positions` KEEPS THE JOB IT IS GOOD AT — keeping a copy out of the
        sellable set, which `uncommitted_positions` reads it for. The cap reads a quantity.
        """
        # NO CAP IS THE ORDINARY CASE SINCE D7's rewrite, and it is not "a very large cap". The bound
        # is simply absent: every copy this run holds that TCGplayer does not already have
        # goes. `uncommitted_positions` is what still stops a copy being sent twice — this
        # method's own docstring separates the two jobs, and only the second was retired.
        room = self.room
        # AND THE SEND'S OWN ANSWER FOR THIS CARD BOUNDS IT LAST (D7, amended 2026-09-11). A
        # quantity is what the operator typed for THIS press; it can only take copies out of
        # the file, never put in copies the ceiling or the shelf refuse. `0` is honoured as
        # "none of this card this press", and `nothing_to_add` names it in those words.
        if self.asked is None:
            return room
        return max(0, min(self.asked, room))

    @property
    def room(self) -> int:
        """What could go before this send's own quantity is applied: every copy TCGplayer does
        not already hold, under the ceiling when one was asked for. `add_to_quantity` is this
        bounded by `asked`, and the report reads both to say *asked 5, 3 can go*."""
        if self.live_cap is None:
            return len(self.uncommitted_positions)
        ceiling = self.live_cap - self.copies_out
        return max(0, min(ceiling, len(self.uncommitted_positions)))

    @property
    def asked_short(self) -> bool:
        """The send asked for more of this card than can go. Named, never clamped silently."""
        return self.asked is not None and self.asked > self.room

    @property
    def nothing_to_add(self) -> Optional[str]:
        """Why this run adds no row for a SKU it matched — or None when it adds one.

        NAMED RATHER THAN COUNTED (D59). `at_cap` printed "already at the live cap" for
        every zero, and under an operator who does not reconcile that is almost never the
        reason: `live_before` reads 0 on all 167 pushed copies in the owner's store, so the
        report and `#/pricing` both said TCGplayer already holds nothing. A card that stops
        appearing in import files is the silent drop `CLAUDE.md` forbids, and a count under a
        false sentence is worse than no count.
        """
        if self.add_to_quantity or not self.copies:
            return None
        if not self.uncommitted_positions:
            return "every copy in this run is already listed or has left the box"
        # THE SEND'S OWN ANSWER, BEFORE ANY SENTENCE ABOUT A CAP (D7, amended 2026-09-11): a
        # zero typed for this card is why nothing goes, and it is not a hold, so the way
        # back is the field and not the corpus.
        if self.asked == 0:
            return "this send asked for none of this card"
        # `live_now`, never `live_before`: the sentence names the reading the cap was
        # computed from, which is the newer of the store's and the export's (D87, amended).
        pending = self.copies_out - self.live_now
        # EVERY SENTENCE BELOW NAMES A CAP, SO NONE OF THEM MAY BE REACHED WITHOUT ONE (D7, rewritten).
        # With no cap `add_to_quantity` is `len(uncommitted_positions)`, so reaching this line
        # at all means that list is empty — which the branch above already answered. The guard
        # is here because an UNREACHABLE branch that would print "at the cap of None" is one
        # refactor away from being reachable, and a false sentence is what this method's own
        # docstring exists to prevent.
        if self.live_cap is None:
            return "every copy in this run is already listed or has left the box"
        if pending <= 0:
            if self.copies_out > self.live_cap:
                return f"{self.live_now} live, over the {self.live_cap} this send asked for"
            return f"{self.live_now} live, at the cap of {self.live_cap}"
        # THE OVERRUN IS THE ANSWER WHEN THERE IS ONE, and `min` was hiding exactly that
        # (D7, amended 2026-09-08). A cap is a ceiling on copies LIVE, so the reason this SKU
        # adds nothing is that `copies_out` already meets or exceeds the figure asked for —
        # and `min(copies_out, live_cap)` clamped the very number that explains it, printing
        # "2 of the 2 this SKU may have out" where the true state was seven out against a cap
        # of two. The original argument was that "6 of the 4 is not a sentence"; that is a
        # reason to WORD the overrun, not to suppress it. Under a standing cap the two were
        # rarely far apart and this read fine for months — with the cap asked for per send,
        # an overrun is the ordinary case and the operator cannot act on a hidden figure.
        if self.copies_out > self.live_cap:
            return (
                f"{self.copies_out} already out against the {self.live_cap} this send asked "
                f"for — {self.live_now} live and {pending} on an import this pipeline has "
                f"not seen land"
            )
        return (
            f"{self.live_now} live and {pending} on an import this pipeline has not "
            f"seen land — {self.copies_out} of the {self.live_cap} "
            f"this SKU may have out"
        )

    @property
    def backstock(self) -> int:
        return len(self.uncommitted_positions) - self.add_to_quantity

    @property
    def live_positions(self) -> List[Position]:
        return self.uncommitted_positions[: self.add_to_quantity]

    @property
    def backstock_positions(self) -> List[Position]:
        return self.uncommitted_positions[self.add_to_quantity :]

    @property
    def list_price(self) -> Optional[Decimal]:
        """`clamp_floor(round(rule(basis)))`. None when the basis cell is blank.

        THE FLOOR IS THIS MATCH'S OWN CUT-OFF AND NOT `pricing.FLOOR` (D9, amended
        2026-09-09). One figure, carried once: `threshold` above is the operator's stored
        `policy.threshold`, it is the cheapest price this store lists anything at, and
        clamping at it is what keeps the rule's output inside the partition the same figure
        drew. Reading the module constant instead priced a card the operator's own cut-off
        calls listable ABOVE its market — market $0.32 at a cut-off of $0.29, `match`,
        clamped to $0.40 — while the sub-threshold half of the same box went out at $0.29.
        """
        basis = self.basis_price
        if basis is None:
            return None
        return pricing.list_price(basis, rule=self.rule, floor=self.threshold)

    @property
    def listable(self) -> bool:
        return pricing.is_listable(self.market_price, self.threshold)


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
        # `where_phrase`, not the label: a pooled game's card has no position to name, and
        # this line is a run report — one of the surfaces the pooled ruling forbids the
        # label on. A located card reads exactly as it always did.
        return (
            f"{self.card.name} [{self.lookup}] {self.reason} "
            f"{where_phrase(self.card.game, self.card.position)} (candidates: {conditions})"
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
            f"{self.copies} copies"
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
    # WHICH OF THOSE ROWS THE READ NAME FOUND, by SKU, for a `name_disputed` card whose
    # candidate list holds both readings of one photograph (`name_alternatives`).
    #
    # A SEPARATE FIELD RATHER THAN A FLAG ON THE ROW, because a `tcgcsv.Row` is a line of the
    # operator's export and this is a fact about how this card reached it. The same row is a
    # name match for one card and a number match for another, so the provenance cannot live
    # on the row without being wrong for somebody.
    #
    # EMPTY ON EVERY OTHER ENTRY, and that is the whole of its contract: a list with one
    # provenance does not need it stated, so `cli/resolve.py:_candidate_rows` stamps nothing
    # unless this is non-empty. Nothing about any other reason code moves.
    name_matched_skus: Tuple[str, ...] = ()

    @property
    def queue(self) -> str:
        return self.destination.queue

    @property
    def describe(self) -> str:
        # Same rule as `UnmatchedCard.describe`: the phrase, so a pooled card's line
        # carries the pooled fact and its key rather than a label it must never render.
        return (
            f"{self.card.name} [{self.lookup}] -> {self.destination.describe} "
            f"{where_phrase(self.card.game, self.card.position)}"
        )


@dataclass
class JoinReport:
    matches: "OrderedDict[str, SkuMatch]" = field(default_factory=OrderedDict)
    unmatched_cards: List[UnmatchedCard] = field(default_factory=list)
    queued: List[QueuedCard] = field(default_factory=list)
    below_threshold: SubThresholdBucket = field(default_factory=SubThresholdBucket)
    cards_in: int = 0
    collisions: int = 0
    # D253 — `(box, index) -> catalog product name`, for a card whose
    # read name AGREED with the row it resolved to WITHOUT being byte-identical to it (the
    # near-miss half of `name_corroborates`, never the exact half — that has nothing to
    # correct — and never a disputed card, whether it settled onto the name's own row or
    # stayed in review: both are excluded structurally, see `join_batch`). Empty on every
    # other card. `cli/cmd_emit.py` is the one reader, through `cli/resolve.py:Resolved
    # .name_corrections` — the moment it commits a SKU to a position is the moment
    # `SkuMatch.name` (the row this dict was built from) is in hand to write over
    # `Card.name`, exactly as `set_name` and `rarity` already do at that same write
    # (D213). The model's own reading is untouched here and stays in the run's
    # `identifications.json` as evidence.
    name_corrections: Dict[Tuple[int, int], str] = field(default_factory=dict)

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
        """Matched SKUs this run adds nothing for. The cap is only one of the reasons —
        `SkuMatch.nothing_to_add` names the actual one per SKU (D59). Not written to
        the import file, and reported rather than skipped — the copies are real cards
        sitting at real positions.

        THE NAME OUTLIVED THE RULE AND IS KEPT ANYWAY (D7, rewritten 2026-09-07). With no
        standing cap the cap is usually not a reason at all: every one of these is a SKU
        whose copies are already listed or have left the box, and the cap becomes a
        reason again only for a send that asked for one. It stays `at_cap` because it is
        a WIRE FIELD three screens read and `nothing_to_add` beside it has always been
        what says which reason — renaming it would move a name and not a fact."""
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
            # THE HEADING WAS THE FALSE SENTENCE AND ONLY THE ROWS BENEATH IT WERE FIXED
            # FIRST (D59). "already at the live cap" is almost never the reason under an
            # operator who does not reconcile — `live_before` reads 0 on all 167 pushed
            # copies in the owner's store — so a corrected row under an uncorrected heading
            # is this repo's standing failure shape: a premise deleted while its conclusion
            # is left standing, which two other entries record and neither is about joins.
            lines.append(f"matched but added nothing: {len(self.at_cap)}")
            lines += [
                f"    {m.sku} {m.row[tcgcsv.NAME_COLUMN]} copies={m.copies} — "
                f"{m.nothing_to_add}"
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
        # A human answer also outranks the confidence gate: low confidence measures how
        # legible the MODEL found the card, and the review screen exists so a person looks
        # instead. Routing an answered card back to review for the model's uncertainty
        # would re-ask a question the human answered while looking at the same photograph.
        confidence = (
            None if resolution.stage == variant.HUMAN_ANSWERED else card.confidence
        )
        return routing.route(
            resolved=resolved,
            reason=resolution.reason,
            confidence=confidence,
            price=resolution.market_price,
            candidate_prices=found.market_prices,
            threshold=threshold,
            review_below=review_below,
        )

    return route


def join_batch(
    cards: Sequence[IdentifiedCard],
    catalog: Catalog,
    live_cap: Optional[int] = None,
    router: Optional[Router] = None,
    rule: pricing.Rule = pricing.MATCH,
    basis: str = pricing.BASIS_MARKET,
    copies_out: Optional[Mapping[str, int]] = None,
    threshold: Decimal = pricing.THRESHOLD,
    live_now: Optional[Mapping[str, int]] = None,
    quantities: Optional[Mapping[str, int]] = None,
) -> JoinReport:
    """Resolve every card to exactly one catalog row, aggregating copies by SKU.

    With a `router`, every card that does not list is written into `report.queued` with the
    queue it belongs in — reviews stop suppressing output, because the card is recorded
    (v2 §5.6). Without one, ladder failures land in `unmatched_cards` and `report.ok` is
    False, which is the pre-v2 behaviour and still what `emit_import` refuses on.
    """
    pricing.check_basis(basis)
    rule = pricing.Rule.parse(rule)
    # ONE PARSE FOR THE WHOLE BATCH, and the partition below reads the result rather than the
    # constant. A stored threshold arrives as the string it was typed as; every match built
    # here carries the same `Decimal`.
    threshold = pricing.check_threshold(threshold)
    report = JoinReport(cards_in=len(cards), collisions=len(catalog.colliding_keys))

    for card in cards:
        found = catalog.candidates(card)

        # THE NAME CROSS-CHECK, COMPUTED ONCE AND READ TWICE. Both directions of the same
        # comparison, and both are decided HERE rather than in the ladder: `name_index_key`
        # is this module's fold and `pipeline/variant.py` importing it back would put the
        # rule in two places, where the whole argument for the fold is that there is one.
        #
        # Evaluated before rung 0 and used after it, deliberately. A human's answer outranks
        # both halves — D23 says so in as many words — and the two flags below are read only
        # on the branches rung 0 did not take.
        corroborated = name_corroborates(card.name, found.rows)
        disputed = name_disputes(card.name, found.rows)

        # Rung 0 — a human already answered this card on the review screen, and the answer
        # outranks everything below, including a set collision: the SKU names one row with
        # no key to collide. An answer whose row this export no longer carries (or carries
        # under a different condition — a SKU is one condition, so that is export damage)
        # falls through to the ladder rather than being guessed at.
        answered_row = None
        if card.answered_sku is not None:
            row = catalog.row_for_sku(card.answered_sku)
            if row is not None and (
                card.answered_condition is None
                or row[tcgcsv.CONDITION_COLUMN] == card.answered_condition
            ):
                answered_row = row

        if answered_row is not None:
            resolution = variant.answered(answered_row)
        elif found.set_ambiguous:
            # A colliding key the set hint could not break. Never guessed (§5.1 rung 4).
            resolution = variant.Resolution(
                stage=variant.REVIEW, reason=routing.SET_AMBIGUOUS
            )
        else:
            # `game=` IS NOT OPTIONAL HERE, AND OMITTING IT WAS THE LAST LIVE INSTANCE OF THE
            # POKEMON-ENUM LEAK. `variant.vocabulary` falls back to `games.DEFAULT_GAME`
            # without it, so every card of every game was resolved against Pokemon's three
            # finishes — and `_check_claim` RAISES `UnknownFinish` rather than refusing
            # politely, so a Riftbound card whose sidecar claims `foil` (a finish its own
            # registry entry authors and the capture screen offers) took the whole join down.
            # `variant.vocabulary`'s docstring and `cli/resolve.py`'s detected-finish
            # whitelist each record fixing this at their own layer on 2026-08-23; this call
            # site is one layer above both and was missed. Reached only after
            # `catalog.candidates` has already put `card.game` through `lookup_for`, so a
            # `misc` card refuses there and this can never be handed a game `require` rejects.
            resolution = variant.resolve(
                found.rows,
                metadata_finish=card.metadata_finish,
                detected_finish=card.detected_finish,
                rarity_claim=card.rarity_claim,
                game=card.game,
                # D23's cross-check released by two agreeing signals. The ladder decides
                # what to do with it; this module decides what it IS.
                name_corroborated=corroborated,
            )

        # D35 — THE ROW WAS FOUND BY NAME, SO IT IS NOT LISTED ON THAT ALONE.
        #
        # The rung below `_walk`'s blank-number fallback answers
        # rows for a card whose collector number could not be read. The ladder then does its
        # ordinary work on them and, on a stack with a one-member finish claim, resolves
        # cleanly — which would list the card. That is the outcome this block refuses.
        #
        # The number is the field that distinguishes one card from another, and it is exactly
        # the field that is missing. What is left is a name, a set the operator declared for
        # the stack, and a photograph — and the photograph is the part no code can read. So
        # the card is queued with the row the ladder chose, and a human confirms it against
        # the picture. That is D4's argument, applied to a card that resolved.
        #
        # IT IS NOT ONE PRESS PER CARD. Every entry from this path carries ONE candidate (the
        # ladder's row, narrowed below) under ONE shared reason, and a uniform stack gives one
        # shared condition string — which is D29's group-answer eligibility exactly. Box 2's
        # 45 are one `G`, one Enter and one `U` to reverse, over a grid of their photographs.
        #
        # `found` is narrowed to the resolved row so the queue entry offers one candidate and
        # routing cuts on that row's own price rather than on the cheapest of a pair the
        # ladder has already chosen between.
        #
        # RUNG 0 IS ABOVE THIS BLOCK, NOT INSIDE IT, AND LEAVING IT OUT WAS A SILENT DROP.
        # D3 rung 0 is a human's answer, applied a few lines above, and D23 already states the
        # rule this clause enforces: *"Rung 0 must not consult it. A human who looked at the
        # photograph beside the candidate rows outranks a claim about the stack it came from."*
        # A `HUMAN_ANSWERED` resolution carries a row and does not need review, so without the
        # `stage` test below it satisfied every condition here and was overwritten straight
        # back into a review reason.
        #
        # What that cost is the whole feature. D35's own argument for queuing rather than
        # listing is that box 2's 45 cards are ONE `G` and ONE Enter — and the join after that
        # press re-raised the identical question on every one of them. `store/queues.py:upsert`
        # then refuses to re-queue a position a human has cleared, deliberately, so the card
        # was not re-queued EITHER: not listed, not in the queue, gone from both ends of the
        # pipeline until somebody went looking for it. `CLAUDE.md` forbids exactly that.
        #
        # It is the failure D3 rung 0 was written for, one rung further down. Gate B's record
        # of it is the sentence to keep: an answer that does not outlive the question is not
        # an answer.
        #
        # RELEASED WHERE THE NAME RESOLVES TO EXACTLY ONE CARD, ON THE OWNER'S RULING OF
        # 2026-09-12: *"Release them when the name resolves to exactly one card."*
        #
        # THIS REPEALS THE OPERATIVE HALF OF D35's *"may never list a card on its own"*, and
        # the entry that does it carries the argument. What the ruling rests on is the
        # store's own record: 212 entries reached this rung, every one of them was answered
        # by a human, and in 212 OF 212 the human chose the SKU this block was already
        # holding. Not one disagreed. A question whose answer is known before it is asked,
        # asked 212 times, is the shape D29 and D146 were both written about.
        #
        # WHAT SURVIVES OF D35 IS ITS CAUTION ABOUT A WEAK NAME, and that caution is now the
        # gate rather than a blanket. A name that answers TWO cards is exactly the evidence
        # D35 distrusted, and it still queues — with its photograph, as it always did.
        if (
            found.name_inferred
            and resolution.stage != variant.HUMAN_ANSWERED
            and not resolution.needs_review
            and resolution.row is not None
            and distinct_cards(found.rows) > 1
        ):
            found = replace(found, rows=(resolution.row,))
            resolution = variant.Resolution(
                stage=variant.REVIEW,
                reason=routing.NUMBER_UNREAD_NAME_MATCHED,
                row=resolution.row,
                condition=resolution.condition,
                market_price=resolution.market_price,
            )

        # THE SAME COMPARISON, RUN THE OTHER WAY — and the half that makes the rarity
        # release safe rather than merely quieter (`routing.NAME_DISPUTED`).
        #
        # The block above queues a card whose NUMBER could not be read. This one queues a
        # card whose number read fine, found real rows, and whose NAME says they belong to
        # something else. Both write a review reason over a resolution the ladder completed;
        # they are the two directions of one question and are deliberately adjacent.
        #
        # IT DOES NOT DEPEND ON THE RARITY CLAIM, AND THAT IS THE POINT. Nine box-1 cards
        # were waved through by a claim that happened to fit the wrong card's rows, so a
        # mirror gated on the claim would still miss every one of them. `1/51` is the case:
        # read `Irelia, Blade Dancer`, number `190/221`, rows say `Forgefire Cape`, rarity
        # `Epic` — claimed, agreed, listed, never asked about.
        #
        # ORDERED AFTER THE D35 BLOCK because that one is the more specific finding on the
        # card it fires for: a row reached WITHOUT its number, which is the stronger reason
        # to look, and whose name matched by construction so this can never fire on it.
        #
        # RUNG 0 IS EXEMPT, for the reason that block records at length. A human who looked
        # at the photograph has already answered the question this would ask, and re-raising
        # it is the sixteen-cards failure D3 rung 0 exists to prevent. `store/queues.py`
        # would not even re-queue the card: it would be listed nowhere and asked nowhere.
        # THE GATE WIDENED 2026-09-23 (D253). Until then this fired only
        # `not resolution.needs_review and resolution.row is not None` — a card the ladder
        # had already resolved OUTSIDE review. A card ALREADY queued for a reason of its
        # own — `rarity_claim_mismatch`, `ambiguous_no_signal`, `set_ambiguous`, … — never
        # reached here, and its payload offered only the number's (wrong) rows. Three of
        # thirteen hand-cleared entries measured with this shape were answered onto the
        # NUMBER's SKU although the read NAME disputed it, because that was the only row on
        # screen: `Frigid Jewel` read at `024/219`, queued `rarity_claim_mismatch` (no row
        # at all — that reason never carries one), offered only `Rengar, Unseen`. The owner's
        # ruling: match off name and number; where they still disagree after a fuzzy
        # recorrection, it goes to review WITH suggested options from both signals,
        # `resolution.row is not None` DROPPED for the identical reason — a card queued
        # for a reason of its own may carry no row to be `is not None` about.
        name_matched_skus: Tuple[str, ...] = ()
        if disputed and resolution.stage != variant.HUMAN_ANSWERED:
            # BOTH ROWS, THE NAME'S FIRST — and it offered only the number's until 2026-09-12.
            #
            # D35's block above narrows to the resolved row because there is only one reading
            # to show: the number could not be read at all, so the name's row IS the answer.
            # Here there are two readings and they disagree, and narrowing to one of them
            # meant narrowing to the one this very block has just decided is suspect. The
            # operator's words on finding it: *"i had to click L to see this option -- the
            # initial suggestion is just [the wrong card]"*, and then the shape of the fix:
            # *"it could've suggested both, say hard bargain and factory recall both on the
            # same page."*
            #
            # THE NAME GOES FIRST BECAUSE OF WHAT THE NINE MEASURED, not because a name
            # outranks a number in general. In nine of nine the name was right; digit `1` is
            # therefore the answer on every one of them, and the ordering is worth exactly
            # the one press it saves. Where the name finds nothing the list is what it always
            # was — the number's row alone — so a card this rung cannot help is unchanged.
            #
            # NOTHING HERE DECIDES. The card is queued either way and no row is listed on a
            # name (D35's ruling, untouched); what moved is which rows a human is shown.
            # ONE LOOKUP, READ TWICE. `name_alternatives` narrows these rows and the gate
            # below counts the CARDS among them; fetching the name twice would let the two
            # answers disagree if a later edit moved either one.
            named = catalog.rows_for_name(card.name)
            side = name_alternatives(named, card, resolution.row)
            alternatives = side.rows

            # THE NAME DECIDES WHERE IT RESOLVES TO EXACTLY ONE CARD — the owner's ruling of
            # 2026-09-12, in their words: *"Release them when the name resolves to exactly
            # one card."*
            #
            # MEASURED OVER EVERY `name_disputed` ENTRY THE STORE HAS EVER RECORDED, all
            # nine: the name was right and the number wrong in NINE OF NINE. Eight of the
            # nine names answer exactly one card; the ninth answers two (`Aspirant's Climb`,
            # printed in Origins and again as a promo) and is precisely the card this gate
            # keeps in front of a person. Seven have since been answered by hand and in
            # SEVEN OF SEVEN the operator chose a row the name found.
            #
            # THIS IS NOT "TRUST THE NAME". It is: where two readings of one photograph
            # disagree and one of them resolves to a single card while the other is
            # contradicted by it, the resolving one is the stronger evidence. Where the name
            # resolves to two cards, or the ladder cannot settle the finish beneath it,
            # nothing is decided here and the card faces a human with its photograph and
            # BOTH readings on the list — which is the branch below.
            # `side.settled` AND NOT `len(alternatives) == 1`. The two agree on most
            # cards and part company on the one that matters: a name answering a card the
            # export stocks in ONE finish returns one row whether the ladder settled it or
            # REFUSED it, and releasing the second is listing a card on a finish the ladder
            # rejected. `Alcremie ex` is that card on the committed fixture.
            #
            # "EXACTLY ONE CARD" COUNTS PRODUCTS THE RARITY CLAIM AGREES WITH, WHEN THERE
            # IS ONE — CORRECTED 2026-09-23, a review finding. `named` alone answers a
            # PRODUCT count that a qualifier variant (`rows_for_name` now reaching it,
            # D253) can raise past one even where the claim already
            # picks a single product out of it: `Pyke, Returned` (base, Rare) and
            # `Pyke, Returned (Alternate Art)` (Showcase) are two products under one
            # folded name, and a `rarity_claim=['Showcase']` names exactly one of them.
            # THAT IS A SECOND AGREEING SIGNAL, D146's own shape — the name narrows the
            # search to one card's every printing, the claim narrows within that to one
            # printing — so it may release, the same way two signals release a rarity
            # contradiction elsewhere in this ladder. ONLY THE RARITY CLAIM COUNTS FOR
            # THIS, never the finish claim: two prints of one name generally differ in
            # RARITY, and nothing here argues a finish claim ever tells two PRODUCTS
            # apart, only two conditions of the SAME one. Where there is no rarity claim
            # at all, this is `distinct_cards(named)` exactly as before — unchanged for
            # every card this rung already released correctly.
            products = distinct_cards(
                variant.rarity_filter(named, card.rarity_claim)
                if card.rarity_claim
                else named
            )
            settled = side.settled and products == 1
            if settled:
                chosen = alternatives[0]
                if resolution.needs_review:
                    # THE CARD WAS ALREADY HEADED TO REVIEW FOR A REASON OF ITS OWN, and
                    # that reason has no stage to inherit — a review Resolution carries no
                    # finish decision, only a refusal. `side.resolution` is the ladder's
                    # own answer over the NAME's rows (`name_alternatives`, same claims),
                    # and it is what decided `chosen`, so its stage and reason describe
                    # this SKU honestly, where the reason it is replacing no longer does.
                    settled_by = side.resolution
                    assert settled_by is not None  # `side.settled` guarantees this
                    stage, reason = settled_by.stage, settled_by.reason
                else:
                    # UNCHANGED FROM 2026-09-12: the NUMBER already resolved a row outside
                    # review, and the name settles the dispute onto a DIFFERENT row without
                    # unsettling how that finish was decided.
                    stage, reason = resolution.stage, resolution.reason
                resolution = variant.Resolution(
                    stage=stage,
                    reason=reason,
                    row=chosen,
                    condition=str(chosen[tcgcsv.CONDITION_COLUMN]),
                    market_price=tcgcsv.parse_price(chosen[tcgcsv.MARKET_PRICE_COLUMN]),
                )
                found = replace(found, rows=(chosen,))
                name_matched_skus = (str(chosen[tcgcsv.SKU_COLUMN]),)
            else:
                # THE NUMBER'S OWN ROWS, WHATEVER THEY ARE. A card the ladder had already
                # resolved outside review carries exactly `resolution.row`, one row,
                # unchanged from 2026-09-12. A card already queued for another reason may
                # carry none at all — `rarity_claim_mismatch` and `ambiguous_no_signal`
                # never set one, and `set_ambiguous` is built the same way — so the
                # fallback is every row the NUMBER found, `found.rows` exactly as
                # `catalog.candidates` returned it, before this block ever touches it.
                numbers_rows = (
                    (resolution.row,)
                    if resolution.row is not None
                    else tuple(found.rows)
                )
                found = replace(found, rows=alternatives + numbers_rows)
                name_matched_skus = tuple(
                    str(row[tcgcsv.SKU_COLUMN]) for row in alternatives
                )
                resolution = variant.Resolution(
                    stage=variant.REVIEW,
                    # THE PRIMARY REASON SURVIVES UNCHANGED where the card already had
                    # one — owner's ruling: the card is still queued for what it was
                    # queued for, and only which rows it is queued WITH has grown. A card
                    # the ladder had resolved outside review still gets the dispute's own
                    # reason, exactly as before 2026-09-20.
                    reason=(
                        resolution.reason
                        if resolution.needs_review
                        else routing.NAME_DISPUTED
                    ),
                    # STILL THE NUMBER'S ROW ON THE QUEUED BRANCH, AND DELIBERATELY SO.
                    # `resolution.row` is what routing prices the entry on; the name's rows
                    # are an OFFER to a human, and promoting one of them here without the
                    # gate above would be this module deciding a dispute it has just said it
                    # cannot settle. The screen ranks; the ladder does not.
                    row=resolution.row,
                    condition=resolution.condition,
                    market_price=resolution.market_price,
                )

        # D23 AMENDMENT — WIDEN BY NAME WHERE THE NUMBER'S OWN ROWS MISS THE RARITY CLAIM,
        # THEN RANK WHATEVER IS OFFERED. `set_ambiguous` never even reaches the ladder (it
        # fires in `catalog.candidates`, before `variant.resolve` runs), so a claim can sit
        # on a card whose number-found rows never had a chance to answer to it.
        # `rarity_claim_mismatch` and `ambiguous_no_signal` carry the same gap: neither
        # reason's rows are re-examined once the ladder gives up. `4/383` is the case: read
        # `Calm Rune` / `R02`, claimed `Showcase`, number found five `R02` Commons across
        # three sets — set_ambiguous, claim never consulted — while the three
        # `Calm Rune (R02a)` Showcase rows the claim names sat under a different number the
        # SAME NAME also answers to, offered nowhere.
        #
        # GATED ON A RARITY CLAIM, NOT ON THE OTHER TWO. A finish or set claim only ever
        # chooses AMONG rows the number already found — the ladder's own rungs 1 and the
        # set-hint rung already consult those before a card ever reaches here. A rarity
        # claim is the one axis that can be true of a row under a NUMBER NEITHER SIDE
        # READ, because the finish/rarity split lives one level below the number and the
        # set split lives at the number itself (D25's own collision). So this widens by
        # name only when the claim is the signal being missed.
        #
        # NEVER NARROWS, ONLY ADDS. `found.rows` keeps every row it already had — the
        # widen can never be the reason a row already offered disappears — and the name's
        # claim-matching rows are appended, deduped by SKU, whatever else the two blocks
        # above already did to the list.
        if (
            resolution.needs_review
            and card.rarity_claim
            and not variant.rarity_filter(found.rows, card.rarity_claim)
        ):  # MUTATED: reason-scope removed
            named = catalog.rows_for_name(card.name)
            claim_matching_named = rank_by_claims(
                variant.rarity_filter(named, card.rarity_claim), card
            )
            existing_skus = {str(row[tcgcsv.SKU_COLUMN]) for row in found.rows}
            widened = tuple(
                row
                for row in claim_matching_named
                if str(row[tcgcsv.SKU_COLUMN]) not in existing_skus
            )[:WIDEN_BY_CLAIM_LIMIT]
            if widened:
                found = replace(found, rows=found.rows + widened)
                name_matched_skus = name_matched_skus + tuple(
                    str(row[tcgcsv.SKU_COLUMN]) for row in widened
                )

        # RANK WHAT IS OFFERED, NEVER PICK ONE (D23 job (c), added this entry). A single-
        # row list is a no-op, so this changes nothing for the ordinary resolved card; it
        # reorders only a REVIEW entry whose card carries a rarity claim — the same gate
        # the widen above uses, so a claim that could not add a row can still move the
        # ones already offered to the front. Where the evidence favours no set over
        # another (no set hint, or every candidate row scores the same), `rank_by_claims`
        # is stable and leaves them in the order the catalog already put them in — ranked
        # equally, never chosen for the operator.
        if resolution.needs_review and card.rarity_claim:
            found = replace(found, rows=rank_by_claims(found.rows, card))

        # D253, THE NEAR-MISS HALF. A card that resolved OUTSIDE review
        # (whether the ladder settled it directly or the dispute above settled it here)
        # whose read name agreed with the row it landed on WITHOUT being byte-identical to
        # it — `Corfish` for `Corphish`, the model's own spelling a character or two out —
        # gets the catalogue's own spelling recorded as a candidate for the STORED name,
        # in `report.name_corrections`. The model's raw reading is untouched: it stays
        # exactly where `record_identification` already put it, in the run's own record.
        # A DISPUTED CARD NEVER REACHES THIS AS A NEAR MISS. One that settled above did so
        # onto the name's OWN row (`catalog.rows_for_name` is an exact fold lookup), so its
        # read is byte-identical to what it resolved to and there is nothing to correct;
        # one that did not settle is still `needs_review` and is excluded by that alone.
        if (
            resolution.row is not None
            and not resolution.needs_review
            and resolution.stage != variant.HUMAN_ANSWERED
            and not name_reads_exactly(card.name, resolution.row)
            and _name_compare_key(card.name)
        ):
            report.name_corrections[(card.position.box, card.position.index)] = str(
                resolution.row[tcgcsv.NAME_COLUMN]
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
                        name_matched_skus=name_matched_skus,
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
                # The send's own quantity for this card, or none (D7, amended 2026-09-11).
                asked=None if quantities is None else quantities.get(sku),
                rule=rule,
                basis=basis,
                threshold=threshold,
                # A store fact, and `pipeline/` may not read the store, so it arrives as a
                # value; absent means the export alone decides (D59).
                held_out=None if copies_out is None else copies_out.get(sku),
                live_out=None if live_now is None else live_now.get(sku),
            )
            report.matches[sku] = match
        match.positions.append(card.position)
        match.stages.append(resolution.stage)
        if card.committed:
            match.committed_positions.append(card.position)

    # Deterministic, and equal to the export's own order.
    report.matches = OrderedDict(
        sorted(report.matches.items(), key=lambda kv: catalog.catalog_index(kv[0]))
    )
    for match in report.matches.values():
        match.positions.sort(key=lambda p: (p.box, p.index))
        match.committed_positions.sort(key=lambda p: (p.box, p.index))

    # A row with no market price is NOT sub-threshold — it is unpriced, which D9 keeps as
    # its own category precisely so it cannot be swept into a flat bulk price.
    report.below_threshold = SubThresholdBucket(
        [m for m in report.matches.values() if m.has_market_data and not m.listable],
        threshold=threshold,
    )
    return report


class Undecided(Exception):
    """Sub-threshold SKUs are waiting on a disposition that nobody has given."""


def prices_for(
    report: JoinReport,
    sub_threshold: Optional[pricing.Disposition] = None,
    sku_dispositions: Optional[Dict[str, pricing.Disposition]] = None,
    no_market_data: Optional[Dict[str, object]] = None,
    withheld: Optional[Set[str]] = None,
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
    # THE OPERATOR IS DELIBERATELY NOT LISTING THESE (D49). Absent from the returned mapping,
    # exactly as an UNLISTED answer is below — `import_rows` already reads absence as "write
    # no row", which is the whole reason a withhold needed no new machinery downstream.
    #
    # THERE IS DELIBERATELY NO UNKNOWN-KEY CHECK ON THIS SET, unlike `sku_dispositions` at the
    # bottom of this function, and the absence is the survival guarantee rather than an
    # oversight. A withheld SKU is the one most likely to fall out of a later run — it was
    # withheld BECAUSE it is not being listed — and refusing on it would mean holding a card
    # back eventually breaks `emit` for the whole run.
    held = set(withheld or ())
    prices: "OrderedDict[str, Decimal]" = OrderedDict()
    undecided: List[SkuMatch] = []
    unanswered: List[SkuMatch] = []

    for match in report.matches.values():
        if match.sku in held:
            continue
        disposition = overrides.get(match.sku)
        if disposition is not None:
            # `match.threshold` IS THE FLOOR A `flat_floor` DISPOSITION RESOLVES AT. See
            # `SkuMatch.list_price` for why they are one figure; passing the match's own is
            # what keeps a legacy `"floor"` answer resolving at the store's cut-off rather
            # than at `pricing.FLOOR`, which the operator may have set the cut-off below.
            prices[match.sku] = disposition.resolve(match.threshold)
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
        prices[match.sku] = sub_threshold.resolve(match.threshold)

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
    withheld: Optional[Set[str]] = None,
) -> List[tcgcsv.Row]:
    """The rows an import file would carry. One per SKU, in catalog order.

    `only` selects a subset of SKUs, which is how `emit` splits one join into the listed
    file and the sub-threshold file (v2 §7) without pricing the run twice.
    """
    prices = prices_for(report, sub_threshold, sku_dispositions, no_market_data, withheld)
    rows: List[tcgcsv.Row] = []
    for match in report.matches.values():
        if match.sku not in prices:  # answered UNLISTED
            continue
        if only is not None and match.sku not in only:
            continue
        if match.add_to_quantity == 0:  # nothing to add; `report.at_cap` and its row say why
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
    withheld: Optional[Set[str]] = None,
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
    rows = import_rows(
        report, sub_threshold, sku_dispositions, no_market_data, only, withheld
    )
    return write_import(catalog, path, rows)


def write_import(catalog: Catalog, path, rows: List[tcgcsv.Row]) -> bytes:
    """Write rows that have already been computed, with the duplicate-SKU gate.

    SPLIT OUT OF `emit_import` SO A CALLER CAN LOOK AT THE ROWS BEFORE A FILE HANDLE OPENS,
    and that is not a convenience — it is the whole of D54's rule. `tcgcsv.write_csv` emits
    the header before it iterates, so calling it with an empty list produces a valid CSV of
    nothing, which is indistinguishable on disk from a file whose rows were never written
    and is catastrophic when it lands on top of a file the operator has been told to import.
    `cli/cmd_emit.py` therefore computes rows, decides, and only then calls this.

    `emit_import`'s signature and behaviour are unchanged — T3 calls it in six places and a
    moved seam there would be a wide change for one caller's problem.
    """
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
