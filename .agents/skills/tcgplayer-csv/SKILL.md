---
name: tcgplayer-csv
description: Schema, byte format, and join rules for TCGplayer Filtered CSV exports and Import to Staged files. Use whenever reading, writing, joining against, or validating a TCGplayer export, or when building the catalog join, the fixture round-trip test, or the CSV import path.
---

# TCGplayer Filtered CSV

Confirmed against a real SV09 export, 341 rows, 2026-07-26. Ground truth lives at
`fixtures/sv09_export_untouched.csv`. Never modify it.

## Headers

```
TCGplayer Id, Product Line, Set Name, Product Name, Title, Number, Rarity, Condition,
TCG Market Price, TCG Direct Low, TCG Low Price With Shipping, TCG Low Price,
Total Quantity, Add to Quantity, TCG Marketplace Price, Photo URL
```

The account is single-channel — there are no "My Store" columns. Do not write code that
tolerates them appearing; if they ever do, the account changed and that is a spec event.

## Byte format

- Header row: **unquoted**
- Data fields: **fully quoted**, every field, including empties (`""`)
- Line endings: **CRLF**
- `fixtures/staged-import-accepted.csv` is a 2-row file TCGplayer's Import to Staged
  accepted verbatim. It is the byte-format oracle. Diff against it.

Use a real CSV library — PapaParse in JS, the `csv` module in Python. Never `split(",")`:
product names contain commas, apostrophes, and ampersands (`Billy & O'Nare`).

## Writable columns

Exactly two: `Add to Quantity` and `TCG Marketplace Price`. Everything else round-trips
byte-identical. `TCGplayer Id` is the SKU and is never modified — it is what the import
matches on.

## The price columns are current-state only

Four of them — `TCG Market Price`, `TCG Direct Low`, `TCG Low Price With Shipping`,
`TCG Low Price` — plus `Total Quantity`, the count of live listings. **Not one carries a
timestamp, a sale record or a sample size.** The file is what the marketplace looks like at
the moment the button was pressed, and nothing in it is a window onto anything.

`TCG Market Price` is the only column with sales behind it, and it is TCGplayer's own
aggregate over recent sales rather than a sale — one number, no window. **There are no
last-sold rows in this export, and TCGplayer publishes none anywhere**, so this is not a
gap to be filled from another one of their files. `docs/DECISIONS.md`'s Someday list
carries what is available instead.

## Variant lives in the Condition string

One SKU row per variant:

```
Near Mint
Near Mint Holofoil
Near Mint Reverse Holofoil
```

Most SV-era rares are holofoil-only, so a single condition row for a number is itself
evidence — that is rung 2 of the variant ladder.

## Join key

```
key = zfill(3)(number) + "/" + printedTotal
```

Built from pokemontcg.io data, matched against the `Number` column.

- Secret rares exceed the denominator in the same format: `161/159`. Do not treat this as
  invalid.
- **Never join on `Product Name`.** It inconsistently embeds the number — `Accelgor` in one
  row, `Black Belt's Training - 143/159` in another. Name matching is a fallback for rare
  blank-`Number` rows only.

## Duplicates

Never emit two rows with the same `TCGplayer Id` in one import file — behavior is
undefined. Aggregate by SKU, set `Add to Quantity` to the copy count, cap live quantity at
4, hold the remainder as backstock. See `docs/DECISIONS.md` D7.

## Round trip

After a real import, use the **Export From Staged** button and diff it against what the
pipeline intended to write. This is the only machine-checkable verification against the
live system.
