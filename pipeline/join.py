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

import re
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Callable, Dict, Iterable, List, NamedTuple, Optional, Sequence, Set, Tuple

from pipeline import games, pricing, routing, tcgcsv, variant

# D7 — a playset. Configurable, but never guessed at.
LIVE_QUANTITY_CAP = 4

# D10 — 25 cards per divider. The DEFAULT layout, used for a box that declares none.
# Sections are per-box and declared at capture time since D10's amendment; this constant is
# what a box with an empty `sections` list renders with, which is what keeps every label
# written before boxes existed byte-identical.
CARDS_PER_SECTION = 25


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
    """D10 — sequential, assigned at capture. Sold cards leave permanent gaps; positions
    are never renumbered.

    THE INDEX IS THE IDENTITY; THE LABEL IS A VIEW OF THE BOX'S CURRENT LAYOUT. `sections`
    is the box's divider indices — `(1, 31, 56)` means section 2 starts at card 31 — and
    editing it relabels every card behind the moved divider without touching a single index.
    D10 (amended) accepts that: correcting a wrong layout is the point, and the label was
    never printed on anything, only ever read live off a screen.

    An EMPTY `sections` means the box has declared no layout, and the default divider size
    renders it. That is the whole of the v1 compatibility story — every card recorded before
    boxes existed renders through this branch and comes out unchanged.

    THIS IS THE ONLY LABEL FORMULA IN THE REPO (`docs/specs/capture-server.md` §6.3). The
    TypeScript side receives rendered strings and never computes a section.
    """

    box: int
    index: int
    sections: Tuple[int, ...] = ()

    @property
    def section(self) -> int:
        if not self.sections:
            return (self.index - 1) // CARDS_PER_SECTION + 1
        count = 0
        for start in self.sections:
            if self.index >= start:
                count += 1
            else:
                break
        # An index before the first divider cannot happen with a validated layout (it starts
        # at 1), but clamping beats returning 0 for a hand-edited file.
        return max(1, count)

    @property
    def section_start(self) -> int:
        """The index this card's section begins at."""
        if not self.sections:
            return (self.section - 1) * CARDS_PER_SECTION + 1
        return self.sections[self.section - 1]

    @property
    def section_end(self) -> Optional[int]:
        """The last index in this card's section, or None when it is the final one.

        None rather than a guess: the final section runs to wherever the box ends, and only
        a sealed box knows where that is (D20). The caller holding the capacity fills it in.
        """
        if not self.sections:
            return self.section_start + CARDS_PER_SECTION - 1
        if self.section < len(self.sections):
            return self.sections[self.section] - 1
        return None

    @property
    def card(self) -> int:
        return self.index - self.section_start + 1

    @property
    def label(self) -> str:
        return f"Box {self.box} · Section {self.section} · Card {self.card}"


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
    if is_located(game):
        return f"at {position.label}"
    return f"in the {game} pool ({position.box}/{position.index})"


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


def join_key(number, printed_total) -> str:
    """zfill(3)(number) + "/" + printedTotal. `161/159` is a secret rare, not an error.

    THE COMPOSITION FORM, WHICH IS NOT THE COMPARISON FORM. This builds the key a human
    reads and a report prints, in the shape `CLAUDE.md` documents. Matching against the
    export goes through `number_index_key` below, on BOTH sides, and that is the function
    that decides whether two spellings are the same card. Same split `normalize_set` already
    makes a few lines down: a label to show, and a fold to compare.
    """
    return f"{str(number).strip().zfill(3)}/{str(printed_total).strip()}"


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


# The number this export decorates a `Product Name` with, when it decorates one at all.
# Anchored at the end and requiring the slash, so only a trailing collector number matches:
# `Ho-Oh`, `Wally's Compassion` and `Team Rocket's Mewtwo` keep every character they have.
_NAME_NUMBER_SUFFIX = re.compile(r"\s*-\s*[A-Za-z0-9]+\s*/\s*[A-Za-z0-9]+\s*$")


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
    text = _NAME_NUMBER_SUFFIX.sub("", str(text or "").strip())
    return " ".join(text.split()).upper()


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


