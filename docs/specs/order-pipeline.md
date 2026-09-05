# The order pipeline — steps 8 to 14

**Every number in this file was measured on 2026-08-30 against the owner's real store**, not
carried forward from a plan. Where a fact came from somewhere this session could not check, it
is in section 6 and labelled as such. That split is the point of the file: an earlier draft
transcribed a planning document and re-stated its measurements as though they had been taken,
and two of them had gone stale.

**It is not `docs/specs/order-flow.md`.** That file is search, boxes and the sell path — a card
the owner already knows they sold. This one is an order arriving from outside: how it gets in,
how it becomes a walk to a drawer, how it leaves, and how the tracking number gets back. They
touch at exactly one function, `do_mark_sold`.

---

## STATUS

**Rewritten 2026-08-30, after T1, T2 and T3 landed.** The table below says `built` only where
a human can reach the thing from a screen — `CLAUDE.md`'s rule, and the reason this section was
the last thing edited in that build rather than the first: `make design-check` is the only check
in this repo that can see reachability, and it was green over `#/orders` and `#/shipping` before
a word here moved.

**Reviewed against the tree again on 2026-08-30 and once more on 2026-08-31, and nothing in the
table below changed state either time.** What the pass did change is written where it belongs rather than summarised
here: three sentences that had gone stale inside hours (the cookie, T0's probe, section 8's
"first time"), a store that moved thirty-one sales under section 1, a transcript in section 2
that lost its only `resolved` outcome, one work item that was in the code's header and in no list
here (T2b), and a `T6` that collided with the harness's own.

| step | state |
|---|---|
| 8 order in | **built, two ways, reachable at `#/orders`.** Paste, projected client-side by `app/src/orderPaste.ts`, and a fetch behind the same control — `POST /orders/fetch`, `server/order_transport.py` (T3). **The fetch is two presses since D91**: the window counted by status string, then only the ticked statuses detailed — because the one-press fetch was refused `order_too_many` on every press against this account's 370-order window and had never returned an order. The transport's endpoints, auth kind, body shape and four refusal codes were measured; `search` has run authenticated and returned three real orders, and the summary walk is proven by that refusal. `detail` — the half that carries a buyer's name and address — has not run live. Section 6. |
| 9 resolve | **built and reachable.** `pipeline/orders.py`, drawn by `GET /orders` out of one store snapshot. |
| 10 route | **built and reachable at `#/shipping`.** `pipeline/shipping.py` (D61), on its own surface (T2 below). |
| 11 pull | **built and reachable, in ONE form — the per-copy press.** `POST /orders/pull` writes the ledger and sells in one `Store.write()`, aimed by the row's own `capture_id`, with the undo on a twenty-second receipt. It is pressed a card at a time, from an order's own panel or from the cross-order pass through the drawers (`#/orders`, "Walk the boxes"). **T6's envelope form is deleted, not built** (D96 amended 2026-09-04): main's `POST /orders/fill` and the `#/inventory?order=` walk were reachable from no screen here and are gone, the want they served answered by the walk mode above. |
| 12 ship | **the spreadsheet is reachable; the tcgtracking call still does not exist.** `pipeline/pirateship.py`'s file downloads from `#/shipping`. Nobody has fed it to Pirate Ship. `POST /shipping/batches/<batch>/stamps` fills the three Rubber Stamp columns from the ledger as of 2026-09-05, and NO SCREEN PRESSES IT YET (T2b) — so what an operator downloads today still has them empty. |
| 13 track back | **missing.** |
| 14 tell buyer | **missing.** Deferred behind 13. |

**Step 11 has a SECOND FORM, recorded 2026-08-30 and built 2026-09-02: T6 below.** The owner
wanted an order to drive the inventory walk rather than being pulled from a list, and it does now
— one order or every open order at once, with the write moved from the card to the envelope on his
ruling (D90). It is a different way of doing step 11 and not a fifteenth step, so it gets no row of
its own here, it adds no route, and it takes nothing away from the `built` above: the list pull
still works and is still reachable. T6 is where the want, its three determinations and its costs
are written down, and it now records which of them survived the build.

**`store/orders.py` was the one piece that was wired, and it is now written to by a screen.**
`store/session.py` carries `Ledger` in `Snapshot` and writes it last on every store write.
`inventory/orders.json` did not exist before this session; the re-emit in section 1 created it,
empty, with both of D63's maps. **It has still never held a real order** — nothing below the
paste box has been pressed against one, which is why section 6's last line stands. **It is emptier
than that phrasing suggests**: thirty-one real sales landed in this store on 2026-08-30 and every
one of them went through `#/inventory` rather than through the pull, so the ledger is not merely
unproven, it is being bypassed by the fulfilment that is actually happening. Section 1's
re-measure.

**The three modules that had full harness-T7 coverage and no reachability now have both.**
`pipeline/orders.py` is read by `GET /orders`; `pipeline/shipping.py` and
`pipeline/pirateship.py` are read by `POST /shipping/batches` and its file route. Each has a
route, a client function in `app/src/server.ts`, a control on a screen, and — where it writes —
a receipt and a way back. What has NOT changed is why that paragraph was written: `make harness`
and `make check` were green over all three while none of them could be used, and neither of those
targets can see reachability today either. `app/tests/orders.spec.ts` and
`app/tests/shipping.spec.ts` are what can, and `make design-check` is deliberately off the commit
path.

---

## 1. The store this has to run against

Measured after the re-emit described below, and after the `3/37` stamp that followed it.

| | |
|---|---|
| cards | **715** — 703 identified, 11 sold, 1 retired *(see the re-measure below)* |
| carry a SKU | **217**, across **102 distinct SKUs** |
| stamped by box | 1 → 133/133 · 2 → 45/543 · 3 → **39/39** |
| unstamped | **498**, every one of them in box 2 — 497 identified, 1 retired |
| listing copies | 167 `pushed`, 0 `staged`, 0 `live`, across 117 rows |
| ledger | `inventory/orders.json` present, both maps empty |

**The table above is one snapshot of three, and the store outran it twice inside two days.** It is
left exactly as taken, because it is what section 2's transcripts were run against and rewriting
it would leave those transcripts describing a store no number here reports.

| measured | cards | states | SKU / distinct | box 3 | listings |
|---|---|---|---|---|---|
| 2026-08-30, above | 715 | 703 · 11 · 1 | 217 / 102 | 39/39 | 167 `pushed`, 0 `live`, 117 rows |
| 2026-08-30, later | 715 | 672 · 42 · 1 | 217 / 102 | 39/39 | unchanged |
| **2026-08-31** | **867** | **824 · 42 · 1** | **367 / 159** | **189/191** | **282 `pushed`, 4 `live`, 169 rows** |

States are identified · sold · retired. Between the first two, thirty-one cards were sold. Between
the second and the third, **152 new cards were captured and identified into box 3** and the
listing side moved with them. Box 1 is 133/133 and box 2 is 45/543 throughout; the 497 unstamped
sub-threshold cards in box 2 have not moved at all, and box 3 has picked up 2 unstamped of its own,
so the unstamped total is 500 rather than 498.

**The ledger row is the one that did not move, and that is the finding rather than the footnote.**
Both of D63's maps are still empty across all three snapshots. **Not one of the forty-two sales in
this store went through `POST /orders/pull`** — every one was an `#/inventory` mark-sold press,
which writes card state and never the ledger. Real fulfilment is happening here and it is going
around the order screen. That is the seam T6's determination 2 is about, measured rather than
predicted, and it is why section 6's standing line about a real order is not merely unfinished
bookkeeping.

**The general point is worth more than any of the three rows**, and it governs how this file
should be read: **the store is not a fixture and every measurement taken against it is perishable.**
Three snapshots in two days, two of them a day old before the ink dried. A number here is evidence
of a moment, and a session that finds one stale has found the store moving rather than the file
lying.

### The thirty-one sales, counted out of the history rather than inferred — measured 2026-09-01

**Added 2026-09-05 from the branch that measured it, and it does not replace the table above.**
The three-snapshot table records STATES at three moments; this counts the EVENTS that moved the
store between the first two, out of `inventory/history.jsonl` — which is now
`inventory/legacy-json/history.jsonl`, D88 having moved the store of record into SQLite on
2026-09-01.

