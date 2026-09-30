# Reaching the right printing

**Status: BUILT.** D213 (the set is a stored fact) is the governing entry. Five parts are
built. They are the name-to-printing chooser, the set and rarity columns, the matcher, the
Near Mint filter and the uncapped candidate list. `./pkmnscan cards variants` is retired.
`./pkmnscan cards identity --write` fills the set through `bind_sku`
(`docs/specs/identity-follows-sku.md`).

A search by name on `#/inventory` reaches every printing of the card. `#/review` narrows to the
printing in front of you.

## 1. The name-to-printing level on `#/inventory`

`do_search` returns one group per SKU, each whole. A group carries `sku`, `names`,
`number_display`, `set_hint`, `condition`, `on_hand`, `listable`, `listed` and every copy with
its photograph. `BoxBrowse` reads `results.groups` at group level. The copies panel must not ask
by SKU first, or the sibling printings are never fetched.

A search that returns more than one group draws a chooser (`VariantChooser` in
`app/src/BoxBrowse.tsx`) with one tile per printing. A tile carries a photograph of a copy that
the store holds. It also carries the name, `number_display`, the set hint where there is one,
and the count on hand. A press narrows to that printing and drops into the existing copies
walk. A search that returns one group behaves as before, with no extra press. These do not
change: which copies a group holds, their order, the frozen ranking under a search (D181, D118)
and the wire.

## 2. Inventory facets need a stored set

- `cards` has a `set_name` column and a `rarity` column. Both are written when the card is bound to
  a SKU, from the catalog row.
- The route resolves a typed hint through `pipeline/setnames.py` before storing it. That covers
  the shutter press that skipped Enter, the CLI and the two `set_hint` patch paths.
- Game, set and rarity are filters. Price band and listing state are deferred.
- The control is a dropdown, not chips, so it does not reshape itself per game.
- A card that cannot be classified gets its own visible bucket. It is never hidden.
- A backfill from a catalog needs that catalog fetched. A game with no export in
  `inventory/.exports/` resolves nothing, and fetching one closes the gap.

## 3. `#/review` narrows to the printing in front of you

Some queue entries offer candidates that are identical in name and number and differ only by
set. Set is then the only field that separates them. Others offer one row per condition of each
set, so the real choice is a third as wide as the list that was drawn.

- **The matcher reads set and rarity.** `_catalog_matches` folds the query through
  `join.name_index_key` and compares it with product names and numbers. A query term that
  matches no name and no number is tested against the row's set and its rarity. A term that hits
  there filters. Typing a set name alone finds rows.
- **The queue's candidates are filtered to Near Mint,** the way the catalog lookup filters
  (D137). The dropped rows are conditions and never sets. No printing leaves the choice.
- **The cutoff does not hide rows.** The digits answer the first nine rows, so only those are
  keyboard-reachable. A row past the ninth is a mouse-only press. That is a fact about ten keys.
  It is never a reason to drop a row from the wire.
  - `pipeline/join.rank_by_claims` (D23's amendment) is a fourth job for the rarity claim. It
    puts every claim-agreeing row in front of the rest, before any cutoff.
  - `server/capture_server.do_review_catalog` sends every match up to
    `CATALOG_EGREGIOUS_LIMIT`, which is 200. `found` and `truncated` state the true total and
    whether the ceiling bit. The ceiling is a generous bound, not a fitted one. Re-measure it the
    day a real query reaches it.
  - `MAX_KEYED_CANDIDATES` in `app/src/ReviewQueue.tsx` is 9. `CatalogPanel` reveals
    `CATALOG_REVEAL_STEP` (10) more rows per press of "Show N more". Those rows are already on
    the wire, so no press fetches again. A press adds rows below and moves nothing above it
    (D118).
- **The rarity claim ranks its rows first.** A bare name query finds every printing. The card's
  claimed rarity is on the capture record and not in the query. Without the ranking, the rows
  that agree with the claim could sit in the tail past the cutoff. Now they rank first and keep
  a digit.

A queue entry that predates the ranking keeps its old, unranked suggestions until
`pkmnscan queue refresh --write` runs over it (D167's mechanism).
