## D214 — Sales shows gross, never profit

**Ruling: `#/revenue`, labeled Sales, shows gross revenue only. It never shows profit, fees or cost.** The screen reads the order ledger that already exists. Nothing here is new data.

**The problem.** TCGplayer's seller Orders page indexes orders, not line items. It cannot answer "how much have I made selling one named card". This store's order ledger already carries every line's `unit_price` (`OrderLine`, `store/orders.py`). Sales is one reshaping of that ledger. It shows a verdict sentence for the selected period, a month strip, and a product table that is searchable by name.

### Why its own route, not a lens on `#/orders`

D105 drew the line this decision follows. Reading the same data is kinship of implementation. A route earns its place on kinship of job. `#/orders` is the operational walk: which buyer gets which copies, where they are, pulled one at a time. Sales asks a different question of the same ledger: what did I make, and on what. It is a retrospective over closed orders, by month, searched by product name. A `?view=` lens on `#/orders` would put a retrospective behind a screen whose shape answers an operational question. Two jobs, one shared table, two routes. D69 gave `#/orders` and `#/shipping` the same shape.

### Why gross only

No cost basis exists anywhere in this repository. No fee, shipping or refund figure exists either. `server/order_transport.py`'s `project_order` allowlist drops `transaction` and `refunds` at parse, before either reaches a wire response. A net figure would need one of two invented inputs: a cost basis this store never recorded, or a fee schedule read from nothing. Presenting either as real would be a lie dressed as data. Gross is the only number in this ledger that is true. The screen says "gross" in its own lede. It never subtracts, estimates or asks for a cost. A cost-basis feature, if built, is a second, clearly labeled figure beside this one. It never replaces this one silently.

### Why the table stays mixed

`OrderLine.kind` is null on nearly every line, because the feed says nothing about it. CLAUDE.md and `pipeline/orders.py`'s header refuse classifying a line by pattern-matching its product name. A guess dressed as a fact is worse than an admitted unknown. On the owner's live store, sealed product dominates revenue. Booster packs and boxes make up the top eight names by gross. A screen that assumed singles would be wrong about most of its data on day one. The product table is one list, sorted by gross. It stays that way until the feed carries a real `kind`.

### Measured on the owner's live store

804 orders and 1,346 lines, with zero missing `unit_price`. Excluding Canceled: $66,334.71 gross over 1,268 lines and 539 distinct product names, across the store's whole sales history. `GET /orders` answers in 230ms at 1.15MB. The screen adds no server route, no parsing, and no change to `server/capture_server.py:do_orders`, to order resolution, or to ledger behavior. It reads that one payload and reshapes it in `app/`.

### Canceled is dropped, silently

**Ruling: an order the feed calls Canceled is not a sale.** It does not appear on this screen, and no footnote explains its absence. This is narrower than `store/orders.py:is_terminal_status`. Shipped and Completed orders are terminal too, and they are real revenue. So this screen compares exactly one word, `Canceled`, against the wire's `status` string. It folds case and edge whitespace first, as `is_terminal_status` does. It is not a second `TERMINAL_STATUSES` copy. It recognizes one word, not a vocabulary.

See also: D69 (a screen earns a route on its job, not its data source), D86, D103 and D105 (kinship of implementation is not kinship of job), and D193 (the ledger's buyer field is unread here. This screen never draws a name, an address or a payment detail).

### The nav row

`#/revenue` is an eleventh nav row, on purpose. The screen shipped with a nav row and a hotkey. The owner was shown the measurement: an eleventh row runs the phone drawer's rows 37px past the fold at 390x754, with the rows at the 40px thumb floor CLAUDE.md sets. There is no lower step to give. The owner first ruled the row off: keep the drawer whole, and reach Sales from the command palette and a link on `#/orders`. The owner then reversed that ruling: Sales is a sidebar tab, and no other screen gets a control for it. The off-nav shape had grafted a control onto `#/orders`, and onto `#/shipping` through the shared `OrdersHub`. That graft is reverted. `app/src/Orders.tsx` matches main again. A workaround does not belong in a shared component. One change had become two, on two screens, because the two routes share one component.

`app/tests/brand.spec.ts`'s two drawer-fit cases carry that arithmetic. They drop the test's own stricter promise: every row visible, with nothing to scroll to. D266 already rules that the phone drawer's nav scrolls for any row count, so that promise was never a product floor. Only a test's promise changes here. No decision does.
