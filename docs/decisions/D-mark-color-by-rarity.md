## D-mark-color-by-rarity — The neighbour mark takes its card's rarity color

**The mark in the neighbour row wears the palette of the shown card's rarity. `app/src/kit/rarityMarks.ts` is the one home of the (game, rarity, palette) table.**

The owner ruled the mapping, and the table in `rarityMarks.ts` is the ruling. `markFor(game, rarity)` reads it. `Inventory` passes the result to `CardLocations` as `mark`, which hands it to `PlaceNeighbors`. Nothing else names a rarity's color.

**The rule.**
- **Riftbound wears its gem colors:** Common white gold, Uncommon mint, Rare rose gold, Epic orange, Showcase yellow gold. Promo is not a rung of the ladder and stays bluesteel.
- **Pokémon and One Piece are invented ladders.** Each rarity takes a palette from plainest to richest, in the order `pipeline/games.py` stacks them: bluesteel, mint, lilacish, white gold, rose gold, yellow gold, orange. The chase ranks sit on the golds and the top. One Piece's tail (TR, L, PR, DON!!) is stack order, not rank, and sits on yellow gold.
- **Orange is one new palette** (`logo.md` section 9, bracket family `amber`). `scripts/build-mark.mjs` generates it into `markPalettes.ts`. Nobody edits it by hand.
- **Bluesteel is the answer for anything the table does not name:** no game, no rarity, an unlisted rarity, a code card, `misc`. A color is never guessed.

**The rarity names are the registry's.** They are the `rarities` of `pipeline/games.py`, verbatim. The `game vocabulary` row of `make docs-audit` fails in three cases:
- A game's rarity has no line in the table.
- A line names no rarity of its game.
- A line names a palette that `markPalettes.ts` does not declare.

A rarity that the registry gains cannot go without a color.

**What the table cannot know.** `place.game` is on the wire for pooled blocks only, so the screen reads the game off the row's card. A card with a null `game` (written before the field existed) shows bluesteel. It is not read as Pokémon, because this screen has no registry default to apply.

**What would reopen this.** The owner re-orders a ladder. That is one edit to one table, and this entry changes in place.
