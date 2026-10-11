## D103 — Staleness filters; it never gates

**`#/pricing` draws the operator's whole live inventory from a My Pricing export. The staleness terms are a filter over it.** They are not a decision taken before the data arrives. The operator wanted the live export on the same pricing UI as the runs path, which has the charts, the load-prices flow and familiar controls. A spreadsheet was rejected. That UI was wired to runs, and a live export is not a run.

### Why a lens and not a gate

The operator's My Pricing export has 757 rows, 441 of them live. Against it, the gate selects **177 SKUs at one day, 109 at three and at seven, and 0 at ten and at fourteen**. That zero is the argument. The oldest capture in the store was younger than ten days at the time of that export. So a ten-day window cannot select anything. **A gate hands back an empty screen for a reason about the store's age, not about the listings.** The operator's remedy is to widen `--days` and read again. A filter does that without a re-read.

The owner ruled that the stale rows are not the default view. The lens opens on everything.

**Scale was the objection, and it did not hold.** `app/src/Pricing.tsx` does not virtualize. It already draws the merged worklist across eight runs, about 423 SKUs. 441 is not new territory.

### The record widens, and the offer does not

It applies D100 §5's distinction once more: **the file that records is not the file that offers.**

| file | what it is |
|---|---|
| `worklist.csv` | the **offer**: the rows the rule proposed, export-shaped, `Add to Quantity` 0 |
| `manifest.json` | what the offer said per SKU, including the row's own bytes |
| **`survey.json`** | **new**: every candidate considered, its verdict, and its verbatim export row |
| `import.csv` | what `apply --write` produces |

**A fourth file rather than a wider manifest, for two measured reasons.** `cli/cmd_reprice.py:_apply` builds the upload's bytes from `manifest["skus"]`. Leaving that key alone keeps the money path provably untouched. Every existing assertion in `check_markdown` runs over byte-identical inputs. Also, `server/pipeline_routes.py:_markdown_summary` parses the manifest for every stamp to answer `GET /pipeline/markdowns`. At about 700 bytes a row, a wide manifest is about 530KB on the owner's export. Thirty markdowns would mean parsing 16MB to draw a list.

**The worklist stays narrow.** D100: "every file this feature writes is safe to upload, whichever one the operator grabs." A 441-row worklist has two bad options. It would carry a proposed price on rows the rule refused, a file that marks down the entire store if uploaded by accident. Or it would carry nulls through `set_writable`. `check_markdown`'s "the worklist holds the two listings above the floor and not the one at it" is the mechanical guard, and it is to be read as one.

**`standing` is a third state that `skip` cannot express.** A `deferred` row qualified but fell below `--limit`. It carries `skip: null`, exactly as an offered row does. Without `standing`, the difference between "the rule proposes this" and "you asked for fewer" is invisible. It is not a second fact that can disagree. Both are projections of one partition, taken in one pass. **There is no `below_limit` refusal code,** because those rows qualified, and `plan` deliberately keeps them out of `skipped`.

### What `not_in_worklist` now means

Its old argument was "there are no bytes to build a row from". Once the survey carries the bytes, that is no longer true of a row the rule merely declined to propose. So `read_back` gains `offered=` and `unpriceable=`. Both are optional, so every caller written before this reads exactly as it did. The refusal narrows to a SKU this markdown's survey never saw: a typo'd id, or a row from some other export.

**`dropped` follows the OFFER, not the record.** The figure means "SKUs this file was written for that you deleted". Measured over the wider set, it would tell an operator who priced three cards that they had deleted 438.

### The 33 that are drawn and may never be pushed

408 of the owner's 441 live SKUs are ones this store has held. 33 are not: `Card Sleeves`, `Playmats`, a `YuGiOh` row.

**They are drawn.** Omitting them shows 408 rows against an export that holds 441. Nothing says where the rest went. This is `CLAUDE.md`'s both-directions rule. D100's closing cost becomes something the screen states, not something a decision file does.

**They are not priceable.** Pricing one would lower a live listing this pipeline did not create, and whose copies it cannot verify. That is outside the measurement D100's safety argument rests on. It would also write a permanent corpus answer for a SKU no card here carries. That answer is inert to `join` and `emit`, and visible in `prices show` forever. `sold_out` joins them. TCGplayer holds no copies, so there is no listing for a price to edit. That is `unchanged`'s own argument.

Both are refused under the survey's own code. The sentence on the row and the receipt's sentence are one string from one table.

### Two defects this uncovered