At the time of measurement that file held **44 `sold` events**, and **thirty-one of them landed
between 2026-08-31T00:39:05.926Z and 01:07:41.900Z** — 19:39 to 20:07 local, the same half hour in
which the order screen was being committed — across **11 distinct SKUs**, **16 copies out of box 1
and 15 out of box 3**. The per-SKU shape of the batch is 8, 4, 3, 3, 3, 2, 2, 2, 2, 1, 1, and the
largest cluster is eight copies of one SKU inside seven minutes.

**None of them went through `POST /orders/pull`.** A pull writes `ledger.fulfilment` and both of
D63's maps are empty, so this is measured rather than inferred: every one of those thirty-one was
`POST /inventory/<box>/<index>/sold`, D57's one press on `#/inventory`, the path that predates this
pipeline entirely.

**What that is evidence of, and what it is not.** It is measured that the store's real fulfilment
path that evening was the sell button, and that the order screen's ledger is untouched. Reading the
batch's shape as "what fulfilling real multi-copy orders looks like" is an inference this file is
not entitled to make from a store file. **The timing bounds one excuse**: the order screen reached
`main` in PR #64 at 20:06:09 local, so **twenty-six of the thirty-one** were sold while no merged
tree carried it.

**One figure from that measurement is deliberately not carried, and the reason is worth writing
down.** The branch's own table published a `sold by box` row reading `1 → 18 · 3 → 24`, which is a
count of the store's SOLD CARDS at that moment — 42, matching the second snapshot — and not of the
events in the window, which are 16 and 15. The two are different quantities over different
sources and both were right; printed side by side they read as a contradiction. **The card-state
split no longer reproduces at all**: history positions are not stable identities, because D10 lets
a mid-box delete slide every higher index down one, so re-deriving it today from the same file
gives 19 and 24 over 43 distinct positions against a store that reported 42. The window count is
what this file keeps, because it is the one the history can still be made to answer.

### The 497 unstamped cards are not a failure, and reading them as one is the trap

`runs/2026-08-24-box2-01` reports `below $0.40 threshold: 108 SKU(s), 497 copies — disposition
required before output`, and its manifest reads `joined: true` with no emit and no `pricing.json`.
**Every SKU in box 2 is sub-threshold** — $0.04 to $0.09 a card. They carry no SKU because D9 says
they are not to be listed, and **no order will ever arrive for a card that was never listed**. A
screen reporting `sku_unseen` across box 2 is correct, not broken.

What box 2 actually needs is a **disposition decision**, which that run has been waiting on since
2026-08-25. It is the oldest open item in the store and it is not order-pipeline work.

### The backfill, run 2026-08-30, and what it proves

`./pkmnscan emit runs/2026-08-30-box3-01` was re-run against the live store. The report said
*"nothing new to send — every copy this run matched is already at pushed"* and named the reason
for the SKU that mattered: `9189797 — 0 live and 4 on an import this pipeline has not seen land`.
**The identity stamp still happened, and that is the whole distinction** — the D7 cap governs how
many copies are offered for sale, and it has nothing to do with whether a card knows its own SKU.

Diffed against a copy of the store taken immediately before:

    card records changed       4   (3/20, 3/30, 3/36 gained sku + condition; 3/29 restamped)
    listing rows changed       0   (pushed stayed at 4 — the cap held, nothing new was sent)
    states before / after      703 identified, 11 sold, 1 retired — identical
    import CSVs                unchanged
    history lines added        4

**Purely additive, which is D54, and no sold card was resurrected, which is D57's invariant
measured rather than argued.** Before it, an eight-copy order for Rengar, Trophy Hunter resolved
`short` on five picks; after it, `resolved` on eight. **That last clause was true for a few hours
and is not true now** — all eight of that SKU's copies are sold as of the re-measure above, so the
same order resolves `no_copies_on_hand` today. What the backfill proved is unaffected: it is a
statement about the emit being additive, not about the store staying still.

It left box 3 one card short of stamped — `3/37`, sold, which no emit reaches — and a `sold` line
at 20:43 UTC carried a SKU onto that one too. That is why the table above reads 39/39 and why
section 7 has one fewer loose end than it was written with.

---

## 2. What the built modules do when you actually run them

Neither transcript below is a test fixture. Both are the shipped code against real data.

### The resolver, against the live store — 2026-08-30

```
ORDER A2FFC195-B8B497-80225
   Moonfall     sku 9191486 x3  ->  short              3/3
ORDER SECOND-SAME-SKU
   Moonfall     sku 9191486 x1  ->  short              —
ORDER BOX2-PLUS-UNKNOWN
   Rengar       sku 9189797 x2  ->  resolved           3/1, 3/2
   Never seen   sku 0000000 x1  ->  sku_unseen         —
   Vi           sku 9197729 x1  ->  no_copies_on_hand  —
```

**Four of the six reasons fired on real data, and the double-book guard held**: the second order
for the same SKU got no picks at all, because the first took the only copy on hand. That is the
single most important property of `resolve_all` and there is deliberately no `resolve_one`.

**The demo this pipeline was designed around no longer reproduces, and the replacement is
better.** Order `A2FFC195-B8B497-80225` sold 3× Moonfall and the plan advertised it resolving to
`Box 3 · Cards 3, 31, 34, 35`. Three of those four are now `sold`, so the honest answer today is
`short`, one of three. The resolver reporting a shortfall correctly is worth more as evidence
than a pick list that only existed on a particular afternoon.

**AND THE SAME THING HAS SINCE HAPPENED TO THE `resolved` LINE, WHICH IS THE ONE THIS TRANSCRIPT
COULD LEAST AFFORD TO LOSE.** The `BOX2-PLUS-UNKNOWN` row above picks `3/1, 3/2` for Rengar; both
were sold in the thirty-one sales section 1 re-measures, along with the other six copies of that
SKU. Re-run today the row answers `no_copies_on_hand`, and **this transcript no longer holds a
single `resolved` outcome demonstrated against the live store.** That was true of the whole FILE
when it was written; the 2026-09-01 pass below took a second transcript against on-hand stock and
its first line is a `resolved`, so what stands is the narrower claim about this block.
The transcript is kept as taken — it is
dated evidence, and the second time a demonstration here has decayed for the same reason, which is
the point worth carrying: **`resolve_all`'s output is a function of a store that moves under it,
so any transcript of it is perishable by construction.** Three of the four reasons this
transcript demonstrated still reproduce as written; `resolved` is not unreachable — 824 cards are
still `identified` as of the third snapshot, and an order against any SKU with a copy on hand would
produce one — it is only that no order **written down here** produces one any more. What is NOT weakened is the double-book
guard, which is a property of one pass over the open set rather than of which copies happen to be
on hand.

### The resolver again, against the live store — 2026-09-01

**A second transcript, added 2026-09-05 from the branch that took it, and it stands beside the
first rather than replacing it.** It was run against on-hand stock after the sales section 1
counts, which is why it reaches reasons the block above could not.

```
ORDER-ONE
   Xerath, FREED          x2  ->  resolved           4 on hand, 0 sold    1/27, 1/40
   Moonfall               x3  ->  short              1 on hand, 4 sold    3/3
ORDER-TWO
   Xerath, FREED          x3  ->  short              4 on hand, 0 sold    1/100, 1/113
   Moonfall               x1  ->  short              1 on hand, 4 sold    —
ORDER-THREE
   Rengar, Trophy Hunter  x2  ->  no_copies_on_hand  0 on hand, 8 sold    —
   Never seen             x1  ->  sku_unseen         0 on hand, 0 sold    —
   A playmat              x1  ->  not_a_single       0 on hand, 0 sold    —

counts: resolved 1 · short 3 · no_copies_on_hand 1 · sku_unknown 0 · sku_unseen 1 ·
        not_a_single 1
```

**Five of the six reasons fire on real records, and the double-book guard is visible twice in one
pass** — which is the single most important property `resolve_all` has and the reason there is
deliberately no `resolve_one`. ORDER-ONE takes two of the four Xerath copies; ORDER-TWO asks for three,
is handed the remaining two, and is `short` rather than being told it can have four. ORDER-ONE
takes the last Moonfall; ORDER-TWO gets none and is `short` with an empty pick list — **`short`
and not `no_copies_on_hand`, because the copies exist and are spoken for, and `on_hand` beside the
reason is what tells the two apart.**

