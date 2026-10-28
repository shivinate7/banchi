# D97 — Copy map ranks, never picks

**An order line draws every box that holds the ordered card. It ranks the boxes by free copies and recommends without making the choice.** The design on `#/orders` came from the owner. The owner's rule: the best option holds the most of the unit in one box, and within one box, in one section. The walk does not pick.

**The rank is over free copies, not over copies held.** A box holding three, of which two are already recorded against somebody, is a worse stop than a box holding two that nobody counts on. A recommendation that walked you to the first would send you on a wasted trip. The held count is still drawn on the block, because it is true of that drawer. It gets no vote. Ties break to the lower box number. Sections inside the leading box rank by the same rule, one level down.

**Nothing is preselected and nothing is hidden.** Every copy the store holds of that card is drawn beneath the map, in the map's own order, with its own control. That includes copies in far boxes, a copy another open order was offered, and a copy the ledger has already recorded. A recorded copy is drawn and marked, and it is not pressable. The map is the union of this line's resolver picks and the store's on-hand copies of the same SKU. It is deduped on box and index, and the resolver's row wins, because that row carries who holds it. A resolver that offered three copies while the store holds nine must show nine. D93 made the copies panel the picker on the inventory side. This is the same principle on the order side: the machine ranks, the person reaches.

### The walk plan is the same rule one level up

**Above an order's lines, the boxes rank by how much of the whole order each one satisfies.** A buyer who wants four different singles is walked in one pass, not four. The plan is additive. No line's map changes, and no copy is chosen. Inside a stop, the sections list in ascending order, not by density. At this level the question is which parts of the drawer the walk passes through. A hand goes front to back. Density decides what to reach for, and that decision belongs to the per-line map.

### A partly-pulled line says what remains

**The figure on a line is `N remaining`, with `2 already pulled` kept quiet beside it. It is never `1 of 3 found`.** The owner ruled this wording. The buyer's original quantity is not a progress denominator on this screen. A denominator suggests the store failed to find two, when two copies are in the envelope.

**The pulled count is the ledger's, not the resolver's. Getting that wrong is the easy mistake here.** `ResolvedLine.fulfilled` is the number of copies the resolver can offer now. `outstanding` is the same arithmetic over the same quantity, so neither can say how many copies are already taken. `OrderRow.progress` carries the ledger's recorded count per SKU, and that is the answer. The merge brings `ResolvedLine.recorded`, and the lookup goes there.

### What is not built, and what would reopen this

**It is sized to the owner's own store and nothing deeper.** The densest SKU there holds fourteen copies of one card, all fourteen in box 3 section 4. Fourteen identical pressable rows is a wall, not a choice. So six copies are drawn and the rest fold. Six is more candidates than any line needs. The largest `remaining` across the owner's twenty open orders is four. The fold leaves 51 of the 59 lines drawing every copy with no fold at all. The map blocks never fold, because the drawers a card sits in are the primary read. A deeper store has never rendered this. The fold is the first figure to re-measure against one.

**A copy another open order was offered is a mark, not a lock.** It stays pressable. Two orders that want the same card are the operator's problem, and the fact belongs in front of them. The screen should not solve it by hiding a row. If that causes a real double-take against the ledger, the mark becomes a refusal. D93's *a full line refuses the take* is the shape it takes.

**Amended in D274: the fact is no longer marked on screen.** The owner ruled that the claim by another order is not shown as a visual descriptor. The "mark rather than a lock" sentence above described a visible caption: `.orders-pick-claim` and `.orders-map-claimed` named which order was offered a shared copy. That caption is deleted. The lock half is unchanged. The row stays pressable, and `LineCopy.claimedBy` still keeps a claimed copy out of `free` for the density rank. Only the on-screen naming of the other order is gone.

---
