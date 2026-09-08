"""`pkmnscan reconcile <run-dir> <staged-export.csv>` — what TCGplayer actually staged.

Writing a CSV proves only that a CSV was written. This is the machine-checkable round trip
against the real system that GATES.md calls the highest-value finding from Gate A: download
TCGplayer's own Export From Staged and diff it against what the run sent.

BOTH DIRECTIONS, always. Rows TCGplayer has that the run did not send, and rows the run sent
that did not land. v1 matched by box+position, silently skipped identified cards, and
reported nothing for unmatched rows — a one-directional check passes on that bug.

`pushed` -> `staged` happens here and only here, because `staged` means "something outside
this pipeline confirmed it". Collapsing `staged` into `live` would make D7's refill math
wrong: `Add to Quantity = min(cap - live, backstock)` reads the LIVE number, and an import
staged but never moved live has no live quantity at all.

IT MOVES QUANTITIES, NOT COPIES (D7 amended). The three stages are counts held against a SKU
rather than states a card wears, so what this command does is take `n` off that SKU's
`pushed` and add it to its `staged`. Which physical copies those are is deliberately
unrecorded — every unsold copy of a SKU is equally sellable, and TCGplayer's export could
not tell us which ones anyway.
"""

from __future__ import annotations

from pathlib import Path

from cli import cmd_reprice, runs
from pipeline import join, livecheck, tcgcsv
from store import master
from store.session import Store


def _card_counts(inventory):
    """Per SKU: copies marked sold, copies still on hand, and every SKU ever seen.

    `seen` IS WIDER THAN THE LISTING LEDGER AND HAS TO BE. A card can carry a SKU that was
    never pushed — withheld (D49), sub-threshold and not yet emitted, or simply queued. Judging
    "listed outside pkmnscan" against the ledger alone would accuse the operator of every one
    of them the moment it showed up live.
    """
    sold, hand, seen = {}, {}, set()
    for card in inventory.cards.values():
        sku = getattr(card, "sku", None)
        if not sku:
            continue
        seen.add(sku)
        state = getattr(card, "state", None)
        if state == master.SOLD:
            sold[sku] = sold.get(sku, 0) + 1
        elif state not in master.TERMINAL_STATES:
            hand[sku] = hand.get(sku, 0) + 1
    return sold, hand, seen


def _say_rows(say, rows, head, note, limit=20):
    if not rows:
        return
    say("")
    say(head)
    say(f"  {note}")
    say(f"  {'copies':>6} {'sku':>10} {'push':>4} {'live':>4} {'sold':>4} {'hand':>4}  card")
    for row in rows[:limit]:
        n = row.unexplained or row.live
        say(f"  {n:>6} {row.sku:>10} {row.pushed:>4} {row.live:>4} {row.sold:>4} "
            f"{row.on_hand:>4}  {(row.name or row.condition)[:38]}")
    if len(rows) > limit:
        say(f"  ... and {len(rows) - limit} more")


def _settlement(rows, listings, as_of: str):
    """What a write over `rows` would do, by `Listing.live_reading` — the same rule the
    write applies through `observe_live`, so the preview cannot promise a correction the
    write then refuses. Returns `(adopt, kept, caught_up)`: copies moved per SKU, the rows
    the store outranks as `(sku, stored, stored-as-of, offered)`, and the SKUs whose figure
    already agrees but whose counted sales this file supersedes.

    THE THIRD BUCKET IS D115's, and the preview needs it for the reason it needs the other
    two: `observe_live` returns `CLEARED` there and WRITES — it empties `sold_here` and
    advances `live_as_of` — so a preview that counted it as "nothing to do" would promise a
    no-op and then move a figure on screen. It moves no COPIES, which is why it is counted
    apart from `adopt` rather than folded into it."""
    adopt = {}
    kept = []
    caught_up = []
    for row in rows:
        listing = listings.get(row.sku)
        if listing is None:
            continue
        stored = max(0, int(listing.live))
        offered = max(0, int(row.live))
        if offered == stored:
            if listing.sales_pending(as_of) != max(0, int(listing.sold_here)):
                caught_up.append((row.sku, max(0, int(listing.sold_here))))
            continue
        if listing.live_reading(offered, as_of) == stored:
            kept.append((row.sku, stored, listing.live_observed_at, offered))
        else:
            adopt[row.sku] = abs(offered - stored)
    return adopt, kept, caught_up


