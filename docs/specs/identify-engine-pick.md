# Pick the identification engine for each run

**Status: DESIGN. Nothing is built.** D2 (identification is Haiku vision, end to end) carries the
owner's ruling. For each run, the owner picks who reads the cards: Haiku or the stock-photo matcher.
Haiku as the default is a proposal. The owner confirms it.

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
| `finish`: normal, holo, reverse holo or unknown | Cannot read foil. It reports `unknown` every time. | The finish ladder (D3, variants resolve by a fixed ladder) runs on the claim and the catalog. See below. |
| `confidence`: high, medium, low | Has a cosine margin and a similarity | The accept rule in section 3 sets `high` or `low`. |
| The set hint, as a prompt hint | The hint narrows the candidate pool | See the set rules below. |
| A read of any card, stock photo or not | Cannot place a card whose printing has no stock photo | Leaves that card unread. See below. |

**Finish (D3).** The prompt gives Haiku a finish field with an `unknown` member. The ladder already
treats no detection as a `detected_finish` of `None`. Rung 1 is the capture-time claim. Rung 2 is the
catalog row, when one condition remains. Rung 3 is detection. Rung 4 is review.

A matcher run never reaches rung 3. A card with no claim and more than one stocked finish ends at rung 4.
It lands in review with the existing reason `ambiguous_no_signal`. Review gets only cards the matcher accepted (`pipeline/variant.py`).
The matcher read it and the ladder could not finish it. No new reason code is needed.

Detection is weak evidence in any case. On box 2, the owner's measurement put its false contradictions at 42%.
That is why the ladder lets a claim outrank it. How many unclaimed multi-finish cards sit in the owner's boxes today is unmeasured.

**Set hints and widening (D76, a set hint's width is per game; D170, a Pokemon run names its sets).**
These rules scope the TCGplayer export fetch. They do not scope the Haiku read.
They stay unchanged for both engines, because both engines still join against the export.
The matcher adds one use of the same facts: the candidate pool.

**The rule: the matcher reads a card only when its whole candidate pool is complete.**

- **A hinted card.** Its pool is its hinted set. The set must be complete.
- **An unhinted card.** Its set is unknown, so its pool is every set of its game. Every one of those sets must be complete.
  If any set of the game is incomplete, the card is left unread. A per-set test would let the matcher accept a guess here.
- **Sealed product and anything with no number** is never matched. It has no card photo to compare.
- A set is complete when every numbered product in it has a stock image and a stored fingerprint (section 4).
- For Pokemon, D170 already makes every run name its sets. An unhinted Pokemon card cannot reach a matcher run.
  The pool is therefore never the whole Pokemon category.
- For Riftbound, "every set of its game" is every Riftbound group that holds a numbered product. Riftbound's export scope is `category`,
  so the pool and the export agree.
- A named set did not help accuracy in the spike. On Riftbound, pool-wide and set-only top-1 were both 98.7% (measured, first round).
  The rule exists for correctness when a set is incomplete. It does not exist for accuracy.

**Cards the matcher leaves unread.** A card is left unread in three cases. Its pool is incomplete. Its margin M is below the rule in section 3.
Its floor S is below the rule in section 3. The first rounds of the spike never tested the absent-photo case.
So a second test removed the true card's stock photos from the pool. Every answer is then wrong by construction.
Section 3 gives the result. For an unread card, the matcher run does this and nothing else:

1. It writes no identification. The card stays in the selection as needing identification.
2. The run goes on for the other cards. The preflight and the receipt both say how many cards were left unread, and why.
3. A matcher press never calls Anthropic. Nothing falls back on its own.
   A free press must never spend money by surprise. This is the owner's ruling.
4. The owner presses the paid read for those cards, by choice.

An unread card never goes to review. Review holds a card the matcher accepted and the finish ladder could not finish.
The run record keeps the reason and the top three candidates for each unread card. It writes no identification for it.

**How many of the owner's cards are eligible today** (measured, from the store opened read-only, and the stock-image
coverage listing). The store holds 3,503 cards with a SKU: 2,961 Riftbound and 542 Pokemon. 3,501 have a number.
2,802 carry a set hint and sit in a set whose numbered products all have an image URL.
The other 699 are unhinted Riftbound cards. Every one of the 8 Riftbound groups that holds a numbered product has an image URL for all of them.
So 3,501 of 3,503 (99.9%) meet the rule on image URLs. The two others have no number.
This is an upper bound. A set counts as complete only when every fingerprint is stored.
The fingerprint index run (section 4) confirms it and writes the per-set coverage table.

**Games the matcher refuses.** `pokemon_code` and `misc` have no stock photos.
Code cards follow their own rules. No code-card photo is ever embedded, copied or matched.
The matcher serves `pokemon`, `riftbound` and `one_piece`.

## 3. The accept rule

The matcher answers with its best card and two numbers. The margin M is the cosine of the best match
minus the cosine of the second. The floor S is the cosine of the best match.

