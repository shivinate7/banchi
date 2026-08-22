"""T3 — Join coverage.

For a batch of identified cards, every card matches exactly one fixture row for its
resolved condition string. Report unmatched in BOTH directions before any output is
written.

Pass: zero unmatched, or every unmatched card reported both ways and routed to a standing
queue with its position, before any output is written.

Required cases (docs/GATES.md), all against real SV09 rows:
  - Secret rares where the number exceeds the denominator   Articuno 161/159
  - Blank-`Number` rows (name-matching fallback)            Code Card - Booster Pack
  - Names with apostrophes and ampersands                   Billy & O'Nare 142/159
  - 7 identical cards -> one row, `Add to Quantity` = 4,    Dunsparce 120/159
    3 recorded as backstock
  - Multi-set key collisions                                003/159 in two Set Names

Both directions, and both of the pipeline's pairings:

  cards <-> catalog   a card that resolves to no row is reported with its photo, and the
                      closure check proves no card went in without coming out either
                      matched or reported.
  file  <-> inventory `reconcile_import` — v1 bug #5 verbatim: it matched by box+position,
                      silently skipped identified cards, and reported nothing for
                      unmatched rows. A one-directional check passes on that bug.

TWO EMIT GATES, and the difference between them is the amended pass criterion. Without a
router an unmatched card is UNRECORDED, so `emit_import` raises and no file appears — the
pre-v2 behaviour, still asserted. With a router the same card is ROUTED into a standing
queue with its position retained, and output proceeds: reviews stop suppressing output
(v2 §5.6), because holding 400 good cards hostage to 7 ambiguous ones is the wrong trade.
Unlisted is acceptable; unrecorded is not, and that is what is actually being tested.

MULTI-SET KEYING IS SYNTHETIC, and labelled. The committed fixture is a single-set export
(SV09: Journey Together, 341 rows), so a cross-set key collision does not exist in it to
test against. `_multi_set_catalog()` clones a handful of rows under a second Set Name with
distinct SKUs — the same approach, and the same reason, as T4's synthetic three-row block.
Replace it the day a two-set export is committed.
"""

from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

from harness.tests import Checks, Result
from pipeline import join, pricing, routing, tcgcsv, variant

NAME = "T3"
DESCRIPTION = "Catalog join covers every card, unmatched reported both ways"
PASS_CRITERIA = (
    "zero unmatched, or every unmatched card reported both ways and routed to a "
    "standing queue with its position, before any output is written"
)

LIVE_QUANTITY_CAP = 4

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_FIXTURE = "fixtures/sv09_export_untouched.csv"

# Required-case rows, by SKU, so a fixture re-export that moves them fails loudly here
# rather than quietly matching something else.
SECRET_RARE_SKU = "8608859"  # Articuno - 161/159, Near Mint Holofoil, 22.03
BLANK_NUMBER_SKU = "8665451"  # Code Card - Journey Together Booster Pack, no Number
BLANK_NUMBER_NAME = "Code Card - Journey Together Booster Pack"
AMPERSAND_NAME = "Billy & O'Nare"
AMPERSAND_NORMAL_SKU = "8608674"  # 142/159 Near Mint, 0.12
AMPERSAND_REVERSE_SKU = "8608679"  # 142/159 Near Mint Reverse Holofoil, 0.23
SEVEN_COPY_SKU = "8608459"  # Dunsparce 120/159 Near Mint, 2.06
BUTTERFREE_REVERSE_SKU = "8607369"  # 003/159 Near Mint Reverse Holofoil, 0.47

BOX = 3


SECOND_SET = "SV08: Surging Sparks"
CLONED_HOLO_SKU = "9100001"
CLONED_REVERSE_SKU = "9100002"
COLLIDING_KEY = "003/159"


def _card(
    index, name, number=None, total="159", metadata=None, detected=None,
    set_hint=None, confidence="high",
):
    return join.IdentifiedCard(
        position=join.Position(box=BOX, index=index),
        name=name,
        number=number,
        printed_total=None if number is None else total,
        metadata_finish=metadata,
        detected_finish=detected,
        photo=f"captures/box{BOX}/{index:04d}.jpg",
        set_hint=set_hint,
        confidence=confidence,
    )


