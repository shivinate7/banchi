## D-orders-and-shipping-are-two-rows — Orders and Shipping are two sidebar rows with no tabs, and the walk gets the full height

**The ruling, 2026-09-23, from the second round of the UX review.** The orchestrator stated it
to the owner as a call on the round-two findings:

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

### What is still open

- The exact layout: where the buyer list goes when the walk takes the height. The orders lane
  draws it at 1440, 820, 720 and 390, and shows the owner first.
- CLAUDE.md's hub note changes in the docs-sweep lane, not here.

### What is built

NOT BUILT. The orders lane of the round-two plan builds it. That lane's plan names its own entry
for this change (slug `orders-walk-layout`). One of the two entries must go before either
merges.
