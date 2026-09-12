## D103 — Staleness is a filter and not a gate, the record holds every live row, and the file that leaves the machine stays narrow

**`#/pricing` draws the operator's whole live inventory out of a My Pricing export, and the staleness terms become a filter over it rather than a decision taken before the data arrives.** Built 2026-09-06 on the owner's reaction to D100's screen, verbatim: *"I was sorta hoping that when I upload it, that I then get to interact with the same pricing sorta setup I get when I'm first listing prices with the ability to hit load prices and see all the graphs/charts and such and price with the UI I'm used to (instead it gives me an excel that I can then manipulate in excel, that's no fun)."*

The UI they wanted already existed. It was wired to runs, and a live export is not a run.

### Why a lens and not a gate, in the owner's own figures

Against their My Pricing export of 2026-09-01 — 757 rows, 441 live — the gate selects **177 SKUs at one day, 109 at three and at seven, and 0 at ten and at fourteen**. That zero is the argument: the oldest capture in the store is 2026-08-23, so a ten-day window cannot select anything. **A gate hands back an empty screen for a reason that is about the store's age rather than about the listings**, and the operator's remedy — widen `--days` and read again — is the thing a filter does without a re-read.

The owner ruled the stale rows are **not** the default view. The lens opens on everything.

**Scale was the objection and it did not survive contact.** `app/src/Pricing.tsx` does not virtualize and already draws the merged worklist across eight runs — ~423 SKUs. 441 is not new territory.

### The record widens and the offer does not

This is the whole shape of the change, and it is D100 §5's own distinction applied once more: **the file that records is not the file that offers.**

| file | what it is |
|---|---|
| `worklist.csv` | the **offer** — the rows the rule proposed, export-shaped, `Add to Quantity` 0 |
| `manifest.json` | what the offer said per SKU, including the row's own bytes |
| **`survey.json`** | **new** — every candidate considered, its verdict, and its verbatim export row |
| `import.csv` | what `apply --write` produces |

**A fourth file rather than a wider manifest, for two measured reasons.** `cli/cmd_reprice.py:_apply` builds the upload's bytes out of `manifest["skus"]`, so leaving that key alone is what keeps the money path *provably* untouched — every existing assertion in `check_markdown` runs over byte-identical inputs. And `server/pipeline_routes.py:_markdown_summary` parses the manifest for **every stamp** to answer `GET /pipeline/markdowns`: at ~700 bytes a row a wide manifest is ~530KB on the owner's export, so thirty markdowns would mean parsing 16MB to draw a list.

**The worklist stays narrow, and this is the strongest single constraint here.** D100: *"every file this feature writes is safe to upload, whichever one the operator grabs."* A 441-row worklist would either carry a proposed price on rows the rule refused — a file that, uploaded by accident, marks down the entire store — or carry nulls through `set_writable`. `check_markdown`'s *"the worklist holds the two listings above the floor and not the one at it"* is the mechanical guard on that, and is to be read as one.

**`standing` is a third state `skip` cannot express.** A `deferred` row — one that qualified and fell below `--limit` — carries `skip: null` exactly as an offered row does, so without it the difference between "the rule proposes this" and "you asked for fewer" is invisible. It is not a second fact that can disagree: both are projections of one partition taken in one pass. **No `below_limit` refusal code**, because those rows qualified and `plan` deliberately keeps them out of `skipped`.

### What `not_in_worklist` now means

Its own argument was *"there are no bytes to build a row from"*. Once the survey carries them that is no longer true of a row the rule merely declined to propose, so `read_back` gains `offered=` and `unpriceable=` — both optional, so every caller written before this reads exactly as it did — and the refusal narrows to a SKU **this markdown's survey never saw**: a typo'd id, or a row out of some other export.

**`dropped` follows the OFFER rather than the record, and that is the assertion that catches the sloppy version of this whole change.** The figure means "SKUs this file was written for that you deleted". Measured over the wider set it would tell an operator who priced three cards that they had deleted 438.

### The 33 that are drawn and may never be pushed

408 of the owner's 441 live SKUs are ones this store has held; 33 are not — `Card Sleeves`, `Playmats`, a `YuGiOh` row.

**They are drawn.** Omitting them shows 408 rows against an export the operator can see holds 441, with nothing saying where the rest went — `CLAUDE.md`'s both-directions rule, and D100's own closing cost becomes something the screen states rather than something a decision file does.

