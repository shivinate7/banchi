# The order pipeline — steps 8 to 14

**Every number in this file was re-measured on 2026-08-30 against the owner's real store**,
after the order screen, the shipping lane and the transport landed. Where a fact came from
somewhere this session could not check, it is in section 6 and labelled as such. That split is
the point of the file: an earlier draft transcribed a planning document and re-stated its
measurements as though they had been taken, and two of them had gone stale.

**The store moved under this document between one measurement and the next, which is the
strongest argument the split has.** Section 1 records what changed and section 2 records what
it did to the answers.

**It is not `docs/specs/order-flow.md`.** That file is search, boxes and the sell path — a card
the owner already knows they sold. This one is an order arriving from outside: how it gets in,
how it becomes a walk to a drawer, how it leaves, and how the tracking number gets back. They
touch at exactly one function, `do_mark_sold` — and section 1 records the day the owner used
that function thirty-one times while this pipeline watched.

---

## STATUS

**Steps 8 through 11 are BUILT AND REACHABLE. Step 12 is half of each. Steps 13 and 14 do not
exist.** The table says `built` only where a human can reach the thing from a screen —
`CLAUDE.md`'s rule, and the reason this section is written last rather than first: `make
design-check` is the only check in this repo that can see reachability, and it is green over
`#/orders` and `#/shipping` at **275 passed, exit 0** as of this rewrite.

| step | state |
|---|---|
| 8 order in | **built, two ways, reachable at `#/orders`.** Paste, projected client-side by `app/src/orderPaste.ts`, and a fetch behind the same control — `POST /orders/fetch`, `server/order_transport.py`. The transport's endpoints, auth kind, body shape and refusal codes were measured, and `search` has run authenticated against the live host. Section 6 says which half has not. |
| 9 resolve | **built and reachable.** `pipeline/orders.py`, drawn by `GET /orders` out of one store snapshot. Five of its six reasons fire on today's real data — section 2. |
| 10 route | **built and reachable at `#/shipping`.** `pipeline/shipping.py` (D61), on a surface of its own (D69). |
| 11 pull | **built and reachable.** `POST /orders/pull` writes the ledger and sells in one `Store.write()`, aimed by the row's own `capture_id`, with the undo on a twenty-second receipt. **Never yet pressed** — the ledger is empty. |
| 12 ship | **the spreadsheet is reachable; the tcgtracking call does not exist.** `pipeline/pirateship.py`'s file downloads from `#/shipping`. Nobody has fed it to Pirate Ship. |
| 13 track back | **missing.** T5 below. |
| 14 tell buyer | **missing.** Deferred behind 13. |

**The whole chain exists in code and has never carried one real order end to end.**
`inventory/orders.json` is present with both of D63's maps and both are empty. Every claim
about the screens below rests on `app/tests/orders.spec.ts` (7 cases) and
`app/tests/shipping.spec.ts` (9 cases) against stubbed routes, plus T7's 1579 checks — and on
nothing that came off a marketplace.

**Reachability is settled and stays settled by three artifacts, none of which is on the commit
path.** `pipeline/orders.py` is read by `GET /orders`; `pipeline/shipping.py` and
`pipeline/pirateship.py` by `POST /shipping/batches` and its file route. Each has a route, a
client function in `app/src/server.ts`, a control on a screen, and — where it writes — a
receipt and a way back. What has not changed is why that paragraph exists: `make harness` and
`make check` were green over all three while none could be used, and neither target can see
reachability today either.

---

## 1. The store this runs against, and the thirty-one sales that moved it

Measured 2026-08-30, after the sale session described below.

| | |
|---|---|
| cards | **715** — 672 identified, **42 sold**, 1 retired |
| carry a SKU | **217**, across **102 distinct SKUs** |
| stamped by box | 1 → 133/133 · 2 → 45/543 · 3 → **39/39** |
| unstamped | **498**, every one in box 2 — 497 identified, 1 retired |
| sold by box | 1 → 18 · 3 → 24 · box 2 → none |
| SKUs with nothing on hand | **12** fully sold out; 3 more partly |
| listing copies | 167 `pushed`, 0 `staged`, 0 `live`, across 117 rows |
| ledger | `inventory/orders.json` present, **both maps empty** |

