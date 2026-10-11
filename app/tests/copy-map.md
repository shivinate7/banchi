# Copy map, wave 2 (base e48fbecd)

Kinds: `casing` (Chicago Title Case, copyRules.ts) or `voice` (second person, no I, my, me or mine).
Line numbers are on e48fbecd. A row whose note starts `builder:` leaves the wording to the builder.
A typed value (price, quantity, hold note, search text, box name) never changes.
No row is open.

## Voice (12 source hits, unit "source scan" test)

| # | kind | file, line | old | new | note |
|---|---|---|---|---|---|
| 1 | voice | Pricing.tsx, line 3753 | `Under my price` | `Under your price` | segmented option (owner example) |
| 2 | voice | Pricing.tsx, line 3754 | `At my price` | `At your price` | segmented option |
| 3 | voice | Pricing.tsx, line 3986 | `Tell me when market is above` | `Alert when market is above` | hold field label |
| 4 | voice | Orders.tsx, line 4012 | `I already sent it` | `Already sent it` | stand-down legend term (owner example) |
| 5 | voice | Orders.tsx, line 4022 | `I shipped these by hand` | `Shipped these by hand` | stand-down legend term |
| 6 | voice | Orders.tsx, line 4609 | `I already sent {it or these N}` | `Already sent {it or these N}` | button; keep the template |
| 7 | voice | Orders.tsx, line 4669 | `I shipped {this or these N} by hand` | `Shipped {this or these N} by hand` | button; keep the template |
| 8 | voice | Pricing.tsx, line 2835 | `Price my live listings` | `Price your live listings` | button |
| 9 | voice | LiveReconcile.tsx, line 149 | `Fetch my live listings` | `Fetch your live listings` | button |
| 10 | voice | LiveReconcile.tsx, line 158 | title `Drop the My Pricing export here` | `Drop the “My Pricing” export here` | owner ruling: the page name goes in quotes, as the app's other on-screen strings do. The curly-quoted phrase alone is exempt (NAMED_EXEMPT in copySource.ts). The same words unquoted still go red. |
| 11 | voice | RunPanel.tsx, line 67 | `Only the sets I tick` | `Only the sets you tick` | key label |
| 12 | voice | RunsComposer.tsx, line 929 | `The cards I ticked` | `The cards you ticked` | key label |

## Casing (sweep: 74 offenders across 55 distinct labels, first-line label rule)

Without the typed-data exemption in row 31, the same sweep reads 76 offenders across 56 labels.

