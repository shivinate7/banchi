# Sales: three design directions

**Status: reasoning, not a spec.** The owner's own gripe, recorded in `RULINGS.md`'s "Owner
gripes" section, called Sales "literally just an excel sheet", and asked for a visual
redesign. `RULINGS.md`'s "Sales" section carries the final ruling: build Direction B. This file
holds the findings made while comparing the three directions, and why B won.

## The data every direction uses

Every figure below comes from the published demo's own recording. Six months of the demo hold
$41.47 gross, 7 orders, 29 copies and 21 printings. Each sale line already carries a date,
name, SKU, quantity, unit price, card number, rarity and condition on the wire. So
foil-against-normal, rarity mix, average order, best day and days-since are all front-end work,
never a new server read.
"On the shelf" reads from the unsold-stock-value route (D236). The demo's own recording holds
no answer for that route. Its figure here is market price times unsold copies instead, read
straight from the demo's own fixture.

## Findings made while comparing the directions

1. **Today's Sales draws an unpriced line as a $0.00 sale.** Six demo lines carry an empty
   unit price. `Revenue.tsx`'s own sales reader tests only for `null`. An empty string converts
   to zero, so each line lands in the table as a sold $0.00 line. Whether the owner's own store
   carries the same defect is unmeasured. Every direction here shows such a line with no figure
   at all, reading "TCGplayer sent no price", never as $0.00.
2. **A sold card's own photograph is usually gone.** D89 reclaims it on purpose. A thumbnail on
   a sales row needs a fresh lookup, by SKU, for any other held copy's photo. A row with no such
   copy falls back to a plain tile.
3. **"On the shelf" on arrival reverses a convention.** Today the figure waits behind a
   "Value my stock" press. Drawing it on arrival instead means a fetch on every visit, whose
   cost on the owner's own store stays unmeasured.
4. **The card name is not on the wire at live density.** A live name carries its full game and
   set prefix before the card's own name. Leading each row with the name alone needs that
   prefix split off, and whether one client-side rule can do it reliably is unmeasured.

## Direction A: the headline

A hero figure with a comparison line, four stats, and a weekly bar chart over the period with
its peak week labelled. Beside it, "On the shelf" by box. Below both, the ranked table shows
the top eight with "Show all". Each row carries a thumbnail, the name first, and a Foil pill.
Then the card number, rarity and condition sit as quiet text, then copies, gross with a share
bar, and the last sale date. Search and sort stay in the table's own bar. On a phone the table
becomes a list of rows, and the share bars drop below the fold.

Its build cost is front end only, except for two reads: gross by box, and the thumbnail lookup.
It is the smallest change from today's screen. On real data its weekly chart is honest but
sparse until the store holds real history. With two years of history it becomes the strongest
of the three.

## Direction B: the leaderboard (chosen)

A slim summary band carries the gross figure, six month bars (the running month striped as "so
far"), and "On the shelf" at the right. Below it, "Best sellers" shows the top three as large
photo tiles, each with its rank, its share of gross, and its last sale date. A fourth tile shows
foil against normal, and gross by rarity. Places four through ten follow as rows, each bar's
length measured on the same scale as the podium tiles. A sort control and search sit above the
podium, and a search narrows the podium and the rows as one list. On a phone the tiles turn into
photo-left cards, each row keeping its photo, name, gross and copy count.

Its build cost is front end only for every figure, since month sums, rarity, foil and share
all already sit on the wire. It also needs the same thumbnail lookup as Direction A. It reads
as the most visual answer to the owner's own words, and it keeps every job the table did
before.

## Direction C: rhythm and boxes

A calendar strip, one square per day over the period, shaded by gross, with the best day ringed.
Beside it sit the facts the strip supports: days with a sale, the best day, the last sale, and
the shelf value now. Below that, one card per box shows gross sold from it, and sell-through
against what remains. Each card also shows the typical wait from capture to sale, and its own
shelf value. The table gains a Box column and an on-the-shelf-for column.

Its calendar and facts are front end only. Its box cards and both new table columns need a
new server join. That join runs from an order line to the copy that sold, to its box, to its
capture date.
Today's capture-id field on an order line holds a value only where a pull was recorded. That
was 2 of 21 demo lines. Until that join exists, Direction C cannot be truthful.
A second problem compounds it. The box registry's own sold count disagrees with the order
ledger's copy count on the demo, a defect already tracked. So Direction C must not draw both
figures on one screen until that is fixed.

## Recommendation, and why it was chosen

Build Direction B now. It is the direction that stops the screen reading as a spreadsheet.
Every figure it needs already sits on the wire today, except the thumbnail lookup both A and B
share. Direction A's weekly chart can join B once a period holds more than two months of real
sales. Direction C's box cards wait for the server to trace a sale back to its box. Its calendar
strip could join B later, at low cost, once that join exists.

Two items come before any build. First, finding 1: a $0.00 sale reading as sold. Second, the
owner's own answer on finding 3: whether the shelf value fetches on every visit. Both are
answered in `RULINGS.md`'s "Sales" section. The $0.00 lines are fixed by finding the real
TCGplayer price rather than excluding them, and the shelf value loads on arrival.