**`on_hand` is the STORE's count and not the remaining pool, which is why ORDER-TWO reads `4 on
hand` while being handed two.** That is the field doing its job rather than lagging: a `short` with
copies on hand means they are spoken for and the remedy is to wait, and a `short` with none means
they have left and the remedy is to stop looking. A field that counted the unclaimed pool would
make those two read identically at zero. `pipeline/orders.py:_reason` is where the distinction is
made, and its own comment says the same thing.

**`not_a_single` is answered without an inventory lookup at all**, from the line's declared kind —
`_Draw.resolve` returns it before `available()` is ever called, and the comment above that return
says why: an accessory's SKU is not a card's SKU, so asking the inventory about it produces
`sku_unseen`, which reads as "we have lost track of a card" and sends the owner hunting through
boxes for a playmat.

**`sku_unknown` did not fire and could not have, for two independent reasons rather than one.**
The structural half is permanent: `GET /orders` passes no `paperwork=`, and `do_orders`'s docstring
argues why — `cli/resolve.py:paperwork_for` takes ONE run, calls `realign`, and `realign` hashes
every photograph off disk and raises on an ambiguous digest, so one bad run would take the whole
screen render down. The second half is a measurement and is dated to that pass and scoped to what
it covered: on 2026-09-01 `paperwork_for` was run against **both runs that then had a
`pricing.json`** — `2026-08-29-box1-01`, 50 entries, and `2026-08-30-box3-01`, 15 entries, both
realigned clean — and not one SKU either of them named was unknown to the store. That says nothing
about the runs the store has gained since, and it is not a claim that the reason is unreachable in
principle; `do_orders`'s own docstring already puts it correctly, that the zero is a limit of the
route and not a fact about the store.

### The router and the emitter, against the committed fixture

```
shipments: 331
lanes:   {'envelope': 166, 'parcel': 126, 'unjudged': 39}
reasons: {'value_at_threshold': 112, 'non_card_signal': 14, 'cards_only': 166,
          'no_weight_data': 39, 'no_value_data': 0, 'sub_single_weight': 0}
parcel lane: 126 orders
certain:     112 of 331
```

Unchanged from the last measurement, as it should be — the fixture is committed and the router
reads nothing else, so these numbers cannot go stale the way section 1's can.

**`Routing.certain` is 112 and not 292, and it is the split section 5 calls worth surfacing
without ever stating.** 292 orders are JUDGED — they got a lane. 112 of them were answered by a
published price against a published threshold, which is a fact; the other 180 were answered by an
18x weight separation, which is an inference off a catalog constant. The two produce the same lane
without being the same quality of answer, and `Routing.certain` is `reason == VALUE_AT_THRESHOLD`
for exactly that reason. Harness T7 asserts both halves — that the only certain rows are the
`value_at_threshold` ones, and that there are 112 of them out of the 331.

`render()` produced a well-formed Pirate Ship import file — **twelve columns**, being `Name`,
`Address`, `Address Line 2`, `City`, `State`, `Zipcode`, `Country`, `Package Weight`, `Order ID`
and three `Rubber Stamp` columns — 126 rows, CRLF, no BOM, `QUOTE_ALL` on the rows. `Name`
pre-joined on every row, `Order ID` present on every row, `Package Weight` blank on every row, all
three stamp columns empty and waiting for a location. **The >=$50 lane is complete apart from a
screen.**

---

## 3. The work, in order

**The `T0`–`T6` below are work items in this file and NOT the harness's tests.** The two schemes
overlapped the moment T6 was added below on 2026-08-30 — the harness's own T6 is
`harness/tests/t6_geometry.py` and its T7 is `harness/tests/t7_store_and_seams.py`, and both are
cited in this file. Every reference to one of those now says `harness` in front of the number; a
bare `T4` is this section's.

The order below is D66's, and D66 carries the argument. Three claims decide it: a transport-first
session cannot state a Done this repo accepts, the shipping lane depends on neither the screen nor
the transport, and the transport question is one probe rather than one session.

### T0 — free, no code, hours. DISCHARGED, but for box 2's disposition

- ~~**Probe `order-management-api` auth**~~ — **answered 2026-08-30**, and the guess in the
  sentence that stood here was wrong: this host does NOT answer a Bearer challenge. The auth is a
  cookie session, the same `TCGAuthTicket_Production` the admin portal takes, so T3 is a Python
  client and not a browser relay. Measured in the owner's own browser, then confirmed by an
  authenticated `search`. Section 6, and `server/order_transport.py`'s STATUS block.
- **Rule on box 2's disposition** — 108 SKUs, 497 copies, all sub-threshold. Not this pipeline's
  work, but it is the oldest thing in the store waiting on a person.
- ~~Re-emit `runs/2026-08-30-box3-01`~~ — **done 2026-08-30**, section 1.

### T1 — the order screen. The one that unlocks everything. BUILT 2026-08-30 (D69)

The eighth route; `o` is free as a chord, with `c r q p i` taken. Ingest by paste, the order list,
the pick list, all six reasons, and the pull.

**Done:** an order is pasted, walked and pulled end to end, and the ledger holds what was taken.

**Done as it now stands, 2026-08-30.** Route `#/orders`, chord `,o`. `GET /orders` answers the
order list and the resolution out of ONE store snapshot so the two cannot disagree;
`POST /orders/ingest` takes the projection and nothing else; `POST /orders/pull` records the
copies and sells them in one `Store.write()`, and carries its own reversal. Client functions
`getOrders`, `ingestOrders`, `fetchOrders`, `pullCopy` and `undoPull` in `app/src/server.ts`.
The screen is `app/src/Orders.tsx`: the way in (paste and fetch behind one control), the six-way
counts breakdown drawn including its zeros, the open/fulfilled split taken from `open` — the
LEDGER's answer, never the feed's `status` string — every line's reason large with the machine
string beneath it and a remedy where there is one, each pick's place block and its `held_by`, and
a twenty-second receipt carrying the undo.

**Three things it does deliberately.** The pull is aimed by the row's own `capture_id`, so a
mid-box delete or a re-shoot between render and press is refused rather than selling whatever is
at that slot. The receipt reads `places[]` — the labels as they were BEFORE the write — and never
`sales[].card.place.label`, which reads `Box 3 · departed` by the time the answer is composed
(D58). The undo lives on the receipt rather than in the row, because a successful pull makes the
resolver stop offering the copy and the row unmounts.

**What remains unmeasured about it.** Nobody has pasted a real order, so section 6's line stands
unchanged: pasted JSON being a sufficient input is still an argument. `sku_unknown` is
structurally unreachable from this route and always draws a zero — the route passes no
`paperwork=`, and `do_orders`'s docstring says why — so five of the six reasons are all this
screen can ever show. The counts, the spoken-for row, the aim and the receipt are asserted in
`app/tests/orders.spec.ts` against stubbed routes; none of them has met the real server.

**Why first, and not the transport:** the resolver, the labels and the ledger are all built and
demonstrated in section 2, so a screen fed by pasted JSON is a complete product with no network
in it. The transport is then a better source behind a control that already exists. The alternative
ships an ingest route no human can reach, whose Done — *"an order lands in `inventory/orders.json`"*
— is satisfiable without a screen, which is exactly the failure this repo keeps recording.

### T2 — lanes and the Pirate Ship download. BUILT 2026-08-30 (D69)

The lane badge, the abstention drawn as a third answer, and the CSV as a download.

**Done:** a >=$50 order produces a spreadsheet, and the 39 unjudged are visible as unjudged.

**It depends on neither T1's engine nor the transport.** `Shipment` carries no line items and
`to_parcel`'s `stamps` argument defaults to empty. The resolver's only contribution is the
location in `Rubber Stamp`, which is optional by construction. **The limit is the surface, not the
engine**: if the badge and the download draw on T1's screen, two branches revise one file, which
this repo has paid for twice. Sequence them, or give the lane its own surface.