| # | kind | file, line | routes | old | new | note |
|---|---|---|---|---|---|---|
| 1 | casing | App.tsx, lines 1223, 1224 and 1258 | every route (sidebar foot) | `Go to` | `Go To` | the palette title at App.tsx, line 802 is also `Go To` (not in the sweep) |
| 2 | casing | CaptureScreen.tsx, line 5427 | capture | `Connect dispenser` | `Connect Dispenser` | |
| 3 | casing | ReviewQueue.tsx, lines 1629 and 3049 | review | `Re-check every waiting card` | `Re-Check Every Waiting Card` | line 3049 is the sheet title |
| 4 | casing | ReviewQueue.tsx, lines 1633 and 1836 | review | `Reload the queue` | `Reload the Queue` | |
| 5 | casing | ReviewQueue.tsx, line 1635 | review | `Past runs` | `Past Runs` | |
| 6 | casing | ReviewQueue.tsx, line 2552 | review | `Show {n} more` | `Show {n} More` | n is the reveal step |
| 7 | casing | Pricing.tsx, line 2496 | pricing | `Clear typed prices` | `Clear Typed Prices` | label; the typed values stay |
| 8 | casing | ClearPrices.tsx, line 163 | pricing | `Clear typed prices` | `Clear Typed Prices` | sheet title |
| 9 | casing | PricesAsOf.tsx, line 135 | pricing | `Refresh now` | `Refresh Now` | |
| 10 | casing | Pricing.tsx, line 1658 | pricing | `Needs you` | `Needs You` | group heading |
| 11 | casing | Pricing.tsx, line 3413 | pricing | `Hold back` | `Hold Back` | button label; the tooltip reads the same |
| 12 | casing | Pricing.tsx, line 3414 | pricing | `Hold back {sku.name}` | `Hold Back {sku.name}` | the card name is data |
| 13 | casing | Orders.tsx, lines 2363 and 2377 | orders | `Add orders` | `Add Orders` | icon label and sheet title |
| 14 | casing | Orders.tsx, line 3921 | orders | `Skip to the walk` | `Skip to the Walk` | |
| 15 | casing | Orders.tsx, line 4338 | orders | `Manage this buyer's orders` | `Manage This Buyer's Orders` | accessible name |
| 16 | casing | Orders.tsx, line 3868 | orders | `Fold {n} section` | `Fold {n} Section` | builder: either, the rendered label must read `Fold {n} Section`. The noun comes from `countOf`, so fix either one. The folded form `Open {n} Section` takes the same rule. |
| 17 | casing | orderView.ts, line 289 | orders | `Buyer on order` + NBSP + tail | `Buyer on Order` + NBSP + tail | keep the non-breaking space; the tail is data |
| 18 | casing | OrdersWalkPane.tsx, line 976; Orders.tsx, line 5149 | orders | `Mark sold: {place}` | `Mark Sold: {place}` | the place is data |
| 19 | casing | Inventory.tsx, line 1249 | inventory | `Mark sold: {place}` | `Mark Sold: {place}` | the visible text at line 1239 is the same words; the accessible name wins in the sweep |
| 20 | casing | Orders.tsx, line 2804 | orders | `Previous pick` | `Previous Pick` | |
| 21 | casing | Orders.tsx, line 2809 | orders | `Next pick` | `Next Pick` | |
| 22 | casing | OrdersShipStage.tsx, line 492 | shipping | `Forget this file` | `Forget This File` | |
| 23 | casing | OrdersShipStage.tsx, line 55 | shipping | `Needs a look` | `Needs a Look` | chip and button; the value of the `unjudged` key |
| 24 | casing | OrdersShipStage.tsx, line 202 | codes, inventory, product (sweep) | `Export read` | `Export Read` | one shared title; fix it once at its source. The sweep reads it on these routes. |
| 25 | casing | Revenue.tsx, line 1185 | revenue | `By month` | `By Month` | sr-only heading; `By week` takes the same rule |
| 26 | casing | Revenue.tsx, line 965 | revenue | `Refresh what's on the shelf` | `Refresh What's on the Shelf` | |
| 27 | casing | Revenue.tsx, line 1373 | revenue | `Compare to today's market` | `Compare to Today's Market` | shown only when prices are not loading |
| 28 | casing | Revenue.tsx, line 87 | revenue | `Last sold` | `Last Sold` | sort label |
| 29 | casing | Revenue.tsx, line 1414 | revenue | `Show the orders behind {name}` and `Hide the orders behind {name}` | `Show the Orders Behind {name}` and `Hide the Orders Behind {name}` | three names in the sweep |
| 30 | casing | BoxBrowse.tsx, line 2196 | inventory | `Collapse the box rail` | `Collapse the Box Rail` | |
| 31 | casing | box name in fixture data | inventory, fulfillment | `SV commons` | unchanged (typed data) | exempt. The owner typed the box name, so it is data, and the sweep and the unit tier skip it by exact text (TYPED_DATA in copyRules.ts). The fixture is not renamed. A label with the same words in other casing still goes red. |
| 32 | casing | see note | inventory, orders, fulfillment, product | `Not identified yet` | `Not Identified Yet` | the fallback for a card with no name. Sources: OrdersWalkPane.tsx, lines 928 and 1009; CardHero.tsx, line 573; InventorySets.tsx, line 85; Home.tsx, line 748; DeletedBoxes.tsx, line 179; BoxBrowse.tsx, lines 727, 2528 and 3263; kit/data.tsx, line 346 |
| 33 | casing | Codes.tsx, lines 797, 1163 and 1369 | codes | `Read a box` | `Read a Box` | button, title and sheet title |
| 34 | casing | Codes.tsx, lines 1064 and 1068 | codes | `The pile` | `The Pile` | aria-label and heading |
| 35 | casing | Codes.tsx, lines 1120 and 1123 | codes | `By product` | `By Product` | aria-label and heading |
| 36 | casing | Codes.tsx, lines 1172 and 1436 | codes | `Hand codes to a buyer` | `Hand Codes to a Buyer` | title and sheet title |
| 37 | casing | Codes.tsx, lines 1186, 1216 and 1538 | codes | `Build a lot` | `Build a Lot` | title, button and sheet title |
| 38 | casing | Codes.tsx, line 1236 | codes | `Reveal codes` and `Hide codes` | `Reveal Codes` and `Hide Codes` | label template |
| 39 | casing | ProductHistory.tsx, line 680; App.tsx, line 253 | product | `Product history` | `Product History` | page title; the palette label is at App.tsx, line 253 |
| 40 | casing | ProductHistory.tsx, line 694 | product | `Look up` | `Look Up` | submit label |
| 41 | casing | PriceFacts.tsx, line 140 | product | `Prices now` | `Prices Now` | heading |
| 42 | casing | PriceFacts.tsx, line 155 | product | `Sales, last 30 days` | `Sales, Last 30 Days` | heading |
| 43 | casing | PriceFacts.tsx, line 181 | product | `On your shelf` | `On Your Shelf` | heading |
| 44 | casing | ProductHistory.tsx, lines 546 and 561 | product | `What you got` | `What You Got` | heading |
| 45 | casing | Fulfillment.tsx, line 1046 | fulfillment | `Cards to pull` | `Cards to Pull` | h1; the nav label is at App.tsx, line 245 |
| 46 | casing | Fulfillment.tsx, line 1541 | fulfillment | `Or look through a box` | `Or Look Through a Box` | |
| 47 | casing | Fulfillment.tsx, line 1567 | fulfillment | `Unnamed box` | `Unnamed Box` | the fallback when a box has no name |
| 48 | casing | OrdersShipStage.tsx, line 55 (chip) | shipping | `Needs a look Manual` | see 23 | a composite chip. The label is the first line. |
| 49 | casing | ReviewQueue.tsx, line 2873 | review | `Close the queue` | `Close the Queue` | icon button tooltip, read by the tooltip pass of the sweep |
| 50 | casing | kit/data.tsx, line 1179 (default); Orders.tsx, line 887; Pricing.tsx, lines 544 to 547 | revenue, pricing, orders | `High to low` | `High to Low` | sort direction tooltip. Its pair `Low to high` takes the same rule (`Low to High`), which the sweep does not reach on these routes. |
| 51 | casing | Codes.tsx, lines 944 and 1329 | codes | `Open the photograph at {box}, slot {n}` | `Open the Photograph at {box}, Slot {n}` | icon link name. The box name is data. |
| 52 | casing | CardLocations.tsx, lines 344 and 914; Orders.tsx, line 5148 | inventory, orders | `Mark sold` | `Mark Sold` | sell button tooltip. Same word as rows 18 and 19, but the tooltip is a separate read. About 110 test lines assert the button by name (see the notes). |
| 53 | casing | Orders.tsx, lines 2366 and 2367 | orders | `Cards to pull, in a new tab` | `Cards to Pull, in a New Tab` | icon link accessible name (href to #/fulfillment). Test: orders.spec.ts, the landing loop. |
| 54 | casing | Orders.tsx, line 2366 | orders | `Cards to pull` | `Cards to Pull` | icon link tooltip. Same element as row 53. |
| 55 | casing | Gallery.tsx, line 978 | gallery (specimen, not in the sweep) | `Mark sold` | `Mark Sold` | specimen label. gallery.spec.ts, line 1245 asserts it, so the label changes with the test. |
| 56 | casing | Gallery.tsx, line 1016 | gallery (specimen, not in the sweep) | `Cards to pull` | `Cards to Pull` | specimen label and tooltip. icon-button.spec.ts asserts it. |

## Notes for the builder

- The sweep reads the first non-empty line of a button or heading. A description under a title is a sentence and is not a label.
- The sweep now also reads the icon links (`a[aria-label]`) and the icon tooltips (`.bn-icon-tip`). That closed the gap that hid rows 49 to 54.
- `Export read` on several routes comes from one shared component. Fix it once at its source.
- Row 10 is the only change to a voice string that keeps a first-person word. It stays red until the builder quotes the page name.
- Rows 55 and 56 are gallery specimens. The gallery is not in the sweep, but two tests assert those labels.
- Tests re-pointed to the new casing: `Mark sold` locators (about 110 lines in inventory.spec.ts, orders.spec.ts, order-walk.spec.ts, demo-coverage.spec.ts, stability.spec.ts, request-budget.spec.ts and empty-section.spec.ts) now use `/^Mark Sold/`. `Cards to pull` locators (icon-button.spec.ts and the orders.spec.ts landing loop) use `Cards to Pull`.
- Left as they are on purpose: orders.spec.ts line 4845 and deleted-boxes.spec.ts line 114 are negative checks (count 0). A case-sensitive rename would make them pass on the base for the wrong reason.

## Not in this sweep

- A11: a placeholder that ends with an ellipsis. 31 offenders. Stays out (over the 30 stop rule).
- A4: an image width and height. 44 offenders. Stays out (over the 30 stop rule).
