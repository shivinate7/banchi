# Stale listings, and the markdown that pushes them back

**STATUS, 2026-09-04: SPECIFIED and BUILT. NOT VALIDATED.** The two commands, the four routes,
the screen and the harness block all exist and are green, and every number below was measured
from `fixtures/`, from the twelve exports recorded into run directories, from the owner's real
My Pricing download of 2026-09-01, or from the store as it stood on 2026-09-03. **No file this
feature writes has ever been uploaded to TCGplayer.** §6 says exactly which claim that leaves
unmeasured and what press would measure it.

**The screen was re-drawn for Banchi and the backend was not.** This work was written against
the shell D94–D95 replaced and landed here in two halves: the commands, the pipeline module, the
routes and the harness block came across unchanged, and the screen was rebuilt against
`app/src/kit/` as a modal on `#/runs` rather than restyled. Nothing on the wire moved — §8's
routes, §3's predicate and §2's byte contract are the same ones T7 asserts. §5 records what
changed about the placement argument and why the pixel measurement in it is now history.

Governed by D100. The decision entry carries the argument; this file carries the numbers, what
was given up, and what would reopen it.

---

## 1. What it does

The operator downloads their **My Pricing** export from TCGplayer — the same file
`reconcile --live` reads (D87) — and hands it to `pkmnscan reprice list`. That reports which
listings TCGplayer says are live, that nothing has sold from here inside a window, and that
this store has held for longer than the window, and what each would be re-priced to. With
`--write` it produces a **worklist**: the same rows, in export shape, with a price already
proposed on every one.

The operator edits that worklist or does not. `pkmnscan reprice apply` reads it back and
writes **`import.csv`**, which is the file they upload to TCGplayer through My Pricing.

```
./pkmnscan reprice list  <my-pricing.csv> [--days N] [--percent P] [--write]
./pkmnscan reprice apply <worklist.csv> [--write]
```

Both halves preview by default. Nothing in this repo talks to TCGplayer on this path; the
upload is a manual step. Reachable on `#/runs`, from a header button beside the store-wide
reconcile — see §5 for why it opens there and not on a route of its own.

## 2. Nothing is deleted at TCGplayer, and the evidence is in this repo

The owner's question was whether inventory has to be deleted from TCGplayer between the export
and the re-upload. **No.** Three measurements settle it, and the third one is a defect that
already happened.

### `Add to Quantity` is a delta, and TCGplayer's own export says so

**72,701 real export rows carry `Add to Quantity` = `"0"`.** That is the four untouched
fixtures (21,843 rows) and the twelve TCGplayer exports recorded into run directories (50,858
rows), which is the whole of it: 21,843 + 50,858 = 72,701. Not one row anywhere carries anything
else. The My Pricing download of 2026-09-01 is one of those twelve, not a third source — an
earlier draft counted it separately and put 40,858 against the run directories, leaving a total
that was right and a breakdown that did not add up. Recounted 2026-09-04.

The 510 rows on this machine that DO carry a non-zero `Add to Quantity` are all in files this
pipeline wrote — `import*.csv` — which is the column doing its job. No file TCGplayer produced
carries anything but `0`.

**649 of those rows are ones on which TCGplayer simultaneously reported live copies** —
`Total Quantity` between 1 and 10 — and every one of them still carries `Add to Quantity` = 0.
That is decisive on its own: if the column meant *set the quantity to*, re-uploading an
untouched export would delist the seller's entire inventory, and TCGplayer does not ship an
export that destroys the account it was taken from.

`Total Quantity` is not a writable column at all (`pipeline/tcgcsv.py:WRITABLE_COLUMNS`, and
the `tcgplayer-csv` skill). **There is no CSV route to lowering or setting a quantity even for
a caller that wanted one.**

### The price column edits the live listing in place

