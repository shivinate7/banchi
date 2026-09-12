"""`pkmnscan queue refresh` — re-resolve every open queue entry, store-wide.

FREE, RE-RUNNABLE, AND IT PREVIEWS BY DEFAULT — `join`, `reconcile` and `reprice list`'s
posture, for `reconcile --live`'s reason: it rewrites every open entry in the store at once,
and a migration nobody watched is how a wrong number becomes the new floor.

THE EXPORTS DEFAULT TO THE ONES THE RUNS ALREADY RECORDED, newest per game, and that is the
ordinary case rather than a convenience. The 513 frozen entries this command exists for do
not need a NEWER catalogue — they need to be re-resolved through CURRENT CODE. `rarity` on a
candidate row and D137's Near Mint rule are properties of `cli/resolve.py:_candidate_rows`
and of the candidate path, not of the CSV: re-running the ladder over the very file a run
used already repairs both. A fresher or wider export is accepted with `--export` and changes
what the ladder can find; it is not what makes the refresh work.

`--export` IS REPEATABLE RATHER THAN COMMA-SEPARATED, which is `/trends`, `/scope` and
`?run=`'s rule for their reason: a comma inside a value is indistinguishable from the
separator, and these are file paths.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple

from pipeline import corpus as corpus_mod
from pipeline import decisions
from store import files
from store.session import Store

from cli import requeue, runs


def _recorded_exports(root: Optional[Path] = None) -> "List[Tuple[str, Path]]":
    """Every export the JOINED runs recorded, oldest first, deduped by path.

    OLDEST FIRST BECAUSE `catalogs_from` LETS THE LAST FILE WIN. A game two runs both
    recorded an export for answers off the freshest reading, which is D87's rule applied to
    a catalogue rather than to a quantity.

    A run that has never been joined is left out. Its export is a real file and its cards
    are not in any queue this command can reach — `join` has not run, so nothing was queued
    — so reading it would widen the catalogue on behalf of no entry.
    """
    root = root or files.runs_dir()
    found: "List[Tuple[str, Path]]" = []
    if not root.is_dir():
        return found
    for entry in sorted(root.iterdir()):
        manifest = entry / runs.MANIFEST
        if not entry.is_dir() or not manifest.is_file():
            continue
        try:
            payload = json.loads(manifest.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if not payload.get("joined"):
            continue
        # BOTH SHAPES. `exports` is the per-game map every run written since D25 carries;
        # `export` is the single block the runs before it carry, and the owner's store still
        # holds one (`2026-08-22-box1-03`). Reading only the new shape would silently drop
        # the oldest catalogues, which are exactly the ones the oldest entries were joined
        # against.
        blocks = []
        if isinstance(payload.get("exports"), dict):
            blocks += list(payload["exports"].values())
        if isinstance(payload.get("export"), dict):
            blocks.append(payload["export"])
        for block in blocks:
            raw = block.get("path") if isinstance(block, dict) else None
            if not raw:
                continue
            path = Path(str(raw))
            if not path.is_absolute():
                path = files.home() / path
            if path.is_file():
                found.append((str(block.get("mtime") or ""), path))
    found.sort()
    seen: set = set()
    out: "List[Tuple[str, Path]]" = []
    for mtime, path in found:
        if path in seen:
            continue
        seen.add(path)
        out.append((mtime, path))
    return out


def run(args, say) -> int:
    if getattr(args, "queue_command", None) != "refresh":
        say("give a subcommand: `pkmnscan queue refresh [--export <file.csv>] [--write]`")
        return 2
    return refresh(args, say)


def refresh(args, say) -> int:
    asked = [Path(p) for p in (getattr(args, "export", None) or [])]
    missing = [p for p in asked if not p.is_file()]
    if missing:
        for path in missing:
            say(f"export not found: {path}")
        return 1

    if asked:
        paths = asked
        chose = "named on the command line"
    else:
        recorded = _recorded_exports()
        paths = [path for _, path in recorded]
        chose = "recorded by the joined runs, newest per game"
        if not paths:
            say("")
            say("no export to resolve against.")
            say(
                "    Every open entry was queued by a join, and a join records the export it "
                "used — so an empty list here means no run in this checkout has been joined. "
                "Name one with `--export <file.csv>`."
            )
            return 1

    catalogs, source, unreadable = requeue.catalogs_from(paths)
    for path, why in unreadable:
        say(f"export skipped   {path.name}: {why}")
    if not catalogs:
        say("")
        say("no usable catalogue in any export given — nothing can be re-resolved.")
        return 1

    store = Store()
    snapshot = store.read()
    try:
        book = corpus_mod.Corpus.read()
    except (decisions.MalformedDecisions, ValueError) as exc:
        say(f"pricing corpus will not parse: {exc}")
        return 1
    threshold, rule, basis = requeue.policy_of(book)

    plan = requeue.plan(
        snapshot.inventory,
        snapshot.review,
        snapshot.parked,
        catalogs,
        threshold=threshold,
        rule=rule,
        basis=basis,
    )

    say("")
    say(f"catalogues       {len(catalogs)} game(s), {chose}")
    for game in sorted(catalogs):
        rows = len(catalogs[game].export.rows)
        say(f"                   {game:<14} {rows} row(s)  {source[game].name}")
    say(f"policy           threshold={threshold} rule={rule} basis={basis}")
    say("")
    say(f"open entries     {plan.examined}")
    say(f"answered, left alone   {plan.cleared} — a cleared entry is never re-queued (D28)")
    say("")
    say(f"unchanged        {plan.unchanged}")
    say(f"refreshed        {len(plan.refreshed)} entry(ies) rewritten in place")
    if plan.refreshed:
        rarity = sum(c.gained_rarity for c in plan.refreshed)
        dropped = sum(c.dropped_off_condition for c in plan.refreshed)
        if rarity:
            say(f"                   +{rarity} candidate row(s) now carry a rarity")
        if dropped:
            say(
                f"                   -{dropped} candidate row(s) dropped: not Near Mint "
                f"(D137 — this lists Near Mint)"
            )
        if plan.answerable:
            say(
                f"                   {len(plan.answerable)} now offer exactly ONE row — "
                f"answerable in one tap"
            )
        for change in plan.refreshed[:12]:
            say(f"    {change.describe}")
        if len(plan.refreshed) > 12:
            say(f"    ... and {len(plan.refreshed) - 12} more")
    say("")
    say(f"resolves now     {len(plan.resolved)} entry(ies) leave the queue")
    if plan.resolved:
        say(
            "                   the ladder settles these against a current catalogue, so "
            "the card lists rather than waiting for a person."
        )
        for change in plan.resolved[:12]:
            say(f"    {change.describe}")
        if len(plan.resolved) > 12:
            say(f"    ... and {len(plan.resolved) - 12} more")

    if plan.photo_moved:
        say("")
        say(
            f"re-bound         {plan.photo_moved} entry(ies) name a different photograph than "
            f"the card now at their position"
        )
        say(
            "                   a mid-box delete slides every higher card down one (D10), and "
            "the question is rebuilt for the card that is THERE. The store says which slot a "
            "card is in (D36)."
        )

    if plan.skipped:
        say("")
        say(f"skipped          {len(plan.skipped)} entry(ies), left exactly as they stand")
        for reason, count in Counter(s.reason for s in plan.skipped).most_common():
            say(f"    {count:>5}  {requeue.SKIP_SENTENCES.get(reason, reason)}")
        for skip in plan.skipped[:8]:
            say(f"    {skip.describe}")
        if len(plan.skipped) > 8:
            say(f"    ... and {len(plan.skipped) - 8} more")

    if not args.write:
        say("")
        say(
            f"DRY RUN — nothing written. {plan.touched} entry(ies) would change. "
            f"Re-run with --write to apply."
        )
        return 0

    if not plan.touched:
        say("")
        say("nothing to write — every open entry already reads the way this pass resolves it.")
        return 0

    with store.write() as writable:
        added_main, added_parked, released = plan.apply(writable.review, writable.parked)
        line = writable.queue_summary

    say("")
    say(
        f"written          +{added_main} main, +{added_parked} parked, "
        f"-{len(released)} resolved"
    )
    say(f"queues           {line}")
    # NEW ENTRIES ARE NOT EXPECTED AND ARE REPORTED RATHER THAN ASSUMED IMPOSSIBLE. This pass
    # walks positions that are already queued, so every `upsert` should be a refresh; a
    # non-zero count here means a position moved between the two queues, which `apply_run`
    # handles and which the operator should be able to see happening.
    if added_main or added_parked:
        say(
            "                   a position counted as NEW moved between the two queues — "
            "the entry it left behind is released in the same transaction (`queues.apply_run`)."
        )
    return 0
