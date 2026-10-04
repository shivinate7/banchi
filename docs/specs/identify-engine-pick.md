# Pick the identification engine for each run

**Status: phase 1 is built (the per-run picker, the free read, the second look). Phase 2, the background reader (section 8), is built and off by default. Its two ship gates are measured and wait for the owner.** D2 (identification is Haiku vision, end to end) carries the
owner's ruling. For each run, the owner picks who reads the cards: Haiku or the stock-photo matcher.
The free read is the default pick, on the owner's ruling.

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
| A read of any card, stock photo or not | Cannot place a card whose printing has no stock photo | Does not accept that card. The paid read gives it a second look. See below. |

**Finish (D3).** The prompt gives Haiku a finish field with an `unknown` member. The ladder already
treats no detection as a `detected_finish` of `None`. Rung 1 is the capture-time claim. Rung 2 is the
catalog row, when one condition remains. Rung 3 is detection. Rung 4 is review.

A matcher run never reaches rung 3. A card with no claim and more than one stocked finish ends at rung 4.
It lands in review with the existing reason `ambiguous_no_signal`. Review gets the cards the matcher accepted that the ladder could not finish (`pipeline/variant.py`).
It also gets every second-look card (section 2). No new reason code is needed for the first kind.

Detection is weak evidence in any case. On box 2, the owner's measurement put its false contradictions at 42%.
That is why the ladder lets a claim outrank it. How many unclaimed multi-finish cards sit in the owner's boxes today is unmeasured.