### Thirty-one copies were sold in twenty-eight minutes, and the order pipeline recorded none of it

`inventory/history.jsonl` holds 44 `sold` events. **Thirty-one of them landed between
2026-08-31T00:39:05Z and 01:07:41Z** — 19:39 to 20:07 local, the same half hour in which the
order screen was being committed — across **11 distinct SKUs**, 16 copies out of box 1 and 15
out of box 3. The largest cluster is eight copies of one SKU in seven minutes.

**None of them went through `POST /orders/pull`.** A pull writes `ledger.fulfilment`, and the
ledger is empty, so this is not an inference: every one of those thirty-one was
`POST /inventory/<box>/<index>/sold` — D57's one press on `#/inventory`, the path that
predates this pipeline entirely.

**What that is evidence of, and what it is not.** It is measured that the store's real
fulfilment path on 2026-08-30 was the sell button, and that the order screen's ledger is
untouched. The shape of the batch — 8, 4, 3, 3, 3, 2, 2, 2, 2, 1, 1 copies per SKU in one sitting
— is what fulfilling real multi-copy orders looks like, and reading it that way is an
inference this file is not entitled to make from a store file. **The timing bounds one
excuse**: the order screen reached `main` at 20:06:09 local, so twenty-six of the thirty-one
sales happened while no merged tree carried it.

The consequence is in section 2 and it is not small: the resolver's demonstration data
changed under it, and one of the two orders the plan was designed around now resolves to
nothing at all.

### The 497 unstamped cards are not a failure, and reading them as one is the trap

`runs/2026-08-24-box2-01` reports `below $0.40 threshold: 108 SKU(s), 497 copies — disposition
required before output`, and its manifest reads `joined: true` with no emit and no
`pricing.json`. **Every SKU in box 2 is sub-threshold** — $0.04 to $0.09 a card. They carry no
SKU because D9 says they are not to be listed, and **no order will ever arrive for a card that
was never listed**. A screen reporting `sku_unseen` across box 2 is correct, not broken. It is
also why box 2 contributes nothing to the sold column above.

What box 2 actually needs is a **disposition decision**, which that run has been waiting on
since 2026-08-25. It is the oldest open item in the store and it is not order-pipeline work.

### The backfill of 2026-08-30, kept because it is evidence about a run

`./pkmnscan emit runs/2026-08-30-box3-01` was re-run against the live store. The report said
*"nothing new to send — every copy this run matched is already at pushed"* and named the reason
for the SKU that mattered: `9189797 — 0 live and 4 on an import this pipeline has not seen
land`. **The identity stamp still happened, and that is the whole distinction** — the D7 cap
governs how many copies are offered for sale, and it has nothing to do with whether a card
knows its own SKU.

Diffed against a copy of the store taken immediately before:

    card records changed       4   (3/20, 3/30, 3/36 gained sku + condition; 3/29 restamped)
    listing rows changed       0   (pushed stayed at 4 — the cap held, nothing new was sent)
    states before / after      703 identified, 11 sold, 1 retired — identical
    import CSVs                unchanged
    history lines added        4

**Purely additive, which is D54, and no sold card was resurrected, which is D57's invariant
measured rather than argued.** Before it, an eight-copy order for Rengar, Trophy Hunter
resolved `short` on five picks; after it, `resolved` on eight. **All eight of those copies were
sold by hand four hours later**, which is section 2's first line.

Those state counts are what the store held at 20:07 local and are never rewritten. The table
at the top of this section is what it holds now.

---

## 2. What the built modules do when you actually run them

Neither transcript below is a test fixture. Both are the shipped code against real data, re-run
for this rewrite.

### The resolver, against the live store — five of six reasons on real records

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

