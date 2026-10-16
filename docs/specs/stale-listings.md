# Stale listings, and the markdown that pushes them back

**STATUS: SPECIFIED and BUILT.** The two commands, the routes, the lens on `#/pricing`, the
send routes and the harness blocks exist. TCGplayer's importer accepted a real price-only
import, and a one-row push and publish ran through this repo's routes. The rule that proposes
prices has not run at scale against TCGplayer. §6 says which claims stay unmeasured.

Governed by D100 (never delete to lower a price), D103 (the markdown is a lens on `#/pricing`),
D105 (it lives where prices are decided), D107 (a typed raise goes through), D109 (listing
age) and D273 (one press to send). The decision entries carry the argument. This file carries
what was measured, what was given up, and what would reopen it.

---

## 1. What it does

The operator downloads their **My Pricing** export from TCGplayer, or fetches it with
**Fetch my live listings**. It is the file `reconcile --live` reads (D87).

The command `reprice list` reports the listings that are live at TCGplayer. It selects those
that have not sold here inside a window and have been listed longer than the window. It also
reports what each would be re-priced to. With `--write` it produces a **worklist**: the same
rows, in export shape, with a price already proposed on every one.

The operator edits the worklist or does not. `banchi reprice apply` reads it back and writes
**`import.csv`**, the file for TCGplayer's My Pricing.

```
./banchi reprice list  <my-pricing.csv> [--days N] [--percent P] [--write]
./banchi reprice apply <worklist.csv> [--corpus-revision <digest>] [--write]
```

Both halves preview by default. `--write` also leaves a `survey.json` that holds every live
row with its verdict. `#/pricing?markdown=<stamp>` prices those rows in the same screen that
prices a joined run, charts included. §5 has the shape. The screen can also push the file to
TCGplayer's staged copy, publish it, or do both in one press (`send`). §8 lists the routes.

## 2. Nothing is deleted at TCGplayer, and the evidence is in this repo

The question was whether inventory must be deleted from TCGplayer between the export and the
re-upload. **It need not.** Three findings settle it.

### `Add to Quantity` is a delta, and TCGplayer's own export says so

Every real export row that TCGplayer produced carries `Add to Quantity` = `"0"`. Rows that
carry a non-zero value are all in files this pipeline wrote, which is the column doing its
job. Many of those export rows also report live copies (`Total Quantity` from 1 to 10), and
they still carry 0. That is decisive alone. If the column meant *set the quantity to*, an
untouched re-upload would delist the seller's whole inventory. TCGplayer does not ship an
export that destroys the account it came from.

`Total Quantity` is not a writable column (`pipeline/tcgcsv.py:WRITABLE_COLUMNS`, and the
`tcgplayer-csv` skill). A negative `Add to Quantity` does lower a live quantity (D100's
amendment). This feature never writes one.

### The price column edits the live listing in place

The `TCG Marketplace Price` cell of an uploaded row sets the price of the existing listing,
matched on `TCGplayer Id`. A second listing is not created, and the old one does not have to
be removed first. Live SKUs that this pipeline had pushed carried the price it last wrote.

### The doubling is real

An import file that was uploaded twice added every quantity twice. The listings were updated
and not duplicated: one listing per SKU, at double the quantity. **The dangerous case is one
extra press on a file that sits in this repo.** A markdown push that carried the copy count
again would do that to every row it touched.

### What follows

`Add to Quantity` is `0` on every row of every file this feature writes, the worklist and the
import alike. `pipeline/reprice.py:ADD_TO_QUANTITY` is a module constant. It is not a
parameter, not a default and not reachable from a flag: **the quantity is not a variable
anywhere on this path.** It is written explicitly, because a column left alone is a column
that nobody asserts. `tcgcsv.check_only_writable_changed` then runs over every row on the way
out.

## 3. What "not selling" can honestly mean

A SKU is stale when **all three** hold:

1. **Live now.** `Total Quantity > 0` in the My Pricing export. A fact from TCGplayer, as of
   the moment of the download.
2. **No sale here inside the window.** No card of that SKU is in the `sold` state with a
   `state_at` inside the window.
3. **Listed longer than the window.** `store/master.py:Listing.first_seen_live` is the
   earliest export that held the SKU live (D109). `reconcile --live --write` records it,
   and only the earliest sighting wins.

### Term 3 falls back to a proxy, and the report says so

Where no export has caught the SKU yet, term 3 falls back to the oldest `captured_at` of any
card that ever carried it. That measures how long the card has been **owned**, not how long
the listing has been live. It is a floor on the real age, so it can make live SKUs
`too_young`. Every report counts
both clocks and says which one dated which rows. A proxy that nobody is told about is a lie,
and so is one claimed where it is not used.

### Term 2 reads the card records and never the event log

A `sold` event can carry no `sku` key. A query over the log loses that sale silently, and a
SKU whose only sale is invisible reads as "never sold". That is the exact input that this
command lowers a price on. Every sold card record carries both a SKU and a `state_at`.

### The fallback counts departed cards too

