## D97 — The copy map ranks and never picks, and a line says what remains

**An order line draws every box that holds the ordered card, ranked by how many free copies each holds, and it recommends without ever making the choice.** Built 2026-09-03 on `#/orders`, from the owner's own design: *"a map is good, with the highest option being basically the option that has the most of the unit in one box, and if within one box already then within one section"*, under the constraint quoted in D96 — the walk does not pick.

**The rank is over free copies, not over copies held.** A box holding three of which two are already recorded against somebody is a worse stop than a box holding two nobody is counting on, and a recommendation that walked you to the first would be recommending a wasted trip. The held count is still drawn on the block, because it is a true thing about that drawer; it simply gets no vote. Ties break to the lower box number, and sections inside the leading box rank by the same rule one register down.

**Nothing is preselected and nothing is hidden.** Every copy the store holds of that card is drawn beneath the map in the map's own order with its own control — copies in far boxes, a copy another open order was offered, and a copy the ledger has already recorded, which is drawn, marked, and not pressable. The map is the union of this line's resolver picks and the store's own on-hand copies of the same SKU, deduped on box and index with the resolver's row winning, because that row is the one carrying who holds it. A resolver that offered three copies and a store holding nine is a screen that must show nine: D93 made the copies panel the picker on the inventory side, and this is the same principle on the order side — the machine ranks, the person reaches.

### The walk plan is the same rule one register up

**Above an order's lines, the boxes are ranked by how much of the whole order each satisfies**, so a buyer wanting four different singles is walked in one pass rather than four. It is additive: no line's map changes, and no copy is chosen. Inside a stop the sections are listed ascending and deliberately not by density — at the plan's register the question is which parts of the drawer the walk passes through, and a hand goes front to back. Density decides what to reach for, and that decision belongs to the per-line map.

### A partly-pulled line says what remains

**The figure on a line is `N remaining`, with `2 already pulled` kept quiet beside it, and it is never `1 of 3 found`.** The owner: *"It should say 1 remaining why would it ever say 1 of 3 found."* The buyer's original quantity is not a progress denominator on this screen. A denominator invites the reading that the store failed to find two, when what happened is that two are in the envelope.

**The pulled count is the ledger's and not the resolver's, and getting that wrong is the easy mistake here.** `ResolvedLine.fulfilled` is the number of copies the resolver can offer right now and `outstanding` is the same arithmetic over the same quantity, so neither can answer how many have already been taken; `OrderRow.progress` carries the ledger's own recorded count per SKU, which is that answer. The merge brings `ResolvedLine.recorded` and the lookup goes then.

### What is not built, and what would reopen this

**It is sized to the owner's own store and to nothing deeper.** The densest SKU there holds fourteen copies of one card, all fourteen in box 3 section 4, and fourteen identical pressable rows is a wall rather than a choice — so six copies are drawn and the rest fold, which is more candidates than any line needs (the largest `remaining` across his twenty open orders is four) and leaves 51 of his 59 lines drawing every copy with no fold at all. The map blocks themselves never fold, because the drawers a card sits in are the primary read. A store deeper than that one has never rendered this, and the fold is the first figure to re-measure against one. **And a copy another open order was offered is a mark rather than a lock** — pressable, because two orders wanting the same card is the operator's problem to solve with the fact in front of them, not the screen's to solve by hiding a row. If that produces a real double-take against the ledger, the mark becomes a refusal and D93's *a full line refuses the take* is the shape it takes.

---
