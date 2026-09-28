#!/usr/bin/env python3
"""`scripts/repair-born-game.py` proved against a throwaway store (the F1 defect's own
repair). NULL-game cards with a bound sku get the right game, a card that already has a game
is left alone, a card whose sku maps to no registered game is refused and named, and the
preview writes nothing. In `make check` and never in the git hook: it writes, into a
directory it creates and destroys (D18).
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from store import files  # noqa: E402
from store.master import Card, position_key  # noqa: E402
from store.session import Store  # noqa: E402
from store.skus import SkuRow  # noqa: E402

PASS = 0
FAIL = 0


def ok(condition: bool, label: str, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok     {label}")
    else:
        FAIL += 1
        print(f"  FAIL   {label}")
        if detail:
            for line in str(detail).splitlines()[:8]:
                print(f"         {line}")


def _load_repair_module():
    """`repair-born-game.py` has a hyphen, so it is loaded by path rather than imported."""
    spec = importlib.util.spec_from_file_location(
        "_repair_born_game", ROOT / "scripts" / "repair-born-game.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sku_row(product_line: str, rarity: str, source: str = "20260101-000000_pokemon.csv") -> SkuRow:
    return SkuRow(
        product_line=product_line, set_name="Set", product_name="Card", number="1/1",
        rarity=rarity, condition="Near Mint", grade="Near Mint", printing=None,
        first_seen=1, last_seen=1, source=source, raw={},
    )


def main() -> int:
    print("repair-born-game self-test — F1's own repair, against a throwaway store\n")
    repair = _load_repair_module()

    # --------------------------------------------------- game_for_sku, unit level
    print("  -- game_for_sku: the registry's forward partition, read in reverse --")
    ok(repair.game_for_sku("Riftbound League of Legends Trading Card Game", "Common") == "riftbound",
       "a product line only one game claims resolves outright")
    ok(repair.game_for_sku("One Piece Card Game", "Rare") == "one_piece",
       "same, for one_piece")
    ok(repair.game_for_sku("Pokemon", "Rare Holo") == "pokemon",
       "Pokemon's shared product line falls to the GENERAL claimant off a rarity no "
       "restricted game names")
    ok(repair.game_for_sku("Pokemon", "Code Card") == "pokemon_code",
       "the SPECIFIC claimant (product_line_rarities) wins over the general one")
    ok(repair.game_for_sku("Nonsense Trading Card Game", "Common") is None,
       "a product line no registered game claims is not knowable")

    with tempfile.TemporaryDirectory() as raw:
        home = Path(raw)
        (home / "inventory").mkdir(parents=True, exist_ok=True)
        previous = os.environ.get(files.HOME_ENV)
        os.environ[files.HOME_ENV] = str(home)
        try:
            # ---------------------------------------------- the fixture store
            with Store().write() as writable:
                # A NULL-game card with a bound sku that resolves — the F1 shape itself.
                writable.inventory.cards[position_key(5, 1)] = Card(
                    box=5, index=1, sku="RIFT1", cid="riftbound-1",
                    identity_source="sku", bound_by="join",
                )
                writable.skus.entries["RIFT1"] = _sku_row(
                    "Riftbound League of Legends Trading Card Game", "Common",
                )
                # A card that ALREADY has a game — must never be touched or even planned.
                writable.inventory.cards[position_key(1, 1)] = Card(
                    box=1, index=1, sku="POKE1", cid="pokemon-1", game="pokemon",
                )
                writable.skus.entries["POKE1"] = _sku_row("Pokemon", "Rare")
                # A NULL-game card whose sku maps to no registered game — must refuse.
                writable.inventory.cards[position_key(9, 1)] = Card(
                    box=9, index=1, sku="MYST1", cid="mystery-1",
                )
                writable.skus.entries["MYST1"] = _sku_row("Magic: The Gathering", "Mythic")
                # A NULL-game card with a sku THIS STORE HAS NEVER SEEN — must refuse.
                writable.inventory.cards[position_key(9, 2)] = Card(
                    box=9, index=2, sku="GHOST1", cid="ghost-1",
                )
                # A NULL-game card with NO sku at all — not this script's candidate.
                writable.inventory.cards[position_key(9, 3)] = Card(
                    box=9, index=3, cid="nosku-1",
                )

            # ---------------------------------------------- build_plan, on a lock-free read
            print("\n  -- build_plan --")
            plan = repair.build_plan(Store().read())
            planned_keys = {r.card.key for r in plan.repairs}
            ok(position_key(5, 1) in planned_keys,
               "the resolvable NULL-game card is planned", str(planned_keys))
            ok(position_key(1, 1) not in planned_keys,
               "the card that already has a game is never planned")
            ok(position_key(9, 3) not in planned_keys,
               "the card with no sku is never planned (not a candidate, not a refusal)")
            ok(len(plan.repairs) == 1, "exactly one repair", str(plan.repairs))
            ok(plan.repairs[0].game == "riftbound", "and it derives riftbound",
               plan.repairs[0].game)

            refused_keys = {r.key for r in plan.refusals}
            ok(refused_keys == {position_key(9, 1), position_key(9, 2)},
               "both the unmapped-product-line card and the unknown-sku card are refused, "
               "named, and nothing else is", str(refused_keys))

            # ---------------------------------------------- preview writes nothing
            print("\n  -- preview (no --write) --")
            before = {k: v.game for k, v in dict(Store().read().inventory.cards).items()}
            exit_code = repair.main(["--home", str(home / "inventory")])
            after = {k: v.game for k, v in dict(Store().read().inventory.cards).items()}
            ok(exit_code == 0, "preview exits 0")
            ok(before == after, "preview writes nothing at all", str((before, after)))

            # ---------------------------------------------- --write applies exactly the plan
            print("\n  -- --write --")
            exit_code = repair.main(["--home", str(home / "inventory"), "--write"])
            ok(exit_code == 0, "--write exits 0")
            reloaded = Store().read().inventory.cards
            ok(reloaded[position_key(5, 1)].game == "riftbound",
               "the resolvable card now carries its derived game")
            ok(reloaded[position_key(1, 1)].game == "pokemon",
               "the already-gamed card is untouched")
            ok(reloaded[position_key(9, 1)].game is None,
               "the unmapped-product-line card is still untouched (refused, not guessed)")
            ok(reloaded[position_key(9, 2)].game is None,
               "the unknown-sku card is still untouched")
            ok(reloaded[position_key(9, 3)].game is None,
               "the no-sku card is still untouched")

            # A second --write over an already-repaired store has nothing left to plan.
            print("\n  -- a second --write finds nothing left --")
            plan_again = repair.build_plan(Store().read())
            ok(not plan_again.repairs and len(plan_again.refusals) == 2,
               "the two refusals persist (still unrepairable) and nothing else is replanned",
               str(plan_again))
        finally:
            if previous is None:
                os.environ.pop(files.HOME_ENV, None)
            else:
                os.environ[files.HOME_ENV] = previous

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
