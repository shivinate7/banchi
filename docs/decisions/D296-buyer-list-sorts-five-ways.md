## D296 — Buyer list sorts six ways

**The owner's request, verbatim, 2026-09-25:**

```
on orders, on its filters, under the sort category, you can only pick placed by newest and
placed by oldest, we could have more there? dollar value? etc?
```

The owner then picked all four suggestions offered back to him: **Dollar value, Card count, Buyer name, Fewest drawers to open.**

### The ruling

1. **Every sort ranks BUYERS, never orders.** Each reads an aggregate over the group's OPEN
   orders (D193), the same register every other figure on this screen already uses
   (`groupMissing`, `verdictOf`'s lede). Dollar value is the buyer's order total
   (`quantity * unit_price`, summed over every open line). It takes D221's mono face
   wherever it is drawn. Card count is copies still owed, the same figure `verdictOf` sums
   store-wide. Buyer name is the label the row already draws (`buyerLabel`). Fewest drawers
   is the count of distinct physical boxes the walk planner's own solve says hold this
   buyer's copies.

2. **The ready lead is a GROUPING, kept across every key.** A buyer whose every owed copy is in
   the boxes (the buyer's pull status reads Ready) leads, whatever key is picked. A buyer finished
   on this screen counts as ready, so it keeps its place. The owner changed this lead: it was the
   feed's "Ready to Ship" status, and is now whether the copies are in the boxes ("Ready first,
   then oldest order"). The bucket check runs BEFORE the picked key's own comparison, in
   `orderView.ts:compareGroups`, never inside one key's arm. The caller says who is ready, so the
   comparator stays pure. **At rest the key is "Oldest order" (`waited`), oldest first.** It reads
   the buyer's EARLIEST open order, so the buyer who has waited longest comes first. The `placed`
   key still reads the buyer's newest order, as ruling 1 says. A buyer who becomes ready
   mid-view does not jump: the position freeze (ruling 6) holds every row until the next sort,
   filter or search press retakes the order.

3. **Ties break by placed date, newest first, on every key.** This is the owner's own words
   for this task, read as the one tiebreak all six keys share.

4. **Fewest drawers reuses the walk planner's own solve.** It is never a second box-counting
   pass. `POST /orders/walk-plan` (`pipeline/walkplan.py`) already answers, for a set of
   order keys, which boxes hold which take, and for which orders
   (`WalkPlanStop.takes[].for`). `Orders.tsx` fetches one plan over every walkable order on
   the screen. It fetches lazily, only while this sort is picked. `orderView.ts:
   drawerCountsFromPlan` reads that plan. It is a pure function over data the screen already
   fetched, never a fetcher of its own. A pooled stop (D24) holds no box and is never
   counted. A SKU the plan could not fill at all (`shortfall`) touches no stop either.

5. **An unplaced buyer counts as 0 drawers, and 0 ranks FIRST by default.** A buyer whose
   copies are entirely pooled, entirely a shortfall, or who owns no walkable order at all
   gets 0. Ascending (the key's default direction) puts them first. This reads correctly:
   there is genuinely nothing to open for that buyer, so "fewest drawers to open" is 0, the
   true minimum. It is recorded here on purpose. A buyer waiting on stock the store lacks is
   not the same fact as a buyer standing at one drawer. This sort does not tell them apart
   from each other, only from a buyer standing at one or more.

6. **Three of the six keys read mutable fields, and a freeze protects all six alike.**
   Dollar value and Card count read `OrderLineWire.quantity`/`unit_price` against what a pull
   has recorded. Fewest drawers reads a network answer that also changes under a pull.
   Picking any of the three would re-rank the list under the operator's hand the moment a
   write lands (D181, D118), with no freeze. A position snapshot
   (`GroupTake`/`takeOrder`/`applyTake` in `orderView.ts`) is taken at every EXPLICIT input —
   a sort press, a facet, a search keystroke. It is held across a write's own re-render. This
   generalizes D181's "a press may reorder, nothing else may" to every key alike. It does not
   freeze three of six and leave `placed`/`buyer` unguarded by mere convention. The snapshot
   also retakes the moment a freshly-picked Fewest-drawers sort's own walk-plan answer lands.
   That fetch is the one this press itself asked for. It is not held back by the freeze that
   guards against a pull. The first rows to land are taken too: the first render has no ledger,
   and an empty take froze nothing.

### What was tried and rejected

Scoping the position freeze to only the three volatile keys, and leaving `placed` and
`buyer` recomputed live on every render, was rejected. It works today: neither field moves
under a pull. But it makes the freeze a property of which key happens to be volatile right
now, rather than a property of the list. A future key that starts stable and later gains a
mutable aggregate would silently lose the protection. Freezing every key alike costs nothing
observable for the two stable ones, and it closes that gap.

### What is not built

No per-buyer live price re-read. Dollar value is the order's own ask (`unit_price *
quantity` from the feed). It is not a live market price. The owner's word was "order total,"
and a live re-price is a different figure `#/pricing` already owns (D86).

No settings for the tiebreak. Ties always break by placed date, newest first, on every key.
This matches the owner's own words for this task, rather than a per-screen preference.

A sort orders and hides nothing; the ready buyers lead, and every other buyer stays reachable.
