## D213 — The set is a stored fact

**AMENDED, WIDENED (`D258`).** This entry's rule covered `set_name` and `rarity`. It now covers `name`, `number` and `condition` too. Measured: 64 cards draw a name their own listing disputes, and 241 draw a number. The old premise was wrong. `name` and `number` stayed "what the model read" even after a SKU bound. They now write at bind time, from the SKU table, as `set_name` and `rarity` already did. The source moves from an export file to that table. A row outlives its export. "The hint was never a fact" generalizes: the read was never one either. The backfill press this entry built, `cards variants`, is retired. It wrote `set_name` and `rarity` outside the one writer. `cards identity --write` now fills both through `bind_sku`, from the SKU table. The old command prints one line, writes nothing, and exits 2.

**Origin.** The owner reported on `#/inventory` that searching `Mind Rune` or `Calm Rune` lands on one SKU. No move reaches a sibling printing. The only way is to click around boxes until a copy of another printing turns up. The owner's words: *"the inventory shows me the most of whatever SKU first and I have to pick around the boxes to find maybe the right SKU."* The owner widened the ask to a per-set view within a game, such as Spiritforged inside Riftbound.

This entry settles where a card's set and rarity live. The name-to-printing navigation is in `docs/specs/card-printings.md`.

### The store has never held a set

The owner expected identified cards to carry accurate set data. They do not. Measured against `inventory/store.sqlite`:

`cards` has `key, box, idx, state, sku, condition, capture_id, name, number, game, set_hint, run, captured_at, state_at, payload, cid, number_key, number_display`. **There is no set column.** The `payload` blob has no set either. All five `Calm Rune` records carry `set_hint = NULL`.

So identification never wrote the set down, though the answering row carried one. A queue candidate is `{"condition", "market", "name", "number", "rarity", "set", "sku"}`. The operator had the set in hand at the answer, and it was dropped.

### The hint normalizes, so normalization is not why it cannot be the source

An earlier draft said a facet built on `set_hint` would split one drawer in two. It cited 790 Riftbound cards that say `Unleashed` and 99 that say `UNL`. **That claim was wrong, and the owner caught it.** `pipeline/setnames.py:resolve` already folds both to one set. Every distinct Riftbound value on the owner's hints resolves:

| hint | cards | resolves to |
|---|---|---|
| `Origins` | 303 | Origins |
| `Spiritforged` | 680 | Spiritforged |
| `UNL` | 99 | Unleashed |
| `Unleashed` | 790 | Unleashed |
| `Vendetta` | 395 | Vendetta |

The real reason is coverage and authority. **700 Riftbound cards carry no hint.** 698 of them carry a SKU. A hint is a claim the operator types at the shutter. It can be absent, and it can be wrong. A SKU resolves for every card that has one. So the hint is the fallback, and the SKU is the source.

This keeps two distinctions. D145 separates a box label from a box identity. D36 separates what the model read from where the card is. The hint is evidence about its own card. The set is a fact about the product.

### The capture screen completes the hint, and the 99 rows predate it

The owner asked why `UNL` was ever stored, expecting the field to rewrite it. It does. `CaptureScreen.tsx` computes the verdict on every keystroke. On Enter it writes the full name: `if (hintVerdict.state === 'matched' && !hintVerdict.exact) setSetHint(hintVerdict.set)`. The note under the field says so, in the words `Enter writes the name out`.

`app/src/setHint.ts` landed in `356dd8f7`. The 99 `UNL` cards were captured in one run, in one box, inside 35 minutes, before that field landed. Every capture since writes the full name. **This is residue, not a live defect. No capture-screen work follows from it.**

**The remaining hole is narrow, and still worth closing.** Completion is offered on Enter, not enforced at the shutter. An operator who types a code and presses the shutter without Enter still sends the raw string. The CLI and the two `set_hint` patch paths in `capture_server.py` never reach the screen. So resolution also runs on the route, against the game vocabulary, and covers every writer. The screen keeps its own completion, because the operator should see the name before the photograph is taken.

### Why the set is stored, not resolved on read