def _key_number_and_printed_total(card: "IdentifiedCard") -> Optional[str]:
    """Pokemon: two printed halves composed into one key, zero-padded on the left.

    Both halves or nothing. A number without its denominator cannot compose the key the export
    is indexed by, and guessing a denominator would invent half an identity.
    """
    if card.number is None or card.printed_total is None:
        return None
    return join_key(card.number, card.printed_total)


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

    THAT EXACT FAILURE THEN HAPPENED FROM THE MODEL'S SIDE. Three of run
    `2026-08-29-box1-01`'s reads came back `UNL • 140/219` — the set code glued to the
    identifier, which the Riftbound prompt forbids in as many words — and matched nothing. The
    name rung below is what now recovers them.

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
    2. Failing that — no key at all — the export's blank-`Number` rows by name. Sealed
       products, promos and code cards land here whatever keys the rest of the export.
    3. D35's last resort: the name, for a card that DOES print a number we could not read.

    STEP 3 IS REACHED FROM TWO DIRECTIONS AND NOT FROM A THIRD. A key that found nothing falls
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
    "printed_code": KeyStrategy(_key_printed_code, "code", True),
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
    ):
        # Which game's rows these are (None for a direct, pre-scoped build) and how many
        # rows of the source file the game's filter dropped — reported by the caller, per
        # D25's "reports the drop count".
        self.game = game
        self.dropped_rows = dropped_rows
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
                # Folded by `name_index_key`, and `rows_for_name` folds what it is handed
                # with the same function — the invariant this class already keeps for
                # numbers, kept for the other column too.
                self._by_name.setdefault(
                    name_index_key(row[tcgcsv.NAME_COLUMN]), []
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

        Refuses on zero rows — see `EmptyCatalog`. The drop count is carried on the
        catalog (`dropped_rows`) for the caller to report: zero is the ordinary case for a
        file exported per game, and a large number is a combined file working as intended.
        """
        entry = games.require(game)
        line = entry["product_line"]
        rarities = entry.get("product_line_rarities")
        kept = tuple(
            row
            for row in export.rows
            if row.get(tcgcsv.PRODUCT_LINE_COLUMN) == line
            and (not rarities or row.get(tcgcsv.RARITY_COLUMN) in rarities)
        )
        if not kept:
            lines = ", ".join(repr(v) for v in tcgcsv.product_lines(export)) or "none"
            source = f" {export.source}" if export.source else ""
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
            dropped_rows=len(export.rows) - len(kept),
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
        """
        return list(self._by_name.get(name_index_key(name), ()))

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

        # Rung 3 of §5.1 — a colliding key, disambiguated by the sidecar set hint.
        if card.set_hint:
            narrowed = [
                row
                for row in rows
                if set_matches(card.set_hint, row.get(tcgcsv.SET_COLUMN, ""))
            ]
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
    live_cap: int = LIVE_QUANTITY_CAP
    rule: pricing.Rule = pricing.MATCH
    basis: str = pricing.BASIS_MARKET
    # Copies TCGplayer already holds (staged/live/sold records) — see
    # `IdentifiedCard.committed`. Subset of `positions`; they occupy room under the cap
    # and take nothing from the import file.
    committed_positions: List[Position] = field(default_factory=list)

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
    def uncommitted_positions(self) -> List[Position]:
        """The copies this run may still list — everything TCGplayer does not hold yet."""
        held = {(p.box, p.index) for p in self.committed_positions}
        return [p for p in self.positions if (p.box, p.index) not in held]

    @property
    def add_to_quantity(self) -> int:
        """New copies only. Committed copies occupy room under the cap alongside what the
        export reports live, and contribute nothing to the file — re-importing a copy
        TCGplayer already holds doubles it in Staged, which is the failure the first real
        post-import re-emit produced."""
        room = self.live_cap - self.live_before - len(self.committed_positions)
        return max(0, min(room, len(self.uncommitted_positions)))

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
    # Cards that resolved ONLY because the run was joined with the detection cross-check
    # off (`trust_claim`). Reported rather than left to be inferred from a smaller queue:
    # the operator is accepting responsibility for exactly these cards, and a number is the
    # only honest way to say how many that is.
    bypassed: int = 0

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
    live_cap: int = LIVE_QUANTITY_CAP,
    router: Optional[Router] = None,
    rule: pricing.Rule = pricing.MATCH,
    basis: str = pricing.BASIS_MARKET,
    trust_claim: bool = False,
) -> JoinReport:
    """Resolve every card to exactly one catalog row, aggregating copies by SKU.

    `trust_claim` is passed straight to `variant.resolve` — see its docstring for the one
    rule it encodes. It reaches only the ladder call below: rung 0 (a human's answer) is
    above it and already outranks detection, and the set-collision refusal is not about
    finishes at all.

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
                trust_claim=trust_claim,
            )
        if resolution.bypassed:
            report.bypassed += 1

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
        if (
            found.name_inferred
            and resolution.stage != variant.HUMAN_ANSWERED
            and not resolution.needs_review
            and resolution.row is not None
        ):
            found = replace(found, rows=(resolution.row,))
            resolution = variant.Resolution(
                stage=variant.REVIEW,
                reason=routing.NUMBER_UNREAD_NAME_MATCHED,
                row=resolution.row,
                condition=resolution.condition,
                market_price=resolution.market_price,
                bypassed=resolution.bypassed,
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
