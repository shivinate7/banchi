"""`pkmnscan prices` — the pricing corpus: fold the run files in, and look at what is in it.

WHY THERE IS A COMMAND AT ALL. `pipeline/corpus.py` moved the listing answer out of the run
directory and into one file for the store (D86, amended). Eight run directories on this
machine already hold answers, and a migration that ran implicitly on the next join would be a
data move nobody watched — with a real decision inside it, because 8 of those SKUs are
answered twice and 3 of the pairs are a `withheld` hold against a later price.

SO IT IS EXPLICIT, IT PREVIEWS BY DEFAULT, AND IT REPORTS EVERY CHOICE IT MAKES. `adopt`
without `--write` reads and prints; the owner's ruling on the contested rows is newest-wins,
and the three that lose a hold are named in as many words rather than counted.
"""

from __future__ import annotations

import json

from cli import runs
from pipeline import corpus, decisions
from store import files


def _run_answers():
    """Every run's legacy `decisions.json`, OLDEST FIRST — the order newest-wins depends on.

    Run names are date-prefixed, so directory order is chronological. A run whose file cannot
    be parsed is REPORTED and skipped rather than taken as empty: an unreadable answer file is
    the one an operator most needs to be told about, and reading it as `{}` would silently
    adopt nothing from it.
    """
    root = files.runs_dir()
    if not root.is_dir():
        return [], []
    found, broken = [], []
    for entry in sorted(root.iterdir()):
        path = entry / runs.DECISIONS
        if not entry.is_dir() or not path.is_file():
            continue
        try:
            found.append((entry.name, json.loads(path.read_text("utf-8"))))
        except (OSError, ValueError) as exc:
            broken.append((entry.name, str(exc)))
    return found, broken


def _adopt(args, say) -> int:
    book = corpus.Corpus.read()
    if book.answers and not args.force:
        say(f"{corpus.FILENAME} already holds {len(book.answers)} answer(s).")
        say("Adopting again would fold the run files over them. Pass --force if that is what")
        say("you want; the run files are legacy and are read by nothing else.")
        return 1

    found, broken = _run_answers()
    for name, why in broken:
        say(f"SKIPPED {name}/{runs.DECISIONS}: {why}")
    if not found:
        say(f"no run carries a {runs.DECISIONS} — nothing to adopt")
        return 0

    folded, changes = corpus.adopt(found, corpus.Corpus() if args.force else book)
    say(f"{len(found)} run file(s) -> {len(folded.answers)} answer(s)")
    say(f"policy           rule={folded.rule} basis={folded.basis} sub_threshold={folded.sub_threshold}")
    holds = sum(1 for answer in folded.answers.values() if answer.is_hold)
    say(f"holds            {holds} card(s) held back, and they now outlive their run")

    if changes:
        say("")
        say(f"{len(changes)} card(s) were answered more than one way. Newest wins:")
        for change in changes:
            mark = "  <-- A HOLD WAS REPLACED BY A PRICE" if change.hold_lost else ""
            say(f"  {change.sku}  kept {change.kept}{mark}")
            for name, token in change.dropped:
                say(f"      dropped {token} ({name})")
        lost = [change for change in changes if change.hold_lost]
        if lost:
            say("")
            # THE ONE OUTCOME WORTH SAYING TWICE. A hold is a deliberate "not this one", and
            # newest-wins resolves it to the price that was typed by somebody who could not see
            # it — which is the direction that cost money in the first place (D86).
            say(f"{len(lost)} hold(s) were replaced by a later price. If any of those were")
            say("deliberate, re-hold the card on #/pricing — it is one answer now, not one")
            say("per box:")
            for change in lost:
                say(f"  {change.sku}")

    if not args.write:
        say("")
        say("DRY RUN — nothing written. Re-run with --write to adopt.")
        return 0

    written = folded.write()
    say("")
    say(f"written          {written}")
    say("                 the run files are legacy now and are read by nothing.")
    return 0


def _show(args, say) -> int:
    try:
        book = corpus.Corpus.read()
    except (decisions.MalformedDecisions, ValueError) as exc:
        # `ValueError` COVERS THE POLICY REFUSALS — `UnknownRule`, `UnknownBasis` and
        # `InvalidThreshold` are all `ValueError`s and none is a `MalformedDecisions`, so this
        # command answered a bad threshold with a traceback where `join` and `emit` answer it
        # with a sentence. It is the one command whose whole job is showing you this file.
        say(f"{corpus.FILENAME} is unusable: {exc}")
        return 1
    say(f"{files.prices_path()}")
    say(
        f"policy           rule={book.rule} basis={book.basis} "
        f"threshold=${book.threshold} sub_threshold={book.sub_threshold}"
    )
    for name, over in sorted(book.overrides.items()):
        say(f"  override       {name}: {over}")
    held = {sku: answer for sku, answer in book.answers.items() if answer.is_hold}
    say(f"answers          {len(book.answers)} ({len(held)} held back)")
    if args.held:
        # THE CROSS-RUN VIEW OF WHAT IS BEING HELD — D49 named its absence and D62 repeated it.
        # It is one line here because the answers are in one file; it was unbuildable while
        # they were in eight.
        for sku, answer in sorted(held.items()):
            value = answer.value
            reason = value.get("withheld") if isinstance(value, dict) else "unlisted"
            watch = value.get("watch_above") if isinstance(value, dict) else None
            note = value.get("note") if isinstance(value, dict) else None
            line = f"  {sku}  {reason}"
            if watch:
                line += f" above ${watch}"
            if note:
                line += f" — {note}"
            say(line)
    return 0


def run(args, say) -> int:
    if args.prices_command == "adopt":
        return _adopt(args, say)
    return _show(args, say)
