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

The operator edits the worklist or does not. `pkmnscan reprice apply` reads it back and writes
**`import.csv`**, the file for TCGplayer's My Pricing.

```
./pkmnscan reprice list  <my-pricing.csv> [--days N] [--percent P] [--write]
./pkmnscan reprice apply <worklist.csv> [--corpus-revision <digest>] [--write]
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
the listing has been live. It is a floor on the real age. It once made most live SKUs
`too_young`, because the window measured when the project got a camera. Every report counts
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
SKUs move with every export, so none is recorded here. Run `pkmnscan reprice list` on a
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

**How the first three were learned is part of the finding.** A session drove the importer as a
dry run. Its request interceptor was built from function names in the portal's bundle, and the
wire names were different. Nothing matched, nothing was blocked, and the upload was real.
**A deny-list over a surface that nobody has seen fails open.** The next session that drives a
path like this blocks every non-GET by default. It allows only what it has observed and
judged. It proves that the guard fires on a harmless write before it points the guard at a
real file. `Import To Staged` is not a live write, and that is what made the mistake
recoverable.

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

## 8. Where things are

| | |
|---|---|
| decision | `pipeline/reprice.py`: pure, no I/O, no `store` import, no network |
| command | `cli/cmd_reprice.py`, wired in `cli/__main__.py` |
| routes | `GET` and `POST /pipeline/markdowns`. `POST /pipeline/markdowns/<stamp>/apply` takes a `worklist` upload or `edits`, and an optional `revision`. Also `.../push`, `.../rollback`, `.../publish`, `.../send`, `GET .../file`, and D103's `GET .../table`, `GET .../history?sku=` and `GET .../trends?sku=`. |
| lens | `app/src/pricingSource.ts`, the source seam and the adapter. The screen is `app/src/Pricing.tsx`, opened at `#/pricing?markdown=<stamp>`. |
| output | `inventory/markdowns/<stamp>/`: `worklist.csv`, `report.txt`, `manifest.json`, `survey.json`, then `import.csv` and `receipt.txt` |
| answers | `inventory/prices.json`, through `pipeline/corpus.py` |
| harness | `check_markdown` and `check_markdown_lens` in `harness/tests/t7_store_and_seams.py`, and the markdown arms of `check_history_route` and `check_corpus_revision` |
| screen tests | `app/tests/pricing-markdown.spec.ts`, run by `make design-check` |

## 9. What would reopen this

- **A measured publish lag.** §6 item 6 gets a number, and `PUBLISH_LAG_S` follows it.
- **A reason column in the worklist.** §5 names what it would cost.
- **A second person working the markdown while the first works a run.** That would be a reason
  for a route of its own.
- **A markdown that is not a percentage.** `--rule` already carries `match` and `markup`, and
  `--basis market` prices to the market and not off the asking price. Nothing has asked for a
  per-row rule, and a per-row rule is what `#/pricing` already is.