**Taken 2026-08-30: its own surface.** Route `#/shipping`, chord `,s`, `app/src/Shipping.tsx`,
`POST /shipping/batches` with `GET /shipping/batches/<batch>/file` and
`DELETE /shipping/batches/<batch>` beside it. Not sequencing, and the reason is scheduling
first: the order screen was being designed in the same build, so "sequence them" would have put
one finished design in a drawer for a session with nothing else to do.

**The split earns an independent argument besides, and it is the better one.**
`server/shipping_routes.py` opens by saying it is the one module in this server that holds a
buyer's name and street address, and containing that at a FILE boundary is exactly what
`server/tcg_export.py` does for the session cookie: an operator asking "where does the PII go"
reads one file, and a reviewer can check the answer by reading it rather than by tracing a
screen. Folding the lane into the order screen would have put those routes in
`server/capture_server.py` beside forty that hold none, and the boundary would have been a
convention instead of a module. The screen is typed so it cannot draw a buyer — `ShippingRow`
carries no name, no street, no city, no postcode — and those details cross the wire exactly
once, as the CSV download.

### T2b — the rubber stamps. BUILT 2026-09-05, SERVER HALF ONLY

`POST /shipping/batches/<batch>/stamps`. It fills Pirate Ship's three Rubber Stamp columns from
the order ledger, so **the label in the operator's hand IS the pick instruction** — section 2's
transcript notes those three columns rendering empty and waiting for a location, and this is what
fills them. It changed no type and no component: the wire has carried `stamp` on every row and
`stamps` on the batch since the seam was cut, and `app/src/OrdersShipStage.tsx` already draws
both.

**Both stated blockers are spent, and they were spent by other people's work rather than by this
one.** `server/shipping_routes.py`'s header named them: both of D63's maps being empty, and
needing a `store.orders.OrderRecord -> pipeline.orders.Order` adapter "that the order branch also
needs, which is exactly the two-branches-one-file collision D66 told us to avoid." The order
branch landed and the adapter is `server/capture_server.py:_engine_order`, whose own docstring
calls itself THE ONLY ADAPTER, so that collision cannot happen. And the ledger stopped being empty
on 2026-09-02: **twenty real TCGplayer orders with real SKUs, 17 of them since pulled to the end.**

**Done:** a batch whose orders are in the ledger renders with its Rubber Stamp columns filled, and
one whose orders are not renders them empty rather than guessing. Both halves are asserted in
`harness/tests/t7_store_and_seams.py:check_shipping_stamps`, over the same 331-order export in one
store, and each was watched fail under a mutation before it was kept.

**The seam is a callable, and what crosses it is order numbers and strings.** `do_shipping_stamps`
takes a `locate` function and never sees a `Snapshot`, an `Inventory` or a `Ledger`;
`server/capture_server.py:_order_stamps` is what is passed in. That keeps T2's own argument intact
— the module an operator reads to answer "where does the PII go" did not grow a second subject —
and it is forced besides, since `capture_server` imports `shipping_routes` and the reverse is the
cycle `ShippingRefusal` exists for.

#### Three determinations, and the second is the one that will get "fixed"

**A stamp is one position label and it comes from `pipeline/join.py:Position` by way of
`_Places`.** No second formula, per that property's own docstring and the closing prohibition
`server/shipping_routes.py` already carried.

**IT STAMPS WHAT IS STILL OWED, NEVER WHAT HAS ALREADY BEEN PULLED.** The obvious alternative —
stamp every copy of the order at the position the ledger recorded it from — fills far more corners
on the real store, where 17 of 20 orders are fully pulled, and is actively harmful: D90 sells a
copy as it is pulled, a sold card renders `join.departed_label`, and the box closes up behind it
(D58), so that index now holds a DIFFERENT card. Under that mutation the harness draws
`Box 4 · departed · B4 #1` into `Rubber Stamp 1` — a pick instruction to a slot whose occupant has
changed. An order with nothing outstanding has nothing to pick, and empty corners are the true
answer for it.

**ALL THREE CORNERS OR NONE.** An order needing more positions than the label has corners gets
none and is counted unstamped. There is no fourth corner to say "and two more", and a pick list
sliced to fit reads as a complete one — the wrong-shelf failure `pipeline/pirateship.py` refuses to
enforce a stamp LENGTH over, one register up. **Measured on the owner's own ledger, 2026-09-05: 12
of 20 orders hold three copies or fewer; the other 8 hold between 5 and 13.** So this rule leaves
real orders unstamped today, and that is the reopening condition rather than a defect to patch: if
the ratio holds as the store deepens, what changes is the REGISTER — a stop per box in D97's
walk-plan vocabulary rather than a card per corner — and never the refusal to truncate.

**What is NOT built: the client half.** `app/src/server.ts` has no function for this route and
`#/shipping` has no control that presses it, so by CLAUDE.md's own hard rule this is the unfinished
part of one task and not a follow-up. The rendering half already exists — `OrdersShipStage.tsx`
draws `row.stamp` as a pinned line and `batch.stamps.stamped` in its file sentence — so what is
owed is a `shippingStamps(batch)` call and a button beside the download.

### T3 — the transport. BUILT 2026-08-30 (D69)

**Built 2026-08-30 as `server/order_transport.py`, and the probe T0 describes was answered by
measurement in the owner's own logged-in browser rather than by a request from this tree.** The
auth is a cookie session and not a Bearer challenge, so T3 is a Python client and not a browser
relay. `POST /orders/fetch` answers EXACTLY the body `POST /orders/ingest` accepts, which is why
the fetch needed no adapter and enters through the same one door the paste does. What is NOT
established is in section 6.

**The deliverable is that a fetch replaces a paste behind the control T1 already built.** Ingest writes no card state and no listing count, so a replay is a no-op — and
D63 makes that true by construction rather than by a guard, because `store/orders.py` holds no
`Inventory` and imports nothing that can reach one.

**It is two calls, and that is not an optimisation failure.** The search result carries no per-line
SKU; only the order detail does, as `products[].skuId`. The SKU is the join key — `products[].skuId`
is the export's `TCGplayer Id` is `store/master.py:Card.sku` — so an order without it resolves to
nothing at all, and there is no bulk line-item endpoint to ask instead. The module's own header
says the same in the same words.

**One credential legitimately serves two hosts.** `TCGAuthTicket_Production` is set on
`.tcgplayer.com`, so the same `TCGPLAYER_STORE_COOKIE` the export reads reaches the order host as
well — it is the account's session and not one site's. A second env name would be a second thing to
rotate, and half a working tree with no way to tell which half. **What does not transfer is the
body convention**: the admin portal takes Knockout's `model=<json>` form and this host takes a
plain JSON document, so a client carrying D65's shape here fails in a way that reads like an auth
problem.

**403 is `order_seller_key_rejected` and not `order_session_expired`**, because a missing or wrong
`filters.sellerKey` answers 403 rather than 400 — measured. Folding it into "sign in again" sends
the operator off to re-copy a working cookie over a bug in a request body, which is precisely the
defect D65 recorded on the other host. The refusal leads with the body and not the credential.

**The shape a second fetch should take is already in the tree**, landed by D65 after this file was
written. `server/tcg_export.py` is this server's one outbound call: stdlib `urllib`, one host and
one method reachable from it, the secret read at call time and present in no return value, refusal
message or log line, ten named failure codes because "the fetch failed" is three different
problems, and a control on `#/runs` that a person presses. It is **not** the order host — its
cookie session is the admin portal's and does not transfer — so what carries over is the shape and
not the auth.

### T4 — the envelope, and the money gate. NOT BUILT

The tcgtracking call for the sub-$50 lane, under **D33's gate verbatim**: a free preflight, the
count and the premium on screen, an explicit `confirm`, and the spending control **absent** until
the preflight has answered. This is the second route in this repo that can spend money.

**Done:** harness T7 asserts the refusal without `confirm`, and that replaying one order id
creates nothing.

### T5 — closing the loop. NOT BUILT

Tracking read back and emitted as TCGplayer's Import Shipping Info CSV. T2's byte rules already
govern the file, and the order id T2 carries into Pirate Ship is what makes the match possible.