**They are not priceable.** Pricing one would lower a live listing this pipeline did not create and whose copies it cannot verify — outside the measurement D100's entire safety argument rests on — and would write a permanent corpus answer for a SKU no card here carries, inert to `join` and `emit` and visible in `prices show` forever. `sold_out` joins it: TCGplayer holds no copies, so there is no listing for a price to edit, which is `unchanged`'s own argument.

Both are refused under the survey's own code, so the sentence on the row and the sentence in the receipt are one string from one table.

### Two defects this uncovered, both of which the lens makes ordinary

**`corpus.Answer.at` was written in exactly one place in this repo and read in one.** `reprice apply` set it; that command's ratchet read it. So `priced_recently` meant *"marked down recently"* while D100's own ratchet section claims it means *"a card the operator hand-priced on `#/pricing` yesterday is not stale"*. **It never did.** The screen has never stamped anything, and hand-pricing fifty live listings left every one reading as stale the next morning.

`pipeline/corpus.py:stamp_answers` is the one rule both writers date by, and its three constraints are each load-bearing. **Diff-based**, because `PUT /pricing` replaces the whole document on every debounced save and a blanket stamp moves every answer to now on every keystroke — the entire corpus reading `priced_recently` forever, the ratchet inverted into a permanent refusal. **`channel == "price"` only**, because `cli/cmd_join.py` seeds an `unknown` answer for every card the catalogue could not price and stamping those makes an *unpriced* card read as priced, in the direction that costs money. **A hold is not a price.**

**THIS IS A BEHAVIOUR CHANGE THE OPERATOR MUST BE TOLD ABOUT.** Hand-price fifty live listings and those fifty arrive as `priced_recently` on tomorrow's survey. That is D100's stated claim *becoming true*, and `--again` is the override.

**`reprice apply` had no stale-write guard**, while `PUT /pricing` has had one since D86. `emit` never needed one — `cli/cmd_emit.py` only reads — but this command read-modify-writes the corpus from a subprocess, so a `#/pricing` tab open during an apply had its next keystroke refused for a write it had made itself. Once the press lives on that screen this stops being a race and becomes the ordinary path. The digest moves to `pipeline/corpus.py:revision` because `cli/` may not import `server/`, which is the only reason the guard could not be shared before; `--corpus-revision` refuses the **whole file** before a byte is built, and the apply answers with the new digest so the screen adopts it.

**One reader of the file, for both writers, also closes a hazard `check_corpus_revision`'s own header names:** a digest cache added to the route would have left a route-only test green while the real refusal silently stopped firing.

### The address, and the two readings

**`#/pricing?markdown=<stamp>`.** The hash router strips `?…` and that screen already parses its own query for `?run=`, so **eleven routes stays eleven** and `route census`, `route rosters` and every pinned spec roster are untouched. D100's ROUTES-table comment left the route *"available for the asking and not taken"*; this takes it as a query on an existing one, which is neither of the two options that comment anticipated.

**`GET /pipeline/markdowns/<stamp>/{table,history,trends}`.** The reading routes are a second ADDRESS over one body and never a second implementation: the catalogue walk reads five identity cells — `Product Line`, `Set Name`, `Number`, `Product Name`, `TCGplayer Id` — off a verbatim export row, and a My Pricing export carries all five. The cache is keyed by product rather than by document, so a card already read on a run is warm here.

**A run-free `GET /pipeline/history` taking `?sku=` and the row's own cells was rejected.** It makes the *client* the source of a card's identity, where a mistyped `Set Name` resolves silently to a different real product — the failure `pipeline/join.py:number_index_key` exists to prevent after a 950-row silent zero-join — and it has no address to check, so `sku_not_in_run`'s real membership test would have nothing to test against.

**The markdown strip requires an explicit `?sku=` list.** The run route measured 46 SKUs at ~34s of courtesy delay; a survey is the whole live inventory, so an unfiltered walk is **~5.5 minutes** at a free public mirror. D62's rule is that this is a press, and a walk that big makes the press meaningless rather than merely slow.

### The upload comes from `edits`, materialised server-side

`#/pricing` holds `{sku -> price}` and has no CSV writer: `app/package.json` carries exactly two runtime dependencies, and PapaParse — the library `CLAUDE.md` requires for this job — is not among them. So the pairs arrive as JSON on `POST .../apply` and are written with `pipeline/tcgcsv.py:write_csv`, the repo's own writer, into the markdown's own directory.

