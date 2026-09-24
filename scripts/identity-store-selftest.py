#!/usr/bin/env python3
"""`Inventory.bind_sku`/`unbind_sku` — THE ONE WRITER (docs/specs/identity-follows-sku.md
§4.1, lane 1) — and `record_identification`'s narrowed write, proved in memory.

WHAT THIS PROVES. `bind_sku` stamps `name`/`number`/`printed_total`/`rarity`/`set_name`/
`condition` off a `skus` table row (store/skus.py, lane 0 — never an export file) for a
Pokemon card (the catalog `Number` cell split into numerator/denominator), a Riftbound card
(the cell kept verbatim), and a Riftbound double-sided token cell (`T02 // T03`, which has no
`/` a splitter could misread as one). `unbind_sku` round-trips a rebind back to the first
binding, every field but `bound_at` restored exactly (`bound_at` is a fresh stamp on purpose
— see `unbind_sku`'s own docstring). `SkuUnknown` and `GameMismatch` both refuse before
touching the card, the events list, or the `skus` table. `record_identification` writes only
`read_name`/`read_number`/`read_printed_total` on a card `bind_sku` has bound, and still
writes the identity too on a card that has never been bound — the read-side continuity §4.2
requires.

NO SQLITE ANYWHERE HERE. `bind_sku`/`unbind_sku`/`record_identification` are pure methods
over `Inventory`'s in-memory mapping and a `Skus` table built the same way — `store/skus.py`'s
own `Skus(entries=Rows(Skus.ENTRIES, objects={...}))`, no `Store`, no `mktemp`, no
`PKMNSCAN_HOME`. This lane changes no data on disk (§11's own line: "no (code only; lane 2's
press writes the data)"), so nothing here should either.

`number`/`printed_total` come from `pipeline/join.catalog_number_fields`, called HERE and
handed to `bind_sku` as a parameter — never re-derived inside `store/master.py`, which cannot
import `pipeline/` at all (D63). This script is not `store/`, so it is free to import
`pipeline.join` the way every real future caller (lane 2's press, lane 3a's routes, lane 3b's
CLI writers) will.

Every arm is a MEASUREMENT or a REFUSAL, never a restatement of the code, `scripts/
skus-selftest.py`'s own rule. In `make check` and never in the git hook: it writes nothing to
disk at all (D18 does not even apply).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import games  # noqa: E402
from pipeline.join import catalog_number_fields  # noqa: E402
from pipeline.skus import row_from_csv  # noqa: E402
from store import master  # noqa: E402
from store.master import Card, GameMismatch, Inventory, SkuUnknown  # noqa: E402
from store.skus import Skus  # noqa: E402

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


# ------------------------------------------------------------------------------ the fixtures


def export_row(
    sku: str,
    *,
    product_line: str,
    set_name: str,
    product_name: str,
    number: str,
    rarity: str = "Common",
    condition: str = "Near Mint",
) -> dict:
    """One `tcgcsv.CANONICAL_HEADER`-shaped row, the six fact cells `pipeline/
    skus.row_from_csv` reads plus the rest of the columns it ignores — `scripts/
    skus-selftest.py:export_row`'s own convention, narrowed to what this script needs."""
    return {
        "TCGplayer Id": sku,
        "Product Line": product_line,
        "Set Name": set_name,
        "Product Name": product_name,
        "Title": "",
        "Number": number,
        "Rarity": rarity,
        "Condition": condition,
        "TCG Market Price": "1.00",
        "TCG Direct Low": "",
        "TCG Low Price With Shipping": "",
        "TCG Low Price": "1.00",
        "Total Quantity": "0",
        "Add to Quantity": "",
        "TCG Marketplace Price": "",
    }