**pkmnscan never writes order status back to TCGplayer** — tcgtracking owns mark-shipped, and two
authors on one shipment is D34's problem twice. The two endpoints that would do it were seen on
the wire and are recorded in `server/order_transport.py`'s WHAT IS DELIBERATELY NOT BUILT block,
quoted here so that adding either reads as a change of policy rather than a change of code:

    POST /orders/status-updates?api-version=2.0            {orderNumbers:[], status:"Shipped"}
    POST /orders/<orderNumber>/tracking?api-version=2.0    {carrier, trackingNumber}

That module cites this section by number for the ruling, and this section quotes the module for
the endpoints, so neither can be read without the other. `not-built endpoints` in
`scripts/docs-audit.py` is what keeps the two lists identical.

### T6 — the order drives the walk, and the pull becomes a mode of the inventory screen. SUPERSEDED 2026-09-04 (D96 amended)

> **SUPERSEDED 2026-09-04, and DELETED rather than left standing (D96, amended).** Everything
> below records what main built and is kept as that record; none of it is in this product's tree.
> The owner used both shapes and ruled for the per-copy walk — *"I don't want the walk picking for
> me"* — so `POST /orders/fill`, `do_order_fill`, `app/src/orderWalk.ts`,
> `app/src/OrderWalkBanner.tsx`/`.css` and harness T7's `check_order_fill` are gone, 1,484 lines,
> reachable from no screen for the day and a half they sat here. **The want at the head of this
> section is still met**, by `app/src/Orders.tsx`'s `buildWalk`/`WalkView` — the "Walk the boxes"
> mode on `#/orders`, written here independently, which sorts the same cross-order pass by the same
> `(box, index)` and leaves the choice of copy to the operator (D93, D97). What survives of the
> envelope idea is one figure: the walk's head says how many open orders are whole beside how many
> cards are left. `_prepare_targets` and `_ledger_pull` also survive — they are `POST /orders/pull`'s
> own two phases and always were.

**Built 2026-09-02, and D90 carries the ruling.** The want is the owner's own and it is unchanged:
*"as orders arrive on TCGPlayer I want them to be matched against PKMNSCAN for SKUs they may hit,
and then I literally want to be able to have all the cards pulled either in one go across all
orders or work order by order with basically an order fulfillment screen showing me one after the
other without me searching for each card"*. An order of 3x card X and 2x card Y now lands the
operator on card X inside `#/inventory`, under its own photograph, and the queue steps to card Y.
Zero attention spent on navigation between drawers, which is the same sentence `CLAUDE.md` opens
with about capture.

**One sentence of the recorded form did not survive, and it is THE ONE THAT MATTERED.** This
section used to read *"the third copy marked sold should advance the screen to card Y on its
own"* — an advance driven by a per-card sale. The owner ruled that out before it was built, and
named the failure the per-card press produces at the drawer: *"i'd rather it be i can't move on
from the envelope until I click a button saying the envelope is filled all items mark sold
something like that, yanno? currently i think my biggest error point might be remembering only
after i've already switched to pulling another card that oh did i even mark the previous card
sold?"* **So the walk writes NOTHING per card.** Stepping the queue is navigation and nothing
else; one press per ORDER records every copy in it; and in order mode the next order is not
offered until that press has happened. **D90 is where the unit of the write is argued**, and it
reopens D69's *"One card, one press, and there is no batch control."* on the owner's word while
leaving `POST /orders/pull` exactly as D69 built it.

**It is a second form of step 11 rather than a fifteenth step, and it was downstream of neither T4
nor T5.** It needed the ledger, the resolver and the walk; all three were already built and
reachable, which is why it could be taken the moment the owner asked. What it replaces is the
*gesture*: the pull was a button on a list of picks, and the operator carried the position in
their head to the drawer.

#### Two modes, because the owner asked for both in one sentence

**Order mode walks one order** — `#/inventory?order=<key>` — and its stops keep the payload's own
order, which is `order_sequence`'s. **Wave mode walks every open order at once** —
`#/inventory?orders=open` — and sorts every stop by `(landing.box, landing.index)`, so the pass
through the drawers runs one direction and a drawer is opened once. Wave mode draws an envelope
list under the banner, one row per open order with its own fill button, which is how *"all the
cards pulled in one go"* stays one walk and still one press per envelope.

**A landing is re-derived on every read rather than stored**, and that is what keeps wave mode
inside determination 1 below. A three-copy line whose first copy was just recorded stands at its
next copy the next time `GET /orders` is read, so the pass through the boxes is a property of the
read rather than a list somebody built. A line the ledger still owes on with no copy `aimable` picks out —
`no_copies_on_hand`, a pooled copy, a record carrying no capture id — is `unfillable`: counted on
the banner, linked to `#/orders`, and never walked to, because the walk may not land on a place
that does not exist.

#### Nearly nothing in it was new machinery, and the one exception is the envelope

| what | where | what it already does |
|---|---|---|
| ~~the handoff~~ **superseded, and D49 is the precedent** | ~~`app/src/runHandoff.ts`~~ → the route's own parameter | the walk is asked for in the URL — `#/inventory?order=<key>` or `#/inventory?orders=open`, read by `app/src/orderWalk.ts:askInHash`. `sessionStorage` would stand a second source of truth, with its own clearing rules, beside a hash that already says what the screen is doing; D49 made exactly this argument for `#/pricing?run=`. It also decides the reload question this section left open |
| the jump | `BoxBrowse`'s `goTo: {key, at}` (D45) | the walk already takes a jump request from OUTSIDE, switching box if it has to, with a counter so one target may be asked for twice |
| its callers | `app/src/Inventory.tsx` `walkTo`, and now the landing effect | `walkTo` is one line fed by a press on a copy's position label; the walk adds one more caller and no second mechanism |
| the arrows | `BoxBrowse`'s existing window `keydown` listener, behind `arrows?: {says, onStep}` | ArrowLeft/Right already step card to card inside the box, and the copies panel already redraws for whichever card is selected. While an order drives, the same two keys step the QUEUE, consulted after the same guards in the same listener — one table, one listener. This is the owner's request verbatim: *"i want that same mechanic on the order walks too"* |
| the address, and the sort | `PickRow.box`/`.index` against `SearchCopy.key` | `"<box>/<index>"` IS `store/master.py`'s position key, so the resolver's picks are ALREADY spelled in the walk's own address space. Wave mode's sort is those same two integers and needs no second address |
| the pick list | `app/src/CardLocations.tsx` | every copy of a SKU, across boxes, each label a walk-to |
| the gesture | D57 | the one-press sale, its twenty-second undo on the row AND on a receipt that outlives the row's unmount |
| the resolution | `GET /orders` | the picks, their `held_by`, and all six reasons out of ONE store snapshot |
| **the envelope — the exception** | `POST /orders/fill`, `server/capture_server.py` | NEW, and the only new server surface here. Every line of one order in one `Store.write()`, two phases, through `_prepare_targets` and `_ledger_pull` lifted out of `do_order_pull` so both doors share one implementation of the aim check. Determination 2 argues it |

#### Three determinations, which are the whole of the design work

**1. The queue is a queue of LINES, not of positions.** D7 puts the three copies of one SKU in
three different boxes, and the obvious reading is that a line therefore has to be exploded into
three queued positions. It does not, and the owner's own question is what settles it: searching a
card on `#/inventory` already shows that SKU across boxes. `do_search` renders a SKU's group
**whole** — every copy, including ones the query did not match — and D45 already makes each of
those position labels one press away. So landing the walk on the LINE puts its whole pick list on
screen for free, and the queue advances per line: three of X, then two of Y, which is the shape
the want was stated in. **A queue of positions would stand a second pick list beside the panel
already drawn**, which is the second-renderer failure section 4 names and this repo has recorded
three times.

**Amended 2026-09-02 by wave mode, and the amendment does not repeal it.** Wave mode orders its
stops by `(landing.box, landing.index)`, which reads like the queue of positions this
determination refused. It is not one, and the test is what gets DRAWN: a stop is still one line,
its whole pick list is still the copies panel that was already on screen, and the sort chooses
which line the walk stands on next rather than exploding a line into entries. Nothing renders a
second list of positions, which is the failure the determination exists to prevent. `stopsOf` in
`app/src/orderWalk.ts` is where both orderings live, and it is one function because the
membership rule is the same in both modes.

