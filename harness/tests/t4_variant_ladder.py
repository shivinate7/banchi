"""T4 — Variant ladder.

For a card with normal, holo, and reverse rows in the fixture, assert each ladder stage
resolves to the correct condition string and price.

Pass: all four stages, plus the review path fires on disagreement.

The ladder (D3 in docs/DECISIONS.md), in order:
  1. Capture-time metadata — variant toggle recorded in the card's JSON sidecar. Primary
     path. `--variant` on the batch script is only an override.
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

Guards v1 bug #1: variant mispricing, which blindly took
holofoil || reverseHolofoil || normal.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from harness.tests import Checks, Result
from pipeline import join, tcgcsv, variant

NAME = "T4"
DESCRIPTION = "Variant ladder resolves all four stages"
PASS_CRITERIA = "all four stages correct, and review fires on metadata/detection disagreement"

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

    return c.result()
