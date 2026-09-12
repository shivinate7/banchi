## D86 — The pricing answer is one file for the store, and the worklist spans runs

**AMENDED THE SAME DAY IT WAS BUILT, ON THE OWNER'S QUESTION.** Shown the fan-out write and the conflict detector below, they asked: *"why can't it be my front end is largely a pricing corpus/dashboard of everything, with boxes feeding it? why is it we've made a federalist state system when this is best done as a centralized system?"*

They were right, and this entry had already written the evidence down without acting on it. `runs/<n>/decisions.json` held **two kinds of fact in one file**:

| scope | keys | what it is |
|---|---|---|
| run-wide | `rule`, `basis`, `sub_threshold` | arguably a property of the lot — D48's argument |
| **per-SKU** | `overrides`, `no_market_data` | **a property of the CARD** — D7's argument |

The second half is what a price *is*. TCGplayer prices per SKU globally, D7 states *"price is per-SKU and shared across copies"*, and `pipeline/join.py` spends the live cap against every box at once. Stored in a run directory, one card carried one answer per drawer it had ever been photographed in.

**`pipeline/corpus.py` is the home, and `inventory/prices.json` is the file.** Keyed by SKU, holding the policy too on the owner's instruction, with a per-run policy override kept for the lot that genuinely differs — which is D48's argument surviving in the one place it is actually about. `Corpus.for_run`/`scoped_to` project it into a `Decisions`, so `join`, `emit` and `prices_for` never learned that answers moved: the property D48 spends its length protecting, applied to this move.

**D49 AND D62 BOTH NAMED THIS GAP AND NEITHER CLOSED IT.** D49: *"no durable home for a hold outside the run directory; no cross-run view of what is being held."* D62: *"No cross-run view."* `pkmnscan prices show --held` is one line now.

**What the amendment DELETED, which is the useful part.** The first build answered the duplication with machinery: a fan-out write into N files, conflict detection on every row, and an agreement refusal before a merged file could be written. All of it existed only to reconcile a duplication. `pipeline/merge.py`'s first version carried a `PriceDisagreement` and, run against three real runs, **refused on 66 SKUs — almost every one of them the market having moved between two joins rather than any disagreement at all**. Reporting a defect is worth less than making it unrepresentable.

**What survived whole: the cap.** It is arithmetic over positions, not an answer, so centralising changed nothing about it — see "The cap is D59's defect one register up" below.

**`pkmnscan prices adopt` is the migration**, and it previews by default because there is a real decision inside it. The owner's ruling was newest-wins; three of the eight contested SKUs are a `withheld` hold answered by a later price, and newest-wins resolves those **to the price** — the direction that cost money. The command names those three rather than counting them.

**A legacy run file is never read as a fallback.** That would put the duplication back on the first re-join of an old run. `join` and `emit` refuse with a sentence naming the command instead.

**Amended 2026-09-02: the refusal is unconditional, the migration retires what it folds, and the per-run editor is deleted.** The refusal above was gated on an EMPTY corpus — `join` and `emit` looked for a legacy file only while `inventory/prices.json` held no answers — so from the first adoption onward eight files on the owner's store were silently ignored while this entry and CLAUDE.md described a refusal. It is unconditional now and fires before anything is read or written, naming `pkmnscan prices adopt --write`. That command RETIRES each folded file to `decisions.json.adopted` (`cli/runs.py:retire_decisions`, never overwriting); a re-adopt over SKUs the corpus already answers keeps the corpus's answer, reports the file's under `kept`, and retires the file without `--force`; and `--force` folds the files OVER the corpus rather than into a fresh one — the old form dropped every answer written on `#/pricing` since adoption. `PUT /pipeline/runs/<name>/decisions`, the `#/runs` textarea and `remembered_sub_threshold` are deleted: they answered 409 for every run made after this entry, because `join` no longer wrote the file they edited. The policy's default is D9's amendment of the same day.

---

**The original entry follows, with the parts the amendment retired marked where they stand.**