**What the copies panel is blind to, and the queue must therefore carry: `held_by`.**
`resolve_all` is a one-pass allocation over the WHOLE open set, and the double-book guard is its
single most important property — section 2's transcript is a second order for one SKU correctly
getting no picks at all. `CardLocations` reads `GET /search`, which knows nothing of the ledger,
so a copy already spoken for by another buyer looks identical to a free one there. The queue
carries the resolver's `picks` and their `held_by` beside the line, and the walk marks a copy that
is spoken for. **This is the one fact the reused panel cannot supply and the only thing the queue
has to add** — `marksOf` is that mapping, and it draws five claims with the highest winning:
`pulled`, `held`, `target`, `pick`, `spoken`.

**2. The sale on the walk has to be the PULL, and this is the seam the feature is really about.**
It is already named in the tree: `do_order_pull`'s undo refuses with *"If it was marked sold on
#/inventory, reverse it there."* `POST /inventory/<box>/<index>/sold` writes card state and **not**
the ledger, so a card sold on the walk while an order is driving it leaves the line uncounted and
the order open forever — the operator would ship a card the ledger still says is owed. While a
queue is running the control brings three guards the plain sale does not have: the aim check
(`capture_id_mismatch` rather than selling whatever sits at that slot after a mid-box delete —
D10 ruling 1, D58), `over_fulfilled` (nothing is clamped, because you cannot ship the fourth), and
`copy_already_pulled`.

**Kept, and it is enforced now rather than asked for: `Mark sold` is not rendered on any row while
an order drives.** The determination was a rule a screen could quietly break, and the screen was
the only thing that could break it, so the mode removes the control instead of documenting it.
`Retire` stays, because a damaged card found at the drawer is not a sale and leaves no line owed.

**What changed is the ROUTE: the control posts `POST /orders/fill` — the whole envelope — and not
`POST /orders/pull`.** The owner's ruling above is the first reason and the mechanical ones agree
with it. `/orders/pull` takes one SKU per call, so an envelope of three lines would be three
writes; a refusal on the second leaves a half-recorded envelope on a shelf somebody is standing
at; and the undo could not reverse it in one press, because that route's undo refuses
`pull_spans_lines`. **One transaction, one refusal, one undo.** Every guard named above survives
the move intact: `_prepare_targets` and `_ledger_pull` were lifted out of `do_order_pull` so the
aim check, the SKU check and the duplicate guard are one implementation behind both doors, phase
one validates every target of every line before anything is written, and a refusal anywhere
aggregates to `fill_entry_refused` naming the line and the position with nothing written.
`ORDER_FILL_TARGET_LIMIT` caps one envelope at 50 positions. Harness T7's `check_order_fill`
covers the route; `/orders/pull` is untouched and still reachable from `#/orders`.

**The undo goes through the same door, and it names what it is reversing.** `undoPull` and
`undoSale` reverse different writes, and a receipt offering the wrong one leaves the ledger
holding a copy the store says is on hand. The envelope's undo is a third: it carries the lines the
screen sent, and the ledger's own `holder_of` must agree with every one of them or the whole undo
refuses `fill_line_mismatch` — a receipt cannot half-reverse an envelope any more than the write
could half-record one. **It is on the receipt ALONE and deliberately not on the rows**, which is
where it parts company with D57's doubled undo: a fill sells every copy it wrote, so a row-level
Undo would reverse an envelope of five copies from the slot of one. D57's receipt already outlives
the row's unmount, which is exactly what this needs — a successful fill makes the resolver stop
offering every copy in it, so all of those rows go at once.

**3. The advance reads the line's `outstanding` off the server and never counts in the client.**
`Orders.tsx` re-reads after every write for this reason and its own header says why — a pull
changes the resolution of every OTHER line that wanted the same SKU. A client-side decrement would
advance past a line the server refused, which is the one failure mode that ends with a buyer short
and nothing on screen saying so.

**Kept, and true twice over now, because the server half was wrong in the same direction.**
`_engine_order` asked the resolver for the BUYER's quantity, so after one of three copies was
pulled it still wanted three, found the two unsold and reported `short`; with five copies in the
store it allocated three picks against a line owed two, taking copies from every other order for
that SKU. It passes `Ledger.outstanding` now, and `pipeline/orders.py:OrderLine` accepts a
quantity of zero — a line already filled — refusing only negatives. On the wire a resolved line
carries `owed` beside `wanted`. The client half is the same rule one register up: the queue is
re-derived from a fresh `GET /orders` after every write, and `cursorAfter` keeps the cursor by
stop id rather than by any count, so a stop that vanished takes the walk to the next one that is
still there.

#### What it costs, named rather than designed away

- **Every advance across boxes discards the mass-select.** A shelf change clears the ticks (D31,
  because the write the selection feeds is box-scoped), and D45 already pays this. What is new is
  that the shelf now changes on an advance the operator did not press rather than on a label they
  did, so a selection on its way to `#/runs` through D39's handoff can vanish without a gesture.
- ~~**`#/inventory` acquires a MODE, and it stays a mode.**~~ **Discharged as designed.** What
  landed is a banner saying which order is driving and a way out of it — `app/src/OrderWalkBanner.tsx`,
  one row that never wraps and never changes height (D28), ending in a quiet `Stop walking`. No
  route and no chord: `App.tsx`'s ROUTE table is untouched, this feature adds no route, and the
  screen count in `CLAUDE.md` and `README.md` does not move. D31's grounds for merging two routes
  away are the grounds this stayed a mode.
- **It is owner-side only**, which is D31's downstream rule rather than an omission.
  `app/src/PositionLabel.tsx`'s header records that the Fulfiller's screens never import it, and
  he has no walk to drive.
- **It is built over an ingest nobody has proved.** Section 6's standing line — that pasted JSON
  is a sufficient input until somebody pastes a real order — is not discharged by this, and a
  queue makes the unproven path longer rather than shorter.

**Done, and this is what was built.** An open order is walked from `#/orders` — `Walk this order`
per row, `Walk every open order` in the header, both plain links to the parameter. Each line lands
under its own photograph and the arrows step the queue. Every copy is aimed by its own
`capture_id`, and **which copies fill the line is picked off the copies panel** — `Take` and
`Don't take` on every unsold copy of the SKU, in any box (D93). One press per order records the
whole envelope — pulled and sold — with its own receipt and a distinct undo label, and the next
order is not offered until it has been pressed. **Reachable at both ends**, which is `CLAUDE.md`'s
route-is-not-a-feature rule: the entry controls on `#/orders`, the banner and its exit on
`#/inventory`.

**`make design-check` WAS where the reachability half was evidenced, and it no longer is** —
`app/tests/order-walk.spec.ts` was deleted with the mode it covered when the Banchi front end
declined D90's envelope walk (D96), so the thirteen cases below describe a screen this product
does not draw. They are left in this paragraph as the record of what the walk WAS proved to do,
in main's history at `71c6dcb`, and not as a claim about what is tested today. What they covered: the parameter
reaching the screen, the landing, the arrows stepping the queue across a box, `Mark sold` absent
from every row, the picker taking a copy in another box without moving the walk, a full line
refusing the take, one press sending one `POST /orders/fill` and zero `/sold`, the receipt
reversing the whole envelope, and the wave. It is the only check in this repo that can see whether
a human can reach a thing, which is why the STATUS table above says `built` on its say-so and why
it is deliberately off the commit path. Harness T7's `check_order_fill` covers the SERVER half and
cannot see a screen. **The paragraph this replaces said the mode was asserted by nothing, and it
was true on the day it was written** — the spec landed with D90's own commit and the sentence was
never struck.

**The choice is box-agnostic, on the owner's ruling of 2026-09-02.** The swap it grew out of was
going to be fenced to the copy under the photograph and never one in another box; the owner:
*"You're giving boxes too much independence."* D7 already says why they have none here — every
unsold copy of a SKU is equally sellable, which is the whole reason the copies panel draws them
across boxes at all.

