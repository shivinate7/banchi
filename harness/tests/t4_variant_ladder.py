"""T4 — Variant ladder.

For a card with normal, holo, and reverse rows in the fixture, assert each ladder stage
resolves to the correct condition string and price.

Pass: all four stages correct, review fires on metadata/detection disagreement, and every
routing row sends the card to the queue named.

The ladder (D3 in docs/DECISIONS.md), in order:
  1. Capture-time metadata — variant toggle recorded in the card's JSON sidecar. Primary
     path. `--variant` on the batch script fills the finish in where a sidecar records
     none, and NEVER overrides one — asserted at the end of this file, because a flag able
     to replace a recorded toggle is the one thing that would stop it being a claim.
  2. Catalog-forced — one condition row for that number in the fixture (most SV-era rares
     are holofoil-only), so the row decides.
  3. Haiku `finish` field (normal | holo | reverse_holo), returned in every identification
     call at no extra cost. Runs as a cross-check even when metadata exists: a normal card
     mis-sorted into the reverse stack still matches a valid catalog row, so only
     detection catches it.
  4. Review queue — still ambiguous, detection disagrees with metadata, or no matching
     catalog row.

Stage 4 is not an afterthought: the disagreement case is the one that catches a mis-sort,
and it must be asserted to fire, not merely to be reachable.

THE TOGGLE IS TRUSTED (owner's call, 2026-08-03), so rung 2 is narrower than it reads: it
fires only when a card carries NO capture-time metadata. Metadata the catalog contradicts
— toggle says normal, the number is holofoil-only — reviews as METADATA_NOT_STOCKED rather
than being corrected to the only available row. The four stages below are asserted in that
shape.

FIXTURE GAP, and why part of this test is synthetic: no number in SV09 has all three
condition rows. The set is 127 numbers of (Near Mint, Near Mint Reverse Holofoil), 47 of
(Near Mint Holofoil) alone, and 16 of (Near Mint Holofoil, Near Mint Reverse Holofoil).
So GATES' "a card with normal, holo, and reverse rows in the fixture" does not exist to
test against. All four stages are therefore exercised against real rows, in the shapes the
fixture actually has, and one clearly-labelled synthetic three-row catalog covers the
literal requirement that each of the three condition strings resolves to its own row and
price. If a future export does contain a three-row number, replace the synthetic block —
`_three_row_gap()` reports the count on every run so the gap stays visible.

AND THE ROUTING TABLE (v2 §5.4), because resolving a card and trusting the answer are two
different decisions and only the second one decides whether it gets listed. Confidence is
the only signal that a card was GUESSED at: a misread `026/198` as `025/198` is still a
valid number that joins to a real row and prices cleanly, so nothing downstream can catch
it. That makes the routing table the last line, and it is asserted row by row here.

The main/parked split matters as much as the routing does. A low-confidence $12 card in
front of a human is a tap; a low-confidence 15-cent card in front of a human is how the $12
ones get missed. And an UNPRICED card is never parked — no price is not a low price, and a
misread secret rare is exactly that case.

Guards v1 bug #1: variant mispricing, which blindly took
holofoil || reverseHolofoil || normal.
"""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

from harness.tests import Checks, Result
from cli import resolve, runs
from identify import prompt, sidecar
from pipeline import games, join, routing, tcgcsv, variant
from store import files

NAME = "T4"
DESCRIPTION = "Variant ladder resolves all four stages, and the routing table"
PASS_CRITERIA = (
    "all four stages correct, review fires on metadata/detection disagreement, and "
    "every routing row sends the card to the queue named"
)

FINISHES = ("normal", "holo", "reverse_holo")

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_FIXTURE = "fixtures/sv09_export_untouched.csv"

# Real rows, chosen for their shape.
#   142/159  Billy & O'Nare   normal 0.12 + reverse 0.23   two rows, both variants stocked
#   161/159  Articuno         holofoil 22.03               one row, holofoil-only
#   003/159  Butterfree       holofoil 0.20 + reverse 0.47 two rows, no normal — the exact
#                                                          shape v1 bug #1 mispriced
BOTH_VARIANTS = "142/159"
BOTH_NORMAL_SKU, BOTH_NORMAL_PRICE = "8608674", Decimal("0.12")
BOTH_REVERSE_SKU, BOTH_REVERSE_PRICE = "8608679", Decimal("0.23")

HOLO_ONLY = "161/159"
HOLO_ONLY_SKU, HOLO_ONLY_PRICE = "8608859", Decimal("22.03")

NO_NORMAL = "003/159"
NO_NORMAL_HOLO_SKU, NO_NORMAL_HOLO_PRICE = "8607364", Decimal("0.20")
NO_NORMAL_REVERSE_SKU, NO_NORMAL_REVERSE_PRICE = "8607369", Decimal("0.47")


def _check_stage(c, resolution, stage, sku, condition, price, label):
    c.equal(
        (
            resolution.stage,
            resolution.sku,
            resolution.condition,
            resolution.market_price,
        ),
        (stage, sku, condition, price),
        label,
    )


