"""`pkmnscan join <run-dir>` — resolve identifications against the export. Free.

Free and re-runnable, which is what makes the rest of the design affordable: clear a review,
refresh the export, change the rule, run it again. Nothing here spends money and nothing here
writes an import file.

WHAT IT PRODUCES. The report, in both directions and in full. The standing queues, updated
with every card that did not list. And `decisions.json`, pre-filled with every SKU that needs
an answer and the run-wide choice left UNSET — `emit` refuses until you set it.

REVIEWS DO NOT BLOCK. An unresolved card sits at a known position in a box: it is not lost
and it is not urgent, and holding 400 good cards hostage to 7 ambiguous ones is the wrong
trade (v2 §5.6). What the hard rule actually demands is that unmatched be reported in both
directions BEFORE any output exists, and that is exactly the order here — this command
reports and queues, and `emit` is a separate command that runs afterwards.

THE EXPORT'S AGE IS A WARNING, NEVER A REFUSAL. A stale export is a judgment call, and a
hard stop on a snapshot's age would block a legitimate run for a reason already on screen.
"""

from __future__ import annotations

from pathlib import Path

from cli import resolve, runs
from pipeline import decisions, routing
from store import master, queues
from store.session import Store

STALE_EXPORT_DAYS = 7


def run(args, say) -> int:
    run_dir = runs.open_run(args.run_dir)
    export_path = resolve.export_for(run_dir, args.export)
    if not Path(export_path).is_file():
        say(f"export not found: {export_path}")
        return 1

    store = Store()
    snapshot = store.read()

    # The queue totals LEAD the report — you see them while choosing what to work on.
    say("")
    say(f"standing queues  {snapshot.queue_summary}")

    stale = snapshot.inventory.staged_stale()
    if stale:
        say(
            f"staged >14 days  {len(stale)} card(s) staged and never moved live: "
            + ", ".join(c.key for c in stale[:8])
        )

    resolved = resolve.load(
        run_dir,
        Path(export_path),
        rule=args.rule,
        basis=args.basis,
        review_below=args.review_below_confidence,
    )

    source = resolved.source
    say("")
    say(f"export           {source['path']}")
    say(f"                 {source['mtime']} ({source['age_days']} days old), "
        f"sha256 {source['sha256'][:12]}")
    if source["age_days"] >= STALE_EXPORT_DAYS:
        say(f"                 WARNING: {source['age_days']} days old. Prices and "
            f"quantities move. Warning only — this run is not blocked.")
    say(f"catalog          {len(resolved.export.rows)} rows, "
        f"{len(resolved.catalog.set_names)} set(s), "
        f"{len(resolved.catalog.colliding_keys)} colliding key(s)")
    if resolved.catalog.colliding_keys:
        for key in resolved.catalog.colliding_keys[:8]:
            say(f"                   {key} -> {', '.join(resolved.catalog.sets_for_key(key))}")
    say(f"pricing          rule={resolved.rule} basis={resolved.basis} "
        f"review-below-confidence={args.review_below_confidence}")
    say("")

    # ---------------------------------------------------------------- the report itself
    report_text = resolved.report.report()
    for line in report_text.splitlines():
        say(line)

    if resolved.failures:
        say(f"pre-join failures (-> main queue): {len(resolved.failures)}")
        for failure in resolved.failures:
            say(f"    {failure.describe}")

    # --------------------------------------------------------------- write the queues
    main, parked = resolve.entries_for(resolved)
    # A card this run resolved leaves whichever queue it was sitting in. Scoped to the
    # positions this run actually processed, so joining box 3 cannot evict box 7's entries.
    freed = resolved.processed_positions - resolved.queued_positions
    with store.write() as writable:
        # Upsert and release as one unit — `queues.apply_run` also releases the entry a
        # re-routed position leaves behind in the OTHER queue, which the two independent
        # release calls that used to sit here could not see. Found by a real run: 16
        # positions moved review -> parked and every stale review entry survived.
        added_main, added_parked, released = queues.apply_run(
            writable.review, writable.parked, main, parked, freed
        )

        # `live` is refreshed here and costs nothing new: the export's `Total Quantity` is
        # already read for D7's refill math (`SkuMatch.live_before`). A staged copy whose
        # SKU now shows quantity against it on TCGplayer has been moved live by a human,
        # and nothing else in this pipeline would ever notice. Capped at the quantity the
        # export reports, so N staged copies of a SKU showing 1 live promotes exactly one.
        went_live = 0
        for match in resolved.report.matches.values():
            quantity = match.live_before
            if quantity <= 0:
                continue
            staged = [
                card
                for card in writable.inventory.positions_for_sku(match.sku)
                if card.state == master.STAGED
            ]
            for card in staged[:quantity]:
                if writable.inventory.set_state(card.key, master.LIVE, run=run_dir.name):
                    went_live += 1

        queue_line = writable.queue_summary
        counts = writable.inventory.counts()

    say("")
    say(f"queued           +{added_main} main, +{added_parked} parked, "
        f"-{len(released)} resolved and released")
    say(f"standing queues  {queue_line}")
    if went_live:
        say(f"live             {went_live} staged copy(ies) now show quantity on TCGplayer")
    held = ", ".join(f"{k} {v}" for k, v in counts.items() if v)
    if held:
        say(f"inventory        {held}")

    # ------------------------------------------------------------- decisions.json (merge)
    decisions_path = run_dir.path(runs.DECISIONS)
    if decisions_path.is_file():
        choice = decisions.Decisions.read(decisions_path)
        say(f"decisions        merging into existing {runs.DECISIONS} — your edits are kept")
    else:
        choice = decisions.Decisions(rule=resolved.rule, basis=resolved.basis)

    added = choice.add_unpriced(sorted(resolved.no_market_data_skus))
    dropped = choice.prune(set(resolved.report.matches))
    choice.rule = resolved.rule
    choice.basis = resolved.basis
    choice.write(decisions_path)

    say(f"                 {decisions_path}")
    say(f"                 {choice.describe}")
    if added:
        say(f"                 +{len(added)} unpriced SKU(s) need a hand-entered answer")
    if dropped:
        say(f"                 -{len(dropped)} stale unanswered entr(ies) removed")
    for warning in choice.warnings:
        say(f"                 note: {warning}")

    for reason in choice.blocking(resolved.sub_threshold_skus):
        say(f"                 EMIT WILL REFUSE: {reason}")

    # ------------------------------------------------------------------------ persist
    run_dir.set(
        export=source,
        rule=str(resolved.rule),
        basis=resolved.basis,
        review_below_confidence=args.review_below_confidence,
        joined=True,
        counts={
            "cards_in": resolved.report.cards_in,
            "skus": len(resolved.report.matches),
            "queued_main": len(resolved.report.queue(routing.MAIN)) + len(resolved.failures),
            "queued_parked": len(resolved.report.queue(routing.PARKED)),
            "no_market_data": len(resolved.no_market_data_skus),
            "sub_threshold": len(resolved.sub_threshold_skus),
        },
    )

    full_report = "\n".join(
        [
            f"run: {run_dir.name}",
            f"export: {source['path']} ({source['age_days']}d, {source['sha256'][:12]})",
            f"rule={resolved.rule} basis={resolved.basis}",
            "",
            report_text,
            "",
            "pre-join failures:",
        ]
        + [f"    {f.describe}" for f in resolved.failures]
        + ["", f"standing queues: {queue_line}"]
    )
    path = run_dir.write_text(runs.REPORT, full_report + "\n")
    say("")
    say(f"report           {path}")
    say(f"next: edit {decisions_path}, then pkmnscan emit {run_dir.directory}")
    return 0
