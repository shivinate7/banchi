"""T7 group: markdown, the send guard and its review rounds, the pricing route.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import contextlib
import json
import http.server
import os
import shutil
import sqlite3
import re
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import envfile

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from http import HTTPStatus
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from harness.tests import Checks
from cli import cmd_reprice, resolve, runs
from pipeline import corpus, reprice, sendguard, tcgcsv
from server import capture_server, pipeline_routes, send_routes, tcg_export, tcg_import
from store import db, files, master, sendclaims
from store.session import Store
from harness.tests.t7.common import (
    ARTICUNO_SKU,
    DUNSPARCE_REVERSE_SKU,
    DUNSPARCE_SKU,
    FIXTURE_EXPORT,
    QuietHandler,
    SEAM_SKUS,
    _live_export_bytes,
    _spawn_server,
    capture_payload,
    command,
    error_code,
    isolated_home,
    quiet,
    request,
    seam_run,
)

def check_markdown(checks: Checks) -> None:
    """The live listings that are not selling, marked down and pushed back (D100).

    THE ONE INVARIANT THAT CARRIES MONEY IS ASSERTED FOUR TIMES, in four different ways,
    because the defect it prevents has already happened once on the owner's real store.
    `Add to Quantity` is a DELTA against the quantity TCGplayer already holds — measured:
    72,701 real export rows carry "0", including all 649 on which TCGplayer simultaneously
    reported live copies — and one import file uploaded twice left nine SKUs at exactly
    `2 x pushed - sold`. So: the worklist carries 0, the upload carries 0, a worklist handed
    back carrying 4 still produces an upload carrying 0, and the whole file refuses rather
    than write a row that does not.

    THE UPLOAD IS BUILT FROM THE MANIFEST'S BYTES AND NOT FROM THE FILE THE OPERATOR HANDS
    BACK, which is the structural half of the same argument: only `TCGplayer Id` and
    `TCG Marketplace Price` are read out of the worklist, so a spreadsheet's reformatting —
    a stripped leading zero in `Number`, a trailing zero gone from a price, a re-rendered
    empty cell — cannot reach TCGplayer through this path. The case below mangles all three
    and asserts the output is byte-identical to the unmangled one.

    AND A PRICE IS COMPARED AS `Decimal`, NEVER AS TEXT. A live export writes four decimal
    places ("0.6600") where this pipeline writes two ("0.66"); those are equal as money and
    different as bytes, and a string comparison would read every untouched row as an edit and
    mark down the whole store on a rounding artefact.

    THE AGE TERM IS A PROXY AND THE REPORT SAYS SO. The store cannot measure how long a
    listing has been live — `Listing` has no first-listed stamp, and `live_as_of` is absent
    from all 443 stored payloads on the owner's store — so what is measured is the oldest
    capture of any card that ever carried the SKU. The sentence is asserted here because it
    is the one thing in the report that is not what it looks like.
    """
    checks.note("")
    checks.note("MARKDOWN — the live listings that are not selling")

    # THE REVERSE-HOLO COPY IS HERE TO BE PRICED AT THE FLOOR. Without a card carrying it the
    # SKU would be refused as `not_this_store` before the floor was ever consulted, and the
    # case below would pass for the wrong reason.
    cards = [
        (3, 1, "Dunsparce", "120", "normal"),
        (3, 2, "Dunsparce", "120", "normal"),
        (3, 3, "Articuno", "161", None),
        (3, 4, "Dunsparce", "120", "reverse_holo"),
    ]

    def live_export(path, *, live, asking, sold_out=()):
        """A My Pricing export: the seam rows, live, with an asking price on each.

        `TCG Marketplace Price` is BLANK on every row of the Filtered Export fixture, and
        populated on 441 of 441 live rows of the owner's real My Pricing download. That
        difference is the whole reason `reprice.BASIS_ASKING` is local to that module rather
        than added to `pricing.BASES`: a basis reading this column would leave the price
        untouched on an ordinary listing run with nothing anywhere raising.
        """
        source = tcgcsv.read_export(FIXTURE_EXPORT)
        by_sku = source.by_sku()
        rows = []
        for sku in SEAM_SKUS:
            row = dict(by_sku[sku])
            row[tcgcsv.LIVE_QUANTITY_COLUMN] = "0" if sku in sold_out else str(live.get(sku, 1))
            # FOUR DECIMAL PLACES, THE WAY THE REAL EXPORT WRITES THEM. Two decimals here
            # would let a string comparison pass every case below.
            row[tcgcsv.PRICE_COLUMN] = f"{Decimal(asking[sku]):.4f}"
            rows.append(row)
        tcgcsv.write_csv(path, source.header, rows)
        return Path(path)

    def rows_of(path):
        return list(tcgcsv.read_export(path).rows)

    with isolated_home() as home:
        run_dir, _ = seam_run(checks, cards)
        book = corpus.Corpus.read()
        book.sub_threshold = "floor"
        book.write()
        command(checks, "emit", str(run_dir.directory))

        # OWNED THIRTY DAYS, WRITTEN INTO THE STORE RATHER THAN WAITED FOR. The window's third
        # term reads `Card.captured_at` over every card that ever carried the SKU, and a
        # capture taken a moment ago is `too_young` for every window a person would ask for.
        old = "2026-08-01T00:00:00.000+00:00"
        with Store().write() as writable:
            for box, index, *_ in cards:
                writable.inventory.cards[master.position_key(box, index)].captured_at = old

        export = live_export(
            home / "live.csv",
            live={DUNSPARCE_SKU: 2, DUNSPARCE_REVERSE_SKU: 1, ARTICUNO_SKU: 1},
            asking={DUNSPARCE_SKU: "2.00", DUNSPARCE_REVERSE_SKU: "0.40", ARTICUNO_SKU: "20.00"},
        )

        said = command(checks, "reprice", "list", str(export), "--days", "7", "--percent", "10")
        checks.ok("DRY RUN" in said, "IT PREVIEWS BY DEFAULT — nothing is written without --write")
        checks.ok(
            not (files.inventory_dir() / cmd_reprice.DIRNAME).exists(),
            "and the preview created no directory at all, not an empty one",
        )
        # THE SUBSTITUTION IS STILL NAMED — and the assertion moved from "the proxy paragraph
        # is present" to "the report says WHICH CLOCK IT USED", because printing the proxy
        # paragraph unconditionally became a lie of its own once `Listing.first_seen_live`
        # gave some rows a real listing age. D100's rule cuts both ways: a substitution nobody
        # is told about is a lie, and so is one claimed where it is not happening. This
        # fixture's store has no sightings, so every row falls back and the sentence is owed.
        checks.ok(
            "fall back to OWNERSHIP" in said and "never the age itself" in said,
            "THE PROXY IS NAMED ON THE REPORT'S OWN HEADER, for the rows that actually use "
            "it. The store cannot say how long these listings have been live, and a "
            "substitution the operator is not told about is a lie",
            said,
        )
        checks.ok(
            "dated by FIRST SIGHTING" not in said,
            "AND THE REPORT DOES NOT CLAIM A SIGHTING IT DOES NOT HAVE. No reconcile has run "
            "over this store, so no row has a listing age and none may be reported as having "
            "one — the same rule, pointed the other way",
            said,
        )
        checks.ok(
            f"[{reprice.AT_FLOOR}]" in said,
            f"the $0.40 listing is refused as `{reprice.AT_FLOOR}` rather than written as a "
            f"no-op row — there is nowhere down to go, and D9's floor is what says so",
        )

        command(checks, "reprice", "list", str(export), "--days", "7", "--percent", "10", "--write")
        made = sorted((files.inventory_dir() / cmd_reprice.DIRNAME).iterdir())
        checks.equal(len(made), 1, "--write made exactly one markdown directory")
        directory = made[0]
        worklist = rows_of(directory / cmd_reprice.WORKLIST)
        checks.equal(
            sorted(row[tcgcsv.SKU_COLUMN] for row in worklist),
            sorted([DUNSPARCE_SKU, ARTICUNO_SKU]),
            "the worklist holds the two listings above the floor and not the one at it",
        )
        checks.equal(
            sorted({row[tcgcsv.QUANTITY_COLUMN] for row in worklist}),
            ["0"],
            "EVERY WORKLIST ROW CARRIES `Add to Quantity` 0. The worklist is export-shaped and "
            "therefore uploadable by accident; this is what makes that harmless",
        )
        original = tcgcsv.read_export(export).by_sku()
        for row in worklist:
            try:
                tcgcsv.check_only_writable_changed(original[row[tcgcsv.SKU_COLUMN]], row)
                clean = True
            except tcgcsv.ReadOnlyColumn:
                clean = False
            checks.ok(
                clean,
                f"and {row[tcgcsv.SKU_COLUMN]}'s worklist row differs from the export in the "
                f"two writable columns and nowhere else",
            )

        # ---------------------------------------------------------------- reading it back
        said = command(checks, "reprice", "apply", str(directory / cmd_reprice.WORKLIST))
        checks.ok("DRY RUN" in said, "apply previews by default too")
        checks.ok(
            not (directory / cmd_reprice.IMPORT).exists(),
            "and wrote no import file — the last press before bytes leave for a marketplace",
        )

        command(checks, "reprice", "apply", str(directory / cmd_reprice.WORKLIST), "--write")
        upload = rows_of(directory / cmd_reprice.IMPORT)
        checks.equal(
            sorted({row[tcgcsv.QUANTITY_COLUMN] for row in upload}),
            ["0"],
            "EVERY UPLOADED ROW CARRIES `Add to Quantity` 0, so the file lowers prices and "
            "cannot add, remove or delete a copy — uploading it twice is a no-op the second "
            "time, which is not true of an import from `emit`",
        )
        checks.equal(
            {row[tcgcsv.SKU_COLUMN]: row[tcgcsv.PRICE_COLUMN] for row in upload},
            {DUNSPARCE_SKU: "1.80", ARTICUNO_SKU: "18.00"},
            "and the prices are the rule's, rounded then floored, off the ASKING price",
        )
        answered = corpus.Corpus.read().answers
        checks.equal(
            {sku: answered[sku].value for sku in (DUNSPARCE_SKU, ARTICUNO_SKU)},
            {DUNSPARCE_SKU: "1.80", ARTICUNO_SKU: "18.00"},
            "THE ANSWER GOES IN THE CORPUS, KEYED BY SKU (D86). Without it the next `emit` "
            "over another copy re-lists at the rule price and quietly undoes the markdown",
        )

        # ------------------------------------------------------------------- the ratchet
        said = command(checks, "reprice", "list", str(export), "--days", "7", "--percent", "10")
        checks.ok(
            f"[{reprice.PRICED_RECENTLY}]" in said,
            f"THE RATCHET. A SKU this store answered inside the window is refused as "
            f"`{reprice.PRICED_RECENTLY}` — `undercut:10` run daily compounds to -52% in a "
            f"week, with every single run justified because the card still has not sold",
        )
        said = command(
            checks, "reprice", "list", str(export), "--days", "7", "--percent", "10", "--again"
        )
        checks.ok(
            f"[{reprice.PRICED_RECENTLY}]" not in said,
            "and `--again` lifts it, which is the only way past it",
        )

        # --------------------------------------------------- what the operator hands back
        def hand_back(name, mutate):
            """Write an edited worklist into its own directory, beside the same manifest."""
            target = files.inventory_dir() / cmd_reprice.DIRNAME / name
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy(directory / cmd_reprice.MANIFEST, target / cmd_reprice.MANIFEST)
            edited = [dict(row) for row in rows_of(directory / cmd_reprice.WORKLIST)]
            edited = mutate(edited)
            tcgcsv.write_csv(
                target / cmd_reprice.WORKLIST, tcgcsv.CANONICAL_HEADER, edited
            )
            return target

        def apply_edited(target):
            from cli import __main__ as entry

            with quiet() as said:
                code = entry.main(
                    ["reprice", "apply", str(target / cmd_reprice.WORKLIST), "--write"]
                )
            return code, said.getvalue()

        def raised(rows):
            rows[0][tcgcsv.PRICE_COLUMN] = "99.99"
            return rows

        code, said = apply_edited(hand_back("20200101-000001", raised))
        # THIS ASSERTION IS THE INVERSE OF THE ONE IT REPLACES (D107). It used to read "a
        # raised price refuses the whole file — this path only lowers". The owner asked for
        # raises, and what was retired is the REFUSAL, not the care: the rule still cannot
        # propose one (`plan` refuses `NOT_A_MARKDOWN`), so a price above `was` is one a person
        # typed, and the file says so on its face rather than passing quietly.
        written = (files.inventory_dir() / cmd_reprice.DIRNAME / "20200101-000001"
                   / cmd_reprice.IMPORT)
        checks.ok(
            code == 0 and written.exists(),
            "AN OPERATOR'S RAISE GOES THROUGH — the screen offers a price field and this is "
            "what makes it one the pipeline will honour in both directions",
        )
        checks.ok(
            "RAISED" in said or "raised" in said.lower(),
            "and the report SAYS SO. A row pointing up inside a thing called a markdown is the "
            "one an operator most needs told about",
        )
        # THE MONEY FIGURE DOES NOT NET, which is the part a careless implementation gets
        # wrong: `given_up` answers "what does pressing this cost me", and a raise offsetting a
        # markdown would report a file that cuts $40 and lifts $40 as free.
        sent = tcgcsv.read_export(written).rows
        checks.ok(
            any(row[tcgcsv.PRICE_COLUMN] == "99.99" for row in sent),
            "and the raised price is what reaches the upload, unrounded and unmodified",
        )
        checks.ok(
            all(row[tcgcsv.QUANTITY_COLUMN] == "0" for row in sent),
            "AND EVERY ROW STILL CARRIES `Add to Quantity` 0 — D100's invariant is about "
            "quantity and is untouched by which way the price moved",
        )

        def duplicated(rows):
            return rows + [dict(rows[0])]

        code, said = apply_edited(hand_back("20200101-000002", duplicated))
        checks.ok(
            code == 1 and f"[{reprice.DUPLICATE}]" in said,
            "A DUPLICATED SKU REFUSES THE WHOLE FILE (D7). Two rows with one `TCGplayer Id` "
            "in one import is undefined behaviour at TCGplayer, not a row to skip past",
        )

        def carrying_quantity(rows):
            for row in rows:
                row[tcgcsv.QUANTITY_COLUMN] = "4"
            return rows

        target = hand_back("20200101-000003", carrying_quantity)
        code, _ = apply_edited(target)
        checks.equal(
            sorted({row[tcgcsv.QUANTITY_COLUMN] for row in rows_of(target / cmd_reprice.IMPORT)}),
            ["0"],
            "A WORKLIST HANDED BACK CARRYING A QUANTITY STILL PRODUCES AN UPLOAD CARRYING 0. "
            "The quantity is not a variable on this path: the upload is built from the "
            "manifest's bytes, and the operator's file supplies only the SKU and the price",
        )

        def like_a_spreadsheet(rows):
            """What Excel does to a CSV it opens and saves."""
            for row in rows:
                row[tcgcsv.NUMBER_COLUMN] = row[tcgcsv.NUMBER_COLUMN].lstrip("0")
                row[tcgcsv.LOW_PRICE_COLUMN] = "0.01"
                row["Photo URL"] = "0"
            return rows

        target = hand_back("20200101-000004", like_a_spreadsheet)
        apply_edited(target)
        checks.equal(
            (target / cmd_reprice.IMPORT).read_bytes(),
            (directory / cmd_reprice.IMPORT).read_bytes(),
            "AND A MANGLED WORKLIST PRODUCES A BYTE-IDENTICAL UPLOAD. A spreadsheet strips a "
            "leading zero from `Number` and a trailing one from a price; none of it can reach "
            "TCGplayer, because the edited file is an instruction sheet and never a source of "
            "bytes",
        )

        def four_decimals(rows):
            """The export's own rendering of the price already in the file."""
            for row in rows:
                row[tcgcsv.PRICE_COLUMN] = f"{Decimal(row[tcgcsv.PRICE_COLUMN]):.4f}"
            return rows

        target = hand_back("20200101-000005", four_decimals)
        code, said = apply_edited(target)
        checks.ok(
            f"[{reprice.UNCHANGED}]" not in said and (target / cmd_reprice.IMPORT).exists(),
            "A PRICE IS COMPARED AS `Decimal`, NEVER AS TEXT. The export writes four decimal "
            "places and this writer emits two; equal as money, different as bytes, and a "
            "string comparison would mark down the whole store on a rounding artefact",
        )

        # ------------------------------------------------------- what the window refuses
        stranger = live_export(
            home / "stranger.csv",
            live={DUNSPARCE_SKU: 2, DUNSPARCE_REVERSE_SKU: 1, ARTICUNO_SKU: 1},
            asking={DUNSPARCE_SKU: "2.00", DUNSPARCE_REVERSE_SKU: "5.00", ARTICUNO_SKU: "20.00"},
            sold_out=(ARTICUNO_SKU,),
        )
        said = command(checks, "reprice", "list", str(stranger), "--days", "7", "--again")
        checks.ok(
            f"[{reprice.SOLD_OUT}]" in said,
            f"a row TCGplayer holds no copies of is `{reprice.SOLD_OUT}` — the export keeps "
            f"the row and there is no listing to re-price",
        )

        with Store().write() as writable:
            writable.inventory.set_state(master.position_key(3, 1), master.SOLD)
        said = command(checks, "reprice", "list", str(export), "--days", "7", "--again")
        checks.ok(
            f"[{reprice.SOLD_RECENTLY}]" in said,
            f"A COPY THAT SOLD INSIDE THE WINDOW IS `{reprice.SOLD_RECENTLY}`, read off the "
            f"CARD RECORDS and never the event log: one of the 193 `sold` events on the "
            f"owner's store carries no `sku` key, and a query over the log loses it silently",
        )

def check_markdown_floor(checks: Checks) -> None:
    """The floor a markdown obeys is the STORE's cut-off (D9, amended 2026-09-09).

    THE DEFECT, MEASURED ON THE OWNER'S REAL STORE ON 2026-09-09. `policy.threshold` was
    $0.29; every clamp in `pipeline/reprice.py` read `pricing.FLOOR`. `reprice apply` over a
    354-row worklist wrote 49 SKUs and refused 293 as `below_floor`, naming *"below the $0.40
    floor"* — a figure the store had not used for a week — after writing all 342 answers into
    `prices.json`. So the screen said the work was done, the corpus agreed, and the spreadsheet
    that goes to TCGplayer carried a seventh of it.

    BOTH DIRECTIONS ARE ASSERTED, because a fix that only widens is a fix that removed a guard.
    A cut-off LOOSER than a price lets it through; a cut-off TIGHTER than it still refuses.

    AND THE OFFER IS ASSERTED TOO, not just the apply. `plan` refuses a candidate already at or
    under the floor as `at_floor`, so at $0.40 a $0.35 listing was never proposed either — the
    two halves of one figure, and a fix to one of them would leave the other silently wrong.
    """
    checks.note("")
    checks.note("MARKDOWN FLOOR — the store's cut-off, in both directions")

    cards = [
        (3, 1, "Dunsparce", "120", "normal"),
        (3, 2, "Articuno", "161", None),
    ]

    def live_export(path, *, asking):
        source = tcgcsv.read_export(FIXTURE_EXPORT)
        by_sku = source.by_sku()
        rows = []
        for sku in SEAM_SKUS:
            row = dict(by_sku[sku])
            row[tcgcsv.LIVE_QUANTITY_COLUMN] = "1" if sku in asking else "0"
            row[tcgcsv.PRICE_COLUMN] = f"{Decimal(asking.get(sku, '0')):.4f}"
            rows.append(row)
        tcgcsv.write_csv(path, source.header, rows)
        return Path(path)

    with isolated_home() as home:
        run_dir, _ = seam_run(checks, cards)
        book = corpus.Corpus.read()
        # THE OWNER'S OWN FIGURE, WHICH IS WHAT MAKES THIS A REGRESSION TEST RATHER THAN A
        # PARAMETER SWEEP: $0.29 is below D9's $0.40, so every constant-reading clamp in the
        # pipeline disagrees with it and disagrees in the direction that costs an upload.
        book.threshold = "0.29"
        book.sub_threshold = {"flat": "0.29"}
        book.write()
        # `emit` IS WHAT PUTS THE SKU ON THE CARD RECORD, and without it every row here is
        # `too_young` — dated by neither clock, because `owned_since` is keyed by SKU and the
        # store does not know one until the pipeline chooses it. Not incidental setup: it is
        # also the half of this amendment the join path owns, so the file it writes is the
        # $0.29 store's own listed price.
        command(checks, "emit", str(run_dir.directory))

        old = "2026-08-01T00:00:00.000+00:00"
        with Store().write() as writable:
            for box, index, *_ in cards:
                writable.inventory.cards[master.position_key(box, index)].captured_at = old

        # $0.35 SITS BETWEEN THE TWO FIGURES, WHICH IS THE WHOLE POINT. At the store's $0.29 it
        # is a live listing with room to fall; at `pricing.FLOOR` it is already under the floor.
        export = live_export(home / "live.csv", asking={DUNSPARCE_SKU: "0.35"})
        said = command(
            checks, "reprice", "list", str(export), "--days", "7", "--percent", "10", "--write"
        )
        checks.ok(
            "floored at $0.29" in said,
            "THE REPORT NAMES THE STORE'S FIGURE. `below_floor`'s own sentence carries no "
            "number on purpose, so this line is the only place the floor is printed and it can "
            "only print the value actually used",
            said,
        )
        checks.ok(
            f"[{reprice.AT_FLOOR}]" not in said,
            f"AND THE $0.35 LISTING IS OFFERED. At `pricing.FLOOR` it was refused "
            f"`{reprice.AT_FLOOR}` — 'nowhere down to go' against a floor the operator had "
            f"moved — so the rule never proposed the row the apply then never wrote",
            said,
        )
        directory = sorted((files.inventory_dir() / cmd_reprice.DIRNAME).iterdir())[-1]
        offered = [row[tcgcsv.SKU_COLUMN] for row in tcgcsv.read_export(
            directory / cmd_reprice.WORKLIST
        ).rows]
        checks.equal(
            offered,
            [DUNSPARCE_SKU],
            "and the worklist holds it — the proposal is $0.32, which is `undercut:10` off "
            "$0.35 rounded, clamped at $0.29 rather than lifted to $0.40",
        )

        def hand_priced(name, price, *, cut_off=None):
            """Hand one price back, optionally after moving the store's cut-off under it."""
            from cli import __main__ as entry

            target = files.inventory_dir() / cmd_reprice.DIRNAME / name
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy(directory / cmd_reprice.MANIFEST, target / cmd_reprice.MANIFEST)
            rows = [dict(row) for row in tcgcsv.read_export(
                directory / cmd_reprice.WORKLIST
            ).rows]
            for row in rows:
                row[tcgcsv.PRICE_COLUMN] = price
            tcgcsv.write_csv(target / cmd_reprice.WORKLIST, tcgcsv.CANONICAL_HEADER, rows)
            if cut_off is not None:
                moved = corpus.Corpus.read()
                moved.threshold = cut_off
                moved.write()
            with quiet() as out:
                code = entry.main(
                    ["reprice", "apply", str(target / cmd_reprice.WORKLIST), "--write"]
                )
            return target, code, out.getvalue()

        target, code, said = hand_priced("20200101-000101", "0.29")
        upload = target / cmd_reprice.IMPORT
        checks.ok(
            code == 0 and upload.is_file(),
            "A PRICE AT THE STORE'S OWN CUT-OFF REACHES THE UPLOAD. This is the row that was "
            "refused 293 times on the owner's store: the answer went into `prices.json` and "
            "the spreadsheet TCGplayer reads did not carry it",
            said,
        )
        # READ ONLY IF IT IS THERE, so a regression reports as a NAMED failure rather than as a
        # `FileNotFoundError` out of the middle of the module. Measured while mutation-testing
        # this block: three of the four arms make the upload not exist, and a traceback aborts
        # T7 before a single one of these sentences is printed — so the guard fires and says
        # nothing about which floor was wrong.
        checks.equal(
            {row[tcgcsv.SKU_COLUMN]: row[tcgcsv.PRICE_COLUMN]
             for row in tcgcsv.read_export(upload).rows} if upload.is_file() else None,
            {DUNSPARCE_SKU: "0.29"},
            "and it is the operator's figure, unrounded and unlifted",
        )
        checks.ok(
            f"[{reprice.BELOW_FLOOR}]" not in said,
            f"with no `{reprice.BELOW_FLOOR}` anywhere in the report",
            said,
        )

        # ---------------------------------------------------- and the guard still bites
        target, code, said = hand_priced("20200101-000102", "0.29", cut_off="0.50")
        checks.ok(
            f"[{reprice.BELOW_FLOOR}]" in said and not (target / cmd_reprice.IMPORT).exists(),
            f"TIGHTEN THE CUT-OFF ABOVE THE PRICE AND THE SAME FILE IS REFUSED "
            f"`{reprice.BELOW_FLOOR}`. The floor FOLLOWS the store; it was not removed, and a "
            f"widening that could not still refuse would have deleted the guard rather than "
            f"corrected it",
            said,
        )
        checks.ok(
            "floored at $0.50" in said,
            "AND THE FIGURE IS READ AT THE PRESS RATHER THAN OFF THE MANIFEST. The survey was "
            "taken at $0.29; what a price may not go below is the cut-off in force when the "
            "operator presses, which is the figure on the screen in front of them",
            said,
        )