**`corpus.Answer.at` was written in one place in this repo and read in one.** `reprice apply` set it, and that command's ratchet read it. So `priced_recently` meant "marked down recently". D100's ratchet section claims it means "a card the operator hand-priced on `#/pricing` yesterday is not stale". It never did. The screen never stamped anything. Hand-pricing fifty live listings left every one reading as stale the next morning.

`pipeline/corpus.py:stamp_answers` is the one rule both writers date by. Its three constraints are each load-bearing:

- **Diff-based.** `PUT /pricing` replaces the whole document on every debounced save. A blanket stamp would move every answer to now on every keystroke. The whole corpus would read `priced_recently` forever. The ratchet would then invert into a permanent refusal.
- **`channel == "price"` only.** `cli/cmd_join.py` seeds an `unknown` answer for every card the catalogue could not price. Stamping those would make an unpriced card read as priced, in the direction that costs money. **A hold is not a price.**
- **One reader for both writers.** `check_corpus_revision`'s own header names this hazard. A digest cache added to the route would leave a route-only test green while the real refusal silently stopped firing.

**`reprice apply` had no stale-write guard.** `PUT /pricing` has had one since D86. `emit` never needed one, because `cli/cmd_emit.py` only reads. This command reads and then rewrites the corpus from a subprocess. So a `#/pricing` tab open during an apply had its next keystroke refused for a write it had made itself. Once the press lives on that screen, this becomes the ordinary path, not a race. The digest moved to `pipeline/corpus.py:revision`. `cli/` may not import `server/`, which is why the guard could not be shared before. `--corpus-revision` refuses the whole file before a byte is built. The apply answers with the new digest, so the screen adopts it.

**Behavior change the operator must know about.** Hand-price fifty live listings, and those fifty arrive as `priced_recently` on the next survey. That is D100's stated claim becoming true. `--again` is the override.

### The address, and the two readings

**`#/pricing?markdown=<stamp>`.** The hash router strips `?…`. That screen already parses its own query for `?run=`. So **eleven routes stays eleven**. `route census`, `route rosters` and every pinned spec roster are untouched. D100's ROUTES-table comment left the route "available for the asking and not taken". This takes it as a query on an existing route. That is neither of the two options the comment anticipated.

**`GET /pipeline/markdowns/<stamp>/{table,history,trends}`.** The reading routes are a second address over one body. They are never a second implementation. The catalogue walk reads five identity cells off a verbatim export row: `Product Line`, `Set Name`, `Number`, `Product Name` and `TCGplayer Id`. A My Pricing export carries all five. The cache is keyed by product, not by document, so a card already read on a run is warm here.

**A run-free `GET /pipeline/history` that takes `?sku=` and the row's own cells was rejected.** It makes the client the source of a card's identity. A mistyped `Set Name` resolves silently to a different real product. That is the failure `pipeline/join.py:number_index_key` exists to prevent, after a 950-row silent zero-join. The route would also have no address to check. So `sku_not_in_run`'s real membership test would have nothing to test against.

**The markdown strip requires an explicit `?sku=` list.** The run route measured 46 SKUs at about 34 seconds of courtesy delay. A survey is the whole live inventory. So an unfiltered walk takes about 5.5 minutes at a free public mirror. D278's rule makes this a press. A walk that big makes the press meaningless, not merely slow.

### The upload comes from `edits`, materialized server-side

`#/pricing` holds `{sku -> price}` and has no CSV writer. `app/package.json` carries exactly two runtime dependencies. PapaParse, the library `CLAUDE.md` requires for this job, is not among them. So the pairs arrive as JSON on `POST .../apply`. They are written with `pipeline/tcgcsv.py:write_csv`, the repo's own writer, into the markdown's own directory.

**Two columns, and that is the point.** `reprice apply` reads exactly `TCGplayer Id` and `TCG Marketplace Price`. It builds every other byte from the manifest. So a two-column file is the narrowest possible expression of D100's "the operator's editor is not where the bytes come from". There is no column for a quantity to hide in.

**Synthesizing it in the browser was the alternative, and it was argued for twice.** It works today with no server change, keeps one reader of `read_back`, and leaves an artifact on disk. Server materialization keeps all three properties. It does not put file-format authority where D100's safety argument says it must not live. The residual risk is that `edits` becomes a second door upstream of the file. T7 closes it. T7 asserts that the `import.csv` it produces is byte-identical to the one the worklist path produces.

**`wrote` is answered by the file being there, not by the flag that was asked for.** `_apply` exits 0 with nothing written when every row is refused. One unreadable price does that. The route used to report `wrote: true` over an `import.csv` that did not exist, and it offered a download of nothing.

### What it costs