**The double-book guard is visible twice in one pass, which is the single most important
property `resolve_all` has and the reason there is deliberately no `resolve_one`.** ORDER-ONE
takes two of the four Xeraths; ORDER-TWO asks for three, is handed the remaining two, and is
`short` rather than being told it can have four. ORDER-ONE takes the last Moonfall; ORDER-TWO
gets none and is `short` with an empty pick list — **`short` and not `no_copies_on_hand`,
because the copies exist and are spoken for, and `on_hand` beside the reason is what tells the
two apart.**

**`on_hand` is the STORE's count and not the remaining pool, which is why ORDER-TWO reads
`4 on hand` while being handed two.** That is the field doing its job rather than lagging: a
`short` with copies on hand means they are spoken for and the remedy is to wait, and a `short`
with none means they have left and the remedy is to stop looking. A field that counted the
unclaimed pool would make those two read identically at zero.

**`not_a_single` is answered without a lookup at all**, from the line's declared kind, so an
order carrying a playmat never sends anybody hunting through boxes for it.

**`sku_unknown` did not fire and could not have**, for two independent reasons now rather than
one. `GET /orders` passes no `paperwork=` — `do_orders`'s docstring argues why, and it is that
`cli/resolve.py:paperwork_for` hashes every photograph off disk and raises on an ambiguous
digest, so one bad run would take the whole screen down. **And it would draw a zero anyway**:
`paperwork_for` was run for this rewrite against both runs that have a `pricing.json`
(`2026-08-29-box1-01`, 50 entries; `2026-08-30-box3-01`, 15 entries), both realigned clean, and
**not one SKU either of them names is unknown to the store**. That zero is a limit of the route
*and* a fact about today's data, and it was only the first of those before this measurement.

**The demo this pipeline was designed around is gone twice over, and the replacement is
better each time.** Order `A2FFC195-B8B497-80225` sold 3× Moonfall and the plan advertised it
resolving to `Box 3 · Cards 3, 31, 34, 35`; three of those four were sold by 2026-08-30 and it
became `short`. Rengar then replaced it as the file's `resolved` example, and all eight Rengars
were sold that evening — so the SKU that demonstrated success now demonstrates
`no_copies_on_hand`. **A resolver reporting a shortfall correctly is worth more as evidence
than a pick list that only existed on a particular afternoon**, and this file has now been
taught that twice.

### The router and the emitter, against the committed fixture

```
shipments: 331
lanes:   {'envelope': 166, 'parcel': 126, 'unjudged': 39}
reasons: {'value_at_threshold': 112, 'non_card_signal': 14, 'cards_only': 166,
          'no_weight_data': 39, 'no_value_data': 0, 'sub_single_weight': 0}
parcel lane: 126 orders
certain:    112 of 331
```

Unchanged from the last measurement, as it should be — the fixture is committed and the router
reads nothing else. **`Routing.certain` is 112 and not 292**: a published price against a
published threshold is a different quality of claim from an 18x weight separation, and the two
produce the same lane without being the same answer.

`render()` produced a well-formed Pirate Ship import file: **twelve columns** — `Name`,
`Address`, `Address Line 2`, `City`, `State`, `Zipcode`, `Country`, `Package Weight`,
`Order ID` and three `Rubber Stamp` columns — 126 rows, CRLF, no BOM, `QUOTE_ALL` on the rows.
`Name` pre-joined on every row, `Order ID` present on every row, `Package Weight` blank on
every row, all three stamp columns empty and waiting for a location. **The >=$50 lane is
complete apart from an upload.**

**This file said "ten columns" until this rewrite and it was simply wrong** — recorded rather
than quietly fixed, because it is the one number here nobody would have caught by reading.

---

## 3. The work, in order — three discharged, two open

The order is D66's and D66 carries the argument. Three claims decided it: a transport-first
session cannot state a Done this repo accepts, the shipping lane depends on neither the screen
nor the transport, and the transport question is one probe rather than one session. **All three
held.**

### T0 — free, no code, hours. DISCHARGED

