## D-gross-sales-retrospective — A gross-revenue retrospective is its own route, and it never claims to be profit

**The problem this closes.** TCGplayer's own seller Orders page indexes orders, not line
items. There is no way to ask it "how much have I made selling Charizard ex". This store's
own order ledger already carries every line's `unit_price` (`OrderLine`, `store/orders.py`).
The answer was always one reshaping away. `#/revenue`, labelled **Sales**, is that reshaping:
a verdict sentence for the selected period, a month strip, and a searchable table by name.
Nothing here is new data.

### Why its own route, and not a lens on `#/orders`

D105 already drew the line this decision follows. Reading the same data is kinship of
IMPLEMENTATION, and a route earns its place on kinship of JOB. `#/orders` is today's
walk — which buyer gets which copies, where they physically are, pulled one at a time. This
screen asks a different question of the same ledger. Not "what do I still owe", but "what did
I make, and on what" — a retrospective over everything closed, months at a time, searched by
a product's name rather than walked order by order. A `?view=` lens on `#/orders` would put a
retrospective behind a screen whose whole shape answers an operational question. Two jobs,
one shared table, two routes — the same shape D69 already gave `#/orders` and `#/shipping`.

### Why gross-only is the honest product, not a half-built P&L

There is no cost basis anywhere in this repository. There is no fee, shipping or refund
figure either: `server/order_transport.py`'s `project_order` allowlist drops `transaction`
and `refunds` at parse, before either ever reaches a wire response. Building a "net" number
here would mean inventing one of two things. Either a cost basis this store has never
recorded, or a fee schedule read off nothing. Presenting either as a real figure would be a
lie dressed as data. **Gross is the only number in this ledger that is actually true.** The
screen says "gross" in its own lede rather than implying a profit or loss. It never subtracts,
estimates, or asks for a cost. A real cost-basis feature, if it is ever built, is a second,
clearly-labelled figure beside this one — never a silent replacement.

### Why the table stays mixed, sealed and singles together

`OrderLine.kind` is null on nearly every line because the feed says nothing about it.
Classifying a line by pattern-matching its product name is refused at length by CLAUDE.md and
`pipeline/orders.py`'s own header. A guess dressed as a fact is worse than an admitted
unknown. Measured on the owner's live store, 2026-09-19, revenue is in fact dominated by
sealed product. Booster packs and boxes make up the top eight names by gross. A screen that
assumed singles would be wrong about most of its own data on day one. The product table is
one list, sorted by gross, and stays that way until the feed itself carries a real `kind`.

### Measured, once, on the owner's live store (2026-09-19)

804 orders, 1,346 lines, zero missing `unit_price`. Excluding Canceled: $66,334.71 gross over
1,268 lines, 539 distinct product names, spanning 2026-05 through 2026-09. `GET /orders`
answers in 230ms at 1.15MB. There is no new server route, no new parsing, and no change to
`server/capture_server.py:do_orders` or to any order resolution or ledger behaviour. This
screen reads that one payload and reshapes it in `app/`.

### Canceled is dropped, silently, on the owner's own ruling

The owner's instruction, 2026-09-19, having been shown the alternative: an order the feed
calls Canceled is not a sale. It should not appear anywhere on this screen, with no footnote
explaining the omission. This is narrower than `store/orders.py:is_terminal_status`'s own
vocabulary. Shipped and Completed orders are terminal too, and they are real revenue. So this
screen folds and compares exactly the one word `Canceled` against the wire's own `status`
string. That mirrors how `is_terminal_status` folds case and edge whitespace before comparing
its own wider set. It is not a second `TERMINAL_STATUSES` copy. It recognizes one word, not a
vocabulary.

See also: D69 (a screen earns a route on its job, not its data source), D86/D103/D105
(kinship of implementation is not kinship of job), D193 (the ledger's own buyer field is
unread here — this screen never draws a name, an address or a payment detail).
