"""`pkmnscan emit <run-dir>` — write the import CSVs. Free, re-runnable.

TWO FILES PER GAME, and neither split is cosmetic:

    import-listed.csv        above-threshold cards
    import-subthreshold.csv  cards priced by this run's disposition

The valuable cards can be staged and moved live immediately while the bulk file waits, and a
pricing mistake on the cheap file cannot touch the valuable one. Each file independently
obeys the no-duplicate-SKU rule, because two rows with one `TCGplayer Id` in one import file
is undefined behaviour and the emitter must not be able to produce it.

PER GAME because nobody has established that Import to Staged accepts a file spanning two
`Product Line`s — `fixtures/staged-import-accepted.csv` proves it for one line only, and
per-game files are correct under either answer. The default game keeps the two names above;
every other game suffixes its key (`import-listed-riftbound.csv`), see `cli/runs.py`.

IT REFUSES, LOUDLY, WRITING NOTHING, when:

  - the run-wide sub-threshold choice is unset while sub-threshold SKUs exist
  - a `no_market_data` SKU has no hand-entered price (D9: unknown is not cheap)
  - two rows in one file share a `TCGplayer Id`
  - any non-writable column differs from the catalog original
  - a card was queued but is not actually IN the standing queue — the "reported before any
    output is written" rule, checked against the file on disk rather than against the fact
    that `join` said it would

IT DOES NOT REFUSE for a non-empty review queue. It restates the totals beside the row
counts it wrote, so the number is in front of you at the moment you commit an import file.

Byte format is `pipeline.tcgcsv`, unchanged: unquoted header, fully quoted data fields, CRLF,
only `Add to Quantity` and `TCG Marketplace Price` ever written, `TCGplayer Id` never
modified, and `check_only_writable_changed` run per row against the catalog original.

On success every emitted SKU's `pushed` COUNT rises by the copies this run wrote into a file,
and each copy's identity write is appended to `history.jsonl`. `pushed` is a quantity of a
SKU and not a state a card wears (D7 amended) — which copies back it is deliberately
unrecorded, because every unsold copy is equally sellable and an address here would be a
fiction the pull then has to honour. `pushed` still means one thing only: a CSV was written.
Everything past it is confirmed by something outside this pipeline — see `pkmnscan reconcile`.
"""

from __future__ import annotations

from cli import resolve, runs
from pipeline import decisions, join, tcgcsv
from store import master
from store.session import Store


def _warn_stale(run_dir, say) -> None:
    """Name any import file left by an EARLIER emit, at the moment this one refuses.

    Refusing writes nothing, which correctly leaves a previously-valid file alone — but a
    refusal message sitting next to an `import-listed.csv` from an hour ago is exactly how
    a stale file gets imported. Deleting it would be worse: that file may be the one already
    staged. So it is named, not removed. Globbed rather than listed, because the import
    files are per-game now and a stale one is stale whichever game wrote it.
    """
    stale = [
        path
        for pattern in ("import-listed*.csv", "import-subthreshold*.csv")
        for path in sorted(run_dir.directory.glob(pattern))
    ]
    if not stale:
        return
    say("")
    say("NOTE: this run directory still holds import files from an EARLIER emit.")
    say("They are unchanged and may be out of date. Do not import them as this run's output:")
    for path in stale:
        say(f"    {path}")


def _scoped(dispositions, report):
    """The per-SKU dispositions that belong to this game's report.

    `decisions.json` is run-wide and SKUs are TCGplayer-global, so with one report per
    game a disposition for a pokemon SKU must not reach the riftbound pricing pass —
    `prices_for` would refuse it as naming a SKU "not in this batch", which is true of the
    slice and false of the run. The run-level version of that refusal still stands: `run`
    below checks every disposition names SOME game's match before any file is written.
    """
    return {sku: d for sku, d in dispositions.items() if sku in report.matches}


def _game_only(report):
    """(listed, sub_threshold) SKU sets for one game's report — emit's two files."""
    listed = {m.sku for m in report.matches.values() if m.listable} | {
        m.sku for m in report.no_market_data
    }
    return listed, set(report.below_threshold.skus)