def skus_with(*rows) -> Skus:
    """A `Skus` table holding exactly these export rows, `pipeline/skus.row_from_csv` doing
    the same CSV-cell -> `SkuRow` fold the real fill (`pipeline/skus.py:fill`) uses — no
    second copy of that rule either."""
    table = Skus()
    for row in rows:
        parsed = row_from_csv(row, at=1, source="test-fixture.csv")
        assert parsed is not None, row
        sku, sku_row = parsed
        table.fold(sku, sku_row)
    return table


def number_fields(game: str, raw_number: str):
    """`catalog_number_fields`, called here and handed to `bind_sku` — §4.1's own contract,
    restated by this script's module docstring."""
    return catalog_number_fields(game, raw_number)


def product_line_of(game: str) -> Optional[str]:
    return games.get(game)["product_line"]


def new_card(key_suffix: int, *, game: str, cid: Optional[str] = None) -> Inventory:
    """One fresh `Inventory` holding one captured card at `1/<key_suffix>`, isolated per
    case so no arm can see another arm's write."""
    inventory = Inventory()
    inventory.cards[f"1/{key_suffix}"] = Card(
        box=1, index=key_suffix, game=game,
        cid=cid or f"cid-{key_suffix}",
        state=master.IDENTIFIED,
    )
    return inventory


# ------------------------------------------------------------------------------------- main