Of the 288 live SKUs in the 2026-09-02 export that this pipeline had previously pushed,
**282 carry exactly the price the pipeline last wrote into an import CSV.** The remaining six
sit one or two cents below what was written. The `TCG Marketplace Price` cell of an uploaded
row sets the price of the existing listing, matched on `TCGplayer Id`; a second listing is not
created, and the old one does not have to be removed first.

### The doubling is real, it is measured, and it is on the owner's store

Ten live SKUs in that export held **more copies than this pipeline ever pushed**, and nine of
them sit at exactly `2 x pushed - sold`:

| sku | pushed | live | sold before the export | `2 x pushed - sold` |
|---|---|---|---|---|
| 9026926 | 2 | 4 | 0 | 4 |
| 9035581 | 1 | 2 | 0 | 2 |
| 9035566 | 4 | 8 | 0 | 8 |
| 9035628 | 4 | 5 | 3 | 5 |
| 9035648 | 1 | 2 | 0 | 2 |
| 9037787 | 1 | 2 | 0 | 2 |
| 9035556 | 2 | 4 | 0 | 4 |
| 9027225 | 3 | 6 | 0 | 6 |
| 9198149 | 3 | 6 | 0 | 6 |
| 9034719 | 4 | 6 | 0 | 8 (the one that does not fit) |

Eight of the nine came from one file, `runs/2026-08-31-box3-01/import-subthreshold-riftbound.csv`.
**It was uploaded twice, and every quantity on it was added twice.** The listings were updated
rather than duplicated — one listing per SKU, at double the quantity.

**So the dangerous case is not hypothetical and it is not exotic: it is one extra press on a
file that is sitting in this repo.** A markdown push that carried the copy count again would
do that to every row it touched.

### What follows

`Add to Quantity` is `0` on every row of every file this feature writes — the worklist and the
import alike. `pipeline/reprice.py:ADD_TO_QUANTITY` is a module constant, not a parameter, not
a default and not reachable from a flag: **the quantity is not a variable anywhere on this
path.** It is written explicitly rather than left as the export found it, because a column
left alone is a column nobody is asserting, and `tcgcsv.check_only_writable_changed` then runs
over every row on the way out.

## 3. What "not selling" can honestly mean

A SKU is stale when **all three** hold:

1. **Live now.** `Total Quantity > 0` in the My Pricing export. A fact, from TCGplayer, as of
   the moment the file was downloaded.
2. **No sale here inside the window.** No card of that SKU is in the `sold` state with a
   `state_at` inside the window.
3. **Owned longer than the window.** The oldest `captured_at` of any card that ever carried
   the SKU is older than the window.

### Term 3 is a proxy, and it is the weak one

It measures **how long the card has been owned, not how long the listing has been live.**

The store cannot measure the second. `store/master.py:Listing` has no `first_listed_at`.
`live_as_of` — which does exist, and which D87's amendment added — is **absent from all 443
stored listing payloads** on the owner's store, so `Listing.from_record` backfills it from `at`
on every one. And `at` means "last touched by any writer": **346 of those 443 carry a single
identical timestamp**, `2026-09-02T02:30:54.805+00:00`, which is the D87 store-wide
settlement. There is no listing age in this store to read.

The substitution is printed on the report's own header, on the screen in its own paragraph,
and asserted by both the harness block and the browser spec. A proxy nobody is told about is a
lie.

### Term 2 reads the card records and never the event log

Measured on the owner's store: **one of the 193 `sold` events carries no `sku` key**, while all
**186 cards in the `sold` state carry both a SKU and a `state_at`**. A query over the log loses
that copy silently, and a SKU whose only sale is invisible reads as "never sold" — which is the
exact input this command lowers a price on.

### Term 3 counts departed cards too

A floor taken over on-hand copies alone moves *forward* as the oldest copy sells, so a listing
would get younger the longer it sat. `cli/cmd_reprice.py:_card_facts` walks every card that
ever carried the SKU.

### The one axis that is not a proxy

