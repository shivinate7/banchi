# Pick the identification engine for each run

**Status: DESIGN. Nothing is built.** D2 (identification is Haiku vision, end to end) carries the
owner's ruling. For each run, the owner picks who reads the cards: Haiku or the stock-photo matcher.
Haiku stays the default.

This spec answers six questions. What can the matcher not do? When may it decide? Where do its
candidates come from? What does it weigh? Where does the pick sit on screen? How does the pipeline
stay one path? Every figure is marked measured or unmeasured.

**The two engines.** `haiku` is the existing paid read. `marqo-b` is Marqo ecommerce-B, an open
image-embedding model, run on onnxruntime. It embeds the cropped card photo. It ranks that vector
against the embedded stock photos of the cards the run could hold. The wire names are `haiku` and
`marqo-b`. The screen uses the operator's words (section 6).

## 1. What the spike measured

The spike ran on the owner's store, read-only. It used 500 real photographs: 300 Riftbound and 200
Pokemon. Each card has a confirmed SKU. The crop is the one `detect_card` and `registered_card`
already cut. `detect_card` found the card in 500 of 500 photographs.
The eval scripts and raw results live in a scratchpad. They are not in the repo.

- Marqo-B ranks the right card first for 99.2% of the 500 (measured). Riftbound 98.7%, Pokemon 100%.
- It ranks the right card in its first five for 99.8% (measured).
- Near-duplicates share a name with another number in the same set. Marqo-B is right for 99.2% of them (measured).
- The right art with the wrong printing wins for 0.2% of all cards. That is 0.8% of near-duplicates (measured).
- A 256-bit perceptual hash ranks the right card first for 51% (measured). It is not an engine.
- Pokemon is the easy case. The photos cover one set and 109 distinct printings.
  Photos of one printing can sit on both sides of a split. Treat the 100% as optimistic (measured).
- One Piece is unmeasured. The store holds no One Piece card.
- Haiku's own figure is T1: 97.1% on 150 official flat images, scored on name and join key.
  The two figures do not compare. The images differ, and the tasks differ.
  Nobody has run Haiku on these 500 photographs. DEBT63 (T1 never compared with Scan & Identify) is the same gap.
- Haiku costs about $0.0011 a card (measured from T1 usage: 295,485 input and 5,697 output tokens for 150 images).
  The owner's 3,503 identified cards would have cost about $3.80 in all.
  Cost is not the reason for the matcher. The reasons are speed with no batch wait, no network for the read, and a second opinion.

## 2. What the Haiku read gives that the matcher does not

| Haiku gives | The matcher | A matcher run does |
|---|---|---|
| Name read from the print | Takes the name from the matched catalog entry | Writes the same fields. No gap when the card is in the pool. |
| Collector `number` and `printed_total`, as printed | Takes both from the matched entry: the tcgcsv `Number` cell, or the vendored set file | Builds the join key with `number_index_key` from catalog data. It is exact. No gap when the card is in the pool. |
| `finish`: normal, holo, reverse holo or unknown | Cannot read foil. It reports `unknown` every time. | The finish ladder (D3) runs on the claim and the catalog. See below. |
| `confidence`: high, medium, low | Has a cosine margin and a similarity | The accept rule in section 3 sets `high` or `low`. |
| The set hint, as a prompt hint | The hint narrows the candidate pool | See the set rules below. |
| A read of any card, stock photo or not | Cannot place a card whose printing has no stock photo | Never guesses that card. See below and section 4. |

**Finish (D3).** The prompt gives Haiku a finish field with an `unknown` member. The ladder already
treats no detection as a `detected_finish` of `None`. Rung 1 is the capture-time claim. Rung 2 is the
catalog row, when one condition remains. Rung 3 is detection. Rung 4 is review.

A matcher run never reaches rung 3. A card with no claim and more than one stocked finish ends at rung 4.
It lands in review with the existing reason `ambiguous_no_signal` (`pipeline/variant.py`).
No new reason code is needed.

Detection is weak evidence in any case. On box 2, the owner's measurement put its false contradictions at 42%.
That is why the ladder lets a claim outrank it. How many unclaimed multi-finish cards sit in the owner's boxes today is unmeasured.

