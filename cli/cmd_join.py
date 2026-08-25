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

from collections import Counter

from cli import resolve, runs
from pipeline import decisions, join, routing
from store import master, queues
from store.session import Store

STALE_EXPORT_DAYS = 7


def _reason_counts(resolved: resolve.Resolved) -> Counter:
    """What this run would put in the standing queues, counted by reason code.

    Read off `entries_for` rather than off the reports directly, so the preview counts the
    entries that would actually be WRITTEN — pre-join failures included. A preview built
    from a different source than the write is a preview that can be wrong in the one way
    that matters.

    Raw reason strings, never a friendly gloss. `app/src/ReviewQueue.tsx` carries the only
    label table in the product and says in its own comment that nothing keeps it in step
    with the Python constants; a second table here would be a third vocabulary with even
    less holding it together, which is exactly the drift D16 exists to catch. The plain
    English the operator needs is about the BYPASS RULE, not about each code, and that is
    one sentence printed once — see `_preview`.
    """
    main, parked = resolve.entries_for(resolved)
    return Counter(entry.reason for entry in main + parked)


def _counts_block(say, counts: Counter, indent: str = "                   ") -> None:
    for reason, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        say(f"{indent}{reason:<34} {count}")


def _preview(args, run_dir, plan, resolved, say) -> int:
    """`--dry-run`: everything the join would compute, and nothing it would write.

    The comparison is the point. It walks the ladder a SECOND time with the bypass flipped
    and diffs the two queues, so the operator sees what the flag buys on their own cards
    before spending a decision on it — rather than reading a description of what it does
    and guessing. Walking twice is free: the ladder is local arithmetic over an export
    already parsed and a store already read.
    """
    mine = _reason_counts(resolved)
    say("")
    say(f"DRY RUN          nothing written — no queues, no {runs.DECISIONS}, no "
        f"{runs.REPORT}, no manifest")
    say(f"would queue      {sum(mine.values())} card(s)")
    _counts_block(say, mine)

    try:
        other = resolve.load(
            run_dir,
            plan.by_game,
            rule=args.rule,
            basis=args.basis,
            review_below=args.review_below_confidence,
            trust_claim=not args.bypass,
        )
    except join.EmptyCatalog:  # pragma: no cover — the first load would have refused first
        return 0

    theirs = _reason_counts(other)
    with_bypass, without = (mine, theirs) if args.bypass else (theirs, mine)
    cleared = sum(without.values()) - sum(with_bypass.values())
    say("")
    if args.bypass:
        say(f"without --bypass {sum(without.values())} would queue instead — "
            f"--bypass is clearing {cleared}")
    else:
        say(f"with --bypass    {cleared} of these resolve by the finish claim you made at "
            f"capture,")
        say(f"                 and {sum(with_bypass.values())} still need you: they have no "
            f"claim to fall back on,")
        say(f"                 so answering them for you would mean inventing a row rather "
            f"than trusting you.")
        if with_bypass:
            _counts_block(say, with_bypass)
    say("")
    say(f"next: pkmnscan join {run_dir.directory} --export <file>"
        f"{'' if args.bypass else ' --bypass'}  (to write it)")
    return 0


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
            trust_claim=args.bypass,
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
    if args.bypass:
        # Named on every run it is on, and named as a LOSS rather than as a setting. The
        # operator chose "resolved by the claim, and the run report says so", and a line
        # that read `bypass=True` would satisfy the letter of that while telling a reader
        # six weeks later nothing about what the run gave up to get its small queue.
        say("cross-check      OFF (--bypass): where a finish claim exists, the photo may "
            "not contradict it.")
        say("                 D3 rung 3 is not consulted for those cards. Cards with no "
            "claim are unaffected.")
    say("")

    # ------------------------------------------------- the report itself, game by game
    sections = []
    for game_join in resolved.joins.values():
        text = game_join.report.report()
        sections.append(f"[{game_join.game}]\n{text}" if multi else text)
    report_text = "\n\n".join(sections)
    for line in report_text.splitlines():
        say(line)

    # D36 — said before the report rather than after it, because it changes what every
    # position in that report MEANS. A correction the operator learns about afterwards is one
    # they have already read a run report without.
    if resolved.realigned:
        say("")
        say(
            f"slots realigned: {len(resolved.realigned)} card(s) matched to the slot their "
            f"photograph is in NOW, not the slot they were identified at."
        )
        say(
            "    A card was deleted from the middle of this box since it was identified, so "
            "everything after it slid down one (D10). Matched by photograph, never guessed."
        )
        for old_key, new_key in sorted(
            resolved.realigned.items(), key=lambda kv: int(kv[0].split("/")[1])
        )[:5]:
            say(f"    {old_key} -> {new_key}")
        if len(resolved.realigned) > 5:
            say(f"    ... and {len(resolved.realigned) - 5} more")
        say("")

    # Named rather than dropped in silence — `CLAUDE.md`'s rule is that a card may leave the
    # pipeline unlisted, never unrecorded, and a card that has left the BOX is the one case
    # where there is no queue to record it into.
    if resolved.departed:
        say(
            f"skipped: {len(resolved.departed)} card(s) in this run are no longer in the box "
            f"— deleted mid-box or retired since it was identified."
        )
        for key in resolved.departed[:5]:
            say(f"    {key} (identified here, photograph is gone)")
        if len(resolved.departed) > 5:
            say(f"    ... and {len(resolved.departed) - 5} more")
        say("")

    # An unchecked box must not read as a verified one.
    if resolved.unverified_boxes:
        boxes = ", ".join(str(b) for b in resolved.unverified_boxes)
        say(
            f"slots NOT verified for box {boxes}: nothing on disk to check them against — "
            f"no photographs, no record carrying a digest, or none of this run's digests "
            f"among the photographs there (a re-shoot replaces the bytes). This run's slot "
            f"numbers were taken as recorded. If a card was deleted mid-box since it was "
            f"identified, they are wrong and nothing here can tell."
        )
        say("")

    if resolved.failures:
        say(f"pre-join failures (-> main queue): {len(resolved.failures)}")
        for failure in resolved.failures:
            say(f"    {failure.describe}")

    # ------------------------------------------------------------------------ dry run
    # BEFORE the first write and after the whole report, which is the only ordering that
    # makes this useful: a preview that skipped the report would preview nothing, and one
    # that ran after the queues were written would not be a preview.
    if args.dry_run:
        return _preview(args, run_dir, plan, resolved, say)

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
    if resolved.bypassed:
        say(f"bypassed         {resolved.bypassed} card(s) resolved by the finish claim "
            f"over a disagreeing photo")
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
        # The manifest is what explains a result months later, so the flag is recorded
        # beside the count it produced. `bypassed: 0` on a `--bypass` run is a real and
        # different fact from the key being absent, which is why both are written.
        bypass_detection=bool(args.bypass),
        bypassed=resolved.bypassed,
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
        ]
        + (
            [f"cross-check: OFF (--bypass) — {resolved.bypassed} card(s) resolved by the "
             f"finish claim over a disagreeing photo"]
            if args.bypass
            else []
        )
        + [
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