**The raise cliff is now reachable by one keystroke.** `read_back` marks a raised price `RAISED`. `Application.fatal` refuses the whole file. On a lens over 408 live listings, an operator will eventually type a higher number. The screen refuses its own press while the raise count is non-zero, and it says so on the row. The count comes from the survey's own `asking`, not a recomputed figure. That is still a second implementation of `after > before`, and it can drift.

**A row carries exactly one refusal code, even when three apply.** `plan`'s ladder is an early exit. So a "held" filter chip will not show a row refused `sold_recently` first. `SKIP_ORDER` is the precedence. The screen names it rather than changing the ladder.

**`_stamp` walks past a collision one second at a time.** Two `reprice list --write` calls inside one second resolved to one directory. The later manifest replaced the earlier, so a worklist was judged against an offer that was no longer its own. **There is no suffix.** The shape is an address, spelled in five route patterns. A `-2` would make the second markdown unreachable rather than merely lost. The cost is a directory named a few seconds after the moment it describes. The manifest's `at` is the truth.

**Nothing this feature writes has been uploaded to TCGplayer yet.** D100's §6 is unchanged by any of this. The first real press is still `--limit 5`. Then upload, then `reconcile --live` against a fresh download.

### What this amends

**D100**, on two points: the manifest's scope, and the placement. The manifest records the offer, and the survey beside it records the export. The placement is one that D100 already flagged as "a judgment rather than a measurement". Its three subjects are untouched. Nothing is deleted, the quantity is not a variable, and the age is a proxy that says so.

**D86**, on two points: the worklist spans runs and the live export. Its write path now stamps the provenance its own `Answer` type declares.

### What would reopen this

A listing age this store can read. Populate `live_as_of` on a first sighting, or record a `first_listed_at` when `emit` pushes. That retires the proxy, and the paragraph every report carries about it. The first upload, whose answers belong in D100's spec §6. An operator who wants the markdown bookmarkable on its own, which is a ROUTES row and three mechanical counts, not a rebuild. A raise that should be allowed. That is a change to what this path promises, not a widening of `read_back`.

### Dead rows leave the record

The record held every live row, and it also held every row TCGplayer no longer holds. `sold_out` is the only member of `UNPRICEABLE_CODES` since D109. So those rows could never be answered. They existed on the lens only to be scrolled past. **372 of the owner's 759 rows were dead, so the screen drew nearly twice as many dead rows as live ones.** `Plan.surveyed` now drops them.

**The export is not narrowed.** The operator first wanted the fetch scoped to in-stock listings. Two things stop that. `Export From Live` is `GET …/DownloadMyExportCSV?type=Pricing&exportLowestListingNotMe=true`, and it ignores every parameter. Under D65, eight spellings returned byte-identical output. More importantly, the same file feeds `reconcile --live`. There, **a SKU going from four copies to zero is how the store learns something sold.** `pipeline/livecheck.py` tells a zero-quantity row from a SKU that is `absent` from the export entirely. Narrowing the download would erase that difference silently. The export stays complete. The worklist is what gets narrowed, and the report still counts what it dropped.

**The cut-off is drawn on both doors, which reverses this entry's `repartition: false`.** The earlier reason was that "the cut-off decides which import file a row is bound for, and a live listing is bound for none." That is right about the file and wrong about the figure. D99 made the line and the cheap price one variable. So the cut-off also says what everything under it is worth. That is as much a question about a live listing as about a card in a drawer. The operator asked to reuse the runs path's threshold rather than rebuild it.

So the lens draws `CutoffPanel` itself. It uses the same component, the same `policy.threshold`, and the same `bucketAt` partition. **The only difference between the doors is when the figure is spent.** `emit` prices a run's cheap half from `sub_threshold` at write time, so those rows need no press. A lens has no emit. `reprice apply` sends typed answers and nothing else. So the same figure is spent by a press that writes real answers, in one act with one reversal. `CutoffPanel.applyCount` is `null` on a run. A button there would offer to redo what the pipeline already does.

**A first build of this was a bespoke two-field widget, and it was wrong twice.** It asked for a threshold and a price. D99 had already ruled that the pair is one variable. It also collided with `.pricing-cheap`, the run's own cut-off panel. That panel's `flex-direction: column` won on source order and stacked the control into a tower. **A screen-prefixed class needs more than its prefix to be unique.**

