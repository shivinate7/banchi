## D-the-set-is-a-stored-fact-and-the-hint-was-never-one

**The owner, 2026-09-17, on searching a card by name and reaching the wrong printing.** Searching
`Mind Rune` or `Calm Rune` on `#/inventory` lands on one SKU. It offers no way to reach a sibling
printing. The only move is to click around boxes until a copy of a different printing falls under
the hand. The owner's words: *"the inventory shows me the most of whatever SKU first and I have to
pick around the boxes to find maybe the right SKU."* Asked what the fix should look like, the owner
widened it: *"what if I want to see just my riftbound inventory, what about just my spiritforged
inventory within riftbound."*

This entry settles where a card's set and rarity live. The name-to-printing navigation it was found
through is `docs/specs/card-variants.md`.

### The store has never held a set, and the surprise is the finding

The owner expected otherwise, and said so plainly. The expectation was that an identified card
carries accurate set data. It does not. Measured against `inventory/store.sqlite` on 2026-09-17:

`cards` has `key, box, idx, state, sku, condition, capture_id, name, number, game, set_hint, run,
captured_at, state_at, payload, cid, number_key, number_display`. **There is no set column.** The
`payload` blob has no set either. All five `Calm Rune` records carry `set_hint = NULL`.

So identification never wrote the set down, although the row it answered from carried one. A queue
candidate is `{"condition", "market", "name", "number", "rarity", "set", "sku"}`. The set was in the
operator's hand at the moment of the answer, and it was dropped on the floor.

### The hint normalizes correctly, and that is not the reason it cannot be the source

An earlier draft of this entry claimed a facet built on `set_hint` would split one drawer into two.
The ground given was that 790 Riftbound cards say `Unleashed` and 99 say `UNL`.
**That claim was wrong, and the owner caught it.**
`pipeline/setnames.py:resolve` already folds both to one set.
Measured on the owner's own hints, every distinct Riftbound value resolves:

| hint | cards | resolves to |
|---|---|---|
| `Origins` | 303 | Origins |
| `Spiritforged` | 680 | Spiritforged |
| `UNL` | 99 | Unleashed |
| `Unleashed` | 790 | Unleashed |
| `Vendetta` | 395 | Vendetta |

The real reason is coverage and authority. **700 Riftbound cards carry no hint at all**, and 698 of
those do carry a SKU. A hint is a claim the operator types at the shutter. It can be absent, and it
can be wrong. The SKU resolves for every card that has one. So the hint is the fallback, and the SKU
is the source.

This keeps the distinction D145 draws between a box label and a box identity. It keeps the one D36
draws between what the model read and where the card is. The hint is evidence about its own card.
The set is a fact about the product.

### The capture screen already completes the hint, and the 99 rows predate it

The owner asked why `UNL` was ever stored, having expected the field to rewrite it. It does.
`CaptureScreen.tsx` computes the verdict on every keystroke. On Enter it writes the name out:
`if (hintVerdict.state === 'matched' && !hintVerdict.exact) setSetHint(hintVerdict.set)`. The note
under the field says so in the operator's words, `Enter writes the name out`.

`app/src/setHint.ts` landed 2026-08-31 in `356dd8f7`. The 99 `UNL` cards were captured 2026-08-29,
in one run, in one box, inside 35 minutes. They predate the completing field by two days. Every
capture since writes the full name.
**This is residue, not a live defect, and no capture-screen work follows from it.**

**The remaining hole is narrow, and it is still worth closing.** Completion is offered on Enter, not
enforced at the shutter. An operator who types a code and presses the shutter without pressing Enter
still sends the raw string. The CLI and the two `set_hint` patch paths in `capture_server.py` never
reach the screen at all. So the resolution runs on the route as well, against the game vocabulary,
where it covers every writer. The screen keeps its own completion, because the operator should see
the name before the photograph is taken.

### Why the set is stored and not resolved on read

The alternative was a SKU-to-`Set Name` join on every request. It is refused on two grounds.

**The route is polled.** `#/inventory` is read on a timer. `_copies_out` is already a full-table
pass costing about 1s on the owner's store. Adding a per-request export join to a polled route
repeats that defect rather than introducing a new one.