def main() -> int:
    print("identity-store self-test (docs/specs/identity-follows-sku.md §4.1, lane 1)\n")

    # ---------------------------------------------------------- case 1: a Pokemon card
    pokemon_row = export_row(
        "8001", product_line="Pokemon", set_name="Scarlet & Violet",
        product_name="Stufful - 111/132", number="024/132", rarity="Uncommon",
    )
    skus = skus_with(pokemon_row)
    inv = new_card(1, game="pokemon")
    number, printed_total = number_fields("pokemon", "024/132")
    card = inv.bind_sku(
        "1/1", "8001", bound_by="answer", skus=skus,
        number=number, printed_total=printed_total,
        expected_product_line=product_line_of("pokemon"),
    )
    ok(card is not None, "bind_sku returns the bound card (Pokemon)")
    ok(card.sku == "8001", "sku stamped", card.sku)
    ok(card.name == "Stufful", "name composed off product_name, suffix dropped", card.name)
    ok((card.number, card.printed_total) == ("024", "132"),
       "number/printed_total split off the catalog cell",
       f"{card.number!r}/{card.printed_total!r}")
    ok(card.rarity == "Uncommon" and card.set_name == "Scarlet & Violet"
       and card.condition == "Near Mint",
       "rarity/set_name/condition verbatim off the row's own cells")
    ok(card.bound_by == "answer" and card.identity_source == master.IDENTITY_SKU,
       "bound_by and identity_source stamped")
    ok(card.bound_at is not None, "bound_at stamped")
    ok(len(inv.events) == 1 and inv.events[0]["event"] == "sku_bound",
       "one sku_bound history event", inv.events)
    ok(inv.events[0].get("restores_to") == {"sku": None, "bound_by": None},
       "restores_to names the (empty) previous binding", inv.events[0].get("restores_to"))

    # ------------------------------------------------------ case 2: Riftbound, verbatim
    rift_row = export_row(
        "9001", product_line="Riftbound League of Legends Trading Card Game",
        set_name="Origins", product_name="Baccai Sandspinner", number="001/166",
        rarity="Common",
    )
    skus2 = skus_with(rift_row)
    inv2 = new_card(2, game="riftbound")
    number2, printed_total2 = number_fields("riftbound", "001/166")
    card2 = inv2.bind_sku(
        "1/2", "9001", bound_by="join", skus=skus2,
        number=number2, printed_total=printed_total2,
        expected_product_line=product_line_of("riftbound"),
    )
    ok((card2.number, card2.printed_total) == ("001/166", None),
        "Riftbound number kept verbatim, printed_total empty",
        f"{card2.number!r}/{card2.printed_total!r}")
    ok(card2.name == "Baccai Sandspinner", "Riftbound name, no suffix to drop", card2.name)

    # --------------------------------------------- case 3: Riftbound double-sided token
    token_row = export_row(
        "9002", product_line="Riftbound League of Legends Trading Card Game",
        set_name="Riftbound Organized Play Promotional Cards", product_name="Bird // Buff",
        number="T02 // T03", rarity="Promo",
    )
    skus3 = skus_with(token_row)
    inv3 = new_card(3, game="riftbound")
    number3, printed_total3 = number_fields("riftbound", "T02 // T03")
    card3 = inv3.bind_sku(
        "1/3", "9002", bound_by="group_answer", skus=skus3,
        number=number3, printed_total=printed_total3,
        expected_product_line=product_line_of("riftbound"),
    )
    ok((card3.number, card3.printed_total) == ("T02 // T03", None),
        "the double-sided token cell survives whole — no `/`-split misfires on it",
        f"{card3.number!r}/{card3.printed_total!r}")
    ok(card3.name == "Bird // Buff", "token card's name", card3.name)

    # --------------------------------------------------------- case 4: sku_unknown, refuses
    inv4 = new_card(4, game="pokemon")
    before = dict(inv4.cards["1/4"].__dict__)
    threw = False
    try:
        inv4.bind_sku(
            "1/4", "no-such-sku", bound_by="answer", skus=skus,
            number="1", printed_total="1",
        )
    except SkuUnknown:
        threw = True
    ok(threw, "bind_sku raises SkuUnknown for a SKU absent from the table")
    ok(inv4.cards["1/4"].__dict__ == before, "and the card is unchanged", inv4.cards["1/4"])
    ok(inv4.events == [], "and no history event was appended", inv4.events)

    # -------------------------------------------------------- case 5: game_mismatch, refuses
    inv5 = new_card(5, game="pokemon")  # claims Pokemon; skus2's row is Riftbound
    before5 = dict(inv5.cards["1/5"].__dict__)
    threw5 = False
    try:
        inv5.bind_sku(
            "1/5", "9001", bound_by="answer", skus=skus2,
            number="1", printed_total=None,
            expected_product_line=product_line_of("pokemon"),
        )
    except GameMismatch:
        threw5 = True
    ok(threw5, "bind_sku raises GameMismatch for a row whose product_line disagrees")
    ok(inv5.cards["1/5"].__dict__ == before5, "and the card is unchanged", inv5.cards["1/5"])
    ok(inv5.events == [], "and no history event was appended", inv5.events)

    # ------------------------------------------------- case 5b: no claim, no mismatch
    inv5b = new_card(50, game="misc")  # `misc`'s product_line is None — no claim to violate
    card5b = inv5b.bind_sku(
        "1/50", "9001", bound_by="answer", skus=skus2,
        number=number2, printed_total=printed_total2,
        expected_product_line=product_line_of("misc"),
    )
    ok(card5b is not None, "a falsy expected_product_line (misc) never refuses")

    # ------------------------------------------------ case 6: bound_by outside the vocabulary
    inv6 = new_card(6, game="pokemon")
    threw6 = False
    try:
        inv6.bind_sku(
            "1/6", "8001", bound_by="typo_act", skus=skus,
            number="1", printed_total="1",
        )
    except master.UnknownBoundBy:
        threw6 = True
    ok(threw6, "bind_sku raises UnknownBoundBy for an act outside BOUND_BY_ACTS")

    # ----------------------------------------------------- case 7: the undo round trip
    inv7 = new_card(7, game="pokemon")
    first = inv7.bind_sku(
        "1/7", "8001", bound_by="answer", skus=skus,
        number="024", printed_total="132", read_disputes=True,
    )
    snapshot_after_first = {
        k: v for k, v in dict(first.__dict__).items() if k != "bound_at"
    }
    second_row = export_row(
        "8002", product_line="Pokemon", set_name="Scarlet & Violet",
        product_name="Pikachu", number="025/132", rarity="Common",
    )
    skus7 = skus_with(pokemon_row, second_row)
    second = inv7.bind_sku(
        "1/7", "8002", bound_by="correction", skus=skus7,
        number="025", printed_total="132", read_disputes=False,
    )
    ok(second.sku == "8002" and second.name == "Pikachu",
       "the rebind overwrote the identity", (second.sku, second.name))
    restores_to = inv7.events[-1]["restores_to"]
    ok(restores_to == {"sku": "8001", "bound_by": "answer"},
       "the rebind's own history line names the FIRST binding to restore to", restores_to)
    restored = inv7.unbind_sku(
        "1/7", skus=skus7, sku=restores_to["sku"], bound_by=restores_to["bound_by"],
        number="024", printed_total="132", read_disputes=True,
    )
    restored_fields = {
        k: v for k, v in dict(restored.__dict__).items() if k != "bound_at"
    }
    ok(restored_fields == snapshot_after_first,
       "unbind_sku round-trips every field but bound_at back to the first binding",
       f"restored={restored_fields}\nfirst   ={snapshot_after_first}")
    ok(restored.bound_at is not None and restored.bound_at >= first.bound_at,
       "bound_at is a fresh stamp, not the original moment", restored.bound_at)

    # ------------------------------------------------- case 8: unbind to no binding at all
    inv8 = new_card(8, game="pokemon")
    inv8.bind_sku(
        "1/8", "8001", bound_by="answer", skus=skus,
        number="024", printed_total="132",
    )
    cleared = inv8.unbind_sku("1/8", skus=skus, sku=None, bound_by=None)
    ok(cleared.sku is None and cleared.identity_source == master.IDENTITY_READ,
       "unbind_sku(sku=None) clears back to identity_source = read")
    ok(cleared.condition is None and cleared.set_name is None and cleared.rarity is None,
       "and clears condition/set_name/rarity with it")
    ok((cleared.name, cleared.number, cleared.printed_total)
       == (cleared.read_name, cleared.read_number, cleared.read_printed_total),
       "and the identity fields fall back to the evidence fields")

    # --------------------------------------------- case 9: record_identification, unbound
    inv9 = Inventory()
    inv9.cards["1/9"] = Card(box=1, index=9, game="pokemon", cid="cid-9", state=master.CAPTURED)
    inv9.record_identification(
        "1/9", name="Pikachu", number="025", printed_total="132", confidence="high",
    )
    card9 = inv9.cards["1/9"]
    ok((card9.read_name, card9.read_number, card9.read_printed_total)
       == ("Pikachu", "025", "132"), "record_identification writes the evidence fields")
    ok((card9.name, card9.number, card9.printed_total) == ("Pikachu", "025", "132"),
       "and the identity too, on a card with no active binding")
    ok(card9.state == master.IDENTIFIED, "and the captured card advances to identified")

    # -------------------------------------------- case 10: record_identification, bound
    inv10 = new_card(10, game="pokemon")
    inv10.bind_sku(
        "1/10", "8001", bound_by="answer", skus=skus,
        number="024", printed_total="132",
    )
    bound_before = dict(inv10.cards["1/10"].__dict__)
    inv10.record_identification(
        "1/10", name="Something Else Entirely", number="999", printed_total="999",
        confidence="low", read_disputes=True,
    )
    card10 = inv10.cards["1/10"]
    ok((card10.read_name, card10.read_number, card10.read_printed_total)
       == ("Something Else Entirely", "999", "999"),
       "record_identification still writes the evidence fields on a bound card")
    ok((card10.name, card10.number, card10.printed_total)
       == (bound_before["name"], bound_before["number"], bound_before["printed_total"]),
       "and leaves the SKU-derived identity untouched",
       (card10.name, bound_before["name"]))
    ok(card10.sku == bound_before["sku"] and card10.identity_source == master.IDENTITY_SKU,
       "the binding itself is untouched")
    ok(card10.read_disputes is True, "read_disputes is the caller's own answer, written")

    print("\nidentity-store self-test: {0} passed{1}".format(
        PASS, ", {0} FAILED".format(FAIL) if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