**Accept only when all three hold:** the card's candidate pool is complete (section 2), M is at least 0.02, and S is
at least 0.755. An accepted card gets `confidence` of `high` in the identification record.
**Every other card is left unread** (section 2). It is not routed to review, and no `low` record is written for it.
No new join branch is built, because an unread card never reaches the join.

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
  For an unhinted card the pool is every set of the game, so one incomplete set blocks every unhinted card of that game.
- The spike did not demonstrate 99.5% precision. It split the 500 cards at random 20 times.
  Each time it fit the margin on one half and scored the other half.
  Marqo-B accepted 99% of cards at a mean precision of 99.4% and a worst split of 98.8% (measured).
  A half of 250 cards cannot show 99.5%.
- The values 0.02 and 0.755 were chosen on the same 500 cards. They are a starting point, not a result.
  Both values live in one constant, beside the eval that produced them.
  The record also carries the model file hash.
- **Build-lane gate: a held-out check confirms the thresholds before adoption.**
  The owner supplies photographs that the spike never saw, and the eval scores them with the fixed constants.
  The build lane does not ship the matcher pick until that check reports no wrong answer among the accepted cards,
  and reports the share accepted. A failed check lowers the constants or ends the build. It never edits the held-out set.
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
Only `make catalog-refresh` renews it. A set released after the snapshot has no row (DEBT44, the vendored tree lags a new set).
The pool index records the snapshot it was built from, so a stale index is visible.

**Complete pool.** A set is complete when every numbered product in its tcgcsv group, or in its vendored
set file, has an image and a stored fingerprint that matches the current model file. Section 2 says which
cards need which sets. The preflight names each incomplete set, and the cards it leaves unread because of it.

**The index.** One stock image becomes one vector of 768 floats, which is 3 KB.
The spike's 1,365 images make about 4.2 MB (measured). The index lives under `inventory/`, beside the other
derived stores. It is keyed by image URL and model hash.

Building the index needs the image bytes once. D301 (stock photos are hotlinked, never mirrored) is amended
on the owner's word for this one read. The server reads each stock image, computes its fingerprint, and drops the bytes.
Only the fingerprint is stored. A fingerprint records the model file hash and the source URL.
**A change of model rebuilds every fingerprint.** An old fingerprint never meets a new model.
The read is the matcher's own step. The owner starts it from a screen (section 6). The spike fetched 1,365 images
at a polite pace, which took a few minutes (measured).

**A matcher press never builds or refreshes fingerprints.** It reads only fingerprints that are already stored.
A fingerprint is stale when the model file hash differs, or when the set now holds a numbered product with no fingerprint.
A stale or missing fingerprint makes its set incomplete, so the cards that need that set are left unread.
Only the owner's press on the fingerprint control (section 6) reads images, and it shows its size first.
A matcher press never downloads, and it never spends money.

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

**The source is a release asset of `shivinate7/banchi`**, with the file's SHA-256 pinned in code.
It is one download of 372 MB. The owner chose this source. Marqo's license is Apache-2.0, which allows
redistribution with a notice. A legal read is unmeasured. The release does not exist yet.
The owner creates it, on the owner's word, when the build lane needs it. This PR creates no release.
The export script stays the developer's way to rebuild the file. It needs torch in a throwaway venv.

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
Haiku as the default pick is a proposal. The owner confirms it.
It is one term of the press, so the selection stays the cards the operator named (D180, a press names the cards it covers).
Nothing else about selection changes.

**What each pick says.** The labels are the operator's words.
D196 (no screen string names a mechanism) rules out model names on screen, with one named exception.
The owner's word: plain words on the control, and the model name in a hover tooltip.
The tooltip on the matcher pick names the model. It is the constant `MATCHER_NAME_TOOLTIP`, exported from `app/src/engines.ts`.
D196 records the exception. The `no mechanism on screen` row exempts that one string and reads it from the constant.
The build lane must export the constant under that name, or the exemption finds nothing.

| Pick | Label | Line under it |
|---|---|---|
| `haiku` | Read from the photo | Reads the name, the number and the foil. Costs about the quoted amount. |
| `marqo-b` | Match to stock photos | Free. Needs a stock photo for each card. Cannot tell foil from normal. Cards it is unsure of are left unread, and you can read them with the paid read. |

**A tooltip on each pick.** Both picks carry a `title` tooltip. The matcher's tooltip is `MATCHER_NAME_TOOLTIP` and names the model.
The Haiku pick's tooltip is a plain sentence about what the read does. It carries no model name,
because the owner's exception is one string (D196). If the owner wants the Haiku name in its tooltip, that needs a second
named exception. This is an open point for the owner.

- The cost line comes from the free preflight. `POST /pipeline/preflight` takes the engine.
  It returns a dollar amount for Haiku and zero for the matcher.
- The accuracy line carries no percentage. The two figures do not compare.
  The line names outcomes: what the engine reads, what it cannot read, and where doubt goes.
- The matcher quote adds three counts. They are the cards it can match, the cards it must leave unread because
  their pool is incomplete, and the cards already answered. A card can also be left unread after the read, when its margin is too small.
  The quote cannot count those, so it says so. It also adds the setup state.