**`#/pricing` opens on every run that still has pricing in it, merges the same SKU across them into one row, and — ~~writes one answer into every run's own `decisions.json`~~ RETIRED, see the amendment — writes one answer into the corpus.** Built 2026-09-01 on the owner's instruction: *"if I capture from multiple boxes, they ought to be processed in pricing at the same time"*, with the general form beside it — *"items that aren't processed ought to have the functionality of being processed all at once"* — and the boundary they set on it, that pricing by box is good too and must not be lost.

**This is D48's own resolution one register over, and it overturns nothing.** That entry ruled a send is a cart of boxes and a run is still one box, because *"a run carries a reading, a `--bypass` ruling and a `decisions.json`, and all three are properties of what is IN the drawer"*. Every word stays true. The **view** merges; the **file** does not. One answer to a merged row is one `PUT /pipeline/runs/<name>/decisions` per run holding that SKU, the route is untouched, and nothing downstream learns a new shape — the property D48 spends its length protecting.

**~~One answer to a merged row is one `PUT` per run holding that SKU.~~ RETIRED.** There is one document and one write. The sentence stood for about four hours.

**Nothing in D49 argued for the single-select this replaces.** That entry defends where the run comes from — *"a picker here cannot disagree with anything"*, because `GET /pipeline/runs` is the single source — and says nothing about how many may be picked. A set over that same single source has the identical property. D39's one-mass-select rule is about **cards** and is untouched; `#/inventory` still owns the only one. `useState<string | null>` was the cheapest thing to write on 2026-08-30 and no entry defended it.

### What it costs today, measured rather than argued

Across the eight runs in `runs/` on 2026-09-01, **78 of 423 SKUs sit in more than one run** and **8 carry an answer in more than one**. Three of those eight are a `withheld` hold answered with a price in a later sitting:

| SKU | Card | Earlier run | Later run |
|---|---|---|---|
| 9191210 | LeBlanc, Everywhere At Once | box3 08-31 `{withheld: bullish, watch_above: "5"}` | box4 09-01 **`"3.45"`** |
| 9405228 | Death Mark | box3 08-31 `{withheld: bullish}` | box3 09-01 `"2.29"` |
| 9422429 | Public Execution | box3 08-31 `{withheld: bullish}` | box3 09-01 `"2.29"` |

LeBlanc was held bullish above $5 out of one drawer and listed at $3.45 out of another the next day, below the operator's own watch. That row drew as an ordinary listable one — `at_cap: false`, `nothing_to_add: null`, no note anywhere — because a hold lives in its run and dies with it (D49) and no screen had ever read two runs at once.

**D49's stated reopening measurement was the other direction and has never fired.** It watched for *"the same SKU withheld in two runs over one box"*; that count is zero. It is the asymmetric case that bites, and **this entry replaces the measurement rather than repealing it**: what to watch is a hold in one run answered with a price in another.

**Four of the eight pairs were not disagreements at all** — `0.5` against `.5`, the same figure typed with and without its leading zero. `_same_price` compares as `Decimal`, so the flag means something when it fires.

### The cap is D59's defect one register up

`pipeline/join.py:add_to_quantity` spends `live_cap - copies_out` **per run** against a cap that is **global**, so runs joined before either emitted each spend the same room. The 2026-09-01 cart joined boxes 3, 4 and 5 in the same second; five SKUs' per-run claims sum past four, and two reached `pushed: 6` in `inventory/inventory.json` against `LIVE_QUANTITY_CAP = 4`:

    Void Assault (9197754):  pushed: 6, live: 1
    Deathgrip    (9038187):  pushed: 6, live: 1

D59 fixed per-**box** capping inside one join and this survived per-**run** across joins that never saw each other. `GET /pipeline/pricing` computes the figure once — `min(claimed, cap - copies_out, copies)` — and reports `claimed_add` beside it so the row says the runs disagree with it. **It corrects nothing on disk**: this route writes no import file, and the emitter is where the arithmetic has to change.

**`copies` is the distinct positions and not the sum.** Box 3 has been joined three times, so summing each run's count made Void Assault twelve copies of a card there are seven of.

### What the picker became