def run_live(args, say) -> int:
    """`pkmnscan reconcile --live <export.csv>` — the whole store against one live export.

    PREVIEWS BY DEFAULT, for `pkmnscan prices adopt`'s reason: it moves quantities the cap
    arithmetic reads, over every SKU at once, and a migration nobody watched is how a wrong
    number becomes the new floor.
    """
    path = Path(args.live)
    if not path.is_file():
        say(f"live export not found: {path}")
        return 1

    export = tcgcsv.read_export(path)
    source = runs.describe_source(path)
    store = Store()
    snapshot = store.read()
    sold, hand, seen = _card_counts(snapshot.inventory)
    report = livecheck.compare(
        export.rows, snapshot.inventory.listings, sold, hand, seen
    )

    say("")
    say(f"live export      {source['path']}")
    say(f"                 {source['mtime']}, sha256 {source['sha256'][:12]}")
    say(f"                 {len(export.rows)} row(s)")
    say(f"ledger           {len(snapshot.inventory.listings)} SKU(s) with a listing record")
    say("")
    say(f"agreed           {len(report.agreed)} SKU(s) — every pushed copy is live or marked sold")

    _say_rows(
        say, report.unexplained,
        f"unexplained      {report.unexplained_copies} copy(ies) across "
        f"{len(report.unexplained)} SKU(s)",
        "this pipeline pushed them, TCGplayer does not hold them, and no card is marked sold. "
        "Sold and unmarked, pulled by hand, or a row the portal rejected.",
    )
    _say_rows(
        say, report.beyond,
        f"beyond this pipeline  {len(report.beyond)} SKU(s)",
        "TCGplayer's own quantity for a SKU this pipeline never sent — more than it sent, or "
        "none at all where the store still holds a reading. The READING is written either "
        "way; the copies are left alone, because this pipeline did not put them there.",
    )
    _say_rows(
        say, report.unknown,
        f"never seen here  {len(report.unknown)} SKU(s) live at TCGplayer",
        "sealed product, or singles listed outside pkmnscan. Nothing to reconcile.",
    )
    _say_rows(
        say, report.absent,
        f"absent           {len(report.absent)} SKU(s) in the ledger, not in the export at all",
        "not even a zero-quantity row — check the export covers every Product Line you sell.",
    )

    # THE READING'S TIME IS THE FILE'S, and the preview and the write are computed by one
    # local so they cannot disagree about which rows the store outranks.
    as_of = str(source["mtime"])
    # WHAT THIS PIPELINE PUBLISHED TOO RECENTLY FOR THE EXPORT TO KNOW ABOUT (D106), read
    # BEFORE the preview and not just before the write. `_settlement`'s own docstring says the
    # preview and the write are computed from one rule so the preview "cannot promise a
    # correction the write then refuses" — a skip applied only on the write path would break
    # exactly that, and silently, because the dry run is what the operator reads first.
    just_published = cmd_reprice.published_recently()
    settling = [
        row for row in report.agreed + report.unexplained + report.beyond
        if row.sku not in just_published
    ]
    held_back = [
        row for row in report.agreed + report.unexplained + report.beyond
        if row.sku in just_published
    ]
    adopt, kept, caught_up = _settlement(settling, snapshot.inventory.listings, as_of)

    def _say_held(stored_of) -> None:
        """The SKUs this refuses to settle, and why, in both the preview and the receipt.

        NAMED, NEVER SILENT. A held SKU is a settlement the operator asked for and did not
        get, and D87's posture for a reading it will not take is to keep the stored figure and
        REPORT it. The sentence says what to do, because "wait" is actionable and "skipped"
        is not.
        """
        if not held_back:
            return
        say("")
        say(f"held back        {len(held_back)} SKU(s) published from here in the last "
            f"{cmd_reprice.PUBLISH_LAG_S // 60} minutes")
        say("                 TCGplayer's live export is not read-your-writes: after a publish it "
            "goes on serving")
        say("                 the old price, and the file's date is when it was FETCHED — so a "
            "stale reading")
        say("                 arrives looking fresh and would overwrite what was just set. The "
            "store keeps its")
        say("                 own figure. Re-run this later and they settle normally.")
        for row in held_back[:8]:
            stored = stored_of(row.sku)
            say(f"                   {row.sku}  published {just_published[row.sku]}  "
                f"store {stored} vs export {row.live}")
        if len(held_back) > 8:
            say(f"                   … and {len(held_back) - 8} more")

    if not args.write:
        say("")
        say(f"DRY RUN — nothing written. {sum(adopt.values())} copy(ies) of `{master.LIVE}` "
            f"would be corrected from the export; {len(kept)} SKU(s) kept: store newer than "
            f"this export (fetched {source['mtime']}).")
        for sku, stored, stamp, offered in kept[:8]:
            say(f"                   {sku}  store {stored} (as of {stamp}) vs export {offered}")
        _say_held(lambda sku: max(0, int(snapshot.inventory.listings[sku].live))
                  if sku in snapshot.inventory.listings else 0)
        would_record = len([row for row in report.unknown if row.sku not in just_published])
        if would_record:
            say(f"                 {would_record} SKU(s) live at TCGplayer with no record here "
                f"would be recorded,")
            say("                 each with the first sighting this export is evidence of. "
                "`pushed` stays 0 on")
            say("                 them: this pipeline did not send them, and `live` is what "
                "the export attests.")
        if caught_up:
            say(f"                 {len(caught_up)} SKU(s) carry sales counted here that this "
                f"file already reflects;")
            say("                 their counters would be cleared. No copy moves — the "
                "figure on screen was")
            say("                 already right, and what changes is that the store stops "
                "subtracting them twice.")
        say("`pushed` is left alone: it is the cumulative record of what was sent, and")
        say("`cli/resolve.py:_copies_out` already corrects a stuck one against the physical")
        say("ceiling. Re-run with --write.")
        return 0

    moved = 0
    touched = 0
    kept_count = 0
    caught_up_count = 0
    sighted = 0
    recorded = 0
    # WHAT THIS PIPELINE PUBLISHED TOO RECENTLY FOR THE EXPORT TO KNOW ABOUT (D106). Read
    # before the write opens, because it walks the markdown receipts on disk and the store
    # lock is not the place to do that.
    with store.write() as writable:
        for row in settling:
            listing = writable.inventory.listings.get(row.sku)
            if listing is None:
                continue
            # `live` COMES FROM THE EXPORT AND IS NOT NEGOTIATED BETWEEN READINGS OF EQUAL
            # AGE. D8 and D11 make the export authoritative about what TCGplayer holds at
            # the moment it was read, and `cli/resolve.py:_copies_out` treats the NEWEST
            # reading as a floor that "cannot be argued below". A store observation made
            # after this file — a sale, a later settlement — stands, and is reported (D87,
            # amended). This is the one field the reconcile writes — see
            # `pipeline/livecheck.py`'s header for why `pushed` is read and never rewritten.
            before = listing.live
            verdict = listing.observe_live(row.live, as_of)
            if verdict == master.ADOPTED:
                moved += abs(listing.live - before)
                touched += 1
            elif verdict == master.KEPT:
                kept_count += 1
            elif verdict == master.CLEARED:
                # THE FIGURE AGREED AND THE FILE STILL TAUGHT US SOMETHING (D115): it was
                # taken after sales this store had counted against the older reading, so
                # those sales are now in the reading and the counter is emptied. No copy
                # moved, which is why it is counted apart from `moved` — but a figure on
                # screen did, so it may not be silent either. D59's rule.
                caught_up_count += 1
            # THE SIGHTING IS TAKEN WHATEVER THE QUANTITY VERDICT WAS, and that is the
            # point of it being a separate call. A SKU sitting at the same figure returns
            # `UNCHANGED` above and is exactly the row whose age nothing else can
            # establish — every one of the owner's 443 records was in that state when this
            # landed, none of them carrying a first sighting.
            if row.live > 0 and listing.sight(as_of):
                sighted += 1
        # SKUS TCGPLAYER HOLDS THAT THIS STORE HAS NEVER SEEN, WRITTEN RATHER THAN ONLY
        # REPORTED. Until 2026-09-06 this loop skipped them — `listings.get(sku)` returned
        # None and the row was named in the preview and dropped — so the store had no
        # memory of its own live book beyond what it had photographed: measured, 0 of 443
        # listing records had no card behind them, while the export carried 28 live SKUs
        # that did. Without a record there is no first sighting, so nothing could say how
        # long any of them had been listed, nothing stopped a rule marking the same one
        # down on every pass, and a copy selling was invisible.
        #
        # `pushed` STAYS 0 AND THAT IS NOT AN OMISSION. It is the cumulative record of what
        # THIS pipeline sent, and it sent none of these; `live` is an observation of what
        # TCGplayer holds, which is exactly what the export is evidence of. The two fields
        # already mean different things and this is the row where the difference shows.
        for row in report.unknown:
            if row.sku in just_published:
                continue
            listing = writable.inventory.listing(row.sku, condition=row.condition or None)
            if listing.observe_live(row.live, as_of) == master.ADOPTED:
                recorded += 1
            if row.live > 0 and listing.sight(as_of):
                sighted += 1
        stages = writable.inventory.listing_counts()
        # THE HELD SKUS' OWN FIGURES, LIFTED INSIDE THE LOCK. They are what the receipt
        # prints, and reading them off `snapshot` afterwards would print a number from before
        # a write that may have touched other rows of the same document.
        stages_live = {
            sku: writable.inventory.listings[sku].live
            for sku in just_published
            if sku in writable.inventory.listings
        }

    say("")
    say(f"settled          {touched} listing(s); {moved} copy(ies) of `{master.LIVE}` "
        f"corrected from the export; {kept_count} listing(s) kept: store newer than this "
        f"export")
    for sku, stored, stamp, offered in kept[:8]:
        say(f"                   {sku}  store {stored} (as of {stamp}) vs export {offered}")
    _say_held(lambda sku: max(0, int(stages_live.get(sku, 0))))
    if caught_up_count:
        say("")
        say(f"caught up        {caught_up_count} SKU(s) whose counted sales this export "
            f"already reflects")
        say("                 The reading did not move, so no copy was corrected. What "
            "moved is that those")
        say("                 sales are now IN the reading and are no longer counted on top "
            "of it (D115).")
    if recorded or sighted:
        say("")
        say(f"recorded         {recorded} SKU(s) live at TCGplayer that this store had no "
            f"record of; {sighted} first sighting(s) stamped")
        say("                 A first sighting is how long the LISTING has been up, which is "
            "what `reprice`")
        say("                 ranks staleness on. It is monotone — the earliest reading wins "
            "and nothing")
        say("                 overwrites it — so it only sharpens as more exports are read.")
    counted = ", ".join(f"{k} {v}" for k, v in stages.items() if v) or "empty"
    say(f"listings         {counted}")
    if report.unexplained_copies:
        say("")
        say(f"{report.unexplained_copies} copy(ies) were sent and are neither live nor marked "
            f"sold.")
        say("Mark the sold ones on #/inventory; what is left is a listing you pulled or a")
        say("row TCGplayer refused. Nothing here adjusts them — `pushed` is a record.")
    return 0


