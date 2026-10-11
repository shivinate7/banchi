# Copy map, wave 2 (base e48fbecd)

Kinds: `casing` (Chicago Title Case, copyRules.ts) or `voice` (second person, no I, my, me or mine).
Line numbers are on e48fbecd. Rows marked `?` need an owner or builder decision; the note says why.
A typed value (price, quantity, hold note, search text) never changes.

## Voice (12 source hits, unit "source scan" test)

| # | kind | file:line | old | new | note |
|---|---|---|---|---|---|
| 1 | voice | Pricing.tsx, line 3753 | `Under my price` | `Under your price` | segmented option (owner example) |
| 2 | voice | Pricing.tsx, line 3754 | `At my price` | `At your price` | segmented option |
| 3 | voice | Pricing.tsx, line 3986 | `Tell me when market is above` | `Notify you when market is above` | hold field label |
| 4 | voice | Orders.tsx, line 4012 | `I already sent it` | `Already sent it` | stand-down legend term (owner example) |
| 5 | voice | Orders.tsx, line 4022 | `I shipped these by hand` | `Shipped these by hand` | stand-down legend term |
| 6 | voice | Orders.tsx, line 4609 | `I already sent {it or these N}` | `Already sent {it or these N}` | button; keep the template |
| 7 | voice | Orders.tsx, line 4669 | `I shipped {this or these N} by hand` | `Shipped {this or these N} by hand` | button; keep the template |
| 8 | voice | Pricing.tsx, line 2835 | `Price my live listings` | `Price your live listings` | button |
| 9 | voice | LiveReconcile.tsx, line 149 | `Fetch my live listings` | `Fetch your live listings` | button |
| 10 | voice | LiveReconcile.tsx, line 158 | title `Drop the My Pricing export here` | `?` `Drop the TCGplayer pricing export here` | `?` `My Pricing` is the name of TCGplayer's own page. The rule forbids the word even as a name. Owner to confirm the wording. |
| 11 | voice | RunPanel.tsx, line 67 | `Only the sets I tick` | `Only the sets you tick` | key label |
| 12 | voice | RunsComposer.tsx, line 929 | `The cards I ticked` | `The cards you ticked` | key label |

## Casing (sweep: 71 offenders across 48 labels, first-line label rule)

