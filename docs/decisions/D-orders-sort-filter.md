## D-orders-sort-filter — The buyer list leads with Ready to Ship, and a re-sort is a press

**The owner's ruling, verbatim in intent, 2026-09-13:** TCGplayer "Ready to Ship" leads the
buyer list, newest first within a group, and everything else stays reachable behind a status
control rather than dropped by a default nobody chose. Read as an ORDERING, not a hiding — the
same shape D103 already ruled for staleness ("a filter and not a gate").

### The controls

One strip on `#/orders`' Pull stage, in `mode === 'orders'` only: a **Status** select built from
the distinct `status` strings the FEED itself sent, with counts (D114 — "there is no status
vocabulary anywhere in `app/`"); **Sort** (`Newest`/`Oldest`, on `placed_at`); and **Hide unknown SKUs**, a toggle over the `sku_unseen` line reason the "Never seen" chip already carries. All
three default to "show everything" and compose as an AND with the existing reason chips; sort
applies last. `app/src/orderView.ts` is the pure module behind all of it.

### The freeze

A re-sort or an arrival that would reorder the buyer list is exactly the reshuffle D181
forbids on `#/inventory`'s copies list — a press the operator made may reorder; nothing else
may. `app/src/frozenRank.ts`'s ruling is carried over rather than respelled, adapted to a
total order with insertions rather than a per-row departed/live boolean: `OrderTake` is a
position snapshot (group key -> index) taken at the last explicit action, `applyTake` renders
known groups in their taken order and appends anything new after them, and `staleCount` is
the same "how far does this differ from a fresh take" question `stalenessSentence` already
answers for copies. A changed STATUS or hide-unknown toggle retakes immediately (an explicit
new question); a changed SORT direction or a new arrival only offers to, via a reserved
`Order is N buyers stale · re-sort` chip (D118 — the slot is always rendered).

**Why not `frozenRank.ts`'s own types verbatim:** that module's argument against snapshotting
a rendered array of keys is that three call sites (the copies list, the box rail, the walk's
landing) already compute one ordering from a single per-row predicate, and a fourth copy of
that arithmetic would drift the day one call site gains a term. Neither premise holds for the
buyer list — there is exactly one call site, and what moves under it is not a per-row boolean
but the comparator's own two keys (a status bucket transition, a sort flip) plus insertion of
new groups, which a single frozen boolean per key cannot describe. `OrderTake`'s position map
is the smallest state that answers the same question for that shape.

### Storage

`view: {status, sort, hideUnknown}` is added to `banchi.orders.fetch-filter`'s existing
document (`app/src/deviceMemory.ts`) — not a new `localStorage` key. D142's precedent for the
six capture values applies word for word: the view a person works the buyer list in is the
same habit as the fetch filter beside it in that document.

### What this does not do

No date range: the status control plus newest-first answers the stated want, and a range is a
second control to maintain for a case nobody has hit. The freeze does not extend to the
`Earlier` (closed, >7-day) fold — it is a secondary bucket under the "Done" chip only and is
left sorted the way `orderBuyers.ts` already sorts it, to keep this change's blast radius to
the primary list the owner described.