def check_markdown_lens(checks: Checks) -> None:
    """`survey.json`, and the rows the offer never held (D103).

    THE LENS'S PREMISE IS THAT STALENESS IS A FILTER, so `#/pricing` has to be able to draw —
    and price — a live listing the rule declined to propose. Today's manifest holds `plan.rows`
    alone, which on the owner's export is ~109 of 441; the other ~332 had no bytes anywhere and
    were refused `not_in_worklist`.

    THE RECORD WIDENS AND THE OFFER DOES NOT, and every assertion here is about that seam.
    `survey.json` carries every candidate with its verdict; `worklist.csv` still carries only
    the rows the rule proposed, which is what keeps D100's *"every file this feature writes is
    safe to upload, whichever one the operator grabs"* true — a 441-row worklist proposing
    prices on rows the rule refused would mark down the whole store if uploaded by accident.

    AND `dropped` FOLLOWS THE OFFER RATHER THAN THE RECORD. That figure means "SKUs this file
    was written for that you deleted", and measured over the wider set it would tell an
    operator who priced three cards that they had deleted four hundred. It is the assertion
    that catches the sloppy version of this whole change.
    """
    checks.note("")
    checks.note("MARKDOWN LENS — the survey, and pricing a row the offer never held")

    cards = [
        (3, 1, "Dunsparce", "120", "normal"),
        (3, 2, "Dunsparce", "120", "normal"),
        (3, 3, "Articuno", "161", None),
        (3, 4, "Dunsparce", "120", "reverse_holo"),
    ]

    def live_export(path, *, live, asking, sold_out=()):
        source = tcgcsv.read_export(FIXTURE_EXPORT)
        by_sku = source.by_sku()
        rows = []
        for sku in SEAM_SKUS:
            row = dict(by_sku[sku])
            row[tcgcsv.LIVE_QUANTITY_COLUMN] = "0" if sku in sold_out else str(live.get(sku, 1))
            row[tcgcsv.PRICE_COLUMN] = f"{Decimal(asking[sku]):.4f}"
            rows.append(row)
        tcgcsv.write_csv(path, source.header, rows)
        return Path(path)

    with isolated_home() as home:
        run_dir, _ = seam_run(checks, cards)
        book = corpus.Corpus.read()
        book.sub_threshold = "floor"
        book.write()
        command(checks, "emit", str(run_dir.directory))

        old = "2026-08-01T00:00:00.000+00:00"
        with Store().write() as writable:
            for box, index, *_ in cards:
                writable.inventory.cards[master.position_key(box, index)].captured_at = old

        # ARTICUNO IS SOLD OUT, AND `--limit 1` DEFERS ONE OF THE TWO THAT QUALIFY. So the
        # survey holds three rows in all three standings — one offered, one deferred, one
        # refused — and the offer holds exactly one. That gap is the whole subject here.
        #
        # `at_risk` RANKS THEM: the reverse holo asks $5.00 over one live copy and Dunsparce
        # $2.00 over two, so the limit keeps the reverse holo and defers Dunsparce.
        export = live_export(
            home / "live.csv",
            live={DUNSPARCE_SKU: 2, DUNSPARCE_REVERSE_SKU: 1, ARTICUNO_SKU: 1},
            asking={DUNSPARCE_SKU: "2.00", DUNSPARCE_REVERSE_SKU: "5.00", ARTICUNO_SKU: "20.00"},
            sold_out=(ARTICUNO_SKU,),
        )

        command(
            checks, "reprice", "list", str(export),
            "--days", "7", "--percent", "10", "--limit", "1", "--write",
        )
        directory = sorted((files.inventory_dir() / cmd_reprice.DIRNAME).iterdir())[0]

        manifest = json.loads((directory / cmd_reprice.MANIFEST).read_text("utf-8"))
        survey = json.loads((directory / cmd_reprice.SURVEY).read_text("utf-8"))
        by_sku = {row["sku"]: row for row in survey["skus"]}

        checks.equal(
            sorted(manifest["skus"]),
            [DUNSPARCE_REVERSE_SKU],
            "THE OFFER STAYS NARROW. Only the row the rule proposed is in the manifest, which "
            "is what keeps `worklist.csv` safe to upload by accident",
        )
        checks.equal(
            sorted(by_sku),
            sorted(sku for sku in SEAM_SKUS if sku != ARTICUNO_SKU),
            "and the SURVEY holds every LIVE row the export carried, including the ones the "
            "rule refused — the lens draws all of them or it is a gate wearing a filter's "
            "name. `live` is the one word doing work: a row TCGplayer holds no copies of is "
            "not a row this screen can act on, and it is dropped (see below)",
        )
        checks.equal(
            (by_sku[DUNSPARCE_REVERSE_SKU]["standing"], by_sku[DUNSPARCE_REVERSE_SKU]["skip"]),
            ("offered", None),
            "the proposed row is `offered` and carries no refusal code",
        )
        checks.equal(
            (by_sku[DUNSPARCE_SKU]["standing"], by_sku[DUNSPARCE_SKU]["skip"]),
            ("deferred", None),
            "A DEFERRED ROW CARRIES NO CODE EITHER, which is why `standing` exists. It "
            "QUALIFIED and fell below `--limit`, so a screen reading `skip` alone cannot tell "
            "it from an offered row — and only one of the two is in the worklist",
        )
        # INVERTED 2026-09-07. This asserted that the sold-out row was in the survey carrying
        # `SOLD_OUT`, which was right while every refusal was drawn — and `sold_out` is the one
        # refusal nothing can be done about, `UNPRICEABLE_CODES`' only member since D109. On
        # the owner's export it is 372 of 759 rows, so the lens drew nearly twice as many dead
        # rows as live ones. The principle it was protecting — a REFUSED row is still drawn —
        # is unchanged and asserted on a live refusal in `check_pricing_reach`.
        checks.ok(
            ARTICUNO_SKU not in by_sku,
            "AND A SOLD-OUT ROW IS NOT IN THE SURVEY AT ALL. There is no live listing for a "
            "price to edit, so it can never be answered and would only be something to "
            "scroll past",
        )
        # (THE REPORT STILL NAMES IT is asserted in `check_markdown`, which holds the command's
        # stdout; this block only has the files on disk.)
        checks.ok(
            all(row.get("row") for row in survey["skus"]),
            "EVERY SURVEY ROW CARRIES THE VERBATIM EXPORT ROW. It is what an upload's bytes "
            "are built from and what the five identity cells of a price history are read out "
            "of — a survey without it could be drawn and never acted on",
        )

        # ------------------------------------------- pricing a row the offer never held
        def apply_edits(target, edits, *, revision=None):
            from cli import __main__ as entry

            tcgcsv.write_csv(
                target / cmd_reprice.WORKLIST,
                (tcgcsv.SKU_COLUMN, tcgcsv.PRICE_COLUMN),
                [{tcgcsv.SKU_COLUMN: sku, tcgcsv.PRICE_COLUMN: price} for sku, price in edits],
            )
            argv = ["reprice", "apply", str(target / cmd_reprice.WORKLIST), "--write"]
            if revision is not None:
                argv += ["--corpus-revision", revision]
            with quiet() as said:
                code = entry.main(argv)
            return code, said.getvalue()

        # DUNSPARCE IS DEFERRED — in the survey, out of the offer — and priced here anyway.
        # Two columns, because that is exactly what the screen will send.
        code, said = apply_edits(directory, [(DUNSPARCE_SKU, "1.50")])
        checks.ok(
            code == 0 and f"[{reprice.NOT_IN_WORKLIST}]" not in said,
            "A ROW THE OFFER NEVER HELD IS PRICEABLE, because the survey holds its bytes. This "
            "is the refusal's own argument applied honestly: it protects against there being "
            "no row to build, and there is one",
        )
        # READ THROUGH A GUARD RATHER THAN OFF THE PATH, so that reverting the widening reports
        # this assertion by name instead of tracebacking three lines later on a missing file. A
        # harness that raises tells you something broke; one that fails tells you what.
        pushed = (
            list(tcgcsv.read_export(directory / cmd_reprice.IMPORT).rows)
            if (directory / cmd_reprice.IMPORT).is_file()
            else []
        )
        checks.equal(
            [row[tcgcsv.SKU_COLUMN] for row in pushed],
            [DUNSPARCE_SKU],
            "and the upload carries it",
        )
        checks.equal(
            sorted({row[tcgcsv.QUANTITY_COLUMN] for row in pushed}),
            ["0"],
            "carrying `Add to Quantity` 0, like every other file on this path",
        )
        original = tcgcsv.read_export(export).by_sku()
        try:
            tcgcsv.check_only_writable_changed(original[DUNSPARCE_SKU], pushed[0])
            clean = True
        except (tcgcsv.ReadOnlyColumn, IndexError):
            clean = False
        checks.ok(
            clean,
            "AND ITS BYTES CAME FROM THE SURVEY'S COPY OF THE EXPORT ROW, not from the two "
            "columns handed back — the same property the manifest gives an offered row",
        )
        checks.ok(
            "deleted from the worklist  1 SKU(s)" in said,
            "`dropped` COUNTS THE OFFER AND NOT THE SURVEY. One row was offered and not handed "
            "back; measured over the record this would have claimed three",
        )

        # ------------------------------------------------------ the rows that may never go
        code, said = apply_edits(directory, [(ARTICUNO_SKU, "9.00")])
        # THE REFUSAL MOVED AND THE PROPERTY DID NOT. This expected `[sold_out]` while the
        # survey still carried the row; it no longer does, so `read_back`'s bytes check fires
        # first and the complaint becomes `not_in_worklist`. That is the one `read_back`'s own
        # comment calls "the one that is true": there IS no row for this SKU here. The state is
        # unreachable from the screen — the row is not drawn — and stays reachable only by
        # hand-editing a worklist, which is exactly what this asserts still refuses.
        checks.ok(
            code == 0 and f"[{reprice.NOT_IN_WORKLIST}]" in said,
            f"a `{reprice.SOLD_OUT}` row is refused however good its price — TCGplayer "
            f"holds no copies, so there is no listing for a price to edit",
        )

        # ----------------------------------------------------------------- the ratchet
        answered = corpus.Corpus.read().answers.get(DUNSPARCE_SKU)
        checks.ok(
            answered is not None and bool(answered.at) and answered.channel == "price",
            "the applied price is stamped, which is what the ratchet reads next time",
        )

        # ------------------------------------------------------ the stale-write refusal
        code, said = apply_edits(
            directory, [(DUNSPARCE_REVERSE_SKU, "3.00")], revision="not-the-digest"
        )
        checks.ok(
            code == 1 and "REFUSED" in said,
            "A STALE CORPUS REVISION REFUSES THE WHOLE FILE. `PUT /pricing` has been guarded "
            "since D86 while this command was not, and now that the press lives on `#/pricing` "
            "a tab open during an apply is the ordinary case rather than a race",
        )
        checks.ok(
            DUNSPARCE_REVERSE_SKU not in corpus.Corpus.read().answers
            or corpus.Corpus.read().answers[DUNSPARCE_REVERSE_SKU].value != "3.00",
            "and it writes NOTHING — the refusal runs before a byte is built, because a file "
            "built against a corpus the operator cannot see moves money on nobody's decision",
        )
        code, said = apply_edits(
            directory, [(DUNSPARCE_REVERSE_SKU, "3.00")], revision=corpus.revision()
        )
        checks.ok(
            code == 0 and corpus.Corpus.read().answers[DUNSPARCE_REVERSE_SKU].value == "3.00",
            "while the current digest lands, which is what makes the guard a guard rather "
            "than a wall",
        )

        # ------------------------------------------------- a window that proposes nothing
        # THE MOST ORDINARY WAY TO ASK FOR THE WHOLE TABLE. On the owner's real store
        # `--days 10` selects zero rows because the oldest capture is nine days old, and this
        # used to return before writing anything — leaving the lens no stamp to open.
        #
        # AND IT LANDS IN ITS OWN DIRECTORY EVEN THOUGH IT RUNS IN THE SAME SECOND AS THE ONE
        # ABOVE, which is the collision `_stamp` now walks past. Before that, this call
        # replaced the first markdown's manifest with an empty offer and every assertion above
        # about `directory` was quietly about a different survey.
        command(checks, "reprice", "list", str(export), "--days", "9999", "--write")
        made = sorted((files.inventory_dir() / cmd_reprice.DIRNAME).iterdir())
        checks.equal(
            len(made),
            2,
            "TWO WRITES IN ONE SECOND ARE TWO MARKDOWNS. `_stamp` advances a second at a time "
            "until the name is free rather than growing a suffix — `[0-9]{8}-[0-9]{6}` is an "
            "ADDRESS, spelled in five route patterns, so a `-2` would make the second markdown "
            "unreachable instead of merely lost",
        )
        checks.equal(
            sorted(json.loads((made[0] / cmd_reprice.MANIFEST).read_text("utf-8"))["skus"]),
            [DUNSPARCE_REVERSE_SKU],
            "and the FIRST markdown's offer is untouched by the second — the collision used "
            "to overwrite it, so a worklist was judged against an offer that was not its own",
        )
        empty = made[-1]
        checks.ok(
            (empty / cmd_reprice.WORKLIST).is_file()
            and not list(tcgcsv.read_export(empty / cmd_reprice.WORKLIST).rows),
            "A SURVEY THAT PROPOSES NOTHING STILL WRITES, with a HEADER-ONLY worklist rather "
            "than no worklist — the directory's shape is invariant, and the lens is reached BY "
            "a stamp on a screen whose premise is that staleness is a filter",
        )
        checks.equal(
            len(json.loads((empty / cmd_reprice.SURVEY).read_text("utf-8"))["skus"]),
            len([sku for sku in SEAM_SKUS if sku != ARTICUNO_SKU]),
            "and the survey holds every LIVE row, which is the whole point of writing at all "
            "— the sold-out one is not among them, and a lens reached by a stamp draws what "
            "can still be priced rather than everything the export happened to carry",
        )

        # -------------------------------------- the screen's press, through the route (D103)
        #
        # THE ASSERTION THAT MAKES `edits` SAFE. `#/pricing` holds `{sku -> price}` and has no
        # CSV writer — `app/package.json` carries two runtime dependencies and PapaParse is
        # not one — so the pairs arrive as JSON and the ROUTE materialises them with the
        # repo's own writer. That is a second entry point upstream of the file, and the only
        # thing that makes it as safe as the tested one is that it produces the same bytes.
        edits = [{"sku": DUNSPARCE_SKU, "price": "1.25"}]
        answer = pipeline_routes.do_markdown_apply(directory.name, {"edits": edits, "write": True})
        checks.ok(answer["ok"] and answer["wrote"], "the screen's press writes an upload")
        by_edits = (directory / cmd_reprice.IMPORT).read_bytes()

        tcgcsv.write_csv(
            directory / cmd_reprice.WORKLIST,
            (tcgcsv.SKU_COLUMN, tcgcsv.PRICE_COLUMN),
            [{tcgcsv.SKU_COLUMN: DUNSPARCE_SKU, tcgcsv.PRICE_COLUMN: "1.25"}],
        )
        (directory / cmd_reprice.IMPORT).unlink()
        pipeline_routes.do_markdown_apply(directory.name, {"write": True})
        checks.equal(
            by_edits,
            (directory / cmd_reprice.IMPORT).read_bytes(),
            "AND IT IS BYTE-IDENTICAL TO THE FILE THE WORKLIST PATH PRODUCES. `edits` is a "
            "second door into the money path, and this is what says the two doors open on "
            "one room — every gate `check_markdown` proves over a spreadsheet runs over this",
        )
        checks.ok(
            (directory / "edited-screen.csv").is_file(),
            "and the press leaves its instruction sheet on disk beside the upload, so `what "
            "did I send` has an answer six months later",
        )

        # `wrote` IS ANSWERED BY THE FILE BEING THERE. `_apply` exits 0 with nothing written
        # when every row is refused, and this route used to report `wrote: true` over an
        # `import.csv` that does not exist — the screen would then offer a download of nothing.
        (directory / cmd_reprice.IMPORT).unlink()
        refused_all = pipeline_routes.do_markdown_apply(
            directory.name, {"edits": [{"sku": ARTICUNO_SKU, "price": "9.00"}], "write": True}
        )
        checks.ok(
            refused_all["ok"] and not refused_all["wrote"],
            "a press whose every row was refused reports `wrote: false` — answered by the "
            "file being there rather than by the flag that was asked for",
        )
        checks.ok(
            bool(refused_all.get("revision")),
            "and every press answers with the NEW corpus digest, so the screen adopts it and "
            "its next keystroke is not refused for a write it made itself",
        )

        for payload, code in (
            ({"edits": [], "write": False}, "edits_invalid"),
            ({"edits": [{"sku": DUNSPARCE_SKU}], "write": False}, "edits_invalid"),
            ({"edits": edits, "worklist": {"name": "x.csv", "content": "a,b\n1,2\n"}}, "worklist_and_edits"),
        ):
            try:
                pipeline_routes.do_markdown_apply(directory.name, payload)
                checks.ok(False, f"the route refuses `{code}`", "it answered instead")
            except pipeline_routes.PipelineRefusal as refusal:
                checks.equal(refusal.code, code, f"the route refuses `{code}` by name")

def check_markdown_push(checks: Checks) -> None:
    """The two routes that reach TCGplayer, at every gate that fires BEFORE the socket opens.

    NOTHING HERE TOUCHES THE NETWORK, AND THAT IS THE POINT OF WHAT IT COVERS. Every assertion
    is a refusal raised before `server/tcg_import.py` would open a connection — a missing file,
    a missing `confirm`, nothing staged, an already-published upload — so the gates that decide
    whether a request happens at all are proved without one happening.

    THE PAYLOAD GATES ARE WORTH MORE THAN THEY LOOK. `confirm` is what stands between a
    reloaded tab replaying a POST and a real push, and `published_at` is what stands between a
    double-press and a second move of rows TCGplayer no longer holds staged. Both are cheap to
    delete by accident and neither has any other reader.

    AND THE PUBLISH ROUTE MUST NOT READ AN UPLOAD ID OFF THE REQUEST, which is asserted by
    handing it one and watching it refuse anyway: `scope` is pinned to "this upload" in the
    transport, so the id IS the scope, and a client-supplied one would let a mistyped body
    publish an upload this markdown never made.
    """
    checks.note("")
    checks.note("MARKDOWN PUSH — the gates that fire before anything reaches TCGplayer")

    with isolated_home() as home:
        directory = home / "inventory" / "markdowns" / "20260906-120000"
        directory.mkdir(parents=True)

        for route, code, payload in (
            (pipeline_routes.do_markdown_push, "no_import_file", {"confirm": True}),
            (pipeline_routes.do_markdown_publish, "nothing_staged", {"confirm": True}),
            (pipeline_routes.do_markdown_rollback, "nothing_staged", {"confirm": True}),
            # AN ID ON THE REQUEST CHANGES NOTHING. Same refusal, because the route reads the
            # receipt on disk and never the body.
            (
                pipeline_routes.do_markdown_publish,
                "nothing_staged",
                {"confirm": True, "upload_id": "42", "stagedPricingUploadId": "42"},
            ),
        ):
            try:
                route(directory.name, payload)
                checks.ok(False, f"the route refuses `{code}`", "it answered instead")
            except pipeline_routes.PipelineRefusal as refusal:
                checks.equal(refusal.code, code, f"the route refuses `{code}` by name")

        # WITH A FILE PRESENT, `confirm` IS THE ONLY THING LEFT — so this is what says the
        # unconfirmed request stops here rather than at the socket.
        (directory / cmd_reprice.IMPORT).write_text("TCGplayer Id\n1\n", encoding="utf-8")
        try:
            pipeline_routes.do_markdown_push(directory.name, {})
            checks.ok(False, "an unconfirmed push refuses", "it answered instead")
        except pipeline_routes.PipelineRefusal as refusal:
            checks.equal(refusal.code, "confirm_required", "an unconfirmed push refuses by name")

        # A PUBLISHED UPLOAD IS LATCHED. The receipt is the record and the route reads it, so a
        # second press over the same upload is refused rather than sent.
        pipeline_routes._write_push(
            directory,
            {
                "upload_id": "abc",
                "rows": 1,
                "accepted": 1,
                "messages": [],
                "pushed_at": "2026-09-06T12:00:00+00:00",
                "published_at": "2026-09-06T12:05:00+00:00",
            },
        )
        try:
            pipeline_routes.do_markdown_publish(directory.name, {"confirm": True})
            checks.ok(False, "a second publish refuses", "it answered instead")
        except pipeline_routes.PipelineRefusal as refusal:
            checks.equal(refusal.code, "already_published", "a second publish refuses by name")

        # AND A ROLLBACK IS REFUSED ONCE IT IS PUBLISHED. TCGplayer no longer holds those rows
        # staged, so there is nothing to discard — and offering it would imply a live price can
        # be taken back, which D100 says it cannot.
        try:
            pipeline_routes.do_markdown_rollback(directory.name, {"confirm": True})
            checks.ok(False, "a rollback after publish refuses", "it answered instead")
        except pipeline_routes.PipelineRefusal as refusal:
            checks.equal(refusal.code, "already_published",
                         "a rollback after publish refuses by name")

        # THE RECEIPT REACHES THE SCREEN, which is the reload path: without it an operator who
        # pushed and then refreshed would have rows staged and no control able to publish them.
        summary = pipeline_routes._markdown_summary(directory.name)
        checks.equal(
            (summary.get("pushed") or {}).get("upload_id"),
            "abc",
            "and the markdown summary carries the push receipt, so a reload finds it",
        )

    # THE TRANSPORT'S OWN GATES, over rows rather than routes. `_check` runs before a
    # transaction is opened, so a bad file is a refusal with nothing sent rather than a
    # half-written staged upload.
    checks.note("")
    checks.note("MARKDOWN PUSH — what the transport refuses to send")
    good = {
        "Id": 0,
        "ProductConditionId": "123",
        "CategoryName": "Pokemon",
        "SetName": "S",
        "ProductName": "P",
        "ConditionName": "Near Mint",
        "AddToQuantity": "0",
        "MyPrice": "1.00",
        "ProOnlineStoreReserveQuantity": "",
        "ProOnlineStorePrice": "",
        "Number": "1/1",
    }
    for code, mutate in (
        ("tcg_import_empty", None),
        ("tcg_import_no_sku", {"ProductConditionId": ""}),
        ("tcg_import_bad_price", {"MyPrice": "nope"}),
        ("tcg_import_bad_price", {"MyPrice": "0"}),
        ("tcg_import_bad_price", {"MyPrice": "200001"}),
        ("tcg_import_bad_quantity", {"AddToQuantity": "x"}),
        # D100's invariant, asserted a fifth time and at the last possible moment: nothing on
        # this path may move a copy, so a row that would is refused at the wire rather than
        # relied upon to have been filtered upstream.
        ("tcg_import_moves_quantity", {"AddToQuantity": "1"}),
    ):
        rows = [] if mutate is None else [dict(good, **mutate)]
        try:
            tcg_import._check(rows)
            checks.ok(False, f"the transport refuses `{code}`", "it accepted instead")
        except tcg_import.FetchRefusal as refusal:
            checks.equal(refusal.code, code, f"the transport refuses `{code}` by name")

    tcg_import._check([good])
    checks.ok(True, "and a well-formed zero-quantity row passes every one of them")

    # THE WIRE FORMAT IS jQUERY'S DEEP FORM ENCODING AND NOT JSON, which is what their server
    # reads: `data[0][MyPrice]`. `urlencode` alone would stringify the whole list into one
    # value and the server would see no rows at all.
    body = tcg_import._form({"data": [good], "type": "Pricing"}).decode("utf-8")
    checks.ok(
        "data%5B0%5D%5BMyPrice%5D=1.00" in body and "type=Pricing" in body,
        "the row goes on the wire as `data[0][MyPrice]`, which is what their importer reads",
    )
    # LOWERCASE ON INITIALIZE, camelCase ON UPLOAD. Their bundle really does spell it both
    # ways, and matching by symmetry instead of by reading would break the upload silently.
    checks.equal(
        (tcg_import.INITIALIZE, tcg_import.UPLOAD, tcg_import.CHUNK_SIZE, tcg_import.SCOPE_THIS_UPLOAD),
        ("/admin/pricing/initializeexportcsv", "/admin/pricing/uploadexportcsv", 750, 3),
        "and the endpoints, the chunk size and the pinned scope are the ones read off their bundle",
    )

@contextmanager
def send_portal():
    """A loopback TCGplayer: the live export GET and the five pricing POSTs, and a record of
    every call. NOTHING HERE CAN REACH THE REAL PORTAL: `tcg_import._url` and
    `tcg_export.live_endpoint` both follow `PKMNSCAN_TCG_EXPORT_URL`, which is set to this
    socket, and `envfile` is made hermetic so a real `.env` cannot supply a real cookie.

    THE MODES, EACH A WAY THE REAL PORTAL CAN ANSWER THAT A SEND MUST SURVIVE:

      `fail`      endpoints (the last path segment) that answer 500 — an UNCLEAR answer: the
                  server may have done the work before it failed. `{"rollbackexportcsv"}` is
                  the rollback-refused mode.
      `refuse`    endpoints that answer 400 — a CLEAR refusal: the request was turned away.
      `slow`      endpoint -> seconds to sleep before answering (`"GET"` for the live read).
                  Past `tcg_export.TIMEOUT_S` this is the slow mode, and the work still lands.
      `turn_away` how many rows of each upload chunk `SuccessfulProductCount` leaves out —
                  the partial-accept mode.
      `published_then_5xx`  `movetolive` publishes, then answers 500 — the portal did the
                  work and said it failed.
      `hold`      endpoint -> a `threading.Event` the handler waits on before answering, so a
                  case can look at a press while it is still running.
      `gate`      a `threading.Barrier` the live read waits on, so two presses overlap.
      `catalog`   the CATALOGUE export a run's match fetches (a POST to the export URL), with
                  `filters` as the set list `getjsonfilters` answers. `signed_out` reaches it.

    `state["live"]` is the export body; `state["signed_out"]` makes the GET redirect to the
    login page. The server is THREADED, as the real one is: a rollback sent while a slow chunk
    is still sleeping must be answered, not queued behind it.
    """
    state = {
        "live": _live_export_bytes({DUNSPARCE_SKU: 0}),
        "signed_out": False,
        "fail": set(),
        "refuse": set(),
        "slow": {},
        "turn_away": 0,
        "published_then_5xx": False,
        "hold": {},
        "gate": None,
        "catalog": FIXTURE_EXPORT.read_bytes(),
        "filters": {
            "Sets": [
                {"Text": "All Set Names", "Value": "0"},
                {"Text": "SV09: Journey Together", "Value": "4242"},
            ],
            "Rarities": [{"Text": "All Rarities", "Value": "0"}],
            "Conditions": [{"Text": "All Conditions", "Value": "0"}],
            "Printings": [{"Text": "All Printings", "Value": "0"}],
        },
        "calls": [],
        "rows": [],
        "moved": [],
        "rolled": [],
        "uploads": 0,
    }

    class Portal(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # noqa: A003
            pass

        def _answer(self, status, body, kind="application/json"):
            try:
                self.send_response(status)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except OSError:
                # THE CLIENT GAVE UP (the slow mode's whole point). The work above stands.
                pass

        def _wait(self, name):
            held = state["hold"].get(name)
            if held is not None:
                held.wait(20)
            delay = state["slow"].get(name)
            if delay:
                time.sleep(delay)

        def do_GET(self):  # noqa: N802
            state["calls"].append(("GET", urllib.parse.urlparse(self.path).path))
            if "getjsonfilters" in self.path:
                self._answer(200, json.dumps(state["filters"]).encode("utf-8"))
                return
            gate = state["gate"]
            if gate is not None:
                with contextlib.suppress(threading.BrokenBarrierError):
                    gate.wait(3)
            self._wait("GET")
            if state["signed_out"]:
                self.send_response(302)
                self.send_header("Location", "https://store.tcgplayer.com/oauth/login")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self._answer(200, state["live"], "text/csv")

        def do_POST(self):  # noqa: N802
            path = urllib.parse.urlparse(self.path).path
            name = path.rsplit("/", 1)[-1]
            length = int(self.headers.get("Content-Length") or 0)
            form = urllib.parse.parse_qs(
                self.rfile.read(length).decode("utf-8"), keep_blank_values=True
            )
            state["calls"].append(("POST", name))
            if name == "downloadexportcsv":
                if state["signed_out"]:
                    self.send_response(302)
                    self.send_header("Location", "https://store.tcgplayer.com/oauth/login")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self._answer(200, state["catalog"], "text/csv")
                return
            if name in state["refuse"]:
                self._wait(name)
                self._answer(400, b"{}")
                return
            if name in state["fail"]:
                self._wait(name)
                self._answer(500, b"{}")
                return
            answer: dict = {}
            if name == "initializeexportcsv":
                state["uploads"] += 1
                answer = {"StagedPricingUploadId": f"u-{state['uploads']}"}
            elif name == "uploadexportcsv":
                rows: Dict[int, dict] = {}
                for key, values in form.items():
                    found = re.match(r"^data\[(\d+)\]\[(\w+)\]$", key)
                    if found:
                        rows.setdefault(int(found.group(1)), {})[found.group(2)] = values[0]
                kept = [rows[index] for index in sorted(rows)]
                kept = kept[: max(0, len(kept) - int(state["turn_away"]))]
                state["rows"] += kept
                answer = {"SuccessfulProductCount": len(kept), "Messages": []}
            elif name == "movetolive":
                state["moved"].append(form.get("stagedPricingUploadId", [""])[0])
                if state["published_then_5xx"]:
                    self._wait(name)
                    self._answer(500, b"{}")
                    return
                answer = {"Success": True}
            elif name == "rollbackexportcsv":
                state["rolled"].append(form.get("stagedPricingUploadId", [""])[0])
            self._wait(name)
            self._answer(200, json.dumps(answer).encode("utf-8"))

    keys = (
        "PKMNSCAN_TCG_EXPORT_URL",
        "TCGPLAYER_STORE_COOKIE",
        "PKMNSCAN_TCG_USER_AGENT",
        envfile.FROM_FILE_ENV,
    )
    previous = {name: os.environ.get(name) for name in keys}
    portal = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Portal)
    portal.daemon_threads = True
    thread = _spawn_server(portal)
    os.environ["PKMNSCAN_TCG_EXPORT_URL"] = (
        f"http://127.0.0.1:{portal.server_address[1]}/admin/pricing/downloadexportcsv"
    )
    os.environ["TCGPLAYER_STORE_COOKIE"] = "TCGAuthTicket_Production=t7-send-not-a-real-session"
    os.environ.pop("PKMNSCAN_TCG_USER_AGENT", None)
    env_before = (envfile.ENV_FILE, set(envfile._from_file), envfile._loaded)
    envfile.ENV_FILE = Path(tempfile.gettempdir()) / "t7-send-no-such.env"
    envfile._from_file.clear()
    os.environ.pop(envfile.FROM_FILE_ENV, None)
    envfile._loaded = False
    try:
        yield state
    finally:
        portal.shutdown()
        portal.server_close()
        thread.join(5)
        envfile.ENV_FILE, from_file, envfile._loaded = env_before
        envfile._from_file.clear()
        envfile._from_file.update(from_file)
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

def _refusal_text_route(fn) -> Optional[Tuple[str, str]]:
    """`(code, message)` off the `PipelineRefusal` `fn` raised, or None if it answered. For a case
    whose refusal must NAME a card, where the message is the contract."""
    try:
        fn()
    except pipeline_routes.PipelineRefusal as caught:
        return (caught.code, str(caught))
    return None

def _route_refusal(fn) -> Optional[str]:
    """The `PipelineRefusal` code `fn` raised, or None if it answered."""
    try:
        fn()
    except pipeline_routes.PipelineRefusal as caught:
        return caught.code
    return None

