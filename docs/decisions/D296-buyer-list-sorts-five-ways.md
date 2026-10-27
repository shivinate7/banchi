# D296 — Buyer list sorts six ways

**The owner asked for more sort keys on the orders filters.** The screen offered only "placed by newest" and "placed by oldest". The owner then picked all four suggestions offered: **Dollar value, Card count, Buyer name, Fewest drawers to open.**

### The ruling

1. **Every sort ranks BUYERS, never orders.** Each reads an aggregate over the group's OPEN orders (D193), the same basis as every other figure on this screen (`groupMissing`, `verdictOf`'s lede). Dollar value is the buyer's order total (`quantity * unit_price`, summed over every open line). It takes D221's mono face wherever it is drawn. Card count is copies still owed, the same figure `verdictOf` sums store-wide. Buyer name is the label the row already draws (`buyerLabel`). Fewest drawers is the count of distinct physical boxes that the walk planner's own solve says hold this buyer's copies.

2. **The ready lead is a GROUPING, and it holds for every key.** A buyer whose every owed copy is in the boxes (the buyer's pull status reads Ready) leads, whatever key is picked. A buyer finished on this screen counts as ready, so it keeps its place. The owner changed this lead. It was the feed's "Ready to Ship" status. It is now whether the copies are in the boxes. The order is "Ready first, then oldest order". The bucket check runs BEFORE the picked key's own comparison, in `orderView.ts:compareGroups`, never inside one key's branch. The caller says who is ready, so the comparator stays pure. **At rest the key is "Oldest order" (`waited`), oldest first.** It reads the buyer's EARLIEST open order, so the buyer who has waited longest comes first. The `placed` key still reads the buyer's newest order, as ruling 1 says. A buyer who becomes ready mid-view does not jump. The position freeze (ruling 6) holds every row until the next sort, filter or search press retakes the order.

3. **Ties break by placed date, newest first, on every key.** This is the one tiebreak that all six keys share. It was set by the owner for this task.

4. **Fewest drawers reuses the walk planner's own solve.** It is never a second box-counting pass. `POST /orders/walk-plan` (`pipeline/walkplan.py`) already answers, for a set of order keys, which boxes hold which take, and for which orders (`WalkPlanStop.takes[].for`). `Orders.tsx` fetches one plan over every walkable order on the screen. It fetches lazily, and only while this sort is picked. `orderView.ts:drawerCountsFromPlan` reads that plan. It is a pure function over data the screen already fetched. It is not a fetcher of its own. A pooled stop (D24) holds no box and is never counted. A SKU the plan could not fill at all (`shortfall`) touches no stop either.

5. **An unplaced buyer counts as 0 drawers, and 0 ranks FIRST by default.** A buyer whose copies are all pooled, all a shortfall, or who owns no walkable order gets 0. Ascending order, the key's default direction, puts them first. This is correct. There is genuinely nothing to open for that buyer, so the fewest-drawers count is 0, the true minimum. It is recorded here on purpose. A buyer waiting on stock the store lacks is a different fact from a buyer standing at one drawer. This sort does not tell them apart. It separates both from a buyer standing at one or more drawers.

6. **Three of the six keys read mutable fields, and one freeze protects all six alike.** Dollar value and Card count read `OrderLineWire.quantity` and `unit_price` against what a pull has recorded. Fewest drawers reads a network answer that also changes under a pull. Picking any of the three would re-rank the list under the operator's hand when a write lands (D181, D118), with no freeze. A position snapshot (`GroupTake`, `takeOrder`, `applyTake` in `orderView.ts`) is taken at every EXPLICIT input: a sort press, a facet, or a search keystroke. It is held across a write's own re-render. This extends D181's "a press may reorder, nothing else may" to every key. It does not freeze three keys and leave `placed` and `buyer` unguarded by convention. The snapshot also retakes when a freshly picked Fewest-drawers sort receives its walk-plan answer. That fetch is the one this press asked for, so the freeze does not hold it back. The first rows to land are taken too. The first render has no ledger, and an empty take would freeze nothing.

### What was tried and rejected

Limiting the position freeze to the three volatile keys was rejected. It works today, because neither `placed` nor `buyer` moves under a pull. But it makes the freeze a property of which key is volatile right now, not a property of the list. A future key that starts stable and later gains a mutable aggregate would lose the protection without notice. Freezing every key costs nothing visible for the two stable keys, and it closes that gap.

### What is not built

No per-buyer live price re-read. Dollar value is the order's own ask (`unit_price * quantity` from the feed). It is not a live market price. The owner's term for it was order total. A live re-price is a different figure, and `#/pricing` already owns it (D86).

No settings for the tiebreak. Ties always break by placed date, newest first, on every key. This is the owner's ruling for this task, not a per-screen preference.

A sort orders and hides nothing. The ready buyers lead, and every other buyer stays reachable.