A floor taken over on-hand copies alone moves *forward* as the oldest copy sells, so a listing
would get younger the longer it sat. `cli/cmd_reprice.py:_card_facts` walks every card that
ever carried the SKU.

### The one axis that is not a proxy

`--above-market P` compares the operator's asking price with `TCG Market Price` on the same
row of the same file at the same instant. It needs no history and no inference. It is the
only term that says anything about *why* a card is not selling.

**Read it against the floor.** A cheap card is correctly listed at the floor. It is far above
market as an arithmetic result of the floor, and not as an overpricing.

**The floor is the store's own cut-off, and not `pipeline/pricing.py`'s constant** (D9,
amended). `policy.threshold` is the figure the operator sets on `#/pricing`. It earns a
listing, and it is what the cheap half goes out at. Nothing here may be priced below it.
`cli/cmd_reprice.py` reads it and hands it to both `plan` and `read_back`.

The constant was once on both and read by nobody. An operator cut-off below it made `apply`
refuse most of a worklist as `below_floor`. That happened after all the answers were written
into `prices.json`. The screen, the corpus and the receipt then all agreed that the work was
done. Both halves need the same figure.

### What no amount of work here can know

The export carries **no sales window, no sample size, no last-sold date, no view count and no
watcher count**. It carries no competing-seller count either. TCGplayer publishes none of
them. The `tcgplayer-csv` skill states this, and D8 rests on it. `TCG Market Price` is their
own aggregate over recent sales, one number with no window behind it. **There is no
sales-velocity figure in this product, and this feature does not invent one.**

## 4. What the windows select

The windows select by age and by sales. A window longer than the store's age selects nothing.
That is a fact about the store and not about the feature. The counts of live, held and sold
SKUs move with every export, so none is recorded here. Run `banchi reprice list` on a
current export to measure them.

## 5. The four files, and why the worklist is not the upload

| file | what it is |
|---|---|
| `worklist.csv` | the stale rows in export shape, price already proposed. What the operator edits. |
| `manifest.json` | what the **offer** said per SKU, **including the row's own bytes**. |
| `survey.json` | **every live row the export carried**, with its verdict and its own bytes (D103). What `#/pricing`'s lens draws. A row with no live copies is left out. |
| `import.csv` | what `apply --write` produces. The file that goes to TCGplayer. |

`report.txt` and `receipt.txt` sit beside them.

**`survey.json` is a fourth file and not a wider manifest.** `_apply` builds the upload's
bytes from `manifest["skus"]`, so leaving that key alone keeps the money path untouched. Also
`server/pipeline_routes.py:_markdown_summary` parses the manifest for every stamp to answer
`GET /pipeline/markdowns`. A wide manifest would make that list parse megabytes.

**`--write` produces the directory even when the plan proposes nothing**, with a header-only
worklist. The lens is reached by a stamp, so a window that selects zero rows must still leave
something to address.

The files live in `inventory/markdowns/<stamp>/`, under `inventory/` and never under `runs/`.
A run directory is one box's immutable input and is disposable. A markdown is store-wide and
is state.

**`apply` reads exactly two cells** from whatever the operator hands back: `TCGplayer Id` and
`TCG Marketplace Price`. It takes every other byte from the manifest. A spreadsheet reformats
cells on open and on save. It strips the leading zero from `Number` (`001/132` becomes
`1/132`), strips a trailing zero from a price (`0.0100` becomes `0.01`), and writes `0` into an
empty cell. A worklist mangled all three ways produces an `import.csv` **byte-identical** to the
unmangled one. The edited file is an instruction sheet, and never a source of bytes.

The worklist is in full 16-column export shape and carries `Add to Quantity` 0. So
**uploading the worklist by mistake is harmless**: it applies the proposed markdown and moves
no quantity.

**What this gives up:** the worklist carries no "why this row is here" column. A seventeenth
column would break the round trip above. The reasoning is in `report.txt`. A request for the
reasons in the spreadsheet reopens the file's shape.

### It opens on `#/pricing` as a lens (D103)

**`#/pricing?markdown=<stamp>` draws every live listing the survey saw**, in the screen where
new inventory is priced. That screen has the rule strip and presets, **Load trends**,
`PriceHistoryPanel`, snap-to-column, holds, the undo and the keyboard walk. It is the Live tab
(D277). **Staleness is a filter over it**, and it defaults to *All*, because a window can select
few rows or none.

**No `ROUTES` row.** The hash router strips `?…`. The screen addresses itself by `?run=` and
`?markdown=`, so no route is added and the mechanical route counts do not move. The lens has an
address that can be bookmarked, is in the palette and is reachable by chord. A second pricing
route would be two screens for one job.

**The lens needs a door that a human can reach.** A lens that could be opened only by typing
its URL would leave every mechanical check green over a screen that no person can open. So the
Live tab lists the markdowns, and it opens on the newest stamp when none is in the hash. A
history row whose directory holds no `survey.json` keeps its downloads and nothing more. An
offer that leads to a refusal is worse than no offer. `app/tests/pricing-markdown.spec.ts`
asserts the stamp in the hash, so a door wired to the wrong stamp would fail.

