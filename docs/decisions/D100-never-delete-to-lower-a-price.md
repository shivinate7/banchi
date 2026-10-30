# D100 — Never delete to lower a price

**A live listing's price is lowered by re-uploading the same row with a new `TCG Marketplace Price` and `Add to Quantity` of 0. Nothing is deleted at TCGplayer, and nothing has to be.** Built on the owner's request: export live inventory (cards listed and not selling), mass re-edit the prices down, and re-upload. The owner asked whether inventory must be deleted at TCGplayer in between.

That question is what this entry exists to answer, and the answer is measured rather than reasoned.

### `Add to Quantity` is a delta, and TCGplayer's own export is the proof

**72,701 real export rows carry `Add to Quantity` = `"0"`** — the four untouched fixtures (21,843 rows) and the twelve TCGplayer exports recorded into run directories (50,858 rows). That is the whole of it: 21,843 + 50,858 = 72,701. Not one row carries anything else. The owner's My Pricing download is one of those twelve, not a third source. An earlier draft counted it twice and put 40,858 against the run directories. The total was right, but the breakdown did not reconcile.

**649 of those are rows on which TCGplayer simultaneously reported live copies**, `Total Quantity` between 1 and 10, and every one still carries `Add to Quantity` = 0. That settles it on its own. If the column meant *set the quantity to*, re-uploading an untouched export would delist the entire account. Nobody ships an export that destroys the account it came from. **`Total Quantity` cannot be set from a CSV, but a negative `Add to Quantity` lowers a live quantity (measured, amendment below).**

**And the price column edits the live listing in place.** Of the 288 live SKUs in the export, **282 carry exactly the price the pipeline last wrote into an import CSV**. This pipeline had pushed all 288. The other six sit a cent or two below. One listing per SKU is updated, with no second listing.

### The dangerous case already happened here, which is why it is designed out rather than avoided

**Ten live SKUs in that export held more copies than this pipeline ever pushed, and nine of them sit at exactly `2 x pushed - sold`.** Eight came from one file, `runs/2026-08-31-box3-01/import-subthreshold-riftbound.csv`. It was uploaded twice and every quantity on it was added twice: 2 became 4, 4 became 8, 3 became 6.

So the failure mode is not exotic and is not hypothetical. **It is one extra press on a file sitting in this repo.** A markdown push that carried the copy count again would do it to every row it touched.

**The remedy is not a rule to remember. `pipeline/reprice.py:ADD_TO_QUANTITY` is a module constant — not a parameter, not a default, not reachable from a flag — so the quantity is not a variable anywhere on this path.** It is written explicitly on every row rather than left as the export found it, because a column left alone is a column nobody is asserting. Also, `tcgcsv.check_only_writable_changed` runs over every row on the way out. A worklist handed back carrying `Add to Quantity` 4 on every row still produces an upload carrying 0, and T7 asserts exactly that.

### The upload is built from the manifest's bytes, and the operator's file is an instruction sheet

**Only two cells are read out of whatever comes back — `TCGplayer Id` and `TCG Marketplace Price`.** Everything else comes from the export row the manifest kept verbatim.

**Because a spreadsheet is how a person does "mass re-edit", and a spreadsheet reformats.** It strips the leading zero from `Number` (`001/132` becomes `1/132`), strips a trailing zero from a price (`0.0100` becomes `0.01`), and writes `0` into an empty cell. Measured: a worklist mangled all three ways produces an `import.csv` byte-identical to the unmangled one. **The byte contract cannot be broken by the operator's editor, because the operator's editor is not where the bytes come from.**

**And prices are compared as `Decimal`, never as text.** A live export writes four decimal places and this writer emits two. They are equal as money and different as bytes. A string comparison would read every untouched row as an edit and mark down the whole store on a rounding artifact.

### Two commands, because the operator's sentence has two halves

`reprice list` writes the worklist; `reprice apply` reads it back and writes the upload. Between them sits a spreadsheet, or nothing at all. **The worklist arrives with a price already proposed on every row**, so the common case is download, glance, hand it straight back.

**The worklist is in full export shape and carries `Add to Quantity` 0, so uploading it by mistake is harmless.** That is the property the shape was chosen for: every file this feature writes is safe to upload, whichever one the operator grabs.

**Both halves preview by default**, which is `banchi prices adopt`'s rule and one more. `apply --write` is the last press before bytes leave for a marketplace, and the file it writes cannot be un-uploaded.

