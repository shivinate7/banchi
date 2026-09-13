## D114 — The status requirement is answered by a remembered tick, not by an echo of the preview

**Built 2026-09-06, on the owner's report.** They pressed *Fetch from TCGplayer* and got every
order in the window back, long-shipped ones included, and expected only the orders that still
need work. The behaviour is not a bug in anything: it is what two rulings produce where they
meet, and neither of them is wrong.

**D91 MADE THE SERVER REFUSE TO GUESS, AND THAT PART IS UNCHANGED.**
`POST /orders/fetch` answers `statuses_required` to a call that names none, and
`server/order_transport.py` argues it at length: TCGplayer never published the status
vocabulary — one capture, one account, one afternoon — and a guess that drops an order is an
envelope that never ships. The comparison there is `str(status).strip() in wanted`, verbatim,
never folded and never mapped. **Nothing on this branch touches any of that.**

**THE OWNER THEN RULED OUT D91's TWO-PRESS FLOW** — *"why would it ever say 1 of 3 found"* — so
`Orders.tsx` answered the requirement mechanically: a free `previewOrders()`, then
`seen.by_status.map((row) => row.status)` handed straight back to `fetchOrders`. Somebody NAMED
the statuses, which is all the wire ever asked for. What nobody did was CHOOSE them. So nothing
was dropped (D91's goal) and nothing was narrowed (nobody's goal), and the press has been
taking the whole window since the day it was written.

**THE VOCABULARY IS KNOWABLE AT RUN TIME, WHICH IS THE WHOLE OPENING.** The preview already
returns `by_status` — the status string, how many orders carry it, and how many of those the
ledger already holds at that status — for one search page per 25 orders, no detail call and
`writes_nothing: true` on the answer. That is a real list of real strings, and it is the only
list this product may ever draw a status picker from.
**There is no status vocabulary anywhere in `app/`**, and adding one would be the defect
`order_transport.py` refuses at the other end.

**So: the operator ticks, this device remembers, and the press stays one press.**
`banchi.orders.fetch-filter` in `app/src/deviceMemory.ts` holds the tick list and one more
toggle; the picker sits beside the Fetch button on `#/orders` and is never in front of it. An
operator who never opens it fetches exactly what they fetched yesterday.

**THE DEFAULT WAS "EVERY STATUS" UNTIL THE NUMBERS CAME IN, AND THE OWNER CHANGED IT.** This
entry was drafted, built and reviewed with an unchosen device fetching the whole window — an
operator who never opens the control loses nothing, which is a good instinct and was the wrong
answer here. A parallel session measured the owner's own store the same afternoon, and every
figure below was re-derived independently against `inventory/store.sqlite` and the live
`GET /orders` before it was acted on:

- **100 orders: 68 `Shipped - In Transit`, 18 `Shipped - Delivered`, 14 `Ready to Ship`.**
- **83 are OPEN by the ledger's reckoning, and 69 of those 83 TCGplayer has already shipped.**
  `open` means "still owes copies" and nothing here ever pulled them: those orders were shipped
  without going through this app, so they never leave.
- **Those orders hold 31 physical copies, and three Ready-to-Ship lines read `short`.**
  `pipeline/orders.py:resolve_all` walks `order_sequence` — oldest `placed_at` first — over ONE
  shared `_Draw`, whose `_taken` set stops two orders claiming one copy. A delivered order from
  August is older than a live one from September, so it takes the card first, and the picker is
  told a card is unavailable while it sits in a box.

So the every-status default does not merely fail to help. It keeps a correctness defect alive on
every device where nobody opens the panel, which is every device by construction.

**AND THE OBVIOUS FIX IS THE ONE THING THIS PRODUCT MAY NOT DO.** "Everything except the shipped
ones" requires `app/` to know that `Shipped - In Transit` means shipped. That vocabulary does not
exist — `server/order_transport.py` refuses to have it, and the same session refused the same
guess at ingest for the same reason: the set is open-ended, and a `Refunded` TCGplayer adds next
year is swallowed silently by a rule written against this year's strings.

**So a human is asked once, in front of the real list, and never again.** The owner chose this on
2026-09-06 over both alternatives. `asked` is a third field on the key: the first press runs the
preview, opens the panel with everything ticked, and details NOTHING; its own primary press —
*Fetch these 370 orders* — records the answer and completes the errand. Touching any tick counts
as answering too, because somebody unticking a status has already done the thing the ask is for.

**THIS IS NOT D91's TWO-PRESS FLOW COMING BACK.** That asked on *every* press, and the owner
ruled it out — *"why would it ever say 1 of 3 found"*. This is spent once per device, ever, and
what it buys is the one thing no default can: somebody has looked at the actual strings, which is
the only place in this product where a status may be judged.

