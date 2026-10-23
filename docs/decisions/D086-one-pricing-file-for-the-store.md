## D86 — One pricing file for the store

**Ruling: prices are one corpus keyed by SKU, in `inventory/prices.json`, not one file per run.** Per-run data stays per run only where it is a property of the lot.

The owner saw the fan-out write and the conflict detector and asked why the front end was not a central pricing corpus and dashboard, with boxes feeding it.

`runs/<n>/decisions.json` held two kinds of fact in one file:

| scope | keys | what it is |
|---|---|---|
| run-wide | `rule`, `basis`, `sub_threshold` | arguably a property of the lot (D180's argument) |
| **per-SKU** | `overrides`, `no_market_data` | **a property of the CARD** (D7's argument) |

The per-SKU half is what a price is. TCGplayer prices per SKU globally. D7 states "price is per-SKU and shared across copies". `pipeline/join.py` spends the live cap against every box at once. Stored per run, one card held one answer per drawer it was ever photographed in.

**Home:** `pipeline/corpus.py`. The file is `inventory/prices.json`, keyed by SKU, and it holds the policy too, on the owner's instruction. A per-run policy override stays for a lot that differs. `Corpus.for_run`/`scoped_to` project it into a `Decisions`, so `join`, `emit` and `prices_for` do not change. The pricing design and the price history both named this gap and did not close it: no durable home for a hold outside the run directory, and no cross-run view of what is held. `banchi prices show --held` shows held SKUs across runs.

**Deleted.** The first build answered the duplication with a fan-out write into N files, conflict detection on every row, and an agreement refusal. All of it reconciled a duplication. The first `pipeline/merge.py` carried a `PriceDisagreement`. Run against three real runs, it refused 66 SKUs. Almost all were the market moving between two joins, not a disagreement. Making a defect unrepresentable is worth more than reporting it.

**A send never prices from an export older than today.** `emit` refuses the old reading and refreshes it first (`refresh_before_send`), because a market price moves between joins. The corpus stays the answer. Only the market reading under it is renewed.

**Kept whole: the cap.** It is arithmetic over positions, not an answer. Centralizing does not change it. See "The cap is D59's defect one register up" below.

**Migration.** `banchi prices adopt` previews by default, because it holds a real decision. Ruling: newest wins. Three of the eight contested SKUs are a `withheld` hold answered by a later price. Newest-wins resolves those to the price, the direction that cost money. The command names those three.

- A legacy run file is never a fallback. It would bring the duplication back on the first re-join of an old run.
- The first refusal fired only while the corpus was empty. After the first adoption, eight files on the owner's store were silently ignored.
- `join` and `emit` refuse, unconditionally and before anything is read or written. The refusal names `banchi prices adopt --write`.
- `adopt --write` retires each folded file to `decisions.json.adopted` (`cli/runs.py:retire_decisions`, never overwriting).
- A re-adopt keeps the corpus's answer for a SKU the corpus already answers. It reports the file's answer under `kept`. It retires the file without `--force`.
- `--force` folds the files over the corpus. The old form dropped every answer written on `#/pricing` since adoption.
- Deleted: `PUT /pipeline/runs/<name>/decisions`, the `#/runs` textarea and `remembered_sub_threshold`. They answered 409 for every run made after this entry, because `join` no longer wrote the file they edited.

The policy default is D9's amendment of the same day.

### The merged view

`#/pricing` opens on every run that still has pricing. It merges one SKU across runs into one row, and it writes one answer into the corpus. Built on the owner's instruction. Boxes captured together are priced together. The general form: unprocessed items are processed all at once. The owner also set a boundary: pricing by box must not be lost.

This is D180's resolution one register over, and it overturns nothing. D180 ruled that a send is a cart of boxes and that a run is still one box. A run carries a reading, a `--bypass` ruling and a `decisions.json`. All three are properties of what is in the drawer. The view merges. The file does not. Nothing downstream learns a new shape. D180 protects that property.

The single-select this replaces had no argument for it. The design defends where the run comes from (`GET /pipeline/runs` is the one source) and says nothing about how many runs may be picked. A set over the same source has the same property. D39's one-mass-select rule covers cards, not runs. `#/inventory` keeps the only one.

### What it costs today

Across the eight runs in `runs/`, 78 of 423 SKUs sit in more than one run. Eight carry an answer in more than one. Three of those eight are a `withheld` hold answered with a price in a later sitting:

| SKU | Card | Earlier run | Later run |
|---|---|---|---|
| 9191210 | LeBlanc, Everywhere At Once | box3 08-31 `{withheld: bullish, watch_above: "5"}` | box4 09-01 **`"3.45"`** |
| 9405228 | Death Mark | box3 08-31 `{withheld: bullish}` | box3 09-01 `"2.29"` |
| 9422429 | Public Execution | box3 08-31 `{withheld: bullish}` | box3 09-01 `"2.29"` |

LeBlanc was held bullish above $5 from one drawer and listed at $3.45 from another the next day, below the operator's own watch. That row drew as an ordinary listable one. A hold lived in its run and died with it. No screen read two runs at once.

The stated reopening measurement watched the other direction: the same SKU withheld in two runs over one box. That count is zero. The case that bites is asymmetric. This entry replaces the measurement. It watches for a hold in one run answered with a price in another.

Four of the eight pairs were not disagreements. `0.5` and `.5` are one figure. `_same_price` compares as `Decimal`, so the flag is meaningful when it fires.

### The cap is D59's defect one register up

`pipeline/join.py:add_to_quantity` spends `live_cap - copies_out` per run. The cap is global. Runs joined before either emitted each spent the same room. A cart joined boxes 3, 4 and 5 in one second. Five SKUs' per-run claims summed past four. Two reached `pushed: 6` in `inventory/inventory.json` against `LIVE_QUANTITY_CAP = 4`:

    Void Assault (9197754):  pushed: 6, live: 1
    Deathgrip    (9038187):  pushed: 6, live: 1

D59 fixed per-box capping inside one join. This defect survived per run, across joins that never saw each other. `GET /pipeline/pricing` computes `min(claimed, cap - copies_out, copies)` once. It reports `claimed_add` beside it, so the row shows the runs disagree with it. It corrects nothing on disk. This route writes no import file. The emitter is where the arithmetic must change.

`copies` is the count of distinct positions, not a sum. Box 3 was joined three times. A sum made Void Assault twelve copies of a card there are seven of.

### The picker

The picker is a filter over the list, not a gate in front of it. It draws a remainder. `counts.skus` is the size of a job, never the job. Box 2's 109 SKUs are one `floor` press. Box 3's 199 are 117 real decisions. `counts.sub_threshold` and `counts.no_market_data` rode every poll and were read by nothing. The roster asks `Decisions.blocking`, the Python that refuses an emit. So the chip cannot claim a refusal that Python does not make. This is the pricing screen's rule over `readiness.ts`, applied to the server.

The earlier design promised a terminal state the screen never reached: "a screen whose job is to report there is nothing to do". The only empty state fired when no run had ever been joined. So eight fully answered runs drew eight chips. They cost about 909KB and sixteen round trips to learn they owed nothing.

Boxes sort ascending within a sitting. `GET /pipeline/runs` sorted by directory name reversed, so box 5 came before box 3. `Runs.tsx` orders the same drawers "the order they sit on a shelf". Two screens ordering the same drawers two ways is drift. A test pins it.

### Three defects found on the way

- **`inFlight` became a `Set`, and an empty `Set` is truthy.** The emit guard read `if (dirty || saving || inFlight.current) return`, written for a boolean. The press always returned and did nothing. Four cases in `app/tests/pricing.spec.ts` caught it.
- **The hash was read in an effect, so mount fired two loads.** The last load to land won `docs`. But `savedDocs` is a ref written outside React's batching. A render could pair the first load's documents with the second's saved marker. `dirty` went true with nothing typed, and the screen PUT a document the operator never touched. The per-run design calls that write the load-bearing absence of the whole screen. The hash is now read in the `useState` initializer. A generation guard drops a stale response.
- **`unsaved` must not be memoized.** `savedDocs` is a ref, so a `useMemo` keyed on `[loaded, docs]` never recomputes when a write lands. The save loop oscillated between unsaved, saving and unsaved.

### The threshold and the cheap-card price are one figure

**Owner ruling, made with the two defaults shown side by side: threshold and cheap-card price are one variable and must match.** The cut-off is one number with two jobs. It is the line a card sits above or below. Everything below it lists at that figure. `#/pricing` cannot write one without the other.

The inversion forced this. A threshold of $0.40 beside a cheap-card answer of $0.49 prices a card worth $0.38 at $0.49. It prices a card worth $0.42 at $0.42. The card that failed the bar is sold dearer than the card that cleared it. That happens across the 9-cent window between them. The window is where bulk lives. D9's derivation puts the threshold where card density is highest. Two figures free to cross cannot be kept apart by care. Only a design that makes crossing unrepresentable survives an operator typing.

- One press writes both keys. `policy.threshold` is what `pipeline/join.py` partitions by. `policy.sub_threshold` prices the lower half. The screen writes them together, at the store and at the run. The pipeline did not change. `Corpus.policy_for` still folds the two keys independently. A hand-written document can still hold two figures. The screen maintains this constraint. The schema does not enforce it, on purpose. The command line can still write a gap, and the file is still read.
- A store that holds two figures is reported, never resolved for the operator. This machine's store held `threshold: "0.40"` beside `sub_threshold: {flat: "0.24"}`. Neither was wrong. Drawing the cut-off alone would claim cheap cards sell at $0.40, while `emit` wrote $0.24. That is the screen lying about money. The panel names the stranded figure, says `emit` uses it until something overwrites it, and offers one press that makes them agree. The screen cannot know which figure the operator meant.
- The list re-partitions as the figure is typed. `bucketAt` is `pipeline/pricing.py:is_listable` in the client's terms. Market at or above the cut-off is listable. Market below it is cheap. No market data is unpriced and is neither. A cut-off equal to the stored one re-derives the buckets the server sent. A changed one moves rows at once, without a reload. This does not weaken D28. D28 stops the list reflowing under a commit. A typed price still moves nothing. A policy change is the moment the partition should move. Readiness reads the partition as drawn. So a raised cut-off over listable rows says `emit` will refuse, before it does.
- Client re-partitioning is the accurate reading. It was not the reason for building it. `GET /pipeline/pricing`'s `bucket` cell comes from the join that wrote `pricing.json`. `emit` does not read it. `cli/resolve.py:load` takes the stored threshold and re-runs `join_batch`. On this machine's box 6, the stored cut-off moved to $1.25. The payload still reported 3 listable and 8 sub-threshold, split at $0.40. The screen drew 1 and 10. `emit` would write 1 and 10. Reading the payload would have put a card in the listed section that the file puts in the cheap one.
- The panel is drawn whether or not any card is under the line. It was conditional on cheap cards existing. That was right while the figure only answered about those cards. Now the figure is the line. A cut-off typed low enough to empty the lower section would have removed its own control from the screen.

### The default is one figure too

The merge with main removed this entry's first promise. The first build said a store that never set a threshold partitions as it did before. D9's amendment gave `sub_threshold` a default of a flat $0.49. A `threshold` still fell back to `pricing.THRESHOLD` at $0.40. A store that chose neither figure split at $0.40 and priced the lower half at $0.49. So a card worth $0.38 listed above one worth $0.42. That is the inversion this entry exists to end.

`pipeline/corpus.py` now has one fallback. Both keys read `DEFAULT_CUTOFF`, $0.49. The figure is the owner's. The owner stated it as the cheap-card default and again as the one-variable ruling.

**Cost.** An existing store that never set a threshold splits at $0.49, where it split at $0.40. A SKU whose market sits between the two moves from the listed half to the cheap half on its next join. That moves cards, not money. Those SKUs sell at $0.49 either way, because the cheap half has been priced at $0.49 since the amendment.

The earlier text here said the owner's store was unaffected because it held $0.40. That was wrong. `inventory/prices.json` holds `{"basis": "market", "rule": "match", "sub_threshold": "floor"}` and no `threshold` key. So `DEFAULT_CUTOFF` applies, and the store splits at $0.49. The file has not been written since, so `sub_threshold: "floor"` (a form D9 retired) still parses. It becomes a flat figure on its first edit. `harness/tests/t7/emit_pricing.py` asserts the shared fallback and records the trade beside the assertion.

**Reopening.** An operator who wants the listing bar below the price cheap cards sell at. For example, list everything over $0.40 and sell the bulk at $0.49. The one-variable rule cannot express that. No one has asked for it. A screen would need a way to say it that cannot be taken for the pair drifting apart.

### Not built

**The merged emit.** The owner asked for one CSV across runs, across the listed and sub-threshold split, and across games. It came with a checkbox to peel off the above-threshold rows. It needs changes to `pipeline/join.py`, `cli/resolve.py` and `cli/cmd_emit.py`. A merged file cannot be made by concatenating the CSVs on disk. The cap must be recomputed across the union, or the over-push above lands in the file. Until it lands, `emit` stays per run. The press is absent on a worklist of more than one run. Absent, not disabled. D33's rule for the control that spends applies to the one that writes files.

**TCGplayer's Import to Staged** may not accept a file spanning two `Product Line`s. This is unknown. `cli/runs.py:import_listed_name` has said so since it was written. `fixtures/staged-import-accepted.csv` proves one line only. The owner will test it. Nothing here depends on the answer.

**The two over-pushed SKUs** are not corrected. Fixing the arithmetic removes nothing TCGplayer already holds. That is the owner's to reconcile.

**Reopening conditions, two.**

- *A worklist never used with more than one run.* The remaining cost of the merge is the union and the cap arithmetic. If every sitting is one box, the honest simplification is the single-select again. The measurement is whether any `GET /pipeline/pricing` answers with more than one run in it.
- *A lot that needs its own policy.* `Corpus.overrides` keeps a per-run `rule`, `basis` and `sub_threshold` for that case. Nothing writes one today. No screen offers it, and the migration never produces one. If the field stays empty after several sittings, it is speculative generality and should go. That removes `_agree_policy` and its refusal too. If it fills up, D180's per-lot argument is stronger than this entry credits, and the policy belongs back in the run.

**Amended: `Corpus.overrides` has a writer.** `#/pricing` draws a per-run sub-threshold override beside the store's answer. It writes to `policy.per_run[<run>].sub_threshold`, drawn so it cannot be read as the store's answer. Building it settles neither branch above. What changes is that a sitting now produces evidence. D9.

**One file, two writers.** `PUT /pricing` replaces the document wholesale. That is deliberate, so a key this screen has never heard of survives. `#/pricing` autosaves the corpus it took at mount. Together, any write that landed under an open pricing tab was undone by that tab's next keystroke. No error appeared, on the one file in this product that holds money. Two tabs reach it. So does `banchi prices adopt --write` while a tab is open.

**The guard is a revision in the envelope, never in the document.** The screen decides "unsaved" by comparing the corpus it holds with the one it last sent, by identity. A revision inside the document would rebuild on every landed write and re-dirty the screen: unsaved, saving, unsaved, without end. So `GET /pricing` returns a sibling `revision`, a short digest of the file. `PUT /pricing` compares it and refuses with `corpus_moved` / 409. The write's receipt carries the new revision, so the operator's next keystroke is never stale against the file they just wrote.

**An absent revision is allowed.** It means that the client did not read one. That is the terminal user who edits `inventory/prices.json` and PUTs it back. The guard covers a client that did read one and is now behind. That is the only case that can destroy a write nobody saw happen. Verified on the live server in three states: stale refuses 409, current writes, absent writes.

**Found on another branch** (`claude/great-nightingale-37cf84`). A markdown re-prices every stale SKU at once. That made the hazard acute. A stale PUT would have undone the whole sweep. The bug is in the answer, not in that feature. It exists once the answer became one file with one wholesale write.

**Still not built: the reconcile is per run.** `cli/cmd_reconcile.py` scopes its diff to one run's `emitted_skus`. The thing it diffs against, `store/master.py`'s `Listing`, is already per SKU across every box and run. The owner named the consequence. A full live TCGplayer export should reconcile across every emit, box and date at once. It should report both directions, which is that command's own rule. It would be the first thing able to see the two SKUs measured at `pushed: 6` against a cap of 4. Not built here.

---

A hold is a stated reason, never a zero price. A suggestion writes nothing until typed.

- A hold is absent from `dispositions()`. `emit` and `prices_for` refuse a run when that mapping names a SKU the batch does not hold. A withheld SKU is the one most likely to go stale. A hold in it would break `emit` for the whole run, with nothing able to clear it.
- A preset writes `rule` and `basis` and never an override, because an override beats the rule. It prices what it can and names what it could not. `cli/cmd_join.py:PRESETS` and `app/src/Pricing.tsx:PRESETS` agree on key, rule and basis. The `pricing presets` row of `make docs-audit` checks that.
- The active preset chip comes from `rule` and `basis` and is never stored. A remembered chip would name a live rule while the run used another.
- `withheld` means that this SKU is kept out of the import (`pipeline/decisions.py`). `held` means that copies TCGplayer holds (`store/master.py:Listing.held`), the opposite direction. A box that may not be deleted for a listing is a third thing, `_listing_hold`. Keep the three words apart.