def check_send_guard(checks: Checks) -> None:
    """The double-send guard, at the command: TCGplayer never ends up holding more than is here.

    THE OWNER'S RULING (`D273`): a send "never doubles a quantity".
    THE DEFECT IS SHOWN FIRST, THEN THE GUARD. A store whose bookkeeping says nothing is out,
    while TCGplayer's own export says all three copies are live — the D100 §2 shape, a file
    uploaded by hand. `emit` alone writes all three again. `emit --live-guard` over the same
    store writes none, and names the card.
    """
    checks.note("")
    checks.note("SEND GUARD — a file never leaves TCGplayer holding more than is on hand")

    cards = [(3, i, "Articuno", "161", None) for i in (1, 2, 3)]
    cards.append((3, 4, "Dunsparce", "120", "normal"))

    def written(run_dir):
        rows = tcgcsv.read_export(run_dir.path(runs.IMPORT_MERGED)).rows
        return {row[tcgcsv.SKU_COLUMN]: row[tcgcsv.QUANTITY_COLUMN] for row in rows}

    live = Path(tempfile.mkdtemp()) / "live.csv"

    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        command(checks, "emit", str(run_dir.directory))
        checks.equal(
            written(run_dir).get(ARTICUNO_SKU),
            "3",
            "THE DEFECT: with no guard, a store that has lost track of three live copies "
            "writes all three again — a doubled quantity the moment the file is uploaded",
        )

    for held_live, goes in ((3, None), (2, "1")):
        live.write_bytes(_live_export_bytes({ARTICUNO_SKU: held_live, DUNSPARCE_SKU: 0}))
        with isolated_home():
            run_dir, _ = seam_run(checks, cards)
            said = command(checks, "emit", str(run_dir.directory), "--live-guard", str(live))
            checks.equal(
                written(run_dir).get(ARTICUNO_SKU),
                goes,
                f"WITH THE GUARD, TCGplayer holding {held_live} of 3 leaves room for "
                f"{goes or 'none'}: live plus added never passes what is on hand",
            )
            checks.equal(
                written(run_dir).get(DUNSPARCE_SKU),
                "1",
                "and a card TCGplayer does not hold goes out untouched",
            )
            report = send_routes._guard_line(said) or {}
            trimmed = {row["sku"]: row for row in report.get("trimmed", [])}
            checks.ok(
                ARTICUNO_SKU in trimmed
                and trimmed[ARTICUNO_SKU]["would"] == 3
                and trimmed[ARTICUNO_SKU]["live"] == held_live,
                f"the trim is NAMED in the command's JSON line, with the figures: {report}",
            )
            listing = Store().read().inventory.listings.get(ARTICUNO_SKU)
            checks.equal(
                0 if listing is None else listing.pushed,
                int(goes or 0),
                "and `pushed` follows the trimmed file, never the untrimmed one",
            )

    # A GUARD FILE THAT CANNOT BE READ REFUSES THE WRITE. It never fails open to no guard.
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        from cli import __main__ as entry

        with quiet() as said:
            code = entry.main(
                ["emit", str(run_dir.directory), "--live-guard", "/no/such/live.csv"]
            )
        checks.ok(
            code == 1 and not run_dir.path(runs.IMPORT_MERGED).exists(),
            f"an unreadable guard file writes nothing. exit {code}: {said.getvalue()[-200:]!r}",
        )

    # THE PURE RULE, ONCE, WITHOUT A STORE: a departed copy is not on hand, and a matched
    # position the store has never seen is.
    sold = master.Card(box=1, index=1)
    sold.sku, sold.state = "9", master.SOLD
    kept = master.Card(box=1, index=2)
    kept.sku = "9"
    cards_by_key = {"1/1": sold, "1/2": kept}
    checks.equal(
        sendguard.on_hand([kept], cards_by_key, ["1/1", "1/2", "1/3"]),
        2,
        "on hand is the store's unsold copies union this send's matched positions, less "
        "every copy that has left",
    )
    checks.equal(sendguard.room(live=5, held=3), 0, "room is never negative")

def check_send_press(checks: Checks) -> None:
    """The one press, every path, against the loopback portal (`send_portal`).

    NOTHING HERE REACHES TCGPLAYER. What is asserted is what the portal RECEIVED and what the
    store and the receipt say afterwards: the live read first, a refusal that sends nothing,
    the double-send trim end to end, a failed push and a failed publish that both put the
    copies back, the download door, take-back, the live check after the lag, and the
    mark-down's one press.
    """
    checks.note("")
    checks.note("SEND PRESS — read what is live, send, make live, check")

    cards = [(3, i, "Articuno", "161", None) for i in (1, 2, 3)]
    cards.append((3, 4, "Dunsparce", "120", "normal"))

    def pushed(sku):
        listing = Store().read().inventory.listings.get(sku)
        return 0 if listing is None else listing.pushed

    # ------------------------------------------------ the happy path, and the check after it
    with send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})

        checks.equal(
            _route_refusal(lambda: send_routes.do_send({"runs": [run_dir.name]})),
            "confirm_required",
            "an unconfirmed send refuses",
        )
        checks.equal(portal["calls"], [], "and it refuses before TCGplayer is asked anything")

        answer = send_routes.do_send({"runs": [run_dir.name], "confirm": True})
        sent = answer["send"]
        names = [call for call in portal["calls"]]
        checks.equal(
            names[0],
            ("GET", "/admin/pricing/DownloadMyExportCSV"),
            "THE LIVE READ COMES FIRST, before any write reaches TCGplayer",
        )
        checks.equal(
            [name for kind, name in names if kind == "POST"],
            ["initializeexportcsv", "uploadexportcsv", "finalizeexportcsv", "movetolive"],
            "ONE PRESS pushes and publishes: the four calls, in order, and no rollback",
        )
        checks.equal(
            {row["ProductConditionId"]: row["AddToQuantity"] for row in portal["rows"]},
            {ARTICUNO_SKU: "3", DUNSPARCE_SKU: "1"},
            "the portal received every unsent copy, as the listing file's own quantities",
        )
        checks.equal(portal["moved"], ["u-1"], "and the publish named the upload it pushed")
        checks.equal(sent["state"], "waiting", "the receipt waits for the check after the lag")
        checks.ok(bool(sent["check_after"]), "and says when that check is due")
        checks.ok(
            ARTICUNO_SKU in cmd_reprice.published_recently(),
            "THE LAG GUARD SEES A LISTING PUBLISH, not only a mark-down's",
        )

        # NOT DUE YET: the check runs only when a receipt's lag has passed.
        early = send_routes.do_live_check({})
        checks.equal(early["ran"], False, "a check inside the lag does not run")

        # THE LAG PASSES (the receipt's clock moved back), and TCGplayer shows one short.
        directory = send_routes.sends_dir() / sent["stamp"]
        record = send_routes._read(directory)
        record["check_after"] = "2000-01-01T00:00:00+00:00"
        send_routes._write(directory, record)
        checks.ok(send_routes.do_sends()["due"], "once the lag has passed, the check is due")
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 3, DUNSPARCE_SKU: 0})
        checked = send_routes.do_live_check({})
        summary = checked["checked"][0]
        checks.equal(
            (summary["state"], summary["check"]["found"], summary["check"]["expected"]),
            ("short", 3, 4),
            "the check finds three of four live and names the short one",
        )
        checks.equal(
            [row["sku"] for row in summary["check"]["missing"]],
            [DUNSPARCE_SKU],
            "by SKU, so the screen can name the card",
        )
        checks.equal(
            send_routes.do_live_check({})["ran"], False, "and a checked send is not checked again"
        )

        # A SECOND SEND OF THE SAME COPIES ADDS NOTHING: they are pushed, and TCGplayer holds
        # three. The send refuses rather than uploading an empty file.
        portal["calls"].clear()
        checks.equal(
            _route_refusal(lambda: send_routes.do_send({"runs": [run_dir.name], "confirm": True})),
            "nothing_to_send",
            "a second press over copies already sent refuses and sends nothing",
        )
        checks.equal(
            [name for kind, name in portal["calls"] if kind == "POST"],
            [],
            "and TCGplayer receives no write",
        )

    # ----------------------------------------- the double-send trim, end to end through the press
    with send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        # TCGplayer holds two Articuno the store never recorded (a hand upload).
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 2, DUNSPARCE_SKU: 0})
        send_routes.do_send({"runs": [run_dir.name], "confirm": True})
        checks.equal(
            {row["ProductConditionId"]: row["AddToQuantity"] for row in portal["rows"]},
            {ARTICUNO_SKU: "1", DUNSPARCE_SKU: "1"},
            "THE PRESS NEVER DOUBLES: two live of three on hand sends one Articuno, not three",
        )

    # --------------------------------------------------------- the live read cannot run
    with send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["signed_out"] = True
        checks.equal(
            _route_refusal(lambda: send_routes.do_send({"runs": [run_dir.name], "confirm": True})),
            "live_check_failed",
            "SIGNED OUT, THE SEND REFUSES by name, and the screen offers Try again",
        )
        checks.equal(
            [name for kind, name in portal["calls"] if kind == "POST"],
            [],
            "and nothing was pushed or published",
        )
        checks.equal(pushed(ARTICUNO_SKU), 0, "and no copy was marked sent")
        checks.ok(
            not send_routes.sends_dir().exists() or not any(send_routes.sends_dir().iterdir()),
            "and no receipt was written",
        )

    # ------------------------------------------------ a failed push, then a failed publish
    # A 500 ON THE OPENING CALL (nothing staged: no upload id, no row), then a CLEAR 400 on
    # the publish, which is rolled back. An UNCLEAR publish is `check_send_hazards`' case: its
    # copies are held, never put back (the 2026-09-24 review, S1-b).
    for failing, rolled in (("initializeexportcsv", []), ("movetolive", ["u-1"])):
        with send_portal() as portal, isolated_home():
            run_dir, _ = seam_run(checks, cards)
            portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
            portal["fail" if failing == "initializeexportcsv" else "refuse"] = {failing}
            code = _route_refusal(
                lambda run_dir=run_dir: send_routes.do_send({"runs": [run_dir.name], "confirm": True})
            )
            checks.equal(code, "send_rolled_back" if rolled else "tcg_write_refused", f"a failing {failing} refuses the press; after a rollback it is `send_rolled_back`, never a retry (round 6, S4)")
            checks.equal(
                (pushed(ARTICUNO_SKU), pushed(DUNSPARCE_SKU)),
                (0, 0),
                f"and after a failing {failing} THE COPIES ARE BACK ON THE LIST: a copy is "
                f"never marked sent when it was not",
            )
            checks.equal(portal["rolled"], rolled, f"and the upload is rolled back ({failing})")
            receipt = send_routes.do_sends()["sends"][0]
            checks.equal(receipt["state"], "failed", "and the receipt says the press failed")

    # --------------------------------------------------- the download door, and take-back
    with send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
        answer = send_routes.do_send({"runs": [run_dir.name], "download": True})
        checks.equal(
            [name for kind, name in portal["calls"] if kind == "POST"],
            [],
            "THE DOWNLOAD DOOR sends nothing to TCGplayer — but it still read what is live",
        )
        checks.equal(answer["send"]["state"], "written", "its copies are written, not confirmed")
        status = send_routes.do_sends()
        checks.equal(status["unconfirmed"]["copies"], 4, "and Pricing can name all four copies")
        checks.equal(pushed(ARTICUNO_SKU), 3, "the file's copies are held out of the next file")
        stamp = answer["send"]["stamp"]
        checks.ok(
            ARTICUNO_SKU.encode() in send_routes.do_send_file(stamp, answer["send"]["files"][0]),
            "the file the download door wrote is served by name",
        )
        checks.equal(
            _route_refusal(lambda: send_routes.do_send_file(stamp, "../send.json")),
            "no_such_file",
            "and a name the receipt does not list is refused, never joined onto a path",
        )
        # THE OWNER'S RULING, 2026-09-24: Take them back only after a check past the wait.
        checks.equal(
            _route_refusal(
                lambda: send_routes.do_take_back(answer["send"]["stamp"], {"confirm": True})
            ),
            "take_back_not_yet",
            "TAKE THEM BACK WAITS for a live check past the wait: the file may be uploading now",
        )
        checks.ok(
            bool(send_routes.do_sends()["sends"][0]["take_back_after"]),
            "and the receipt says when it will be safe",
        )
        directory = send_routes.sends_dir() / stamp
        record = send_routes._read(directory)
        record["check_after"] = "2000-01-01T00:00:00+00:00"
        send_routes._write(directory, record)
        send_routes.do_live_check({})
        checks.equal(
            send_routes.do_sends()["sends"][0]["takeable"],
            0,
            "past the wait, ONE check that finds none of the file's copies offers none back: the "
            "owner uploads a download by hand, at a time Banchi does not know",
        )
        # THE SECOND CHECK, ONE WAIT AFTER THE FIRST (the orchestrator's call, round 3).
        record = send_routes._read(directory)
        record["checked_at"] = record["first_checked_at"] = "2000-01-01T00:00:00+00:00"
        send_routes._write(directory, record)
        send_routes.do_live_check({})
        checks.equal(
            send_routes.do_sends()["sends"][0]["takeable"],
            4,
            "and a second check one wait later that still finds none offers all four back",
        )
        taken = send_routes.do_take_back(answer["send"]["stamp"], {"confirm": True})
        checks.equal(taken["send"]["state"], "taken_back", "Take them back puts them back")
        checks.equal(pushed(ARTICUNO_SKU), 0, "and the next send offers them again")
        checks.equal(
            _route_refusal(
                lambda: send_routes.do_take_back(answer["send"]["stamp"], {"confirm": True})
            ),
            "not_takeable",
            "and a second take-back refuses: there is nothing left to take",
        )

    # ------------------------------------------------ the same bytes are never pushed twice
    with isolated_home():
        directory = send_routes.sends_dir() / "20260923-120000"
        send_routes._write(
            directory,
            {"kind": "send", "digest": "abc", "pushed": {"upload_id": "u"}, "taken_back_at": None},
        )
        checks.equal(
            send_routes._already_pushed("abc"),
            "20260923-120000",
            "a file whose bytes already went to TCGplayer is found by its digest",
        )

    # ------------------------------------------------------------ the mark-down's one press
    for failing in (None, "movetolive"):
        with send_portal() as portal, isolated_home() as home:
            directory = _markdown_dir(home, "20260923-130000")
            portal["live"] = _live_export_bytes({ARTICUNO_SKU: 1})
            if failing:
                # A CLEAR REFUSAL (400): rolled back, nothing left. The unclear 500 is
                # `check_send_hazards`' case, where the receipt stays and the SKUs are held.
                portal["refuse"] = {failing}
                checks.equal(
                    _route_refusal(
                        lambda directory=directory: send_routes.do_markdown_send(directory.name, {"confirm": True})
                    ),
                    "send_rolled_back",
                    "a mark-down whose publish fails refuses, and after its rollback it says so (round 6, S4)",
                )
                checks.equal(portal["rolled"], ["u-1"], "and its upload is rolled back")
                checks.ok(
                    pipeline_routes._read_push(directory) is None,
                    "and no receipt is left offering to publish rows TCGplayer was told to forget",
                )
                continue
            send_routes.do_markdown_send(directory.name, {"confirm": True})
            checks.equal(
                [call for call in portal["calls"]][0][0],
                "GET",
                "THE MARK-DOWN'S PRESS READS WHAT IS LIVE FIRST, like the listing send",
            )
            checks.equal(
                [name for kind, name in portal["calls"] if kind == "POST"],
                ["initializeexportcsv", "uploadexportcsv", "finalizeexportcsv", "movetolive"],
                "ONE PRESS pushes and publishes a mark-down",
            )
            checks.equal(
                [row["AddToQuantity"] for row in portal["rows"]],
                ["0"],
                "and the price file still moves no copy (D100's rule, untouched)",
            )
            checks.ok(
                bool((pipeline_routes._read_push(directory) or {}).get("published_at")),
                "and its receipt says it went live",
            )

    # ------------------------------------------------ the transport's listing door
    good = {
        "Id": 0, "ProductConditionId": "123", "CategoryName": "Pokemon", "SetName": "S",
        "ProductName": "P", "ConditionName": "Near Mint", "AddToQuantity": "3",
        "MyPrice": "1.00", "ProOnlineStoreReserveQuantity": "", "ProOnlineStorePrice": "",
        "Number": "1/1",
    }
    tcg_import._check([good], listing=True)
    checks.ok(True, "a listing row may add copies")
    checks.equal(
        _refusal_code_transport([dict(good, AddToQuantity="-1")], listing=True),
        "tcg_import_moves_quantity",
        "but never a negative quantity",
    )
    checks.equal(
        _refusal_code_transport([good], listing=False),
        "tcg_import_moves_quantity",
        "and a price file still refuses any quantity at all (D100)",
    )

def _press_thread(fn, answers, index):
    """Run one press on its own thread and keep what it answered, or the code it refused."""

    def go():
        try:
            answers[index] = ("sent", fn())
        except pipeline_routes.PipelineRefusal as caught:
            answers[index] = ("refused", caught.code)
        except Exception as caught:  # noqa: BLE001 — the case reports it, never swallows it
            answers[index] = ("raised", f"{type(caught).__name__}: {caught}")

    thread = threading.Thread(target=go, daemon=True)
    thread.start()
    return thread

@contextmanager
def _short_timeout(seconds: float):
    """The transport's timeout, lowered for one case so the slow mode is past it quickly."""
    before = tcg_export.TIMEOUT_S
    tcg_export.TIMEOUT_S = seconds
    try:
        yield
    finally:
        tcg_export.TIMEOUT_S = before

def _age_receipt(stamp: str) -> None:
    """Move a receipt's wait into the past: the lag has passed for it."""
    directory = send_routes.sends_dir() / stamp
    record = send_routes._read(directory)
    record["check_after"] = "2000-01-01T00:00:00+00:00"
    send_routes._write(directory, record)

def _posts(portal) -> List[str]:
    return [name for kind, name in portal["calls"] if kind == "POST"]

@contextmanager
def _case(checks: Checks, label: str):
    """One case of many: a case that raises is a FAIL naming it, and the next case still runs."""
    try:
        yield
    except Exception:  # noqa: BLE001 — reported, never swallowed
        import traceback

        checks.ok(False, f"{label}: the case raised", traceback.format_exc()[-1500:])

def check_send_hazards(checks: Checks) -> None:
    """The adversarial review's failures, each against the stand-in portal's own mode.

    EVERY CASE HERE WENT RED ON THE BUILD BEFORE IT. Two presses at once, a publish TCGplayer
    answered 500 after doing it, a rollback it refused, a chunk that never answered, a partial
    accept, one live rise read as two confirmations, a same-bytes rule that never forgot, an
    export with no quantity column. What is asserted is what the portal RECEIVED and what the
    store and the receipt say afterwards — never a message's wording.
    """
    checks.note("")
    checks.note("SEND HAZARDS — two presses, unclear answers, slow answers, partial answers")

    cards = [(3, i, "Articuno", "161", None) for i in (1, 2, 3)]
    cards.append((3, 4, "Dunsparce", "120", "normal"))
    empty = {ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0}

    def pushed(sku):
        listing = Store().read().inventory.listings.get(sku)
        return 0 if listing is None else listing.pushed

    def newest():
        return send_routes.do_sends()["sends"][0]

    # ------------------------------------------------------- S1-a: two presses at once
    with _case(checks, "S1-a: two presses at once"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)
        portal["gate"] = threading.Barrier(2)
        answers: Dict[int, tuple] = {}
        threads = [
            _press_thread(
                lambda: send_routes.do_send({"runs": [run_dir.name], "confirm": True}),
                answers,
                index,
            )
            for index in (0, 1)
        ]
        for thread in threads:
            thread.join(60)
        kinds = sorted(kind for kind, _ in answers.values())
        checks.equal(
            kinds,
            ["refused", "sent"],
            f"TWO PRESSES AT ONCE: one sends and the other is refused, never both: {answers}",
        )
        checks.equal(
            [code for kind, code in answers.values() if kind == "refused"],
            ["send_in_progress"],
            "and the refusal names the press that is already sending",
        )
        checks.equal(
            _posts(portal).count("initializeexportcsv"),
            1,
            "ONE upload reached TCGplayer, not two",
        )
        checks.equal(
            {row["ProductConditionId"]: row["AddToQuantity"] for row in portal["rows"]},
            {ARTICUNO_SKU: "3", DUNSPARCE_SKU: "1"},
            "and it carried each copy once",
        )
        checks.equal(pushed(ARTICUNO_SKU), 3, "and the store counts three Articuno sent, not six")

    # --------------------------------- S1-a: the store claim holds across processes too
    with _case(checks, "S1-a: the store claim holds across processes too"), \
            send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)
        with Store().write() as writable:
            writable.send_claims.claim(
                "20260924-120000-aaaaaa", "listing", {ARTICUNO_SKU: 3}, pid=os.getpid()
            )
        checks.equal(
            _route_refusal(lambda: send_routes.do_send({"runs": [run_dir.name], "confirm": True})),
            "send_in_progress",
            "A LIVE STORE CLAIM ON A CARD refuses a press over it, whoever wrote the claim",
        )
        checks.equal(
            [name for name in _posts(portal)],
            [],
            "and nothing reaches TCGplayer's write side",
        )
        checks.equal(pushed(ARTICUNO_SKU), 0, "and no copy is counted sent")

    # ------------------------------------ S1-a: a stamp is unique within one second
    with _case(checks, "S1-a: a stamp is unique within one second"), isolated_home():
        first, second = send_routes._new_stamp(), send_routes._new_stamp()
        checks.ok(
            first != second
            and (send_routes.sends_dir() / first).is_dir()
            and (send_routes.sends_dir() / second).is_dir(),
            f"two presses in one second get two directories of their own: {first}, {second}",
        )

    # ---------------- S1-a: a dropped connection sees the press still running, not a retry
    with _case(checks, "S1-a: a dropped connection sees the press still running, not a retry"), \
            send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)
        release = threading.Event()
        portal["hold"] = {"movetolive": release}
        answers = {}
        thread = _press_thread(
            lambda: send_routes.do_send({"runs": [run_dir.name], "confirm": True}), answers, 0
        )
        deadline = time.monotonic() + 20
        while "movetolive" not in _posts(portal) and time.monotonic() < deadline:
            time.sleep(0.05)
        running = newest()
        checks.equal(
            running["state"],
            "sending",
            "WHILE A PRESS RUNS, its receipt says so: a screen whose request dropped reads this",
        )
        gets = len([call for call in portal["calls"] if call[0] == "GET"])
        checks.equal(
            _route_refusal(lambda: send_routes.do_send({"runs": [run_dir.name], "confirm": True})),
            "send_in_progress",
            "and a second press is refused while the first still runs",
        )
        checks.equal(
            len([call for call in portal["calls"] if call[0] == "GET"]),
            gets,
            "before it asks TCGplayer anything",
        )
        release.set()
        thread.join(30)
        checks.equal(answers.get(0, ("", {}))[0], "sent", "and the first press still lands")
        checks.equal(newest()["state"], "waiting", "and its receipt moves on to the wait")

    # --------------------------------------------- S1-a: a holder that died is unknown
    with _case(checks, "S1-a: a holder that died is unknown"), isolated_home():
        gone = subprocess.Popen(["true"])
        gone.wait()
        stamp = "20260924-120000-bbbbbb"
        send_routes._write(
            send_routes.sends_dir() / stamp,
            {
                "stamp": stamp, "kind": "send", "at": "2026-09-24T12:00:00+00:00",
                "phase": "publishing", "holder": {"pid": gone.pid, "proc_start": "gone"},
                "copies": {ARTICUNO_SKU: 3}, "copies_total": 3,
                "pushed": {"upload_id": "u-9", "rows": 1, "accepted": 1},
                "publish_started_at": "2026-09-24T12:00:05+00:00",
            },
        )
        checks.equal(
            newest()["state"],
            "unknown",
            "A PRESS WHOSE SERVER DIED MID-PUBLISH is unknown, never failed and never live",
        )

    # --------------------- S1-b: TCGplayer published, then answered 500 (unclear publish)
    with _case(checks, "S1-b: TCGplayer published, then answered 500 (unclear publish)"), \
            send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)
        portal["published_then_5xx"] = True
        checks.equal(
            _route_refusal(lambda: send_routes.do_send({"runs": [run_dir.name], "confirm": True})),
            "send_unknown",
            "AN UNCLEAR PUBLISH is its own answer: TCGplayer did not say whether they went live",
        )
        checks.equal(
            (pushed(ARTICUNO_SKU), pushed(DUNSPARCE_SKU)),
            (3, 1),
            "and THE COPIES ARE NOT TAKEN BACK: they may be live, and taking them back would "
            "send them twice",
        )
        receipt = newest()
        checks.ok(
            receipt["state"] == "unknown" and receipt["held"],
            f"the receipt says unknown and holds its cards: {receipt['state']}, {receipt['held']}",
        )
        checks.ok(
            bool(receipt["take_back_after"]),
            "and says when taking them back will be safe",
        )
        # A NEW COPY OF A HELD CARD IS NOT SENT WHILE THE OUTCOME IS UNKNOWN.
        second, _ = seam_run(checks, [(4, 1, "Articuno", "161", None)])
        portal["calls"].clear()
        checks.equal(
            _route_refusal(lambda: send_routes.do_send({"runs": [second.name], "confirm": True})),
            "send_held",
            "A HELD CARD STAYS OUT OF EVERY SEND until a check past the wait resolves it",
        )
        checks.equal(_posts(portal), [], "and nothing is written to TCGplayer")
        checks.equal(
            _route_refusal(lambda: send_routes.do_take_back(receipt["stamp"], {"confirm": True})),
            "take_back_not_yet",
            "TAKE THEM BACK IS REFUSED before a check has run past the wait",
        )
        # THE WAIT PASSES AND TCGPLAYER SHOWS THEM: the unknown send did go live.
        _age_receipt(receipt["stamp"])
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 3, DUNSPARCE_SKU: 1})
        send_routes.do_live_check({})
        resolved = [s for s in send_routes.do_sends()["sends"] if s["stamp"] == receipt["stamp"]][0]
        checks.ok(
            resolved["state"] == "checked" and not resolved["held"],
            f"a check past the wait resolves it: found live, the hold released: {resolved['state']}",
        )
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 3, DUNSPARCE_SKU: 1})
        portal["published_then_5xx"] = False
        send_routes.do_send({"runs": [second.name], "confirm": True})
        checks.equal(
            portal["rows"][-1]["AddToQuantity"] if portal["rows"] else None,
            "1",
            "and the held card's new copy goes on the next press",
        )

    # --------------- S1-b / S1-c: a clear publish refusal whose rollback is ALSO refused
    with _case(checks, "S1-b / S1-c: a clear publish refusal whose rollback is ALSO refused"), \
            send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)
        portal["refuse"] = {"movetolive"}
        portal["fail"] = {"rollbackexportcsv"}
        checks.equal(
            _route_refusal(lambda: send_routes.do_send({"runs": [run_dir.name], "confirm": True})),
            "send_unknown",
            "A REFUSED ROLLBACK leaves the upload waiting at TCGplayer: the answer is unknown",
        )
        checks.equal(pushed(ARTICUNO_SKU), 3, "and the copies are not taken back")
        receipt = newest()
        checks.equal(
            (receipt["unknown"] or {}).get("upload_id"),
            "u-1",
            "the receipt names the upload that waits at TCGplayer",
        )
        _age_receipt(receipt["stamp"])
        portal["live"] = _live_export_bytes(empty)
        send_routes.do_live_check({})
        after = [s for s in send_routes.do_sends()["sends"] if s["stamp"] == receipt["stamp"]][0]
        checks.ok(
            after["state"] == "short" and after["takeable"] == 4,
            f"PAST THE WAIT, a check that finds none of them offers all four back: {after}",
        )
        taken = send_routes.do_take_back(receipt["stamp"], {"confirm": True})
        checks.equal(taken["moved"], 4, "and Take them back returns them")
        checks.equal(pushed(ARTICUNO_SKU), 0, "so the next send offers them again")

    # ---------------------- a push chunk refused whose rollback is refused: unknown too
    with _case(checks, "a push chunk refused whose rollback is refused: unknown too"), \
            send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)
        portal["fail"] = {"uploadexportcsv", "rollbackexportcsv"}
        checks.equal(
            _route_refusal(lambda: send_routes.do_send({"runs": [run_dir.name], "confirm": True})),
            "send_unknown",
            "A FAILED CHUNK WHOSE ROLLBACK FAILED is unknown: rows may wait at TCGplayer",
        )
        checks.equal(pushed(ARTICUNO_SKU), 3, "and nothing is taken back on a guess")
        checks.equal(_posts(portal).count("movetolive"), 0, "and nothing is published")

    # ----------------------------------------------------------- S2: the slow modes
    with _case(checks, "S2: the slow modes"), \
            send_portal() as portal, isolated_home(), _short_timeout(0.4):
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)
        portal["slow"] = {"GET": 1.2}
        checks.equal(
            _route_refusal(lambda: send_routes.do_send({"runs": [run_dir.name], "confirm": True})),
            "live_check_failed",
            "A LIVE READ THAT NEVER ANSWERS is the named refusal, not a crash",
        )
        checks.equal(_posts(portal), [], "and nothing is written to TCGplayer")
        checks.equal(pushed(ARTICUNO_SKU), 0, "and nothing is counted sent")
        try:
            tcg_export._open(tcg_export.live_endpoint(), cookie="a=b")
            code = None
        except tcg_export.FetchRefusal as refusal:
            code = refusal.code
        except Exception as caught:  # noqa: BLE001
            code = type(caught).__name__
        checks.equal(code, "tcg_unreachable", "every timeout on the transport is `tcg_unreachable`")

        with send_portal() as portal, isolated_home(), _short_timeout(0.4):
            run_dir, _ = seam_run(checks, cards)
            portal["live"] = _live_export_bytes(empty)
            portal["slow"] = {"uploadexportcsv": 1.2}
            code = _route_refusal(
                lambda: send_routes.do_send({"runs": [run_dir.name], "confirm": True})
            )
            receipt = newest() if send_routes.do_sends()["sends"] else {}
            checks.ok(
                code == "send_rolled_back" and receipt.get("state") == "failed",
                f"A SLOW CHUNK after the copies were counted leaves a receipt: {code}, "
                f"{receipt.get('state')}",
            )
            checks.equal(portal["rolled"], ["u-1"], "and the upload is rolled back")
            checks.equal(pushed(ARTICUNO_SKU), 0, "and, the rollback confirmed, the copies are back")

        with send_portal() as portal, isolated_home(), _short_timeout(0.4):
            run_dir, _ = seam_run(checks, cards)
            portal["live"] = _live_export_bytes(empty)
            portal["slow"] = {"movetolive": 1.2}
            checks.equal(
                _route_refusal(lambda: send_routes.do_send({"runs": [run_dir.name], "confirm": True})),
                "send_unknown",
                "A SLOW PUBLISH is unknown: TCGplayer may have done it",
            )
            checks.equal(pushed(ARTICUNO_SKU), 3, "and the copies are held, not taken back")

    # ------------------------------------------------------- S2: the partial accept
    with _case(checks, "S2: the partial accept"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)
        portal["turn_away"] = 1
        answer = send_routes.do_send({"runs": [run_dir.name], "confirm": True})["send"]
        checks.ok(
            answer["accepted"] == 1 and answer["rows"] == 2 and answer["turned_away"] == 1,
            f"TCGPLAYER TOOK 1 OF 2 ROWS, and the receipt says so: {answer['accepted']} of "
            f"{answer['rows']}, {answer['turned_away']} turned away",
        )
        _age_receipt(answer["stamp"])
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 3, DUNSPARCE_SKU: 0})
        send_routes.do_live_check({})
        after = newest()
        checks.equal(
            ([row["sku"] for row in (after["check"] or {}).get("missing", [])], after["takeable"]),
            ([DUNSPARCE_SKU], 1),
            "the check names the copy turned away and offers exactly it back",
        )
        send_routes.do_take_back(answer["stamp"], {"confirm": True})
        checks.equal(
            (pushed(ARTICUNO_SKU), pushed(DUNSPARCE_SKU)),
            (3, 0),
            "and taking it back returns the turned-away copy and nothing that went live",
        )

    # ---------------------------------------------------- S3: the same bytes, windowed
    with _case(checks, "S3: the same bytes, windowed"), isolated_home():
        now = send_routes._now()
        # ROUND-1 STAMPS, WITHOUT THE RANDOM TAIL: the old shape still reads, and it is the
        # shape the round-1 build could see, so this case goes red on that build for the
        # right reason (it refused the 20-minute-old bytes) rather than by not seeing them.
        for stamp, age in (("20260924-110000", 20 * 60), ("20260924-115900", 60)):
            send_routes._write(
                send_routes.sends_dir() / stamp,
                {
                    "kind": "send", "digest": f"d{age}", "taken_back_at": None,
                    "pushed": {"upload_id": "u", "pushed_at": send_routes._iso(now - timedelta(seconds=age))},
                },
            )
        checks.equal(
            send_routes._already_pushed(f"d{20 * 60}"),
            None,
            "THE SAME BYTES PAST THE UPLOAD WINDOW do not refuse: the live read sees them now",
        )
        checks.equal(
            send_routes._already_pushed("d60"),
            "20260924-115900",
            "and the same bytes inside the window still do",
        )

    # --------------------------------------- S3: an export with no quantity column refuses
    with _case(checks, "S3: an export with no quantity column refuses"):
        for missing in (tcgcsv.SKU_COLUMN, tcgcsv.LIVE_QUANTITY_COLUMN):
            present = {tcgcsv.SKU_COLUMN: ARTICUNO_SKU, tcgcsv.LIVE_QUANTITY_COLUMN: "2"}
            present.pop(missing)
            try:
                sendguard.live_by_sku([present])
                refused = False
            except ValueError:
                refused = True
            checks.ok(refused, f"AN EXPORT WITH NO `{missing}` COLUMN is refused, never read as zero")

    # -------------------------------------- S3: one live rise confirms one receipt only
    with _case(checks, "S3: one live rise confirms one receipt only"), \
            send_portal() as portal, isolated_home():
        base = {
            "kind": "send", "copies": {ARTICUNO_SKU: 3}, "copies_total": 3,
            "names": {ARTICUNO_SKU: "Articuno"}, "live_before": {ARTICUNO_SKU: 0},
            "sold_before": {ARTICUNO_SKU: 0}, "pushed": {"upload_id": "u", "rows": 1, "accepted": 1},
            "published_at": "2026-09-24T10:00:00+00:00", "check_after": "2000-01-01T00:00:00+00:00",
            "phase": "done",
        }
        for stamp in ("20260924-100000-eeeeee", "20260924-100500-ffffff"):
            send_routes._write(send_routes.sends_dir() / stamp, dict(base, stamp=stamp))
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 3})
        send_routes.do_live_check({})
        states = {s["stamp"]: (s["state"], (s["check"] or {}).get("found")) for s in send_routes.do_sends()["sends"]}
        checks.equal(
            states,
            {"20260924-100000-eeeeee": ("checked", 3), "20260924-100500-ffffff": ("short", 0)},
            "ONE RISE OF THREE confirms the older send's three, and never both sends",
        )

    # ----------------------------------------- S3: the first check fires past the lag
    with _case(checks, "S3: the first check fires past the lag"), \
            send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)
        sent = send_routes.do_send({"runs": [run_dir.name], "confirm": True})["send"]
        gap = send_routes._parse(sent["check_after"]) - send_routes._parse(sent["published_at"])
        checks.ok(
            gap.total_seconds() > cmd_reprice.PUBLISH_LAG_S,
            f"THE FIRST CHECK IS DUE PAST THE LAG, not at it: {gap.total_seconds()}s after the publish",
        )

    # ------------------------------------------- the mark-down: two presses at once
    with _case(checks, "the mark-down: two presses at once"):
        def markdown(home):
            return _markdown_dir(home, "20260924-130000")

        with send_portal() as portal, isolated_home() as home:
            directory = markdown(home)
            portal["live"] = _live_export_bytes({ARTICUNO_SKU: 1})
            portal["gate"] = threading.Barrier(2)
            answers = {}
            threads = [
                _press_thread(
                    lambda: send_routes.do_markdown_send(directory.name, {"confirm": True}),
                    answers,
                    index,
                )
                for index in (0, 1)
            ]
            for thread in threads:
                thread.join(60)
            checks.equal(
                sorted(
                    kind if kind == "sent" else f"{kind} {answer}"
                    for kind, answer in answers.values()
                ),
                ["refused send_in_progress", "sent"],
                f"TWO MARK-DOWN PRESSES AT ONCE: one sends, the other is refused by name: {answers}",
            )
            checks.equal(
                (_posts(portal).count("initializeexportcsv"), _posts(portal).count("movetolive")),
                (1, 1),
                "and the price file is pushed and published once",
            )

        with send_portal() as portal, isolated_home() as home:
            directory = markdown(home)
            portal["live"] = _live_export_bytes({ARTICUNO_SKU: 1})
            portal["published_then_5xx"] = True
            checks.equal(
                _route_refusal(lambda: send_routes.do_markdown_send(directory.name, {"confirm": True})),
                "send_unknown",
                "A MARK-DOWN WHOSE PUBLISH IS UNCLEAR is unknown, not failed",
            )
            record = pipeline_routes._read_push(directory) or {}
            checks.ok(
                bool(record.get("unknown")) and not record.get("published_at"),
                f"and its receipt stays, saying so, rather than being removed: {sorted(record)}",
            )

