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
from identify import sidecar
from pipeline import join, routing, tcgcsv, variant
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
        c.equal(
            [without[k].metadata_finish for k in ("0001", "0002", "0003")],
            ["normal", None, None],
            "with no flag: only the recorded toggle supplies a finish",
        )

        filled = {
            c_.photo.stem: c_
            for c_ in sidecar.scan(captures, box=3, variant_default="reverse_holo")
        }
        c.equal(
            filled["0001"].metadata_finish,
            "normal",
            "--variant=reverse_holo does NOT override a sidecar that says normal",
        )
        c.ok(
            not filled["0001"].variant_from_flag,
            "...and the card is not marked as having taken the flag",
        )
        c.equal(
            [filled["0002"].metadata_finish, filled["0003"].metadata_finish],
            ["reverse_holo", "reverse_holo"],
            "--variant fills a sidecar with no variant, and a photo with no sidecar",
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
    original = variant.FINISHES
    try:
        variant.FINISHES = original + ("foil_etch",)
        widened = _detected_finishes(REPO_ROOT / SOURCE_FIXTURE, {1: "foil_etch"})
    finally:
        variant.FINISHES = original
    c.equal(
        widened.get(1),
        "foil_etch",
        "a finish ADDED to variant.FINISHES survives the trip through cli/resolve.py — the "
        "whitelist is the enum itself, never a copy of it",
    )
    c.equal(
        variant.FINISHES,
        original,
        "and the enum is left exactly as it was found, so the six tests after this one see "
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
