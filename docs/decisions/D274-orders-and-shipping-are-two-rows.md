## D274 — Orders and Shipping are two sidebar rows with no tabs, and the walk gets the full height

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
- **A walk row is a pick count** (D212, D279). One row is one card in one
  section: "Pick 1 of 2". It names the buyer when the walk holds more than one.
- **The card pane is the photograph, the pick and every copy** with its place and Mark sold.
  The card's details table stays on `#/inventory`. This amends one sentence above: "The card
  pane is inventory's own, with inventory's words." The words stay inventory's (the kit
  `Location` draws each place). The pane is no longer inventory's whole pane (UX-169). The owner
  looked at three mockups and picked one quiet line under the card: the market reading and the
  live count, a dash when there is none, linking to the product view (2026-09-24).
- **The list uses the kit `FilterBar`**, and its view lives in the URL (D285).
  A sort press re-sorts at once (FLT-01, D263).
- **The stand-down backlog** (D203) names its cutoff, its span and every order TCGplayer still
  calls Ready to ship. The first cutoff it offers closes none of them.
- **A buyer with no name reads `Buyer on order …00012`**, in the UI face (UX-268). D220 said:
  "The name slot now reads `MM-DD-YY_XXXXX`." That form read as an order id. On the owner's
  store, 0 of 834 orders have no buyer name (measured 2026-09-24, read-only). The label is for a
  pasted order.

- **Walk mode** (the owner's ruling, 2026-09-24): "try being super shrunk instead, and look at
  how much space is wasted by stuff i dont need to see when im in the order walk hogging real
  estate", and "literally 50% of the phone view is a wasted upper currently". Choosing a buyer
  enters walk mode, `?walk=1`. It is a navigation (D118), and Back leaves it. Under 1000px of
  column the title and a walk line share one slim row, and the card pane becomes one thin row:
  thumbnail, name, place and a Mark sold icon. The filter bar, the buyer list, the order header
  and the walk's tools hide. At 1000px and wider only the verdict hides. Measured on the seeded
  store: the first walk row moved from 894 px (106% of the 844 px viewport) to 206 px (24%) at
  390x844, and from 815 px (91%) to 154 px (17%) at 720x900. The owner accepted it as built:
  "much better, a little overkill, but much better than before".

- **The two header presses are small square icon buttons** (the owner's plan, 2026-09-24,
  built 2026-09-25):

  ```
  add orders and cards to pull ought to be mini square buttons that'll fit on the same line
  eventually i'd imagine, but that can happen later (as long as you RECORD taht somewhere)
  ```

  "Add orders" and "Cards to pull" are kit `IconButton`s, each with a tooltip and an accessible
  name. They sit on the one-line filter bar, beside the search, in its `beside` slot. The header
  keeps the title, and in walk mode the walk line. "Cards to pull" opens the Fulfiller's page
  in a new tab, as the sidebar's own row does. It uses the `IconButton` anchor form (`href`,
  `target="_blank"`, `rel="noreferrer"`), never `window.open`. `Gallery.tsx` already linked
  the same route this way (2026-09-25).

- **A shared copy carries no visual descriptor.** The owner, 2026-09-25:

  ```
  i had said to get rid of claiming wanted by <order> as a visual descriptor
  ```

  The "wanted by \<order\>" caption on a pick row (`.orders-pick-claim`) and the block-level
  "N wanted elsewhere" caption (`.orders-map-claimed`) are both deleted, with their CSS. This
  amends D97's *"And a copy another open order was offered is a mark rather than a lock"*: the
  mark is gone. The lock half is unchanged — a copy another open order was offered is still
  pressable, still ranked as not free (D212's fungibility, `LineCopy.claimedBy` still feeds
  `free`), and still not enforced. Every Mark sold looks the same, on every row, whether or not
  another order was offered the same copy.

`app/tests/orders.spec.ts` and `app/tests/order-walk.spec.ts` assert each part. They check
the widths 1440, 820, 720 and 390.

### What is still open

- CLAUDE.md's hub note changes in the docs-sweep lane, not here.