**The presets are real on the lens, and the press means something different on each door.** The operator asked what "Match market" and "Market −5%" do on the lens. The answer was nothing useful. `asRow` shipped `presets: {}`. So every lens row had no per-SKU figure, and the buttons filled nothing. They still wrote `policy.rule` and `policy.basis` to `inventory/prices.json`, the store-wide setting that every future joined run lists by. **On a copy of the owner's store, pressing `Market −5%` on the lens left 387 fields untouched and flipped the store's rule from `match` to `undercut:5`.** Repricing a live book silently repriced the next box out of the camera, and nothing on screen said so. D101's defect, on the money path.

The figures are now computed server-side by `pipeline/pricing.py:preset_prices`. It is the same function a run's `pricing.json` uses, so the two doors cannot compute different numbers for one card. That table moved out of `cli/cmd_join.py`. A second copy of `Rule.apply`, `round_money` and `clamp_floor` is what D86 refused to have in two languages. Two Python modules holding it is the same bet at shorter odds. `make docs-audit`'s `pricing presets` row followed the move and still reconciles. Its resolver now reads a bare `RULE_MATCH`, because inside `pricing.py` a `pricing.` prefix would name the module itself.

**On a lens, a preset writes answers where a run writes a rule.** `emit` prices a run's unanswered rows by the standing rule at write time. Writing 300 per-SKU answers there would freeze a rule into figures. That is D54's staleness. `reprice apply` sends typed answers and nothing else, so on a lens the rule governs nothing. The press must write real answers or do nothing at all. It was doing the wrong one of those. The fix is one act with one reversal, the same shape as the cut-off press.

**A row the pipeline cannot price is left and named.** `None` per preset key is a real answer. 394 of 2,476 rows on the wide Pokemon export carry a blank `TCG Low Price`. On this lens, 4 of 387 live rows could not be priced by any preset.

**A blank box keeps the price it already has, and the screen says so.** The operator asked for this. It was stated only once typing had begun, which is when it is least needed. An operator looking at 387 fields, with a faint current price in each, has to know that leaving one alone changes nothing at TCGplayer. Otherwise the ghost reads as a value about to be re-sent. This is also the true rule. `pushable` collects rows carrying a typed answer, and `apply` receives only those.

**The field's ghost is the live price.** D109 opened the lens field empty, with the rule's figure behind it. The operator asked for the price they are actually asking now. The ghost is faint gray, and it is replaced once a new number is typed. `snap.now` is that cell. Because it is a placeholder rather than a value, the first digit typed replaces it whole. There is no selecting and no backspace. It falls back to the rule only on a `no_asking_price` row, where there is no "now" to draw.

### Singles, counts and the rule press

- **Singles and Sealed.** The Live tab filters on its own by kind, in the URL (`?kind=singles` or `?kind=sealed`, D285). A row is sealed when its condition is `Unopened` (`pipeline/reprice.py:is_sealed`, `tcgcsv.SEALED_CONDITION`). No sales-lane rule existed to reuse. A name rule misfiles singles such as Tinkatink and Pack of Wonders. The survey carries the flag per row. The apply takes the filter as `kind` and refuses an edit of the other kind (`kind_mismatch`), so a Singles view never sends a sealed price.
- **The counts add up.** "Passed over" read the survey's `counts.refused`, which also counts sold-out rows the tab never draws. On the owner's read, that gave 727 beside "All 408". Each lens count is now the rows it shows, under the kind filter. All is Not selling plus Passed over.
- **The Live tab's heads.** "Needs you" on this tab used to count every listing worth $5 or more, 236 of 408. A live listing already has a price somebody chose. So on this tab only a row with no market price leads, under "No market price". The owner types its price, and the rule never lowers it.
- **What "N new prices" counts.** A price that is not the price the read showed. It was written on this visit (typed, a preset, the cut-off press, or "Mark down"). Or it was stored on an earlier visit above the live price. The owner ruled that a typed price higher than the live price counts. A lower earlier price does not. The bar names each earlier price that goes, card by card, before the press. Earlier, every stored answer on a surveyed row counted, most of them equal to the live price. That was the "280".
- **The cap is the rule's only.** The owner ruled that the cap governs the rule and nothing else. "Mark down" writes the capped proposal. A typed price is never held back by the cap.
- **A press for the rule.** A blank box keeps its price, as above. So the rule's price reaches a field only by a press. "Mark down N" on the rule line writes the server's proposal, capped and never on a no-market row, onto the rule's picks on screen. It is one act with one undo, the presets' own shape. A row the owner priced away from its live price keeps the owner's price.
- **Money to the cent.** A field shows two decimal places. The export's `349.9900` is drawn as `349.99`. What the field shows is what the press sends (D221).

Proof: `app/tests/pricing-markdown.spec.ts`, the singles-and-counts cases.