@contextmanager
def _isolated_home():
    """An empty store in a temporary directory. `cli/resolve.py` reads the live inventory."""
    previous = os.environ.get(files.HOME_ENV)
    with tempfile.TemporaryDirectory() as tmp:
        os.environ[files.HOME_ENV] = tmp
        try:
            yield Path(tmp)
        finally:
            if previous is None:
                os.environ.pop(files.HOME_ENV, None)
            else:
                os.environ[files.HOME_ENV] = previous


def _detected_finishes(export_path, reads):
    """`detected_finish` as `cli/resolve.py` hands it to the ladder, per model read.

    `reads` is `{index: finish string the model returned}`. Every card names a collector
    number no row in the fixture carries, so each queues as `no_catalog_row` — which is
    deliberate and is the only way this is observable: `variant.resolve` checks the finish
    BEFORE it checks for candidates, so the whitelist has already done its work by then, and
    a fixture row for a finish this export has never heard of does not exist to resolve to.
    """
    with _isolated_home() as home:
        run = runs.Run(directory=home, manifest={})
        run.write_identifications(
            {
                "cards": {
                    f"9/{index}": {
                        "box": 9,
                        "index": index,
                        "photo": f"captures/box9/{index:04d}.jpg",
                        "identification": {
                            "name": "Ghost",
                            "number": "999",
                            "printed_total": "159",
                            "confidence": "high",
                            "finish": finish,
                        },
                    }
                    for index, finish in reads.items()
                }
            }
        )
        resolved = resolve.load(run, Path(export_path))
        return {
            q.card.position.index: q.card.detected_finish for q in resolved.report.queued
        }


def _three_row_gap(export) -> str:
    counts = {}
    for row in export.rows:
        number = row[tcgcsv.NUMBER_COLUMN].strip()
        if number:
            counts[number] = counts.get(number, 0) + 1
    three = [n for n, k in counts.items() if k >= 3]
    return (
        f"fixture gap: {len(three)} numbers in SV09 carry all three condition rows; "
        "the three-condition case below is synthetic and labelled"
    )