`--above-market P` compares the operator's asking price against `TCG Market Price` **on the same
row of the same file at the same instant**. It needs no history and no inference, and it is the
only term here that says anything about *why* a card is not selling rather than only that it
has not.

**It has to be read against the floor.** On the owner's real export, 290 of 441 live rows are
priced more than 50% above market — but 115 of the 441 are at or under D9's `$0.40` floor,
where a $0.03 card is *correctly* listed at $0.40 and is 1,233% above market as an arithmetic
consequence of the floor rather than as an overpricing.

### What no amount of work here can know

The export carries **no sales window, no sample size, no last-sold date, no view count, no
watcher count and no competing-seller count**, and TCGplayer publishes none of them anywhere —
the `tcgplayer-csv` skill states this and D8 rests on it. `TCG Market Price` is their own
aggregate over recent sales, one number with no window behind it.

**There is no sales-velocity figure in this product and this feature does not invent one.**
Everything above is either a fact from the export, a fact from this store's own card records,
or the one proxy named as a proxy.

## 4. What the windows select, measured

The owner's My Pricing export, 2026-09-01: **757 rows, 441 live, 1,140 live copies.** Every one
of the 441 live rows carries a `TCG Marketplace Price`, at four decimal places; 438 carry a
`TCG Market Price` and 431 a `TCG Low Price`.

Against the store as of that export:

| | SKUs |
|---|---|
| live at TCGplayer | 441 |
| ...this store has ever held | 408 |
| ...this store has **never** held | 33 |
| ...that have ever sold a copy here | 55 |
| ...live, held here, and never sold | 353 |

The 33 include `Card Sleeves`, `Playmats` and a `YuGiOh` row — genuinely other inventory, which
is why `not_this_store` is a refusal and not a default.

What each window selects, anchored at the export:

| `--days` | SKUs | copies |
|---|---|---|
| 1 | 177 | 577 |
| 2 | 154 | 502 |
| 3 | 109 | 394 |
| 7 | 109 | 394 |
| 10 | 0 | 0 |
| 14 | 0 | 0 |

**These figures are perishable and describe a store nine days old.** The oldest capture in it is
`2026-08-23T18:34:42`. A 14-day window firing on nothing is a fact about that store's age, not
about this feature.

At `--days 7 --percent 10`: 109 SKUs, 394 copies, asking value **$193.06 → $173.36**.

## 5. The three files, and why the worklist is not the upload

| file | what it is |
|---|---|
| `worklist.csv` | the stale rows in export shape, price already proposed. What the operator edits. |
| `manifest.json` | what the export said per SKU — **including the row's own bytes**. |
| `import.csv` | what `apply --write` produces. The file that goes to TCGplayer. |

They live in `inventory/markdowns/<stamp>/`, under `inventory/` and never under `runs/`: a run
directory is one box's immutable input and is declared disposable, and a markdown is store-wide
and is state.

**`apply` reads exactly two cells** out of whatever the operator hands back — `TCGplayer Id` and
`TCG Marketplace Price` — and takes every other byte from the manifest. A spreadsheet reformats
cells on open and on save: it strips the leading zero from `Number` (`001/132` → `1/132`),
strips a trailing zero from a price (`0.0100` → `0.01`), and writes `0` into an empty cell.
Measured: a worklist mangled all three of those ways produces an `import.csv` **byte-identical**
to the unmangled one. The edited file is an instruction sheet and never a source of bytes.

The worklist is nevertheless in full 16-column export shape and carries `Add to Quantity` 0, so
**uploading the worklist by mistake is harmless** — it applies the proposed markdown and moves
no quantity. That is the property the shape was chosen for.

**What this gives up:** the worklist carries no "why this row is here" column, because a
seventeenth column would break the round-trip the previous paragraph depends on. The reasoning
is in `report.txt` beside it. If the operator asks for the reasons in the spreadsheet, that
reopens the file's shape.

### It opens on `#/runs`, and the measurement that decided that is history

