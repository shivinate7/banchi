# Stale-listing markdown

**STATUS, 2026-09-03: BUILT and SPECIFIED. NOT VALIDATED.** The command, the route, the panel
and the harness block all exist and are green. **No real listing has been through this path,
and the one assumption that carries money has never been measured** — see §5. Read that
section before treating a green `make check` as evidence about TCGplayer.

Governed by D94. The decision entry carries the argument; this file carries the numbers and
the things that are not yet known.

---

## 1. What it does

The operator downloads their **My Pricing** export from TCGplayer — the same file
`reconcile --live` reads — and hands it to `pkmnscan markdown`. The command reports which
listings are live, old, and not selling, and what each would be re-priced to. With `--write`
it produces an import CSV that lowers those prices and **adds no copies**, plus a receipt, and
records the new price per SKU in `inventory/prices.json`.

The upload back to TCGplayer is a manual step the operator performs. Nothing here talks to
TCGplayer.

```
./pkmnscan markdown <my-pricing.csv> --days N --percent P [--write]
```

Reachable at `#/runs`, in the panel beside the store-wide reconcile.

## 2. The staleness predicate

A SKU is stale when **all three** hold:

1. `Total Quantity > 0` in the export — TCGplayer says it is live now.
2. No copy sold within `--days`.
3. The oldest card ever to carry the SKU was photographed here more than `--days` ago.

**Measured on the owner's store, 2026-09-03** (443 listings; 378 with `live > 0`, 996 copies):

| oldest copy captured | never sold | sold at some point |
|---|---|---|
| 2026-08-23 | 108 SKUs / 390 copies | 1 |
| 2026-08-29 | 45 / 108 | 4 |
| 2026-08-31 | 22 / 73 | 12 |
| 2026-09-01 | 177 / 374 | 9 |

**352 of 378 live SKUs — 93%, and 945 of 996 live copies — have never sold a copy.** That is
why term 3 exists: without it the sweep fires on nearly the whole store, half of which was
captured two days before this was built.

What the window selects, on that same store:

| `--days` | SKUs | copies |
|---|---|---|
| 3 | 177 | 577 |
| 5 | 154 | 502 |
| 7 | 109 | 394 |
| 14 | 0 | 0 |

**These figures are perishable.** They describe a store 12 days old. A 14-day window firing on
nothing is a fact about that store's age, not about the feature.

### What term 3 actually measures

`Card.captured_at` — **how long the card has been owned**, not how long it has been listed.
The store cannot answer the second question: `Listing` has no `first_listed_at`, and
`live_as_of` is absent from all 443 stored payloads, so `Listing.from_record` backfills it
from `at` and every value it would report is a legacy fallback rather than a reading.

The proxy is printed in the report's own header, where the operator reads it.

Two implementation traps, both measured:

- **Over every card that ever carried the SKU, including departed ones.** A floor over on-hand
  copies moves forward as the oldest copy sells, so a listing gets younger the longer it sits.
- **Read the `cards` table, not the `events` log.** One of the 193 `sold` events on the
  owner's store carries no `sku` key, so a `NOT IN (SELECT ...)` over the log returns nothing.
  The accepted difference between the two sources is one SKU out of 87.

## 3. The arithmetic

`pricing.Rule` and `pricing.list_price` unchanged: `clamp_floor(round_money(rule(basis)))`, in
that order, floor `$0.40`.

| flag | what it is |
|---|---|
| `--percent P` | `undercut:P` off the operator's own asking price. The screen's whole vocabulary. |
| `--rule` | the power form — `match`, `undercut:PCT`, `markup:PCT`. CLI only. |
| `--basis` | `listed` (default), `market`, `low`. CLI only. |
| `--above-market P` | only listings priced more than P% above `TCG Market Price`. |
| `--limit N` | the N rows worth the most. Everything below the cut is named. |
| `--again` | override the ratchet guard. |

`reprice.BASES` is **local**. Adding `listed` to `pricing.BASES` would offer it on `join` and
`emit` via `cli/__main__.py`'s `choices=`, where a blank basis cell leaves
`TCG Marketplace Price` untouched — blank on 7,787 of 7,802 rows in the wide Pokemon export —
with nothing raising. D94 traces it.

### Refusals

