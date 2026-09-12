## D-the-queue-is-refreshed-where-it-stands — A queue entry is re-resolved where it stands, and the answer reaches the price without a second press

**Every OPEN queue entry in the store can be re-resolved against a current export by one free, re-runnable command, and a card the operator answers by hand reaches `#/pricing` without anybody pressing Join again.** Built 2026-09-12, on two findings from the review-queue pass that landed the ladder and the screen.

**The two are one defect wearing two coats: a stored artefact frozen at the moment of a join, with nothing in the product able to re-derive it.** The queue entry is one, the pricing row is the other, and the operator pays for both — the first by working a queue that is part current and part frozen, the second by navigating to a screen named after an implementation step.

### Finding 4 — an entry could be permanently unrefreshable, and 513 of 565 were

Measured on the owner's store, grouped by `first_seen`:

| entries first seen | carry `rarity` | conditions filtered to Near Mint |
|---|---|---|
| 2026-09-12 | 70 of 70 | yes |
| 2026-09-11 | 1 of 283 | no |
| 2026-08-24 … 09-02 | 0 of 230 | mixed |

**Two fixes landed on 2026-09-11 — `rarity` on every candidate row, and D137's Near Mint rule on the candidate path — and both are correct in the CODE.** 230 + 283 = **513 of the 565 stored entries could never see them**, so the operator worked a queue that was part current and part frozen with no way to tell which by looking.

**`store/queues.py:upsert` is not the defect; it is the unreachable fix.** That function replaces an entry wholesale, preserves `first_seen`, and refuses only a `cleared_by_human` one — it would refresh happily. **Its only caller is `queues.apply_run`, from `cli/cmd_join.py`; a join is scoped to a run and a run to a box.** So an entry whose box holds no live run is frozen at the code that wrote it, and every later improvement to the ladder lands the same way.

**Proved rather than inferred.** The `Calm Rune` entry is position `4/357`, `first_seen: 2026-09-11`. All six runs over box 4 — `2026-09-01-box4-01`, `2026-09-11-box4-01` through `-04`, `2026-09-12-box4-01` — were re-joined with a freshly fetched export each, and every one reported `+0 main, +0 parked, -0 resolved`. No run alive covers index 357.

**The precedent is exact and is `reconcile --live` (D87).** That command is store-wide *because* a run-scoped reconcile could not reach everything, and its own sentence transfers without amendment: the scoping was a property of the command, not of the data. `Queue` is keyed by position across every box, and `upsert` was written to refresh.

### What the refresh is, and what it deliberately is not

**`pkmnscan queue refresh` walks every OPEN entry, rebuilds the card's reading off the STORE, and runs the same ladder a join runs.** `cli/requeue.py` composes the `join.IdentifiedCard` that `cli/resolve.py:load` would have composed, hands it to `join.join_batch` with `join.default_router`, and turns the verdict back into a `queues.QueueEntry` with `cli/resolve.py:queue_entry` — the same three functions, in the same order. **So a later improvement to the ladder reaches this path the day it lands, with nothing here to keep in step.** A refresh that restated the ladder would be the second thing to keep current, which is the disease rather than the cure.

**It previews by default and writes only with `--write`**, which is `join`, `reconcile` and `reprice list`'s posture for `reconcile --live`'s reason: it rewrites every open entry at once.

**The exports default to the ones the joined runs already recorded, and that is the ordinary case rather than a convenience.** The 513 frozen entries do not need a NEWER catalogue — they need the CURRENT LADDER. `rarity` on a candidate row and the Near Mint filter are properties of the code, not of the CSV, so re-running the ladder over the very file a run used repairs both. `--export` accepts a fresher or wider file and changes what the ladder can find; it is not what makes the refresh work.

**No quantity arithmetic runs.** `join_batch` is handed no `copies_out` and no `live_now`: routing reads the resolution, the confidence and the cheapest candidate price, and none of those is a quantity. What this writes is a QUESTION, never a price and never a copy.

### The three refusals, and two of them are not this module's code

**An answered entry is never re-queued and never dropped, and that comes free from reusing `queues.apply_run`.** `upsert` refuses a `cleared_by_human` position and `release` refuses to drop one, so **D28's undo window stays the only door back out of an answer**. Reusing that function rather than writing the pair of loops was the point: it is the seam T7 already tests, and it is what keeps the two queues from being released in ignorance of each other. Measured on the owner's real store: 564 cleared entries, 565 rows before the write and 565 after, nothing written.