**A markdown from an earlier day can be handed back.** Re-picking the export would mint a new
stamp, and the edited file would be judged against a manifest that is not its own. So a
history row resumes at the original stamp.

The palette matches a route's `keywords` by substring. `#/pricing` carries *stale*, *markdown*,
*reprice* and *live listings*, so the feature is findable.

**Basis and rule are on the screen.** *New price is* takes **A percentage under** or
**Exactly**. *Cut comes off* takes **Your asking price**, **Market** or **TCG Low**. The two
mirror `cli/__main__.py`'s mutually exclusive `markdown_size` group. `_markdown_flags` reads
`rule` first and `percent` only after it, so a request that carries both would silently drop
one. Picking *Exactly* removes the percent field and does not disable it.

**`markup` is not offered.** It is a real `pricing.Rule`. On this path a price above the live
one is a raise, and the rule cannot propose one (§6b).

**`asking` is the default basis.** `TCG Marketplace Price` is filled on every live row of a My
Pricing export and is blank on nearly every row of the wide Filtered Export. So
`reprice.BASES` is local to that module and is not added to `pricing.BASES`. A history row
names the basis only when it is not the default.

**Step 1 is a press** (D104). **Fetch my live listings** calls `POST /pipeline/live-export`,
which runs `server/tcg_export.py:fetch_live`. One fetch feeds both consumers. The file is kept
and named, and either route takes `fetched: <name>` in place of an upload. So a markdown and a
reconcile act on **one** reading and not on two downloads minutes apart. The drop zone stays. A
person with a download in hand should not fetch again, and a dead cookie must not be a dead end.

**The request was captured off the portal, and was not designed.** `Export From Live` sends
`GET /Admin/Pricing/DownloadMyExportCSV?type=Pricing&exportLowestListingNotMe=true` (`LIVE_QUERY`),
with no category, no sets, no conditions and no POST body. A guessed filtered POST with
`CategoryId: "0"` came back as a valid header with **zero rows**, because that select has no
all-rows option. So this endpoint fails *empty*, and not with `System Error`. `fetch_live`
refuses an export with no rows outright. Otherwise the lens would draw an empty inventory, and
a reconcile would write `live: 0` across the store.

**The screen sends `edits`.** It does not send a CSV that the browser wrote, because PapaParse
is not a runtime dependency of the app. The pairs go as JSON, and `do_markdown_apply` writes
them with `tcgcsv.write_csv`. T7 asserts that the resulting `import.csv` is byte-identical to
the worklist path's.

**A price above the live price is marked on the row.** `fieldState` says "Above the live price"
at the keystroke.

### The markdown is a lens, and does not have its own route

D86's precedent says a worklist that the operator sits in earns a route. This one did not,
for two reasons that still hold. First, the lens already has an address. Second, reading one
export is kinship of implementation. `#/runs` is the pipeline over a box just photographed. A
markdown decides a **price** over inventory already listed, and this product has a screen
where prices are decided (D105). `LiveReconcile` stays on `#/runs`. It writes `live` onto the
store's own listing records (D87), which is a fact about inventory, so it lives where the other
inventory facts live.

`app/src/App.tsx` renders the view under `key={path}`, where `path` is the hash minus its
query. So `#/pricing` and `#/pricing?markdown=<stamp>` are one key. A press that writes the
stamp into the hash changes the rows under the operator, on the screen where they stand.

### Prices are compared as `Decimal`, never as text

A live export writes four decimal places (`"0.6600"`). This writer emits two (`"0.66"`). They
are equal as money and different as bytes. A string comparison would read every untouched row
as an edit and mark down the entire store on a rounding artifact. T7 asserts it.

### Refusals

`reprice list`, per row:

| code | when |
|---|---|
| `sold_out` | `Total Quantity` 0. The export keeps the row. There is no listing. |
| `not_this_store` | live at TCGplayer, and no card here ever carried the SKU |
| `held` | withheld in the corpus (D86), and live. Reported, never silently marked down. |
| `sold_recently` | a copy sold here inside the window |
| `too_young` | listed for less than the window, or a stamp that does not parse |
| `priced_recently` | this store answered this SKU's price inside the window (the ratchet) |
| `no_asking_price` | live with a blank `TCG Marketplace Price` |
| `no_basis` | the chosen basis column is blank or zero (`pricing.has_market_data`) |
| `near_market` | not far enough above `TCG Market Price` for `--above-market` |
| `at_floor` | already at the store's cut-off, or the rule would land there |
| `not_a_markdown` | the rule would raise the price or leave it |

`reprice apply`, per row. The `duplicate` refusal is the one that refuses the **whole file**:

| code | when |
|---|---|
| `unchanged` | the same price as now. Dropped, because a no-op row reads like a press that did something. |
| `below_floor` | under the store's cut-off. The sentence carries no figure. The report's own `floored at` line prints it, from the value used. |
| `not_in_worklist` | a SKU this worklist was not written for, so there are no bytes to build a row from |
| `raised` | retired as a refusal by D107. An operator's raise is sent and named. The code stays in the vocabulary so older receipts still render. |
| `duplicate` | **whole file.** Two rows, one SKU. Undefined behavior in a TCGplayer import (D7). |

