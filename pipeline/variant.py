"""The D3 variant-resolution ladder.

Resolve normal / holo / reverse holo per card, in order:

  0. HUMAN_ANSWERED  a human already answered this card on the review screen. Above the
                     ladder rather than in it, and `join_batch` applies it before the walk
                     below ever starts — the ladder infers, and an answer is not an
                     inference. Added 2026-08-22; see the constant's own comment for the
                     bug that produced it.
  1. METADATA        capture-time variant toggle, stored in the card's JSON sidecar.
                     Primary path.
  2. CATALOG_FORCED  one condition row for that number in the fixture, so the row decides.
                     Most SV-era rares are holofoil-only; a single row is itself evidence.
  3. DETECTION       Haiku's `finish` field. Decides where NO claim exists, and chooses
                     INSIDE a multi-member claim. It never contradicts one (D3, amended
                     2026-09-02): it ran as a cross-check over a one-member claim until
                     then, and across every disagreement a human ruled on the claim was
                     right, so a read outside the claimed set is dropped rather than argued
                     with.
  4. REVIEW          still ambiguous, or no matching catalog row.

THE TOGGLE IS TRUSTED (owner's call, 2026-08-03). It is set per stack, not left on a
default, so metadata is a claim and not a hint. Two consequences, and they are the whole
shape of the ladder:

  - Metadata naming a variant the catalog does not stock — toggle says normal, the number
    has only a Near Mint Holofoil row — is a CONTRADICTION, not a correction. It reviews
    (METADATA_NOT_STOCKED). Something is misfiled or misidentified, and resolving it
    silently to the only available row would list a card nobody thought was in the stack.
    This costs a tap per mis-toggled holofoil-only rare; that is the price of the toggle
    meaning something.
  - Rung 2 therefore fires only when there is NO capture-time metadata: a card captured
    before the toggle was set, or a batch run without it. One condition row and no claim
    to contradict, so the row decides.

The review reasons carry distinct strings so the queue can be triaged: a run full of
METADATA_NOT_STOCKED means a stack is misfiled or misidentified. The sibling it used to be
read against, `metadata_detection_disagreement`, is retired (2026-09-02): the 16 a human
ruled on all went to the claim, and box 2's 230 were all wrong.

Guards v1 bug #1: variant mispricing from blindly taking holofoil || reverseHolofoil ||
normal.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional, Sequence, Tuple, Union

from pipeline import games, tcgcsv

NORMAL = "normal"
HOLO = "holo"
REVERSE_HOLO = "reverse_holo"

# THE FINISH ENUM AND THE CONDITION MAP ARE THE POKEMON ENTRY'S, READ OUT OF THE REGISTRY.
# They were written out here as literals until the registry existed, and the values have not
# moved: `pipeline/games.py` was authored against fixtures/sv09_export_untouched.csv to
# reproduce them exactly, so T3 and T4 pass untouched. That is the point of doing it this
# way round — the registry is only trustworthy if it can restate what the ladder already
# knew, byte for byte, before anything new is built on it.
#
# `require` rather than `get` (D22): a game with no authored vocabulary refuses here rather
# than borrowing another game's. Pokemon's is never empty, so this raises only if somebody
# empties the entry, which is the moment to hear about it.
#
# D12 still decides the *contents*: all Near Mint, hardcoded. Vintage condition strings
# (1st Edition, Shadowless, Unlimited) are a spec change, not a parameter — and now not a
# registry field either, since a game's `condition_by_finish` names one condition per
# finish and has nowhere to put a second grading axis.
_POKEMON = games.require(games.DEFAULT_GAME)

FINISHES: Tuple[str, ...] = tuple(_POKEMON["finishes"])

CONDITION_BY_FINISH: Dict[str, str] = dict(_POKEMON["condition_by_finish"])
FINISH_BY_CONDITION: Dict[str, str] = {v: k for k, v in CONDITION_BY_FINISH.items()}

# The three names above are still literals, because a name derived from a position in a
# tuple is a name that silently changes meaning when the tuple is reordered. This is the
# seam where the two halves are reconciled, and it fails at import: a registry that renames
# or drops a finish stops the process here, next to the mismatch, rather than at whichever
# `CONDITION_BY_FINISH[...]` lookup happens to run first.
_MISSING = [name for name in (NORMAL, HOLO, REVERSE_HOLO) if name not in CONDITION_BY_FINISH]
if _MISSING or set(FINISHES) != set(CONDITION_BY_FINISH):
    raise RuntimeError(
        "pipeline/games.py's `pokemon` entry no longer describes this ladder: "
        f"finishes={FINISHES}, conditions={sorted(CONDITION_BY_FINISH)}, "
        f"unmatched here={_MISSING}"
    )

# Ladder stages, named for the rung that DECIDED — not merely one that was consulted.
METADATA = "metadata"
CATALOG_FORCED = "catalog_forced"
DETECTION = "detection"
REVIEW = "review"

# Rung 0, above the whole ladder: a human answered this card on the review screen. Not in
# the ladder's own walk below, because it does not belong to it — the ladder infers, and
# an answer is not an inference. `join_batch` applies it before the ladder runs. Added
# 2026-08-22, when the first real run proved the answer route wrote answers that nothing
# ever read back: sixteen answered cards re-derived their disagreement on every join and
# re-parked forever, listed never.
HUMAN_ANSWERED = "human_answered"

# Review reasons. Distinct strings so the queue can be triaged and so a test can assert
# which path fired, rather than only that something failed.
NO_CATALOG_ROW = "no_catalog_row"
# D23 job (a): the operator's multi-select rarity claim contradicts every candidate row.
# Emitted here in the ladder and not in routing, deliberately — routing answers "is this
# trusted enough to list?" and stays the one pipeline module with no game in it; this
# answers "which row is this?", which is the ladder's question. The name was argued in D23:
# `metadata_rarity_disagreement` was rejected because the three `metadata_*` reasons are
# all about the finish toggle, and `rarity_not_claimed` parses as the empty case.
RARITY_CLAIM_MISMATCH = "rarity_claim_mismatch"
METADATA_NOT_STOCKED = "metadata_not_stocked"
DETECTED_FINISH_NOT_STOCKED = "detected_finish_not_stocked"
AMBIGUOUS_NO_SIGNAL = "ambiguous_no_signal"
DUPLICATE_CONDITION = "duplicate_condition"

# THE LADDER'S REVIEW REASONS, PUBLISHED AS A SET (D3). Six of the fourteen module-level
# constants in this file are reasons; the other eight are finishes (`normal`, `holo`,
# `reverse_holo`) and ladder stages (`metadata`, `catalog_forced`, `detection`, `review`,
# `human_answered`). Every one of the fourteen is spelled `UPPER_NAME = "lowercase_string"`,
# so nothing in the SHAPE of a line says which kind it is.
#
# WHY THAT MATTERS ENOUGH TO ADD A TUPLE. `scripts/docs-audit.py` reconciles this vocabulary
# against the screen's labels and docs/DESIGN.md, and it could only ever run one direction —
# it starts from a reason somebody published and asks whether the code defines it. The other
# direction, "what are all the reasons", had no answer that did not involve guessing which
# constants qualify, and the cheapest guess ("every UPPER = lowercase string here") is wrong
# about eight of fourteen in this file alone. On a blocking row a guess does not produce a
# report someone shrugs at; it stops commits, and a row that stops commits for bad cause is
# one people learn to bypass.
#
# So the set is declared rather than inferred. The reader is the audit, not the interpreter —
# there is no runtime assertion here worth writing, because a tuple built from the constants
# beside it cannot disagree with them. What it buys is that a SEVENTH reason added below and
# left out of this tuple is now a failed commit instead of a silent omission.
LADDER_REASONS = (
    NO_CATALOG_ROW,
    RARITY_CLAIM_MISMATCH,
    METADATA_NOT_STOCKED,
    DETECTED_FINISH_NOT_STOCKED,
    AMBIGUOUS_NO_SIGNAL,
    DUPLICATE_CONDITION,
)


class UnknownFinish(ValueError):
    """A finish string outside the enum. Never coerce — guess once and it prices wrong."""


@dataclass(frozen=True)
class Resolution:
    stage: str
    reason: str
    row: Optional[tcgcsv.Row] = None
    condition: Optional[str] = None
    market_price: Optional[Decimal] = None

    @property
    def needs_review(self) -> bool:
        return self.stage == REVIEW

    @property
    def sku(self) -> Optional[str]:
        return self.row[tcgcsv.SKU_COLUMN] if self.row else None


def vocabulary(game: Optional[str] = None) -> Tuple[Tuple[str, ...], Dict[str, str]]:
    """This game's finishes and its finish->Condition map.

    THE LADDER READ POKEMON'S THREE FOR EVERY GAME UNTIL 2026-08-23, and it did not refuse
    politely — `_check` RAISED `UnknownFinish`, so a Riftbound card claiming `foil` (a
    finish its own registry entry authors, and which the capture screen offers) crashed the
    join outright rather than resolving or reviewing. It was the same Pokemon-enum leak the
    capture route had at `_optional_variant`, one layer down and with a worse failure mode:
    a refusal names itself and an exception takes the run with it.

    `require` rather than `get`, exactly as the module-level Pokemon lookup does: a game
    with no authored vocabulary refuses here rather than borrowing another game's (D22).
    """
    entry = games.require(game if game else games.DEFAULT_GAME)
    return tuple(entry["finishes"]), dict(entry["condition_by_finish"])


def _check(finish: Optional[str], stocked: Tuple[str, ...] = FINISHES) -> Optional[str]:
    if finish is None:
        return None
    if finish not in stocked:
        raise UnknownFinish(f"{finish!r} not in {stocked}")
    return finish


def _check_claim(
    claim: Union[str, Sequence[str], None], stocked: Tuple[str, ...]
) -> Tuple[str, ...]:
    """The finish claim as a SET (D3 rung 1, amended 2026-08-23).

    A BARE STRING READS AS A ONE-MEMBER SET AND NOTHING HERE EVER WRITES ONE — D21's
    read-side backfill, for D21's reason: every record and every sidecar written before the
    amendment carries a string, and rewriting 767 of them to say what this function can work
    out is a migration that buys nothing.

    Deduped, and ordered by the game's own enum rather than by the order the operator
    tapped, so two identical claims are one value however they were made.
    """
    if claim is None:
        return ()
    members = (claim,) if isinstance(claim, str) else tuple(claim)
    for member in members:
        _check(member, stocked)
    return tuple(finish for finish in stocked if finish in members)


def _resolved(stage: str, row: tcgcsv.Row) -> Resolution:
    return Resolution(
        stage=stage,
        reason=stage,
        row=row,
        condition=row[tcgcsv.CONDITION_COLUMN],
        market_price=tcgcsv.parse_price(row[tcgcsv.MARKET_PRICE_COLUMN]),
    )


def answered(row: tcgcsv.Row) -> Resolution:
    """Rung 0 — the human's one-tap answer, applied to the row it chose.

    The caller looked the row up by the answered SKU; this only shapes it as a resolution.
    Metadata and detection are deliberately not consulted: their disagreement is the
    question the review screen asked, and the answer is what the human said after looking
    at the photograph beside the candidates. Re-checking the signals that raised the
    question would re-raise it forever."""
    return _resolved(HUMAN_ANSWERED, row)


def resolve(
    candidates: Sequence[tcgcsv.Row],
    metadata_finish: Union[str, Sequence[str], None] = None,
    detected_finish: Optional[str] = None,
    rarity_claim: Optional[Sequence[str]] = None,
    game: Optional[str] = None,
    name_corroborated: bool = False,
) -> Resolution:
    """Walk the ladder for one card. `candidates` are the catalog rows for its number.

    `rarity_claim` is D23's multi-select stack claim: the exact `Rarity` cells the operator
    says this stack holds. None or empty narrows nothing — the compatibility guarantee that
    makes the claim strictly additive.

    `metadata_finish` is D3 rung 1's claim and is a SET: a string, a sequence, or None. See
    `_check_claim` for why a string still works and `game` for why the vocabulary is not
    Pokemon's any more. Omitting `game` reads as `games.DEFAULT_GAME`, which is what every
    caller written before games existed meant.

    `name_corroborated` says the model's own reading of the card's NAME agrees with one of
    these rows. Computed by the CALLER — `pipeline/join.py:name_corroborates`, where the
    name fold already lives — because a fold with two homes is a fold with two answers.
    Default False, so every caller written before this walks the path it always did."""
    stocked, condition_by_finish = vocabulary(game)
    claimed = _check_claim(metadata_finish, stocked)
    detected_finish = _check(detected_finish, stocked)

    if not candidates:
        return Resolution(stage=REVIEW, reason=NO_CATALOG_ROW)

    # D23 job (a) — FILTER-THEN-CONTRADICT, before any rung consults the rows. Filtering
    # first means the claim breaks a duplicate-condition tie for free (two sets colliding
    # on one key at different rarities), and it means every rung below runs on the narrowed
    # set — rung 2 (CATALOG_FORCED) fires when the claim leaves one row, and rung 1 reads
    # the catalog as the claim says it is, so a toggle naming a finish only an unclaimed
    # rarity stocks reviews as METADATA_NOT_STOCKED, which is the honest verdict against
    # the claimed catalog. When nothing survives at all, the claim contradicts the
    # identification outright — the review reason that catches T1's recorded misses:
    # `051/197` for `031/197` is a CONFIDENT answer no confidence threshold fires on, and a
    # rarity contradiction does.
    #
    # A blank or missing `Rarity` cell PASSES the filter rather than being treated as a
    # mismatch. Same principle as D9's `no_market_data`: a missing value is an unknown
    # value, not a member of any band — a row that carries no rarity is evidence of
    # nothing, and filtering it out would convert a data gap into a review tap for every
    # claimed card in its set.
    #
    # Rung 0 (`answered`) never reaches this: `join_batch` resolves a human's answer before
    # calling here at all. A human who looked at the photograph outranks a claim about the
    # stack it came from.
    if rarity_claim:
        kept = [
            row
            for row in candidates
            if not (row.get(tcgcsv.RARITY_COLUMN) or "").strip()
            or (row.get(tcgcsv.RARITY_COLUMN) or "").strip() in rarity_claim
        ]
        if not kept:
            # THE CONTRADICTION IS RELEASED WHEN THE NAME AGREES WITH THE ROWS, and this is
            # the one exit this branch has that is not a refusal.
            #
            # The claim is one thing the operator typed over a whole stack. The name is the
            # model reading THIS card, and the rows are the export's answer for the number
            # it read. When those two independent signals agree, the claim is the odd one
            # out — a stack labelled `Epic` whose cards the catalogue calls `Rare` — and
            # refusing here asks a human to confirm a card two signals already name.
            #
            # WHAT IT COST TO RETURN HERE UNCONDITIONALLY, measured over the owner's whole
            # store: 159 refusals, 145 of which the ladder below resolves cleanly, 145 of
            # which a human then answered, and 142 of those answers byte-identical to the
            # row the ladder was holding. One typed word, 142 taps to agree with the machine.
            #
            # IT FALLS THROUGH RATHER THAN RESOLVING. The claim is released, not believed:
            # every rung below runs on the UNFILTERED rows, so two rows still reach rung 2
            # as two and still go to review. `1/65` and `1/73` on the owner's store are
            # exactly that shape, and both are genuinely the wrong card. A single-candidate
            # auto-approve would have listed them — which is why the rule is two AGREEING
            # SIGNALS and never one uncontradicted row.
            #
            # The mirror of this release lives in the caller, and it has to: a name that
            # matches NONE of the rows is a review reason of its own
            # (`routing.NAME_DISPUTED`), including on the cards this filter waved through
            # because the claim happened to agree with a row for a different card.
            if not name_corroborated:
                return Resolution(stage=REVIEW, reason=RARITY_CLAIM_MISMATCH)
        else:
            candidates = kept

    by_condition: Dict[str, tcgcsv.Row] = {}
    for row in candidates:
        condition = row[tcgcsv.CONDITION_COLUMN]
        if condition in by_condition:
            # Two candidate rows claiming the same condition string. The dict this used to
            # be built as would have kept the last one silently and priced whichever the
            # export happened to list second — a coin flip dressed as a resolution. The
            # shape that produces it is a cross-set join-key collision (v2 §5.1), which
            # `Catalog.candidates` normally catches first; this is the backstop for every
            # other way two rows can arrive here, and it reviews rather than picking.
            return Resolution(stage=REVIEW, reason=DUPLICATE_CONDITION)
        by_condition[condition] = row

    # Rung 1 — capture-time metadata, trusted. D3's amendment of 2026-08-23 makes the claim
    # a SET, and the member count decides what it does: ONE determines, exactly as this rung
    # always has; TWO OR MORE narrow the rows and let the rungs below choose within what
    # survives. A less specific claim can only ever narrow, which is what keeps it a claim
    # rather than a hint.
    if claimed:
        wanted = {condition_by_finish[finish] for finish in claimed}
        kept = {c: row for c, row in by_condition.items() if c in wanted}
        if not kept:
            # The claim names finishes this card does not come in. Reported before the
            # detection cross-check because it is the more specific finding: it points at
            # a misfiled stack or a wrong identification, not at one mis-sorted card.
            # A SET empties only when NONE of its members is stocked — claiming
            # {holo, reverse_holo} against a normal-only number is the same fact as
            # claiming `holo` against it, which is why this needs no reason code of its own.
            return Resolution(stage=REVIEW, reason=METADATA_NOT_STOCKED)
        # DETECTION OUTSIDE THE CLAIMED SET IS DROPPED, NOT ARGUED WITH (D3, amended
        # 2026-09-02). This was rung 3's cross-check — `metadata_detection_disagreement`,
        # switchable off per run by `--bypass` — and the measurement retired it: 16 of 16
        # rulings went to the claim, box 2's 230 disagreements were all wrong, and every run
        # since Gate B was joined with the flag on. A switch every run flips is a default
        # wearing a flag, so the rule the flag encoded is the ladder's rule now.
        #
        # Dropped rather than left live, because a live read would fire at rung 3 against
        # the narrowed rows below and answer DETECTED_FINISH_NOT_STOCKED — a refusal sourced
        # from the signal the claim outranks, wearing a reason code that sends the operator
        # to look at the catalog instead.
        if detected_finish is not None and detected_finish not in claimed:
            detected_finish = None
        if len(claimed) == 1:
            return _resolved(METADATA, next(iter(kept.values())))
        # TWO OR MORE: narrow and FALL THROUGH. Deliberately the same move D23's rarity
        # filter makes a few lines above — narrow the rows, then let every rung below run on
        # what is left. Rung 2 fires when the claim leaves exactly one row, rung 3 picks
        # within the claimed set, and rung 4 reviews. Re-implementing those three rungs
        # inside this branch was the alternative and would have been three more places for
        # the ladder to disagree with itself.
        candidates = list(kept.values())
        by_condition = kept

    # Rung 2 — catalog-forced. Reached with no metadata to contradict, or with a set-valued
    # claim that narrowed to one row.
    if len(candidates) == 1:
        return _resolved(CATALOG_FORCED, candidates[0])

    # Rung 3 — detection. Reached with no claim, or with a multi-member claim it lands
    # inside of; a read outside the claim never gets here.
    if detected_finish is not None:
        wanted_row = condition_by_finish[detected_finish]
        if wanted_row in by_condition:
            return _resolved(DETECTION, by_condition[wanted_row])
        return Resolution(stage=REVIEW, reason=DETECTED_FINISH_NOT_STOCKED)

    # Rung 4 — review.
    return Resolution(stage=REVIEW, reason=AMBIGUOUS_NO_SIGNAL)
