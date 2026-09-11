"""`pkmnscan scan` — read the codes off a directory of code-card photographs.

FREE, LOCAL, DETERMINISTIC, AND RE-RUNNABLE. It makes no model call and no network call of
any kind, so unlike `identify` it has no money gate, no confirmation and no dry-run cost.
`--dry-run` exists anyway, for the same reason `join --dry-run` does: seeing what a write
would do before it happens is worth having even when the write is cheap.

WHY IT IS ITS OWN COMMAND RATHER THAN A BRANCH INSIDE `identify`. `identify` is the command
whose docstring opens "submit, wait, collect, cache" and whose one job is spending money at
the Batch API. The code-card primary path is the opposite of that in every respect — no
submission, no waiting, no cache, no cost — and folding it in would mean the command that
COSTS MONEY sometimes silently does not, which is the property a money gate depends on being
unambiguous. Two commands, two costs, and `--dry-run` means the same thing in both.

WHAT IT WRITES, AND WHERE. Two places, in one locked session:

    inventory/codes.jsonl    the ledger (`codes/ledger.py`), keyed by the CODE
    inventory.json           the code onto the card's own `number` field

THE SECOND IS C8's DISPUTE LOOKUP AND IS NOT REDUNDANT. `GET /search` substring-matches and
ranks exact on `number`, so putting the code there makes "type the code, get the card, tap
its photograph" work through the search that already exists, with no new screen. It is free
for this game: `pokemon_code` joins by name (`join_key: name_only`), so nothing ever composes
a `number/printed_total` key out of these fields. `identify/prompt.py:_parse_code` reaches
the same field by the paid route, and the two agreeing matters more than either rule.

A CARD IS NEVER SKIPPED, which is `identify/sidecar.py`'s rule and applies here unchanged.
Every degraded case ends in a named outcome:

    decoded                  the ordinary path
    no QR found              REPORTED, and the card keeps its photograph and its position.
                             The remedy is the next reader — the paid vision transcription,
                             then a human — and the report says so rather than implying the
                             card is lost.
    decoded, no `2d_code`    the QR read but is not a redemption URL. Reported with its
                             payload, because "this is not a code card" and "this code card
                             did not read" want different remedies and only the payload
                             tells them apart.
    no position              cannot be keyed to a photograph, so it gets no ledger line and
                             is named. Same rule `cli/cmd_identify.py:_code_ledger_lines`
                             already applies.
    not a code card          a photo whose game claim is not `pokemon_code` is left entirely
                             alone. This command never touches the singles track.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from codes import ledger, products, scan
from store import files as store_files
from store.session import Store

CODE_GAME = scan.CODE_GAME


def run(args, say) -> int:
    directory = Path(args.capture_dir)
    if not directory.is_dir():
        say(f"not a directory: {directory}")
        return 2

    try:
        reading = scan.read_directory(directory, box=getattr(args, "box", None))
    except Exception as exc:  # noqa: BLE001 — `QrUnavailable` is the one that matters
        say(str(exc))
        return 1
    others = reading.other_games

    say(f"capture dir     {directory}")
    say(f"photographs     {reading.photographs}")
    say(f"code cards      {reading.code_cards}"
        + (f"  ({others} other games, untouched)" if others else ""))
    if not reading.code_cards:
        say("")
        say("Nothing to scan. A code card is a capture whose game claim is "
            f"`{CODE_GAME}` — set it on the capture screen's Game field.")
        return 0

    fresh = reading.entries
    problems = reading.problems
    malformed = reading.malformed

    say("")
    say(f"decoded         {len(fresh)}/{reading.code_cards}   (no model call, no network)")
    if malformed:
        say(f"unusual shape   {len(malformed)} code(s) decoded but do not match the printed "
            "3-4-3-3 layout. REPORTED, NOT REFUSED — a payload that survived the QR's own "
            "error correction is far likelier to be a print run this repo has not met.")

    if args.dry_run:
        existing = ledger.read()
        _, counts = ledger.merge([ledger.Entry.parse(e.to_payload()) for e in existing], fresh)
        say("")
        say("DRY RUN — nothing written.")
        say(f"would add       {counts['new']} new, {counts['updated']} updated, "
            f"{counts['duplicate']} duplicate position(s), "
            f"{counts['terminal_skipped']} already sold or dead")
        _report_problems(say, problems)
        return 0

    with Store().write() as writable:
        merged, counts, recorded = scan.apply(writable, fresh)

    say("")
    say(f"ledger          {store_files.codes_ledger_path()}")
    say(f"                {counts['new']} new, {counts['updated']} updated, "
        f"{len(merged)} code(s) on file")
    say(f"searchable      {recorded} card record(s) now carry their code — "
        "type the code into the app's search to find the card and its photograph")

    if counts["duplicate"]:
        say("")
        say(f"DUPLICATE       {counts['duplicate']} code(s) were read at a SECOND position. "
            "That is either one card photographed twice or two cards bearing one code — "
            "and if it is the second, one of them is worth nothing. Both photographs are "
            "named on the ledger line; look at them before selling either.")
    if counts["terminal_skipped"]:
        say(f"already gone    {counts['terminal_skipped']} code(s) are delivered or dead and "
            "were left alone. A re-scan never returns a sold code to stock.")

    _report_problems(say, problems)

    held = [e for e in merged if e.sellable]
    say("")
    say("held by product:")
    for row in products.summarize(held):
        mark = "PREMIUM" if row["premium"] else "bulk   "
        say(f"                {mark}  {row['count']:5d}  {row['display']}")
    unclaimed = sum(1 for e in held if not e.product)
    if unclaimed:
        say(f"                {unclaimed} held code(s) carry NO product claim, so no channel "
            "can tier them. Set the Game and Product fields on the capture screen, or "
            "correct them per card on the inventory screen.")
    say("")
    say("next: open the app's Codes screen to export a channel file.")
    return 0


def _report_problems(say, problems: List[str]) -> None:
    if not problems:
        return
    say("")
    say(f"unread          {len(problems)} card(s). NEVER dropped — each keeps its photograph "
        "and its position, and the remedy is the next reader:")
    for problem in problems:
        say(f"                  {problem}")