def run(args, say) -> int:
    if getattr(args, "live", None):
        return run_live(args, say)
    if not args.run_dir or not args.staged_export:
        say("give a run directory and a staged export, or --live <export.csv> for the "
            "whole store")
        return 1
    run_dir = runs.open_run(args.run_dir)
    staged_path = Path(args.staged_export)
    if not staged_path.is_file():
        say(f"staged export not found: {staged_path}")
        return 1

    # THROUGH `emitted_skus`, WHICH IS THE UNION ACROSS EVERY EMIT (D54). This report runs in
    # BOTH directions, so a record holding only the last emit's delta would put every SKU
    # from an earlier import into `rows_without_cards` — reconcile accusing something else of
    # writing rows it wrote itself.
    sent = run_dir.emitted_skus
    if not sent:
        say("this run has emitted nothing — run `pkmnscan emit` first")
        return 1

    staged = tcgcsv.read_export(staged_path)
    source = runs.describe_source(staged_path)
    report = join.reconcile_import(staged.rows, sent)

    say("")
    say(f"staged export    {source['path']}")
    say(f"                 {source['mtime']}, sha256 {source['sha256'][:12]}")
    say(f"run sent         {len(sent)} SKU(s)")
    say("")
    for line in report.report().splitlines():
        say(line)

    # --------------------------------------------------- pushed -> staged, as SKU quantities
    landed = set(report.matched_skus)

    # HOW MANY COPIES OF EACH SKU TCGPLAYER SAYS IT STAGED. `Add to Quantity` is the column
    # `emit` wrote and the only one that can carry a STAGED quantity: `Total Quantity` is the
    # LIVE number (D8, D11), which `join` reads as `SkuMatch.live_before`. A copy moved to
    # `staged` on the strength of `Total Quantity` would be a command reading a column it did
    # not mean to name, which is the class of defect T7's command-seam cases exist for.
    #
    # `.get` rather than indexing, because nothing validates that an Export From Staged
    # carries every column a Filtered Export does, and a missing column must read as an
    # unknown quantity — handled below — rather than raise here.
    staged_quantity = {
        row[tcgcsv.SKU_COLUMN]: tcgcsv.parse_quantity(row.get(tcgcsv.QUANTITY_COLUMN, ""))
        for row in staged.rows
    }

    store = Store()
    moved = 0
    moved_skus = 0
    assumed = []
    with store.write() as writable:
        for sku in sorted(landed):
            listing = writable.inventory.listings.get(sku)
            if listing is None or listing.pushed <= 0:
                # Nothing this pipeline pushed is waiting on this SKU. The row is matched and
                # is reported above either way; there is simply no count here to move, and
                # inventing one would stage copies nothing ever wrote into a file.
                continue
            reported = staged_quantity.get(sku, 0)
            if reported <= 0:
                # A BLANK OR ZERO CELL IS AN UNKNOWN QUANTITY, NOT A ZERO ONE — D9's reading
                # of a blank market cell, applied to a quantity. The SKU is in this export,
                # so TCGplayer has it; refusing to move anything would strand every pushed
                # copy at `pushed` forever and make `staged_stale` warn about an import that
                # in fact landed. So the SKU's own pushed count stands in, and the assumption
                # is named in the report rather than made silently.
                reported = listing.pushed
                assumed.append(sku)
            # Capped at what this pipeline pushed. The export is authoritative about the SKU
            # being there and about how much of it is there; it says nothing about copies
            # nobody here ever sent, and `bump` would floor `pushed` at zero while inflating
            # `staged` past the truth.
            count = min(reported, listing.pushed)
            listing.bump(master.STAGED, count)
            listing.bump(master.PUSHED, -count)
            moved += count
            moved_skus += 1
        counts = writable.inventory.counts()
        stages = writable.inventory.listing_counts()

    held = ", ".join(f"{k} {v}" for k, v in counts.items() if v) or "empty"
    listings = ", ".join(f"{k} {v}" for k, v in stages.items() if v) or "empty"
    say("")
    say(f"staged           {moved} copy(ies) across {moved_skus} SKU(s) moved "
        f"{master.PUSHED} -> {master.STAGED}")
    if assumed:
        say(f"                 {len(assumed)} SKU(s) reported no quantity in the export; "
            f"this pipeline's own pushed count stood in:")
        say(f"                   {', '.join(assumed[:8])}")
    say(f"listings         {listings}")
    say(f"inventory        {held}")

    if not report.ok:
        say("")
        say("NOT a clean round trip. Both directions are above; neither is ignorable —")
        say("a row TCGplayer has that this run did not send means something else wrote it,")
        say("and a row that did not land means a card is marked pushed and is not staged.")

    text = "\n".join(
        [
            f"run: {run_dir.name}",
            f"staged export: {source['path']} ({source['sha256'][:12]})",
            f"sent: {len(sent)} SKU(s)",
            "",
            report.report(),
            "",
            f"moved {master.PUSHED} -> {master.STAGED}: "
            f"{moved} copies across {moved_skus} SKU(s)",
            f"clean: {report.ok}",
        ]
    )
    path = run_dir.write_text(runs.RECONCILE, text + "\n")
    run_dir.set(
        reconciled={
            "staged_export": source,
            "matched": len(report.matched_skus),
            "rows_without_cards": report.rows_without_cards,
            "cards_without_rows": report.cards_without_rows,
            "ok": report.ok,
        }
    )
    say("")
    say(f"report           {path}")
    return 0 if report.ok else 1
