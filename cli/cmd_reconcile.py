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

from cli import runs
from pipeline import join, tcgcsv
from store import master
from store.session import Store


def run(args, say) -> int:
    run_dir = runs.open_run(args.run_dir)
    staged_path = Path(args.staged_export)
    if not staged_path.is_file():
        say(f"staged export not found: {staged_path}")
        return 1

    emitted = run_dir.manifest.get("emitted") or {}
    sent = list(emitted.get("listed") or []) + list(emitted.get("sub_threshold") or [])
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
