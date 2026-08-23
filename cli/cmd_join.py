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

from cli import resolve, runs
from pipeline import decisions, join, routing
from store import master, queues
from store.session import Store

STALE_EXPORT_DAYS = 7


def run(args, say) -> int:
    run_dir = runs.open_run(args.run_dir)
    # The file->game mapping, read off each file's own Product Line cells, and every
    # refusal it can raise — two files claiming one game, a game in the run with no
    # export, a file naming no registered game — fires HERE, before the store is opened,
    # before any catalog is built, before anything is written or queued.
    try:
        plan = resolve.exports_for(run_dir, args.export)
    except join.EmptyCatalog as refusal:
        say(str(refusal))
        return 1

    store = Store()
    snapshot = store.read()

    # The queue totals LEAD the report — you see them while choosing what to work on.
    say("")
    say(f"standing queues  {snapshot.queue_summary}")

    # `staged_stale` reads LISTINGS now, not positions (D7 amended): staged is a quantity of
    # a SKU rather than a state a card wears, so what has gone stale is the SKU's import and
    # not any one copy. The line names the SKU and how many copies of it are sitting there,
    # because that is what you would go and finish in TCGplayer — a position label would send
    # you to a box, which is the one place the problem is not.
    stale = snapshot.inventory.staged_stale()
    if stale:
        say(
            f"staged >{master.STAGED_STALE_DAYS} days  {len(stale)} SKU(s) staged and never "
            f"moved live: " + ", ".join(f"{e.sku} x{e.staged}" for e in stale[:8])
        )

    try:
        resolved = resolve.load(
            run_dir,
            plan.by_game,
            rule=args.rule,
            basis=args.basis,
            review_below=args.review_below_confidence,
        )
    except join.EmptyCatalog as refusal:
        say(str(refusal))
        return 1

    # One export/catalog block per game. A one-game run prints exactly the block it
    # always did; a multi-game run names the game on each line, because two files with
    # two ages and two collision counts under one unlabelled heading is a report that
    # cannot be read back.
    multi = len(resolved.joins) > 1
    say("")
    for game_join in resolved.joins.values():
        source = game_join.source
        prefix = f"{game_join.game}: " if multi else ""
        say(f"export           {prefix}{source['path']}")
        say(f"                 {source['mtime']} ({source['age_days']} days old), "
            f"sha256 {source['sha256'][:12]}")
        if source["age_days"] >= STALE_EXPORT_DAYS:
            say(f"                 WARNING: {source['age_days']} days old. Prices and "
                f"quantities move. Warning only — this run is not blocked.")
        catalog = game_join.catalog
        dropped = (
            f", {catalog.dropped_rows} row(s) of other product lines dropped"
            if catalog.dropped_rows
            else ""
        )
        say(f"catalog          {prefix}{len(game_join.export.rows)} rows, "
            f"{len(catalog.set_names)} set(s), "
            f"{len(catalog.colliding_keys)} colliding key(s){dropped}")
        if catalog.colliding_keys:
            for key in catalog.colliding_keys[:8]:
                say(f"                   {key} -> {', '.join(catalog.sets_for_key(key))}")
    for note in plan.notes:
        say(f"                 {note}")
    say(f"pricing          rule={resolved.rule} basis={resolved.basis} "
        f"review-below-confidence={args.review_below_confidence}")
    say("")

    # ------------------------------------------------- the report itself, game by game
    sections = []
    for game_join in resolved.joins.values():
        text = game_join.report.report()
        sections.append(f"[{game_join.game}]\n{text}" if multi else text)
    report_text = "\n\n".join(sections)
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
        # already read for D7's refill math (`SkuMatch.live_before`). A SKU that now shows
        # quantity against it on TCGplayer has been moved live by a human, and nothing else
        # in this pipeline would ever notice.
        #
        # IT IS SET, NOT INCREMENTED, AND IT IS SET FROM THE EXPORT. D8 and D11 put the
        # authority in the export, so the stored number is the optimistic local estimate
        # `master.Listing` describes and this is the line that corrects it. A count that
        # walked up on its own would be a second source of truth competing with the file
        # the whole join is built on.
        #
        # This block used to choose WHICH positions went live — the first `live_before`
        # copies in box-walk order took a `live` state and the rest stayed `staged`. That
        # made listing progress an address for no physical reason (the owner's ruling is
        # that copies of one SKU are fungible), and it could not represent the ordinary
        # case of a SKU showing more live quantity than this pipeline ever pushed.
        moved_live = []
        for match in resolved.matches.values():
            quantity = max(0, int(match.live_before))
            # Peeked rather than got-or-created: `Inventory.listing` creates on read, and
            # calling it for every matched SKU would fill the file with empty records whose
            # only content is that the SKU exists — which the export already says, better.
            if writable.inventory.listings.get(match.sku) is None and quantity == 0:
                continue
            listing = writable.inventory.listing(match.sku, condition=match.condition)
            before = listing.live
            if quantity == before:
                continue
            listing.live = quantity
            listing.at = master.now()
            moved_live.append((match.sku, before, quantity))

            # Copies that just went live are no longer staged. `reconcile` is the only thing
            # that puts a copy in `staged` and nothing else would ever take it out, so
            # without this drawdown `staged_stale` names every SKU that has ever staged,
            # forever — a warning that fires on success is a warning nobody reads.
            #
            # Drawn down by the RISE in live quantity, never by the absolute reading. The
            # absolute number would also erase copies staged since the last join, which are
            # exactly the copies the stale warning exists to find.
            newly_live = quantity - before
            if newly_live > 0 and listing.staged > 0:
                listing.bump(master.STAGED, -min(listing.staged, newly_live))

        queue_line = writable.queue_summary
        counts = writable.inventory.counts()
        stages = writable.inventory.listing_counts()

    say("")
    say(f"queued           +{added_main} main, +{added_parked} parked, "
        f"-{len(released)} resolved and released")
    say(f"standing queues  {queue_line}")
    if moved_live:
        rose = sum(after - before for _, before, after in moved_live if after > before)
        fell = sum(before - after for _, before, after in moved_live if after < before)
        say(f"live             {len(moved_live)} SKU(s) moved, +{rose}/-{fell} cop(ies), "
            f"read from the export")
        for sku, before, after in moved_live[:8]:
            say(f"                   {sku}  {before} -> {after}")
    held = ", ".join(f"{k} {v}" for k, v in counts.items() if v)
    if held:
        say(f"inventory        {held}")
    # The three TCGplayer stages used to appear on the line above, because a card wore one
    # of them as its state. They are quantities of a SKU now, so they are counted separately
    # — reporting only `counts()` would have quietly deleted them from every run report.
    listed = ", ".join(f"{k} {v}" for k, v in stages.items() if v)
    if listed:
        say(f"listings         {listed}")

    # ------------------------------------------------------------- decisions.json (merge)
    decisions_path = run_dir.path(runs.DECISIONS)
    if decisions_path.is_file():
        choice = decisions.Decisions.read(decisions_path)
        say(f"decisions        merging into existing {runs.DECISIONS} — your edits are kept")
    else:
        choice = decisions.Decisions(rule=resolved.rule, basis=resolved.basis)

    added = choice.add_unpriced(sorted(resolved.no_market_data_skus))
    dropped = choice.prune(set(resolved.matches))
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
    # `exports` is the recorded shape: {game: source}, the mapping VERIFIED off the
    # files' own Product Line cells above. An old run's scalar `export` key is read-side
    # backfilled by `runs.Run.exports_by_game` and never rewritten here — this writes
    # what THIS join verified, nothing else.
    run_dir.set(
        exports={g.game: g.source for g in resolved.joins.values()},
        rule=str(resolved.rule),
        basis=resolved.basis,
        review_below_confidence=args.review_below_confidence,
        joined=True,
        counts={
            "cards_in": sum(g.report.cards_in for g in resolved.joins.values()),
            "skus": len(resolved.matches),
            "queued_main": sum(
                len(g.report.queue(routing.MAIN)) for g in resolved.joins.values()
            )
            + len(resolved.failures),
            "queued_parked": sum(
                len(g.report.queue(routing.PARKED)) for g in resolved.joins.values()
            ),
            "no_market_data": len(resolved.no_market_data_skus),
            "sub_threshold": len(resolved.sub_threshold_skus),
        },
    )

    full_report = "\n".join(
        [f"run: {run_dir.name}"]
        + [
            f"export: {(g.game + ': ') if multi else ''}{g.source['path']} "
            f"({g.source['age_days']}d, {g.source['sha256'][:12]})"
            for g in resolved.joins.values()
        ]
        + [
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