- **A Haiku press reads the unread cards only, by default.** A selection can hold cards the matcher accepted.
  Those are answered. The Haiku preflight quote names the count it would bill, and that count excludes them.
  Reading them again is an explicit choice, a second line on the quote: "Also read again the 412 cards that matching decided".
  That line shows its own cost, and it is off until the owner turns it on.
- The press button names the cards, as D180 requires. It reads "Match 412 cards, free" for the matcher.
  It reads "Read 412 cards, about $0.45" for Haiku.
- When the matcher is picked, the crop and size choice is hidden. The matcher always uses the same crop.
- Haiku is the default pick each time the composer opens. The pick is not stored on the device.

**Fingerprint control.** The runs sheet has one card named "Prepare matching" with two parts. Each part shows its size first and
starts only on the owner's press.

- The model file: 372 MB, a download (section 5).
- The fingerprints: the number of stock images to read, one read each, and how many sets are complete today.
  A press reads the missing and stale images, in memory, and stores the fingerprints (D301, amended).
  It reports sets complete and sets incomplete when it ends. Nothing else starts it.

**The receipt.** The run record shows the engine. It then shows three counts: matched, left unread, and already answered.
A matched card the finish ladder cannot finish goes to Review as before. The run line reads, for example,
"Matched 412 cards. 9 were left unread for a paid read. 37 of the matched cards need a finish answer in Review."

The manifest records the engine in `flags`. It records the model hash and the pool snapshot in the existing
`model` field and a new run field. A review queue entry carries the engine that read it, beside the existing read fields.
D258 (identity follows the SKU) keeps those read fields as evidence.

**The wire.** `RunSend` gains `engine`, default `haiku`. `onTheWire` in `app/src/server.ts` sends it.
`app/src/types.ts` carries its shape. `POST /pipeline/identify` keeps its `confirm` field for both engines.
One gate stays one press. The CLI takes `--engine`. Two free routes serve setup.
One reports the matcher state. One downloads on a `confirm`.

**A route is not a feature (hard rule).** The build is done only when the route, the `server.ts` function
and this control exist, and a human can reach them. Where it writes, done also needs a receipt and a way back.
The way back is the explicit re-read choice on a Haiku press. It overwrites a matcher answer (section 7).

## 7. One path for both engines

**The seam is `identify/batch.py`.** A Haiku run returns a `BatchRun`.
Its `outcomes` map a card to an `Outcome`. An `Outcome` carries a status, a parsed `Identification` and an error.
`cmd_identify._apply` reads them. The matcher is a new module, `identify/match.py`.
It returns the same `BatchRun` shape, with zero usage. Everything after `_apply` is unchanged.

- The run payload records the same `identification` dictionary: name, number, printed total, finish `unknown`, and confidence.
- Collect has nothing to collect. A matcher run finishes in its child process. The run directory is polled as before.
- `join` reads the same `IdentifiedCard`. A matcher record always carries `high`, because a card the matcher doubts is never written.
  The finish ladder still routes by its own reasons. `emit` is untouched.
- The run is a detached child, like a Haiku run (D33, every pipeline step is reachable from a screen).
  It outlives a closed tab or a server restart.
- A matcher run takes the same claim on its cards as a Haiku run (D174, the claim that stops two live presses reading one card).
  No money is at stake. The claim still stops two engines from writing one card at once.

**The cache must learn the engine.** Today `store/cache.py`'s `CacheEntry` holds a prompt fingerprint.
It holds nothing about the reader. `_adopt_cached` adopts any entry.
A stale entry is kept unless the press asks to re-identify stale answers.
Without a change, a Haiku press would adopt a matcher answer as paid for. So:

- Each entry carries `engine`. An entry with no `engine` is `haiku`.
- A Haiku press adopts Haiku entries, human-cleared entries and matcher entries as answered. It does not bill them.
- The explicit re-read choice (section 6) overwrites matcher entries only. It never overwrites a human-cleared entry.
- A matcher press never overwrites any entry. It skips every answered card.
- The way back from a matcher answer is the explicit re-read choice.
- The matcher's fingerprint is the model file hash, the pool snapshot and the thresholds.

**Tests the build must add.**

- A seam test with stubbed embeddings, so CI needs no model.
- A cache test for the four rules above.
- The parity script.
- The spike's eval, as a script that runs on demand. It is not in `make check`, because it needs the owner's photographs.
- T1 stays the Haiku gate.

## 8. The owner's rulings

- A card the matcher cannot accept is left unread and stays in the selection. It never goes to review. Nothing falls back on its own (sections 2 and 3).
- The matcher reads a card only when its whole candidate pool is complete (section 2).
- D301 is amended for one fingerprint read of each stock image. A model change rebuilds every fingerprint (section 4).
- The model file is a release asset of `shivinate7/banchi`, with a pinned hash, downloaded when the owner presses a control (section 5).
- The control uses plain words. The model name sits in one hover tooltip, as a named exception in D196 (section 6).
- Before adoption, a held-out check confirms the thresholds. That is a build-lane gate (section 3).
- Process only: the build starts on fp32. The build lane commits the eval scripts.

**Open for the owner.** Whether Haiku is the default pick. Whether the Haiku pick's tooltip may name Haiku, as a second named exception.
