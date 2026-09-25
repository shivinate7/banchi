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

import hashlib
import os
import time
import tempfile
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from decimal import Decimal
from io import StringIO
from pathlib import Path

from harness.tests import Checks, Result
from cli import resolve, runs
from pipeline import games, join, pricing, routing, tcgcsv, variant
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
ONEPIECE_FIXTURE = "fixtures/onepiece_export_untouched.csv"  # `P-044`: a ONE-letter prefix

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
# A second set sharing the FIRST's colon side, which is the shape that broke the pairwise
# `set_matches`. The pairing is invented — the committed fixture is single-set and a
# collision cannot be produced from it — but the shape is not: four live Pokemon sets are
# `SV: Prismatic Evolutions`, `SV: Paldean Fates`, `SV: Scarlet & Violet 151` and
# `SV: Shrouded Fable`, and `SV` names every one of them.
SHARED_SIDE_SET = "SV09: Paldean Fates"
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


def _multi_set_catalog(export, second_set=SECOND_SET):
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
                    tcgcsv.SET_COLUMN: second_set,
                    tcgcsv.NAME_COLUMN: "Pikachu",
                    tcgcsv.MARKET_PRICE_COLUMN: "5.00",
                },
            )
        )
    return join.Catalog(tcgcsv.Export(header=export.header, rows=tuple(rows)))


# D253's qualifier fix (the review's second CRITICAL finding). The
# committed fixture carries no parenthetical-qualifier name — no `(Alternate Art)`, no
# `(Overnumbered)` — to test the real shape against, so this clones ONE synthetic
# printing under a different number and a different rarity, the same approach and the
# same reason as `_multi_set_catalog` above.
QUALIFIER_BASE_SKU = "8607894"  # Banette 060/159, Near Mint, Uncommon
QUALIFIER_ALT_NAME = "Banette (Alternate Art)"
QUALIFIER_ALT_NUMBER = "060a/159"
QUALIFIER_ALT_SKU = "9100201"


