"""T7 group: copy listing, order resolver and ledger, order screen, walk plan, order fetch.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import ast
import base64
import json
import hashlib
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import envfile

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Tuple
from harness.tests import Checks
from cli import resolve, runs
from pipeline import join, orders, tcgcsv
# `pipeline.skus`, aliased — this module's own `skus` name would collide with
# `store.skus`'s `Skus`/`SkuRow` classes imported right below, and both are used by
# `_seed_sku_table` (identity-follows-sku.md §4.2's review round: a review answer now
# refuses a SKU the `skus` table does not already hold, so fixtures that answer a
# hand-built candidate seed the table first, through the real fold).
from pipeline import skus as sku_pipeline
from server import capture_server, order_transport
from store import db, files, master
# `orders` is already `pipeline.orders` above. The store's ledger is a DIFFERENT module
# — the resolver computes and stores nothing, this one persists — so it takes an alias
# rather than shadowing the name half this file's order cases are written against.
from store import orders as order_store
from store.session import Store
from harness.tests.t7.common import (
    ARTICUNO_SKU,
    DUNSPARCE_SKU,
    FIXTURE_EXPORT,
    _refusal_text,
    answers,
    capture_payload,
    command,
    entry,
    identifications_for,
    isolated_home,
    refusal,
    seam_run,
    store_tables,
    stored_payloads,
    write_export,
)


def write_staged(path, quantities):
    """An Export From Staged: the seam rows, with `Add to Quantity` set per SKU.

    `Add to Quantity` is the column `emit` wrote and the only one that can carry a STAGED
    quantity. `Total Quantity` is deliberately set to a DIFFERENT number by every caller
    below, so a command reading the wrong column cannot pass.
    """
    source = tcgcsv.read_export(FIXTURE_EXPORT)
    by_sku = source.by_sku()
    rows = []
    for sku, quantity in quantities.items():
        rows.append(
            dict(
                by_sku[sku],
                **{
                    tcgcsv.QUANTITY_COLUMN: str(quantity),
                    tcgcsv.LIVE_QUANTITY_COLUMN: "97",
                },
            )
        )
    tcgcsv.write_csv(path, source.header, rows)
    return Path(path)


def orders_with_picks() -> dict:
    """`GET /orders` with real `picks` merged back in, for tests written against the combined
    shape the route answered before 2026-09-16's two-tier split.

    `do_orders()` now answers `picks: []` on every line — decorating a `place` for every
    candidate copy of every unfulfilled order was 52% of that route's wall time for a buyer
    nobody had opened, so it moved to `POST /orders/picks` for exactly the orders a screen
    asks about. Most of the assertions in this block are about the RESOLUTION (reason, the
    breakdown, `open`/`terminal`, idempotence) and never cared which route answered `picks` —
    so rather than rewrite every one of them to call two routes and thread the results
    together by hand, this helper does that once: it calls `do_orders()`, asks
    `do_order_picks` for every resolved order's key in one batch (`resolve_all` over a
    subset answers each of those orders identically to the whole ledger — the same fact
    `_resolve_records` relies on), and replaces each answered order's `lines` with the real
    ones. `check_order_picks_tier` below is the one block that asserts the SPLIT itself.
    """
    payload = capture_server.do_orders()
    keys = [order["key"] for order in payload["resolution"]["orders"]]
    if keys:
        detailed = capture_server.do_order_picks({"keys": keys})
        by_key = {order["key"]: order for order in detailed["orders"]}
        for order in payload["resolution"]["orders"]:
            full = by_key.get(order["key"])
            if full is not None:
                order["lines"] = full["lines"]
    return payload

# --------------------------------------------------- emit, reconcile and join as quantities


def _stages(inventory) -> str:
    """The `listings` line the three commands print, rebuilt from `listing_counts()`.

    Built here rather than written out as a literal, so the assertion is that the commands
    print THIS number — not that they print some number that happens to match today.
    """
    return ", ".join(f"{k} {v}" for k, v in inventory.listing_counts().items() if v)


def check_committed_copies_are_the_oldest(checks: Checks) -> None:
    """The copies held back as already-at-TCGplayer are the OLDEST CAPTURES, not the first box.

    THE OPERATOR'S OWN SHAPE, 2026-09-11, and the reason this case exists rather than a
    tidier one: their backstock is box 3 and tonight's capture is box 1. `_committed_keys`
    picked out of `copies_on_hand`, which answers in BOX-WALK order, so box 1 sorted first
    and the copies photographed an hour ago were marked as the ones TCGplayer already holds.
    The older backstock stayed uncommitted — and no run is joining box 3, so nobody could
    list it either. **52 of run `2026-09-11-box1-01`'s 119 matched SKUs offered zero copies
    and 59 real cards were stranded**, under the sentence *"every copy in this run is already
    listed or has left the box"*. The operator's words were that this is *"just not
    true/possible"*.

    SO THE FIXTURE INVERTS THE TWO ORDERS DELIBERATELY: the LOWER-numbered box is the NEWER
    capture. A case where box order and capture order agree passes under either rule and
    proves nothing — which is how the old order survived every emit case in this file.

    AND TONIGHT'S COPY IS STAMPED BY A REVIEW ANSWER, WHICH IS NOT DECORATION. `copies_on_hand`
    selects on `card.sku`, so a copy the store has not stamped is invisible to it, can never be
    committed, and is offerable whatever the order — a fixture that stamps the new copy by
    EMITTING it is therefore blind to this defect, and the first draft of this case was, passing
    under the old order. The operator's box 1 has never been emitted: its manifest carries no
    `emitted` key, and **158 `answered` events** stamped those SKUs. D59 names the mechanism in
    passing — *"a review answer stamps a SKU without sending anything"* — and that is precisely
    the copy this defect strands.

    THE STAMPS ARE WRITTEN, NOT WAITED FOR. `master.now()` is millisecond-resolution and
    captures in a loop can share a millisecond, which would leave the tie broken by
    `(box, index)` — the very order under test — and the case would go green for the wrong
    reason on a fast machine and red on a slow one. Writing them states the premise instead.

    Its own isolated home, this file's own lesson yet again: it emits, which writes `pushed`
    counts that `check_listing_commands` and `check_cli_seams` assert over their own fixtures.
    """
    checks.note("")
    checks.note("COMMITTED COPIES — the oldest captures back the claim, not the lowest box")

    backstock = [(3, 1, "Dunsparce", "120", "normal"), (3, 2, "Dunsparce", "120", "normal")]
    tonight = [(1, 1, "Dunsparce", "120", "normal")]

    with isolated_home():
        # Captured in real order too — box 3 first — so the fixture is not relying on the
        # stamps alone to describe a history that could not have happened.
        for box, index, *_ in backstock + tonight:
            while Store().read().inventory.next_index(box) <= index:
                capture_server.do_capture(capture_payload(box))

        with Store().write() as writable:
            for key, stamp in (
                (master.position_key(3, 1), "2026-09-01T10:00:00.000+00:00"),
                (master.position_key(3, 2), "2026-09-01T10:00:01.000+00:00"),
                (master.position_key(1, 1), "2026-09-11T22:38:00.000+00:00"),
            ):
                writable.inventory.cards[key].captured_at = stamp

        # --- the backstock run, which is what puts a claim on the SKU ---------------------
        first = runs.create("t7-oldest-backstock")
        first.write_identifications(identifications_for(backstock))
        export = write_export(first.path("export.csv"))
        command(checks, "join", str(first.directory), "--export", str(export))
        command(checks, "emit", str(runs.open_run(first.directory).directory))
        # identity-follows-sku.md §4.2's review round: `do_review_answer` below (tonight's
        # copy) now refuses a SKU the `skus` table does not already hold. `cli/cmd_join.py
        # --export` is Lane 3b's own fill point and is not on this base, so the fixture
        # seeds the table directly off the same real export, through the real fold.
        with Store().write() as writable:
            sku_pipeline.apply_rows(
                tcgcsv.read_export(export).rows, at=int(time.time()), source=export.name,
                skus=writable.skus, events=writable.inventory.events,
            )

        listing = Store().read().inventory.listing_for(DUNSPARCE_SKU)
        checks.equal(
            (listing.pushed, listing.staged, listing.live),
            (2, 0, 0),
            "the backstock run pushed its two copies and the export reports none live — "
            "which is the ordinary state of this store, not a corner: `Total Quantity` is "
            "blank for every SKU on the operator's own fetched exports",
        )

        # --- tonight's copy gets its SKU the way the operator's did: answered, not sent ----
        with Store().write() as writable:
            writable.inventory.set_state(master.position_key(1, 1), master.IDENTIFIED)
            writable.review.upsert(
                entry(
                    1,
                    1,
                    reason="rarity_claim_mismatch",
                    candidates=[
                        {
                            "sku": DUNSPARCE_SKU,
                            "name": "Dunsparce",
                            "set": "SV09",
                            "number": "120/159",
                            "condition": "Near Mint",
                            "market": "2.06",
                        }
                    ],
                )
            )
        capture_server.do_review_answer(1, 1, {"sku": DUNSPARCE_SKU, "condition": "Near Mint"})
        checks.equal(
            Store().read().inventory.get(master.position_key(1, 1)).sku,
            DUNSPARCE_SKU,
            "TONIGHT'S COPY CARRIES THE SKU AND WAS NEVER PUSHED. This is the premise the "
            "whole case rests on — an unstamped copy is invisible to `copies_on_hand`, so it "
            "could not be wrongly committed and the defect would be unreachable from here",
        )

        # --- the claim is spent on the OLDER copies --------------------------------------
        inventory = Store().read().inventory
        checks.equal(
            [c.key for c in inventory.copies_on_hand(DUNSPARCE_SKU)],
            ["1/1", "3/1", "3/2"],
            "and all three copies are on hand in BOX-WALK order, tonight's first — which is "
            "the list the claim used to be spent down",
        )
        copies_out, _ = resolve._copies_out(inventory, {})
        committed = resolve._committed_keys(inventory, copies_out)
        checks.equal(
            sorted(committed),
            ["3/1", "3/2"],
            "THE TWO COPIES THAT BACK THE CLAIM ARE THE TWO OLDEST CAPTURES. Box-walk order "
            "spent it on `1/1` and `3/1` — a copy photographed tonight standing in for one "
            "sent last week, which is a thing causality forbids: an emit walks the run's "
            "own positions, so a card captured after that emit was in no file it wrote",
        )
        checks.ok(
            master.position_key(1, 1) not in committed,
            "and TONIGHT'S copy is NOT among them, which is the whole defect: committed is "
            "subtracted per-run by `SkuMatch.uncommitted_positions`, so marking the new "
            "copy as held is what left the run in front of the operator with nothing to send",
        )

        # --- and the run in front of the operator can list it -----------------------------
        second = runs.create("t7-oldest-tonight")
        second.write_identifications(identifications_for(tonight))
        export = write_export(second.path("export.csv"))
        command(checks, "join", str(second.directory), "--export", str(export))
        said = command(checks, "emit", str(runs.open_run(second.directory).directory))

        written = second.path(runs.IMPORT_MERGED)
        rows = tcgcsv.read_export(written).by_sku() if written.is_file() else {}
        checks.ok(
            written.is_file(),
            "AN IMPORT FILE EXISTS AT ALL. The defect wrote none — the run's only matched "
            "SKU added nothing — so this is what the regression looks like before any "
            "quantity can be asserted about, and reading the file unguarded would hide it "
            "behind a traceback",
            said,
        )
        checks.equal(
            rows.get(DUNSPARCE_SKU, {}).get(tcgcsv.QUANTITY_COLUMN),
            "1",
            "AND TONIGHT'S COPY IS IN IT, at one copy. This is the assertion the operator "
            "would make: the card is in the box, it is not listed, and the file this press "
            "writes has to carry it",
        )
        checks.equal(
            Store().read().inventory.listing_for(DUNSPARCE_SKU).pushed,
            3,
            "and the claim GROWS to three — the two from backstock plus this one. A fix that "
            "freed the copy by forgetting the earlier push would read as two here, and would "
            "be D59's stuck-`pushed` correction undone rather than this defect fixed",
        )


def _copies_out_reference(
    inventory: master.Inventory, live_by_sku: dict
) -> Tuple[dict, dict]:
    """THE OLD PER-LISTING IMPLEMENTATION, KEPT HERE ONLY, as the equivalence oracle for
    `check_copies_out_one_pass_matches_reference` below. Never import this into `cli/`; it
    exists so a future edit to `_copies_out`'s one-pass body can be checked against the
    arithmetic it must never silently drift from. Copied verbatim from `cli/resolve.py`
    before the one-pass rewrite.
    """
    out: dict = {}
    live_now: dict = {}
    for sku in set(live_by_sku) | set(inventory.listings):
        listing_entry = inventory.listings.get(sku)
        reading = live_by_sku.get(sku)
        offered = reading.quantity if reading else None
        as_of = reading.as_of if reading else None
        read = (
            listing_entry.live_reading(offered, as_of)
            if listing_entry is not None
            else (reading.quantity if reading else 0)
        )
        read = max(0, int(read))
        live = max(
            0,
            read - (listing_entry.sales_pending(as_of) if listing_entry is not None else 0),
        )
        live_now[sku] = live
        claim = listing_entry.held if listing_entry is not None else 0
        if read <= 0 and claim <= 0:
            continue
        read_at = (
            listing_entry.reading_taken_at(offered, as_of)
            if listing_entry is not None
            else as_of
        )
        sold = (
            len(inventory.positions_for_sku(sku)) - len(inventory.copies_not_sold(sku))
            if read > 0
            else inventory.sales_before(sku, read_at)
        )
        out[sku] = max(live, claim - sold)
    return out, live_now


def check_copies_out_one_pass_matches_reference(checks: Checks) -> None:
    """`resolve._copies_out`'s one-pass rewrite must equal the per-listing arithmetic it
    replaced, on a store exercising every branch: `read > 0` with a sale, `read <= 0` with a
    sale before AND after `read_at`, a SKU only in `live_by_sku`, a SKU only in
    `inventory.listings`, and a SKU whose two copies are one SOLD and one RETIRED — the case
    that tells `SOLD` alone from `TERMINAL_STATES` (D26), which `copies_not_sold` warns
    against conflating and which the mutation arm for this check flips.
    """
    checks.note("")
    checks.note("COPIES OUT — one pass equals the old per-listing arithmetic")

    with isolated_home():
        # SKU A: read > 0, one sold, one not — exercises the `read > 0` branch.
        for box, idx in ((1, 1), (1, 2)):
            while Store().read().inventory.next_index(box) <= idx:
                capture_server.do_capture(capture_payload(box))
        with Store().write() as writable:
            writable.inventory.get(master.position_key(1, 1)).sku = "SKU-A"
            writable.inventory.get(master.position_key(1, 2)).sku = "SKU-A"
        capture_server.do_mark_sold(1, 1, {})

        # SKU B: read <= 0, one sale before `read_at`, one after — exercises both arms of
        # the `read <= 0` branch. `state_at` ordering is what `sales_before` reads.
        for box, idx in ((2, 1), (2, 2)):
            while Store().read().inventory.next_index(box) <= idx:
                capture_server.do_capture(capture_payload(box))
        with Store().write() as writable:
            writable.inventory.get(master.position_key(2, 1)).sku = "SKU-B"
            writable.inventory.get(master.position_key(2, 2)).sku = "SKU-B"
        capture_server.do_mark_sold(2, 1, {})  # before
        read_at = master.now()
        capture_server.do_mark_sold(2, 2, {})  # after

        # SKU D: read > 0, one SOLD and one RETIRED — the mutation arm's own case (a
        # naive "how many of this SKU's copies have left the box" would count both).
        for box, idx in ((4, 1), (4, 2)):
            while Store().read().inventory.next_index(box) <= idx:
                capture_server.do_capture(capture_payload(box))
        with Store().write() as writable:
            writable.inventory.get(master.position_key(4, 1)).sku = "SKU-D"
            writable.inventory.get(master.position_key(4, 2)).sku = "SKU-D"
        capture_server.do_mark_sold(4, 1, {})
        capture_server.do_retire(4, 2, {"reason": "pulled"})
        # A large `held` claim so `claim - sold` (99 correct, 98 under the mutation) is what
        # `max(live, claim - sold)` actually returns rather than `live` masking the difference.
        with Store().write() as writable:
            writable.inventory.listing("SKU-D").bump(master.PUSHED, 100)
            # SKU C: only in `inventory.listings` (no export row at all this run).
            writable.inventory.listing("SKU-ONLY-LISTED").bump(master.PUSHED)  # by=1 default

        inventory = Store().read().inventory
        live_by_sku = {
            "SKU-A": resolve.LiveReading(quantity=1, as_of=master.now()),
            "SKU-B": resolve.LiveReading(quantity=0, as_of=read_at),
            "SKU-D": resolve.LiveReading(quantity=6, as_of=master.now()),
            "SKU-ONLY-LIVE": resolve.LiveReading(quantity=2, as_of=master.now()),
        }

        one_pass = resolve._copies_out(inventory, live_by_sku)
        reference = _copies_out_reference(inventory, live_by_sku)
        checks.equal(
            one_pass, reference,
            "the one-pass rewrite and the old per-listing arithmetic agree on every SKU, "
            "across both `copies_out` and `live_now` — including SKU-D, whose retired copy "
            "must NOT be counted alongside the sold one",
        )


def check_listing_commands(checks: Checks) -> None:
    """`emit`, `reconcile` and `join` moving SKU QUANTITIES rather than card states (D7).

    THE WHOLE SECTION EXISTS BECAUSE THE FACT MOVED. `pushed`, `staged` and `live` used to be
    states a card wore, so "has this copy been listed" was answerable from the card and every
    command wrote it there. The owner's ruling is that copies of one SKU are fungible — "if i
    have 15 of one copy and mark 3 as live, it's any 3 are live, not 3 specific locations are
    live" — so the three are counts on the SKU's `Listing` now, and each command moves a
    number instead of flagging a position.

    What that makes newly breakable, and what is therefore asserted below: a count can be
    double-added where a state could only be re-set, it can be moved by reading the wrong
    column, and it can go negative. None of those three failures exists in a state machine.
    Every case runs the real subcommand through `cli/__main__.py`, because the command is the
    only place these three writes happen.
    """
    checks.note("")
    checks.note("LISTING COMMANDS — emit, reconcile and join as quantities")

    cards = [
        (3, 1, "Dunsparce", "120", "normal"),
        (3, 2, "Dunsparce", "120", "normal"),
        (3, 3, "Dunsparce", "120", "normal"),
        (3, 4, "Articuno", "161", None),
    ]

    # --- emit: identity onto the card, count onto the SKU --------------------------------
    with isolated_home():
        run_dir, joined = seam_run(checks, cards)
        checks.equal(
            Store().read().inventory.listings,
            {},
            "JOIN CREATES NO LISTING for a matched SKU with no live quantity and no record "
            "— `Inventory.listing` creates on read, and a run that merely matched a thousand "
            "SKUs would otherwise leave a thousand empty records for `staged_stale` and "
            "`listing_counts` to walk on every call",
        )

        emitted = command(checks, "emit", str(run_dir.directory))
        inventory = Store().read().inventory

        checks.equal(
            [
                (c.state, c.sku, c.condition, c.run)
                for c in (inventory.get(f"3/{i}") for i in (1, 4))
            ],
            [
                (master.IDENTIFIED, DUNSPARCE_SKU, "Near Mint", run_dir.name),
                (master.IDENTIFIED, ARTICUNO_SKU, "Near Mint Holofoil", run_dir.name),
            ],
            "emit writes the IDENTITY onto each copy — sku, condition and the run that "
            "decided them — and leaves the card at `identified`, which is where it stays: "
            "the stage it reached is not a fact about this piece of cardboard",
        )
        listing = inventory.listing_for(DUNSPARCE_SKU)
        checks.equal(
            (listing.pushed, listing.staged, listing.live, listing.condition),
            (3, 0, 0, "Near Mint"),
            "and the COUNT onto the SKU: three copies pushed, nothing further, at the "
            "condition the ladder resolved",
        )
        checks.ok(
            listing.at and listing.live_as_of is None,
            "`at` is stamped — the touch stamp, which nothing reads — and `live_as_of` is "
            "not: an emit takes no reading of `live`, and that stamp is what the arbitration "
            "reads (D87 amended), so a forged one here would outrank a real export",
        )
        checks.equal(
            inventory.listing_counts(),
            {master.PUSHED: 4, master.STAGED: 0, master.LIVE: 0},
            "and listing_counts() sums the stages across every SKU",
        )
        checks.ok(
            f"listings         {_stages(inventory)}" in emitted,
            "which is exactly the line `emit` prints — the run report's listing totals are "
            "that function and not a second count kept beside it",
            emitted,
        )
        rows = tcgcsv.read_export(run_dir.path(runs.IMPORT_MERGED)).by_sku()
        checks.equal(
            [rows[DUNSPARCE_SKU][tcgcsv.QUANTITY_COLUMN], rows[ARTICUNO_SKU][tcgcsv.QUANTITY_COLUMN]],
            ["3", "1"],
            "and the file carries one row per SKU with the copy count, never one row per copy",
        )

        # --- the re-emit that produced the Gate B defect ---------------------------------
        # A second `join` then `emit` over the same run, which is the ordinary thing to do
        # after editing a review. `cli/resolve.py` reads the counts back as `committed`, so
        # every copy is already spoken for and the file gets nothing.
        #
        # CAPTURED BEFORE THE SECOND EMIT, because the assertion below is about the file NOT
        # being touched, and that cannot be checked against a file this block wrote itself.
        before_bytes = run_dir.path(runs.IMPORT_MERGED).read_bytes()
        command(checks, "join", str(run_dir.directory))
        again = command(checks, "emit", str(run_dir.directory), exits=1)
        re_inventory = Store().read().inventory
        checks.equal(
            re_inventory.listing_counts(),
            {master.PUSHED: 4, master.STAGED: 0, master.LIVE: 0},
            "A RE-EMIT ADDS NOTHING TO `pushed`. The first real post-import re-emit "
            "(2026-08-22) re-counted 37 copies into the files; a count that is incremented "
            "rather than set is the one thing that can be double-added, so this is the case "
            "that has to be re-asserted against every change to the push loop",
        )
        checks.equal(
            [c.state for c in re_inventory.copies_on_hand(DUNSPARCE_SKU)],
            [master.IDENTIFIED] * 3,
            "and no copy is walked backwards to an earlier state — the other half of the "
            "same defect, which regressed staged copies to `pushed`",
        )
        checks.ok(
            "no room          2 SKU(s)" in again
            # A REASON PER SKU, whichever of `nothing_to_add`'s branches it is. Naming one
            # branch here would pin the wording of a sentence that is per-SKU by design,
            # and would go green the day a SKU took a different branch.
            and again.count(" — ") >= 2,
            "the SKUs are REPORTED and each is given ITS OWN reason (D59), because they "
            "are real cards at real positions and a run that silently omitted them would "
            "look identical to a run that lost them. It pinned the words `at cap` and the "
            "count alone until D59, which is why the heading went on saying `already at "
            "the live cap` — false for every copy of an import this pipeline has not seen "
            "land — while the rows beneath it had already been corrected. The label may "
            "move again; what may not is that every such SKU is named with a reason",
            again,
        )
        # A RE-EMIT WITH NOTHING NEW TO WRITE DOES NOT OPEN THE FILE.
        #
        # This replaced `len(rows) == 0`, which was blind: "the file holds no rows" is
        # satisfied IDENTICALLY by the emitter correctly omitting a zero-quantity row and by
        # the emitter overwriting two good rows with a bare header. A pass condition met
        # equally by a behaviour and by that behaviour's catastrophic opposite is not testing
        # the behaviour, and the destruction lived behind it.
        #
        # BYTE equality and not row equality, deliberately: `tcgcsv.render` writes the header
        # before it iterates, so a file rewritten with no rows is a valid CSV of nothing and
        # the row count cannot tell that from the rows never having existed.
        checks.equal(
            run_dir.path(runs.IMPORT_MERGED).read_bytes(),
            before_bytes,
            "A RE-EMIT THAT HAS NOTHING NEW TO WRITE DOES NOT TOUCH THE FILE. Rewriting it "
            "with a header and no rows destroys the output the operator was told to import, "
            "and leaves a valid CSV of nothing in its place",
        )
        # LOOKED UP DEFENSIVELY, because the failure this case exists to catch empties the
        # file — and a KeyError here would abort the block before the manifest and round-trip
        # assertions below ever ran, reporting one crash instead of four findings.
        surviving = tcgcsv.read_export(run_dir.path(runs.IMPORT_MERGED))
        by_sku = surviving.by_sku()
        checks.equal(
            [
                by_sku.get(DUNSPARCE_SKU, {}).get(tcgcsv.QUANTITY_COLUMN),
                by_sku.get(ARTICUNO_SKU, {}).get(tcgcsv.QUANTITY_COLUMN),
            ],
            ["3", "1"],
            "and the first emit's content is still there to be imported",
        )
        checks.ok(
            "0" not in [row[tcgcsv.QUANTITY_COLUMN] for row in surviving.rows],
            "and no row carries `Add to Quantity` of 0, which TCGplayer would accept and act "
            "on — the claim the assertion this replaced was written to make, asserted where "
            "it is actually observable",
        )
        checks.equal(
            sorted(runs.open_run(run_dir.directory).manifest["emitted"]["listed"]),
            sorted([DUNSPARCE_SKU, ARTICUNO_SKU]),
            "AND THE MANIFEST STILL NAMES WHAT WAS SENT. Nothing asserted this record after a "
            "second emit, which is why the destruction survived: every assertion in this "
            "block was about the store, and the store side was already safe. `reconcile` "
            "reads exactly this list, and an empty one makes it refuse a run that emitted",
        )
        checks.ok(
            "next: import" not in again,
            "and a re-emit that wrote nothing does not tell the operator to go and import it",
            again,
        )

        # AND THE ROUND TRIP STILL CLOSES AFTER TWO EMITS.
        #
        # THE ASSERTION THAT WOULD HAVE CAUGHT THIS IN ONE LINE, and the only one in this
        # block that spans two commands. `cli/cmd_reconcile.py` reads `emitted.listed +
        # emitted.sub_threshold` and refuses "this run has emitted nothing" when it is empty
        # — so a second emit that blanked the manifest made a run that had emitted perfectly
        # an hour ago unreconcilable, with its CSV already imported to TCGplayer. `command`
        # asserts exit 0, so the refusal fails here rather than needing its own check.
        staged = write_staged(
            run_dir.path("staged.csv"), {DUNSPARCE_SKU: 3, ARTICUNO_SKU: 1}
        )
        command(checks, "reconcile", str(run_dir.directory), str(staged))
        checks.equal(
            Store().read().inventory.listing_for(DUNSPARCE_SKU).staged,
            3,
            "and the copies reach `staged`, which is the whole point of the round trip: a "
            "run whose emit record was destroyed cannot move a single copy off `pushed`, "
            "and nothing else in the product ever takes them off it",
        )

    # --- emit against a position the store has never seen ---------------------------------
    # A run joined from a recovered or hand-made identifications file. It USED TO upsert a
    # card here; that birth made 99 ghost cards and ~96 phantom TCGplayer copies on
    # 2026-09-27 (D36, D145). No caller needs it, so it is gone: the
    # emit refuses, names the position, and writes and creates nothing.
    with isolated_home():
        run_dir = runs.create("t7-unseen")
        run_dir.write_identifications(identifications_for([(7, 1, "Articuno", "161", None)]))
        export = write_export(run_dir.path("export.csv"))
        command(checks, "join", str(run_dir.directory), "--export", str(export))
        checks.ok(
            Store().read().inventory.get("7/1") is None,
            "the store has never seen this position, and `join` does not invent it",
        )
        said = command(checks, "emit", str(run_dir.directory), exits=1)
        checks.ok(
            "Box 7, card 1" in said,
            "emit REFUSES and names the position the store holds no card at",
            said,
        )
        checks.ok(
            Store().read().inventory.get("7/1") is None,
            "and it births no card: an emit ships only copies a stored card stands behind",
        )

    # --- reconcile: pushed -> staged, as counts -------------------------------------------
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        command(checks, "emit", str(run_dir.directory))
        before = [c.state for c in Store().read().inventory.cards.values()]

        staged_export = write_staged(
            run_dir.path("staged.csv"), {DUNSPARCE_SKU: 3, ARTICUNO_SKU: 1}
        )
        moved = command(
            checks, "reconcile", str(run_dir.directory), str(staged_export)
        )
        inventory = Store().read().inventory
        listing = inventory.listing_for(DUNSPARCE_SKU)
        checks.equal(
            (listing.pushed, listing.staged),
            (0, 3),
            "reconcile MOVES A COUNT: three copies leave `pushed` and arrive at `staged`, "
            "and which physical copies they are is deliberately not recorded",
        )
        checks.ok(
            listing.staged_at,
            "and `staged_at` is stamped, which is the whole of what `staged_stale` reads — "
            "an import that staged and never moved live is invisible without it",
        )
        checks.equal(
            [c.state for c in inventory.cards.values()],
            before,
            "and NO CARD MOVED. A sale changes a card; a stage changes a quantity, and the "
            "cards are exactly where emit left them",
        )
        checks.ok(
            f"listings         {_stages(inventory)}" in moved,
            "and `reconcile` prints listing_counts() too, so the same number reads the same "
            "on all three commands",
            moved,
        )

        # Re-running it moves nothing more. `pushed` is now zero, so there is no count left
        # to take — the idempotence is the cap below doing its job at the boundary.
        command(checks, "reconcile", str(run_dir.directory), str(staged_export))
        checks.equal(
            Store().read().inventory.listing_counts(),
            {master.PUSHED: 0, master.STAGED: 4, master.LIVE: 0},
            "and a second reconcile stages nothing twice — there is no pushed count left",
        )

    # --- reconcile reads `Add to Quantity`, never `Total Quantity` -------------------------
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        command(checks, "emit", str(run_dir.directory))

        # The two columns disagree on purpose: `write_staged` sets `Total Quantity` to 97 on
        # every row. A command reading the live column would stage 97 copies of each.
        disagreeing = write_staged(
            run_dir.path("staged.csv"), {DUNSPARCE_SKU: 1, ARTICUNO_SKU: 9}
        )
        command(checks, "reconcile", str(run_dir.directory), str(disagreeing))
        inventory = Store().read().inventory
        dunsparce = inventory.listing_for(DUNSPARCE_SKU)
        checks.equal(
            (dunsparce.pushed, dunsparce.staged),
            (2, 1),
            "reconcile reads `Add to Quantity`, the column `emit` wrote — `Total Quantity` "
            "is the LIVE number (D8, D11) and staging on it would move copies TCGplayer "
            "never said it had staged",
        )
        articuno = inventory.listing_for(ARTICUNO_SKU)
        checks.equal(
            (articuno.pushed, articuno.staged),
            (0, 1),
            "and the move is CAPPED at what this pipeline pushed: a reported 9 against 1 "
            "pushed stages 1 and floors `pushed` at zero rather than going negative",
        )

        # A blank cell is an UNKNOWN quantity, not a zero one — D9's reading of a blank
        # market cell, applied to a quantity. The SKU is in the export, so TCGplayer has it.
        # Both SKUs, because `reconcile` reports in both directions and an export missing
        # one of them is a different finding from the one under test here.
        blank = write_staged(
            run_dir.path("blank.csv"), {DUNSPARCE_SKU: "", ARTICUNO_SKU: ""}
        )
        assumed = command(checks, "reconcile", str(run_dir.directory), str(blank))
        dunsparce = Store().read().inventory.listing_for(DUNSPARCE_SKU)
        checks.equal(
            (dunsparce.pushed, dunsparce.staged),
            (0, 3),
            "a blank quantity falls back to this pipeline's own `pushed` count rather than "
            "stranding every pushed copy at `pushed` forever and making `staged_stale` warn "
            "about an import that in fact landed",
        )
        checks.ok(
            DUNSPARCE_SKU in assumed and "reported no quantity" in assumed,
            "and the assumption is NAMED with its SKU, never made silently",
            assumed,
        )

    # --- reconcile on a landed SKU this pipeline never pushed ------------------------------
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        # THE SEND NAMES THE CAP (D7, amended 2026-09-08): this case asserts cap
        # arithmetic, and the store cannot hold a standing figure any more.
        command(checks, "emit", str(run_dir.directory), "--cap", "4")
        with Store().write() as snapshot:
            del snapshot.inventory.listings[ARTICUNO_SKU]

        landed = write_staged(
            run_dir.path("staged.csv"), {DUNSPARCE_SKU: 3, ARTICUNO_SKU: 4}
        )
        command(checks, "reconcile", str(run_dir.directory), str(landed))
        checks.ok(
            Store().read().inventory.listing_for(ARTICUNO_SKU) is None,
            "a matched row whose SKU has no listing record CREATES NOTHING — the row is "
            "reported either way, and inventing a count here would stage copies nothing "
            "ever wrote into a file",
        )

    # --- join sets `live` from the export, absolutely ---------------------------------------
    with isolated_home():
        run_dir, _ = seam_run(checks, cards)
        # THE SEND NAMES THE CAP (D7, amended 2026-09-08): this case asserts cap
        # arithmetic, and the store cannot hold a standing figure any more.
        command(checks, "emit", str(run_dir.directory), "--cap", "4")

        # Hand-set, because what is under test is the direction of the write and not how the
        # numbers got there. Dunsparce is the rise case, Articuno the no-change case.
        with Store().write() as snapshot:
            dunsparce = snapshot.inventory.listing(DUNSPARCE_SKU)
            dunsparce.set(master.PUSHED, 0)
            dunsparce.set(master.STAGED, 2)
            dunsparce.set(master.LIVE, 0)
            articuno = snapshot.inventory.listing(ARTICUNO_SKU)
            articuno.set(master.PUSHED, 0)
            articuno.set(master.STAGED, 2)
            articuno.set(master.LIVE, 4)

        rose = write_export(
            run_dir.path("export.csv"), live={DUNSPARCE_SKU: 2, ARTICUNO_SKU: 4}
        )
        # DATED, NOT RACED: the store stamped `live_as_of` to the millisecond a moment ago
        # and a tie goes to the store, so a file written in that same millisecond is not
        # NEWER and is refused. Say which order this case means, as the cases below do.
        newer = time.time() + 60
        os.utime(rose, (newer, newer))
        said = command(checks, "join", str(run_dir.directory), "--export", str(rose))
        inventory = Store().read().inventory
        checks.equal(
            (inventory.listing_for(DUNSPARCE_SKU).live, inventory.listing_for(DUNSPARCE_SKU).staged),
            (2, 0),
            "join reads `live` off the export and DRAWS `staged` DOWN BY THE RISE: two "
            "copies went live, so two stop being staged — otherwise the stale warning names "
            "every SKU that has ever staged, forever",
        )
        checks.equal(
            (inventory.listing_for(ARTICUNO_SKU).live, inventory.listing_for(ARTICUNO_SKU).staged),
            (4, 2),
            "and by the RISE and not the absolute reading: a SKU whose live quantity did not "
            "move keeps its staged copies, which are exactly the ones the warning exists to "
            "find",
        )
        checks.ok(
            f"listings         {_stages(inventory)}" in said,
            "and `join` prints listing_counts() as well — the third of the three commands",
            said,
        )

        # DOWNWARD TOO — WHERE THE EXPORT IS THE NEWER READING. The export is the authority
        # (D8, D11) for the moment it was read, and a join that only ever raised the stored
        # number would let a sale on TCGplayer leave this Mac permanently overstating what is
        # for sale. BOTH DIRECTIONS ARE DATED WITH `os.utime` RATHER THAN RELIED ON: `set`
        # stamps `live_as_of` to the millisecond and the file is written after it, so the
        # order would hold in practice — and a case about ordering should say which order.
        # Articuno is pinned at the store's own 4 so the counts below are Dunsparce alone.
        with Store().write() as snapshot:
            snapshot.inventory.listing(DUNSPARCE_SKU).set(master.LIVE, 9)
        fell = write_export(
            run_dir.path("export.csv"), live={DUNSPARCE_SKU: 2, ARTICUNO_SKU: 4}
        )
        later = time.time() + 3600
        os.utime(fell, (later, later))
        said = command(checks, "join", str(run_dir.directory), "--export", str(fell))
        listing = Store().read().inventory.listing_for(DUNSPARCE_SKU)
        checks.equal(
            (listing.live, listing.live_as_of),
            (2, runs.describe_source(fell)["mtime"]),
            "a stored 9 against a NEWER export that says 2 becomes 2, dated to the FILE'S "
            "time — a newer export sets `live`, never nudges it",
        )
        checks.ok("1 SKU(s) moved" in said, "and the report counts it as moved", said)

        # AND NOT WHERE THE STORE'S READING IS THE NEWER ONE (D87 amended, 2026-09-02).
        with Store().write() as snapshot:
            snapshot.inventory.listing(DUNSPARCE_SKU).set(master.LIVE, 9)
        stamped = Store().read().inventory.listing_for(DUNSPARCE_SKU).live_as_of
        earlier = time.time() - 3600
        os.utime(fell, (earlier, earlier))
        said = command(checks, "join", str(run_dir.directory), "--export", str(fell))
        listing = Store().read().inventory.listing_for(DUNSPARCE_SKU)
        checks.equal(
            (listing.live, listing.live_as_of),
            (9, stamped),
            "an OLDER export cannot overwrite a reading the store took after it, and the "
            "stamp stands too — the measured re-join with a run's recorded export, fetched "
            "fifteen minutes before the emit, took the owner's store from 1,072 live copies "
            "to 700 on exactly this path",
        )
        checks.ok(
            "1 SKU(s) kept: store newer than this export" in said
            and f"{DUNSPARCE_SKU}  store 9 (as of {stamped}) vs export 2" in said,
            "and the report NAMES what it kept, with both readings and the store's stamp, "
            "rather than counting it (D59's rule)",
            said,
        )

    # --- the cap is a QUANTITY, and a sold copy gives its slot back (D59) -----------------
    #
    # ITS OWN `isolated_home`, and this file has now recorded that lesson four times — the
    # sharpest being `check_emit_claim_decides`, which emits and therefore writes `pushed` counts
    # that the block above asserts as absolute dicts over its own fixtures. This one emits
    # three times.
    #
    # SIX COPIES, NOT FOUR, AND THE COUNT IS THE CASE. At `copies == live_before` the answer
    # is zero however the room is computed, so a four-copy fixture could not fail; the
    # refill only exists where there is real backstock behind the cap.
    with isolated_home():
        six = [(3, i, "Dunsparce", "120", "normal") for i in range(1, 7)]
        run_dir, _ = seam_run(checks, six)
        # THE SEND NAMES THE CAP (D7, amended 2026-09-08): this case asserts cap
        # arithmetic, and the store cannot hold a standing figure any more.
        command(checks, "emit", str(run_dir.directory), "--cap", "4")
        checks.equal(
            Store().read().inventory.listing_for(DUNSPARCE_SKU).pushed,
            4,
            "SIX COPIES, FOUR PUSHED: the cap is what the file may carry, and the two behind "
            "it are backstock at known positions (D7) rather than cards this run lost",
        )
        checks.equal(
            tcgcsv.read_export(run_dir.path(runs.IMPORT_MERGED))
            .by_sku()[DUNSPARCE_SKU][tcgcsv.QUANTITY_COLUMN],
            "4",
            "and the file carries the four",
        )

        # THE IMPORT LANDS, WHICH IS THE STEP THE OLD ARITHMETIC COULD NOT SURVIVE.
        # `reconcile` moves the count off `pushed`, and `join` then reads the four copies
        # live off the export — the only two commands that ever move these numbers.
        landed_staged = write_staged(run_dir.path("staged.csv"), {DUNSPARCE_SKU: 4})
        command(checks, "reconcile", str(run_dir.directory), str(landed_staged))
        landed = write_export(run_dir.path("landed.csv"), live={DUNSPARCE_SKU: 4})
        command(checks, "join", str(run_dir.directory), "--export", str(landed))
        checks.equal(
            (
                Store().read().inventory.listing_for(DUNSPARCE_SKU).live,
                Store().read().inventory.listing_for(DUNSPARCE_SKU).staged,
            ),
            (4, 0),
            "four live, nothing pending: the round trip closed and the SKU is at its cap",
        )

        # --- two copies sell -------------------------------------------------------------
        # Through the real route, because the sale's own half of D7 is what makes the refill
        # arithmetic true: `do_mark_sold` decrements the SKU's `live` count, and nothing else
        # in the product does. Hand-setting the number here would assert the refill against a
        # figure this test had written rather than against one a sale produced.
        for index in (1, 2):
            capture_server.do_mark_sold(3, index, {})
        after_sales = Store().read().inventory.listing_for(DUNSPARCE_SKU)
        checks.equal(
            after_sales.live_estimate,
            2,
            "two sales take the count to two, which is the room the cap now has",
        )
        checks.equal(
            (after_sales.live, after_sales.sold_here),
            (4, 2),
            "and they do it WITHOUT editing the reading (D115): the export said four and "
            "still says four; what the store knows on top of it is that two have since sold",
        )

        # A STALE EXPORT CANNOT CLOSE THE CAP AGAINST THE STORE'S NEWER READING (D87
        # amended, 2026-09-02). The export still says four — the operator has not
        # downloaded a fresh one since the sales — and until this date that reading was a
        # FLOOR the store could not argue below, so this case pinned "every copy in this
        # run is already listed" and its own comment admitted THE SENTENCE WAS THE COMMITTED
        # ONE, NOT THE CAP ONE. The two sales are observations the store made AFTER the
        # file (`bump(LIVE, -1)` stamps `live_as_of`), the file is dated an hour before them
        # so the ordering is asserted rather than relied on, and the store's 2 is the newer
        # reading: TCGplayer holds two, the cap has room for two, and the two backstock
        # copies are exactly what it should offer.
        earlier = time.time() - 3600
        os.utime(landed, (earlier, earlier))
        stale = command(checks, "join", str(run_dir.directory), "--export", str(landed))
        # THIS ASSERTION BROKE RATHER THAN INVERTED AT D115, and the reason is the whole
        # design. It used to read `"1 SKU(s) kept: store newer than this export" in stale` —
        # true while a sale EDITED `live` down to 2, so a file saying 4 disagreed with the
        # store and had to be arbitrated away as `KEPT`. The sale no longer edits the reading,
        # so the file and the store now AGREE at four and there is nothing to arbitrate: the
        # verdict is `UNCHANGED` and no SKU is kept. The protection did not go anywhere — it
        # moved from the figure to the counter, and `sales_pending` is what refuses the file.
        checks.ok(
            "kept: store newer than this export" not in stale,
            "a stale export reporting four live is no longer KEPT, because it no longer "
            "disagrees: the reading it offers is the reading the store holds",
        )
        stood = Store().read().inventory.listing_for(DUNSPARCE_SKU)
        checks.equal(
            (stood.live, stood.sold_here, stood.live_estimate),
            (4, 2, 2),
            "AND THE SALES SURVIVE IT, which is what the old assertion was really protecting. "
            "The file was fetched an hour before the sales, so `sales_pending` refuses to let "
            "it cancel them — the store's own two still stands, by the counter's stamp rather "
            "than by a reading time a sale had forged",
        )
        held = resolve.load(
            runs.open_run(run_dir.directory), landed
        ).matches[DUNSPARCE_SKU]
        checks.equal(
            (held.copies_out, held.add_to_quantity),
            (2, 2),
            "a stale export cannot CLOSE the cap against the store's newer reading: "
            "`copies_out` is the newer 2, not the file's 4 — `SkuMatch.copies_out` used to "
            "`max` the row's own column back over `_copies_out`'s answer, which put the 4 "
            "back — and the two backstock copies have room",
        )
        # AND IT CANNOT RE-OPEN IT EITHER, which is the D59 hazard `_copies_out` said it did
        # not close: after a reconcile `pushed` and `staged` are both zero, and an export
        # that under-reports would compute `room = cap - 0` and send the SKU again.
        reopened = write_export(run_dir.path("reopened.csv"), live={DUNSPARCE_SKU: 0})
        os.utime(reopened, (earlier, earlier))
        held = resolve.load(
            runs.open_run(run_dir.directory), reopened
        ).matches[DUNSPARCE_SKU]
        checks.equal(
            (held.copies_out, held.add_to_quantity),
            (2, 2),
            "an older export reading ZERO cannot re-open the cap either — two, not four: "
            "the store's newer reading is the floor, closed by time rather than by trusting "
            "either side",
        )

        # --- and the fresh one refills ---------------------------------------------------
        before_bytes = run_dir.path(runs.IMPORT_MERGED).read_bytes()
        fresh = write_export(run_dir.path("fresh.csv"), live={DUNSPARCE_SKU: 2})
        later = time.time() + 3600
        os.utime(fresh, (later, later))
        refilled = command(checks, "join", str(run_dir.directory), "--export", str(fresh))
        checks.ok(
            # THE SKU MUST BE ABSENT FROM THE no-room BLOCK, NOT MERELY UNNAMED BY ONE
            # STRING. This pinned `"already at the live cap" not in refilled` until D59
            # renamed that heading — after which no production path emitted the string at
            # all and the assertion was TRUE in the failure state too. A check that cannot
            # fail is not coverage, which this file records having paid for twice.
            f"{DUNSPARCE_SKU} — " not in refilled and "no room" not in refilled,
            "TWO LIVE, FOUR COPIES IN THE BOX, CAP FOUR — D7's own `min(cap - live, "
            "backstock)`, and the SKU is no longer at the cap. Against the old expression "
            "this answered zero: `live_cap - live_before - len(committed_positions)` counted "
            "the two SOLD copies that `live_before` had already accounted for, so a departed "
            "card shrank what its SKU could ever list and this row would never have appeared "
            "in an import file again",
            refilled,
        )
        # THE SEND NAMES THE CAP (D7, amended 2026-09-08): this case asserts cap
        # arithmetic, and the store cannot hold a standing figure any more.
        refill = command(checks, "emit", str(run_dir.directory), "--cap", "4")
        checks.ok(
            "1 row(s), 2 card(s)" in refill,
            "and the emit sends exactly the two the cap has room for",
            refill,
        )
        inventory = Store().read().inventory
        checks.equal(
            tcgcsv.read_export(run_dir.path(runs.IMPORT_MERGED))
            .by_sku()[DUNSPARCE_SKU][tcgcsv.QUANTITY_COLUMN],
            "2",
            "THE FILE CARRIES THE DELTA AND NOT THE CAP (D54). Four here would re-import the "
            "copies already live and double-stage them, which is the Gate B defect — the two "
            "TCGplayer is holding were never withdrawn, and this run may only add the two "
            "the sales made room for",
        )
        checks.equal(
            inventory.listing_for(DUNSPARCE_SKU).pushed,
            2,
            "the count on the SKU is the same two, so a reconcile can move exactly them",
        )
        checks.equal(
            sorted(c.key for c in inventory.positions_for_sku(DUNSPARCE_SKU)),
            ["3/1", "3/2", "3/3", "3/4", "3/5", "3/6"],
            "AND THE COPIES SENT ARE THE TWO THAT HAD NOT BEEN. `live_positions` is "
            "`uncommitted_positions[:add_to_quantity]`, so a budget that failed to commit "
            "the copies TCGplayer already has out would re-send those instead and leave the "
            "backstock unstamped — same row count, wrong cards, and invisible in the file",
        )
        checks.ok(
            "next: import" in refill,
            "and an emit that wrote something tells the operator to go and import it",
            refill,
        )
        checks.ok(
            run_dir.path(runs.IMPORT_MERGED).read_bytes() != before_bytes,
            "which is the other side of the re-emit case above: that one must not touch the "
            "file, and this one must",
        )

    # --- pushed and live disagreeing, which is the case that refutes the obvious fix ------
    #
    # GREEN IN BOTH BUILDS, DELIBERATELY, AND KEPT FOR THE MUTATION. `pushed=4, live=2` is
    # produced by "four went live and two sold" AND by "two rows landed and two are still
    # sitting in Staged", and those want opposite answers — the first has room for two, the
    # second has none. Nothing on this Mac can tell them apart (D34: no export this pipeline
    # reads can assert what TCGplayer is holding), so the conservative reading is the only
    # honest one, and any "fix" that makes the refill above work by trusting `live` alone
    # takes this case red.
    with isolated_home():
        eight = [(3, i, "Dunsparce", "120", "normal") for i in range(1, 9)]
        run_dir, _ = seam_run(checks, eight)
        # THE SEND NAMES THE CAP (D7, amended 2026-09-08): this case asserts cap
        # arithmetic, and the store cannot hold a standing figure any more.
        command(checks, "emit", str(run_dir.directory), "--cap", "4")
        untouched = run_dir.path(runs.IMPORT_MERGED).read_bytes()

        partial = write_export(run_dir.path("partial.csv"), live={DUNSPARCE_SKU: 2})
        said = command(checks, "join", str(run_dir.directory), "--export", str(partial))
        # `join` NAMES NO CAP ANY MORE (D7, amended 2026-09-08), because there is no standing
        # one to read and the figure a send asks for is not known until `emit --cap`. This
        # asserted the report's cap sentence — "4 of the 4 this SKU may have out" — and with
        # no cap the SKU is not `at_cap` at all, so the `no room` section it lived in does not
        # print. That sentence is covered at the unit level now, in
        # `t3:_check_overrun_is_named`, over BOTH arms and including the overrun `min` hid.
        #
        # WHAT THIS CASE IS ACTUALLY FOR SURVIVES INTACT, and is asserted where it is a number
        # rather than a sentence: `pushed=4, live=2` must be read as FOUR out, not two.
        checks.ok(
            "4 of the 4" not in said,
            "`join` does NOT invent a cap — reporting a bound the send has not chosen is a "
            "promise a later emit could quietly break, which is the argument that keeps "
            "`--rule` and `--basis` off `#/runs` too",
            said,
        )
        offered = json.loads(run_dir.path(runs.PRICING).read_text())
        row = next(r for r in offered["skus"] if r["sku"] == DUNSPARCE_SKU)
        checks.equal(
            row["add_to_quantity"],
            4,
            "AND FOUR COPIES ARE OFFERED, NOT SIX. Eight in the box against four already out "
            "leaves four — the conservative reading of `pushed=4, live=2`. The fix this case "
            "exists to refute trusts `live` alone, reads two out, and offers six",
        )
        # THE SEND NAMES THE CAP (D7, amended 2026-09-08): this case asserts cap
        # arithmetic, and the store cannot hold a standing figure any more.
        again = command(checks, "emit", str(run_dir.directory), "--cap", "4", exits=1)
        checks.ok(
            "nothing new to send" in again,
            "and the re-emit says so rather than writing a file",
            again,
        )
        checks.equal(
            run_dir.path(runs.IMPORT_MERGED).read_bytes(),
            untouched,
            "leaving the first emit's file exactly as the operator was told to import it",
        )

        # AND A RETIRED COPY IS STILL A COPY TCGPLAYER IS HOLDING (D26, D59).
        #
        # `Inventory.copies_not_sold` bounds the claim by what we physically hold, and it
        # filters `SOLD` alone rather than `TERMINAL_STATES` — which is the opposite of the
        # choice `copies_on_hand` makes one method up. A sale is proof a copy reached
        # TCGplayer and left it; a retirement is the other door, where the card left THIS BOX
        # and TCGplayer was never told, so its row is still out there. Counting a retired
        # copy as gone lowers the ceiling and frees a slot under the cap that is not free,
        # and the six unstamped copies behind it are exactly what would pour through.
        for index in (1, 2):
            capture_server.do_retire(3, index, {"reason": "damaged"})
        command(checks, "join", str(run_dir.directory), "--export", str(partial))
        after = json.loads(run_dir.path(runs.PRICING).read_text())
        row = next(r for r in after["skus"] if r["sku"] == DUNSPARCE_SKU)
        checks.equal(
            row["add_to_quantity"],
            2,
            "TWO COPIES LEAVING THE BOX CHANGES NOTHING ABOUT WHAT TCGPLAYER IS HOLDING. Six "
            "copies remain against the same four already out, so two are offered — a "
            "retirement that wrongly lowered `copies_out` to two would offer four, and the "
            "six unstamped copies behind it are exactly what would pour through",
        )
        # THE SEND NAMES THE CAP (D7, amended 2026-09-08): this case asserts cap
        # arithmetic, and the store cannot hold a standing figure any more.
        command(checks, "emit", str(run_dir.directory), "--cap", "4", exits=1)
        checks.equal(
            run_dir.path(runs.IMPORT_MERGED).read_bytes(),
            untouched,
            "and the file is still the first emit's — a retirement may never re-open the cap",
        )

    # --- a zero reading taken AFTER the sale ages the claim (D150) ---
    #
    # THE OWNER'S OWN CASE, WHICH D150 LEAVES OUT OF SCOPE BY THE OWNER'S CHOICE. A copy
    # is pushed, it sells, and a later export reads `Total Quantity` 0 for the SKU. `pushed`
    # has no drawdown and the old gate aged it only where the export reported copies LIVE, so
    # the claim stood at its full count forever: the copies on hand were committed against it
    # and a card captured tonight could not be sent. Seven real cards on run
    # `2026-09-11-box1-01`, two of them cards the operator had just scanned in.
    #
    # TWO COPIES AND A CAP OF ONE, because the difference is only observable where there is
    # stock behind the claim — at `copies_out >= copies on hand` every copy is committed
    # whatever the claim is, which is the property that made the seven ordering-independent.
    with isolated_home():
        pair = [(3, i, "Dunsparce", "120", "normal") for i in (1, 2)]
        run_dir, _ = seam_run(checks, pair)
        command(checks, "emit", str(run_dir.directory), "--cap", "1")
        checks.equal(
            Store().read().inventory.listing_for(DUNSPARCE_SKU).pushed,
            1,
            "one copy sent, one behind it: the claim is one and the second copy is backstock",
        )
        capture_server.do_mark_sold(3, 1, {})
        # THE READING IS TAKEN AFTER THE SALE, AND THAT IS THE WHOLE DISCRIMINATOR. The file
        # is dated an hour from now so the ordering is ASSERTED rather than relied on — the
        # sale's `state_at` is `now()`, and a fixture that let the two land in the same second
        # would be deciding this case on `newer_stamp`'s tie rule instead of on the arithmetic.
        after = write_export(run_dir.path("after.csv"), live={DUNSPARCE_SKU: 0})
        later = time.time() + 3600
        os.utime(after, (later, later))
        match = resolve.load(runs.open_run(run_dir.directory), after).matches[DUNSPARCE_SKU]
        checks.equal(
            (match.live_out, match.copies_out, match.add_to_quantity),
            (0, 0, 1),
            "A ZERO READ AFTER THE SALE IS THE SALE'S OWN RESULT. Nothing is live, the one "
            "sent copy has gone, the claim ages to zero and the copy on hand is offered — "
            "against the old gate `copies_out` stood at 1, the backstock copy was committed "
            "against a claim TCGplayer had already drawn down, and the SKU printed "
            "`nothing_to_add` over a card sitting in the box",
        )

    # --- and a sale AFTER the reading is not aged, which is the other half ------------------
    #
    # THE SAME FIXTURE WITH THE FILE AND THE SALE THE OTHER WAY ROUND. A reading that said
    # nothing of ours was live at its own time cannot vouch for a copy that sold later: the
    # copies may be sitting in Staged, and a card marked sold against THAT state did not leave
    # TCGplayer's hands (D59). Ageing here is the double-list the corroboration gate was built
    # to prevent, and it is what keeps the re-emit idempotence case above green.
    with isolated_home():
        pair = [(3, i, "Dunsparce", "120", "normal") for i in (1, 2)]
        run_dir, _ = seam_run(checks, pair)
        command(checks, "emit", str(run_dir.directory), "--cap", "1")
        stale = write_export(run_dir.path("stale.csv"), live={DUNSPARCE_SKU: 0})
        earlier = time.time() - 3600
        os.utime(stale, (earlier, earlier))
        capture_server.do_mark_sold(3, 1, {})
        match = resolve.load(runs.open_run(run_dir.directory), stale).matches[DUNSPARCE_SKU]
        checks.equal(
            (match.live_out, match.copies_out, match.add_to_quantity),
            (0, 1, 0),
            "THE CLAIM STANDS AT ONE. The export predates the sale, so it corroborates "
            "nothing about it — `copies_out` is the unaged claim, the backstock copy is "
            "committed against it, and nothing is offered. A date comparison that read the "
            "wrong way, or a fix that dropped the gate outright, offers a second copy of a "
            "row TCGplayer may still be holding staged",
        )

    # --- the v1 -> v2 migration, through a real store session ------------------------------
    # `check_boxes_and_listings` drives `Inventory.parse` directly. This is the other half:
    # that the migration survives a read and a commit through `store/session.py`, which is
    # the only path a running system ever takes.
    with isolated_home():
        # A LEGACY STORE, WRITTEN AS THE FILE IT WAS. The first `Store()` open imports it
        # into the database (D88) through `Inventory.parse`, which is where the v1->v2
        # migration has always lived — so this is both migrations in one read.
        files.write_json(
            files.inventory_dir() / db.LEGACY_INVENTORY,
            {
                "version": 1,
                "cards": {
                    "4/1": {
                        "box": 4, "index": 1, "sku": DUNSPARCE_SKU,
                        "condition": "Near Mint", "state": "pushed",
                        "state_at": "2026-08-01T00:00:00+00:00",
                    },
                    "4/2": {
                        "box": 4, "index": 2, "sku": DUNSPARCE_SKU,
                        "condition": "Near Mint", "state": "live",
                        "state_at": "2026-08-01T00:00:00+00:00",
                    },
                },
            },
        )
        with Store().write():
            pass  # read, migrate, commit — the shape every request has

        on_disk = Store().read().inventory.to_payload()
        checks.equal(on_disk["version"], master.VERSION, "the committed store is v2")
        checks.equal(
            [record["state"] for record in stored_payloads("cards").values()],
            [master.IDENTIFIED, master.IDENTIFIED],
            "and no stored card wears a listing stage any more — a v2 row that did would "
            "fail `check_state` loudly on the next write rather than being repaired forever",
        )
        checks.ok(
            not (files.inventory_dir() / db.LEGACY_INVENTORY).exists()
            and (db.legacy_dir(files.inventory_dir()) / db.LEGACY_INVENTORY).is_file(),
            "and the legacy file was moved to legacy-json/, never deleted and never re-read",
        )
        checks.equal(
            {
                stage: on_disk["listings"][DUNSPARCE_SKU][stage]
                for stage in master.LISTING_STAGES
            },
            {master.PUSHED: 1, master.STAGED: 0, master.LIVE: 1},
            "and each stage arrived on the SKU as a count, through the session rather than "
            "only through `Inventory.parse`",
        )
        checks.equal(
            Store().read().inventory.listing_counts(),
            {master.PUSHED: 1, master.STAGED: 0, master.LIVE: 1},
            "which a second session reads back unchanged — a v2 payload is not re-migrated",
        )


def check_order_resolver(checks: Checks) -> None:
    """`pipeline/orders.py` — an order line resolved to the copies that fill it.

    ITS OWN `isolated_home`, this file's own repeated lesson: the second half writes
    photographs and a run directory, and the blocks above count records and history lines
    over boxes they build card by card. The FIRST half needs no home at all — the resolver
    reads an `Inventory` it is handed and touches no disk — and that is itself the property
    worth having: a pure core is testable without a store.

    THE CASE THAT MATTERS IS THE FIRST ONE, AND IT CHANGED SHAPE ON 2026-09-16. Until then
    it asserted that two open orders for one SKU, resolved per-order, are handed THE SAME
    PHYSICAL CARDS and both report success — the picker walks to box 3 card 3 twice — and
    that `resolve_all`'s shared pool was what stopped it, by giving the older order the
    copies EXCLUSIVELY and leaving the younger one `short`. The owner overruled that
    exclusivity outright: *"All orders should not 'claim' or take priority/claim any item,
    because they're all fungible."* So the case now asserts the opposite of what it used
    to: two orders wanting the same one copy are BOTH offered it, in full, and the guard
    against shipping it twice moved to the WRITE — `store/orders.py:record_pull`'s
    `CopyAlreadyPulled` — which this file asserts explicitly rather than trusting the
    resolver to still be doing a job it no longer does.

    OBSERVED FAILING FIRST. Every case here was run against a mutation of the code it
    covers before it was kept — a per-order pool, a dropped SKU coercion, a dropped
    terminal filter, a paperwork lookup that reads `pricing.json` raw instead of through
    `realign`. A test that cannot fail is not coverage, and this repo has already paid for
    that lesson at the multi-game prompt seam.

    The domain objects are constructed here rather than parsed from a fixture, and that is
    not the hand-authored-fixture problem the owner declined: `Order` and `OrderLine` have
    a confirmed shape (a real observed line — Moonfall, UNL #198/219, Foil, Near Mint,
    Epic, SKU 9191486, qty 3, $11.88), and the order CSVs carry no line items at all, so
    there is no wire format here to guess at.
    """
    checks.note("")
    checks.note("ORDER RESOLVER — pipeline/orders.py")

    def card(box, index, sku, **extra):
        fields = {
            "box": box,
            "index": index,
            "sku": sku,
            "capture_id": f"C{box}-{index}",
            "state": master.IDENTIFIED,
        }
        fields.update(extra)
        return master.Card(**fields)

    def stock(*cards) -> master.Inventory:
        return master.Inventory(cards={c.key: c for c in cards})

    def line(sku, quantity, **extra) -> orders.OrderLine:
        return orders.OrderLine(sku=sku, quantity=quantity, **extra)

    with isolated_home() as home:
        # -------------------------------------------------- 1. fungibility, not allocation
        #
        # The proven real join: sku 9191486 (Moonfall) is four copies in box 3. Two open
        # orders both want three, and there are four — RED against the pre-2026-09-16
        # code, which gave the older order three of the four EXCLUSIVELY and left the
        # younger one `short` with one.
        inventory = stock(
            card(3, 3, "9191486"),
            card(3, 31, "9191486"),
            card(3, 34, "9191486"),
            card(3, 35, "9191486"),
        )
        first = orders.Order(
            number="A-1",
            placed_at="2026-08-28T10:00:00+00:00",
            lines=(
                line(
                    "9191486", 3,
                    name="Moonfall", number="UNL #198/219", printing="Foil",
                    condition="Near Mint", rarity="Epic", unit_price="11.88",
                ),
            ),
        )
        second = orders.Order(
            number="B-2",
            placed_at="2026-08-29T10:00:00+00:00",
            lines=(line("9191486", 3),),
        )

        # DELIBERATELY HANDED OVER NEWEST-FIRST, so a sequencing bug would still be
        # visible — though sequence no longer decides WHO GETS OFFERED anything, only the
        # order the answer reports orders back in (`order_sequence`, amended 2026-09-16).
        answer = orders.resolve_all(inventory, [second, first])
        a = answer.for_order("A-1")
        b = answer.for_order("B-2")

        checks.equal(
            (a.lines[0].reason, a.lines[0].fulfilled),
            (orders.RESOLVED, 4),
            "BOTH orders are offered every copy the store holds — wanting 3 with 4 on hand "
            "is `resolved`, and `fulfilled` is now the count of CANDIDATES (4), not an "
            "allocation. RED against the old code, which gave this order only 3",
        )
        checks.equal(
            (b.lines[0].reason, b.lines[0].fulfilled, b.lines[0].outstanding),
            (orders.RESOLVED, 4, 0),
            "and the SECOND order is ALSO `resolved` with all four candidates and zero "
            "outstanding — the owner's ruling in one assertion: 'they're all fungible', so "
            "nothing an earlier order was offered is withheld from a later one. RED against "
            "the old code, which reported this order `short` with one copy and 2 "
            "outstanding",
        )
        picks_a = {(p.box, p.index) for p in a.lines[0].picks}
        picks_b = {(p.box, p.index) for p in b.lines[0].picks}
        checks.equal(
            picks_a,
            picks_b,
            "the two orders are offered the IDENTICAL set of four copies — not a "
            "complementary split, which is what an exclusive pool would still produce even "
            "if it happened to leave nothing short",
        )
        checks.equal(
            sorted(picks_a),
            [(3, 3), (3, 31), (3, 34), (3, 35)],
            "and it is all four positions the store actually holds",
        )
        checks.equal(
            [(p.box, p.index) for p in orders.resolve_all(inventory, [first, second])
             .for_order("A-1").lines[0].picks],
            sorted(picks_a),
            "re-running over an unchanged inventory, orders handed over in the OTHER "
            "sequence, answers identically — the answer is a function of the store and the "
            "orders, never of the walk order, which is order_sequence's remaining job now "
            "that it decides no priority",
        )
        checks.equal(
            a.lines[0].picks[0].capture_id,
            "C3-3",
            "a pick carries the capture_id, which is what a caller that must record "
            "something records: a position key is a fourth thing no renumber path remaps",
        )
        checks.equal(
            answer.counts(),
            {orders.RESOLVED: 2, orders.SHORT: 0, orders.NO_COPIES_ON_HAND: 0,
             orders.SKU_UNKNOWN: 0, orders.SKU_UNSEEN: 0, orders.NOT_A_SINGLE: 0},
            "and every reason is reported including the zeros — BOTH lines are `resolved` "
            "now, where the old exclusive pool made one of them `short`",
        )
        checks.ok(
            answer.complete and a.complete and b.complete,
            "the whole resolution is complete because both orders are now that the pool is "
            "shared rather than exclusive",
        )

        # ------------------------------------- 1b. `short` is a genuine shortfall, only
        #
        # Two orders wanting the SAME one copy: both are `short`, neither `resolved`,
        # because the store does not hold enough — never because someone else got there
        # first. And wanting exactly what is on hand resolves even with a competing order.
        one_copy = stock(card(4, 1, "SHORTSKU"))
        want_two = orders.resolve_all(
            one_copy, [orders.Order(number="C-1", lines=(line("SHORTSKU", 2),))]
        ).lines[0]
        checks.equal(
            (want_two.reason, want_two.on_hand, len(want_two.picks), want_two.outstanding),
            (orders.SHORT, 1, 1, 1),
            "wanting 2 with 1 on hand is `short` with the one candidate offered and one "
            "outstanding — a genuine shortfall, the only kind `short` means now",
        )
        want_one_a = orders.Order(number="D-1", lines=(line("SHORTSKU", 1),))
        want_one_b = orders.Order(number="D-2", lines=(line("SHORTSKU", 1),))
        competing = orders.resolve_all(one_copy, [want_one_a, want_one_b])
        checks.equal(
            (
                competing.for_order("D-1").lines[0].reason,
                competing.for_order("D-2").lines[0].reason,
            ),
            (orders.RESOLVED, orders.RESOLVED),
            "wanting 1 with 1 on hand is `resolved` for BOTH competing orders — the fact "
            "that another order also wants it does not make either one `short`, which is "
            "the whole owner's ruling: fungible means every order sees the same stock",
        )

        # ------------------------------------------------- 1c. the write-time guard holds
        #
        # THE SAFETY THAT REPLACED THE EXCLUSIVE DRAW is `store/orders.py:record_pull`'s
        # `CopyAlreadyPulled`, asserted explicitly rather than assumed: this pass offers
        # the same card to two orders on purpose now, so the module that must still refuse
        # shipping it twice is the ledger, at the point it is actually recorded.
        ledger = order_store.Ledger()
        ledger.ingest([
            order_store.OrderRecord(
                source="TCGplayer", number="E-1",
                placed_at="2026-08-28T10:00:00+00:00",
                lines=[order_store.OrderLine(sku="SHORTSKU", quantity=1)],
            ),
            order_store.OrderRecord(
                source="TCGplayer", number="E-2",
                placed_at="2026-08-29T10:00:00+00:00",
                lines=[order_store.OrderLine(sku="SHORTSKU", quantity=1)],
            ),
        ])
        e1 = order_store.order_key("TCGplayer", "E-1")
        e2 = order_store.order_key("TCGplayer", "E-2")
        ledger.record_pull(e1, "SHORTSKU", ["CARD-SHORTSKU-1"])
        checks.raises(
            order_store.CopyAlreadyPulled,
            lambda: ledger.record_pull(e2, "SHORTSKU", ["CARD-SHORTSKU-1"]),
            "and pulling the SAME physical copy for the second order — the one this pass "
            "was perfectly willing to offer it — is refused at the write, which is where "
            "the safety this dropped claim used to provide now lives entirely",
        )

        # ------------------------------------------- 1d. the walk itself is widened too
        #
        # The owner, 2026-09-16, extending the brief mid-review: *"widen the walk itself
        # too... how is the walk only showing one instance."* A line wanting ONE copy of a
        # SKU the store holds FIVE of is offered every one of the five, ranked and never
        # rationed — `picks` is a candidate list the operator chooses from, not an
        # allocation capped at the buyer's quantity. RED against the pre-2026-09-16 code,
        # which capped `picks` at `line.quantity` and offered exactly one.
        wide = stock(
            card(6, 1, "WIDESKU"), card(6, 2, "WIDESKU"), card(6, 3, "WIDESKU"),
            card(6, 4, "WIDESKU"), card(6, 5, "WIDESKU"),
        )
        want_one_of_five = orders.resolve_all(
            wide, [orders.Order(number="F-1", lines=(line("WIDESKU", 1),))]
        ).lines[0]
        checks.equal(
            (
                want_one_of_five.reason,
                want_one_of_five.outstanding,
                sorted((p.box, p.index) for p in want_one_of_five.picks),
            ),
            (
                orders.RESOLVED, 0,
                [(6, 1), (6, 2), (6, 3), (6, 4), (6, 5)],
            ),
            "a line wanting 1 copy of a SKU the store holds 5 of is offered EVERY copy, "
            "and still reads `resolved` with `outstanding` 0 — wanting one no longer "
            "means being handed one",
        )

        # -------------------------------------------------------- 2. the SKU is coerced
        #
        # `Card.sku` is a string out of a CSV; a JSON order payload carries the int.
        # `"9191486" == 9191486` is False, so without this every line resolves to zero,
        # raises nothing and logs nothing — a silent total failure.
        integer = orders.Order(number="C-3", lines=(orders.OrderLine(sku=9191486, quantity=1),))
        coerced = orders.resolve_all(inventory, [integer]).for_order("C-3")
        checks.equal(
            (coerced.lines[0].sku, coerced.lines[0].reason, coerced.lines[0].fulfilled),
            # `inventory` above holds all four Moonfall copies, and `fulfilled` is every
            # candidate offered (2026-09-16) rather than the one this line asked for —
            # 4, not 1. What this case is actually proving is unchanged: an uncoerced SKU
            # comparison finds nothing at all, silently, and `reason` would read
            # `sku_unseen` rather than `resolved`.
            ("9191486", orders.RESOLVED, 4),
            "a line built from an int SKU resolves — uncoerced, it silently finds nothing",
        )

        # ---------------------------------------- 3. an empty result gets the right word
        departed = stock(
            card(4, 1, "SOLDOUT", state=master.SOLD),
            card(4, 2, "SOLDOUT", state=master.RETIRED, retire_reason="damaged"),
        )
        gone = orders.resolve_all(
            departed, [orders.Order(number="D-4", lines=(line("SOLDOUT", 1),))]
        ).lines[0]
        checks.equal(
            (gone.reason, gone.fulfilled, gone.on_hand, gone.sold, gone.retired),
            (orders.NO_COPIES_ON_HAND, 0, 0, 1, 1),
            "every copy has left, so the reason says so and the BREAKDOWN says how — "
            "deliberately not `already_pulled`, because D26 makes a retirement a departure "
            "WITHOUT a sale and calling it filled tells the owner to ship nothing and "
            "believe it shipped",
        )

        pooled = stock(card(9, 1, "CODECARD", game="pokemon_code"))
        code = orders.resolve_all(
            pooled, [orders.Order(number="E-5", lines=(line("CODECARD", 1),))]
        ).lines[0]
        checks.equal(
            (code.reason, code.fulfilled, code.pooled),
            (orders.NO_COPIES_ON_HAND, 0, 1),
            "a pooled game's copy is never walked to (D24) — it is a count, not a place, "
            "and the breakdown says pooled rather than sold so nobody hunts for it",
        )

        unseen = orders.resolve_all(
            inventory, [orders.Order(number="F-6", lines=(line("NOSUCHTHING", 1),))]
        ).lines[0]
        checks.equal(
            (unseen.reason, unseen.fulfilled),
            (orders.SKU_UNSEEN, 0),
            "a SKU nothing anywhere knows is `sku_unseen`",
        )

        sealed = orders.resolve_all(
            inventory,
            [orders.Order(
                number="G-7",
                lines=(line("BOOSTERBOX", 1, kind=orders.LINE_KIND_SEALED),),
            )],
        ).lines[0]
        checks.equal(
            (sealed.reason, sealed.fulfilled),
            (orders.NOT_A_SINGLE, 0),
            "a sealed line routes as `not_a_single` and is NOT looked for among the cards — "
            "`sku_unseen` there would send the owner hunting boxes for a booster box, and "
            "the signal that matters is that this order cannot ship in an envelope",
        )
        checks.raises(
            orders.UnknownLineKind,
            lambda: orders.OrderLine(sku="1", quantity=1, kind="mystery"),
            "and a kind the resolver does not know is refused rather than defaulted to "
            "`single`: a feed that has learned a new category is telling us something",
        )
        checks.equal(
            sorted(orders.LINE_REASONS),
            sorted(["resolved", "short", "no_copies_on_hand", "sku_unknown",
                    "sku_unseen", "not_a_single"]),
            "six reasons, because an empty result has several causes with different remedies",
        )

        # ------------------------------- 4. the run paperwork is the backup, and it is named
        #
        # A card whose run was joined and never emitted carries `sku: null` — invisible to
        # every SKU-keyed surface, which is 498 of the owner's 502 unstamped records. The
        # paperwork is what finds it, and the source is recorded so a screen can say
        # "matched via run X, not stamped" rather than answering from an invisible fallback.
        unstamped = stock(
            card(3, 3, "9191486"),
            card(5, 7, None),
        )
        paper = [orders.PaperworkEntry(
            sku="9191486", run="2026-08-30-box5-01", positions=("3/3", "5/7")
        )]
        backed = orders.resolve_all(
            unstamped,
            [orders.Order(number="H-8", lines=(line("9191486", 2),))],
            paperwork=paper,
        ).lines[0]
        checks.equal(
            (backed.reason, backed.fulfilled),
            (orders.RESOLVED, 2),
            "the paperwork finds the copy no stamp names, so the line fills",
        )
        checks.equal(
            [(p.box, p.index, p.source, p.run) for p in backed.picks],
            [(3, 3, orders.SOURCE_CARD, None),
             (5, 7, orders.SOURCE_RUN, "2026-08-30-box5-01")],
            "CARD-FIRST, then the run, and each pick says which answered — a silent "
            "fallback is what makes a later disagreement unexplainable",
        )
        checks.equal(
            len({(p.box, p.index) for p in backed.picks}),
            2,
            "and a position the paperwork ALSO names is not drawn twice — 3/3 is in both",
        )
        unknown = orders.resolve_all(
            stock(card(1, 1, "OTHER")),
            [orders.Order(number="I-9", lines=(line("9191486", 1),))],
            paperwork=paper,
        ).lines[0]
        checks.equal(
            (unknown.reason, unknown.fulfilled),
            (orders.SKU_UNKNOWN, 0),
            "no card carries it and a run's pricing.json does: `sku_unknown`, whose remedy "
            "is to look at what happened to the box rather than at the order",
        )

        # -------------------------- 5. paperwork_for realigns, because positions MOVE (D36)
        #
        # `pricing.json` stores position keys and a mid-box delete slides every higher index
        # in the box down one (D10 ruling 1). Reading that file raw is the defect that wrote
        # all 47 of box 2's queue entries one position off, each carrying the right read with
        # its NEIGHBOUR's photograph. So the loader re-binds through `cli/resolve.py:realign`.
        photos = home / "captures" / "cards" / "box3"
        photos.mkdir(parents=True)
        bodies = {i: f"order-resolver-card-{i}".encode() for i in (1, 2, 3)}
        for i, body in bodies.items():
            (photos / f"{i:04d}.jpg").write_bytes(body)
        run = runs.create("orders")
        run.write_identifications({
            "cards": {
                f"3/{i}": {
                    "box": 3,
                    "index": i,
                    "photo": f"captures/cards/box3/{i:04d}.jpg",
                    "photo_sha256": hashlib.sha256(body).hexdigest(),
                }
                for i, body in bodies.items()
            }
        })
        files.write_json(run.path(runs.PRICING), {"skus": [
            {"sku": "9191486", "positions": [
                {"box": 3, "index": 2}, {"box": 3, "index": 3},
            ]},
        ]})

        checks.equal(
            [(e.sku, e.run, e.positions) for e in resolve.paperwork_for(run)],
            [("9191486", run.name, ("3/2", "3/3"))],
            "an unmoved box reads back exactly what the run wrote",
        )

        # Card 1 is deleted mid-box: 2 and 3 slide down to 1 and 2.
        (photos / "0001.jpg").write_bytes(bodies[2])
        (photos / "0002.jpg").write_bytes(bodies[3])
        (photos / "0003.jpg").unlink()
        checks.equal(
            [e.positions for e in resolve.paperwork_for(run)],
            [("3/1", "3/2")],
            "after a mid-box delete the SAME paperwork names where those photographs are "
            "NOW — read raw, it would send a picker one slot past every card (D36)",
        )

        # And a copy whose photograph is on no slot at all has left the box.
        (photos / "0002.jpg").unlink()
        checks.equal(
            [e.positions for e in resolve.paperwork_for(run)],
            [("3/1",)],
            "and a departed copy is dropped rather than named — there is no card at its "
            "old slot to walk to, and its successor is a different card",
        )

        files.write_json(run.path(runs.PRICING), {"skus": [
            {"sku": "9191486", "positions": [{"box": 3, "index": 3}]},
        ]})
        checks.equal(
            resolve.paperwork_for(run), [],
            "a SKU every one of whose positions has departed contributes no entry at all, "
            "rather than an entry naming nothing",
        )

        run_without = runs.create("orders")
        checks.equal(
            resolve.paperwork_for(run_without), [],
            "and a run that was identified and never joined has no pricing table, which is "
            "an ordinary state and not a complaint (D86) — the card-first pass needs none",
        )


def check_order_ledger(checks: Checks) -> None:
    """`store/orders.py` — `inventory/orders.json`, the durable half of the order flow.

    ITS OWN `isolated_home`, and this file has now paid for that lesson twice: a block that
    writes into a store another block counts records and history lines over fails on the
    fixture rather than on the code. The queue-starvation cases and the listing-release
    cases both took sibling assertions red before they were moved out, and this one writes
    cards, a listing, a sale and a mid-box renumber.

    IDEMPOTENCE IS ASSERTED AS BYTE EQUALITY, NEVER AS A COUNT, which is D54's lesson said
    out loud: that entry's guard read `len(rows) == 0` under the message "the file holds no
    zero row", and "the file holds 0 rows" is satisfied IDENTICALLY by the emitter correctly
    omitting a row and by the emitter overwriting two good rows with a bare header. The
    destruction lived behind it for as long as it existed. A second sync here must therefore
    leave `orders.json` AND `inventory.json` AND `history.jsonl` byte-for-byte as they were
    — a row count would go green on a ledger that had thrown its fulfilment away and
    re-ingested the same order over the top.

    THE CASE THAT MATTERS MOST IS THE RENUMBER. A pull is recorded, a junk capture is then
    deleted from the middle of the box through the real route, and every higher card slides
    down one — so the position key the pulled copy used to have now belongs to a DIFFERENT
    physical card. A ledger keyed by position reports that the wrong card is in the post; a
    ledger keyed by `capture_id` still names the right one. It is asserted as both halves,
    because the first alone is satisfied by a ledger that stores nothing at all.

    OBSERVED FAILING FIRST, AND EACH ONE THROUGH THE ASSERTION THAT OWNS IT. Six mutations
    were run against this block before it was kept:

      fulfilment moved inside the replaced record   7 red, headed by the survival case
      `changed_at` restamped unconditionally        2 red, headed by the byte comparison
      the pull's dedup dropped                      1 red, the idempotence case
      `holder_of` not consulted                     1 red, the two-buyers refusal
      the nested `__annotations__` filter removed   1 red, the LINE case
      capture ids stored as POSITION KEYS (D36)     7 red, headed by the renumber

    THREE OF THEM FIRST FAILED BY ABORTING THE BLOCK RATHER THAN BY NAMING ANYTHING, and
    two assertions were changed for it — the repeat pull is caught as a value and the line
    case tests the list before it indexes it. A mutation that raises out of the middle of a
    block leaves the assertion that covers it unrun and everything after it unreported: it
    is loud, so it is not the silent pass this repo fears most, but it is coverage of the
    traceback rather than of the defect. A test that cannot fail is not coverage, and a
    test that fails somewhere other than the case is barely better.
    """
    checks.note("")
    checks.note("ORDER LEDGER — store/orders.py")

    def line(sku, quantity, **extra) -> order_store.OrderLine:
        return order_store.OrderLine(sku=sku, quantity=quantity, **extra)

    def record(number, *lines, **extra) -> order_store.OrderRecord:
        fields = {
            "source": "TCGplayer",
            "number": number,
            "placed_at": "2026-08-28T10:00:00.000+00:00",
            "lines": list(lines),
        }
        fields.update(extra)
        return order_store.OrderRecord(**fields)

    # ------------------------------------------------------ 1. the key, and its refusals
    checks.equal(
        order_store.order_key("TCGplayer", "A-1"),
        order_store.order_key("tcgplayer", " a-1 "),
        "the key folds case and strips to COMPARE — D20's box-name rule one register over, "
        "because TCGplayer and tcgplayer are one marketplace to a person",
    )
    checks.raises(
        order_store.BadOrderKey,
        lambda: order_store.order_key("tcg:player", "A-1"),
        "a source carrying the separator refuses — the key splits on the FIRST colon, so "
        "such a source makes two different orders share one record",
    )
    checks.equal(
        order_store.order_key("TCGplayer", "A:1"),
        "tcgplayer:a:1",
        "and an order NUMBER may carry one, which is the asymmetry that refusal buys",
    )
    for bad in (("", "A-1"), ("TCGplayer", "  ")):
        checks.raises(
            order_store.BadOrderKey,
            lambda pair=bad: order_store.order_key(*pair),
            f"an empty half refuses ({bad!r}) — every empty-half key is the same key",
        )

    with isolated_home():
        # A real store to ingest beside: one identified card carrying the proven SKU, and a
        # listing record with counts on it, so "ingest writes no card state and no listing
        # count" is a comparison this block can lose rather than an absence it assumes.
        for i in range(1, 6):
            capture_server.do_capture(
                {"box": 3, "capture_id": f"o{i}", "image": base64.b64encode(
                    b"\xff\xd8\xff" + bytes([i]) * 64).decode("ascii")}
            )
        with Store().write() as snapshot:
            for i in range(1, 6):
                snapshot.inventory.record_identification(
                    f"3/{i}", name="Moonfall", number="198/219", printed_total="219",
                    confidence="high",
                )
                snapshot.inventory.cards[f"3/{i}"].sku = "9191486"
            snapshot.inventory.listing("9191486").set(master.PUSHED, 4)

        store = Store()
        moonfall = record(
            "A-1",
            line("9191486", 3, name="Moonfall", number="UNL #198/219",
                 printing="Foil", condition="Near Mint", rarity="Epic",
                 unit_price="11.88"),
        )

        # ------------------------------------------- 2. the first sync, and what it wrote
        with store.write() as snapshot:
            report = snapshot.ledger.ingest([moonfall])
        checks.equal(
            (report.added, report.changed, report.unchanged, report.wrote_nothing),
            (1, 0, 0, False),
            "the first sync reports the order as new",
        )

        key = order_store.order_key("TCGplayer", "A-1")
        after = store.read()
        checks.ok(
            after.ledger.get(key) is not None
            and after.ledger.get(key).source == "TCGplayer",
            "the record round-trips through the session, storing the source VERBATIM "
            "while the key that found it was folded",
        )
        checks.equal(
            [c.state for c in sorted(after.inventory.cards.values(), key=lambda c: c.index)],
            [master.IDENTIFIED] * 5,
            "INGEST WROTE NO CARD STATE — not one of the five moved, which is what makes a "
            "second press a no-op by construction rather than by a guard",
        )
        checks.equal(
            (after.inventory.listing_for("9191486").pushed,
             after.inventory.listing_for("9191486").staged,
             after.inventory.listing_for("9191486").live),
            (4, 0, 0),
            "and no listing count — a ledger that bumped one would re-list every order in "
            "the file on every sync",
        )

        # --------------------------- 2b. buyer: content, carry-over, `name_buyer` (D-the-
        # ledger-names-the-buyer)
        a2_key = order_store.order_key("TCGplayer", "A-2")
        with store.write() as snapshot:
            named = snapshot.ledger.ingest(
                [record("A-2", line("9191486", 1, name="Moonfall"))]
            )
        checks.equal(named.added, 1, "a second order, with no buyer, ingests as ordinary "
                     "content — `None` means the feed said nothing")
        checks.equal(
            store.read().ledger.get(a2_key).buyer,
            None,
            "and nothing is invented in its place",
        )

        with store.write() as snapshot:
            outcome = snapshot.ledger.name_buyer("TCGplayer", "A-2", "Ada Lovelace")
        checks.equal(
            outcome, "named",
            "`name_buyer` attaches a display name to an order the ledger already holds",
        )
        checks.equal(
            store.read().ledger.get(a2_key).buyer, "Ada Lovelace", "and it is stored",
        )

        before_changed = store.read().ledger.get(a2_key).changed_at
        with store.write() as snapshot:
            repeat = snapshot.ledger.name_buyer("TCGplayer", "A-2", "Ada Lovelace")
        checks.equal(
            repeat, "unchanged",
            "naming the SAME buyer again is a no-op down to the word, the ingest "
            "byte-identical-on-a-repeat promise one field over",
        )
        checks.equal(
            store.read().ledger.get(a2_key).changed_at, before_changed,
            "and `changed_at` does not move on a repeat",
        )

        with store.write() as snapshot:
            missing = snapshot.ledger.name_buyer("TCGplayer", "NOT-REAL-ORDER", "Nobody")
        checks.equal(
            missing, "unknown",
            "an order this ledger has never ingested is REPORTED, never created",
        )
        checks.ok(
            store.read().ledger.get(order_store.order_key("TCGplayer", "NOT-REAL-ORDER"))
            is None,
            "and nothing was minted from a name and a number alone",
        )

        with store.write() as snapshot:
            batch = snapshot.ledger.name_buyers(
                [
                    ("TCGplayer", "A-2", "Ada Lovelace"),
                    ("TCGplayer", "NOT-REAL-ORDER", "Nobody"),
                ]
            )
        checks.equal(
            (batch.named, batch.unchanged, batch.unknown, batch.total),
            (0, 1, 1, 2),
            "`name_buyers` is the same three verdicts over a list, `ingest`'s own shape",
        )

        # a paste WITHOUT a buyer preserves the one already recorded
        with store.write() as snapshot:
            carried = snapshot.ledger.ingest(
                [record("A-2", line("9191486", 1, name="Moonfall"))]
            )
        checks.equal(
            (carried.changed, carried.unchanged),
            (0, 1),
            "A HAND-PASTE CARRYING NO BUYER DOES NOT ERASE ONE THE FETCH ALREADY WROTE — "
            "the incoming record says nothing, `ingest` carries the incumbent's name "
            "across, and the content then compares equal",
        )
        checks.equal(
            store.read().ledger.get(a2_key).buyer, "Ada Lovelace",
            "the buyer survived a paste that said nothing about it",
        )

        # a paste WITH a different buyer overwrites, same as any other feed-owned field
        before_changed2 = store.read().ledger.get(a2_key).changed_at
        with store.write() as snapshot:
            overwritten = snapshot.ledger.ingest(
                [record(
                    "A-2", line("9191486", 1, name="Moonfall"), buyer="Grace Hopper",
                )]
            )
        checks.equal(overwritten.changed, 1, "a feed-supplied buyer overwrites the stored one")
        after2 = store.read().ledger.get(a2_key)
        checks.equal(after2.buyer, "Grace Hopper", "the new name is stored verbatim")
        checks.ok(
            after2.changed_at != before_changed2,
            "and `changed_at` MOVES — `buyer` is `_content` now, same as `status`",
        )
        # A-2 is scratch for this sub-section alone. Closed out here — a hand-fill, not a
        # deletion this module refuses to offer — so the fixed `unfulfilled` roster later
        # in this block stays exactly the three orders it has always named.
        with store.write() as snapshot:
            snapshot.ledger.record_fill(a2_key, "9191486", 1, "t7 buyer scratch, closed out")

        # --------------------------------------- 3. IDEMPOTENCE, AS BYTES AND NOT A COUNT
        before_tables = store_tables()

        with store.write() as snapshot:
            second = snapshot.ledger.ingest([record(
                "A-1",
                line("9191486", 3, name="Moonfall", number="UNL #198/219",
                     printing="Foil", condition="Near Mint", rarity="Epic",
                     unit_price="11.88"),
            )])
        checks.equal(
            (second.added, second.changed, second.unchanged, second.wrote_nothing),
            (0, 0, 1, True),
            "the SECOND sync of the same order reports it unchanged",
        )
        after_tables = store_tables()
        checks.equal(
            (after_tables["orders"], after_tables["fulfilment"]),
            (before_tables["orders"], before_tables["fulfilment"]),
            "and the orders and fulfilment rows are IDENTICAL — a row count would go green "
            "on a ledger that threw its fulfilment away and re-ingested over the top (D54)",
        )
        checks.equal(
            (after_tables["cards"], after_tables["listings"]),
            (before_tables["cards"], before_tables["listings"]),
            "and so are the cards and listings, which is the half a count could never see",
        )
        checks.equal(
            after_tables["events"],
            before_tables["events"],
            "and the history — a sync appending a row per order is not the no-op the "
            "module promises, however small the row is",
        )

        # ---------------------------------------------- 4. the pull, and its idempotence
        with store.write() as snapshot:
            newly = snapshot.ledger.record_pull(key, "9191486", ["o2", "o3"])
        checks.equal(newly, 2, "a pull records the copies it was handed")
        # THE REPEAT IS CAUGHT AS A VALUE RATHER THAN AS A TRACEBACK, deliberately. A pull
        # that has stopped deduping does not return the wrong number, it RAISES — the same
        # two copies counted twice overshoot the line and trip `OverFulfilled` — and an
        # exception here would abort this block, leaving the assertion that owns the defect
        # unrun and everything after it unreported. Turning it into a value is what makes
        # the named case the one that goes red.
        try:
            with store.write() as snapshot:
                again = snapshot.ledger.record_pull(key, "9191486", ["o2", "o3"])
        except Exception as exc:  # noqa: BLE001 - reported as the failure it is
            again = f"raised {type(exc).__name__}"
        checks.equal(
            again,
            0,
            "and recording the SAME pull again records nothing — idempotent because a "
            "capture id already on the line is skipped, not because a caller checked",
        )
        after = store.read()
        checks.equal(
            (after.ledger.fulfilled(key, "9191486"),
             after.ledger.outstanding(key, "9191486")),
            (2, 1),
            "two of the three copies are recorded and one is still owed",
        )

        # -------------------------------------- 5. A COUNT, AND NOT A LIST OF POSITIONS
        row = stored_payloads("fulfilment")[key]["9191486"]
        checks.equal(
            sorted(row.keys()),
            ["at", "by_hand", "closed_at", "closed_reason", "copies", "fulfilled",
             "kind", "reason"],
            "the stored row is COUNTS, its capture ids, stamps and the operator's own "
            "words — and still not one position. D113 added five keys to this row and "
            "this assertion is what made that a decision rather than a drift: `by_hand` "
            "and `reason` are the hand-fill, `closed_at`/`closed_reason` the stand-down, "
            "`kind` the operator's claim. Every one is a fact about the LINE; none is a "
            "slot, which is the property this roster exists to hold",
        )
        checks.equal(
            int(row["fulfilled"]) - len(row["copies"]) - int(row["by_hand"]),
            0,
            "and `fulfilled` == len(copies) + by_hand — the invariant four methods "
            "maintain and nothing else may write. A fifth writer would break it "
            "silently, because every reader downstream takes `fulfilled` alone",
        )
        checks.equal(
            [c for c in row["copies"] if "/" in str(c)],
            [],
            "and not one value is a position key — D36: a stored position names a "
            "different card the moment a mid-box delete slides the box down one",
        )
        checks.ok(
            isinstance(row["fulfilled"], int),
            "`fulfilled` is a number rather than a length somebody has to trust",
        )

        # ------------------------------ 6. THE RENUMBER — capture_id, never position_key
        #
        # The real route, not a simulated shift. `renumber_blocked` refuses while the SKU
        # carries a listing hold, so the pushed count set above is cleared first — D10
        # ruling 1's own boundary, and clearing it here is what lets the shift happen at
        # all rather than a convenience.
        with Store().write() as snapshot:
            snapshot.inventory.listing("9191486").set(master.PUSHED, 0)

        pulled_before = {
            c.capture_id: c.key for c in store.read().inventory.cards.values()
        }
        checks.equal(
            (pulled_before["o2"], pulled_before["o3"]),
            ("3/2", "3/3"),
            "the two pulled copies sit at 3/2 and 3/3 before the shift",
        )
        body = capture_server.do_remove_card(3, 1, {"capture_id": "o1"})
        checks.equal(body["shifted"], 4, "the mid-box delete slides four records down one")

        moved = store.read()
        checks.equal(
            moved.inventory.card_by_capture_id("o2").key,
            "3/1",
            "so both pulled copies moved: the one that WAS 3/2 is now 3/1",
        )
        checks.equal(
            moved.inventory.cards["3/3"].capture_id,
            "o4",
            "AND POSITION 3/3 NOW HOLDS A CARD THAT WAS NEVER PULLED — a ledger storing "
            "['3/2', '3/3'] would name o4 here and send that card to the buyer",
        )
        drawn = answers(checks, capture_server.do_orders, "GET /orders answers after the shift")
        if drawn is not None:
            shifted = next(order for order in drawn["orders"] if order["key"] == key)
            checks.equal(
                sorted(shifted["progress"][0]["copies"]),
                ["o2", "o3"],
                "AND THE LEDGER'S OWN RECORD FOLLOWED THE CARDS BY IDENTITY: capture ids, "
                "never a position — the mid-box delete renumbered the drawer and neither "
                "recorded copy dropped out or changed name",
            )
            checks.ok(
                "pulled" not in shifted["progress"][0],
                "AND NO POSITION IS JOINED FOR AN ALREADY-PULLED COPY (docs/specs/undo.md "
                "§5, D212) — the card has left the box, so the wire says which card and how "
                "many, never the slot it came out of; a renumber is the case that used to "
                "prove the join was live, and it is exactly the case this drops",
            )
        recorded = moved.ledger.recorded(key, "9191486")
        checks.equal(
            sorted(recorded.copies),
            ["o2", "o3"],
            "the ledger still names the same two physical cards, unmoved by the shift — "
            "which is the whole reason it keys by capture_id",
        )
        checks.ok(
            "o4" not in recorded.copies,
            "and does not name the card that inherited a pulled position",
        )
        checks.equal(
            recorded.fulfilled,
            2,
            "with the count untouched: `_drop_from_stores` remaps the three position-keyed "
            "stores at every delete, and this one does not need remapping",
        )

        # --------------------------------- 7. THE LOAD-BEARING ONE: ingest cannot clobber
        with store.write() as snapshot:
            changed = snapshot.ledger.ingest([record(
                "A-1", line("9191486", 3, name="Moonfall"), status="Shipped"
            )])
        checks.equal(
            (changed.changed, changed.added), (1, 0), "a feed that says something new updates"
        )
        survived = store.read()
        checks.equal(
            (survived.ledger.fulfilled(key, "9191486"),
             sorted(survived.ledger.recorded(key, "9191486").copies)),
            (2, ["o2", "o3"]),
            "AND THE FULFILMENT SURVIVES IT. Ingest replaces the feed's half by key, so a "
            "count living in that record dies on the next sync — and the consequence is "
            "the picker being sent to a slot whose card is already in the post",
        )
        checks.equal(
            survived.ledger.get(key).status,
            "Shipped",
            "while the feed's own word is carried verbatim and unvalidated",
        )
        checks.ok(
            survived.ledger.get(key).first_seen == after.ledger.get(key).first_seen,
            "`first_seen` is the ONE field ingest preserves, exactly as Queue.upsert does",
        )

        # ------------------------------------------------------------- 8. the refusals
        checks.raises(
            order_store.UnknownOrder,
            lambda: store.read().ledger.record_pull("tcgplayer:nope", "9191486", ["o3"]),
            "a pull against an order the ledger has never ingested refuses — inventing it "
            "would record a shipment for a purchase nobody can produce",
        )
        checks.raises(
            order_store.UnknownOrderLine,
            lambda: store.read().ledger.record_pull(key, "8608859", ["o3"]),
            "and a pull against a SKU the buyer did not order",
        )
        checks.raises(
            order_store.CopyNotIdentifiable,
            lambda: store.read().ledger.record_pull(key, "9191486", [None]),
            "a copy with no capture_id refuses rather than being counted blind — without "
            "an identity the pull cannot be made idempotent, and a silent double-pull is "
            "the worst outcome this feature has",
        )
        checks.raises(
            order_store.OverFulfilled,
            lambda: store.read().ledger.record_pull(key, "9191486", ["o4", "o5"]),
            "and recording more copies than the buyer ordered refuses rather than clamping "
            "— you cannot ship the fourth, so there is nothing to be gained by hiding it",
        )

        # THE ONE THIS MODULE EXISTS FOR: one physical card against two orders.
        with store.write() as snapshot:
            snapshot.ledger.ingest([record("B-2", line("9191486", 2),
                                           placed_at="2026-08-29T10:00:00.000+00:00")])
        other = order_store.order_key("TCGplayer", "B-2")
        caught = checks.raises(
            order_store.CopyAlreadyPulled,
            lambda: store.read().ledger.record_pull(other, "9191486", ["o2"]),
            "a copy already recorded against ANOTHER order refuses — this is selling the "
            "same physical card twice, said out loud rather than counted twice",
        )
        if caught is not None:
            checks.ok(
                key in str(caught),
                "and the refusal names the order holding the copy, so the operator "
                "can go and look rather than guess",
            )

        checks.raises(
            order_store.DuplicateOrderLine,
            lambda: store.read().ledger.ingest([
                record("C-3", line("9191486", 1), line("9191486", 2))
            ]),
            "an order carrying two lines for one SKU refuses — fulfilment is keyed by SKU, "
            "so a count against it would have two owners and no way to say which",
        )

        # ----------------------------------------------------- 9. the reversal, and D26
        with store.write() as snapshot:
            gone = snapshot.ledger.forget_pull(key, "9191486", ["o3", "never-pulled"])
        checks.equal(gone, 1, "the reversal removes what is there and skips what is not")
        reversed_ = store.read()
        checks.equal(
            (reversed_.ledger.fulfilled(key, "9191486"),
             reversed_.ledger.recorded(key, "9191486").copies),
            (1, ["o2"]),
            "moving the count and the ids TOGETHER — nothing else in the module writes "
            "either, so they cannot come apart anywhere but there",
        )
        checks.equal(
            store.read().ledger.holder_of("o3"),
            None,
            "and the released copy is free for another order, which is what makes the "
            "reversal a reversal rather than a decrement",
        )

        # ------------------------- 10. NO ORDER STATE REACHES `master.STATES` (D26's trap)
        #
        # The failure this is aimed at is not abstract: `_state_before_sale` scans
        # history.jsonl for the last event whose name is in `master.STATES`, so a ledger
        # that logged an order state would make a sale's reversal restore a card to it.
        checks.equal(
            sorted(master.STATES),
            sorted([
                master.CAPTURED, master.IDENTIFIED, master.SOLD, master.RETIRED, master.MOVED,
            ]),
            "the state tuple is still the five (D83 added `moved`, deliberately, at "
            "the store layer) — the ledger adds none",
        )
        capture_server.do_mark_sold(3, 2, {})
        sold_at = store.read()
        with store.write() as snapshot:
            snapshot.ledger.ingest([record("D-4", line("9191486", 1),
                                           placed_at="2026-08-30T10:00:00.000+00:00")])
        checks.equal(
            capture_server._state_before_sale(Store().history(), "3/2"),
            master.IDENTIFIED,
            "and a sale's reversal still reads the right state back out of the log with "
            "orders ingested either side of it — D26's removed/retired collision, refused "
            "by this module holding no states at all",
        )
        checks.ok(
            sold_at.inventory.cards["3/2"].state == master.SOLD,
            "(the sale itself landed, so the assertion above is about a real reversal)",
        )

        # ------------------------------------------------- 11. unfulfilled, and its order
        owing = [r.number for r in store.read().ledger.unfulfilled()]
        checks.equal(
            owing,
            ["A-1", "B-2", "D-4"],
            "orders still owing copies come back oldest-placed first — the same sequence "
            "pipeline/orders.py:order_sequence serves them in, so a screen listing what is "
            "outstanding and the resolver deciding who gets the last copy cannot disagree",
        )

        # ------------- 11b. D113: THE TWO WAYS A LINE CLOSES WITH NO CARD BEHIND IT
        #
        # `record_pull` needs a `capture_id` and is right to. But a sealed product has no
        # card record and never will, and neither has a single that shipped from a pile
        # this rig never photographed — so before D113 such a line could not be closed at
        # all, and three real orders sat open with nothing on any screen able to move them.
        # These two writers are the answer, and they are DIFFERENT: a fill says copies
        # WENT and adds to the count; a stand-down says this store is no longer accounting
        # for them and touches no count at all.
        sealed_key = order_store.order_key("TCGplayer", "E-5")
        with store.write() as snapshot:
            snapshot.ledger.ingest([record("E-5", line("8791361", 2, name="Holiday Calendar"),
                                           placed_at="2026-08-31T10:00:00.000+00:00")])
            snapshot.ledger.record_fill(sealed_key, "8791361", 2, order_store.FILL_SEALED)
        filled = store.read()
        checks.equal(
            (filled.ledger.fulfilled(sealed_key, "8791361"),
             filled.ledger.outstanding(sealed_key, "8791361"),
             filled.ledger.recorded(sealed_key, "8791361").by_hand,
             filled.ledger.recorded(sealed_key, "8791361").copies),
            (2, 0, 2, []),
            "a hand-fill closes the line with NO copy behind it — `fulfilled` 2, `by_hand` "
            "2, `copies` empty. `LineProgress` anticipated this from the beginning ('so "
            "`fulfilled` may legitimately exceed len(copies)') and nothing wrote it until "
            "D113",
        )
        checks.ok(
            all(r.number != "E-5" for r in filled.ledger.unfulfilled()),
            "and the order leaves the open list, which is the whole point of the press",
        )
        checks.equal(
            filled.ledger.progress_drift(), [],
            "and the invariant holds across a store that now carries both kinds of row",
        )
        checks.raises(
            order_store.OverFulfilled,
            lambda: store.read().ledger.record_fill(sealed_key, "8791361", 1,
                                                    order_store.FILL_SEALED),
            "a hand-fill past the order refuses rather than clamping — it is NOT "
            "idempotent (there is no identity to compare, so two presses are two claims) "
            "and this ceiling is what stops a repeated press running away",
        )
        with store.write() as snapshot:
            back = snapshot.ledger.forget_fill(sealed_key, "8791361", 99)
        checks.equal(back, 2, "the reversal is clamped, not refused — forget_pull's rule")
        checks.ok(
            store.read().ledger.recorded(sealed_key, "8791361").reason is None
            and "8791361" not in store.read().ledger.fulfilment.get(sealed_key, {}),
            "and a row that has come to record NOTHING is dropped rather than left behind "
            "— `progress` creates on write, so without this a stand-down and its undo left "
            "one all-default row per line (measured: 80 from a single bulk close)",
        )

        # A STAND-DOWN IS NOT A FILL, and this is the assertion that says so.
        with store.write() as snapshot:
            snapshot.ledger.close_line(sealed_key, "8791361",
                                       order_store.CLOSE_SHIPPED_ELSEWHERE)
        stood = store.read()
        checks.equal(
            (stood.ledger.fulfilled(sealed_key, "8791361"),
             stood.ledger.outstanding(sealed_key, "8791361"),
             stood.ledger.recorded(sealed_key, "8791361").closed),
            (0, 2, True),
            "it closes the line while `fulfilled` stays 0 and the line still OWES 2 — no "
            "copy is claimed to have gone. Measured 2026-09-06: 69 of 83 open orders were "
            "already shipped by TCGplayer, many using copies STILL in the boxes, so a fill "
            "would have made the count read right while the card stayed on the shelf",
        )
        checks.ok(
            all(r.number != "E-5" for r in stood.ledger.unfulfilled()),
            "and `unfulfilled` honours it even though `outstanding` is positive — two "
            "different questions, read separately rather than subtracted",
        )

        # THE PROPERTY THE KIND'S HOME EXISTS FOR.
        with store.write() as snapshot:
            snapshot.ledger.declare_kind(sealed_key, "8791361", "sealed")
            snapshot.ledger.ingest([record("E-5", line("8791361", 2, name="Holiday Calendar"),
                                           status="Shipped - Delivered",
                                           placed_at="2026-08-31T10:00:00.000+00:00")])
        outlived = store.read()
        checks.equal(
            (outlived.ledger.declared_kind(sealed_key, "8791361"),
             outlived.ledger.recorded(sealed_key, "8791361").closed,
             outlived.ledger.get(sealed_key).status),
            ("sealed", True, "Shipped - Delivered"),
            "THE OPERATOR'S CLAIM AND THE STAND-DOWN BOTH SURVIVE A SYNC THAT MOVED THE "
            "STATUS. This is why neither lives on `OrderRecord`: `ingest` replaces that "
            "wholesale, so a kind written there would die the moment the marketplace "
            "changed a word, and a sealed product would silently become a single again",
        )
        with store.write() as snapshot:
            snapshot.ledger.reopen_line(sealed_key, "8791361")
        checks.ok(
            store.read().ledger.recorded(sealed_key, "8791361").closed is False
            and store.read().ledger.declared_kind(sealed_key, "8791361") == "sealed",
            "and reopening reverses ONLY the stand-down — the claim about what the line "
            "IS is a different fact and is left standing",
        )
        checks.raises(
            order_store.UnknownOrderLine,
            lambda: store.read().ledger.record_fill(sealed_key, "0000000", 1,
                                                    order_store.FILL_SEALED),
            "and a hand-fill against a SKU the buyer did not order refuses, like a pull",
        )

        # ---- 11c. D113: A COPY THAT LEFT BY THE WRONG DOOR, which is the walk's own edge case
        #
        # Reproduced against the owner's store 2026-09-06: mark ONE copy sold on `#/inventory`
        # while an order wants three, then pull the other two through the walk. `#/inventory`'s
        # sale does not touch the ledger — D63 keeps them apart, rightly, because a sale is a
        # fact about a card and a fulfilment is a fact about an order — so nothing ever counted
        # the first copy. The line ended `fulfilled` 2, `outstanding` 1, `no_copies_on_hand`:
        # OPEN FOREVER, with the third copy already in the envelope.
        mixed = order_store.order_key("TCGplayer", "F-6")
        with store.write() as snapshot:
            snapshot.ledger.ingest([record("F-6", line("9191486", 3, name="Moonfall"),
                                           placed_at="2026-09-01T10:00:00.000+00:00")])
            snapshot.ledger.record_pull(mixed, "9191486", ["m1", "m2"])
        checks.equal(
            (store.read().ledger.fulfilled(mixed, "9191486"),
             store.read().ledger.outstanding(mixed, "9191486")),
            (2, 1),
            "two pulled through the walk, one still owed — and the third copy has already left "
            "the store by the sale door, so no pull can ever reach it",
        )
        with store.write() as snapshot:
            snapshot.ledger.record_fill(mixed, "9191486", 1,
                                        order_store.FILL_SOLD_SEPARATELY)
        settled = store.read()
        row = settled.ledger.recorded(mixed, "9191486")
        checks.equal(
            (settled.ledger.fulfilled(mixed, "9191486"),
             settled.ledger.outstanding(mixed, "9191486"),
             len(row.copies), row.by_hand, row.reason),
            (3, 0, 2, 1, order_store.FILL_SOLD_SEPARATELY),
            "THE TWO KINDS OF CLOSE COMPOSE ON ONE LINE: 2 pulled copies with their capture ids "
            "and 1 recorded by hand, `fulfilled` 3, and the row still says which was which. A "
            "single count could not tell the operator that two of these are traceable to a slot "
            "and one is only their word",
        )
        checks.ok(
            all(r.number != "F-6" for r in settled.ledger.unfulfilled()),
            "and the order finally closes — the state it could not reach before D113",
        )
        checks.equal(
            settled.ledger.progress_drift(), [],
            "with `fulfilled == len(copies) + by_hand` holding across a MIXED row, which is the "
            "case that would break it if a fifth writer ever moved one half alone",
        )
        # ---- 11d. D113: A LINE STANDS DOWN WITHOUT TAKING ITS SIBLINGS
        #
        # `close_line` was line-shaped from the start; `POST /orders/close` was not, so the
        # screen drew "It isn't shipping" only on single-line orders and a refunded line on a
        # three-line order had no press at all. The wire carries both scopes now and this is the
        # property that makes the line one worth having.
        many = order_store.order_key("TCGplayer", "G-7")
        with store.write() as snapshot:
            snapshot.ledger.ingest([record(
                "G-7",
                line("9191486", 1, name="Moonfall"),
                line("9197754", 2, name="Sunrise"),
                line("9199579", 1, name="Dusk"),
                placed_at="2026-09-02T10:00:00.000+00:00",
            )])
            snapshot.ledger.close_line(many, "9197754", order_store.CLOSE_NOT_SHIPPING)
        one_down = store.read()
        checks.equal(
            [one_down.ledger.recorded(many, sku).closed
             for sku in ("9191486", "9197754", "9199579")],
            [False, True, False],
            "one refunded line stands down and its two siblings are untouched — the whole "
            "reason this scope exists, and what an order-shaped close cannot express",
        )
        checks.ok(
            any(r.number == "G-7" for r in one_down.ledger.unfulfilled()),
            "and the ORDER is still open, because it still owes the other two. A stand-down "
            "answers for a line, and `unfulfilled` asks about all of them",
        )
        checks.equal(
            one_down.ledger.closed_lines(many), 1,
            "and the count of stood-down lines is readable, so a screen can say so in words",
        )
        with store.write() as snapshot:
            snapshot.ledger.reopen_line(many, "9197754")
        checks.equal(
            store.read().ledger.closed_lines(many), 0,
            "the reversal reaches only the line it names — a sibling the press never touched "
            "cannot be reopened by it either, because it was never closed",
        )

        checks.equal(
            order_store.FILL_SOLD_SEPARATELY != order_store.FILL_OFF_SYSTEM, True,
            "`sold_separately` is its own word and not `off_system`: that one means this store "
            "never photographed the card, and this card it did — the two want telling apart by "
            "whoever reads the row later",
        )

    # ------------------------------- 12. parse drops what the dataclasses do not declare
    #
    # `store/master.py:parse` filters on `__annotations__`, and a field written but not
    # declared is served, persisted, and SILENTLY DROPPED on the next reload — live-looking
    # right up until the process restarts. Asserted at all THREE levels, because filtering
    # only the record lets exactly that through one level down.
    payload = {
        "version": 1,
        "orders": {
            "tcgplayer:z-9": {
                "source": "TCGplayer", "number": "Z-9", "invented": "gone",
                "lines": [{"sku": "1", "quantity": 2, "also_invented": "gone"}],
            },
            "_note": {"source": "x", "number": "y"},
        },
        "fulfilment": {
            "tcgplayer:z-9": {"1": {"fulfilled": 1, "copies": ["z"], "third": "gone"}}
        },
    }
    parsed = order_store.Ledger.parse(payload)
    got = parsed.get("tcgplayer:z-9")
    checks.ok(
        got is not None and not hasattr(got, "invented"),
        "an undeclared field on the RECORD is dropped rather than carried",
    )
    checks.ok(
        # `got.lines` rather than `got.lines[0]` first: without the filter the line's
        # constructor raises TypeError and `parse` skips it, so the list is EMPTY — and an
        # IndexError here would abort the block instead of naming the defect.
        got is not None and got.lines and not hasattr(got.lines[0], "also_invented"),
        "and on a LINE, which filtering only the record would have let through",
    )
    checks.ok(
        not hasattr(parsed.recorded("tcgplayer:z-9", "1"), "third"),
        "and on a PROGRESS row, which is the half holding the physical claim",
    )
    checks.equal(
        parsed.get("_note"), None, "and an underscore key is skipped, as in Queue.parse"
    )
    checks.equal(
        order_store.Ledger.parse(parsed.to_payload()).to_payload(),
        parsed.to_payload(),
        "and the round trip is exact, so to_payload and parse are each other's inverse",
    )
    checks.equal(
        order_store.Ledger.parse({"orders": {"bad": {"number": "no source"}}}).orders,
        {},
        "a record that cannot be constructed is SKIPPED rather than raising — one "
        "malformed order must not take every other order's fulfilment off the screen",
    )

    # ------------------------------------- 12b. the terminal-status vocabulary (D63 amended)
    #
    # `is_terminal_status` is the ONE place the vocabulary is spelled, and it is asserted at
    # the function itself before anything downstream (`do_orders`, `_order_row`) is trusted
    # to call it correctly. The fail-safe case — an unrecognised word answers False — is the
    # one this section exists for: the owner's two rulings are useless if getting them wrong
    # for a THIRD word silently drops an order off the screen.
    checks.ok(
        order_store.is_terminal_status("Canceled"),
        "a Canceled order is recognised as terminal",
    )
    checks.ok(
        order_store.is_terminal_status(" canceled "),
        "and the comparison folds case and strips, exactly as order_key does",
    )
    checks.ok(
        order_store.is_terminal_status("Shipped - In Transit"),
        "Shipped - In Transit is recognised as terminal",
    )
    checks.ok(
        order_store.is_terminal_status("Shipped - Delivered"),
        "and so is Shipped - Delivered",
    )
    checks.ok(
        not order_store.is_terminal_status("Ready to Ship"),
        "Ready to Ship is NOT terminal — it is the operator's real queue",
    )
    checks.ok(
        not order_store.is_terminal_status("Completed - Paid"),
        "Completed - Paid is deliberately NOT terminal — ruling 3's one-time reconcile "
        "handles those 513 orders, not this function; payment clearing says nothing about "
        "whether a card shipped",
    )
    checks.ok(
        not order_store.is_terminal_status("Quantum Superposition"),
        "AND AN UNRECOGNISED STATUS ANSWERS FALSE — THE FAIL-SAFE CASE. A closed vocabulary "
        "compared against an open-ended feed string must never treat 'never seen it' as "
        "'must be finished', or a marketplace that learns a new word silently vanishes every "
        "order carrying it",
    )
    checks.ok(
        not order_store.is_terminal_status(None),
        "and None answers False too — an order with no status yet is never terminal",
    )
    checks.ok(
        not order_store.is_terminal_status(""),
        "and an empty string answers False rather than matching the empty-key edge case",
    )

    # ------------------------------------ 13. the lock is never held across I/O, checked
    #
    # `files.exclusive` polls at 50ms and gives up at 30s while the feeder captures a card
    # every 623ms, so a fetch down here would stall real capture. It is a property of the
    # module's imports rather than of its behaviour, so it is asserted that way — a
    # behavioural test would have to hang to fail.
    tree = ast.parse(Path(order_store.__file__).read_text("utf-8"))
    imported = set()
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
            modules.add(node.module)
    checks.equal(
        sorted(imported & {"urllib", "http", "socket", "requests", "subprocess", "pathlib"}),
        [],
        "store/orders.py imports nothing that can reach the network or the filesystem — "
        "the ledger is a data structure and session.py does its I/O, inside the lock it "
        "already holds",
    )
    checks.equal(
        sorted(m for m in modules if m.split(".")[0] in {"store", "pipeline"}),
        ["store.rows"],
        "and nothing from `pipeline`, which is why OrderLine is declared twice: the edge "
        "runs the other way and a cycle is what reusing the resolver's would cost. "
        "`store.rows` is the one package import (D88): a container with no I/O, which is "
        "what lets the two maps be tables without this module learning what a table is",
    )

# -------------------------------------------------------- the one-time backlog reconcile


def check_order_reconcile_backlog(checks: Checks) -> None:
    """`POST /orders/reconcile-backlog` — the two-year backlog `is_terminal_status` cannot see
    (D203).

    THE ONE ASSERTION THIS FILE CARES ABOUT MOST: closing a backlog order claims NO physical
    copy. `store_tables()`'s `cards` table is compared byte-for-byte before and after the
    press — a stand-down that ever touched inventory would pass every other assertion here
    and still be the defect D113 exists to prevent one register up.

    THE SECOND: a candidate carrying a status this store has never proposed closing before —
    "Ready to Ship" beside "Completed - Paid", at the SAME age — draws its OWN row in the
    breakdown rather than being folded into one count. Nothing in the predicate tells the two
    apart, on purpose: CLAUDE.md itself refuses a hard-coded status exclusion here, because
    that reintroduces the exact guess `is_terminal_status`'s own docstring argues against one
    register down. What this route protects a live order WITH is that live work is recent —
    the cutoff excludes it without reading a status at all — and what it protects the operator
    WITH, for the case a status this store has never proposed closing shares the cutoff's age
    anyway, is visibility before the press rather than after it.
    """
    checks.note("")
    checks.note("ORDER RECONCILE — POST /orders/reconcile-backlog (D203)")

    def line(sku, quantity=1, **extra) -> dict:
        row = {"sku": sku, "quantity": quantity}
        row.update(extra)
        return row

    def paste(number, *lines, **extra) -> dict:
        order = {
            "source": "TCGplayer",
            "number": number,
            "placed_at": extra.pop("placed_at", "2024-01-01T10:00:00.000+00:00"),
            "status": extra.pop("status", "Completed - Paid"),
            "lines": list(lines),
        }
        order.update(extra)
        return {"orders": [order]}

    with isolated_home():
        # A-1: the ordinary candidate — old, Completed - Paid, nothing recorded.
        capture_server.do_order_ingest(paste("A-1", line("sku-a", 1)))
        # B-2: LIVE WORK, RECENT — Ready to Ship, placed AFTER the cutoff below, zero
        # recorded. This is the realistic protective case: live work is recent, so an
        # honest cutoff on the backlog excludes it without any status ever being read.
        capture_server.do_order_ingest(
            paste("B-2", line("sku-b", 1), status="Ready to Ship",
                  placed_at="2026-09-05T10:00:00.000+00:00")
        )
        # C-3: PART-PULLED — old, Completed - Paid, but one copy is already recorded
        # against it. Live work by the "zero recorded" test alone.
        capture_server.do_order_ingest(paste("C-3", line("sku-c", 2)))
        c_key = order_store.order_key("TCGplayer", "C-3")
        with Store().write() as snapshot:
            snapshot.ledger.record_fill(c_key, "sku-c", 1, order_store.FILL_OFF_SYSTEM)
        # D-4: TERMINAL — the feed itself says this order is done. Excluded by `open`
        # before the reconcile predicate ever runs.
        capture_server.do_order_ingest(
            paste("D-4", line("sku-d", 1), status="Shipped - Delivered")
        )
        # E-5: TOO RECENT — placed after the cutoff, so `placed_at[:10] >= cutoff` excludes
        # it regardless of status.
        capture_server.do_order_ingest(
            paste("E-5", line("sku-e", 1), placed_at="2026-09-13T10:00:00.000+00:00")
        )
        # F-6: NO DATE AT ALL — an order this ledger somehow holds with no `placed_at`.
        # Never a candidate: there is no date to test against a cutoff.
        capture_server.do_order_ingest(paste("F-6", line("sku-f", 1), placed_at=None))
        # G-7: THE CASE THE BREAKDOWN EXISTS FOR. Old, zero recorded, exactly like A-1 —
        # but "Ready to Ship" rather than "Completed - Paid". Nothing about the predicate
        # tells these two apart, on purpose: CLAUDE.md's own instruction refuses a
        # hard-coded status exclusion here, because that reintroduces the exact guess
        # `is_terminal_status`'s docstring already argues against. The safety this route
        # offers is that the breakdown shows "Ready to Ship: 1" BEFORE the press, not that
        # it silently protects a same-aged live order from one — an operator who presses
        # anyway gets exactly what the breakdown told them they would.
        capture_server.do_order_ingest(
            paste("G-7", line("sku-g", 1), status="Ready to Ship")
        )

        cutoff = "2026-01-01"
        before = store_tables()["cards"]

        # -------------------------------------------------------------- 1. the preview
        preview = capture_server.do_order_reconcile({"preview": True, "cutoff": cutoff})
        checks.equal(
            preview["writes_nothing"], True,
            "the preview says of itself that it writes nothing, `do_order_fetch`'s own field",
        )
        checks.equal(
            preview["cutoff"], cutoff,
            "the cutoff it used rides back on the answer rather than being assumed",
        )
        checks.equal(
            preview["total"], 2,
            "A-1 and G-7: B-2 and E-5 are not before the cutoff, C-3 is part-pulled, D-4 "
            "is terminal, and F-6 carries no placed_at to test",
        )
        checks.equal(
            preview["breakdown"],
            [{"status": "Completed - Paid", "count": 1}, {"status": "Ready to Ship", "count": 1}],
            "THE WHOLE SAFETY THIS ROUTE OFFERS: the breakdown is BY FEED STATUS, so G-7 — "
            "same age, same zero-recorded shape as A-1, but 'Ready to Ship' — shows up as "
            "its OWN row rather than being folded into one count an operator could misread "
            "as entirely backlog",
        )
        checks.equal(
            store_tables()["cards"], before,
            "the preview is read-only: the cards table is untouched",
        )

        # ---------------------------------------------------------------- 2. the press
        pressed = capture_server.do_order_reconcile({"cutoff": cutoff})
        checks.equal(
            (pressed["orders"], pressed["moved"], pressed["lines"]),
            (2, 2, 2),
            "A-1 and G-7 close — the breakdown told the operator G-7 was there and the "
            "press closes exactly what the preview named, never more and never less",
        )
        checks.equal(
            sorted(pressed["closed"], key=lambda row: row["number"]),
            [{"source": "TCGplayer", "number": "A-1"}, {"source": "TCGplayer", "number": "G-7"}],
            "the receipt names what closed, by (source, number) — what `reopenOrders` takes",
        )
        checks.equal(
            pressed["reason"], order_store.CLOSE_SHIPPED_ELSEWHERE,
            "never a configurable reason — this route writes exactly one, D113's own "
            "'it went out; this store did not track it'",
        )
        checks.equal(
            store_tables()["cards"], before,
            "THE ASSERTION THIS ROUTE EXISTS TO PASS: closing A-1 and G-7 claimed no "
            "physical copy. The cards table is byte-identical to before the press — a "
            "stand-down that ever touched inventory would be the exact defect D113 was "
            "built to prevent",
        )
        a_key = order_store.order_key("TCGplayer", "A-1")
        ledger_after = Store().read().ledger
        checks.equal(
            (ledger_after.fulfilled(a_key, "sku-a"), ledger_after.recorded(a_key, "sku-a").closed),
            (0, True),
            "A-1 is closed and STILL owes its copy — `fulfilled` stayed 0. Nothing was filled",
        )
        checks.ok(
            all(r.number not in ("A-1", "G-7") for r in ledger_after.unfulfilled()),
            "and both have left the open list",
        )
        checks.ok(
            any(r.number == "B-2" for r in ledger_after.unfulfilled())
            and any(r.number == "C-3" for r in ledger_after.unfulfilled())
            and any(r.number == "E-5" for r in ledger_after.unfulfilled()),
            "B-2 (too recent), C-3 (part-pulled) and E-5 (too recent) are all still open — "
            "none of them was swept",
        )

        # ------------------------------------------------------ 3. idempotence, said out loud
        again = capture_server.do_order_reconcile({"cutoff": cutoff})
        checks.equal(
            (again["orders"], again["moved"], again["lines"], again["closed"]),
            (0, 0, 0, []),
            "a second press over the same cutoff finds A-1 and G-7 already closed and "
            "therefore no longer open, so the predicate recomputes to nothing rather than "
            "re-stamping either — the same construction `close_line` gives every other "
            "write on this screen",
        )
        checks.equal(
            store_tables()["cards"], before,
            "and still nothing was ever claimed against inventory",
        )

        # --------------------------------------------------------------------- 4. the undo
        undone = capture_server.do_order_close({"orders": [{"source": "TCGplayer", "number": "A-1"}], "undo": True})
        checks.ok(undone["moved"] == 1, "the existing D113 reversal reopens what this route closed")
        reopened = Store().read().ledger
        checks.ok(
            any(r.number == "A-1" for r in reopened.unfulfilled()),
            "A-1 is open again, and `reopenOrders` needed no new mechanism to do it",
        )

        # ----------------------------------------------------------------- 5. bad cutoffs
        checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_order_reconcile({"cutoff": "not-a-date"}),
            "a cutoff that is not YYYY-MM-DD refuses rather than being parsed loosely",
        )
        checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_order_reconcile({"reason": "shipped_elsewhere"}),
            "an unknown field refuses — this route never takes a reason; it writes exactly "
            "one",
        )

        # search-server lane, 2026-09-24 (from the Orders review): a cutoff after today
        # would stand down every open order, live Ready-to-ship included — the SAME
        # hazard HOR-04 found in the screen's own preview, at the server this time. The
        # screen already disables the press past today; this is the SECOND guard.
        future = str(int(order_store.today()[:4]) + 1) + order_store.today()[4:]
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_order_reconcile({"preview": True, "cutoff": future}),
            "a cutoff after today refuses, even under preview, which writes nothing",
        )
        if caught is not None:
            checks.equal(
                caught.code, "cutoff_in_future",
                "and the refusal names itself so a client can tell it apart from "
                "cutoff_invalid's plain formatting complaint",
            )
        checks.equal(
            capture_server.do_order_reconcile({"preview": True, "cutoff": order_store.today()})["cutoff"],
            order_store.today(),
            "today itself is still a valid cutoff — the refusal is strictly AFTER today, "
            "never on it",
        )

        # S4, THE OPUS REVIEW, 2026-09-25: THE BOUNDARY ITSELF, NOT A YEAR PAST IT. The
        # `future` case above jumps a whole year ahead, which a looser mutant (a cutoff
        # refused only past, say, 30 days out) would still pass — it never asks the one
        # question the guard's own docstring answers ("NEVER AFTER TODAY... strictly AFTER
        # today, never on it"): where exactly the line falls. `tomorrow`, one real UTC day
        # past `order_store.today()`, is that line.
        tomorrow = (
            datetime.now(timezone.utc) + timedelta(days=1)
        ).strftime("%Y-%m-%d")
        caught = checks.raises(
            capture_server.BadRequest,
            lambda: capture_server.do_order_reconcile({"preview": True, "cutoff": tomorrow}),
            "exactly tomorrow refuses too — the boundary is today, not 'today plus some "
            "slack'",
        )
        if caught is not None:
            checks.equal(
                caught.code, "cutoff_in_future",
                "with the same refusal code as a cutoff a year out",
            )


def check_order_line_sealed_from_title(checks: Checks) -> None:
    """A sold sealed box whose SKU left the `skus` table, on a paste with no condition cell,
    still answers `Unopened` (Sales' Singles/Sealed switch reads that one condition). A
    single's name, and a name with "Box" in it but no `- Unopened` suffix, stay untouched."""

    class NoSkus:
        entries: dict = {}

    def wire(name: str) -> dict:
        return capture_server._order_line_wire(order_store.OrderLine(sku="1", quantity=1, name=name), NoSkus())

    checks.equal(
        wire("Pokemon - SV09: Journey Together: Journey Together Booster Box - Unopened")["condition"],
        "Unopened", "a sealed title with no sku row and no condition reads Unopened",
    )
    checks.equal(wire("Pokemon - SV09: Journey Together: N's Zoroark - 100/159 - Near Mint")["condition"],
                 None, "a single's title never gains a condition")
    checks.equal(wire("Pokemon - Some Booster Box Promo")["condition"], None,
                 "a name with Box in it but no Unopened suffix is never guessed sealed")

    from types import SimpleNamespace

    class OnePieceSkus:
        entries = {"1": SimpleNamespace(condition="", rarity="SR", product_line="One Piece Card Game", set_name="")}

    def rarity_of(code: str, skus) -> object:
        return capture_server._order_line_wire(
            order_store.OrderLine(sku="1", quantity=1, name="x", rarity=code), skus
        )["rarity"]

    checks.equal(rarity_of("SR", OnePieceSkus()), "Super Rare", "a One Piece SR reads Super Rare")
    checks.equal(rarity_of("DON!!", OnePieceSkus()), "DON!!", "a code no ruling names stays verbatim")
    checks.equal(rarity_of("SR", NoSkus()), "SR", "with no game known, a code is never guessed")

# ---------------------------------------------------------------- the order screen


def check_order_screen(checks: Checks) -> None:
    """`GET /orders`, `POST /orders/ingest` and `POST /orders/pull` — the order screen's own
    three routes, and the seam where D63's ledger meets `pipeline/orders.py`'s resolver.

    `check_order_resolver` covers the resolver over an `Inventory` and `check_order_ledger`
    covers the ledger over a file. NEITHER OF THEM CAN FAIL ON THE ROUTE, and the route is
    where the two are joined: it composes the orders into engine objects, resolves them in
    ONE pass, renders a place per pick, then writes the ledger and sells the copies inside a
    single `Store.write()`. Every defect below lives in that composition and in nothing the
    other two sections read.

    THE CASE THIS BLOCK EXISTS FOR IS THE DOUBLE BOOK THROUGH THE ROUTE. `resolve_all` is the
    only entry point and there is deliberately no `resolve_one`, so a handler that looped the
    resolver per order would pass every assertion in `check_order_resolver` — that section
    calls `resolve_all` itself — and hand two buyers the same physical card. It is asserted
    on the ROUTE's payload, oldest order carrying the pick and the newer carrying `short`
    with no picks at all, because that is the only place the mistake is visible.

    FOUR MORE PROPERTIES, EACH ONE A THING A PLAUSIBLE BUILD GETS WRONG:

      the reason vocabulary   `sorted(counts) == sorted(orders.LINE_REASONS)`, so a seventh
                              reason added to `pipeline/orders.py` and not to the screen
                              fails HERE rather than as a key the app draws as blank.
      one label formula       every pick's `place.label` is compared against
                              `cli/resolve.py:box_views(...).at(...).label` — the reporter's
                              renderer, the other implementation of D58's walk. A second
                              renderer on this screen is the failure this repo has recorded
                              three times, and the two are already asserted equal elsewhere
                              for exactly one card.
      the PII backstop        `_reject_unknown` runs FIRST at every level of the ingest body,
                              so an unprojected paste carrying `buyer` REFUSES BY NAME
                              instead of being stored with the buyer's fields quietly
                              trimmed. A trim is silent; a refusal sends the caller back to
                              project. Both levels are asserted, and both leave nothing.
      the receipt is pre-write A pull's `places` are computed before anything is sold, because
                              a sale moves the box's occupancy (D58) — so the receipt names
                              where the operator just was rather than where the box has
                              closed up to. Asserted as a DIFFERENCE: the answer's label and
                              a `_Places` built after the call disagree, and the second one
                              is `join.departed_label`.

    IDEMPOTENCE IS BYTE EQUALITY AND NEVER A ROW COUNT, which is `check_order_ledger`'s
    lesson applied one layer up: "the file holds one order" is satisfied identically by a
    second ingest changing nothing and by a second ingest throwing the fulfilment away and
    re-ingesting over the top. So `orders.json`, `inventory.json` AND `history.jsonl` are all
    compared as bytes across the second identical paste.

    ITS OWN `isolated_home` — FOUR OF THEM, and that is this file's own repeated lesson
    rather than caution. This block writes cards, listings, sales, ledger rows and history
    lines; sharing a store with `check_order_ledger`'s, which counts all five, has already
    taken sibling assertions red twice in this file. The four are split so the empty-store
    case has an empty store to be right about and the double-book case has exactly one copy.
    """
    checks.note("")
    checks.note(
        "ORDER SCREEN — GET /orders, POST /orders/ingest, POST /orders/pull (D63, D69)"
    )

    def line(sku, quantity=1, **extra) -> dict:
        row = {"sku": sku, "quantity": quantity}
        row.update(extra)
        return row

    def paste(number, *lines, **extra) -> dict:
        order = {
            "source": "TCGplayer",
            "number": number,
            "placed_at": extra.pop("placed_at", "2026-08-27T10:00:00.000+00:00"),
            "lines": list(lines),
        }
        order.update(extra)
        return {"orders": [order]}

    def target(box: int, index: int, capture_id: str) -> dict:
        return {"box": box, "index": index, "capture_id": capture_id}

    def stock(box: int, count: int, sku: str, prefix: str = "o") -> None:
        """`count` identified copies of one SKU in `box`, each with its own capture id."""
        # THROUGH `capture_payload`, WHICH MINTS A PHOTOGRAPH PER CALL. The bytes were keyed
        # on the index within the box, so box 3's card 1 and box 4's card 1 sent the same
        # blob — and two cards cannot share one name since D172 (`cards_cid` is UNIQUE).
        for at in range(1, count + 1):
            capture_server.do_capture(capture_payload(box, capture_id=f"{prefix}{at}"))
        with Store().write() as snapshot:
            for at in range(1, count + 1):
                snapshot.inventory.record_identification(
                    f"{box}/{at}", name="Moonfall", number="198/219",
                    printed_total="219", confidence="high",
                )
                snapshot.inventory.cards[f"{box}/{at}"].sku = sku

    # ------------------------------------------------- 1. the empty store, and its vocabulary
    with isolated_home():
        empty = answers(checks, capture_server.do_orders, "GET /orders answers an empty store")
        if empty is not None:
            checks.equal(empty["orders"], [], "with no orders at all")
            checks.equal(
                empty["summary"],
                "0 orders",
                "and a summary that says so — the ledger's own sentence, so a screen never "
                "has to compose one out of two counts",
            )
            checks.equal(
                sorted(empty["resolution"]["counts"]),
                sorted(orders.LINE_REASONS),
                "EVERY REASON IS PUBLISHED INCLUDING THE ZEROS, and the key set is "
                "`pipeline/orders.py:LINE_REASONS` itself rather than a literal — so a "
                "seventh reason added there and not carried through this route fails HERE, "
                "rather than as a count the app draws as a blank row. Reporting only the "
                "reasons that fired would make 'nothing was short' and 'nothing was "
                "checked' the same output",
            )

    # ------------------------------ 2-5. the ingest: idempotence, the PII backstop, the kinds
    with isolated_home():
        stock(3, 3, "9191486")
        moonfall = paste("A-1", line("9191486", 1, name="Moonfall"))

        first = answers(checks, lambda: capture_server.do_order_ingest(moonfall),
                        "POST /orders/ingest takes one pasted order")
        if first is not None:
            checks.equal(
                (first["added"], first["wrote_nothing"]),
                (1, False),
                "the first paste reports one order added and says it wrote something",
            )

        def bytes_now() -> dict:
            tables = store_tables()
            return {name: tables[name] for name in ("orders", "fulfilment", "cards", "events")}

        before = bytes_now()
        again = answers(checks, lambda: capture_server.do_order_ingest(moonfall),
                        "and the identical paste a second time is accepted rather than refused")
        after = bytes_now()
        if again is not None:
            checks.equal(
                (again["added"], again["changed"], again["unchanged"], again["wrote_nothing"]),
                (0, 0, 1, True),
                "the second press reports the order UNCHANGED and that it wrote nothing — "
                "there is deliberately no `last_synced_at`, which would move on every press",
            )
        checks.equal(
            after,
            before,
            "AND EVERY TABLE IS ROW-IDENTICAL ACROSS IT — orders, fulfilment, cards and the "
            "history. ROW EQUALITY, NEVER A ROW COUNT: 'the store holds one order' "
            "is satisfied identically by a ledger that learned nothing and by a ledger that "
            "threw its fulfilment away and re-ingested the same order over the top, which is "
            "D54's lesson said one layer up",
        )

        def ledger_now():
            return Store().read().ledger

        held = len(ledger_now().orders)
        # `buyer` NOW SUCCEEDS, ON THE OWNER'S RULING (D193) — the
        # display name is the one fact about a person this ledger keeps, and a paste that
        # carries it stores it exactly as it stores `status` or `placed_at`.
        named_paste = answers(
            checks,
            lambda: capture_server.do_order_ingest(
                paste("B-2", line("9191486", 1), buyer="Buyer001 Placeholder")
            ),
            "AN ORDER CARRYING `buyer` NOW INGESTS — the owner's ruling narrowed the "
            "allowlist rather than widening a refusal",
        )
        if named_paste is not None:
            checks.equal(named_paste["added"], 1, "one order added, with a name on it")
        checks.equal(
            ledger_now().get(order_store.order_key("TCGplayer", "B-2")).buyer,
            "Buyer001 Placeholder",
            "and the ledger holds the name verbatim",
        )
        checks.equal(
            next(row["buyer"] for row in capture_server.do_orders()["orders"]
                 if row["number"] == "B-2"),
            "Buyer001 Placeholder",
            "and GET /orders draws it",
        )
        at_address = _refusal_text(
            lambda: capture_server.do_order_ingest(
                paste(
                    "B-3", line("9191486", 1),
                    shippingAddress={"line1": "101 Example St"},
                )
            )
        )
        checks.ok(
            at_address is not None
            and at_address[0] == "field_not_settable"
            and "shippingAddress" in at_address[1],
            "BUT `shippingAddress` STILL REFUSES BY NAME. The owner's ruling narrowed what "
            "was excluded; it did not widen what is kept — address, email, payment and the "
            "transaction breakdown stay out by the same allowlist mechanism",
            f"got {at_address!r}",
        )
        at_email = _refusal_text(
            lambda: capture_server.do_order_ingest(
                paste("B-4", line("9191486", 1), email="buyer@example.com")
            )
        )
        checks.ok(
            at_email is not None
            and at_email[0] == "field_not_settable"
            and "email" in at_email[1],
            "and `email` refuses the same way",
            f"got {at_email!r}",
        )
        at_line = _refusal_text(
            lambda: capture_server.do_order_ingest(
                paste("B-2", line("9191486", 1, buyer_email="someone@example.com"))
            )
        )
        checks.ok(
            at_line is not None
            and at_line[0] == "field_not_settable"
            and "buyer_email" in at_line[1],
            "and a LINE carrying `buyer_email` refuses the same way and names it too — the "
            "PII backstop is at EVERY level of the ingest body, not only at the top one",
            f"got {at_line!r}",
        )
        checks.equal(
            len(ledger_now().orders),
            held + 1,
            "and NOTHING WAS WRITTEN BY ANY OF THE THREE REFUSALS — only `B-2`'s named paste "
            "landed. The paste is validated whole before the store lock is taken, so a body "
            "carrying one bad field stores no part of itself",
        )

        sealed = answers(
            checks,
            lambda: capture_server.do_order_ingest(
                paste("S-1", line("777001", 1, name="Booster Box", kind="sealed"))
            ),
            "a line declaring `kind: sealed` ingests — the feed's own word, stored verbatim",
        )
        if sealed is not None:
            checks.equal(sealed["added"], 1, "and it is a new order")
        screen = answers(checks, capture_server.do_orders,
                         "GET /orders draws the store with a sealed line on it")
        if screen is not None:
            sealed_lines = [
                row
                for order in screen["resolution"]["orders"]
                for row in order["lines"]
                if order["number"] == "S-1"
            ]
            checks.equal(
                [(row["reason"], row["picks"], row["on_hand"]) for row in sealed_lines],
                [("not_a_single", [], 0)],
                "and it is drawn `not_a_single` with NO picks and NO copies on hand. The "
                "reason is produced BEFORE any inventory lookup, and the order matters: "
                "asking the store about a playmat SKU answers `sku_unseen`, which reads as "
                "'we have lost track of a card' and sends the owner hunting through boxes "
                "for a playmat",
            )
        refusal(
            checks,
            lambda: capture_server.do_order_ingest(
                paste("N-1", line("777002", 1, kind="nonsense"))
            ),
            "line_kind_invalid",
            "and a kind outside `LINE_KINDS` refuses AT THE DOOR. `store/orders.py` leaves "
            "kind unvalidated on purpose — a closed vocabulary in a document would refuse a "
            "marketplace that learned a new product category — so this is the route's job: "
            "a stored kind outside the tuple raises `UnknownLineKind` at resolve time and "
            "takes the WHOLE order screen down for one bad paste",
        )

    # ------------------------- 6-7. both orders share one copy, and the one label formula
    with isolated_home():
        stock(3, 1, "9191486")
        # NEWEST FIRST, deliberately: it used to matter for who "won" the one copy under
        # the exclusive draw; it no longer decides who is OFFERED anything (2026-09-16),
        # only the order the answer reports orders back in.
        booked = answers(
            checks,
            lambda: capture_server.do_order_ingest(
                {
                    "orders": [
                        {
                            "source": "TCGplayer", "number": "NEW",
                            "placed_at": "2026-08-29T10:00:00.000+00:00",
                            "lines": [line("9191486", 1)],
                        },
                        {
                            "source": "TCGplayer", "number": "OLD",
                            "placed_at": "2026-08-27T10:00:00.000+00:00",
                            "lines": [line("9191486", 1)],
                        },
                    ]
                }
            ),
            "two orders for one SKU ingest in one paste, newest first",
        )
        if booked is not None:
            checks.equal(booked["added"], 2, "and both are recorded")

        drawn = answers(checks, orders_with_picks,
                        "GET /orders resolves both against the one copy on hand")
        if drawn is not None:
            by_number = {
                order["number"]: order["lines"][0] for order in drawn["resolution"]["orders"]
            }
            checks.equal(
                (by_number["OLD"]["reason"], len(by_number["OLD"]["picks"])),
                ("resolved", 1),
                "the older order is `resolved` — it wants 1 and 1 is on hand",
            )
            checks.equal(
                (by_number["NEW"]["reason"], len(by_number["NEW"]["picks"]),
                 by_number["NEW"]["on_hand"]),
                ("resolved", 1, 1),
                "AND THE NEWER ONE IS ALSO `resolved`, OFFERED THE SAME ONE COPY — asserted "
                "on the ROUTE's payload. Until 2026-09-16 this was `short` with no picks: "
                "the pool was exclusive and the older order took the copy alone. The owner "
                "ruled every copy fungible, so both orders see the same one copy and both "
                "read `resolved`; the guard against shipping it twice is "
                "`store/orders.py:record_pull`'s `CopyAlreadyPulled` at the PULL, not "
                "anything this route's resolution withholds. RED against the pre-2026-09-16 "
                "code, which answered `short` here",
            )
            checks.equal(
                by_number["OLD"]["picks"][0]["capture_id"],
                by_number["NEW"]["picks"][0]["capture_id"],
                "and it is literally the SAME physical copy on both lines",
            )

            checks.equal(
                sorted(drawn["resolution"]["orders"][0]),
                ["complete", "key", "lines", "number", "outstanding"],
                "THE ORDER SCREEN DRAWS NO POSTAGE LANE, and that is a prohibition rather "
                "than an omission to fill in later (D69). `pipeline/orders.py` carries an "
                "`OrderResolution.ships_in_an_envelope` and this route does NOT put it on "
                "the wire: the shipping lane is D61's answer, computed from an export this "
                "screen has never read, and a second answer to it here would be drawn from "
                "data that cannot produce one. Asserted as the whole key set, so the field "
                "cannot arrive quietly",
            )
            checks.equal(
                sorted(by_number["OLD"]),
                ["fulfilled", "line", "on_hand", "order", "order_key", "outstanding", "owed",
                 "picks", "pooled", "reason", "retired", "sku", "sold", "wanted"],
                "and a LINE is the reason, the breakdown behind it and the copies it found "
                "— fourteen keys, no lane and no stamp among them",
            )

            inventory = Store().read().inventory
            views = resolve.box_views(inventory)
            drawn_labels = [
                pick["place"]["label"]
                for order in drawn["resolution"]["orders"]
                for row in order["lines"]
                for pick in row["picks"]
            ]
            expected_labels = [
                views.get(pick["box"], join.BoxView()).at(pick["box"], pick["index"]).label
                for order in drawn["resolution"]["orders"]
                for row in order["lines"]
                for pick in row["picks"]
            ]
            checks.ok(bool(drawn_labels), "the screen drew at least one pick to compare")
            checks.equal(
                drawn_labels,
                expected_labels,
                "ONE LABEL FORMULA. Every pick's `place.label` is what "
                "`cli/resolve.py:box_views` renders for the same position — the reporter's "
                "walk, which is the OTHER implementation of D58's counting space. A second "
                "renderer on this screen would print `Section 1 · Card 300` beside an app "
                "drawing `Section 4 · Card 48`, with nothing saying which is which",
            )

    # ---------------------- 7b. `open` vs RESOLVED (D63 amended 2026-09-13, then 2026-09-16)
    #
    # The owner's `open` rulings are UNCHANGED: a Canceled order is never open, and a
    # Shipped-or-Delivered order closes on the feed's own word — but ONLY those recognised
    # words, and never a guess. WHAT CHANGED is which orders get RESOLVED: until
    # 2026-09-16 a terminal order was excluded from the resolution pool outright (D113's
    # priority bug, a shipped order taking a copy ahead of a live one because it was
    # older). That hazard cannot occur any more — no order's draw withholds anything from
    # another's — so every order that still owes copies is resolved now, terminal or not,
    # and `open` is the only field a terminal status still moves. RED against the
    # pre-2026-09-16 code, which answered only 3 of these 6 orders in `resolution.orders`.
    with isolated_home():
        stock(3, 1, "9191486")
        answers(
            checks,
            lambda: capture_server.do_order_ingest(
                {
                    "orders": [
                        {
                            "source": "TCGplayer", "number": "CANCELED-1",
                            "placed_at": "2026-08-20T10:00:00.000+00:00",
                            "status": "Canceled",
                            "lines": [line("9191486", 1)],
                        },
                        {
                            "source": "TCGplayer", "number": "TRANSIT-1",
                            "placed_at": "2026-08-21T10:00:00.000+00:00",
                            "status": "Shipped - In Transit",
                            "lines": [line("9191486", 1)],
                        },
                        {
                            "source": "TCGplayer", "number": "DELIVERED-1",
                            "placed_at": "2026-08-22T10:00:00.000+00:00",
                            "status": "Shipped - Delivered",
                            "lines": [line("9191486", 1)],
                        },
                        {
                            "source": "TCGplayer", "number": "READY-1",
                            "placed_at": "2026-08-23T10:00:00.000+00:00",
                            "status": "Ready to Ship",
                            "lines": [line("9191486", 1)],
                        },
                        {
                            "source": "TCGplayer", "number": "PAID-1",
                            "placed_at": "2026-08-24T10:00:00.000+00:00",
                            "status": "Completed - Paid",
                            "lines": [line("9191486", 1)],
                        },
                        {
                            "source": "TCGplayer", "number": "MYSTERY-1",
                            "placed_at": "2026-08-25T10:00:00.000+00:00",
                            "status": "Quantum Superposition",
                            "lines": [line("9191486", 1)],
                        },
                    ]
                }
            ),
            "six orders for one SKU, one copy on hand, oldest carrying the terminal statuses",
        )
        drawn = answers(
            checks, capture_server.do_orders,
            "GET /orders resolves the whole set against the store's one copy",
        )
        if drawn is not None:
            by_number = {row["number"]: row for row in drawn["orders"]}
            checks.equal(
                (by_number["CANCELED-1"]["open"], by_number["CANCELED-1"]["terminal"]),
                (False, True),
                "a Canceled order is never open, even though it owes a copy nobody has "
                "pulled — ruling 1",
            )
            checks.equal(
                (by_number["TRANSIT-1"]["open"], by_number["TRANSIT-1"]["terminal"]),
                (False, True),
                "Shipped - In Transit closes on the feed's own word — ruling 2",
            )
            checks.equal(
                (by_number["DELIVERED-1"]["open"], by_number["DELIVERED-1"]["terminal"]),
                (False, True),
                "and so does Shipped - Delivered",
            )
            checks.equal(
                (by_number["READY-1"]["open"], by_number["READY-1"]["terminal"]),
                (True, False),
                "Ready to Ship is unaffected by any of this and stays open — the "
                "operator's real queue",
            )
            checks.equal(
                (by_number["PAID-1"]["open"], by_number["PAID-1"]["terminal"]),
                (True, False),
                "Completed - Paid is UNCHANGED BY THIS PR — ruling 3's one-time reconcile "
                "handles those 513 orders on the owner's real store, not this predicate",
            )
            checks.equal(
                (by_number["MYSTERY-1"]["open"], by_number["MYSTERY-1"]["terminal"]),
                (True, False),
                "AND THE UNRECOGNISED STATUS STAYS OPEN — THE FAIL-SAFE CASE. A word this "
                "store has never seen must never silently close an order; it falls through "
                "to the ledger's own `unfulfilled` answer, which still says this order owes "
                "a copy",
            )
            resolved_numbers = {
                order["number"] for order in drawn["resolution"]["orders"]
                if order["lines"][0]["reason"] == "resolved"
            }
            checks.equal(
                resolved_numbers,
                {"CANCELED-1", "TRANSIT-1", "DELIVERED-1", "READY-1", "PAID-1", "MYSTERY-1"},
                "AND ALL SIX ORDERS RESOLVE — EVEN THE THREE TERMINAL ONES — because the "
                "one copy is fungible and every order wanting one is offered it. This is "
                "the change from 2026-09-16: the old exclusive draw gave the copy to "
                "'the oldest non-terminal order' alone; there is no 'the one order that "
                "gets it' any more, by the owner's own ruling. RED against the pre-2026-09-16 "
                "code, which resolved only READY-1 here",
            )
            checks.equal(
                {order["number"] for order in drawn["resolution"]["orders"]},
                {"CANCELED-1", "TRANSIT-1", "DELIVERED-1", "READY-1", "PAID-1", "MYSTERY-1"},
                "and the resolution answers for EVERY order that still owes a copy, "
                "terminal or not — the old exclusion from the resolution pool (never only "
                "from the summary list) is gone along with the priority hazard it existed "
                "to prevent. `open` is still false for the three terminal ones (asserted "
                "above): a terminal order resolving with a real pick does not make it draw "
                "open on screen, because the screen branches on `open`/`terminal` and not "
                "on whether a resolution answers for the order",
            )

    # ------------------------------- 7c. a fully-pulled order is never resolved, terminal or not
    #
    # `Ledger.unfulfilled()` is what decides `resolve_keys` now (no terminal filter). An
    # order with nothing left to pull must still not appear in `resolution.orders` at
    # all — it does not need an answer, and giving it a picks list over a copy it has
    # already recorded would suggest there is something still to walk to.
    with isolated_home():
        stock(3, 1, "9191486", prefix="full")
        answers(
            checks,
            lambda: capture_server.do_order_ingest(
                {
                    "orders": [
                        {
                            "source": "TCGplayer", "number": "DONE-1",
                            "placed_at": "2026-08-20T10:00:00.000+00:00",
                            "status": "Shipped - Delivered",
                            "lines": [line("9191486", 1)],
                        },
                    ]
                }
            ),
            "one order for the one copy on hand, already shipped",
        )
        answers(
            checks,
            lambda: capture_server.do_order_pull(
                {
                    "source": "TCGplayer", "number": "DONE-1", "sku": "9191486",
                    "targets": [target(3, 1, "full1")],
                }
            ),
            "and it is fully pulled",
        )
        drawn = answers(
            checks, capture_server.do_orders,
            "GET /orders after the line is fully recorded",
        )
        if drawn is not None:
            checks.equal(
                {order["number"] for order in drawn["resolution"]["orders"]},
                set(),
                "DONE-1 owes nothing (`Ledger.unfulfilled()` excludes it), so it is not "
                "resolved at all — terminal status is not what kept it out here, having "
                "nothing left to pull is",
            )
            checks.equal(
                next(row["open"] for row in drawn["orders"] if row["number"] == "DONE-1"),
                False,
                "and `open` still reads false, unchanged by any of this",
            )

    # ------------------------------------------- 8-21. the pull, in both directions
    with isolated_home():
        stock(3, 5, "9191486", prefix="p")
        with Store().write() as snapshot:
            snapshot.inventory.listing("9191486").set(master.LIVE, 3)
            # D24's pooled copy: a count, never a place. It holds the ordered SKU and must
            # still never be walked to.
            snapshot.inventory.cards["3/5"].game = "pokemon_code"
            # A record predating the capture server. Every record this server writes has a
            # capture id; this is the one that cannot be made idempotent.
            snapshot.inventory.cards["3/4"].capture_id = None

        answers(
            checks,
            lambda: capture_server.do_order_ingest(
                paste("A-1", line("9191486", 3, name="Moonfall", unit_price="11.88"))
            ),
            "an order for three copies of a SKU the box holds is ingested",
        )
        key = order_store.order_key("TCGplayer", "A-1")

        before_screen = answers(checks, orders_with_picks,
                                "GET /orders resolves it against a box holding a pooled copy")
        if before_screen is not None:
            row = before_screen["resolution"]["orders"][0]["lines"][0]
            checks.equal(
                (row["pooled"], sorted((pick["index"] for pick in row["picks"]))),
                (1, [1, 2, 3, 4]),
                "A POOLED-GAME COPY COUNTS AND IS NEVER PICKED (D24). It carries the "
                "ordered SKU and is not terminal, so it is in the SKU's history and reaches "
                "`pooled`; it is not at a place, so the resolver will not send anybody to "
                "walk to it. The breakdown is what makes `no_copies_on_hand` readable — "
                "sold, retired and pooled are three different remedies. AND EVERY LOCATED "
                "COPY IS OFFERED, NOT ONLY THE THREE WANTED (2026-09-16, the owner: 'widen "
                "the walk itself too') — index 4 carries no `capture_id` and is still a "
                "candidate the operator may choose, because `picks` is a ranked list to "
                "choose from and never an allocation capped at the buyer's quantity",
            )

        pulled = answers(
            checks,
            lambda: capture_server.do_order_pull(
                {
                    "source": "TCGplayer", "number": "A-1", "sku": "9191486",
                    "targets": [target(3, 1, "p1")],
                    # `docs/specs/order-walk-plan.md` §8's ruling of 2026-09-19: the cards
                    # the caller is STILL DRAWING and is not pulling. 3/2 and 3/3 stay in
                    # the drawer and are renumbered by this write (D58); box 9 is a drawer
                    # this press never opened and must be skipped rather than answered.
                    "refresh": [{"box": 3, "index": 2}, {"box": 3, "index": 3},
                                {"box": 9, "index": 1}],
                }
            ),
            "POST /orders/pull records one copy against the line and sells it",
        )
        if pulled is not None:
            checks.equal(
                (pulled["newly"], pulled["recorded"], pulled["outstanding"], pulled["undone"]),
                (1, 1, 2, False),
                "one newly recorded, one recorded in total, two still outstanding on a line "
                "of three — the counts come off the LEDGER rather than off the request",
            )
            checks.equal(
                sorted(pulled["sales"][0]),
                ["box", "card", "index", "listing", "position", "previous_state",
                 "restores_to", "state", "undone"],
                "AND `_sell`'S EXTRACTION LEFT `do_mark_sold`'S CONTRACT INTACT. The pull "
                "answers exactly the nine keys the mark-sold route answers — the same body, "
                "produced by the same function — so `app/src/Fulfillment.tsx` reads one "
                "shape whichever door the sale came through. Asserted as the WHOLE key set: "
                "a tenth key added on one path and not the other is the drift this catches",
            )
            snapshot = Store().read()
            checks.equal(
                snapshot.inventory.cards["3/1"].state,
                master.SOLD,
                "the card is sold — the ledger row and the card's state move in one "
                "`Store.write()`, so neither can land without the other",
            )
            recorded = snapshot.ledger.recorded(key, "9191486")
            checks.equal(
                (recorded.copies, recorded.fulfilled),
                (["p1"], 1),
                "and the ledger keyed the copy by `capture_id` — the one identity a "
                "renumber cannot move (D36)",
            )
            pulled_record = snapshot.inventory.listings["9191486"]
            checks.equal(
                pulled_record.live_estimate,
                2,
                "the SKU's count fell by one, because a listing record existed. A Fulfiller "
                "pulling copies would otherwise leave TCGplayer's cap arithmetic refilling "
                "against cards that are in the post",
            )
            checks.equal(
                (pulled_record.live, pulled_record.sold_here),
                (3, 1),
                "and the ORDER PULL counts its sale exactly as the single mark-sold does "
                "(D115) — both go through `_sell`, so there is one rule for what a sale does "
                "to a listing and neither door edits the export's reading",
            )
            checks.equal(
                pulled["places"][0]["label"],
                join.place_label(
                    join.box_title(Store().read().inventory.box(3).name, 3), 1, 1
                ),
                "THE RECEIPT IS COMPOSED BEFORE THE WRITE — where the operator just was",
            )
            checks.equal(
                capture_server._Places(Store().read().inventory).of(3, 1)["label"],
                join.departed_label(
                    join.box_title(Store().read().inventory.box(3).name, 3), 1, 1
                ),
                "AND A `_Places` BUILT AFTER THE CALL NAMES THE SAME PLACE THROUGH THE DEPARTED "
                "COMPOSER (D259): the place the card left. Its `slot` "
                "is null, which is what a screen draws the departure from, and the response "
                "still carries the receipt composed before the write",
            )
            # ---------------------------------------------------- `refreshed`, the other way in time
            #
            # THE SAME RESPONSE CARRIES BOTH DIRECTIONS AND THEY MUST NOT BE FOLDED TOGETHER.
            # `places` above is the RECEIPT and is pre-write on purpose. `refreshed` is the
            # answer to the request's own `refresh` list — cards the caller is still DRAWING
            # and did not touch — and is post-write on purpose, because the write is what made
            # their description wrong. `docs/specs/order-walk-plan.md` §8, ruled 2026-09-19.
            #
            # The case is the walk's own: the solver packs a pass into the fewest drawers, so
            # the next card in the list is LIKELY to be the next card in the drawer, and D58
            # renumbers it the moment the one in front of it leaves.
            checks.equal(
                [(row["box"], row["index"]) for row in pulled["refreshed"]],
                [(3, 2), (3, 3)],
                "SCOPED TO THE DRAWER THIS PRESS OPENED. Box 9 was asked for and is not "
                "answered — nothing moved in it, so re-describing it would be a re-read "
                "dressed as a consequence. The order is the caller's own, unsorted",
            )
            checks.equal(
                [row["slot"] for row in pulled["refreshed"]],
                [1, 2],
                "AND THE NUMBERS ARE THE POST-WRITE ONES. Card 2 of the drawer became card "
                "1 and card 3 became card 2, because the copy in front of them left (D58). "
                "Pre-write they read 2 and 3, which is what a `refreshed` computed beside "
                "the receipt would have answered — the exact defect this field exists to "
                "remove, and the reason phase three builds its own `_Places`",
            )
            checks.equal(
                pulled["places"][0]["slot"],
                1,
                "and the RECEIPT in the same body still reads the pre-write slot, so one "
                "response carries both times without either overwriting the other",
            )
            refused_refresh = _refusal_text(
                lambda: capture_server.do_order_pull(
                    {
                        "source": "TCGplayer", "number": "A-1", "sku": "9191486",
                        "targets": [target(3, 2, "p2")],
                        "refresh": [{"box": 3, "index": 3, "capture_id": "p3"}],
                    }
                )
            )
            checks.ok(
                "capture_id" in " ".join(refused_refresh or ()),
                "A REFRESH IS NOT A TARGET, AND THE FIELD LIST SAYS SO. Nothing is aimed at "
                "and nothing is written, so an aim check on a card nobody is touching would "
                "only refuse a re-description over a re-shoot. `_reject_unknown` names the "
                "field rather than ignoring it, and the whole pull refuses — so this press "
                f"wrote nothing either. Said: {refused_refresh!r}",
            )
            checks.equal(
                Store().read().ledger.recorded(key, "9191486").fulfilled,
                1,
                "and the refusal above cost the line nothing, which is the half of "
                "`_reject_unknown`-before-anything that matters",
            )

        after_screen = answers(
            checks, orders_with_picks, "GET /orders after the pull answers"
        )
        if after_screen is not None:
            row = after_screen["resolution"]["orders"][0]["lines"][0]
            checks.equal(
                (
                    row["wanted"], row["owed"], row["fulfilled"], row["outstanding"],
                    row["reason"], sorted(pick["index"] for pick in row["picks"]),
                ),
                (3, 2, 3, 0, "resolved", [2, 3, 4]),
                "THE RESOLVER IS ASKED FOR WHAT IS STILL OWED. One of three is recorded, so "
                "the line wants two more; it is `resolved` because three are ON HAND, which "
                "is at least the two owed — not `short` with a pick withheld from the "
                "buyer. `wanted` stays the order's quantity and `owed` is the ledger's; the "
                "resolver is handed `owed` rather than the raw quantity. `fulfilled` and "
                "`picks` are EVERY remaining candidate (2, 3 and 4), never capped at 2 — "
                "picks is a list to choose from, not an allocation (2026-09-16)",
            )
            checks.equal(
                after_screen["orders"][0]["progress"][0]["copies"],
                ["p1"],
                "AND THE LEDGER NAMES THE CARD IT PULLED, BY CAPTURE ID — the one identity "
                "a renumber cannot move",
            )
            checks.ok(
                "pulled" not in after_screen["orders"][0]["progress"][0],
                "AND NO POSITION RIDES BESIDE IT (docs/specs/undo.md §5, D212) — a recorded "
                "copy has already left the box, so `GET /orders` states the card and the "
                "count and never the slot it came out of; nothing under `app/` ever read "
                "the position this used to join",
            )

        refusal(
            checks,
            lambda: capture_server.do_order_pull(
                {
                    "source": "TCGplayer", "number": "A-1", "sku": "9191486",
                    "targets": [target(3, 1, "p1")],
                }
            ),
            "already_sold",
            "pulling the same copy again refuses — the ledger dedups the capture id, and "
            "`_sell` will not record a second sale of one physical card",
        )
        checks.equal(
            Store().read().ledger.recorded(key, "9191486").fulfilled,
            1,
            "and the ledger still reads one, so the refusal cost the line nothing",
        )

        # THE PLACE THIS REFUSAL NAMES, computed the same way `capture_id_mismatch`'s own
        # message computes it — before the call, since the target is not sold by a refusal.
        where_3_2 = join.said_place(Store().read().inventory, 3, 2)
        refused_aim = _refusal_text(
            lambda: capture_server.do_order_pull(
                {
                    "source": "TCGplayer", "number": "A-1", "sku": "9191486",
                    "targets": [target(3, 2, "not-the-card-on-screen")],
                }
            )
        )
        checks.ok(
            refused_aim is not None
            and refused_aim[0] == "pull_entry_refused"
            and "not the card the screen showed" in refused_aim[1],
            "a target whose `capture_id` is not the card at that position is refused as "
            "`capture_id_mismatch`, reported through the whole-pull `pull_entry_refused`. A "
            "mid-box delete, a capture undo releasing an index or a re-shoot all change a "
            "slot's occupant, so a screen drawn a minute ago may aim at a different card",
            f"got {refused_aim!r}",
        )
        checks.ok(
            refused_aim is not None
            and f"The card at {where_3_2} is not the card the screen showed" in refused_aim[1]
            and "3/2" not in refused_aim[1]
            and "box 3" not in refused_aim[1].lower(),
            "and the message NAMES THE PLACE, not the store position — the section and "
            "card within it, never `3/2` or the box number (D259)",
            f"where: {where_3_2!r}; got: {refused_aim!r}",
        )
        checks.equal(
            (Store().read().inventory.cards["3/2"].state,
             Store().read().ledger.recorded(key, "9191486").fulfilled),
            ("identified", 1),
            "AND NOTHING WAS WRITTEN: the card is still identified and the fulfilment map "
            "is unmoved. Phase one validates every target and writes nothing, so a pull is "
            "never half-applied — a half-applied pull is an operator holding cards with no "
            "record of which ones went",
        )

        refusal(
            checks,
            lambda: capture_server.do_order_pull(
                {
                    "source": "TCGplayer", "number": "A-1", "sku": "9191486",
                    "targets": [target(3, 2, "p2"), target(3, 2, "p2")],
                }
            ),
            "pull_entry_refused",
            "the SAME POSITION TWICE in one call is refused as `duplicate_target` inside the "
            "whole-pull refusal, and the reason is not tidiness: `_sale_origin` reads "
            "`history.jsonl` FROM DISK and cannot see an event this session has queued, so "
            "the second sale of a repeated position would compute `previous` from "
            "pre-session history and name the state the card held before the FIRST one",
        )

        refusal(
            checks,
            lambda: capture_server.do_order_pull(
                {
                    "source": "TCGplayer", "number": "A-1", "sku": "9191486",
                    "targets": [target(3, 4, "p4")],
                }
            ),
            "pull_entry_refused",
            "a card carrying no `capture_id` refuses as `copy_not_identifiable` rather than "
            "being counted blind — the pull cannot be made idempotent without one",
        )
        refusal(
            checks,
            lambda: capture_server.do_order_pull(
                {
                    "source": "TCGplayer", "number": "A-1", "sku": "555999",
                    "targets": [target(3, 2, "p2")],
                }
            ),
            "pull_entry_refused",
            "and a pull whose SKU is not the SKU the card carries refuses as `sku_mismatch` "
            "— a copy fills a line by CARRYING its SKU, and nothing here recategorises a "
            "card to make it fit",
        )
        refusal(
            checks,
            lambda: capture_server.do_order_pull(
                {
                    "source": "TCGplayer", "number": "NOT-INGESTED", "sku": "9191486",
                    "targets": [target(3, 2, "p2")],
                }
            ),
            "order_not_ingested",
            "an order this ledger has never seen refuses rather than being invented — "
            "inventing it would put a shipment on record for a purchase nobody can produce",
        )
        with Store().write() as snapshot:
            snapshot.inventory.cards["3/2"].sku = "555999"
        refusal(
            checks,
            lambda: capture_server.do_order_pull(
                {
                    "source": "TCGplayer", "number": "A-1", "sku": "555999",
                    "targets": [target(3, 2, "p2")],
                }
            ),
            "sku_not_on_order",
            "and a SKU the card genuinely carries but the ORDER has no line for refuses at "
            "the ledger — the buyer did not order it, and fulfilment is keyed by SKU",
        )
        with Store().write() as snapshot:
            snapshot.inventory.cards["3/2"].sku = "9191486"
        checks.equal(
            (Store().read().ledger.recorded(key, "9191486").fulfilled,
             Store().read().inventory.cards["3/2"].state),
            (1, "identified"),
            "NONE of those four refusals moved a count or a card's state",
        )

        answers(
            checks,
            lambda: capture_server.do_order_pull(
                {
                    "source": "TCGplayer", "number": "A-1", "sku": "9191486",
                    "targets": [target(3, 2, "p2"), target(3, 3, "p3")],
                }
            ),
            "the line's other two copies are pulled in one press",
        )
        capture_server.do_capture(
            {"box": 3, "capture_id": "p6",
             "image": base64.b64encode(b"\xff\xd8\xff" + b"\x06" * 64).decode("ascii")}
        )
        with Store().write() as snapshot:
            snapshot.inventory.record_identification(
                "3/6", name="Moonfall", number="198/219", printed_total="219",
                confidence="high",
            )
            snapshot.inventory.cards["3/6"].sku = "9191486"
        refusal(
            checks,
            lambda: capture_server.do_order_pull(
                {
                    "source": "TCGplayer", "number": "A-1", "sku": "9191486",
                    "targets": [target(3, 6, "p6")],
                }
            ),
            "over_fulfilled",
            "A FOURTH COPY AGAINST A LINE OF THREE REFUSES AND IS NOT CLAMPED. Swallowing "
            "it would gain nothing — you cannot ship the fourth — and would leave a count "
            "nobody can explain",
        )
        checks.equal(
            Store().read().ledger.recorded(key, "9191486").fulfilled,
            3,
            "and the ledger still reads three",
        )

        answers(
            checks,
            lambda: capture_server.do_order_ingest(
                paste("B-2", line("9191486", 1),
                      placed_at="2026-08-28T10:00:00.000+00:00")
            ),
            "a second order for the same SKU is ingested",
        )
        held_text = _refusal_text(
            lambda: capture_server.do_order_pull(
                {
                    "source": "TCGplayer", "number": "B-2", "sku": "9191486",
                    "targets": [target(3, 1, "p1")],
                }
            )
        )
        checks.ok(
            held_text is not None
            and held_text[0] == "copy_already_pulled"
            and "tcgplayer:a-1" in held_text[1],
            "a copy already recorded against ANOTHER line refuses, and the message NAMES "
            "THE HOLDING ORDER — this is the failure `store/orders.py` exists for, and a "
            "refusal that will not say who holds the card cannot be acted on",
            f"got {held_text!r}",
        )

        answers(
            checks,
            lambda: capture_server.do_order_pull(
                {
                    "source": "TCGplayer", "number": "B-2", "sku": "9191486",
                    "targets": [target(3, 6, "p6")],
                }
            ),
            "the second order takes the sixth copy",
        )
        refusal(
            checks,
            lambda: capture_server.do_order_pull(
                {"undo": True, "targets": [target(3, 1, "p1"), target(3, 6, "p6")]}
            ),
            "pull_spans_lines",
            "an undo whose copies are held by two different lines refuses — one press "
            "pulled one line and one press reverses one",
        )

        # THE AGGREGATE. Two good targets and one stale one, so the case can distinguish
        # 'the whole pull refused' from 'every target was bad anyway'.
        before_agg = Store().read().inventory
        where_3_3 = join.said_place(before_agg, 3, 3)
        where_3_4 = join.said_place(before_agg, 3, 4)
        aggregate = _refusal_text(
            lambda: capture_server.do_order_pull(
                {
                    "source": "TCGplayer", "number": "B-2", "sku": "9191486",
                    "targets": [target(3, 2, "p2"), target(3, 3, "stale-id"),
                                target(3, 4, "p4")],
                }
            )
        )
        checks.ok(
            aggregate is not None
            and aggregate[0] == "pull_entry_refused"
            and f"{where_3_3}: The card at" in aggregate[1]
            and f"{where_3_4}: The card at" in aggregate[1]
            and "3/3:" not in aggregate[1] and "3/4:" not in aggregate[1],
            "THREE TARGETS, TWO REFUSALS, AND EACH IS NAMED BY ITS PLACE, WITH ITS OWN "
            "CODE — never the store position `3/3` or `3/4` (D259). "
            "A per-position refusal is collected rather than raised and the whole set is "
            "answered at once — `group_entry_refused`'s shape — because a pull half-refused "
            "is an operator holding cards with no record of which ones went",
            f"got {aggregate!r}",
        )
        checks.equal(
            [Store().read().inventory.cards[f"3/{at}"].state for at in (2, 3, 4)],
            ["sold", "sold", "identified"],
            "AND NOT ONE OF THE THREE MOVED STATE — the two already-sold copies are still "
            "sold and the untouched one is still identified. Validate everything, then "
            "write everything",
        )

        undone = answers(
            checks,
            lambda: capture_server.do_order_pull(
                {"undo": True, "targets": [target(3, 1, "p1")]}
            ),
            "THE UNDO NAMES NO ORDER AND NO SKU AND STILL FINDS THE LINE",
        )
        if undone is not None:
            checks.equal(
                (undone["undone"], undone["order_key"], undone["sku"]),
                (True, key, "9191486"),
                "and it answers with the order and the SKU it found. The client cannot name "
                "the line and must not: the server asks `Ledger.holder_of` which line holds "
                "this copy, so a screen holding a stale order key cannot reverse the wrong "
                "one",
            )
            checks.equal(
                Store().read().inventory.cards["3/1"].state,
                "identified",
                "the card is restored to the state HISTORY recorded, not to a guess — an "
                "unreadable history refuses `sold_origin_unknown` rather than inventing one",
            )
            restored = Store().read().ledger.recorded(key, "9191486")
            checks.equal(
                (restored.fulfilled, restored.copies),
                (2, ["p2", "p3"]),
                "and the ledger gave the copy back: the count fell and the capture id left "
                "the list, so the line can be filled again by any copy that carries the SKU",
            )
        refusal(
            checks,
            lambda: capture_server.do_order_pull(
                {
                    "undo": True, "source": "TCGplayer", "number": "A-1",
                    "sku": "9191486", "targets": [target(3, 2, "p2")],
                }
            ),
            "field_not_settable",
            "AN UNDO THAT ALSO NAMES AN ORDER REFUSES rather than being obeyed with the "
            "order ignored. The two directions take different tuples — `undo` is read FIRST "
            "and the narrow one is checked against it — because a body carrying both is a "
            "client that has confused the directions, and obeying it would reverse a pull "
            "the caller believed it was recording",
        )
        refusal(
            checks,
            lambda: capture_server.do_order_pull(
                {"undo": True, "targets": [target(3, 1, "p1")]}
            ),
            "pull_not_recorded",
            "and an undo of a copy no pull recorded refuses — this route did not do what is "
            "being undone, and a sale marked on #/inventory is reversed there",
        )
        checks.equal(
            Store().read().inventory.cards["3/1"].state,
            "identified",
            "AND THE CARD IS NOT UN-SOLD BY IT: a refusal in phase two discards every state "
            "change queued behind it, because `Store.write()` commits only on a clean exit",
        )


def check_order_walk_plan_route(checks: Checks) -> None:
    """`POST /orders/walk-plan` composes a REAL position for every copy it offers, and —
    RULED 2026-09-19 (`docs/specs/order-walk-plan.md` §8) — carries EVERY on-hand copy of the take's SKU,
    store-wide, not only the copies standing at the stop the solver chose.

    `pipeline/walkplan.py` is proved by T11 and renders no labels on purpose. This is the
    route above it. Two defects, one per ruling:

      2026-09-18   it shipped using `_Places.for_keys`, so every copy answered
                   `neighbors: null` and — because `WalkPlanCopy` carried no box total at
                   all — `app/src/OrdersWalk.tsx` drew `PositionBar`'s honest "a box the
                   server could not size" blank track on every row, for ever (§9a finding 4).
                   Fixed 2026-09-19 by dropping `for_keys` for the ordinary, lazy `_Places`.
      2026-09-19   the stop rebuild found the SAME shape still wrong in its UNIT: a
                   `WalkPlanCopy` carried only the copies the solver picked for this one
                   stop, so a card the store held three of could draw two, with no way to
                   see where the third was. D212 (every copy is fungible, no order claims
                   one) and D93 (the copies panel draws every copy and hides none) both
                   already ruled this for the resolver and for `/search`; this is that same
                   rule reaching the walk's own row. `WalkPlanCopy` is now `_copy_row`'s own
                   dict (`key`, `state`, `has_photo`, `capture_id`, `cid`, `place`) plus
                   `here` — the flat fields (`box`, `index`, `slot`, `card`, `label`,
                   `neighbors`, `box_total`, `box_closed`, `fraction`) are GONE, folded into
                   `place`, exactly as `SearchCopy.place` already carries them.

    THE SCOPING WAS BORROWED FROM A DIFFERENT CALLER AND THE PREMISE DID NOT REACH HERE.
    `for_keys` exists for `do_orders` — "the route the Orders and Shipping screens poll" —
    whose picks span most of the store's boxes. The walk fires ONCE per pass (§8: computed
    once, no `Re-plan` control) over the few drawers the solver picked, and the ordinary
    `_Places` is already scoped by being lazy per box. Measured 2026-09-19 at the owner's own
    scale (2,560 cards, 8 drawers, 275 walkable orders): 4.5 ms -> 18.5 ms for 40 open
    orders, 24.1 ms -> 32.2 ms for all 275. The delta is the per-box walk of the drawers the
    plan reaches, paid once per press. MEASURED AGAIN the day the copies list widened,
    end to end this time (`do_order_walk_plan` itself): 6.8 ms -> 9.0 ms for 40 open orders,
    19.6 ms -> 34.9 ms for 275, over a second synthetic store of the same scale — see
    `do_order_walk_plan`'s own docstring for the fixture and the caveat about its shape.

    WHY THIS IS A ROUTE TEST AND NOT A SCREEN TEST. `app/tests/orders.spec.ts` stubs the
    wire, so it proves the screen draws what it is handed and can prove nothing about what
    the server hands it. A null `neighbors` here reads as a legal degraded state all the way
    up, which is exactly how it survived a review.
    """
    checks.note("")
    checks.note("WALK PLAN ROUTE — POST /orders/walk-plan (order-walk-plan.md §7-8)")

    with isolated_home():
        for at in range(1, 13):
            capture_server.do_capture(capture_payload(3, capture_id=f"w{at}", set_hint="sv9"))
        # A THIRD COPY OF THE ORDERED SKU, IN A DRAWER THE SOLVER NEVER VISITS — demand is
        # one and box 3 alone holds two, so nothing sends the walk to box 7. Store-wide
        # widening (D212, D93) is the only reason this copy appears on the wire at all.
        for at in range(1, 4):
            capture_server.do_capture(capture_payload(7, capture_id=f"o{at}", set_hint="sv9"))
        with Store().write() as snapshot:
            for at in range(1, 13):
                # EVERY CARD NAMED, because D260 walks PAST a card nobody has named: a box
                # straight off the feeder draws no ladder at all, and a fixture like that
                # would make a null `neighbors` look correct.
                snapshot.inventory.record_identification(
                    f"3/{at}", name=f"Landmark {at}", number=f"{at:03d}/219",
                    printed_total="219", confidence="high",
                )
                snapshot.inventory.cards[f"3/{at}"].sku = "9191486" if at in (4, 5) else f"91914{at:02d}"
            for at in range(1, 4):
                snapshot.inventory.record_identification(
                    f"7/{at}", name=f"Other {at}", number=f"{at:03d}/219",
                    printed_total="219", confidence="high",
                )
                snapshot.inventory.cards[f"7/{at}"].sku = "9191486" if at == 2 else f"91915{at:02d}"
            # `set`/`rarity` AGREE ACROSS ALL THREE COPIES OF THE ORDERED SKU, so the take
            # header's `_agreed` fold has something real to agree on — D213's pair, composed
            # for the take exactly as `do_search` composes them for a `SearchGroup`.
            for key in ("3/4", "3/5", "7/2"):
                snapshot.inventory.cards[key].set_name = "Twilight Masquerade"
                snapshot.inventory.cards[key].rarity = "Rare"

        answers(
            checks,
            lambda: capture_server.do_order_ingest(
                {"orders": [{
                    "source": "TCGplayer", "number": "W-1",
                    "placed_at": "2026-09-18T10:00:00.000+00:00",
                    "lines": [{"sku": "9191486", "quantity": 1, "name": "Landmark 4"}],
                }]}
            ),
            "an order for a card sitting mid-box ingests",
        )

        search_before = answers(
            checks,
            lambda: capture_server.do_search("9191486"),
            "GET /search over the same SKU, to check the walk's `place` against the truth",
        )
        search_places = {}
        if search_before is not None:
            for group in search_before["groups"]:
                if group["sku"] == "9191486":
                    search_places = {copy["key"]: copy["place"] for copy in group["copies"]}

        plan = answers(
            checks,
            lambda: capture_server.do_order_walk_plan({"keys": ["tcgplayer:w-1"]}),
            "POST /orders/walk-plan answers a plan over that order",
        )
        if plan is not None:
            stops = [stop for stop in plan["stops"] if not stop["pooled"]]
            checks.equal(len(stops), 1, "one drawer to open — box 7's copy never earns a stop")
            stop = stops[0]
            checks.equal(
                stop["box_total"],
                12,
                "THE STOP CARRIES THE BOX'S OWN TOTAL BESIDE THE SPAN (§8's 2026-09-19 "
                "ruling: 'both are real now that `box_total` is on the wire') — the span "
                "bar's own denominator, read off the same `.of()` call the span itself "
                "comes from, not a copy's place reached into from one level up",
            )
            checks.equal(len(stop["takes"]), 1, "one SKU wanted at this stop")
            take = stop["takes"][0]
            copies = take["copies"]

            checks.equal(
                [copy["key"] for copy in copies],
                ["3/4", "3/5", "7/2"],
                "EVERY ON-HAND COPY OF THE SKU, STORE-WIDE (D212, D93; RULED 2026-09-19) — "
                "not only the two the solver chose at this stop. ORDER IS LOAD-BEARING: the "
                "stop's own copies first, densest-first as the solver ranked them, then the "
                "rest ascending (box, index) — box 7's copy last because nothing outranks "
                "'this drawer' but the drawer itself",
            )
            checks.equal(
                [copy["here"] for copy in copies],
                [True, True, False],
                "`here` IS TRUE FOR EXACTLY THE STOP'S OWN COPIES and false for a copy this "
                "stop merely offers — a fungible pick in another drawer, D212's own words",
            )
            checks.equal(
                [set(copy) for copy in copies],
                [{"key", "state", "state_at", "has_photo", "capture_id", "cid", "place", "here"}] * 3,
                "AND THE OLD FLAT FIELDS ARE GONE. `_copy_row`'s own dict plus `here` — no "
                "`box`, `index`, `slot`, `card`, `label`, `neighbors`, `box_total`, "
                "`box_closed` or `fraction` riding beside `place` a second time. A client "
                "reading `copy.box_total` now reads `undefined`, not a stale zero",
            )
            checks.equal(
                [copy["place"]["box_total"] for copy in copies],
                [12, 12, 3],
                "and each copy's OWN place carries ITS OWN box's total — box 3's twelve, "
                "box 7's three — which a stop-level `box_total` alone could not say for the "
                "widened copy sitting in a different drawer",
            )
            if search_places:
                checks.equal(
                    [copies[0]["place"], copies[1]["place"], copies[2]["place"]],
                    [search_places.get("3/4"), search_places.get("3/5"), search_places.get("7/2")],
                    "EACH COPY'S `place` EQUALS WHAT `/search` SENDS FOR THE SAME KEY — one "
                    "composer (`_copy_row` -> `_Places.of`), not two describing one physical "
                    "card differently depending on which route asked",
                )
            named = [
                ((copy["place"]["neighbors"] or {}).get("prev") or {}) for copy in copies[:2]
            ]
            checks.equal(
                [side.get("name") for side in named],
                ["Landmark 3", "Landmark 4"],
                "AND D58's LADDER IS REAL, WHICH IS THE WHOLE OF THIS BLOCK. `for_keys` "
                "answered null here for every copy on every walk — a legal degraded state "
                "that reads as correct all the way to the screen. D260 is what it buys: a "
                "card nobody has named is not a landmark, and the ladder is what makes "
                "`Card 4` countable by hand once the section has holes",
            )
            checks.equal(
                [copy["place"]["slot"] for copy in copies],
                [4, 5, 2],
                "and the slot is D58's count, composed by the one renderer rather than "
                "read off the store index beside it",
            )
            checks.equal(
                (take["set"], take["rarity"]),
                ("Twilight Masquerade", "Rare"),
                "THE TAKE CARRIES `set`/`rarity` EXACTLY AS `do_search` COMPOSES THEM FOR A "
                "`SearchGroup` — `_agreed` over the SKU's whole position history, all three "
                "copies agreeing",
            )
            checks.ok(
                "condition" in take,
                "and `condition` rides beside them even where nothing agrees (null here — "
                "no listing recorded and no card carries one)",
            )
            checks.equal(
                (take.get("listed"), take.get("sold_here"), take.get("live_as_of")),
                ({stage: 0 for stage in master.LISTING_STAGES}, 0, None),
                "AND `listed`/`sold_here`/`live_as_of` RIDE BESIDE THEM TOO — "
                "`_listing_reading`, the one composer `_walk_plan_take` and `do_search`'s "
                "`_group_row` both call now, off no listing record for this SKU: zero every "
                "stage, zero sold here, null read time — the same shape a SKU with no "
                "listing gets from `/search` (D115), never a fabricated absence",
            )


def check_order_places_scoped(checks: Checks) -> None:
    """Store-scaling item 6: `do_orders` scopes its `_Places` build to the boxes its picks
    actually touch, never to the whole store.

    `_Places.of()` has always been lazy PER BOX (D88) — the ordinary constructor does no
    eager scan — but the cost that survived that fix is what "per box" means once it runs:
    `_walk` hydrates a full `Card` for every record in a touched box (`records_in`), to
    answer `slot`/`label`/`section`/`fraction`, fields two indexed integer columns already
    answer, because the SAME walk also builds D58's neighbor/gap decoration, which
    genuinely needs every card's name. An order's picks routinely span most of the store's
    boxes, so five boxes cost a fifth of a full read, five times — measured 185 ms ->
    3,465 ms at 20x the store.

    `Orders.tsx`/`OrdersShipStage.tsx` read neither `neighbors` nor `section_gaps`, so
    `_Places.for_keys` answers everything else — `Inventory.occupied_indices`, two columns
    per box — and those two fields null, the SAME null the ordinary constructor already
    answers when `_walk` degrades. This is an existing, typed, degraded state and not a
    new one.

    THE RISK IS SILENT DEFEAT: a bug that calls `_walk` anyway (forgetting `_sparse` in
    `_company`, or a future `.of()` refactor that opens a second path into `_walk`/
    `_boxmates`) produces an IDENTICAL response at the OLD cost. A response that "looks
    right" cannot catch that — only a loaded-object count can, which is Assertion 1.

    A MIXED BOX IS ALREADY IN THIS FILE'S OWN FIXTURES AND IS NOT INVENTED HERE:
    `check_order_screen`'s pull block sets `cards["3/5"].game = "pokemon_code"` beside four
    ordinary cards and its assertions on `pooled`/`picks` already exercise the ordinary
    `_Places` over that box — `check_order_places_scoped` exercises the SAME shape through
    `for_keys`, because `Inventory.occupied_indices` cannot itself decide D24's `located`
    flag (`store/` imports nothing from `pipeline/`, D63) and the filter that decides it
    lives in `_Places.for_keys`/`_location_of` instead. A parity break there would silently
    put a pooled card back into D58's counting space for every OTHER card in a mixed box.
    """
    checks.note("")
    checks.note("PLACES SCOPED TO PICKS — do_orders")

    with isolated_home():
        # Five 20-card boxes, mirroring §0's own shape ("five boxes, an order's picks span
        # most of them") — one SKU resolved only in box 3, a divider opened after it so
        # `section`/`section_start`/`section_end` are exercised for real rather than off
        # the `(1,)` fallback, and a pooled code card sitting beside the picked cards so
        # the occupied-space filter is exercised on the box the picks actually land in.
        for box in (1, 2, 3, 4, 5):
            for at in range(1, 21):
                capture_server.do_capture(
                    capture_payload(box, capture_id=f"b{box}c{at}", set_hint="sv9")
                )
        with Store().write() as snapshot:
            for at in range(1, 4):
                snapshot.inventory.record_identification(
                    f"3/{at}", name="Moonfall", number="198/219",
                    printed_total="219", confidence="high",
                )
                snapshot.inventory.cards[f"3/{at}"].sku = "9191486"
            # D24's pooled copy, mixed into the same box as the picks. It must consume no
            # slot in box 3's counting space, exactly as it must not in the ordinary
            # `_Places` path `check_order_screen` already covers.
            snapshot.inventory.cards["3/20"].game = "pokemon_code"
        capture_server.do_open_section(3, {})

        answers(
            checks,
            lambda: capture_server.do_order_ingest(
                {"orders": [{
                    "source": "TCGplayer", "number": "A-1",
                    "placed_at": "2026-08-27T10:00:00.000+00:00",
                    "lines": [{"sku": "9191486", "quantity": 3, "name": "Moonfall"}],
                }]}
            ),
            "an order for the box-3 SKU ingests",
        )

        # ---------------------------------------- Assertion 1 — the sparse build's own cost
        #
        # `do_orders` opens its OWN `Store().read()` internally, so `loaded_count` has to be
        # read from INSIDE that call's snapshot and not from a separate read — the existing
        # idiom (`check_inventory_box_route`) is to call the pieces `do_orders` calls,
        # directly, against one fresh session, rather than monkeypatching `Store.read`.
        snapshot = Store().read()
        ledger = snapshot.ledger
        sequence = sorted(
            ledger.orders.values(),
            key=lambda record: (
                record.placed_at is None, record.placed_at or "", record.key
            ),
        )
        open_keys = {record.key for record in ledger.unfulfilled()}
        open_records = [record for record in sequence if record.key in open_keys]
        asked = [capture_server._engine_order(record, ledger) for record in open_records]
        resolution = orders.resolve_all(snapshot.inventory, asked)
        before_loaded = snapshot.inventory.cards.loaded_count

        keys = {
            (pick.box, pick.index)
            for answer in resolution.orders
            for line in answer.lines
            for pick in line.picks
        }
        checks.ok(bool(keys), "the fixture resolved at least one pick to scope against")

        places = capture_server._Places.for_keys(snapshot.inventory, keys)
        # Force one `.of()` per pick, exactly as `_pick_row` does inside `do_orders`.
        for answer in resolution.orders:
            for line in answer.lines:
                for pick in line.picks:
                    places.of(pick.box, pick.index)

        after_loaded = snapshot.inventory.cards.loaded_count
        checks.equal(
            after_loaded - before_loaded,
            0,
            "ZERO card objects to place three picks in a 20-card box. `_Places.of()` is "
            "lazy PER BOX already (D88), so the ordinary constructor would ALSO touch only "
            "this one box — the saving this item makes is not 'the other four boxes', it "
            "is that the touched box's `_walk` (`records_in`) hydrates every one of its "
            "records to answer `slot`, where `occupied_indices` answers the same three "
            "picks' slots from two indexed columns and builds nothing. Measured by hand "
            "against the OLD `_Places(inventory)` over this identical fixture: 17 — the "
            "box's other 17 records, on top of the 3 the resolver's own `where(sku=…)` "
            "already loaded before `_Places` runs at all",
        )
        checks.ok(
            not snapshot.inventory.cards.complete,
            "and the whole-store table was never fully loaded either",
        )

        # ------------------------------ Assertion 2 — parity with the ordinary constructor
        ordinary = capture_server._Places(snapshot.inventory)
        for answer in resolution.orders:
            for line in answer.lines:
                for pick in line.picks:
                    sparse_block = dict(places.of(pick.box, pick.index))
                    ordinary_block = dict(ordinary.of(pick.box, pick.index))
                    for field in ("neighbors", "section_gaps"):
                        checks.equal(
                            sparse_block.pop(field, "missing"), None,
                            f"the sparse build answers `{field}` null for {pick.box}/"
                            f"{pick.index}, the same null the ordinary path answers on a "
                            "degraded walk — an existing typed state, not a new one",
                        )
                        ordinary_block.pop(field, None)
                    checks.equal(
                        sparse_block, ordinary_block,
                        f"the sparse and whole-box builds agree on everything but D58's "
                        f"decoration for {pick.box}/{pick.index} — slot, label, section, "
                        "card, fraction, box_total, box_name and box_closed all included",
                    )

        # AND SLOT EQUALITY AGAINST `do_inventory`'s OWN `_Places`, over the SAME cards — a
        # second, independent path to the same number. `do_inventory` opens its own
        # snapshot, so this is a genuinely different `_Places` instance built the ordinary
        # way, not a re-read of `ordinary` above.
        inventory_rows = capture_server.do_inventory()["cards"]
        for answer in resolution.orders:
            for line in answer.lines:
                for pick in line.picks:
                    key = master.position_key(pick.box, pick.index)
                    checks.equal(
                        places.of(pick.box, pick.index)["slot"],
                        inventory_rows[key]["place"]["slot"],
                        f"the sparse slot for {key} agrees with `GET /inventory`'s own "
                        "`_Places`, a second independent renderer of D58's counting space",
                    )

        # -------------------------------------------------- Assertion 3 — empty resolution
        empty_places = capture_server._Places.for_keys(snapshot.inventory, set())
        checks.equal(
            empty_places._cache, {},
            "`_Places.for_keys` over an empty key set caches no box — an order with no "
            "open lines with picks must build nothing",
        )

        # The existing empty-store case (`check_order_screen`'s first block) already
        # exercises `GET /orders` through this same path with zero orders at all; this is
        # its unit-level companion for the classmethod alone.


def check_order_picks_tier(checks: Checks) -> None:
    """`GET /orders` answers no picks; `POST /orders/picks` answers exactly the ones asked
    for, and the two never disagree about anything else — the split this session made
    2026-09-16 to stop decorating a `place` block for every candidate copy of every
    unfulfilled order on the route `#/orders` and `#/shipping` poll (measured 52% of that
    route's wall time, over 1,777 pick-rows for 819 distinct positions).
    """
    checks.note("")
    checks.note("ORDER PICKS TIER — GET /orders vs POST /orders/picks")

    def line(sku, quantity=1, **extra) -> dict:
        row = {"sku": sku, "quantity": quantity}
        row.update(extra)
        return row

    def paste(number, *lines, **extra) -> dict:
        order = {
            "source": "TCGplayer",
            "number": number,
            "placed_at": extra.pop("placed_at", "2026-08-27T10:00:00.000+00:00"),
            "lines": list(lines),
        }
        order.update(extra)
        return {"orders": [order]}

    with isolated_home():
        for at in range(1, 3):
            capture_server.do_capture(capture_payload(3, capture_id=f"tier{at}"))
        with Store().write() as snapshot:
            for at in range(1, 3):
                snapshot.inventory.record_identification(
                    f"3/{at}", name="Moonfall", number="198/219",
                    printed_total="219", confidence="high",
                )
                snapshot.inventory.cards[f"3/{at}"].sku = "9191486"

        answers(
            checks,
            lambda: capture_server.do_order_ingest(paste("T-1", line("9191486", 1))),
            "one order for the SKU ingests",
        )
        key = order_store.order_key("TCGplayer", "T-1")

        lite = answers(checks, capture_server.do_orders, "GET /orders answers")
        if lite is not None:
            lite_line = lite["resolution"]["orders"][0]["lines"][0]
            checks.equal(
                lite_line["picks"], [],
                "NO PICKS AND NO PLACE — every OTHER field is still the real resolution: "
                "reason, on_hand and the rest are computed exactly as before",
            )
            checks.equal(
                (lite_line["reason"], lite_line["on_hand"], lite_line["fulfilled"]),
                ("resolved", 2, 2),
                "the reason and the counts answer without ever building a `_Places` — RED "
                "if the list tier silently stopped resolving lines to save the same time "
                "a different way",
            )

        detailed = answers(
            checks,
            lambda: capture_server.do_order_picks({"keys": [key]}),
            "POST /orders/picks answers the same order, asked for by key",
        )
        if detailed is not None:
            checks.equal(
                len(detailed["orders"]), 1, "exactly the one order asked about, no more"
            )
            full_line = detailed["orders"][0]["lines"][0]
            checks.equal(
                (full_line["reason"], full_line["on_hand"], full_line["fulfilled"]),
                ("resolved", 2, 2),
                "AND THE VERDICT AGREES WITH THE LIST TIER — the split changes WHEN a pick "
                "is decorated, never WHETHER a line resolved",
            )
            checks.equal(
                sorted((pick["box"], pick["index"]) for pick in full_line["picks"]),
                [(3, 1), (3, 2)],
                "and the real picks are exactly the two copies on hand, each carrying a "
                "real `place` block",
            )
            checks.ok(
                all(pick["place"]["located"] for pick in full_line["picks"]),
                "every pick carries a decorated, located place",
            )

        refusal(
            checks,
            lambda: capture_server.do_order_picks({"keys": []}),
            "keys_required",
            "an empty `keys` list refuses rather than answering an empty list — those are "
            "different answers to 'did that work'",
        )
        refusal(
            checks,
            lambda: capture_server.do_order_picks({"keys": [key], "extra": True}),
            "field_not_settable",
            "and an unlisted field refuses by name, the allowlist rule every write on this "
            "screen already follows",
        )

        unknown = answers(
            checks,
            lambda: capture_server.do_order_picks({"keys": ["tcgplayer:never-heard-of-it"]}),
            "a key the ledger does not hold is a normal answer, not a refusal",
        )
        if unknown is not None:
            checks.equal(
                unknown["orders"], [],
                "SKIPPED, NOT REFUSED — a screen's own last `GET /orders` names an order "
                "that closed or was un-fetched between that read and this press, and that "
                "is not a caller error",
            )


def check_inventory_copies_route(checks: Checks) -> None:
    """DEBT27, site 1: `POST /inventory/copies` — every on-hand copy of a SKU
    set, store-wide, in `do_inventory`'s own per-card shape.

    THE WHOLE POINT IS THAT A COPY THE RESOLVER NEVER PICKED STILL COMES BACK. A box-scoped
    implementation — narrowing the initial scan, or the `_Places` build, to the boxes an
    order's own resolved picks happen to name — passes a test that only checks the picked
    copies and silently drops every other one, which is exactly the defect
    `Orders.tsx:indexStore`'s own header describes: a line stops drawing picks once it is
    filled, so a card fourteen copies deep across five boxes shows up as two. This fixture
    puts the SAME SKU in two boxes an order for ONE unit of it would never need to open, and
    asserts both come back.

    Assertions, each pinned to a fixture fact the response could get wrong in its own way:
      1. every on-hand copy of the requested SKU, from EVERY box it sits in, not only the
         box(es) an order's own resolved picks would touch
      2. a SKU never asked about is never in the response, however many copies it has
      3. a GONE copy (sold) of a requested SKU is excluded
      4. the place block on each returned card equals what `_Places` renders for that same
         position independently — the two must agree on `slot`/`label`/`section`/`card`
      5. `listings` carries the shared SKU's own record, narrowed to what the scan matched —
         the market-and-listings parity task (`#/orders` reusing `#/inventory`'s card pane)
      6. and excludes the unrelated SKU's listing, proving the narrowing runs both ways
    """
    checks.note("")
    checks.note("POST /inventory/copies — DEBT27, site 1")

    with isolated_home():
        # Box 1 and box 3 both hold a copy of the SAME SKU — the shape a box-scoped
        # implementation cannot see past. Box 2 holds an unrelated SKU, which must never
        # appear in a response asking only about the shared one. Box 1's second copy is
        # later marked sold, to prove a GONE state is excluded rather than merely unlisted.
        for box, count in ((1, 2), (2, 1), (3, 1)):
            for at in range(1, count + 1):
                capture_server.do_capture(
                    capture_payload(box, capture_id=f"b{box}c{at}", set_hint="sv9")
                )
        with Store().write() as snapshot:
            snapshot.inventory.record_identification(
                "1/1", name="Moonfall", number="198/219",
                printed_total="219", confidence="high",
            )
            snapshot.inventory.cards["1/1"].sku = "9191486"
            snapshot.inventory.record_identification(
                "1/2", name="Moonfall", number="198/219",
                printed_total="219", confidence="high",
            )
            snapshot.inventory.cards["1/2"].sku = "9191486"
            snapshot.inventory.record_identification(
                "3/1", name="Moonfall", number="198/219",
                printed_total="219", confidence="high",
            )
            snapshot.inventory.cards["3/1"].sku = "9191486"
            snapshot.inventory.record_identification(
                "2/1", name="Different Card", number="1/100",
                printed_total="100", confidence="high",
            )
            snapshot.inventory.cards["2/1"].sku = "9191999"
            # BOTH SKUs carry a listing record — the unrelated one's must still be excluded,
            # because it is a record the store holds and not a record this request asked
            # about, which is the one shape a "narrow to `wanted`, never to what matched"
            # mistake and a "return everything the store holds" mistake would both pass.
            snapshot.inventory.listing("9191486").set(master.LIVE, 4)
            snapshot.inventory.listing("9191999").set(master.LIVE, 9)
        # box 1's second copy is now sold — a GONE copy, requested-SKU or not.
        capture_server.do_mark_sold(1, 2, {})

        # ------------------------------------------------------------- Assertion 1 and 2
        answer = answers(
            checks,
            lambda: capture_server.do_inventory_copies({"skus": ["9191486"]}),
            "POST /inventory/copies over the shared SKU answers",
        )
        cards = answer["cards"]
        checks.equal(
            sorted(cards.keys()), ["1/1", "3/1"],
            "both on-hand copies of the SKU come back, from BOTH boxes it sits in — a "
            "box-scoped scan (narrowed to whatever boxes an order's own resolved picks "
            "would touch) would answer only one of these two",
        )
        checks.ok(
            "2/1" not in cards,
            "the OTHER SKU's copy, sitting in its own box, is not in a response that never "
            "asked about it",
        )

        # ------------------------------------------------------------------- Assertion 3
        checks.ok(
            "1/2" not in cards,
            "the SOLD copy of the requested SKU is excluded — GONE is GONE regardless of "
            "which SKU it carries",
        )

        # ------------------------------------------------------------------- Assertion 4
        #
        # GUARDED BY `in cards` RATHER THAN INDEXED BLIND: assertion 1 above already fails
        # by name on a missing key, and a box-scoped mutation that drops one must not also
        # crash this assertion with a bare `KeyError` — a failure this test cannot render is
        # no better than one it never made.
        inventory = Store().read().inventory
        reference = capture_server._Places.for_keys(inventory, {(1, 1), (3, 1)})
        for box, index in ((1, 1), (3, 1)):
            key = master.position_key(box, index)
            if key not in cards:
                checks.ok(False, f"{key} missing from the response — see Assertion 1 above")
                continue
            checks.equal(
                cards[key]["place"], reference.of(box, index),
                f"the place block {key} carries agrees with an independently built "
                "`_Places.for_keys` over the same position",
            )

        # --------------------------------------------------------------- Assertions 5 and 6
        #
        # THE MARKET-AND-LISTINGS PARITY TASK: `#/orders` reuses `#/inventory`'s card pane,
        # and this route is the copies path `Orders.tsx` reads its listings map through — a
        # dictionary lookup over `inventory.listings`, not a second scan, so the `unscoped
        # walk` allow list must not move.
        listings = answer["listings"]
        checks.equal(
            sorted(listings.keys()), ["9191486"],
            "the shared SKU's own listing record is in the map, and the unrelated SKU's is "
            "not — narrowed the same way `do_inventory_box`'s own `listings` is, to the SKUs "
            "the scan actually matched",
        )
        # GUARDED, NOT INDEXED BLIND — the assertion above already fails by name on a
        # missing or extra key, and a defect there must not also crash this one.
        checks.equal(
            listings.get("9191486", {}).get("live"), 4,
            "and the record itself is the one this store actually holds, not a placeholder",
        )

        # --------------------------------------------------------------- refusals
        refusal(
            checks,
            lambda: capture_server.do_inventory_copies({"skus": []}),
            "skus_required",
            "an empty SKU list asks for nothing and is refused rather than answered with "
            "an empty map",
        )
        refusal(
            checks,
            lambda: capture_server.do_inventory_copies({}),
            "skus_required",
            "and a body with no `skus` key at all refuses the same way",
        )
        refusal(
            checks,
            lambda: capture_server.do_inventory_copies({"skus": ["9191486"], "extra": 1}),
            "field_not_settable",
            "an unrecognised field is refused by name",
        )


def check_order_fetch_route(checks: Checks) -> None:
    """`POST /orders/fetch` in both of its bodies (D91), against canned pages and no socket.

    THE FIRST ROUTE-LEVEL COVERAGE THIS ROUTE HAS HAD. `check_shipping_routes`' T3 block proves
    the transport's pieces — the projection, the body builder, the refusal codes — and nothing
    proved that `do_order_fetch` maps the transport's dict into the body `do_order_ingest`
    accepts; that contract lived in two docstrings. It is asserted here by feeding one route's
    answer to the other. And the reason the route has two bodies is asserted as a measurement:
    a window larger than the cap is walked whole and refused nowhere, because the cap counts
    DETAIL calls (D91) — until it did, the owner's 370-order window had never returned an order.

    NO SOCKET. `urllib.request.build_opener` answers canned pages, the seam the T3 block uses,
    because this suite runs on the Stop hook and a case that reached a third party would put a
    stranger's uptime on the path that decides whether work is done. The cookie is this block's
    own fixture, read through `envfile.get_live` off a temp file, for `check_export_fetch`'s
    reason: an earlier `load()` over a real `.env` would otherwise hand the stub the operator's
    session.
    """
    checks.note("")
    checks.note("ORDER FETCH — POST /orders/fetch, two bodies, no socket (D91)")

    cookie = "TCGAuthTicket_Production=t7-fetch-not-a-session; other=1"
    dotenv = Path(tempfile.gettempdir()) / "t7-order-fetch.env"
    dotenv.write_text(
        f"TCGPLAYER_STORE_COOKIE={cookie}\nBANCHI_TCG_SELLER_KEY=a2ffc195\n",
        encoding="utf-8",
    )
    env_keys = (
        "BANCHI_TCG_ORDERS_URL",
        "TCGPLAYER_STORE_COOKIE",
        "BANCHI_TCG_SELLER_KEY",
        envfile.FROM_FILE_ENV,  # check_export_fetch's `keys` says why this is in the ritual
    )
    previous = {name: os.environ.get(name) for name in env_keys}
    env_before = (envfile.ENV_FILE, set(envfile._from_file), envfile._loaded)
    envfile.ENV_FILE = dotenv
    envfile._from_file.clear()
    os.environ.pop(envfile.FROM_FILE_ENV, None)
    envfile._loaded = False

    # SIXTY ORDERS IN THREE STATUSES: three search pages of 25, and more than any cap this
    # block will set. The strings are the API's own spelling as seen on the owner's account.
    statuses = ["Shipped"] * 40 + ["Ready to Ship"] * 15 + ["Cancelled"] * 5
    window = [
        {
            "orderNumber": f"A2FFC195-{at:06X}-{at % 7:05d}",
            "orderDate": f"2026-08-{(at % 28) + 1:02d}",
            "orderStatus": status,
            "buyerName": "Buyer Placeholder",
        }
        for at, status in enumerate(statuses, start=1)
    ]
    detailed: list = []

    class _Reply:
        """What `_open` reads off an opener: a status, headers, and a body."""

        def __init__(self, payload) -> None:
            self.status = 200
            self.headers = {"Content-Type": "application/json"}
            self._body = json.dumps(payload).encode("utf-8")

        def read(self, size=-1):  # noqa: ARG002 — the opener's signature
            return self._body

    class _Canned:
        """An opener answering search pages and details out of `window`, recording each."""

        def __init__(self) -> None:
            self.requests: list = []

        def open(self, request, data=None, timeout=None):  # noqa: A003, ARG002
            self.requests.append(request)
            url = request.full_url
            if "/orders/search" in url:
                body = json.loads(request.data.decode("utf-8"))
                frm, size = int(body["from"]), int(body["size"])
                return _Reply({"totalOrders": len(window), "orders": window[frm : frm + size]})
            asked = url.rsplit("/", 1)[1].split("?")[0]
            match = next(entry for entry in window if entry["orderNumber"] == asked)
            detailed.append(asked)
            return _Reply(
                {
                    "orderNumber": asked,
                    "createdAt": match["orderDate"],
                    "status": match["orderStatus"],
                    "buyerName": "Buyer Placeholder",
                    "shippingAddress": {"line1": "101 Example St", "city": "Springfield"},
                    "paymentType": "Visa",
                    "products": [
                        {"skuId": 9191486, "quantity": 2, "name": "Moonfall", "unitPrice": 11.88}
                    ],
                }
            )

    canned = _Canned()
    real_opener = urllib.request.build_opener
    try:
        for name in ("TCGPLAYER_STORE_COOKIE", "BANCHI_TCG_SELLER_KEY"):
            os.environ.pop(name, None)
        os.environ["BANCHI_TCG_ORDERS_URL"] = "http://127.0.0.1:1"
        checks.equal(
            envfile.get_live("TCGPLAYER_STORE_COOKIE"),
            cookie,
            "the reader answers this block's own fixture cookie and not the operator's",
        )
        urllib.request.build_opener = lambda *args, **kwargs: canned

        with isolated_home():
            # ---- 1. the preview: the pages walked whole, nothing detailed, nothing written
            preview = answers(
                checks,
                lambda: capture_server.do_order_fetch({"preview": True}),
                "the preview body answers",
            )
            if preview is not None:
                checks.equal(
                    sorted(preview),
                    ["by_status", "range", "total", "writes_nothing"],
                    "the preview's key set, whole",
                )
                checks.equal(
                    preview["total"],
                    60,
                    "A WINDOW LARGER THAN THE CAP IS WALKED WHOLE AND REFUSED NOWHERE. The cap "
                    "counts detail calls and not orders in the window (D91) — until it did, the "
                    "owner's 370-order window answered `order_too_many` on every press and this "
                    "route had never handed the ledger an order",
                )
                checks.equal(
                    preview["by_status"],
                    [
                        {"status": "Shipped", "count": 40, "known": 0},
                        {"status": "Ready to Ship", "count": 15, "known": 0},
                        {"status": "Cancelled", "count": 5, "known": 0},
                    ],
                    "counted by the STRING the wire returned, largest first — no status "
                    "vocabulary lives on this side of the wire, and which of these means "
                    "'needs picking' is the operator's tick",
                )
                checks.equal(
                    [request.get_method() for request in canned.requests],
                    ["POST", "POST", "POST"],
                    "three search pages of 25 and NOT ONE detail request",
                )
                checks.equal(detailed, [], "no order was detailed by a preview")
                checks.ok(
                    cookie not in json.dumps(preview) and "Buyer" not in json.dumps(preview),
                    "and neither the credential nor a buyer is in the answer",
                )
            checks.equal(
                capture_server.do_orders()["orders"],
                [],
                "the preview WROTE NOTHING — the ledger is still empty",
            )

            # ---- 2. the fetch: only the ticked status, ingest-shaped, accepted verbatim
            del canned.requests[:]
            fetched = answers(
                checks,
                lambda: capture_server.do_order_fetch(
                    {"statuses": ["Ready to Ship"], "skip_known": True}
                ),
                "the fetch body answers",
            )
            if fetched is not None:
                checks.equal(
                    sorted(fetched),
                    ["detailed", "matched", "names", "orders", "remaining", "skipped_known"],
                    "the fetch's key set, whole: the ingest body, the four counts and the "
                    "buyer backfill (D193)",
                )
                checks.equal(
                    (
                        fetched["matched"],
                        fetched["skipped_known"],
                        fetched["detailed"],
                        fetched["remaining"],
                    ),
                    (15, 0, 15, 0),
                    "fifteen matched the ticked status; all fifteen detailed, none skipped, "
                    "none left over",
                )
                checks.equal(
                    len(detailed),
                    15,
                    "EXACTLY the ticked orders were detailed — the forty shipped and the five "
                    "cancelled cost no request, which is the whole saving",
                )
                checks.equal(
                    sorted(fetched["orders"][0]),
                    ["buyer", "lines", "number", "placed_at", "source", "status"],
                    "each order is the ingest's shape, key set whole — five fields now, "
                    "`buyer` among them",
                )
                checks.equal(
                    fetched["orders"][0]["buyer"],
                    "Buyer Placeholder",
                    "the display name rides the ordinary detail path, same as status or date",
                )
                checks.equal(
                    fetched["names"],
                    [],
                    "AND NAMES IS EMPTY HERE — every one of these fifteen was DETAILED, so "
                    "its buyer already rides on `orders[]`. The backfill is for orders this "
                    "press skips, not the ones it just fetched",
                )
                checks.equal(
                    fetched["orders"][0]["lines"],
                    [{"sku": "9191486", "quantity": 2, "name": "Moonfall", "unit_price": "11.88"}],
                    "and each line is the ingest's spelling, the SKU coerced to a string",
                )
                ingested = answers(
                    checks,
                    lambda: capture_server.do_order_ingest({"orders": fetched["orders"]}),
                    "AND THE INGEST ACCEPTS THE FETCH'S ANSWER VERBATIM — the contract both "
                    "routes' docstrings state, asserted by feeding one to the other",
                )
                if ingested is not None:
                    checks.equal(
                        (ingested["added"], ingested["total"]),
                        (15, 15),
                        "fifteen orders landed in the ledger",
                    )

            # ---- 3. the delta: known at this status is skipped; a moved status is detailed again
            del canned.requests[:]
            del detailed[:]
            again = answers(
                checks,
                lambda: capture_server.do_order_fetch(
                    {"statuses": ["Ready to Ship"], "skip_known": True}
                ),
                "the second press answers",
            )
            if again is not None:
                checks.equal(
                    (
                        again["matched"],
                        again["skipped_known"],
                        again["detailed"],
                        again["remaining"],
                        again["orders"],
                    ),
                    (15, 15, 0, 0, []),
                    "THE LEDGER IS THE DELTA: all fifteen are held at this status, so the second "
                    "press details nothing and pays three search pages",
                )
                checks.equal(
                    again["names"],
                    [],
                    "AND THE STEADY STATE NAMES NOTHING EITHER: the ingest just recorded "
                    "these fifteen buyers verbatim, so `_known_buyers` agrees with the wire "
                    "and there is nothing to backfill",
                )
                checks.equal(len(canned.requests), 3, "three requests, all search pages")
            preview_after = answers(
                checks,
                lambda: capture_server.do_order_fetch({"preview": True}),
                "the preview after an ingest answers",
            )
            if preview_after is not None:
                row = next(
                    entry for entry in preview_after["by_status"]
                    if entry["status"] == "Ready to Ship"
                )
                checks.equal(
                    row["known"],
                    15,
                    "and the preview's `known` is the same compare the delta makes — what it "
                    "says the ledger holds is exactly what the fetch will skip",
                )
            moved = window[40]
            moved["orderStatus"] = "Shipped"
            del detailed[:]
            third = answers(
                checks,
                lambda: capture_server.do_order_fetch({"statuses": ["Shipped"], "skip_known": True}),
                "a fetch of the shipped status answers",
            )
            if third is not None:
                checks.equal(
                    third["detailed"],
                    41,
                    "AN ORDER WHOSE STATUS MOVED IS DETAILED AGAIN, beside the forty never "
                    "fetched — how a shipped order's new word reaches the ledger without a "
                    "full re-fetch",
                )
                checks.ok(
                    moved["orderNumber"] in detailed,
                    "the moved order is among the detailed",
                    f"detailed {len(detailed)}",
                )
            moved["orderStatus"] = "Ready to Ship"

            # ---- 4. the cap counts detail calls, and the leftover is counted rather than dropped
            del detailed[:]
            capped = order_transport.fetch_open_orders(
                "LastThreeMonths", statuses=["Shipped"], limit=10
            )
            checks.equal(
                (capped.total, capped.matched, capped.detailed, capped.remaining),
                (60, 40, 10, 30),
                "A LIMIT OF TEN OVER FORTY MATCHES DETAILS TEN AND REPORTS THIRTY REMAINING. The "
                "window of sixty is not refused; the drop is loud and finite, and the next press "
                "picks the thirty up because the ledger will then know these ten",
            )
            checks.equal(len(detailed), 10, "ten detail requests and no more")

            # ---- 4b: the buyer backfill (D193) — all_statuses,
            # names, and POST /orders/names, none of it costing a detail call it did not
            # already pay for.
            bare_number = window[0]["orderNumber"]
            ingested_bare = answers(
                checks,
                lambda: capture_server.do_order_ingest(
                    {
                        "orders": [
                            {
                                "source": "TCGplayer",
                                "number": bare_number,
                                "status": "Shipped",
                                "lines": [{"sku": "9191486", "quantity": 1}],
                            }
                        ]
                    }
                ),
                "a hand-paste with NO buyer field lands one Shipped order with buyer=None",
            )
            if ingested_bare is not None:
                checks.equal(ingested_bare["added"], 1, "one order added, unnamed")

            del canned.requests[:]
            del detailed[:]
            all_fetch = answers(
                checks,
                lambda: capture_server.do_order_fetch(
                    {"all_statuses": True, "skip_known": True}
                ),
                "all_statuses: true details every status in one body",
            )
            if all_fetch is not None:
                checks.equal(
                    (all_fetch["matched"], all_fetch["skipped_known"], all_fetch["detailed"],
                     all_fetch["remaining"]),
                    (60, 16, 44, 0),
                    "sixteen are known at their current status — the fifteen ingested "
                    "Ready-to-Ship orders and the one bare Shipped paste — so forty-four "
                    "(39 Shipped + 5 Cancelled) are fresh and all fit under the cap",
                )
                checks.equal(
                    len(canned.requests),
                    3 + 44,
                    "three search pages plus exactly forty-four detail requests — NAMING "
                    "COSTS NOTHING BEYOND THAT: the sixteen known orders' buyers come off "
                    "summaries this walk already paid for",
                )
                checks.equal(
                    all_fetch["names"],
                    [{"source": "TCGplayer", "number": bare_number, "buyer": "Buyer Placeholder"}],
                    "AND NAMES LISTS EXACTLY THE KNOWN-NAMELESS ORDER. The fifteen "
                    "Ready-to-Ship orders are known too, but this ledger already spells "
                    "their buyer identically to the wire, so `_known_buyers` drops them — "
                    "only the bare paste, which the ledger holds with no name at all, is "
                    "worth reporting",
                )

                named = answers(
                    checks,
                    lambda: capture_server.do_order_names({"names": all_fetch["names"]}),
                    "POST /orders/names attaches the backfilled name",
                )
                if named is not None:
                    checks.equal(
                        (named["named"], named["unchanged"], named["unknown"], named["total"]),
                        (1, 0, 0, 1),
                        "one order named, nothing unchanged, nothing unknown",
                    )
                checks.equal(
                    next(
                        row["buyer"] for row in capture_server.do_orders()["orders"]
                        if row["number"] == bare_number
                    ),
                    "Buyer Placeholder",
                    "and GET /orders now shows the name on the order the paste left bare",
                )

                repeat_named = answers(
                    checks,
                    lambda: capture_server.do_order_names({"names": all_fetch["names"]}),
                    "naming the same order again",
                )
                if repeat_named is not None:
                    checks.equal(
                        (repeat_named["named"], repeat_named["unchanged"], repeat_named["unknown"]),
                        (0, 1, 0),
                        "A REPEAT NAMES NOTHING NEW: the stored name already equals what was "
                        "sent, so this is `unchanged` rather than a second `named` — the same "
                        "byte-identical-on-a-repeat promise `ingest` makes one field over",
                    )
                unknown_named = answers(
                    checks,
                    lambda: capture_server.do_order_names(
                        {"names": [{"source": "TCGplayer", "number": "NOT-A-REAL-ORDER",
                                     "buyer": "Nobody"}]}
                    ),
                    "naming an order this ledger has never ingested",
                )
                if unknown_named is not None:
                    checks.equal(
                        (unknown_named["named"], unknown_named["unchanged"], unknown_named["unknown"]),
                        (0, 0, 1),
                        "COUNTED, NEVER CREATED. `name_buyer` refuses to mint an order from a "
                        "name and a number alone — that would be a permanent `wanted == 0` "
                        "row no other reader expects",
                    )

                del canned.requests[:]
                del detailed[:]
                again_all = answers(
                    checks,
                    lambda: capture_server.do_order_fetch(
                        {"all_statuses": True, "skip_known": True}
                    ),
                    "a second identical all_statuses press",
                )
                if again_all is not None:
                    checks.equal(
                        again_all["names"],
                        [],
                        "AND NOW NAMES IS EMPTY: the backfill just wrote the one name this "
                        "ledger was missing, so the steady-state press sends none",
                    )
                    checks.equal(
                        (again_all["matched"], again_all["skipped_known"], again_all["detailed"]),
                        (60, 16, 44),
                        "the same sixteen are known and the same forty-four are fresh — "
                        "nothing about the DETAIL arithmetic changed, only the names answer",
                    )

            # ---- 4c. the terminal override reads what THIS FEED actually wrote — not a
            # near-miss. This account's own canned strings are "Shipped" (bare, no " - "
            # suffix) and "Cancelled" (British double-l); neither is a literal member of
            # `store/orders.py:TERMINAL_STATUSES` ("shipped - in transit",
            # "shipped - delivered", "canceled"), so this is the fail-safe proven against
            # REAL WIRE SPELLINGS rather than an invented word — a substring or prefix match
            # on "shipped" or "cancel" would wrongly close both, and it does not.
            # `do_order_fetch` WRITES NOTHING (its own docstring: "not even the ledger"), so
            # the Cancelled row from `window` is ingested directly here, the same shape a
            # detail call would have produced, to put a real "Cancelled" status in the
            # ledger to check.
            answers(
                checks,
                lambda: capture_server.do_order_ingest(
                    {
                        "orders": [
                            {
                                "source": "TCGplayer",
                                "number": "T7-BRITISH-CANCEL",
                                "status": "Cancelled",
                                "lines": [{"sku": "9191486", "quantity": 1}],
                            }
                        ]
                    }
                ),
                "a hand-paste carrying the British 'Cancelled' spelling lands, for 4c below",
            )
            drawn = capture_server.do_orders()
            by_number = {row["number"]: row for row in drawn["orders"]}
            checks.ok(
                bare_number in by_number and "T7-BRITISH-CANCEL" in by_number,
                "the bare-Shipped paste and the British-Cancelled paste are both in the "
                "ledger to check",
                f"got numbers {sorted(by_number)!r}",
            )
            if bare_number in by_number:
                checks.equal(
                    by_number[bare_number]["terminal"],
                    False,
                    "BARE 'Shipped' — NO ' - In Transit' OR ' - Delivered' SUFFIX — DOES "
                    "NOT MATCH. The vocabulary is the exact strings this codebase measured, "
                    "never a prefix, so a feed spelling it more tersely than the two "
                    "recognised variants leaves the order open rather than guessed closed",
                )
            if "T7-BRITISH-CANCEL" in by_number:
                checks.equal(
                    (by_number["T7-BRITISH-CANCEL"]["terminal"],
                     by_number["T7-BRITISH-CANCEL"]["open"]),
                    (False, True),
                    "AND THE BRITISH SPELLING DOES NOT MATCH THE ONE THIS ACCOUNT WAS "
                    "MEASURED USING ('Canceled', one L) — it stays OPEN. Casefold and strip "
                    "tolerate case and whitespace, deliberately never a second spelling — "
                    "recognising one unmeasured near-miss is the first step toward the "
                    "guess this vocabulary exists to refuse",
                )

            refusal(
                checks,
                lambda: capture_server.do_order_fetch(
                    {"statuses": ["Shipped"], "all_statuses": True}
                ),
                "fields_conflict",
                "statuses and all_statuses do not mix — 'these particular ones' and 'every "
                "one' cannot both be the caller's word",
            )
            refusal(
                checks,
                lambda: capture_server.do_order_names(
                    {"names": [{"source": "TCGplayer", "number": bare_number, "buyer": "X",
                                 "email": "buyer@example.com"}]}
                ),
                "field_not_settable",
                "AN EMAIL ON A NAMES PAYLOAD REFUSES BY NAME, exactly as it would on "
                "/orders/ingest — this route writes into the same ledger record through the "
                "same allowlisted field and no other",
            )
            refusal(
                checks,
                lambda: capture_server.do_order_names({"names": []}),
                "names_required",
                "an empty list names nothing and is refused rather than reported as a press "
                "that learned nothing",
            )

            # ---- 5. the refusals
            refusal(
                checks,
                lambda: capture_server.do_order_fetch({}),
                "statuses_required",
                "a body naming no status is refused rather than detailing the window — the "
                "one-press fetch is the thing that never worked",
            )
            refusal(
                checks,
                lambda: capture_server.do_order_fetch({"statuses": []}),
                "statuses_required",
                "an empty tick list is the same refusal",
            )
            refusal(
                checks,
                lambda: capture_server.do_order_fetch({"preview": True, "statuses": ["Shipped"]}),
                "fields_conflict",
                "the two bodies do not mix",
            )
            refusal(
                checks,
                lambda: capture_server.do_order_fetch({"statuses": ["Shipped"], "page_size": 100}),
                "field_not_settable",
                "THE PAGE SIZE AND THE CAP ARE STILL NOT THE CLIENT'S — `_reject_unknown` "
                "refuses by name, so no page can raise this account's request budget",
            )
            refusal(
                checks,
                lambda: capture_server.do_order_fetch({"preview": "yes"}),
                "preview_invalid",
                "a stringified flag is refused rather than read as true",
            )
    finally:
        urllib.request.build_opener = real_opener
        envfile.ENV_FILE, restore_from_file, envfile._loaded = env_before
        envfile._from_file.clear()
        envfile._from_file.update(restore_from_file)
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        dotenv.unlink(missing_ok=True)


CHECKS = (
    check_listing_commands,
    check_committed_copies_are_the_oldest,
    check_copies_out_one_pass_matches_reference,
    check_order_resolver,
    check_order_ledger,
    check_order_reconcile_backlog,
    check_order_line_sealed_from_title,
    check_order_screen,
    check_order_walk_plan_route,
    check_order_places_scoped,
    check_order_picks_tier,
    check_inventory_copies_route,
    check_order_fetch_route,
)