**Set hints and widening (D76, D170).** These rules scope the TCGplayer export fetch. They do not scope the Haiku read.
They stay unchanged for both engines, because both engines still join against the export.
The matcher adds one use of the same facts: the candidate pool.

- A Pokemon matcher run names its sets, as D170 already requires.
  `_scope_for_run` is the one function that decides this. It refuses a run that would widen.
  That refusal also protects the pool, so the pool is never the whole category.
- A Riftbound matcher run uses every Riftbound set that has stock photos.
  That is 1,177 images across the store's four Riftbound sets in the spike (measured).
  Riftbound's export scope is `category`, so the pool and the export agree.
- A named set did not help accuracy in the spike. On Riftbound, pool-wide and set-only top-1 were both 98.7% (measured, first round).
  The pool rule exists for the size of the Pokemon category. It does not exist for accuracy.

**Cards with no stock image.** Two kinds exist. Sealed product has no number and no card photo.
A numbered printing can also lack one. The first rounds of the spike never tested this case.
So a second test removed the true card's stock photos from the pool. Every answer is then wrong by construction.
Section 3 gives the result. Per card, the matcher run does this and nothing else:

1. If the card's set has no complete pool, the card is left unread. It stays in the selection as needing identification.
2. The preflight says how many cards are left, and why. The owner presses Haiku for them.
3. A matcher press never calls Anthropic. A free press must never spend money by surprise.

A card could go to review with its photo instead. That is an open question for the owner.

**Games the matcher refuses.** `pokemon_code` and `misc` have no stock photos.
Code cards follow their own rules. No code-card photo is ever embedded, copied or matched.
The matcher serves `pokemon`, `riftbound` and `one_piece`.

## 3. The accept rule

The matcher answers with its best card and two numbers. The margin M is the cosine of the best match
minus the cosine of the second. The floor S is the cosine of the best match.

**Accept only when all three hold:** the card's set pool is complete, M is at least 0.02, and S is
at least 0.755. Everything else gets `confidence` of `low` in the same identification record.
The existing routing gate (`review_below`, set to low by default) sends it to the review queue with
its photo. No new join branch is built. The record also carries the top three candidates.
The queue can draw them as evidence.

Measured on the 500 photographs, Marqo-B:

| Rule | Right cards accepted | Wrong among accepted | Wrong answers accepted when the true card has no stock photo |
|---|---|---|---|
| M at least 0.0057 (the 99.5% fit) | 99.4% | 2 of 497 | 76.4% |
| M at least 0.02 | 96.8% | 1 of 484 | 41.6% |
| M at least 0.02 and S at least 0.755 | 91.8% | 0 of 459 | 12.2% |
| M at least 0.02 and S at least 0.80 | 75.4% | 0 of 377 | 4.8% |

- The margin alone filters almost nothing. Marqo-B errs on 4 of 500 cards.
  It also accepts three of four wrong answers when the true card is absent.
- The right art with the wrong printing is the cause. When a printing is missing, its sibling wins with a high margin.
  Among the wrong accepted answers in the first row, 96 were siblings with the same name.
- A complete pool is therefore a hard precondition. A threshold cannot replace it.
  Even with both thresholds, 12.2% of absent-truth answers pass. Completeness removes that case.
- The spike did not demonstrate 99.5% precision. It split the 500 cards at random 20 times.
  Each time it fit the margin on one half and scored the other half.
  Marqo-B accepted 99% of cards at a mean precision of 99.4% and a worst split of 98.8% (measured).
  A half of 250 cards cannot show 99.5%.
- The values 0.02 and 0.755 were chosen on the same 500 cards. They are a starting point, not a result.
  A held-out set of photographs must confirm them before the owner adopts the engine.
  Both values live in one constant, beside the eval that produced them.
  The record also carries the model file hash.