- ~~**Probe `order-management-api` auth**~~ — **answered 2026-08-30, and the answer reversed
  this file.** It is a cookie session and not a Bearer challenge, so T3 is a Python client and
  not a browser relay. The measurement was taken in the owner's own logged-in browser; the
  original claim, that this host answers a Bearer challenge, was recorded in four places and
  all four are amended in place (D69).
- **Rule on box 2's disposition** — 108 SKUs, 497 copies, all sub-threshold. **STILL OPEN.**
  Not this pipeline's work, but it is the oldest thing in the store waiting on a person.
- ~~Re-emit `runs/2026-08-30-box3-01`~~ — **done 2026-08-30**, section 1.

### T1 — the order screen. BUILT 2026-08-30 (D69)

Route `#/orders`, chord `,o`. `GET /orders` answers the order list and the
resolution out of ONE store snapshot so the two cannot disagree; `POST /orders/ingest` takes
the projection and nothing else; `POST /orders/pull` records the copies and sells them in one
`Store.write()`, and carries its own reversal. Client functions `getOrders`, `ingestOrders`,
`fetchOrders`, `pullCopy` and `undoPull` in `app/src/server.ts`.

`app/src/Orders.tsx` draws: the way in (paste and fetch behind one control that never moves),
the six-way counts breakdown **including its zeros**, the open/fulfilled split taken from
`open` — the LEDGER's answer, never the feed's `status` string — every line's reason large with
the machine string beneath it and a remedy where there is one, each pick's place block and its
`held_by`, and a twenty-second receipt carrying the undo.

**Three things it does deliberately.** The pull is aimed by the row's own `capture_id`, so a
mid-box delete or a re-shoot between render and press is refused rather than selling whatever
is at that slot. The receipt reads `places[]` — the labels as they were BEFORE the write — and
never `sales[].card.place.label`, which reads `Box 3 · departed` by the time the answer is
composed (D58). The undo lives on the receipt rather than in the row, because a successful pull
makes the resolver stop offering the copy and the row unmounts.

**What remains unmeasured about it, and section 1 made the gap wider rather than narrower.**
Nobody has pasted a real order, nobody has pressed the pull, and on the evening the screen
landed the owner sold thirty-one copies through `#/inventory` instead. Section 6's last
paragraph says what a session would have to hold to strike that line. `sku_unknown` is
structurally unreachable from this route and always draws a zero, so five of the six reasons
are all this screen can ever show.

### T2 — lanes and the Pirate Ship download. BUILT 2026-08-30 (D69)

Route `#/shipping`, chord `,s`, `app/src/Shipping.tsx`, `POST /shipping/batches` with
`GET /shipping/batches/<batch>/file` and `DELETE /shipping/batches/<batch>` beside it.

**It got its own surface rather than being sequenced behind T1**, which is the second of the
two options D66 offered. The scheduling reason came first — the order screen was being designed
in the same build, so "sequence them" would have put one finished design in a drawer — **but
the independent argument is the better one and is what keeps the split.**
`server/shipping_routes.py` opens by saying it is the one module in this server that holds a
buyer's name and street address, and containing that at a FILE boundary is exactly what
`server/tcg_export.py` does for the session cookie: an operator asking "where does the PII go"
reads one file, and a reviewer can check the answer by reading it rather than by tracing a
screen. Folding the lane into the order screen would have put those routes in
`server/capture_server.py` beside every other route this server serves, not one of which holds
a buyer, and the boundary would have been a convention instead of a module.

The screen is typed so it cannot draw a buyer — `ShippingRow` carries no name, no street, no
city, no postcode — and those details cross the wire exactly once, as the CSV download. The
batch table lives in this process's memory, holds at most four exports, expires at 1800
seconds, and touches no disk; T7 asserts that reading a 331-order export and downloading its
import file wrote not one file into the store.