A deleted line is not a refusal. **Deleting a row is how a person says "not this one".** The
report names how many rows were dropped that way.

### The ratchet

`undercut:10` applied daily compounds to about −52% in a week, floored only at the store's
cut-off. Every single run is justified, because the card has still not sold and is still old.
The guard is `corpus.Answer.at`. A SKU that this store answered inside `--days` is refused as
`priced_recently`, unless `--again`. **It reads the corpus and not the receipt directories.** A
directory can be deleted. An answer cannot be deleted without giving the card its rule price
back. And a card that the operator hand-priced yesterday is, correctly, not stale.

### The answer goes in the corpus

`apply --write` writes each new price into `inventory/prices.json` as a per-SKU `Answer` (D86).
Without that, the next `emit` over another copy of the same card re-lists it at the rule price
and quietly undoes the markdown. The marked-down price is the store's price for that SKU from
then on. It is not a property of one file.

## 6. What is not known, and it is the part that carries money

These are the lessons from driving TCGplayer's importer with real files.

1. **The importer accepts a zero-quantity, price-only row.** TCGplayer's validator reports the
   headers as valid and the records as processed, with no duplicates. The import then
   completes.
2. **It accepts a subset of rows.** Rows that are absent from the file are left alone.
3. **A price change stages, and staging is total.** `Import To Staged` puts nothing in front of
   a buyer. Re-fetching the live export after an upload showed no change in any live price and
   no change in any live quantity. A separate `Move To Live` press changes what a buyer pays.
   `POST /pipeline/markdowns/<stamp>/push` stages. `.../publish` moves live. `.../rollback`
   discards a staged upload before it is published.
4. **The live export can be fetched.** It has every product line, and it matches the download
   that the owner takes by hand.
5. **A push and a publish through this repo's routes changed a real price and reverted it.**
   The form encoding is right. TCGplayer accepted the row with no errors and no warnings.
   Once a row is live, the way back is another markdown. `rollback` no longer applies.
6. **`Export From Live` is not read-your-writes.** After a confirmed publish, the export kept
   serving the old price for a while. The portal's own grid served the new one. So a reconcile
   run soon after a publish writes the pre-publish price into the store's `live` field (D87).
   `PUBLISH_LAG_S` in `cli/cmd_reprice.py` is a guess at the lag. **Unmeasured:** the real
   lag. To measure it, publish one SKU and fetch the live export at a fixed interval. Record
   the interval at which its price agrees.

**A deny-list over a surface that nobody has seen fails open.** A session that drives a path like
this blocks every non-GET by default and allows only what it has observed and judged. It proves
that the guard fires on a harmless write before it points the guard at a real file. `Import To
Staged` is not a live write, and that is what keeps a mistake recoverable.

## 6b. This path can raise a price (D107)

**The operator's typed price goes through in either direction. The rule still cannot propose a
raise.** `plan` refuses its own non-markdown proposal (`NOT_A_MARKDOWN`). This is a *markdown*
rule. It ranks by staleness and cuts by a percentage. A rule that points up would need a
market-movement trigger, which is a sibling command and not a flag. So **a price above `was`
that reaches `read_back` is one that a person typed**. That is why letting it through is safe.
It is an argument from the code and not from intent.

The screen draws a price field on every live row. An `apply` that refused the whole file when
a typed price pointed up would offer a control that it would not honor.

**What D100 protects is untouched.** `Add to Quantity` is 0 on every row, including a raised
row. Nothing is deleted at TCGplayer. A duplicate SKU is still fatal. The argument that a file
is safe to upload by accident points this way. An upload by mistake that raises costs sales
until it is noticed. One that lowers sells real stock at the wrong price and cannot be
recalled.

**A raise is never silent.** `Application.raised` and `taken_on` sit beside `lowered` and
`given_up`. The preview and `receipt.txt` name the count and the amount on their own line, with
a `^` on the row. **`given_up` counts reductions only.** It answers what the press costs.
Netting a raise against a markdown would report a file that cuts $40 and lifts $40 as free.

**Not built:** a rule that proposes raises, and any plausibility check on the figure.
TCGplayer's own 0.01–200,000 validator is the only ceiling, and `server/tcg_import.py`
enforces it.

## 7. What is reversible

**Reversible.** Both previews, which write nothing and can run again. The worklist and the
import, which are files. A staged upload, until it is published (`rollback`). The corpus
answers: clearing an answer restores rule pricing, and `receipt.txt` holds what each SKU was
asking before.

**Not reversible.** Once a file is published at TCGplayer, the prices have moved. They can be
pushed back with another markdown, but a sale at the lower price is done. The one thing that
cannot go wrong this way is the quantity, because no file on this path can move one.

## 7b. Pricing opens on fresh prices, with more on T