| # | kind | file:line | routes | old | new | note |
|---|---|---|---|---|---|---|
| 1 | casing | App.tsx, line 1223, 1224 and 1258| every route (sidebar foot) | `Go to` | `Go To` | the palette title at App.tsx, line 802 is also `Go To` (not in the sweep) |
| 2 | casing | CaptureScreen.tsx, line 5427 | capture | `Connect dispenser` | `Connect Dispenser` | |
| 3 | casing | ReviewQueue.tsx, line 1629 and 3049| review | `Re-check every waiting card` | `Re-Check Every Waiting Card` | line 3049 is the sheet title |
| 4 | casing | ReviewQueue.tsx, line 1633 and 1836| review | `Reload the queue` | `Reload the Queue` | |
| 5 | casing | ReviewQueue.tsx, line 1635 | review | `Past runs` | `Past Runs` | |
| 6 | casing | ReviewQueue.tsx, line 2552 | review | `Show {n} more` | `Show {n} More` | n is the reveal step |
| 7 | casing | Pricing.tsx, line 2496 | pricing | `Clear typed prices` | `Clear Typed Prices` | label; the typed values stay |
| 8 | casing | ClearPrices.tsx, line 163 | pricing | `Clear typed prices` | `Clear Typed Prices` | sheet title |
| 9 | casing | PricesAsOf.tsx, line 135 | pricing | `Refresh now` | `Refresh Now` | |
| 10 | casing | Pricing.tsx, line 1658 | pricing | `Needs you` | `Needs You` | group heading |
| 11 | casing | Pricing.tsx, line 3413 | pricing | `Hold back` | `Hold Back` | button label |
| 12 | casing | Pricing.tsx, line 3414 | pricing | `Hold back {sku.name}` | `Hold Back {sku.name}` | the card name is data |
| 13 | casing | Orders.tsx, line 2363 and 2377| orders | `Add orders` | `Add Orders` | icon label and sheet title |
| 14 | casing | Orders.tsx, line 3921 | orders | `Skip to the walk` | `Skip to the Walk` | |
| 15 | casing | Orders.tsx, line 4338 | orders | `Manage this buyer's orders` | `Manage This Buyer's Orders` | accessible name |
| 16 | casing | Orders.tsx, line 3868 | orders | `Fold {n} section` | `Fold {n} Section` | `?` the noun comes from `countOf`. Decide whether to fix `countOf` or the template. |
| 17 | casing | orderView.ts, line 289 | orders | `Buyer on order` + NBSP + tail | `Buyer on Order` + NBSP + tail | keep the non-breaking space |
| 18 | casing | OrdersWalkPane.tsx, line 976; Orders.tsx, line 5149 | orders | `Mark sold: {place}` | `Mark Sold: {place}` | the place is data |
| 19 | casing | Inventory.tsx, line 1249 | inventory | `Mark sold: {place}` | `Mark Sold: {place}` | |
| 20 | casing | Orders.tsx, line 2804 | orders | `Previous pick` | `Previous Pick` | |
| 21 | casing | Orders.tsx, line 2809 | orders | `Next pick` | `Next Pick` | |
| 22 | casing | OrdersShipStage.tsx, line 492 | shipping | `Forget this file` | `Forget This File` | |
| 23 | casing | OrdersShipStage.tsx, line 55 | shipping | `Needs a look` | `Needs a Look` | chip and button; the value of the `unjudged` key |
| 24 | casing | OrdersShipStage.tsx, line 202 | shipping, revenue, inventory, codes, product | `Export read` | `Export Read` | one shared title; fix it once at its source |
| 25 | casing | Revenue.tsx, line 1185 | revenue | `By month` | `By Month` | sr-only heading; `By week` takes the same rule |
| 26 | casing | Revenue.tsx, line 965 | revenue | `Refresh what's on the shelf` | `Refresh What's on the Shelf` | |
| 27 | casing | Revenue.tsx, line 1373 | revenue | `Compare to today's market` | `Compare to Today's Market` | shown only when prices are not loading |
| 28 | casing | Revenue.tsx, line 87 | revenue | `Last sold` | `Last Sold` | sort label |
| 29 | casing | Revenue.tsx, line 1414 | revenue | `Show the orders behind {name}` and `Hide the orders behind {name}` | `Show the Orders Behind {name}` and `Hide the Orders Behind {name}` | three names in the sweep |
| 30 | casing | BoxBrowse.tsx, line 2196 | inventory | `Collapse the box rail` | `Collapse the Box Rail` | |
| 31 | casing | box name in fixture data | inventory, fulfillment | `SV commons` | unchanged | `?` `SV commons` is a box name the owner typed, so it is data. The rule should not apply to data. Decide: exempt data in the checker, or rename the fixture box. |
| 32 | casing | see note | inventory, orders, fulfillment, product | `Not identified yet` | `Not Identified Yet` | the fallback for a card with no name. Sources: OrdersWalkPane.tsx at lines 928 and 1009; CardHero.tsx at line 573; InventorySets.tsx at line 85; Home.tsx at line 748; DeletedBoxes.tsx at line 179; BoxBrowse.tsx at lines 727, 2528 and 3263; kit/data.tsx at line 346 |
| 33 | casing | Codes.tsx, line 797, 1163 and 1369| codes | `Read a box` | `Read a Box` | button, title and sheet title |
| 34 | casing | Codes.tsx, line 1064 and 1068| codes | `The pile` | `The Pile` | aria-label and heading |
| 35 | casing | Codes.tsx, line 1120 and 1123| codes | `By product` | `By Product` | aria-label and heading |
| 36 | casing | Codes.tsx, line 1172 and 1436| codes | `Hand codes to a buyer` | `Hand Codes to a Buyer` | title and sheet title |
| 37 | casing | Codes.tsx, line 1186, 1216 and 1538| codes | `Build a lot` | `Build a Lot` | title, button and sheet title |
| 38 | casing | Codes.tsx, line 1236 | codes | `Reveal codes` and `Hide codes` | `Reveal Codes` and `Hide Codes` | label template |
| 39 | casing | ProductHistory.tsx, line 680; App.tsx, line 253 | product | `Product history` | `Product History` | page title; the palette label is at App.tsx, line 253 |
| 40 | casing | ProductHistory.tsx, line 694 | product | `Look up` | `Look Up` | submit label |
| 41 | casing | PriceFacts.tsx, line 140 | product | `Prices now` | `Prices Now` | heading |
| 42 | casing | PriceFacts.tsx, line 155 | product | `Sales, last 30 days` | `Sales, Last 30 Days` | heading |
| 43 | casing | PriceFacts.tsx, line 181 | product | `On your shelf` | `On Your Shelf` | heading |
| 44 | casing | ProductHistory.tsx, line 546 and 561| product | `What you got` | `What You Got` | heading |
| 45 | casing | Fulfillment.tsx, line 1046 | fulfillment | `Cards to pull` | `Cards to Pull` | h1; the nav label is at App.tsx, line 245 |
| 46 | casing | Fulfillment.tsx, line 1541 | fulfillment | `Or look through a box` | `Or Look Through a Box` | |
| 47 | casing | Fulfillment.tsx, line 1567 | fulfillment | `Unnamed box` | `Unnamed Box` | the fallback when a box has no name |
| 48 | casing | OrdersShipStage.tsx, line 55 (chip) | shipping | `Needs a look Manual` | see 23 | a composite chip. The label is the first line. |

## Notes for the builder

- The sweep now reads the first non-empty line of a button or heading. A description under a title is a sentence and is not a label.
- `Export read` on four routes comes from one shared component. Fix it once at its source.
- Open decisions: voice row 10 (wording), casing row 16 (noun), casing row 31 (box-name data).
- Not in this table: the bare `Mark sold` button (about 100 test lines assert it) and the Orders icon link `Cards to pull`. Neither draws its label on the landing sweep. Decide before the next sweep.
