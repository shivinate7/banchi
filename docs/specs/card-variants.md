# Reaching the right printing

**Status, 2026-09-17.** Sections 1, 2, 3a and 3b are BUILT. Section 3c is MEASURED and needs no
build. The governing entry is D213.

**The backfill ran against the owner's store, at some point after the 2026-09-17
measurement.** A read-only query found 0 of 3,502 SKU-bound cards with a null `set_name` or
`rarity`. It found no `sku_bound`, `sku_held` or `identity_migration_*` events. `./pkmnscan
cards variants` is retired. `./pkmnscan cards identity --write` fills the set now, through
`bind_sku` (D213, amended). The old measurement over the real store: 2,960 of 3,502 cards
would gain a set.

The owner's report: searching a card by name on `#/inventory` reaches one printing and offers no way
to any other. The only move is to click around boxes until a copy of a different printing falls
under the hand. Three separate causes were found. They are fixed in three separate pieces.

## 1. The name-to-printing level is missing on `#/inventory`

**The server already answers this.** `do_search` returns one group per SKU, each group whole, with
`sku`, `names`, `number_display`, `set_hint`, `condition`, `on_hand`, `listable`, `listed` and every
copy with its photograph. No wire change is needed.

**Two places drop it.** `BoxBrowse` flattens `results.groups` into a copy-level filter and a box
ranking, so the grouping is discarded. `CopiesPanel` asks with `skuOrName(row.card)`, which is SKU
first, so once a row is identified the sibling printings are never fetched. It then keeps the one
group holding the current row and drops the rest.

**What is built.** A search returning more than one group draws a chooser. There is one tile per
printing. A tile carries a photograph of a copy the store holds. Beside it are the name,
`number_display`, the set hint where there is one, and the count on hand. A press narrows to that
printing. It then drops into the existing copies walk unchanged. A search returning one group
behaves exactly as it does today, with no extra press.

**What does not change.** Which copies a group holds, and their order. The frozen ranking under a
search (D181, D118). The wire.

## 2. Inventory has no facets, because the store has no set

Covered in full by the decision entry. In short:

- `cards` gains a `set` column and a `rarity` column, both written at identification time out of the
  candidate row, both backfilled once.
- The route resolves a typed hint through `pipeline/setnames.py` before storing it. That covers the
  shutter press that skipped Enter, the CLI, and the two `set_hint` patch paths.
- The 99 `UNL` rows from 2026-08-29 are swept in the same migration.
- Game, set and rarity become filters. Price band and listing state are deferred.
- The control is a dropdown, not chips, so it does not reshape itself per game.
- A card that cannot be classified gets its own visible bucket and is never hidden.

**Backfill coverage, measured 2026-09-17.** Riftbound resolves 2,960 of 2,960. Pokemon resolves 0 of
542. No Pokemon export has ever been fetched into `inventory/.exports/`. Fetching one closes it. All
543 Pokemon cards carry `set_hint = 'ME01'`, one set, which is the fallback.

## 3. `#/review` cannot be narrowed to the printing in front of you

Found by reproducing the owner's own case on the real store, read-only.

**`4/383`**, read as `Calm Rune` / `R02`, offers five candidates. They are identical in name and
number. They differ only by set: Spiritforged, Unleashed twice, Vendetta twice. **Set is the only
field that separates them.**

**`4/357`** offers fifteen. Three sets times five conditions. Only three rows are Near Mint, one per
set. **The real choice is three wide and is drawn fifteen wide.**

### 3a. The matcher cannot see a set or a rarity

`_catalog_matches` folds the query through `join.name_index_key` and compares it to product names
and numbers only. It never reads `Set Name` or `Rarity`, although both columns sit in the row it is
ranking. So typing a set word narrows nothing. Typing `Spiritforged` alone returns nothing at all,
because no product name answers to it. The owner reported exactly this: neither `Calm Rune` nor
`Calm Rune (Alternate Art)` reaches the right row.

**Fix.** A query term that matches no name and no number is tested against the row's set and its
rarity. A term that hits there filters rather than being ignored.

### 3b. The queue's candidates are not filtered to Near Mint

The catalogue lookup filters to Near Mint by rule (D137). The queue's own candidate rows do not. So
twelve rows nobody would ever pick sit in the list, and they consume the nine digit slots.

**Fix.** The queue's candidates are filtered the same way the catalogue lookup already filters. The
rows that are dropped are conditions, never sets, so no printing is ever removed from the choice.

### 3c. Nine rows is a keyboard limit presented as an answer

`CATALOG_LOOKUP_LIMIT` is 9 because the digits answer. With fifteen candidates, rows ten to fifteen
cannot be reached by any press. Every Vendetta row in `4/357` is in that tail.

**Fix.** 3a and 3b are expected to make the cut unreachable in practice, because the choice narrows
below nine before the cut applies. The cap itself is not raised. If a real case still exceeds nine
rows after both land, it is a narrowing control and not more digits. That case is not built on
speculation.

**Ordering.** 3b first. It is the smallest change and it alone takes `4/357` from fifteen rows to
three. 3a second. 3c is measured after both, and may turn out to be nothing.


### 3c amendment, 2026-09-24 — the real case exceeded nine, and the cap moved

3a and 3b landed. They were not enough for `4/383`. A bare `Calm Rune` query still finds all
sixteen of that name's rows. The card's claimed rarity, `Showcase`, is not typed into the query.
It lives on the capture record. 3a's set and rarity words narrow nothing here. This is not a
defect in 3a or 3b. It is the case 3c named and declined to build ahead of. That case is now
measured.

The owner's ruling on the cutoff itself, 2026-09-24, quoted verbatim:

```
the search shouldn't cut off i should see all rows that matched unless it's an egregious
amount no? or a 'show 10 more' etc
```

**The fix, over two doors.** `pipeline/join.py:rank_by_claims` is D23's own amendment. It is a
fourth job the rarity claim now does. It puts every claim-agreeing row in front of the rest.
It runs before any cutoff.

`server/capture_server.py:do_review_catalog` stops cutting the wire response at nine. It now
sends every match up to `CATALOG_EGREGIOUS_LIMIT`. That ceiling is 200. It is measured against
the widest real group this game's catalogue holds for one folded name: 16, `Calm Rune` itself.
`found` and `truncated` still say the true total. They say whether that ceiling ever bit.

`MAX_KEYED_CANDIDATES` stays 9. A row past the ninth is still a mouse-only press. That is a fact
about ten fingers and ten keys. It is never a reason to drop a row on the wire.
`app/src/ReviewQueue.tsx`'s `CatalogPanel` reveals ten more rows per press of "Show N more".
Those rows are already on the wire. No press fetches a second time. D118 holds: a press adds
rows below and moves nothing above it.

**`4/383`, before and after.** `GET /review/4/383/catalog?q=Calm%20Rune` found 16 rows before
this fix. It returned 9, in catalog order. The three `Calm Rune (R02a)` Showcase rows sat in the
tail. Spiritforged was among them, SKU `9139842`. Past the ninth row, no digit could reach them.

After this fix the same query still finds 16. It now returns all 16 on the wire. The card's own
rarity claim agrees with the Showcase rows, so they rank first. All three keep a digit.
`truncated` reads false. 16 sits under the 200-row ceiling.

No egregious case has been measured yet. `CATALOG_EGREGIOUS_LIMIT` is a generous bound, not a
fitted one. Re-measure it the day a real query reaches it.

An entry written before this change keeps its old, unranked suggestions until
`pkmnscan queue refresh --write` runs over it. That press is D167's own mechanism, unchanged.
It is a one-time step over the live store, on the owner's word, not part of this change.