**AND THE SWAP ITSELF DID NOT SURVIVE THE FIRST WALK (D93, the same day).** It aimed at one copy
at a time, replaced the stop's first target, and — because `SearchCopy` carried no `capture_id` —
could only be pressed on a copy the operator had already walked to. The owner: *"when I have an
order of 2 cards and I have inventory for 3, I basically should be able to pick which two I sell,
instead currently it's like predetermined, and using the `take this one instead` system is not
intuitive."* The panel is the picker now: every copy carries `Take` / `Don't take`, the ink mark
`taking` says what the envelope will record, and the resolver's picks are the DEFAULT rather than
the answer. **A full line refuses the take** — at `2 of 2` the other rows draw the count where
their control would be, because nothing may leave the envelope on a press aimed at something else
— and a take APPENDS, so the walk stands still; dropping the copy it is standing on is what moves
it. This was D90's own third reopening condition, taken.

**What this does not decide.** Nothing whatsoever about postage, which is D61's ruling and
`#/shipping`'s answer, computed from a file this ledger has never seen. **The reload question IS
decided**, and it was the open one this section left: the ask is in the URL, so a reload re-reads
`GET /orders` and lands on the first stop still owed. What a reload does drop is this session's own
choice of copies, because it is the screen's and not the store's, and the resolver's picks stand
in again.

---

## 4. What the order screen holds to, and must keep holding to

**These were T1's requirements and they are invariants over shipped code now.** Each is the kind a
later edit quietly undoes, which is why they are written as things to keep rather than things to
do.

**The label formula is `pipeline/join.py:Position` and there is no second one.** D58 makes drawing
one need the box's whole occupancy, so a formula on this screen is the second-renderer failure
this repo has recorded three times. `server/capture_server.py:_Places` is the walk that feeds it,
one renderer instantiated per request — per request because `Inventory.box_fill` is O(cards) and
an uncached one would walk the store for every row.

**`do_mark_sold` opens its own store session**, so the pull uses the snapshot-taking form
extracted beside it. The undo scans the ledger rather than making the client name the line it is
undoing.

**All six reasons get drawn**, with the machine string small beneath a human label: `resolved`,
`short`, `no_copies_on_hand`, `sku_unknown`, `sku_unseen`, `not_a_single` — **including the ones
that are zero**, which `app/tests/orders.spec.ts` asserts by name in its "all six reasons are
drawn, including the ones that are zero" case. An empty result has several causes with different
remedies, and one blank row for all of them throws away the resolver's best work — section 2 shows
three different empties in a single order.

**PII is projected in the client before the POST**, and unknown keys are refused on the server BY
NAME rather than trimmed — `_reject_unknown` answers `field_not_settable` and lists both what was
sent and what the route accepts. `app/src/orderPaste.ts` is the one place in the app that decides
what leaves the browser about a purchase, and it draws the top-level keys it dropped rather than
dropping them silently; keys inside a LINE are dropped without being listed, and its header says
why. A silent trim would make a broken projection indistinguishable from a working one forever.

**Fulfilment is a count, never a list of positions**, and the one identity it holds is a
`capture_id`. D10 lets a mid-box delete slide every higher index down one, so a position written
down today names a different card tomorrow — D63 measured exactly that.