@contextmanager
def _patched(owner, name: str, value):
    """Swap one attribute for one case, and put it back whatever the case did."""
    before = getattr(owner, name)
    setattr(owner, name, value)
    try:
        yield
    finally:
        setattr(owner, name, before)

class _Died(BaseException):
    """A server dying mid-press, as the code under test sees it: nothing after this line runs,
    and no `except Exception` catches it."""

def _markdown_dir(home: Path, stamp: str, price: str = "19.99", *, at: Optional[str] = None) -> Path:
    """A mark-down directory holding one price row for Articuno, as `reprice list` writes it.

    WITH ITS SURVEY, which the send reads twice (the owner's ruling, 2026-09-26): its `at` says
    whether the read is fresh enough to send from, and its asking price is the price the screen
    drew, which the fresh read must still show. The asking price is the fixture's market price,
    the same figure `_live_export_bytes` puts live. `at` defaults to now."""
    directory = home / "inventory" / "markdowns" / stamp
    directory.mkdir(parents=True)
    source = tcgcsv.read_export(FIXTURE_EXPORT)
    original = source.by_sku()[ARTICUNO_SKU]
    row = dict(original, **{tcgcsv.QUANTITY_COLUMN: "0", tcgcsv.PRICE_COLUMN: price})
    tcgcsv.write_csv(directory / cmd_reprice.IMPORT, source.header, [row])
    files.write_json(
        directory / cmd_reprice.SURVEY,
        {
            "kind": "survey",
            "at": at or master.now(),
            "asked": {},
            "counts": {},
            "skus": [
                {
                    "sku": ARTICUNO_SKU,
                    "standing": "offered",
                    "skip": None,
                    "name": original.get(tcgcsv.NAME_COLUMN, ""),
                    "asking": str(original.get(tcgcsv.MARKET_PRICE_COLUMN) or ""),
                    "live": 1,
                    "sealed": False,
                    "row": dict(original),
                }
            ],
        },
    )
    return directory

def _live_export_priced(quantities: Dict[str, int], prices: Dict[str, str]) -> bytes:
    """A live export holding these quantities, and these marketplace prices where named."""
    source = tcgcsv.read_export(FIXTURE_EXPORT)
    by_sku = source.by_sku()
    rows = []
    for sku, quantity in quantities.items():
        row = dict(by_sku[sku], **{tcgcsv.LIVE_QUANTITY_COLUMN: str(quantity)})
        if sku in prices:
            row[tcgcsv.PRICE_COLUMN] = prices[sku]
        rows.append(row)
    path = Path(tempfile.mkdtemp()) / "live.csv"
    tcgcsv.write_csv(path, source.header, rows)
    return path.read_bytes()

def _dead_pid() -> int:
    gone = subprocess.Popen(["true"])
    gone.wait()
    return gone.pid

def check_send_review_r3(checks: Checks) -> None:
    """The round-2 adversarial review's failures (F1-F6, and three more), each red first.

    EVERY CASE HERE WENT RED ON THE ROUND-2 BUILD. A failure after the receipt was written left
    it "sending" for as long as the server lived; a mark-down press that died left a claim
    nothing released; the check read a missing baseline as zero; a press that sent nothing
    left a claim; the stale half of the claim had no case; a listing row could carry no copy;
    and a downloaded file offered its copies back after one check, although the owner may have
    uploaded it late. (Round 3's price wait had a case here too. Round 4 removed the wait, whose
    premise was false, and `check_send_review_r4`'s H3 case proves the price a send carries.)
    """
    checks.note("")
    checks.note("SEND REVIEW, ROUND 3 — what the round-2 review found, each red first")

    cards = [(3, i, "Articuno", "161", None) for i in (1, 2, 3)]
    cards.append((3, 4, "Dunsparce", "120", "normal"))
    empty = {ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0}
    real_run_sync = pipeline_routes._run_sync

    def pushed(sku):
        listing = Store().read().inventory.listings.get(sku)
        return 0 if listing is None else listing.pushed

    def receipt(stamp):
        return [s for s in send_routes.do_sends()["sends"] if s["stamp"] == stamp][0]

    def press(run_dir):
        return _route_refusal(
            lambda: send_routes.do_send({"runs": [run_dir.name], "confirm": True})
        )

    # --------------------------- F1: the emit step times out after the receipt is written
    with _case(checks, "F1: a timed-out step after the receipt"), send_portal() as portal, \
            isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)

        def timed_out(argv, timeout):
            code, console = real_run_sync(argv, timeout)
            if len(argv) > 1 and argv[1] == "emit":
                # THE CHILD COMMITTED, THEN THE WAIT RAN OUT: the copies are counted and the
                # press never heard so.
                raise pipeline_routes.PipelineRefusal(
                    HTTPStatus.GATEWAY_TIMEOUT, "step_timed_out", "emit did not finish"
                )
            return code, console

        with _patched(pipeline_routes, "_run_sync", timed_out):
            code = press(run_dir)
        checks.equal(
            code, "send_unknown",
            "F1: A STEP THAT TIMES OUT AFTER THE COPIES WERE COUNTED is unknown",
        )
        sends = send_routes.do_sends()["sends"]
        stamp = sends[0]["stamp"] if sends else ""
        checks.ok(
            bool(sends) and sends[0]["state"] == "unknown" and sends[0]["held"],
            f"F1: the receipt reads unknown and holds its cards, never 'sending': "
            f"{[(s['state'], s['held']) for s in sends]}",
        )
        checks.equal(_posts(portal), [], "F1: and nothing reached TCGplayer's write side")
        if stamp:
            _age_receipt(stamp)
            portal["live"] = _live_export_bytes(empty)
            send_routes.do_live_check({})
            after = receipt(stamp)
            checks.ok(
                after["state"] == "short" and after["takeable"] == 4 and not after["held"],
                f"F1: THE CHECK PAST THE WAIT RESOLVES IT: none found, the hold released, all "
                f"four offered back: {after['state']}, {after['takeable']}, held {after['held']}",
            )

    # --------------------------- F1: any other error before "sending"
    with _case(checks, "F1: an error before sending"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)

        def broken(_skus):
            raise RuntimeError("the store read broke")

        with _patched(send_routes, "_sold_by_sku", broken):
            code = press(run_dir)
        checks.equal(code, "send_unknown", "F1: AN ERROR AFTER THE COPIES WERE COUNTED is unknown")
        sends = send_routes.do_sends()["sends"]
        checks.ok(
            bool(sends) and sends[0]["state"] == "unknown" and sends[0]["held"]
            and bool(sends[0]["check_after"]),
            f"F1: unknown, held, and it says when Banchi checks: "
            f"{[(s['state'], s['held'], s['check_after']) for s in sends]}",
        )
        checks.equal(pushed(ARTICUNO_SKU), 3, "F1: and the copies stay counted until the check")

    # --------------------------- F1: a timeout before anything was counted leaves nothing
    with _case(checks, "F1: a timeout before the count"), send_portal() as portal, \
            isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)

        def never_ran(argv, timeout):
            if len(argv) > 1 and argv[1] == "emit":
                raise pipeline_routes.PipelineRefusal(
                    HTTPStatus.GATEWAY_TIMEOUT, "step_timed_out", "emit did not finish"
                )
            return real_run_sync(argv, timeout)

        with _patched(pipeline_routes, "_run_sync", never_ran):
            code = press(run_dir)
        checks.equal(code, "step_timed_out", "F1: a step that counted nothing is its own refusal")
        checks.equal(
            (send_routes.do_sends()["sends"], Store().read().send_claims.live(), pushed(ARTICUNO_SKU)),
            ([], [], 0),
            "F1: and it leaves no receipt, no claim and no copy counted",
        )

    # ------------- F2: a mark-down press that died leaves a claim the check resolves
    for died_at, pushed_first in (("the live read", False), ("the publish", True)):
        label = f"F2: a mark-down press that died at {died_at}"
        with _case(checks, label), send_portal() as portal, isolated_home() as home:
            directory = _markdown_dir(home, "20260924-130000")
            if pushed_first:
                pipeline_routes._write_push(
                    directory,
                    {"upload_id": "u-7", "rows": 1, "accepted": 1, "messages": [],
                     "pushed_at": "2026-09-24T13:00:05+00:00", "published_at": None},
                )
            with Store().write() as writable:
                claim = writable.send_claims.claim(
                    "md-20260924-130000", "markdown", {ARTICUNO_SKU: 0}, pid=_dead_pid()
                )
                claim.started_at = "2026-09-01T13:00:00+00:00"
                writable.send_claims.entries[claim.stamp] = claim
            run_dir, _ = seam_run(checks, cards)
            portal["live"] = _live_export_bytes(empty)
            try:
                send_routes.do_send({"runs": [run_dir.name], "confirm": True})
                code, said = None, ""
            except pipeline_routes.PipelineRefusal as refusal:
                code, said = refusal.code, str(refusal)
            checks.ok(
                code == "price_change_held" and "price change" in said and "13:00" in said,
                f"{label}: THE LISTING SEND NAMES THE MARK-DOWN THAT BLOCKS IT: {code}: {said}",
            )
            checks.ok(
                send_routes.do_sends()["due"],
                f"{label}: A DEAD PRESS'S CLAIM IS AN UNKNOWN MARK-DOWN, and past its wait the "
                f"check is due",
            )
            # TCGplayer's price is still the old one: the file never went live.
            portal["live"] = _live_export_priced(empty, {ARTICUNO_SKU: "25.00"})
            send_routes.do_live_check({})
            checks.equal(
                Store().read().send_claims.live(),
                [],
                f"{label}: THE CHECK RELEASES THE DEAD PRESS'S CLAIM, with no price re-sent",
            )
            checks.equal(
                [name for name in _posts(portal) if name == "movetolive"],
                [],
                f"{label}: and nothing was published to clear it",
            )
            portal["live"] = _live_export_bytes(empty)
            sent = send_routes.do_send({"runs": [run_dir.name], "confirm": True})["send"]
            checks.equal(sent["copies"], 4, f"{label}: and the listing send goes through after it")

    # ------------------------- F2: an error inside a mark-down press is held, not stuck
    with _case(checks, "F2: an error inside a mark-down press"), send_portal() as portal, \
            isolated_home() as home:
        directory = _markdown_dir(home, "20260924-140000")
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 1})

        def broken_push(rows, filename="import.csv", *, listing=False):
            raise RuntimeError("the socket broke in a way nothing names")

        with _patched(tcg_import, "push_to_staged", broken_push):
            code = _route_refusal(
                lambda: send_routes.do_markdown_send(directory.name, {"confirm": True})
            )
        checks.equal(code, "send_unknown", "F2: AN ERROR MID-PRESS is unknown, not a crash")
        record = pipeline_routes._read_push(directory) or {}
        checks.ok(
            bool(record.get("unknown")) and bool(record.get("check_after")),
            f"F2: and the receipt says so, with its wait: {sorted(record)}",
        )
        record["check_after"] = "2000-01-01T00:00:00+00:00"
        pipeline_routes._write_push(directory, record)
        send_routes.do_live_check({})
        checks.equal(Store().read().send_claims.live(), [], "F2: and the check past the wait releases it")

    # ------------------- F4: the server dies after emit counted, before the baseline
    with _case(checks, "F4: a death before the baseline"), send_portal() as portal, \
            isolated_home():
        run_dir, _ = seam_run(checks, cards)
        # TCGplayer already holds two Articuno the store never recorded, so the guard sends one.
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 2, DUNSPARCE_SKU: 0})

        def died(_path):
            raise _Died()

        try:
            with _patched(send_routes, "_copies", died):
                send_routes.do_send({"runs": [run_dir.name], "confirm": True})
        except _Died:
            pass
        stamp = send_routes._receipts()[0][0]
        directory = send_routes.sends_dir() / stamp
        record = send_routes._read(directory)
        record["holder"] = {"pid": _dead_pid(), "proc_start": "gone"}
        record["phase"] = "deciding"
        record.pop("unknown", None)
        record.pop("check_after", None)
        send_routes._write(directory, record)
        checks.equal(receipt(stamp)["state"], "unknown", "F4: a press that died after the count is unknown")
        # NOTHING WAS PUSHED. TCGplayer still holds the two it held before.
        _age_receipt(stamp)
        send_routes.do_live_check({})
        after = receipt(stamp)
        checks.ok(
            after["state"] == "short" and after["takeable"] == 2,
            f"F4: THE CHECK READS THE BASELINE TAKEN BEFORE THE COUNT: two live before, two now, "
            f"so neither copy this send counted went, and both come back: {after['state']}, "
            f"{after['takeable']}, {after['check']}",
        )

    # ------------------------------------------ F5: a press that sends nothing claims nothing
    with _case(checks, "F5: a press that sends nothing"), send_portal() as portal, \
            isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)
        send_routes.do_send({"runs": [run_dir.name], "confirm": True})
        before = sorted(Store().read().send_claims.entries.keys())
        checks.equal(press(run_dir), "nothing_to_send", "F5: a second press has nothing to send")
        after_rows = sorted(Store().read().send_claims.entries.keys())
        checks.equal(
            (after_rows, Store().read().send_claims.live()),
            (before, []),
            "F5: A PRESS THAT SENDS NOTHING WRITES NO CLAIM, live or released",
        )

    # ------------- F5b: one unreadable live claim must not kill the Sends list (DEBT59)
    with _case(checks, "F5b: an unreadable live claim"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)
        sent = send_routes.do_send({"runs": [run_dir.name], "confirm": True})["send"]
        conn = db.connect(Store().directory)
        try:
            conn.execute(
                "INSERT INTO send_claims (key, pid, state, started_at, kind, payload) "
                "VALUES ('bad-row', 1, 'live', '2026-09-01T00:00:00+00:00', 'send', '{\"pid\": \"x\"}')"
            )
            conn.commit()
        finally:
            conn.close()
        try:
            listed = send_routes.do_sends()
        except Exception as exc:  # noqa: BLE001
            listed = {"sends": [], "unreadable_claims": repr(exc)}
        checks.equal(
            ([row["stamp"] for row in listed["sends"]], listed["unreadable_claims"]),
            ([sent["stamp"]], 1),
            "F5b: THE LIST DRAWS EVERY READABLE SEND AND FLAGS THE UNREADABLE CLAIM",
        )
        try:
            Store().read().send_claims.overlap([ARTICUNO_SKU])
            refused = False
        except files.UnreadableClaim:
            refused = True
        checks.ok(refused, "F5b: and a path that guards a send still refuses over that claim")

    # ------------- F5c: a copy `set_state` could not stamp is named in the emit result
    with _case(checks, "F5c: unstamped copies are named"):
        from types import SimpleNamespace as NS
        from cli import cmd_emit

        class NoRecord:
            def set_state(self, key, state, **kw):
                return False

        position = NS(box=1, index=7)
        match = NS(
            sku="S1", row={}, condition="NM", live_positions=[position],
            uncommitted_positions=[position],
        )
        writable = NS(inventory=NoRecord())
        _, _, single = cmd_emit._stamp_single(
            writable, NS(matches={"S1": match}, joins={}), {"S1"}, {}, NS(name="r"), {}, {}
        )
        leg = NS(run="r", match=match)
        row = NS(sku="S1", game=None, legs=[leg], match=match)
        plan = NS(skus=[row], live_keys={"S1": set()})
        _, _, merged = cmd_emit._stamp_merged(writable, plan, {"S1"}, {})
        said: List[str] = []
        cmd_emit._report_unstamped(merged, said.append)
        checks.ok(
            len(single) == 1 and len(merged) == 1 and any("unstamped" in line for line in said),
            f"F5c: BOTH STAMP PATHS COUNT THE MISS AND THE RESULT SAYS SO: {single} {merged} {said}",
        )

    # --------------- F6: a hand emit between a press's plan and its save refuses the press
    with _case(checks, "F6: the stale half of the claim"), isolated_home():
        run_dir, _ = seam_run(checks, cards)
        from cli import __main__ as entry
        from cli import cmd_emit

        real_guard = cmd_emit._apply_guard
        own = Path(tempfile.mkdtemp())
        interleaved: List[bool] = []

        def plan_then_hand_emit(*args, **kwargs):
            # `_apply_guard` RUNS AFTER THE PLAN IS DECIDED AND BEFORE THE STORE WRITE: the
            # exact gap the stale check covers. The hand emit lands in it, once (it runs this
            # same function itself).
            if not interleaved:
                interleaved.append(True)
                with quiet():
                    entry.main(["emit", str(run_dir.directory)])
            return real_guard(*args, **kwargs)

        with _patched(cmd_emit, "_apply_guard", plan_then_hand_emit), quiet() as said:
            code = entry.main(
                ["emit", str(run_dir.directory), "--send-dir", str(own),
                 "--send-claim", "20260924-150000-cccccc"]
            )
        claim_line = send_routes._json_line(said.getvalue(), "send_claim") or {}
        checks.ok(
            code == 1 and ARTICUNO_SKU in (claim_line.get("stale") or []),
            f"F6: A HAND EMIT THAT SAVED WHILE THE PRESS DECIDED makes the press refuse, naming "
            f"the moved card: exit {code}, {claim_line}",
        )
        checks.equal(
            (pushed(ARTICUNO_SKU), Store().read().send_claims.get("20260924-150000-cccccc")),
            (3, None),
            "F6: and the copies are counted once, by the hand emit, with no claim written",
        )

    # --------------------------- the listing door and a row that adds no copy
    # REVERSED IN ROUND 5 ON THE OWNER'S RULING (2026-09-24, "Allow mixed"): the listing door
    # takes a price-only row now, so a send can reprice live cards. `check_send_review_r5`.
    with _case(checks, "the listing door: a zero row"):
        good = {
            "Id": 0, "ProductConditionId": "123", "CategoryName": "Pokemon", "SetName": "S",
            "ProductName": "P", "ConditionName": "Near Mint", "AddToQuantity": "0",
            "MyPrice": "1.00", "ProOnlineStoreReserveQuantity": "", "ProOnlineStorePrice": "",
            "Number": "1/1",
        }
        checks.equal(
            _refusal_code_transport([good], listing=True),
            None,
            "A LISTING ROW THAT ADDS NO COPY IS A PRICE-ONLY ROW, D100's own shape (the mixed "
            "send, round 5)",
        )
        checks.equal(
            _refusal_code_transport([good], listing=False),
            None,
            "and the same row still passes the price door",
        )

    # --------- the orchestrator's call: a downloaded file takes back after a second check
    with _case(checks, "a downloaded file: take back after a second check"), \
            send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)
        stamp = send_routes.do_send({"runs": [run_dir.name], "download": True})["send"]["stamp"]
        _age_receipt(stamp)
        send_routes.do_live_check({})
        first = receipt(stamp)
        checks.ok(
            first["takeable"] == 0 and first["state"] == "written" and bool(first["take_back_after"]),
            f"A DOWNLOADED FILE IS NOT OFFERED BACK AFTER ONE CHECK: the owner may upload it "
            f"late. {first['state']}, {first['takeable']}, after {first['take_back_after']}",
        )
        checks.equal(
            send_routes.do_live_check({})["ran"], False, "and the second check waits one more wait"
        )
        directory = send_routes.sends_dir() / stamp
        record = send_routes._read(directory)
        for key in ("checked_at", "first_checked_at"):
            if record.get(key):
                record[key] = "2000-01-01T00:00:00+00:00"
        send_routes._write(directory, record)
        checks.ok(send_routes.do_sends()["due"], "one wait after the first check, the second is due")
        send_routes.do_live_check({})
        second = receipt(stamp)
        checks.equal(
            (second["state"], second["takeable"]),
            ("short", 4),
            "and a second check that still finds none offers all four back",
        )

class _GatedStore:
    """`Store`, with the first two `write()` calls held at a barrier until both arrive. Two
    presses at once then enter their store write together, which is the race a take-back must
    survive. Reads pass straight through."""

    gate: Optional[threading.Barrier] = None
    arrived: List[int] = []

    def __init__(self, *args, **kwargs):
        self._real = Store(*args, **kwargs)

    def read(self, *args, **kwargs):
        return self._real.read(*args, **kwargs)

    def write(self, *args, **kwargs):
        if self.gate is not None and len(self.arrived) < 2:
            self.arrived.append(1)
            with contextlib.suppress(threading.BrokenBarrierError):
                self.gate.wait()
        return self._real.write(*args, **kwargs)

