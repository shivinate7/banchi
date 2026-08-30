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

OTHER EXPORTS ARE READ FOR TWO THINGS: THE NUMBER FOLD, AND THE GAME PARTITION. SV09 is
padded, so every case in this file could pass against a join that read `39/236` and
`039/236` as different cards — which it did, silently, for as long as SV09 was the only
committed fixture. `_check_number_fold` joins against the unpadded Pokemon export and the
letter-suffixed Riftbound one for exactly that reason: a fold can only be shown to work by
a dialect the rest of the file does not speak. `_check_game_partition` reads the Riftbound
export again as the OTHER GAME (D25): the file->game mapping off `Product Line` cells and
never filenames, one catalog per game, the two refusals, the zero-row wrong-file refusal,
one import file per game, and `pokemon` keeping its Code Card rows under the partition.

MULTI-SET KEYING IS SYNTHETIC, and labelled. The committed fixture is a single-set export
(SV09: Journey Together, 341 rows), so a cross-set key collision does not exist in it to
test against. `_multi_set_catalog()` clones a handful of rows under a second Set Name with
distinct SKUs — the same approach, and the same reason, as T4's synthetic three-row block.
Replace it the day a two-set export is committed.
"""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from decimal import Decimal
from io import StringIO
from pathlib import Path

from harness.tests import Checks, Result
from cli import resolve, runs
from pipeline import join, pricing, routing, tcgcsv, variant
from store import files, master
from store.session import Store

NAME = "T3"
DESCRIPTION = "Catalog join covers every card, unmatched reported both ways"
PASS_CRITERIA = (
    "zero unmatched, or every unmatched card reported both ways and routed to a "
    "standing queue with its position, before any output is written"
)

LIVE_QUANTITY_CAP = 4

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_FIXTURE = "fixtures/sv09_export_untouched.csv"

# The two exports that spell a collector number differently from SV09, and the reason
# `number_index_key` exists. They are here to be the OTHER dialect, which is the only way
# the fold can be shown to work — and the Riftbound one is read a second time by
# `_check_game_partition`, as the other GAME.
WIDE_FIXTURE = "fixtures/pokemon_wide_export_untouched.csv"  # SM Cosmic Eclipse, unpadded
RIFTBOUND_FIXTURE = "fixtures/riftbound_export_untouched.csv"  # letter-suffixed variants

# The partition's own cases (D25). The Riftbound cell is quoted in full because it is not
# guessable from the game's name, which is half the argument for reading cells at all.
RIFTBOUND_LINE = "Riftbound League of Legends Trading Card Game"
RIFTBOUND_DEFY_SKU = "8925787"  # Defy 045/298, Origins, Near Mint, 3.52
RIFTBOUND_DEFY_NUMBER = "045/298"

# Required-case rows, by SKU, so a fixture re-export that moves them fails loudly here
# rather than quietly matching something else.
SECRET_RARE_SKU = "8608859"  # Articuno - 161/159, Near Mint Holofoil, 22.03
BLANK_NUMBER_SKU = "8665451"  # Code Card - Journey Together Booster Pack, no Number
BLANK_NUMBER_NAME = "Code Card - Journey Together Booster Pack"
AMPERSAND_NAME = "Billy & O'Nare"
AMPERSAND_NORMAL_SKU = "8608674"  # 142/159 Near Mint, 0.12
AMPERSAND_REVERSE_SKU = "8608679"  # 142/159 Near Mint Reverse Holofoil, 0.23
SEVEN_COPY_SKU = "8608459"  # Dunsparce 120/159 Near Mint, 2.06
# The same number's other condition row. 120/159 is stocked in both finishes, which is
# what makes it the number a set-valued claim can be asserted against at all: a claim of
# {normal, reverse_holo} has two rows to narrow to and something left for rung 3 to pick.
SEVEN_COPY_REVERSE_SKU = "8608464"  # Dunsparce 120/159 Near Mint Reverse Holofoil, 2.60
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


@contextmanager
def _isolated_home():
    """A whole store in a temporary directory, restored on the way out.

    The cases below read the live inventory through `cli/resolve.py`, which is the only path
    that turns a SKU's listing COUNTS into per-position `committed` flags. Restores the
    previous value rather than deleting the key: six other tests share this process.
    """
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


def _capture(copies):
    """`copies` bare capture records at box 3, carrying no identity at all."""
    with Store().write() as snapshot:
        for index in range(1, copies + 1):
            snapshot.inventory.record_capture(
                master.Card(
                    box=BOX, index=index, photo=f"captures/box{BOX}/{index:04d}.jpg"
                )
            )


def _stock(sku, condition, copies, *, pushed=0, staged=0, live=0, sold=()):
    """Record `copies` copies of one SKU at box 3, with the SKU's listing counts set.

    Exactly the shape `cli/cmd_emit.py` leaves behind — the IDENTITY on each card, the
    PROGRESS on the SKU — and written through the store rather than assembled as an
    `Inventory` literal, so `cli/resolve.py` reads it the way a real run does.
    """
    _capture(copies)
    with Store().write() as snapshot:
        for index in range(1, copies + 1):
            snapshot.inventory.set_state(
                master.position_key(BOX, index),
                master.IDENTIFIED,
                sku=sku,
                condition=condition,
            )
        for index in sold:
            snapshot.inventory.set_state(master.position_key(BOX, index), master.SOLD)
        entry = snapshot.inventory.listing(sku, condition=condition)
        entry.pushed, entry.staged, entry.live = pushed, staged, live


def _identifications(copies, name, number):
    """An `identifications.json` payload, shaped as `cli/cmd_identify.py` writes it."""
    return {
        "prompt_fingerprint": "t3",
        "cards": {
            master.position_key(BOX, index): {
                "photo": f"captures/box{BOX}/{index:04d}.jpg",
                "box": BOX,
                "index": index,
                "set_hint": None,
                "metadata_finish": "normal",
                "status": "ok",
                "identification": {
                    "name": name,
                    "number": number,
                    "printed_total": "159",
                    "confidence": "high",
                    "finish": "normal",
                },
            }
            for index in range(1, copies + 1)
        },
    }


def _export_file(path, export, live_quantity=None):
    """The committed fixture, optionally with one SKU's `Total Quantity` rewritten.

    That column is what D8 and D11 make authoritative and what `SkuMatch.live_before` reads,
    so a case about live quantity moves it here rather than anywhere the code could read it
    back from.
    """
    rows = [dict(row) for row in export.rows]
    if live_quantity is not None:
        for row in rows:
            if row[tcgcsv.SKU_COLUMN] == SEVEN_COPY_SKU:
                row[tcgcsv.LIVE_QUANTITY_COLUMN] = str(live_quantity)
    tcgcsv.write_csv(path, export.header, rows)
    return Path(path)


def _resolve_in(home, copies, export_path, *, name="Dunsparce", number="120"):
    """`cli/resolve.py:load` over `copies` positions, against the store this home holds."""
    run = runs.Run(directory=home, manifest={})
    run.write_identifications(_identifications(copies, name, number))
    return resolve.load(run, export_path)


def _command(c, *argv):
    """One `./pkmnscan` subcommand through the real dispatch. Returns what it printed."""
    from cli import __main__ as entry

    buffer = StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        code = entry.main(list(argv))
    text = buffer.getvalue()
    c.ok(code == 0, f"`pkmnscan {argv[0]}` exits 0", f"exit {code}\n{text}")
    return text


def _check_set_valued_claim(c, export) -> None:
    """D3 rung 1's SET, across the hop T3 owns: run record -> `cli/resolve.py` -> the ladder.

    THE ONE HOP NOTHING ELSE REACHES. T4 asserts the ladder against `variant.resolve`
    directly and T7 asserts the wire, the record and the sidecar — but the claim also
    travels `identifications.json`, which `cli/cmd_identify.py` writes and `cli/resolve.py`
    reads back into a FROZEN `IdentifiedCard`. Nothing proved a list crossed it, and the two
    ways it can fail there are both silent: a raw `record.get` puts a mutable list on a
    frozen dataclass, and a bare string iterated as a sequence becomes six one-letter
    "finishes" that `variant._check_claim` then raises `UnknownFinish` on.

    Both shapes travel the SAME RUN, deliberately, and take different rungs: the set falls
    through and lets detection choose within it, the bare string determines at rung 1. That
    pair is the amendment in one assertion — a set narrows, one member behaves exactly as
    this rung always has — and the bare string is the half that matters most, because every
    run record written before 2026-08-23 carries one and `join` and `emit` are free and
    deliberately re-runnable over old identification files.
    """
    with _isolated_home() as home:
        _capture(2)
        run = runs.create("t3-set-claim")
        payload = _identifications(2, "Dunsparce", "120")
        cards = payload["cards"]
        # Card 1: a SET, in the order the operator tapped rather than the enum's. Detection
        # reads `normal`, INSIDE the claim, so rung 3 chooses within what the claim left.
        cards[master.position_key(BOX, 1)]["metadata_finish"] = ["reverse_holo", "normal"]
        # Card 2: the BARE STRING every pre-amendment record carries, with detection
        # agreeing, so rung 1 determines exactly as it did before the amendment.
        cards[master.position_key(BOX, 2)]["metadata_finish"] = "reverse_holo"
        cards[master.position_key(BOX, 2)]["identification"]["finish"] = "reverse_holo"
        run.write_identifications(payload)
        resolved = resolve.load(run, _export_file(home / "export.csv", export))
        report = resolved.report

        c.equal(
            [q.destination.reason for q in report.queued],
            [],
            "neither card queues — a two-member claim NARROWS and the rungs below decide "
            "within what survives, which is the whole of the amendment",
        )
        matched = report.matches.get(SEVEN_COPY_SKU)
        if c.ok(matched is not None, "the set-claimed copy matches 120/159 Near Mint"):
            c.equal(
                matched.stages,
                [variant.DETECTION],
                "and it resolved at rung 3 — the set filtered the rows to the two it named "
                "and DETECTION picked between them. A reader that reduced the set to its "
                "first member would report `metadata` here, having determined on half of "
                "what the operator said, with no refusal and no review reason",
            )
        reverse = report.matches.get(SEVEN_COPY_REVERSE_SKU)
        if c.ok(reverse is not None, "and the bare-string copy matches the Reverse row"):
            c.equal(
                reverse.stages,
                [variant.METADATA],
                "at rung 1, DETERMINING — one member behaves exactly as this rung always "
                "has, which is the compatibility guarantee that makes the amendment "
                "additive rather than a rewrite of the ladder",
            )

    # THE QUEUE ENTRY, which is what the review screen reads. A set that reached the ladder
    # and then rendered as "no claim" on screen is the failure with no error attached:
    # `app/src/ReviewQueue.tsx` would ask the operator to judge a card while showing them a
    # claim they never made, or none at all.
    with _isolated_home() as home:
        _capture(1)
        run = runs.create("t3-set-claim-queue")
        payload = _identifications(1, "Articuno", "161")
        payload["cards"][master.position_key(BOX, 1)]["metadata_finish"] = [
            "normal",
            "reverse_holo",
        ]
        run.write_identifications(payload)
        resolved = resolve.load(run, _export_file(home / "export.csv", export))
        queued = resolved.report.queued
        if c.equal(
            [q.destination.reason for q in queued],
            ["metadata_not_stocked"],
            "a claim NONE of whose members 161/159 is stocked in reviews as "
            "metadata_not_stocked — the same fact as a single claim the number does not "
            "come in, which is why D3 gives it no reason code of its own",
        ):
            c.equal(
                queued[0].card.metadata_finish,
                ("normal", "reverse_holo"),
                "the claim reached `IdentifiedCard` with BOTH members and as a TUPLE — the "
                "carrier is frozen, and a list on it is a hashability bug waiting for its "
                "first `set()` (the reason `rarity_claim` beside it is one too)",
            )
            c.equal(
                resolve.queue_entry(queued[0]).read["metadata_finish"],
                ["normal", "reverse_holo"],
                "and the queue entry carries the whole claim as a JSON LIST — this is what "
                "`review.json` holds and the review screen renders, so a set silently shown "
                "as one member would put a claim nobody made in front of the operator",
            )


def _check_committed_from_counts(c, export) -> None:
    """`committed` derived from the SKU's listing COUNTS, which is where it lives now.

    D7 amended: `pushed`, `staged` and `live` are quantities on a `Listing` and no longer
    states a card wears, because copies of one SKU are fungible. `SkuMatch` is still
    per-position, so `cli/resolve.py:_committed_keys` is the one place a count becomes a set
    of addresses — and it is a COUNTING device, not an address: it picks that many unsold
    copies in box-walk order and the join does nothing with them but `len()` and a set
    subtraction.

    Three ways to get it wrong, one case each. Commit every copy whenever any count is
    non-zero, and a SKU never refills to the cap again. Count `live` alongside the other two,
    and every SKU that has ever been live under-lists by its live quantity forever. Let a
    sold copy back into the sellable set, and the import file offers a card that is in the
    post.
    """
    # --- the count picks that many copies, and no more --------------------------------
    with _isolated_home() as home:
        _stock(SEVEN_COPY_SKU, "Near Mint", 7, staged=2)
        resolved = _resolve_in(home, 7, _export_file(home / "export.csv", export))
        held = resolved.report.matches.get(SEVEN_COPY_SKU)
        if c.ok(held is not None, "seven copies with two staged still match their SKU"):
            c.equal(held.copies, 7, "and every physical copy is counted in the report")
            c.equal(
                len(held.committed_positions),
                2,
                "TWO of them are committed — the staged COUNT, resolved into that many "
                "positions and not into 'any non-zero count commits everything'",
            )
            c.equal(held.add_to_quantity, 2, "so there is room for two more under the cap")
            c.equal(held.backstock, 3, "and three stay backstock at known positions")
            c.equal(
                [p.index for p in held.live_positions],
                [3, 4],
                "and the copies offered are the ones the count did not already claim",
            )

    # --- `live` is subtracted once, by the export, and never again here ----------------
    with _isolated_home() as home:
        _stock(SEVEN_COPY_SKU, "Near Mint", 6, live=3)
        resolved = _resolve_in(
            home, 6, _export_file(home / "export.csv", export, live_quantity=3)
        )
        held = resolved.report.matches[SEVEN_COPY_SKU]
        c.equal(
            len(held.committed_positions),
            0,
            "`live` COMMITS NOTHING. `SkuMatch.add_to_quantity` already subtracts the "
            "export's Total Quantity, so counting the stored live number here would "
            "subtract the same copies twice",
        )
        c.equal(
            held.add_to_quantity,
            1,
            "three live against a cap of four leaves room for exactly one more — counting "
            "live twice would say zero and under-list this SKU forever",
        )
        c.equal(held.backstock, 5, "and the rest is backstock, not lost")

    # --- a sold copy is gone, whatever any count says ----------------------------------
    with _isolated_home() as home:
        _stock(SEVEN_COPY_SKU, "Near Mint", 7, sold=(3,))
        resolved = _resolve_in(home, 7, _export_file(home / "export.csv", export))
        held = resolved.report.matches[SEVEN_COPY_SKU]
        c.equal(
            [p.index for p in held.committed_positions],
            [3],
            "a SOLD copy is committed by its own state and not by any count — sold is "
            "per-copy and stays per-copy",
        )
        c.ok(
            3 not in [p.index for p in held.live_positions]
            and 3 not in [p.index for p in held.backstock_positions],
            "and it reaches neither the import file nor the backstock — the one thing a "
            "card that has left the building may never do",
            f"live: {[p.index for p in held.live_positions]}",
        )

    # --- the post-import re-emit, as counts --------------------------------------------
    # REGRESSION. The first real cycle (2026-08-22) ran join -> emit -> import -> reconcile
    # -> join -> emit and the second emit wrote every staged copy again: rows that would
    # have DOUBLED in Staged on import, and records walked backwards from `staged` to
    # `pushed`. Re-expressed against counts because that is where the fact lives now, and
    # because a count is the thing that can be double-ADDED where a state could only be
    # re-set.
    with _isolated_home():
        _capture(7)
        run = runs.create("t3-cycle")
        run.write_identifications(_identifications(7, "Dunsparce", "120"))
        export_path = _export_file(run.path("export.csv"), export)
        _command(c, "join", str(run.directory), "--export", str(export_path))

        first = resolve.load(runs.open_run(run.directory), export_path)
        seven = first.report.matches[SEVEN_COPY_SKU]
        c.equal(seven.add_to_quantity, 4, "the first join offers four copies, the live cap")
        c.equal(seven.backstock, 3, "and holds three as backstock")

        _command(c, "emit", str(run.directory))
        listing = Store().read().inventory.listing_for(SEVEN_COPY_SKU)
        c.equal(
            (listing.pushed, listing.staged, listing.live),
            (4, 0, 0),
            "and emit records those four as a COUNT against the SKU — `pushed` is a "
            "quantity now, not four cards each flagged at a position",
        )
        c.equal(
            tcgcsv.read_export(run.path(runs.IMPORT_LISTED)).by_sku()[SEVEN_COPY_SKU][
                tcgcsv.QUANTITY_COLUMN
            ],
            "4",
            "one row, Add to Quantity 4, three copies left in the box (D7)",
        )

        staged_path = _export_file(run.path("staged.csv"), export)
        rows = [
            dict(row, **{tcgcsv.QUANTITY_COLUMN: "4"})
            for row in tcgcsv.read_export(staged_path).rows
            if row[tcgcsv.SKU_COLUMN] == SEVEN_COPY_SKU
        ]
        tcgcsv.write_csv(staged_path, export.header, rows)
        _command(c, "reconcile", str(run.directory), str(staged_path))

        live_export = _export_file(run.path("live.csv"), export, live_quantity=4)
        _command(c, "join", str(run.directory), "--export", str(live_export))
        _command(c, "emit", str(run.directory))

        after = Store().read().inventory.listing_for(SEVEN_COPY_SKU)
        c.equal(
            len(tcgcsv.read_export(run.path(runs.IMPORT_LISTED)).rows),
            0,
            "THE SECOND EMIT WRITES NO SECOND ROW. Four copies are already live on "
            "TCGplayer and the cap is four, so there is nothing to add — importing this "
            "file again is what doubled them",
        )
        c.equal(
            (after.pushed, after.staged, after.live),
            (0, 0, 4),
            "and the counts walked forward only: pushed -> staged -> live, never back",
        )
        c.ok(
            after.pushed + after.staged + after.live <= LIVE_QUANTITY_CAP,
            "and the three stages together never exceed the cap across a full cycle — the "
            "sum is what TCGplayer would be holding, and D7 caps that at a playset",
            f"pushed {after.pushed} staged {after.staged} live {after.live}",
        )


def _check_answer_off_the_record(c, export) -> None:
    """D3 rung 0, read off the LIVE INVENTORY rather than handed in as a field.

    The block above this one drives rung 0 by setting `answered_sku` on an `IdentifiedCard`
    directly, which proves the ladder honours an answer and proves nothing about whether one
    ever arrives. `cli/resolve.py` is the seam that reads it back off the card record, and it
    is the seam that was missing on 2026-08-22: sixteen answered cards re-derived their
    disagreement on every join and re-parked forever, because the answer route wrote to a
    record nothing on the join path read.

    Re-fixtured for v2 rather than rewritten: the answer is `sku` + `condition` on the record
    and is deliberately NOT a state, a count or a stage, so nothing in the listing model can
    make it fall through.
    """
    with _isolated_home() as home:
        # The disagreement that parks a card: the toggle says normal, the photograph reads
        # reverse holo. 161/159 is holofoil-only, so without an answer this reviews.
        _stock(SECRET_RARE_SKU, "Near Mint Holofoil", 1)
        payload = _identifications(1, "Articuno", "161")
        payload["cards"][f"{BOX}/1"]["identification"]["finish"] = "reverse_holo"
        run = runs.Run(directory=home, manifest={})
        run.write_identifications(payload)
        resolved = resolve.load(run, _export_file(home / "export.csv", export))

        c.equal(len(resolved.report.queued), 0, "an ANSWERED card is not re-queued")
        if c.ok(SECRET_RARE_SKU in resolved.report.matches, "it matches the answered row"):
            c.equal(
                resolved.report.matches[SECRET_RARE_SKU].stages,
                ["human_answered"],
                "and the stage says a human decided it — read off the record, not inferred",
            )

        # FALL-THROUGH, both shapes, and neither is a guess. A SKU the export no longer
        # carries and a SKU it carries under a different Condition are the same failure from
        # two directions: the answer names one row exactly, and if that row is not there the
        # card walks the ladder as though nobody had answered.
        for label, sku, condition in (
            ("a SKU this export no longer carries", "0000000", "Near Mint Holofoil"),
            ("a SKU carried under a different Condition", SECRET_RARE_SKU, "Near Mint"),
        ):
            with Store().write() as snapshot:
                snapshot.inventory.set_state(
                    master.position_key(BOX, 1),
                    master.IDENTIFIED,
                    sku=sku,
                    condition=condition,
                )
            fell = resolve.load(run, _export_file(home / "export.csv", export))
            c.equal(
                [q.destination.reason for q in fell.report.queued],
                ["metadata_not_stocked"],
                f"an answer naming {label} falls through to the ladder, never a guess",
            )


def _two_game_payload():
    """One pokemon card and one riftbound card, as `cli/cmd_identify.py` would record
    them: the game claim on each run record, per card and never per run (D21)."""
    return {
        "prompt_fingerprint": "t3-partition",
        "cards": {
            master.position_key(BOX, 1): {
                "photo": f"captures/box{BOX}/0001.jpg",
                "box": BOX, "index": 1, "set_hint": None,
                "metadata_finish": "normal", "status": "ok",
                "game": "pokemon",
                "identification": {
                    "name": "Dunsparce", "number": "120", "printed_total": "159",
                    "confidence": "high", "finish": "normal",
                },
            },
            master.position_key(BOX, 2): {
                "photo": f"captures/box{BOX}/0002.jpg",
                "box": BOX, "index": 2, "set_hint": "Origins",
                "metadata_finish": "normal", "status": "ok",
                "game": "riftbound",
                "identification": {
                    "name": "Defy", "number": RIFTBOUND_DEFY_NUMBER,
                    "printed_total": None, "confidence": "high", "finish": "normal",
                },
            },
        },
    }


def _check_game_partition(c, export) -> None:
    """D25 — the join partitions by game, and `Product Line` is a real reader.

    THE DEFECT THIS GUARDS AGAINST WAS MEASURED, NOT IMAGINED. `Product Line` sat in
    `CANONICAL_HEADER` read by nothing, so two exports concatenated would have cross-joined
    in silence — a Riftbound number matching a Pokemon row with nothing in a position to
    notice. Blind is not agnostic. The cases here hold the four rules that close it: the
    file->game mapping comes off each file's own cells and never its filename; catalogs are
    built per game and never merged; a run refuses BEFORE any catalog is built when the
    mapping cannot be exactly one file per game; and `emit` writes one import file per
    game, because nothing has established Import to Staged accepts a mixed one.
    """
    riftbound = tcgcsv.read_export(REPO_ROOT / RIFTBOUND_FIXTURE)

    # --- the reader reads cells ---------------------------------------------------
    c.equal(
        tcgcsv.product_lines(export),
        ("Pokemon",),
        "SV09's Product Line cells say Pokemon and nothing else",
    )
    c.equal(
        tcgcsv.product_lines(riftbound),
        (RIFTBOUND_LINE,),
        "and the Riftbound export carries its own line, verbatim, in every row — a "
        "string nobody would guess from a filename",
    )

    # --- the partition pair, and pokemon keeping its Code Card rows ----------------
    code_rows = [r for r in export.rows if r[tcgcsv.RARITY_COLUMN] == "Code Card"]
    c.ok(code_rows, "the fixture really does hold Code Card rows to keep")
    pokemon_catalog = join.Catalog.from_export(export, "pokemon")
    c.equal(
        len(pokemon_catalog.export.rows),
        len(export.rows),
        "`pokemon` claims the whole Pokemon line — the Code Card rows INCLUDED, because "
        "the entry sets no product_line_rarities and narrowing it to its claimed "
        "rarities would drop the blank-Number rows the name fallback resolves",
    )
    c.equal(pokemon_catalog.dropped_rows, 0, "and the drop count reports zero")
    c.equal(
        [
            r[tcgcsv.SKU_COLUMN]
            for r in pokemon_catalog.rows_for_blank_number_name(BLANK_NUMBER_NAME)
        ],
        [BLANK_NUMBER_SKU],
        "so the blank-Number case still resolves by name under the partition",
    )
    code_catalog = join.Catalog.from_export(export, "pokemon_code")
    c.equal(
        sorted(r[tcgcsv.SKU_COLUMN] for r in code_catalog.export.rows),
        sorted(r[tcgcsv.SKU_COLUMN] for r in code_rows),
        "`pokemon_code` narrows the SAME file to exactly its Code Card rows — the pair "
        "(Product Line, Rarity) is the partition key, and the line alone could not "
        "split the two games that share it",
    )
    c.equal(
        code_catalog.dropped_rows,
        len(export.rows) - len(code_rows),
        "and its drop count is the rest of the file",
    )

    # --- a single-game join through the partition is the join it always was --------
    direct = join.join_batch(
        _clean_batch(), join.Catalog(export), live_cap=LIVE_QUANTITY_CAP
    )
    partitioned = join.join_batch(
        _clean_batch(), pokemon_catalog, live_cap=LIVE_QUANTITY_CAP
    )
    c.equal(
        [
            (m.sku, m.copies, m.add_to_quantity, str(m.list_price))
            for m in partitioned.matches.values()
        ],
        [
            (m.sku, m.copies, m.add_to_quantity, str(m.list_price))
            for m in direct.matches.values()
        ],
        "an all-Pokemon batch joins identically through the filtered catalog: same "
        "SKUs, same order, same quantities, same prices — the compatibility half of "
        "the partition",
    )

    # --- zero rows is the wrong file, and it refuses -------------------------------
    caught = c.raises(
        join.EmptyCatalog,
        lambda: join.Catalog.from_export(export, "riftbound"),
        "an SV09 export handed to the riftbound game refuses: zero rows after the "
        "filter means the wrong file, the one case where stopping beats continuing",
    )
    if caught is not None:
        c.ok(
            "'Pokemon'" in str(caught),
            "and the refusal names the file's own Product Line cells",
            str(caught),
        )

    # --- file -> game off the cells, never the filename ----------------------------
    with _isolated_home() as home:
        _capture(2)
        run_dir = runs.create("t3-partition")
        run_dir.write_identifications(_two_game_payload())
        sv09_path = _export_file(home / "export.csv", export)
        # The Riftbound catalogue under the most Pokemon-shaped name available.
        misleading = home / "sv09_export_pokemon.csv"
        misleading.write_bytes((REPO_ROOT / RIFTBOUND_FIXTURE).read_bytes())

        plan = resolve.exports_for(run_dir, [str(sv09_path), str(misleading)])
        c.equal(
            {game: path.name for game, path in plan.by_game.items()},
            {"pokemon": "export.csv", "riftbound": "sv09_export_pokemon.csv"},
            "the file->game mapping reads each file's Product Line cells: a Riftbound "
            "export named like a Pokemon one still answers for riftbound",
        )

        # REFUSAL: a game present in the run with no export.
        caught = c.raises(
            runs.RunError,
            lambda: resolve.exports_for(run_dir, [str(sv09_path)]),
            "a run holding a riftbound card refuses to join on a pokemon export alone",
        )
        if caught is not None:
            message = str(caught)
            c.ok(
                "Box 3 · Section 1 · Card 2" in message,
                "the refusal names the card's position",
                message,
            )
            c.ok(
                "PUT /inventory/" in message,
                "and points at the correction route for a wrong game claim",
                message,
            )

        # REFUSAL: two files claiming one game.
        second = home / "second.csv"
        second.write_bytes(Path(sv09_path).read_bytes())
        caught = c.raises(
            runs.RunError,
            lambda: resolve.exports_for(
                run_dir, [str(sv09_path), str(second), str(misleading)]
            ),
            "two files carrying the Pokemon line refuse — no rule may pick between two "
            "catalogs for one card",
        )
        if caught is not None:
            c.ok(
                str(sv09_path) in str(caught) and str(second) in str(caught),
                "and both files are named",
                str(caught),
            )

        # REFUSAL: a file whose cells match no registered game rides along with the
        # others — accepted and silently unused is the same shape as silently dropped.
        alien = home / "alien.csv"
        tcgcsv.write_csv(
            alien,
            export.header,
            [
                dict(r, **{tcgcsv.PRODUCT_LINE_COLUMN: "Magic The Gathering"})
                for r in export.rows[:3]
            ],
        )
        c.raises(
            runs.RunError,
            lambda: resolve.exports_for(
                run_dir, [str(sv09_path), str(alien), str(misleading)]
            ),
            "a file matching no registered game refuses rather than being ignored",
        )

        # Every refusal above ran before any catalog was built: nothing queued,
        # nothing written.
        c.equal(
            Store().read().queue_summary,
            "0 cards in review | 0 cards in parked",
            "the refusals touched no queue",
        )
        c.ok(
            not run_dir.path(runs.REPORT).is_file()
            and not run_dir.path(runs.IMPORT_LISTED).is_file(),
            "and wrote nothing into the run directory",
        )

        # --- the two-game round trip through the real commands ---------------------
        said = _command(
            c, "join", str(run_dir.directory),
            "--export", str(sv09_path), "--export", str(misleading),
        )
        c.ok(
            "[pokemon]" in said and "[riftbound]" in said,
            "the run report is per game",
            said,
        )

        resolved = resolve.load(runs.open_run(run_dir.directory), plan.by_game)
        c.equal(
            list(resolved.joins),
            ["pokemon", "riftbound"],
            "one catalog and one report per game, in registry order, never merged",
        )
        c.equal(
            list(resolved.joins["pokemon"].report.matches),
            [SEVEN_COPY_SKU],
            "the pokemon card matched in the pokemon catalog",
        )
        c.equal(
            list(resolved.joins["riftbound"].report.matches),
            [RIFTBOUND_DEFY_SKU],
            "and the riftbound card in the riftbound catalog — never each other's",
        )

        _command(c, "emit", str(run_dir.directory))
        listed = tcgcsv.read_export(run_dir.path(runs.IMPORT_LISTED))
        riftbound_listed = tcgcsv.read_export(
            run_dir.path(runs.import_listed_name("riftbound"))
        )
        c.equal(
            [r[tcgcsv.SKU_COLUMN] for r in listed.rows],
            [SEVEN_COPY_SKU],
            "one import file per game: the un-suffixed file holds the pokemon row alone",
        )
        c.equal(
            [r[tcgcsv.SKU_COLUMN] for r in riftbound_listed.rows],
            [RIFTBOUND_DEFY_SKU],
            "and import-listed-riftbound.csv its own row alone",
        )
        c.equal(
            (
                {r[tcgcsv.PRODUCT_LINE_COLUMN] for r in listed.rows},
                {r[tcgcsv.PRODUCT_LINE_COLUMN] for r in riftbound_listed.rows},
            ),
            ({"Pokemon"}, {RIFTBOUND_LINE}),
            "no import file spans two Product Lines — the accepted fixture proves the "
            "format for one line only",
        )

    # --- the manifest: exports keyed by game, the old scalar backfilled on read -----
    old = runs.Run(directory=Path("unused"), manifest={"export": {"path": "sv09.csv"}})
    c.equal(
        old.exports_by_game,
        {"pokemon": Path("sv09.csv")},
        "an old scalar manifest reads as the default game's file — backfilled at the read",
    )
    c.equal(
        old.manifest,
        {"export": {"path": "sv09.csv"}},
        "and the read rewrote nothing: the backfill is read-side only",
    )
    recorded = runs.Run(
        directory=Path("unused"),
        manifest={"exports": {"riftbound": {"path": "r.csv"}}},
    )
    c.equal(
        recorded.exports_by_game,
        {"riftbound": Path("r.csv")},
        "the recorded shape is a dict keyed by game",
    )


def _check_number_fold(c, sv09: join.Catalog) -> None:
    """`number_index_key` — the fold both sides of the number comparison now pass through.

    THE SILENT ZERO-JOIN. `Catalog.__init__` indexed the export's `Number` cell VERBATIM
    while `join_key` composed a `zfill(3)`-padded key, so the two agreed only for exports
    whose cells happen to be three wide. SV09 is one of those, which is why every case above
    this one passed for months against a join that could not read half the exports in
    `fixtures/`. The failure had the worst shape a join failure can take: every affected card
    came back `no_catalog_row`, which is the report pointing at the EXPORT rather than at the
    key, so the remedy it suggests is to go and get a different CSV.

    THE MEASUREMENT IS THE ASSERTION, so the case cannot be satisfied by a lookup that
    happens to work. `fixtures/pokemon_wide_export_untouched.csv` carries SM Cosmic Eclipse
    with unpadded cells, and the number below is how many of its rows the old index put out
    of reach.

    THREE DIRECTIONS, BECAUSE A FOLD IS AS EASY TO OVER-APPLY AS TO OMIT. It has to reach the
    unpadded export; it has to leave a secret rare exactly where it was, since `161/159`
    already agreed on both sides and a fold that damaged it would trade one silent miss for
    another; and it must not collapse two cards that a letter suffix distinguishes, which is
    the case that rules out the tempting fix of padding the index to match `join_key`.
    """
    c.equal(
        [
            join.number_index_key("001/236"),
            join.number_index_key("1/236"),
            join.number_index_key("161/159"),
            join.number_index_key("066a/298"),
        ],
        ["1/236", "1/236", "161/159", "66A/298"],
        "number_index_key strips leading zeros from every digit run and folds case: two "
        "spellings of one card land together, a secret rare is untouched, a suffix survives",
    )
    c.equal(
        [join.number_index_key("EB01-009"), join.number_index_key("TG01/TG30")],
        ["EB1-9", "TG1/TG30"],
        "and it decorates nothing but the digits — a prefix or a hyphen is identity, not "
        "padding, so both sides of a One Piece or a Trainer Gallery number keep their shape",
    )

    # --- an unpadded export joins ---------------------------------------------------
    wide = tcgcsv.read_export(REPO_ROOT / WIDE_FIXTURE)
    wide_catalog = join.Catalog(wide)
    composed = join.join_key("1", "236")

    c.equal(composed, "001/236", "the composed key is padded, as CLAUDE.md documents it")
    c.ok(
        not any(row[tcgcsv.NUMBER_COLUMN].strip() == composed for row in wide.rows),
        "and that string appears in NO `Number` cell of the unpadded export — which is "
        "exactly why a verbatim index found nothing and blamed the file",
    )
    c.equal(
        len(wide_catalog.rows_for_key(composed)),
        5,
        "the fold finds the card anyway: five condition rows for 1/236, reached by a key "
        "spelled 001/236",
    )

    unpadded_rows = [
        row
        for row in wide.rows
        if (cell := row[tcgcsv.NUMBER_COLUMN].strip())
        and cell.split("/")[0].isdigit()
        and len(cell.split("/")[0]) < 3
    ]
    c.equal(
        len(unpadded_rows),
        950,
        "950 rows in this export carry an unpadded cell — the size of the silent miss, "
        "counted rather than described",
    )

    # END TO END, not just through the accessor. Two cards from that export, one of each
    # finish the catalog stocks for them, joined the way a run joins: a lookup that works
    # while `join_batch` still composes its key somewhere else would be a half-fix.
    joined = join.join_batch(
        [
            _card(1, "Venusaur & Snivy GX", "1", total="236", metadata="holo"),
            _card(2, "Alolan Vulpix", "39", total="236", metadata="normal"),
        ],
        wide_catalog,
        router=join.default_router(),
    )
    c.equal(
        sorted(joined.matches),
        ["4230084", "4256285"],
        "and a batch of unpadded cards resolves through join_batch to its own rows",
    )
    c.equal(
        [q.destination.reason for q in joined.queued],
        [],
        "with nothing queued as no_catalog_row — the reason code that used to be the only "
        "symptom",
    )

    # --- the padded export is undamaged ---------------------------------------------
    secret = sv09.rows_for_key(join.join_key("161", "159"))
    c.equal(
        [row[tcgcsv.SKU_COLUMN] for row in secret],
        [SECRET_RARE_SKU],
        "SV09's secret rare 161/159 still reaches exactly one row: the fold changed a "
        "spelling that was already three wide by not touching it",
    )

    # --- a letter suffix is a different card ----------------------------------------
    # THE CASE THAT DECIDED THE IMPLEMENTATION. Padding the index instead of folding both
    # sides is the shorter fix and it is wrong here: `066a` is already three wide before its
    # suffix, so `zfill(3)` is a no-op on it while `66a` from another export is not, and the
    # two dialects drift apart again. Stripping the run and keeping the suffix keeps them
    # apart on purpose.
    riftbound = join.Catalog(tcgcsv.read_export(REPO_ROOT / RIFTBOUND_FIXTURE))
    alternate = riftbound.rows_for_key("066a/298")
    plain = riftbound.rows_for_key("066/298")
    c.equal(
        sorted({row[tcgcsv.NAME_COLUMN] for row in alternate}),
        ["Ahri, Alluring (Alternate Art)"],
        "Riftbound's 066a/298 is Ahri, Alluring (Alternate Art) and nothing else",
    )
    c.ok(
        "Ahri, Alluring" in {row[tcgcsv.NAME_COLUMN] for row in plain},
        "066/298 is the plain Ahri, Alluring",
    )
    c.ok(
        {row[tcgcsv.SKU_COLUMN] for row in alternate}.isdisjoint(
            row[tcgcsv.SKU_COLUMN] for row in plain
        ),
        "and the two keys share NOT ONE SKU — a suffixed number is a different card, and a "
        "fold that merged them would mis-list an $8.89 showcase as a $1.18 rare",
    )


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

    _check_number_fold(c, catalog)

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

    # Both blocks above hand `committed` and `answered_sku` to `join_batch` as fields, which
    # proves the ladder honours them and proves nothing about whether one ever arrives. The
    # two sections below drive the same two rules through `cli/resolve.py` against a real
    # store, which is the seam where a count becomes a `committed` flag and where a human's
    # answer is read back off the card record.
    _check_set_valued_claim(c, export)
    _check_committed_from_counts(c, export)
    _check_answer_off_the_record(c, export)
    _check_game_partition(c, export)

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

    # --- D35: the number could not be read, so the name found the row ------------------
    #
    # `Accelgor` is a real SV09 row whose name maps to exactly one collector number — 133 of
    # the fixture's 157 names do, which is why a name is a usable last resort at all.
    REAL_NAME, REAL_NUMBER, REAL_TOTAL = "Accelgor", "013", "159"

    #
    # THE RUNG BELOW THE BLANK-NUMBER FALLBACK. The Pokemon lookup used to
    # treat "this card has no number" as "this PRODUCT prints no number" and look only at the
    # export's blank-`Number` rows — true for a code card, false for a photograph whose bottom
    # edge was cropped off. Box 2 sent 544 cards through a bad crop: 37 came back with no
    # number and 9 with a National Pokedex number read off the artwork strip, and 46 of the 47
    # queued as `no_catalog_row` against an export that held their row the whole time.
    #
    # Every case below was observed FAILING before it was kept.
    name_rows = catalog.rows_for_name(REAL_NAME)
    c.ok(len(name_rows) > 0, "D35: the name index finds a NUMBERED row by its name")
    c.equal(
        catalog.rows_for_blank_number_name(REAL_NAME),
        [],
        "D35: and the blank-number fallback above it finds nothing for that same name — "
        "the two indexes are disjoint, which is what keeps a card and a code card apart",
    )

    # 1. A blank number resolves by name, and says so in the lookup string.
    blank = catalog.candidates(_card(801, REAL_NAME, number=None))
    c.ok(blank.name_inferred, "D35: a card with no number is name-inferred")
    c.ok(blank.lookup.startswith("name?:"), "D35: and the lookup says `name?:`, not `name:`")
    c.ok(len(blank.rows) > 0, "D35: and it found rows")

    # 2. A WRONG number falls through. This is the half that nearly shipped missing: four of
    #    box 2's misreads carried a denominator too, so they composed a well-formed key that
    #    matched nothing and stopped there.
    wrong = catalog.candidates(_card(802, REAL_NAME, number="0342", total="132"))
    c.ok(
        wrong.name_inferred,
        "D35: a number that matches NO row falls through to the name rung",
    )
    c.equal(
        {r[tcgcsv.SKU_COLUMN] for r in wrong.rows},
        {r[tcgcsv.SKU_COLUMN] for r in name_rows},
        "D35: and finds the same rows the name index holds",
    )

    # 3. A number that DOES match is never second-guessed.
    good = catalog.candidates(_card(803, REAL_NAME, number=REAL_NUMBER, total=REAL_TOTAL))
    c.ok(not good.name_inferred, "D35: a number that matches is used, and the name rung is not reached")
    c.ok(good.lookup.startswith("number:"), "D35: and the lookup still says `number:`")

    # 4. A name that matches nothing is still `no_catalog_row` — the rung adds no guessing.
    missing = catalog.candidates(_card(804, "Not A Real Card At All", number=None))
    c.equal(len(missing.rows), 0, "D35: an unknown name finds nothing and stays unmatched")

    # 5. It ROUTES TO REVIEW rather than listing, which is the owner's ruling and the half
    #    that cannot be inferred from the lookup alone.
    named = join.join_batch(
        [_card(805, REAL_NAME, number=None, metadata=("normal",))],
        catalog,
        router=join.default_router(),
        live_cap=LIVE_QUANTITY_CAP,
    )
    queued = named.queue(routing.MAIN) + named.queue(routing.PARKED)
    c.equal(len(queued), 1, "D35: a name-resolved card is QUEUED, never listed on the name alone")
    c.equal(
        queued[0].resolution_reason,
        routing.NUMBER_UNREAD_NAME_MATCHED,
        "D35: under its own reason code",
    )
    c.equal(
        len(queued[0].candidates),
        1,
        "D35: offering exactly ONE candidate — the row the ladder chose — which is what "
        "makes a queue of these answerable as one D29 group",
    )

    # 6. The name fold, on both sides. `Product Name` embeds the number inconsistently, and
    #    matching raw scored 35 of box 2's 46 against 45 through the fold.
    c.equal(join.name_index_key("Delibird - 105/132"), "DELIBIRD", "D35: the embedded number folds away")
    c.equal(join.name_index_key("Nickit"), "NICKIT", "D35: and a bare name is unchanged")
    c.equal(join.name_index_key("Ho-Oh"), "HO-OH", "D35: an interior hyphen is not a suffix")
    c.equal(
        join.name_index_key("Wally's Compassion - 132/132"),
        "WALLY'S COMPASSION",
        "D35: an apostrophe survives the fold",
    )

    # 7. D3 RUNG 0 OUTRANKS THIS RUNG, AND THE CASE IS HERE BECAUSE IT DID NOT.
    #
    #    The block in `join_batch` fired on `name_inferred and not needs_review and row`, and
    #    a human's answer satisfies all three — `variant.answered` returns a resolution
    #    carrying the chosen row at stage `HUMAN_ANSWERED`. So the answer was overwritten back
    #    into `number_unread_name_matched` on the very next join.
    #
    #    What made it a SILENT DROP rather than a re-ask: `store/queues.py:upsert` refuses to
    #    re-queue a position a human has cleared, so the card was pushed out of listing and
    #    then refused re-entry to the queue. Not listed, not queued. That is the failure D3
    #    rung 0 exists to prevent (Gate B: sixteen answered cards re-deriving their
    #    disagreement forever) and the one `CLAUDE.md` names as never dropping a card.
    #
    #    Observed failing before the `stage != HUMAN_ANSWERED` clause was added: this asserted
    #    REVIEW/`number_unread_name_matched` and zero listed rows.
    answered_row = catalog.rows_for_name(REAL_NAME)[0]
    answered = join.join_batch(
        [
            join.IdentifiedCard(
                position=join.Position(box=BOX, index=806),
                name=REAL_NAME,
                number=None,
                printed_total=None,
                metadata_finish=("normal",),
                photo=f"captures/box{BOX}/0806.jpg",
                confidence="high",
                answered_sku=answered_row[tcgcsv.SKU_COLUMN],
                answered_condition=answered_row[tcgcsv.CONDITION_COLUMN],
            )
        ],
        catalog,
        router=join.default_router(),
        live_cap=LIVE_QUANTITY_CAP,
    )
    c.equal(
        len(answered.queue(routing.MAIN) + answered.queue(routing.PARKED)),
        0,
        "D35/D3 rung 0: a card the human already answered is NOT re-queued by the name rung",
    )
    c.ok(
        answered_row[tcgcsv.SKU_COLUMN] in answered.matches,
        "D35/D3 rung 0: it is listed on the answer, because an answer outlives the question",
    )

    # 8. D35 REACHES THE `printed_code` GAMES TOO, AND FOR ONE COMMIT IT DID NOT.
    #
    #    Every case above exercises the Pokemon key — `number_and_printed_total`. D35 is
    #    written as a rule about a READ, not about a game ("a number that finds nothing is a
    #    number we should stop believing"), but it was only ever wired into that one strategy.
    #    the printed-code lookup returned `rows_for_key` even when EMPTY, so Riftbound and One
    #    Piece stopped at zero candidates where Pokemon fell through to the name.
    #
    #    THE COST IS NOT AN EXTRA TAP, IT IS AN UNANSWERABLE CARD.
    #    `POST /review/<box>/<index>/answer` refuses an entry with no candidates as
    #    `no_candidates`, so those cards could only be skipped — forever, every session.
    #
    #    Measured on run 2026-08-29-box1-01, 133 real Riftbound cards: 4 unusable reads, all 4
    #    zero-candidate `no_catalog_row`. Three carried a set-code prefix the prompt forbids in
    #    as many words — `UNL • 140/219` for `140/219` — and all three hold exactly one row by
    #    name. One of them, Hwei at $2.86, is above D9's threshold: a listable card stuck
    #    unanswerable. The fourth read `Wuju Master` for `Master Yi, Wuju Master` and is
    #    correctly still unmatched, because the name it gave is not the name the export has.
    #
    #    Observed failing before the fall-through was added: `rift_prefixed` returned 0 rows
    #    with `name_inferred` False.
    rift_catalog = join.Catalog.from_export(
        tcgcsv.read_export(REPO_ROOT / RIFTBOUND_FIXTURE), "riftbound"
    )
    RIFT_NAME, RIFT_NUMBER = "Adaptatron", "056/298"

    def _rift(index, name, number):
        return join.IdentifiedCard(
            position=join.Position(box=BOX, index=index),
            name=name,
            number=number,
            printed_total=None,  # this game prints no denominator — D25
            photo=f"captures/box{BOX}/{index:04d}.jpg",
            confidence="high",
            game="riftbound",
        )

    by_name = rift_catalog.rows_for_name(RIFT_NAME)
    c.ok(len(by_name) > 0, "D35/printed_code: the name index holds this game's rows too")

    # THE LIVE SHAPE, AND IT IS RECOVERED BY THE NUMBER RATHER THAN THE NAME. A set code glued
    # to the identifier is noise the model added on top of digits it read correctly, so the
    # honest repair is to strip the noise — an exact join on the field that tells one card from
    # another — not to fall back to the name, which is a weaker signal that only ever queues.
    # `_strip_set_code` is licensed by a measurement: no export cell anywhere carries a bullet
    # or a middle dot.
    rift_prefixed = rift_catalog.candidates(_rift(810, RIFT_NAME, "UNL \u2022 " + RIFT_NUMBER))
    c.ok(
        not rift_prefixed.name_inferred,
        "set code: a prefixed identifier is recovered by NUMBER, not rescued by name",
    )
    c.ok(
        rift_prefixed.lookup.startswith("code:"),
        "set code: and the lookup says `code:`, because that is what it matched on",
    )
    c.equal(
        {r[tcgcsv.NUMBER_COLUMN] for r in rift_prefixed.rows},
        {RIFT_NUMBER},
        "set code: and it lands on the exact row the bare identifier would have",
    )

    # THE NAME RUNG IS STILL REACHED, by a code that is well-formed and simply wrong — which is
    # the case D35 exists for and which no strip can repair. Kept alongside the case above so a
    # future change cannot quietly delete the rung by making every bad code recoverable.
    rift_unread = rift_catalog.candidates(_rift(813, RIFT_NAME, "999/219"))
    c.ok(
        rift_unread.name_inferred,
        "D35/printed_code: a code that matches NO row still falls through to the name rung",
    )
    c.ok(
        rift_unread.lookup.startswith("name?:"),
        "D35/printed_code: and says `name?:`, so the report can tell it from a blank-number row",
    )
    c.equal(
        {r[tcgcsv.SKU_COLUMN] for r in rift_unread.rows},
        {r[tcgcsv.SKU_COLUMN] for r in by_name},
        "D35/printed_code: and finds the rows the export held the whole time",
    )

    # A code that DOES match is never second-guessed — the rung is a last resort, not a peer.
    rift_good = rift_catalog.candidates(_rift(811, RIFT_NAME, RIFT_NUMBER))
    c.ok(
        not rift_good.name_inferred,
        "D35/printed_code: a code that matches is used, and the name rung is not reached",
    )
    c.ok(
        rift_good.lookup.startswith("code:"),
        "D35/printed_code: and the lookup still says `code:`",
    )

    # An unknown name adds no guessing here either.
    rift_missing = rift_catalog.candidates(_rift(812, "Not A Real Riftbound Card", "ZZZ/999"))
    c.equal(
        len(rift_missing.rows),
        0,
        "D35/printed_code: an unknown name finds nothing and stays unmatched",
    )

    return c.result()