### "Not selling" is three terms and one of them is a proxy, and the proxy says so on every report

A SKU is stale when TCGplayer says it is **live now**, **no copy sold here inside the window**, and **this store has owned a copy for longer than the window**.

**The third term measures how long the card has been OWNED, not how long the listing has been live, and this store cannot measure the second.** `Listing` has no `first_listed_at`. `live_as_of` is **absent from all 443 stored listing payloads**, so it is backfilled from `at` on every one. And `at` means "last touched", with **346 of the 443 carrying one identical timestamp**, the store-wide settlement of D87 (reconcile writes live). There is no listing age here to read.

**So the substitution is printed on the report's own header, on the screen in its own paragraph, and asserted in both the harness block and the browser spec.** A proxy nobody is told about is a lie, and this is the one figure in the report that is not what it looks like.

**Two implementation traps, both measured.** The age is taken over every card that ever carried the SKU, departed ones included. A floor over on-hand copies moves *forward* as the oldest copy sells, so a listing would get younger the longer it sat. And the sale is read off the CARD RECORDS and never the event log. **One of the 193 `sold` events on the owner's store carries no `sku` key**, while all 186 cards in the `sold` state carry both. So a query over the log loses that copy silently. A SKU whose only sale is invisible reads as never sold, which is the exact input this lowers a price on.

### No sales velocity is invented, because none exists

The export carries **no sales window, no sample size, no last-sold date, no view count, no watcher count and no competing-seller count**. TCGplayer publishes none of them anywhere. The `tcgplayer-csv` skill states it and D8 (export is the price source) rests on it. `TCG Market Price` is their aggregate over recent sales: one number, no window.

**The one axis here that is not a proxy is `--above-market`**, which compares the asking price against `TCG Market Price` on the same row of the same file at the same instant. It is the only term that says anything about *why* a card is not selling. **It has to be read against the floor in D9 (cut-off is the price floor)**: 115 of the owner's 441 live rows sit at or under `$0.40`. There a $0.03 card is correctly listed at the floor and is 1,233% above market as arithmetic rather than as overpricing.

### `asking` is a basis and is deliberately not one of `pricing.BASES`

The markdown is off the operator's own live price, which is `TCG Marketplace Price`. That column is populated on **441 of 441** live rows of a My Pricing export and **blank on 7,787 of 7,802 rows** of the wide Pokemon Filtered Export. Adding it to `pricing.BASES` would offer it on `join` and `emit` through `cli/__main__.py`'s `choices=`, where a blank basis cell leaves the price untouched with nothing anywhere raising. So `reprice.BASES` is local, and the argument lives beside it.

### The ratchet, and what guards it

`undercut:10` applied daily compounds to **-52% in a week**, floored only at `$0.40`, with every individual run justified because the card still has not sold and is still old.

**The guard is `corpus.Answer.at`**: a SKU this store answered inside the window is refused as `priced_recently` unless `--again`. It reads the corpus rather than the receipt directories. A directory can be deleted, and an answer cannot be without also giving the card its rule price back. It also has a second correct consequence: **a card the operator hand-priced on `#/pricing` yesterday is not stale**. That is true, and no separate mechanism had to be built to say it.

### The answer goes in the corpus, keyed by SKU

`apply --write` writes each new price into `inventory/prices.json`, per D86 (one pricing file for the store). **Without it the next `emit` over another copy of the same card re-lists at the rule price and quietly undoes the markdown.** The marked-down price is the store's price for that SKU from then on, not a property of one file. `pipeline/corpus.py` is untouched: `Answer` already carries a value and a time, and nothing here needed a field it did not have.

### It wanted a route on D86's precedent, and it is a modal on `#/runs` instead

**It is a worklist the operator sits in over three presses, with a file leaving the machine in the middle of it and coming back.** That is exactly what earned `#/pricing` a route, and it is not what `#/runs`' own lede describes when it names the four pipeline commands. So `#/markdown` was built, and then measured out.

