## D-orders-and-shipping-are-two-rows — Orders and Shipping are two sidebar rows with no tabs, and the walk gets the full height

**The owner's ruling, 2026-09-23, in the final interview on the round-two findings:**

- Keep the walk model of D220 (Orders is inventory's screen with orders in the rail).
- The walk gets the screen's full height.
- Orders and Shipping become two sidebar rows. The tab strip between them goes.

This amends the layout half of D220. It also amends one note in CLAUDE.md: "`#/orders` and
`#/shipping` are two stages of one screen and two routes." The record of the review is
`docs/reviews/ux-2026-09-23/`, file `held-orders-review.md`.

### The premise that no longer holds

D220 gave Orders inventory's skeleton. The orders sit in the left column. The order's panel
sits where the box panel was, and the walk sits where the section list was. That skeleton fits a box, whose
walk is the whole screen's subject. On Orders, the rail holds three things stacked: the buyer
list, the buyer's panel and the walk. So each one gets a small window.

The hub put Orders and Shipping as two tabs of one screen, joined on order number. Both are
also sidebar rows. So the owner reaches two pages by two kinds of navigation.

### The evidence

The held-screen pass measured main at PR #456, on a seeded store.

- **HOR-03.** The walk is a list 96px tall in the 300px left column. Two rows show. At
  1440x900 no walk row is above the fold. The right column shows one card's detail table.
- **HOR-14.** The buyer list is a window 216px tall at every desktop height. Three and a half
  buyers show.
- **HOR-33.** The page, the buyer list and the walk each scroll. A wheel over the rail moves a
  different thing for each pixel.
- **HOR-06.** At 720 and 390, the buyer list and the walk hide behind a dropdown of buyer names.
- **HOR-19.** Orders and Shipping are both sidebar rows and both tabs. On the Shipping tab the
  title changes and a button goes. The strip is a second navigation.

### What D220 protected, and what protects it now

D220 protects three outcomes. A click on an order starts its walk at once. A tick widens the
walk to more orders. The card pane is inventory's own, with inventory's words. All three stay.
Only the space changes: the walk is the tallest thing on the screen, not the smallest.

The hub protected one sale drawn as two stages, joined on order number. Two sidebar rows keep
both routes and both screens. The join between them stays in code. A row on one screen that
names an order still opens it on the other.

### What is built

BUILT by the orders lane, 2026-09-24. This entry is the one record: no `orders-walk-layout`
entry is written.

D220 said: "Fetch, paste, the status picker and the stand-downs sit behind the panel's
`Manage`." That sentence is amended. They act on the whole store, so they open from the page's
own "Add orders" sheet. The panel's `Manage` keeps only that buyer's own orders.

- **Two rows, no tabs.** `#/orders` and `#/shipping` each draw the kit `Page`. They still share
  the hub's state (`OrdersHub`, `OrdersHubStore.ts`).
- **The walk gets the height.** One scroll, the page's. The shape follows the column, a
  container named `orders` (docs/DESIGN.md registers 560 and 1000). At 1000 and up: buyers,
  the walk, and a sticky card pane. From 560: buyers beside the card over the walk. This holds
  720 beside the desktop rail and 820. Under 560: one line that says who, how many and what is
  next opens the buyer list as a sheet. Then the card, then the walk.
- **A walk row is a pick count** (D212, D-pull-list-is-a-pick-count). One row is one card in one
  section: "Pick 1 of 2". It names the buyer when the walk holds more than one.
- **The card pane is the photograph, the pick and every copy** with its place and Mark sold.
  The card's details table stays on `#/inventory`. This amends one sentence above: "The card
  pane is inventory's own, with inventory's words." The words stay inventory's (the kit
  `Location` draws each place). The pane is no longer inventory's whole pane (UX-169).
- **The list uses the kit `FilterBar`**, and its view lives in the URL (D-view-state-in-url).
  A sort press re-sorts at once (FLT-01, D-a-press-reorders-and-nothing-else-moves).
- **The stand-down backlog** (D203) names its cutoff, its span and every order TCGplayer still
  calls Ready to ship. The first cutoff it offers closes none of them.

`app/tests/orders.spec.ts` and `app/tests/order-walk.spec.ts` assert each part. They check
the widths 1440, 820, 720 and 390.

### What is still open

- D220 also says the unnamed label reads `MM-DD-YY_XXXXX`, in the mono face, on the owner's
  ruling of 2026-09-19. UX-268 finds that it reads as an order id. It is unchanged until the
  owner rules.
- The Details table (the market reading and the listing counts) left the Orders card pane, per
  the held-orders cut list. The owner once asked for that parity on this screen. Confirm.
- CLAUDE.md's hub note changes in the docs-sweep lane, not here.