**Not built here, and named rather than left to be discovered**:
`POST /shipping/batches/<batch>/stamps`, which would fill Pirate Ship's three Rubber Stamp
columns from the order ledger so the label in the operator's hand IS the pick instruction. The
wire already carries `stamp` on every row and `stamps` on the batch as nulls, so it changes no
type and no component when it lands. It waits on the ledger holding something.

### T3 — the transport. BUILT 2026-08-30 (D69)

`server/order_transport.py`. `POST /orders/fetch` answers EXACTLY the body
`POST /orders/ingest` accepts, which is why the fetch needed no adapter and enters through the
same one door the paste does. Ingest writes no card state and no listing count, so a replay is
a no-op — and D63 makes that true by construction rather than by a guard, because
`store/orders.py` holds no `Inventory` and imports nothing that can reach one.

**It is two calls and that is not an optimization failure.** The search result carries no
per-line SKU; only the order detail does, as `products[].skuId`, which is the export's
`TCGplayer Id` is `store/master.py:Card.sku`. There is no bulk line-item endpoint.

**One credential serves two hosts.** `TCGAuthTicket_Production` is set on `.tcgplayer.com`, so
the same `TCGPLAYER_STORE_COOKIE` the export uses reaches the order host — a second env name
would be a second thing to rotate and half a working tree with no way to tell which half.
**What does not transfer is the body convention**: the admin portal takes Knockout's
`model=<json>` form and this host takes a plain JSON document, and a client carrying D65's
shape here fails in a way that reads like an auth problem. **403 is `order_seller_key_rejected`
and not `order_session_expired`**, because a missing `filters.sellerKey` answers 403 —
measured — and folding it into "sign in again" sends the operator to re-copy a working cookie
over a bug in a request body, which is precisely the defect D65 recorded on the other host.

`search` has run authenticated and returned three real orders. `detail` and `fetch_open_orders`
have not — section 6.

### T4 — the envelope, and the money gate. NOT BUILT

The tcgtracking call for the sub-$50 lane, under **D33's gate verbatim**: a free preflight, the
count and the premium on screen, an explicit `confirm`, and the spending control **absent**
until the preflight has answered. **This would be the second route in this repo that can spend
money**, and `POST /pipeline/identify` is still the only one.

**Done:** T7 asserts the refusal without `confirm`, and that replaying one order id creates
nothing.

**What it is blocked on is nothing in this tree.** The API has never been called from here and
every response shape is documentation-verified — section 6. The 166 envelope-lane orders in the
fixture are what it would be for.

### T5 — closing the loop. NOT BUILT

Tracking read back and emitted as TCGplayer's Import Shipping Info CSV. T2's byte rules already
govern the file, and the `Order ID` T2 carries into Pirate Ship — present on all 126 parcel
rows, measured — is what makes the match possible.

**pkmnscan never writes order status back to TCGplayer.** tcgtracking owns mark-shipped, and
two authors on one shipment is D34's problem twice. The two endpoints that would do it were
seen on the wire and are recorded in `server/order_transport.py`'s "deliberately not built"
block precisely so that adding them is visibly a change of policy rather than a change of code:

    POST /orders/status-updates?api-version=2.0            {orderNumbers:[], status:"Shipped"}
    POST /orders/<orderNumber>/tracking?api-version=2.0    {carrier, trackingNumber}

---

## 4. What the order screen holds to, and must keep holding to

These were T1's requirements and they are now invariants over shipped code. Each is the kind a
later edit quietly undoes.

**The label formula is `pipeline/join.py:Position` and there is no second one.** D58 makes
drawing one need the box's whole occupancy, so a formula on this screen would be the
second-renderer failure this repo has recorded three times. `server/capture_server.py:_Places`
is the walk that feeds it, cached per request.

**`do_mark_sold` opens its own store session**, so the pull uses the snapshot-taking form
extracted beside it. The undo scans the ledger rather than making the client name the line it
is undoing.

**All six reasons get drawn**, with the machine string small beneath a human label: `resolved`,
`short`, `no_copies_on_hand`, `sku_unknown`, `sku_unseen`, `not_a_single` — **including the
ones that are zero**, which `app/tests/orders.spec.ts` asserts by name. An empty result has
several causes with different remedies, and one blank row for all of them throws away the
resolver's best work: section 2 shows three different empties in a single order.

