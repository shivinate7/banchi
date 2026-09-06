# The seller portal's own API, as read off its bundle

**Status: MAPPED. The whole staged-upload-and-publish chain is measured; the rest is not. Nothing here is built except what
`server/tcg_export.py` and `server/tcg_import.py` already call.**

This file exists because the map is worth more than the one feature that produced it. It was
read on 2026-09-06 out of `https://store.tcgplayer.com/admin/scripts/pricing/main-built.<v>.js`
— **652,827 bytes, served without authentication**, which is why this can be re-read at any
time and why nothing here required guessing.

**Read §4 before calling anything on this page.** Three of these endpoints destroy inventory.

## 1. What is authenticated, and how

A cookie session, and nothing else. Checked specifically for anti-forgery: the bundle has **no
`$.ajaxSetup`, no `beforeSend`, and no `__RequestVerificationToken`** attached to any of these
calls — its single match for that name is inside a vendored library's ignore list. Measured:
three POSTs went through on the session cookie alone.

So `server/tcg_export.py`'s `_cookie()` — the whole `Cookie:` header out of `.env` — is
sufficient for every route below. **That is also the risk**: there is no second factor between
this repo's `.env` and a route that wipes live inventory.

## 2. The endpoints

Every path is under `https://store.tcgplayer.com`. All are form POSTs (`$.post`) unless noted.
`type` is the string `"Pricing"` or `"Buylist"`. **The bundle cannot tell you this** — it only
ever passes `window.config["pricing-settings"].type` through, and compares it via
`type.toUpperCase()` against `"PRICING"`/`"BUYLIST"`. The literal values were read off the live
page's own inline settings, which is the only place they appear:
`pricingTypes: { Buylist: 'Buylist', Pricing: 'Pricing' }`. Every call in the staged-upload
contract carries it — initialize, upload, finalize **and rollback**.

| endpoint | body | what it does | standing |
|---|---|---|---|
| `GET /Admin/Pricing/DownloadMyExportCSV` | query | the live export | **measured** — 759 rows |
| `/admin/pricing/downloadexportcsv` | filter model | the Filtered Export | **measured** (D65) |
| `/admin/pricing/getjsonfilters` | — | the filter vocabulary | **measured** |
| `/admin/pricing/initializeexportcsv` | `{filename, type}` → `{StagedPricingUploadId}` | opens a staged upload | **measured** |
| `/admin/pricing/uploadexportcsv` | `{data[], stagedPricingUploadId, fileName, type}` → `{SuccessfulProductCount, Messages}` | adds a chunk — **their client fires all chunks in parallel** | **measured** |
| `/admin/pricing/finalizeexportcsv` | `{stagedPricingUploadId, productCount, type}` | closes it | **measured** |
| `/admin/pricing/rollbackexportcsv` | `{stagedPricingUploadId, type}` | undoes one staged upload — the per-upload counterpart to `clearstagedinventory` | read, unexercised |
| `/admin/pricing/movetolive` | `{searchModel, scope, connectionId, stagedPricingUploadId, type}` | **publishes staged prices** | **measured** — $23.22 to $750.00 and back, 2026-09-06 |
| `/admin/pricing/productsearch` | search model | the catalog grid's own query | read, unexercised |
| `/admin/pricing/bulkpricematch` | — | their bulk repricer | read, unexercised |
| `/admin/pricing/updateinventory` | — | edits inventory | read, unexercised |
| `/admin/pricing/clearstagedinventory` | `{type}` **only** | **empties ALL of Staged for that channel** | read, unexercised |
| `/admin/pricing/clearliveinventory` | `{clearOption, …}` | **empties LIVE** | read, unexercised |
| `/admin/product/clearliveinventory` | `{productId}` | clears ONE product, live | read, unexercised |
| `GET /Admin/Pricing/StagedInventoryUploads` | — | the upload history | read, unexercised |

**`clearstagedinventory` carries no id and no scope** — one field, `type`, and its own dialog
says *"This will clear all quantities and prices from your Staged inventory."* There is no
narrowing it to one upload; `rollbackexportcsv` is the per-upload undo and this is the whole
channel. Its call site registers a success callback and **no `.fail`**, so their own dialog
spins forever on a non-2xx.

**`clearliveinventory` is parameterised by a six-member `clearOption`** read from
`window.config["pricing-settings"].clearLiveInventoryParams.clearOptions` — `Inventory`,
`InventoryAndPrices`, `ReserveQuantity`, `ReserveQuantityAndPrices`, `BuylistInventory` and one
more. **The wire values, and even whether they are strings or integers, are unknown**: the
bundle only ever passes them through from server-injected config. The `/admin/product/`
sibling is a different operation, not a variant — it clears a single `productId`.