def check_send_review_r4(checks: Checks) -> None:
    """The round-3 adversarial review's failures (H1-H4), each red first on the round-3 build.

    H1: the live check credited a SKU's rise to the OLDEST due receipt, whatever its kind and
    whatever earlier checks had already credited. A download nobody uploaded took the credit
    for a send that went live, so the live send was offered back (A), and two checks each
    credited the same single copy (B). H3: the price wait held copies out of a listing send for
    a reason that was never true, since a mark-down writes its price into the price file.
    H4: two Take back presses at once both took the copies back. And a route shape the round-2
    stamp outgrew: the screen's take-back and file routes matched no new receipt.
    """
    checks.note("")
    checks.note("SEND REVIEW, ROUND 4 — what the round-3 review found, each red first")

    cards = [(3, i, "Articuno", "161", None) for i in (1, 2, 3)]
    cards.append((3, 4, "Dunsparce", "120", "normal"))
    empty = {ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0}

    def pushed(sku):
        listing = Store().read().inventory.listings.get(sku)
        return 0 if listing is None else listing.pushed

    def receipt(stamp):
        return [s for s in send_routes.do_sends()["sends"] if s["stamp"] == stamp][0]

    def found(stamp, sku):
        """Copies of `sku` the receipt's last check credited it with."""
        summary = receipt(stamp)
        sent = send_routes._read(send_routes.sends_dir() / stamp).get("copies", {}).get(sku, 0)
        for row in (summary["check"] or {}).get("missing") or []:
            if row["sku"] == sku:
                return int(row["found"])
        return int(sent) if summary["check"] else 0

    def one_articuno(run_dir, **extra):
        return dict(
            {"runs": [run_dir.name], "quantities": {ARTICUNO_SKU: 1, DUNSPARCE_SKU: 0}}, **extra
        )

    # ------------- H1-A: a download nobody uploaded never takes a live send's credit
    with _case(checks, "H1-A: a download and a send, one check"), send_portal() as portal, \
            isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)
        download = send_routes.do_send(one_articuno(run_dir, download=True))["send"]["stamp"]
        sent = send_routes.do_send(one_articuno(run_dir, confirm=True))["send"]["stamp"]
        checks.equal(
            [row["AddToQuantity"] for row in portal["rows"]],
            ["1"],
            "H1-A: one Articuno is written to a file and not uploaded, and one is sent",
        )
        # THE SEND WENT LIVE. The downloaded file never left the Mac.
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 1, DUNSPARCE_SKU: 0})
        _age_receipt(download)
        _age_receipt(sent)
        send_routes.do_live_check({})
        live_send, file = receipt(sent), receipt(download)
        checks.equal(
            (live_send["state"], live_send["takeable"], found(sent, ARTICUNO_SKU)),
            ("checked", 0, 1),
            "H1-A: THE RISE IS THE SEND'S. Banchi saw its upload succeed, and the time of a "
            "download's upload is not known, so the send is credited first and is never "
            "offered back",
        )
        checks.equal(
            (file["state"], found(download, ARTICUNO_SKU)),
            ("written", 0),
            "H1-A: and the download is found at none, and waits for its second check",
        )
        checks.equal(
            _route_refusal(lambda: send_routes.do_take_back(sent, {"confirm": True})),
            "not_takeable",
            "H1-A: TAKE BACK OF THE LIVE SEND IS REFUSED, so the next press cannot send its copy "
            "again",
        )
        directory = send_routes.sends_dir() / download
        record = send_routes._read(directory)
        record["checked_at"] = record["first_checked_at"] = "2000-01-01T00:00:00+00:00"
        send_routes._write(directory, record)
        send_routes.do_live_check({})
        checks.equal(
            (receipt(download)["state"], receipt(download)["takeable"], receipt(sent)["state"]),
            ("short", 1, "checked"),
            "H1-A: THE SECOND CHECK STILL CREDITS THE SEND, not the file: the file's one copy "
            "comes back, and the send stays found",
        )
        send_routes.do_take_back(download, {"confirm": True})
        checks.equal(
            pushed(ARTICUNO_SKU),
            1,
            "H1-A: and after the file's copy comes back the store counts one Articuno out, "
            "which is what TCGplayer holds",
        )

    # ------------- H1-B: two checks never credit one copy twice
    with _case(checks, "H1-B: two sends, two checks, one copy live"), send_portal() as portal, \
            isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)
        first = send_routes.do_send(one_articuno(run_dir, confirm=True))["send"]["stamp"]
        # THE EXPORT HAS NOT SHOWN THE FIRST SEND YET (D273's lag), so the second press reads
        # the same baseline of none.
        second = send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {ARTICUNO_SKU: 1, DUNSPARCE_SKU: 1},
             "confirm": True}
        )["send"]["stamp"]
        # ONE ARTICUNO WENT LIVE, NOT TWO. The Dunsparce went too.
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 1, DUNSPARCE_SKU: 1})
        _age_receipt(first)
        send_routes.do_live_check({})
        checks.equal(
            (receipt(first)["state"], found(first, ARTICUNO_SKU)),
            ("checked", 1),
            "H1-B: the first check credits the one live Articuno to the older send",
        )
        _age_receipt(second)
        send_routes.do_live_check({})
        checks.equal(
            found(first, ARTICUNO_SKU) + found(second, ARTICUNO_SKU),
            1,
            "H1-B: ONE CREDIT LEDGER PER SKU ACROSS CHECKS: the second check does not credit "
            "the same live Articuno again. TCGplayer holds one, and the two receipts together "
            "claim one",
        )
        checks.equal(
            (receipt(second)["state"], receipt(second)["takeable"], found(second, DUNSPARCE_SKU)),
            ("short", 1, 1),
            "H1-B: so the second send is short one Articuno, which can come back, and its "
            "Dunsparce is found",
        )

    # ------------- H3: a listing send carries the price a mark-down just set
    with _case(checks, "H3: a listing send after a mark-down"), send_portal() as portal, \
            isolated_home() as home:
        run_dir, _ = seam_run(checks, cards)
        priced = home / "live-priced.csv"
        priced.write_bytes(_live_export_priced({ARTICUNO_SKU: 1, DUNSPARCE_SKU: 0}, {ARTICUNO_SKU: "25.00"}))
        command(checks, "reprice", "list", str(priced), "--days", "9999", "--write")
        stamp = sorted((files.inventory_dir() / cmd_reprice.DIRNAME).iterdir())[-1].name
        applied = pipeline_routes.do_markdown_apply(
            stamp, {"edits": [{"sku": ARTICUNO_SKU, "price": "20.00"}], "write": True}
        )
        checks.ok(applied["ok"] and applied["wrote"], f"H3: the mark-down to 20.00 is written: {applied.get('ok')}")
        portal["live"] = priced.read_bytes()
        send_routes.do_markdown_send(stamp, {"confirm": True})
        # THE MARK-DOWN WENT LIVE MOMENTS AGO. The listing send comes straight after it.
        portal["rows"].clear()
        send_routes.do_send({"runs": [run_dir.name], "confirm": True, "moves": [{"sku": ARTICUNO_SKU, "price": "20.00", "copies": 1}]})
        rows = {row["ProductConditionId"]: row for row in portal["rows"]}
        checks.equal(
            (rows.get(ARTICUNO_SKU) or {}).get("MyPrice"),
            "20.00",
            "H3: A LISTING SEND RIGHT AFTER A MARK-DOWN CARRIES THE MARKED-DOWN PRICE. The "
            "mark-down wrote it into the price file, so no row can put the old price back, and "
            "no copy waits",
        )

    # ------------- H4: two Take back presses at once take the copies back once
    with _case(checks, "H4: two take-backs at once"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)
        stamp = send_routes.do_send({"runs": [run_dir.name], "confirm": True})["send"]["stamp"]
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 1, DUNSPARCE_SKU: 0})
        _age_receipt(stamp)
        send_routes.do_live_check({})
        checks.equal(receipt(stamp)["takeable"], 3, "H4: the check offers three copies back")
        _GatedStore.gate = threading.Barrier(2, timeout=5)
        _GatedStore.arrived = []
        answers: Dict[int, tuple] = {}
        try:
            with _patched(send_routes, "Store", _GatedStore):
                threads = [
                    _press_thread(
                        lambda: send_routes.do_take_back(stamp, {"confirm": True}), answers, index
                    )
                    for index in (0, 1)
                ]
                for thread in threads:
                    thread.join(30)
        finally:
            _GatedStore.gate = None
        checks.equal(
            sorted(kind if kind == "sent" else f"{kind} {answer}" for kind, answer in answers.values()),
            ["refused not_takeable", "sent"],
            f"H4: TWO TAKE BACK PRESSES AT ONCE: one takes the copies back, the other is "
            f"refused: {answers}",
        )
        checks.equal(
            (pushed(ARTICUNO_SKU), pushed(DUNSPARCE_SKU)),
            (1, 0),
            "H4: and the store still counts the one live Articuno out: the copies came back once",
        )

    # ------------- H2: a taken-back receipt keeps its warning until it is dismissed
    with _case(checks, "H2: the warning a take-back keeps"), send_portal() as portal, \
            isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes(empty)
        download = send_routes.do_send(one_articuno(run_dir, download=True))
        # THE REST GO IN A SEND WHOSE PUBLISH AND ROLLBACK ARE BOTH REFUSED: its upload may
        # still wait in Staged.
        portal["refuse"] = {"movetolive"}
        portal["fail"] = {"rollbackexportcsv"}
        _route_refusal(lambda: send_routes.do_send({"runs": [run_dir.name], "confirm": True}))
        portal["refuse"], portal["fail"] = set(), set()
        staged = [stamp for stamp, record in send_routes._receipts() if record.get("kind") == "send"][0]
        checks.equal(
            _route_refusal(lambda: send_routes.do_dismiss(staged, {})),
            "nothing_to_dismiss",
            "H2: before Take back there is no taken-back warning to dismiss",
        )
        _age_receipt(staged)
        send_routes.do_live_check({})
        send_routes.do_take_back(staged, {"confirm": True})
        checks.equal(
            receipt(staged)["warning"],
            "staged",
            "H2: A SEND TAKEN BACK WHOSE UPLOAD MAY WAIT IN STAGED KEEPS SAYING SO: publishing "
            "it now would list the copies twice",
        )
        # TWENTY NEWER SENDS, stamped a day later so none can sort before it.
        for index in range(send_routes.SENDS_SHOWN):
            stamp = f"29990101-{index:06d}-aaaaaa"
            send_routes._write(
                send_routes.sends_dir() / stamp,
                {"stamp": stamp, "kind": "send", "phase": "done", "failure": {"code": "x", "message": "x"},
                 "taken_back_at": "2026-09-24T12:00:00+00:00"},
            )
        listed = [s["stamp"] for s in send_routes.do_sends()["sends"]]
        checks.ok(
            staged in listed and len(listed) == send_routes.SENDS_SHOWN + 1,
            "H2: and it is listed while it warns, however many newer sends there are",
        )
        dismissed = send_routes.do_dismiss(staged, {})["send"]
        checks.equal(
            (dismissed["warning"], staged in [s["stamp"] for s in send_routes.do_sends()["sends"]]),
            (None, False),
            "H2: until the owner dismisses it: then it warns no more, and ages off the list",
        )
        checks.equal(
            download.get("send", {}).get("warning"),
            None,
            "H2: a written file carries no taken-back warning before it is taken back",
        )
        record = send_routes._read(send_routes.sends_dir() / download["send"]["stamp"])
        record["taken_back_at"] = "2026-09-24T12:30:00+00:00"
        checks.equal(
            send_routes._warning(record),
            "old_file",
            "H2: A DOWNLOADED FILE TAKEN BACK WARNS: uploading the old file now would list its "
            "copies twice",
        )

    # ------------- the screen's routes read the stamp a press now writes
    with _case(checks, "the take-back and file routes read a round-2 stamp"), isolated_home():
        stamp = "20260924-120000-abcdef"
        directory = send_routes.sends_dir() / stamp
        send_routes._write(
            directory,
            {"stamp": stamp, "kind": "download", "at": "2026-09-24T12:00:00+00:00",
             "phase": "done", "files": ["import.csv"], "copies": {ARTICUNO_SKU: 1},
             "copies_total": 1, "check_after": "2999-01-01T00:00:00+00:00"},
        )
        (directory / "import.csv").write_text("x\n", encoding="utf-8")
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        try:
            file_status, _, _ = request(port, "GET", f"/pipeline/sends/{stamp}/file?name=import.csv")
            back_status, back_body, _ = request(
                port, "POST", f"/pipeline/sends/{stamp}/take-back", payload={"confirm": True}
            )
        finally:
            httpd.shutdown()
            thread.join(timeout=5)
        checks.equal(
            (file_status, back_status, (json.loads(back_body or b"{}").get("error") or {}).get("code")),
            (200, 409, "take_back_not_yet"),
            "THE SCREEN'S ROUTES MATCH THE STAMP A PRESS WRITES: the file is served, and Take "
            "back answers for the receipt rather than 404",
        )

def check_send_review_r5(checks: Checks) -> None:
    """Round 5: the mixed send (the owner's ruling, 2026-09-24: "Allow mixed"), and the order of
    two presses in one second. Each case went red on the round-4 build before the fix.

    ONE PRESS LISTS NEW COPIES AND REPRICES LIVE ONES. A card already live that this press adds
    no copy of, whose TYPED price differs from TCGplayer's, rides the send as a price-only row
    (Add to Quantity 0). It never claims, counts or takes back a copy. The check past the wait
    compares its price with TCGplayer's. A rule price never reaches a live listing this way.
    """
    checks.note("")
    checks.note("SEND REVIEW, ROUND 5 — the mixed send, and two presses in one second")

    cards = [(3, i, "Articuno", "161", None) for i in (1, 2, 3)]
    cards.append((3, 4, "Dunsparce", "120", "normal"))

    def pushed(sku):
        listing = Store().read().inventory.listings.get(sku)
        return 0 if listing is None else listing.pushed

    def receipt(stamp):
        return [s for s in send_routes.do_sends()["sends"] if s["stamp"] == stamp][0]

    def typed(sku, price):
        book = corpus.Corpus.read()
        book.answers[sku] = corpus.Answer(value=price)
        book.write()

    def portal_rows(portal):
        return {
            row["ProductConditionId"]: (row["AddToQuantity"], row["MyPrice"]) for row in portal["rows"]
        }

    # ------------- M1: one press lists the new copy and reprices the live card
    with _case(checks, "M1: a mixed send"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
        send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {DUNSPARCE_SKU: 0}, "confirm": True}
        )
        # THE ARTICUNO WENT LIVE AT 22.03. The owner now types 30.00 for it, and the Dunsparce
        # is still unsent.
        portal["live"] = _live_export_priced(
            {ARTICUNO_SKU: 3, DUNSPARCE_SKU: 0}, {ARTICUNO_SKU: "22.03"}
        )
        typed(ARTICUNO_SKU, "30.00")
        portal["rows"].clear()
        sent = send_routes.do_send({"runs": [run_dir.name], "confirm": True, "prices": [{"sku": ARTICUNO_SKU, "price": "30.00", "was": "22.03"}]})["send"]
        checks.equal(
            portal_rows(portal).get(ARTICUNO_SKU),
            ("0", "30.00"),
            "M1: THE LIVE CARD'S NEW PRICE RIDES THE SEND as a price-only row: Add to Quantity 0, "
            "at the typed 30.00",
        )
        checks.equal(
            portal_rows(portal).get(DUNSPARCE_SKU, ("?",))[0],
            "1",
            "M1: and the same press lists the new Dunsparce copy",
        )
        checks.equal(
            (pushed(ARTICUNO_SKU), pushed(DUNSPARCE_SKU)),
            (3, 1),
            "M1: A PRICE-ONLY ROW COUNTS NO COPY: the Articuno stays at three sent, the "
            "Dunsparce is one",
        )
        claim = Store().read().send_claims.get(sent["stamp"])
        checks.equal(
            dict(claim.skus) if claim else None,
            {DUNSPARCE_SKU: 1, ARTICUNO_SKU: 0},
            "M1: and the press claimed the card it adds a copy of, and the repriced card at 0 copies (round 6, S3)",
        )
        checks.equal(
            (sent["copies"], sent["prices"]),
            (1, 1),
            "M1: the receipt names one copy and one price change, apart",
        )
        conn = db.connect(files.inventory_dir())
        try:
            postings = [
                entry
                for entry in db.postings_for_sku(conn, ARTICUNO_SKU)
                if entry["source"] == "emit-price"
            ]
        finally:
            conn.close()
        checks.equal(
            [(entry["price"], entry["replaced"]) for entry in postings],
            [("30.00", "22.03")],
            "M1: the price change is a posting, and it names the live price it replaced (D243)",
        )
        # THE WAIT PASSES. TCGplayer shows the new price, and the Dunsparce never showed.
        portal["live"] = _live_export_priced(
            {ARTICUNO_SKU: 3, DUNSPARCE_SKU: 0}, {ARTICUNO_SKU: "30.00"}
        )
        _age_receipt(sent["stamp"])
        send_routes.do_live_check({})
        after = receipt(sent["stamp"])
        checks.equal(
            (after["price_check"] or {}).get("matched"),
            1,
            "M1: THE CHECK PAST THE WAIT COMPARES THE PRICE with TCGplayer's, as a mark-down's does",
        )
        checks.equal(
            (after["state"], after["takeable"]),
            ("short", 1),
            "M1: and Take back offers only the copy it did not find, never the price row",
        )

    # ------------- M2: a price-only press; a rule price and an unchanged price send nothing
    with _case(checks, "M2: prices only"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
        send_routes.do_send({"runs": [run_dir.name], "confirm": True})
        live = {ARTICUNO_SKU: 3, DUNSPARCE_SKU: 1}
        portal["live"] = _live_export_priced(live, {ARTICUNO_SKU: "22.03", DUNSPARCE_SKU: "9.99"})
        typed(ARTICUNO_SKU, "22.03")
        checks.equal(
            _route_refusal(lambda: send_routes.do_send({"runs": [run_dir.name], "confirm": True, "prices": [{"sku": ARTICUNO_SKU, "price": "22.03", "was": "22.03"}]})),
            "nothing_to_send",
            "M2: A TYPED PRICE TCGPLAYER ALREADY SHOWS IS NO CHANGE, and a RULE price that differs "
            "from the live one (the Dunsparce) never reaches a live listing: nothing is sent",
        )
        typed(ARTICUNO_SKU, "25.00")
        portal["rows"].clear()
        sent = send_routes.do_send({"runs": [run_dir.name], "confirm": True, "prices": [{"sku": ARTICUNO_SKU, "price": "25.00", "was": "22.03"}]})["send"]
        checks.equal(
            portal_rows(portal),
            {ARTICUNO_SKU: ("0", "25.00")},
            "M2: A PRESS OF PRICE CHANGES ONLY SENDS AND MAKES LIVE, one price-only row",
        )
        checks.equal(
            (sent["state"], sent["copies"], sent["prices"], pushed(ARTICUNO_SKU)),
            ("waiting", 0, 1, 3),
            "M2: its receipt waits for the check, and no copy was counted",
        )
        portal["live"] = _live_export_priced(live, {ARTICUNO_SKU: "22.03", DUNSPARCE_SKU: "9.99"})
        _age_receipt(sent["stamp"])
        send_routes.do_live_check({})
        after = receipt(sent["stamp"])
        checks.equal(
            (after["state"], after["takeable"], [row["sku"] for row in after["price_check"]["missing"]]),
            ("short", 0, [ARTICUNO_SKU]),
            "M2: A PRICE TCGPLAYER DOES NOT SHOW IS NAMED, and nothing is offered back: another "
            "price change is the way a live price moves again",
        )

    # ------------- M3: a price change never races a mark-down over the same card
    with _case(checks, "M3: a mark-down holds the card"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
        send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {DUNSPARCE_SKU: 0}, "confirm": True}
        )
        portal["live"] = _live_export_priced({ARTICUNO_SKU: 3, DUNSPARCE_SKU: 0}, {ARTICUNO_SKU: "22.03"})
        typed(ARTICUNO_SKU, "30.00")
        with Store().write() as writable:
            writable.send_claims.claim(
                f"{send_routes.MARKDOWN_CLAIM}20260924-110000",
                sendclaims.KIND_MARKDOWN,
                {ARTICUNO_SKU: 0},
                pid=_dead_pid(),
            )
        portal["rows"].clear()
        checks.equal(
            _route_refusal(lambda: send_routes.do_send({"runs": [run_dir.name], "confirm": True, "prices": [{"sku": ARTICUNO_SKU, "price": "30.00", "was": "22.03"}]})),
            "price_change_held",
            "M3: A PRICE CHANGE OVER A CARD A MARK-DOWN HOLDS IS REFUSED by name, and the whole "
            "press sends nothing",
        )
        checks.equal(portal["rows"], [], "M3: and TCGplayer receives no row")

    # ------------- the listing door takes a price-only row, and never a negative one
    with _case(checks, "the listing door"):
        good = {
            "Id": 0, "ProductConditionId": "123", "CategoryName": "Pokemon", "SetName": "S",
            "ProductName": "P", "ConditionName": "Near Mint", "AddToQuantity": "0",
            "MyPrice": "1.00", "ProOnlineStoreReserveQuantity": "", "ProOnlineStorePrice": "",
            "Number": "1/1",
        }
        checks.equal(
            _refusal_code_transport([good, dict(good, ProductConditionId="124", AddToQuantity="2")], listing=True),
            None,
            "THE LISTING DOOR TAKES A MIXED FILE: a price-only row beside a row that adds copies",
        )
        checks.equal(
            _refusal_code_transport([dict(good, AddToQuantity="-1")], listing=True),
            "tcg_import_moves_quantity",
            "and still refuses a row that would take a copy away",
        )

    # ------------- two presses in one second are ordered by when they were pressed
    with _case(checks, "two presses in one second"), isolated_home():
        older, newer = "20260924-120000-ffffff", "20260924-120000-000000"
        for stamp, ns in ((older, 1_000), (newer, 2_000)):
            send_routes._write(
                send_routes.sends_dir() / stamp,
                {
                    "stamp": stamp, "kind": "send", "at": "2026-09-24T12:00:00+00:00",
                    "pressed_ns": ns, "phase": "done", "copies": {ARTICUNO_SKU: 1},
                    "copies_total": 1, "live_before": {ARTICUNO_SKU: 0},
                    "sold_before": {ARTICUNO_SKU: 0}, "published_at": "2026-09-24T12:00:05+00:00",
                    "check_after": "2000-01-01T00:00:00+00:00", "files": ["import.csv"],
                },
            )
        checks.equal(
            [stamp for stamp, _ in send_routes._receipts()],
            [newer, older],
            "THE RECEIPT LIST IS NEWEST PRESS FIRST, not by the stamp's random tail",
        )
        receipts = send_routes._receipts()
        credits = send_routes._credits(
            receipts,
            frozenset({older, newer}),
            {older: {ARTICUNO_SKU: 1}, newer: {ARTICUNO_SKU: 1}},
            {ARTICUNO_SKU: 1},
            {ARTICUNO_SKU: 0},
            datetime.now(timezone.utc),
        )
        checks.equal(
            (credits[older].get(ARTICUNO_SKU), credits[newer].get(ARTICUNO_SKU)),
            (1, 0),
            "AND THE CREDIT LEDGER AGREES: one live copy goes to the send pressed first",
        )

