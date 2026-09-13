## D-home-counts-only-open-orders — Home's "cannot be filled" figure counts only orders that read `open`

**The report.** Home's front-page standing line painted `tone: 'danger'`, `lead: 'Cannot be
filled'` and summed copies "for N open orders" across every row `GET /orders`'
`resolution.orders` carried — unconditionally, with no check against which of those orders
were still open. The Orders stage tile's note (`X not found`) summed the same field the same
way. Pressing the button either one offers goes to `#/orders`, which explains a terminal
order's stand-down calmly; the front page's own wording did not distinguish it from a
genuine shortfall.

**Root cause.** `server/capture_server.py:do_orders` (D63 amended 2026-09-13) already excludes
a terminal order — Canceled, Shipped - In Transit, Shipped - Delivered
(`store/orders.py:TERMINAL_STATUSES`) — from `open_keys` before either the wire's per-row
`open` field or `resolution.orders` is built, so in an ordinary response the two are already
the same population and `resolution.orders` is a strict subset of the open rows. Neither
`app/src/standing.ts` nor `app/src/Home.tsx` read `open` when summing `resolution.orders`,
trusting that upstream narrowing blind rather than checking it. That is correct today and
would stop being correct the moment either module's assumption about the other's shape drifted
without a compiler or a test noticing — the client had no way to tell "the server always
filters this" from "the server happened to, this time."

**The fix.** Both modules now index the wire's `open` orders by `key` and sum a
`resolution.orders` entry's `outstanding` only where its own order's key is in that set —
`standing.ts`'s `unfindable` and `Home.tsx`'s Orders-stage `unfindable`, the same join in both
places rather than two independent trusts of the same invariant. Neither reads `status` or
grows a copy of `store/orders.py:TERMINAL_STATUSES` — `open` is the one field either module
is allowed to read (D114: "there is no status vocabulary anywhere in `app/`"), and D63's own
terminal-override paragraph is the authority for what `open` already means; this entry does
not amend it, only makes the client's arithmetic agree with it by construction rather than by
assumption.

**Guard.** `app/tests/home.spec.ts` hands the client a `resolution.orders` shaped as a stale
or partially-narrowed response would be — one open order short 2 copies, one order whose own
`open` field reads `false` (a Shipped - Delivered status) still carrying a `resolution.orders`
entry short 5 — and asserts the standing sentence and the Orders tile both read "2", never
"7". Red on the unfixed tree (`"Cannot be filled — 7 copies for 1 open order cannot be
found."`, tile note `"7 not found"`); green after.

**What this does not touch.** D63's terminal vocabulary and its amendment are read from, not
reopened — this is the client half of "read from the same source," applied to a boolean the
wire already carries rather than a predicate derived from `status` text. `standing.ts`'s
ranking and null invariant (D121) are unchanged: `unfindable`'s null-ness still follows
`orders === null` alone, and the `open`-keyed sum only refines a number that was already fully
resolved.