- Rotation retries do not help Marqo-B. Take the best of four rotations. Its top-1 on 13 sideways battlefield cards falls from 85% to 77%.
  Its top-1 on upright Riftbound cards stays at 99% (measured). The retry lowered upright top-1 for each of the nine other models in the first round of ten.
  Only CLIP L/14 gained, from 92% to 100% on the 13 sideways cards. The matcher does not retry.
- Foil glare does not hurt Marqo-B. It is right for 99% of the brightest 15% of crops in each game, and for 99% of the rest (measured).

## 4. The candidate pool

**Where the images come from.** `pipeline/stockimages.py` resolves a stock image URL for a card.
Riftbound and One Piece use `imageUrl` from the tcgcsv product groups. Those images are 200 pixels wide.
Pokemon uses `images.small` from the vendored `vendor/pokemon-tcg-data/` tree. Those are 245 pixels wide.
D301 (stock photos are hotlinked, never mirrored) governs how they are used today.

**How many printings lack one** (measured, from the store's `skus` table, through the same resolver):

| Game | Printings | No stock image | SKUs | SKUs with none |
|---|---|---|---|---|
| Riftbound | 1,453 | 10 (0.7%), all with no number | 10,197 | 96 |
| Pokemon | 329 | 76 (23.1%), 30 with no number | 1,815 | 200 |
| One Piece | 37 | 11 (29.7%), all with no number | 43 | 17 |

- The cause of the 46 numbered Pokemon printings with no image is unmeasured.
- Coverage is higher for the cards the owner holds. 1,072 of 1,079 Riftbound photographs map to a catalog entry (99.4%).
  All 109 distinct Pokemon printings map (measured).

**How fresh they are.** tcgcsv answers come from `Market`. They are cached for `TCGCSV_TTL_SECONDS`, which is one hour.
The vendored Pokemon tree is a committed snapshot. `vendor/pokemon-tcg-data/SNAPSHOT.json` records when it was taken.
Only `make catalog-refresh` renews it. A set released after the snapshot has no row (DEBT44).
The pool index records the snapshot it was built from, so a stale index is visible.

**Complete pool.** A set pool is complete when every numbered product in its tcgcsv group, or in its
vendored set file, has an image. A scope that includes an incomplete set is not eligible for the matcher.
The preflight names each such set.

**The index.** One stock image becomes one vector of 768 floats, which is 3 KB.
The spike's 1,365 images make about 4.2 MB (measured). The index lives under `inventory/`, beside the other
derived stores. It is keyed by image URL and model hash.

Building the index needs the image bytes once. That conflicts with D301, which says this repo never
downloads or stores the bytes. The bytes would be held in memory and dropped. Only the vectors are stored.
This needs the owner's word. The spike fetched 1,365 images at a polite pace, which took a few minutes (measured).

## 5. Weight

No ML dependency is installed today. `requirements.txt` holds ruff, anthropic, Pillow, numpy and zxing-cpp.

**The runtime is onnxruntime and nothing else.** The owner chose it as the app's one model runtime.
It goes in first for the crop model. The matcher reuses it.

- The installed size of onnxruntime 1.30.0 on this Mac is 80 MB (measured).
  It requires numpy, packaging, protobuf and flatbuffers. numpy and Pillow are already pinned.
- Not added: torch, torchvision, open_clip, transformers, timm and any tokenizer.
  The text tower is never used.
- Preprocessing uses Pillow and numpy only. Resize to 224 by 224 with a bicubic filter. Scale to 0 through 1.
  Subtract 0.5, divide by 0.5, and put the channel axis first.
  The parity check below proves that this matches the torch path.

**The model file.** Only the image tower is exported. It has 92.9 million parameters (measured).

| File | Size | Top-1 on the 500 | Latency | Parity with torch |
|---|---|---|---|---|
| ONNX fp32 | 372 MB | 99.2%, the same cards as torch | 34 ms | cosine at least 0.999999 on every vector |
| ONNX int8, dynamic quantization | 94 MB | 99.4% | 32 ms | cosine mean 0.994, minimum 0.970 |

All rows are measured. Latency is one photo on four threads, on a busy M5 Pro. Allow 20% either way.
The crop adds 70 to 120 ms. A card costs about 0.15 seconds, so 500 cards take about 75 seconds.
int8 saves disk and no time, and it moves the cosines. It needs its own threshold fit. Start with fp32.

**The export path.** This is a one-off developer step. Torch is needed here only.
It runs in a throwaway venv and never enters `requirements.txt`.

1. Load `hf-hub:Marqo/marqo-ecommerce-embeddings-B` with open_clip.
2. Wrap `model.visual` and an L2 normalization in one module.
3. Call `torch.onnx.export` with opset 17, input `pixels`, output `embedding`, and a dynamic batch axis.
4. Record the SHA-256 of the file. The build pins it in code.

The spike ran this path, and it worked. The committed script will be `scripts/export-matcher-model.py`.
It is not part of this design PR.

**The parity check.** A script must pass before the app accepts a model file:

- Embed 50 fixed stock images. Compare each to a stored reference vector. Each cosine must be at least 0.9999.
- Rank a fixed sample of 100 photographs against a small fixed pool. Each top-1 card must equal the stored answer.
- The check records the file hash. A changed file fails until someone regenerates the reference on purpose.

The spike ran the same comparison on all 500 photographs and all 1,365 stock images.
It gave the numbers in the table above.

**The first-run download and who triggers it.** A download needs the owner's word.
The owner gives it by pressing a button on a screen. The runs sheet shows a card named "Prepare matching".
It states the size, 372 MB, and the source. A press starts the download and checks the hash.
Until the download finishes, the matcher pick is dimmed with one sentence. Nothing downloads on its own.

Two sources are possible. The owner chooses:

- A. A converted file, hosted as a release asset of this repo, with the hash pinned in code.
  It is one download of 372 MB. Marqo's license is Apache-2.0, which allows redistribution with a notice.
  A legal read is unmeasured.
- B. The owner runs the export script. That needs torch (574 MB installed) and the original 775 MB weights.
  Both are deleted afterward.

Recommendation: A. It keeps the app's runtime to onnxruntime, and it needs one 372 MB download.

**Where the runtime loads.** The capture server stays free of ML code. `server/pipeline_routes.py` is stdlib only.
onnxruntime loads only in the detached child that runs the identify command. The Anthropic client loads there too.

**Licenses.** Marqo-B is Apache-2.0 (its model card).
The card lists Google Shopping and Amazon evaluation sets. It names no TCGplayer data.
That is not proof the model saw none. It is unverified.
The spike also measured CLIP L/14 (Apache-2.0), SigLIP (Apache-2.0), EVA02-B (MIT) and DINOv2 (Apache-2.0).
jina-clip-v2 is CC-BY-NC-4.0, which rules it out for a store. It also failed to load on the installed transformers.

**Other models measured** (top-1 on the same 500, measured): CLIP L/14 99.2% at 187 ms and 1.7 GB.
SigLIP-B 98.4% at 45 ms. Marqo-L 98.4% at 164 ms. SigLIP2-B 95.8%. SigLIP2-so400m 95.2% at 205 ms.
EVA02-B 92.6%. DINOv2-b 90.2%. DINOv2-s 88.8%.
Marqo-B is the best on accuracy for its cost. CLIP L/14 ties it on accuracy at about five times the latency.

## 6. The control

**Where.** The runs sheet. `Runs.tsx` draws `RunsComposer`, the staged composer for the one press that can spend money.
Its second stage, "One reading for this press", already holds a per-press choice about how photographs are read.
The pick is a segmented control above that choice, labeled "Who reads these cards".
It is one term of the press, so the selection stays the cards the operator named (D180, a press names the cards it covers).
Nothing else about selection changes.

**What each pick says.** The words are the operator's words.
D196 (no screen string names a mechanism) rules out model names and the word "model".

| Pick | Label | Line under it |
|---|---|---|
| `haiku` | Read from the photo | Reads the name, the number and the foil. Costs about the quoted amount. |
| `marqo-b` | Match to stock photos | Free. Needs a stock photo for each card. Cannot tell foil from normal. Cards it is unsure of go to Review with their photo. |

- The cost line comes from the free preflight. `POST /pipeline/preflight` takes the engine.
  It returns a dollar amount for Haiku and zero for the matcher.
- The accuracy line carries no percentage. The two figures do not compare.
  The line names outcomes: what the engine reads, what it cannot read, and where doubt goes.
- The matcher quote adds three counts. They are the cards it can match, the cards it must leave because
  their set has no complete pool, and the cards already answered. It also adds the setup state.
- The press button names the cards, as D180 requires. It reads "Match 412 cards, free" for the matcher.
  It reads "Read 412 cards, about $0.45" for Haiku.
- When the matcher is picked, the crop and size choice is hidden. The matcher always uses the same crop.
- Haiku is the default pick each time the composer opens. The pick is not stored on the device.

**The receipt.** The run record shows the engine. It then shows four counts: matched and decided, sent to Review,
left unread, and already answered. The run line reads, for example, "Matched 412 cards. 37 went to Review. 9 were left for a Haiku read."

The manifest records the engine in `flags`. It records the model hash and the pool snapshot in the existing
`model` field and a new run field. A review queue entry carries the engine that read it, beside the existing read fields.
D258 (identity follows the SKU) keeps those read fields as evidence.

**The wire.** `RunSend` gains `engine`, default `haiku`. `onTheWire` in `app/src/server.ts` sends it.
`app/src/types.ts` carries its shape. `POST /pipeline/identify` keeps its `confirm` field for both engines.
One gate stays one press. The CLI takes `--engine`. Two free routes serve setup.
One reports the matcher state. One downloads on a `confirm`.

**A route is not a feature (hard rule).** The build is done only when the route, the `server.ts` function
and this control exist, and a human can reach them. Where it writes, done also needs a receipt and a way back.
The way back is a Haiku press. It overwrites a matcher answer (section 7).

## 7. One path for both engines

**The seam is `identify/batch.py`.** A Haiku run returns a `BatchRun`.
Its `outcomes` map a card to an `Outcome`. An `Outcome` carries a status, a parsed `Identification` and an error.
`cmd_identify._apply` reads them. The matcher is a new module, `identify/match.py`.
It returns the same `BatchRun` shape, with zero usage. Everything after `_apply` is unchanged.

- The run payload records the same `identification` dictionary: name, number, printed total, finish `unknown`, and confidence.
- Collect has nothing to collect. A matcher run finishes in its child process. The run directory is polled as before.
- `join` reads the same `IdentifiedCard`. The routing gate sends `low` to review. `emit` is untouched.
- The run is a detached child, like a Haiku run (D33, every pipeline step is reachable from a screen).
  It outlives a closed tab or a server restart.
- A matcher run takes the same claim on its cards as a Haiku run (D174, the claim that stops two live presses reading one card).
  No money is at stake. The claim still stops two engines from writing one card at once.

**The cache must learn the engine.** Today `store/cache.py`'s `CacheEntry` holds a prompt fingerprint.
It holds nothing about the reader. `_adopt_cached` adopts any entry.
A stale entry is kept unless the press asks to re-identify stale answers.
Without a change, a Haiku press would adopt a matcher answer as paid for. So:

- Each entry carries `engine`. An entry with no `engine` is `haiku`.
- A Haiku press adopts only Haiku entries and human-cleared entries.
- A matcher press never overwrites a Haiku entry or a human-cleared entry. It skips them as answered.
- A Haiku press overwrites a matcher entry. That is the way back.
- The matcher's fingerprint is the model file hash, the pool snapshot and the thresholds.

**Tests the build must add.**

- A seam test with stubbed embeddings, so CI needs no model.
- A cache test for the four rules above.
- The parity script.
- The spike's eval, as a script that runs on demand. It is not in `make check`, because it needs the owner's photographs.
- T1 stays the Haiku gate.

## 8. Not decided here

The owner decides these. The report that carried this PR lists each one as options with a recommendation.

- What the matcher does for a card with no stock photo.
- Whether model names show anywhere on screen.
- Whether D301 may be amended so that the app reads image bytes once, to build the index.
- Where the converted model file comes from.
- Whether int8 is worth its own threshold fit.
- Whether the spike's eval is committed.
