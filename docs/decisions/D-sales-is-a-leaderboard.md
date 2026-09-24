## D-sales-is-a-leaderboard — Sales leads with a summary band and the best sellers, and a line with no price gets its price from TCGplayer

**The owner's rulings, 2026-09-23.** The owner called Sales "literally just an excel sheet". A
design pass drew three directions on the demo's own data. The owner picked direction B, the
leaderboard:

1. A slim summary band: the gross figure, the months of the period as bars, and "On the shelf".
2. The top three cards as large photo tiles.
3. A tile for the mix: foil against normal, and gross by rarity.
4. Places 4 to 10 as bar rows, on one scale with the tiles.
5. Then the table.

Three more rulings came with it:

- **A line sold at $0.00 is not left out.** The owner's words: "TCGplayer has all the data of
  what items sold at what prices tho". The fix finds the real sale price in TCGplayer's own data
  and fills it in. Only where no TCGplayer source has a price does the line say so.
- **"On the shelf" loads on arrival,** after one timing on the real store.
- **A tile gets a photo** from a server lookup by SKU for another copy's photograph. A plain
  tile is the fallback.

This amends D214 (a gross-revenue retrospective is its own route) and D217 (Sales becomes a
tool). The record is `docs/reviews/ux-2026-09-23/`, file `RULINGS.md`.

### The premises that no longer hold

**D214 and D217 drew Sales as a table.** D214 drew every product name as it came. D217 made the
table a tool: sort, filter, cross-filter, drill down and deep link. The month strip carries the
reading, and the sparkline is `aria-hidden` by design. At real density that is 562 rows on a
30,598px page (VIS-11). The chart labels only its two ends (VIS-10).

**A missing price read as zero.** `Revenue.tsx` tests a line's unit price for `null` only. An
empty string becomes 0. So a line with no price lands in the table at $0.00 and counts as a
sale. The demo has six such lines. The live count is unmeasured.

**D250 (unsold stock reaches Sales) waited behind a press.** "Value my stock" put the shelf
value after the table. The ruling moves it above the table and loads it on arrival.

### What each decision protected, and what protects it now

- **D214** protects an honest retrospective: gross only, never profit, canceled orders left out.
  The band and the tiles read the same figures from the same lines.
- **D217** protects a tool: search, sort and a deep link. The sort control and the search sit
  above the tiles. A search narrows the tiles and the rows as one list. The deep link stays.
- **D250** protects the stock value on the same screen as the sales. It stays, higher up.
- **A missing price** is never a zero, the rule D159 (the band is copies) already set for
  value. The line shows its real price when TCGplayer has one, and says it has none otherwise.
- **D89 (a sold card's photograph is reclaimed on purpose).** Kept. The tile borrows another
  copy's photograph, by SKU, and never keeps a reclaimed one.

### What is still open

- Which TCGplayer source holds the price of a $0.00 line: the order detail, the shipping export
  or another export. First measure how many live lines have an empty price.
- The cost of loading "On the shelf" on every visit, measured once on the real store.
- Whether one rule can split the catalog prefix off a live name, so rows lead with the card.

### What is built

NOT BUILT. The sales lane builds it. That lane's plan names its own entry for the row shape
(slug `sales-rows-by-sku`). The two can merge into one before either lands.