def check_send_review_r6(checks: Checks) -> None:
    """Round 6: the fresh review of round 5 (B1-B3, S1-S4, N2), each red first on the round-5
    build. Probes P1-P7 are the reviewer's, turned into cases.

    THE ORCHESTRATOR'S RULING ON THE OWNER'S WORDS: only a price the SCREEN named rides a send.
    A corpus answer the owner did not type on the worklist never does. A named price whose live
    figure moved since the screen drew it is refused by name; one TCGplayer already shows is
    left out and named. A named price under the floor is refused, as the mark-down door does.
    """
    checks.note("")
    checks.note("SEND REVIEW, ROUND 6 — only a named price rides; the reviewer's probes")

    cards = [(3, i, "Articuno", "161", None) for i in (1, 2, 3)]
    cards.append((3, 4, "Dunsparce", "120", "normal"))

    def pushed(sku):
        listing = Store().read().inventory.listings.get(sku)
        return 0 if listing is None else listing.pushed

    def receipt(stamp):
        return [s for s in send_routes.do_sends()["sends"] if s["stamp"] == stamp][0]

    def typed(sku, price):
        book = corpus.Corpus.read()
        book.answers[sku] = corpus.Answer(value=price)
        book.write()

    def portal_rows(portal):
        return {
            row["ProductConditionId"]: (row["AddToQuantity"], row["MyPrice"]) for row in portal["rows"]
        }

    def named(price, was):
        return [{"sku": ARTICUNO_SKU, "price": price, "was": was}]

    def articuno_live(run_dir, portal, price="22.03"):
        """Every Articuno sent and live at `price`; the Dunsparce still unsent."""
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
        send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {DUNSPARCE_SKU: 0}, "confirm": True}
        )
        portal["live"] = _live_export_priced({ARTICUNO_SKU: 3, DUNSPARCE_SKU: 0}, {ARTICUNO_SKU: price})
        portal["rows"].clear()

    # ------------- P1 (S1): a named price under the store's floor is refused, by name
    with _case(checks, "P1: under the floor"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        articuno_live(run_dir, portal)
        typed(ARTICUNO_SKU, "0.05")
        refused = _refusal_text_route(lambda: send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {DUNSPARCE_SKU: 0}, "confirm": True,
             "prices": named("0.05", "22.03")}
        ))
        checks.equal(
            (refused or ("", ""))[0],
            "price_refused",
            "P1: A NAMED PRICE UNDER THE FLOOR IS REFUSED, the mark-down door's own rule",
        )
        checks.ok("under the store's floor" in (refused or ("", ""))[1], f"P1: and named: {refused}")
        checks.equal(portal["rows"], [], "P1: and TCGplayer receives no row")

    # ------------- P2 (B1): the guard trims a listing to nothing; an unnamed price never rides
    with _case(checks, "P2: an unnamed price after a trim"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_priced({ARTICUNO_SKU: 3, DUNSPARCE_SKU: 0}, {ARTICUNO_SKU: "22.03"})
        typed(ARTICUNO_SKU, "30.00")
        portal["rows"].clear()
        checks.equal(
            _route_refusal(lambda: send_routes.do_send(
                {"runs": [run_dir.name], "quantities": {DUNSPARCE_SKU: 0}, "confirm": True}
            )),
            "nothing_to_send",
            "P2: A PRICE THE BUTTON DID NOT NAME NEVER RIDES: the guard held back every Articuno, "
            "and its typed 30.00 does not go out as a price change",
        )
        checks.equal(portal["rows"], [], "P2: and TCGplayer receives no row")

    # ------------- P3 (N1, kept): Qty 0 with a named price moves the price, and no copy
    with _case(checks, "P3: Qty 0 and a named price"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
        send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {ARTICUNO_SKU: 1, DUNSPARCE_SKU: 0}, "confirm": True}
        )
        portal["live"] = _live_export_priced({ARTICUNO_SKU: 1, DUNSPARCE_SKU: 0}, {ARTICUNO_SKU: "22.03"})
        typed(ARTICUNO_SKU, "30.00")
        portal["rows"].clear()
        send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {ARTICUNO_SKU: 0, DUNSPARCE_SKU: 1},
             "confirm": True, "prices": named("30.00", "22.03")}
        )
        checks.equal(
            (portal_rows(portal).get(ARTICUNO_SKU), pushed(ARTICUNO_SKU)),
            (("0", "30.00"), 1),
            "P3: QTY 0 AND A NAMED PRICE is the owner's price-only edit: the price moves, no copy does",
        )

    # ------------- P4 (S2): a press that died mid-push reads as possibly staged
    with _case(checks, "P4: a hard crash mid-push"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
        portal["fail"] = {"movetolive", "rollbackexportcsv"}
        _route_refusal(lambda: send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {DUNSPARCE_SKU: 0}, "confirm": True}
        ))
        portal["fail"] = set()
        stamp = send_routes._receipts()[0][0]
        directory = send_routes.sends_dir() / stamp
        record = send_routes._read(directory)
        record.update({
            "phase": "sending", "unknown": None, "check_after": None, "publish_started_at": None,
            "pushed": {"upload_id": "u-1", "rows": 1, "accepted": 1, "messages": []},
            "holder": {"pid": _dead_pid(), "proc_start": "x"},
        })
        send_routes._write(directory, record)
        checks.equal(
            (receipt(stamp)["state"], receipt(stamp)["staged"]),
            ("unknown", True),
            "P4: A RECEIPT LEFT IN PHASE SENDING BY A DEAD SERVER READS AS POSSIBLY STAGED",
        )
        record = send_routes._read(directory)
        record["at"] = "2000-01-01T00:00:00+00:00"
        send_routes._write(directory, record)
        send_routes.do_live_check({})
        send_routes.do_take_back(stamp, {"confirm": True})
        checks.equal(
            receipt(stamp)["warning"],
            "staged",
            "P4: and after the check and Take back it keeps the Staged warning until dismissed",
        )

    # ------------- P5 (S3): an unconfirmed price change holds its card from a mark-down
    with _case(checks, "P5: a held price change"), send_portal() as portal, isolated_home() as home:
        run_dir, _ = seam_run(checks, cards)
        articuno_live(run_dir, portal)
        typed(ARTICUNO_SKU, "30.00")
        portal["fail"] = {"movetolive"}
        code = _route_refusal(lambda: send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {DUNSPARCE_SKU: 0}, "confirm": True,
             "prices": named("30.00", "22.03")}
        ))
        portal["fail"] = set()
        held = [claim for claim in Store().read().send_claims.live() if ARTICUNO_SKU in claim.skus]
        checks.equal(
            (code, [dict(claim.skus) for claim in held]),
            ("send_unknown", [{ARTICUNO_SKU: 0}]),
            "P5: AN UNCONFIRMED PRICE-ONLY SEND CLAIMS ITS CARD AT 0 COPIES",
        )
        markdown = _markdown_dir(home, "20260924-130000", "19.99")
        checks.equal(
            _route_refusal(lambda: send_routes.do_markdown_send(markdown.name, {"confirm": True})),
            "send_held",
            "P5: so a mark-down over the same card is refused as held, not running, until the check says what happened (round 7, R6-4)",
        )
        _age_receipt(send_routes._receipts()[0][0])
        send_routes.do_live_check({})
        checks.equal(
            [claim.stamp for claim in Store().read().send_claims.live()],
            [],
            "P5: and the check past the wait releases the claim",
        )

    # ------------- P7 (B1, B2): a price the screen did not name, or whose live price moved
    with _case(checks, "P7: the live price moved"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        articuno_live(run_dir, portal)
        typed(ARTICUNO_SKU, "25.99")
        refused = _refusal_text_route(lambda: send_routes.do_send(
            {"runs": [run_dir.name], "confirm": True, "prices": named("25.99", "25.99")}
        ))
        checks.equal(
            (refused or ("", ""))[0],
            "price_refused",
            "P7: A NAMED PRICE WHOSE LIVE FIGURE MOVED SINCE THE SCREEN DREW IT IS REFUSED, by name",
        )
        checks.ok("$22.03" in (refused or ("", ""))[1], f"P7: naming the live price: {refused}")
        checks.equal(portal["rows"], [], "P7: and TCGplayer receives no row")
        sent = send_routes.do_send({"runs": [run_dir.name], "confirm": True})["send"]
        checks.equal(
            (sorted(portal_rows(portal)), sent["prices"]),
            ([DUNSPARCE_SKU], 0),
            "P7: AND A CORPUS ANSWER THE SCREEN DID NOT NAME NEVER RIDES: the send lists the "
            "Dunsparce and leaves the Articuno's price alone",
        )

    # ------------- a named price TCGplayer already shows is left out and named, not refused
    with _case(checks, "already live"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        articuno_live(run_dir, portal)
        typed(ARTICUNO_SKU, "22.03")
        sent = send_routes.do_send(
            {"runs": [run_dir.name], "confirm": True, "prices": named("22.03", "19.99")}
        )["send"]
        checks.equal(
            ([note["why"] for note in sent["prices_left"]], list(portal_rows(portal))),
            (["already"], [DUNSPARCE_SKU]),
            "A NAMED PRICE TCGPLAYER ALREADY SHOWS IS LEFT OUT AND NAMED, and the press still goes",
        )

    # ------------- N2: a price row on a card that sold out settles, named
    with _case(checks, "N2: sold out after the send"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        articuno_live(run_dir, portal)
        typed(ARTICUNO_SKU, "30.00")
        sent = send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {DUNSPARCE_SKU: 0}, "confirm": True,
             "prices": named("30.00", "22.03")}
        )["send"]
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
        _age_receipt(sent["stamp"])
        send_routes.do_live_check({})
        after = receipt(sent["stamp"])
        checks.equal(
            (after["state"], [row["sku"] for row in (after["price_check"] or {}).get("gone") or []]),
            ("checked", [ARTICUNO_SKU]),
            "N2: A PRICE ROW ON A CARD THAT SOLD OUT SETTLES, and names the card, never short for ever",
        )

    # ------------- S4: a rollback's answer is not proof
    with _case(checks, "S4: after a rollback"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
        portal["refuse"] = {"movetolive"}
        code = _route_refusal(lambda: send_routes.do_send({"runs": [run_dir.name], "confirm": True}))
        stamp = send_routes._receipts()[0][0]
        checks.equal(
            (code, receipt(stamp)["warning"]),
            ("send_rolled_back", "rolled_back"),
            "S4: A ROLLED-BACK PRESS IS `send_rolled_back`, never a retry, and it keeps a "
            "'check the Staged list' warning",
        )
        send_routes.do_dismiss(stamp, {})
        checks.equal(receipt(stamp)["warning"], None, "S4: until the owner dismisses it")

    # ------------- B3 and S4: a mark-down's rollback is named for what it is
    with _case(checks, "B3: a mark-down rolled back"), send_portal() as portal, isolated_home() as home:
        directory = _markdown_dir(home, "20260924-140000", "19.99")
        pipeline_routes._write_push(directory, {"upload_id": "u-9", "rows": 1, "accepted": 1})
        answer = pipeline_routes.do_markdown_rollback(directory.name, {"confirm": True})
        note = files.read_json(directory / send_routes.ROLLED_BACK_RECORD, {}) or {}
        checks.equal(
            (answer.get("check_staged"), note.get("live"), note.get("check_staged")),
            (True, False, True),
            "B3: A MARK-DOWN ROLLED BACK IS RECORDED AS NOT LIVE, AND 'CHECK THE STAGED LIST'",
        )

def check_send_review_r7(checks: Checks) -> None:
    """Round 7: the review of round 6 (R6-1 to R6-4) and the owner's ruling on R6-3, each red
    first on the round-6 build (9ee9b6e3).

    THE OWNER'S RULING, 2026-09-24 (R6-3): a new copy of a card already live carries Banchi's
    stored price, and TCGplayer lists every copy of one SKU at one price, so the live copies
    move with it. The BUTTON names every live copy that moves and its new price, and the press
    refuses a move it did not name. R6-1 (the orchestrator's call): the worklist names prices
    against the newest live export on disk, and a refusal carries the live price as data, so
    the screen can send again at the owner's price with the live price named.
    """
    checks.note("")
    checks.note("SEND REVIEW, ROUND 7 — live copies that move are named; a refusal carries data")

    cards = [(3, i, "Articuno", "161", None) for i in (1, 2, 3)]
    cards.append((3, 4, "Dunsparce", "120", "normal"))

    def typed(sku, price):
        book = corpus.Corpus.read()
        book.answers[sku] = corpus.Answer(value=price)
        book.write()

    def portal_rows(portal):
        return {
            row["ProductConditionId"]: (row["AddToQuantity"], row["MyPrice"]) for row in portal["rows"]
        }

    def refusal_of(fn):
        try:
            fn()
        except pipeline_routes.PipelineRefusal as caught:
            return caught
        return None

    # ------------- P11 (R6-3): a listing row moves live copies; the button must name the move
    with _case(checks, "P11: live copies move"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
        send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {ARTICUNO_SKU: 2, DUNSPARCE_SKU: 0}, "confirm": True}
        )
        portal["live"] = _live_export_priced({ARTICUNO_SKU: 2, DUNSPARCE_SKU: 0}, {ARTICUNO_SKU: "22.03"})
        portal["rows"].clear()
        typed(ARTICUNO_SKU, "19.99")
        refused = refusal_of(lambda: send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {DUNSPARCE_SKU: 0}, "confirm": True}
        ))
        notes = ((getattr(refused, "data", None) or {}).get("refused")) or []
        checks.equal(
            (getattr(refused, "code", None), [(n["sku"], n["why"], n["live"], n["price"], n["copies"]) for n in notes]),
            ("price_refused", [(ARTICUNO_SKU, "move_unnamed", "22.03", "19.99", 2)]),
            "P11: A NEW COPY THAT WOULD MOVE TWO LIVE COPIES TO A PRICE THE BUTTON DID NOT NAME "
            "IS REFUSED, and the refusal carries the live price and the new one as data",
        )
        checks.equal(portal["rows"], [], "P11: and TCGplayer receives no row")
        sent = send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {DUNSPARCE_SKU: 0}, "confirm": True,
             "moves": [{"sku": ARTICUNO_SKU, "price": "19.99", "copies": 2}]}
        )["send"]
        checks.equal(
            (portal_rows(portal).get(ARTICUNO_SKU), [(m["sku"], m["copies"], m["price"], m["was"]) for m in sent["moves"]]),
            (("1", "19.99"), [(ARTICUNO_SKU, 2, "19.99", "22.03")]),
            "P11: NAMED, THE NEW COPY CARRIES THE STORED PRICE, and the receipt records the two "
            "live copies it moves and from what",
        )

    # ------------- R6-1: a refused price carries the live price, and one press sends again
    with _case(checks, "R6-1: send again at the live price"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
        send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {DUNSPARCE_SKU: 0}, "confirm": True}
        )
        portal["live"] = _live_export_priced({ARTICUNO_SKU: 3, DUNSPARCE_SKU: 0}, {ARTICUNO_SKU: "22.03"})
        portal["rows"].clear()
        typed(ARTICUNO_SKU, "30.00")
        named = {"sku": ARTICUNO_SKU, "price": "30.00", "was": "25.99"}
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        try:
            status, body, _ = request(
                port, "POST", "/pipeline/send",
                payload={"runs": [run_dir.name], "quantities": {DUNSPARCE_SKU: 0}, "confirm": True,
                         "prices": [named]},
            )
        finally:
            httpd.shutdown()
            thread.join(timeout=5)
        error = json.loads(body or b"{}").get("error") or {}
        notes = (error.get("data") or {}).get("refused") or []
        checks.equal(
            (status, error.get("code"), [(n["sku"], n["why"], n["live"], n["price"]) for n in notes]),
            (409, "price_refused", [(ARTICUNO_SKU, "live_moved", "22.03", "30.00")]),
            "R6-1: THE REFUSAL CARRIES {sku, live, price} AS DATA on the wire, so the screen can "
            "say 'TCGplayer shows $22.03 now. Send $30.00?'",
        )
        sent = send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {DUNSPARCE_SKU: 0}, "confirm": True,
             "prices": [dict(named, was="22.03")]}
        )["send"]
        checks.equal(
            (portal_rows(portal), sent["prices"]),
            ({ARTICUNO_SKU: ("0", "30.00")}, 1),
            "R6-1: AND ONE PRESS WITH THE LIVE PRICE NAMED SENDS THE OWNER'S PRICE",
        )

    # ------------- R6-1: the worklist names what TCGplayer holds now, off the newest live export
    with _case(checks, "R6-1: the worklist's live price"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
        send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {DUNSPARCE_SKU: 0}, "confirm": True}
        )
        portal["live"] = _live_export_priced({ARTICUNO_SKU: 3, DUNSPARCE_SKU: 0}, {ARTICUNO_SKU: "22.03"})
        _age_receipt(send_routes._receipts()[0][0])
        send_routes.do_live_check({})
        work = pipeline_routes.do_pipeline_worklist([run_dir.name])
        rows = {row["sku"]: row for row in work["skus"]}
        live = rows.get(ARTICUNO_SKU, {}).get("live_now") or {}
        checks.equal(
            (live.get("price"), live.get("copies"), rows.get(ARTICUNO_SKU, {}).get("snap", {}).get("now")),
            ("22.03", 3, "25.99"),
            "R6-1: THE WORKLIST CARRIES TCGPLAYER'S PRICE FROM THE NEWEST LIVE EXPORT (22.03), not "
            "only the join's (25.99)",
        )

def check_schema_eleven_then_twelve(checks: Checks) -> None:
    """Two branches each took schema 11. Main's identity lane took it for `skus` and
    `cards.identity_source`. The send lane took it for `send_claims`, which is now 12.

    A store at 10 must pass through 11 and then 12. A store that main already moved to 11
    must still get `send_claims`, and keep its `skus` rows. Each case builds the older shape
    from a fresh store, stamps the older number, and lets the next ordinary read upgrade it.
    """
    def shape(store_path):
        conn = sqlite3.connect(store_path)
        try:
            stamp = conn.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()
            tables = {
                row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            views = {
                row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='view'")
            }
            columns = {row[1] for row in conn.execute("PRAGMA table_info(cards)").fetchall()}
            skus_rows = (
                conn.execute("SELECT COUNT(*) FROM skus").fetchone()[0] if "skus" in tables else None
            )
        finally:
            conn.close()
        return stamp, tables, views, columns, skus_rows

    checks.equal(
        db.SCHEMA_VERSION, 14,
        "the current schema is 14: skus at 11, send_claims at 12, the order key at 13 (D294), the price summary at 14 (D219)",
    )

    # --- a store at 10 has neither table -------------------------------------------------
    with isolated_home():
        capture_server.do_capture(capture_payload(1))
        store_path = str(files.inventory_dir() / "store.sqlite")
        conn = sqlite3.connect(store_path, isolation_level=None)
        try:
            conn.execute("DROP VIEW IF EXISTS sku_products")
            conn.execute("DROP VIEW IF EXISTS sku_printings")
            conn.execute("DROP TABLE IF EXISTS skus")
            conn.execute("DROP TABLE IF EXISTS send_claims")
            conn.execute("ALTER TABLE cards DROP COLUMN identity_source")
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('schema', '10')")
        finally:
            conn.close()
        stamp, tables, _views, columns, _rows = shape(store_path)
        checks.equal(
            (stamp, "skus" in tables, "send_claims" in tables, "identity_source" in columns),
            (("10",), False, False, False),
            "the fixture really is a schema-10 store",
        )
        Store().read()
        stamp, tables, views, columns, _rows = shape(store_path)
        checks.equal(
            (stamp, "skus" in tables, "send_claims" in tables, "identity_source" in columns,
             {"sku_products", "sku_printings"} <= views),
            ((str(db.SCHEMA_VERSION),), True, True, True, True),
            "a schema-10 store passes through 11 and then 12, and gains both tables",
        )
        checks.equal(
            sorted(Store().read().inventory.cards), ["1/1"], "and its card survives the upgrade"
        )

    # --- a store main already moved to 11 has `skus` and no `send_claims` ----------------
    with isolated_home():
        capture_server.do_capture(capture_payload(1))
        store_path = str(files.inventory_dir() / "store.sqlite")
        conn = sqlite3.connect(store_path, isolation_level=None)
        try:
            conn.execute("DROP TABLE IF EXISTS send_claims")
            conn.execute(
                "INSERT INTO skus (key, product_name, payload) VALUES ('7777', 'Venusaur', ?)",
                (json.dumps({"sku": "7777", "product_name": "Venusaur"}),),
            )
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('schema', '11')")
        finally:
            conn.close()
        stamp, tables, _views, _columns, rows = shape(store_path)
        checks.equal(
            (stamp, "skus" in tables, "send_claims" in tables, rows),
            (("11",), True, False, 1),
            "the fixture really is a schema-11 store from main, with one skus row",
        )
        Store().read()
        stamp, tables, _views, _columns, rows = shape(store_path)
        checks.equal(
            (stamp, "send_claims" in tables, rows),
            ((str(db.SCHEMA_VERSION),), True, 1),
            "a schema-11 store from main gains send_claims at 12 and keeps its skus row",
        )

    # --- a store the UX branch stamped 11 has `send_claims` and no `skus` ----------------
    # The UX branch took 11 for `send_claims` before the merge moved it to 12. Its stamp says
    # 11, and it is not main's 11. It must still get `skus`, the views and
    # `cards.identity_source`, or the first card write fails on the missing column.
    with isolated_home():
        capture_server.do_capture(capture_payload(1))
        store_path = str(files.inventory_dir() / "store.sqlite")
        conn = sqlite3.connect(store_path, isolation_level=None)
        try:
            conn.execute("DROP VIEW IF EXISTS sku_products")
            conn.execute("DROP VIEW IF EXISTS sku_printings")
            conn.execute("DROP TABLE IF EXISTS skus")
            conn.execute("ALTER TABLE cards DROP COLUMN identity_source")
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('schema', '11')")
        finally:
            conn.close()
        stamp, tables, _views, columns, _rows = shape(store_path)
        checks.equal(
            (stamp, "skus" in tables, "send_claims" in tables, "identity_source" in columns),
            (("11",), False, True, False),
            "the fixture really is the UX branch's schema-11 store: send_claims and no skus",
        )
        Store().read()
        stamp, tables, views, columns, _rows = shape(store_path)
        checks.equal(
            (stamp, "skus" in tables, "send_claims" in tables, "identity_source" in columns,
             {"sku_products", "sku_printings"} <= views),
            ((str(db.SCHEMA_VERSION),), True, True, True, True),
            "the UX branch's schema-11 store reaches 12 with skus, both views and "
            "cards.identity_source",
        )
        try:
            capture_server.do_capture(capture_payload(1))
            wrote = None
        except Exception as exc:  # the failure this case exists for is a sqlite error
            wrote = f"{type(exc).__name__}: {exc}"
        checks.equal(wrote, None, "and a card write on that store works")
        checks.equal(
            sorted(Store().read().inventory.cards), ["1/1", "1/2"],
            "and both cards are in the store",
        )

def check_send_review_r8(checks: Checks) -> None:
    """Round 8: the review of round 7 (R7-1, R7-3, R7-4), each red first on the round-7 build
    (19c3bc3e). A move of live copies under the floor is refused and never offered back; a move
    carries its count and the count must match; a live row with copies and no price moves."""
    checks.note("")
    checks.note("SEND REVIEW, ROUND 8 — a move's floor, its count, and a live row with no price")

    cards = [(3, i, "Articuno", "161", None) for i in (1, 2, 3)]
    cards.append((3, 4, "Dunsparce", "120", "normal"))

    def typed(sku, price):
        book = corpus.Corpus.read()
        book.answers[sku] = corpus.Answer(value=price)
        book.write()

    def refusal_of(fn):
        try:
            fn()
        except pipeline_routes.PipelineRefusal as caught:
            return caught
        return None

    def notes(refused):
        return [
            (n["sku"], n["why"], n["live"], n["price"], n["copies"])
            for n in ((getattr(refused, "data", None) or {}).get("refused") or [])
        ]

    def two_live(portal, run_dir, price):
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 0, DUNSPARCE_SKU: 0})
        send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {ARTICUNO_SKU: 2, DUNSPARCE_SKU: 0}, "confirm": True}
        )
        portal["live"] = _live_export_priced({ARTICUNO_SKU: 2, DUNSPARCE_SKU: 0}, {ARTICUNO_SKU: price})
        portal["rows"].clear()

    # ------------- R7-1: a move of live copies under the floor is refused, and is data
    with _case(checks, "R7-1: a move under the floor"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        two_live(portal, run_dir, "22.03")
        typed(ARTICUNO_SKU, "0.05")
        refused = refusal_of(lambda: send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {DUNSPARCE_SKU: 0}, "confirm": True,
             "moves": [{"sku": ARTICUNO_SKU, "price": "0.05", "copies": 2}]}
        ))
        checks.equal(
            (getattr(refused, "code", None), notes(refused)),
            ("price_refused", [(ARTICUNO_SKU, "below_floor", "22.03", "0.05", 2)]),
            "R7-1: A NAMED MOVE THAT WOULD TAKE TWO LIVE COPIES UNDER THE FLOOR IS REFUSED "
            "`below_floor`, as data",
        )
        checks.equal(portal["rows"], [], "R7-1: and TCGplayer receives no row")

    # ------------- R7-3: the button's count of live copies must be TCGplayer's
    with _case(checks, "R7-3: a move's count"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        two_live(portal, run_dir, "22.03")
        typed(ARTICUNO_SKU, "19.99")
        refused = refusal_of(lambda: send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {DUNSPARCE_SKU: 0}, "confirm": True,
             "moves": [{"sku": ARTICUNO_SKU, "price": "19.99", "copies": 1}]}
        ))
        checks.equal(
            (getattr(refused, "code", None), notes(refused)),
            ("price_refused", [(ARTICUNO_SKU, "move_count", "22.03", "19.99", 2)]),
            "R7-3: A MOVE NAMED AT ONE LIVE COPY WHERE TCGPLAYER HOLDS TWO IS REFUSED, with "
            "TCGplayer's count as data",
        )
        sent = send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {DUNSPARCE_SKU: 0}, "confirm": True,
             "moves": [{"sku": ARTICUNO_SKU, "price": "19.99", "copies": 2}]}
        )["send"]
        checks.equal(
            [(m["sku"], m["copies"]) for m in sent["moves"]],
            [(ARTICUNO_SKU, 2)],
            "R7-3: and named at TCGplayer's count, it sends",
        )

    # ------------- R7-4: a live row with copies and no price moves, and must be named
    with _case(checks, "R7-4: a live row with no price"), send_portal() as portal, isolated_home():
        run_dir, _ = seam_run(checks, cards)
        two_live(portal, run_dir, "")
        typed(ARTICUNO_SKU, "19.99")
        refused = refusal_of(lambda: send_routes.do_send(
            {"runs": [run_dir.name], "quantities": {DUNSPARCE_SKU: 0}, "confirm": True}
        ))
        checks.equal(
            (getattr(refused, "code", None), notes(refused)),
            ("price_refused", [(ARTICUNO_SKU, "move_unnamed", None, "19.99", 2)]),
            "R7-4: TWO LIVE COPIES WITH NO PRICE ARE A MOVE THE BUTTON MUST NAME, the safe side",
        )
        checks.equal(portal["rows"], [], "R7-4: and TCGplayer receives no row")

def check_run_match(checks: Checks) -> None:
    """Q4 of the flow interview: matching runs by itself when a reading finishes, and a problem
    becomes the run's next step. Against the stand-in portal's catalogue export.

    `POST /pipeline/runs/<name>/match` is what the screen calls when it sees a run reach the
    match step. What is asserted: a finished reading is matched with nobody pressing anything;
    a refusal is recorded as the run's `match_problem` and is NOT asked again by the next
    automatic call; the door's own press (`retry`) asks again; and a run that is not waiting
    for a match is left alone.
    """
    checks.note("")
    checks.note("RUN MATCH — matching runs by itself when the reading finishes (Q4)")
    cards = [(3, 1, "Dunsparce", "120/159", "normal"), (3, 2, "Articuno ex", "161/159", None)]

    def reading_done(hinted):
        """A run whose reading has finished: identified, collected, not yet matched."""
        run, _ = seam_run(checks, cards, join=False)
        path = run.directory / pipeline_routes.run_files.IDENTIFICATIONS
        payload = json.loads(path.read_text())
        for at, key in enumerate(sorted(payload["cards"])):
            payload["cards"][key].pop("set_hint", None)
            if at < hinted:
                payload["cards"][key]["set_hint"] = "SV09"
        path.write_text(json.dumps(payload))
        run.set(collected=True)
        return run

    def exports(portal):
        return [name for kind, name in portal["calls"] if kind == "POST" and name == "downloadexportcsv"]

    with _case(checks, "Q4: a finished reading matches by itself"), send_portal() as portal, \
            isolated_home():
        run = reading_done(hinted=len(cards))
        checks.equal(
            pipeline_routes._summary(run.directory)["phase"],
            "join",
            "a finished reading waits for its match",
        )
        answer = pipeline_routes.do_run_match(run.name, {})
        checks.ok(
            answer["ran"] and answer["ok"],
            f"THE MATCH RAN WITH NOBODY PRESSING: {answer.get('problem')}",
        )
        checks.equal(len(exports(portal)), 1, "it fetched the catalogue once")
        checks.ok(
            answer["summary"]["phase"] != "join" and answer["summary"]["match_problem"] is None,
            f"and the run moved on to its next step: {answer['summary']['phase']}",
        )
        again = pipeline_routes.do_run_match(run.name, {})
        checks.equal(
            (again["ran"], again["reason"], len(exports(portal))),
            (False, "not_waiting", 1),
            "a run that is not waiting for a match is left alone",
        )

    with _case(checks, "Q4: a problem becomes the next step"), send_portal() as portal, \
            isolated_home():
        run = reading_done(hinted=0)
        answer = pipeline_routes.do_run_match(run.name, {})
        problem = answer["summary"]["match_problem"] or {}
        checks.equal(
            (answer["ok"], problem.get("code")),
            (False, "export_needs_set_hint"),
            "A CARD WITH NO SET is the run's next step, by name",
        )
        checks.equal(
            pipeline_routes._summary(run.directory)["match_problem"]["code"],
            "export_needs_set_hint",
            "and every read of the run says so, until it is fixed",
        )
        calls = len(portal["calls"])
        standing = pipeline_routes.do_run_match(run.name, {})
        checks.equal(
            (standing["ran"], standing["reason"], len(portal["calls"])),
            (False, "problem_stands", calls),
            "THE NEXT AUTOMATIC CALL DOES NOT ASK AGAIN over a problem that stands",
        )
        run = runs.open_run(run.directory)
        path = run.directory / pipeline_routes.run_files.IDENTIFICATIONS
        payload = json.loads(path.read_text())
        for key in payload["cards"]:
            payload["cards"][key]["set_hint"] = "SV09"
        path.write_text(json.dumps(payload))
        fixed = pipeline_routes.do_run_match(run.name, {"retry": True})
        checks.ok(
            fixed["ok"] and fixed["summary"]["match_problem"] is None,
            "and the door's own press asks again, and the fixed run matches",
        )

    with _case(checks, "Q4: a signed-out session is the next step"), send_portal() as portal, \
            isolated_home():
        run = reading_done(hinted=len(cards))
        portal["signed_out"] = True
        answer = pipeline_routes.do_run_match(run.name, {})
        checks.equal(
            (answer["summary"]["match_problem"] or {}).get("code"),
            "tcg_session_expired",
            "A SIGN-IN THAT HAS EXPIRED is the run's next step, never a silent stall",
        )

def _refusal_code_transport(rows, *, listing: bool) -> Optional[str]:
    try:
        tcg_import._check(rows, listing=listing)
    except tcg_import.FetchRefusal as refusal:
        return refusal.code
    return None