**Two columns, and that is the point.** `reprice apply` reads exactly `TCGplayer Id` and `TCG Marketplace Price` and builds every other byte from the manifest, so a two-column file is the narrowest possible expression of D100's *"the operator's editor is not where the bytes come from"* — there is no column in it for a quantity to hide in.

**Synthesising it in the browser was the alternative and was argued for twice.** It works today with no server change, keeps one reader of `read_back`, and leaves an artefact on disk. Server materialisation keeps all three of those properties and does not put file-format authority in the one place D100's safety argument says it does not live. The residual risk — that `edits` is a second door upstream of the file — is closed by T7 asserting the `import.csv` it produces is **byte-identical** to the one the worklist path produces.

**And `wrote` is answered by the file being there rather than by the flag that was asked for.** `_apply` exits 0 with nothing written when every row is refused — one unreadable price does it — and the route used to report `wrote: true` over an `import.csv` that does not exist, offering a download of nothing.

### What it costs

**The raise cliff is now reachable by one keystroke.** `read_back` marks a raised price `RAISED` and `Application.fatal` refuses the *whole file*; on a lens over 408 live listings an operator will eventually type a higher number. The screen refuses its own press while the raise count is non-zero and says so on the row, counted from the survey's own `asking` rather than a recomputed figure — but that is a second implementation of `after > before` and it can drift.

**A row carries exactly one refusal code even when three apply.** `plan`'s ladder is an early exit, so a "held" filter chip will not show a row refused `sold_recently` first. `SKIP_ORDER` is the precedence and the screen names it rather than the ladder being changed.

**`_stamp` walks past a collision a second at a time.** Two `reprice list --write` calls inside one second resolved to one directory and the later manifest replaced the earlier, so a worklist was judged against an offer that was no longer its own. **No suffix**: the shape is an address, spelled in five route patterns, and a `-2` would make the second markdown unreachable rather than merely lost. The cost is a directory named a few seconds after the moment it describes, and the manifest's `at` is the truth.

**And nothing this feature writes has still ever been uploaded to TCGplayer.** D100's §6 is unchanged by any of this. The first real press is still `--limit 5`, upload, then `reconcile --live` against a fresh download.

### What this amends

**D100**, on two points: the manifest's scope — it records the offer, and the survey beside it records the export — and the placement, which that entry already flagged as *"a judgement rather than a measurement"*. Its three subjects are untouched: nothing is deleted, the quantity is not a variable, and the age is a proxy that says so.

**D86**, on two: the worklist spans runs *and* the live export; and its write path never stamped the provenance its own `Answer` type declares.

### What would reopen this

*A listing age this store can read* — populate `live_as_of` on a first sighting, or record a `first_listed_at` when `emit` pushes — which retires the proxy and the paragraph every report carries about it. *The first upload*, whose answers belong in D100's spec §6. *An operator who wants the markdown bookmarkable on its own*, which is a ROUTES row and three mechanical counts, not a rebuild. *A raise that should be allowed*, which is a change to what this path promises and not a widening of `read_back`.

### Amended 2026-09-07, on the operator's three corrections

**A DEAD ROW LEAVES THE RECORD.** This entry's title says the record holds every live row, and it did — plus every row TCGplayer no longer holds. `sold_out` is the only member of `UNPRICEABLE_CODES` since D109, so those rows can never be answered and existed on the lens purely as something to scroll past: **372 of the owner's 759 rows, so the screen drew nearly twice as many dead rows as live ones.** `Plan.surveyed` drops them.

**THE EXPORT IS NOT NARROWED, AND THAT IS THE WHOLE CARE IN THIS CHANGE.** The operator's first instinct was to scope the fetch — *"you need to select 'in stock' as part of your fetch"* — and two things stop it. `Export From Live` is `GET …/DownloadMyExportCSV?type=Pricing&exportLowestListingNotMe=true` and **ignores every parameter**, measured under D65 as eight spellings returning byte-identical output. More importantly the same file feeds `reconcile --live`, where **a SKU going from four copies to zero is how the store learns something sold**, and `pipeline/livecheck.py` tells a zero-quantity row from a SKU `absent` from the export entirely. Narrowing the download would erase that difference silently. The export stays complete; the WORKLIST is what gets narrowed, and the report still counts what it dropped.

