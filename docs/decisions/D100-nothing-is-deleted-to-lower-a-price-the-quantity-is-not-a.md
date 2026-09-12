## D100 — Nothing is deleted to lower a price, the quantity is not a variable, and the age is a proxy that says so

**A live listing's price is lowered by re-uploading the same row with a new `TCG Marketplace Price` and `Add to Quantity` of 0. Nothing is deleted at TCGplayer, and nothing has to be.** Built 2026-09-03 on the owner's request: *"I then wanted to build some relationship where I can export my live inventory back out (for cards I have listed and aren't selling) and be able to mass re-edit the prices down (and then reupload it back) <maybe deleting inventory in between from tcgplayer?>"*

The parenthetical is the question this entry exists to answer, and the answer is measured rather than reasoned.

### `Add to Quantity` is a delta, and TCGplayer's own export is the proof

**72,701 real export rows carry `Add to Quantity` = `"0"`** — the four untouched fixtures (21,843 rows) and the twelve TCGplayer exports recorded into run directories (50,858 rows), which is the whole of it: 21,843 + 50,858 = 72,701. Not one row anywhere carries anything else. The owner's My Pricing download of 2026-09-01 is one of those twelve and is not a third source; an earlier draft of this paragraph counted it twice and put 40,858 against the run directories, which made the total right and the breakdown unreconcilable. Recounted 2026-09-04.

**649 of those are rows on which TCGplayer simultaneously reported live copies**, `Total Quantity` between 1 and 10, and every one still carries `Add to Quantity` = 0. That settles it on its own: if the column meant *set the quantity to*, re-uploading an untouched export would delist the entire account, and nobody ships an export that destroys the account it came from. `Total Quantity` is not a writable column at all, so **there is no CSV route to lowering or setting a quantity even for a caller that wanted one.**

**And the price column edits the live listing in place.** Of the 288 live SKUs in the 2026-09-02 export that this pipeline had pushed, **282 carry exactly the price the pipeline last wrote into an import CSV**; the other six sit a cent or two below. One listing per SKU, updated — not a second listing beside the first.

### The dangerous case already happened here, which is why it is designed out rather than avoided

**Ten live SKUs in that export held more copies than this pipeline ever pushed, and nine of them sit at exactly `2 x pushed - sold`.** Eight came from one file, `runs/2026-08-31-box3-01/import-subthreshold-riftbound.csv`. It was uploaded twice and every quantity on it was added twice: 2 became 4, 4 became 8, 3 became 6.

So the failure mode is not exotic and is not hypothetical — **it is one extra press on a file sitting in this repo**, and a markdown push that carried the copy count again would do it to every row it touched.

**The remedy is not a rule to remember. `pipeline/reprice.py:ADD_TO_QUANTITY` is a module constant — not a parameter, not a default, not reachable from a flag — so the quantity is not a variable anywhere on this path.** It is written explicitly on every row rather than left as the export found it, because a column left alone is a column nobody is asserting, and `tcgcsv.check_only_writable_changed` runs over every row on the way out. A worklist handed back carrying `Add to Quantity` 4 on every row still produces an upload carrying 0, and T7 asserts exactly that.

### The upload is built from the manifest's bytes, and the operator's file is an instruction sheet

**Only two cells are read out of whatever comes back — `TCGplayer Id` and `TCG Marketplace Price`.** Everything else comes from the export row the manifest kept verbatim.

**Because a spreadsheet is how a person does "mass re-edit", and a spreadsheet reformats.** It strips the leading zero from `Number` (`001/132` becomes `1/132`), strips a trailing zero from a price (`0.0100` becomes `0.01`), and writes `0` into an empty cell. Measured: a worklist mangled all three ways produces an `import.csv` byte-identical to the unmangled one. **The byte contract cannot be broken by the operator's editor, because the operator's editor is not where the bytes come from.**

**And prices are compared as `Decimal`, never as text.** A live export writes four decimal places and this writer emits two; equal as money, different as bytes, and a string comparison would read every untouched row as an edit and mark down the whole store on a rounding artifact.

### Two commands, because the operator's sentence has two halves

`reprice list` writes the worklist; `reprice apply` reads it back and writes the upload. Between them sits a spreadsheet, or nothing at all — **the worklist arrives with a price already proposed on every row**, so the common case is download, glance, hand it straight back.

**The worklist is in full export shape and carries `Add to Quantity` 0, so uploading it by mistake is harmless.** That is the property the shape was chosen for: every file this feature writes is safe to upload, whichever one the operator grabs.

**Both halves preview by default**, which is `pkmnscan prices adopt`'s rule and one more: `apply --write` is the last press before bytes leave for a marketplace, and the file it writes cannot be un-uploaded.

### "Not selling" is three terms and one of them is a proxy, and the proxy says so on every report

A SKU is stale when TCGplayer says it is **live now**, **no copy sold here inside the window**, and **this store has owned a copy for longer than the window**.

**The third term measures how long the card has been OWNED, not how long the listing has been live, and this store cannot measure the second.** `Listing` has no `first_listed_at`. `live_as_of` is **absent from all 443 stored listing payloads**, so it is backfilled from `at` on every one — and `at` means "last touched", with **346 of the 443 carrying one identical timestamp**, the D87 store-wide settlement. There is no listing age here to read.

**So the substitution is printed on the report's own header, on the screen in its own paragraph, and asserted in both the harness block and the browser spec.** A proxy nobody is told about is a lie, and this is the one figure in the report that is not what it looks like.