def check_live_markdown_guards(checks: Checks) -> None:
    """The Live tab's four rules (the owner's rulings, 2026-09-26), each red under its own
    mutation: a fresh read before any send, no mark-down for a card with no market price, a
    dollar cap on top of the percentage, and a Singles / Sealed filter the apply holds the
    screen to. And the mark-down send checks each price against the fresh read (D273)."""
    checks.note("")
    checks.note("LIVE TAB — fresh read, no-market skip, dollar cap, sealed filter")

    now = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
    long_ago = (now - timedelta(days=30)).isoformat()

    def listing(sku, asking, market, condition="Near Mint"):
        return {
            tcgcsv.SKU_COLUMN: sku,
            tcgcsv.NAME_COLUMN: sku,
            tcgcsv.CONDITION_COLUMN: condition,
            tcgcsv.LIVE_QUANTITY_COLUMN: "1",
            tcgcsv.PRICE_COLUMN: asking,
            tcgcsv.MARKET_PRICE_COLUMN: market,
        }

    rows = [
        listing("SINGLE", "100.0000", "80.00"),
        listing("NO-MARKET", "6000.0000", ""),
        listing("SEALED", "349.9900", "300.00", tcgcsv.SEALED_CONDITION),
    ]

    def plan(cap=None):
        return reprice.plan(
            rows,
            owned_since={row[tcgcsv.SKU_COLUMN]: long_ago for row in rows},
            now=now,
            days=7,
            rule="undercut:10",
            basis=reprice.BASIS_ASKING,
            floor=Decimal("0.25"),
            cap=cap,
        )

    # ------------------------------------------------------------- no market, no mark-down
    uncapped = plan()
    skipped = {c.sku: c.skip for group in uncapped.skipped.values() for c in group}
    checks.equal(
        skipped.get("NO-MARKET"),
        reprice.NO_MARKET,
        "SKIP NO-MARKET CARDS: a card with no market price is refused `no_market`, even on the "
        "asking-price basis that could price it",
    )
    checks.ok(
        "NO-MARKET" not in {c.sku for c in uncapped.rows},
        "and it is not in the mark-down set, so no rule lowers it",
    )

    # -------------------------------------------------------------------- the dollar cap
    proposed = {c.sku: c.proposed for c in uncapped.rows}
    checks.equal(proposed.get("SINGLE"), Decimal("90.00"), "with no cap, 10% off $100 is $90")
    capped = {c.sku: c.proposed for c in plan(Decimal("5.00")).rows}
    checks.equal(
        capped.get("SINGLE"),
        Decimal("95.00"),
        "A $5 CAP CLAMPS THE RULE: 10% off $100 would take $10, so the proposal is $95",
    )
    checks.equal(plan(Decimal("5.00")).asked.get("cap"), "5.00", "and the read records its cap")
    back = reprice.read_back(
        [{tcgcsv.SKU_COLUMN: "SINGLE", tcgcsv.PRICE_COLUMN: "80.00"}],
        {"SINGLE": "100.0000"},
        floor=Decimal("0.25"),
    )
    checks.equal(
        [e.sku for e in back.edits],
        ["SINGLE"],
        "THE CAP IS THE RULE'S ONLY (\"Rule only\"): a price typed $20 under the live one goes as "
        "typed, whatever the read's cap",
    )

    # ------------------------------------ an earlier answer goes out only when it is higher
    back = reprice.read_back(
        [
            {tcgcsv.SKU_COLUMN: "LOWER", tcgcsv.PRICE_COLUMN: "80.00"},
            {tcgcsv.SKU_COLUMN: "HIGHER", tcgcsv.PRICE_COLUMN: "120.00"},
            {tcgcsv.SKU_COLUMN: "TYPED-NOW", tcgcsv.PRICE_COLUMN: "70.00"},
            {tcgcsv.SKU_COLUMN: "RULE", tcgcsv.PRICE_COLUMN: "90.00"},
        ],
        {"LOWER": "100.0000", "HIGHER": "100.0000", "TYPED-NOW": "100.0000", "RULE": "100.0000"},
        floor=Decimal("0.25"),
        earlier={
            "LOWER": Decimal("80.00"),
            "HIGHER": Decimal("120.00"),
            "TYPED-NOW": Decimal("75.00"),
            "RULE": Decimal("90.00"),
        },
        proposed={"RULE": Decimal("90.00")},
    )
    checks.equal(
        ({e.sku: e.refusal for e in back.refused}, sorted(e.sku for e in back.edits)),
        ({"LOWER": reprice.EARLIER_LOWER}, ["HIGHER", "RULE", "TYPED-NOW"]),
        "\"IF THE PRICE I'VE TYPED IS HIGHER YEA\": a lower answer stored before the read is "
        "refused, a higher one goes, a price written after the read goes, and the rule's own "
        "price goes",
    )
    checks.raises(reprice.InvalidCap, lambda: reprice.check_cap("0"), "a cap of $0 is refused")

    # ------------------------------------------------------------------ the sealed rule
    checks.equal(
        [reprice.is_sealed(row) for row in rows],
        [False, False, True],
        "SEALED IS THE `Unopened` CONDITION, and nothing else",
    )
    checks.equal(
        [cmd_reprice._surveyed(c, "offered").get("sealed") for c in uncapped.rows],
        [reprice.is_sealed(c.row) for c in uncapped.rows],
        "and the survey carries it per row, so the Live tab can filter by it",
    )

    # ------------------------------------------------------------------ a fresh read
    checks.equal(
        [
            reprice.read_is_fresh((now - timedelta(hours=23)).isoformat(), now),
            reprice.read_is_fresh((now - timedelta(hours=25)).isoformat(), now),
            reprice.read_is_fresh(None, now),
        ],
        [True, False, False],
        "A READ IS FRESH FOR A DAY, and one nothing can date is not fresh",
    )
    with send_portal() as portal, isolated_home() as home:
        stale = _markdown_dir(home, "20260926-100000", at=long_ago)
        portal["live"] = _live_export_bytes({ARTICUNO_SKU: 1})
        checks.equal(
            _route_refusal(lambda: send_routes.do_markdown_send(stale.name, {"confirm": True})),
            "read_stale",
            "REQUIRE A FRESH READ: a mark-down from a read a month old refuses",
        )
        checks.equal(portal["calls"], [], "and it refuses before TCGplayer is asked anything")

        # THE APPLY REFUSES A STALE READ TOO, so "Download the file instead" cannot write one.
        manual = _markdown_dir(home, "20260926-100100", at=long_ago)
        (manual / cmd_reprice.IMPORT).unlink()
        files.write_json(manual / cmd_reprice.MANIFEST, {"at": long_ago, "asked": {}, "skus": {}})
        worklist = pipeline_routes._write_edits(manual, [{"sku": ARTICUNO_SKU, "price": "19.99"}])
        said = command(checks, "reprice", "apply", str(worklist), "--write", exits=1)
        checks.ok(
            "more than a day ago" in said and not (manual / cmd_reprice.IMPORT).exists(),
            "and `reprice apply --write` over a stale read writes no file",
            said,
        )

    # AN EARLIER, LOWER ANSWER, THROUGH THE COMMAND: `_apply` reads the corpus's own stamps.
    with isolated_home() as home:
        fresh_at = master.now()
        directory = _markdown_dir(home, "20260926-100200", at=fresh_at)
        (directory / cmd_reprice.IMPORT).unlink()
        files.write_json(directory / cmd_reprice.MANIFEST, {"at": fresh_at, "asked": {}, "skus": {}})
        # BACKDATED BY HAND, WHICH IS ONLY EVER SETUP HERE: there is no real path that writes
        # an answer dated in 2026-01 without the wall clock actually being there, so seeding
        # "an old answer already sat in the corpus" has no route to go through.
        book = corpus.Corpus.read()
        book.answers[ARTICUNO_SKU] = corpus.Answer(value="19.99", at="2026-01-01T00:00:00.000+00:00")
        book.write()
        worklist = pipeline_routes._write_edits(directory, [{"sku": ARTICUNO_SKU, "price": "19.99"}])
        said = command(checks, "reprice", "apply", str(worklist), "--write")
        checks.ok(
            f"[{reprice.EARLIER_LOWER}]" in said and not (directory / cmd_reprice.IMPORT).exists(),
            "an answer stored before the read, lower than the live price, writes no file",
            said,
        )

        # A DIFFERENT PRICE, WRITTEN AFTER THE READ THROUGH THE REAL SAVE PATH. The case this
        # replaces built `corpus.Answer(at=master.now())` BY HAND, which never runs
        # `stamp_answers` at all and so cannot tell a real "after this read" from a fake one.
        # `do_pricing_corpus_write` is what `#/pricing` actually calls.
        seeded = dict(pipeline_routes.do_pricing_corpus()["corpus"], skus={ARTICUNO_SKU: {"value": "20.00"}})
        pipeline_routes.do_pricing_corpus_write({"corpus": seeded})
        checks.ok(
            str(corpus.Corpus.read().answers[ARTICUNO_SKU].at or "") >= fresh_at,
            "and `stamp_answers` dates a CHANGED answer to now, which is after the read",
        )
        worklist = pipeline_routes._write_edits(directory, [{"sku": ARTICUNO_SKU, "price": "20.00"}])
        said = command(checks, "reprice", "apply", str(worklist), "--write")
        checks.ok(
            (directory / cmd_reprice.IMPORT).exists(),
            "and a genuinely new price, saved through the real route after the read, is written",
            said,
        )

    # THE ACTUAL DEFECT: A PRICE RETYPED, UNCHANGED, THROUGH THE REAL SAVE PATH. `stamp_answers`
    # keeps the OLD `at` here on purpose (its own ratchet rule, for `priced_recently`) — so
    # retyping, on this visit, a price already stored from days ago leaves the timestamp
    # pointing at the past, and `_apply`'s `earlier` map still calls it "earlier". The owner's
    # ruling, 2026-09-26: "if the price i've typed is higher yea" — but this price is retyped,
    # not raised, and is refused for a reason ("typed before this read") that is false this
    # time. Only naming the SKU as typed THIS VISIT (`typed`, D273's `typedHere`) fixes it,
    # because the caller is the one witness the timestamp cannot be.
    with isolated_home() as home:
        old_at = "2026-01-01T00:00:00.000+00:00"
        book = corpus.Corpus.read()
        book.answers[ARTICUNO_SKU] = corpus.Answer(value="19.99", at=old_at)
        book.write()

        fresh_at = master.now()
        directory = _markdown_dir(home, "20260926-100250", at=fresh_at)
        (directory / cmd_reprice.IMPORT).unlink()
        files.write_json(directory / cmd_reprice.MANIFEST, {"at": fresh_at, "asked": {}, "skus": {}})

        # THE RETYPE, THROUGH THE REAL SAVE PATH — same value, so `stamp_answers` keeps `old_at`.
        seeded = dict(pipeline_routes.do_pricing_corpus()["corpus"], skus={ARTICUNO_SKU: {"value": "19.99"}})
        pipeline_routes.do_pricing_corpus_write({"corpus": seeded})
        checks.equal(
            corpus.Corpus.read().answers[ARTICUNO_SKU].at,
            old_at,
            "AN UNCHANGED RETYPE KEEPS THE OLD `at`, through the real save path",
        )

        refused = pipeline_routes.do_markdown_apply(
            directory.name, {"edits": [{"sku": ARTICUNO_SKU, "price": "19.99"}], "write": True}
        )
        checks.ok(
            not refused["wrote"] and f"[{reprice.EARLIER_LOWER}]" in refused["console"],
            "WITHOUT NAMING THE VISIT: the price the owner just retyped is refused for a false "
            "reason, because the timestamp alone cannot see this visit",
            refused["console"],
        )

        rescued = pipeline_routes.do_markdown_apply(
            directory.name,
            {
                "edits": [{"sku": ARTICUNO_SKU, "price": "19.99"}],
                "write": True,
                "typed": [ARTICUNO_SKU],
            },
        )
        checks.ok(
            rescued["ok"] and rescued["wrote"],
            "NAMING THE VISIT (`typed`, `Pricing.tsx`'s `typedHere`) RIDES: the caller is the "
            "witness the timestamp cannot be",
            rescued["console"],
        )

    # ------------------------------------------- each price, checked against the fresh read
    for label, live, code in (
        ("TCGplayer moved the price", _live_export_priced({ARTICUNO_SKU: 1}, {ARTICUNO_SKU: "30.00"}), "price_refused"),
        ("TCGplayer already shows it", _live_export_priced({ARTICUNO_SKU: 1}, {ARTICUNO_SKU: "19.99"}), "nothing_to_send"),
        ("TCGplayer holds no copy", _live_export_bytes({ARTICUNO_SKU: 0}), "nothing_to_send"),
    ):
        with send_portal() as portal, isolated_home() as home:
            directory = _markdown_dir(home, "20260926-110000")
            portal["live"] = live
            checks.equal(
                _route_refusal(
                    lambda directory=directory: send_routes.do_markdown_send(directory.name, {"confirm": True})
                ),
                code,
                f"THE FRESH READ JUDGES EACH PRICE: {label}, so the mark-down refuses ({code})",
            )
            checks.equal(
                [name for kind, name in portal["calls"] if kind == "POST"],
                [],
                f"{label}: and nothing is pushed",
            )
            checks.equal(
                [claim.stamp for claim in Store().read().send_claims.live()],
                [],
                f"{label}: and its claim is released",
            )

    # --------------------------------------------------------------- the sealed filter
    with isolated_home() as home:
        directory = _markdown_dir(home, "20260926-120000")
        edits = [{"sku": ARTICUNO_SKU, "price": "19.99"}]
        checks.equal(
            _route_refusal(
                lambda: pipeline_routes.do_markdown_apply(directory.name, {"edits": edits, "kind": "sealed"})
            ),
            "kind_mismatch",
            "THE SEALED FILTER HOLDS: a list filtered to Sealed may not carry a single's price",
        )
        checks.equal(
            _route_refusal(
                lambda: pipeline_routes.do_markdown_apply(directory.name, {"edits": edits, "kind": "singles"})
            ),
            None,
            "and a list filtered to Singles carries it",
        )

def check_publish_lag(checks: Checks) -> None:
    """`reconcile --live` will not settle a SKU this pipeline just published (D273).

    THE DEFECT IS A TIMESTAMP THAT TELLS THE TRUTH ABOUT THE WRONG THING. `Export From Live`
    is not read-your-writes — measured 2026-09-06, forty seconds after a confirmed publish it
    still served the pre-publish price — and the reading is dated by the FILE'S mtime, which
    is when it was fetched. So a stale body arrives carrying a fresh date,
    `Listing.live_reading` prefers it over the store, and the figure this pipeline just set is
    overwritten by the one it replaced. Nothing inside the document can reveal that.

    WHAT IS ASSERTED IS THE SELECTION, NOT THE CLOCK. A test that published and then waited
    would be a test of TCGplayer's convergence time, which is unmeasured and not ours. These
    assert what `published_recently` picks out of receipts on disk, which is the whole input
    the reconcile's skip runs on.
    """
    checks.note("")
    checks.note("PUBLISH LAG — the SKUs a reconcile must not settle from the export")

    with isolated_home() as home:
        root = home / "inventory" / "markdowns"

        def markdown(stamp, sku, published_at, price="1.00"):
            directory = root / stamp
            directory.mkdir(parents=True)
            tcgcsv.write_csv(
                directory / cmd_reprice.IMPORT,
                (tcgcsv.SKU_COLUMN, tcgcsv.PRICE_COLUMN),
                [{tcgcsv.SKU_COLUMN: sku, tcgcsv.PRICE_COLUMN: price}],
            )
            (directory / "push.json").write_text(
                json.dumps({"upload_id": stamp, "rows": 1, "accepted": 1, "messages": [],
                            "pushed_at": published_at, "published_at": published_at}),
                encoding="utf-8",
            )
            return directory

        now = datetime(2026, 9, 6, 20, 0, 0, tzinfo=timezone.utc)
        markdown("20260906-195900", "SKU-JUST-NOW", "2026-09-06T19:59:00+00:00")
        markdown("20260906-120000", "SKU-HOURS-AGO", "2026-09-06T12:00:00+00:00")

        # PUSHED BUT NEVER PUBLISHED CONTRIBUTES NOTHING, and this is the case most likely to
        # be broken by a careless edit: staging changes nothing a buyer or an export can see,
        # so holding its SKUs back would refuse a settlement for no reason at all.
        staged = root / "20260906-195800"
        staged.mkdir(parents=True)
        tcgcsv.write_csv(
            staged / cmd_reprice.IMPORT,
            (tcgcsv.SKU_COLUMN, tcgcsv.PRICE_COLUMN),
            [{tcgcsv.SKU_COLUMN: "SKU-STAGED-ONLY", tcgcsv.PRICE_COLUMN: "2.00"}],
        )
        (staged / "push.json").write_text(
            json.dumps({"upload_id": "x", "rows": 1, "accepted": 1, "messages": [],
                        "pushed_at": "2026-09-06T19:58:00+00:00", "published_at": None}),
            encoding="utf-8",
        )

        recent = cmd_reprice.published_recently(now=now)
        checks.equal(
            sorted(recent),
            ["SKU-JUST-NOW"],
            "only a SKU published INSIDE the window is held back — not one published hours "
            "ago, and not one merely staged",
        )

        # AN UNREADABLE STAMP IS TREATED AS RECENT. The point of the guard is to refuse a
        # figure it cannot vouch for, and a receipt it cannot date is exactly that — failing
        # open here would settle from an export that may well be stale.
        broken = markdown("20260906-195700", "SKU-BAD-STAMP", "not-a-date")
        checks.ok(
            "SKU-BAD-STAMP" in cmd_reprice.published_recently(now=now),
            "and a receipt whose stamp will not parse is held back rather than settled",
        )
        shutil.rmtree(broken)

        # A HALF-DELETED MARKDOWN MUST NOT TAKE THE RECONCILE DOWN. This runs inside a
        # settlement the operator asked for.
        gone = markdown("20260906-195600", "SKU-NO-FILE", "2026-09-06T19:59:30+00:00")
        (gone / cmd_reprice.IMPORT).unlink()
        checks.equal(
            sorted(cmd_reprice.published_recently(now=now)),
            ["SKU-JUST-NOW"],
            "and a receipt whose import file is gone contributes nothing rather than raising",
        )

        # THE WINDOW IS A PARAMETER SO THE RULE CAN BE TESTED WITHOUT WAITING ON THE CONSTANT.
        checks.equal(
            sorted(cmd_reprice.published_recently(now=now, window_s=24 * 3600)),
            ["SKU-HOURS-AGO", "SKU-JUST-NOW"],
            "and widening the window reaches the older publish, so the cut is the window and "
            "not something else",
        )

    checks.ok(
        cmd_reprice.PUBLISH_LAG_S >= 60,
        "the window is at least a minute — the measured staleness was ~40s, so anything "
        "shorter would be a guard that does not cover the one reading it was built for",
    )

def check_pricing_route(checks: Checks) -> None:
    """`GET /pipeline/runs/<name>/pricing` — free, read-only, two files from one moment.

    THE ONE THING WORTH ASSERTING HARDEST IS A SHAPE THAT LOOKS LIKE AN ACCIDENT AND IS NOT:
    `_RUN_STEP_RE` matches `^/pipeline/runs/<name>/([a-z]+)$`, so a **POST** to this same
    path reaches `do_pipeline_step` with `step="pricing"` and is refused against `FREE_STEPS`.
    That refusal is correct — pricing is a read and has no step — and it is asserted rather
    than left to be discovered by whoever next wonders why a POST here 404s.
    """
    checks.note("")
    checks.note("PRICING ROUTE — the table and the answers, in one read")

    cards = [(3, 1, "Articuno", "161", None)]

    with isolated_home():
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        try:
            bare = runs.create("unjoined")
            bare.set(capture_dir="/tmp/nowhere")
            status, body, _ = request(
                port, "GET", f"/pipeline/runs/{bare.directory.name}/pricing"
            )
            checks.equal(
                (status, error_code(body)),
                (409, "pricing_not_written"),
                "a run that has not been joined refuses IN ITS OWN CODE and names the "
                "command that writes the file — every run made before D86 is in this state, "
                "so the screen has to be able to say `re-join this run` rather than break",
            )

            run_dir, _ = seam_run(checks, cards)
            status, body, _ = request(
                port, "GET", f"/pipeline/runs/{run_dir.directory.name}/pricing"
            )
            payload = json.loads(body)
            checks.equal(
                (
                    status,
                    payload["run"],
                    [s["sku"] for s in payload["pricing"]["skus"]],
                    payload["decisions"]["rule"],
                ),
                (200, run_dir.directory.name, [ARTICUNO_SKU], "match"),
                "and a joined run answers with the table AND this run's answers together — "
                "two fetches could straddle a re-join, and a table describing one join "
                "beside answers written against another is a screen pricing the wrong cards",
            )
            checks.equal(
                len(payload["pricing"]["skus"][0]["row"]),
                len(tcgcsv.CANONICAL_HEADER),
                "every export cell travels VERBATIM — the owner asked for all the data from "
                "the CSV in front of them while they price, and a subset chosen here is a "
                "decision about what matters taken by the wrong file",
            )
            # WHEN THE TABLE WAS WRITTEN, WHICH IS THE ONLY AGE A PRICE CAN HONESTLY CARRY.
            # `#/inventory`'s card panel draws `$5.47 · read 2 days ago` off this, and the
            # second half is not decoration: `join` is free, re-runnable and routinely pointed
            # at a REFRESHED export, so two cards on one shelf can carry prices read a week
            # apart and a bare figure claims a currency the file cannot support.
            #
            # BACKDATED FIRST, AND THAT IS THE WHOLE OF THE CASE. Asserting the field against
            # the file's live mtime is VACUOUS here: `seam_run` joins immediately before the
            # request, so a route that stamped `time.time()` instead would answer the same
            # integer and pass. That version was written, mutated to a clock, and observed
            # PASSING — which is the shape this repo has paid for before at the multi-game
            # prompt seam. Backdating the file by a week separates the two answers, so what is
            # checked is that the number describes THIS TABLE rather than THIS REQUEST.
            #
            # The failure it forbids is invisible from the screen: a price whose age resets to
            # `read today` every time the panel is opened is a stale figure wearing a fresh
            # stamp, which is worse than no stamp at all.
            table_file = run_dir.path(runs.PRICING)
            backdated = int(table_file.stat().st_mtime) - 7 * 86400
            os.utime(table_file, (backdated, backdated))
            status, body, _ = request(
                port, "GET", f"/pipeline/runs/{run_dir.directory.name}/pricing"
            )
            checks.equal(
                (status, json.loads(body).get("written_at")),
                (200, backdated),
                "and it says WHEN the table was written, off that file's own mtime — a week-old "
                "table reads a week old, where a clock read at request time would call every "
                "price fresh forever",
            )

            # THE ANSWER IS THE CORPUS'S, AND A LATER RUN DOES NOT HAVE TO BE REMINDED OF IT.
            # `remembered_sub_threshold` walked up to five sibling run directories looking for
            # the newest answer, because each run held its own — a label offered so the
            # operator did not have to re-decide, which D9 then forbade defaulting. It is gone
            # from every payload now (D86, amended 2026-09-02): with one document there is
            # nothing to remember — the answer IS the policy, it has a default (D9 amended),
            # and the next run is priced by it without a screen offering anything.
            book = corpus.Corpus.read()
            book.sub_threshold = "floor"
            book.write()
            later, _ = seam_run(checks, cards)
            checks.equal(
                corpus.Corpus.read().policy_for(later.directory.name)["sub_threshold"],
                "floor",
                "A LATER RUN IS PRICED BY THE STANDING ANSWER, with no per-run copy of it. "
                "The sibling-walk that used to offer it as a label is gone with the thing it "
                "worked around — eight files that could disagree about one question",
            )

            status, body, _ = request(
                port,
                "POST",
                f"/pipeline/runs/{run_dir.directory.name}/pricing",
                payload={},
            )
            checks.equal(
                (status, error_code(body)),
                (404, "no_such_step"),
                "a POST to the same path is refused as a STEP rather than reaching this "
                "handler — the step pattern admits any lowercase word, so `pricing` matches "
                "it and is turned away by the free-steps list, which is correct and is the "
                "kind of overlap that is only obvious once somebody has asserted it",
            )
        finally:
            httpd.shutdown()
            thread.join(timeout=5)

def check_corpus_revision(checks: Checks) -> None:
    """`PUT /pricing` refuses a write that is behind the file on disk.

    WHY THE GUARD EXISTS. That route replaces `inventory/prices.json` WHOLESALE, which is D86's
    design and is right: the screen round-trips every key it does not understand. It had no
    concurrency guard because the operator was the only writer, and `pkmnscan reprice` is a
    second one — it re-prices every stale SKU at once, so a `#/pricing` tab holding a snapshot
    from mount would revert an entire sweep on the next keystroke, with no error anywhere, on
    the one file in this product that holds money.

    WHY THIS CASE EXISTS, WHICH IS A DIFFERENT QUESTION. The guard shipped with no harness
    coverage at all. The only test naming `corpus_moved` was `app/tests/pricing.spec.ts`, and
    it is a `page.route()` mock fulfilling a hand-written 409 body — it asserts the SCREEN
    reacts to a conflict and never executes `_corpus_revision` or the comparison in
    `server/pipeline_routes.py`. A stub that answers 409 is green whether or not the server
    would ever send one.

    THE SECOND WRITER GOES AROUND THE ROUTE, AND THAT IS THE POINT OF THIS CASE. As first
    merged, every "another writer moved the file" step here went through
    `do_pricing_corpus_write` — the same route the guard lives in. But the writer the guard
    exists for never touches that route: D86's amendment names it as a NON-ROUTE writer moving
    `inventory/prices.json` under an open `#/pricing` tab, and that writer is
    `pkmnscan prices adopt --write` (`cli/cmd_prices.py`'s `folded.write()` ->
    `pipeline/corpus.py:Corpus.write()` -> `store/files.py:write_json()`). A reprice sweep is
    the same call. Neither imports `server/pipeline_routes.py`.

    WHY THE DISTINCTION HAS TEETH RATHER THAN BEING TIDINESS. `_corpus_revision` re-reads and
    re-hashes the file on every call. The obvious future optimisation is to cache the digest
    the route last wrote, so a growing file is not re-hashed on every GET — and under that
    cache a route-only version of this case stays GREEN while the real case silently stops
    refusing: the route writes, the route updates its own cache, a tab's stale revision still
    differs, the refusal fires. The CLI writes, the cache does not move, `current` equals what
    the tab offers, and the tab's wholesale write reverts the entire sweep. That is exactly
    the defect the guard exists to prevent. Measured before this was changed: with that cache
    added to `_corpus_revision`, the route-only case passed 6 of 6.

    THE ASSERTIONS ARE MUTUALLY REINFORCING ON PURPOSE, because most of them are individually
    vacuous, and no mutation here is caught by the assertion that looks like it is about
    revisions. Against a `_corpus_revision` that returned a CONSTANT, the first three still
    pass — a constant is truthy, is not a key of the document, and is trivially equal to
    itself — and what fails is the operator's own save (it answers with the revision it was
    given) and the refusal. Against one that returned a COUNTER, the refusal still fires and
    what fails is the idempotent re-save and the step after it. Against the digest cache
    above, only the refusal fails, and only because the writer before it is the CLI's.

    AN ABSENT REVISION IS ALLOWED, AND THAT IS NOT A HOLE. It means "did not read one", which
    is the terminal user editing the file and putting it back. The guard is for a client that
    DID read one and is now behind — the only case that can silently destroy another writer's
    work.
    """
    checks.note("")
    checks.note("CORPUS REVISION — the stale-write refusal on PUT /pricing")

    with isolated_home():
        corpus.Corpus().write()
        first = pipeline_routes.do_pricing_corpus()
        checks.ok(
            bool(first.get("revision")),
            "`GET /pricing` carries a revision BESIDE the document. Inside it, the screen's "
            "identity-compared `dirty` would see it — the oscillation `_corpus_revision`'s own "
            "docstring records the design against",
        )
        checks.ok(
            "revision" not in first["corpus"],
            "and it is NOT a key of the corpus itself, so nothing round-trips it into the file",
        )

        # THE REVISION IS THE FILE'S OWN DIGEST, so an IDEMPOTENT write does not move it — and
        # that is the better semantic than a counter: a client is stale only when the content
        # it holds actually differs from what is on disk, not merely when somebody else wrote.
        # THIS IS THE ONLY ASSERTION HERE THAT A COUNTER FAILS.
        idempotent = (
            "a write that changes nothing does not move the revision — it is a digest of the "
            "file, not a counter, so re-saving an unchanged document is never a conflict"
        )
        # CAUGHT RATHER THAN LET FLY, because a counter does not fail the comparison below —
        # it never reaches it. The revision moves between the read and the write, so the guard
        # refuses the operator's own unchanged re-save and this case dies in a traceback that
        # names a line rather than a claim. The refusal IS the finding, so it is reported as
        # one.
        try:
            same = pipeline_routes.do_pricing_corpus_write(
                {"corpus": first["corpus"], "revision": first["revision"]}
            )
        except pipeline_routes.PipelineRefusal as refused:
            checks.ok(
                False,
                idempotent,
                f"re-saving the unchanged document was refused `{refused.code}` — the "
                f"revision moved without the file changing",
            )
        else:
            checks.equal(same["revision"], first["revision"], idempotent)

        # THE OPERATOR'S OWN SAVE, which is the step that used to double as the second writer
        # and no longer does. It is kept for two reasons. It is the only place the RESPONSE to
        # a legitimate write is looked at, which is what tells a working digest apart from a
        # constant. And it is what leaves the tab holding a revision the ROUTE issued —
        # `app/src/Pricing.tsx` assigns `revision.current = receipt.revision` off every write
        # receipt — so the stale press below quotes that, not the one from mount, which is the
        # value a cached digest would still agree with.
        moved = dict(first["corpus"])
        moved["skus"] = {DUNSPARCE_SKU: {"value": "4.50"}}
        advances = (
            "a write that CHANGES the document answers with the new revision, so the next "
            "save is not refused for being the one that landed"
        )
        # `held` IS WHAT THE TAB IS HOLDING, and it defaults to the revision from mount so the
        # steps below still run and report when this one is refused. CAUGHT FOR THE SAME
        # REASON AS THE ONE ABOVE: a revision that moves on its own refuses this write too —
        # the read it quotes is one write old — and a legitimate change made from a fresh read
        # being refused is a finding, not a crash.
        held = first["revision"]
        try:
            landed = pipeline_routes.do_pricing_corpus_write(
                {"corpus": moved, "revision": first["revision"]}
            )
        except pipeline_routes.PipelineRefusal as refused:
            checks.ok(
                False,
                advances,
                f"a change written against the revision just read was refused "
                f"`{refused.code}` — nothing else had written",
            )
        else:
            checks.ok(landed["revision"] != first["revision"], advances)
            held = landed["revision"]

        # NOW THE SECOND WRITER MOVES THE FILE, AND IT DOES NOT GO THROUGH THE ROUTE. This is
        # `cli/cmd_prices.py`'s `folded.write()` and `cmd_reprice`'s sweep — `Corpus.write()`
        # onto `store/files.py:write_json`, the same three calls, neither of which imports
        # `server/pipeline_routes.py`. See this case's own header for why the distinction is
        # the whole point.
        swept = dict(first["corpus"])
        swept["skus"] = {DUNSPARCE_SKU: {"value": "4.05"}}
        corpus.Corpus.parse(swept).write()
        checks.equal(
            corpus.Corpus.read().answers[DUNSPARCE_SKU].value,
            "4.05",
            "a NON-ROUTE writer moved the file — `prices adopt --write`'s own call, made "
            "here the way that command makes it. Asserted before the refusal below so that a "
            "failure there names the guard rather than a fixture that quietly wrote nothing",
        )

        # THE INLINE FORM, because `refusal` catches `capture_server.BadRequest` and the
        # pipeline routes raise their own class — the seam its own header argues for.
        #
        # THE DOCUMENT SENT IS `moved`, WHICH IS WHAT THE TAB ALREADY SAVED, so this press is
        # not an unusual one: it is the screen writing back the document it holds. Landing it
        # would put the file back at `moved`'s exact bytes — `write_json` serialises with
        # `indent=2, sort_keys=True`, so a revert is byte-identical and the digest returns to
        # `held`. The sweep would be gone with nothing anywhere reading differently afterwards,
        # which is why the refusal has to happen BEFORE the write rather than be detectable
        # after it.
        label = (
            "and the write that would REVERT it is refused. This is the exact press a "
            "`#/pricing` tab makes on its next keystroke after a reprice has run — wholesale, "
            "against a revision the ROUTE issued, over a file only the CLI has touched since"
        )
        try:
            pipeline_routes.do_pricing_corpus_write({"corpus": moved, "revision": held})
            checks.ok(False, label, "it accepted the stale write")
        except pipeline_routes.PipelineRefusal as refused:
            checks.equal(refused.code, "corpus_moved", label)

        after = pipeline_routes.do_pricing_corpus_write({"corpus": first["corpus"]})
        checks.ok(
            after["ok"],
            "and a write carrying NO revision still lands: absent means 'did not read one', "
            "which is a person editing the file by hand",
        )

        # ------------------------------------- the answer is DATED, and only when it changed
        #
        # `Answer.at` WAS WRITTEN IN ONE PLACE IN THIS REPO AND READ IN ONE (D103). `reprice
        # apply` set it; that command's ratchet read it. So `priced_recently` meant "marked
        # down recently" while D100 claimed it meant *"a card the operator hand-priced on
        # #/pricing yesterday is not stale"* — which it never did, because the screen has
        # never stamped anything.
        #
        # BOTH DIRECTIONS, AND THE SECOND IS THE ONE THAT MATTERS. A one-directional "the
        # answer got an `at`" assertion is passed by the naive fix — stamping every answer on
        # every save — and this route replaces the WHOLE document on every debounced keystroke,
        # so that fix moves every answer's date to now continuously and reads the entire corpus
        # as `priced_recently` forever. The ratchet inverted into a permanent refusal, with
        # nothing on screen to see.
        book = dict(first["corpus"])
        book["skus"] = {DUNSPARCE_SKU: {"value": "7.00"}, ARTICUNO_SKU: {"value": "8.00"}}
        pipeline_routes.do_pricing_corpus_write({"corpus": book})
        dated = corpus.Corpus.read().answers[DUNSPARCE_SKU].at
        checks.ok(
            bool(dated),
            "A PRICE WRITTEN FROM THE SCREEN IS DATED, which is what makes D100's ratchet "
            "claim true rather than aspirational",
        )

        book["skus"] = {DUNSPARCE_SKU: {"value": "7.00"}, ARTICUNO_SKU: {"value": "9.00"}}
        pipeline_routes.do_pricing_corpus_write({"corpus": book})
        settled = corpus.Corpus.read().answers
        checks.equal(
            settled[DUNSPARCE_SKU].at,
            dated,
            "AND AN UNCHANGED ANSWER KEEPS THE DATE IT HAD. This is the assertion the naive "
            "blanket stamp fails, and the only one that does",
        )
        checks.ok(
            settled[ARTICUNO_SKU].at and settled[ARTICUNO_SKU].at != dated
            or settled[ARTICUNO_SKU].value == "9.00",
            "while the answer that moved is re-dated",
        )

        # `.50` AND `0.50` ARE ONE ANSWER, which is D86's own rule for comparing them and has
        # to hold here too: `#/pricing`'s price field is a text input, so a figure round-tripped
        # through it comes back spelled differently and identical in money. Re-dating on that
        # would make every visit to the screen a markdown refusal the next morning.
        book["skus"] = {DUNSPARCE_SKU: {"value": "7.0"}, ARTICUNO_SKU: {"value": "9.00"}}
        pipeline_routes.do_pricing_corpus_write({"corpus": book})
        checks.equal(
            corpus.Corpus.read().answers[DUNSPARCE_SKU].at,
            dated,
            "the same money spelled differently is not a new answer, and is not re-dated",
        )

        # AND A `no_market_data` SEED IS NEVER DATED. `cli/cmd_join.py` writes one for every
        # card the catalogue could not price — the ABSENCE of an answer, and what makes
        # `blocking` refuse an emit. Dating it would make an UNPRICED card read as priced, in
        # the one direction that costs money.
        book["skus"] = {
            DUNSPARCE_SKU: {"value": "7.0"},
            ARTICUNO_SKU: {"value": None, "channel": "unknown"},
        }
        pipeline_routes.do_pricing_corpus_write({"corpus": book})
        checks.ok(
            not corpus.Corpus.read().answers[ARTICUNO_SKU].at,
            "an `unknown`-channel seed carries no date — it is the absence of an answer, and "
            "the ratchet reads `channel == 'price'` for exactly this reason",
        )