A SKU-to-`Set Name` join on every request is refused on two grounds.

**The route is polled.** `#/inventory` is read on a timer. `_copies_out` is already a full-table pass costing about 1s on the owner's store. A per-request export join on a polled route repeats that defect.

**A derived facet disappears.** `inventory/.exports/` holds whatever was last fetched. It is deduped by digest and reused within 900s (D166). A filter that works today and empties tomorrow, because an export aged out, is worse than no filter. The operator cannot tell a set they own nothing in from a set the machine can no longer see. A stored column answers the same on a machine with no export.

So the set is written onto the card **at identification time**, from the candidate row the answer already carries. What the store already holds is backfilled once.

### The backfill was measured first, and it has one hole

Measured against the one export on disk (`inventory/.exports/riftbound/`, 10,191 SKU rows), over the 3,502 cards that carry a SKU:

| game | cards with SKU | resolve to a set |
|---|---|---|
| riftbound | 2,960 | **2,960** (100%) |
| pokemon | 542 | **0** |

The Pokemon hole is not a data problem. No Pokemon export exists in `inventory/.exports/`. Only Riftbound has been fetched there. All 543 Pokemon cards carry `set_hint = 'ME01'`, one set. The hole closes by fetching a Pokemon export through the existing route (D104). The hint is the fallback for that game, because it is unambiguous there.

**The backfill is not a gate and never refuses a card.** A card whose SKU resolves to nothing keeps a null set. It appears in its own bucket, described below.

### Rarity is the catalogue's, and the claim is kept beside it

Two sources disagree, and both are real. `rarity_claim` is the operator's claim at the shutter, a list (D23). The catalogue `Rarity` column is what TCGplayer calls the product.

The owner ruled for the catalogue. Data sitting in inventory after identification is the cleanest data available. The filter reads the catalogue rarity. The same write stores it alongside the set.

The claim is kept and drawn beside it, because showing the capture claim costs nothing. **A disagreement between the two is itself information.** Card `4/383` is the worked example. Its claim reads `["Showcase"]`, and every candidate offered reads `Common`. `Showcase` is a real rarity in this export's vocabulary. Either the card is a Showcase printing whose number never matched, or the claim is wrong.

A filter that stored only the catalogue answer would erase that question. One that stored only the claim would filter on a word the catalogue does not use for this card. Both are kept. Neither is reconciled automatically.

### The control is a dropdown, for standardization across games

The owner ruled a dropdown, because dropdowns standardize across card games.

The facet space is small today. Five sets (Origins, Secret Garden, Spiritforged, Unleashed, Vendetta) and six rarities (Common, Uncommon, Rare, Epic, Promo, Showcase) cover the whole store. A row of chips would fit, and an earlier draft proposed one.

Chips are refused. The control must not reshape itself per game. Pokemon alone publishes far more sets than a chip row holds. Chips for Riftbound and something else for Pokemon would teach two controls for one job. A dropdown is one control at every width, for every game, whatever the set count. It also survives the set list growing, which it will on every release.

### A card that cannot be classified gets a bucket, and is never hidden

8 cards carry no SKU. A SKU may also resolve to no set. Under any active filter, these land in their own visible bucket rather than disappearing.

This is the standing rule in `CLAUDE.md`, never silently drop a card, applied to a filter. It is the argument D132 makes for folding sold cards away rather than deleting them from the view. A card the pipeline could not classify is the card an operator is looking for. A filter is the easiest place to lose it.

An empty bucket is not drawn. Absence is drawn as nothing.

### What this does not decide

**Price band and listing state are deferred**, by the owner's word that they are not needed now. Both are computable today. The `listed` stages already ride every search group, and the cut-off is a figure the operator sets (D99). Neither is built here.

**The Review screen has its own variant problem.** This entry does not fix it. `_catalog_matches` folds the query through `name_index_key` and compares it only to product names. A set word narrows nothing, and so does a rarity word. The queue candidate rows are also not filtered to Near Mint the way the catalogue lookup is. Twelve rows nobody would pick therefore eat the nine digit slots. That is `docs/specs/card-printings.md` section 3.
