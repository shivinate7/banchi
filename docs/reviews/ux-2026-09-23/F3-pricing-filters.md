# F3: Pricing filters (design pass)

The owner's word, 2026-09-29: give `#/pricing` the filters an end user needs. The blind review
asked for a name search, a price sort, a set and game filter, and price bands. Source: F3 in
`PLAN-PR4-PR5.md`. Governing entries: D49 (a missing price is unknown, not low), D277 (the rows
that need the owner sit on top), D271 (one forgiving matcher, `kit/match.ts`).

## Which filters

- **Search.** One field, "Name, set, number or SKU". It calls `matchQuery` from the kit. No
  second matcher. It reads the name, set, game, condition, collector number and SKU.
- **Sort.** Suggested (the resting order), Market price, Name. Suggested is the arrival order
  the screen already had.
- **Facets.** Game (drawn only when the list holds two or more games), Set, and Market price
  band: No market price, under $1, $1 to $5, $5 to $20, $20 and up. A band with no rows is not
  offered. Each option shows its count under the other picks and the search.
- **Held**, the button that already existed (UX-212), stays where it was.

## Where they sit

The kit's `FilterBar`, over the list and under the notices: the search, one Filters trigger
(facets and sort inside it), and the count line with Clear. Same shape as Orders. The toolbar
above keeps its own controls (tabs, runs, lens, kind, Held, Trends). It is drawn on both tabs.

## Default state

Nothing picked, Suggested sort, empty search. The URL carries the state (`?q=`, `?sort=`,
`?dir=`, `?game=`, `?set=`, `?band=`), so a link lands on the same view. Nothing goes in
`deviceMemory.ts`: none of it is a fact about the device, and the storage-key roster is
unchanged.

## How they combine

- Filters AND together: search, every facet, and Held.
- **A sort orders within each heading and never across them.** "Needs you" stays on top and the
  closed headings stay at the foot (D277). A row with no market price goes last in either
  direction (D49).
- **The filters change the view only.** The Send bar, its counts, the presets and every bulk
  press read every row, as the Held press already did. While a filter is on, one line under
  the bar says so.
- Nothing matching is an empty state with a sentence, and Clear is in the count line.

## The held count (defect in the same entry)

The screen said "10 held" in the bar and "Held 15" on the button. The button counted every row
with a hold. The bar counted a hold only when the row was not at the cap, because the cap branch
came first and skipped it (`progress.held` in `Pricing.tsx`). The fix: a hold is a fact about
the row, sent or not, so the bar counts it before the cap branch. Both now read the same rows.

## Wire

No change. Sorting and filtering run client-side over the rows already loaded. Not measured
for size: the list is the store's unsent SKUs and the screen already maps every one.