D49's precedent says a worklist the operator sits in earns a route, and this is one. `#/markdown`
was built and then measured out against the shell of the time: **the horizontal nav strip needed
1,484.9px to draw eleven links on one row against the owner's 1,440.** The aside group wrapped,
the nav doubled from 45.5px to 90px, and `app/tests/review.spec.ts`'s between-cards floor went
red as the web font swapped in and tipped the wrap mid-screen. No label rescued it — an eleventh
link would have had to be 68px and `Runs` was 72.6.

**That strip no longer exists.** D95's shell is a sidebar collapsing to a rail with a command
palette beside it, where a nav item costs a row of vertical space rather than a share of one
horizontal line, so the arithmetic above constrains nothing here any more. Re-measured in a
browser on 2026-09-04, at the owner's 1440x900: nine links, each 36px tall and 211px wide, in
four groups on a 2px gap, running y=68 to y=537 with the sidebar foot ending at y=704 — **196px
of slack, against the 38px a tenth link would cost**, and on a phone a nav route that is not one
of the four tabs goes in the More drawer at no width cost at all. **A row would fit.** The
placement did not
change with it: this opens as a modal on `#/runs` from a header button beside the store-wide
reconcile, a structural sibling of `app/src/LiveReconcile.tsx`, because both read the same live
export and the order is the order of the work. What was a forced choice is a deliberate one.

**What that costs is a hash of its own**: no link, no bookmark, no chord, and it opens over a
screen whose first two thirds are about one run. `app/src/App.tsx`'s ROUTES table carries the
argument where the row would have gone.

### Prices are compared as `Decimal`, never as text

A live export writes four decimal places (`"0.6600"`); this writer emits two (`"0.66"`). Equal
as money, different as bytes. A string comparison would read every untouched row as an edit and
mark down the entire store on a rounding artefact. Asserted in T7.

### Refusals

`reprice list`, per row:

| code | when |
|---|---|
| `sold_out` | `Total Quantity` 0. The export keeps the row; there is no listing. |
| `not_this_store` | live at TCGplayer, no card here ever carried the SKU |
| `held` | withheld in the corpus (D49), and live. Reported, never silently marked down. |
| `sold_recently` | a copy sold here inside the window |
| `too_young` | owned for less than the window, or a stamp that does not parse |
| `priced_recently` | this store answered this SKU's price inside the window — the ratchet |
| `no_asking_price` | live with a blank `TCG Marketplace Price` |
| `no_basis` | the chosen basis column is blank or zero (`pricing.has_market_data`) |
| `near_market` | not far enough above `TCG Market Price` for `--above-market` |
| `at_floor` | already at `$0.40`, or the rule would land there |
| `not_a_markdown` | the rule would raise the price or leave it |

`reprice apply`, per row — except the two marked, which refuse the **whole file**:

| code | when |
|---|---|
| `unchanged` | the same price it is already listed at. Dropped: a no-op row is a press that did nothing and reads like a press that did something. |
| `below_floor` | under `$0.40` |
| `not_in_worklist` | a SKU this worklist was not written for, so there are no bytes to build a row from |
| `raised` | **whole file.** Above the live price. This path only lowers. |
| `duplicate` | **whole file.** Two rows, one SKU. Undefined behaviour in a TCGplayer import (D7). |

A deleted line is not a refusal: **deleting a row is how a person says "not this one"**, and the
report names how many were dropped that way.

### The ratchet

`undercut:10` applied daily compounds to **−52% in a week**, floored only at `$0.40`, with every
individual run justified because the card still has not sold and is still old.

The guard is `corpus.Answer.at`: a SKU this store answered inside `--days` is refused as
`priced_recently` unless `--again`. **It reads the corpus rather than the receipt directories**,
because a directory can be deleted and an answer cannot be without also giving the card its rule
price back — and because a card the operator hand-priced on `#/pricing` yesterday is, correctly,
not stale.

### The answer goes in the corpus

