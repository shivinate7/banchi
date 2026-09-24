## D-a-press-reorders-and-nothing-else-moves — A sort press re-sorts at once, a sold row folds on the next load, and box lists lead with the most recent

**The owner's rulings, 2026-09-23, in the UX review interview.** Three rulings about when a list
may change its order.

1. **A sort press re-sorts at once** (FLT-01). This amends D209 (the buyer list leads with Ready
   to Ship, and a re-sort is a press). The freeze still stops a sale from re-ranking the list.
2. **Nothing jumps** (FLT-22). A sold row stays in place, marked sold, until the next box load
   or refresh. Then it folds. D118 (a press changes what is on the screen, never where the rest
   of it is) wins over the timing in D132 (sold is folded away by default).
3. **Box lists lead with the most recent box, everywhere.** That covers the Inventory rail, the
   Capture picker, Home and Cards to pull. This extends D132's rail order and D142 (the box
   list is ordered by the hand) to the two screens that order by number today.

The record of the review is `docs/reviews/ux-2026-09-23/`, lens `filtering.md`.

### The premises that no longer hold

**D209.** D209 rules that a changed sort only offers a "re-sort" chip, and that only the chip's
press re-orders. It extends D181 (the order is taken once). But the sort toggle is itself an
explicit press. D209's own title says a re-sort is a press. The lens measured the result on
`#/orders`: "Oldest" shows pressed and the list does not move. A chip then says "Order is 6
buyers stale, re-sort". So the toggle states an order the list does not have.

**D132.** D132 folds a sold row "the moment the walk steps off it". The lens measured that
moment on `#/inventory`. The owner marks card 1 sold and presses card 2. At that click the sold
row folds, and every row below moves up 32px under the pointer. The row just pressed slides
away. D132 and D118 conflict here, and the owner picked D118.

**Box order.** Home and Cards to pull order boxes by number. Inventory and Capture order them
by the hand. So one store shows two orders (COH-11, UX-079).

### What each decision protected, and what protects it now

**D209 and D181** protect a list that does not reshuffle under the hand because of something
the owner did not do. That stays. A sale, an arrival or a background refresh still never
re-ranks the list. Only a press the owner makes on a sort or filter control re-orders it, and
it re-orders at once.

**D132** protects a walk the owner does not scroll through sold cards to use. That stays, at a
safer moment. The sold row folds on the next box load or refresh, when no row is under the
hand. Until then it reads "Sold" in place and keeps its height.

**D142** protects a box list that starts where the hand left off. Most recent first on every
screen keeps that, and the kit-data lane's `BoxLabel` list draws it once for all screens.

### What is still open

- **Which clock "most recent" reads.** D132 reads the last press on a box, stored on the
  device (`banchi.box-recency`). Home and Cards to pull have no such press today. The builder
  asks the owner before choosing between the last press and the last capture.
- **The rail re-orders under the pointer** (FLT-21). A press on a box moves it to the top of
  the rail at the press. The owner did not rule on this case. The "nothing jumps" ruling
  suggests the same timing: re-order on the next visit.

### What is built

NOT BUILT. The filtering lane builds rulings 1 and 2. The kit-data lane builds ruling 3.
`app/tests/inventory.spec.ts` already asserts D118 around a sale. The filtering lane extends it
to the next click after a sale, red on today's tree first.