def _multi_set_catalog(export):
    """SYNTHETIC: the SV09 export plus 003/159 cloned into a second Set Name.

    Labelled, because the committed fixture is single-set and a cross-set collision cannot
    be produced from it. Distinct SKUs, so nothing about the clone can be mistaken for the
    original by the thing under test — the join matches on `TCGplayer Id`.
    """
    rows = list(export.rows)
    for row in export.rows:
        if row[tcgcsv.NUMBER_COLUMN] != COLLIDING_KEY:
            continue
        sku = (
            CLONED_HOLO_SKU
            if row[tcgcsv.CONDITION_COLUMN] == "Near Mint Holofoil"
            else CLONED_REVERSE_SKU
        )
        rows.append(
            dict(
                row,
                **{
                    tcgcsv.SKU_COLUMN: sku,
                    tcgcsv.SET_COLUMN: SECOND_SET,
                    tcgcsv.NAME_COLUMN: "Pikachu",
                    tcgcsv.MARKET_PRICE_COLUMN: "5.00",
                },
            )
        )
    return join.Catalog(tcgcsv.Export(header=export.header, rows=tuple(rows)))


def _clean_batch():
    """13 cards covering all four required cases."""
    cards = []
    # 7 identical Dunsparce, normal, at seven consecutive positions.
    for index in range(1, 8):
        cards.append(_card(index, "Dunsparce", "120", metadata="normal"))
    # Secret rare, no capture-time metadata: the catalog forces holofoil.
    cards.append(_card(8, "Articuno", "161"))
    # Apostrophe + ampersand, both variants.
    cards.append(_card(9, AMPERSAND_NAME, "142", metadata="normal"))
    cards.append(_card(10, AMPERSAND_NAME, "142", metadata="reverse_holo"))
    # Blank-Number product: no collector number, so the name fallback applies.
    cards.append(_card(11, BLANK_NUMBER_NAME))
    # Two reverse-holo Butterfree, to give the import file more than one listable row.
    cards.append(_card(12, "Butterfree", "003", metadata="reverse_holo"))
    cards.append(_card(13, "Butterfree", "003", metadata="reverse_holo"))
    return cards