**The measurement was taken against a shell that no longer exists, and it is recorded here rather than carried forward.** The horizontal nav strip needed 1,484.9px to draw eleven links on one row against a 1,440px desk. The aside group wrapped, and the nav doubled from 45.5px to 90px. `app/tests/review.spec.ts`'s between-cards floor went red as the web font swapped in and tipped the wrap mid-screen. That floor is the one in D28 (list holds still), which says the photograph does not move as the operator answers. No label rescued it; the eleventh link would have had to be 68px wide and `Runs` was 72.6. **That strip is gone.** The shell of D95 (rail, palette, reference sheet) is a sidebar collapsing to a rail with a command palette beside it. A nav item there costs a row of vertical space rather than a share of one horizontal line. So the arithmetic that refused the route does not apply to the shell this lands on, and nothing here should be read as though it still does.

**The placement did not change with the shell, and the reason for it is now a judgement rather than a measurement.** This is a second modal on `#/runs`, opened from its own header button beside the store-wide reconcile, built as a structural sibling of `LiveReconcile.tsx`. That neighbor was always the right one. Both read the same live export. The order there is the order of the work: settle what TCGplayer holds, then decide about the part of it that is not moving. What was a forced choice is a deliberate one.

**What it costs is a hash of its own**, so the markdown cannot be linked to, bookmarked, or reached by a chord. It also opens over a screen whose first two thirds are about one run. `App.tsx`'s ROUTES table carries this reasoning where the row would have gone, so the next session to want the route finds the argument rather than rediscovering it. The number above is now history, not a constraint to re-measure against.

### What it costs

**The worklist carries no reason column.** A seventeenth column would break the round-trip that makes the file safe to upload. So the reasoning is in `report.txt` beside it, and a person editing in a spreadsheet cannot see why a row is there.

**Nothing this feature writes has been uploaded to TCGplayer.** Every measurement above is from files TCGplayer produced, or from files this pipeline produced that TCGplayer then accepted. None of it is a measurement of *this* file being accepted by the My Pricing importer. `docs/specs/stale-listings.md` §6 names the three unmeasured questions in order of consequence and the press that settles them: `--limit 5`, upload, then `reconcile --live` against a fresh download.

**And the whole thing is scoped to what one export says.** A listing on a SKU this store never held is reported and never touched, which is right. It means that a person selling through two channels gets no help here with the other one.

**What would reopen this.** *The first upload*, whose answers belong in the spec's section 6. *A listing age this store can read.* Populate `live_as_of` on a first sighting, or record a `first_listed_at` when `emit` pushes. The third term then stops being a proxy, and the report's header paragraph goes away. *A reason column in the worklist*, at the cost named above. *An importer that rejects a zero-quantity row*, which would make the whole design unbuildable in this shape and is the one outcome the 649 rows argue hardest against.

### Amended: a dollar cap on the rule, and no mark-down without a market price

Two rules change.