**STATUS: BUILT.** `server/pipeline_routes.py:do_prices_refresh` is the one home, T7's
`price_fresh` group proves the server half and the Pricing specs the screen half. It started from four
rulings by the owner. The daily job also refreshes Market and Lowest for every card waiting to be
sent. The screen opens with the morning's data already in it. A press brings everything current.
The row grows by two columns, and the rest waits behind T.

### The defect, measured

A waiting card draws `snap` from its run's `pricing.json`. The join wrote that table from the
catalog export it read that day, and nothing writes it again. The daily job (D104, live fetch is
its own guarded constant) reads the live listings and the Trends strips. Neither reaches `snap`.

One waiting card showed Market $10.37 and Lowest $9.06 from its batch. Its saved strip says
$16.25 for the same SKU on the day of the read. Six waiting cards were compared with the newest
point of their strips. The batch Market was off by 7% to 64% of the current figure. Five of the
six were off by more than 10%.

The join derives more from that cell, and all of it is stale too. That covers the bucket
(`listable` or `sub_threshold`, D9, cut-off is also the price floor), the preset figures and
`rule_price`. It also covers the price `emit` writes for a card with no typed answer. A fix that
only repaints the two cells leaves the screen proposing one price and the send writing another.

### Decision: refresh the run tables, never overlay them

**The cause is that a run table is a copy that nothing refreshes.** So the job refreshes the
copy, through the path that already makes it. It does not add a second figure beside `snap`.

The unit is the existing pair `do_pipeline_export`, then `do_pipeline_step(name, "join", ...)`.
`do_run_match` already composes it for one run. A new `pipeline_routes.do_prices_refresh`
composes it for every open run (the roster of `do_pipeline_worklist`), in this order:

| step | what it does | reads | writes |
|---|---|---|---|
| 1. listings | `do_live_export`, unchanged | one portal request | `inventory/.live/`, the readings table |
| 2. catalog prices | per game with a waiting card: `do_pipeline_export` with `refresh: true` once. `_reusable` then serves every later run of that game for `EXPORT_REUSE_S` | one portal request per game | `inventory/.exports/<game>/` |
| 3. join | per open run: `do_pipeline_step(name, "join", {"fetched": [file]})` | local | each run's `pricing.json`, and the readings table (`reading_from_table`) |
| 4. sales history | `do_price_trends_preload`, now saving per-day facts (below) | market history host, at its courtesy pace | `inventory/price-trends.json` |

Steps 1 to 3 set the page's "Prices as of". Step 4 is the slow one and runs last. So prices are
fresh long before history is. Each step records its own outcome in `inventory/price-refresh.json`
(`steps.<name>`: `at`, `ok`, counts). A failed step keeps the last good data and says so, as
`pricerefresh.run` does today. Nothing is silent.

**The join is free and re-runnable** (the Commands block). A typed answer lives in
`inventory/prices.json` (D86, one pricing file for the store) and never in `pricing.json`. So a
re-join cannot lose one. The "typed answer survives" and "re-join is idempotent" items in the
list below pin that.

**What this changes in D104.** D104 says the daily job "changes no price". That stays true at
TCGplayer, because nothing here writes there. But the job now rewrites run tables. So what the
screen proposes can move overnight.

D104 now says this, by the owner's word. The daily job also fetches the catalog export per game
and re-joins every open run. Everything else in D104 stands. The guard stands: nothing here
writes at TCGplayer, a failed step is named, and a typed answer never moves.

### The one home for the current Market and Lowest of a SKU

`pipeline/readings.py` (D189, the market reading is a table) is the home. It already answers "the
newest Market this machine has read for a SKU". It reads run tables and the live export, and the
clock decides. It gains the rest of the price row.

- `Reading` adds `low`, `low_with_shipping` and `direct_low`. Each is optional. The row payload
  carries them, so the `readings` table needs no migration. `_parse_reading` defaults a missing
  field to none.
- `reading_from_table` and `reading_from_export` copy all four cells. One reading keeps all four
  from one source and one second. So Market and Lowest never come from different moments.

Two readers draw from it. Neither holds a second copy:

- The T panel reads it through `GET /pipeline/price-facts?sku=`, a local read.
- The row keeps drawing `snap`, which step 3 made fresh. Its age is `snap_at`, a new field on each
  worklist row. It is the fetch time of the export the run was last joined against. That is the
  file's mtime, which is its fetch time by D104's own rule.

**One time per card.** A Live tab "read again" also re-joins the open runs, by the owner's
ruling. So the row and the T panel never show two times for one card. The Live press ends in
the same steps 2 and 3 as a refresh, and it records the same `steps.<name>` notes.

### Bug: the trend lines must draw at first paint

The owner saw no trend lines until pressing the Trends button. The screen is meant to draw the
morning's saved strips with no press. `Pricing` reads `GET /pipeline/trends-saved` once on
mount and draws `savedRead(saved, sku)` when `trends[sku]` is empty. The likely causes, none
yet reproduced:

- **The read is one-shot and silent.** The `getSavedTrends` effect swallows a failure and never
  retries. One failed or slow read (a server restart, a busy slot) leaves `saved` null for the
  whole visit. Every strip stays empty, and only the Trends press fills them.