**`first_seen` survives**, because `upsert` preserves it. A card that has been waiting nineteen days has been waiting nineteen days.

**A card that has LEFT THE BOX is skipped, not re-asked about.** Sold, retired and moved are terminal (D26, D83): the physical copy is gone, so the question is moot and a refreshed version of it on the review screen would spend a person's attention on a card they cannot look at. `cli/cmd_join.py` already draws this line — *"skipped: N card(s) in this run are no longer in the box"* — and this is that line for the store-wide pass. **Skipped rather than released**, which is the conservative half: this pass has no opinion about a card it will not resolve. Found by reconstruction: six of box 4's entries sat over `sold` cards, and without the rule the refresh re-queued every one.

### The agreement measurement, which is what makes the ladder claim checkable

**Over one run's own export, the refresh and a real join reach the same verdict on every position both see: 172 of 172 the same queued-or-listed, and 132 of 132 the same reason AND the same candidate rows.** Zero disagreements. That number was 177 of 183 and then 172 of 172 across two real defects this measurement found and nothing else would have:

**An empty string is not a number, and the two route differently.** `load` normalises `(x or "").strip() or None`; this module passed `""` through. `_key_number_and_printed_total` answers None for a card with no number, which sends it down the blank-`Number` name branch, where `""` walks the number key, misses, and lands on D35's last-resort name rung. Six positions the join listed, this queued.

**A reading must be ONE reading, and the store was missing its fifth field.** `record_identification` wrote `name`, `number`, `printed_total` and `confidence`; the model also answers `finish`, and that went only into the run's `identifications.json`. Taking it off the queue entry instead looked free and is not — **an entry may have been written by an OLDER identification of the same photograph**, and six of box 4's cards read `finish: null` on 2026-09-12 while their 2026-09-11 entries still said `foil`. **`store/master.py:Card.detected_finish` closes it**: the store now carries the whole reading, the queue entry contributes nothing to it, and the entry decides only WHICH positions the pass examines. It is None on every card identified before the field existed, which is the honest reading rather than a gap to backfill.

**What it repairs, measured against the 513 the finding names**, on a reconstruction of the store as it stood (the entries reopened and their answers withdrawn on a throwaway copy, because a human has since answered 564 of the 565 by hand): **437 repaired — 199 resolve outright and leave the queue, 238 refreshed in place, 337 candidate rows gain a rarity, 880 off-condition rows dropped, and 9 become answerable in one tap.** The remaining 76 are named rather than counted: 68 cards that have left the box, 7 with no stored reading, 1 already current.

**It is idempotent, which is D87's own test for this shape of command.** A second pass over the written store reports 0 changes.

### Finding 5 — answering the queue did not fold through, and 458 of 489 already did

The owner's words: *"and then after finishing review queue having to do 'join' again, is so fucking unintuitive."*

**The answer writes `sku` and `condition` onto the card; the pricing table is written by `join` and by nothing else.** So the shape of the complaint was right. **What the measurement changed is the size of it.** D156's `_unsent_ledger` already re-derives every merged row against the live store and already unions in copies no table drew — *"a review answer writes `sku` onto a record after `pricing.json` was written"* — so of 489 hand-answered copies still on hand, **458 folded through already**.

**The 31 that did not are the ones whose SKU no table names at all.** The union iterated the SKUs some run's `pricing.json` already carried, so an answer counted only when a SIBLING copy of the same card had happened to resolve at join time. A card whose answer named a new SKU had no row to be counted onto and appeared on `#/pricing` nowhere — and the run holding it could read `0 unsent` for that reason alone, which is the compounding half.

**The union now reaches every SKU the store carries for a run on screen, and a SKU no table names gets a row composed for it.** `cards.sku` is indexed and `cards.run` is not, so the pass is one `distinct` and one `copies_on_hand` per orphan — **measured at 0.001s for 568 values**, against the 3.2s `_copies_out` already costs. `_catalog_rows` returns immediately when there is nothing to look up, so a store with no unfolded answers pays **0.0000s**.

**The row is the join's own and not a second description of it.** `pipeline/worklist.py:sku_row` is the one declaration of that twenty-field shape; `cli/cmd_join.py:_pricing_table` composes the matches a join produced and calls it, and the route composes a `SkuMatch` for a SKU the store carries and calls the same function. Twenty fields with four arithmetic ones among them is not a shape to write twice — `claimed_add` and `over_cap` exist a few lines away precisely because two descriptions of one send disagreed once already. **The extraction is proved inert: the same run, store, export and corpus through the old code and the new produced `pricing.json` byte for byte identical, 397,291 bytes over 206 SKUs.**