def run() -> Result:
    c = Checks()

    export = tcgcsv.read_export(REPO_ROOT / SOURCE_FIXTURE)
    catalog = join.Catalog(export)

    both = catalog.rows_for_key(BOTH_VARIANTS)
    holo_only = catalog.rows_for_key(HOLO_ONLY)
    no_normal = catalog.rows_for_key(NO_NORMAL)

    c.note(_three_row_gap(export))
    c.equal(len(both), 2, f"{BOTH_VARIANTS} has normal + reverse rows")
    c.equal(len(holo_only), 1, f"{HOLO_ONLY} has exactly one condition row")
    c.equal(len(no_normal), 2, f"{NO_NORMAL} has holo + reverse rows, no normal")

    # --- stage 1: metadata-driven -------------------------------------------------------
    _check_stage(
        c,
        variant.resolve(both, metadata_finish="normal"),
        variant.METADATA,
        BOTH_NORMAL_SKU,
        "Near Mint",
        BOTH_NORMAL_PRICE,
        "stage 1 metadata=normal -> Near Mint @ 0.12",
    )
    _check_stage(
        c,
        variant.resolve(both, metadata_finish="reverse_holo"),
        variant.METADATA,
        BOTH_REVERSE_SKU,
        "Near Mint Reverse Holofoil",
        BOTH_REVERSE_PRICE,
        "stage 1 metadata=reverse_holo -> Near Mint Reverse Holofoil @ 0.23",
    )
    _check_stage(
        c,
        variant.resolve(both, metadata_finish="normal", detected_finish="normal"),
        variant.METADATA,
        BOTH_NORMAL_SKU,
        "Near Mint",
        BOTH_NORMAL_PRICE,
        "stage 1 survives an agreeing cross-check",
    )

    # --- stage 2: catalog-forced ---------------------------------------------------------
    # Reached only with no metadata to contradict — the toggle is trusted, so a card that
    # carries one is never resolved by the catalog against it.
    _check_stage(
        c,
        variant.resolve(holo_only),
        variant.CATALOG_FORCED,
        HOLO_ONLY_SKU,
        "Near Mint Holofoil",
        HOLO_ONLY_PRICE,
        "stage 2 no metadata, one row -> Near Mint Holofoil @ 22.03",
    )
    _check_stage(
        c,
        variant.resolve(holo_only, detected_finish="holo"),
        variant.CATALOG_FORCED,
        HOLO_ONLY_SKU,
        "Near Mint Holofoil",
        HOLO_ONLY_PRICE,
        "stage 2 outranks an agreeing detector when there is only one row",
    )
    _check_stage(
        c,
        variant.resolve(holo_only, metadata_finish="holo"),
        variant.METADATA,
        HOLO_ONLY_SKU,
        "Near Mint Holofoil",
        HOLO_ONLY_PRICE,
        "metadata that agrees with the only row resolves at rung 1",
    )

    # --- stage 3: detection-driven --------------------------------------------------------
    _check_stage(
        c,
        variant.resolve(both, detected_finish="reverse_holo"),
        variant.DETECTION,
        BOTH_REVERSE_SKU,
        "Near Mint Reverse Holofoil",
        BOTH_REVERSE_PRICE,
        "stage 3 no metadata, detected=reverse_holo -> reverse @ 0.23",
    )
    _check_stage(
        c,
        variant.resolve(both, detected_finish="normal"),
        variant.DETECTION,
        BOTH_NORMAL_SKU,
        "Near Mint",
        BOTH_NORMAL_PRICE,
        "stage 3 no metadata, detected=normal -> Near Mint @ 0.12",
    )

    # --- the toggle is trusted: metadata the catalog contradicts goes to review -----------
    not_stocked_one_row = variant.resolve(holo_only, metadata_finish="normal")
    c.equal(
        (not_stocked_one_row.stage, not_stocked_one_row.reason, not_stocked_one_row.row),
        (variant.REVIEW, variant.METADATA_NOT_STOCKED, None),
        "toggle=normal against a holofoil-only number -> review, nothing resolved",
    )
    c.equal(
        variant.resolve(
            holo_only, metadata_finish="normal", detected_finish="holo"
        ).reason,
        variant.METADATA_NOT_STOCKED,
        "an agreeing detector does not rescue a contradicted toggle",
    )
    c.equal(
        variant.resolve(
            no_normal, metadata_finish="normal", detected_finish="holo"
        ).reason,
        variant.METADATA_NOT_STOCKED,
        "same when the number has two rows and neither is the one claimed",
    )
    c.note(
        "rung 2 fires only without metadata; a contradicted toggle reviews as "
        "metadata_not_stocked (owner's call 2026-08-03)"
    )

    # --- stage 4: review ---------------------------------------------------------------------
    disagreement = variant.resolve(
        both, metadata_finish="normal", detected_finish="reverse_holo"
    )
    c.equal(
        (disagreement.stage, disagreement.reason, disagreement.row),
        (variant.REVIEW, variant.METADATA_DETECTION_DISAGREEMENT, None),
        "stage 4 metadata=normal vs detected=reverse_holo -> review, nothing resolved",
    )
    c.ok(disagreement.needs_review, "the disagreement path fires, it is not merely reachable")

    mis_sort = variant.resolve(
        both, metadata_finish="reverse_holo", detected_finish="normal"
    )
    c.equal(
        (mis_sort.stage, mis_sort.reason),
        (variant.REVIEW, variant.METADATA_DETECTION_DISAGREEMENT),
        "the mis-sort catches in the other direction too",
    )

    ambiguous = variant.resolve(both)
    c.equal(
        (ambiguous.stage, ambiguous.reason),
        (variant.REVIEW, variant.AMBIGUOUS_NO_SIGNAL),
        "stage 4 two rows and no signal -> review",
    )
    not_stocked = variant.resolve(no_normal, detected_finish="normal")
    c.equal(
        (not_stocked.stage, not_stocked.reason),
        (variant.REVIEW, variant.DETECTED_FINISH_NOT_STOCKED),
        "stage 4 detected a finish this card does not come in -> review",
    )
    no_row = variant.resolve([], metadata_finish="normal", detected_finish="normal")
    c.equal(
        (no_row.stage, no_row.reason),
        (variant.REVIEW, variant.NO_CATALOG_ROW),
        "stage 4 no catalog row -> review",
    )

    # --- v1 bug #1: holofoil || reverseHolofoil || normal ---------------------------------
    bug1 = variant.resolve(no_normal, metadata_finish="reverse_holo")
    _check_stage(
        c,
        bug1,
        variant.METADATA,
        NO_NORMAL_REVERSE_SKU,
        "Near Mint Reverse Holofoil",
        NO_NORMAL_REVERSE_PRICE,
        "v1 bug #1: reverse holo is not mispriced as the holofoil row",
    )
    c.ok(
        bug1.market_price != NO_NORMAL_HOLO_PRICE,
        f"v1 bug #1: price is {NO_NORMAL_REVERSE_PRICE}, not the holofoil {NO_NORMAL_HOLO_PRICE}",
    )

    # --- an unknown finish is never coerced -----------------------------------------------
    c.raises(
        variant.UnknownFinish,
        lambda: variant.resolve(both, metadata_finish="holographic"),
        "an unknown finish string raises rather than being guessed at",
    )
    c.equal(
        set(variant.CONDITION_BY_FINISH),
        set(FINISHES),
        "the finish enum is exactly normal | holo | reverse_holo",
    )

    # --- the ladder's vocabulary is PER GAME, and it used to raise ------------------------
    # `variant.FINISHES` is `_POKEMON["finishes"]`, and `resolve` checked every game against
    # it — so a Riftbound card claiming `foil`, the finish its own registry entry authors and
    # the capture screen offers, did not review and did not resolve: it raised
    # `UnknownFinish` and took the join down with it. A refusal names itself; an exception
    # does not. Asserted in both directions, because the fix must not have widened Pokemon's
    # enum to make the crash go away.
    def _row(condition, price="1.00", rarity="Rare", sku="1"):
        return {
            tcgcsv.CONDITION_COLUMN: condition,
            tcgcsv.MARKET_PRICE_COLUMN: price,
            tcgcsv.RARITY_COLUMN: rarity,
            tcgcsv.SKU_COLUMN: sku,
        }

    riftbound = variant.resolve(
        [_row("Near Mint Foil", price="2.00")], metadata_finish="foil", game="riftbound"
    )
    c.equal(
        [riftbound.stage, riftbound.condition],
        [variant.METADATA, "Near Mint Foil"],
        "a Riftbound `foil` claim resolves at rung 1 against Riftbound's own vocabulary — "
        "it raised UnknownFinish against Pokemon's three until 2026-08-23",
    )
    c.raises(
        variant.UnknownFinish,
        lambda: variant.resolve(both, metadata_finish="foil", game="pokemon"),
        "and `foil` is still unknown to POKEMON — the per-game fix widened nothing",
    )

    # --- rung 3 for the two printed-code games, against their OWN prompts' enum ----------
    # Riftbound and One Piece got real identification profiles on 2026-08-23
    # (`riftbound_card_v1`, `one_piece_card_v1`); until then their registry entries named
    # `unwritten` and no model answer could reach this ladder at all, so rung 3 was
    # unreachable for both games however well the vocabulary was authored.
    #
    # ASSERTED FROM THE PROFILE'S SCHEMA RATHER THAN FROM A LITERAL, which is what makes
    # this a seam test rather than a restatement. The chain is: the schema enum the model
    # is sent -> `prompt.parse`'s whitelist -> `cli/resolve.py:_detected` -> `variant
    # .vocabulary` -> the ladder. A `foil` that the profile offers and the ladder rejects
    # would be a card sent to review with nothing on screen saying why, which is the silent
    # drop this pipeline may never do; a finish the ladder stocks and the profile never
    # offers is a cross-check that can never fire. Both directions, both games.
    for game in ("riftbound", "one_piece"):
        stocked, condition_by_finish = variant.vocabulary(game)
        offered = set(
            prompt.profile(str(games.get(game)["prompt"]))
            .schema["properties"]["finish"]["enum"]
        ) - {prompt.UNKNOWN_FINISH}
        c.equal(
            sorted(offered),
            sorted(stocked),
            f"{game}: every finish its prompt may return is a finish its ladder stocks, "
            "and vice versa — the schema enum and the ladder's vocabulary are one "
            "registry entry read twice",
        )
        for finish in sorted(stocked):
            condition = condition_by_finish[finish]
            rows = [
                _row(condition_by_finish[other], sku=f"sku-{other}")
                for other in sorted(stocked)
            ]
            resolution = variant.resolve(rows, detected_finish=finish, game=game)
            c.equal(
                [resolution.stage, resolution.condition],
                [variant.DETECTION, condition],
                f"{game}: a model-detected `{finish}` decides at rung 3 and resolves to "
                f"{condition!r} — the row a wrong read here would mis-price against",
            )
        # `unknown` is the third schema member and is NOT a finish: `prompt.parse` maps it
        # to None, which is D3's no-signal case rather than a manufactured disagreement.
        c.ok(
            prompt.UNKNOWN_FINISH not in stocked,
            f"{game}: `unknown` is a schema member and NOT a ladder finish — parse maps "
            "it to None, and a card with no foil signal walks the ladder rather than "
            "arguing with the toggle",
            f"stocked was {stocked!r}",
        )
        c.equal(
            variant.resolve(
                [_row(condition_by_finish[f], sku=f"sku-{f}") for f in sorted(stocked)],
                detected_finish=None,
                game=game,
            ).reason,
            variant.AMBIGUOUS_NO_SIGNAL,
            f"{game}: with no claim and no detection the ladder reviews as "
            "ambiguous_no_signal rather than picking a finish",
        )

    # --- D3 rung 1's claim is a SET (amended 2026-08-23) -----------------------------------
    # One member determines, exactly as this rung always has. Two or more FILTER: the rows
    # narrow to the claimed finishes and the rungs BELOW choose within what survives, which
    # is deliberately the move D23's rarity claim already makes. The cases below walk every
    # exit from that branch, because a filter that falls through has more of them than a
    # rung that returns.
    NM, NMH, NMR = (
        variant.CONDITION_BY_FINISH["normal"],
        variant.CONDITION_BY_FINISH["holo"],
        variant.CONDITION_BY_FINISH["reverse_holo"],
    )
    three = [_row(NM), _row(NMH), _row(NMR)]

    c.equal(
        variant.resolve(three, metadata_finish=["holo"]).condition,
        variant.resolve(three, metadata_finish="holo").condition,
        "a ONE-MEMBER set resolves identically to the bare string it replaces — the "
        "compatibility guarantee that makes the amendment additive, and what lets every "
        "record written before it read as a one-member claim",
    )

    two = variant.resolve(three, metadata_finish=["normal", "reverse_holo"])
    c.equal(
        [two.stage, two.reason],
        [variant.REVIEW, variant.AMBIGUOUS_NO_SIGNAL],
        "a TWO-MEMBER set with two rows surviving and no detection falls all the way to "
        "rung 4 — the claim narrowed and then had nothing left to decide with, which is a "
        "review rather than a guess between the two the operator named",
    )

    inside = variant.resolve(
        three, metadata_finish=["normal", "reverse_holo"], detected_finish="reverse_holo"
    )
    c.equal(
        [inside.stage, inside.condition],
        [variant.DETECTION, NMR],
        "detection INSIDE the claimed set decides at rung 3 — the set said which two are "
        "possible and detection said which of them it is",
    )

    outside = variant.resolve(
        three, metadata_finish=["normal", "reverse_holo"], detected_finish="holo"
    )
    c.equal(
        [outside.stage, outside.reason],
        [variant.REVIEW, variant.METADATA_DETECTION_DISAGREEMENT],
        "detection OUTSIDE the claimed set is the same disagreement it always was — with "
        "one member this is the identity test, so the reason code needed no sibling",
    )

    forced = variant.resolve([_row(NM), _row(NMH)], metadata_finish=["normal", "reverse_holo"])
    c.equal(
        [forced.stage, forced.condition],
        [variant.CATALOG_FORCED, NM],
        "a set that narrows to ONE row resolves at rung 2 — the fall-through is what makes "
        "this reachable, and re-implementing rung 2 inside rung 1 is what it avoids",
    )

    empty = variant.resolve([_row(NMH)], metadata_finish=["normal", "reverse_holo"])
    c.equal(
        [empty.stage, empty.reason],
        [variant.REVIEW, variant.METADATA_NOT_STOCKED],
        "a set NONE of whose members is stocked reviews as metadata_not_stocked — the same "
        "fact as a single claim the number does not come in, so it earns no new reason code",
    )

    c.equal(
        variant._check_claim(["reverse_holo", "normal", "normal"], FINISHES),
        ("normal", "reverse_holo"),
        "a claim is deduped and ordered by the game's own enum, never by the order the "
        "operator tapped — two identical claims are one value however they were made",
    )
    c.raises(
        variant.UnknownFinish,
        lambda: variant.resolve(three, metadata_finish=["normal", "holographic"]),
        "and ONE bad member refuses the whole claim rather than being dropped from it — a "
        "silently shortened claim is a claim the operator did not make",
    )

    # --- three condition strings, one number: SYNTHETIC (see the fixture gap above) --------
    template = {row[tcgcsv.CONDITION_COLUMN]: row for row in both}
    synthetic = [
        template["Near Mint"],
        dict(
            template["Near Mint"],
            **{
                tcgcsv.SKU_COLUMN: "9000001",
                tcgcsv.CONDITION_COLUMN: "Near Mint Holofoil",
                tcgcsv.MARKET_PRICE_COLUMN: "1.50",
            },
        ),
        template["Near Mint Reverse Holofoil"],
    ]
    expected = {
        "normal": (BOTH_NORMAL_SKU, "Near Mint", BOTH_NORMAL_PRICE),
        "holo": ("9000001", "Near Mint Holofoil", Decimal("1.50")),
        "reverse_holo": (
            BOTH_REVERSE_SKU,
            "Near Mint Reverse Holofoil",
            BOTH_REVERSE_PRICE,
        ),
    }
    for finish, (sku, condition, price) in expected.items():
        _check_stage(
            c,
            variant.resolve(synthetic, metadata_finish=finish),
            variant.METADATA,
            sku,
            condition,
            price,
            f"synthetic 3-row catalog: metadata={finish} -> {condition} @ {price}",
        )
        _check_stage(
            c,
            variant.resolve(synthetic, detected_finish=finish),
            variant.DETECTION,
            sku,
            condition,
            price,
            f"synthetic 3-row catalog: detected={finish} -> {condition} @ {price}",
        )
    c.equal(
        variant.resolve(
            synthetic, metadata_finish="holo", detected_finish="reverse_holo"
        ).reason,
        variant.METADATA_DETECTION_DISAGREEMENT,
        "synthetic 3-row catalog: disagreement still reviews",
    )

    # --- the ladder as the join sees it ----------------------------------------------------
    batch = [
        join.IdentifiedCard(
            position=join.Position(1, 1),
            name="Billy & O'Nare",
            number="142",
            printed_total="159",
            metadata_finish="normal",
            detected_finish="reverse_holo",
            photo="captures/box1/0001.jpg",
        ),
        join.IdentifiedCard(
            position=join.Position(1, 2),
            name="Articuno",
            number="161",
            printed_total="159",
            photo="captures/box1/0002.jpg",
        ),
    ]
    report = join.join_batch(batch, catalog)
    c.note(report.report())
    c.equal(
        [u.reason for u in report.unmatched_cards],
        [variant.METADATA_DETECTION_DISAGREEMENT],
        "a mis-sorted card reaches the review queue through the join",
    )
    c.ok(
        report.unmatched_cards[0].card.photo is not None,
        "the review item carries its capture photo",
    )
    c.equal(
        [m.stages for m in report.matches.values()],
        [["catalog_forced"]],
        "the unambiguous card still resolves in the same batch",
    )

    # ======================================================================================
    # The routing table (v2 §5.4). Which queue a card lands in, row by row.
    # ======================================================================================

    expensive = Decimal("12.00")
    cheap = Decimal("0.15")

    table = [
        # (label, kwargs, expected queue, expected reason)
        (
            "resolved + high confidence",
            dict(resolved=True, reason="metadata", confidence="high", price=expensive),
            routing.LISTED,
            routing.LISTED,
        ),
        (
            "resolved + medium confidence",
            dict(resolved=True, reason="metadata", confidence="medium", price=expensive),
            routing.LISTED,
            routing.LISTED,
        ),
        (
            "resolved + LOW confidence, market >= $0.40",
            dict(resolved=True, reason="metadata", confidence="low", price=expensive),
            routing.MAIN,
            routing.LOW_CONFIDENCE,
        ),
        (
            "resolved + LOW confidence, market < $0.40",
            dict(resolved=True, reason="metadata", confidence="low", price=cheap),
            routing.PARKED,
            routing.LOW_CONFIDENCE,
        ),
        (
            "ladder -> review, cheapest candidate >= $0.40",
            dict(
                resolved=False,
                reason=variant.AMBIGUOUS_NO_SIGNAL,
                confidence="high",
                candidate_prices=[expensive, Decimal("18.00")],
            ),
            routing.MAIN,
            variant.AMBIGUOUS_NO_SIGNAL,
        ),
        (
            "ladder -> review, cheapest candidate < $0.40",
            dict(
                resolved=False,
                reason=variant.METADATA_DETECTION_DISAGREEMENT,
                confidence="high",
                candidate_prices=[cheap, expensive],
            ),
            routing.PARKED,
            variant.METADATA_DETECTION_DISAGREEMENT,
        ),
        (
            "no catalog row at all",
            dict(resolved=False, reason=variant.NO_CATALOG_ROW, confidence="high"),
            routing.MAIN,
            variant.NO_CATALOG_ROW,
        ),
        (
            "identification failed",
            dict(resolved=False, reason=routing.IDENTIFICATION_FAILED),
            routing.MAIN,
            routing.IDENTIFICATION_FAILED,
        ),
        (
            "no position recoverable",
            dict(resolved=False, reason=routing.NO_POSITION),
            routing.MAIN,
            routing.NO_POSITION,
        ),
        (
            "matched row with a blank market price",
            dict(resolved=True, reason="metadata", confidence="high", price=None),
            routing.NO_MARKET_DATA,
            routing.NO_MARKET_DATA,
        ),
        (
            "matched row with a $0.00 market price",
            dict(
                resolved=True, reason="metadata", confidence="high", price=Decimal("0.00")
            ),
            routing.NO_MARKET_DATA,
            routing.NO_MARKET_DATA,
        ),
    ]
    for label, kwargs, queue, reason in table:
        destination = routing.route(**kwargs)
        c.equal((destination.queue, destination.reason), (queue, reason), label)

    # The cheapest candidate decides, not the dearest — routing on the optimistic end of a
    # range would park cards that might be valuable.
    c.equal(
        routing.route(
            resolved=False,
            reason=variant.AMBIGUOUS_NO_SIGNAL,
            candidate_prices=[cheap, expensive],
        ).price,
        cheap,
        "the main/parked cut reads the CHEAPEST candidate row",
    )
    c.equal(
        routing.cheapest([None, Decimal("0.00"), Decimal("2.00"), Decimal("1.00")]),
        Decimal("1.00"),
        "and blank/zero prices are skipped when finding it, not treated as zero",
    )

    # An unpriced card is never parked, whatever else is true of it.
    never_parked = True
    for reason in (
        variant.NO_CATALOG_ROW,
        routing.IDENTIFICATION_FAILED,
        routing.NO_POSITION,
        routing.SET_AMBIGUOUS,
    ):
        destination = routing.route(resolved=False, reason=reason, candidate_prices=[])
        if destination.queue != routing.MAIN or destination.price is not None:
            never_parked = False
            c.note(f"{reason} -> {destination.describe}")
    c.ok(never_parked, "an unpriced card always goes to MAIN, never parked — D9 in reverse")

    # --- the confidence gate is configurable ---------------------------------------------
    c.equal(
        routing.route(
            resolved=True,
            reason="metadata",
            confidence="low",
            price=expensive,
            review_below=routing.CONFIDENCE_NONE,
        ).queue,
        routing.LISTED,
        "--review-below-confidence=none restores 'confidence never routes on its own'",
    )
    c.equal(
        routing.route(
            resolved=True,
            reason="metadata",
            confidence="medium",
            price=expensive,
            review_below=routing.CONFIDENCE_MEDIUM,
        ).queue,
        routing.MAIN,
        "--review-below-confidence=medium routes medium as well as low",
    )
    c.equal(
        routing.route(
            resolved=True,
            reason="metadata",
            confidence="high",
            price=expensive,
            review_below=routing.CONFIDENCE_MEDIUM,
        ).queue,
        routing.LISTED,
        "...but never high",
    )
    c.raises(
        routing.UnknownConfidenceGate,
        lambda: routing.check_review_below("very-low"),
        "a confidence gate outside none | low | medium is refused",
    )

    # --- main-queue order: priced first, descending; unpriced last -------------------------
    ordered = join.join_batch(
        [
            join.IdentifiedCard(
                position=join.Position(9, 1), name="Articuno", number="161",
                printed_total="159", confidence="low",
                photo="captures/box9/0001.jpg",
            ),
            join.IdentifiedCard(
                position=join.Position(9, 2), name="Ghost", number="999",
                printed_total="159", confidence="high",
                photo="captures/box9/0002.jpg",
            ),
            join.IdentifiedCard(
                position=join.Position(9, 3), name="Butterfree", number="003",
                printed_total="159", metadata_finish="reverse_holo", confidence="low",
                photo="captures/box9/0003.jpg",
            ),
        ],
        catalog,
        router=join.default_router(),
    )
    c.note(ordered.report())
    c.equal(
        [q.destination.price for q in ordered.queue(routing.MAIN)],
        [HOLO_ONLY_PRICE, NO_NORMAL_REVERSE_PRICE, None],
        "main queue: priced first, descending by price, unpriced last",
    )
    c.equal(
        [q.card.position.index for q in ordered.queue(routing.MAIN)],
        [1, 3, 2],
        "...so you work the known-valuable cards first and nothing is hidden",
    )
    c.equal(
        len(ordered.matches), 0, "and every low-confidence card stayed out of the file"
    )

    # A low-confidence CHEAP card parks instead, and is not in the main queue at all.
    parked_run = join.join_batch(
        [
            join.IdentifiedCard(
                position=join.Position(9, 4), name="Billy & O'Nare", number="142",
                printed_total="159", metadata_finish="normal", confidence="low",
                photo="captures/box9/0004.jpg",
            )
        ],
        catalog,
        router=join.default_router(),
    )
    c.equal(
        [q.destination.queue for q in parked_run.queued],
        [routing.PARKED],
        "a low-confidence $0.12 card parks",
    )
    c.equal(
        len(parked_run.queue(routing.MAIN)),
        0,
        "...and is NOT in the main queue, where it would bury the expensive ones",
    )

    # --- rung 1's `--variant`: fills gaps, NEVER overrides ---------------------------------
    # D3 spends three paragraphs establishing that the capture toggle is a claim rather than
    # a hint. A flag able to replace a recorded toggle across a whole run is the single thing
    # that would undo that, so the guarantee is asserted here and not left to care.
    with tempfile.TemporaryDirectory() as tmp:
        captures = Path(tmp)
        (captures / "0001.jpg").write_bytes(b"")
        (captures / "0001.json").write_text(
            json.dumps({"box": 3, "position": 1, "variant": "normal"})
        )
        (captures / "0002.jpg").write_bytes(b"")
        (captures / "0002.json").write_text(json.dumps({"box": 3, "position": 2}))
        (captures / "0003.jpg").write_bytes(b"")  # no sidecar at all

        without = {c_.photo.stem: c_ for c_ in sidecar.scan(captures, box=3)}
        # The seeded sidecar at 0001 says `"variant": "normal"` — a BARE STRING, kept
        # deliberately. It is the shape every sidecar written before D3's amendment of
        # 2026-08-23 carries, and asserting the reader hands back the one-member tuple
        # `("normal",)` is what proves the read-side backfill rather than only the new path.
        # This used to assert the bare string back, which was strictly weaker: it could not
        # tell a backfill from a reader that had never heard of a set.
        c.equal(
            [without[k].metadata_finish for k in ("0001", "0002", "0003")],
            [("normal",), None, None],
            "with no flag: only the recorded toggle supplies a finish, and a bare string in "
            "the file reads as the ONE-MEMBER SET it always meant (D3 rung 1)",
        )
        c.ok(
            without["0002"].metadata_finish is None,
            "and no claim is None rather than an empty tuple — one spelling of 'nobody "
            "said anything', so `is None` stays the test every caller writes",
        )

        filled = {
            c_.photo.stem: c_
            for c_ in sidecar.scan(captures, box=3, variant_default="reverse_holo")
        }
        c.equal(
            filled["0001"].metadata_finish,
            ("normal",),
            "--variant=reverse_holo does NOT override a sidecar that says normal",
        )
        c.ok(
            not filled["0001"].variant_from_flag,
            "...and the card is not marked as having taken the flag",
        )
        c.equal(
            [filled["0002"].metadata_finish, filled["0003"].metadata_finish],
            [("reverse_holo",), ("reverse_holo",)],
            "--variant fills a sidecar with no variant, and a photo with no sidecar — with "
            "a ONE-MEMBER claim, which is what `docs/specs/batch-script.md` settles: the "
            "flag stays single-valued and is deliberately not repeatable",
        )
        c.ok(
            filled["0002"].variant_from_flag and filled["0003"].variant_from_flag,
            "...and both are marked, so the run report can say how many took the flag",
        )
        c.equal(
            sum(1 for c_ in filled.values() if c_.variant_from_flag),
            2,
            "exactly the cards with nothing recorded took the flag",
        )
        c.ok(
            sidecar.load(
                captures / "0003.jpg", root=captures, box=3, variant_default="holographic"
            ).metadata_finish
            is None,
            "a finish outside the enum is not applied, even from the flag",
        )

        # --- the reader keeps the WHOLE set (D3 rung 1, amended 2026-08-23) --------------
        # NOTHING ASSERTED THIS UNTIL NOW, which is the reason it is here. `_check_variant`
        # accepted a list from the day it was written and returned `kept[0]` — the first
        # member in the game's enum order — so a two-member claim was reduced to one on
        # every read. That reduction could have survived this whole change in silence: no
        # test looked at a list-valued sidecar, and a reduced claim does not refuse or
        # report a problem. It resolves. Rung 1 stops FILTERING and starts DETERMINING on
        # half of what the operator said, which is worse than dropping the claim outright.
        (captures / "0004.jpg").write_bytes(b"")
        (captures / "0004.json").write_text(
            json.dumps({"box": 3, "position": 4, "variant": ["reverse_holo", "normal"]})
        )
        (captures / "0005.jpg").write_bytes(b"")
        (captures / "0005.json").write_text(
            json.dumps({"box": 3, "position": 5, "variant": ["normal", "holographic"]})
        )
        (captures / "0006.jpg").write_bytes(b"")
        (captures / "0006.json").write_text(
            json.dumps({"box": 3, "position": 6, "variant": []})
        )

        sets = {c_.photo.stem: c_ for c_ in sidecar.scan(captures, box=3)}
        c.equal(
            sets["0004"].metadata_finish,
            ("normal", "reverse_holo"),
            "a TWO-MEMBER sidecar keeps both members — the reduction to `kept[0]` is gone, "
            "and the order is the GAME'S ENUM's and not the file's, so the same claim "
            "written in either order is one value",
        )
        c.equal(
            sets["0005"].metadata_finish,
            ("normal",),
            "a member outside the game's finishes is DROPPED from the claim rather than "
            "refusing it — this reader defends files already on disk, where salvage beats a "
            "refusal nobody can act on; the capture route refuses the same body outright, "
            "because its caller can fix the request",
        )
        c.ok(
            sets["0005"].problem is not None and "holographic" in sets["0005"].problem,
            "...and the dropped member is NAMED in the problem, never discarded silently",
        )
        c.ok(
            sets["0006"].metadata_finish is None,
            "an empty list is no claim, identical to the null this field has always "
            "allowed (D3) — and it is None, not `()`, so rungs 2 and 3 stay live",
        )

    # --- rung 3's whitelist is the enum itself, asserted by ADDING to it ------------------
    # `cli/resolve.py` is the one seam where the model's `finish` crosses from the
    # identification payload into an `IdentifiedCard`, and it is the only place the value can
    # be dropped. It used to be whitelisted against a literal tuple written beside it, which
    # is a second copy of this enum that nothing keeps in step: a finish added to
    # `variant.FINISHES` would fall out of the literal, land as `None`, and route the card to
    # review with nothing on screen saying why — a silent drop, which is the one thing this
    # pipeline may never do.
    #
    # ASSERTED BY ADDING ONE, because that is the case a source scan cannot reach. A grep can
    # say the two agree today; only this can say they cannot come apart. T7 keeps the source
    # half — that no finish is spelled out in that file at all.
    #
    # THE ENUM'S HOME MOVED ON 2026-08-23 AND SO DID THIS WIDENING. It used to assign to
    # `variant.FINISHES`, which was the home while the ladder was Pokemon-only. The ladder
    # now reads each game's finishes from `pipeline/games.py` through `variant.vocabulary`,
    # so `variant.FINISHES` is a Pokemon-shaped alias that `cli/resolve.py` no longer
    # consults — and patching it proved nothing about the seam this case exists to guard.
    # Widening the REGISTRY entry keeps the assertion pointed at the real single source, and
    # it now exercises the whole chain: resolve.py -> variant.vocabulary -> games registry.
    pokemon = games.get(games.DEFAULT_GAME)
    original = tuple(pokemon["finishes"])
    try:
        pokemon["finishes"] = original + ("foil_etch",)
        widened = _detected_finishes(REPO_ROOT / SOURCE_FIXTURE, {1: "foil_etch"})
    finally:
        pokemon["finishes"] = original
    c.equal(
        widened.get(1),
        "foil_etch",
        "a finish ADDED to the game's registry entry survives the trip through "
        "cli/resolve.py — the whitelist is the enum itself, never a copy of it",
    )
    c.equal(
        tuple(games.get(games.DEFAULT_GAME)["finishes"]),
        original,
        "and the registry is left exactly as it was found, so the tests after this one see "
        "the real one",
    )

    # The negative, which is the reason the test exists at all rather than being deleted with
    # the literal: an unknown string from the model is not a finish, and `variant.resolve`
    # raises `UnknownFinish` rather than guessing, so it has to be dropped before it reaches
    # the ladder.
    c.equal(
        _detected_finishes(
            REPO_ROOT / SOURCE_FIXTURE, {1: "holographic", 2: "reverse_holo", 3: None}
        ),
        {1: None, 2: "reverse_holo", 3: None},
        "a string OUTSIDE the enum still lands as None, and a real one still lands intact — "
        "the whitelist did not simply stop whitelisting",
    )

    return c.result()