- **The Live tab skips the saved strips.** `trend={trends[sku] ?? (liveTab ? undefined : ...)}`
  draws nothing from `saved` when `liveTab` is true.
- **The column is hidden.** `.pricing-col-trend` is `display: none` under a 900 wide page, and so
  is the Trends button. Nothing draws, with no hint why.

The fix: the saved read retries on failure, and shows a sentence when it cannot read. The Live
tab draws the saved strips of its own SKUs. A page too narrow for the column says that T
holds the strip. The build reproduces the owner's case first and names the real cause.

### Where the sales facts come from

TCGplayer's history gives these fields for each day: `quantitySold`, `transactionCount`,
`lowSalePrice`, `highSalePrice` and `marketPrice`. `pricehistory.Series` and
`pricehistory.Bucket` already parse all of them. The month range is daily, and the preload
already fetches it for the strip. So the new facts cost no extra request.

- `pricehistory.Series` gains one pure method, `window(days)`. It returns units sold, sales, the
  volume-weighted average sale price, and the low and high, over the newest `days` buckets. It is
  the one home for those figures. The browser computes nothing (`app/src/types.ts` is the only
  wire shape).
- The preload saves, for each SKU, `facts` (the row's figures) and `days` beside `ranges`. `days`
  is 30 tuples of date, units, sales, low, high and market. `through` is the date of the newest
  bucket.
- `GET /pipeline/trends-saved` serves `ranges` and `facts` and leaves out `days`, so first paint
  stays small. `GET /pipeline/price-facts?sku=` serves `days` for one SKU.
- Size: the saved file is 289 KB for 366 SKUs today. The `days` add an estimated 0.4 MB. This is
  unmeasured. The build measures it. If the file passes 1 MB, the days move to their own file.

### The read budget

| read | cost today | cost after |
|---|---|---|
| live listings | 1 request a day | unchanged |
| catalog prices | none in the job | 1 request per game with a waiting card. Today all 902 waiting rows are one game. |
| sales history | 2 ranges per product at the market reader's pace (measured: 0.82 s a request, 876 requests in 361 s) | unchanged. The job already asks the month range. |
| a visit to `#/pricing` | 0 requests at any market host | unchanged |
| a press of T | 0 | 0. It reads two local files. |

**The history step is slow, and that is measured.** The daily log shows about two hours from the
live read to the end of the trends read for 366 SKUs. The measured request time is 361 s. The gap
is unmeasured. It is why the job runs prices first. It is also why Refresh now never repeats a
full history read.

### Refresh now

One button in the page header, beside "Prices as of 5:18 AM". It replaces the Trends press. The
screen already reads saved strips at first paint (D278, one product view, two frames, and the
`getSavedTrends` read in `Pricing`). So the Trends press only ever asked for a newer read. This
button asks for that, and for everything else.

- **Route.** New: `POST /pipeline/prices/refresh` starts the work and answers 202.
  `GET /pipeline/prices/refresh` answers `{state, step, done, total, note}`. The work runs in a
  worker thread, as the match setup does. Steps 2 and 3 can outlast the 120 s that a request slot
  may hold (DEBT11, a parked writer still holds a request slot). `server/capture_server.py`
  dispatches both. `app/src/server.ts` is the only client.
- **Guard (D104).** The press is free. It fetches the owner's listings and the catalog and writes
  nothing at TCGplayer. It reads the stored session secret, so the route follows
  `/pipeline/live-export`'s posture. One run goes at a time: a second press while one runs
  answers `running` and starts nothing. Only a press calls it. No render, route load or timer
  calls it. A second press inside `EXPORT_REUSE_S` of a finished run is refused unless the body
  says `force`. The screen sends `force` only from an explicit "Try again" after a failed run.
- **What it runs.** Steps 1 to 3 always. Step 4 runs only for a SKU whose saved history ends
  before the newest finished day. So a press after the morning job asks the market host for
  nothing. The step works in chunks. Closing the page does not stop it.
- **States.** Resting: "Prices as of 5:18 AM" and a line of counts. In progress: the same line
  stays, the button is busy, one line shows the steps (Listings, Catalog prices, Sales history
  118 of 366), and a thin bar fills. Done: "Prices as of 6:11 PM". Failed: the refusal's own
  sentence, the last good time, and "Try again". A failed step never blanks a figure.
- **Time is a sentence.** "Prices as of" is the catalog step's finish time. Sales history has its
  own "through" date and never claims the page's time.

### The row as it opens

One new column sits between Lowest and the trend: **Range 7d**, by the owner's pick. It is the
lowest and highest price that copies sold at over the last 7 days. It is the safe read for a
price floor. It comes from the month history already read. The trend column, with its yearly
strip, stays where it is.

Every other figure goes in the T panel: Sold/week, Sales/week, Avg 7d, Lowest with shipping,
copies listed and the sold-per-day chart.

Direct Low is not a candidate. Every waiting card's export row carries it blank (measured: none
of 902). Total Quantity is the owner's own listed copies and never market supply. So it stays
where it is (`LiveCount`) and on T.