**THE CUT-OFF IS DRAWN ON BOTH DOORS, WHICH REVERSES THIS ENTRY'S `repartition: false`.** The reason given was that *"the cut-off decides which import file a row is bound for, and a live listing is bound for none"* — right about the FILE and wrong about the FIGURE. **D99 made the line and the cheap price one variable**, so the cut-off also says what everything under it is worth, and that is as much a question about a live listing as about a card in a drawer. The operator's instruction was to reuse rather than rebuild: *"become pretty much as uniform as the pricing that comes from the runs path when it comes to using threshold — don't just rebuild the wheel when there's plenty to reference and reuse."*

So the lens draws `CutoffPanel` itself — same component, same `policy.threshold`, same `bucketAt` partition — and **the only difference between the doors is when the figure is spent**. `emit` prices a run's cheap half from `sub_threshold` at write time, so those rows need no press. A lens has no emit: `reprice apply` sends typed answers and nothing else, so the identical figure is spent by a press that writes real answers, in one act with one reversal. `CutoffPanel.applyCount` is `null` on a run, and a button there would offer to redo what the pipeline already does.

**A FIRST BUILD OF THIS WAS A BESPOKE TWO-FIELD WIDGET AND IT WAS WRONG TWICE.** It asked for a threshold *and* a price, which is the pair D99 had already ruled is one variable; and it collided with `.pricing-cheap`, the run's own cut-off panel, whose `flex-direction: column` won on source order and stacked the control into a tower. **A screen-prefixed class is not unique by itself.** Both are the same mistake — building beside the thing instead of reading it.

**THE PRESETS ARE REAL ON THE LENS, AND THE PRESS MEANS THE OPPOSITE THING ON EACH DOOR.** The operator asked what "Match market" and "Market −5%" do there, and the answer was: nothing good. `asRow` shipped `presets: {}`, so every lens row had no per-SKU figure and the buttons filled NOTHING — while still writing `policy.rule` and `policy.basis` to `inventory/prices.json`, which is the store-wide setting every future joined run lists by. **Measured on a copy of the owner's store: pressing `Market −5%` on the lens left 387 fields untouched and flipped the store's rule from `match` to `undercut:5`.** Repricing a live book silently repriced the next box out of the camera, and nothing on screen said so — D101's defect on the money path.

The figures are now computed server-side by `pipeline/pricing.py:preset_prices`, which is the SAME function a run's `pricing.json` uses, so two doors cannot compute a different number for one card. That table moved out of `cli/cmd_join.py` — a second copy of `Rule.apply` + `round_money` + `clamp_floor` is the thing D49 refused to have in two languages, and having it in two Python modules is the same bet at shorter odds. `make docs-audit`'s `pricing presets` row followed it and still reconciles; its resolver learned to read a bare `RULE_MATCH`, because inside `pricing.py` a `pricing.` prefix would be the module naming itself.

**And a preset writes ANSWERS on a lens where it writes a RULE on a run.** `emit` prices a run's unanswered rows by the standing rule at write time, so writing 300 per-SKU answers there would freeze a rule into figures — D54's staleness. `reprice apply` sends typed answers and nothing else, so on a lens the rule governs nothing and the press must write real answers or do nothing at all. It was doing exactly the wrong one of those. One act, one reversal, the same shape as the cut-off press.

**A ROW IT CANNOT PRICE IS LEFT AND NAMED.** `None` per preset key is a real answer: 394 of 2,476 rows on the wide Pokemon export carry a blank `TCG Low Price`. Measured here, 4 of 387 live rows could be priced by no preset at all.

**AND A BLANK BOX KEEPS THE PRICE IT ALREADY HAS, SAID ON THE SCREEN** (the operator, 2026-09-07). It was stated only once typing had begun — "the rest are left exactly as they are listed" — which is the moment it is least needed. An operator looking at 387 fields ghosting a faint current price has to know that leaving one alone changes nothing at TCGplayer, or the ghost reads as a value about to be re-sent. It is also the true rule: `pushable` collects rows carrying a typed answer and `apply` receives only those.

**THE FIELD'S GHOST IS THE LIVE PRICE.** D109 opened the lens field empty with the rule's figure behind it; the operator asked for the price they are actually asking now, *"in a faint gray… and it immediately gets rewritten once i type a new number."* `snap.now` is that cell, and because it is a placeholder rather than a value the first digit typed replaces it whole — no selecting and no backspace. It falls back to the rule only on a `no_asking_price` row, where there is no "now" to draw.