def run() -> Result:
    c = Checks()

    export = tcgcsv.read_export(REPO_ROOT / SOURCE_FIXTURE)
    catalog = join.Catalog(export)
    by_sku = export.by_sku()

    # --- join key ---------------------------------------------------------------------
    c.equal(join.join_key("13", "159"), "013/159", "join key zero-pads to three digits")
    c.equal(join.join_key("161", "159"), "161/159", "secret rare key exceeds denominator")
    c.equal(
        join.join_key(161, "159"), "161/159", "join key accepts an int collector number"
    )

    # --- clean batch ------------------------------------------------------------------
    cards = _clean_batch()
    report = join.join_batch(cards, catalog, live_cap=LIVE_QUANTITY_CAP)
    c.note(report.report())

    c.equal(report.cards_in, 13, "13 cards in")
    c.equal(len(report.unmatched_cards), 0, "direction 1: zero cards without a row")
    c.equal(len(report.unmatched_rows), 0, "direction 2: zero rows without a card")
    c.equal(report.dropped, 0, "no card silently dropped (v1 bug #5)")
    c.ok(report.ok, "clean batch joins clean")
    c.equal(len(report.matches), 6, "13 cards aggregate to 6 SKUs")

    # Every card resolved to exactly one row, and that row is the only one in the whole
    # catalog for its identity and condition. Identity is the number; for the blank-Number
    # rows it is the product name, which is what the fallback matched on.
    unique = True
    for match in report.matches.values():
        number = match.row[tcgcsv.NUMBER_COLUMN]
        identity = tcgcsv.NUMBER_COLUMN if number else tcgcsv.NAME_COLUMN
        peers = [
            r
            for r in export.rows
            if r[identity] == match.row[identity]
            and r[tcgcsv.CONDITION_COLUMN] == match.condition
        ]
        if len(peers) != 1:
            unique = False
            c.note(
                f"{match.sku} {match.row[identity]!r} {match.condition}: "
                f"{len(peers)} catalog rows"
            )
    c.ok(unique, "each card resolved to exactly one catalog row for its condition")

    # --- rung 0: a human answer outranks the whole ladder -----------------------------
    # REGRESSION, NOT NEW COVERAGE. The first real run (2026-08-22) parked 16 cards on
    # metadata/detection disagreement; the owner answered every one on the review screen;
    # and the next join re-derived the same disagreement and re-parked them, because the
    # answer landed on the inventory record and nothing on the join path ever read it.
    # An answered card must resolve to its answered row — the ladder's signals are the
    # question, and the human already gave the answer while looking at the photograph.
    answered_card = join.IdentifiedCard(
        position=join.Position(box=BOX, index=90),
        name="Articuno",
        number="161",
        printed_total="159",
        # The exact disagreement that parks a card: the toggle claims one finish, the
        # photograph reads another. Without rung 0 this is METADATA_DETECTION_DISAGREEMENT.
        metadata_finish="normal",
        detected_finish="reverse_holo",
        photo=f"captures/box{BOX}/0090.jpg",
        confidence="high",
        answered_sku=SECRET_RARE_SKU,
        answered_condition="Near Mint Holofoil",
    )
    answered_report = join.join_batch(
        [answered_card], catalog, live_cap=LIVE_QUANTITY_CAP, router=join.default_router()
    )
    c.equal(
        len(answered_report.queue(routing.MAIN)) + len(answered_report.queue(routing.PARKED)),
        0,
        "an answered card is never re-queued — the answer consumed, not re-derived",
    )
    if c.ok(SECRET_RARE_SKU in answered_report.matches, "the answered SKU is the match"):
        answered_match = answered_report.matches[SECRET_RARE_SKU]
        c.equal(answered_match.condition, "Near Mint Holofoil", "at the answered condition")
        c.equal(
            answered_match.stages,
            ["human_answered"],
            "and the stage says a human decided it — greppable from screen to report",
        )
    # An answer against a row this export no longer carries falls through to the ladder
    # rather than being guessed: the same card with an unknown SKU reviews exactly as it
    # would have with no answer at all — here as METADATA_NOT_STOCKED, because 161/159 is
    # holofoil-only and the toggle claims normal, which rung 1 reports ahead of the
    # disagreement by its own stated ordering.
    stale_answer = join.IdentifiedCard(
        position=join.Position(box=BOX, index=91),
        name="Articuno",
        number="161",
        printed_total="159",
        metadata_finish="normal",
        detected_finish="reverse_holo",
        photo=f"captures/box{BOX}/0091.jpg",
        confidence="high",
        answered_sku="0000000",
        answered_condition="Near Mint Holofoil",
    )
    stale_report = join.join_batch(
        [stale_answer], catalog, live_cap=LIVE_QUANTITY_CAP, router=join.default_router()
    )
    c.equal(
        [q.destination.reason for q in stale_report.queued],
        ["metadata_not_stocked"],
        "an answer naming a SKU the export dropped falls through to the ladder, never a guess",
    )

    # --- committed copies: TCGplayer already holds them -------------------------------
    # REGRESSION. The first real post-import re-emit (2026-08-22) re-counted 37 staged
    # copies into the files — quantities that would have DOUBLED in Staged on import —
    # and re-pushed their records backwards from `staged`. A committed copy still matches
    # and still counts as a copy in the report, but it takes no room in the import file
    # and is never handed to the emitter's push loop.
    committed_pair = [
        join.IdentifiedCard(
            position=join.Position(box=BOX, index=95),
            name="Articuno",
            number="161",
            printed_total="159",
            metadata_finish="holo",
            photo=f"captures/box{BOX}/0095.jpg",
            confidence="high",
            committed=True,
        ),
        join.IdentifiedCard(
            position=join.Position(box=BOX, index=96),
            name="Articuno",
            number="161",
            printed_total="159",
            metadata_finish="holo",
            photo=f"captures/box{BOX}/0096.jpg",
            confidence="high",
        ),
    ]
    committed_report = join.join_batch(
        committed_pair, catalog, live_cap=LIVE_QUANTITY_CAP, router=join.default_router()
    )
    if c.ok(SECRET_RARE_SKU in committed_report.matches, "both copies match their SKU"):
        held = committed_report.matches[SECRET_RARE_SKU]
        c.equal(held.copies, 2, "the report counts every physical copy, committed or not")
        c.equal(held.add_to_quantity, 1, "the file takes only the copy TCGplayer lacks")
        c.equal(
            [(p.box, p.index) for p in held.live_positions],
            [(BOX, 96)],
            "and the push loop is handed only that copy — never a staged record",
        )
        c.equal(held.backstock, 0, "a committed copy is not backstock; it is on TCGplayer")

    # A SKU whose every copy is committed adds nothing and is excluded from the files by
    # the same gate that excludes a SKU at the live cap.
    all_committed = join.join_batch(
        [committed_pair[0]], catalog, live_cap=LIVE_QUANTITY_CAP, router=join.default_router()
    )
    c.equal(
        [m.sku for m in all_committed.at_cap],
        [SECRET_RARE_SKU],
        "a fully committed SKU is reported, not re-emitted — nothing added, nothing lost",
    )

    # --- required case: secret rare ---------------------------------------------------
    c.ok(SECRET_RARE_SKU in report.matches, "secret rare 161/159 matched")
    if SECRET_RARE_SKU in report.matches:
        secret = report.matches[SECRET_RARE_SKU]
        c.equal(secret.condition, "Near Mint Holofoil", "161/159 resolved holofoil-only")
        c.equal(secret.stages, ["catalog_forced"], "161/159 resolved by the catalog")

    # --- required case: blank-Number name fallback -------------------------------------
    c.ok(BLANK_NUMBER_SKU in report.matches, "blank-Number row matched by name")
    c.equal(
        by_sku[BLANK_NUMBER_SKU][tcgcsv.NUMBER_COLUMN],
        "",
        "the name-fallback row really does have a blank Number",
    )

    # --- required case: apostrophes and ampersands -------------------------------------
    c.ok(
        AMPERSAND_NORMAL_SKU in report.matches
        and AMPERSAND_REVERSE_SKU in report.matches,
        f"{AMPERSAND_NAME!r} matched in both variants",
    )
    c.equal(
        by_sku[AMPERSAND_NORMAL_SKU][tcgcsv.NAME_COLUMN],
        AMPERSAND_NAME,
        "apostrophe and ampersand survive the parse",
    )

    # --- required case: 7 identical cards ----------------------------------------------
    seven = report.matches.get(SEVEN_COPY_SKU)
    if c.ok(seven is not None, "7 identical cards collapse to one SKU"):
        c.equal(seven.copies, 7, "7 copies recorded")
        c.equal(seven.add_to_quantity, 4, "Add to Quantity = 4 (live cap)")
        c.equal(seven.backstock, 3, "3 recorded as backstock")
        c.equal(
            [p.index for p in seven.live_positions],
            [1, 2, 3, 4],
            "live copies are the first four positions",
        )
        c.equal(
            [p.index for p in seven.backstock_positions],
            [5, 6, 7],
            "backstock copies keep their own positions",
        )
        c.equal(
            seven.backstock_positions[0].label,
            "Box 3 · Section 1 · Card 5",
            "backstock position is addressable",
        )

    # --- never join on Product Name -----------------------------------------------------
    wrong_name = join.join_batch(
        [_card(90, "NOT THE RIGHT NAME", "120", metadata="normal")], catalog
    )
    c.equal(
        list(wrong_name.matches),
        [SEVEN_COPY_SKU],
        "a wrong Product Name still joins on the number",
    )
    name_only = join.join_batch([_card(91, BLANK_NUMBER_NAME, "999")], catalog)
    c.equal(
        len(name_only.unmatched_cards),
        1,
        "a numbered card never falls back to name matching",
    )

    # --- sub-threshold cards are a decision, not a constant ------------------------------
    below = set(report.below_threshold.skus)
    c.equal(
        below,
        {AMPERSAND_NORMAL_SKU, AMPERSAND_REVERSE_SKU, BLANK_NUMBER_SKU},
        f"sub-${pricing.THRESHOLD} SKUs bucketed, not dropped",
    )
    c.equal(
        report.cards_out, report.cards_in, "every card in is accounted for on the way out"
    )

    # The distribution is preserved, banded — a $0.23 card and a $0.03 card are not the
    # same later decision, and "everything under $0.40" would hide that.
    bands = report.below_threshold.bands()
    c.equal([b.label for b in bands], ["$0.30-$0.40", "$0.20-$0.30", "$0.10-$0.20", "$0.00-$0.10"],
            "sub-threshold bands follow the threshold")
    c.equal(
        {b.label: b.copies for b in bands},
        {"$0.30-$0.40": 0, "$0.20-$0.30": 1, "$0.10-$0.20": 1, "$0.00-$0.10": 1},
        "each sub-threshold card lands in the right band",
    )
    c.equal(
        sum(b.copies for b in bands),
        report.below_threshold.copies,
        "the bands account for every sub-threshold copy",
    )
    c.equal(
        {b.label: str(b.share) for b in bands}["$0.00-$0.10"],
        "33.3",
        "band share is reported as a percentage of sub-threshold copies",
    )

    # --- output ----------------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        undecided_path = Path(tmp) / "undecided.csv"
        c.raises(
            join.Undecided,
            lambda: join.emit_import(report, catalog, undecided_path),
            "emit_import refuses while sub-threshold cards have no disposition",
        )
        c.ok(not undecided_path.exists(), "no file written for an undecided bucket")

        # Run default: flat at the floor.
        out_path = Path(tmp) / "import.csv"
        data = join.emit_import(
            report, catalog, out_path, sub_threshold=pricing.flat_floor()
        )
        written = tcgcsv.parse(data)
        emitted = {r[tcgcsv.SKU_COLUMN]: r for r in written.rows}

        skus = [r[tcgcsv.SKU_COLUMN] for r in written.rows]
        c.equal(len(skus), len(set(skus)), "no duplicate TCGplayer Id rows in the file")
        c.equal(
            sorted(skus),
            sorted(
                [
                    SEVEN_COPY_SKU,
                    SECRET_RARE_SKU,
                    BUTTERFREE_REVERSE_SKU,
                    AMPERSAND_NORMAL_SKU,
                    AMPERSAND_REVERSE_SKU,
                    BLANK_NUMBER_SKU,
                ]
            ),
            "every matched SKU is written once the disposition is given",
        )
        c.equal(
            emitted[SEVEN_COPY_SKU][tcgcsv.QUANTITY_COLUMN],
            "4",
            "the 7-copy SKU is written once with Add to Quantity = 4",
        )
        c.equal(
            emitted[BUTTERFREE_REVERSE_SKU][tcgcsv.QUANTITY_COLUMN],
            "2",
            "two copies under the cap are written as 2",
        )
        c.equal(
            emitted[SECRET_RARE_SKU][tcgcsv.PRICE_COLUMN],
            "22.03",
            "an at-market SKU follows the D9 match rule",
        )
        c.equal(
            {emitted[s][tcgcsv.PRICE_COLUMN] for s in below},
            {"0.40"},
            "flat_floor lists every sub-threshold card at $0.40, whatever its market",
        )

        # Run default plus going under the hood on one SKU.
        mixed_path = Path(tmp) / "mixed.csv"
        mixed = tcgcsv.parse(
            join.emit_import(
                report,
                catalog,
                mixed_path,
                sub_threshold=pricing.flat_price("0.50"),
                sku_dispositions={BLANK_NUMBER_SKU: pricing.flat_floor()},
            )
        )
        mixed_rows = {r[tcgcsv.SKU_COLUMN]: r for r in mixed.rows}
        c.equal(
            mixed_rows[AMPERSAND_NORMAL_SKU][tcgcsv.PRICE_COLUMN],
            "0.50",
            "a custom flat price applies to the whole sub-threshold bucket",
        )
        c.equal(
            mixed_rows[BLANK_NUMBER_SKU][tcgcsv.PRICE_COLUMN],
            "0.40",
            "a per-SKU disposition overrides the run default",
        )
        c.equal(
            mixed_rows[SECRET_RARE_SKU][tcgcsv.PRICE_COLUMN],
            "22.03",
            "the run default does not touch at-market SKUs",
        )
        c.equal(
            tcgcsv.parse(
                join.emit_import(
                    report,
                    catalog,
                    Path(tmp) / "override.csv",
                    sub_threshold=pricing.flat_floor(),
                    sku_dispositions={SECRET_RARE_SKU: pricing.flat_price("19.99")},
                )
            ).by_sku()[SECRET_RARE_SKU][tcgcsv.PRICE_COLUMN],
            "19.99",
            "a per-SKU disposition can also override an at-market SKU",
        )

    c.raises(
        pricing.BelowFloor,
        lambda: pricing.flat_price("0.25"),
        f"a flat price under the ${pricing.FLOOR} floor has to be deliberate",
    )
    c.equal(
        pricing.flat_price("0.25", allow_below_floor=True).resolve(),
        Decimal("0.25"),
        "and is honoured once it is",
    )
    c.raises(
        join.Undecided,
        lambda: join.prices_for(
            report,
            sub_threshold=pricing.flat_floor(),
            sku_dispositions={"0000000": pricing.flat_floor()},
        ),
        "a disposition for a SKU not in the batch is an error, not a no-op",
    )

    # --- D7 refill: live quantity already on TCGplayer ------------------------------------
    partly_live = dict(by_sku[SEVEN_COPY_SKU], **{tcgcsv.LIVE_QUANTITY_COLUMN: "3"})
    refill = join.SkuMatch(
        sku=SEVEN_COPY_SKU,
        row=partly_live,
        positions=[join.Position(BOX, i) for i in range(1, 8)],
    )
    c.equal(refill.add_to_quantity, 1, "refill tops up to the cap, not past it")
    c.equal(refill.backstock, 6, "the rest stays backstock")

    # --- unmatched in both directions, output suppressed ---------------------------------
    dirty = _clean_batch() + [
        _card(14, "Fake Card", "999"),  # no such row in the catalog
        _card(15, "Unlabelled Promo"),  # no number, no blank-Number row by that name
    ]
    dirty_report = join.join_batch(dirty, catalog, live_cap=LIVE_QUANTITY_CAP)
    c.note(dirty_report.report())
    c.equal(len(dirty_report.unmatched_cards), 2, "both bad cards reported, not dropped")
    c.equal(
        [u.reason for u in dirty_report.unmatched_cards],
        ["no_catalog_row", "no_catalog_row"],
        "unmatched cards carry a reason",
    )
    c.ok(
        all(u.card.photo for u in dirty_report.unmatched_cards),
        "each review-queue item carries its capture photo (D4)",
    )
    c.equal(dirty_report.dropped, 0, "unmatched cards are reported, never dropped")
    c.ok(not dirty_report.ok, "a batch with unmatched cards is not ok")

    with tempfile.TemporaryDirectory() as tmp:
        suppressed_path = Path(tmp) / "must-not-exist.csv"
        c.raises(
            join.OutputSuppressed,
            lambda: join.emit_import(
                dirty_report, catalog, suppressed_path,
                sub_threshold=pricing.flat_floor(),
            ),
            "emit_import refuses to write while anything is unmatched",
        )
        c.ok(not suppressed_path.exists(), "no output file was written")
        c.ok(
            "2 card(s) matched no catalog row" in "; ".join(dirty_report.blocking_reasons),
            "the refusal names both directions",
        )

    # A matched SKU holding no card is direction two of the same pairing.
    hollow = join.JoinReport(cards_in=0)
    hollow.matches[SECRET_RARE_SKU] = join.SkuMatch(
        sku=SECRET_RARE_SKU, row=by_sku[SECRET_RARE_SKU]
    )
    c.equal(len(hollow.unmatched_rows), 1, "direction 2: a row with no card is reported")
    c.ok(not hollow.ok, "a row with no card blocks output")

    # A card that went in and came out nowhere is the v1 bug #5 shape itself.
    silent = join.JoinReport(cards_in=5)
    c.equal(silent.dropped, 5, "a dropped card is visible in the report")
    c.ok(not silent.ok, "dropped cards block output")

    # --- routed, not suppressed: the amended pass criterion ---------------------------------
    routed = join.join_batch(
        dirty, catalog, live_cap=LIVE_QUANTITY_CAP, router=join.default_router()
    )
    c.note(routed.report())
    c.equal(
        len(routed.unmatched_cards),
        0,
        "with a router, an unresolvable card is not left unrecorded",
    )
    c.equal(len(routed.queued), 2, "it is recorded in a standing queue instead")
    c.equal(routed.dropped, 0, "and the closure check still holds — nothing dropped")
    c.ok(routed.ok, "a fully routed batch no longer suppresses output (v2 §5.6)")
    c.equal(
        sorted(q.card.position.index for q in routed.queued),
        [14, 15],
        "each queued card keeps its position — the queue is addressable, not a count",
    )
    c.ok(
        all(q.card.photo for q in routed.queued),
        "each queued card keeps its capture photo (D4)",
    )
    c.equal(
        sorted({q.resolution_reason for q in routed.queued}),
        ["no_catalog_row"],
        "and the reason it could not be resolved",
    )
    with tempfile.TemporaryDirectory() as tmp:
        routed_path = Path(tmp) / "routed.csv"
        written = tcgcsv.parse(
            join.emit_import(
                routed, catalog, routed_path, sub_threshold=pricing.flat_floor()
            )
        )
        c.ok(routed_path.exists(), "the 400 good cards are written while 2 wait in a queue")
        c.equal(
            len(written.rows),
            6,
            "and the file holds exactly the SKUs that resolved",
        )

    # --- multi-set key collisions (SYNTHETIC — see the module docstring) ----------------------
    multi = _multi_set_catalog(export)
    c.equal(
        len(multi.set_names), 2, "the synthetic catalog really does carry two Set Names"
    )
    c.equal(
        multi.colliding_keys,
        [COLLIDING_KEY],
        "the colliding key is computed at catalog build, before any card is joined",
    )
    c.equal(
        sorted(multi.sets_for_key(COLLIDING_KEY)),
        sorted(["SV09: Journey Together", SECOND_SET]),
        "and it names which sets collide, so the exposure is a number not an assumption",
    )
    c.equal(
        multi.colliding_keys and join.Catalog(export).colliding_keys,
        [],
        "the single-set fixture has no collisions at all",
    )

    hinted = join.join_batch(
        [_card(20, "Butterfree", "003", metadata="reverse_holo", set_hint="sv9")],
        multi,
        router=join.default_router(),
    )
    c.equal(
        list(hinted.matches),
        [BUTTERFREE_REVERSE_SKU],
        "a colliding key is resolved by the sidecar set hint",
    )
    c.equal(
        [q.destination.queue for q in hinted.queued], [], "and nothing is queued for it"
    )

    other_set = join.join_batch(
        [_card(21, "Pikachu", "003", metadata="reverse_holo", set_hint="SV08")],
        multi,
        router=join.default_router(),
    )
    c.equal(
        list(other_set.matches),
        [CLONED_REVERSE_SKU],
        "the hint picks the OTHER set when that is the one named",
    )

    c.ok(
        join.set_matches("sv9", "SV09: Journey Together"),
        "set hints fold zero-padding: pokemontcg.io writes sv9, TCGplayer writes SV09",
    )
    c.ok(
        join.set_matches("Journey Together", "SV09: Journey Together"),
        "the name on its own matches too",
    )
    c.ok(
        not join.set_matches("sv1", "SV19: Nothing"),
        "and a hint is never a substring match — sv1 must not select sv19",
    )

    for label, hint in (("no hint", None), ("a hint naming neither set", "sv5")):
        ambiguous = join.join_batch(
            [_card(22, "Butterfree", "003", metadata="reverse_holo", set_hint=hint)],
            multi,
            router=join.default_router(),
        )
        c.equal(
            [q.destination.reason for q in ambiguous.queued],
            [routing.SET_AMBIGUOUS],
            f"a colliding key with {label} goes to review as set_ambiguous, never guessed",
        )
        c.equal(list(ambiguous.matches), [], f"...and resolves to nothing with {label}")

    untouched = join.join_batch(
        [_card(23, "Dunsparce", "120", metadata="normal")],
        multi,
        router=join.default_router(),
    )
    c.equal(
        list(untouched.matches),
        [SEVEN_COPY_SKU],
        "a NON-colliding key is unaffected by the presence of a second set",
    )

    # The latent bug §5.1 closes: `by_condition` used to keep the last of two rows sharing a
    # condition string, silently pricing whichever the export happened to list second.
    twins = [by_sku[SEVEN_COPY_SKU], dict(by_sku[SEVEN_COPY_SKU], **{tcgcsv.SKU_COLUMN: "9200001"})]
    c.equal(
        variant.resolve(twins, metadata_finish="normal").reason,
        variant.DUPLICATE_CONDITION,
        "two candidate rows with one condition string review, rather than a coin flip",
    )

    # --- file <-> inventory, the v1 bug #5 pairing ----------------------------------------
    inventory = [SEVEN_COPY_SKU, SECRET_RARE_SKU, AMPERSAND_NORMAL_SKU]
    file_rows = [by_sku[SEVEN_COPY_SKU], by_sku[SECRET_RARE_SKU], by_sku["8607459"]]
    reconcile = join.reconcile_import(file_rows, inventory)
    c.note(reconcile.report())
    c.equal(
        reconcile.rows_without_cards,
        ["8607459"],
        "a file row with no inventory card is reported",
    )
    c.equal(
        reconcile.cards_without_rows,
        [AMPERSAND_NORMAL_SKU],
        "an inventory card the file never mentions is reported",
    )
    c.ok(not reconcile.ok, "either direction blocks a clean import")
    c.ok(
        join.reconcile_import(
            [by_sku[s] for s in inventory], inventory
        ).ok,
        "a matching file and inventory reconcile clean",
    )

    return c.result()