**Set hints and widening (D76, a set hint's width is per game; D170, a Pokemon run names its sets).**
These rules scope the TCGplayer export fetch. They do not scope the Haiku read.
They stay unchanged for both engines, because both engines still join against the export.
The matcher adds one use of the same facts: the candidate pool.

**The rule: a printing with no stock image blocks only a match that shares its card name.**
The fingerprint index (section 4) lists every numbered product of every set it covers, with or without a photo.
The pool is the fingerprinted printings of the sets that apply to the card.

- **A hinted card.** Its pool is its hinted set.
- **An unhinted card.** Its set is unknown, so its pool is every set of its game, except the promo sets (below).
- **The look-alike guard.** After the match, the matcher compares the best answer's card name with the names of the pool's no-image printings.
  If the best answer shares a name with one, the card is not accepted. Every other card stays eligible, whatever else is missing from its set.
- **The premise, measured:** a no-image printing loses to its same-name twin. When the true printing has no photo, its sibling with the same name wins.
  In the absent-photo test, 96 of the wrong accepted answers were same-name siblings (section 3). The held-out check (section 3) tests the guard.
- **Sealed product and anything with no number** is never matched. It has no card photo to compare.
- **Promo sets are left out of the pool.** A promo set is a set whose name holds "Promo".
  A card hinted into a promo set is never matched. It goes to the second look.
- **A pool of one printing** (a set or a card name with a single printing) needs no change. The guard checks the best answer's name against the no-image names, so it still works.
  A one-printing pool can only mislead when its one printing has no photo, and then the guard blocks the name.
- **A set the index does not cover** cannot be guarded. Every card that needs it goes to the second look until the fingerprint refresh press covers it.
- For Pokemon, D170 already makes every run name its sets. An unhinted Pokemon card cannot reach a matcher run.
  The pool is therefore never the whole Pokemon category.
- For Riftbound, "every set of its game" is every Riftbound group that holds a numbered product. Riftbound's export scope is `category`,
  so the pool and the export agree.
- A named set did not help accuracy in the spike. On Riftbound, pool-wide and set-only top-1 were both 98.7% (measured, first round).
  The pool rule exists for the absent-photo case. It does not exist for accuracy.

**Cards the matcher does not accept.** The owner's flow: *"we have the free one do all first and then for those it
finds under a threshold of accuracy they get a second look by haiku and then it reaches my queue. so haiku isnt on all of them just the low con"*.
One press runs both reads. The matcher reads every selected card first. Four things stop it accepting a card.
The look-alike guard fires. Its pool is not complete, so the guard cannot run. Its margin M is below the rule in section 3.
Its floor S is below the rule in section 3. The first rounds of the spike never tested the absent-photo case.
So a second test removed the true card's stock photos from the pool. Every answer is then wrong by construction.
Section 3 gives the result. For a card the matcher does not accept, the same press does this:

1. The matcher writes no identification for it.
2. The press sends the card to a Haiku batch at once. This is the second look. Only these cards are sent.
3. Haiku's answer is not saved as the card's identity. It goes to the review queue.
   The cache entry for that answer carries the second-look marker. A later press that adopts the entry from the cache keeps the hold.
   A person's answer in review is what releases it.
   The entry shows the photo, Haiku's answer and the matcher's top pick. A person decides.
4. The run record keeps the matcher's reason and top pick for each such card, beside Haiku's answer.
   The receipt says how many cards the matcher took and how many went to the second look.

This replaces the earlier rule that left such cards unread until a separate paid press. Nothing is guessed at any step.
A card Haiku answers wrongly cannot reach a listing, because a person sees it first.

**Money is named before it is spent (D180).** The quote states how many cards the matcher will take free.
It states how many go to the second look, and what that costs. The press needs the same confirm as a paid send.
When the index is ready, the preflight runs the matcher over the selection and counts the cards. The figure is measured.
A dry run over more than 200 cards does not run the matcher, because the screen's request waits for it. The real press always counts, in its own child.
Whenever the quote is not measured, it uses 40% as the unaccepted share and says "estimated". The held-out check measured 37.5%, with a 95% upper bound of 39.2%.
So the estimate rounds up and never understates. It is also never under the count of cards the pool rules already send to the second look.
The background reader (section 8) stays free. It never spends. A card it cannot accept waits for a press.

**The owner's word on promos: "i have no promos".** Printings with no stock image that are promos are left out of the matcher's pool.
Unhinted Riftbound cards match against the main sets. A promo card is never read by the matcher. It goes to the paid read.

**The premise holds today** (measured, store opened read-only). The check joined the `cards` table to the `skus` table.
It covered all 2,961 Riftbound cards the store has held in any state, which are 806 distinct SKUs.

- None sits in a set named "Promo". Every card sits in Origins, Spiritforged, Unleashed or Vendetta.
- None has "promo", "prerelease", "judge", "serial", "signature" or "overnumbered" in its name, set, product, printing or rarity.
- None is one of the 229 products that have no photo.

**The known risk, in one line.** If a promo enters the store, the matcher could read it as its main-set twin.
Organized Play promos repeat main-set numbers.

**What catches it.** The promo guard is cheap. At queue build and at preflight, the run asks the store one question:
does any held card sit in a promo set of this game? If yes, unhinted cards of that game go to the second look.
It is one query on `cards.set_name`, which has an index. It is built (`held_promo_games` in `identify/match.py`) and runs once per read and per preflight.
The reason code is `promo_held`. A store that cannot be read counts as holding a promo in every game. A promo that is hinted into its promo set goes to the second look without it.
A promo whose set name does not hold "Promo" is not caught. A card whose `set_name` was never filled in is not seen. Both are open items.

**The 229 products with no photo** (measured). The CDN answers 403 with an XML error for every size of each image URL.
The working images answer 200. CloudFront answers 403 for a key that does not exist. So each is a product with a URL and no photo.
They count as "no stock image". They sit in the index as no-image printings, and the guard reads their names.

| Group | Products | What they are |
|---|---|---|
| Organized Play Promotional Cards | 174 | Promos. Left out of the pool by the owner's rule. |
| Promotional Cards | 6 | Promos. Left out of the pool. |
| Radiance | 11 | An unreleased set, due in about a month. No special case: its names are blocked by the guard until images exist. |
| Spiritforged, Unleashed, Vendetta | 38 | Runes (numbers such as R01b) and Tokens (numbers such as T01 // T05). Not promos. Not broken links. |

- The owner holds 96 Runes (measured). Their printings all have photos. None of the 38 is held today.
- The fingerprint refresh press picks up Radiance after release. It reads the missing images and clears those names from the guard.

**How many of the owner's cards are eligible today** (measured, before the read). The store holds 3,501 numbered cards with a SKU:
2,959 Riftbound and 542 Pokemon. The guard blocks 163 card names. 479 held cards carry one of those names (414 hinted, 65 unhinted).
**Eligible: 3,022 of 3,501 (86.3%).** The 479 go to the second look.
This is a pre-read estimate. The guard fires on the best answer, so a card with a blocked name may still be read when its best answer has another name.
It is a floor on eligibility. How many of the 479 the real read accepts is unmeasured.

**Games the matcher refuses.** `pokemon_code` and `misc` have no stock photos.
Code cards follow their own rules. No code-card photo is ever embedded, copied or matched.
The matcher serves `pokemon`, `riftbound` and `one_piece`.

## 3. The accept rule

The matcher answers with its best card and two numbers. The margin M is the cosine of the best match
minus the cosine of the second. The floor S is the cosine of the best match.

**Accept only when all three hold:** the look-alike guard does not fire (section 2), M is at least 0.05, and S is
at least 0.755. An accepted card gets `confidence` of `high` in the identification record.
The margin floor of 0.05 is the owner's ruling: *"maybe those under .05 get a haiku auto pass"*.
**Every other card gets the second look** (section 2). Haiku's answer for it is held for review.
The join marks such a card as a second-look card, and the router sends it to review at any confidence setting.

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
- The look-alike guard (section 2) is therefore a hard precondition. A threshold cannot replace it.
  Even with both thresholds, 12.2% of absent-truth answers pass. The guard removes the same-name case, which is where they come from.
  The guard is not yet measured on real photographs. The held-out check below tests it.
- The spike did not demonstrate 99.5% precision. It split the 500 cards at random 20 times.
  Each time it fit the margin on one half and scored the other half.
  Marqo-B accepted 99% of cards at a mean precision of 99.4% and a worst split of 98.8% (measured).
  A half of 250 cards cannot show 99.5%.
- The value 0.755 was chosen on the same 500 cards. The margin floor is the owner's ruling, checked on held-out photographs below.
  Both values live in one constant, beside the eval that produced them.
  The record also carries the model file hash.
- **Build-lane gate: a held-out check confirms the thresholds and the look-alike guard before adoption.**
  The owner supplies photographs that the spike never saw, and the eval scores them with the fixed constants.
  The set includes cards whose same-name twin has no stock image, and the check must show the guard does not accept each of them.
  The build lane does not ship the matcher pick until that check reports no wrong answer among the accepted cards,
  and reports the share accepted. A failed check lowers the constants or ends the build. It never edits the held-out set.
- **Held-out result (measured, 3,001 fresh store photographs).** At a margin of 0.05, 1,876 cards are accepted (62.5%) and 0 are wrong.
  At 0.02 the check accepted 2,104 cards and found 3 real wrong answers. Correct accepts under a margin of 0.04 are 6.6% of all correct accepts.
  The unaccepted share is about 37%. It sets the estimate in the quote.
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

**The index lists every printing.** The index holds each numbered product of each set it covers, with its fingerprint or its no-image mark.
It is current when its model file hash matches the matcher's file. A set not in the index cannot be guarded (section 2).
The preflight names each such set and the cards it sends to the second look because of it.

**The index.** One stock image becomes one vector of 768 floats, which is 3 KB.
The spike's 1,365 images make about 4.2 MB (measured). The index lives under `inventory/`, beside the other
derived stores. It is keyed by image URL and model hash.

Building the index needs the image bytes once. D301 (stock photos are hotlinked, never mirrored) is amended
on the owner's word for this one read. The server reads each stock image, computes its fingerprint, and drops the bytes.
Only the fingerprint is stored. A fingerprint records the model file hash and the source URL.
**A change of model rebuilds every fingerprint.** An old fingerprint never meets a new model.
The read is the matcher's own step. It starts by itself (section 8, Free setup), and the owner's press on a screen (section 6) refreshes it. The spike fetched 1,365 images
at a polite pace, which took a few minutes (measured).

**A matcher press never builds or refreshes fingerprints.** It reads only fingerprints that are already stored.
A fingerprint is stale when the model file hash differs, or when the set now holds a numbered product with no fingerprint.
A stale fingerprint is never read. A missing one leaves its printing as a no-image printing, and the guard blocks its name.
Only the free setup (section 8) and the owner's press on the fingerprint control (section 6) read images.
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

**The first-run download and who triggers it.** The owner ruled that the free setup runs by itself (section 8, Free setup).
The 372 MB file downloads once, and the hash is checked. The runs sheet shows a card named "Prepare matching".
It states the size and the source. A press there is a manual refresh.
Until the download finishes, the matcher pick is dimmed with one sentence.

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
The free read is the default pick each time the composer opens. The pick is not stored on the device.
It is one term of the press, so the selection stays the cards the operator named (D180, a press names the cards it covers).
Nothing else about selection changes.

**What each pick says.** The labels are the operator's words.
D196 (no screen string names a mechanism) rules out model names on screen, with two named exceptions.
The owner's word: plain words on the control, and each pick's model name in its hover tooltip.
The two tooltips are the constants `HAIKU_NAME_TOOLTIP` and `MATCHER_NAME_TOOLTIP`, both exported from `app/src/engines.ts`.
D196 records the exceptions. The `no mechanism on screen` row exempts exactly those two strings. It reads each from its constant.
It exempts a word-list hit only. The build lane must export both constants under those names, or the exemption finds nothing.

| Pick | Label | Line under it |
|---|---|---|
| `haiku` | Read from the photo | Reads the name, the number and the foil. Costs about the quoted amount. |
| `marqo-b` | Match to stock photos | Reads every card free first. Cards it is unsure of get a second look from the paid read, then wait in your review queue. |

**A tooltip on each pick.** Both picks carry a `title` tooltip, and both name their model.
The Haiku pick uses `HAIKU_NAME_TOOLTIP`. The matcher pick uses `MATCHER_NAME_TOOLTIP`.

- The cost line comes from the free preflight. `POST /pipeline/preflight` takes the engine.
  It returns a dollar amount for both. The matcher's amount covers only the second look.
- The accuracy line carries no percentage. The two figures do not compare.
  The line names outcomes: what the engine reads, what it cannot read, and where doubt goes.
- The matcher quote adds the cards read free and the cards that go to the second look. Each is marked measured or estimated (section 2).
  It also adds the pool-rule counts and the setup state.
- **A paid press over cards the free reader matched asks every time, and the default answer is skip.**
  A selection can hold cards the matcher accepted. Those are answered.
  The Haiku preflight quote names the count it would bill, and that count excludes them.
  The ask is a second line on the quote: "Also read again the 412 cards that matching decided".
  That line shows its own cost. It is off until the owner turns it on, and it asks again at every press.
  This replaces the earlier idea of a cross-check default. Nothing cross-checks the free read by default.
- The press button names the cards, as D180 requires. It reads "Match 412 cards, then spend $0.17 on the second look" for the matcher.
  It reads "Read 412 cards, about $0.45" for Haiku.
- When the matcher is picked, the crop and size choice is hidden. The matcher always uses the same crop.
- The free read is the default pick each time the composer opens. The pick is not stored on the device.

**Fingerprint control.** The runs sheet has one card named "Prepare matching" with two parts. Each part shows its size first.
The setup also starts by itself (section 8, Free setup). A press is a manual refresh.

- The model file: 372 MB, a download (section 5).
- The fingerprints: the number of stock images to read, one read each, and how many printings still have no image.
  A press reads the missing and stale images, in memory, and stores the fingerprints (D301, amended).
  It reports the printings read and the printings still with no image when it ends.

**The receipt.** The run record shows the engine. It then shows the counts: matched, second look, and already answered.
A matched card the finish ladder cannot finish goes to Review as before. The run line reads, for example,
"Matched 412 free. 150 got a second look from the paid read and wait in review."

The manifest records the engine in `flags`. It records the model hash and the pool snapshot in the existing
`model` field and a new run field. A review queue entry carries the engine that read it, beside the existing read fields.
D258 (identity follows the SKU) keeps those read fields as evidence.

**The wire.** `RunSend` gains `engine`, default `marqo-b`. `onTheWire` in `app/src/server.ts` sends it.
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

## 8. Background reader

**Free setup.** The free setup (`match prepare`) starts by itself, with no press. Nothing in it spends money.
`pipeline_routes.ensure_stock_setup` looks once and starts one detached `match prepare` when the model file is missing
or a target set has no fingerprints (`match.unread_targets`). It starts none while one runs.
`capture_server.serve` calls it at start and runs `pipeline_routes.stock_setup_loop` on a daemon thread, so a card from
a new set starts a read. With the model runtime missing (`matchconst.runtime_importable`), nothing starts.
The first look and the loop run on the daemon thread, so the server answers at once.
The switch is the env `PKMNSCAN_AUTO_SETUP`: `on` forces auto-start. Unset, it is refused when `CI` or `PKMNSCAN_HARNESS` is set
(`make harness` and the Playwright config set it), and unless the checkout is primary and the store is its own (`PKMNSCAN_HOME` unset or pointing at it): a linked worktree or a demo or throwaway store never auto-starts.
A look that would start the same setup again (a set the catalog cannot name, a failed download) waits 30 minutes.
A retry downloads the model from zero, because `match prepare` clears the partial file first.
`pipeline_routes._spawn_prepare` is the one door: under a lock it writes the running record before it spawns, so a second start is refused.
A tried mark made while a Prepare runs never counts once the Prepare ends.
`match.index_stamp` changes when the index gains a set. `sweep.tried` counts a tried mark from an older stamp as empty,
so cards tried before their set was read are tried again.

**The owner's ruling: the free read may run in the background, and always.** It is allowed on one condition:
with an empty queue it uses barely any memory. This section bends two decisions, D1 and D273 (question 3).
Both are rewritten in place and cite the owner's word.

**What it is.** A separate child, the CLI command `match` with the `--sweep` flag (`identify/sweep.py`). It lives outside the capture server.
It takes no request slot. `REQUEST_SLOTS` and `PHOTO_SLOTS` in `server/capture_server.py` are never spent on it.
It reads photographs from disk. It never runs inside a capture request.
The capture server starts the watcher when the switch goes on, and once at server start when the switch is already on. It does nothing else for it.

**The queue.** A card is queued when its state is `captured` and the `identifications` table holds no row for it.
The game must be one the matcher serves. An unhinted Pokemon card is never queued.
A card the worker looked at and did not accept is recorded as tried, against that photograph and that model file.
It leaves the queue until it is re-shot or the model changes. It waits for a press.

**What it writes.** One thing: an `identifications` row with engine `marqo-b`. It never writes card state.
It never sets a SKU, a name or a number on a card. Those follow D258 (identity follows the SKU) and the join.
The row records the card's `cid`. A move or a renumber changes the position key and never the `cid`.
The row is keyed like every cache row, by position, and the `cid` lets a reader match it back to the card.

**A re-shoot drops the row.** Today `do_reshoot` writes new bytes and touches neither `cards` nor `identifications`
(`store/db.py`, the comment on the naming ladder). A matcher row would then hold the digest of bytes that exist nowhere.
So the build makes a re-shoot delete a `marqo-b` row for that card in the same transaction.
The sweep then reads the new photograph. A Haiku row keeps today's behavior.

**What it never reads.**

- An unhinted Pokemon card, because its pool is the whole category (section 2, D170).
- A card whose best answer shares a name with a no-image printing (section 2).
- A card from another game's rules: code cards and `misc`.
- It never borrows a hint from a neighbor or from the box. A hint is evidence about the card that carries it (D76).

**Memory is a ship gate.** Measured on this Mac with onnxruntime 1.30.0 and the fp32 file:

| State | Resident memory |
|---|---|
| Python with sqlite only | 15 MB |
| Plus numpy and Pillow | 29 MB |
| Plus onnxruntime imported | 47 MB |
| Model loaded, after three reads | 454 MB |
| After the session is freed in the same process | 454 MB |

Freeing the session does not return the memory in the same process (measured). So the design is two parts:

- A **watcher** that imports only `sqlite3` and the standard library. It polls the queue. It never imports numpy, Pillow or onnxruntime.
  Its idle memory is the first row, 15 MB.
- A **worker** that the watcher starts when the queue is not empty. It loads the model, reads the queue to empty, and exits.
  Exit returns the memory. A cold start to the first vector took 0.26 seconds with the file cached (measured).

The gate is a measurement, and it has no pass mark yet. The owner said: "let's measure first".
The build lane measures the watcher's idle resident memory, with an empty queue, on the shipped build.
It brings the number to the owner before ship, and the owner sets the pass mark then.
A queue with cards in it may use the 454 MB peak, in the worker only.

**While cards are being fed (the capture gate).** The owner's ruling: the reader reads even mid-feed (*"Even mid-feed"*).
The quiet time is 0. The worker starts as soon as a card waits, and a capture never stops it.
The gate: 300 feeder-paced captures on a scratch store, run with the reader off and with it on. The metric is the p99 time of a capture request.
The measured p99 is 30.5 ms with the reader on and 30.6 ms with it off, so the ruling stands on the figures below.
`--quiet N` still exists on the watcher. With N above 0 the worker starts only when the newest capture is N seconds old, and a capture stops it.
The measuring script uses it for its third arm.

**Measured (scratch store, `scripts/sweep-memory.py` and `scripts/capture-gate.py`).**

| Measure | Result |
|---|---|
| Watcher idle resident memory, empty queue | 22.1 MB |
| Worker peak resident memory, 20 captured cards | 929 MB |
| Worker peak resident memory, 3000 captured cards | 1103.5 MB |
| Capture request, reader off (300 captures at 623 ms) | p50 20.1 ms, p99 30.6 ms |
| Capture request, reader on, quiet of 3 s | p50 21.0 ms, p99 34.1 ms |
| Capture request, reader on, quiet of 0 (shipped) | p50 16.6 ms, p99 30.5 ms |

With a quiet of 3 s the worker never ran during the feed, because a card arrived every 623 ms.
With a quiet of 0 it wrote 139 rows during the feed and the p99 did not move.
The first worker peak came from a 20-card store. The second comes from a store of 3000 cards.
The worker runs `store.read()` once per chunk of 8 cards. A snapshot loads only the rows it names, so the figure does not grow with the store.
The peak is above the 454 MB of the model alone, because the worker also holds the CLI imports and decoded crops.

**It cannot crash-loop.** A worker that exits with any code but 0 or 3 is waited out for longer each time: 30 seconds, doubling to 30 minutes.
Exit code 3 means the model file, the index or the runtime is not ready, and the wait is 300 seconds.
The worker writes its log to `.serve/match-sweep.log`. Before each chunk it records the cards in `match-sweep-inflight.json`.
On exit 3 from a missing runtime it also writes `match-sweep-blocked.json`. `GET /pipeline/match/sweep` reports `blocked: "runtime_missing"` only while the runtime is not importable now, so the answer follows the present state. `GET /pipeline/match` carries `runtime_missing`, and Prepare refuses with 409 `runtime_missing`.
A worker that dies inside a chunk, even by an out-of-memory kill, leaves the file. The next start marks those cards tried.
**One watcher runs at a time, by one lock.** The watcher holds an `flock` on `inventory/match-sweep.lock`. A held lock is the only thing that reads as running, so a reused pid cannot.
The watcher writes `.serve/match-sweep.json` and a reap owner mark (D305). `make down` and `make reap` stop it, and a SIGTERM stops the worker before the watcher exits.
It exits when its store or its tree is gone.

**The toggle.** The on and off switch is one row, "Background Match", in the Rig panel of the Capture screen.
Its state is the `match_sweep` row in the store's `meta` table. It is not a device key, and it is not in `deviceMemory.ts`.
`PUT /pipeline/match/sweep` writes it and starts the watcher. `GET /pipeline/match/sweep` reads it.
The row holds its size until the store answers (D313). The reader is off until the owner turns it on.
The setup press downloads the model file and builds the fingerprints once (section 6, "Prepare matching"). It asks first, and it shows both sizes.
Turning the toggle on never downloads. With no model or no index, the toggle reads as on and the sweep does nothing.

**What the screens show (D313, nothing on screen moves unless the person moved it).**

- Nothing on the capture screen changes while the sweep reads. No count, no spinner, no new element.
- The runs sheet shows one snapshot count: how many cards the free reader has matched. It sits on the "Prepare matching" card, read when the sheet opens
  and when the owner presses refresh. It never ticks. It counts every `marqo-b` row, from a press or from the background reader.
- A per-card detail shows on request only: the engine, the match and the margin.

**What a paid press does over matched cards.** Section 6 gives the rule. It asks every time, and the default is skip.

## 9. The owner's rulings

- The margin floor is 0.05. The S floor of 0.755 stays (section 3). The owner's word: *"maybe those under .05 get a haiku auto pass"*.
- One press runs the free reader on every card, then sends each card it does not accept to Haiku for a second look. Haiku is on the low-confidence cards only (section 2).
- Haiku's second-look answer goes to the review queue with the photo, the answer and the matcher's top pick. It is never saved on its own (section 2).
- The quote names the free count, the second-look count and the cost before any spend. The press needs the paid confirm. The background reader never spends (section 2).
- The matcher does not accept a card whose best answer shares a name with a no-image printing (section 2).
- Dropped on the owner's word: the option that skips names with two or more printings, and the twin-margin options.
- D301 is amended for one fingerprint read of each stock image. A model change rebuilds every fingerprint (section 4).
- The model file is a release asset of `shivinate7/banchi`, with a pinned hash, downloaded when the owner presses a control (section 5).
- The control uses plain words. The model name sits in one hover tooltip, as a named exception in D196 (section 6).
- Before adoption, a held-out check confirms the thresholds. That is a build-lane gate (section 3).
- Process only: the build starts on fp32. The build lane commits the eval scripts.

- The free read is the default pick. Both tooltips name their model. D196 holds both as named exceptions (section 6).
- The free read may run in the background, always, if its idle memory is barely any. D1 and D273 are rewritten for it (section 8).
- A printing with no stock image blocks only a match that shares its card name. Radiance is no special case (section 2).
- The pass marks for idle memory and capture speed are not set. Measure first, then bring the numbers to the owner (section 8).
- The reader reads even mid-feed. The owner's word: *"Even mid-feed"*. The quiet time is 0, from the measured capture gate (section 8).
- A paid press over matched cards asks every time and defaults to skip (section 6).
- The on and off toggle is in the rig settings. Its state is a store row. The setup press downloads once (section 8).

**Open for the owner.** The two gates are measurements with no pass mark. The build lane brings the numbers before ship.
The held-out check (section 3) also tests the look-alike guard, with photographs of cards whose same-name twin has no stock image.
