"""`pkmnscan emit <run-dir>` — write the import CSVs. Free, re-runnable.

TWO FILES, and the split is not cosmetic:

    import-listed.csv        above-threshold cards
    import-subthreshold.csv  cards priced by this run's disposition

The valuable cards can be staged and moved live immediately while the bulk file waits, and a
pricing mistake on the cheap file cannot touch the valuable one. Each file independently
obeys the no-duplicate-SKU rule, because two rows with one `TCGplayer Id` in one import file
is undefined behaviour and the emitter must not be able to produce it.

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

On success every emitted SKU's copies transition to `pushed`, and the transition is appended
to `history.jsonl`. `pushed` means one thing only: a CSV was written. Everything past it is
confirmed by something outside this pipeline — see `pkmnscan reconcile`.
"""

from __future__ import annotations

from pathlib import Path

from cli import resolve, runs
from pipeline import decisions, join, tcgcsv
from store import master
from store.session import Store


def _warn_stale(run_dir, say) -> None:
    """Name any import file left by an EARLIER emit, at the moment this one refuses.

    Refusing writes nothing, which correctly leaves a previously-valid file alone — but a
    refusal message sitting next to an `import-listed.csv` from an hour ago is exactly how
    a stale file gets imported. Deleting it would be worse: that file may be the one already
    staged. So it is named, not removed.
    """
    stale = [
        run_dir.path(name)
        for name in (runs.IMPORT_LISTED, runs.IMPORT_SUBTHRESHOLD)
        if run_dir.path(name).is_file()
    ]
    if not stale:
        return
    say("")
    say("NOTE: this run directory still holds import files from an EARLIER emit.")
    say("They are unchanged and may be out of date. Do not import them as this run's output:")
    for path in stale:
        say(f"    {path}")


def _write(resolved, path, only, choice, say, label):
    if not only:
        say(f"{label:<16} nothing to write")
        return []
    data = join.emit_import(
        resolved.report,
        resolved.catalog,
        path,
        sub_threshold=choice.sub_threshold,
        sku_dispositions=choice.dispositions(),
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
    export_path = resolve.export_for(run_dir, args.export)
    if not Path(export_path).is_file():
        say(f"export not found: {export_path}")
        return 1

    decisions_path = run_dir.path(runs.DECISIONS)
    if not decisions_path.is_file():
        say(f"no {runs.DECISIONS} in this run — run `pkmnscan join` first")
        return 1

    resolved = resolve.load(
        run_dir,
        Path(export_path),
        rule=run_dir.manifest.get("rule", args.rule),
        basis=run_dir.manifest.get("basis", args.basis),
        review_below=run_dir.manifest.get(
            "review_below_confidence", args.review_below_confidence
        ),
    )

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
    listed = resolved.listed_skus | resolved.no_market_data_skus
    sub = resolved.sub_threshold_skus
    say("")
    try:
        listed_skus = _write(
            resolved,
            run_dir.path(runs.IMPORT_LISTED),
            listed,
            choice,
            say,
            "listed",
        )
        sub_skus = _write(
            resolved,
            run_dir.path(runs.IMPORT_SUBTHRESHOLD),
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
    if resolved.report.at_cap:
        say(f"{'at cap':<16} {len(resolved.report.at_cap)} SKU(s) already at the live "
            f"cap, nothing added")

    # ---------------------------------------------------------- pushed, and the audit trail
    pushed = 0
    with store.write() as writable:
        for match in resolved.report.matches.values():
            if match.sku not in emitted:
                continue
            for position in match.live_positions:
                key = master.position_key(position.box, position.index)
                # Upsert first. A position the store has never seen — a run joined from a
                # recovered identifications file, say — would otherwise take a state
                # transition that lands nowhere and is still reported as having happened.
                writable.inventory.record_capture(
                    master.Card(
                        box=position.box,
                        index=position.index,
                        photo=resolved.photos.get(key),
                    )
                )
                if writable.inventory.set_state(
                    key,
                    master.PUSHED,
                    sku=match.sku,
                    condition=match.condition,
                    run=run_dir.name,
                ):
                    pushed += 1
        queue_line = writable.queue_summary

    run_dir.set(
        emitted={"listed": listed_skus, "sub_threshold": sub_skus, "pushed": pushed}
    )

    say("")
    say(f"pushed           {pushed} card copy(ies) -> {master.PUSHED}")
    # Restated here on purpose: this is the moment it is easiest to forget that cards are
    # still sitting in a box unlisted.
    say(f"standing queues  {queue_line}")
    say("")
    say(f"next: import {run_dir.path(runs.IMPORT_LISTED).name} to Staged in TCGplayer, "
        f"then Export From Staged and run")
    say(f"      pkmnscan reconcile {run_dir.directory} <staged-export.csv>")
    return 0
