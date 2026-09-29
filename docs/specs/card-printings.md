# Reaching the right printing

**Status: BUILT.** D213 (the set is a stored fact) is the governing entry. Five
parts are built. They are the name-to-printing chooser, the set and rarity columns, the matcher,
the Near Mint filter and the uncapped candidate list. The set backfill has run on the
owner's store. `./pkmnscan cards variants` is retired, and `./pkmnscan cards identity --write`
fills the set through `bind_sku`.

The problem: searching a card by name on `#/inventory` reached one printing and offered no way to
any other. Three separate causes were found and fixed in three separate pieces.

## 1. The name-to-printing level on `#/inventory`

`do_search` already returns one group per SKU, each whole. A group carries `sku`, `names`,
`number_display`, `set_hint`, `condition`, `on_hand`, `listable`, `listed` and every copy with its
photograph. Two places used to drop that. `BoxBrowse` flattened `results.groups` into a copy-level filter and a box
ranking. `CopiesPanel` asked with `skuOrName(row.card)`, which is SKU first, so once a row was
identified the sibling printings were never fetched.

A search that returns more than one group draws a chooser with one tile per printing. A tile carries
a photograph of a copy the store holds. It also carries the name, `number_display`, the set hint
where there is one, and the count on hand. A press narrows to that printing and drops into the existing copies walk. A
search that returns one group behaves as before, with no extra press. Which copies a group holds,
their order, the frozen ranking under a search (D181, D118) and the wire do not change.

## 2. Inventory facets need a stored set

- `cards` has a `set` column and a `rarity` column, both written at identification time from the
  candidate row.
- The route resolves a typed hint through `pipeline/setnames.py` before storing it. That covers the
  shutter press that skipped Enter, the CLI, and the two `set_hint` patch paths.
- Game, set and rarity are filters. Price band and listing state are deferred.
- The control is a dropdown and not chips, so it does not reshape itself per game.
- A card that cannot be classified gets its own visible bucket and is never hidden.
- A backfill from a catalog needs that catalog fetched. A game with no export in
  `inventory/.exports/` resolves nothing, and fetching one closes it.

## 3. `#/review` narrowing to the printing in front of you

Two real cases show the need. `4/383`, read as `Calm Rune`, offers five candidates that are identical
in name and number and differ only by set. Set is the only field that separates them. `4/357` offers
fifteen, three sets times five conditions. Only three rows are Near Mint, so the real choice is three
wide and was drawn fifteen wide.

- **The matcher reads set and rarity.** `_catalog_matches` folds the query through
  `join.name_index_key` and compares it with product names and numbers. A query term that matches no
  name and no number is now tested against the row's set and its rarity. A term that hits there
  filters. Typing `Spiritforged` alone finds rows.
- **The queue's candidates are filtered to Near Mint,** the way the catalog lookup already filters
  (D137). The dropped rows are conditions and never sets. No printing leaves the choice.
- **The cutoff does not hide rows.** The first nine rows are keyboard-reachable because the digits
  answer, and a row past the ninth is a mouse-only press. That is a fact about ten keys and never a
  reason to drop a row from the wire.
  - `pipeline/join.py:rank_by_claims` (D23's amendment) is a fourth job for the rarity claim. It
    puts every claim-agreeing row in front of the rest, before any cutoff.
  - `server/capture_server.py:do_review_catalog` sends every match up to `CATALOG_EGREGIOUS_LIMIT`,
    which is 200. The widest real group for one folded name measured 16 (`Calm Rune`).
    `found` and `truncated` state the true total and whether the ceiling bit. The ceiling is a
    generous bound and not a fitted one. Re-measure it the day a real query reaches it.
  - `MAX_KEYED_CANDIDATES` stays 9. `app/src/ReviewQueue.tsx`'s `CatalogPanel` reveals ten more rows
    per press of "Show N more". Those rows are already on the wire, so no press fetches again. A
    press adds rows below and moves nothing above it (D118).
- **`4/383` shows why.** A bare `Calm Rune` query finds all 16 rows, and the card's claimed rarity
  (`Showcase`) is on the capture record and not in the query. Before the change, the wire cut at
  nine and the three Showcase rows sat in the tail. Now all 16 return, and the rows that agree with
  the rarity claim rank first and keep a digit.

An entry written before this change keeps its old, unranked suggestions until
`pkmnscan queue refresh --write` runs over it (D167's mechanism). That press is a one-time step over
the live store, on the owner's word.