def check_pricing_clear(checks: Checks) -> None:
    """The mass-clear: what it removes, what it refuses to touch, and the way back.

    WHY THE FEATURE EXISTS, IN THE OPERATOR'S WORDS: *"I also need a clear claims on pricing
    (after several emits a lot of pricing is pre typed but stale and there's no way to mass
    clear)"*. Measured on their store, 2026-09-12: **269 of 407 typed prices — 66% — were
    answered on 2026-09-07** and were still pre-filling the field on every row they appear on.

    AND WHY IT IS A PRESS RATHER THAN A RULE. Offered an expiry — a typed price ageing out by
    itself after N days — they refused it: *"Just give me a mass-clear button."* Nothing in this
    case exercises a timer, because there is none to exercise: the window is an argument to one
    call and the store carries no memory of it.

    THE THREE REFUSALS ARE THE POINT AND THE CLEAR IS ALMOST INCIDENTAL. A mass-delete over the
    one file in this product that holds money is only safe if the set it may reach is exactly
    the set of TYPED PRICES, and each of the three things it must not reach fails differently:

    - A HOLD IS A JUDGEMENT (D86) and removing one puts the card back into the next `emit`.
      The owner's store carries 23, every one `bullish`.
    - A `channel != "price"` ANSWER IS THE ABSENCE OF ONE. `pipeline/decisions.py:blocking`
      reads that table to refuse an emit, so clearing one makes an unpriced card read as
      though nothing were owed on it.
    - AN UNDATED ANSWER CANNOT BE PLACED BY AN AGE FILTER. 20 of the owner's carry no `at`.

    THE SCOPE IS NOT A PREDICATE, WHICH IS THE ASSERTION THAT SURVIVES A CLIENT REWRITE. The
    route takes the SKUs a screen is looking at only to narrow what is considered; whether each
    may go is re-derived here from the file. So the case names a hold in the scope explicitly:
    a build that trusted the client's list would clear it, and every other assertion in this
    function would still pass.

    THE WAY BACK IS ASSERTED ON PROVENANCE AND NOT ONLY ON PRESENCE. A restore that re-dated
    every answer to now would put the values back and read as a store-wide re-pricing on the
    next markdown survey — D103's ratchet inverted by the one press whose entire job is to
    change nothing. `at` coming back byte-identical is the only assertion that catches it.
    """
    checks.note("")
    checks.note("PRICING CLEAR — the mass-clear, its three refusals, and the restore")

    with isolated_home():
        # A FIXTURE SHAPED LIKE THE OWNER'S FILE: old typed prices, fresh ones, a hold, an
        # `unknown`-channel seed, and one price carrying no date at all.
        #
        # BOTH STAMPS ARE RELATIVE TO THE MOMENT THE TEST RUNS, AND THAT IS THE FIX FOR A
        # DEFECT THIS FILE ONCE HAD. Written 2026-09-12 as the two literal absolute stamps
        # `"2026-09-07T06:50:31.891+00:00"` and `"2026-09-12T03:42:00.000+00:00"` — the
        # owner's own real measurement that day, 269 of 407 typed prices five days stale —
        # the second one meant "answered today" only on the day it was written. `older_than_days`
        # compares against `master.now()`, which never stops moving, so by 2026-09-17 the
        # "answered today" seed had drifted to five days old itself and the `older_than_days: 3`
        # case below swept it up with the two genuinely old ones. `old` is five days back,
        # matching the owner's own five-day measurement; `new` is six hours back — inside the
        # three-day window on every future day, and never zero so it cannot straddle midnight
        # in any timezone the suite runs in.
        _now = datetime.now(timezone.utc)
        old = (_now - timedelta(days=5)).isoformat(timespec="milliseconds")
        new = (_now - timedelta(hours=6)).isoformat(timespec="milliseconds")
        book = corpus.Corpus()
        book.answers = {
            "1000": corpus.Answer(value="4.50", at=old),
            "1001": corpus.Answer(value="0.29", at=old),
            "1002": corpus.Answer(value="9.99", at=new),
            "1003": corpus.Answer(value="1.25"),  # no `at` — predates the stamp
            "1004": corpus.Answer(value={"withheld": "bullish"}, at=old),
            "1005": corpus.Answer(value=None, channel="unknown", at=old),
        }
        book.write()

        read = pipeline_routes.do_pricing_corpus()
        block = read["clearable"]
        checks.equal(
            sorted(block["days"]),
            ["1000", "1001", "1002", "1003"],
            "`GET /pricing` names the four TYPED PRICES as clearable and neither the hold nor "
            "the `unknown` seed — the set is exactly `stamp_answers`' own inclusion rule",
        )
        checks.equal(block["holds"], 1, "and it counts the hold it is leaving alone")
        checks.equal(
            block["unknown"], 1, "and the `unknown` seed, so the sheet can say both figures"
        )
        checks.ok(
            block["days"]["1003"] is None,
            "an answer with no `at` reports a null age and never a zero — a zero would read as "
            "written today, which is the direction that makes a stale price look fresh",
        )
        checks.ok(
            "clearable" not in read["corpus"],
            "and the block is in the ENVELOPE, never in the document: `PUT /pricing` replaces "
            "the file wholesale and round-trips keys it does not know, so a derived block "
            "inside it would be written into inventory/prices.json",
        )

        # ---------------------------------------------------- the scope is not a predicate
        named = pipeline_routes.do_pricing_clear(
            {"skus": ["1004", "1005"], "revision": read["revision"]}
        )
        checks.equal(
            named["count"],
            0,
            "a scope naming ONLY a hold and an `unknown` seed clears nothing. A build that "
            "trusted the client's list instead of re-deriving would delete both here, and "
            "every other assertion in this case would still pass",
        )
        checks.equal(named["holds"], 1, "the hold is reported rather than silently skipped")
        checks.equal(
            len(corpus.Corpus.read().answers), 6, "and nothing left the file"
        )

        # ------------------------------------------------------------ the age filter selects
        preview = pipeline_routes.do_pricing_clear(
            {"skus": [], "revision": pipeline_routes._corpus_revision()}
        )
        checks.equal(
            preview["count"], 0, "an EMPTY scope is a real scope and clears nothing at all"
        )

        stale = pipeline_routes.do_pricing_clear({"older_than_days": 3})
        checks.equal(
            sorted(stale["cleared"]),
            ["1000", "1001"],
            "`older_than_days` takes the two answered five days ago and leaves the one "
            "answered today",
        )
        checks.equal(
            stale["undated"],
            1,
            "and it LEAVES the undated answer, counted rather than swept in on a guess that "
            "it must be old (D103 refuses inventing a date for one of these)",
        )
        checks.equal(
            stale["cleared"]["1000"]["at"],
            old,
            "every cleared answer comes back with the date it was typed on — the way back is "
            "the ANSWERS and not a list of SKUs, or the undo would be a re-type",
        )

        left = corpus.Corpus.read()
        checks.equal(sorted(left.answers), ["1002", "1003", "1004", "1005"], "the file agrees")
        checks.ok(
            left.answers["1004"].is_hold,
            "THE HOLD IS STILL STANDING after a store-wide clear — D86's judgement with a "
            "reason on it, which no window and no scope in this route can reach",
        )
        checks.equal(
            left.answers["1005"].channel,
            "unknown",
            "and so is the `unknown` seed `pipeline/decisions.py:blocking` reads to refuse "
            "an emit",
        )

        # --------------------------------------------------------------------- the way back
        typed_again = corpus.Corpus.read()
        typed_again.answers["1000"] = corpus.Answer(value="7.77", at=new)
        typed_again.write()

        back = pipeline_routes.do_pricing_restore({"answers": stale["cleared"]})
        checks.equal(
            back["restored"], ["1001"], "the restore puts back the answer nothing has re-typed"
        )
        checks.equal(
            back["skipped"],
            [{"sku": "1000", "reason": "answered_since"}],
            "and REFUSES the one answered again since the clear, naming it and why — an undo "
            "that quietly overwrote newer work would be worse than one that refuses",
        )
        after = corpus.Corpus.read()
        checks.equal(
            after.answers["1000"].value, "7.77", "the newer answer is the one kept"
        )
        checks.equal(
            after.answers["1001"].at,
            old,
            "AND THE RESTORED ANSWER KEEPS ITS ORIGINAL DATE. Stamping it would make the undo "
            "of a clear read as a store-wide re-pricing on the next markdown survey, refusing "
            "every restored SKU `priced_recently` (D103's ratchet)",
        )

        # ------------------------------------------------------------- the stale-write guard
        label = (
            "a clear offered against a revision the file has moved past is refused, which is "
            "the guard `PUT /pricing` has had since D86 and the reason a second writer of this "
            "file is allowed at all"
        )
        try:
            pipeline_routes.do_pricing_clear({"revision": read["revision"]})
            checks.ok(False, label, "it accepted the stale clear")
        except pipeline_routes.PipelineRefusal as refused:
            checks.equal(refused.code, "corpus_moved", label)

        checks.ok(
            pipeline_routes.do_pricing_clear({})["ok"],
            "and an ABSENT revision still lands — 'did not read one', which is the terminal "
            "user, exactly as the PUT allows",
        )

def check_pricing_labels(checks: Checks) -> None:
    """`pricing.json`'s position labels are re-rendered on every read, and the file never moves.

    THE SAME DEFECT D58 FIXED FOR THE REVIEW QUEUE, ON THE SCREEN THAT PRICES. `cli/cmd_join.py:
    _pricing_table` writes `{"box", "index", "label"}` per matched SKU and `cli/runs.py` makes a
    run an immutable input, so that label is a snapshot of a rendering — and D56 states the rule
    one register up: never write down an answer nobody can correct; join it when it is read.
    `capture_server._queue_row` has obeyed it since D58 and this route did not, so a copy sold
    after the join went on drawing `Box 3, Section 1, Card 1` at a slot whose occupant had
    closed up behind it, under a photograph `photoUrl` addresses BY SLOT — the caption naming
    one card and the picture showing another.

    BOTH MOVEMENTS ARE ASSERTED, BECAUSE THEY FAIL SEPARATELY AND A BUILD CAN GET EITHER ONE
    ALONE. A sale moves the CARDS; a divider edit moves the SECTIONS. `Position.layout` maps the
    dividers into the same counting space as the slots precisely so the two compose, and a
    re-render that consulted the store for one and not the other would pass half of this block.

    THE FILE IS ASSERTED AS BYTES, NOT AS A FIELD, AND THAT IS D54'S LESSON RATHER THAN
    THOROUGHNESS. D58 kept the stored label on disk deliberately — nothing already written
    moves, and every run made before this lands is corrected the next time a screen opens it —
    so "the route re-rendered" and "the route rewrote the run directory" are two different
    builds, and only a byte comparison tells them apart. A field check is satisfied identically
    by a handler that quietly rewrote the table it read.

    THE BASELINE CASE IS THE ONE THAT LOOKS LIKE PADDING AND IS NOT. Before anything departs,
    the re-rendered label and the stored one are the same string — the two spaces coincide until
    the first departure, which is what makes this additive and what makes the three cases after
    it about a real difference rather than about a renderer that answers differently for its own
    reasons.

    TWO CONTRACTS ARE CHECKED AT `_position_label` RATHER THAN THROUGH THE ROUTE, and the reason
    is that neither is reachable from a joined run without breaking the store to get there: the
    pooled branch (a game whose cards a join reaches but a box walk skips) and the no-view
    branch (a box `box_views` will not answer for, which is the store-wide degrade
    `check_place_neighbors` already drives). What they assert is the door, not the wiring — the
    wiring is the three cases above.
    """
    checks.note("")
    checks.note("PRICING LABELS — the stored string is never served (D58)")

    def positions(name: str) -> dict:
        """`box/index` -> the label the ROUTE answers, for the one SKU this run matches."""
        table = pipeline_routes.do_pipeline_pricing(name)["pricing"]
        row = next(s for s in table["skus"] if s["sku"] == ARTICUNO_SKU)
        return {f"{p['box']}/{p['index']}": p["label"] for p in row["positions"]}

    def written(run_dir) -> dict:
        """The same map, off the FILE — what `join` froze and what may never be served."""
        table = json.loads(run_dir.path(runs.PRICING).read_text("utf-8"))
        row = next(s for s in table["skus"] if s["sku"] == ARTICUNO_SKU)
        return {f"{p['box']}/{p['index']}": p["label"] for p in row["positions"]}

    with isolated_home():
        # Two sections over four cards — dividers at 1 and 3 — so a divider has cards on both
        # sides of it and a departure in front of one can be told from a departure behind it.
        capture_server.do_create_box({"box": 3})
        run_dir, _ = seam_run(
            checks, [(3, at, "Articuno", "161", None) for at in (1, 2, 3, 4)],
            sections={3: [1, 3]},
        )
        name = run_dir.directory.name
        joined_bytes = run_dir.path(runs.PRICING).read_bytes()

        # The box was created with no name, so it carries its stored default, `Box 1`
        # (D259): the first box in this store.
        at_join = {
            "3/1": "Box 1, Section 1, Card 1",
            "3/2": "Box 1, Section 1, Card 2",
            "3/3": "Box 1, Section 2, Card 1",
            "3/4": "Box 1, Section 2, Card 2",
        }
        checks.equal(
            written(run_dir),
            at_join,
            "`join` writes four positions under one SKU and a label for each — D7's "
            "aggregation seen from the pricing table, and the fixture the rest of this "
            "block moves the store out from under",
        )
        checks.equal(
            positions(name),
            at_join,
            "and with nothing departed and no divider touched the route answers the SAME "
            "four strings — the counting space and the index space coincide until the first "
            "departure, which is what makes re-rendering additive rather than a second "
            "numbering system arriving on the screen",
        )

        # --- a copy leaves after the join -------------------------------------------------
        capture_server.do_mark_sold(3, 1, {})
        checks.equal(
            positions(name),
            {
                "3/1": "Box 1, Section 1, Card 1",
                "3/2": "Box 1, Section 1, Card 1",
                "3/3": "Box 1, Section 2, Card 1",
                "3/4": "Box 1, Section 2, Card 2",
            },
            "SELL A COPY AND THE CARD BEHIND IT TAKES THE NUMBER IT VACATED (D58), while the "
            "sold copy's caption names the place it LEFT (D259). The "
            "two strings are equal on purpose: the screen tells them apart by the departed "
            "mark it draws off a null `slot`, never by a word or a store key in the string",
        )
        checks.equal(
            run_dir.path(runs.PRICING).read_bytes(),
            joined_bytes,
            "and the run directory is untouched to the byte — D58 keeps the stored label on "
            "disk and serves none of it, so nothing already written moves and no re-join is "
            "needed to correct a run made before this",
        )

        # --- a divider moves after the join -----------------------------------------------
        # COUNT SPACE, because that is what `do_put_box` takes (D58): "section 2 starts at the
        # 3rd card on hand". Three cards remain — 2, 3 and 4 — so this puts the divider in
        # front of index 4, one card further back than it was.
        capture_server.do_put_box(3, {"sections": [1, 3]})
        checks.equal(
            positions(name),
            {
                "3/1": "Box 1, Section 1, Card 1",
                "3/2": "Box 1, Section 1, Card 1",
                "3/3": "Box 1, Section 1, Card 2",
                "3/4": "Box 1, Section 2, Card 1",
            },
            "MOVE A DIVIDER AND EVERY CAPTION BEHIND IT FOLLOWS — 3/3 crosses from section 2 "
            "into section 1 and 3/4 becomes the section's first card. This is the failure D58 "
            "MEASURED at 15 of 92 review entries: a label describing a sectioning that is no "
            "longer in the plastic, on the screen somebody prices from",
        )
        checks.equal(
            run_dir.path(runs.PRICING).read_bytes(),
            joined_bytes,
            "and the file is STILL byte-identical after the second movement — the route "
            "composes and never writes back, which a field comparison could not tell from a "
            "handler quietly rewriting the table it had just read (D54's lesson)",
        )

        # --- the two branches that are doors rather than wiring ---------------------------
        inventory = Store().read().inventory
        views = resolve.box_views(inventory)
        checks.equal(
            pipeline_routes._position_label(views, inventory, 9, 1),
            None,
            "a box `box_views` will not answer for — deleted out from under the run, or the "
            "store-wide degrade — answers NULL rather than an index-space label. A bare "
            "`BoxView()` would render `Box 9, Section 1, Card 1` in the numbering D58 "
            "replaced, silently, beside three captions drawn in the other one",
        )

        capture_server.do_capture(capture_payload(5, game="pokemon_code"))
        pooled = Store().read().inventory
        answer = pipeline_routes._position_label(
            resolve.box_views(pooled), pooled, 5, 1
        )
        checks.ok(
            answer is not None and "Section" not in answer and answer.endswith(" · 5/1"),
            "and a POOLED copy is named by the pooled fact and its store key, never by a "
            "section — `pokemon_code` is `located: False` AND `catalogued: True`, so its "
            "cards do reach a join and did land in this table wearing a label D24 says may "
            "never be printed for them (`place_text`, not `Position.label`)",
            f"answered {answer!r}",
        )

def check_box_views_bounded(checks: Checks) -> None:
    """`cli/resolve.py:box_views(inventory, boxes=...)` — the bounded
    branch a caller uses when its own positions already name a small set of boxes, and the
    unbounded default every existing caller still gets.

    THE TWO BRANCHES DEGRADE DIFFERENTLY, ON PURPOSE (the function's own docstring). The
    unbounded branch degrades the WHOLE result to `{}` the instant any record's position
    will not coerce; the bounded branch degrades ONE box at a time, because a caller naming
    `boxes={3, 7, 12}` already knows exactly what it is asking about and a corrupt box 7
    should not cost it box 3 and box 12's views too.
    """
    checks.note("")
    checks.note("BOX_VIEWS BOUNDED — a caller that already knows which boxes it wants")

    with isolated_home():
        capture_server.do_create_box({"box": 1, "sections": [1]})
        capture_server.do_create_box({"box": 2, "sections": [1]})
        capture_server.do_create_box({"box": 3, "sections": [1]})
        for box in (1, 2, 3):
            for _ in range(2):
                capture_server.do_capture(capture_payload(box))

        inventory = Store().read().inventory
        unbounded = resolve.box_views(inventory)
        bounded = resolve.box_views(inventory, boxes={1, 3})

        checks.equal(
            sorted(bounded), [1, 3], "the bounded call answers ONLY for the boxes named"
        )
        checks.equal(
            bounded[1], unbounded[1], "and agrees with the unbounded call on box 1"
        )
        checks.equal(
            bounded[3], unbounded[3], "and agrees with the unbounded call on box 3"
        )
        checks.ok(
            2 not in bounded,
            "a box NOT in `boxes` is absent from the bounded result even though the "
            "unbounded call would include it",
        )

        # --- a corrupt INDEX in one requested box degrades only that box -------------------
        # (`box` itself stays readable, which is what a bounded `select(box=n)` query can
        # still see — a record whose own `box` column is unreadable is a separate, named gap
        # in `box_views`'s own docstring, not what this case exercises.)
        with Store().write() as snapshot:
            snapshot.inventory.cards["3/1"].index = "not-a-number"
        degraded = resolve.box_views(Store().read().inventory, boxes={1, 3, 99})
        checks.ok(
            1 in degraded and 3 not in degraded,
            "box 3's own corrupt index degrades box 3 alone — box 1, also requested, still "
            "answers, which is a genuine deviation from the store-wide branch's "
            "all-or-nothing degrade",
            f"degraded keys were: {sorted(degraded)!r}",
        )
        checks.ok(
            99 not in degraded,
            "a requested box that holds no on-hand card at all is simply absent, never a "
            "refusal",
        )

def check_withholding(checks: Checks) -> None:
    """A withheld SKU writes no row, moves no count, and is still FINDABLE (D86).

    THE OWNER ASKED THE QUESTION THIS SECTION ANSWERS. Shown that a held card would keep
    `state: captured` and carry no `sku`, they said: "Wait i want to be able to find it, why
    can't it be emitted?" It can. `cli/cmd_emit.py` had one `continue` doing two jobs —
    skipping the identity write and the `pushed` bump together — which was correct only while
    "reached a file" and "we know what this is" meant the same thing. A withhold is the first
    thing that splits them.

    So the three facts below are asserted together, because the value of each depends on the
    other two: no import row, no `pushed`, and the card knows what it is.
    """
    checks.note("")
    checks.note("WITHHOLDING — no row, no count, still findable")

    cards = [
        (3, 1, "Dunsparce", "120", "normal"),
        (3, 2, "Articuno", "161", None),
    ]

    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        # THE HOLD IS THE CORPUS'S AND OUTLIVES THE RUN (D86).
        book = corpus.Corpus.read()
        book.sub_threshold = "floor"
        book.answers[ARTICUNO_SKU] = corpus.Answer(
            value={
                "withheld": "bullish",
                "watch_above": "30.00",
                "note": "holding for rotation",
            }
        )
        book.write()

        said = command(checks, "emit", str(run_dir.directory))
        listed = tcgcsv.read_export(run_dir.path(runs.IMPORT_MERGED))
        checks.equal(
            [row[tcgcsv.SKU_COLUMN] for row in listed.rows],
            [DUNSPARCE_SKU],
            "A WITHHELD SKU WRITES NO IMPORT ROW, and the SKU beside it still does — a hold "
            "that emptied the file would be a hold nobody could tell from a broken emit",
        )

        inventory = Store().read().inventory
        held_card = inventory.get("3/2")
        checks.equal(
            (held_card.state, held_card.sku, held_card.condition),
            (master.IDENTIFIED, ARTICUNO_SKU, "Near Mint Holofoil"),
            "AND ITS CARD STILL KNOWS WHAT IT IS. The identity is a fact about the physical "
            "object that the join established; nothing about withholding it makes that fact "
            "less true, and a card carrying no `sku` is invisible to GET /search and every "
            "SKU-keyed surface in the product",
        )
        checks.equal(
            inventory.listings.get(ARTICUNO_SKU),
            None,
            "AND NO COUNT MOVED — not even an empty record. `pushed` means a CSV was written "
            "and none was; `cli/resolve.py:_committed_keys` reads `pushed + staged` back as "
            "`committed`, so a count moved here would make the next run treat a card it never "
            "listed as already spoken for",
        )
        checks.ok(
            "withheld" in said and ARTICUNO_SKU in said,
            "and `emit` NAMES the hold as it commits the file — the moment a person can "
            "still change their mind is the moment it is worth saying, which is why this is "
            "a warning rather than a refusal",
        )

        # --- the watch, on the next join -------------------------------------------------
        said = command(
            checks, "join", str(run_dir.directory), "--export", str(run_dir.path("export.csv"))
        )
        checks.ok(
            "WATCH" not in said,
            "a watch set ABOVE the market says nothing — an alert that fires on every join "
            "is an alert nobody reads",
        )

        book = corpus.Corpus.read()
        book.answers[ARTICUNO_SKU].value["watch_above"] = "1.00"
        book.write()
        said = command(
            checks, "join", str(run_dir.directory), "--export", str(run_dir.path("export.csv"))
        )
        checks.ok(
            "WATCH" in said and "Articuno" in said and "$1.00" in said,
            "and one the market has passed is reported BY NAME on the run — `join` is free, "
            "re-runnable and pointed at a refreshed export, which is the only moment a price "
            "has moved and the only moment a watch has anything to say",
        )

        checks.equal(
            corpus.Corpus.read().answers[ARTICUNO_SKU].value,
            {"withheld": "bullish", "watch_above": "1.00", "note": "holding for rotation"},
            "and the hold ROUND-TRIPS through the re-join unchanged — reason, watch and note. "
            "`join` rewrites this file on every run, so a hold that lost its note would lose "
            "it on the first free command the operator pressed",
        )

        # --- a re-emit that HAS something new to say (D54) --------------------------------
        #
        # THE CASE THAT STOPS THE FIX BEING "EMIT ONCE, EVER". The block above proves a
        # no-op re-emit leaves the file alone; on its own, that assertion is satisfied just
        # as well by an emitter that refuses every second press. Lifting a hold is the
        # ordinary reason to emit again, and what must then be written is the DELTA — the
        # copies not already sent — because TCGplayer's Import to Staged ADDS quantity, so a
        # file repeating already-imported rows double-stages them. That is Gate B's recorded
        # 37-copy defect, and it is why a re-emit may not simply rewrite the whole file.
        book = corpus.Corpus.read()
        del book.answers[ARTICUNO_SKU]
        book.write()
        command(
            checks, "join", str(run_dir.directory), "--export", str(run_dir.path("export.csv"))
        )
        freed = command(checks, "emit", str(run_dir.directory))

        delta = tcgcsv.read_export(run_dir.path(runs.IMPORT_MERGED))
        checks.equal(
            [row[tcgcsv.SKU_COLUMN] for row in delta.rows],
            [ARTICUNO_SKU],
            "A RE-EMIT WRITES WHAT HAS NOT BEEN SENT, AND ONLY THAT. Dunsparce went in the "
            "first emit and its copies are at `pushed`; re-writing its row would import "
            "three copies a second time",
        )
        checks.equal(
            sorted(runs.open_run(run_dir.directory).emitted_skus),
            sorted([DUNSPARCE_SKU, ARTICUNO_SKU]),
            "AND THE RECORD IS THE UNION ACROSS BOTH EMITS, not the last delta. `reconcile` "
            "reports in BOTH directions against this list, so a record holding only the "
            "second emit would put Dunsparce in `rows_without_cards` — reconcile accusing "
            "something else of writing a row it wrote itself",
        )
        checks.equal(
            runs.open_run(run_dir.directory).emitted["emits"],
            2,
            "and the record counts the emits that wrote a row, so a later reader can tell a "
            "run that was emitted once from one that was worked over several sittings",
        )
        checks.ok(
            "next: import" in freed,
            "and THIS re-emit does tell the operator to import, because this one wrote "
            "something — the no-op branch is the one that stays quiet",
            freed,
        )


CHECKS = (
    check_markdown,
    check_markdown_floor,
    check_markdown_lens,
    check_markdown_push,
    check_send_guard,
    check_send_press,
    check_send_hazards,
    check_send_review_r3,
    check_send_review_r4,
    check_send_review_r5,
    check_send_review_r6,
    check_send_review_r7,
    check_send_review_r8,
    check_live_markdown_guards,
    check_schema_eleven_then_twelve,
    check_run_match,
    check_publish_lag,
    check_withholding,
    check_pricing_route,
    check_corpus_revision,
    check_pricing_clear,
    check_pricing_labels,
    check_box_views_bounded,
)