**A derived facet disappears.** `inventory/.exports/` holds whatever was last fetched. It is deduped
by digest and reused within 900s (D166). A filter that works this afternoon and empties tomorrow,
because an export aged out, is worse than no filter. The operator cannot tell a set they own nothing
in from a set the machine can no longer see. A stored column answers the same on a machine with no
export at all.

The set is therefore written onto the card **at identification time**, out of the candidate row the
answer already carries. What is already in the store is backfilled once.

### The backfill was measured before it was promised, and it has one hole

Measured against the one export on disk (`inventory/.exports/riftbound/`, 10,191 SKU rows), over the
3,502 cards carrying a SKU:

| game | cards with SKU | resolve to a set |
|---|---|---|
| riftbound | 2,960 | **2,960** (100%) |
| pokemon | 542 | **0** |

The Pokemon hole is not a data problem. There is no Pokemon export in `inventory/.exports/`. Only
Riftbound has ever been fetched there. All 543 Pokemon cards carry `set_hint = 'ME01'`, a single
set. The hole closes by fetching a Pokemon export through the route that already exists (D104). The
hint is the fallback for that one game, because it is unambiguous there.

**The backfill is not a gate and never refuses a card.** A card whose SKU resolves to nothing keeps
a null set. It appears in its own bucket, described below.

### Rarity is the catalogue's, and the claim is kept beside it

Two sources disagree, and both are real. `rarity_claim` is the operator's claim at the shutter, a
list (D23, D146). The catalogue `Rarity` column is what TCGplayer calls the product.

The owner ruled for the catalogue, reasoning that data sitting in inventory after identification is
the cleanest data available. The filter reads the catalogue rarity. The same write stores it
alongside the set.

The claim is kept and drawn beside it, on the owner's second clause, that showing the capture claim
is worth it where it costs nothing. **A disagreement between the two is itself information.** Card
`4/383` is the worked example. Its claim reads `["Showcase"]`. Every candidate offered reads
`Common`. `Showcase` is a real rarity in this export's own vocabulary. Either the card is a Showcase
printing whose number never matched, or the claim is wrong.

A filter that stored only the catalogue answer would erase that question. One that stored only the
claim would filter on a word the catalogue does not use for this card. Both are kept. Neither is
reconciled automatically.

### The control is a dropdown, and the reason is other games

The owner's ruling: *"realistically it should be a dropdown given that dropdowns would allow for
standardization across card games."*

The facet space is small today. Five sets (Origins, Secret Garden, Spiritforged, Unleashed,
Vendetta) and six rarities (Common, Uncommon, Rare, Epic, Promo, Showcase) cover the whole store. A
row of chips would fit, and an earlier draft of this entry proposed one.

It is refused because the control must not reshape itself per game. Pokemon alone publishes far more
sets than a chip row can hold. A facet drawn as chips for Riftbound and as something else for
Pokemon teaches two controls for one job. A dropdown is one control at every width, for every game,
whatever the set count. It also survives the set list growing, which it will on every release.

### A card that cannot be classified gets a bucket, and is never hidden

8 cards carry no SKU at all. A SKU may also resolve to no set. Under any active filter these land in
their own visible bucket rather than disappearing.

This is not a courtesy. It is the standing rule in `CLAUDE.md` — never silently drop a card —
applied to a filter. It is the argument D132 makes for folding sold cards away rather than deleting
them from the view. A card the pipeline could not classify is exactly the card an operator is
looking for. A filter is the one place it would be easiest to lose.

An empty bucket is not drawn. Absence is absence, and it is drawn as nothing.

### What this does not decide

**Price band and listing state are deferred**, on the owner's word that they are not needed right
now. Both are computable today. The `listed` stages ride every search group already, and the cut-off
is a figure the operator sets (D99). Neither is built here.

**The Review screen has its own variant problem**, and this entry does not fix it. `_catalog_matches`
folds the query through `name_index_key` and compares it to product names only. A set word narrows
nothing, and a rarity word narrows nothing. The queue candidate rows are also not filtered to Near
Mint the way the catalogue lookup is. Twelve rows nobody would pick therefore eat the nine digit
slots. That is `docs/specs/card-variants.md` section 3.