def _qualifier_catalog(export):
    """SYNTHETIC: the SV09 export plus one alt-art clone of Banette, folding to the
    SAME name as the base print once the trailing qualifier is stripped — the shape
    `Pyke, Returned` / `Pyke, Returned (Alternate Art)` measured on the owner's store."""
    rows = list(export.rows)
    base = next(row for row in export.rows if row[tcgcsv.SKU_COLUMN] == QUALIFIER_BASE_SKU)
    rows.append(
        dict(
            base,
            **{
                tcgcsv.SKU_COLUMN: QUALIFIER_ALT_SKU,
                tcgcsv.NAME_COLUMN: QUALIFIER_ALT_NAME,
                tcgcsv.NUMBER_COLUMN: QUALIFIER_ALT_NUMBER,
                tcgcsv.RARITY_COLUMN: "Showcase",
                tcgcsv.MARKET_PRICE_COLUMN: "3.00",
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


def _capture_at(box, copies):
    """`copies` bare capture records in `box`, carrying no identity at all.

    CALLED DIRECTLY, THE POINT IS THAT THE COPIES ARE UNSTAMPED. `cli/cmd_emit.py` writes a
    SKU onto `match.live_positions` and onto nothing else, so copies that have never been
    emitted are invisible to `Inventory.positions_for_sku` — which is the ordinary state of
    the box a second run is pointed at, and what makes `committed_positions` zero there
    however the SKU's counts are read.

    EVERY CARD IS NAMED, AND THE NAME IS SHA256 OF `<box>/<index>` (D172). A test's card has
    no photograph, so it has no digest to be named by — and `record_capture` refuses a
    nameless row, because the one caller that cannot supply a name is a caller that forgot.
    The seed carries the BOX as well as the index because `_stock_at` deliberately splits one
    SKU's copies across two drawers of one store, and two cards sharing a name is what
    `cards_cid` refuses. It is a real digest rather than a padded constant so that the UNIQUE
    index is actually exercised: N cards from N seeds collide under a constant and do not
    collide here. Deterministic, so a re-record at the same key carries the same name.
    """
    with Store().write() as snapshot:
        for index in range(1, copies + 1):
            snapshot.inventory.record_capture(
                master.Card(
                    box=box,
                    index=index,
                    photo=f"captures/box{box}/{index:04d}.jpg",
                    cid=hashlib.sha256(f"{box}/{index}".encode()).hexdigest(),
                )
            )


def _capture(copies):
    """`_capture_at` at box 3, which is where every single-box case in this file lives."""
    _capture_at(BOX, copies)


def _stock_at(box, sku, condition, copies, *, pushed=0, staged=0, live=0, sold=()):
    """Record `copies` copies of one SKU in `box`, with the SKU's listing counts set.

    Exactly the shape `cli/cmd_emit.py` leaves behind — the IDENTITY on each card, the
    PROGRESS on the SKU — and written through the store rather than assembled as an
    `Inventory` literal, so `cli/resolve.py` reads it the way a real run does.

    THE BOX IS A PARAMETER BECAUSE THE CAP IS NOT PER BOX (D7, D59). A playset is what
    TCGplayer may hold of one SKU, and TCGplayer has never heard of a box — so the case
    that tells a per-SKU cap from a per-run one needs a SKU whose copies are split across
    two, one of which the run under test never looks at.
    """
    _capture_at(box, copies)
    with Store().write() as snapshot:
        for index in range(1, copies + 1):
            snapshot.inventory.set_state(
                master.position_key(box, index),
                master.IDENTIFIED,
                sku=sku,
                condition=condition,
            )
        for index in sold:
            snapshot.inventory.set_state(master.position_key(box, index), master.SOLD)
        entry = snapshot.inventory.listing(sku, condition=condition)
        entry.pushed, entry.staged = pushed, staged
        # `set`, not assignment: a store holding a live count has READ it somewhen, and the
        # reading is dated now (D87 amended) — the shape a sale leaves. Every export a case
        # writes after this is newer by the file's own mtime, so the export still answers
        # wherever it used to; the one case about the ORDER dates its file with `os.utime`.
        entry.set(master.LIVE, live)


def _stock(sku, condition, copies, **counts):
    """`_stock_at` at box 3 — the box `_identifications` and `_resolve_in` speak."""
    _stock_at(BOX, sku, condition, copies, **counts)


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


def _resolve_in(
    home, copies, export_path, *, name="Dunsparce", number="120", live_cap=LIVE_QUANTITY_CAP
):
    """`cli/resolve.py:load` over `copies` positions, against the store this home holds.

    IT ASKS FOR A CAP OF FOUR BY DEFAULT, AND THAT DEFAULT MOVED HERE AT D7's rewrite. The standing
    cap was retired — a send is unbounded unless it asks — so the cases below, every one of
    which is ABOUT the cap arithmetic, have to ask for it or they would be testing its
    absence. Pass `live_cap=None` for a case about the ordinary uncapped send.
    """
    run = runs.Run(directory=home, manifest={})
    run.write_identifications(_identifications(copies, name, number))
    return resolve.load(run, export_path, live_cap=live_cap)


def _command(c, *argv, exits=0):
    """One `./pkmnscan` subcommand through the real dispatch. Returns what it printed.

    `exits=1` is for an emit that adds nothing, which is refused on both paths (DEBT35)."""
    from cli import __main__ as entry

    buffer = StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        code = entry.main(list(argv))
    text = buffer.getvalue()
    c.ok(code == exits, f"`pkmnscan {argv[0]}` exits {exits}", f"exit {code}\n{text}")
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

    AND TWO MORE THAT ARE ABOUT THE CAP RATHER THAN ABOUT THE SET (D59). Measure the cap
    against the positions ONE RUN happens to hold, and a SKU whose copies sit in two boxes
    is capped once per box — an OVER-SEND, six rows against a playset of four, in a file
    `emit` then tells the operator to import. Correct that by adding the store's claim to
    the export's live quantity and stopping there, and a `pushed` nobody reconciled away
    makes the SKU permanently un-refillable. The two errors pull in opposite directions,
    which is why both are asserted rather than one: a fix aimed at either alone lands on
    the other.
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

    # --- `live` is subtracted EXACTLY ONCE, and `copies_out` is where ------------------
    # This block asserted `live` COMMITS NOTHING until D59, on a reason that was right about
    # the arithmetic and wrong about the set: while `add_to_quantity` separately subtracted
    # `live_before`, counting the stored live number here too really would have subtracted
    # the same copies twice. The cost of leaving it out was that no copy TCGplayer had
    # actually LISTED was ever marked held — so once `pushed` and `staged` reached zero, a
    # SKU with fewer copies than the cap had its own live copies handed back to the import
    # file. One reconcile forward on the owner's store: 83 rows across 64 SKUs.
    with _isolated_home() as home:
        _stock(SEVEN_COPY_SKU, "Near Mint", 6, live=3)
        resolved = _resolve_in(
            home, 6, _export_file(home / "export.csv", export, live_quantity=3)
        )
        held = resolved.report.matches[SEVEN_COPY_SKU]
        c.equal(
            len(held.committed_positions),
            3,
            "`live` COMMITS ITS OWN COPIES. Three are for sale on TCGplayer, so three of "
            "this run's copies are not the pipeline's to offer again — and it is counted "
            "ONCE, inside `cli/resolve.py:_copies_out`, which is what lets "
            "`add_to_quantity` stop subtracting `live_before` a second time",
        )
        c.equal(
            held.add_to_quantity,
            1,
            "three live against a cap of four leaves room for exactly one more — counting "
            "live twice would say zero and under-list this SKU forever",
        )
        c.equal(
            held.backstock,
            2,
            "and the rest is backstock, not lost — TWO, not five. Six copies, three live "
            "and one added leaves two unlisted; the old five counted the three live copies "
            "as backstock as well, which is the same double-count read from the other end",
        )

    # --- the store's reading and the export's are told apart by TIME (D87 amended) -------
    # `_stock` dates its `live` reading now, as a sale would. The file is dated an hour on
    # either side of that with `os.utime`, so the case asserts the ordering rather than
    # relying on the order the fixture happened to write things in.
    # THE SAME SHELF WITH NO CAP ASKED FOR (D7, rewritten 2026-09-07), and this is the case
    # that says removing the bound is safe. Six copies, three of them already live at
    # TCGplayer: the send offers THREE, not six — `_copies_out` commits the live ones and
    # `uncommitted_positions` keeps them out, exactly as it does under a cap. The bound that
    # went was the one on EXPOSURE; the one that stops a copy being sent twice never was the
    # cap, and is untouched.
    with _isolated_home() as home:
        _stock(SEVEN_COPY_SKU, "Near Mint", 6, live=3)
        resolved = _resolve_in(
            home, 6, _export_file(home / "export.csv", export, live_quantity=3), live_cap=None
        )
        free = resolved.report.matches[SEVEN_COPY_SKU]
        c.equal(
            free.add_to_quantity,
            3,
            "uncapped, the send offers every copy TCGplayer does not already hold — three of "
            "six — rather than all six. Under a cap of four it offered one; the difference is "
            "the exposure bound and nothing else",
        )
        c.equal(
            len(free.committed_positions),
            3,
            "and the three live copies are still committed, which is the guard that survived",
        )

    with _isolated_home() as home:
        _stock(SEVEN_COPY_SKU, "Near Mint", 6, live=3)
        path = _export_file(home / "export.csv", export, live_quantity=0)
        past = time.time() - 3600
        os.utime(path, (past, past))
        held = _resolve_in(home, 6, path).report.matches[SEVEN_COPY_SKU]
        c.equal(
            (held.copies_out, held.add_to_quantity, held.live_now),
            (3, 1, 3),
            "an export OLDER than the store's reading cannot re-open the cap: the store's "
            "newer 3 reaches the cap, there is room for one, and `live_now` is the 3 the "
            "cap was computed from — D59's post-reconcile hazard, closed by time",
        )
        future = time.time() + 3600
        os.utime(path, (future, future))
        held = _resolve_in(home, 6, path).report.matches[SEVEN_COPY_SKU]
        c.equal(
            (held.copies_out, held.add_to_quantity, held.live_now),
            (0, 4, 0),
            "and the export wins when it is the NEWER reading — the rule that stood "
            "unconditionally until 2026-09-02, now conditional on the file being newer",
        )

    # --- a copy that is ALREADY LISTED is not offered a second time --------------------
    # THE 83 ROWS, AT THE SIZE THEY ACTUALLY OCCUR. The block above holds six copies against
    # a cap of four, so the most it can measure is how much room is LEFT — and almost nothing
    # in the owner's store looks like that. A SKU is held in ones and twos, every copy of it
    # is already for sale, and the only honest answer is that this run has nothing to send.
    # `room = 4 - 1 - 0 = 3` said otherwise and wrote the row again: one `reconcile` forward
    # on the real store, 83 rows across 64 SKUs, each one a second listing of a card the
    # owner owns exactly one of.
    for copies in (1, 3):
        with _isolated_home() as home:
            _stock(SEVEN_COPY_SKU, "Near Mint", copies, live=copies)
            resolved = _resolve_in(
                home,
                copies,
                _export_file(home / "export.csv", export, live_quantity=copies),
            )
            held = resolved.report.matches[SEVEN_COPY_SKU]
            c.equal(
                held.add_to_quantity,
                0,
                f"{copies} on hand and {copies} live ADDS NOTHING — every copy this run "
                "holds is already for sale, so there is no second one to send",
            )
            c.equal(
                len(held.committed_positions),
                copies,
                "and the zero is a statement about COPIES rather than an accident of the "
                "cap arithmetic: all of them are committed, so there is nothing left to "
                "offer even where the cap has room",
            )

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
        c.equal(
            held.add_to_quantity,
            4,
            "AND A DEPARTED COPY TAKES NO ROOM UNDER THE CAP. Six copies on hand against a "
            "Total Quantity of zero offers four, not three — TCGplayer decremented on that "
            "sale, so `live_before` had already counted it and `room` counted it a second "
            "time. `Listing.held` forbids exactly this double-subtraction for `live`; it "
            "arrived here by a third road, and needed no listing record to do it",
        )

    # --- the cap is a QUANTITY PER SKU, not a count of one run's positions -------------
    # THE MOST SERIOUS CASE IN D59, AND NO SINGLE-BOX RUN CAN SEE IT.
    # `len(self.committed_positions)` is scoped to the cards THIS run holds while the cap it
    # was subtracted from is global, so a SKU split across two boxes had the cap enforced
    # once per box: box 1 writes four rows, a later run over box 3 writes two more, and the
    # import file `emit` hands the operator carries six against a playset of four. That is an
    # OVER-SEND rather than an under-list, which is why it goes first — the file is imported
    # before anybody can count it, and D7 caps a SKU at four for the two reasons it gives.
    #
    # BOX 3's COPIES ARE UNSTAMPED ON PURPOSE — see `_capture_at`. It is the ordinary state
    # of a box that has never been emitted, and it is what makes `committed_positions` zero
    # here however the SKU's counts are read.
    with _isolated_home() as home:
        _stock_at(1, SEVEN_COPY_SKU, "Near Mint", 4, pushed=4)
        _capture_at(BOX, 2)
        resolved = _resolve_in(
            home, 2, _export_file(home / "export.csv", export, live_quantity=0)
        )
        held = resolved.report.matches[SEVEN_COPY_SKU]
        c.equal(
            len(held.committed_positions),
            0,
            "a run over box 3 holds NO committed position — box 1's four pushed copies are "
            "not among the cards it is looking at, which is exactly why a `len()` over them "
            "could never enforce a cap that belongs to the SKU",
        )
        c.equal(
            held.add_to_quantity,
            0,
            "AND IT ADDS NOTHING ANYWAY. Four copies of this SKU are already out under a "
            "cap of four, so the room is zero wherever those copies physically sit — "
            "`copies_out` is a quantity read off the SKU across every box, where the old "
            "expression saw an empty run-scoped list and offered two more",
        )

    # (b) THE REFILL SURVIVES, which is what a conservative fix breaks. Two of box 1's four
    # have SOLD, so TCGplayer is holding two and there is room for two more — while `pushed`
    # still claims four, because `cli/cmd_reconcile.py` is the only thing that draws it down
    # and an operator who never exports from Staged never runs it. The physical ceiling in
    # `cli/resolve.py:_copies_out` is what corrects the stale claim, on the one fact that
    # needs no second CSV: we cannot have sent more copies than we own and have not sold.
    with _isolated_home() as home:
        _stock_at(1, SEVEN_COPY_SKU, "Near Mint", 4, pushed=4, sold=(1, 2))
        _capture_at(BOX, 2)
        resolved = _resolve_in(
            home, 2, _export_file(home / "export.csv", export, live_quantity=2)
        )
        held = resolved.report.matches[SEVEN_COPY_SKU]
        c.equal(
            held.add_to_quantity,
            2,
            "two sold leaves room for two, and box 3's two copies fill it. A fix that just "
            "added the store's claim to the export's live quantity would read six copies "
            "out against a cap of four and refuse to refill this SKU ever again — the "
            "opposite error to the one above, from the same reading",
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

        first = resolve.load(runs.open_run(run.directory), export_path, live_cap=LIVE_QUANTITY_CAP)
        seven = first.report.matches[SEVEN_COPY_SKU]
        c.equal(seven.add_to_quantity, 4, "the first join offers four copies, the live cap")
        c.equal(seven.backstock, 3, "and holds three as backstock")

        _command(c, "emit", str(run.directory), "--cap", "4")
        listing = Store().read().inventory.listing_for(SEVEN_COPY_SKU)
        c.equal(
            (listing.pushed, listing.staged, listing.live),
            (4, 0, 0),
            "and emit records those four as a COUNT against the SKU — `pushed` is a "
            "quantity now, not four cards each flagged at a position",
        )
        c.equal(
            tcgcsv.read_export(run.path(runs.IMPORT_MERGED)).by_sku()[SEVEN_COPY_SKU][
                tcgcsv.QUANTITY_COLUMN
            ],
            "4",
            "one row, Add to Quantity 4, three copies left in the box (D7) — and it is in "
            "`import.csv`, because ONE FILE is what a press writes now. This read "
            "`import-listed.csv` until 2026-09-03; the buckets are one file unless "
            "--split-threshold asks for two",
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
        # CAPTURED BEFORE THE SECOND EMIT — the claim below is that this file is not touched,
        # which cannot be checked against a file the assertion's own command rewrote.
        sent = run.path(runs.IMPORT_MERGED).read_bytes()
        _command(c, "emit", str(run.directory), "--cap", "4", exits=1)

        after = Store().read().inventory.listing_for(SEVEN_COPY_SKU)
        c.equal(
            run.path(runs.IMPORT_MERGED).read_bytes(),
            sent,
            "THE SECOND EMIT WRITES NO SECOND ROW. Four copies are already live on "
            "TCGplayer and the cap is four, so there is nothing to add — a second row here "
            "is what doubled them at Gate B, where a re-emit re-counted 37 copies into the "
            "files. This asserted `len(rows) == 0` until 2026-08-30, which measured "
            "something else entirely: the emitter was BLANKING the file, and 'no rows' is "
            "satisfied identically by 'no second row was written' and by 'the first row was "
            "destroyed'. D54 makes a no-op re-emit leave the file alone, so the property is "
            "byte equality — the file still holds exactly what was sent",
        )
        c.equal(
            tcgcsv.read_export(run.path(runs.IMPORT_MERGED)).by_sku()[SEVEN_COPY_SKU][
                tcgcsv.QUANTITY_COLUMN
            ],
            "4",
            "and it still says 4, not 8: the surviving row is the FIRST emit's, unchanged, "
            "rather than a second one added on top of copies already live",
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


def _check_overrun_is_named(c, export) -> None:
    """A SKU already past the cap says BY HOW MUCH, and `min` used to hide exactly that.

    THE CAP IS A CEILING ON COPIES LIVE (D7, amended 2026-09-08 on the operator's ruling),
    so the reason a matched SKU adds nothing is that `copies_out` already meets or exceeds
    the figure the send asked for. The sentence that says so printed
    `min(copies_out, live_cap)` — clamping the very number that explains the refusal to the
    cap itself, so seven copies out against a cap of two read as "2 of the 2 this SKU may
    have out". The operator's next question is "then why is nothing going out", and the
    answer had been rounded away.

    IT WAS SURVIVABLE UNDER A STANDING CAP and is not under a per-send one. With a bound of
    four standing over everything, `copies_out` rarely ran far past it; with the figure typed
    per press, asking for two while seven are out is the ordinary case, and D7's rewrite made
    uncapped the default so `copies_out` grows without a ceiling to hold it down.

    ASSERTED ON THE SENTENCE AND NOT ON THE COUNT. That `add_to_quantity` is zero here is
    D59's arithmetic and is already covered; what this pins is that the report can be acted
    on, which is the property `nothing_to_add`'s own docstring exists for.
    """
    c.note("")
    c.note("OVERRUN — a SKU past the cap names the figure that explains it")

    with _isolated_home() as home:
        # SEVEN ON THE SHELF, FIVE OF THEM LIVE. Two copies have never been sent, so
        # `uncommitted_positions` is NOT empty — which is what makes this the overrun case
        # rather than the "every copy is already listed" one. A fixture where every copy is
        # committed answers the first branch and never reaches the sentence under test.
        _stock(SEVEN_COPY_SKU, "Near Mint", 7, live=5)
        resolved = _resolve_in(
            home, 7, _export_file(home / "export.csv", export, live_quantity=5), live_cap=2
        )
        match = resolved.report.matches[SEVEN_COPY_SKU]
        c.equal(
            len(match.uncommitted_positions),
            2,
            "two copies have never been sent — stated first, because a fixture that "
            "committed all seven would answer a different branch and pass for the wrong "
            "reason",
        )
        c.equal(
            match.add_to_quantity,
            0,
            "five already live against a cap of two adds nothing, even though two copies sit "
            "unsent on the shelf — the ceiling reading, which is D59's arithmetic and right",
        )
        said = match.nothing_to_add or ""
        # ASSERTED ON THE WORD, NOT THE DIGITS. Both the old sentence and the new one contain
        # a 5 and a 2 — "5 live, at the cap of 2" against "5 live, over the 2 this send asked
        # for" — so a check for the figures passes against the defect. What was wrong is the
        # CLAIM: five out under a cap of two is not "at the cap", it is past it, and an
        # operator reading "at the cap" has been told the state is the one they asked for.
        c.ok(
            "over the 2" in said,
            f"THE SENTENCE SAYS THE STATE IS PAST THE FIGURE. Got: {said!r}",
        )
        c.ok(
            "at the cap" not in said,
            f"and it does NOT claim to be AT the cap, which is the false sentence: it reads "
            f"as compliance when the store is over by three. Got: {said!r}",
        )

    # THE OTHER ARM, where copies are out that this pipeline has not seen land. `pending > 0`
    # takes a different sentence, and that is the one `min(copies_out, live_cap)` was written
    # into — the arm the operator meets after an import they have not reconciled.
    with _isolated_home() as home:
        _stock(SEVEN_COPY_SKU, "Near Mint", 7, pushed=5, live=2)
        resolved = _resolve_in(
            home, 7, _export_file(home / "export.csv", export, live_quantity=2), live_cap=2
        )
        match = resolved.report.matches[SEVEN_COPY_SKU]
        c.equal(
            match.add_to_quantity,
            0,
            "five out against a cap of two adds nothing on this arm too",
        )
        said = match.nothing_to_add or ""
        c.ok(
            "5 already out" in said,
            f"AND IT NAMES THE FIVE THAT ARE OUT. `min(copies_out, live_cap)` printed the CAP "
            f"here — '2 of the 2 this SKU may have out' — which is a true statement about the "
            f"cap and a false one about the store, on the row whose whole question is why "
            f"nothing is going. Got: {said!r}",
        )
        c.ok(
            "of the 2 this SKU may have out" not in said,
            f"and the clamped phrasing is gone rather than merely joined. Got: {said!r}",
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
                "Box 3, Section 1, Card 2" in message,
                "the refusal names the card's position",
                message,
            )
            # The remedy names the SCREEN and its controls (`Correct claims` on a card in
            # `app/src/BoxBrowse.tsx`, `Set claims` on `app/src/BoxOps.tsx`'s panel), not
            # the `PUT /inventory/<box>/<index>` route it used to send the operator to by
            # hand — a route is not a remedy, and one wrong on a reused box number would
            # have edited another drawer's live records (D36 amended).
            c.ok(
                "#/inventory" in message
                and "Correct claims" in message
                and "Set claims" in message
                and "PUT /inventory/" not in message,
                "and points at the claim editor on #/inventory for a wrong game claim, not "
                "at the raw route",
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
            and not list(run_dir.directory.glob("import*.csv")),
            "and wrote nothing into the run directory — globbed rather than named, because "
            "`emit` writes `import.csv` by default and two other shapes behind flags, and a "
            "check that names one of them is a check three shapes can walk past",
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

        _command(c, "emit", str(run_dir.directory), "--split-games")
        listed = tcgcsv.read_export(run_dir.path(runs.import_merged_name("pokemon")))
        riftbound_listed = tcgcsv.read_export(
            run_dir.path(runs.import_merged_name("riftbound"))
        )
        c.equal(
            [r[tcgcsv.SKU_COLUMN] for r in listed.rows],
            [SEVEN_COPY_SKU],
            "--split-games writes one import file per game: import-pokemon.csv holds the "
            "pokemon row alone",
        )
        c.equal(
            [r[tcgcsv.SKU_COLUMN] for r in riftbound_listed.rows],
            [RIFTBOUND_DEFY_SKU],
            "and import-riftbound.csv its own row alone",
        )
        c.equal(
            (
                {r[tcgcsv.PRODUCT_LINE_COLUMN] for r in listed.rows},
                {r[tcgcsv.PRODUCT_LINE_COLUMN] for r in riftbound_listed.rows},
            ),
            ({"Pokemon"}, {RIFTBOUND_LINE}),
            "and under that flag no import file spans two Product Lines — the accepted "
            "fixture proves the format for one line only, and this is the way back if "
            "Import to Staged turns the merged file away",
        )

    # --- and the DEFAULT is one file, across the games and across the buckets -------
    #
    # THE OWNER'S ASK, ASSERTED RATHER THAN DESCRIBED: *"emit by default only should now
    # emit only one spreadsheet by default"*. It is a second isolated home rather than a
    # second press in the one above, because the first press spends the cap: every copy is
    # at `pushed` afterwards and a second emit correctly writes nothing (D54), so a merged
    # file could not be observed there at all.
    with _isolated_home() as home:
        _capture(2)
        run_dir = runs.create("t3-one-file")
        run_dir.write_identifications(_two_game_payload())
        sv09_path = _export_file(home / "export.csv", export)
        riftbound_path = home / "riftbound.csv"
        riftbound_path.write_bytes((REPO_ROOT / RIFTBOUND_FIXTURE).read_bytes())
        _command(
            c, "join", str(run_dir.directory),
            "--export", str(sv09_path), "--export", str(riftbound_path),
        )
        _command(c, "emit", str(run_dir.directory))
        c.equal(
            sorted(path.name for path in run_dir.directory.glob("import*.csv")),
            [runs.IMPORT_MERGED],
            "one press, one spreadsheet — no per-game file and no listed/sub-threshold pair",
        )
        merged = tcgcsv.read_export(run_dir.path(runs.IMPORT_MERGED))
        c.equal(
            sorted(r[tcgcsv.SKU_COLUMN] for r in merged.rows),
            sorted([SEVEN_COPY_SKU, RIFTBOUND_DEFY_SKU]),
            "and it carries both games' rows, which is the whole of what one file means",
        )
        c.equal(
            len({r[tcgcsv.SKU_COLUMN] for r in merged.rows}),
            len(merged.rows),
            "with no SKU twice — two rows sharing a TCGplayer Id in one import file is "
            "undefined behaviour, and merging is where that could have been lost",
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


def _check_condition_scope(c) -> None:
    """D137 — the catalog holds the conditions this product lists, and nothing else.

    EVERY ASSERTION HERE RUNS AGAINST A WIDE FIXTURE, AND THAT IS THE WHOLE LESSON. T3's
    `SOURCE_FIXTURE` is `sv09_export_untouched.csv`, which is Near-Mint-only — so the
    `from_export` block above cannot see this rule at all, passed identically before and after
    it existed, and was green through the ten days the owner's real catalog carried every play
    grade. A guard that cannot see its subject is not a guard. The two wide fixtures ARE the
    subject: Riftbound 10,078 rows over 11 conditions, Pokemon 7,802 over 16.

    What this is defending, in the order the failures actually bite:

      1. no play grade survives — the operator is never offered `Damaged Foil` for a card
         D12 says this product sells at Near Mint, and `_answer_target` cannot be handed one;
      2. NO NUMBER LOSES A FINISH — the one that separates this from D64's variant-thinning
         worry, and the one that must never be weakened. D64 measured it in as many words:
         "all 153 numbers read as thinned and not one had lost a finish";
      3. D3 rung 2 is alive — a number stocked in ONE finish resolves `catalog_forced` rather
         than queueing. The wide file had killed it outright: zero of the owner's 1,246
         numbers held a single row;
      4. sealed product survives, because it is not a grade (`tcgcsv.SEALED_CONDITION`);
      5. D25's carve-out survives — `pokemon` still keeps the Code Card rows the name
         fallback resolves, one per product instead of five.
    """
    rift = tcgcsv.read_export(REPO_ROOT / RIFTBOUND_FIXTURE)
    wide = tcgcsv.read_export(REPO_ROOT / WIDE_FIXTURE)

    # The fixtures have to BE wide or every assertion below is vacuous — the shape of failure
    # that let this bug live. Asserted, not assumed.
    c.ok(
        len({r[tcgcsv.CONDITION_COLUMN] for r in rift.rows}) > 2
        and len({r[tcgcsv.CONDITION_COLUMN] for r in wide.rows}) > 3,
        "the wide fixtures really do carry play grades — without that this whole block "
        "passes by accident, which is exactly how the sv09-only coverage stayed green",
    )

    for label, source, game in (
        ("riftbound", rift, "riftbound"),
        ("pokemon", wide, "pokemon"),
    ):
        catalog = join.Catalog.from_export(source, game)
        listable = {
            str(v) for v in dict(games.require(game)["condition_by_finish"]).values()
        } | {tcgcsv.SEALED_CONDITION}

        # 1. no play grade survives
        held = {r[tcgcsv.CONDITION_COLUMN] for r in catalog.export.rows}
        c.equal(
            sorted(held - listable),
            [],
            f"{label}: the catalog holds only the conditions this product lists — no "
            f"Lightly Played, no Damaged, nothing the ladder would never pick",
        )

        # 2. no number loses a finish. Keyed the way the row is FOUND, so this is a
        # statement about what the join can reach and not about the file's own spelling.
        def finishes(rows):
            out = {}
            for row in rows:
                number = row[tcgcsv.NUMBER_COLUMN].strip()
                if not number:
                    continue
                out.setdefault(join.number_index_key(number), set()).add(
                    (row[tcgcsv.SET_COLUMN], row[tcgcsv.CONDITION_COLUMN].endswith(
                        ("Foil", "Holofoil")
                    ))
                )
            return out

        mine = [r for r in source.rows if r[tcgcsv.PRODUCT_LINE_COLUMN] == games.require(
            game
        )["product_line"]]
        before, after = finishes(mine), finishes(catalog.export.rows)
        c.equal(
            sorted(k for k in before if before[k] != after.get(k)),
            [],
            f"{label}: NOT ONE number loses a finish — a play grade is not a finish (D64), "
            f"and this is the assertion that keeps the narrowing honest",
        )

        # 3. rung 2 is alive — COUNTED IN ROWS, NOT IN FINISHES, and the first draft of this
        # counted finishes and passed with the filter deleted. `variant.resolve`'s rung 2 is
        # `len(candidates) == 1` over ROWS, so five grades of one finish is five candidates
        # and the rung does not fire. A set of finishes cannot see that; it collapses the
        # exact multiplicity the bug was made of. Mutation-tested, which is the only reason
        # this comment exists.
        rows_per_key = {}
        for row in catalog.export.rows:
            number = row[tcgcsv.NUMBER_COLUMN].strip()
            if number:
                rows_per_key.setdefault(join.number_index_key(number), []).append(row)
        singles = [k for k, rows in rows_per_key.items() if len(rows) == 1]
        c.ok(
            len(singles) > 0,
            f"{label}: numbers resolving to exactly ONE ROW exist again, so D3 rung 2 can "
            f"fire — against the unfiltered file there were ZERO, which is what took the "
            f"catalog_forced rung out of service entirely",
            f"{len(singles)} of {len(rows_per_key)}",
        )
        # And through the ladder itself, because a count is not a resolution. This is the
        # behaviour the operator feels: the card decides itself instead of queueing.
        if singles:
            lone = rows_per_key[singles[0]][0]
            resolved = variant.resolve(
                [lone], metadata_finish=None, detected_finish=None, game=game
            )
            c.equal(
                resolved.stage,
                variant.CATALOG_FORCED,
                f"{label}: and a one-row number really does resolve catalog_forced through "
                f"the ladder rather than reaching rung 4 and facing a human "
                f"({lone[tcgcsv.NAME_COLUMN]} {lone[tcgcsv.NUMBER_COLUMN]})",
            )

        # 4. sealed survives
        sealed_in = [
            r
            for r in mine
            if r[tcgcsv.CONDITION_COLUMN] == tcgcsv.SEALED_CONDITION
        ]
        sealed_out = [
            r
            for r in catalog.export.rows
            if r[tcgcsv.CONDITION_COLUMN] == tcgcsv.SEALED_CONDITION
        ]
        c.ok(sealed_in, f"{label}: the fixture really does hold sealed product to keep")
        c.equal(
            len(sealed_out),
            len(sealed_in),
            f"{label}: every sealed row survives — it is not a grade, it carries no "
            f"Number, and it is reachable by name at $250 a Booster Display",
        )
        if sealed_in:
            name = sealed_in[0][tcgcsv.NAME_COLUMN].strip()
            c.equal(
                [
                    r[tcgcsv.SKU_COLUMN]
                    for r in catalog.rows_for_blank_number_name(name)
                ],
                [sealed_in[0][tcgcsv.SKU_COLUMN]],
                f"{label}: and it is still findable through the blank-Number index that "
                f"is the only rung that ever reaches it",
            )

    # 5. D25's carve-out, and the code-card track getting rung 2 back with it.
    code_rows = [r for r in wide.rows if r[tcgcsv.RARITY_COLUMN] == "Code Card"]
    pokemon = join.Catalog.from_export(wide, "pokemon")
    kept_codes = [
        r
        for r in pokemon.export.rows
        if r[tcgcsv.RARITY_COLUMN] == "Code Card"
    ]
    c.equal(
        len(kept_codes),
        len({r[tcgcsv.NAME_COLUMN] for r in code_rows}),
        "`pokemon` still keeps the Code Card rows D25 keeps them for — ONE per product "
        "now rather than one per grade, which is the same fix one register down: a code "
        "card looked up by name used to offer five rows and resolve none of them",
    )

    # And the emptiness that is NOT the wrong file. An export carrying this game's rows in
    # play grades only is a plausible hand-download with the wrong box ticked, and it used to
    # refuse with a sentence about `Product Line` — sending the operator to check the one
    # column that was right.
    played_only = tcgcsv.Export(
        header=rift.header,
        rows=tuple(
            r
            for r in rift.rows
            if r[tcgcsv.CONDITION_COLUMN].startswith(("Lightly", "Damaged"))
        ),
        source="played-only.csv",
    )
    caught = c.raises(
        join.EmptyCatalog,
        lambda: join.Catalog.from_export(played_only, "riftbound"),
        "an export holding this game's rows in play grades only refuses rather than "
        "joining nothing",
    )
    if caught is not None:
        c.ok(
            "Near Mint" in str(caught) and "Product Line" not in str(caught),
            "and the refusal names the CONDITION axis rather than blaming the one column "
            "that was correct",
            str(caught),
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
        # The toggle claims one finish, the photograph reads another. Without rung 0 the
        # toggle would decide this card; the answer outranks the toggle.
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
    _check_overrun_is_named(c, export)
    _check_answer_off_the_record(c, export)
    _check_game_partition(c, export)
    _check_condition_scope(c)

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
            "Box 3, Section 1, Card 5",
            "backstock position is addressable",
        )

    # --- never join on Product Name -----------------------------------------------------
    #
    # THE KEY IS STILL THE NUMBER AND THE NAME IS STILL NOT A KEY. What changed on
    # 2026-09-11 is what happens AFTER the number finds the row: a read name matching none
    # of the rows the number found is `routing.NAME_DISPUTED`, so the card is queued rather
    # than listed. This case is that rule's own subject — a name deliberately unlike any row
    # — and it asserts both halves, because the second one is worthless if the first ever
    # stops being true.
    wrong_name = join.join_batch(
        [_card(90, "NOT THE RIGHT NAME", "120", metadata="normal")], catalog
    )
    c.equal(
        [row[tcgcsv.SKU_COLUMN] for row in wrong_name.unmatched_cards[0].candidates]
        if wrong_name.unmatched_cards
        else [],
        [SEVEN_COPY_SKU],
        "a wrong Product Name still FINDS its row on the number",
    )
    c.equal(
        [u.reason for u in wrong_name.unmatched_cards],
        [routing.NAME_DISPUTED],
        "and is queued rather than listed, because the name matches no row it found",
    )
    c.equal(list(wrong_name.matches), [], "so nothing is listed off a disputed name")
    c.equal(
        [row[tcgcsv.SKU_COLUMN] for row in wrong_name.unmatched_cards[0].candidates]
        if wrong_name.unmatched_cards
        else [],
        [SEVEN_COPY_SKU],
        "AND A NAME THAT FINDS NOTHING CHANGES NOTHING — the number's row alone, exactly "
        "as before 2026-09-12. `NOT THE RIGHT NAME` is in no row, so the rung below has "
        "nothing to offer and must not invent a second candidate",
    )

    # --- BOTH READINGS, THE NAME'S FIRST -------------------------------------------------
    #
    # THE SCREEN LED WITH THE CARD IT HAD JUST REASONED WAS WRONG, and this is the case that
    # fixes. A disputed entry offered only `resolution.row` — the row the NUMBER found —
    # which is the one row the entry's own sentence tells the operator is not what the
    # photograph says. The only way to the right row was `L` and typing the name the model
    # had already read.
    #
    # MEASURED OVER EVERY `name_disputed` ENTRY THE OWNER'S STORE HAS RECORDED, all nine: in
    # nine of nine the NAME was right and the NUMBER wrong, and seven have since been
    # answered by a human who chose, in seven of seven, a row the name finds. Re-run through
    # this rung, the answer is digit 1 on all nine.
    #
    # Dunsparce at 120/159 read under Butterfree's name is that shape exactly — the number
    # lands on a real row for a real card, and the name says it is a different one.
    released = join.join_batch(
        [_card(92, AMPERSAND_NAME, "120", metadata="normal")],
        catalog,
        router=join.default_router(),
    )
    c.equal(
        list(released.matches),
        [AMPERSAND_NORMAL_SKU],
        "THE NAME DECIDES, AND THE CARD IS LISTED — the owner's ruling of 2026-09-12: "
        "*\"Release them when the name resolves to exactly one card.\"* The number found "
        "Dunsparce's row and the name answers one card, so the name is the stronger "
        "evidence and no human is asked",
    )
    c.equal(
        released.queued,
        [],
        "and nothing is queued for it — which is the whole of the release, measured at 209 "
        "cards on the owner's store against 209 human answers with ZERO disagreements",
    )

    # A NAME THAT ANSWERS TWO CARDS IS THE EVIDENCE D35 DISTRUSTED, AND IT STILL QUEUES.
    # `Articuno` is printed at 32/159 and again as the secret rare 161/159, which is the
    # same shape as `Aspirant's Climb` on the owner's store — the one of the nine the
    # release deliberately does not reach. No claim about a stack can settle which print is
    # in the box; only a person looking at the photograph can.
    two_cards = join.join_batch(
        [_card(93, "Articuno", "120", metadata="normal")],
        catalog,
        router=join.default_router(),
    )
    queued = two_cards.queued[0] if two_cards.queued else None
    if c.ok(queued is not None, "a name answering TWO cards is queued, never listed"):
        c.equal(list(two_cards.matches), [], "and nothing is listed off it")
        c.equal(
            queued.resolution_reason,
            routing.NAME_DISPUTED,
            "under the same reason code, which the release does not change",
        )
        names = [row[tcgcsv.NAME_COLUMN] for row in queued.candidates]
        c.equal(
            names[-1],
            "Dunsparce",
            "BOTH READINGS ARE OFFERED AND THE NUMBER'S GOES LAST. The operator's own "
            "words for what was wanted: *\"it could've suggested both, say hard bargain "
            "and factory recall both on the same page\"*",
        )
        c.equal(
            {join.name_index_key(n) for n in names[:-1]},
            {"ARTICUNO"},
            "every row ahead of it is the name's, so the reading that resolves is what the "
            "operator reaches first — THROUGH THE FOLD, because this export spells one of "
            "the two prints `Articuno - 032/159` and the other `Articuno`. That is "
            "`CLAUDE.md`'s `Delibird - 105/132` hazard in the fixture, and it landing in "
            "one name bucket is D35's fold doing the job the rung depends on",
        )
        c.equal(
            [row[tcgcsv.SKU_COLUMN] for row in queued.candidates][-1:],
            [SEVEN_COPY_SKU],
            "the number's row is still there and still itself — this adds candidates and "
            "removes none, so a card whose number was right is never worse off",
        )
        stamped = resolve._candidate_rows(queued.candidates, queued.name_matched_skus)
        c.equal(
            [row.get("found_by") for row in stamped][-1],
            "number",
            "AND THE WIRE SAYS WHICH SIGNAL FOUND WHICH. Rows for two different cards with "
            "no provenance is a worse question than the one it replaced: the operator can "
            "see two cards and not which reading argued for either",
        )
        c.ok(
            all(row.get("found_by") == "name" for row in stamped[:-1]),
            "with every row the name found stamped as the name's",
        )
    plain = resolve._candidate_rows(wrong_name.unmatched_cards[0].candidates)
    c.equal(
        [("found_by" in row) for row in plain],
        [False],
        "and an entry with one provenance carries no stamp at all — a badge on every row "
        "in the queue is what stamping `number` unconditionally would have produced",
    )

    # ONE ROW IS NOT THE SAME AS ONE SETTLED ROW, AND THIS CASE SHIPPED BROKEN FOR AN HOUR.
    #
    # The release gate counted `len(alternatives) == 1`, which is true in two different
    # situations: the ladder narrowed a stack to one row, and the name answered a card the
    # export stocks in exactly ONE finish and the ladder REFUSED it. `Alcremie ex` is the
    # second — a single `Near Mint Holofoil` row — so a `normal` claim resolves
    # `metadata_not_stocked` with no row at all, and the gate read that as settled and
    # listed the card on a finish the ladder had just rejected. `CLAUDE.md`'s first hard
    # rule, broken by an off-by-one-concept in a boolean.
    #
    # `NameSide.settled` is the fix: the ladder's own answer, carried rather than inferred.
    refused = join.join_batch(
        [_card(95, "Alcremie ex", "120", metadata="normal")],
        catalog,
        router=join.default_router(),
    )
    c.equal(
        list(refused.matches),
        [],
        "A SINGLE ROW THE LADDER REFUSED IS NOT RELEASED. `Alcremie ex` is stocked in one "
        "finish and the claim contradicts it, so there is no settled answer to release — "
        "counting rows instead of asking the ladder listed this card on a finish it had "
        "just rejected",
    )
    c.equal(
        len(refused.queued),
        1,
        "and it queues instead, which is where a card whose finish nobody can settle goes",
    )

    # WHAT COUNTS AS ONE CARD, ASSERTED DIRECTLY — because the fixture cannot reach it.
    #
    # `distinct_cards` keys on `(Set Name, folded Number)`, and SV09 is a SINGLE SET, so a
    # version of it that dropped the set entirely answers identically on every row in this
    # file. The mutation arm that deletes the set from the key survives the whole suite for
    # that reason alone, which is a gap in the fixture rather than in the rule. Hand-built
    # rows are the only way to state it here, and the case is real and live: the owner's
    # `Calm Rune (R02a)` is stocked at one number across Spiritforged, Unleashed and
    # Vendetta, and reading those three as one card would auto-list a card nobody could say
    # the set of.
    one_card = [
        {tcgcsv.SET_COLUMN: "Origins", tcgcsv.NUMBER_COLUMN: "276/298"},
        {tcgcsv.SET_COLUMN: "Origins", tcgcsv.NUMBER_COLUMN: "276/298"},
    ]
    two_sets = [
        {tcgcsv.SET_COLUMN: "Spiritforged", tcgcsv.NUMBER_COLUMN: "R02a"},
        {tcgcsv.SET_COLUMN: "Unleashed", tcgcsv.NUMBER_COLUMN: "R02a"},
    ]
    two_numbers = [
        {tcgcsv.SET_COLUMN: "Origins", tcgcsv.NUMBER_COLUMN: "276/298"},
        {tcgcsv.SET_COLUMN: "Origins", tcgcsv.NUMBER_COLUMN: "276a/298"},
    ]
    c.equal(
        join.distinct_cards(one_card),
        1,
        "two rows of one card in one set are ONE card — the finishes beneath a card are "
        "not a question about which card it is",
    )
    c.equal(
        join.distinct_cards(two_sets),
        2,
        "ONE NUMBER IN TWO SETS IS TWO CARDS, which the number alone cannot tell and is "
        "why the set is half the key",
    )
    c.equal(
        join.distinct_cards(two_numbers),
        2,
        "and two numbers in one set are two cards — `276a/298` is the promo print of "
        "`276/298`, which is the ninth of the owner's nine and the one still queued",
    )
    c.equal(
        join.distinct_cards(
            [
                {tcgcsv.SET_COLUMN: "Origins", tcgcsv.NUMBER_COLUMN: "276/298"},
                {tcgcsv.SET_COLUMN: "Origins", tcgcsv.NUMBER_COLUMN: "0276/298"},
            ]
        ),
        1,
        "and the number goes through the same fold the index does, so a padded spelling "
        "is not a second card",
    )

    # A NAME WHOSE FINISH THE LADDER CANNOT SETTLE IS NOT RELEASED EITHER, AND GUESSES
    # NOTHING. Butterfree is ONE card — so the release's card test passes — but it is
    # stocked Holofoil and Reverse Holofoil only, so a `normal` claim contradicts both and
    # the ladder reviews. The release needs the finish settled as well as the card, and this
    # is the case that separates the two conditions. `CLAUDE.md`: ambiguity goes to the
    # queue with its photo, and nothing is silently dropped.
    unsettled = join.join_batch(
        [_card(94, "Butterfree", "120", metadata="normal")],
        catalog,
        router=join.default_router(),
    )
    spread = unsettled.queued[0] if unsettled.queued else None
    if c.ok(spread is not None, "an unsettled finish on the name side still queues"):
        c.equal(list(unsettled.matches), [], "and lists nothing")
        c.equal(
            [row[tcgcsv.NAME_COLUMN] for row in spread.candidates],
            ["Butterfree", "Butterfree", "Dunsparce"],
            "BOTH OF THE NAME'S FINISHES ARE OFFERED, still ahead of the number's row — a "
            "rung that narrowed to one here would be guessing a finish the ladder just "
            "refused to guess",
        )
        c.equal(
            len(spread.name_matched_skus),
            2,
            "and both are claimed by the name, so the screen can say so on each",
        )

    # --- D253, 2026-09-23: THE GATE REACHES A CARD ALREADY QUEUED -----
    #
    # Until this date the whole block above only fired `not resolution.needs_review and
    # resolution.row is not None` — a card the ladder had already resolved OUTSIDE review.
    # A card ALREADY headed to review for a reason of its OWN — `ambiguous_no_signal`,
    # `rarity_claim_mismatch`, `set_ambiguous`, … — never got the name cross-check at all,
    # and its queue entry offered only the wrong card's rows. Measured on the owner's
    # store: `4/176` read "Daisy!" over a number that resolved to `Lilting Lullaby`'s two
    # rows, queued `ambiguous_no_signal`, and the entry offered only those two — never
    # Daisy's. `6/563` read "Frigid Jewel" at `024/219`, capture claimed a foil finish and
    # a Common/Uncommon rarity, queued `rarity_claim_mismatch` — a reason that never
    # carries a row at all — and offered only `Rengar, Unseen`, a Rare. Both were answered
    # onto the wrong-name SKU because that was the only row on screen.
    #
    # Dunsparce `120/159` stands in for both shapes: stocked in two conditions, so a card
    # with no capture claim over it reviews `ambiguous_no_signal`; the SAME number reviews
    # `rarity_claim_mismatch` under a rarity claim neither of its rows carries (both are
    # Common). Neither reason carries a row for the disputed name to be compared or ranked
    # against, which is exactly the gap `resolution.row is not None` used to require.

    # Daisy's shape: queued for a reason of its own, the name resolves to exactly ONE
    # OTHER card with exactly one stocked condition, so the ladder settles it by
    # `CATALOG_FORCED` — no capture claim needed. D162 still decides alone. `Alcremie ex
    # 075/159` stands in: one row, Near Mint Holofoil, a real (non-blank) number — a
    # BLANK-Number product is deliberately unreachable here, since `Catalog.rows_for_name`
    # excludes it (`_blank_number_by_name` is a separate index, D35's own fallback rung,
    # never this one).
    ALCREMIE_EX_SKU = "8608039"  # Alcremie ex 075/159, Near Mint Holofoil, single row
    daisy = join.join_batch(
        [_card(96, "Alcremie ex", "120")],
        catalog,
        router=join.default_router(),
    )
    c.equal(
        list(daisy.matches),
        [ALCREMIE_EX_SKU],
        "THE CARD IS LISTED, off the row the NAME settled. Before the gate widened this "
        "stayed queued under `ambiguous_no_signal` with Dunsparce's two conditions on "
        "offer — the wrong card, with nothing pointing at the right one",
    )
    c.equal(daisy.queued, [], "and nothing is left in a queue for it")
    c.equal(
        daisy.name_corrections,
        {},
        "and no name correction either — the read and the row it settled on ARE "
        "byte-identical (\"Alcremie ex\" is both), so there is nothing to correct",
    )

    # A RARITY CLAIM THAT CONTRADICTS THE NAME'S OWN ROWS MUST STILL QUEUE — the review's
    # first CRITICAL finding, 2026-09-23. `name_alternatives` passed `name_corroborated=
    # True` HARD-CODED from 2026-09-12 until this fix: the argument was that a row
    # `rows_for_name` found BY the name already "agrees" with it, so a contradicting
    # rarity claim could be waived exactly as D146 waives one the NUMBER's own row
    # corroborates. That argument is circular — finding a row by name is not a SECOND
    # signal independent of the name, and D146 needs two. Measured cost: this exact
    # shape (`Billy & O'Nare`'s rows are Common, the claim says `Rare`) auto-released
    # onto `Billy & O'Nare` before the fix. Real case: `4/442` read "Pyke, Returned",
    # `rarity_claim=['Showcase']`, auto-released onto the BASE print (Rare) — the owner
    # confirmed the true card is the Alternate Art print, `074/219`'s own sibling shape
    # one register over. `name_corroborated=False` now, and this asserts REVIEW.
    contradicted_name_card = join.IdentifiedCard(
        position=join.Position(box=BOX, index=97),
        name=AMPERSAND_NAME,
        number="120",
        printed_total="159",
        metadata_finish=("reverse_holo",),
        rarity_claim=("Rare",),
        photo=f"captures/box{BOX}/0097.jpg",
        confidence="high",
    )
    contradicted_name = join.join_batch(
        [contradicted_name_card], catalog, router=join.default_router()
    )
    c.equal(
        list(contradicted_name.matches),
        [],
        "NOTHING LISTS. `Rare` matches neither of `Billy & O'Nare`'s Common rows, and a "
        "claim contradicting every row the name found is not waived just because the "
        "name is what found them",
    )
    contradicted_queued = (
        contradicted_name.queued[0] if contradicted_name.queued else None
    )
    if c.ok(contradicted_queued is not None, "and it queues instead"):
        c.equal(
            contradicted_queued.resolution_reason,
            variant.RARITY_CLAIM_MISMATCH,
            "under the reason the claim actually failed on",
        )

    # Frigid's REAL shape: the claim MATCHES the name's own row, and a finish claim then
    # picks which of its conditions is meant — `rarity_claim_mismatch` on the NUMBER
    # (Dunsparce, Common, claimed Uncommon), no row at all, released over `Banette`'s own
    # rows (Uncommon, matching the claim) with the finish claim settling Reverse
    # Holofoil first, the same way the real `6/563` settled Near Mint Foil under
    # `metadata_finish: ['foil']` and a Common/Uncommon claim.
    BANETTE_REVERSE_SKU = "8607899"  # Banette 060/159, Near Mint Reverse Holofoil
    frigid_card = join.IdentifiedCard(
        position=join.Position(box=BOX, index=101),
        name="Banette",
        number="120",
        printed_total="159",
        metadata_finish=("reverse_holo",),
        rarity_claim=("Uncommon",),
        photo=f"captures/box{BOX}/0101.jpg",
        confidence="high",
    )
    frigid = join.join_batch([frigid_card], catalog, router=join.default_router())
    c.equal(
        list(frigid.matches),
        [BANETTE_REVERSE_SKU],
        "THE CLAIM MATCHES THE NAME'S ROW, so the claimed finish wins over it. "
        "`rarity_claim_mismatch` never carries a row to rank from and `found.rows` is "
        "the wrong card (Dunsparce, Common) — the claim agrees with `Banette` (Uncommon) "
        "and settles over its own rows, putting Reverse Holofoil in front",
    )
    c.equal(frigid.queued, [], "and nothing is queued for it")

    # The review's second CRITICAL finding: a QUALIFIED name was unreachable.
    # `Catalog.__init__` indexed `_by_name` on the raw fold, which never strips a
    # trailing `(Alternate Art)`, so `rows_for_name` never found the alt-art print and
    # D162's "exactly one card" test saw one product where the export stocks two — the
    # real `4/442` shape exactly. `_qualifier_catalog` clones `Banette (Alternate Art)`
    # at `060a/159`, `Showcase`, to prove it against.
    qualifier_catalog = _qualifier_catalog(export)
    c.equal(
        {row[tcgcsv.SKU_COLUMN] for row in qualifier_catalog.rows_for_name("Banette")},
        {QUALIFIER_BASE_SKU, "8607899", QUALIFIER_ALT_SKU},
        "THE QUALIFIER VARIANT IS AMONG THE NAME'S ROWS NOW — indexed and looked up "
        "through the same catalog-side fold, so `(Alternate Art)` no longer hides a "
        "printing from this rung",
    )
    c.equal(
        {
            row[tcgcsv.SKU_COLUMN]
            for row in qualifier_catalog.candidates(_card(0, "Dunsparce", "120")).rows
        },
        {SEVEN_COPY_SKU, SEVEN_COPY_REVERSE_SKU},
        "AND THE NUMBER'S OWN LOOKUP IS UNTOUCHED — the qualifier fold is a NAME-side "
        "change only, the number key finds exactly the rows it always found",
    )
    alt_art_card = join.IdentifiedCard(
        position=join.Position(box=BOX, index=102),
        name="Banette",
        number="120",
        printed_total="159",
        rarity_claim=("Showcase",),
        photo=f"captures/box{BOX}/0102.jpg",
        confidence="high",
    )
    alt_art = join.join_batch(
        [alt_art_card], qualifier_catalog, router=join.default_router()
    )
    c.equal(
        list(alt_art.matches),
        [QUALIFIER_ALT_SKU],
        "THE CLAIM PICKS THE ALT-ART PRINT, and the card lists on it — TWO agreeing "
        "signals, D146's own shape: the name narrows every printing to one CARD, "
        "`Showcase` narrows within that to the one PRINTING it names. Before both "
        "fixes this queued, or worse, released onto the base (Rare) print",
    )
    c.equal(alt_art.queued, [], "and nothing is queued for it")
    two_products_card = join.IdentifiedCard(
        position=join.Position(box=BOX, index=103),
        name="Banette",
        number="120",
        printed_total="159",
        photo=f"captures/box{BOX}/0103.jpg",
        confidence="high",
    )
    two_products = join.join_batch(
        [two_products_card], qualifier_catalog, router=join.default_router()
    )
    two_products_queued = two_products.queued[0] if two_products.queued else None
    if c.ok(
        two_products_queued is not None,
        "NO CLAIM AT ALL still queues rather than guessing between the two prints",
    ):
        c.equal(list(two_products.matches), [], "and lists nothing")

    # A DISPUTED NAME THAT DOES NOT SETTLE STILL KEEPS ITS PRIMARY REASON, and its
    # candidates are the name's rows first, then the NUMBER'S OWN — `found.rows`, plural,
    # because `rarity_claim_mismatch` left `resolution.row` at `None` and there is no
    # single row to fall back to. `Articuno` answers TWO cards (32/159 and the secret rare
    # 161/159), so the name never settles it, whatever the claim says.
    unsettled_review_card = join.IdentifiedCard(
        position=join.Position(box=BOX, index=98),
        name="Articuno",
        number="120",
        printed_total="159",
        rarity_claim=("Rare",),
        photo=f"captures/box{BOX}/0098.jpg",
        confidence="high",
    )
    unsettled_review = join.join_batch(
        [unsettled_review_card], catalog, router=join.default_router()
    )
    still_queued = unsettled_review.queued[0] if unsettled_review.queued else None
    if c.ok(still_queued is not None, "an unsettled dispute over a reason of its own still queues"):
        c.equal(list(unsettled_review.matches), [], "and lists nothing")
        c.equal(
            still_queued.resolution_reason,
            variant.RARITY_CLAIM_MISMATCH,
            "THE PRIMARY REASON SURVIVES — it is not overwritten to `name_disputed`, "
            "because the card is still queued for what it was queued for",
        )
        candidate_names = [row[tcgcsv.NAME_COLUMN] for row in still_queued.candidates]
        c.equal(
            set(candidate_names[:-2]),
            {"Articuno - 032/159", "Articuno - 161/159"},
            "the name's rows (both prints) lead the list",
        )
        c.equal(
            candidate_names[-2:],
            ["Dunsparce", "Dunsparce"],
            "and BOTH of the number's own rows close it — `found.rows`, not one row, "
            "because `rarity_claim_mismatch` never gave this card a single row to fall "
            "back to",
        )

    # --- D253, THE NEAR-MISS HALF: a read that agreed WITHOUT being ---
    # byte-identical offers the catalogue's own spelling as a correction; an exact read
    # offers none, because there is nothing to correct.
    near_miss = join.join_batch(
        [_card(99, "Dunsprce", "120", metadata="normal")],
        catalog,
        router=join.default_router(),
    )
    c.equal(
        near_miss.name_corrections,
        {(BOX, 99): "Dunsparce"},
        "a read one letter short of the row it resolved to offers the catalogue's own "
        "spelling as a stored-name correction — the model's own reading is untouched, "
        "this is a candidate for `Card.name` alone",
    )
    exact_read = join.join_batch(
        [_card(100, "Dunsparce", "120", metadata="normal")],
        catalog,
        router=join.default_router(),
    )
    c.equal(
        exact_read.name_corrections,
        {},
        "and NOTHING when the read was already byte-identical to the row",
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
    # ASKING FOR THE CAP, WHICH IS WHAT D7's rewrite MADE THIS CASE DO. The refill arithmetic is
    # unchanged and still worth pinning — it is simply no longer applied to a send that did
    # not ask. The uncapped answer for this same match is asserted immediately below.
    refill = join.SkuMatch(
        sku=SEVEN_COPY_SKU,
        row=partly_live,
        positions=[join.Position(BOX, i) for i in range(1, 8)],
        live_cap=LIVE_QUANTITY_CAP,
    )
    c.equal(refill.add_to_quantity, 1, "refill tops up to the cap, not past it")
    # AND THE ORDINARY SEND, WHICH ASKS FOR NO CAP AT ALL (D7, rewritten 2026-09-07). Same
    # match, same three copies already live at TCGplayer, no bound: every copy this run holds
    # that TCGplayer does not already have goes. Four, not seven — `uncommitted_positions` is
    # what keeps the three live ones out, and it is untouched by the rewrite. That distinction
    # is the whole reason removing the bound is safe: the cap read a QUANTITY, and something
    # else has always done the work of not sending a copy twice.
    uncapped = join.SkuMatch(
        sku=SEVEN_COPY_SKU,
        row=partly_live,
        positions=[join.Position(BOX, i) for i in range(1, 8)],
    )
    c.equal(
        uncapped.add_to_quantity, 7,
        "with no cap asked for, every position this match holds is offered — a bare match has "
        "committed none, so seven. The real path commits the live ones first; see below",
    )
    c.equal(
        uncapped.live_cap, None,
        "and `live_cap` is None rather than a large number: the bound is ABSENT, not loose",
    )
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

    # THE HINT THAT ANSWERS TO BOTH SETS, which is the shape a pairwise predicate cannot see.
    # `set_matches` is asked about ONE name at a time, so a hint matching both candidate sets
    # narrowed the rows to BOTH of them and `Catalog.candidates` returned that as decisive:
    # no `set_ambiguous`, no review, and a card listed off a two-set pile.
    #
    # IT NEEDS ITS OWN CATALOG AND THAT IS THE POINT. Against `multi` the two sets are `SV09:`
    # and `SV08:`, whose colon sides differ, so the old predicate matched NEITHER and this case
    # would have passed against the very code it is here to catch. `SHARED_SIDE_SET` gives the
    # two sets one colon side, which is the live shape: `SV` names four real sets at once.
    # Resolution is set-wise now and a tie answers None, so this card reaches a human.
    shared = _multi_set_catalog(export, second_set=SHARED_SIDE_SET)
    both = join.join_batch(
        [_card(24, "Butterfree", "003", metadata="reverse_holo", set_hint="SV09")],
        shared,
        router=join.default_router(),
    )
    c.equal(
        [q.destination.reason for q in both.queued],
        [routing.SET_AMBIGUOUS],
        "a hint answering to BOTH candidate sets reviews rather than narrowing to both",
    )
    c.equal(list(both.matches), [], "...and lists nothing off the two-set pile")

    # And a three-letter set code the alias table never carried resolves at the join, not just
    # at the export fetch — the two used to be different matchers and only one knew codes.
    c.ok(
        join.set_matches("SSP", SECOND_SET),
        "a set code resolves at join time: SSP is Surging Sparks by the shared ladder",
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

    # 5. IT LISTS WHERE THE NAME ANSWERS EXACTLY ONE CARD, AND THIS ASSERTION IS REVERSED.
    #
    #    It read "a name-resolved card is QUEUED, never listed on the name alone" until
    #    2026-09-12, which was D35's ruling and the owner's at the time. They repealed the
    #    operative half of it on the store's own record: 212 entries reached this rung,
    #    every one was answered by a human, and in 212 OF 212 the human chose the SKU the
    #    entry was already holding. Their words: *"Release them when the name resolves to
    #    exactly one card."*
    #
    #    D35's CAUTION IS NOT REPEALED, IT IS AIMED. That entry distrusted the name as a
    #    weak signal, and a name answering SEVERAL cards is exactly that — still queued,
    #    immediately below. What fell is the blanket prohibition over the case where the
    #    name is not weak at all.
    named = join.join_batch(
        [_card(805, REAL_NAME, number=None, metadata=("normal",))],
        catalog,
        router=join.default_router(),
        live_cap=LIVE_QUANTITY_CAP,
    )
    queued = named.queue(routing.MAIN) + named.queue(routing.PARKED)
    c.equal(
        len(queued),
        0,
        "a name answering exactly one card is LISTED — 212 of 212 such questions on the "
        "owner's store were answered by a human who chose the row already on offer",
    )
    c.equal(
        len(named.matches),
        1,
        "and it reaches the import file, which is the whole point of releasing it",
    )

    #    THE WEAK NAME IS STILL QUEUED. `Articuno` is printed at 32/159 and again as the
    #    secret rare 161/159, so its name answers TWO cards and no claim about a stack can
    #    say which is in the box. This is the half of D35 that survives.
    two = join.join_batch(
        [_card(806, "Articuno", number=None, metadata=("normal",))],
        catalog,
        router=join.default_router(),
        live_cap=LIVE_QUANTITY_CAP,
    )
    weak = two.queue(routing.MAIN) + two.queue(routing.PARKED)
    c.equal(
        len(weak),
        1,
        "D35 SURVIVES WHERE IT WAS AIMED: a name answering two cards is queued, never "
        "listed — the release reaches the strong name and not this one",
    )
    if weak:
        c.equal(
            weak[0].resolution_reason,
            routing.NUMBER_UNREAD_NAME_MATCHED,
            "D35: under its own reason code",
        )
        c.equal(
            len(weak[0].candidates),
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
    # `_repair_set_code` is licensed by a measurement: across every distinct `Number` cell in
    # both games keyed this way — 1,237 Riftbound and 396 One Piece — none is set-code-shaped.
    #
    # THE SEPARATOR IS ARBITRARY, WHICH IS WHY THE RULE IS A SHAPE (2026-08-30). Box 3 glued a
    # set code onto 7 of 39 reads across THREE separators — bullet, hyphen and slash — including
    # two copies of one card read both ways. The old rule was a tuple of two characters and an
    # `rsplit`, and neither of the new separators could join it: `rsplit("/")` over `120/219`
    # yields `219`, a real identifier belonging to a different card. Every case below was
    # observed failing against that rule before the shape rule replaced it.
    for separator in ("\u2022", "\u00b7", "-", "/"):
        glued = f"UNL {separator} {RIFT_NUMBER}"
        found = rift_catalog.candidates(_rift(814, RIFT_NAME, glued))
        c.equal(
            {r[tcgcsv.NUMBER_COLUMN] for r in found.rows},
            {RIFT_NUMBER},
            f"set code: {glued!r} lands on the row the bare identifier would have",
        )
        c.ok(
            not found.name_inferred,
            f"set code: {glued!r} is recovered by NUMBER, not rescued by name",
        )
        c.ok(
            found.lookup == f"code~:{RIFT_NUMBER}",
            f"set code: {glued!r} reports `code~:`, so the report counts the model ignoring "
            "its own prompt rather than hiding it as an ordinary match",
        )

    # A MATCHING IDENTIFIER IS NEVER HANDED TO THE REPAIR, which is the ordering guarantee and
    # is stronger than any of the shape bounds: the repair runs only after a miss, so it cannot
    # move a card that was already joining. Red if `_repair_set_code` moves back into
    # `_key_printed_code`, where it used to live and where it rewrote every identifier on its
    # way to the lookup.
    rift_plain = rift_catalog.candidates(_rift(815, RIFT_NAME, RIFT_NUMBER))
    c.ok(
        rift_plain.lookup == f"code:{RIFT_NUMBER}",
        "set code: an identifier that matches is reported as a plain `code:` match, unrepaired",
    )

    # THE TWO SHAPE BOUNDS ARE ASSERTED ON THE FUNCTION, NOT THROUGH THE LADDER, AND THAT IS
    # FORCED RATHER THAN LAZY. `_repair_set_code` is reached only after a key MISSES, so a real
    # cell like `P-044` or `T02 // T03` never reaches it at all — a catalog-level case over
    # either one passes whatever the bounds say. Both were written that way first and observed
    # passing against a deliberately broken rule, which is the shape of assertion this file
    # refuses. What the bounds actually protect is the narrow case the ordering cannot: a read
    # that misses raw and whose over-eager repair lands on a real row belonging to another card.
    #
    #   at least two letters   One Piece prints 16 cells as `P-044` — ONE letter, a hyphen,
    #                          digits. At a bound of one, a missed `P-<digits>` read repairs to
    #                          a bare number that is a different card's identifier.
    #   letters only           `T02 // T03` is a real double-sided token, 13 cells carry the
    #                          form, and the prompt asks for the spaces around the `//` by name.
    #                          Digits in the prefix token would make its first half a set code.
    for intact in ("P-044", "T02 // T03", "056/298", "066a/298", "303*/298", "SP3/006", "R04"):
        c.equal(
            join._repair_set_code(intact),
            None,
            f"set code: {intact!r} is a real identifier shape and is left ENTIRELY alone",
        )
    for glued, bare in (
        ("UNL \u2022 056/298", "056/298"),
        ("UNL \u00b7 080/219", "080/219"),
        ("UNL - 150/219", "150/219"),
        ("UNL / 120/219", "120/219"),
        ("UNL-150/219", "150/219"),
    ):
        c.equal(
            join._repair_set_code(glued),
            bare,
            f"set code: {glued!r} gives up its prefix and nothing else",
        )

    # ---------------------------------------------------------------- D67: the same shape, read
    # by a SCREEN. `strip_set_code` is the published rule and `_repair_set_code` is now a reader
    # of it, so the two can no longer drift — the case below is what would go red if a second
    # regex appeared. It is asserted in BOTH directions on purpose: the repair still answers None
    # where nothing was removed (the ladder needs a candidate-or-nothing) and the strip still
    # answers the string (a screen needs something to draw).
    for intact in ("P-044", "T02 // T03", "056/298", "SP3/006", "R04"):
        c.equal(
            join.strip_set_code(intact),
            intact,
            f"D67: {intact!r} is a real identifier and the display strip leaves it alone",
        )
        c.equal(
            join._repair_set_code(intact),
            None,
            f"D67: and the ladder's reader of the same shape still answers None for {intact!r}",
        )
    for glued, bare in (
        ("UNL \u2022 198/219", "198/219"),
        ("UNL \u00b7 080/219", "080/219"),
        ("UNL - 150/219", "150/219"),
        ("UNL / 120/219", "120/219"),
    ):
        c.equal(
            join.strip_set_code(glued),
            bare,
            f"D67: {glued!r} is drawn as {bare!r} — one shape rule, two readers",
        )

    # THE COMPOSITION, AND THE HALF THAT COST A QUARTER OF THE STORE. `printed_total` arrives as
    # `""` on 174 of the owner's 676 numbered records — every Riftbound card, which prints one
    # identifier and has no denominator — and the two client copies of this tested it for `null`
    # alone, one line below testing `number` for null OR blank. Those rendered `198/219/`.
    # The first case here is red against that spelling; the rest hold the shape around it.
    for number, total, drawn in (
        ("198/219", "", "198/219"),
        ("198/219", None, "198/219"),
        ("UNL \u2022 198/219", "", "198/219"),
        ("025", "132", "025/132"),
        ("  025  ", " 132 ", "025/132"),
        ("161", "159", "161/159"),
        ("", "132", None),
        (None, "132", None),
        ("  ", None, None),
    ):
        c.equal(
            join.display_number(number, total),
            drawn,
            f"D67: {number!r} + {total!r} is drawn as {drawn!r}",
        )

    # NO `zfill`, WHICH IS THE ONE THING THIS MUST NOT BORROW FROM ITS NEIGHBOUR. `join_key`
    # pads to three digits because the export's `Number` column is padded; the same string on a
    # screen would be a number nothing in the run ever said.
    c.equal(
        (join.display_number("25", "132"), join.join_key("25", "132")),
        ("25/132", "025/132"),
        "D67: the display form and the key form of one card differ, and both are correct",
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

    _check_near_mint_candidates(c)

    return c.result()


def _near_mint_row(sku: str, set_name: str, condition: str) -> dict:
    """A `tcgcsv.Row`-shaped dict carrying only the three columns
    `cli/resolve.py:_near_mint_candidates` reads. `Product Name`/`Number` are irrelevant to
    that function and are left out on purpose, so a future read of a field this fixture does
    not carry fails loudly rather than passing on an accidental default."""
    return {
        tcgcsv.SKU_COLUMN: sku,
        tcgcsv.SET_COLUMN: set_name,
        tcgcsv.CONDITION_COLUMN: condition,
    }


def _check_near_mint_candidates(c: Checks) -> None:
    """docs/specs/card-variants.md section 3b: the review queue's own candidates narrowed to
    Near Mint (D12, D137), through `cli/resolve.py:_near_mint_candidates` /
    `pipeline/games.py:near_mint_conditions` — never a fourth inline copy of the condition
    set.

    THE REAL SHAPE, REPRODUCED. Measured read-only against the owner's store: the widest
    open `set_ambiguous` entry (`4/102`, 2026-09-11) is 15 rows — two SKUs of one promo
    print, five conditions each, plus five more of a third SKU under `Unleashed` — and
    narrows to exactly 3, one per SKU, when this filter runs. This fixture reproduces that
    multiplicity (3 SKUs by 5 conditions, two of them sharing one `Set Name` string) rather
    than a tidier 3-sets-3-rows shape that would not exercise the same collapse.
    """
    c.note("")
    c.note("NEAR MINT CANDIDATES — cli/resolve.py:_near_mint_candidates (section 3b)")

    conditions = ("Near Mint Foil", "Lightly Played Foil", "Moderately Played Foil",
                  "Heavily Played Foil", "Damaged Foil")
    wide = []
    for sku_base, set_name in (("A", "Riftbound Organized Play Promotional Cards"),
                                ("B", "Riftbound Organized Play Promotional Cards"),
                                ("C", "Unleashed")):
        for i, condition in enumerate(conditions):
            wide.append(_near_mint_row(f"{sku_base}{i}", set_name, condition))

    narrowed = resolve._near_mint_candidates(wide, "riftbound")
    c.equal(len(narrowed), 3, "15 candidates narrow to 3 — one per SKU, all off-grade rows gone")
    c.equal(
        {row[tcgcsv.CONDITION_COLUMN] for row in narrowed},
        {"Near Mint Foil"},
        "every surviving row is the game's own Near Mint string",
    )
    c.equal(
        {row[tcgcsv.SET_COLUMN] for row in narrowed},
        {"Riftbound Organized Play Promotional Cards", "Unleashed"},
        "DROPS CONDITIONS, NEVER SETS — both `Set Name` strings the wide list carried are "
        "still present; no printing left the choice, only the play-grade rows of each one",
    )
    c.equal(
        {row[tcgcsv.SKU_COLUMN] for row in narrowed},
        {"A0", "B0", "C0"},
        "and the specific SKU kept from each group of five is its own Near Mint row, not "
        "an arbitrary survivor",
    )

    # THE OTHER CASE: every candidate off-grade. Filtering would leave zero rows to answer
    # over a photograph the operator is looking at, which is worse than a wide list — a wide
    # list is at least answerable. `_near_mint_candidates` must return every row unchanged.
    #
    # MEASURED UNREACHABLE ON THE OWNER'S STORE: read-only against the real store, 124
    # review/parked entries first seen in 2026-09 carry at least one off-grade candidate —
    # `set_ambiguous` 61, `detected_finish_not_stocked` 33, `ambiguous_no_signal` 20,
    # `rarity_claim_mismatch` 10 — and NONE of the 124 would be emptied; every one keeps at
    # least one Near Mint row. That makes this arm untested by any real entry today, which
    # is exactly why it needs a fixture rather than a trust: a branch nobody can reach still
    # has to be correct.
    all_off_grade = [
        _near_mint_row("X0", "Vendetta", "Lightly Played"),
        _near_mint_row("X1", "Vendetta", "Moderately Played"),
        _near_mint_row("X2", "Vendetta", "Damaged"),
    ]
    kept = resolve._near_mint_candidates(all_off_grade, "riftbound")
    c.equal(
        kept,
        all_off_grade,
        "an entry whose every candidate is off-grade keeps them all, unchanged and in "
        "order — an unanswerable entry is worse than a wide one",
    )