### The staged-price row

`PricingStagedPrice` builds this from each CSV line. Eleven fields, and the byte count of a
real request corroborates the encoding: 46,560 bytes for 100 rows, ~465 each, which is form
encoding and rules out JSON.

```
Id                            row index
ProductConditionId        <-  "TCGplayer Id"        MyPrice        <- "TCG Marketplace Price"
CategoryName              <-  "Product Line"        AddToQuantity  <- "Add to Quantity"
SetName                   <-  "Set Name"            Number         <- "Number"
ProductName               <-  "Product Name"        ProOnlineStoreReserveQuantity
ConditionName             <-  "Condition"           ProOnlineStorePrice
```

Their own validators: `MyPrice` in **0.01 – 200000**, `AddToQuantity` an integer, and
`ProductConditionId`, `CategoryName`, `SetName`, `ProductName`, `ConditionName` all required.
`server/tcg_import.py:_check` runs these before opening a transaction so a bad file is a
refusal rather than a half-written upload.

### `scope`, on `movetolive`

`1` = This Page · `2` = My Search Results · `3` = **this upload**. Their UI sets `scope(3)`
automatically the moment a `stagedPricingUploadId` exists. **Only 3 is reachable from this
repo** — 1 and 2 would publish rows this pipeline never staged and cannot describe.

### `connectionId` is a progress channel, not a credential

It is a SignalR handle (`$.connection.pricingHub`) bound to `onUpdate`/`onStatus`. Their own
`establishConnection` resolves its deferred inside **`.always()`**, so their client proceeds
with the move even when the hub connection has failed. A client without SignalR loses the
percentage, not the operation.

## 3. What this opens up beyond repricing

**The operator raised this, 2026-09-06, and it is the reason this file is a spec and not a
comment.** Recorded as opportunities, none of them designed:

- **A better picture of live / held / sold.** Today the store learns what TCGplayer holds from
  one CSV download (`reconcile --live`, D87), which is why `live` was 0 on 405 of 443 SKUs
  until that landed. `productsearch` is the grid's own query and would answer per-SKU, on
  demand, without a 759-row round trip — and `StagedInventoryUploads` is a history this repo
  has no equivalent of.
- **Wiping and restarting becomes cheap.** `clearstagedinventory`, `clearliveinventory` and
  `rollbackexportcsv` make "put the store back" a call rather than an afternoon. That is
  genuinely useful for rebuilding after a bad import — and it is also the single most
  dangerous capability in this file. See §4.
- **Their own repricer is reachable.** `bulkpricematch` is what the portal's Marketplace
  Pricing Tool presses. Whether it is worth anything next to D100's rule is unknown; it is
  named here so nobody has to find it twice.

## 4. The danger, stated plainly

**`clearliveinventory` deletes the operator's live listings, and nothing between this repo's
`.env` and that call is stronger than a cookie.**

Rules for anything built on this file:

1. **A destructive endpoint gets its own module-level promise set**, the way
   `server/tcg_import.py` is separate from `server/tcg_export.py` precisely because the latter
   promises in writing that it *"cannot cause a charge"*.
2. **No wildcard call site.** Every route this repo calls is a named constant. A helper that
   takes a path as an argument is how `clearliveinventory` gets called by a typo.
3. **A scope that can widen is not a parameter.** `SCOPE_THIS_UPLOAD` is a constant for this
   reason.
4. **Never a deny-list.** A guard that blocks named-dangerous calls fails open on the one
   nobody named — which already happened on 2026-09-06, when a "dry run" interceptor built
   from the bundle's *function* names (`uploadPrices`, `finalizeUpload`) missed the wire
   names (`uploadexportcsv`, `finalizeexportcsv`) and a real 100-row upload went through.
   The upload was survivable only because Staged is not Live.

## 5. What is not known

- **`movetolive` has never been called from here.** Its contract is read, not exercised.
- **The bodies of `clearliveinventory`, `clearstagedinventory`, `updateinventory`,
  `productsearch` and `bulkpricematch` are unread.** They are named in the bundle; their
  parameters were not traced, because tracing a destructive call means being one mistake from
  making it.
- **Whether `Id` (the row index) matters to the server**, or is only their client's key.
- **Whether the version in the bundle path pins a contract.** `main-built.31397.js` carries
  the same `v=313357` the page footer prints as the portal version. A changed contract would
  arrive as a changed filename, which is a cheap thing to watch and nothing watches it.