**PII is projected in the client before the POST**, and unknown keys are refused on the server
BY NAME rather than trimmed. `app/src/orderPaste.ts` is the one place in the app that decides
what leaves the browser about a purchase, and it draws what it dropped. A silent trim would
make a broken projection indistinguishable from a working one forever.

**Fulfilment is a count, never a list of positions**, and the one identity it holds is a
`capture_id`. D10 lets a mid-box delete slide every higher index down one, so a position
written down today names a different card tomorrow.

**The route count is maintained in four places** — `CLAUDE.md`, `README.md`, `docs/map.py`,
`app/src/App.tsx` — and `scripts/views.txt` carries a LINE rather than a number, which is the
one a session looking for a count will not find. `CLAUDE.md` warns in its own words that this
count has been wrong more often than right and that nothing checks it.

---

## 5. What the shipping lane holds to, and must keep holding to

All three are D61's and all three are the kind a screen quietly undoes.

**The abstention is a third answer and is never defaulted into a lane.** Defaulting the 39 to
the envelope ships a playmat in a stamped mailer; defaulting them to the parcel spends postage
nobody chose. `parcel_lane` leaves them out of the download entirely, and
`app/tests/shipping.spec.ts` asserts that an unjudged order is not in the parcel file.
`Routing.certain` is the split worth surfacing beside the lane — 112 of 331.

**No weight is ever derived.** `Product Weight` is a catalog constant that counts the cardboard
and not the mailer, so writing it buys postage for less than the parcel weighs, and the bill
arrives weeks later at the far end. There is no control on the screen that could fill it and
`Package Weight` ships blank on all 126 rows.

**No insurance is ever selected and no label is ever bought.** An insurance-shaped column
raises rather than being dropped, and it raises TWICE OVER: `render`'s closed column set stops
it as `MalformedParcel`, and a folded deny list stops it first as `InsuranceRefused` with a
message saying insurance is the owner's per-order choice inside Pirate Ship. The second is not
belt and braces — a refusal reading "not a Pirate Ship column" invites the fix of adding it to
the column set, and one naming the reason does not. `check_no_insurance` runs over the row's own
keys on the way out of `render`, so a row that reached the writer by some other path still has
to pass it.

---

## 6. Facts this file did not verify

Recorded so a green harness and a confident table are not mistaken for evidence.

**The tcgtracking API has never been called from this repo.** `TCG_TRACKING_KEY` is in the main
checkout's `.env`; every response shape is documentation-verified. The rate limit, the free tier
and the per-label price are all claims from outside this tree. This is what T4 is blocked on.

**Nobody has fed Pirate Ship the CSV `pipeline/pirateship.py` emits.** Their importer maps
columns on the far side of a seam no committed fixture can hold. This is the same standing as
T6's synthetic composites, and it is why `Name` is pre-joined rather than left to their mapper.

**The committed shipping fixture carries no real buyer.** `fixtures/orders-shipping.csv` is 331
rows of `Buyer001 Placeholder` at `101 Example St` — which is what makes it committable, and
also means the PII path through `shipping_routes.py` and `pirateship.render` has been exercised
against placeholders and never against a real name and street.

**The order feed's search call is proven and the detail call is not.** `search` ran
authenticated on 2026-08-30 and returned three real orders. The operator ran it — an agent may
not read `.env` here, which is `.claude/settings.json`'s rule and was left standing rather than
worked around. That one call settled four things: the stored `TCGPLAYER_STORE_COOKIE` DOES
authenticate `order-management-api`, so one credential serves both hosts;
`PKMNSCAN_TCG_SELLER_KEY` was accepted; the plain-JSON body was accepted, so D65's form
encoding is the wrong shape here rather than merely a different one; and the response parsed
and projected without raising.