| code | when |
|---|---|
| `not_a_markdown` | the new price is at or above the old. Never raises a live price. |
| `add_to_quantity_not_zero` | an input row carries a quantity. Refuses the whole file. |
| `marked_down_recently` | the corpus says this SKU was marked down inside the window. |
| `sold_out` | a price with `Total Quantity` 0. |
| `held` | withheld in the corpus, and live. Reported, never silently skipped. |
| `not_this_store` | live at TCGplayer, no card here carries the SKU. |
| `too_young` | held for less than the window. |

**Prices are compared as `Decimal`.** A live export writes four decimals (`"0.6600"`), this
writer emits two (`"0.66"`); they are equal as numbers and different as bytes. A string
comparison marks down the entire store on a rounding artefact. Asserted in T7.

## 4. The zero-quantity invariant

Every written row carries `Add to Quantity` = `0`.

**Measured**: `"0"` on all **21,502 rows** across `sv09_export_untouched.csv`,
`pokemon_wide_export_untouched.csv`, `riftbound_export_untouched.csv` and
`onepiece_export_untouched.csv`. It is TCGplayer's own byte.

Because the operation adds nothing, it **cannot breach the live cap** and **cannot delist**.
Asserted in both directions — an input row not already at zero refuses the file, and each
output row is re-checked against its export original.

The written file's byte signature is asserted equal to
`fixtures/staged-import-accepted.csv`'s: header unquoted, every data field quoted, CRLF, no
BOM.

## 5. What is not known, and it is the part that carries money

**The byte oracle is for a different importer.** `fixtures/staged-import-accepted.csv` is what
**Import to Staged** accepted, with `Add to Quantity` = `"1"`. This file goes back through the
**My Pricing** upload, whose endpoints — `initializeexportcsv`, `uploadexportcsv`,
`finalizeexportcsv`, `rollbackexportcsv` — appear nowhere in this repo and have never been
called from it.

**Unmeasured, in order of consequence:**

1. **Does the My Pricing importer accept a zero-quantity price-only row?** The evidence for yes
   is that TCGplayer's own export writes that byte on every row, and that `Total Quantity` is a
   separate, unwritable column. That is an argument, not a measurement. The failure modes split
   cleanly: a no-op is silent and safe; only a reading of `Add to Quantity` as *set the
   quantity to* would delist.
2. **Does it accept a SUBSET of rows** rather than the whole export? `emit`'s files are subsets
   and Import to Staged took them, which is suggestive and not the same importer.
3. **Does a price change land immediately, or stage?** Unknown. `reconcile --live` against a
   fresh download is what answers it.

**The first real press should be `--limit 5 --write`**, uploaded, then `reconcile --live`
against a fresh download to read the prices back. **Record the answer here, in the session
that gets it.**

## 6. What is reversible

**Reversible:** the preview (writes nothing, re-runnable). The CSV (a file). The corpus write —
`Answer.was` holds what the card was asking before this pipeline started moving it, the receipt
holds the whole report, and clearing an answer restores rule pricing.

**Not reversible:** once the CSV is uploaded and confirmed at TCGplayer, the live prices have
moved. They can be pushed back up with another CSV, but a sale that happened at the lower price
is done.

## 7. The ratchet

`undercut:10` applied daily compounds to **−52% in a week**, floored only at `$0.40`, with
every individual run justified because the card still has not sold and is still old.

The guard is `Answer.marked_down`: a SKU marked down inside `--days` is refused unless
`--again`. **It reads the corpus and not the receipt directories**, because a directory can be
deleted and an answer cannot be without also giving the card its rule price back.

## 8. Where things are

| | |
|---|---|
| decision | `pipeline/reprice.py` — pure, no I/O, no `store` import |
| command | `cli/cmd_markdown.py` |
| route | `POST /pipeline/markdown`, `GET /pipeline/markdowns/<stamp>/file` |
| screen | `app/src/StaleListings.tsx`, on `#/runs` |
| output | `inventory/markdowns/<stamp>/` — `markdown.csv`, `markdown.txt`, `manifest.json` |
| answers | `inventory/prices.json`, via `pipeline/corpus.py` |
| harness | `check_markdown` in `harness/tests/t7_store_and_seams.py` |
| screen tests | `app/tests/stale-listings.spec.ts` |

`inventory/markdowns/` is under `inventory/` and **not** under `runs/`: a run directory is
declared disposable, and a markdown receipt is state.
