"""`pkmnscan cards contradictions` — one SKU, two stored numbers (`D-sku-number-contradictions`).

READ-ONLY, ALWAYS. Groups every card by SKU straight out of the store, no `Store()` write
lock taken anywhere in this module. The default preview never touches the network: it
reports every SKU whose stored numbers disagree, and classifies each one as a denominator
mismatch (unambiguous from stored data alone) or as needing the catalogue.

`--resolve` IS THE ONLY THING HERE THAT CALLS THE NETWORK, and only for the SKUs the
preview already named as needing the catalogue — one `Market.products(category_id,
group_id)` request per DISTINCT (game, set) pair among them, cached by
`pipeline/pricehistory.py:Market` exactly as `cmd_pricearchive.py`'s own sweep caches it.
Without `--resolve`, this command opens no socket. It asks whether a candidate number's
catalogue product is named what this SKU's own copies stored — NAME AGREEMENT, not mere
existence (see `pipeline/sku_number_contradictions.py`'s own docstring for why existence
alone is vacuous in a dense set). This module never writes a card, and never touches the
review queue: `store/queues.py:Queue.upsert` refuses to re-queue a position already
answered (D167), and a card this check flags has usually already been through review once.
That gap is recorded separately, not closed here.

Kept in its own file rather than folded into `cli/cmd_cards.py` or `cli/cmd_pricearchive.py`
— it is a separate, more speculative check, on the owner's own ruling to keep it apart from
the four approved stored-data checks (a separate, sibling PR), and it is not the archive
sweep this task's own brief says not to run.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List

from pipeline import games as games_module
from pipeline import pricehistory
from pipeline.sku_number_contradictions import (
    NumberRecord,
    Outcome,
    find_disagreements,
    resolve,
)
from store import db, files


def _read_only(directory: Path) -> sqlite3.Connection:
    """Same door `cli/cmd_cards.py:_read_only` uses — `mode=ro&immutable=1`, never
    `db.connect`, so a preview cannot perform a schema migration.
    """
    target = db.path(directory)
    if not target.is_file():
        raise FileNotFoundError(f"no store at {target}")
    return sqlite3.connect(f"file:{target}?mode=ro&immutable=1", uri=True)


def _by_sku(conn: sqlite3.Connection) -> Dict[str, List[NumberRecord]]:
    out: Dict[str, List[NumberRecord]] = {}
    for key, sku, name, number, set_name, game in conn.execute(
        "SELECT key, sku, name, number, set_name, game FROM cards "
        "WHERE sku IS NOT NULL AND sku != ''"
    ):
        out.setdefault(str(sku), []).append(
            NumberRecord(key=str(key), number=number, name=name, set_name=set_name, game=game)
        )
    return out


def _market_cache_dir() -> Path:
    # Same directory `cli/cmd_pricearchive.py:market_cache_dir` names — a resolve run from
    # here is warm against a sweep's own fetches this hour, and vice versa.
    return files.inventory_dir() / ".market-cache"


def _product_line_for_game(game) -> str:
    return games_module.get(game or games_module.DEFAULT_GAME)["product_line"]


def run(args, say) -> int:
    directory = files.inventory_dir()
    conn = _read_only(directory)
    by_sku = _by_sku(conn)
    conn.close()

    disagreements = find_disagreements(by_sku)
    if not disagreements:
        say("VERDICT: no SKU in this store carries two stored numbers that disagree.")
        return 0

    denom_mismatch = [d for d in disagreements.values() if d.denominator_mismatch]
    same_denom = [d for d in disagreements.values() if not d.denominator_mismatch]

    say(f"SKU NUMBER CONTRADICTIONS  {db.path(directory)}")
    say(f"  {len(disagreements)} SKU(s) carry two or more disagreeing stored numbers")
    say(f"  {len(denom_mismatch)} disagree on the denominator itself — unambiguous, no "
        "catalogue needed")
    say(f"  {len(same_denom)} share a denominator — need the catalogue to tell a misread "
        "from a shared SKU")

    if getattr(args, "verbose", False):
        say("")
        say("  denominator mismatches:")
        for d in denom_mismatch:
            say(f"    {d.sku}  {d.set_name!r}  {d.distinct_keys}")

    if not getattr(args, "resolve", False):
        if same_denom:
            say("")
            say(f"  {len(same_denom)} SKU(s) need `--resolve` to ask the catalogue. "
                "Without it, this command opens no socket.")
        say("")
        say(f"VERDICT: {len(disagreements)} contradiction(s) found. Never a repair — "
            "each is a review signal.")
        return 0

    market = pricehistory.Market(cache_dir=_market_cache_dir())
    outcomes = {outcome: 0 for outcome in Outcome}
    misreads = []
    for d in same_denom:
        resolution = resolve(d, market, _product_line_for_game)
        outcomes[resolution.outcome] += 1
        if resolution.outcome == Outcome.MISREAD:
            misreads.append(resolution)
        if getattr(args, "verbose", False):
            say(f"    {resolution.sku}  {resolution.outcome.value}  {resolution.detail}")

    say("")
    say("  resolved against the live catalogue, by NAME agreement (not mere existence):")
    say(f"    misread, correct number proposed: {outcomes[Outcome.MISREAD]}")
    say(f"    shared SKU, two real named products: {outcomes[Outcome.SHARED_SKU]}")
    say(f"    unresolved, no winner picked: {outcomes[Outcome.UNRESOLVED]}")
    if misreads:
        say("")
        say("  proposed corrections — never applied, a repair is a separate press:")
        for resolution in misreads:
            say(f"    {resolution.sku}  proposed {resolution.confirmed_key!r} "
                f"(misread: {', '.join(resolution.misread_keys)})")
    say("")
    say(f"VERDICT: {len(disagreements)} contradiction(s) found. Never a repair — "
        "each is a review signal.")
    return 0
