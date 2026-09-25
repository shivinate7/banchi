# `#/product` and the price-history views: deliberation

**Status: reasoning, not a spec.** The owner's ruling lives in decision entry D278,
which cites this file. This file holds the view inventory, the trap bug, and the three options
the owner weighed before picking the hybrid.

## Recommendation (picked: the hybrid)

One product view, drawn in two frames. A sheet opens over the screen the owner is on. The route
`#/product?sku=` stays as the deep link. Every product name opens the sheet. The sheet carries
"Open as page". Pricing's drawer becomes this same view, and its hold-key peek stays. It ships
in two steps: step 1 is the doors plus the trap fix, which closes a hard-rule breach at once.
Step 2 folds the Pricing drawer into the shared view.

The owner wants one answer to "what has this product done, and what have I sold of it", from
any screen. Linking every name to the route alone means leaving the current screen each time.
That drops Pricing's typed quantities and loaded trends, and it drops Inventory's selected
card.
Folding everything into one sheet with no route at all loses D227's case for a pasteable deep
link, a bookmark, or an order-line link. The hybrid keeps both: the sheet is the daily path, and
the route is the address. It also fixes a defect neither pure option names. On the live store,
Pricing's own history press sits off on the default landing, because the drawer reads by run,
not by SKU. The hybrid's shared view reads by SKU, so it works there too.

## The view inventory

Four views draw one product's history over time. Four more show a single figure or a store
total. The owner's own count of "about three" was the market-history panel, the product page,
and the Sales drill-down.

| View | Screen | What it draws | Reached by |
|---|---|---|---|
| `PriceHistoryPanel` in Pricing's drawer | `#/pricing` | The export market, two ranges, vwap, momentum, liquidity — no owner sales | The row's history icon, or a hold peek. Off whenever the rows merge two or more runs, which is the default landing |
| `TrendCell` | `#/pricing` rows | A mini spark per row | "Load trends", under the same merged-run gate |
| `ProductHistory` | `#/product?sku=` (off-nav) | A market series per range, the owner's own fills as marks, sales older than the history in a table | Nothing links to it. The palette drops off-nav routes. The only door is a typed URL |
| Revenue drill-down row | `#/revenue` | The owner's sales of one name in the period | The disclosure chevron on a by-product row |
| Revenue "Today" column | `#/revenue` | One market figure against the last sale price | "Compare to today's market" |
| Revenue "On the shelf" | `#/revenue` | The whole store's holdings value over time, not per product | "Value my stock" |
| `CardHero` market fact | `#/inventory` card | One market figure and the SKU, as plain text | Select a card. No history, by D62's old ruling |
| `ValueBands` rows | `#/pricing?band=` | One market figure per copy | The band lens |

Found along the way: a trap on `#/product?sku=X`, where the first nav press out lands the owner
back on an empty `#/product`. The route's own `hashchange` listener clears the SKU, then its
`replaceState` effect fires after the router has already left. Every option below makes this
page busier, so the fix comes first: ignore a hash that does not start with `#/product`. Also
found: `CLAUDE.md` cited the wrong decision id for this route in three places (D226, the STE
ratchet entry, instead of D227). And the demo carries no recording for either history read, so
neither chart could be seen directly, only reasoned about from code.

## The three options weighed

**A. Link every product name to the route.** Every name on Sales, Pricing and Inventory becomes
a link to `#/product?sku=`, and the route joins the palette. This is a small, front-end-only
change, and it closes the hard rule that a route is not a feature until a screen reaches it. But
every visit leaves the current screen. A route change lands at the top. Going back to Pricing
keeps its URL filters but drops the open rows and the loaded trends. Going back to Inventory
drops the selected card, since only the box sits in the URL. Three views stay three separate
views, and the drawer and the page still disagree on what each one draws.

**B. Fold every view into one price-history sheet.** One sheet component holds the market
series, the fills, and the drawer's own numbers, opened from Sales, Pricing, Inventory, Orders
and Graveyard alike. The route is retired, or kept only as a thin wrapper. This gives one place,
with no screen ever left, and it is feasible: the server already stores what a market series
needs. But retiring the route loses D227's pasteable address, its bookmark and its order-line
link. It is also the biggest build, spanning the front end, the server, and a new browser spec.

**H, the hybrid (chosen).** `ProductHistory`'s own body becomes `ProductHistoryView({sku})`. The
route renders it full page. A new sheet renders the same view over any screen, with "Open as
page" to reach the route. Pricing's drawer renders the same view too. Step 1 ships first, and
stays small. It carries the trap fix, the palette command, a name field on the page, and every
door from option A pointed at the route. Step 2 is the sheet frame itself, the drawer rewired
onto the shared view, and a browser spec.
This keeps everything option B gains, plus D227's address. It costs a medium build across the
front end and the server. The drawer's own word count must still fit Pricing's screen once the
sheet sits open, so that needs a measurement before it is pinned.

## Decisions whose premises had moved

- **D227**, "a route, not a lens": its own sentence claimed the capability was reachable
  through its own control. It was not. Zero inbound links stood on fourteen routes, and the
  palette dropped every off-nav route. What it protected, a per-SKU view that never guesses, is
  now protected by `ProductLink`, the new control every screen carries.
- **D62**, "the price history is reachable, drawn beside the hold": its sentence read a history
  request as too costly to fire on a hover or an arrow key, at 1.3 seconds and a public mirror.
  For any SKU the archive has already swept, the read is now local. What it still protects, no
  request per arrow key, holds unchanged: the hybrid still fires only on a press or a hold,
  never on a hover or a keystroke.
- D103 and D226 do not govern this question at all. D103's lens argument reaches it only
  through a quote inside D227. D226 was simply the wrong id, cited by mistake in `CLAUDE.md`.

## What the owner was asked, and answered

1. Hybrid, link-only, or fold-only? The owner picked the hybrid, step 1 first.
2. May Inventory's card carry a door to the product view, since D62 once said no history there?
   Recommended yes, on the SKU line rather than the market row.
3. When a Sales name covers more than one SKU, does its door open the latest sale's SKU, or ask
   which one? Recommended the latest, with the other SKUs listed in the sheet's own header. How
   many names on the live store carry two or more SKUs stayed unmeasured at the time of this
   deliberation.
