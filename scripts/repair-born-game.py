#!/usr/bin/env python3
"""Repair cards born with no `game`, whose bound SKU already says what game they are.

    scripts/repair-born-game.py            preview: count per derived game, 5 examples each,
                                            and every card it refuses to touch.
    scripts/repair-born-game.py --write    apply it, in one transaction under the store's lock.

THE DEFECT (owner's report F1, 2026-09-27: "there's two sets of unleashed, with the one with
99 cards having no photos"). `cli/cmd_emit.py`'s two never-seen-position birth sites
(`_stamp_single`, `_stamp_merged`) called `store/master.py:record_capture` with a `Card(...)`
that carried no `game`, although both had already resolved the row's own game a few lines
earlier to pass it to `bind_sku`'s `expected_product_line`. That gap is fixed at the cause in
`cli/cmd_emit.py` itself, so a FRESH `emit` never repeats this. This script is the one-off
repair for cards it already happened to — measured on the owner's store: 99 Riftbound
Unleashed cards in box 5 with `game IS NULL`, `identity_source='sku'`, `bound_by='join'` and a
`cid` prefixed `nophoto:`. `server/pipeline_routes.py:do_pipeline_sets` groups on
`(game, set_name)`, so they formed a second, photo-less "Unleashed" group —
`pipeline/stockimages.py:url_for` returns no photo for an empty game.

NEVER A GUESS (CLAUDE.md: "Never guess an identification, a variant, or a price"). A card
this script touches already has its identity bound (D258, "Identity follows the SKU"), so its
game is read off the `skus` table's own `product_line` and `rarity` cells through
`pipeline/games.py`'s registry — the SAME partition `pipeline/join.py:Catalog.from_export`
uses forward (a export row belongs to a game when its `Product Line` cell matches and, where
the game restricts by `product_line_rarities`, its `Rarity` cell is in that tuple), run here
in reverse. Never a second, hand-typed product-line-to-game table. A product line the
registry does not recognize, or one two games could claim without the rarity telling them
apart, REFUSES that card and names it (D21: game is a per-card claim, and a wrong one here
would misfile a card exactly as badly as the defect this repairs).

Touches only `game IS NULL` cards that carry a bound `sku`. A card that already has a game is
never in its plan at all — `Inventory.cards.where(game=None)` is an indexed query, not a
full-table scan filtered in Python. Previews by default. `--write` applies every repair
inside one `Store.write()` transaction, under `files.exclusive` (the store's existing lock,
`store/session.py:Store.write`) — an interrupted run just leaves fewer `game IS NULL` rows for
the next one to plan; nothing here is staged outside that transaction.

EVERY REPAIRED CARD LOGS ONE `game_backfilled` EVENT, through `Inventory._log` — the same
primitive `record_capture`, `bind_sku` and every other card mutation in `store/master.py`
use, so this write leaves the durable trail every other one does (`pipeline/skus.py`'s
`sku_facts_changed` is this same idea for the `skus` table). In the same transaction as the
`game` write, never a second pass. A preview logs nothing — `Store.read()` opens no
transaction to append into.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import List, NamedTuple, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline import games as games_module  # noqa: E402
from store import Store  # noqa: E402
from store.master import Card  # noqa: E402


def game_for_sku(product_line: str, rarity: str) -> Optional[str]:
    """The one registered game this SKU's `(product_line, rarity)` pair belongs to, or
    `None` when that is not knowable.

    THE INVERSE OF `pipeline/join.py:Catalog.from_export`'s OWN PARTITION, read off
    `pipeline/games.py`'s registry rather than a second table. `pokemon` and `pokemon_code`
    share one `product_line` ("Pokemon") and are told apart only by rarity, so a SPECIFIC
    match (a game whose `product_line_rarities` names this rarity) always wins over a GENERAL
    one (a game with no such restriction, which claims every row of its product line that no
    more specific game has named). Zero candidates, or more than one at the SAME
    specificity, is not knowable — the caller refuses and names it rather than guessing
    between them.
    """
    candidates = [
        key for key in games_module.keys()  # noqa: SIM118 — a module's own `keys()`, not a dict's
        if games_module.get(key)["product_line"] == product_line
    ]
    if not candidates:
        return None
    specific = [
        key for key in candidates
        if rarity in (games_module.get(key).get("product_line_rarities") or ())
    ]
    if len(specific) == 1:
        return specific[0]
    if len(specific) > 1:
        return None
    general = [
        key for key in candidates if not games_module.get(key).get("product_line_rarities")
    ]
    return general[0] if len(general) == 1 else None


class Repair(NamedTuple):
    """One card this plan would give a game — kept with the card object itself, not just its
    key, so `--write` mutates the SAME loaded row `build_plan` already read (the store's own
    write convention: mutate the attribute in place, never re-fetch)."""

    card: Card
    sku: str
    product_line: str
    rarity: str
    game: str


class Refusal(NamedTuple):
    """One `game IS NULL` card with a bound sku this plan will NOT touch, and why."""

    key: str
    sku: str
    reason: str


class Plan(NamedTuple):
    repairs: List[Repair]
    refusals: List[Refusal]

    def counts(self) -> "Counter[str]":
        return Counter(r.game for r in self.repairs)


def build_plan(snapshot) -> Plan:
    """Every `game IS NULL` card with a bound sku, sorted into a repair or a refusal.

    A card with no sku at all is neither — there is nothing here to derive a game from, and
    it was never a candidate this script could have fixed, so it is simply not iterated over.
    """
    repairs: List[Repair] = []
    refusals: List[Refusal] = []
    for card in snapshot.inventory.cards.where(game=None):
        if not card.sku:
            continue
        row = snapshot.skus.entries.get(card.sku)
        if row is None:
            refusals.append(Refusal(card.key, card.sku, f"{card.sku!r} is not in the skus table"))
            continue
        game = game_for_sku(row.product_line, row.rarity)
        if game is None:
            refusals.append(Refusal(
                card.key, card.sku,
                f"{row.product_line!r} / {row.rarity!r} maps to no registered game",
            ))
            continue
        repairs.append(Repair(card, card.sku, row.product_line, row.rarity, game))
    return Plan(repairs, refusals)


def say_plan(plan: Plan, say) -> None:
    if not plan.repairs and not plan.refusals:
        say("Nothing to repair: no card has game IS NULL with a bound sku.")
        return
    counts = plan.counts()
    say(f"{len(plan.repairs)} card(s) would get a game, across {len(counts)} game(s):")
    for game, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        say(f"  {game:<14} {n}")
        for r in [r for r in plan.repairs if r.game == game][:5]:
            say(f"    {r.card.key}  sku={r.sku}  {r.product_line!r} / {r.rarity!r}")
    if plan.refusals:
        say(f"\n{len(plan.refusals)} card(s) refused, left untouched:")
        for r in plan.refusals[:5]:
            say(f"  {r.key}  sku={r.sku}  {r.reason}")
        if len(plan.refusals) > 5:
            say(f"  ... and {len(plan.refusals) - 5} more")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--write", action="store_true", help="apply the repair. Default: preview only.")
    parser.add_argument(
        "--home", type=Path, default=None,
        help="a store directory to repair, instead of this checkout's own (PKMNSCAN_HOME-"
             "aware default). For testing — the owner runs this with no flag against theirs.",
    )
    args = parser.parse_args(argv)
    store = Store(directory=args.home) if args.home else Store()

    if not args.write:
        say_plan(build_plan(store.read()), print)
        return 0

    with store.write() as writable:
        plan = build_plan(writable)
        for repair in plan.repairs:
            repair.card.game = repair.game
            # ONE EVENT PER REPAIRED CARD, THROUGH THE STORE'S OWN LOGGING PRIMITIVE —
            # `Inventory._log`, the same one `record_capture`, `bind_sku` and `pipeline/
            # skus.py`'s own `sku_facts_changed` all go through, so this write leaves the
            # same durable trail every other card mutation does. In the SAME transaction as
            # the `game` write, never a second pass: `Store.write()` appends `writable.
            # inventory.events` to the history table on the one commit at the end, so a card
            # this repair touched and the event that says so land together or not at all.
            writable.inventory._log(
                "game_backfilled", repair.card.key, sku=repair.sku, game=repair.game,
            )
    say_plan(plan, print)
    print("\nWritten." if plan.repairs else "\nNothing written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