`apply --write` writes each new price into `inventory/prices.json` as a per-SKU `Answer` (D86).
Without that the next `emit` over another copy of the same card re-lists it at the rule price
and quietly undoes the markdown. The marked-down price is the store's price for that SKU from
then on, not a property of one file.

## 6. What is not known, and it is the part that carries money

**No file this feature writes has been uploaded to TCGplayer.** Everything in §2 is measured
from files TCGplayer produced and from files this pipeline produced that TCGplayer then
accepted; none of it is a measurement of *this* file being accepted.

Unmeasured, in order of consequence:

1. **Does the My Pricing importer accept a zero-quantity, price-only row?** The evidence for yes
   is strong: TCGplayer's own export writes that byte on 649 rows it knows are live, and
   `Total Quantity` is a separate unwritable column. That is an argument from their format, not
   a measurement of their importer. The failure modes split cleanly — a no-op is silent and
   safe, and only a reading of `Add to Quantity` as *set the quantity to* could delist, which is
   the reading the 649 rows rule out.
2. **Does it accept a SUBSET of rows** rather than the whole export? `emit`'s files are subsets
   and TCGplayer took them, which is suggestive; that was Import to Staged, and this is the My
   Pricing upload.
3. **Does a price change land immediately, or stage?** Unknown. `reconcile --live` against a
   fresh download is what answers it.

**The first real press should be `reprice list --limit 5 --write`, then `apply --write`,
uploaded, then `reconcile --live` against a fresh download to read the prices back.** Record the
answer in this section, in the session that gets it.

## 7. What is reversible

**Reversible.** Both previews (they write nothing and are re-runnable). The worklist and the
import (files). The corpus answers — clearing an answer restores rule pricing, and `receipt.txt`
holds what each SKU was asking before.

**Not reversible.** Once `import.csv` is uploaded and confirmed at TCGplayer, the prices have
moved. They can be pushed back up with another CSV, but a sale at the lower price is done. The
one thing that *cannot* go wrong this way is the quantity: no file on this path can move one.

## 8. Where things are

| | |
|---|---|
| decision | `pipeline/reprice.py` — pure, no I/O, no `store` import, no network |
| command | `cli/cmd_reprice.py`, wired in `cli/__main__.py` |
| routes | `GET/POST /pipeline/markdowns`, `POST /pipeline/markdowns/<stamp>/apply`, `GET /pipeline/markdowns/<stamp>/file` |
| screen | `app/src/Markdown.tsx` — a sheet on `#/runs`, opened from `app/src/Runs.tsx`'s header beside the store-wide reconcile. No stylesheet of its own: the chrome is in `app/src/Runs.css` beside the composer's, and the primitives are the kit's |
| output | `inventory/markdowns/<stamp>/` — `worklist.csv`, `report.txt`, `manifest.json`, then `import.csv`, `receipt.txt` |
| answers | `inventory/prices.json`, via `pipeline/corpus.py` |
| harness | `check_markdown` in `harness/tests/t7_store_and_seams.py` |
| screen tests | `app/tests/markdown.spec.ts`, run by `make design-check` and never at turn end |

## 9. What would reopen this

- **The first upload.** §6's three questions get answers, and they belong in §6.
- **A listing age this store can actually read.** If `live_as_of` were ever populated on a
  first sighting rather than backfilled — or if a `first_listed_at` were recorded when `emit`
  pushes — term 3 stops being a proxy and the report's header paragraph goes away.
- **A reason column in the worklist.** §5 names what it would cost.
- **An operator who wants to link to it.** The nav arithmetic that refused this a route is gone
  with the strip it measured (§5), so the route is now available for the asking and is not
  taken. A bookmark, a chord, or a second person working the markdown while the first works a
  run would each be a reason to take it.
- **A markdown that is not a percentage.** `--rule` already carries `match` and `markup`, and
  `--basis market` prices to the market rather than off the asking price. Nothing has asked for
  a per-row rule, and a per-row rule is what `#/pricing` already is.