**Two implementation traps, both measured.** The age is taken over every card that ever carried the SKU, departed ones included — a floor over on-hand copies moves *forward* as the oldest copy sells, so a listing would get younger the longer it sat. And the sale is read off the CARD RECORDS and never the event log: **one of the 193 `sold` events on the owner's store carries no `sku` key**, while all 186 cards in the `sold` state carry both, so a query over the log loses that copy silently — and a SKU whose only sale is invisible reads as never sold, which is the exact input this lowers a price on.

### No sales velocity is invented, because none exists

The export carries **no sales window, no sample size, no last-sold date, no view count, no watcher count and no competing-seller count**, and TCGplayer publishes none of them anywhere — the `tcgplayer-csv` skill states it and D8 rests on it. `TCG Market Price` is their aggregate over recent sales: one number, no window.

**The one axis here that is not a proxy is `--above-market`**, which compares the asking price against `TCG Market Price` on the same row of the same file at the same instant. It is the only term that says anything about *why* a card is not selling. **It has to be read against D9's floor**: 115 of the owner's 441 live rows sit at or under `$0.40`, where a $0.03 card is correctly listed at the floor and is 1,233% above market as arithmetic rather than as overpricing.

### `asking` is a basis and is deliberately not one of `pricing.BASES`

The markdown is off the operator's own live price, which is `TCG Marketplace Price`. That column is populated on **441 of 441** live rows of a My Pricing export and **blank on 7,787 of 7,802 rows** of the wide Pokemon Filtered Export. Adding it to `pricing.BASES` would offer it on `join` and `emit` through `cli/__main__.py`'s `choices=`, where a blank basis cell leaves the price untouched with nothing anywhere raising. So `reprice.BASES` is local, and the argument lives beside it.

### The ratchet, and what guards it

`undercut:10` applied daily compounds to **-52% in a week**, floored only at `$0.40`, with every individual run justified because the card still has not sold and is still old.

**The guard is `corpus.Answer.at`**: a SKU this store answered inside the window is refused as `priced_recently` unless `--again`. It reads the corpus rather than the receipt directories — a directory can be deleted and an answer cannot be without also giving the card its rule price back — and it has a second correct consequence: **a card the operator hand-priced on `#/pricing` yesterday is not stale**, which is true and which no separate mechanism had to be built to say.

### The answer goes in the corpus, keyed by SKU

`apply --write` writes each new price into `inventory/prices.json` (D86). **Without it the next `emit` over another copy of the same card re-lists at the rule price and quietly undoes the markdown.** The marked-down price is the store's price for that SKU from then on, not a property of one file. `pipeline/corpus.py` is untouched: `Answer` already carries a value and a time, and nothing here needed a field it did not have.

### It wanted a route on D49's precedent, and it is a modal on `#/runs` instead

**It is a worklist the operator sits in over three presses, with a file leaving the machine in the middle of it and coming back** — which is exactly what earned `#/pricing` a route, and is not what `#/runs`' own lede describes when it names the four pipeline commands. So `#/markdown` was built, and then measured out.

**The measurement was taken against a shell that no longer exists, and it is recorded here rather than carried forward.** The horizontal nav strip needed 1,484.9px to draw eleven links on one row against a 1,440px desk: the aside group wrapped, the nav doubled from 45.5px to 90px, and `app/tests/review.spec.ts`'s between-cards floor — D28's, the one that says the photograph does not move as the operator answers — went red as the web font swapped in and tipped the wrap mid-screen. No label rescued it; the eleventh link would have had to be 68px wide and `Runs` was 72.6. **That strip is gone.** D95's shell is a sidebar collapsing to a rail with a command palette beside it, and a nav item there costs a row of vertical space rather than a share of one horizontal line — so the arithmetic that refused the route does not apply to the shell this lands on, and nothing here should be read as though it still does.

**The placement did not change with the shell, and the reason for it is now a judgement rather than a measurement.** This is a second modal on `#/runs`, opened from its own header button beside the store-wide reconcile, built as a structural sibling of `LiveReconcile.tsx`. That neighbor was always the right one: both read the same live export, and the order there is the order of the work — settle what TCGplayer holds, then decide about the part of it that is not moving. What was a forced choice is a deliberate one.

**What it costs is a hash of its own**, so the markdown cannot be linked to, bookmarked, or reached by a chord, and it opens over a screen whose first two thirds are about one run. `App.tsx`'s ROUTES table carries this reasoning where the row would have gone, so the next session to want the route finds the argument rather than rediscovering it — and the number above is now history, not a constraint to re-measure against.

### What it costs

**The worklist carries no reason column.** A seventeenth column would break the round-trip that makes the file safe to upload, so the reasoning is in `report.txt` beside it and a person editing in a spreadsheet cannot see why a row is there.

**Nothing this feature writes has been uploaded to TCGplayer.** Every measurement above is from files TCGplayer produced, or from files this pipeline produced that TCGplayer then accepted — none of it is a measurement of *this* file being accepted by the My Pricing importer. `docs/specs/stale-listings.md` §6 names the three unmeasured questions in order of consequence and the press that settles them: `--limit 5`, upload, then `reconcile --live` against a fresh download.

**And the whole thing is scoped to what one export says.** A listing on a SKU this store never held is reported and never touched, which is right, and means a person selling through two channels gets no help here with the other one.

**What would reopen this.** *The first upload*, whose answers belong in the spec's section 6. *A listing age this store can read* — populate `live_as_of` on a first sighting, or record a `first_listed_at` when `emit` pushes, and the third term stops being a proxy and the report's header paragraph goes away. *A reason column in the worklist*, at the cost named above. *An importer that rejects a zero-quantity row*, which would make the whole design unbuildable in this shape and is the one outcome the 649 rows argue hardest against.
