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

    # ------------------------------------------------------- pushed -> staged, per copy
    landed = set(report.matched_skus)
    store = Store()
    moved = 0
    with store.write() as writable:
        for card in writable.inventory.in_state(master.PUSHED):
            if card.sku in landed and writable.inventory.set_state(
                card.key, master.STAGED, run=run_dir.name
            ):
                moved += 1
        counts = writable.inventory.counts()

    held = ", ".join(f"{k} {v}" for k, v in counts.items() if v) or "empty"
    say("")
    say(f"staged           {moved} card copy(ies) moved {master.PUSHED} -> {master.STAGED}")
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
            f"moved {master.PUSHED} -> {master.STAGED}: {moved} copies",
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