**`claimed_add` is zero on such a row and that is the honest answer.** That field is what the runs' TABLES believe they may add, and no table believes anything about this SKU. What CAN go is `add_to_quantity`, written off the live store like every other row.

**Measured on the owner's store: four rows, four copies, and they are recognisable.** `Aspirant's Climb`, `Confront`, `Reckoner's Arena` and `Wizened Elder` — four of the nine `name_disputed` entries the ladder finding tabulated, every one a card where the model's name was right and its number wrong, answered by hand, and until now reachable from no pricing screen.

**The other 27 of the 31 are correctly absent, and the reason is one reason rather than several.** Every one is a copy TCGplayer already holds: `31 = 4 drawn + 27 committed`, counted by walking each SKU no table names and asking the ledger about every copy of it. **This worklist is every copy TCGplayer does NOT hold (D156), so a committed copy has no row to want** — and that this accounts for all 27 with nothing left over is the check that the union is neither too narrow nor too wide. An earlier draft of this paragraph attributed 18 of them to a run over a reallocated drawer; that was inferred from which runs the answers belonged to and is wrong, which is why the figure above was measured against the ledger instead.

**A SKU no export on hand names draws no row, and that is not a silent drop.** The copies stay counted in the run's `unsent` and in `unreachable`, and the operator's door is `Join again` — which is the one case where a re-join really is the answer, because the catalogue on hand does not describe the card.

### How the two interact, which was the question worth asking

**An answer survives a refresh because the refresh never looks at one**, and that is by construction rather than by a test: `Queue.open_entries` excludes a cleared entry, so a position a human has answered is not in the set this pass walks, and `apply_run`'s two refusals stand behind that if anything ever changes.

**D28's undo still works after the fold, because the fold writes nothing.** The pricing worklist is a READ that re-derives; `_reverse_answer` restores `card.sku` and `card.condition` from the history's `restores_to` and reopens the entry, and the next read of `#/pricing` simply stops finding the copy. Nothing had to be un-written because nothing was written.

### Reachable, and where

**`#/review`, from the page header, as two presses with the preview first** — `POST /queues/refresh`, free, `write: false` by default. The preview is what makes the apply control exist, which is D87's rule for a store-wide write, and the sheet says in a sentence that an answered card is never re-queued. `pkmnscan queue refresh` is the same operation at the terminal.

### What is NOT built, recorded rather than left to be discovered

**`detected_finish` is None on all 2,535 of the owner's existing cards** and will stay so until each is identified again. The refresh is then exactly as conservative as a card with no detected finish has always been — it does not invent one — but rung 3's cross-check is absent for them, and a backfill from the run records is a real option this entry declines rather than overlooks: the newest run record for a position is not always the reading the store holds, which is the same mixing the field was added to end.

**The refresh releases an entry the ladder now settles, and does not re-price it.** The card lists on the next `emit` exactly as a re-joined card would; nothing here writes a price, and D49 keeps `#/pricing` the one press that answers one.

**A refresh cannot reach a run over a reallocated drawer (D36), and neither can the fold.** Such a run is excluded by name — its positions are another drawer's cards now — and the fix is not in this entry: it is D145's `bid`, which is where a record that outlives its box binds.

### What is guarded but NOT exercised, named because a mutation arm survived

**The fold's off-screen guard is real and untested.** `do_pipeline_worklist` drops a synthesized row's position when `card.run not in loaded_names`, and deleting that clause changes nothing on the owner's store: every orphan SKU there belongs to a run that is on screen, so no real data reaches the branch. It needs a fixture with two joined runs where only one is loaded and the closed one holds a card carrying a SKU no table names. **A guard whose arm survives is recorded rather than presented as covered** — the sixteen arms over the refresh engine were all caught, this one was not, and the distinction is the point.

**Four more of the engine's paths are reachable and unexercised**: a multi-game catalogue, `photo_moved` (asserted 0, as a check that the fixture is not quietly exercising D10's slide), the `no_export` / `no_game` / `unjoinable` refusals, and `catalogs_from`'s last-file-wins for a game two exports both claim. Each is cheap to add; none is load-bearing for the measurements above.