- **A dollar cap.** A read can carry a cap (`reprice list --cap`, the Live tab's Change sheet).
  The rule then takes P% off, but never more than the cap off one copy. `pipeline/reprice.py:plan`
  proposes the rule's price or the asking price less the cap, whichever is higher. The cap lives
  in the read's `asked`, beside the percentage. With no cap in the last read, the sheet offers
  none. Amended the same day by owner ruling: rule only. The cap limits the rule's
  proposal and nothing else. `reprice apply` does not check it, and a typed price goes out as
  typed. The store's floor (`policy.threshold`) still holds for every price.
- **No market price, no mark-down.** `plan` refuses a row with no `TCG Market Price` as
  `no_market`, before the rule prices it, on every basis. The asking-price basis could price it,
  and that was the defect. A card nobody has priced is the owner's to price by hand, per D86 (one pricing file for the store).

Proof: T7 `check_live_markdown_guards`, each rule red under its own mutation.

### Amended, second: an earlier price goes out only when it is higher

Owner ruling: a typed price goes out when it is higher. `reprice apply` refuses an
edit that lowers the price and is exactly an answer the corpus held before the read was taken
(`earlier_lower`), per row. A price written after the read is stamped later and goes. The read's
own rule price always goes. Proof: T7 `check_live_markdown_guards`.

### Amendment: a negative `Add to Quantity` lowers a live quantity, measured

**This replaced the earlier "no CSV route to lowering a quantity" clause above, in place.** Measured through `server/tcg_import.push_to_staged` and `move_to_live`, with `_check` bypassed once on the owner's word. One row first: Eclipse 9198194, `Add to Quantity` -1, price unchanged. TCGplayer accepted 1 of 1, publish answered 1 Update, and the live export went from 1 to 0 within about 2 minutes (`live-tcgplayer-20260929-024030.csv`). Then 63 rows with negative adds: accepted 63, 63 Updates, no errors, all 63 reached target (live copies 2740 to 2645, `live-tcgplayer-20260929-024057.csv`). `Add to Quantity` is a signed delta. A third push on the owner's word, the same day: 21 SKUs, -34 copies, writing live down to the store's identified count wherever live was higher (upload 17334855, 21 accepted, 21 Updates). The export after it (`live-tcgplayer-20260929-024900.csv`, 2611 live copies) shows 0 store SKUs above their held count. Cause, unmeasured per SKU: cards marked sold or retired in the app never lower TCGplayer, plus likely a double upload (the case above).

**The owner decided it: a hold takes live copies off.** When the owner holds a SKU (`bullish`, `keeping`, `next_batch`), the next send writes one row for it. That row has `Add to Quantity` minus the live quantity a fresh live read shows for it, less the copies marked sold since that read. The press fetches that read and works on every held SKU in the store, not only those in the selected runs. `emit` needs `--live-guard` with a file at most an hour old (`TAKE_READ_FRESH_S`). A held SKU with no such read is named in the output and takes off nothing. If Banchi has sent copies of such a SKU, the whole emit refuses with a sentence naming the card and writes nothing. Neither `pushed` nor `live` sizes the row, and a held SKU the read does not name takes off 0. At most one take-off is outstanding per SKU: from the moment its file is written (a press or a download) until a live check past the wait settles it. While one is outstanding no new row is written for that SKU, and the output names the card and says it is outstanding. If the check finds the copies gone, `pushed` falls and `live` is set to the read, once per SKU. If they are still live, the take-off never landed, and only then may a new one be sized. A failed press writes nothing that can land, so it never blocks. Nothing in the store changes at write time. The cards stay in their box and stay sent until the check. Unhold sends them again after it. A copy the owner removed from TCGplayer by hand is not a withhold. It takes nothing else off, and it is held per copy on the listing, per D273 (one press sends listings live) and R-S4. The receipt and the CLI say how many copies come off TCGplayer, and a download says the file takes them off. `server/tcg_import._check` takes a SKU-to-size mapping from `emit` and passes a negative only when its size equals that figure. Every other path still refuses one, and only the two writable columns are written. A held SKU in none of the selected runs is written on the live read's own row. **Measured: TCGplayer clamps a take-off at 0.** One row for Rebuttal (SKU 9405578, Near Mint Foil), `Add to Quantity` -5 against `Total Quantity` 2, was pushed through `push_to_staged` (with `_check` bypassed once) and `move_to_live` (upload 17529205). The move answered Update with no error. A fresh live export read `Total Quantity` 0 with the price unchanged at 4.39. A doubled take-off therefore cannot go below zero, so a download uploaded late after a second take-off is harmless and no guard is built for it. The reprice path's `Add to Quantity` 0 rule is untouched. `banchi reconcile --phantoms` remains a worklist tool. It finds only ghost cards, whose box has no row.

### Amendment: a sale or retirement in the app never lowers TCGplayer

**Owner ruling: marking a card sold or retired in the app must not lower its TCGplayer quantity.** The phantom-listing finding in the amendment above (sold or retired cards never lower TCGplayer) is therefore accepted behavior. The drift it leaves is corrected by an explicit write-down.

**Owner ruling: a phantom is cleared by a session, not by a screen.** A phantom is a SKU that TCGplayer lists above what is on hand, less what sold since the live read. One kind is a ghost card. Another is a card sent under one SKU and then corrected to another (`sku_corrected` with `released.pushed`), which leaves the old listing live with no card behind it. A session finds phantoms on the owner's request, names each one with its live and on-hand counts, and sends a take-off only on the owner's yes for that SKU. The row is `Add to Quantity` minus the excess, price unchanged, sized from the newest live read and never above it. It goes through `server/tcg_import.push_to_staged` with `listing=True` and a `take_off` mapping of that exact size, then `move_to_live`, and a fresh live read confirms it. No screen control or send-path lane is built for phantoms, because the session identifies them. **One exception, on the owner's word: a master-set pull.** When a card retired with reason `master_set` leaves its SKU live above on hand, the retire receipt offers one press that sends this same take-off for that SKU. The press is the owner's yes. A take-off not pressed, or one that failed, stays on an owed list on the Pricing send card with the same press, and every try is a send receipt. It covers that reason only (`docs/specs/master-set.md` section 5).
