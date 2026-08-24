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
  3. DETECTION       Haiku's `finish` field. Runs as a CROSS-CHECK even when metadata
                     exists: a normal card mis-sorted into the reverse stack still matches
                     a valid catalog row, so only detection catches it.
  4. REVIEW          still ambiguous, detection disagrees with metadata, or no matching
                     catalog row.

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

Both review paths carry a distinct reason so the queue can be triaged: a run full of
METADATA_NOT_STOCKED means a stack is misfiled, while METADATA_DETECTION_DISAGREEMENT
scattered across a run means individual cards are mis-sorted.

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
METADATA_DETECTION_DISAGREEMENT = "metadata_detection_disagreement"
DETECTED_FINISH_NOT_STOCKED = "detected_finish_not_stocked"
AMBIGUOUS_NO_SIGNAL = "ambiguous_no_signal"
DUPLICATE_CONDITION = "duplicate_condition"


class UnknownFinish(ValueError):
    """A finish string outside the enum. Never coerce — guess once and it prices wrong."""


@dataclass(frozen=True)
class Resolution:
    stage: str
    reason: str
    row: Optional[tcgcsv.Row] = None
    condition: Optional[str] = None
    market_price: Optional[Decimal] = None
    # This card resolved only because `trust_claim` was on — the detection cross-check
    # would have sent it to review. Carried on the resolution rather than counted at the
    # call site so the run report can say how many cards the operator's claim answered
    # for, which is the whole of what they are accepting when they turn the flag on.
    bypassed: bool = False

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


def _resolved(stage: str, row: tcgcsv.Row, bypassed: bool = False) -> Resolution:
    return Resolution(
        stage=stage,
        reason=stage,
        row=row,
        condition=row[tcgcsv.CONDITION_COLUMN],
        market_price=tcgcsv.parse_price(row[tcgcsv.MARKET_PRICE_COLUMN]),
        bypassed=bypassed,
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
    trust_claim: bool = False,
) -> Resolution:
    """Walk the ladder for one card. `candidates` are the catalog rows for its number.

    `trust_claim` is the operator's pre-emptive bypass, and it is ONE RULE: **detection may
    not contradict a finish claim, but may still choose inside one.** It does nothing at all
    to a card with no claim — there is no claim to resolve by, so rungs 2 and 3 run exactly
    as they always do. Where a claim exists and detection lands outside it, detection is
    dropped for that card rather than overruled selectively: a signal the operator has just
    declared untrustworthy for this run may not go on to pick a row further down the ladder.

    It costs D3 rung 3's cross-check on the cards it touches, and that is the whole of the
    trade — it is not a softening of rung 1, which already trusts the toggle. The evidence
    it was built for is in `docs/GATES.md`'s box-2 section: 230 of 544 cards contradicted a
    claim that the owner confirmed was right every time, at a measured 42% false-positive
    rate, with the same photograph reading differently at two downscales. A cross-check that
    is wrong more often than the thing it checks is not a cross-check.

    `rarity_claim` is D23's multi-select stack claim: the exact `Rarity` cells the operator
    says this stack holds. None or empty narrows nothing — the compatibility guarantee that
    makes the claim strictly additive.

    `metadata_finish` is D3 rung 1's claim and is a SET: a string, a sequence, or None. See
    `_check_claim` for why a string still works and `game` for why the vocabulary is not
    Pokemon's any more. Omitting `game` reads as `games.DEFAULT_GAME`, which is what every
    caller written before games existed meant."""
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
            return Resolution(stage=REVIEW, reason=RARITY_CLAIM_MISMATCH)
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
        # Rung 3 as a cross-check, before trusting rung 1. Detection outside the claimed set
        # is the disagreement whatever the set's size — with one member this is the identity
        # test it has always been.
        contradicted = detected_finish is not None and detected_finish not in claimed
        if contradicted and not trust_claim:
            return Resolution(stage=REVIEW, reason=METADATA_DETECTION_DISAGREEMENT)
        if contradicted:
            # Dropped, not merely not-reported. Leaving it live would let it fire at rung 3
            # against the narrowed rows below and answer DETECTED_FINISH_NOT_STOCKED — a
            # refusal sourced from the signal this flag just set aside, wearing a reason
            # code that would send the operator looking at the catalog instead.
            detected_finish = None
        if len(claimed) == 1:
            return _resolved(METADATA, next(iter(kept.values())), bypassed=contradicted)
        # TWO OR MORE: narrow and FALL THROUGH. Deliberately the same move D23's rarity
        # filter makes a few lines above — narrow the rows, then let every rung below run on
        # what is left. Rung 2 fires when the claim leaves exactly one row, rung 3 picks
        # within the claimed set, and rung 4 reviews. Re-implementing those three rungs
        # inside this branch was the alternative and would have been three more places for
        # the ladder to disagree with itself.
        candidates = list(kept.values())
        by_condition = kept
    else:
        contradicted = False

    # Rung 2 — catalog-forced. Reached with no metadata to contradict, or with a set-valued
    # claim that narrowed to one row.
    if len(candidates) == 1:
        return _resolved(CATALOG_FORCED, candidates[0], bypassed=contradicted)

    # Rung 3 — detection.
    if detected_finish is not None:
        wanted_row = condition_by_finish[detected_finish]
        if wanted_row in by_condition:
            return _resolved(DETECTION, by_condition[wanted_row], bypassed=contradicted)
        return Resolution(stage=REVIEW, reason=DETECTED_FINISH_NOT_STOCKED)

    # Rung 4 — review.
    return Resolution(stage=REVIEW, reason=AMBIGUOUS_NO_SIGNAL)