**`detail` and `fetch_open_orders` remain unexercised against the live host**, which is the
half that carries a buyer's name and address. `products[].skuId` was read in the BROWSER and
never through this module, so the PII projection is proven against T7's fixtures and against
nothing that came off the wire. Whoever presses Fetch first exercises it.
`server/order_transport.py`'s own STATUS block is the primary record and says this at greater
length. **`docs/map.py`'s entry for that module said the opposite — that the authenticated path
was unexercised and the stored value had never been sent — until this rewrite**, which corrected
it in place rather than deleting it. That note survived the run by one session because nothing
reconciles a `note` field against anything.

What was measured in the owner's own logged-in browser, before any of it: the two endpoints,
their methods, the query string and the request bodies; that the auth is a cookie session and
not a Bearer challenge; that `TCGAuthTicket_Production` is scoped to `.tcgplayer.com` and
therefore serves this host and the admin portal alike; that omitting `filters.sellerKey`
answers 403 rather than 400; that `GET /orders` answers 405 because `/orders` is a prefix and
not a route; and that refusals come back as RFC 7807 problem+json. Corroborated against
`tcgtracking-bridge-v2.4.2/background.js`, a third-party extension the owner supplied, which
bridges the same flow through the same two endpoints.

**The browser extension in `tcgtracking-bridge-v2.4.2/` is READ MATERIAL AND NOT A COMPONENT.**
It is a codebase `make check` never sees, `docs/map.py` does not map, and the git hooks do not
guard. Nothing in this repo calls it or depends on it.

**Postage economics, volumes and account state** — the letter rate, the insurance premium, the
347-orders-in-90-days figure, the seller level — are all external facts carried from the
planning session. They decided the lanes and none of them is checkable from here.

**That pasted JSON is a sufficient input for T1 is an argument, not a measurement**, and it is
still an argument with T1 built, reachable and green. `app/tests/orders.spec.ts` drives the
paste against a stubbed `POST /orders/ingest`, which proves the projection and proves nothing
about whether a real marketplace's JSON survives it. **This line may be struck only by a
session holding a transcript of a real order pasted or fetched, walked and pulled** — the same
standing the paragraphs above it have. Section 1 records that the first opportunity to produce
that transcript came and went on the evening the screen shipped.

---

## 7. Loose ends found in the store

- ~~**`3/37` is sold and carries no SKU.**~~ **Closed 2026-08-30**, and not by a re-emit — emit
  walks `uncommitted_positions` and a sold copy is not among them, so that reasoning held and
  the stamp came from the sale itself. **Re-checked after the thirty-one sales: no sold card in
  the store lacks a SKU**, so neither the stamping defect nor the sale session left residue.
- **`3/13` is sold with an empty `name`.** SKU (`9197754`) and number are present, so it
  resolves; only what a screen would draw is wrong. Still open.
- **Nothing is `live`.** 167 copies at `pushed`, none staged, none live — **unchanged by
  thirty-one sales**, because a sale is a card state and the listing counts are D59's per-SKU
  quantities. `store/master.py` already records this in its own comments, so it is known rather
  than newly broken — but any screen drawing a live count against these SKUs draws zero.
- **Twelve SKUs now have no copies on hand at all**, which is new. It is why
  `no_copies_on_hand` is demonstrable on real data in section 2 and why the resolver's old
  success example is not.

---

## 8. What would reopen this

**Line items arriving**, which retire D61's weight cut rather than re-fitting it —
`pipeline/orders.py` already answers the same question correctly from declared line kinds, and
`pipeline/shipping.py`'s own header says the cut is the thing to delete rather than re-fit.

**A real order pulled end to end**, which is still the first thing here that would replace an
argument with a measurement, and is still the largest gap in the file. **The screens being
built does not do it**; section 1 is the account of a day on which they were built and not
used.

**`detail` and `fetch_open_orders` reaching the live host**, which is one press rather than one
build, and is what proves the PII projection against something that came off the wire.

**tcgtracking answering a real call**, which unblocks T4 and is the only remaining thing in
this file that would cost money.