def _write(game_join, path, only, choice, say, label):
    if not only:
        say(f"{label:<16} nothing to write")
        return []
    data = join.emit_import(
        game_join.report,
        game_join.catalog,
        path,
        sub_threshold=choice.sub_threshold,
        sku_dispositions=_scoped(choice.dispositions(), game_join.report),
        no_market_data=choice.no_market_data,
        only=only,
    )
    written = tcgcsv.parse(data)
    skus = [row[tcgcsv.SKU_COLUMN] for row in written.rows]
    quantity = sum(int(row[tcgcsv.QUANTITY_COLUMN] or 0) for row in written.rows)
    say(f"{label:<16} {len(skus)} row(s), {quantity} card(s) -> {path}")
    return skus


def run(args, say) -> int:
    run_dir = runs.open_run(args.run_dir)
    try:
        plan = resolve.exports_for(run_dir, args.export)
    except join.EmptyCatalog as refusal:
        say(str(refusal))
        return 1

    decisions_path = run_dir.path(runs.DECISIONS)
    if not decisions_path.is_file():
        say(f"no {runs.DECISIONS} in this run — run `pkmnscan join` first")
        return 1

    try:
        resolved = resolve.load(
            run_dir,
            plan.by_game,
            rule=run_dir.manifest.get("rule", args.rule),
            basis=run_dir.manifest.get("basis", args.basis),
            review_below=run_dir.manifest.get(
                "review_below_confidence", args.review_below_confidence
            ),
        )
    except join.EmptyCatalog as refusal:
        say(str(refusal))
        return 1

    try:
        choice = decisions.Decisions.read(decisions_path)
    except decisions.MalformedDecisions as exc:
        say(f"{runs.DECISIONS} is unusable: {exc}")
        return 1

    store = Store()
    snapshot = store.read()

    # --------------------------------------------------- reported before any output exists
    missing = sorted(
        position
        for position in resolved.queued_positions
        if position not in snapshot.review.entries
        and position not in snapshot.parked.entries
    )
    if missing:
        say("REFUSING to write: cards were routed to a queue but are not in one on disk.")
        say("Run `pkmnscan join` first — nothing may be written before they are recorded.")
        for position in missing[:10]:
            say(f"    {position}")
        _warn_stale(run_dir, say)
        return 1

    # ------------------------------------------------------------------ decisions gate
    blocking = choice.blocking(resolved.sub_threshold_skus)
    if blocking:
        say(f"REFUSING to write. Nothing was written. Edit {decisions_path}:")
        for reason in blocking:
            say(f"    - {reason}")
        _warn_stale(run_dir, say)
        return 1

    say("")
    say(f"pricing          {choice.describe}")
    for warning in choice.warnings:
        say(f"                 note: {warning}")

    # --------------------------------------------------------------------- write the files
    # One import file per game, and a WHOLE-RUN validation pass before the first byte is
    # written. With a single file, "REFUSING to write. Nothing was written." was a
    # property of `emit_import` raising before its write; with one file per game a
    # refusal on the second game would otherwise leave the first game's file behind —
    # a partial emit that looks complete. So every game is priced and gated first, and
    # only a run that will fully succeed writes anything.
    multi = len(resolved.joins) > 1
    say("")
    try:
        unknown = set(choice.dispositions()) - set(resolved.matches)
        if unknown:
            raise join.Undecided(
                f"sku_dispositions names SKUs not in this batch: {sorted(unknown)}"
            )
        for game_join in resolved.joins.values():
            report = game_join.report
            if not report.ok:
                raise join.OutputSuppressed(
                    "output suppressed; unmatched must be reported first:\n"
                    + "\n".join(f"  - {r}" for r in report.blocking_reasons)
                    + "\n"
                    + report.report()
                )
            join.prices_for(
                report,
                sub_threshold=choice.sub_threshold,
                sku_dispositions=_scoped(choice.dispositions(), report),
                no_market_data=choice.no_market_data,
            )

        listed_skus = []
        sub_skus = []
        for game_join in resolved.joins.values():
            game = game_join.game
            if multi:
                say(f"[{game}]")
            listed, sub = _game_only(game_join.report)
            listed_skus += _write(
                game_join,
                run_dir.path(runs.import_listed_name(game)),
                listed,
                choice,
                say,
                "listed",
            )
            sub_skus += _write(
                game_join,
                run_dir.path(runs.import_subthreshold_name(game)),
                sub,
                choice,
                say,
                "sub-threshold",
            )
    except (join.OutputSuppressed, join.Undecided, tcgcsv.ReadOnlyColumn) as exc:
        say("REFUSING to write. Nothing was written.")
        for line in str(exc).splitlines():
            say(f"    {line}")
        _warn_stale(run_dir, say)
        return 1

    emitted = set(listed_skus) | set(sub_skus)
    at_cap = [m for g in resolved.joins.values() for m in g.report.at_cap]
    if at_cap:
        say(f"{'at cap':<16} {len(at_cap)} SKU(s) already at the live "
            f"cap, nothing added")

    # ---------------------------------------------------------- pushed, and the audit trail
    #
    # TWO WRITES PER SKU, AND THEY ARE ABOUT DIFFERENT THINGS. The card gets its identity —
    # `sku`, `condition`, the run that decided them — because that is a fact about the
    # physical object at that position. The SKU's `Listing` gets the count, because how many
    # copies are pushed is a fact about the listing and deliberately not about any copy: the
    # owner's ruling is that copies are fungible, so an address here would be a fiction the
    # pull would then have to honour.
    pushed = 0
    pushed_skus = 0
    with store.write() as writable:
        for match in resolved.matches.values():
            if match.sku not in emitted:
                continue
            copies = 0
            for position in match.live_positions:
                key = master.position_key(position.box, position.index)
                # Upsert first. A position the store has never seen — a run joined from a
                # recovered identifications file, say — would otherwise take a write that
                # lands nowhere and is still reported as having happened.
                writable.inventory.record_capture(
                    master.Card(
                        box=position.box,
                        index=position.index,
                        photo=resolved.photos.get(key),
                    )
                )
                # `set_state(key, IDENTIFIED)` rather than assigning `sku` and `condition`
                # straight onto the record, and the choice is not style. It is the only
                # writer that returns False for a position with no record, which is what
                # keeps v1 bug #5 — a transition reported as having happened that did not —
                # out of this loop; and it is the only one that appends to `history.jsonl`,
                # so the moment this pipeline committed to a SKU for this copy survives in
                # the audit trail. `identified` is where the card already is and where it
                # stays: `pushed` is not a state a card can wear any more, and passing it
                # here now raises `UnknownState` rather than silently flagging a position.
                if writable.inventory.set_state(
                    key,
                    master.IDENTIFIED,
                    sku=match.sku,
                    condition=match.condition,
                    run=run_dir.name,
                ):
                    copies += 1
            if copies:
                # Incremented, not set: two runs can push copies of one SKU, and the second
                # must not erase the first. Re-emitting the SAME run adds nothing because
                # `cli/resolve.py` reads these counts back as `committed`, so those copies
                # are no longer in `match.live_positions` at all — the idempotence lives
                # there rather than in a special case here.
                writable.inventory.listing(
                    match.sku, condition=match.condition
                ).bump(master.PUSHED, copies)
                pushed += copies
                pushed_skus += 1
        queue_line = writable.queue_summary
        stages = writable.inventory.listing_counts()

    run_dir.set(
        emitted={
            "listed": listed_skus,
            "sub_threshold": sub_skus,
            "pushed": pushed,
            "pushed_skus": pushed_skus,
        }
    )

    say("")
    say(f"pushed           {pushed} copy(ies) across {pushed_skus} SKU(s) -> "
        f"{master.PUSHED}")
    listings = ", ".join(f"{k} {v}" for k, v in stages.items() if v)
    if listings:
        say(f"listings         {listings}")
    # Restated here on purpose: this is the moment it is easiest to forget that cards are
    # still sitting in a box unlisted.
    say(f"standing queues  {queue_line}")
    say("")
    listed_names = ", ".join(
        runs.import_listed_name(game) for game in resolved.joins
    ) or runs.IMPORT_LISTED
    say(f"next: import {listed_names} to Staged in TCGplayer, "
        f"then Export From Staged and run")
    say(f"      pkmnscan reconcile {run_dir.directory} <staged-export.csv>")
    return 0