**SIX THINGS THIS TURNS ON, AND EACH OF THEM IS THE DIFFERENCE BETWEEN A FILTER AND A LIE:**

**1. Unchosen is not "all ticked", and "all ticked" is not "unasked".** `statuses: null` is
"every status this window holds" and stays the value a confirmed device usually carries — a
stored LIST would silently drop a status TCGplayer adds next month, the exact drop D91 exists to
prevent. `asked` is the separate fact that a human has seen the list. An empty list is a third
state and the screen refuses it by name rather than letting the wire answer `statuses_required`,
which is a true sentence about a body and a useless one about a choice somebody made on this
screen. The first untick materialises the list out of THIS WINDOW, which is the only place
strings can come from; ticking back to everything returns to null, so a device does not carry a
list that the next window would narrow against.

**2. A remembered tick the window returned nothing for is drawn, not dropped.** The fetch
cannot ask for a status no order carries, so the string falls out of the call — and it is named
in the receipt and kept on the panel with *none in this window* beside it. Dropping it silently
is the same defect as the one this entry fixes, one register down: the operator said something
and the screen quietly did otherwise.

**3. The receipt's window figure is now two figures.** It drew `matched` as *"N in the
window"*, which was true only while `matched` WAS the window. It is `total` from the preview
now, with *"N matched your statuses"* as a second clause where a filter is set, and no second
clause where none is — the two side by side are what say the filter did something.

**4. "New since" is suppressed where the question changed.** `banchi.orders.last-check` gains
the scope it was taken under, and two `matched` figures counted under different filters are
counts of different things. Subtracting them would put a confident *"12 new"* under a press that
merely narrowed. The clause says *different statuses* instead.

**5. `skip_known` is on the panel because it was a route no screen reached.** It has been on
the wire since D91 and on `fetchOrders` since the client function was written, and nothing ever
sent it — which CLAUDE.md's *a route is not a feature* calls the unfinished half of that task
rather than a follow-up. It narrows the same press for the same reason, so it is ticked in the
same panel, and it shares the key: one habit, one roster row.

**WHY `localStorage` AND NOT THE STORE.** *"I do not want to look at completed orders"* is a
statement about how the person at this screen works — the same kind of fact as the remembered
camera and the theme. It names no order, no card, no position and no SKU, so D13's one truth
about where a card is stays on the Mac, which is the whole of what that ban protects. It went
in `deviceMemory.ts` rather than at its call site, which is what `app/eslint.config.js`'s own
message asks for: the rule bans the STORE, so a named file is the only exception it can
express, and a new key belongs where the reviewer is already looking.

**6. A browser that refuses storage is asked every time**, which is the honest consequence of
refusing storage rather than a case to work around. `storedOrderFilter` returns UNASKED on a
throw, and UNASKED is the safe direction: the unsafe one imports orders delivered a month ago and
lets them hold copies a live order needs.

**What was NOT done, and it is the thing this entry is most about:** no status is coded, here or
anywhere in `app/`. Every string on the panel came off the preview and goes back to the fetch
verbatim. The ask exists precisely so that the product never has to have an opinion about which
of them means "already gone".

**What is NOT fixed by this, and D113 is what fixes it:** the 69 shipped orders ALREADY in the
owner's ledger. A door filter cannot retroactively clear what came through before it. That is the
order-level stand-down, built separately and merged as PR #198 while this branch was open — the
two were kept apart on purpose, both touching `#/orders` and the fulfilment map.
**This entry is numbered D114 for that reason**: D113 reached main first, and the rule is
renumber your own, never another's. The two answer the same complaint from opposite ends — that one clears what is
already in, this one stops more arriving — and neither is sufficient alone.

**What retires this:** TCGplayer publishing the status vocabulary. Then a shipped order could be
recognised rather than merely counted, and the picker could carry a real default instead of the
window's own list.

**AMENDED 2026-09-13 (`D193`): the first-press gate this entry built is gone, and the picker is now secondary rather than the door.** The owner's 2026-09-13 rulings
made the ordinary press "all statuses, skip-known" the default action — a one-time
`LastTwoYears` backfill, then an append of everything the ledger does not already hold — so
`if (!using.asked)` no longer stands between a press and a fetch. `StatusPicker` survives as
"Only these statuses…", reachable from the well rather than blocking the primary button; the
vocabulary it draws is still read off the live preview, never coded, for exactly the reason
this entry gives. What is retired is the ASK, not the six things this entry's own numbered
list argues for `statuses: null` versus `asked`; those still hold for an operator who narrows
on purpose.