- **Age of each price.** A cell prints its age only when it is older than the page's "Prices as
  of" by more than an hour. That is the `STALE_AFTER_S` rule that `keptStrip` already applies to
  strips. The age draws as a date, in the warn tone, under the figure. A fresh figure draws no
  age, so a normal morning adds no noise. Range 7d draws its `through` date by the same
  rule.
- **Width.** The new column needs room for about 76 px. Under 900, Lowest, the trend and the new
  column leave, as Lowest and the trend do now. T keeps every figure at every width. Whether the
  1440 desk with the sidebar open keeps the name column wide enough is unmeasured. The build
  measures it before it picks the breakpoint.
- **Empty states.** No saved history: the cell draws "—" with a title that says so. Nothing sold
  in 7 days also draws "—".

### T, and the panel behind it

**`T` is already bound on this screen.** `PRICING_KEYS` in `app/src/App.tsx` lists it as "Open
the product page for this card". `Pricing.tsx` handles it in two places: the window handler and
the price field's `onKey`. Both call `openSheet('product', ...)`. So the key stays and the sheet
gains a block. The `SHORTCUTS` row changes its sentence to "Open this card's prices and sales".
No new key is added. T on any other screen is untouched.

The block sits at the top of `ProductHistoryView` (D278), so the sheet and the routed page both
get it. It reads only `GET /pipeline/price-facts?sku=`, which reads two local files. So it opens
at once and fires no market request. It keeps D278's rule: a press, never follow-focus, and no
request per arrow key.

Content, compact, in four-column grids:

- **Prices now**, with the read time: Market, Lowest, Lowest with shipping, Direct low ("not
  carried" when blank). Each has its age by the row's rule.
- **Sales, last 30 days**, with "Sales through" and a date. A small bar chart of units sold a day
  (30 bars, three tick labels) with Market as a thin line over it. Then these figures: Sold, Per
  sale, Avg sale 30d and 7d, Sale range 30d and 7d, Best day, and Market change over 30 days.
- **On your shelf**: On hand, Can be sent, Listed now (Total Quantity), Your asking price.
- A card with no saved history draws its strip and one sentence, never an empty grid.

The chart follows `docs/DESIGN.md` and the kit. It uses `--bn-*` tokens only, in light and dark.
Bars use reduced opacity and the line uses ink. A text alternative names what it shows.

### The job after this change

`scripts/price-refresh-daily.py` calls `pipeline_routes.do_prices_refresh` (steps 1 to 4) and logs
one line per step. `pricerefresh` gains the step notes. Today's two notes (`run`, `trends`) stay
readable, because `PriceMovers` reads them.

### Checks that can go red

Each is one claim. A build makes each one red first.

1. **The job refreshes the row.** Seed a run table with a stale `snap.market`. Run
   `do_prices_refresh` against a stub portal that serves a new Market. The run's `pricing.json`
   carries the new Market, the new `bucket` and the new `rule_price`.
2. **The send agrees with the screen.** After the first item, `emit` writes the same price that the
   worklist row proposes. Red on any build that repaints the display only.
3. **A typed answer survives.** Type a price, run the refresh, read `prices.json`: byte-equal.
   The row still shows the typed price.
4. **A re-join is idempotent.** Join twice against one export. `pricing.json` is identical.
5. **Order.** Steps run listings, catalog, join, history. A history step that throws leaves steps
   1 to 3 recorded and the header time set.
6. **Failure keeps the last good figures.** A refused catalog fetch changes no run table. It
   records its sentence in `price-refresh.json`.
7. **One request per game.** Three open runs of one game cause one catalog request. The stub
   counts, as `harness/tests/t7/pipeline_fetch.py` counts for the reuse arm.
8. **Nothing is written at TCGplayer.** The refresh path calls no write at the portal. The
   existing test for the daily job reads its calls. Extend it to the new function.
9. **No request on a visit.** First paint of `#/pricing` and a press of T cause zero requests at
   any market host. The stub counts.
10. **One home.** `Reading` carries all four cells from one source and one second. A test feeds a
    run table and a newer live row. It gets one whole row back, never a mix.
11. **The route.** `POST /pipeline/prices/refresh` answers 202, and a second press answers
    `running`. A press inside `EXPORT_REUSE_S` of a finished run is refused without `force`.
12. **Facts are one function.** `Series.window` gives the units, sales, average and range for a
    fixture history. A window with no sales gives an average of none, never zero.
13. **The saved file.** The preload writes `facts`, `days` and `through`. `trends-saved` omits
    `days`. `price-facts?sku=` serves them.
14. **The key.** `SHORTCUTS` lists T with the new sentence. A test proves T opens the sheet from a
    row and from the price field. It also proves T does nothing inside a text field.
15. **The column.** `app/tests/pricing.spec.ts` asserts the one new header at 1440 and its
    absence at 820. It also asserts the age line in the warn tone on a figure older than an hour.
16. **Nothing moves.** `app/tests/stability.spec.ts` stays green. The age line has a reserved
    line, so a refresh moves no row.
17. **The header.** "Prices as of" shows the catalog step's time. Running shows the steps and the
    count. Failed shows the sentence and keeps the last good time.
18. **Both themes.** The header states, the column and the panel are looked at in light and dark
    at 1440 and 820, with a verdict per screen (`make screenshot`, `make design-check`).
19. **Trends draw at first paint.** Seed `price-trends.json`. Open `#/pricing` and press nothing.
    Every seeded SKU shows its strip, on the run tab and on the Live tab. Red today if either
    tab draws none.
20. **A failed saved read recovers.** Fail the first `trends-saved` request. The strips draw after
    the retry, and a second failure shows a sentence.
21. **Live re-joins.** A Live tab "read again" ends with the open runs re-joined. The row's
    `snap_at` and the T panel's read time are equal afterward.

### The dollar columns sort from their header

The owner asked to sort the dollar columns by pressing the header text: highest first, then
lowest first, then the default order.

- **Columns.** Market, Lowest, Range 7d and Price (New price on the Live tab). Range 7d sorts by
  the upper end of the range. It is not offered where the column is hidden, and a URL sort on it
  falls back to the default order there.
- **Price freezes at the sort.** It sorts by the asking price taken when the sort is chosen
  (`askingAtSort`), so a typed price does not re-rank rows (D181, the order is taken once).
- **Order.** A sort orders within each group. Rows that need the owner stay on top (D277). A row
  with no value for the column goes last in both directions.
- **Left-box rows sit lower (7b-29).** A row whose copies have all left the box
  (`on_hand` 0) sorts below the rows with a copy on hand. That applies in the default order, inside each group. The Live tab's `on_hand`
  is `Inventory.copies_on_hand`'s count. A header sort ignores this.
- **One column at a time.** The sort lives in the URL and survives a reload (D285, filter sort and
  search live in the URL).
- **One control.** The header is the kit's `SortHeader` in `app/src/kit/filters.tsx`, extended.
  Pricing has no second header.
- **Header labels.** Item stays left. Every other header label (Market, Lowest, Range 7d, Trend, Qty, Price) is centered over its column. Row values keep their alignment, except Market, Lowest and Range 7d. Those values are centered in their cell (7b-30, 7b-31; decimal alignment given up on purpose). The hover box hugs the label and the chevron sits outside it (7b-28).
- **Centering.** Row values center on the row's own center. Tokens set it, never pixel literals.
- **Proof.** `app/tests/pricing.spec.ts`, cases `7b-21` to `7b-27`: "a row with a hold note
  centers Market, Lowest, Range 7d and Qty on the row's own center", "header cycles highest first,
  lowest first, then the default order", "typing a price while sorted by Price keeps the row
  order", "below the width that hides Range 7d, no Range sort is offered and a URL one falls back"
  and "Pricing.css holds no literal that a design token already names".

### Open questions for the owner

1. **A card with no history** (18 of 366 today) stays "—". No fix is proposed.
2. **The trends read takes about two hours.** The gap against measured request time is
   unmeasured. It is worth its own look, but not in this change.

## 8. Where things are

| | |
|---|---|
| decision | `pipeline/reprice.py`: pure, no I/O, no `store` import, no network |
| command | `cli/cmd_reprice.py`, wired in `cli/__main__.py` |
| routes | `GET` and `POST /pipeline/markdowns`. `POST /pipeline/markdowns/<stamp>/apply` takes a `worklist` upload or `edits`, and an optional `revision`. Also `.../push`, `.../rollback`, `.../publish`, `.../send`, `GET .../file`, and D103's `GET .../table`, `GET .../history?sku=` and `GET .../trends?sku=`. |
| refresh (7b) | `pipeline_routes.do_prices_refresh`, `POST` and `GET /pipeline/prices/refresh`, `GET /pipeline/price-facts?sku=`, `pipeline/readings.py`, `pipeline/pricerefresh.py`, `scripts/price-refresh-daily.py` |
| lens | `app/src/pricingSource.ts`, the source seam and the adapter. The screen is `app/src/Pricing.tsx`, opened at `#/pricing?markdown=<stamp>`. |
| output | `inventory/markdowns/<stamp>/`: `worklist.csv`, `report.txt`, `manifest.json`, `survey.json`, then `import.csv` and `receipt.txt` |
| answers | `inventory/prices.json`, through `pipeline/corpus.py` |
| harness | `check_markdown` and `check_markdown_lens` in `harness/tests/t7/send_markdown.py`, and the markdown arms of `check_history_route` and `check_corpus_revision` |
| screen tests | `app/tests/pricing-markdown.spec.ts`, run by `make design-check` |

## 9. What would reopen this

- **A measured publish lag.** §6 item 6 gets a number, and `PUBLISH_LAG_S` follows it.
- **A reason column in the worklist.** §5 names what it would cost.
- **A second person working the markdown while the first works a run.** That would be a reason
  for a route of its own.
- **A markdown that is not a percentage.** `--rule` already carries `match` and `markup`, and
  `--basis market` prices to the market and not off the asking price. Nothing has asked for a
  per-row rule, and a per-row rule is what `#/pricing` already is.
