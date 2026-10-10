"""T7 group: emit, pricing authority, prices and readings adopt, caps, live reconcile.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import contextlib
import json
import http.server
import os
import shutil
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import envfile

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Tuple
from harness.tests import Checks
from cli import cmd_reconcile, runs
from identify import cost
from pipeline import corpus, join, merge, pricing, selection, tcgcsv
from server import capture_server, pipeline_routes, send_routes
from store import files, master
# `readings` above is already `pipeline.readings` — the walk. This is the store-side
# table module (`KIND_RUN`/`KIND_LIVE`), aliased for the same reason.
from store import readings as store_readings
from store.session import Store
from harness.tests.t7.common import (
    ARTICUNO_SKU,
    DUNSPARCE_REVERSE_SKU,
    DUNSPARCE_SKU,
    FIXTURE_EXPORT,
    JPEG,
    QuietHandler,
    REPO_ROOT,
    _live_export_bytes,
    _spawn_server,
    capture_payload,
    command,
    error_code,
    error_message,
    fake_cid,
    identifications_for,
    isolated_home,
    quiet,
    request,
    seam_run,
    write_export,
)


def check_emit_claim_decides(checks: Checks) -> None:
    """`join` and `emit` re-derive ONE answer for a contradicted claim, and it is the claim's SKU.

    REDUCED FROM `check_emit_bypass` ON 2026-09-02, when D3's amendment retired `--bypass`.
    That case guarded a seam: `emit` re-derives the run rather than reading it, and for six
    days it re-derived with rung 3 live over a run joined with the flag — inventing a queued
    position for every bypassed card, finding none of them on disk, and refusing with *"Run
    `banchi join` first"* at an operator who had (measured on the owner's box 1: 39 of 39).
    The fix read the flag off the manifest. The amendment deletes the flag, so there is nothing
    left for `emit` to forget; what remains to assert is that the two commands still agree,
    and agree on the CLAIM's row rather than the photograph's.

    THE ASSERTION IS THE OUTPUT AND NOT THE EXIT CODE, for the reason the old case gave: the
    refusal was the second-worst outcome, and had the check passed with the wrong resolution
    the card would have been routed to review and left out of the CSV. So the contradicted
    card must be IN the file, at the SKU its claim names, and NOT at the one detection read.

    Its own isolated home, this file's own lesson yet again: it emits, which writes `pushed`
    counts that `check_listing_commands` and `check_cli_seams` assert over their own fixtures.
    """
    checks.note("")
    checks.note("EMIT, CLAIM DECIDES — join and emit re-derive one answer, and it is the claim's")

    # Dunsparce 120/159 stocks two condition rows, so a claim of `normal` is a claim the
    # catalog cannot settle on its own, and a `reverse_holo` read is the photograph
    # disagreeing with it — the exact shape D3's retired cross-check used to review. A
    # holofoil-only number could not produce the case.
    cards = [(3, 1, "Dunsparce", "120", "normal")]

    with isolated_home():
        for box, index, *_ in cards:
            while Store().read().inventory.next_index(box) <= index:
                capture_server.do_capture(capture_payload(box))

        run_dir = runs.create("t7-claim-decides")
        payload = identifications_for(cards)
        # THE CLAIM AND THE DETECTION MUST DISAGREE, and `identifications_for` sets both from
        # one field by design — a null finish is its rung-2 case. Patched here rather than by
        # widening that helper, because every other block in this file wants the agreeing shape.
        payload["cards"][master.position_key(3, 1)]["identification"]["finish"] = "reverse_holo"
        run_dir.write_identifications(payload)
        export = write_export(run_dir.path("export.csv"))

        command(checks, "join", str(run_dir.directory), "--export", str(export))
        run_dir = runs.open_run(run_dir.directory)

        snapshot = Store().read()
        checks.equal(
            (len(snapshot.review.entries), len(snapshot.parked.entries)),
            (0, 0),
            "A CONTRADICTED CLAIM IS QUEUED NOWHERE — the photograph may no longer put a "
            "claimed card in front of a human (D3, amended 2026-09-02)",
        )

        said = command(checks, "emit", str(run_dir.directory))
        checks.ok(
            "REFUSING to write" not in said,
            "`emit` DOES NOT REFUSE: it re-derives the identical resolution join wrote, "
            "because there is no per-run flag left for it to forget",
        )

        # GUARDED, because the failure this case exists for is a REFUSAL — and a refusal
        # writes no file, so reading one unconditionally turns a clean red line into a
        # traceback that hides every check behind it. `answers()` above states the same rule.
        listed = run_dir.path(runs.IMPORT_MERGED)
        written = (
            {row[tcgcsv.SKU_COLUMN] for row in tcgcsv.read_export(listed).rows}
            if listed.is_file()
            else set()
        )
        checks.ok(
            listed.is_file(),
            "an import file EXISTS at all — the refusal wrote nothing, so this is what a "
            "regression looks like before any SKU can be asserted about",
        )
        checks.ok(
            DUNSPARCE_SKU in written,
            "AND THE CARD IS IN THE FILE AT THE SKU ITS CLAIM NAMES. This is the assertion "
            "that matters: a resolution that merely stopped refusing could still have routed "
            "the card to review and left it out of the CSV — the claim void at the one step "
            "that writes",
        )
        checks.ok(
            DUNSPARCE_REVERSE_SKU not in written,
            "and NOT at the finish detection read. The rule is one line — detection may not "
            "contradict a claim — so the claim decides, and rung 3's other job, choosing "
            "inside a multi-member claim, is untouched",
        )


def check_emit_identity_stamp(checks: Checks) -> None:
    """The live cap bounds the LISTING. Every copy the run matched gets its identity.

    THE DEFECT, FOUND BY THE OWNER ON THEIR OWN STORE. `cli/cmd_emit.py` wrote the SKU inside
    a loop over `match.live_positions` — `uncommitted_positions[:add_to_quantity]`, bounded by
    D7's `live_cap` of 4 — so the fifth copy of anything was left wearing `sku: null`. D7 caps
    how many copies may be LIVE, on the envelope-buster and stale-price arguments it gives; it
    has never said anything about how many copies we know the name of, and the owner's note on
    finding this says so in as many words: *"this was supposed to be just a gentle heads up to
    only list four as a default mainly for cheap cards, it wasn't supposed to take the shape
    it's taken now"*.

    Measured on their store: Rengar, Trophy Hunter (9189797, $30.81) holds SEVEN copies at
    3/1, 3/2, 3/4, 3/17, 3/20, 3/30 and 3/36. Four carry the SKU. The three that do not are
    invisible to `GET /search`, to `copies_on_hand` and to `positions_for_sku` — so the screen
    reported four on hand for a card the owner has seven of, and the invisible three are the
    most valuable cards in the box.

    THE SECOND HALF IS WHAT KEEPS THE FIX FROM BEING WORSE THAN THE BUG. The obvious repair is
    to iterate `match.positions`, and it would destroy data: `cli/resolve.py` marks a copy
    committed on either of two grounds, a count read off the `Listing` or the copy being in a
    TERMINAL state, so every sold and retired copy of a matched SKU is in `positions`. Eight of
    the box-3 run's 33 matched positions are sold today. `set_state` has no terminal guard, so
    a re-emit would have moved all eight back to `identified` — D10's permanent gap and D26's
    terminal state both gone, silently. `uncommitted_positions` is the honest set and cannot
    contain a departed card by construction.

    Its own isolated home, this file's own lesson again: it emits, which writes `pushed` counts
    that `check_listing_commands` and `check_cli_seams` assert over their own fixtures.
    """
    checks.note("")
    checks.note("EMIT IDENTITY — the cap bounds the listing, not the identity")

    # Articuno 161/159 is holofoil-only, so the catalog settles it on its own (D3 rung 2) and
    # no capture toggle is needed to make seven copies resolve to one SKU. SEVEN because the
    # cap is four: it is the smallest count that puts copies on both sides of it and matches
    # the shape the owner actually found.
    copies = 7
    cards = [(3, i, "Articuno", "161", None) for i in range(1, copies + 1)]

    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        # THE SEND NAMES THE CAP, because the store no longer can (D7, amended
        # 2026-09-08). This case is about the cap arithmetic, so it asks for one.
        command(checks, "emit", str(run_dir.directory), "--cap", "4")

        inventory = Store().read().inventory
        stamped = [
            c.index
            for c in inventory.positions_for_sku(ARTICUNO_SKU)
        ]
        checks.equal(
            stamped,
            list(range(1, copies + 1)),
            "EVERY MATCHED COPY CARRIES THE SKU, not the first `live_cap` of them. This is "
            "the assertion the defect fails: it stamped 1-4 and left 5, 6 and 7 null, which "
            "is a copy no SKU-keyed surface can see rather than backstock in D7's sense",
        )
        checks.equal(
            len(inventory.copies_on_hand(ARTICUNO_SKU)),
            copies,
            "so the SKU -> positions map D7 promises is COMPLETE. `copies_on_hand` selects on "
            "`card.sku`, so an unstamped copy was missing from the count the screen draws and "
            "from the set `cli/resolve.py:_committed_keys` slices to size the next join",
        )

        listing = Store().read().inventory.listings[ARTICUNO_SKU]
        checks.equal(
            listing.pushed,
            join.LIVE_QUANTITY_CAP,
            "AND THE CAP STILL HOLDS. `pushed` is a commitment that a CSV row was written, so "
            "it counts `live_positions` and nothing else — the stamp runs over a wider set now "
            "and a shared increment would push the count past `add_to_quantity` and "
            "double-stage on the next import",
        )
        listed = run_dir.path(runs.IMPORT_MERGED)
        rows = [
            row
            for row in tcgcsv.read_export(listed).rows
            if row[tcgcsv.SKU_COLUMN] == ARTICUNO_SKU
        ]
        checks.equal(
            [row[tcgcsv.QUANTITY_COLUMN] for row in rows],
            [str(join.LIVE_QUANTITY_CAP)],
            "and the import file asks for exactly the cap, on ONE row. The file is what D7's "
            "cap is actually about, and it must not move because more copies got a name",
        )

        # --------------------------------------------------------- and a departed copy stays gone
        capture_server.do_mark_sold(3, 1, {})
        checks.equal(
            Store().read().inventory.get(master.position_key(3, 1)).state,
            master.SOLD,
            "a copy is sold — the setup for the assertion below, stated so a failure here "
            "cannot be misread as the re-emit having done it",
        )

        # THE SEND NAMES THE CAP (D7, amended 2026-09-08): this case asserts cap
        # arithmetic, and the store cannot hold a standing figure any more.
        command(checks, "emit", str(run_dir.directory), "--cap", "4", exits=1)
        after = Store().read().inventory
        checks.equal(
            after.get(master.position_key(3, 1)).state,
            master.SOLD,
            "A RE-EMIT DOES NOT RESURRECT A SOLD COPY. This is the case that fails against the "
            "obvious fix: `match.positions` holds every terminal copy of a matched SKU, and "
            "`set_state` has no terminal guard, so iterating it would move this card back to "
            "`identified` and take D10's permanent gap with it",
        )
        checks.equal(
            after.listings[ARTICUNO_SKU].pushed,
            join.LIVE_QUANTITY_CAP,
            "and the re-emit adds nothing (D54). The copies it already sent are `committed` "
            "now, so they are not in `uncommitted_positions` at all — the idempotence lives "
            "in `_committed_keys`, which reads the `Listing` and never `card.sku`",
        )


def check_pricing_authority(checks: Checks) -> None:
    """`decisions.json` decides the price, and `join` may not take that decision back.

    TWO BUGS IN ONE SEAM, BOTH FOUND BY READING THE COMMANDS RATHER THAN THE TESTS, AND BOTH
    INVISIBLE TO EVERY CHECK IN THIS REPO ON THE DAY THEY WERE FOUND.

    The first: `cli/cmd_emit.py` resolved with `run_dir.manifest.get("rule")` and then printed
    `choice.describe` off `decisions.json`, so an operator who set `"rule": "undercut:5"` in the
    file got a run that PRINTED `rule=undercut:5` and priced every row at market. `pipeline/
    decisions.py`'s own docstring calls that file *"the pricing decision, as a file rather than
    as a flag"*, and it was the one thing in it that decided nothing.

    The second is worse because it destroys work: `cli/cmd_join.py` assigned `choice.rule` and
    `choice.basis` back from the run immediately after printing *"merging into existing
    decisions.json — your edits are kept"*. `join` is free and re-runnable and is re-run
    routinely, so an edited rule survived until the next join and then silently was not there.

    T5 asserts `decisions.json` CARRIES a rule and passed throughout — carrying it
    was never the question. These cases assert that it REACHES A PRICE, which is a fact about
    the command seam and belongs here.

    Its own isolated home, which is this file's own lesson three times over: these cases emit,
    which writes `pushed` counts that `check_listing_commands` and `check_cli_seams` both
    assert over their own fixtures.
    """
    checks.note("")
    checks.note("PRICING AUTHORITY — the corpus decides, the run records")

    cards = [(3, 1, "Articuno", "161", None)]

    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        path = files.prices_path()
        checks.ok(
            path.is_file(),
            "a first join writes the CORPUS and not a per-run answer file (D86, amended). "
            "The answer left the run directory because a price is a fact about a SKU: stored "
            "per run, one card carried one answer per box it had ever been photographed in — "
            "measured on the owner's store, 66 SKUs with 8 answered twice, 3 of those a hold "
            "overridden by a later price",
        )
        checks.ok(
            not run_dir.path(runs.DECISIONS).exists(),
            "and the run directory carries NO decisions.json — a second copy is the thing "
            "this move exists to delete, so writing one as a record would put it back",
        )
        seeded = json.loads(path.read_text())
        checks.equal(
            (seeded["policy"]["rule"], seeded["policy"]["basis"]),
            ("match", "market"),
            "the corpus SEEDS from the run's own flags when it is empty — `--rule` is how "
            "pricing starts, and a file with no rule in it would be a document that cannot "
            "answer the question it exists to ask",
        )

        # The market price this SKU is about to be priced from, read off the run's own export
        # rather than written here: a literal would go on passing if the fixture moved.
        export = tcgcsv.read_export(run_dir.path("export.csv"))
        market = export.by_sku()[ARTICUNO_SKU][tcgcsv.MARKET_PRICE_COLUMN]

        seeded["policy"]["rule"] = "markup:100"
        seeded["policy"]["sub_threshold"] = "floor"
        path.write_text(json.dumps(seeded))

        said = command(checks, "emit", str(run_dir.directory))
        written = {
            row[tcgcsv.SKU_COLUMN]: row[tcgcsv.PRICE_COLUMN]
            for row in tcgcsv.read_export(run_dir.path(runs.IMPORT_MERGED)).rows
        }
        checks.equal(
            written.get(ARTICUNO_SKU),
            tcgcsv.format_price(Decimal(market) * 2),
            "A RULE SET IN THE CORPUS REACHES THE EMITTED PRICE. `markup:100` doubles the "
            "market price into the import file — the whole content of the first bug, which "
            "priced at market while printing the rule it had been given",
        )
        checks.ok(
            "rule=markup:100" in said,
            "and the `pricing` line names the rule that was actually applied, which it did "
            "before this too — printing the file and pricing from the manifest is exactly how "
            "a wrong number stays invisible",
        )

    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        path = files.prices_path()
        edited = json.loads(path.read_text())
        edited["policy"]["rule"] = "undercut:5"
        edited["policy"]["basis"] = "low"
        edited["policy"]["sub_threshold"] = "floor"
        path.write_text(json.dumps(edited))

        command(
            checks, "join", str(run_dir.directory), "--export", str(run_dir.path("export.csv"))
        )
        after = json.loads(path.read_text())["policy"]
        checks.equal(
            (after["rule"], after["basis"], after["sub_threshold"]),
            ("undercut:5", "low", "floor"),
            "A RE-JOIN KEEPS THE EDITED RULE. Two assignments used to run immediately after "
            "the sentence promising it and reset exactly the two fields most likely to have "
            "been edited — measured, `markup:100` on `low` went back to `match` on `market` "
            "while `sub_threshold` beside it survived, so the file looked merged and was not",
        )
        checks.equal(
            run_dir.manifest.get("rule"),
            "match",
            "THE MANIFEST STILL RECORDS WHAT THE JOIN RAN WITH, and it is deliberately NOT the "
            "edited value: a record of what happened is a different thing from the answer, "
            "`report.txt` prints this one, and only one of the two may be authoritative",
        )

    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        path = files.prices_path()
        path.write_text(
            json.dumps({"policy": {"rule": "undercut:not-a-number", "sub_threshold": "floor"}})
        )
        from cli import __main__ as entry

        for argv, label in (
            (
                ["emit", str(run_dir.directory)],
                "emit refuses a rule outside the enum with a SENTENCE rather than a traceback",
            ),
            (
                [
                    "join",
                    str(run_dir.directory),
                    "--export",
                    str(run_dir.path("export.csv")),
                ],
                "and so does join — `UnknownRule` is a ValueError and NOT a "
                "`MalformedDecisions`, nothing above `cli/__main__.py` caught it, and the "
                "route that writes this document validates nothing, so a screen can reach "
                "every one of these states",
            ),
        ):
            with quiet() as said:
                code = entry.main(argv)
            checks.equal(
                (code, "is unusable" in said.getvalue()),
                (1, True),
                label,
            )


def check_threshold_and_file_shape(checks: Checks) -> None:
    """The stored D9 cut-off, and how many spreadsheets one press writes.

    TWO CHANGES, ONE SEAM, WHICH IS WHY THEY ARE ASSERTED TOGETHER. The threshold decides
    which bucket a card is in; the flag decides whether the buckets are two files or one. A
    case that moved a card across the cut-off without looking at the file it landed in would
    not have checked the thing the operator sees.

    THE CUT-OFF IS `pipeline/corpus.py`'s `policy.threshold` and D9 has always called it
    configurable — `pipeline/pricing.py:THRESHOLD` was a module constant no flag, env var or
    document could reach, which is exactly the shape D10's `CARDS_PER_SECTION` was deleted
    for. The default is unchanged, so a store that never sets one partitions as it always did.

    THE FIXTURE STRADDLES THE FIGURE ON PURPOSE: Dunsparce is $2.06 and Articuno is $22.03,
    so a cut-off of $5.00 puts exactly one of them on each side and a partition that ignored
    the stored value would put both on the same one.
    """
    checks.note("")
    checks.note("THRESHOLD POLICY — the stored cut-off, and one file or two")

    cards = [
        (3, 1, "Dunsparce", "120", "normal"),
        (3, 2, "Articuno", "161", None),
    ]

    # --- the default: one spreadsheet, both buckets in it ---------------------------------
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        book = corpus.Corpus.read()
        # THIS CHECK ONCE ASSERTED THE D9 CONSTANT, AND THE PROMISE IT GUARDED WAS GIVEN UP ON
        # PURPOSE. D99's first build said a store that had set no threshold would partition
        # exactly as it did yesterday, and that was true while the threshold was the only figure
        # with a default. It stopped being true when D9's amendment gave `sub_threshold` a
        # default of flat $0.49 beside a threshold still reading $0.40: a store that had chosen
        # NEITHER then partitioned at one price and sold the half below it at another, so a
        # $0.38 card listed above a $0.42 one. The owner's ruling is that the two are one
        # variable, so the fallback is one figure and both keys read it.
        #
        # What that costs is written here rather than left to be discovered: an existing store
        # that never set a threshold now partitions at $0.49 instead of $0.40, and cards between
        # the two figures move from the listed half to the cheap half on the next join. Cards,
        # not money — each of them still goes out at $0.49 either way, because that is what the
        # cheap half has been priced at since the amendment.
        checks.equal(
            book.policy_for()["threshold"],
            corpus.DEFAULT_CUTOFF,
            "a corpus nobody has set a cut-off on reads ONE default for both keys, so it can "
            "never partition at one figure and sell the half below it at another",
        )
        checks.equal(
            book.policy_for()["sub_threshold"],
            {"flat": corpus.DEFAULT_CUTOFF},
            "and the cheap-card answer it falls back to IS that figure — the pair cannot "
            "invert unless somebody writes them apart deliberately",
        )
        book.threshold = "5.00"
        book.sub_threshold = "floor"
        book.write()

        said = command(checks, "emit", str(run_dir.directory))
        checks.equal(
            sorted(path.name for path in run_dir.directory.glob("import*.csv")),
            [runs.IMPORT_MERGED],
            "ONE PRESS, ONE SPREADSHEET. The owner's instruction was that emit *\"should now "
            "emit only one spreadsheet by default\"*, and this run holds a card on each side "
            "of the cut-off — the shape that used to write two files",
        )
        merged = tcgcsv.read_export(run_dir.path(runs.IMPORT_MERGED)).by_sku()
        checks.equal(
            sorted(merged),
            sorted([DUNSPARCE_SKU, ARTICUNO_SKU]),
            "and the one file carries both sides — the listed card and the sub-threshold "
            "one, which is what merging the buckets means",
        )
        checks.equal(
            merged[DUNSPARCE_SKU][tcgcsv.PRICE_COLUMN],
            tcgcsv.format_price(Decimal("5.00")),
            "THE $2.06 CARD WAS PRICED BY THE SUB-THRESHOLD DISPOSITION, which is the proof "
            "the stored $5.00 reached the partition: at the $0.49 default this row is "
            "listable and would carry its own market price instead",
        )
        # AND THE FIGURE IS THE STORE'S, NOT `pricing.FLOOR` (D9, amended 2026-09-09). This
        # asserted `$0.40` until that amendment, which is the same defect one register along
        # from the one it was written for: a stored `"floor"` answer resolved at the module
        # constant while the store's own cut-off said something else, so a store set BELOW
        # $0.40 listed its cheapest cards ABOVE the price its mid cards went out at. D9
        # retired `"floor"` as an answer anybody may choose on the ground that a sub-threshold
        # price must not track *"a figure that moves for a different reason"* — and the floor no
        # longer moves for a different reason, because it is the cut-off. `"floor"` and the
        # default `{"flat": <cut-off>}` are the same answer now, which is why this is coherent
        # rather than a reopening.
        checks.ok(
            merged[DUNSPARCE_SKU][tcgcsv.PRICE_COLUMN] != tcgcsv.format_price(pricing.FLOOR),
            "and it is NOT the module constant — a `\"floor\"` answer resolves at the store's "
            "own cut-off, so the cheap half can never go out above the listed half's floor",
        )
        checks.ok(
            "import           2 row(s)" in said,
            "and the command names the one file it wrote",
            said,
        )

    # --- the same run at the default cut-off, which is the control ------------------------
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        command(checks, "emit", str(run_dir.directory))
        merged = tcgcsv.read_export(run_dir.path(runs.IMPORT_MERGED)).by_sku()
        checks.equal(
            merged[DUNSPARCE_SKU][tcgcsv.PRICE_COLUMN],
            tcgcsv.format_price(Decimal("2.06")),
            "AT $0.40 THE SAME CARD IS LISTED AT MARKET, and no sub-threshold answer was "
            "needed to emit at all — the row moved buckets because the figure moved, and "
            "nothing else about the run changed",
        )

    # --- `--split-threshold` puts the pair back -------------------------------------------
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        book = corpus.Corpus.read()
        book.threshold = "5.00"
        book.sub_threshold = "floor"
        book.write()
        command(checks, "emit", str(run_dir.directory), "--split-threshold")
        checks.equal(
            sorted(path.name for path in run_dir.directory.glob("import*.csv")),
            sorted([runs.IMPORT_LISTED, runs.IMPORT_SUBTHRESHOLD]),
            "--split-threshold writes the old pair, under the old names — an operator who "
            "wants the valuable cards staged apart from the bulk gets the files they used "
            "to get, not a differently-named approximation of them",
        )
        checks.equal(
            (
                [
                    row[tcgcsv.SKU_COLUMN]
                    for row in tcgcsv.read_export(run_dir.path(runs.IMPORT_LISTED)).rows
                ],
                [
                    row[tcgcsv.SKU_COLUMN]
                    for row in tcgcsv.read_export(
                        run_dir.path(runs.IMPORT_SUBTHRESHOLD)
                    ).rows
                ],
            ),
            ([ARTICUNO_SKU], [DUNSPARCE_SKU]),
            "and the STORED cut-off decides which file each card lands in, which is the "
            "whole of what threading it to the emitter was for",
        )
        listing = Store().read().inventory.listing_for(DUNSPARCE_SKU)
        checks.equal(
            listing.pushed,
            1,
            "THE CAP IS SPENT ONCE ACROSS EVERYTHING THE PRESS WROTE, not once per file. "
            "`add_to_quantity` is per SKU and a SKU is in exactly one bucket, so splitting "
            "the rows across two files cannot double what reaches `pushed`",
        )

    # --- and a threshold nobody can read is a sentence, not a traceback -------------------
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        path = files.prices_path()
        document = json.loads(path.read_text())
        document["policy"]["threshold"] = "free"
        path.write_text(json.dumps(document))
        from cli import __main__ as entry

        with quiet() as said:
            code = entry.main(["emit", str(run_dir.directory)])
        text = said.getvalue()
        checks.equal(
            (code, "is unusable" in text and "'free'" in text),
            (1, True),
            "an unusable threshold refuses by name. `InvalidThreshold` is a ValueError and "
            "NOT a `MalformedDecisions` — the same shape D86 already paid for twice with "
            "`UnknownRule` and `UnknownBasis`, and nothing above `cli/__main__.py` catches "
            "one, so the catch has to name it",
        )
        checks.ok(
            not list(run_dir.directory.glob("import*.csv")),
            "and nothing was written",
        )


def check_prices_adopt(checks: Checks) -> None:
    """`banchi prices adopt` folds, RETIRES, and the two commands refuse until it has (D86, amended).

    THE REFUSAL WAS GATED ON AN EMPTY CORPUS, AND ON THE OWNER'S STORE EIGHT FILES SAT BEHIND
    IT. `join` and `emit` refused a run carrying `decisions.json` only while `inventory/
    prices.json` held no answers — so from the first adoption onward every legacy file was
    silently ignored, while CLAUDE.md and D86 described an unconditional refusal. And `adopt`
    itself refused to run a second time without `--force`, whose implementation folded the run
    files into a FRESH corpus — every answer written on `#/pricing` since the first fold would
    have gone with it.

    These cases pin the shape that replaces it: the guard is unconditional and fires before
    anything is read or written; `adopt --write` retires each folded file to
    `decisions.json.adopted`; a re-adopt keeps the corpus's answers and retires the files
    without `--force`; `--force` folds OVER the corpus and names the hold it costs; and the
    sub-threshold disposition has a standing default (D9, amended 2026-09-02) so a fresh
    store's first emit is not refused for want of it.

    Its own isolated home per case, for this file's usual reason: emit writes `pushed`.
    """
    from cli import __main__ as entry

    checks.note("")
    checks.note("PRICES ADOPT — fold, retire, and refuse until then")

    cards = [(3, 1, "Articuno", "161", None)]
    older_doc = {
        "sub_threshold": {"flat": ".5"},
        "overrides": {ARTICUNO_SKU: {"withheld": "bullish"}},
    }
    newer_doc = {
        "sub_threshold": "floor",
        "overrides": {ARTICUNO_SKU: "3.45"},
        "no_market_data": {DUNSPARCE_SKU: "1.00"},
    }

    def legacy_run(document: dict):
        made = runs.create("t7-legacy")
        path = made.directory / runs.DECISIONS
        path.write_text(json.dumps(document, indent=2) + "\n", "utf-8")
        return made, path.read_bytes()

    # ---------------------------------------------------------- (1) the first adoption
    with isolated_home():
        older, older_bytes = legacy_run(older_doc)
        newer, newer_bytes = legacy_run(newer_doc)

        preview = command(checks, "prices", "adopt")
        checks.ok(
            "DRY RUN" in preview
            and str(older.directory / runs.DECISIONS) in preview.split("would retire", 1)[-1]
            and preview.count("would retire") == 2,
            "the preview says DRY RUN and names BOTH files under `would retire` — what will "
            "leave the run directory is written down before it moves",
            preview,
        )
        checks.ok(
            (older.directory / runs.DECISIONS).is_file()
            and (newer.directory / runs.DECISIONS).is_file()
            and not files.prices_path().exists(),
            "and the preview moved nothing: both files where they were, no corpus written",
        )

        said = command(checks, "prices", "adopt", "--write")
        book = corpus.Corpus.read()
        checks.equal(
            (
                book.answers[ARTICUNO_SKU].value,
                book.answers[DUNSPARCE_SKU].value,
                book.answers[DUNSPARCE_SKU].channel,
                book.sub_threshold,
            ),
            ("3.45", "1.00", "unknown", "floor"),
            "newest wins: the later price over the earlier hold, the no-market-data answer "
            "on its own channel, and the policy from the newest run that stated one",
        )
        checks.ok(
            "A HOLD WAS REPLACED BY A PRICE" in said and ARTICUNO_SKU in said,
            "and the hold that lost is NAMED, in as many words — the direction that cost money",
            said,
        )
        checks.ok(
            not (older.directory / runs.DECISIONS).exists()
            and not (newer.directory / runs.DECISIONS).exists()
            and (older.directory / runs.DECISIONS_ADOPTED).read_bytes() == older_bytes
            and (newer.directory / runs.DECISIONS_ADOPTED).read_bytes() == newer_bytes
            and "retired" in said,
            "`--write` RETIRES each folded file to `decisions.json.adopted`, byte for byte — "
            "the run keeps the record it was priced with, under a name nothing refuses on",
            said,
        )

    # ------------------------------------------ (2) a re-adopt keeps the corpus's answers
    def answered_corpus():
        book = corpus.Corpus.read()
        book.answers["9999001"] = corpus.Answer(value="9.99")
        book.answers[ARTICUNO_SKU] = corpus.Answer(value={"withheld": "keeping"})
        book.write()

    third_doc = {
        "sub_threshold": {"flat": ".5"},
        "overrides": {ARTICUNO_SKU: "3.45", "9999002": "0.10"},
    }

    with isolated_home():
        legacy_run(older_doc)
        legacy_run(newer_doc)
        command(checks, "prices", "adopt", "--write")
        answered_corpus()
        third, _ = legacy_run(third_doc)

        said = command(checks, "prices", "adopt", "--write")
        book = corpus.Corpus.read()
        checks.equal(
            (
                book.answers[ARTICUNO_SKU].value,
                book.answers["9999001"].value,
                book.answers["9999002"].value,
                book.sub_threshold,
            ),
            ({"withheld": "keeping"}, "9.99", "0.10", "floor"),
            "WITHOUT `--force`, THE CORPUS KEEPS WHAT IT ALREADY ANSWERS: the hold set on "
            "#/pricing survives the file's price, a SKU in no file is untouched, a SKU the "
            "corpus never held is added, and the policy is not moved by the file's `.5`",
        )
        checks.ok(
            "kept" in said and ARTICUNO_SKU in said.split("kept", 1)[-1],
            "and the answer it kept is named under `kept`, with what the file said beside it",
            said,
        )
        checks.ok(
            not (third.directory / runs.DECISIONS).exists()
            and (third.directory / runs.DECISIONS_ADOPTED).is_file(),
            "the file is retired all the same — every SKU it answers is answered in the "
            "corpus, so it has nothing left to say",
        )
        with quiet() as again:
            code = entry.main(["prices", "adopt", "--write"])
        checks.equal(
            (code, "nothing to adopt" in again.getvalue()),
            (0, True),
            "a second `adopt --write` with no files left exits 0 and says so — the migration "
            "is re-runnable, which is what lets a session run it without checking first",
        )

    # ------------------------------------------------- (3) --force folds OVER the corpus
    with isolated_home():
        legacy_run(older_doc)
        legacy_run(newer_doc)
        command(checks, "prices", "adopt", "--write")
        answered_corpus()
        legacy_run(third_doc)

        said = command(checks, "prices", "adopt", "--write", "--force")
        book = corpus.Corpus.read()
        checks.equal(
            (book.answers[ARTICUNO_SKU].value, book.answers["9999001"].value),
            ("3.45", "9.99"),
            "`--force` lets the file win where the two differ, and a SKU in no file SURVIVES "
            "— the old `--force` folded into a fresh corpus and would have dropped it",
        )
        checks.ok(
            "A HOLD WAS REPLACED BY A PRICE" in said and ARTICUNO_SKU in said,
            "and the hold it cost is named — the corpus's own answer is the oldest entry in "
            "the history, so a price folded over a screen hold is reported as the loss it is",
            said,
        )

    # ------------------------------------------------------ (4) join refuses, early
    with isolated_home():
        run_dir, _ = seam_run(checks, cards, join=False)
        (run_dir.directory / runs.DECISIONS).write_text('{"rule": "match"}\n', "utf-8")
        argv = ["join", str(run_dir.directory), "--export", str(run_dir.path("export.csv"))]
        with quiet() as said:
            code = entry.main(argv)
        text = said.getvalue()
        after = Store().read()
        got = (
            code,
            "prices adopt --write" in text,
            "Nothing was joined" in text,
            bool(runs.open_run(run_dir.directory).manifest.get("joined")),
            len(after.review.entries) + len(after.parked.entries),
        )
        want = (1, True, True, False, 0)
        checks.ok(
            got == want,
            "JOIN REFUSES A LEGACY FILE UNCONDITIONALLY, NAMES THE COMMAND, AND HAS WRITTEN "
            "NOTHING when it says so — no `joined` in the manifest, nothing in either queue. "
            "The guard sat after the store write and fired only on an empty corpus before",
            f"expected: {want!r}\nactual:   {got!r}\n{text}",
        )
        command(checks, "prices", "adopt", "--write")
        with quiet() as said:
            code = entry.main(argv)
        checks.ok(
            code == 0,
            "and once the file is retired the same join exits 0",
            f"exit {code}\n{said.getvalue()}",
        )

    # ------------------------------------------------------- (5) emit refuses, per run
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        (run_dir.directory / runs.DECISIONS).write_text('{"rule": "match"}\n', "utf-8")
        with quiet() as said:
            code = entry.main(["emit", str(run_dir.directory)])
        text = said.getvalue()
        got = (
            code,
            "prices adopt --write" in text,
            "Nothing was written" in text,
            run_dir.path(runs.import_listed_name("pokemon")).exists(),
        )
        want = (1, True, True, False)
        checks.ok(
            got == want,
            "emit refuses the same file the same way, before any CSV exists",
            f"expected: {want!r}\nactual:   {got!r}\n{text}",
        )

    with isolated_home():
        first, _ = seam_run(checks, cards)
        second, _ = seam_run(checks, cards)
        (second.directory / runs.DECISIONS).write_text('{"rule": "match"}\n', "utf-8")
        with quiet() as said:
            code = entry.main(["emit", str(first.directory), str(second.directory)])
        text = said.getvalue()
        got = (code, second.name in text, "prices adopt --write" in text)
        want = (1, True, True)
        checks.ok(
            got == want,
            "THE MERGED EMIT REFUSES TOO, NAMING THE RUN THAT CARRIES THE FILE — the merged "
            "path had no guard at all, so a send of several runs walked straight past what "
            "a send of one refused",
            f"expected: {want!r}\nactual:   {got!r}\n{text}",
        )

    # -------------------------------------------- (6) the standing default, flat $0.49
    with isolated_home():
        run_dir, said = seam_run(
            checks, [(3, 1, "Dunsparce", "120", "normal")], market={DUNSPARCE_SKU: "0.12"}
        )
        policy = json.loads(files.prices_path().read_text())["policy"]
        checks.equal(
            policy["sub_threshold"],
            {"flat": "0.49"},
            "A FRESH CORPUS'S SUB-THRESHOLD POLICY IS FLAT $0.49 AFTER THE FIRST JOIN (D9, "
            "amended 2026-09-02): the default is applied on read and reaches the file on the "
            "join's own write, so nothing has to be pressed before the first emit",
        )
        checks.ok(
            "sub-threshold    flat at $0.49" in said and "EMIT WILL REFUSE" not in said,
            "the join names the standing disposition on its own line and stops nagging — "
            "`EMIT WILL REFUSE` fires for a genuinely blocking reason only",
            said,
        )
        before = files.prices_path().read_bytes()
        command(checks, "emit", str(run_dir.directory))
        # READ OUT OF THE MERGED FILE, WHICH IS WHERE ONE PRESS PUTS THE ROW (D99). This case
        # is about the sub-threshold PRICE, not about the file layout: it asserted
        # `import-subthreshold.csv` when it was written, because that was the only shape emit
        # had. The default became one `import.csv` with `--split-threshold` as the way back,
        # so the row moved file and the assertion did not change its subject —
        # `check_threshold_and_file_shape` above owns the layout question.
        written = {
            row[tcgcsv.SKU_COLUMN]: row[tcgcsv.PRICE_COLUMN]
            for row in tcgcsv.read_export(run_dir.path(runs.IMPORT_MERGED)).rows
        }
        checks.equal(
            (written.get(DUNSPARCE_SKU), files.prices_path().read_bytes() == before),
            ("0.49", True),
            "and emit prices the sub-threshold card at the default without touching the "
            "corpus — the answer was already there; emit only reads it",
        )

    # ------------------------------------- (7) every money figure the CLI prints has cents
    # THE CENT RULE, read the way the owner reads it. `corpus._token` compares an answer with
    # `Decimal.normalize`, and it also RENDERS with it, which strips trailing zeros: the adopt
    # report named a $18.50 answer as "$18.5" and a $1200.00 answer as "$1200". Every `$`
    # figure on a CLI line is money, so every one carries exactly two decimals.
    money_token = re.compile(r"\$-?[0-9][0-9,]*(?:\.[0-9]+)?")
    two_decimals = re.compile(r"\$-?[0-9][0-9,]*\.[0-9]{2}")

    def bare_money(text):
        return [tok for tok in money_token.findall(text) if not two_decimals.fullmatch(tok)]

    with isolated_home():
        legacy_run({"overrides": {ARTICUNO_SKU: "18.50", DUNSPARCE_SKU: "1200.00"}})
        legacy_run({"overrides": {ARTICUNO_SKU: "0.49", DUNSPARCE_SKU: "1199.99"}})
        said = command(checks, "prices", "adopt", "--write")
        checks.equal(
            bare_money(said),
            [],
            "the first adoption's kept and dropped rows print every price with two decimals — "
            "a $18.50 answer is `$18.50`, a $1200.00 answer is `$1200.00`, never `$18.5`/`$1200`",
        )
        checks.ok(
            "dropped $18.50 (" in said and "kept $1199.99 (" in said,
            "and the two figures the owner typed are the two figures the report names",
            said,
        )

    with isolated_home():
        legacy_run({"overrides": {ARTICUNO_SKU: "0.49"}})
        command(checks, "prices", "adopt", "--write")
        legacy_run({"overrides": {ARTICUNO_SKU: "18.50"}})
        said = command(checks, "prices", "adopt", "--write")
        checks.equal(
            bare_money(said),
            [],
            "a re-adopt's kept row prints the corpus's figure and the file's with two decimals",
        )
        checks.ok(
            "kept $0.49 (corpus) — file said $18.50" in said,
            "and the row reads `kept $0.49 (corpus) — file said $18.50`",
            said,
        )

    with isolated_home():
        book = corpus.Corpus()
        book.threshold = "0.4"
        book.answers[ARTICUNO_SKU] = corpus.Answer(
            value={"withheld": "bullish", "watch_above": "18.5"}
        )
        book.write()
        shown = command(checks, "prices", "show", "--held")
        checks.equal(
            bare_money(shown),
            [],
            "`prices show` prints the threshold and the watch price with two decimals",
        )
        checks.ok(
            "threshold=$0.40 " in shown and "above $18.50" in shown,
            "a threshold typed as 0.4 shows as $0.40 and a watch typed as 18.5 as $18.50",
            shown,
        )


def check_readings_adopt_cli(checks: Checks) -> None:
    """`banchi readings adopt` and `readings show`, through the real argparse dispatch
    (D189).

    THE WALK ITSELF IS PROVED BY `make readings-selftest` — an independent reimplementation
    compared against `pipeline/readings.py:collect()` across nine fixture shapes, mutation
    style. What that script cannot see is whether the CLI SURFACE over it actually works:
    argument parsing, the `COMMANDS` dispatch, and the preview / `--write` / `show` split.
    This closes that gap the way `check_prices_adopt` closes it for `prices adopt`.
    """
    from cli import __main__ as entry

    checks.note("")
    checks.note("READINGS ADOPT — the CLI surface over pipeline/readings.py:collect")

    with isolated_home():
        # A run table on disk, and nothing adopted yet.
        directory = files.runs_dir() / "2026-01-01-box1-01"
        directory.mkdir(parents=True, exist_ok=True)
        files.write_json(
            directory / "pricing.json",
            {"skus": [{"sku": DUNSPARCE_SKU, "snap": {"market": "1.00"}, "name": "Dunsparce"}]},
        )

        with quiet() as out:
            code = entry.main(["readings", "adopt"])
        checks.equal(code, 0, "a preview exits 0")
        checks.ok(
            "DRY RUN" in out.getvalue(),
            "and says so, in words rather than only by exit code",
            out.getvalue(),
        )
        checks.equal(
            dict(Store().read().readings.entries),
            {},
            "a preview writes nothing — the table is untouched",
        )

        with quiet() as out:
            code = entry.main(["readings", "adopt", "--write"])
        checks.equal(code, 0, "`--write` exits 0")
        adopted = dict(Store().read().readings.entries)
        checks.equal(
            set(adopted),
            {DUNSPARCE_SKU},
            "and the SELECT `_readings()` now performs sees exactly what was just adopted",
        )
        checks.equal(
            adopted[DUNSPARCE_SKU].market, "1.00", "carrying the reading the run table gave it"
        )

        with quiet() as out:
            code = entry.main(["readings", "show"])
        checks.equal(code, 0, "`show` exits 0 and never writes")
        checks.ok(
            "1 reading" in out.getvalue(),
            "and reports what adopt just wrote",
            out.getvalue(),
        )
        checks.equal(
            dict(Store().read().readings.entries),
            adopted,
            "a `show` press is read-only — the table is unchanged by looking at it",
        )


def check_readings_writer_after_join(checks: Checks) -> None:
    """A join leaves `readings` current with no `readings adopt` press (item 5, D189
    amended). `check_readings_adopt_cli` proves the CLI surface over the manual press;
    `check_value_table` proves the two-source arbitration with the table hand-filled. This
    is the one no existing check makes: that `join` itself keeps the table honest as an
    ordinary side effect of the write it already makes.
    """
    checks.note("")
    checks.note("READINGS WRITER — a join refreshes the cache with no adopt press")

    with isolated_home():
        cards = [(1, 1, "Dunsparce", "120", "normal")]
        run_dir, _ = seam_run(checks, cards, market="9.99")

        # NO `readings adopt` ANYWHERE ABOVE THIS LINE. If item 5's wiring in
        # `cli/cmd_join.py` were absent or broken, this table would still be empty exactly
        # as it was the moment PR #333 landed.
        current = dict(Store().read().readings.entries)
        checks.ok(
            len(current) >= 1,
            "the join that just ran left at least one reading behind with no adopt press",
            current,
        )
        if not current:
            return
        sku = next(iter(current))
        checks.equal(
            current[sku].source, run_dir.name,
            "and it is attributed to the run that was just joined",
        )
        checks.equal(
            current[sku].kind, store_readings.KIND_RUN,
            "as a run-table reading, not a live one",
        )

        # THE READ ROUTE AGREES, with no second write. `do_pipeline_value` is the caller
        # `_readings()` exists for; this is the seam a stale table would actually be felt on.
        # `card.sku` is stamped by `emit` (D174/D180), never by `join` itself, so an `emit`
        # is what puts this SKU on a row `do_pipeline_value` can key off of — the readings
        # table is already fresh before this line; this only exercises the read route that
        # was the actual complaint the manual press left standing.
        command(checks, "emit", str(run_dir.directory))
        payload = pipeline_routes.do_pipeline_value()
        row = next(r for r in payload["copies"] if r["sku"] == sku)
        checks.ok(
            row["market"] is not None,
            "GET /pipeline/value prices this card without anyone having pressed adopt",
            row,
        )

        # RE-JOINING SUPERSEDES ONLY THIS RUN'S OWN PRIOR ROWS. A second join of a
        # DIFFERENT run must not evict the first run's readings.
        cards2 = [(2, 1, "Articuno", "161", None)]
        run_dir2, _ = seam_run(checks, cards2, market="4.50")
        after = dict(Store().read().readings.entries)
        checks.ok(
            sku in after,
            "the first run's reading survives a second, unrelated run's join",
            after,
        )


def check_readings_writer_after_live_export(checks: Checks) -> None:
    """A fetched live export leaves `readings` current with no `readings adopt` press (item
    5, D189 amended), and a SECOND fetch supersedes the first — `pipeline/readings.py:
    _newest_live_reading` only ever credits the single newest live file, so the moment a
    fresher one lands every SKU the OLD file was carrying stops being backed by anything
    `collect()` would read, whether or not the new file happens to reprice it.

    ITS OWN HTTP STUB AND ITS OWN ENVIRONMENT, `check_export_fetch`'s reason: a real fetch
    would need the owner's live session, and a stray `.env` on this machine would otherwise
    point `envfile.get_live` at a real secret instead of this block's own fixture cookie.
    `do_live_export` makes ONE GET with no scope (D104), so the stub is a single handler
    rather than that check's whole portal.
    """
    checks.note("")
    checks.note("READINGS WRITER — a live fetch refreshes the cache with no adopt press")

    keys = (
        "BANCHI_TCG_EXPORT_URL",
        "TCGPLAYER_STORE_COOKIE",
        "BANCHI_TCG_USER_AGENT",
        envfile.FROM_FILE_ENV,
    )
    previous = {name: os.environ.get(name) for name in keys}

    stub = {"body": b""}

    class Portal(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # noqa: A003
            pass

        def do_GET(self):  # noqa: N802
            body = stub["body"]
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

    portal = http.server.HTTPServer(("127.0.0.1", 0), Portal)
    portal_thread = _spawn_server(portal)

    os.environ["BANCHI_TCG_EXPORT_URL"] = (
        f"http://127.0.0.1:{portal.server_address[1]}/admin/pricing/downloadexportcsv"
    )
    os.environ["TCGPLAYER_STORE_COOKIE"] = (
        "TCGAuthTicket_Production=t7-readings-not-a-real-session"
    )
    os.environ.pop("BANCHI_TCG_USER_AGENT", None)

    # THE SAME HERMETIC DANCE `check_export_fetch` DOES, for the same reason: an unpolluted
    # `envfile._from_file` is what makes `get_live` honour the variables set above rather than
    # a real `.env` on this machine.
    env_before = (envfile.ENV_FILE, set(envfile._from_file), envfile._loaded)
    envfile.ENV_FILE = Path(tempfile.gettempdir()) / "t7-readings-live-no-such.env"
    envfile._from_file.clear()
    os.environ.pop(envfile.FROM_FILE_ENV, None)
    envfile._loaded = False

    # A FAKE CLOCK, SO THE SECOND FETCH'S FILENAME COMPARES LATER THAN THE FIRST'S WITHOUT
    # SLEEPING A REAL SECOND. `do_live_export` names its file off
    # `datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")` — second precision — so two
    # fetches inside the same wall-clock second would collide on one filename and this test
    # would never see two sources to begin with.
    base = datetime.now(timezone.utc).replace(microsecond=0)
    moments = iter([base, base + timedelta(seconds=2)])

    class _FakeDatetime:
        @staticmethod
        def now(tz=None):
            return next(moments)

    real_datetime = pipeline_routes.datetime
    pipeline_routes.datetime = _FakeDatetime

    try:
        with isolated_home():
            source = tcgcsv.read_export(FIXTURE_EXPORT)
            by_sku = source.by_sku()

            # THE OLD FETCH CARRIES TWO SKUS.
            old_rows = [dict(by_sku[DUNSPARCE_SKU]), dict(by_sku[ARTICUNO_SKU])]
            old_rows[0][tcgcsv.MARKET_PRICE_COLUMN] = "1.00"
            old_path = Path(tempfile.mkdtemp()) / "old-live.csv"
            tcgcsv.write_csv(old_path, source.header, old_rows)
            stub["body"] = old_path.read_bytes()

            # NO `readings adopt` ANYWHERE ABOVE THIS LINE. If item 5's wiring in
            # `do_live_export` were absent or broken, this table would still be empty exactly
            # as it was the moment PR #333 landed.
            first = pipeline_routes.do_live_export()
            sources_after_first = Store().read().readings.sources_payload()
            checks.equal(
                [(s["kind"], s["name"]) for s in sources_after_first],
                [(store_readings.KIND_LIVE, first["fetched"])],
                "the fetch that just ran left exactly one live source behind with no adopt "
                "press",
            )
            entries_after_first = dict(Store().read().readings.entries)
            if DUNSPARCE_SKU not in entries_after_first:
                checks.ok(False, "a fetched SKU's entry exists", entries_after_first)
                return
            checks.equal(
                entries_after_first[DUNSPARCE_SKU].kind, store_readings.KIND_LIVE,
                "a fetched SKU's entry is kind=live",
            )

            # THE SECOND FETCH CARRIES ONLY ONE OF THE TWO SKUS, at a different price, and its
            # own filename is a full clock second later.
            new_rows = [dict(by_sku[DUNSPARCE_SKU])]
            new_rows[0][tcgcsv.MARKET_PRICE_COLUMN] = "2.00"
            new_path = Path(tempfile.mkdtemp()) / "new-live.csv"
            tcgcsv.write_csv(new_path, source.header, new_rows)
            stub["body"] = new_path.read_bytes()

            second = pipeline_routes.do_live_export()
            checks.ok(
                second["fetched"] != first["fetched"],
                "the second fetch is a distinct file from the first",
                (first["fetched"], second["fetched"]),
            )

            sources_after_second = Store().read().readings.sources_payload()
            checks.equal(
                [(s["kind"], s["name"]) for s in sources_after_second],
                [(store_readings.KIND_LIVE, second["fetched"])],
                "the second fetch supersedes the first — the OLD source name is gone from "
                "`sources`",
            )
            entries_after_second = dict(Store().read().readings.entries)
            checks.ok(
                ARTICUNO_SKU not in entries_after_second,
                "a SKU only the OLD file carried is gone from `entries`",
                entries_after_second,
            )
            if DUNSPARCE_SKU in entries_after_second:
                checks.equal(
                    entries_after_second[DUNSPARCE_SKU].market, "2.00",
                    "and the surviving SKU's reading is the NEW file's own price",
                )
    finally:
        pipeline_routes.datetime = real_datetime
        portal.shutdown()
        portal.server_close()
        portal_thread.join(5)
        envfile.ENV_FILE, restore_from_file, envfile._loaded = env_before
        envfile._from_file.clear()
        envfile._from_file.update(restore_from_file)
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def check_phantom_worklist(checks: Checks) -> None:
    """`reconcile --phantoms`: ghosts of a buried box are excluded from what is really on hand.

    Fixture, never the owner's store. SKU A: 2 real copies + 2 ghosts in box 5 (no `boxes` row),
    live 4 -> excess 2. SKU B: ghosts only, live 1 -> excess 1. SKU C: a real copy sold AFTER
    the export, live 2 (the sale not yet counted) -> the sale is not subtracted twice, excess 0.
    SKU D: live below real -> absent. A retired copy is not on hand.
    """
    inventory = master.Inventory()
    n = iter(range(1000))

    def card(box, sku, state="identified", at="2026-09-01T00:00:00+00:00"):
        made, _ = inventory.allocate_capture(box, cid=f"nophoto:{box}/{next(n)}@fixture")
        made.sku, made.state, made.state_at = sku, state, at

    for sku, state, at in (
        ("A", "identified", None), ("A", "identified", None),
        ("C", "identified", None), ("C", "sold", "2026-09-27T17:00:00+00:00"),
        ("E", "identified", None), ("E", "sold", "2026-09-20T00:00:00+00:00"),
        ("D", "identified", None), ("D", "retired", None),
        ("G", "identified", None), ("G", "sold", "2026-09-27T17:00:00+00:00"),
    ):
        card(1, sku, state, at or "2026-09-01T00:00:00+00:00")
    for sku in ("A", "A", "B", "C", "D", "E"):
        card(5, sku)
    card(5, "G", "sold", "2026-09-20T00:00:00+00:00")  # a ghost sold BEFORE the export
    del inventory.boxes["5"]  # the buried box: its cards stay, its row is gone
    rows = [
        {"TCGplayer Id": sku, "Total Quantity": str(qty), "Product Name": sku, "Condition": "NM"}
        for sku, qty in (("A", 4), ("B", 1), ("C", 2), ("D", 1), ("E", 2), ("G", 2))
    ]
    taken = int(datetime(2026, 9, 27, 16, 0, tzinfo=timezone.utc).timestamp())
    got = {w[0]: w[3:] for w in cmd_reconcile.phantom_worklist(inventory, rows, taken)}
    checks.equal(
        got,
        {"A": (4, 2, 2, 0), "B": (1, 0, 1, 0), "E": (2, 1, 1, 0)},  # G: live 2, real 1 sold since, a ghost sale is no real one -> 0
        "ghosts are not on hand: A live 4 real 2 excess 2, B live 1 real 0 excess 1; a sale "
        "after the export is added back (C) and live below real (D) is no excess",
    )


def check_live_reconcile(checks: Checks) -> None:
    """The whole store against one live export, both directions (D87).

    WHY THIS IS NOT THE PER-RUN RECONCILE'S JOB. That command scopes its diff to one run's
    `emitted_skus`, and the thing it diffs against — `store/master.py:Listing` — has never been
    run-scoped: D7 amended makes the three stages quantities held against a SKU across every
    box and run. The scoping was a property of the command.

    MEASURED ON THE OWNER'S STORE, 2026-09-01, BEFORE THIS EXISTED. Reconcile had effectively
    never run: 405 of 443 SKUs read `live: 0` while carrying pushed copies, `staged` was 0
    everywhere, and two SKUs sat at `pushed: 6` against a cap of 4 with nothing in the product
    able to see it. One live export settled 1,125 copies and tied out exactly — the export's
    live total for known SKUs and the ledger's both 1,079, zero per-SKU mismatches.

    THE FOUR ANSWERS ARE ASSERTED SEPARATELY BECAUSE THEY HAVE FOUR DIFFERENT REMEDIES. A copy
    that is live is settled; one this pipeline never sent is not its business; one TCGplayer
    holds more of than was sent is somebody else's listing; and one pushed that is neither live
    nor marked sold is the only ambiguous case, and it is REPORTED rather than cleared.
    """
    checks.note("")
    checks.note("LIVE RECONCILE — the whole store against one export")

    cards = [
        (3, 1, "Dunsparce", "120", "normal"),
        (3, 2, "Dunsparce", "120", "normal"),
        (3, 3, "Articuno", "161", None),
    ]

    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        book = corpus.Corpus.read()
        book.sub_threshold = "floor"
        book.write()
        command(checks, "emit", str(run_dir.directory))

        before = Store().read().inventory.listings
        pushed = {sku: entry.pushed for sku, entry in before.items()}
        checks.ok(
            sum(pushed.values()) > 0,
            f"the emit left {sum(pushed.values())} copy(ies) at `{master.PUSHED}` and "
            f"{sum(e.live for e in before.values())} at `{master.LIVE}` — which is the state "
            f"the owner's store was in for 443 SKUs, because nothing had ever reconciled",
        )

        # A LIVE EXPORT BUILT FROM THE RUN'S OWN, so every column is the real shape. Articuno
        # comes back fully live; Dunsparce comes back with ONE copy short of what was pushed.
        source = tcgcsv.read_export(run_dir.path("export.csv"))
        rows = []
        for row in source.rows:
            sku = row[tcgcsv.SKU_COLUMN]
            if sku not in pushed:
                continue
            out = dict(row)
            out[tcgcsv.LIVE_QUANTITY_COLUMN] = str(
                pushed[sku] - 1 if sku == DUNSPARCE_SKU else pushed[sku]
            )
            rows.append(out)
        # AND ONE ROW THIS STORE HAS NEVER SEEN — sealed product, or a single listed by hand.
        # It must be reported and never touched: the pipeline did not put it there.
        stranger = dict(source.rows[0])
        stranger[tcgcsv.SKU_COLUMN] = "1234567"
        stranger[tcgcsv.LIVE_QUANTITY_COLUMN] = "2"
        rows.append(stranger)
        live_path = run_dir.path("live.csv")
        tcgcsv.write_csv(live_path, source.header, rows)

        said = command(checks, "reconcile", "--live", str(live_path))
        checks.ok(
            "DRY RUN" in said,
            "IT PREVIEWS BY DEFAULT. It moves quantities the cap arithmetic reads, over every "
            "SKU at once — `banchi prices adopt`'s reason, and a settlement nobody watched "
            "is how a wrong number becomes the new floor",
        )
        unchanged = Store().read().inventory.listings
        checks.equal(
            {sku: entry.pushed for sku, entry in unchanged.items()},
            pushed,
            "and the preview WROTE NOTHING — every pushed count is where the emit left it",
        )
        checks.ok(
            "never seen here" in said and "1234567" in said,
            "the stranger row is reported by SKU. `seen` is every SKU a CARD carries and is "
            "deliberately wider than the listing ledger: a withheld or sub-threshold card has "
            "a SKU and no listing, and judging against the ledger alone would accuse the "
            "operator of listing it outside banchi the moment it went live",
        )

        said = command(checks, "reconcile", "--live", str(live_path), "--write")
        after = Store().read().inventory.listings
        checks.equal(
            after[ARTICUNO_SKU].live,
            pushed[ARTICUNO_SKU],
            "`live` COMES FROM THE EXPORT AND IS NOT NEGOTIATED — D8 and D11 make it "
            "authoritative about what TCGplayer holds, which is the same authority "
            "`cli/resolve.py:_copies_out` already grants `Total Quantity` as a floor",
        )
        checks.equal(
            {sku: entry.pushed for sku, entry in after.items() if sku in pushed},
            pushed,
            "AND `pushed` IS READ AND NEVER REWRITTEN. It is the CUMULATIVE count of copies "
            "ever written into an import file — an import file holds the last delta only "
            "(D54), so this is the one cumulative record there is. What was missing was a "
            "real `live`, which nothing in this repo had ever written: 405 of 443 SKUs read "
            "zero while carrying pushed copies",
        )
        checks.equal(
            after[DUNSPARCE_SKU].live,
            pushed[DUNSPARCE_SKU] - 1,
            "a SKU TCGplayer holds fewer of than were sent takes the export's figure like any "
            "other — the discrepancy is a SENTENCE, not an adjustment",
        )
        said_again = command(checks, "reconcile", "--live", str(live_path))
        checks.ok(
            "0 copy(ies) of `live` would be corrected" in said_again,
            "AND IT IS IDEMPOTENT. A second pass over the same export corrects nothing, which "
            "is the property a settlement that rewrote `pushed` could not have: that one "
            "destroys the cumulative record it read, so its own second pass answers a "
            "different question",
        )

        # AN OLDER EXPORT CANNOT UNSETTLE IT (D87 amended, 2026-09-02). The settlement dated
        # every listing to the file's mtime; a second export with different numbers, dated
        # an hour before it, is a reading the store has already overtaken — kept in the
        # preview, kept in the write. Moved forward past the settlement, the same file wins.
        settled_at = live_path.stat().st_mtime
        older_rows = [
            dict(row, **{tcgcsv.LIVE_QUANTITY_COLUMN: str(pushed[row[tcgcsv.SKU_COLUMN]] + 1)})
            for row in rows
            if row[tcgcsv.SKU_COLUMN] in pushed
        ]
        older_path = run_dir.path("older.csv")
        tcgcsv.write_csv(older_path, source.header, older_rows)
        os.utime(older_path, (settled_at - 3600, settled_at - 3600))
        preview = command(checks, "reconcile", "--live", str(older_path))
        checks.ok(
            f"{len(older_rows)} SKU(s) kept: store newer than this export" in preview
            and "0 copy(ies) of `live` would be corrected" in preview,
            "the preview says every differing SKU is KEPT — the store's reading is newer "
            "than the file's — and promises no correction",
            preview,
        )
        command(checks, "reconcile", "--live", str(older_path), "--write")
        checks.equal(
            {sku: entry.live for sku, entry in Store().read().inventory.listings.items()},
            {sku: entry.live for sku, entry in after.items()},
            "and the write, computed by the same rule as the preview, changes no `live`",
        )
        os.utime(older_path, (settled_at + 3600, settled_at + 3600))
        written = command(checks, "reconcile", "--live", str(older_path), "--write")
        checks.equal(
            {sku: Store().read().inventory.listings[sku].live for sku in pushed},
            {sku: pushed[sku] + 1 for sku in pushed},
            "dated after the settlement, the same file is adopted — the export keeps D8 and "
            "D11's authority for the moment it was read, and loses it only to a reading the "
            "store took later",
        )
        checks.ok("0 listing(s) kept" in written, "and nothing was kept that time", written)
        checks.ok(
            "unexplained" in said and DUNSPARCE_SKU in said,
            "and it is REPORTED by SKU rather than counted (D59's rule): a copy that quietly "
            "stopped being accounted for is a number nobody can check",
        )
        checks.equal(
            sum(1 for c in Store().read().inventory.cards.values() if c.state == master.SOLD),
            0,
            "AND NOT ONE CARD WAS MARKED SOLD. This moves quantities and never cards (D7) — "
            "which physical copy sold is deliberately unrecorded, and a command that picked "
            "one from a quantity would be inventing the address D7 refuses to invent",
        )
        # INVERTED 2026-09-06, AND THE RULE IT PROTECTED IS ASSERTED HARDER THAN BEFORE.
        # This read "the stranger SKU gained no listing record — reporting it is the whole of
        # what this command may do about a listing it did not make". That left the store with
        # no memory of any listing it had not photographed: measured on the owner's store, 0
        # of 443 listing records had no card behind them while the export carried 28 live SKUs
        # that did — so nothing could say how long one had been listed, nothing stopped a rule
        # marking the same one down every pass, and a copy selling was invisible.
        #
        # WHAT MUST NEVER HAPPEN IS THE CLAIM, NOT THE RECORD. `pushed` is the cumulative
        # count of what THIS pipeline sent; inventing one for a listing it did not make is the
        # defect the old assertion was really about, and it is now checked directly rather
        # than by the absence of the whole row.
        stranger = Store().read().inventory.listings.get("1234567")
        checks.ok(
            stranger is not None,
            "the stranger SKU GAINED a listing record — a live listing this store did not "
            "make is still a listing it has to be able to date, ratchet and watch sell",
        )
        checks.equal(
            (stranger.pushed if stranger else None, stranger.staged if stranger else None),
            (0, 0),
            "and `pushed` and `staged` stay 0 on it — this pipeline sent none of it, and a "
            "cumulative record that claimed otherwise is the one thing this may not write",
        )
        checks.ok(
            bool(stranger and stranger.live > 0 and stranger.first_seen_live),
            "while `live` and the first sighting ARE written: both are observations of what "
            "TCGplayer holds, which is exactly what the export is evidence of",
        )


def check_merged_emit_cap(checks: Checks) -> None:
    """Two runs, one SKU, one cap — the arithmetic a merged file has to re-derive (D86).

    THIS IS D59's DEFECT ONE REGISTER UP, AND IT SHIPPED. `pipeline/join.py:add_to_quantity`
    spends `live_cap - copies_out` per RUN against a cap that is GLOBAL, so two runs joined
    before either emitted each believe the whole cap is theirs. D59 fixed the per-BOX version
    of exactly this inside one join; the per-RUN version survived it, because no code path had
    ever looked at two runs together.

    IT IS NOT HYPOTHETICAL AND THE NUMBERS ARE OFF THE OWNER'S OWN STORE. The 2026-09-01 cart
    joined boxes 3, 4 and 5 in the same second; five SKUs' claims summed past four, and two
    reached `pushed: 6` against a cap of 4 in `inventory/inventory.json`. Replayed from a
    cleared ledger, three separate emits wrote 2 SKUs over the cap and one merged emit wrote
    none.

    WHAT IS ASSERTED IS THE FILE AND THE STORE, NOT THE PLAN. A plan that computes the right
    figure and a command that writes the wrong one is the failure mode this whole entry is
    about, so the checks read the CSV that was written and the `pushed` count that followed it.
    """
    checks.note("")
    checks.note("MERGED EMIT — one cap across the send")

    with isolated_home():
        # Four copies of one SKU in one box and three in another: seven copies of a card whose
        # cap is four. Each run alone is under the cap; together they are not.
        first, _ = seam_run(checks, [(3, i, "Articuno", "161", None) for i in range(1, 5)])
        second, _ = seam_run(checks, [(4, i, "Articuno", "161", None) for i in range(1, 4)])

        book = corpus.Corpus.read()
        book.sub_threshold = "floor"
        book.write()

        claims = []
        for run_dir in (first, second):
            table = json.loads(run_dir.path(runs.PRICING).read_text())
            row = next(r for r in table["skus"] if r["sku"] == ARTICUNO_SKU)
            claims.append(row["add_to_quantity"])
        checks.ok(
            sum(claims) > join.LIVE_QUANTITY_CAP,
            f"THE TWO RUNS SEPARATELY CLAIM {claims[0]} + {claims[1]} = {sum(claims)} COPIES "
            f"of a SKU capped at {join.LIVE_QUANTITY_CAP}. Neither run is wrong on its own — "
            f"each spends `live_cap - copies_out` and neither can see the other. This is the "
            f"state a concatenation of their two import files would write",
        )

        said = command(
            checks, "emit", str(first.directory), str(second.directory), "--cap", "4"
        )
        target = second.path(runs.IMPORT_MERGED)
        checks.ok(
            target.is_file() and not first.path(runs.IMPORT_MERGED).exists(),
            "ONE FILE FOR THE SEND, in the newest run of it — the owner's ask, and it lands "
            "where `GET /pipeline/runs/<name>/file` already serves a run's artefacts",
        )
        rows = tcgcsv.read_export(target).rows
        ids = [row[tcgcsv.SKU_COLUMN] for row in rows]
        checks.equal(
            len(ids),
            len(set(ids)),
            "NO DUPLICATE SKU ROW, which is a property here rather than a rule a writer has to "
            "keep: the plan is keyed by SKU, so a card in four runs is one row carrying the "
            "summed quantity and there is no shape in which it could be two",
        )
        written = int(
            next(row for row in rows if row[tcgcsv.SKU_COLUMN] == ARTICUNO_SKU)[
                tcgcsv.QUANTITY_COLUMN
            ]
        )
        checks.equal(
            written,
            join.LIVE_QUANTITY_CAP,
            f"AND THE ROW CARRIES {join.LIVE_QUANTITY_CAP} COPIES AND NOT {sum(claims)}. The "
            f"cap is spent ONCE over the union of both runs' positions — this is the whole of "
            f"what a merged emit has to do that a concatenation cannot",
        )
        checks.ok(
            "runs claim" in said,
            "and the command NAMES the SKUs whose runs over-claimed rather than counting them "
            "(D59): a card that quietly stopped being over-listed is a number nobody can check",
        )

        listing = Store().read().inventory.listings.get(ARTICUNO_SKU)
        checks.equal(
            listing.pushed if listing else 0,
            join.LIVE_QUANTITY_CAP,
            "THE STORE AGREES WITH THE FILE. `pushed` is a commitment that a CSV row was "
            "written, so a merged emit that wrote four copies and pushed seven would be the "
            "same over-listing one seam further on — and the first build of this command did "
            "exactly that, stamping every copy once per run that held it",
        )


def check_merged_emit_uncapped(checks: Checks) -> None:
    """The same send with no cap asked for — the shape that raised `TypeError` (D7, rewritten).

    THIS CRASHED FOR A DAY AND NOTHING SAW IT. `pipeline/merge.py` merged the legs' caps with
    `max(leg.match.live_cap for leg in legs)`, which was total while `live_cap` was an int and
    became a comparison against `None` the moment D7's rewrite made no-cap the ordinary value.
    It fired on exactly the shape a merged send exists for — one SKU held by two runs — and
    every existing case missed it because all of them ran against a store whose corpus default
    still answered four.

    WHAT IS ASSERTED IS THE COPY COUNT, NOT MERELY THE ABSENCE OF A CRASH. Seven copies over
    two runs go out as seven on one row: the merge still dedupes the union of positions on
    `(box, index)`, which is D86's other reason for one file and is untouched by the bound.
    """
    checks.note("")
    checks.note("MERGED EMIT — no cap asked for")

    with isolated_home():
        first, _ = seam_run(checks, [(3, i, "Articuno", "161", None) for i in range(1, 5)])
        second, _ = seam_run(checks, [(4, i, "Articuno", "161", None) for i in range(1, 4)])

        book = corpus.Corpus.read()
        checks.ok(
            "live_cap" not in book.to_payload()["policy"],
            "A STORE CANNOT HOLD A CAP AT ALL (D7, amended 2026-09-08). The key is gone from "
            "`policy`, not merely defaulted to None — which is what makes the retirement "
            "stick: `to_payload` wrote it unconditionally, so any default it carried was "
            "stamped into the file on the first save and found by every later read",
        )
        book.sub_threshold = "floor"
        book.write()

        said = command(checks, "emit", str(first.directory), str(second.directory))
        checks.ok(
            "Traceback" not in said,
            "THE MERGED SEND COMPLETES. `max()` over two `None` caps raises `TypeError: '>' "
            "not supported between instances of 'NoneType' and 'NoneType'`, and this is the "
            "one shape that reaches it — a SKU in a single run never merges two legs",
        )
        rows = tcgcsv.read_export(second.path(runs.IMPORT_MERGED)).rows
        ids = [row[tcgcsv.SKU_COLUMN] for row in rows]
        checks.equal(
            len(ids),
            len(set(ids)),
            "still ONE row for the SKU — the union is deduped on (box, index), which is the "
            "half of D86 the cap never had anything to do with",
        )
        checks.equal(
            int(
                next(row for row in rows if row[tcgcsv.SKU_COLUMN] == ARTICUNO_SKU)[
                    tcgcsv.QUANTITY_COLUMN
                ]
            ),
            7,
            "AND IT CARRIES ALL SEVEN COPIES. Under a cap of four the same send writes four; "
            "the difference between those two numbers is the exposure bound and nothing else, "
            "because `uncommitted_positions` — what actually stops a copy going twice — is "
            "the same list in both",
        )


def check_unsent_copies_worklist(checks: Checks) -> None:
    """`GET /pipeline/pricing` counts every copy TCGplayer does not hold, against the live
    store, and keeps a run open for as long as it holds one (D156).

    THE STRANDED SHAPE, REBUILT: seven copies of one card, emitted under a cap of four. The
    run's `pricing.json` was written by the join BEFORE the emit and says `add 4`; the emit
    then raised `pushed` to four, the run answered nothing more, and under the old rule it
    CLOSED — off the default worklist, its chip reading "Answered", and the three copies it
    held back reachable from no screen. On the owner's store on 2026-09-11 that was 381
    copies across five closed runs.

    WHAT IS ASSERTED IS THE FIGURE THE PRESS WILL WRITE, NOT THE TABLE'S. The route used to
    serve `min(sum of the runs' stored add_to_quantity, positions)` — four here, off a table
    the emit had already spent — and a second emit over the same run writes three. The two
    now agree because the route runs `cli/resolve.py`'s own arithmetic over the store as it
    stands; the mutation that reads the table's figure back is what this case is red under.
    """
    checks.note("")
    checks.note("UNSENT COPIES — the worklist counts what the press would send, live")

    with isolated_home():
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        try:
            run_dir, _ = seam_run(checks, [(3, i, "Articuno", "161", None) for i in range(1, 8)])
            book = corpus.Corpus.read()
            book.sub_threshold = "floor"
            book.write()

            status, body, _ = request(port, "GET", "/pipeline/pricing")
            before = json.loads(body)
            row = next(r for r in before["skus"] if r["sku"] == ARTICUNO_SKU)
            chip = next(r for r in before["roster"] if r["run"] == run_dir.directory.name)
            checks.equal(
                (status, row["add_to_quantity"], row["committed"], chip["unsent"], chip["open"], chip["owes"]),
                (200, 7, 0, 7, True, ["never emitted"]),
                "BEFORE ANY EMIT every copy is unsent: seven can go, none committed, the chip "
                "says seven, and the run is open for the reason it always was",
            )

            command(checks, "emit", str(run_dir.directory), "--cap", "4")
            table = json.loads(run_dir.path(runs.PRICING).read_text())
            stored = next(r for r in table["skus"] if r["sku"] == ARTICUNO_SKU)
            checks.equal(
                stored["add_to_quantity"],
                7,
                "THE TABLE STILL SAYS SEVEN. `pricing.json` is the join's record, written before "
                "the emit and untouched by it — which is exactly why a route reading it back "
                "drew a figure the press had already spent",
            )

            status, body, _ = request(port, "GET", "/pipeline/pricing")
            after = json.loads(body)
            chip = next(r for r in after["roster"] if r["run"] == run_dir.directory.name)
            checks.equal(
                (chip["owes"], chip["unsent"], chip["open"]),
                ([], 3, True),
                "AFTER THE CAPPED EMIT the run owes nothing and is STILL OPEN, because three "
                "copies are unsent — the third way to be open, and the one that did not exist. "
                "`owes` is untouched so Home's 'runs to price' does not count it",
            )
            checks.ok(
                run_dir.directory.name in [r["run"] for r in after["runs"]],
                "and it is on the DEFAULT landing — no `?run=` asked for it — which is the whole "
                "of the unsent worklist: every copy anywhere that can still go, in one list",
            )
            row = next(r for r in after["skus"] if r["sku"] == ARTICUNO_SKU)
            checks.equal(
                (row["add_to_quantity"], row["committed"], row["copies"], row["at_cap"], row["nothing_to_add"], row["claimed_add"]),
                (3, 4, 7, False, None, 7),
                "THE ROW IS LIVE: three can go, four are committed, seven on hand — and "
                "`claimed_add` keeps what the table says, so `over_cap` still names a table the "
                "press disagrees with",
            )
            checks.equal(
                ((row.get("listing") or {}).get("pushed"), row["copies_out"]),
                (4, 4),
                "the listing block and `copies_out` are the STORE's now, not the join's — the "
                "table's `listing` said pushed 0 for a card four copies of which had gone",
            )

            command(checks, "emit", str(run_dir.directory))
            rows = tcgcsv.read_export(run_dir.path(runs.IMPORT_MERGED)).rows
            written = int(
                next(r for r in rows if r[tcgcsv.SKU_COLUMN] == ARTICUNO_SKU)[tcgcsv.QUANTITY_COLUMN]
            )
            checks.equal(
                written,
                3,
                "AND THE PRESS WRITES THE FIGURE THE SCREEN DREW. The screen said three; an "
                "uncapped emit over the same run sends three, which is the agreement this "
                "route exists to keep",
            )

            status, body, _ = request(port, "GET", "/pipeline/pricing")
            done = json.loads(body)
            chip = next(r for r in done["roster"] if r["run"] == run_dir.directory.name)
            checks.equal(
                (chip["unsent"], chip["open"], [r["run"] for r in done["runs"]]),
                (0, False, []),
                "once every copy has gone the run closes, and the default landing is empty — "
                "'Everything is sent' is a true sentence and not a stale one",
            )

            # WHAT NO WORKLIST CAN SEND IS NAMED, NOT LEFT OUT. A card captured and never
            # identified, and a run identified and never joined, are both real cardboard
            # that the list above cannot offer.
            capture_server.do_capture(capture_payload(9))
            bare, _ = seam_run(checks, [(9, 1, "Articuno", "161", None)], join=False)
            status, body, _ = request(port, "GET", "/pipeline/pricing")
            named = json.loads(body)["unreachable"]
            checks.equal(
                (named["captured"], [r["run"] for r in named["unjoined"]], named["reallocated"]),
                (1, [bare.directory.name], []),
                "the captured-and-never-identified card and the identified-and-never-joined run "
                "are both named under `unreachable`, each a door to `#/runs` — `CLAUDE.md`: "
                "never silently drop a card",
            )
        finally:
            httpd.shutdown()
            thread.join(timeout=5)


def check_worklist_on_hand(checks: Checks) -> None:
    """A worklist row says how many copies are ON HAND (still in a box: not sold, not departed)
    as `on_hand`, apart from `add_to_quantity`, the copies that can still be sent.

    Five positions drawn, one already live (a capped emit), two since sold: three are on
    hand and two can be sent. `copies` is every position the run drew (five) and is not the
    on-hand figure; the screen's first number is `on_hand`.
    """
    checks.note("")
    checks.note("ON HAND — a worklist row counts the copies still in a box")

    with isolated_home():
        run_dir, _ = seam_run(checks, [(3, i, "Articuno", "161", None) for i in range(1, 6)])
        book = corpus.Corpus.read()
        book.sub_threshold = "floor"
        book.write()
        command(checks, "emit", str(run_dir.directory), "--cap", "1")
        capture_server.do_mark_sold(3, 4, {})
        capture_server.do_mark_sold(3, 5, {})

        row = next(r for r in pipeline_routes.do_pipeline_worklist([])["skus"] if r["sku"] == ARTICUNO_SKU)
        checks.equal(
            (row.get("on_hand"), row["add_to_quantity"]),
            (3, 2),
            "five drawn, two sold, one live: three on hand, two can be sent",
        )


def check_worklist_on_hand_unstamped(checks: Checks) -> None:
    """On hand counts copies a join drew for a SKU that no emit has stamped yet.

    Three Articuno positions joined and NOT emitted: `cards.sku` is empty on all three. One
    is sold. Two are on hand and two can be sent. A fourth position the table drew for
    Articuno but since re-stamped as Dunsparce is not Articuno's copy and does not count.
    """
    checks.note("")
    checks.note("ON HAND — unstamped joined copies count, a re-stamped one does not")

    with isolated_home():
        cards = [(3, i, "Articuno", "161", None) for i in range(1, 5)]
        run_dir, _ = seam_run(checks, cards)
        book = corpus.Corpus.read()
        book.sub_threshold = "floor"
        book.write()

        capture_server.do_mark_sold(3, 3, {})
        with Store().write() as snap:
            for card in snap.inventory.cards.values():
                if (card.box, card.index) == (3, 4):
                    card.sku = DUNSPARCE_SKU

        row = next(r for r in pipeline_routes.do_pipeline_worklist([])["skus"] if r["sku"] == ARTICUNO_SKU)
        checks.equal(
            (row.get("on_hand"), row["add_to_quantity"]),
            (2, 2),
            "four drawn, none stamped by emit: one sold, one re-stamped as another card; "
            "two on hand and two can be sent",
        )


def check_cap_flag_refusals(checks: Checks) -> None:
    """`--cap 0` is a sentence, not a traceback — and it is parsed before any work.

    THE ONLY DOOR HAS TO ANSWER FOR ITSELF (D7, amended 2026-09-08). `_cap_for` raises
    `MalformedDecisions`, and the only `except` in `cli/cmd_emit.py` that names that type
    wraps `Corpus.read()` — the call itself sat inside a `try` catching `join.EmptyCatalog`
    alone. So `--cap 0` came back as a Python traceback. That was survivable while
    `policy.live_cap` was the ordinary door and the flag an exception; with the standing key
    deleted, this flag is the only way a cap is ever named.

    PARSED BEFORE THE STORE IS READ, which is the half worth asserting separately: a refusal
    that arrives after the run directory has been opened and the corpus read is a refusal that
    already cost something, and on a slow store it arrives long after the press.
    """
    checks.note("")
    checks.note("--cap — an unusable figure is refused")

    with isolated_home():
        run_dir, _ = seam_run(checks, [(3, 1, "Articuno", "161", None)])
        before = run_dir.path(runs.IMPORT_MERGED).exists()

        from cli import __main__ as entry

        for bad in ("0", "-1"):
            # `command()` ASSERTS EXIT 0 and cannot be used for a refusal — the same reason
            # every other refusal case here drives `entry.main` directly.
            with quiet() as buf:
                code = entry.main(["emit", str(run_dir.directory), "--cap", bad])
            said = buf.getvalue()
            checks.equal(code, 1, f"`--cap {bad}` exits 1")
            checks.ok(
                "Traceback" not in said,
                f"`--cap {bad}` answers in a sentence rather than a traceback",
            )
            checks.ok(
                "--cap" in said,
                f"and the sentence names the flag that was wrong, not a policy key that no "
                f"longer exists. Got: {said.strip()[:120]!r}",
            )

        checks.equal(
            run_dir.path(runs.IMPORT_MERGED).exists(),
            before,
            "AND NOTHING WAS WRITTEN. The cap is parsed before the run is opened, so a "
            "refusal costs nothing — the shape every refusal on this path takes",
        )


def check_emit_send_quantity(checks: Checks) -> None:
    """A number on the card's row is a SEND quantity, this press only (D7, amended 2026-09-11).

    THE OWNER'S REPORT, ON 2026-09-11: *"I can no longer select quantities to sell at all"*. The
    ceiling `--cap N` holds every SKU to N live at TCGplayer, counting what is already out — so
    it cannot say "two of THIS card", and on a SKU with copies already out it says nothing at
    all. Asked which control they meant, the owner ruled for a number on each row, meaning
    COPIES TO SEND IN THIS FILE: type 2 and two go, whatever TCGplayer holds, bounded by the
    copies on hand that are not already listed.

    WHAT IS ASSERTED IS THE FILE AND THE STORE, `check_merged_emit_cap`'s rule. The figure
    bounds the LISTING and never the RECORD (D7 amended, `check_emit_identity_stamp`): every
    copy still carries the SKU. A second press asking past what remains gets the remainder
    and SAYS SO; `0` sends none of the card and is named as the reason; the ceiling and the
    quantity compose to the tighter; a merged send spends the figure once across the union;
    and every unusable pair is a sentence before the store is read, on both doors — the flag
    and the route's parser.
    """
    checks.note("")
    checks.note("EMIT QUANTITY — a number on the card's row, this press only")

    from cli import __main__ as entry

    copies = 5
    cards = [(3, i, "Articuno", "161", None) for i in range(1, copies + 1)]
    # A second card, given no figure, so the file always has a row and the ordinary case is
    # asserted beside the typed one rather than assumed.
    cards.append((3, copies + 1, "Dunsparce", "120", "normal"))

    def quantity_written(run_dir):
        rows = tcgcsv.read_export(run_dir.path(runs.IMPORT_MERGED)).rows
        return {row[tcgcsv.SKU_COLUMN]: row[tcgcsv.QUANTITY_COLUMN] for row in rows}

    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        said = command(
            checks, "emit", str(run_dir.directory),
            "--quantity", f"{ARTICUNO_SKU}=2", "--quantity", "999999=1",
        )
        written = quantity_written(run_dir)
        checks.equal(
            written.get(ARTICUNO_SKU),
            "2",
            "THE ROW CARRIES THE FIGURE TYPED, not the five on hand: a send quantity is what "
            "goes in the file this press, and the file is what D7 is about",
        )
        checks.equal(
            written.get(DUNSPARCE_SKU),
            "1",
            "and a card given no figure sends every copy that can go — the ordinary press is "
            "untouched by a figure on another row",
        )
        inventory = Store().read().inventory
        checks.equal(
            inventory.listings[ARTICUNO_SKU].pushed,
            2,
            "THE STORE AGREES WITH THE FILE: `pushed` is a commitment that a CSV row was "
            "written, so it follows the figure and not the shelf",
        )
        checks.equal(
            [c.index for c in inventory.positions_for_sku(ARTICUNO_SKU)],
            list(range(1, copies + 1)),
            "AND EVERY COPY STILL CARRIES THE SKU. The figure bounds the listing and never the "
            "record — the same seam D7's identity-stamp amendment closed for the cap",
        )
        checks.ok(
            "quantities" in said and "2 of 5 on hand" in said,
            f"the report names the card and the figure in a `quantities` block rather than "
            f"counting it. Got: {said[-400:]!r}",
        )
        checks.ok(
            "does not hold: 999999" in said,
            "and a SKU named that the send does not hold is named back — a typo that would "
            "otherwise vanish behind an accepted flag and a written file",
        )

        # ------------------------------------------------ a second press asks past the shelf
        said = command(checks, "emit", str(run_dir.directory), "--quantity", f"{ARTICUNO_SKU}=9")
        checks.equal(
            quantity_written(run_dir).get(ARTICUNO_SKU),
            "3",
            "ASKED 9 WITH THREE UNSENT, THREE GO. Bounded by the copies on hand that are not "
            "already listed — never by what TCGplayer holds, which is the ceiling's job and "
            "the reading the owner ruled against for this control",
        )
        checks.equal(
            Store().read().inventory.listings[ARTICUNO_SKU].pushed,
            5,
            "and the second press ADDS on top of the first (D54): two then three, never two "
            "sent twice — `uncommitted_positions` is still what stops a copy going twice",
        )
        checks.ok(
            "asked 9, only 3 can go" in said,
            f"and the shortfall is NAMED, not clamped in silence. Got: {said[-400:]!r}",
        )

    # ---------------------------------------------------------- zero, and the ceiling composing
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        said = command(checks, "emit", str(run_dir.directory), "--quantity", f"{ARTICUNO_SKU}=0")
        written = quantity_written(run_dir)
        checks.ok(
            ARTICUNO_SKU not in written and written.get(DUNSPARCE_SKU) == "1",
            "`0` SENDS NONE OF THAT CARD and the file still carries the rest — it is a "
            "quantity, not a refusal, and not a hold",
        )
        inventory = Store().read().inventory
        listing = inventory.listings.get(ARTICUNO_SKU)
        checks.equal(
            listing.pushed if listing else 0,
            0,
            "nothing is pushed for a card sent at zero",
        )
        checks.equal(
            len(inventory.positions_for_sku(ARTICUNO_SKU)),
            copies,
            "and its five copies are still stamped — asked-for-none is not unknown",
        )
        checks.ok(
            "asked 0, none sent" in said,
            f"and the zero is named as the reason in the report. Got: {said[-400:]!r}",
        )

        said = command(
            checks, "emit", str(run_dir.directory), "--cap", "2", "--quantity", f"{ARTICUNO_SKU}=4",
        )
        checks.equal(
            quantity_written(run_dir).get(ARTICUNO_SKU),
            "2",
            "THE CEILING AND THE QUANTITY COMPOSE TO THE TIGHTER: a cap of 2 over a figure of 4 "
            "sends 2 — the quantity can only ever take copies out of the file, never put in "
            "copies the ceiling refuses",
        )
        checks.ok(
            "asked 4, only 2 can go" in said,
            "and that, too, is named",
        )

    # ---------------------------------------------------------- once across a merged send
    with isolated_home():
        first, _ = seam_run(checks, [(3, i, "Articuno", "161", None) for i in range(1, 4)])
        second, _ = seam_run(checks, [(4, i, "Articuno", "161", None) for i in range(1, 3)])
        book = corpus.Corpus.read()
        book.sub_threshold = "floor"
        book.write()
        said = command(
            checks, "emit", str(first.directory), str(second.directory),
            "--quantity", f"{ARTICUNO_SKU}=4",
        )
        checks.equal(
            quantity_written(second).get(ARTICUNO_SKU),
            "4",
            "A MERGED SEND SPENDS THE FIGURE ONCE OVER THE UNION: five copies across two runs, "
            "asked at 4, is one row of 4 — not 4 per leg and not 3 + 2",
        )
        checks.equal(
            Store().read().inventory.listings[ARTICUNO_SKU].pushed,
            4,
            "and the store pushed four, across both runs' copies",
        )
        checks.ok(
            "4 of 5 on hand" in said,
            f"and the merged report reads the figure off the merged match. Got: {said[-400:]!r}",
        )

    # ---------------------------------------------------------- an unusable pair is a sentence
    with isolated_home():
        run_dir, _ = seam_run(checks, [(3, 1, "Articuno", "161", None)])
        before = run_dir.path(runs.IMPORT_MERGED).exists()
        for bad in (
            ["abc=1"], [f"{ARTICUNO_SKU}=x"], [f"{ARTICUNO_SKU}=-1"], [ARTICUNO_SKU],
            [f"{ARTICUNO_SKU}=1000"], [f"{ARTICUNO_SKU}=1", f"{ARTICUNO_SKU}=2"],
        ):
            argv = ["emit", str(run_dir.directory)]
            for pair in bad:
                argv += ["--quantity", pair]
            with quiet() as buf:
                code = entry.main(argv)
            said = buf.getvalue()
            checks.equal(code, 1, f"`--quantity {' '.join(bad)}` exits 1")
            checks.ok(
                "Traceback" not in said and "--quantity" in said,
                f"and answers in a sentence naming the flag. Got: {said.strip()[:160]!r}",
            )
        checks.equal(
            run_dir.path(runs.IMPORT_MERGED).exists(),
            before,
            "AND NOTHING WAS WRITTEN: parsed beside `--cap`, before the store is read",
        )

    # ---------------------------------------------------------- the route's own door
    checks.equal(
        pipeline_routes._quantity_flags({}),
        [],
        "the route forwards nothing when no card was given a figure — absence is the ordinary press",
    )
    checks.equal(
        pipeline_routes._quantity_flags({"quantities": {ARTICUNO_SKU: 2, DUNSPARCE_SKU: 0}}),
        ["--quantity", f"{ARTICUNO_SKU}=2", "--quantity", f"{DUNSPARCE_SKU}=0"],
        "and turns the screen's map into the flag, one pair per card, zero included",
    )
    for bad in (
        [1], {"abc": 1}, {ARTICUNO_SKU: "2"}, {ARTICUNO_SKU: True},
        {ARTICUNO_SKU: -1}, {ARTICUNO_SKU: 2.5}, {ARTICUNO_SKU: 1000},
    ):
        refused = None
        try:
            pipeline_routes._quantity_flags({"quantities": bad})
        except pipeline_routes.PipelineRefusal as caught:
            refused = caught
        checks.ok(
            refused is not None and getattr(refused, "code", None) == "quantities_invalid",
            f"the route refuses {bad!r} by name rather than forwarding it into argv",
        )


def check_merged_cap_is_the_tightest(checks: Checks) -> None:
    """Legs carrying different caps merge to the SMALLEST, and a leg with none does not win.

    THE OLD `max` TOOK THE LOOSEST, which is the opposite of every other cross-run rule in
    `pipeline/merge.py`. A send spanning a run deliberately held to 2 and a run at 4 offered
    4 — discarding the more conservative answer on the one path that exists to be
    conservative. Asserted on the merge directly rather than through a command, because
    `policy.per_run` is the only writer of a differing cap today and nothing sets one.
    """
    checks.note("")
    checks.note("MERGED EMIT — two caps, and no cap")

    row = {tcgcsv.SKU_COLUMN: ARTICUNO_SKU}

    def leg(cap):
        return merge.Leg(
            run="r%s" % cap,
            game="riftbound",
            match=join.SkuMatch(sku=ARTICUNO_SKU, row=row, live_cap=cap),
        )

    checks.equal(
        merge._merged_cap([leg(4), leg(2)]),
        2,
        "TWO CAPS MERGE TO THE TIGHTER ONE. A cap is a ceiling, and merging two ceilings "
        "takes the lower — `max` gave the run that wanted less exposure the other run's",
    )
    checks.equal(
        merge._merged_cap([leg(None), leg(2)]),
        2,
        "AND NO-CAP NEVER OUTRANKS A REAL FIGURE. `None` is the absence of a bound rather "
        "than a very large one, so a leg that names nothing must not lift a leg that does",
    )
    checks.equal(
        merge._merged_cap([leg(None), leg(None)]),
        None,
        "no cap only when NO leg names one — the ordinary send, and the case that raised",
    )


def check_unsent_listing_sells_out(checks: Checks) -> None:
    """A listing this pipeline never sent, selling out, is settled — the hole D109 armed.

    THE TRAP TAKES TWO EXPORTS TO SPRING, which is why nothing caught it. `reconcile --live`
    records a SKU TCGplayer holds that this store never sent (D109), and every record it makes
    carries `pushed = 0` by design — `pushed` is the cumulative count of what THIS pipeline
    wrote, and it wrote none of these. `pipeline/livecheck.py` then bucketed on `claim`:

        if row.claim == 0:
            if live > 0:
                report.beyond.append(row)
            continue

    so a row at `claim == 0` reading quantity 0 landed in NO bucket — not `agreed`, not
    `beyond`, not `unknown`, not `absent`. `cli/cmd_reconcile.py` builds `settling` from three
    of those, so `observe_live` was never called and the stored reading stood forever. The
    first export writes the record; the SECOND is where it goes wrong, and a single-pass case
    cannot see it.

    MEASURED ON THE OWNER'S OWN BOOK: their export carries 47 live SKUs this pipeline never
    sent, holding 127 copies — 26 of one booster pack alone. The first `--write` would have
    armed this on every one of them.

    WHAT IS NOT SETTLED IS UNCHANGED. A SKU nobody has ever recorded, reading zero, is still
    nothing to say and still falls through — `row.ledger_live > 0` is what separates "the
    store believes something about this" from "neither side has anything".
    """
    checks.note("")
    checks.note("UNSENT LISTING — sold out at TCGplayer, and the store hears about it")

    with isolated_home():
        run_dir, _ = seam_run(checks, [(3, 1, "Articuno", "161", None)])
        stranger = "7654321"

        # A LIVE EXPORT CARRYING ONE ROW THIS STORE HAS NEVER SEEN, built from the run's own
        # so every column is the real shape. `write_export` cannot serve here — it emits the
        # three seam SKUs and nothing else, and the whole case is about a SKU that is not one
        # of them.
        source = tcgcsv.read_export(run_dir.path("export.csv"))

        def live_file(name, quantity):
            row = dict(source.rows[0])
            row[tcgcsv.SKU_COLUMN] = stranger
            row[tcgcsv.LIVE_QUANTITY_COLUMN] = str(quantity)
            path = run_dir.path(name)
            tcgcsv.write_csv(path, source.header, [row])
            return path

        # PASS ONE: TCGplayer holds three of a SKU this store never sent. D109 records it.
        command(checks, "reconcile", "--live", str(live_file("live-1.csv", 3)), "--write")
        recorded = Store().read().inventory.listings.get(stranger)
        checks.equal(
            (getattr(recorded, "live", None), getattr(recorded, "pushed", None)),
            (3, 0),
            "D109 RECORDS IT: `live` is the export's reading and `pushed` stays 0, because "
            "this pipeline sent none of it. That zero is what puts the row in the arm the "
            "defect lived in",
        )

        # PASS TWO: it has sold out. The export still carries the row, at zero — which is
        # what a real My Pricing export does: 372 of the owner's 772 rows read zero.
        said = command(checks, "reconcile", "--live", str(live_file("live-2.csv", 0)), "--write")
        settled = Store().read().inventory.listings.get(stranger)
        checks.equal(
            getattr(settled, "live", None),
            0,
            "AND SELLING OUT REACHES THE STORE. This is the assertion the hole fails: the row "
            "fell into no bucket, `settling` never held it, and the store went on believing "
            "three copies were for sale — on a listing it could not have sold, because it "
            "never sent it",
        )
        checks.ok(
            stranger in said,
            "and the SKU is named in the report rather than settled in silence — a quantity "
            "moving on a listing this pipeline does not manage is exactly the thing the "
            "operator cannot find out any other way",
        )

        # AND THE OTHER HALF OF THE CONDITION, which is why it is not `if True`.
        never = dict(source.rows[0])
        never[tcgcsv.SKU_COLUMN] = "9999999"
        never[tcgcsv.LIVE_QUANTITY_COLUMN] = "0"
        empty = run_dir.path("live-3.csv")
        tcgcsv.write_csv(empty, source.header, [never])
        said = command(checks, "reconcile", "--live", str(empty), "--write")
        checks.ok(
            "9999999" not in said,
            "A SKU NEITHER SIDE HAS ANYTHING ON IS STILL NOTHING TO SAY. The store holds no "
            "record and the export reads zero, so there is no reading to settle and no line "
            "to draw — reporting it would be the noise the `claim == 0` arm was written to "
            "avoid in the first place",
        )

# ------------------------------------------------------------------------------------ run


def check_pipeline_routes(checks: Checks) -> None:
    """The pipeline seam — and every refusal that stands between a screen and an invoice.

    THE ONE ROUTE IN THIS SERVER THAT CAN SPEND MONEY IS `POST /pipeline/identify`, and the
    cases below never let it succeed. That is deliberate rather than a gap: a test that
    proved the happy path would have to submit a real Batch, and `harness/run.py` runs at
    the end of every turn. What IS provable without spending is the whole guard rail — that
    it refuses without an explicit confirm, that it refuses a scope that names nothing, and
    that the free preflight beside it computes the same numbers while creating no run — and
    that is what this section holds.

    Everything else here is free by construction: reading a run reads a directory, and
    `join --dry-run` walks the ladder and writes nothing. Both are exercised over real
    sockets against a real store in a temporary home.
    """
    with isolated_home() as home:
        # A capture directory with two real photographs, so a scope can be built from it and
        # `sidecar.scan` has something to find. THE LEGACY ADDRESS ON PURPOSE: these files
        # are written by hand and never by the shutter, so they carry no card and no name,
        # and `box3/0001.jpg` is exactly the shape of the corpus a store part way through
        # the relocation still holds. All four are the same `JPEG` constant, which no
        # capture may reuse now (a card is named by its photograph's digest, and
        # `cards_cid` is UNIQUE) but which costs nothing here: nothing reads a card out of
        # them and no record is ever written.
        box_dir = home / "captures" / "cards" / "box3"
        box_dir.mkdir(parents=True)
        for index in (1, 2):
            (box_dir / f"{index:04d}.jpg").write_bytes(JPEG)
            (box_dir / f"{index:04d}.json").write_text(
                json.dumps({"box": 3, "index": index, "game": "pokemon", "variant": "normal"})
            )
        # A SECOND BOX, because half of what a cart has to be checked for is that two legs
        # stay two: their own readings, their own runs, and a refusal on one taking the
        # whole send down rather than leaving the other half spawned.
        other_dir = home / "captures" / "cards" / "box7"
        other_dir.mkdir(parents=True)
        for index in (1, 2):
            (other_dir / f"{index:04d}.jpg").write_bytes(JPEG)
            (other_dir / f"{index:04d}.json").write_text(
                json.dumps({"box": 7, "index": index, "game": "pokemon", "variant": "normal"})
            )

        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        try:
            # ---------------------------------------------------------- the money gate
            status, body, _ = request(
                port, "POST", "/pipeline/identify", payload={"box": 3}
            )
            checks.equal(
                (status, error_code(body)),
                (400, "confirm_required"),
                "the spending route refuses a well-formed request that did not say confirm "
                "— the gate is a field a stray request does not carry, not a typed string, "
                "because the owner ruled against typing on this control",
            )
            checks.equal(
                sorted(p.name for p in (home / "runs").iterdir())
                if (home / "runs").is_dir()
                else [],
                [],
                "and the refusal created no run directory — a refused request that left a run "
                "behind would put an empty row on the screen for every mis-tap",
            )

            # ----------------------------------------- `confirm` ALONE NO LONGER REFUSES
            #
            # THE `box_required` REFUSAL IS GONE AND IT WAS THE THESIS STATED AS A 400. This
            # case asserted it in as many words: *"a run is always scoped to one box, so a
            # confirm with no scope is refused rather than read as every box"*. It is read as
            # every box now — that is the whole change — and the gate that makes it safe is the
            # one D33 built and this entry does not touch: a free preflight, then a confirm.
            #
            # PROVED BY THE REFUSAL IT EARNS INSTEAD, which is `selection_is_empty` over a home
            # whose capture root holds nothing. A route that had merely stopped validating would
            # answer 202 here and spawn a child over nothing.
            with isolated_home():
                bare_server = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
                bare_port = bare_server.server_address[1]
                bare_thread = _spawn_server(bare_server)
                try:
                    status, body, _ = request(
                        bare_port, "POST", "/pipeline/identify", payload={"confirm": True}
                    )
                    checks.equal(
                        (status, error_code(body)),
                        (404, "selection_is_empty"),
                        "a confirm with no selection is EVERY photograph in the store, and over "
                        "a store with none it refuses as empty rather than as `box_required` — "
                        "the terminal is the surface that refuses an unbounded selection, and "
                        "it names `--all`, because the screen has a preflight in front of it "
                        "and a terminal has a newline",
                    )
                    checks.ok(
                        "out of 0 scanned" in error_message(body),
                        "and the refusal carries the count it started FROM, which is what "
                        "separates a mistyped term from a capture root that is not there — "
                        "`box_has_no_captures` could only ever say the second",
                    )
                finally:
                    bare_server.shutdown()
                    bare_server.server_close()
                    bare_thread.join(timeout=5)

            # ------------------------------------------------------- selection refusals
            for payload, expected_status, expected, label in (
                (
                    {"box": 3, "keys": []},
                    400,
                    "selection_invalid",
                    "an EMPTY selection is refused rather than read as the whole box — the "
                    "same refusal the old `indices` earned, and for the harder reason here: a "
                    "tick list that failed to send would become a run over 887 cards",
                ),
                (
                    {"keys": ["3/1", "two"]},
                    400,
                    "selection_invalid",
                    "one bad member refuses the whole list rather than being dropped from it, "
                    "which is the rule the finish claim already follows — and which "
                    "`CLAUDE.md` states absolutely: a card is never silently dropped",
                ),
                (
                    {"keys": ["3/017"]},
                    400,
                    "selection_invalid",
                    "and a PADDED index is not a position key: `store/master.py:position_key` "
                    "is the other end of this string and would never write one, so accepting "
                    "it would be a key that matches nothing reported as a selection of one",
                ),
                (
                    {"box": 3, "indices": [1]},
                    400,
                    "selection_invalid",
                    "`indices` is refused BY NAME rather than ignored. It and `keys` are one "
                    "idea spelled twice; a term the route quietly dropped would be a press "
                    "over the whole drawer reported as a press over one card",
                ),
                (
                    {"scopes": [{"box": 3}]},
                    400,
                    "selection_invalid",
                    "and so is `scopes`, for the same reason one register up — a cart of "
                    "boxes silently read as its first box is an invoice for the wrong send",
                ),
                (
                    {"box": 404},
                    404,
                    "selection_is_empty",
                    "a box nothing was photographed into names no card, so a mistyped box "
                    "number cannot silently identify nothing and report success",
                ),
                (
                    {"keys": ["3/90001"]},
                    404,
                    "selection_is_empty",
                    "and neither can a ticked card with no photograph on disk",
                ),
                (
                    {"section": 2},
                    400,
                    "selection_invalid",
                    "a section with no drawer beside it is refused: section 2 is a different "
                    "set of cards in every box",
                ),
                (
                    {"box": [3, 7], "section": 1},
                    400,
                    "selection_invalid",
                    "and a section over TWO drawers is refused too — it would name two "
                    "unrelated runs of cards under one number",
                ),
                (
                    {"box": 3, "bid": 3},
                    400,
                    "selection_invalid",
                    "a drawer named twice, as a shelf number and as a true index, is two "
                    "answers to one question (D145)",
                ),
                (
                    {"state": "unjoined"},
                    400,
                    "selection_invalid",
                    "and `state` takes `master.STATES` and nothing else — the store's own "
                    "vocabulary, so the list here cannot drift from the one `check_state` "
                    "enforces. `unjoined` is a property of a RUN, not of a card",
                ),
                (
                    {"game": "magic"},
                    400,
                    "selection_invalid",
                    "an unregistered game refuses rather than matching nothing: D22 makes the "
                    "taxonomies hand-authored, so a typo that quietly selected zero cards "
                    "would blame the store",
                ),
                (
                    {"box": 3, "max_edge": 99},
                    400,
                    "max_edge_invalid",
                    "max_edge is bounded: the flag reaches the child's argv, and a route "
                    "that passed any integer through would be an argv a request controls",
                ),
                (
                    {"box": 3, "retry_budget": 9},
                    400,
                    "retry_budget_invalid",
                    "as is retry_budget, which multiplies what a run submits",
                ),
            ):
                status, body, _ = request(
                    port, "POST", "/pipeline/preflight", payload=payload
                )
                checks.equal(
                    (status, error_code(body)), (expected_status, expected), label
                )

            # -------------------------------------------- NO DIRECTORY IS BUILT, EVER
            #
            # THE WORK, NOT THE OUTCOME (D180). `_resolve_scope` built a
            # directory of symlinks per ticked selection — `.scopes/box3-<n>-<stamp>` — because
            # `identify` took a path and a subset is not one. Every assertion in this file about
            # what the preview and the preflight ANSWERED stayed green throughout: the old shape
            # was correct, it just could not express a subset without writing to disk first.
            #
            # MEASURED ON THE OPERATOR'S CHECKOUT 2026-09-12: 264 directories under `.scopes/`,
            # and 264 of 264 named `box<n>-1-<stamp>` — a selection of exactly ONE card, so
            # every one was built by the crop preview stepping a card at a time and not one was
            # ever a submission. 13 of 13 run manifests record `whole_box: True, cards: None`.
            #
            # THE ASSERTION IS OVER THE HOME'S TOP LEVEL rather than over `.scopes` by name, so
            # it sees the next temporary directory somebody adds here too. A check naming the
            # thing that was deleted can only ever pass.
            checks.ok(
                not (home / ".scopes").exists(),
                "no scope directory exists after fourteen refusals and a preflight — and "
                "none is created on the happy path either, because a selection is a list of "
                "position keys on the wire rather than a directory of symlinks on disk",
            )

            # ------------------------------------------------- ONE QUOTE, NOT A LIST OF LEGS
            status, body, _ = request(port, "POST", "/pipeline/preflight", payload={"box": 3})
            single = json.loads(body)
            checks.equal(
                (status, single["total"]["cards"], single["total"]["photographs"]),
                (200, 2, 2),
                "a bare `box` still resolves to that box and quotes it — every request ever "
                "written against `_resolve_scope` sent `{box: N}`, so there is no migration "
                "and no second spelling on the wire for one idea",
            )
            checks.ok(
                "scopes" not in single and "boxes" not in single["total"],
                "and the answer is ONE quote. D180's rule was that the shape must not change "
                "with the request, which is why a cart's answer was always a list; with one "
                "selection per press there is one thing being quoted and a one-element list "
                "would be the cart's ghost",
            )
            checks.equal(
                single["total"]["cards"],
                2,
                "`total.cards` REPLACES `total.boxes`, which is D33's one noun change: that "
                "entry's rule is that the total is the number the operator agrees to spend, "
                "and boxes are not what is being bought — a press over 2,535 cards in five "
                "drawers reported `5`",
            )
            checks.equal(
                single["scope"],
                {"box": 3, "whole_box": True, "cards": None, "bid": None},
                "and the drawer the run WOULD record is drawn beside the figures, by the one "
                "derivation `cli/cmd_identify.py` also uses — it was two implementations held "
                "together by a comment in each pointing at the other",
            )
            checks.equal(
                single["sentence"],
                "box 3",
                "with the selection in WORDS, composed once on the server so the report, the "
                "refusals and the screen cannot describe one press three different ways",
            )

            # ----------------------------------- TWO DRAWERS ARE ONE SELECTION AND ONE RUN
            #
            # THE CART WAS USED, ONCE, AND THAT IS WHY `box` IS LIST-VALUED. D180 named its own
            # reopening condition — *"a cart that is never used with more than one box"* — and
            # the measurement does NOT meet it: on 2026-09-01T21:50:52 the operator sent boxes
            # 3, 4 and 5 in one press, three run directories created in the same second, all
            # `started_by: app`. A selection that could name one drawer would have taken a
            # capability away.
            #
            # WHAT WAS NEVER USED IS THE PER-LEG READING, which is the argument D180 actually
            # rested on: all three legs of that press carried `max_edge` 1200, 12 of 15 runs on
            # this store share that figure, and the three that differ are three separate presses
            # on three different days. So the cart survives as a list-valued FILTER and the
            # per-drawer reading does not.
            status, body, _ = request(
                port, "POST", "/pipeline/preflight", payload={"box": [3, 7]}
            )
            both = json.loads(body)
            checks.equal(
                (status, both["total"]["cards"], both["total"]["photographs"]),
                (200, 4, 4),
                "two drawers are ONE selection over four cards — one quote, one console and "
                "one reading, where a cart was two legs each re-walking a drawer",
            )
            checks.equal(
                both["scope"],
                None,
                "and it records NO drawer, because its cards are in two. That was D180's rule "
                "and it is the part of that entry this change keeps: a scope block naming one "
                "of two drawers would be a claim about cards it is wrong about",
            )
            checks.equal(
                both["sentence"],
                "boxes 3 and 7",
                "the sentence names both, in words — `boxes [3, 7]` would be a Python repr in "
                "the one line an operator reads before spending money",
            )

            # ------------------------------ THE BOX IS READ OFF THE SIDECAR, NEVER THE PATH
            #
            # THIS IS THE FAULT THE PATH ARM HAD AND THE REASON `--box` IS A FILTER. Two runs on
            # the operator's store point at a directory whose name is not the drawer their cards
            # are in: `2026-09-02-box6-01`'s 65 cards are all in box 3 today and
            # `2026-08-29-box1-01`'s 99 are too, while `^box(\d+)` answers 6 and 1 without
            # hesitating. Box 6 does not exist on that store at all.
            #
            # POSED THE SAME WAY HERE: a photograph filed under `box7/` whose sidecar says box 3.
            # `sidecar.scan` resolves the box from the SIDECAR first and the path second, so
            # `{box: 3}` must find it and `{box: 7}` must not.
            (other_dir / "0009.jpg").write_bytes(JPEG)
            (other_dir / "0009.json").write_text(
                json.dumps({"box": 3, "index": 9, "game": "pokemon", "variant": "normal"})
            )
            status, body, _ = request(port, "POST", "/pipeline/preflight", payload={"box": 3})
            checks.equal(
                (status, json.loads(body)["total"]["cards"]),
                (200, 3),
                "a photograph sitting in box7's directory whose SIDECAR says box 3 is found by "
                "a box-3 selection — the directory name is a convention and the sidecar is the "
                "claim, and no narrower scan root can see this",
            )
            status, body, _ = request(port, "POST", "/pipeline/preflight", payload={"box": 7})
            checks.equal(
                (status, json.loads(body)["total"]["cards"]),
                (200, 2),
                "and it is NOT found by a box-7 selection, though it is the only thing in that "
                "drawer's directory the path would disagree about. This is the run filed under "
                "box 6 that has no card in box 6, refused at the selection",
            )
            (other_dir / "0009.jpg").unlink()
            (other_dir / "0009.json").unlink()

            # ----------------------------- THE LEGS THAT ARE NO LONGER SPAWNED, COUNTED
            #
            # AN OUTCOME ASSERTION CANNOT SEE A WORK SAVING, which is the lesson the hash-first
            # change paid for: deleting its own gate left every outcome assertion green because
            # hash-first and decode-everything agree on every answer. So the spawn is COUNTED.
            #
            # `Popen` IS MONKEYPATCHED AND THE REAL ROUTE IS DRIVEN, which is the shape the
            # `_spawn` case below already argues for: a fixture that hands the answer to the
            # assertion cannot see the code stop doing the work. Nothing is submitted and no
            # money is spent — the patched child never executes `banchi`.
            spawned: List[list] = []

            class _Fake:
                pid = 424242
                returncode = None

                def poll(self):
                    return None

            def _record(argv, **kwargs):
                spawned.append(list(argv))
                return _Fake()

            real_popen = pipeline_routes.subprocess.Popen
            pipeline_routes.subprocess.Popen = _record
            try:
                status, body, _ = request(
                    port,
                    "POST",
                    "/pipeline/identify",
                    payload={"confirm": True, "box": [3, 7]},
                )
                answer = json.loads(body)
            finally:
                pipeline_routes.subprocess.Popen = real_popen

            checks.equal(
                (status, len(spawned)),
                (202, 1),
                "A PRESS OVER TWO DRAWERS SPAWNS ONE CHILD. The cart spawned one per box, so "
                "this is the leg that is no longer started — and the operator's own "
                "three-drawer press becomes one run instead of three, which is one join, one "
                "export fetch and one emit instead of three of each",
            )
            checks.equal(
                len(answer["started"]),
                1,
                "and the response names one run rather than a list per drawer",
            )
            checks.ok(
                answer["failed"] == [],
                "with `failed` empty and unreachable: one child cannot half-start, so the "
                "partial send the cart had to report honestly cannot happen. The key stays "
                "because the screen's notice is one length check",
            )
            checks.equal(
                answer["started"][0]["cards"],
                4,
                "the receipt says how many cards were claimed for, which is the figure "
                "`total.cards` quoted",
            )
            checks.ok(
                "--box" in spawned[0] and "3,7" in spawned[0],
                "and the SELECTION reaches the child as flags rather than as a directory of "
                "symlinks — which is the whole of what `.scopes/` was for",
            )
            checks.ok(
                not (home / ".scopes").exists(),
                "the spend built no scope directory either. Before this, a ticked selection "
                "wrote one on the way to every press, paid or refused",
            )
            for started in answer["started"]:
                shutil.rmtree(home / "runs" / started["run"], ignore_errors=True)

            # --------------------------- THE PREFLIGHT SHELLS ONE CHILD, NOT ONE PER DRAWER
            #
            # THE SAME COUNT ONE ROUTE UP, and the reason `PREFLIGHT_WORKERS` and its four-thread
            # pool are deleted. `_preflight_leg` shelled `identify --dry-run` per leg, which is a
            # full decode of every photograph in that drawer — measured at about a minute for 544
            # cards — so a cart of five held the request open for five minutes and the pool
            # existed to hide it. One selection is one command however many drawers its cards
            # are in.
            shelled: List[list] = []
            real_sync = pipeline_routes._run_sync

            def _count_sync(argv, timeout):
                shelled.append(list(argv))
                return real_sync(argv, timeout)

            pipeline_routes._run_sync = _count_sync
            try:
                request(port, "POST", "/pipeline/preflight", payload={"box": [3, 7]})
            finally:
                pipeline_routes._run_sync = real_sync
            checks.equal(
                len(shelled),
                1,
                "ONE `identify --dry-run` FOR A TWO-DRAWER PREFLIGHT. The cart ran one per leg "
                "on a four-worker pool; this is the decode pass that is no longer performed "
                "twice, and it is why the pool, the worker bound and the latency argument all "
                "went together",
            )

            # ------------------- the double-click guard is the CLAIM, and the box guard is gone
            #
            # `_busy_run` REFUSED A SECOND PRESS OVER A DRAWER A LIVE RUN WAS READING, and it
            # took a box number — there is no longer one on this route to give it. D174 built
            # its replacement and says in writing that deleting the callers is *"a separate
            # change with its own reasoning, because a guard is removed only once its
            # replacement has been exercised"*. This is that change and this is the reasoning.
            #
            # THE NARROWING, NAMED: a press whose overlap with a live run is entirely CACHE HITS
            # is no longer refused. It is also spending nothing on those cards, which is D174's
            # own rule for why an empty send list writes no row — *"It is spending nothing, so
            # there is nothing to protect."*
            #
            # THE WIDENING, WHICH IS THE HALF THAT COSTS MONEY: a live run over a pile spanning
            # two drawers is invisible to a box compare in BOTH directions, and two disjoint
            # selections in one drawer were refused for no reason at all.
            live = runs.create("box3")
            live.set(scope={"box": 3, "whole_box": True, "cards": None})
            (live.directory / "running.pid").write_text(f"{os.getpid()}\n")
            status, body, _ = request(port, "POST", "/pipeline/preflight", payload={"box": 3})
            checks.equal(
                (status, json.loads(body)["claimed"]),
                (200, None),
                "a live run that has CLAIMED NOTHING no longer withholds the confirm over its "
                "own drawer. It has nothing in flight to be double-billed for, and the guard "
                "that refused this could not see a run over two drawers at all",
            )
            with Store().write() as claiming:
                held, conflicts = claiming.submissions.claim_or_refuse(
                    {"3/1": "a" * 64}, claiming.cache
                )
            checks.ok(
                held is not None and not conflicts,
                "— and with a real claim written over card 3/1 by the command that spends",
            )
            status, body, _ = request(port, "POST", "/pipeline/preflight", payload={"box": 3})
            claimed = json.loads(body)["claimed"]
            checks.equal(
                (status, None if claimed is None else claimed["cards"]),
                (200, 1),
                "the preflight names the CARD that is held, not the drawer it is in — so the "
                "screen can withhold its confirm before the operator reaches for it, in the "
                "one vocabulary that has an answer for a press over two drawers",
            )
            # THE STRIP'S LIST (D291): what a spend over this selection would buy — every
            # photographed card it names, minus the ones a live claim holds. The screen counts,
            # prices and spends exactly this list, so it must leave the claimed card out.
            status, body, _ = request(port, "POST", "/pipeline/waiting", payload={"box": 3})
            waiting = json.loads(body)
            checks.equal(
                (status, "3/1" in waiting["keys"], waiting["claimed"], len(waiting["keys"]) > 0),
                (200, False, 1, True),
                "POST /pipeline/waiting leaves out the card a live run has claimed, and says it did "
                "— so Review's strip never offers to buy what is already being paid for",
            )
            status, body, _ = request(port, "POST", "/pipeline/waiting", payload={"box": 7})
            checks.equal(
                (status, json.loads(body)["claimed"]),
                (200, 0),
                "and it claims nothing held over a drawer nobody is paying to read",
            )
            status, body, _ = request(port, "POST", "/pipeline/preflight", payload={"box": 7})
            checks.equal(
                json.loads(body)["claimed"],
                None,
                "and a press over cards nobody is holding is not refused, whatever drawer they "
                "are in — two live batches over DIFFERENT cards is two answers for two "
                "invoices, which is what the Batch API takes in parallel",
            )
            status, body, _ = request(
                port,
                "POST",
                "/pipeline/identify",
                payload={"confirm": True, "box": [7, 3]},
            )
            checks.equal(
                (status, error_code(body)),
                (409, "cards_already_claimed"),
                "and a press whose selection reaches one claimed card refuses WHOLE before "
                "anything is spawned, naming the receipt and the count — the courtesy half of "
                "D174's guard, at the press, instead of a child that starts, refuses and dies "
                "as a red row on the screen",
            )
            checks.equal(
                sorted(entry.name for entry in (home / "runs").iterdir()),
                [live.directory.name],
                "and NOTHING was spawned by it: the only run directory on disk is the one this "
                "case created by hand, so the refusal cost no invoice and left no row",
            )
            with Store().write() as releasing:
                releasing.submissions.release(held.receipt)
            (live.directory / "running.pid").unlink()
            shutil.rmtree(live.directory)

            # ------------------------------------- the pid the server itself is holding
            #
            # THE FIRST CHILD PROCESS ANY TEST IN THIS HARNESS HAS STARTED, and the argument
            # for it is in `_live_pid`'s own docstring: a detached child is still a CHILD
            # (`start_new_session` is setsid, a new session and not a new parent), nothing
            # ever waited on one, and an unwaited child that exits is a ZOMBIE whose pid
            # `os.kill(pid, 0)` accepts. The route said `Running 8m` about a run that had
            # finished in 3m52s, and `_busy_run` refused that run's own box for just as long.
            #
            # IT CANNOT LEAK. The child's only instruction is to read a pipe this process
            # holds, so it exits by itself the moment this process does — pass, fail, raise or
            # kill. It is ended by CLOSING that pipe and never by a signal, and it is waited
            # on, here, before the block ends. Compare scripts/reap-selftest.sh, which spawns
            # `sleep 300` in its own session and needs a trap to clean up after itself.
            #
            # A REAL ZOMBIE IS NOT POSED AND IS NOT WHAT NEEDS PROVING. `os.waitid` — the one
            # call that waits for exit while LEAVING the zombie — is absent on macOS, and the
            # pipe-EOF approximation races the kernel: fds close in exit_files() before
            # exit_notify() marks the task reapable, so the assertion would flake at every
            # turn end. `os.getpid()` in the marker is the STRONGER lie anyway — not a pid
            # that is merely unreaped, but one that is unambiguously alive. That
            # `os.kill(<zombie>, 0)` succeeds is a fact about Darwin, measured by hand.
            #
            # OBSERVED FAILING FIRST, AND EACH ONE THROUGH THE ASSERTION THAT OWNS IT. Seven
            # mutations were run against this block before it was kept:
            #
            #   the marker read before the table            5 red, headed by the finished child
            #   the table's "exited" read as "silent"       4 red, headed by the finished child
            #   the running branch demoted by the files     3 red, the live-and-collected case
            #   the dead handle DELETED rather than kept    3 red, headed by the SECOND read
            #   `_spawn` registering nothing (as it stood)  2 red, the `_spawn` case below
            #   the orphan floor dropped (signal 0 alone)   2 red, the orphan case
            #   `pid <= 0` admitted                         2 red, the marker-holding-zero case
            #
            # AND THE FIFTH ARM SURVIVED THE FIRST TIME, WHICH IS WHY THE `_spawn` CASE EXISTS.
            # That arm deletes the registration from `_spawn` — it is not a hypothetical, it is
            # the code as it stood and the whole defect — and every case in this block stayed
            # GREEN through it, because the block hands the handle to `_remember_child` itself
            # rather than earning it. A guard has to see its subject. The case further down
            # monkeypatches `Popen` and drives the real `_spawn`, and the arm is red now.
            #
            # `_busy_run` HAD no arms of its own: it consumed `_live_pid` and nothing else, so
            # every arm above was red at the preflight too and the two preflight reads in this
            # block proved the CONSUMPTION rather than new coverage. That guard is deleted —
            # it compared BOX numbers and the route no longer takes one — and the consumption
            # is asserted by the `GET /pipeline/runs/<name>` reads instead, which is where
            # `live`, `pid` and `phase` come from. Two lines carry no arm at all and
            # are named rather than implied: the eviction guard, which cannot be posed without
            # 64 spawns, and the false-alive answer `_CHILDREN_LOCK` prevents, which is a
            # CPython race that cannot be produced on demand. Both are argued against the
            # stdlib source in `_child_of`'s docstring; neither is asserted.
            child = subprocess.Popen(
                [sys.executable, "-c",
                 "import sys; sys.stdout.write('u'); sys.stdout.flush(); sys.stdin.read()"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            )
            held = None
            try:
                checks.equal(
                    child.stdout.read(1),
                    b"u",
                    "the stand-in child is up before anything is asserted about it — a child "
                    "that died on startup would make the live case green for the wrong reason",
                )
                held = runs.create("box3")
                held.set(
                    capture_dir=str(box_dir),
                    scope={"box": 3, "whole_box": True},
                    # COLLECTED, AND NO `identifications.json`. Both halves are load-bearing:
                    # the first is what a rule letting the files demote a RUNNING child fails
                    # on, and the second is what stops the orphan floor answering for the
                    # table here.
                    collected=True,
                )
                (held.directory / "running.pid").write_text(f"{os.getpid()}\n")
                pipeline_routes._remember_child(held.directory, child)

                status, body, _ = request(
                    port, "GET", f"/pipeline/runs/{held.directory.name}")
                payload = json.loads(body)
                checks.equal(
                    (status, payload["live"], payload["phase"]),
                    (200, True, "identifying"),
                    "a run whose child this server is still holding is live, and the files do "
                    "NOT demote it — cmd_identify.py writes collected before the record and "
                    "before a whole locked store write, so a rule letting them outrank a "
                    "running child puts `Needs join` on the screen while identify is writing",
                )
                # THE PREFLIGHT IS NO LONGER ASKED HERE, and that is a deletion rather than a
                # gap. These two reads used to assert `busy_run` over this run's box, and this
                # block's own note below records what they were worth: *"`_busy_run` is given no
                # arms of its own: it consumes `_live_pid` and nothing else... the two preflight
                # cases here prove the CONSUMPTION, not new coverage."* That guard is gone with
                # the box it compared, and the `GET /pipeline/runs/<name>` read directly above
                # this reads `live`, `pid` and `phase` off `_live_pid` — so the consumption is
                # still asserted, through the reader that still exists.

                # THE CHILD ENDS BY LOSING ITS PIPE. No signal is sent to anything.
                child.stdin.close()
                checks.equal(
                    child.wait(timeout=10),
                    0,
                    "the child exits on its own when its pipe closes, and is waited on here — "
                    "this test reaps what it starts rather than leaving the harness to",
                )

                status, body, _ = request(
                    port, "GET", f"/pipeline/runs/{held.directory.name}")
                payload = json.loads(body)
                checks.equal(
                    (payload["live"], payload["pid"], payload["phase"]),
                    (False, None, "join"),
                    "THE CASE THAT WAS THE BUG: the child is gone and `running.pid` still "
                    "names a pid signal 0 accepts — this test's own — and the run is NOT "
                    "live. Signal 0 answers yes to a zombie exactly as it answers yes here, "
                    "which is how a finished run said `Running 8m` until something else in "
                    "the process happened to construct a Popen and reap it by accident",
                )
                status, body, _ = request(
                    port, "GET", f"/pipeline/runs/{held.directory.name}")
                checks.equal(
                    json.loads(body)["live"],
                    False,
                    "and it is still not live on the SECOND read — a dead handle is a "
                    "TOMBSTONE and is not dropped when it is found dead. A table that forgot "
                    "the pid it had just buried would fall back to the marker, whose pid is "
                    "alive, and report Running again",
                )

                (held.directory / "running.pid").write_text("0\n")
                with pipeline_routes._CHILDREN_LOCK:
                    pipeline_routes._CHILDREN.pop(
                        pipeline_routes._child_key(held.directory), None)
                status, body, _ = request(
                    port, "GET", f"/pipeline/runs/{held.directory.name}")
                checks.equal(
                    json.loads(body)["live"],
                    False,
                    "a marker holding 0 is not a pid — `os.kill(0, 0)` probes the CALLER'S "
                    "own process group and always succeeds, so this read as live forever",
                )
            finally:
                with contextlib.suppress(Exception):
                    child.stdin.close()
                if child.poll() is None:
                    child.kill()          # last resort, and only ever at a handle we own
                child.wait(timeout=5)
                if held is not None:
                    with pipeline_routes._CHILDREN_LOCK:
                        pipeline_routes._CHILDREN.pop(
                            pipeline_routes._child_key(held.directory), None)
                    shutil.rmtree(held.directory, ignore_errors=True)

            # AND `_spawn` ITSELF REGISTERS, WHICH THE BLOCK ABOVE CANNOT SEE. It hands the
            # handle to `_remember_child` by hand, so deleting that call from `_spawn` — which
            # IS the code as it stood, and the whole defect — left every case above green. A
            # guard has to see its subject. `subprocess.Popen` is monkeypatched so nothing is
            # started and no money can be spent: this section's own header says a test proving
            # the happy path would have to submit a real Batch, and that is still true of
            # everything except the two lines at the end of `_spawn`.
            real_popen = pipeline_routes.subprocess.Popen
            started = {}

            class _FakePopen:
                def __init__(self, argv, **kwargs):
                    started["argv"] = argv
                    self.pid = 424242
                    self.returncode = None

                def poll(self):
                    return self.returncode

            pipeline_routes.subprocess.Popen = _FakePopen
            try:
                leg = pipeline_routes.Send(
                    selection=selection.Selection(box=(3,)),
                    flags=[],
                    label="box3",
                )
                answer = pipeline_routes._spawn(leg, [])
                spawned = Path(answer["path"])
                checks.equal(
                    (
                        pipeline_routes._child_of(spawned) is not None,
                        (spawned / "running.pid").read_text().strip(),
                    ),
                    (True, "424242"),
                    "`_spawn` puts the child in the table AND writes the marker — the table "
                    "first, so a poll landing between the two still reads a just-started run "
                    "as live. Without the first of those nothing ever reaped a detached child "
                    "and `_live_pid` fell through to a pid that signal 0 accepts forever",
                )
            finally:
                pipeline_routes.subprocess.Popen = real_popen
                with pipeline_routes._CHILDREN_LOCK:
                    pipeline_routes._CHILDREN.pop(
                        pipeline_routes._child_key(spawned), None)
                shutil.rmtree(spawned, ignore_errors=True)

            # The orphan: no handle, a pid that is alive by construction, and a record on
            # disk. This is the case that fixes `Running 8m` ACROSS A RESTART, where the child
            # belongs to launchd and this server has never heard of it.
            orphan = runs.create("box3")
            orphan.set(capture_dir=str(box_dir), scope={"box": 3, "whole_box": True},
                       collected=True)
            orphan.write_identifications({"prompt_fingerprint": "x", "cards": {}})
            (orphan.directory / "running.pid").write_text(f"{os.getpid()}\n")
            status, body, _ = request(port, "GET", f"/pipeline/runs/{orphan.directory.name}")
            payload = json.loads(body)
            checks.equal(
                (payload["live"], payload["phase"]),
                (False, "join"),
                "a run THIS SERVER DID NOT START — an orphan across a restart — is judged by "
                "the marker AND by the run's own record: the pid is alive by construction, "
                "and a run that has already written identifications.json has finished the "
                "step this liveness is about, so whatever holds that pid now it is not this "
                "run's identify. The floor is that file and not `collected`, which stays true "
                "through the whole tail after it",
            )
            shutil.rmtree(orphan.directory)

            # ------------------------------------------ what the run cost, and whose figure
            #
            # OBSERVED FAILING FIRST. Four mutations of `_usage`, all red:
            #
            #   the branch order INVERTED (compute wins)    2 red, the $9.99 case
            #   a missing token count answers zero          3 red, the empty and bogus cases
            #   the backfill not declared on the wire       1 red, the filled-in case
            #   the backfill dropped entirely               1 red, the filled-in case
            #
            # The first is the one worth the $9.99: an inverted order is otherwise SILENT,
            # because today's rates and a figure recorded today are the same number. Only a
            # recorded figure the rates cannot produce can tell the two apart.
            priced = runs.create("box3")
            priced.set(collected=True,
                       usage={"input_tokens": 290470, "output_tokens": 3761})
            status, body, _ = request(port, "GET", f"/pipeline/runs/{priced.directory.name}")
            usage = json.loads(body)["usage"]
            checks.equal(
                (usage["cost_usd"], usage["cost_backfilled"]),
                (cost.recorded(290470, 3761), True),
                "a run that recorded its tokens and not its cost gets the figure filled in at "
                "the READ, from identify/cost.py and not from a second rate sheet here — and "
                "SAYS it was filled in, because the two answers are the same number only "
                "until the price sheet moves. Every run written before 2026-09-11 is this "
                "case, including the one the defect was reported against",
            )
            shutil.rmtree(priced.directory)

            kept = runs.create("box3")
            kept.set(collected=True,
                     usage={"input_tokens": 290470, "output_tokens": 3761, "cost_usd": 9.99})
            status, body, _ = request(port, "GET", f"/pipeline/runs/{kept.directory.name}")
            usage = json.loads(body)["usage"]
            checks.equal(
                (usage["cost_usd"], usage.get("cost_backfilled")),
                (9.99, None),
                "and a RECORDED figure is passed through untouched even where today's rates "
                "would say otherwise — a run is an immutable input and what it cost is what "
                "it cost. $9.99 against tokens that price at $0.15 is deliberate: nothing but "
                "the correct branch order can make this pass, and an inverted one is silent",
            )
            shutil.rmtree(kept.directory)

            blank = runs.create("box3")
            blank.set(collected=True, usage={})
            status, body, _ = request(port, "GET", f"/pipeline/runs/{blank.directory.name}")
            checks.equal(
                json.loads(body)["usage"],
                {},
                "a run with no token counts answers NOTHING rather than zero — a confident "
                "$0.00 is worse than a blank, because a blank is visibly a blank and a zero "
                "is a claim that the run was free. `_total` states the same rule",
            )
            shutil.rmtree(blank.directory)

            bogus = runs.create("box3")
            bogus.set(collected=True,
                      usage={"input_tokens": True, "output_tokens": "3761"})
            status, body, _ = request(port, "GET", f"/pipeline/runs/{bogus.directory.name}")
            checks.equal(
                json.loads(body)["usage"].get("cost_usd"),
                None,
                "and a token count that is not a whole number is refused rather than coerced "
                "— `isinstance(True, int)` is True in Python, so `bool` is excluded BY NAME, "
                "and a hand-edited manifest is exactly what `_phase`'s own comment braces "
                "against one field over",
            )
            shutil.rmtree(bogus.directory)

            # -------------------------------------------------- reading runs, and refusals
            status, body, _ = request(port, "GET", "/pipeline/runs")
            checks.equal(
                (status, json.loads(body)["runs"]),
                (200, []),
                "the run list answers an empty store with an empty list rather than a 404 "
                "— a screen that has done nothing yet is not an error",
            )
            status, body, _ = request(port, "GET", "/pipeline/runs/nope-01")
            checks.equal(
                (status, error_code(body)),
                (404, "no_such_run"),
                "a run that does not exist answers in its own code",
            )
            status, body, _ = request(port, "GET", "/pipeline/runs/..")
            checks.equal(
                status,
                404,
                "and a name that is not a run name never reaches the filesystem at all — "
                "the route pattern admits no separator and no dot-dot",
            )

            # ------------------------------------------------- a real run directory, read
            made = runs.create("box3")
            made.set(capture_dir=str(box_dir), scope={"box": 3, "whole_box": True})
            (made.directory / "console.log").write_text("$ banchi identify\nphotographs 2\n")
            (made.directory / "import-listed.csv").write_text("TCGplayer Id,Add to Quantity\n1,2\n")

            status, body, _ = request(port, "GET", f"/pipeline/runs/{made.directory.name}")
            payload = json.loads(body)
            checks.equal(
                (status, payload["phase"], payload["live"]),
                (200, "ready", False),
                "a run with a manifest and no batch ids reads as `ready` and not live — the "
                "phase is DERIVED from the directory on every read, because cli/runs.py "
                "makes a run an immutable input and a phase held anywhere else would be a "
                "second answer to a question the files already answer",
            )
            checks.ok(
                "photographs 2" in payload["console"],
                "the console tail is served from the child's own log, so a screen polling "
                "this route reads exactly what the command printed",
            )
            checks.equal(
                sorted(row["name"] for row in payload["files"]),
                ["console.log", "import-listed.csv", "manifest.json"],
                "artefacts are listed off the DIRECTORY rather than off a table of names "
                "here — runs.import_listed_name makes the import files per-game, and a "
                "hard-coded list would stop offering them for every game added later",
            )
            checks.equal(
                [row["is_import"] for row in payload["files"] if row["name"].endswith(".csv")],
                [True],
                "and the import file is flagged as one, which is what lets the screen offer "
                "the download the owner actually came for",
            )

            # ------------------------------------------------- which drawer, and its name
            #
            # D56. The screens that list runs drew a box NUMBER and nothing else, on a store
            # whose boxes have been named since D20 — `#/pricing`'s picker offered
            # `2026-08-30-box3-01` over `15 SKUs` while the registry held `RB Epics`. The join
            # is the server's because the name lives in the store, which no screen drawing a
            # run list had read.
            checks.equal(
                (payload["box"], payload["box_name"]),
                (3, None),
                "a run reports the box it is over, and a box the registry has never heard "
                "of reports no name rather than an invented one — D20 leaves a name optional, "
                "so unnamed is an ordinary box and not a fault to mark",
            )

            capture_server.do_create_box({"box": 3, "name": "RB Epics"})
            status, body, _ = request(port, "GET", f"/pipeline/runs/{made.directory.name}")
            checks.equal(
                json.loads(body)["box_name"],
                "RB Epics",
                "naming the box names the run, WITHOUT the run being touched — the join runs "
                "at read time against the registry, so nothing had to be written into a "
                "manifest that `cli/runs.py` makes an immutable input",
            )

            # THE ASSERTION THAT MAKES THE READ-TIME JOIN LOAD-BEARING, and the one a stored
            # name would fail. D20 makes a rename a live edit that relabels every card in the
            # box on every screen that draws one; a name copied into a run directory when the
            # run was created would go on saying `RB Epics` here forever.
            capture_server.do_put_box(3, {"name": "Riftbound epics"})
            status, body, _ = request(port, "GET", f"/pipeline/runs/{made.directory.name}")
            checks.equal(
                json.loads(body)["box_name"],
                "Riftbound epics",
                "and a RENAME reaches the run on the next read, which is the property a name "
                "stored on the run could not have",
            )

            # A RUN STARTED IN A TERMINAL IS PLACED AND NAMED BY ITS OWN SCOPE BLOCK, which
            # `cli/cmd_identify.py:_scope_for` has written since D145 — off the SIDECARS, not
            # off the capture directory's name.
            legacy = runs.create("box3")
            legacy.set(
                capture_dir=str(box_dir), scope={"box": 3, "whole_box": True, "cards": None}
            )
            status, body, _ = request(port, "GET", "/pipeline/runs")
            listed = {row["run"]: row for row in json.loads(body)["runs"]}
            checks.equal(
                (
                    listed[legacy.directory.name]["box"],
                    listed[legacy.directory.name]["box_name"],
                ),
                (3, "Riftbound epics"),
                "a run started from a TERMINAL is placed and named, off the scope block its "
                "own command wrote — and the name still joins at read time",
            )

            # AND A RUN WITH NEITHER NAMES NO DRAWER, WHICH IS THE DELETION
            # (D180). `_run_box` used to parse `^box(\d+)` off the capture
            # directory's basename for exactly this run, and it was CONFIDENTLY WRONG twice on
            # the operator's store: `2026-09-02-box6-01`'s 65 cards are all in box 3 today and
            # `2026-08-29-box1-01`'s 99 are too, while the regex answers 6 and 1. Box 6 has
            # never existed there.
            #
            # NULL IS WHAT EVERY READER OF THIS FIELD WANTED. `runScope.ts:runBoxLabel` draws no
            # drawer for it, `refuse_reallocated` (D36) has nothing to compare and reports the
            # run unverified rather than passing it onto another drawer's records, and a run
            # filed under the wrong drawer is the one fault none of them can detect — because a
            # wrong box number resolves.
            #
            # WHAT IT COSTS is the label on a pre-D145 terminal run that has never been
            # re-joined: two on that store, and it was answering WRONGLY for both.
            unsaid = runs.create("box3")
            unsaid.set(capture_dir=str(box_dir))
            status, body, _ = request(port, "GET", "/pipeline/runs")
            listed = {row["run"]: row for row in json.loads(body)["runs"]}
            checks.equal(
                (
                    listed[unsaid.directory.name]["scope"],
                    listed[unsaid.directory.name]["box"],
                    listed[unsaid.directory.name]["box_name"],
                ),
                (None, None, None),
                "a run whose manifest names NO scope draws no drawer at all — the capture "
                "directory's name is a convention and the sidecar is the claim, so a number "
                "read off a folder is a guess that resolves, which is the one kind nothing "
                "downstream can catch",
            )
            shutil.rmtree(unsaid.directory)
            checks.equal(
                listed[made.directory.name]["box_name"],
                "Riftbound epics",
                "and the LIST carries it as well as the single-run route, off one registry "
                "read for the whole list — this is the polled route, at 4s while anything is "
                "live, so a read per row would be a read per run per poll",
            )
            # A REALLOCATED BOX NUMBER, which is the one shape the read-time join cannot
            # get right on the number alone. D20 hands out the lowest FREE integer, so a box
            # that goes and another that arrives share a number and this map — keyed by the
            # number — holds the newcomer's name under the old run's box. Observed on the
            # owner's store: `2026-08-22-box1-03` drew `UNL Rares`, a registry entry made
            # seven days later over none of that run's 53 cards.
            #
            # BOTH CONDITIONS ARE ASSERTED SEPARATELY BELOW, because the first version of
            # this rule used the timestamp alone and broke the name-it-later flow three
            # assertions up — a box named after its run is ordinary, and that case is
            # already covered, so what is left is to prove the card set is what carries it.
            stranger = runs.create("box3")
            stranger.set(
                capture_dir=str(box_dir),
                scope={"box": 3, "whole_box": True, "cards": None},
                created_at="2000-01-01T00:00:00+00:00",
            )
            status, body, _ = request(port, "GET", f"/pipeline/runs/{stranger.directory.name}")
            checks.equal(
                json.loads(body)["box_name"],
                "Riftbound epics",
                "a box holding NO cards disowns nobody, so a run older than the registry "
                "entry is still named — an empty box is not evidence that the drawer "
                "changed, and refusing the name there would break naming a box afterwards",
            )

            with Store().write() as snapshot:
                seeded, _ = snapshot.inventory.allocate_capture(
                    3, capture_id="reallocated-1", cid=fake_cid("reallocated-1")
                )
                snapshot.inventory.record_identification(
                    seeded.key,
                    name="Moonfall",
                    number="198/219",
                    printed_total="219",
                    confidence="high",
                    run=made.directory.name,
                )
            status, body, _ = request(port, "GET", f"/pipeline/runs/{stranger.directory.name}")
            checks.equal(
                json.loads(body)["box_name"],
                None,
                "and once the box holds cards and NONE of them is this run's, the name is "
                "withheld — the drawer under that number is somebody else's, and naming it "
                "would put a label on a run over 53 cards that are no longer in the store",
            )
            status, body, _ = request(port, "GET", f"/pipeline/runs/{made.directory.name}")
            checks.equal(
                json.loads(body)["box_name"],
                "Riftbound epics",
                "while the run those cards DO belong to keeps its name, which is what stops "
                "this being a rule that simply stops naming a reused box for everyone",
            )
            shutil.rmtree(stranger.directory)

            shutil.rmtree(legacy.directory)

            # ----------------------------------------------------------- the file download
            status, body, headers = request(
                port,
                "GET",
                f"/pipeline/runs/{made.directory.name}/file?name=import-listed.csv",
            )
            checks.equal(
                (status, headers.get("Content-Type")),
                (200, "text/csv"),
                "an import file downloads as CSV, which is the whole point of the route: "
                "before it, an emitted file existed only as a filename in terminal output "
                "the owner never saw when somebody else was driving the commands",
            )
            for name, expected in (
                ("../../etc/passwd", "file_name_invalid"),
                ("no-such-file.csv", "no_such_file"),
            ):
                status, body, _ = request(
                    port,
                    "GET",
                    f"/pipeline/runs/{made.directory.name}/file?name="
                    + urllib.parse.quote(name),
                )
                checks.equal(
                    error_code(body),
                    expected,
                    f"and {name!r} is refused as {expected} — matched by shape and THEN by "
                    f"membership of what this run lists, so a pattern loosened later still "
                    f"cannot reach outside the run directory",
                )

            # ----------------------------------------------------------- the free steps
            status, body, _ = request(
                port,
                "POST",
                f"/pipeline/runs/{made.directory.name}/identify",
                payload={},
            )
            checks.equal(
                (status, error_code(body)),
                (404, "no_such_step"),
                "identify is NOT reachable as a step on a run — it costs money, so it has "
                "its own route and its own confirm rather than hiding among three free ones",
            )
            for payload, expected, label in (
                (
                    {"rule": "undercut:oops"},
                    "rule_invalid",
                    "a pricing rule is validated before it reaches argv",
                ),
                (
                    {"basis": "vibes"},
                    "basis_invalid",
                    "as is the basis",
                ),
                (
                    {"exports": []},
                    "exports_invalid",
                    "an empty exports array is refused rather than read as `re-use what the "
                    "manifest recorded` — absent means that, and the two must not collapse",
                ),
                (
                    {"exports": [{"name": "x.csv", "content": "not a spreadsheet"}]},
                    "export_not_csv",
                    "and a file with no comma on its first line is refused HERE rather than "
                    "several seconds later by an empty-catalog message about product lines",
                ),
            ):
                status, body, _ = request(
                    port,
                    "POST",
                    f"/pipeline/runs/{made.directory.name}/join",
                    payload=payload,
                )
                checks.equal((status, error_code(body)), (400, expected), label)

        finally:
            httpd.shutdown()
            thread.join(timeout=5)

    # --- an uploaded export carries its own time, and the stored copy wears it ------------
    # D87 amended: the stored file's mtime is when its `Total Quantity` was read, and the
    # store arbitrates `live` by it. Both `join`'s uploads and the `--live` upload land here.
    with isolated_home():
        directory = files.inventory_dir() / ".reconcile"
        directory.mkdir(parents=True, exist_ok=True)
        content = "TCGplayer Id,Total Quantity\n1,2\n"
        when = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
        stored = pipeline_routes._store_upload(
            directory,
            {"name": "my.csv", "content": content, "modified": int(when.timestamp() * 1000)},
            "live-",
        )
        checks.equal(
            runs.describe_source(stored)["mtime"],
            "2026-09-01T12:00:00.000+00:00",
            "an upload sent with `modified` — `File.lastModified`, in MILLISECONDS — lands "
            "with THAT mtime, because the write time would date a week-old export to now and "
            "let it outrank every reading the store has taken since",
        )
        plain = pipeline_routes._store_upload(
            directory, {"name": "plain.csv", "content": content}, "live-"
        )
        checks.ok(
            abs(plain.stat().st_mtime - time.time()) < 60,
            "and one sent without it still lands, at the write time",
        )
        odd = pipeline_routes._store_upload(
            directory, {"name": "odd.csv", "content": content, "modified": 12}, "live-"
        )
        checks.ok(
            abs(odd.stat().st_mtime - time.time()) < 60,
            "an unsane stamp — before 2000 here — is ignored rather than trusted: a bogus "
            "one reading as newer than everything would settle the whole store",
        )


def check_pricing_reach(checks: Checks) -> None:
    """A price is a fact about a listing, and the store remembers listings it never saw (D109).

    THE FIVE PROPERTIES THIS FEATURE RESTS ON, and every one of them replaced something that
    was true until 2026-09-06. The measurement that drove it is in D109: 232 of 387 live SKUs
    refused on a card-table fact, carrying 97.4% of the operator's asking value.
    """
    from pipeline import corpus as corpus_mod, decisions as decisions_mod, reprice, pricing

    # -------------------------------------------------- the sighting is monotone
    entry = master.Listing(sku="X")
    checks.equal(
        (entry.first_seen_live, entry.priced_at),
        (None, None),
        "a fresh listing has seen nothing and priced nothing — absent is not a date",
    )
    entry.sight("2026-09-06T00:00:00.000+00:00")
    entry.sight("2026-09-07T00:00:00.000+00:00")
    checks.equal(
        entry.first_seen_live,
        "2026-09-06T00:00:00.000+00:00",
        "THE FIRST SIGHTING IS MONOTONE — a LATER reading never moves it. This is the whole "
        "difference from `observe_live`, which arbitrates a quantity and takes the NEWER "
        "reading: an age settles on the oldest evidence or it is not an age",
    )
    entry.sight("2026-09-01T00:00:00.000+00:00")
    checks.equal(
        entry.first_seen_live,
        "2026-09-01T00:00:00.000+00:00",
        "and an EARLIER reading does move it — a second export can only sharpen the answer",
    )
    before = entry.first_seen_live
    entry.sight(None)
    checks.equal(
        entry.first_seen_live,
        before,
        "a reading with no stamp writes nothing. `None` is not an early date, and a sighting "
        "that cannot be placed in time is not evidence about age",
    )

    # -------------------------------------------------- the stamp, never the figure
    entry.price_set("2026-09-06T12:00:00.000+00:00")
    checks.equal(
        entry.priced_at,
        "2026-09-06T12:00:00.000+00:00",
        "`price_set` records WHEN this store set a price",
    )
    checks.ok(
        not any(
            "price" in name and name not in ("priced_at",)
            for name in vars(entry)
        ),
        "AND NOWHERE DOES IT RECORD WHAT THE PRICE WAS. The figure is live at TCGplayer and "
        "comes back on the next export as `asking`; a copy here would be a second money "
        "truth able to disagree with the first on the one field a buyer can see (D109)",
    )

    # -------------------------------------------------- membership is not a refusal
    checks.equal(
        tuple(reprice.UNPRICEABLE_CODES),
        (reprice.SOLD_OUT,),
        "THE ONLY UNPRICEABLE CODE IS `sold_out`, which is a fact about the LISTING — there "
        "is nothing live for a price to edit. `not_this_store` was in this tuple until "
        "2026-09-06 and refused 94.5% of the owner's live book by asking value (D109)",
    )

    # -------------------------------------------------- the sighting beats the proxy
    row = {
        tcgcsv.SKU_COLUMN: "5550001", tcgcsv.PRODUCT_LINE_COLUMN: "Pokemon",
        tcgcsv.NAME_COLUMN: "Stranger", tcgcsv.CONDITION_COLUMN: "Near Mint",
        tcgcsv.MARKET_PRICE_COLUMN: "10.00", tcgcsv.PRICE_COLUMN: "20.00",
        tcgcsv.LIVE_QUANTITY_COLUMN: "2",
    }
    old = "2026-01-01T00:00:00.000+00:00"
    cuts = pricing.Rule.parse(f"{pricing.RULE_UNDERCUT}:10")
    never_held = reprice.plan(
        [row], owned_since={}, listed_since={"5550001": old}, days=7, rule=cuts
    )
    checks.equal(
        [c.sku for c in never_held.rows],
        ["5550001"],
        "A SKU NO CARD HERE EVER CARRIED IS PRICED, dated by its own first sighting. This "
        "returned zero rows and one `not_this_store` refusal until 2026-09-06 — the row the "
        "$7,000 Kai'Sa and a $2,000 box case asking under market were both sitting in",
    )
    checks.equal(
        never_held.dated.get("sighting"),
        1,
        "and the report can say WHICH CLOCK dated it, so the proxy paragraph is printed only "
        "where the proxy is actually used (D100's rule, pointed both ways)",
    )
    undatable = reprice.plan([row], owned_since={}, days=7, rule=cuts)
    checks.equal(
        [c.skip for c in undatable.skipped.get(reprice.TOO_YOUNG, [])],
        [reprice.TOO_YOUNG],
        "WITH NEITHER CLOCK IT IS `too_young`, not priced on a guess. Membership stopped "
        "being a refusal; being undatable did not",
    )

    # -------------------------------------------------- a dead row is not a worklist row
    gone = dict(row)
    gone[tcgcsv.SKU_COLUMN] = "5550002"
    gone[tcgcsv.LIVE_QUANTITY_COLUMN] = "0"
    both = reprice.plan(
        [row, gone], owned_since={}, listed_since={"5550001": old, "5550002": old},
        days=7, rule=cuts,
    )
    checks.equal(
        [c.skip for c in both.skipped.get(reprice.SOLD_OUT, [])],
        [reprice.SOLD_OUT],
        "a row TCGplayer holds no copies of is still REFUSED and still counted — the operator "
        "is told how many of their export is dead",
    )
    checks.equal(
        sorted(c.sku for c, _standing in both.surveyed()),
        ["5550001"],
        "BUT IT IS NOT IN THE SURVEY, which is what the lens draws. `sold_out` is the one "
        "member of `UNPRICEABLE_CODES`, so the row can never be answered and is only "
        "something to scroll past — 372 of 759 rows on the owner's export. The EXPORT keeps "
        "them: `reconcile --live` reads a zero quantity to see a SKU sell out, and "
        "`livecheck` tells a zero row from a SKU absent altogether",
    )
    checks.equal(
        sorted(c.sku for c, standing in undatable.surveyed() if standing == "refused"),
        ["5550001"],
        "A LIVE ROW THE RULE REFUSED IS STILL DRAWN — this one is `too_young`. That is D103's "
        "rule and the reason the drop above is narrow: staleness is a FILTER over rows the "
        "operator can still price by hand, and only a row that cannot be priced at all goes",
    )
    checks.equal(
        both.considered,
        2,
        "and `considered` still counts it, so no row goes missing from the arithmetic the "
        "report prints",
    )

    # ------------------------------------------ a store may not hold a cap at all (D7)
    # RETIRED IN THREE STEPS AND THIS IS THE LAST. D7's playset was a standing bound applied to
    # every send whether or not anybody asked; 2026-09-07 made it opt-in but left
    # `policy.live_cap` readable, so a corpus that had ever been saved carried four; 2026-09-08
    # deletes the key. `LIVE_QUANTITY_CAP` survives only as the figure a press may offer.
    checks.ok(
        "live_cap" not in corpus_mod.Corpus.parse({"skus": {}}).to_payload()["policy"],
        "A STORE CANNOT HOLD A STANDING CAP. The key is gone from `policy` rather than "
        "defaulted to None, which is what makes the retirement stick: `to_payload` wrote it "
        "unconditionally, so any default it carried was stamped into the file on the first "
        "save and found by every later read",
    )
    refusal = checks.raises(
        decisions_mod.MalformedDecisions,
        lambda: corpus_mod.Corpus.parse({"policy": {"live_cap": 4}, "skus": {}}),
        "AND A STORE THAT STILL HOLDS ONE IS REFUSED BY NAME rather than silently uncapped. "
        "Ignoring the key would remove a bound the operator had asked for, without saying so "
        "— D86's rule about a legacy file, applied to a legacy KEY: read as a fallback and "
        "ignored in silence are one defect wearing two coats. `Corpus.parse` rebuilds "
        "`policy` from named fields and `keep` preserves only unknown TOP-LEVEL keys, so an "
        "unrecognised policy key is destroyed on the next write — which is what makes silence "
        "here irreversible as well as quiet",
    )
    checks.ok(
        "cap when you send" in str(refusal or ""),
        "and the refusal NAMES THE WAY FORWARD — a cap asked for at the send — rather than only reporting that "
        "the key is unwelcome, which is the shape every refusal in this pipeline takes",
    )
    checks.ok(
        "live_cap" not in corpus_mod.Corpus.parse(
            {"policy": {"live_cap": None}, "skus": {}}
        ).to_payload()["policy"],
        "`null` PASSES AND IS DROPPED — it is what a store that cleared its cap holds, and "
        "what `to_payload` wrote for as long as the key existed, so refusing it would refuse "
        "every store this change has already touched",
    )
    checks.equal(
        sorted(corpus_mod.Corpus.parse(
            {"policy": {"per_run": {"r1": {"threshold": "2.00"}}}, "skus": {}}
        ).policy_for("r1").keys()),
        ["basis", "rule", "sub_threshold", "threshold"],
        "AND THE PER-RUN OVERRIDE SURVIVES ITS OTHER KEYS. `policy_for` folds the override "
        "over a `standing` dict, so removing one member had to leave the other four alone — "
        "`#/pricing` writes a per-run `threshold` and would lose it if the fold had been "
        "narrowed instead",
    )
    for bad in ("four", 0, -1):
        checks.raises(
            decisions_mod.MalformedDecisions,
            lambda bad=bad: decisions_mod.parse_live_cap(bad),
            f"a present-and-unusable cap ({bad!r}) is REFUSED rather than clamped — a cap of "
            f"zero emits nothing for every SKU and would read as a broken pipeline. The "
            f"parser survives the key's deletion because `--cap` still runs through it",
        )

    # -------------------------------------------------- the channel is an allow-list
    mixed = corpus_mod.Corpus(
        answers={
            "A": corpus_mod.Answer(value="1.00", channel="price"),
            "B": corpus_mod.Answer(value=None, channel="unknown"),
            "C": corpus_mod.Answer(value="9.99", channel="observed"),
        }
    )
    scoped = mixed.scoped_to({"A", "B", "C"})
    checks.equal(
        sorted(scoped.overrides),
        ["A"],
        "AN UNRECOGNISED CHANNEL DOES NOT REACH `overrides`. This was a deny-list until "
        "2026-09-06 — `unknown if channel == 'unknown' else prices` — so every value but one "
        "landed in the table `prices_for` consults FIRST, beating the rule, the market and "
        "the policy for every future copy out of every future box",
    )
    checks.equal(
        sorted(scoped.no_market_data),
        ["B", "C"],
        "it falls to `no_market_data` instead, which `decisions.blocking` reads as unanswered "
        "and refuses the emit over — the safe direction is the one that STOPS, not the one "
        "that prices (the portal spec's own rule 4: never a deny-list)",
    )

    # -------------------------------------------------- money is not printed in exponents
    checks.equal(
        [corpus_mod._token(v) for v in ("7000.00", "750.00", "0.4900")],
        ["$7000", "$750", "$0.49"],
        "AND MONEY RENDERS AS DIGITS. `Decimal.normalize()` folds `0.50` and `0.5` into one "
        "answer, which is the point — and folds `7000.00` into `7E+3`, which is what the "
        "operator was shown for the two highest-value figures this repo has handled",
    )
    checks.ok(
        corpus_mod._token("0.50") == corpus_mod._token("0.5")
        and corpus_mod._token("7000.00") == corpus_mod._token("7000"),
        "while the FOLDING the comparison depends on is untouched — `stamp_answers` dates an "
        "answer by whether its token moved, so breaking this would re-date the whole corpus",
    )


def check_emit_unpriced_left_out(checks: Checks) -> None:
    """A SEND WITH ONE UNPRICED ROW SENDS EVERY OTHER READY COPY (D277 Q3, the owner's words:
    "send every ready copy; unpriced rows stay on the list").

    `emit` used to refuse the WHOLE file while any card with no market price had no answer
    (`Decisions.blocking`, `join.prices_for`). A missing price is still unknown and never low
    (D9, D86), so that card still cannot go: it is LEFT OUT, named, and stays owed. The two
    priced cards go. Both paths the send can take are asserted: one run, and several runs.
    """
    checks.note("")
    checks.note("EMIT, ONE UNPRICED ROW — the ready copies go, the unpriced one stays owed")

    cards = [
        (3, 1, "Dunsparce", "120", "normal"),
        (3, 2, "Dunsparce", "120", "reverse_holo"),
        (3, 3, "Articuno", "161", None),
    ]
    # A BLANK MARKET CELL IS "NO MARKET PRICE" (D9), and `join` seeds it unanswered.
    no_price = {ARTICUNO_SKU: ""}

    def left_out(said: str) -> None:
        # THE FILE IS WHERE `emit` SAID IT WROTE IT, read off its own line, so one assertion
        # serves the single-run path and the merged one.
        paths = [Path(found) for found in re.findall(r"-> (\S+\.csv)", said)]
        written = {
            row[tcgcsv.SKU_COLUMN]
            for path in paths
            if path.is_file()
            for row in tcgcsv.read_export(path).rows
        }
        checks.equal(
            sorted(written),
            sorted([DUNSPARCE_SKU, DUNSPARCE_REVERSE_SKU]),
            "the file carries EXACTLY the two ready rows — not zero (the old whole-send "
            "refusal) and not three (a guess at a price nobody gave)",
        )
        checks.ok(
            "no market price" in said and ARTICUNO_SKU in said,
            "the unpriced card is NAMED where it was left out, never dropped silently",
            said,
        )
        listing = Store().read().inventory.listings.get(ARTICUNO_SKU)
        checks.equal(
            0 if listing is None else listing.pushed,
            0,
            "and it STAYS OWED: nothing of it was committed as sent, so the next worklist "
            "still carries it",
        )
        checks.equal(
            getattr(corpus.Corpus.read().answers.get(ARTICUNO_SKU), "value", None),
            None,
            "and it still has no answer — nothing was invented for it",
        )

    with isolated_home():
        run_dir, _ = seam_run(checks, cards, market=no_price)
        # THE WORKLIST SAYS THE RUN OWES A PRICE, BEFORE AND AFTER THE SEND (the delta review,
        # R3-2). `blocking` no longer names the card, so the roster reads the rows itself:
        # otherwise Home counted the unpriced copy as ready to send and never said to price it.
        def owes_price() -> List[str]:
            roster = pipeline_routes.do_pipeline_worklist([])["roster"]
            row = next((one for one in roster if one["run"] == run_dir.name), {})
            return [reason for reason in row.get("owes", []) if reason != "never emitted"]

        checks.equal(
            owes_price(),
            ["1 card with no market price needs a price"],
            "the joined run owes a PRICE for the unpriced card, a reason that is not the send",
        )
        # AND EACH REASON CARRIES ITS CODE (R4): the screen reads the code, never the sentence.
        roster = pipeline_routes.do_pipeline_worklist([])["roster"]
        chip = next((one for one in roster if one["run"] == run_dir.name), {})
        checks.equal(
            chip.get("owed"),
            [{"code": "needs_price", "count": 1}, {"code": "never_emitted", "count": None}],
            "the roster sends a machine code beside each owed sentence, in the same order",
        )
        checks.ok(
            all(reason["code"] in pipeline_routes.OWE_CODES for reason in chip.get("owed", [])),
            "every code sent is one `OWE_CODES` declares",
        )
        left_out(command(checks, "emit", str(run_dir.directory)))
        checks.equal(
            owes_price(),
            ["1 card with no market price needs a price"],
            "and after the send it still owes that price: the card stayed back, so the run did",
        )

    with isolated_home():
        first, _ = seam_run(checks, [cards[0], cards[2]], market=no_price)
        second, _ = seam_run(checks, [cards[1]], market=no_price)
        left_out(command(checks, "emit", str(first.directory), str(second.directory)))

    # WHEN EVERY READY CARD NEEDS A PRICE, THE REFUSAL SAYS SO, AND BOTH PATHS AGREE (the delta
    # review, R3-3). The single-run path said "every row is already sent" and exited 0; the
    # merged path said "held back, unlisted, or has no room" and exited 1; the send route read
    # either as "already at TCGplayer or held back". All three were false.
    from cli import __main__ as entry

    def refused(argv) -> Tuple[int, str]:
        with quiet() as said:
            code = entry.main(list(argv))
        return code, said.getvalue()

    with isolated_home():
        only, _ = seam_run(checks, [cards[2]], market=no_price)
        code, said = refused(["emit", str(only.directory)])
        checks.ok(
            code == 1 and merge.ONLY_UNPRICED in said and "already sent" not in said,
            "one run, every card unpriced: `emit` refuses by saying the card needs a price",
            f"exit {code}\n{said}",
        )
    with isolated_home():
        one, _ = seam_run(checks, [cards[2]], market=no_price)
        two, _ = seam_run(checks, [cards[2]], market=no_price)
        code, said = refused(["emit", str(one.directory), str(two.directory)])
        checks.ok(
            code == 1 and merge.ONLY_UNPRICED in said and "no room" not in said,
            "several runs, every card unpriced: the same sentence and the same exit",
            f"exit {code}\n{said}",
        )
    answer = send_routes._empty_send_refusal(f"...\n{merge.ONLY_UNPRICED}\n", [], "sent")
    checks.equal(
        (answer.code, "already at TCGplayer" in str(answer)),
        ("needs_price", False),
        "and the send route names it `needs_price`, never `nothing_to_send`",
    )

    # THE REVIEWER'S STORES, R4 (the delta review of 683860e7).
    #
    # F3: several runs, one card sent with `--quantity SKU=0` and one with no price. The empty
    # send returned on the price sentence before the loop that names every left-out card, so
    # the zero-quantity card was never named.
    with isolated_home():
        one, _ = seam_run(checks, [cards[0], cards[2]], market=no_price)
        two, _ = seam_run(checks, [cards[2]], market=no_price)
        code, said = refused(
            ["emit", str(one.directory), str(two.directory), "--quantity", f"{DUNSPARCE_SKU}=0"]
        )
        checks.ok(
            code == 1 and merge.ONLY_UNPRICED in said and f"{DUNSPARCE_SKU} — " in said,
            "several runs, an empty send: every left-out card is NAMED with its reason before "
            "the price sentence",
            f"exit {code}\n{said}",
        )

    # F4: `--listed-only` over a priced card under the cut-off and an unpriced card. Nothing
    # can go. The single-run path ignored the flag, and the merged path said every card needs a
    # price while a priced card stayed back. Both paths must say the same true thing: the
    # priced card is held back by the flag, and it is named apart from the unpriced one.
    under = {ARTICUNO_SKU: "", DUNSPARCE_SKU: "0.10"}

    def listed_only_truth(argv, label) -> None:
        code, said = refused(argv)
        checks.ok(
            code == 1
            # R6-9: both reasons in one headline, never only the flag's.
            and "nothing to send: 1 card needs a price first, and 1 priced card under the "
            "cut-off is held back by --listed-only" in said
            and merge.ONLY_UNPRICED not in said
            and f"{DUNSPARCE_SKU} — under the cut-off" in said
            and ARTICUNO_SKU in said,
            f"{label}, --listed-only: the priced card under the cut-off is named apart from the "
            "unpriced one, and the refusal says the flag holds it back",
            f"exit {code}\n{said}",
        )

    with isolated_home():
        only, _ = seam_run(checks, [cards[0], cards[2]], market=under)
        listed_only_truth(["emit", str(only.directory), "--listed-only"], "one run")
    with isolated_home():
        one, _ = seam_run(checks, [cards[0]], market=under)
        two, _ = seam_run(checks, [cards[2]], market=under)
        listed_only_truth(
            ["emit", str(one.directory), str(two.directory), "--listed-only"], "several runs"
        )

    # F5: a live-guard trim beside the price reason. The route checked the price sentence
    # first and dropped the trim. It names both now.
    trim = {"sku": DUNSPARCE_SKU, "name": "Dunsparce", "live": 1, "on_hand": 1, "would": 1, "goes": 0}
    answer = send_routes._empty_send_refusal(f"...\n{merge.ONLY_UNPRICED}\n", [trim], "sent")
    checks.ok(
        answer.code == "needs_price" and "Dunsparce" in str(answer) and "TCGplayer already" in str(answer),
        "the send route names the trimmed card beside the price reason, never hides it",
        str(answer),
    )
    answer = send_routes._empty_send_refusal(f"...\n{merge.ONLY_UNDER_CUT}\n", [], "sent")
    checks.equal(
        answer.code,
        "under_cut_off",
        "and a send that --listed-only emptied is named for the flag, not for a price",
    )

# ============================================================================= the send matrix
#
# THE REVIEWER'S CASE MATRIX, MADE PERMANENT (R6). Every round of the pricing lane closed one
# message defect and opened another, because each fix was checked against the case that found
# it and nothing else. This is every store shape and every flag set a send can meet, over one
# run and over several, and for each one it asserts all four places the owner reads the answer:
#
#   the file      each import file's rows, as (SKU, Add to Quantity, price)
#   emit          the reasons it prints, and the ones it must never print
#   the route     the refusal code, and the title the Send card words from the refusal's
#                 figures (`standing.ts:emptySendTitle`, never the server's sentence, D269)
#   Home          the standing line, the Pricing tile and the run chips, from the worklist
#                 the send started from. Read by running `app/src/standing.ts` itself, bundled
#                 by the app's own esbuild, so no third copy of the rule lives here.
#
# A ROW NAMES ITS OWN DEFECT where it has one: R6-3 is the live-guard trim named as a trim,
# R6-5 the one-run twin of F3, R6-6 the merged `--listed-only` naming, R6-9 the headline worded
# from its reasons. R6-4 (a failed read of typed prices) and R6-8 (the chip) are Home columns.

_M_D, _M_R, _M_A = DUNSPARCE_SKU, DUNSPARCE_REVERSE_SKU, ARTICUNO_SKU

_M_CARDS = [
    (3, 1, "Dunsparce", "120", "normal"),
    (3, 2, "Dunsparce", "120", "reverse_holo"),
    (3, 3, "Articuno", "161", None),
    # A SECOND DRAWER HOLDING THE SAME TWO SKUS, for the shared-SKU rows (R7 F5).
    (4, 1, "Dunsparce", "120", "normal"),
    (4, 2, "Articuno", "161", None),
    # TWO MORE NORMAL DUNSPARCE IN DRAWER 3, so one SKU has three copies on hand. The guard
    # alone then leaves room past a cap, for the `--cap` rows (D7).
    (3, 4, "Dunsparce", "120", "normal"),
    (3, 5, "Dunsparce", "120", "normal"),
]

_M_MIX = {_M_A: ""}

_M_SUB = {_M_A: "", _M_D: "0.10"}

_M_SUBALL = {_M_A: "0.05", _M_D: "0.10", _M_R: "0.12"}

_M_LAYOUT = {
    "one": [[0, 1, 2]], "two": [[0, 2], [1]], "share": [[0, 1, 2], [3, 4]],
    "deep1": [[0, 1, 2, 5, 6]], "deep2": [[0, 2, 5], [1, 6]], "share1": [[0, 1, 2, 5]],
    # ONE SKU ALONE, NO R AND NO A, for the D7 2026-09-27 cap-reconcile rows below: three
    # normal Dunsparce and nothing else, so a case can push, reconcile and cap one SKU
    # without a second card's own reasons crowding the assertions.
    "pure1": [[0, 5, 6]], "pure2": [[0, 5], [6]],
}

_M_NONE_NAMED = {"prices": [], "moves": []}

# The reasons, as emit prints them, one per card.
_M_LIVE = "TCGplayer already holds every copy on hand"

_M_HELD = "held back or answered unlisted"

_M_ASKED0 = "this send asked for none of this card"

_M_SENT = "every copy in this run is already listed or has left the box"

# THE HEADLINES, WRITTEN OUT (R7 F6). The matrix never asks `merge` for the sentence it is
# checking, so a defect in the sentence builder goes red here.
_M_ONLY_PRICE = "nothing to send: every card left needs a price first"

_M_ONLY_CUT = "nothing to send: every priced card left is under the cut-off, and --listed-only holds it back"

_M_NOTHING_NEW = "nothing new to send: every card left is already at TCGplayer, held back, or has no room"

_M_PRICE_LIVE2 = "nothing to send: 1 card needs a price first, and TCGplayer already holds every copy of 2 cards"

_M_PRICE_CUT_LIVE = (
    "nothing to send: 1 card needs a price first, and 1 priced card under the cut-off is held "
    "back by --listed-only, and TCGplayer already holds every copy of 1 card"
)


def _m_row(sku: str, price: str) -> Tuple[str, int, str]:
    return (sku, 1, price)


def _m_cases() -> Dict[str, dict]:
    """Every case: store, layout, flags, and what each of the four readers must say."""
    d_mix, r_mix = _m_row(_M_D, "2.06"), _m_row(_M_R, "2.60")
    d_sub = _m_row(_M_D, "0.49")
    both = [d_mix, r_mix]
    send2 = {"line": "send 2 copies to TCGplayer", "behind": "1 card needs a price", "tile": "run to price, 2 ready"}
    cases: Dict[str, dict] = {}
    for layout in ("one", "two"):
        last = "import.csv"

        def add(name, _layout=layout, **spec):
            spec.setdefault("flags", [])
            spec.setdefault("says", [])
            spec.setdefault("never", [])
            spec.setdefault("route", None)
            spec["layout"] = _layout
            cases[f"{name.split('/')[0]}/{_layout}/{name.split('/')[1]}"] = spec

        # A MIXED STORE: two priced cards and one with no market price.
        for flag, argv, want in (
            ("plain", [], {last: both}),
            ("cap1", ["--cap", "1"], {last: both}),
            ("listed", ["--listed-only"], {last: both}),
            ("splitT", ["--split-threshold"], {"import-listed.csv": both}),
            ("splitG", ["--split-games"], {"import-pokemon.csv": both}),
        ):
            add(f"mix/{flag}", market=_M_MIX, flags=argv, exit=0, files=want, says=[_M_A], home=send2)
        add("mix/qty0", market=_M_MIX, flags=["--quantity", f"{_M_D}=0"], exit=0, files={last: [r_mix]},
            says=[f"{_M_D} Dunsparce — asked 0, none sent"], home=send2)
        add("mix/held", market=_M_MIX, pre=(_M_D,), exit=0, files={last: [r_mix]}, says=[_M_A],
            home={"line": "send 1 copy to TCGplayer", "behind": "1 card needs a price", "tile": "run to price, 1 ready",
                  "failed": "send 2 copies to TCGplayer"})
        # R6-5: the one-run empty send names every card it left out, as the merged one does.
        add("mix/heldall", market=_M_MIX, pre=(_M_D, _M_R), exit=1, files={},
            says=[f"{_M_D} — {_M_HELD}", f"{_M_R} — {_M_HELD}", _M_A, _M_ONLY_PRICE],
            route=("needs_price", ["Every card on this list needs a price first"]),
            home={"line": "price 1 card", "behind": None, "tile": "run to price",
                  "failed": "send 2 copies to TCGplayer"})
        add("mix/qty0all", market=_M_MIX, flags=["--quantity", f"{_M_D}=0", "--quantity", f"{_M_R}=0"], exit=1, files={},
            says=[f"{_M_D} — {_M_ASKED0}", f"{_M_R} — {_M_ASKED0}", _M_A, _M_ONLY_PRICE],
            route=("needs_price", ["Every card on this list needs a price first"]), home=send2)
        add("mix/sent", market=_M_MIX, twice=True, exit=1, files={last: both},
            says=[f"{_M_D} — {_M_SENT}", f"{_M_R} — {_M_SENT}", _M_A, _M_ONLY_PRICE],
            route=("needs_price", ["Every card on this list needs a price first"]),
            home={"line": "price 1 card", "behind": None, "tile": "run to price",
                  "chip": "Sent, 1 needs a price"})
        # R6-3 and R6-9: a live-guard trim is named as a trim, and the headline and the title
        # state every reason the send was empty, never only the price.
        for flag, named in (("guard", None), ("guard+named", _M_NONE_NAMED)):
            add(f"mix/{flag}", market=_M_MIX, live={_M_D: 1, _M_R: 1, _M_A: 0}, named=named, exit=1, files={},
                says=[f"{_M_D} — {_M_LIVE}", f"{_M_R} — {_M_LIVE}", _M_A,
                      _M_PRICE_LIVE2],
                never=[_M_ASKED0, _M_ONLY_PRICE],
                route=("needs_price", ["1 card needs a price first", "TCGplayer already had every copy of 2 cards"]),
                home=send2)
        add("mix/guard+part", market=_M_MIX, live={_M_D: 1, _M_R: 0, _M_A: 0}, named=_M_NONE_NAMED, exit=0,
            files={last: [r_mix]}, says=[f"{_M_D} Dunsparce — TCGplayer holds 1 of 1 on hand", f"{_M_D} — {_M_LIVE}"],
            never=[_M_ASKED0], home=send2)
        # R8-2: A SEND THAT IS NOT EMPTY, WITH A LIVE CARD THAT HAS ANOTHER REASON. A card with
        # no price and a withheld card are named for that reason alone, on both paths: never in
        # the "no room" list as live, never in the guard's trimmed list the Send card draws.
        add("own/sub-listed+Alive", market=_M_SUB, flags=["--listed-only"], live={_M_D: 0, _M_R: 0, _M_A: 1},
            named=_M_NONE_NAMED, exit=0, files={last: [r_mix]},
            says=[f"{_M_D} — under the cut-off (Dunsparce)", _M_A],
            never=[f"{_M_A} — {_M_LIVE}", f'"sku": "{_M_A}", "would"', _M_ASKED0], home=send2)
        add("own/held+live", market=_M_MIX, pre=(_M_D,), live={_M_D: 1, _M_R: 0, _M_A: 0}, named=_M_NONE_NAMED,
            # THE OWNER'S RULING, "held items have 0 qty live on TCGplayer": the held card the
            # fresh read shows live gets a take-off row of that size, here minus one.
            exit=0, files={last: [(_M_D, -1, "2.06"), r_mix]}, says=[_M_A],
            never=[f"{_M_D} — {_M_LIVE}", f'"sku": "{_M_D}", "would"', _M_ASKED0],
            home={"line": "send 1 copy to TCGplayer", "behind": "1 card needs a price", "tile": "run to price, 1 ready",
                  "failed": "send 2 copies to TCGplayer"})
        # R7 F4: a card with no price that TCGplayer also holds has one reason, the price. It is
        # counted once, and never named among the live cards.
        add("mix/unpricedlive", market=_M_MIX, live={_M_D: 1, _M_R: 1, _M_A: 1}, named=_M_NONE_NAMED, exit=1,
            files={}, says=[f"{_M_D} — {_M_LIVE}", f"{_M_R} — {_M_LIVE}", _M_A, _M_PRICE_LIVE2,
                            '"live_names": ["Dunsparce", "Dunsparce"]'],
            never=[_M_ASKED0, f"{_M_A} — {_M_LIVE}"],
            route=("needs_price", ["Nothing was sent. 1 card needs a price first. TCGplayer already had every "
                                   "copy of 2 cards (Dunsparce, Dunsparce)."]),
            home=send2)

        # A STORE WITH A PRICED CARD UNDER THE CUT-OFF.
        sub_both = [d_sub, r_mix]
        for flag, argv, want in (
            ("plain", [], {last: sub_both}),
            ("cap1", ["--cap", "1"], {last: sub_both}),
            ("splitT", ["--split-threshold"], {"import-listed.csv": [r_mix], "import-subthreshold.csv": [d_sub]}),
            ("splitG", ["--split-games"], {"import-pokemon.csv": sub_both}),
        ):
            add(f"sub/{flag}", market=_M_SUB, flags=argv, exit=0, files=want, says=[_M_A], home=send2)
        add("sub/qty0", market=_M_SUB, flags=["--quantity", f"{_M_D}=0"], exit=0, files={last: [r_mix]},
            says=[f"{_M_D} Dunsparce — asked 0, none sent"], home=send2)
        # R6-6: `--listed-only` names the priced card it leaves under the cut-off, on both paths.
        add("sub/listed", market=_M_SUB, flags=["--listed-only"], exit=0, files={last: [r_mix]},
            says=[f"{_M_D} — under the cut-off (Dunsparce)", _M_A], home=send2)
        # R6-9: the headline is not "every priced card is under the cut-off" when a priced card
        # above it was trimmed by the guard.
        add("sub/listed+guard", market=_M_SUB, flags=["--listed-only"], live={_M_D: 0, _M_R: 1, _M_A: 0},
            named=_M_NONE_NAMED, exit=1, files={},
            says=[f"{_M_D} — under the cut-off (Dunsparce)", f"{_M_R} — {_M_LIVE}", _M_A,
                  _M_PRICE_CUT_LIVE],
            never=[_M_ONLY_CUT, _M_ASKED0],
            route=("needs_price", ["1 card needs a price first", "1 priced card is under the cut-off",
                                   "TCGplayer already had every copy of 1 card"]),
            home=send2)

        # EVERY CARD PRICED AND UNDER THE CUT-OFF.
        add("suball/listed", market=_M_SUBALL, flags=["--listed-only"], exit=1, files={},
            says=[f"{sku} — under the cut-off" for sku in (_M_D, _M_R, _M_A)] + [_M_ONLY_CUT],
            route=("under_cut_off", ["Every priced card on this list is under the cut-off"]),
            home={"line": "send 3 copies to TCGplayer", "behind": None, "tile": "3 ready",
                  "chip": "Never sent"})
        # ONE ANSWER ON BOTH PATHS. One run exited 0 with its own sentence, and several
        # exited 1 with another. Both exit 1 now, with one headline and each card's reason.
        add("suball/listed-sent", market=_M_SUBALL, flags=["--listed-only"], twice=True, exit=1,
            files={last: [_m_row(_M_D, "0.49"), _m_row(_M_R, "0.49"), _m_row(_M_A, "0.49")]},
            says=[_M_NOTHING_NEW] + [f"{sku} — {_M_SENT}" for sku in (_M_D, _M_R, _M_A)],
            never=["nothing to write"],
            route=("nothing_to_send", ["already at TCGplayer"]),
            home={"line": None, "behind": None, "tile": "nothing to price", "chip": "All sent"})
    # R7 F5: A SKU SHARED BY TWO DRAWERS UNDER `--cap 1`, WITH THE GUARD. The reverse holo is
    # trimmed to nothing and the send is not empty: the trim is named as a trim, never as
    # "asked for none".
    # THE CAP IS 2, NOT 1, since the `--cap` fix below. TCGplayer holds 1 Dunsparce, so a cap
    # of 1 leaves no room and the send is empty. This row is about the trim, not the cap.
    cases["share/two/cap2-guardall"] = {
        "layout": "share", "market": _M_MIX, "flags": ["--cap", "2"],
        "live": {_M_D: 1, _M_R: 1, _M_A: 0}, "named": _M_NONE_NAMED, "exit": 0,
        "files": {"import.csv": [d_mix]},
        "says": [f"{_M_R} — {_M_LIVE}"], "never": [_M_ASKED0], "route": None,
        "home": {"line": "send 3 copies to TCGplayer", "behind": "1 card needs a price", "tile": "runs to price, 3 ready"},
    }
    # R7 F5, UNDER A CAP THE GUARD USED TO CLOSE AND NO LONGER DOES (the owner's ruling,
    # 2026-09-27, replacing the 2026-09-25 "take the larger" amendment, D7). A cap of 1
    # with one Dunsparce live guard-side now leaves room for exactly one, because the guard's
    # own reading no longer feeds the cap at all — only the store's own `copies_out` does, and
    # it is fresh here (no prior push, no pending). What the guard STILL does, unchanged, is
    # trim the reverse holo to nothing on its own reading: R7 F5's own fence, "the guard's
    # on-hand trim must not change", proved by this row surviving the cap rewrite intact.
    for layout, runs_label in (("share1", "one"), ("share", "two")):
        cases[f"share/{runs_label}/cap1-guardall"] = {
            "layout": layout, "market": _M_MIX, "flags": ["--cap", "1"],
            "live": {_M_D: 1, _M_R: 1, _M_A: 0}, "named": _M_NONE_NAMED, "exit": 0,
            "files": {"import.csv": [d_mix]},
            "says": [f"{_M_R} — {_M_LIVE}"],
            "never": [_M_ASKED0, "read what is live, then send again", "1 live, at the cap of 1"],
            "route": None,
            "home": {"line": "send 3 copies to TCGplayer", "behind": "1 card needs a price",
                     "tile": "3 ready"},
        }

    # ============================================================ D7, THE 2026-09-27 RULING
    #
    # `--cap` REFUSES A CARD OUTRIGHT WHILE A COPY SENT SINCE IS STILL PENDING (D7), and
    # once reconciled the cap reads the store's own one reading alone — nothing maxed or
    # summed with a guard any more. `pure1`/`pure2` hold Dunsparce alone (no R, no A), so a
    # case can push, reconcile and cap one SKU with nothing else to crowd the assertions;
    # `deep1`/`deep2` (R and A present) are for the rows that need a second card to prove it
    # still sends. Every group runs on both the one-run and the several-run path.

    # --- fresh (no pending) caps on the store's own count exactly: below, at and over -------
    # `setup` pushes copies with no `--live-guard` and no `--cap` bigger than it needs to be
    # wrong about; `reconcile` then plants the store's own live reading at exactly that many,
    # closing the pending gap before the row's own `--cap` is asked. THIS IS ALSO THE "STALE
    # READING NO LONGER UNDER-SENDS ONCE RECONCILED" ROW: before the reconcile the SKU is
    # pending and `--cap` would refuse it (the row above proves that refusal); the reconcile
    # is the fix, and "below" is the proof it worked — the cap opens back up to the fresh
    # figure rather than staying stuck on the stale one.
    for layout, runs_label in (("pure1", "one"), ("pure2", "two")):
        cases[f"freshcap/{runs_label}/below"] = {
            "layout": layout, "market": _M_MIX, "flags": ["--cap", "5"],
            "setup": ["--quantity", f"{_M_D}=1"], "reconcile": {_M_D: 1},
            "exit": 0, "files": {"import.csv": [(_M_D, 2, "2.06")]},
            "says": [], "never": [_M_ASKED0, "read what is live, then send again"], "route": None,
            "home": {"line": "send 2 copies to TCGplayer", "behind": None,
                     "tile": "2 ready"},
        }
        # AT AND OVER LEAVE THE SETUP PRESS'S OWN FILE ON DISK (D54): the real press adds
        # nothing, and a refusal never touches a file an earlier press wrote.
        cases[f"freshcap/{runs_label}/at"] = {
            "layout": layout, "market": _M_MIX, "flags": ["--cap", "1"],
            "setup": ["--quantity", f"{_M_D}=1"], "reconcile": {_M_D: 1},
            "exit": 1, "files": {"import.csv": [(_M_D, 1, "2.06")]},
            "says": [f"{_M_D} — 1 live, at the cap of 1"],
            "never": [_M_ASKED0, "read what is live, then send again"],
            "route": ("nothing_to_send", ["already at TCGplayer"]),
            # HOME READS NO CAP AT ALL (`do_pipeline_worklist` never asks `--cap` for), so it
            # still counts the two backstock copies as ready — the SAME reason `capguard`'s
            # own home block never claimed otherwise before this rewrite.
            "home": {"line": "send 2 copies to TCGplayer", "behind": None,
                     "tile": "2 ready"},
        }
        cases[f"freshcap/{runs_label}/over"] = {
            "layout": layout, "market": _M_MIX, "flags": ["--cap", "1"],
            "setup": ["--cap", "2"], "reconcile": {_M_D: 2},
            "exit": 1, "files": {"import.csv": [(_M_D, 2, "2.06")]},
            "says": [f"{_M_D} — 2 live, over the 1 this send asked for"],
            "never": [_M_ASKED0, "read what is live, then send again"],
            "route": ("nothing_to_send", ["already at TCGplayer"]),
            "home": {"line": "send 1 copy to TCGplayer", "behind": None,
                     "tile": "1 ready"},
        }

    # --- a pending copy refuses that card, and the other card in the send still goes --------
    # TWO of Dunsparce's three copies are pushed and NEVER reconciled, so one copy is left
    # uncommitted behind the pending pair — the shape that tells a pending refusal apart from
    # "every copy is already listed" (D59's own, unrelated, branch, which is what a FULLY
    # pushed SKU reaches instead: nothing is left to decide, cap or no cap). The reverse holo
    # is left untouched by naming it `=0` in the setup press. The real press then asks a cap
    # of any size: Dunsparce refuses outright, on the remedy — including the one copy that
    # was never sent — and the reverse holo sends normally.
    for layout, runs_label in (("deep1", "one"), ("deep2", "two")):
        cases[f"pendingcap/{runs_label}"] = {
            "layout": layout, "market": _M_MIX, "flags": ["--cap", "5"],
            "setup": ["--quantity", f"{_M_D}=2", "--quantity", f"{_M_R}=0"],
            "exit": 0, "files": {"import.csv": [r_mix]},
            "says": [f"{_M_D} — 2 copies sent and not yet seen live — read what is live, then send again"],
            "never": [_M_ASKED0, _M_LIVE, "1 live, at the cap of"], "route": None,
            "home": {"line": "send 2 copies to TCGplayer", "behind": "1 card needs a price",
                     "tile": "2 ready"},
        }

    # --- D7's capped-card clause: the empty-send headline names a card the cap closed --------
    # Two of Dunsparce's three copies are pushed and never reconciled (one stays uncommitted,
    # for the same reason as the row above), the reverse holo's one copy is pushed in full,
    # and Articuno still has no price — nothing is left to send at all, which is what reaches
    # `empty_send_sentence`. Before this fix the headline counted `needs_price` and `live` (a
    # guard trim) and said nothing about the card the CAP closed.
    for layout, runs_label in (("deep1", "one"), ("deep2", "two")):
        cases[f"capsempty/{runs_label}"] = {
            "layout": layout, "market": _M_MIX,
            "flags": ["--cap", "5"], "setup": ["--cap", "5", "--quantity", f"{_M_D}=2"],
            # THE SETUP PRESS'S FILE STAYS (D54): Dunsparce at 2, the reverse holo at 1.
            "exit": 1, "files": {"import.csv": [(_M_D, 2, "2.06"), r_mix]},
            "says": [
                f"{_M_D} — 2 copies sent and not yet seen live — read what is live, then send again",
                f"{_M_R} — {_M_SENT}",
                _M_A,
                "nothing to send: 1 card needs a price first, and 1 card is held at this "
                "send's cap",
            ],
            "never": [_M_ASKED0, _M_LIVE, _M_ONLY_PRICE],
            "route": (
                "needs_price",
                ["1 card needs a price first", "1 card is held at this send's cap"],
            ),
            "home": {"line": "send 1 copy to TCGplayer", "behind": "1 card needs a price",
                     "tile": "run to price, 1 ready"},
        }

    # --- D7's guard-zero wording: a guard-zeroed `asked` is not a typed zero -----------------
    # The cap already closes Dunsparce to nothing on its own (one pushed and reconciled,
    # exactly at a cap of one, with two more uncommitted behind it) — so the guard's OWN
    # independent closure (it shows the whole three on hand as live) trims `would` from zero,
    # which `sendguard.trims()` never names as a visible trim. Before this fix the row printed
    # "this send asked for none of this card", as if the operator had typed the zero.
    for layout, runs_label in (("pure1", "one"), ("pure2", "two")):
        cases[f"guardzero/{runs_label}"] = {
            "layout": layout, "market": _M_MIX, "flags": ["--cap", "1"],
            "setup": ["--quantity", f"{_M_D}=1"], "reconcile": {_M_D: 1},
            "live": {_M_D: 3}, "named": None,
            # THE SETUP PRESS'S FILE STAYS (D54): one Dunsparce, from before the reconcile.
            "exit": 1, "files": {"import.csv": [(_M_D, 1, "2.06")]},
            "says": [_M_LIVE],
            "never": [_M_ASKED0, "1 live, at the cap of 1", "read what is live, then send again"],
            "route": ("nothing_to_send", ["already at TCGplayer"]),
            "home": {"line": "send 2 copies to TCGplayer", "behind": None,
                     "tile": "2 ready"},
        }
    return cases


def _m_hold(skus) -> None:
    book = corpus.Corpus.read()
    for sku in skus:
        book.answers[sku] = corpus.Answer(value={"withheld": "keeping"})
    book.write()


def _m_files(dirs) -> Dict[str, List[Tuple[str, int, str]]]:
    out: Dict[str, List[Tuple[str, int, str]]] = {}
    for directory in dirs:
        for path in sorted(Path(directory).glob("import*.csv")):
            out[path.name] = sorted(
                (
                    str(row[tcgcsv.SKU_COLUMN]),
                    tcgcsv.parse_quantity(row.get(tcgcsv.QUANTITY_COLUMN, "")),
                    str(row.get("TCG Marketplace Price", "")),
                )
                for row in tcgcsv.read_export(path).rows
            )
    return out


class _ToolchainMissing(Exception):
    """`app/node_modules` is absent: a read that could not run, never a failure."""


def _m_home(worklists: Dict[str, dict]) -> Dict[str, dict]:
    """Home's line, tile and run chips for each worklist, off `app/src/standing.ts` itself."""
    root = REPO_ROOT
    esbuild = root / "app" / "node_modules" / ".bin" / "esbuild"
    if not esbuild.exists() or shutil.which("node") is None:
        raise _ToolchainMissing()
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "standing.mjs"
        subprocess.run(
            [str(esbuild), str(root / "app" / "src" / "standing.ts"), "--bundle", "--format=esm",
             "--platform=node", "--log-level=warning", f"--outfile={bundle}"],
            check=True,
        )
        cases = Path(tmp) / "cases.json"
        cases.write_text(json.dumps(worklists))
        script = (
            f"import * as s from {json.dumps(bundle.as_uri())};"
            "import {readFileSync} from 'node:fs';"
            f"const cases = JSON.parse(readFileSync({json.dumps(str(cases))}, 'utf8'));"
            "const status = {cards: 3, queues: {review: 0, parked: 0}, states: {}, problem: null};"
            "const orders = {orders: [], resolution: {orders: [], counts: {}}};"
            "const out = {};"
            "for (const [name, c] of Object.entries(cases)) {"
            "  const read = (book, failed) => {"
            "    const say = s.standing({status, statusFailed: false, orders, ordersFailed: false,"
            "      pricing: c.pricing, pricingFailed: false, runs: [], runsFailed: false, unconfirmed: 0,"
            "      book, bookFailed: failed});"
            "    return say === null ? null : {lead: say.lead, text: say.say.map((x) => x.text).join(''),"
            "      behind: say.behind.slice()};"
            "  };"
            "  const ready = s.sendCounts(c.pricing, c.book).ready;"
            "  out[name] = {line: read(c.book, false), failed: read(null, true),"
            "    title: c.empty ? s.emptySendTitle(c.empty) : null,"
            "    tile: s.pricingTileNote(s.runsOwingPrice(c.pricing.roster), ready),"
            "    chips: c.pricing.roster.map((r) => s.runChip(r))};"
            "}"
            # RANKS 5 AND 6 ON A FAILED READ (R8 review, LOW note a), off a worklist that owes
            # nothing: a live run, then photographed cards. Each keeps the typed-prices note.
            "const calm = cases['suball/one/listed-sent'];"
            "if (calm) {"
            "  const at = (st, rs) => {"
            "    const say = s.standing({status: st, statusFailed: false, orders, ordersFailed: false,"
            "      pricing: calm.pricing, pricingFailed: false, runs: rs, runsFailed: false, unconfirmed: 0,"
            "      book: null, bookFailed: true});"
            "    return say === null ? null : {key: say.key, lead: say.lead, behind: say.behind.slice()};"
            "  };"
            "  out['rank:working'] = at(status, [{live: true, box: 3}]);"
            "  out['rank:captured'] = at({...status, states: {captured: 2}}, []);"
            "}"
            "process.stdout.write(JSON.stringify(out));"
        )
        done = subprocess.run(
            ["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=False
        )
        if done.returncode != 0:
            raise RuntimeError(f"node could not read Home: {done.stderr.strip()[:900]}")
        return json.loads(done.stdout)


def check_send_matrix(checks: Checks) -> None:
    """THE SEND MATRIX (R6): every store shape and flag set, all four readers, one table."""
    from cli import __main__ as entry

    checks.note("")
    checks.note("THE SEND MATRIX — the file, emit's reasons, the route's refusal, and Home, per case")

    def emit(argv) -> Tuple[int, str]:
        with quiet() as said:
            code = entry.main(["emit", *argv])
        return code, said.getvalue()

    cases = _m_cases()
    worklists: Dict[str, dict] = {}
    for name, spec in cases.items():
        with isolated_home() as home:
            made = [seam_run(checks, [_M_CARDS[i] for i in part], market=spec["market"])[0]
                    for part in _M_LAYOUT[spec["layout"]]]
            dirs = [str(run.directory) for run in made]
            if spec.get("pre"):
                _m_hold(spec["pre"])
            extra: List[str] = []
            if spec.get("live") is not None:
                live = home / "live.csv"
                live.write_bytes(_live_export_bytes(spec["live"]))
                extra += ["--live-guard", str(live)]
            if spec.get("named") is not None:
                told = home / "named.json"
                told.write_text(json.dumps(spec["named"]))
                extra += ["--reprice-live", str(told)]
            if spec.get("twice"):
                emit(dirs)
            # A PRELIMINARY PRESS, FOR THE D7 2026-09-27 CAP-RECONCILE ROWS: pushes copies
            # under its OWN flags (typically its own `--cap`/`--quantity`), so the real press
            # under test meets a store that already carries a claim — pending, unless
            # `reconcile` below catches it up.
            if spec.get("setup"):
                emit(dirs + spec["setup"])
            # A REAL `reconcile --live --write`, off the same seam rows `_live_export_bytes`
            # already builds for the guard. Closes (or, left out, leaves open) the pending gap
            # `SkuMatch._cap_pending` reads.
            if spec.get("reconcile") is not None:
                reconciled = home / "reconciled.csv"
                reconciled.write_bytes(_live_export_bytes(spec["reconcile"]))
                command(checks, "reconcile", "--live", str(reconciled), "--write")
            worklists[name] = {
                "pricing": pipeline_routes.do_pipeline_worklist([]),
                "book": pipeline_routes.do_pricing_corpus().get("corpus") or {},
            }
            code, said = emit(dirs + spec["flags"] + extra)
            checks.equal(code, spec["exit"], f"{name}: emit exits {spec['exit']}")
            checks.equal(_m_files(dirs), {k: sorted(v) for k, v in spec["files"].items()},
                         f"{name}: the import files hold exactly these rows")
            for phrase in spec["says"]:
                checks.ok(phrase in said, f"{name}: emit says {phrase!r}", said[-1500:])
            for phrase in spec["never"]:
                checks.ok(phrase not in said, f"{name}: emit never says {phrase!r}", said[-1500:])
            if spec["route"] is not None:
                guard = send_routes._guard_line(said) or {}
                refusal = send_routes._empty_send_refusal(said, guard.get("trimmed") or [], "sent", code)
                want_code, _ = spec["route"]
                checks.equal(refusal.code, want_code, f"{name}: the route refuses as {want_code}")
                worklists[name]["empty"] = (refusal.data or {}).get("empty")
                worklists[name]["detail"] = str(refusal)

    try:
        home = _m_home(worklists)
    except _ToolchainMissing:
        checks.note("unknown: app/node_modules missing, run make worktree-setup")
        return
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        checks.ok(False, "Home can be read for every matrix case", str(exc))
        return
    for name, spec in cases.items():
        want, got = spec["home"], home[name]
        if spec["route"] is not None:
            # R6-2: the Send card's title states every reason; the server's sentence is only the
            # detail behind the fold. A refusal with no figures keeps its fixed title, and the
            # detail is what names it.
            title = got["title"] if got["title"] is not None else worklists[name]["detail"]
            for phrase in spec["route"][1]:
                checks.ok(phrase in title, f"{name}: the Send card's title says {phrase!r}", title)
        line = (got["line"] or {}).get("text", "")
        if want["line"] is None:
            checks.ok("send" not in line and "price" not in line, f"{name}: Home owes nothing on Pricing", line)
        else:
            checks.ok(want["line"] in line, f"{name}: Home says {want['line']!r}", line)
        if want.get("behind"):
            checks.ok(want["behind"] in (got["line"] or {}).get("behind", []),
                      f"{name}: Home names {want['behind']!r} behind the line", str(got["line"]))
        checks.ok(want["tile"] in got["tile"], f"{name}: the Pricing tile says {want['tile']!r}", got["tile"])
        # R6-4 AND R8-1: a failed read of typed prices degrades to the worklist's own counts, the
        # no-price count included, and a Pricing line names that read. A line from a rank below
        # Pricing still draws.
        failed = (got["failed"] or {})
        # R8-1: A FAILED READ IS NEVER CLEAR. `standing.ts` says Clear only from a complete
        # reading, so a store whose typed prices could not be read never reads as owing nothing.
        checks.ok(
            failed.get("lead") != "Clear" and "nothing is owed" not in failed.get("text", ""),
            f"{name}: with typed prices unread, Home never says Clear",
            str(failed),
        )
        # A ROW THAT OWES NOTHING ON A FAILED READ NAMES THE READ AND NOTHING ELSE (R8 review, LOW
        # note b). R8-1 lets the line say "typed prices", because the line is about that read. It
        # never asks for a send or a price, and nothing behind it counts a card owing a price.
        spare = failed.get("text", "").replace("typed prices", "")
        # THE `failed=None` BRANCH CARRIES THE SAME "typed prices" PROOF AS THE NAMED-TEXT
        # BRANCH (the b-pricing lane's round-8 review: this check was weaker for it). An empty
        # `want["line"]` case once skipped asking whether the failed-read note itself reached
        # the answer at all — a case whose `text` and `behind` both mutated to empty still
        # passed, because the None branch only asserted absences. THE NOTE RIDES ONE OF TWO
        # PLACES: `behind` for ranks 1-6 (`unread` in standing.ts), or `text` alone for rank
        # 7's terminal `unknown()`, whose own `behind` is always `[]` by that helper's own
        # shape — never both, and never neither. `has_note` is asserted for every case now,
        # named or not, so a note the mutation drops is the thing that goes red rather than
        # the words around it.
        has_note = "typed prices" in failed.get("text", "") or any(
            "typed prices" in b for b in failed.get("behind", [])
        )
        checks.ok(
            "the pricing worklist" not in failed.get("text", "")
            and has_note
            and (
                (
                    "send" not in spare and "price" not in spare
                    and not any("needs a price" in b or "need a price" in b for b in failed.get("behind", []))
                )
                if want.get("failed", want["line"]) is None
                else want.get("failed", want["line"]) in failed.get("text", "")
            ),
            f"{name}: with typed prices unread, Home still counts the worklist and names that read",
            str(failed),
        )
        if want.get("chip"):
            checks.ok(any(want["chip"] == chip for chip in got["chips"]),
                      f"{name}: a run chip says {want['chip']!r}", str(got["chips"]))
    # R8 REVIEW, LOW NOTE A: ranks 5 and 6 draw their own list behind the line. On a failed
    # read of typed prices they keep its note, and they are never Clear.
    for rank in ("working", "captured"):
        got = home.get(f"rank:{rank}") or {}
        checks.ok(
            got.get("key") == rank and got.get("lead") != "Clear"
            and any("typed prices" in label for label in got.get("behind", [])),
            f"with typed prices unread, Home's rank {rank!r} still names that read",
            str(got),
        )
    # R6-8: a SENT run that owes a price is told from one never sent that owes one too.
    checks.ok(
        all("Sent, 1 needs a price" in home[f"mix/{layout}/sent"]["chips"] for layout in ("one", "two")),
        "a sent run that owes a price says it was sent",
        str([home[f"mix/{layout}/sent"]["chips"] for layout in ("one", "two")]),
    )
    checks.ok(
        all(any(chip.startswith("Never sent, 1 needs") for chip in home[f"mix/{layout}/plain"]["chips"])
            for layout in ("one", "two")),
        "a never-sent run that owes a price says it was never sent",
        str([home[f"mix/{layout}/plain"]["chips"] for layout in ("one", "two")]),
    )
    checks.note(f"send matrix: {len(cases)} cases")


def check_live_listing_one_home(checks: Checks) -> None:
    """The worklist reads the newest live export by `sendguard.live_by_sku`'s rule (one home).

    A `Total Quantity` cell that is not a whole number must not take the worklist down (it
    was an uncaught ValueError, a 500), and an export with no `Total Quantity` column must
    not read as every SKU at 0 live: `live_by_sku` refuses both, and the worklist's reading of
    "live now" is then UNKNOWN (`live_now` None), never a confident zero.
    """
    checks.note("")
    checks.note("LIVE LISTING — the worklist and the send guard read one rule")

    head = "TCGplayer Id,Product Line,Set Name,Product Name,Title,Number,Rarity,Condition,TCG Market Price,TCG Marketplace Price"
    cases = {
        "a non-integer Total Quantity cell": (
            head.replace("TCG Market Price,", "TCG Market Price,Total Quantity,"),
            f'"{ARTICUNO_SKU}","Pokemon","Set","Articuno","","","","Near Mint","1.00","two","1.00"',
        ),
        "no Total Quantity column": (head, f'"{ARTICUNO_SKU}","Pokemon","Set","Articuno","","","","Near Mint","1.00","1.00"'),
    }
    for label, (header, row) in cases.items():
        with isolated_home():
            run_dir, _ = seam_run(checks, [(3, 1, "Articuno", "161", None)])
            live = files.inventory_dir() / pipeline_routes.LIVE_DIR
            live.mkdir(parents=True, exist_ok=True)
            (live / f"{pipeline_routes.LIVE_PREFIX}20260101-000000.csv").write_bytes(
                ("\r\n".join([header, row]) + "\r\n").encode("utf-8")
            )
            pipeline_routes._NEWEST_LIVE.clear()
            try:
                work = pipeline_routes.do_pipeline_worklist([run_dir.directory.name])
            except Exception as caught:  # noqa: BLE001 - any raise is the defect
                checks.ok(False, f"{label}: the worklist still answers", f"raised {type(caught).__name__}: {caught}")
                continue
            finally:
                pipeline_routes._NEWEST_LIVE.clear()
            row_out = next((r for r in work["skus"] if r["sku"] == ARTICUNO_SKU), {})
            checks.equal(
                row_out.get("live_now"), None,
                f"{label}: `live_by_sku` refuses it, so the worklist says live-now is unknown, never 0 copies",
            )


def check_money_one_home(checks: Checks) -> None:
    """One money rule: `tcgcsv.parse_price` is the home, and every caller agrees with it.

    `$1.50`, `1.50` and `1,234.50` parse the same everywhere a price cell is read.
    """
    checks.note("")
    checks.note("MONEY — parse_price's rule, read the same by every caller")

    def home(text):
        try:
            return tcgcsv.parse_price(text)
        except Exception as caught:  # noqa: BLE001
            return f"raised {type(caught).__name__}"

    def number(text):
        try:
            return pipeline_routes._number(text, "price")
        except pipeline_routes.PipelineRefusal:
            return None

    for text, want in (("$1.50", Decimal("1.50")), ("1.50", Decimal("1.50")), ("1,234.50", Decimal("1234.50"))):
        checks.equal(home(text), want, f"the home reads {text!r} as {want}")
        checks.equal(pipeline_routes._market_of(text), want, f"`_market_of` agrees with the home on {text!r}")
        checks.equal(send_routes._price(text), want, f"`send_routes._price` agrees with the home on {text!r}")
        checks.equal(number(text), want, f"`_number` agrees with the home on {text!r}")

    for text in ("1,50", "1,5", "1,2,3", ",5", "$", "$$5", "-", "N/A"):
        checks.equal(home(text), "raised InvalidOperation", f"the home refuses {text!r}, as main does")
    for text, want in (("$1,234.50", Decimal("1234.50")), ("-3", Decimal("-3"))):
        checks.equal(home(text), want, f"the home reads {text!r} as {want}")
    checks.equal(home(""), None, "a blank cell is None")
    checks.equal(send_routes._price("1,50"), None, "a named price of '1,50' is refused, never written as 150.00")


def check_live_listing_per_sku(checks: Checks) -> None:
    """A bad `Total Quantity` cell makes `live_now` unknown for that SKU only; two rows of one
    SKU sum; `do_pipeline_movers` still counts the SKUs the bad row does not touch."""
    checks.note("")
    checks.note("LIVE LISTING — one bad row takes only its own SKU")

    head = "TCGplayer Id,Product Line,Set Name,Product Name,Title,Number,Rarity,Condition,TCG Market Price,Total Quantity,TCG Marketplace Price"

    def line(sku, qty):
        return f'"{sku}","Pokemon","Set","Name","","","","Near Mint","1.00","{qty}","1.00"'

    def read(rows):
        with isolated_home():
            live = files.inventory_dir() / pipeline_routes.LIVE_DIR
            live.mkdir(parents=True, exist_ok=True)
            (live / f"{pipeline_routes.LIVE_PREFIX}20260101-000000.csv").write_bytes(
                ("\r\n".join([head, *rows]) + "\r\n").encode("utf-8")
            )
            pipeline_routes._NEWEST_LIVE.clear()
            try:
                _, listing = pipeline_routes._newest_live_listing()
                pipeline_routes._NEWEST_LIVE.clear()
                moved = pipeline_routes.do_pipeline_movers()
            finally:
                pipeline_routes._NEWEST_LIVE.clear()
            return {k: v[1] for k, v in listing.items()}, moved

        return None

    counts, _ = read([line("501", 2), line("501", 3)])
    checks.equal(counts, {"501": 5}, "two rows of one SKU sum")
    counts, moved = read([line("501", 2), line("502", "two"), line("503", 4)])
    checks.equal(counts, {"501": 2, "502": None, "503": 4}, "a bad cell is unknown for its own SKU only, every other SKU keeps its count")
    checks.equal(moved["listed"], 2, "`do_pipeline_movers` still counts the live SKUs a bad row does not touch")


def check_hold_takes_live_off(checks: Checks) -> None:
    """A SKU held on `#/pricing` with copies live comes off TCGplayer on the next send.

    THE OWNER'S RULING (D100's open question, "a negative `Add to Quantity` lowers a live
    quantity"), AS THE REVIEW OF PR #768 REDESIGNED IT. The size comes ONLY from a fresh live
    read taken for this send (`--live-guard`, no older than `reprice.READ_FRESH_S`): that
    read's live quantity for the held SKU, less copies sold since it. Never from the store's
    `pushed` or `live`. A held SKU the read does not name takes off 0, no row. The store
    changes NOTHING at write time, so a take-off that never lands heals: the next send
    re-reads live and takes off what is still there, and never twice for the same copies.

    THE WORDING THESE ASSERT: the report says "N copies ... off TCGplayer", and a refusal says
    "live read" and names the card. `tcg_import._check`'s `take_off` is a SKU -> size mapping.
    """
    checks.note("")
    checks.note("HOLD TAKES LIVE COPIES OFF — a negative row sized by a fresh live read")

    from cli import __main__ as entry
    from server import tcg_import

    cards = [(3, i, "Articuno", "161", None) for i in (1, 2, 3)]
    cards.append((3, 4, "Dunsparce", "120", "normal"))
    HOUR = 3600

    def live_file(run_dir, quantities, age_s=0, name="live-read.csv"):
        path = run_dir.path(name)
        path.write_bytes(_live_export_bytes(quantities))
        stamp = time.time() - age_s
        os.utime(path, (stamp, stamp))
        return path

    def emit(run_dirs, *flags, guard=None):
        """Run `emit`; `(code, said, rows)` where rows are the SKU -> quantity THIS press wrote,
        read from every import file it made or changed (a press that writes nothing leaves the
        earlier press's file on disk)."""
        run_dirs = run_dirs if isinstance(run_dirs, (list, tuple)) else [run_dirs]

        def snapshot():
            return {
                path: path.read_bytes()
                for run_dir in run_dirs
                for path in run_dir.directory.glob("import*.csv")
            }

        before = snapshot()
        argv = ["emit", *[str(run_dir.directory) for run_dir in run_dirs], *flags]
        if guard is not None:
            argv += ["--live-guard", str(guard)]
        with quiet() as said:
            code = entry.main(argv)
        rows = {}
        for path, data in snapshot().items():
            if before.get(path) != data:
                for row in tcgcsv.read_export(path).rows:
                    rows[row[tcgcsv.SKU_COLUMN]] = row[tcgcsv.QUANTITY_COLUMN]
        return code, said.getvalue(), rows

    def hold(sku, reason="keeping"):
        book = corpus.Corpus.read()
        if reason is None:
            book.answers.pop(sku, None)
        else:
            book.answers[sku] = corpus.Answer(value={"withheld": reason})
        book.write()

    def store_counts(sku):
        listing = Store().read().inventory.listings.get(sku)
        return (0, 0) if listing is None else (listing.pushed, listing.live)

    def sent_run():
        """A run whose Articuno copies went out (pushed) and whose Dunsparce did not."""
        run_dir, _ = seam_run(checks, cards)
        command(checks, "emit", str(run_dir.directory), "--quantity", f"{DUNSPARCE_SKU}=0")
        return run_dir

    # ------------------------------------- held, a fresh read of three: -3, store unchanged
    for reason in ("bullish", "keeping", "next_batch"):
        with isolated_home():
            run_dir = sent_run()
            before = store_counts(ARTICUNO_SKU)
            hold(ARTICUNO_SKU, reason)
            guard = live_file(run_dir, {ARTICUNO_SKU: 3, DUNSPARCE_SKU: 0})
            code, said, rows = emit(run_dir, guard=guard)
            checks.equal(
                rows.get(ARTICUNO_SKU),
                "-3",
                f"A HELD SKU ({reason}) THE FRESH READ SHOWS THREE OF takes three off: one row, -3",
            )
            checks.ok(
                code == 0 and re.search(r"3 copies.*off TCGplayer", said) is not None,
                f"the report says in a sentence how many come off. Got: {said[-300:]!r}",
            )
            checks.equal(
                store_counts(ARTICUNO_SKU),
                before,
                "THE STORE CHANGED NOTHING at write time: `pushed` and `live` drop only when "
                "the live check confirms the copies are gone",
            )
            if reason != "keeping":
                continue
            # HEALS: the take-off never landed, live still shows three, so it is taken again,
            # and once live shows none it is not taken twice.
            code, said, rows = emit(
                run_dir, guard=live_file(run_dir, {ARTICUNO_SKU: 3}, name="again.csv")
            )
            checks.equal(
                rows.get(ARTICUNO_SKU),
                "-3",
                "A TAKE-OFF THAT NEVER LANDED HEALS: the next send re-reads live and takes "
                "off what is still there",
            )
            code, said, rows = emit(
                run_dir, guard=live_file(run_dir, {ARTICUNO_SKU: 0}, name="gone.csv")
            )
            checks.ok(
                ARTICUNO_SKU not in rows,
                "and once TCGplayer shows none there is no row: never twice for the same copies",
            )

    # ------------------------------------- the size is the read's, never the store's
    with isolated_home():
        run_dir = sent_run()
        hold(ARTICUNO_SKU)
        code, said, rows = emit(run_dir, guard=live_file(run_dir, {ARTICUNO_SKU: 2}))
        checks.equal(
            rows.get(ARTICUNO_SKU),
            "-2",
            "THREE WERE SENT AND THE READ SHOWS TWO (one sold): minus two, from the read",
        )
        code, said, rows = emit(
            run_dir, guard=live_file(run_dir, {ARTICUNO_SKU: 5}, name="five.csv")
        )
        checks.equal(
            rows.get(ARTICUNO_SKU),
            "-5",
            "THE SIZE IS THE READ'S LIVE QUANTITY, never capped by the store's `pushed` (three)",
        )

    # ------------------------------------- copies sold since the read come off the size
    with isolated_home():
        run_dir = sent_run()
        hold(ARTICUNO_SKU)
        guard = live_file(run_dir, {ARTICUNO_SKU: 3}, age_s=50 * 60)
        capture_server.do_mark_sold(3, 3, {})
        code, said, rows = emit(run_dir, guard=guard)
        checks.equal(
            rows.get(ARTICUNO_SKU),
            "-2",
            "ONE COPY SOLD AFTER THE READ: three live less one sold since is minus two",
        )

    # ------------------------------------- a held SKU the fresh read does not name: no row
    with isolated_home():
        run_dir = sent_run()
        hold(ARTICUNO_SKU)
        code, said, rows = emit(run_dir, guard=live_file(run_dir, {DUNSPARCE_SKU: 0}))
        checks.ok(
            ARTICUNO_SKU not in rows,
            "A HELD SKU ABSENT FROM THE FRESH READ TAKES OFF 0: no row, whatever the store holds",
        )

    # ------------------------------------- no fresh read: refused, nothing written
    for label, age in (("a read older than the freshness rule", 25 * HOUR), ("no read at all", None)):
        with isolated_home():
            run_dir = sent_run()
            files_before = {p: p.read_bytes() for p in run_dir.directory.glob("import*.csv")}
            before = store_counts(ARTICUNO_SKU)
            hold(ARTICUNO_SKU)
            guard = None if age is None else live_file(run_dir, {ARTICUNO_SKU: 3}, age_s=age)
            code, said, rows = emit(run_dir, guard=guard)
            checks.ok(
                code != 0 and ARTICUNO_SKU in said and "live read" in said and not rows,
                f"{label.upper()}: refused with a sentence naming the card and the live "
                f"read, and no row written. Got: {said[-300:]!r}",
            )
            checks.ok(
                {p: p.read_bytes() for p in run_dir.directory.glob("import*.csv")} == files_before
                and store_counts(ARTICUNO_SKU) == before,
                f"{label}: no file written and the store untouched",
            )

    # ------------------------------------- held, never sent, nothing live: no row
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        hold(DUNSPARCE_SKU, "bullish")
        code, said, rows = emit(
            run_dir, guard=live_file(run_dir, {ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
        )
        checks.equal(
            rows,
            {ARTICUNO_SKU: "3"},
            "A HELD SKU THAT WAS NEVER SENT WRITES NO ROW, negative or otherwise",
        )

    # ------------------------------------- merged: one SKU in two runs is one row
    with isolated_home():
        first, _ = seam_run(checks, [(3, i, "Articuno", "161", None) for i in (1, 2)])
        second, _ = seam_run(checks, [(4, 1, "Articuno", "161", None)])
        book = corpus.Corpus.read()
        book.sub_threshold = "floor"
        book.write()
        command(checks, "emit", str(first.directory), str(second.directory))
        hold(ARTICUNO_SKU)
        code, said, rows = emit([first, second], guard=live_file(first, {ARTICUNO_SKU: 3}))
        checks.equal(
            rows,
            {ARTICUNO_SKU: "-3"},
            "TWO RUNS HOLDING THE SAME SKU WRITE ONE ROW, -3: not one per run and not -6",
        )

    # ------------------------------------- the send flags beside a take
    for flags in (
        ("--listed-only",),
        ("--split-games",),
        ("--cap", "1"),
        ("--quantity", f"{DUNSPARCE_SKU}=1"),
        ("--listed-only", "--cap", "1"),
    ):
        with isolated_home():
            run_dir = sent_run()
            hold(ARTICUNO_SKU)
            guard = live_file(run_dir, {ARTICUNO_SKU: 3, DUNSPARCE_SKU: 0})
            code, said, rows = emit(run_dir, *flags, guard=guard)
            checks.equal(
                rows.get(ARTICUNO_SKU),
                "-3",
                f"`{' '.join(flags)}` DOES NOT DROP OR RESIZE A TAKE-OFF: the held card still "
                "comes off by the whole read",
            )

    # ------------------------------------- `_check` compares the magnitude
    def row(quantity):
        return {"ProductConditionId": ARTICUNO_SKU, "MyPrice": "5.00", "AddToQuantity": quantity}

    def check_code(quantity, **kwargs):
        try:
            tcg_import._check([row(quantity)], **kwargs)
        except Exception as refusal:  # noqa: BLE001
            return getattr(refusal, "code", type(refusal).__name__)
        return None

    checks.equal(
        check_code("-3", listing=True, take_off={ARTICUNO_SKU: 3}),
        None,
        "A NEGATIVE THE SIZE EMIT COMPUTED PASSES the listing door",
    )
    checks.equal(
        check_code("-2", listing=True, take_off={ARTICUNO_SKU: 3}),
        "tcg_import_moves_quantity",
        "A NEGATIVE OF THE WRONG MAGNITUDE IS REFUSED, though its SKU is named",
    )
    checks.equal(
        check_code("-4", listing=True, take_off={ARTICUNO_SKU: 3}),
        "tcg_import_moves_quantity",
        "and so is a larger one",
    )
    checks.equal(
        check_code("-3", listing=True),
        "tcg_import_moves_quantity",
        "A NEGATIVE WITH NO TAKE-OFF NAMED IS STILL REFUSED on the listing door",
    )
    checks.equal(
        check_code("-1"),
        "tcg_import_moves_quantity",
        "and a price file refuses any negative",
    )

    # ------------------------------------- a SKU not held never gets a negative
    with isolated_home():
        run_dir = sent_run()
        code, said, rows = emit(run_dir, guard=live_file(run_dir, {ARTICUNO_SKU: 3}))
        checks.ok(
            not any(int(q) < 0 for q in rows.values()),
            "A SKU NOT HELD NEVER GETS A NEGATIVE, however many copies the read shows",
        )


def check_hold_take_reads(checks: Checks) -> None:
    """What the CLI does with a held SKU's read (the re-review of PR #768).

    D: a held SKU Banchi never sent, listed by hand and live in a fresh read, is taken off by
    the read's size. E: a held SKU with no fresh read and `pushed` 0 is never skipped in
    silence: the output names it and says there is no live read. F: a size comes from a read
    seconds old, so `--live-guard` older than an hour refuses the take-off (the 24-hour rule
    is for a mark-down's prices, too long for a size).
    """
    checks.note("")
    checks.note("HOLD TAKE-OFF READS — hand-listed, unread, and too old")

    from cli import __main__ as entry

    cards = [(3, i, "Articuno", "161", None) for i in (1, 2, 3)]

    def live_file(run_dir, quantities, age_s=0):
        path = run_dir.path("live-read.csv")
        path.write_bytes(_live_export_bytes(quantities))
        stamp = time.time() - age_s
        os.utime(path, (stamp, stamp))
        return path

    def emit(run_dir, guard=None):
        path = run_dir.path(runs.IMPORT_MERGED)
        before = path.read_bytes() if path.exists() else None
        argv = ["emit", str(run_dir.directory)]
        if guard is not None:
            argv += ["--live-guard", str(guard)]
        with quiet() as said:
            code = entry.main(argv)
        rows = {}
        after = path.read_bytes() if path.exists() else None
        if after is not None and after != before:
            rows = {r[tcgcsv.SKU_COLUMN]: r[tcgcsv.QUANTITY_COLUMN] for r in tcgcsv.read_export(path).rows}
        return code, said.getvalue(), rows

    def hold(sku):
        book = corpus.Corpus.read()
        book.answers[sku] = corpus.Answer(value={"withheld": "keeping"})
        book.write()

    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        hold(ARTICUNO_SKU)
        code, said, rows = emit(run_dir, live_file(run_dir, {ARTICUNO_SKU: 2}))
        checks.equal(
            rows.get(ARTICUNO_SKU),
            "-2",
            "D: A HELD SKU BANCHI NEVER SENT, LIVE 2 IN A FRESH READ, is taken off by two",
        )

    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        hold(ARTICUNO_SKU)
        code, said, rows = emit(run_dir)
        checks.ok(
            "Articuno" in said and "live read" in said,
            "E: A HELD SKU WITH NO FRESH READ AND `pushed` 0 IS NOT SKIPPED IN SILENCE: the "
            f"output names it and says there is no live read. Got: {said[-300:]!r}",
        )

    for label, age, wanted in (("thirty minutes", 1800, "-3"), ("two hours", 7200, None)):
        with isolated_home():
            run_dir, _ = seam_run(checks, cards)
            command(checks, "emit", str(run_dir.directory))
            hold(ARTICUNO_SKU)
            code, said, rows = emit(run_dir, live_file(run_dir, {ARTICUNO_SKU: 3}, age_s=age))
            if wanted:
                checks.equal(rows.get(ARTICUNO_SKU), wanted, f"F: a read {label} old still sizes a take-off")
            else:
                checks.ok(
                    code != 0 and not rows and "live read" in said,
                    f"F: A READ {label.upper()} OLD IS REFUSED for a size, nothing written. "
                    f"Got: {said[-300:]!r}",
                )

    # ------------------------------------- a held SKU in no selected run (the store-wide worklist)
    def two_runs():
        sent_run, _ = seam_run(checks, cards)
        command(checks, "emit", str(sent_run.directory))
        other, _ = seam_run(checks, [(4, 1, "Dunsparce", "120", "normal")])
        hold(ARTICUNO_SKU)
        return other

    with isolated_home():
        other = two_runs()
        guard = live_file(other, {ARTICUNO_SKU: 3, DUNSPARCE_SKU: 0})
        with quiet():
            entry.main(["emit", str(other.directory), "--split-games", "--live-guard", str(guard)])
        homes = [
            path.name
            for path in other.directory.glob("import*.csv")
            if any(
                r[tcgcsv.SKU_COLUMN] == ARTICUNO_SKU and r[tcgcsv.QUANTITY_COLUMN] == "-3"
                for r in tcgcsv.read_export(path).rows
            )
        ]
        checks.ok(
            len(homes) == 1 and "pokemon" in homes[0].lower(),
            f"A HELD SKU IN NO SELECTED RUN IS FILED UNDER ITS OWN GAME in a `--split-games` "
            f"send: one file, named for the game. Got: {homes}",
        )

    with isolated_home():
        sent_run, _ = seam_run(checks, cards)  # never emitted: `pushed` 0
        other, _ = seam_run(checks, [(4, 1, "Dunsparce", "120", "normal")])
        hold(ARTICUNO_SKU)
        code, said, rows = emit(other)
        checks.ok(
            ARTICUNO_SKU in said and "live read" in said,
            "A HELD SKU IN NO SELECTED RUN, NO FRESH READ AND `pushed` 0, IS NAMED in the "
            f"output. Got: {said[-300:]!r}",
        )


CHECKS = (
    check_pipeline_routes,
    check_emit_claim_decides,
    check_emit_unpriced_left_out,
    check_send_matrix,
    check_emit_identity_stamp,
    check_pricing_authority,
    check_prices_adopt,
    check_readings_adopt_cli,
    check_readings_writer_after_join,
    check_readings_writer_after_live_export,
    check_merged_emit_cap,
    check_merged_emit_uncapped,
    check_unsent_copies_worklist,
    check_worklist_on_hand,
    check_worklist_on_hand_unstamped,
    check_cap_flag_refusals,
    check_emit_send_quantity,
    check_hold_takes_live_off,
    check_hold_take_reads,
    check_merged_cap_is_the_tightest,
    check_threshold_and_file_shape,
    check_live_reconcile,
    check_phantom_worklist,
    check_unsent_listing_sells_out,
    check_pricing_reach,
    check_live_listing_one_home,
    check_money_one_home,
    check_live_listing_per_sku,
)