**The route count is maintained in four places** — `CLAUDE.md`, `README.md`, `docs/map.py`,
`app/src/App.tsx` — and `scripts/views.txt` carries a LINE rather than a number, which is the one a
session looking for a count will not find. **This paragraph used to end by saying nothing checks
it, and that has been false since the route census landed**: `make docs-audit`'s `route census` row
reconciles the published counts in the first three against `App.tsx`'s `ROUTES` table, `route
rosters` does the same for each spec's pinned roster, and both fail a commit. `CLAUDE.md`'s own
warning was rewritten at the same time. The sentence outlived its subject in this file and in the
branch that rewrote this section, which is the failure a count with no reader has: nothing
contradicts it.

---

## 5. What the shipping lane holds to, and must keep holding to

All three are D61's and all three are the kind a screen quietly undoes. **Each one names the code
that enforces it and the test that would catch its removal**, because an invariant with neither is
a sentence.

**The abstention is a third answer and is never defaulted into a lane.** Defaulting the 39 to the
envelope ships a playmat in a stamped mailer; defaulting them to the parcel spends postage nobody
chose. `pipeline/shipping.py:parcel_lane` leaves them out of the download entirely — its own
docstring says an order nobody can place is not swept in to be safe — and
`app/tests/shipping.spec.ts`'s "an unjudged order is not in the parcel file" case asserts it from
the screen's end. `Routing.certain` is the split worth surfacing beside the lane, and it is
**112 of 331**: a published price against a published threshold is a different quality of claim
from an inference off a weight ratio, and section 2 has the derivation.

**No weight is ever derived.** `Product Weight` is a catalog constant that counts the cardboard
and not the mailer, so writing it buys postage for less than the parcel weighs, and the bill
arrives weeks later at the far end. There is no control on the screen that could fill it —
`app/src/OrdersShipStage.tsx`'s header says so in its own words, and the caption on the download
tells the operator the column is blank — and `Package Weight` ships blank on all 126 rows.

**No insurance is ever selected and no label is ever bought.** An insurance-shaped column raises
rather than being dropped, and it raises TWICE OVER: `pipeline/pirateship.py:render` closes the
column set, so an unknown header is a `MalformedParcel`, and a folded deny list stops the
insurance-shaped ones first as `InsuranceRefused` with a message saying insurance is the owner's
per-order choice inside Pirate Ship. The second is not belt and braces — a refusal reading "not a
Pirate Ship column" invites the fix of adding it to the column set, and one naming the reason does
not. `check_no_insurance` runs over the row's own keys on the way out of `render`, so a row that
reached the writer by some other path still has to pass it.

---

## 6. Facts this file did not verify

Recorded so a green harness and a confident table are not mistaken for evidence.

**The tcgtracking API has never been called from this repo.** `TCG_TRACKING_KEY` is in the main
checkout's `.env`; every response shape is documentation-verified. The rate limit, the free tier
and the per-label price are all claims from outside this tree.

**Nobody has fed Pirate Ship the CSV `pipeline/pirateship.py` emits.** Their importer maps columns
on the far side of a seam no committed fixture can hold. This is the same standing as harness
T6's synthetic composites, and it is why `Name` is pre-joined rather than left to their mapper.

**The committed shipping fixture carries no real buyer, so the PII path has never met a real name
and street.** `fixtures/orders-shipping.csv` is 331 rows in which every buyer is `BuyerNNN
Placeholder` at `NNN Example St` — the given name and the house number vary row by row, the
surname `Placeholder` and the city `Springfield` do not, 43 states and 331 distinct postcodes are
spread across it, and 26 rows carry an `Address2`. That is what makes it committable, and it also
means `server/shipping_routes.py` and `pipeline/pirateship.render` have been exercised against
placeholders shaped like addresses and never against a real one. It is the same standing as the
paragraph below about `detail`, one seam later: that one is a real address never arriving, this
one is a real address never leaving.

**An order feed HAS been read, and the half that matters has not.** Amended 2026-08-30, when
T3 landed. What was MEASURED, in the owner's own logged-in browser: the two endpoints, their
methods, the query string and the request bodies; that the auth is a cookie session and not a
Bearer challenge; that `TCGAuthTicket_Production` is scoped to `.tcgplayer.com` and therefore
serves this host and the admin portal alike; that omitting `filters.sellerKey` answers 403 rather
than 400; that `GET /orders` answers 405 because `/orders` is a prefix and not a route; and that
refusals come back as RFC 7807 problem+json. Corroborated against
`tcgtracking-bridge-v2.4.2/background.js`, a third-party extension the owner supplied, which
bridges the same flow through the same two endpoints.

**The session question is CLOSED, 2026-08-30.** The operator ran
`server.order_transport.search(page_size=3)` against the live host and it returned three real
orders. An agent may not read `.env` in this repo — `.claude/settings.json` denies it, and that
was left standing rather than worked around — so the run was theirs. It settles four things at
once: the stored `TCGPLAYER_STORE_COOKIE` DOES authenticate `order-management-api`, so one
credential serves both hosts; `PKMNSCAN_TCG_SELLER_KEY` was accepted; the plain-JSON body was
accepted, so D65's form encoding is the wrong shape here rather than merely a different one; and
the response parsed and projected without raising.

**`detail` remains unexercised against the live host**, and it is the half that carries a buyer's
name and address. `products[].skuId` was read in the BROWSER and never through this module, so the
PII projection is proven against fixtures and against nothing that came off the wire.

**`fetch_open_orders` was named here as unexercised until 2026-09-05 and it had run on 2026-09-02**
— the owner pressed Fetch, the search pages walked far enough to count 370 orders in
`LastThreeMonths`, and it was refused `order_too_many`. The paging is proven live and that refusal
is the one D91 answers. This sentence disagreed with the module it points at as the primary record,
which is the drift the `transport standing` audit row now catches.

`server/order_transport.py`'s own STATUS block is the primary record and says this at greater length.

**It is also still true that the search result carries no per-line SKU** — only the order detail
does, as `products[].skuId` — which is why the transport is two calls and not one. That is
measured now rather than carried from a planning session.

**The browser extension `tcgtracking-bridge-v2.4.2` is READ MATERIAL AND NOT A COMPONENT, AND IT
IS NOT IN THIS REPOSITORY.** It was supplied by the owner and read during T3's design; it has
never been committed, is in no worktree, and is not on disk beside this checkout — so the bare
path `tcgtracking-bridge-v2.4.2/` written here and at `server/order_transport.py:50` names
nothing a reader can open, and is kept only to say what was corroborated against what. `make
check` never sees it, `docs/map.py` does not map it, the git hooks do not guard it, and nothing
in this repo calls it or depends on it.

**Postage economics and account state** — the letter rate, the insurance premium, the seller
level — are external facts carried from the planning session. They decided the lanes and none of
them is checkable from here. **The volume is measured now**: this paragraph carried a
347-orders-in-90-days figure from the same session, and on 2026-09-02 the fetch itself counted
**370 orders in `LastThreeMonths`** on the owner's account — the refusal that opened D91. It is
the first number this repo has about the order feed's size that came off the wire.

**That pasted JSON is a sufficient input for T1** is an argument, not a measurement, until
somebody pastes one. **It is still an argument as of 2026-08-30, with T1 built and reachable**,
and the screen shipping is not what settles it: `app/tests/orders.spec.ts` drives the paste
against a stubbed `POST /orders/ingest`, which proves the projection and proves nothing about
whether a real marketplace's JSON survives it. **This line may be struck only by a session
holding a transcript of a real order pasted, walked and pulled** — the same standing the two
paragraphs above it have.

**It is STILL an argument as of 2026-09-02, with T6 built as well, and the walk shipping settles
it no more than the screen did.** What T6 changes is that the strike now has an exact
measurement attached to it rather than a description: **the first real envelope filled through the
walk** — a real order in the ledger however it got there, its lines standing at real drawers,
`POST /orders/fill` answering `complete`, and `inventory/orders.json` holding it afterwards. That
single transcript discharges this paragraph and section 8's `A real order pulled end to end`
bullet together, because it is the one event that exercises the ingest, the resolver, the aim
check and the ledger in a single pass. It says nothing about `detail`, which is the transport's
own unproven half two paragraphs up and is not reached by a paste. Until that transcript exists,
every path below the paste box is proven against fixtures and against a store whose forty-two
sales all went around it — section 1's re-measure, which is the reason this line has never been
close to being struck.

---

## 7. Loose ends found in the store

- ~~**`3/37` is sold and carries no SKU.**~~ **Closed 2026-08-30**, and not by a re-emit — emit
  walks `uncommitted_positions` and a sold copy is not among them, so that reasoning held and the
  stamp came from the sale itself. **No sold card in the store now lacks a SKU**, so the stamping
  defect left no residue.
- **`3/13` is sold with an empty `name`.** SKU and number are present, so it resolves; only what a
  screen would draw is wrong.
- **Twelve SKUs had no copies on hand at all, measured 2026-09-01**, with three more partly sold
  out. It is dated because it is a count over a store that moves: it is why
  `no_copies_on_hand` was demonstrable on real records in section 2's second transcript and why
  the resolver's old success example was not, and it is not a claim about what the store holds
  today.
- ~~**Nothing is `live`.**~~ **No longer true as of 2026-08-31**, and it changed without anything
  in this pipeline touching it: the store now holds **4 `live` copies across two SKUs** (`9189317`
  ×3, `9199579` ×1) against 282 `pushed` over 169 rows. The observation is kept because the
  reasoning attached to it was wrong in a way worth naming — a screen drawing a live count was
  said to draw zero, and one drawing it today does not. **What the earlier observation got right
  is the mechanism, and it is worth keeping out of the strike**: the thirty-one sales of section 1
  moved the live count by nothing at all, because a sale is a card state and the listing counts
  are D59's per-SKU quantities. The two move for different reasons and a reader expecting one to
  follow the other will misread both. `store/master.py`'s comments describe the earlier state.

---

## 8. What would reopen this

**Line items arriving**, which retire D61's weight cut rather than re-fitting it —
`pipeline/orders.py` already answers the same question correctly from declared line kinds.

~~**The probe answering Bearer**~~ — **it answered the other way, 2026-08-30**, and section 3's T0
records it: the auth is a cookie session, the same `TCGAuthTicket_Production` the admin portal
takes, so T3 is a Python client and not a browser relay. The bullet is struck rather than deleted
because it was a real reopening condition that fired and was discharged, and this file annotates
where it can rather than removing the reasoning. What would reopen the question now is the
opposite event — the cookie ceasing to authenticate `order-management-api`, which is one host
policy change away and would put the browser relay back on the table.

**tcgtracking answering a real call**, which unblocks T4 and is the only remaining thing in this
file that would cost money. Section 6's first paragraph is what it would discharge: the API has
never been called from this repo and every response shape in it is documentation-verified, so the
rate limit, the free tier and the per-label price are all still claims from outside this tree.

**A real order pulled end to end**, which is the first thing here that would replace an argument
with a measurement. **T1 being built does not do it** — the screen is the thing that makes it
possible to try, and section 6's last paragraph says what a session would have to hold to strike
the line.

~~**The stored cookie reaching `order-management-api` for the first time**~~ — **happened
2026-08-30**, and it reopened nothing: `search` returned three real orders under the cookie
already in `.env`, which is what closed the session question in section 6. What is left of that
bullet is **`detail` running against the live host**, still one press away rather than one build
away, and still the half that would first put a buyer's name and address through
`project_order` outside a fixture.

~~**The intake meeting `order_too_many` on the real account**~~ — **happened, and was the first
thing the owner said about the fetch**: 370 orders in `LastThreeMonths` against a cap of 100,
refused on every press, with a remedy the range vocabulary could not express. D91 answers it: the
summaries are walked whole and counted by status string, the operator ticks the statuses to
detail, and the cap counts detail calls rather than the window. What is left of this bullet is
the same thing the one above leaves — `detail` has still not run against the live host, and the
first filtered fetch is when it does.

**Two devices filling at once**, which is the envelope's own reopener and is unanswered by
design rather than by oversight. The WRITE is safe and needs nothing: phase one re-validates
every target against the store inside the same `Store.write()` that phase two writes in, D88
makes that one transaction, and a copy the other device already took refuses
`copy_already_pulled` or `capture_id_mismatch` — aggregated to `fill_entry_refused` with nothing
written. **What is undecided is what the loser should then see.** The refusal is all-or-nothing
over the whole envelope by construction, so one contested copy refuses four uncontested lines
with it, and there is no ruling on whether the answer is a re-read and a second press or a
partial fill somebody has to reconcile. The plain sale settled its own version of this and the
envelope has no equivalent: `docs/specs/order-flow.md` §8.1 rules that a second device's
`already_sold` is *"a receipt for a card leaving your list rather than an error"*. The undo has
the same shape one step later — a fill reversed after another device has moved the same copies
refuses `fill_line_mismatch`, correctly, and again with nothing said about what to do next.
**Nothing reopens until two people actually pull at once**, which has not happened, in a store
where no envelope has been filled at all.