**A filter over the list rather than a gate in front of it**, and it draws a **remainder**. `counts.skus` is the size of a job and never the job — box 2's 109 SKUs are one `floor` press and box 3's 199 are 117 real decisions. `counts.sub_threshold` and `counts.no_market_data` had ridden every poll since the manifest gained them and were read by nothing; the roster asks `Decisions.blocking`, the Python that actually refuses an emit, so the chip cannot claim a refusal Python does not make (D49's rule over `readiness.ts`, applied to the server).

**The terminal state D49 predicted and the screen never got.** That entry read the history and said the honest reading was *"a screen whose job is to report there is nothing to do"*. It could never say it: the only empty state fired when NO run had ever been joined, so eight fully-answered runs drew eight chips and cost ~909KB and sixteen round trips to discover they owed nothing.

**Boxes ascending inside a sitting.** `GET /pipeline/runs` sorts by directory name reversed, so within one day the picker drew box 5, box 4, box 3 — backwards against the rule `Runs.tsx` states for the same choice, *"the order they sit on a shelf"*. Two screens ordering the same drawers two ways is drift; it is pinned now because it is otherwise invisible.

### Three defects found on the way, two of them live before this entry

- **`inFlight` became a `Set` and an empty `Set` is truthy.** The emit guard read `if (dirty || saving || inFlight.current) return`, written against a boolean, and so became *always return* — the press silently did nothing. Caught by four cases already in `app/tests/pricing.spec.ts`.
- **The hash was read in an effect, so mount fired two loads.** Whichever landed last won `docs`, but `savedDocs` is a ref written outside React's batching, so a render could see the first load's documents against the second's saved marker: `dirty` went true with nothing typed and the screen PUT a document the operator never touched — **the one write D49 calls the load-bearing absence of the whole screen**. The hash is now read in the `useState` initialiser and a generation guard drops a stale response.
- **`unsaved` must not be memoised.** `savedDocs` is a ref, so a `useMemo` keyed on `[loaded, docs]` never recomputes when a write *lands*; the save loop oscillated unsaved → saving… → unsaved forever.

### Three: the threshold and the cheap-card price are ONE figure

**The owner, on being shown the two defaults side by side:** *"I told you that threshold and
cheap card are the same variable and should be the same."* Built 2026-09-03. The cut-off is now
one number doing two jobs — it is the line a card is above or below, and it is what everything below
it lists at — and `#/pricing` has no way to write one without the other.

**The inversion is what forced it, and it is arithmetic rather than taste.** A threshold of $0.40
beside a cheap-card answer of $0.49 prices a card worth $0.38 at $0.49 and a card worth $0.42 at
$0.42: the card that FAILED the bar goes out dearer than the card that cleared it, at every point
in the 9-cent window between them. The window is not hypothetical — it is where bulk lives, and
D9's own derivation puts the threshold exactly where the density of cards is highest. Two figures
free to cross each other cannot be held apart by care; the only fix that survives an operator
typing is to make crossing unrepresentable.

**So one press writes both keys.** `policy.threshold` is what `pipeline/join.py` partitions by and
`policy.sub_threshold` is what it prices the lower half at, and the screen writes them together at
the store and at the run. Nothing in the pipeline changed: `Corpus.policy_for` still folds the two
keys independently, and a document written by hand may still hold two figures — this is a
constraint the SCREEN maintains, not one the schema enforces, and that is deliberate. The
command-line operator who genuinely wants a gap can still write one, and the file will still be
read.

**A store already holding two figures is REPORTED, never resolved on the operator's behalf.** This
machine's own said `threshold: "0.40"` beside `sub_threshold: {flat: "0.24"}`, and neither is
wrong. Drawing the cut-off alone would claim the cheap cards go out at $0.40 while `emit` wrote
$0.24 — the screen lying about money, which is the one thing `#/pricing` may never do. So the
panel names the stranded figure, says `emit` uses it until something is written over it, and
offers one press that makes them agree. Which of the two the operator meant is not a thing this
screen can know.

**And the list re-partitions under the figure as it is typed.** `bucketAt` is
`pipeline/pricing.py:is_listable` in the client's terms — market at or above the cut-off is
listable, market below it is cheap, no market data is unpriced and never either — so a cut-off
equal to the stored one re-derives exactly the buckets the server sent, and a changed one moves
the rows immediately instead of after a reload. **This does not weaken D28.** What D28 stops is
the list reflowing under a COMMIT, so an answer typed on a row cannot move the row out from under
the hand that typed it; that is unchanged and a typed price still moves nothing. The cut-off is a
policy figure, and a policy change is precisely the moment the partition is supposed to move.
Readiness reads the partition as drawn rather than as fetched, so a cut-off raised over rows that
were listable says `emit` will refuse before it does.

**Re-partitioning on the client is the ACCURATE reading, and that was not why it was built.**
`GET /pipeline/pricing`'s `bucket` cell is the run
table's, frozen by the join that wrote `pricing.json`; `emit` does not read it — `cli/resolve.py:
load` takes the STORED threshold and re-runs `join_batch` with it, so the file is partitioned at
the figure standing when the press happens. Measured on this machine's own box 6: with the stored
cut-off moved to $1.25, the payload still reported 3 listable and 8 sub-threshold — the split at
$0.40 — while the screen drew 1 and 10, and 1 and 10 is what `emit` would have written. A screen
reading the payload's bucket would have been wrong in the direction that matters, showing a card
in the listed section that the file puts in the cheap one.

**The panel is drawn whether or not any card is under the line.** It was conditional on there
being cheap cards, which was right while the figure was only an answer ABOUT those cards; now that
the figure IS the line, a cut-off typed low enough to empty the lower section would have taken its
own control off the screen with it.

### The default is one figure too, and that cost the invisibility promise

**The merge with main took away this entry's own promise.** Its first build said a store which
had never set a threshold would partition exactly as it did yesterday. D9's amendment of
2026-09-02 gave `sub_threshold` a default of flat $0.49, so a fresh store's first `emit` is not
refused for want of an answer the owner had already given once. That is right on its own. Beside a
`threshold` still falling back to `pricing.THRESHOLD` at $0.40 it is the inversion this entry
exists to end, arriving through the back door: a store that has chosen NEITHER figure partitions
at $0.40 and prices the half below it at $0.49, so a card worth $0.38 lists above one worth $0.42.

**So `pipeline/corpus.py` has ONE fallback and both keys read it — `DEFAULT_CUTOFF`, $0.49.** The
figure is the owner's, stated twice: as the cheap-card default they asked to be inserted, and then
as the ruling that the two settings are one variable. The pair cannot invert now unless somebody
writes them apart on purpose, which the command line still permits and no screen does.

**What it costs, said plainly.** An existing store that never set a threshold partitions at $0.49
where it used to partition at $0.40, and every SKU whose market sits between the two moves from the
listed half to the cheap half on its next join. **That moves cards and not money**: those SKUs go
out at $0.49 either way, because $0.49 is what the cheap half has been priced at since the
amendment. **This sentence was wrong about the owner's store and stayed wrong for three days (corrected 2026-09-06).** It read *"The owner's own store is unaffected — it has $0.40
written"*. Measured: `inventory/prices.json` carries `{"basis": "market", "rule": "match",
"sub_threshold": "floor"}` and **no `threshold` key at all**, so `DEFAULT_CUTOFF` applies and
that store partitions at **$0.49**. What the entry is right about still holds — this moves
cards and not money, because the cheap half goes out at $0.49 either way — but the claim that
a real store had been checked was never true of this one, and nothing read it. (`sub_threshold:
"floor"` is the form D98 retired; it still parses and becomes a flat figure on its first edit,
which has not happened because that file has not been written since 2026-09-03.) And
`harness/tests/
t7_store_and_seams.py` asserts the shared fallback with the trade written beside it, where the
assertion that used to promise the opposite stood.

**What would reopen it**: an operator who wants the bar for LISTING to sit below the price cheap
cards go out at, which is a coherent thing to want — list everything over $0.40, sell the bulk at
$0.49 — and is the one case the one-variable rule refuses to express. Nobody has asked for it, and
the screen would need a way to say it that could not be mistaken for the pair drifting apart.

### What is NOT built, named rather than left to be discovered

**The merged emit is not built.** The owner asked for one CSV — across runs, across the listed/sub-threshold split, and across games, with a checkbox to peel off just the above-threshold rows. It is a real change to `pipeline/join.py`, `cli/resolve.py` and `cli/cmd_emit.py`, because **a merged file cannot be a concatenation of the CSVs already on disk**: the cap has to be recomputed across the union or it writes the over-push above into a file. Until it lands, `emit` stays per run and the press is **absent** on a worklist of more than one — absent rather than disabled, which is D33's rule for the control that spends applied to the one that writes files.

**Whether TCGplayer's Import to Staged accepts a file spanning two `Product Line`s is still unknown.** `cli/runs.py:import_listed_name` has said so since it was written and `fixtures/staged-import-accepted.csv` proves it for one line only. The owner has said they will test it. Nothing here depends on the answer.

**The two already-over-pushed SKUs are not corrected.** Fixing the arithmetic does not un-list what TCGplayer already holds; that is the owner's to reconcile.

**What would reopen this, and there are two.**

*A worklist that is never used with more than one run.* The remaining cost of the merge is the union and the cap arithmetic; if every sitting is one box forever, the honest simplification is the single-select again. The measurement is whether any `GET /pipeline/pricing` is answered with more than one run in it.

*A lot that genuinely wants its own policy.* `Corpus.overrides` keeps a per-run `rule`/`basis`/`sub_threshold` for exactly that, and **nothing writes one today** — no screen offers it and the migration never produces one. If the field is still empty after several sittings it is speculative generality and should go, taking `_agree_policy` and its refusal with it. If it fills up, D48's per-lot argument is stronger than this entry credits and the policy belongs back in the run.

**Amended 2026-09-03: `Corpus.overrides` has a writer, so the count above can be taken rather than argued.** `#/pricing` draws a per-run sub-threshold override beside the store's answer, written to `policy.per_run[<run>].sub_threshold` and drawn so it cannot be read as the store's. Neither branch of the condition is settled by building it; what changes is that a sitting now produces evidence. D98.

**Amended 2026-09-04: ONE FILE MEANS TWO WRITERS, AND THE SECOND ONE WAS SILENTLY REVERTING THE FIRST.**
`PUT /pricing` replaces the document wholesale — deliberately, so a key this screen has never
heard of survives it — and `#/pricing` autosaves the corpus object it took at mount. Put together,
any write that landed underneath an open pricing tab was undone by that tab's next keystroke, with
no error anywhere, on the one file in this product that holds money. Two tabs reach it; so does
`pkmnscan prices adopt --write` while one is open.

**The guard is a revision in the ENVELOPE and never in the document**, which is the part worth
reading twice. This screen decides "unsaved" by comparing the corpus it holds against the one it
last sent, BY IDENTITY. A revision inside the document would be rebuilt on every landed write and
would re-dirty the screen each time — unsaved to saving to unsaved, without end. So `GET /pricing`
answers a sibling `revision` (a short digest of the file), `PUT /pricing` compares it and refuses
`corpus_moved` / 409, and the write's receipt carries the new one so the operator's own second
keystroke is never stale against the file they just wrote.

**An ABSENT revision is allowed, and that is not a hole.** It means "did not read one", which is
the terminal user editing `inventory/prices.json` and PUTting it back. The guard exists for a
client that DID read one and is now behind — the only case that can destroy a write nobody saw
happen. Verified on the live server in all three states: stale refuses 409, current writes, absent
writes.

**Found by another branch rather than by this one**, on `claude/great-nightingale-37cf84`, where a
markdown re-prices every stale SKU at once and made the hazard acute — a stale PUT would have
undone the whole sweep. The bug is D86's own, not that feature's: it exists the moment the answer
became one file with one wholesale write.

**What is still NOT built.** The reconcile is per run: `cli/cmd_reconcile.py` scopes its diff to one run's `emitted_skus`, while the thing it diffs against — `store/master.py`'s `Listing` — is already per SKU across every box and run. The owner named the consequence: a full live TCGplayer export should reconcile across every emit, box and date at once, and report **both directions**, which is that command's own rule. It would be the first thing able to see the two SKUs this entry measured at `pushed: 6` against a cap of 4. Not built here.

---
