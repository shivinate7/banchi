# The order pipeline — steps 8 to 14

Where a fact came from somewhere this file could not check, section 6 says so. That split is
the point of the file. A number here is either a property of committed code and fixtures, or it
is marked as unmeasured.

**It is not `docs/specs/order-flow.md`.** That file covers search, boxes and the sell path.
There the owner already knows which card they sold. This one is an order that arrives from outside. It covers
four things. How the order gets in. How it becomes a walk to a drawer. How it leaves. How the
tracking number gets back. The two files touch at one function, `do_mark_sold`.

---

## STATUS

A row says `built` only where a human can reach the thing from a screen. That is `CLAUDE.md`'s
rule. `make design-check` is the only check in this repo that can see reachability.

| step | state |
|---|---|
| 8 order in | **built, two ways, reachable at `#/orders`.** Paste, projected client-side by `app/src/orderPaste.ts`. And a fetch behind the same control: `POST /orders/fetch`, `server/order_transport.py` (T3). **The fetch is one press** (D193's amendment of D91). It takes all statuses and skips known orders by default. D91's ticked-status flow is a secondary control, and `{all_statuses: true}` is the explicit body for "every one". `POST /orders/names` writes buyer display names with no detail call. The transport's `detail` half, which carries a buyer's address, is not proven live. Section 6. |
| 9 resolve | **built and reachable.** `pipeline/orders.py`, drawn by `GET /orders` out of one store snapshot. |
| 10 route | **built and reachable at `#/shipping`.** `pipeline/shipping.py` (D61), on its own surface (T2). |
| 11 pull | **built and reachable, in ONE form: the per-copy press.** `POST /orders/pull` writes the ledger and sells in one `Store.write()`, aimed by the row's own `capture_id`. It is pressed a card at a time, from the walk on `#/orders` (`docs/specs/order-walk-plan.md`). The envelope form (T6) is deleted and not built. |
| 12 ship | **the spreadsheet and the stamps are reachable; the tcgtracking call does not exist.** `pipeline/pirateship.py`'s file downloads from `#/shipping`. `POST /shipping/batches/<batch>/stamps` fills the three Rubber Stamp columns from the ledger, and a control on `#/shipping` presses it (T2b). Whether Pirate Ship accepts the file is unknown (section 6). |
| 13 track back | **missing.** |
| 14 tell buyer | **missing.** Deferred behind 13. |

**Step 11 has one form:** the per-copy press, from the walk on `#/orders`. The envelope form is not built (T6).

**`store/orders.py` is written by a screen.** `store/session.py` carries `Ledger` in `Snapshot`
and writes it last on every store write. `pipeline/orders.py` is read by `GET /orders`.
`pipeline/shipping.py` and `pipeline/pirateship.py` are read by `POST /shipping/batches` and
its file route. Each has a route, a client function in `app/src/server.ts`, a control on a
screen, and where it writes, a receipt and a way back. `make harness` and `make check` do not
see reachability. `app/tests/orders.spec.ts` and `app/tests/shipping.spec.ts` do, and `make
design-check` is deliberately off the commit path.

---

## 1. The store this has to run against

**The store is not a fixture, and every measurement taken against it is perishable.** A number
about the owner's store is evidence of one moment. A session that finds one stale has found the
store moving, and not the file lying. So this file records no counts of the live store. Measure
it (`make status`, `pkmnscan` reports) when a number matters.

Four facts about the store outlive any count.

- **Sub-threshold cards carry no SKU, and that is correct.** D9 says they are not listed, and
  no order arrives for a card that was never listed. A screen that reports `sku_unseen` across
  such a box is correct and not broken. What such a box needs is a disposition decision, which
  is not order-pipeline work.
- **A sale from `#/inventory` writes card state and never the ledger.** `POST /orders/pull`
  writes both. Real fulfillment that goes around the order screen leaves the ledger untouched.
  D63's two maps then stay empty. This is the seam that the walk's design is about.
  History positions are not stable identities, because D10 lets a mid-box delete slide every
  higher index down one. So a count re-derived from an old event log can disagree with the
  card states of the same moment.
- **An emit is additive, and the identity stamp is separate from the D7 quantity.** An emit
  can send nothing new and still stamp a card with its SKU and condition. It resurrects no
  sold card (D54, D57).
- **`resolve_all`'s output depends on a store that moves under it.** Any transcript of it is
  perishable by construction. A `resolved` example decays as the copies sell.

## 2. What the built modules do

### The resolver

`pipeline/orders.py:resolve_all` resolves every open order in one pass, and there is
deliberately no `resolve_one`. Each line answers with one of six reasons: `resolved`, `short`,
`no_copies_on_hand`, `sku_unknown`, `sku_unseen` and `not_a_single`.

- **The double-book guard is a property of one pass over the open set.** The first order for a
  SKU takes the copies. The second gets what remains. Since D212 the guard moved to the write:
  no order claims a copy in the resolver's answer, and `record_pull` refuses a full line.
- **`short` and `no_copies_on_hand` differ.** `short` means that copies exist and are spoken
  for. The remedy is to wait. `no_copies_on_hand` means that they have left, and the remedy is
  to stop looking. `on_hand` beside the reason is the STORE's count and not the remaining pool,
  so a reader can tell the two apart. `pipeline/orders.py:_reason` decides which.
- **`not_a_single` is answered from the line's declared kind, with no inventory lookup.** An
  accessory's SKU is not a card's SKU. Asking the inventory about it would produce `sku_unseen`,
  which reads as "we lost track of a card" and sends the owner hunting for a playmat.
- **`sku_unknown` is unreachable from `GET /orders`, and that is a limit of the route.** The
  route passes no `paperwork=`. `cli/resolve.py:paperwork_for` takes one run and calls
  `realign`, which hashes every photograph and raises on an ambiguous digest. One bad run
  would take the whole screen render down. `do_orders`'s docstring argues the same. The zero is
  not a fact about the store.

### The router and the emitter, against the committed fixture

The fixture is committed and the router reads nothing else, so these numbers cannot go stale
the way a store count can. `fixtures/orders-shipping.csv` has 331 shipments. The router answers:

```
lanes:   {'envelope': 166, 'parcel': 126, 'unjudged': 39}
reasons: {'value_at_threshold': 112, 'non_card_signal': 14, 'cards_only': 166,
          'no_weight_data': 39, 'no_value_data': 0, 'sub_single_weight': 0}
certain: 112 of 331
```

**`Routing.certain` is 112 and not 292.** 292 orders are JUDGED, and they got a lane. 112 of
them were answered by a published price against a published threshold, which is a fact. The
other 180 were answered by an 18x weight separation, which is an inference off a catalog
constant. The two produce the same lane without being the same quality of answer.
`Routing.certain` is `reason == VALUE_AT_THRESHOLD` for that reason. Harness T7 asserts that the
only certain rows are the `value_at_threshold` ones.

`pipeline/pirateship.py:render` writes a Pirate Ship import file — **twelve columns**: `Name`,
`Address`, `Address Line 2`, `City`, `State`, `Zipcode`, `Country`, `Package Weight`, `Order ID`
and three `Rubber Stamp` columns. The fixture's parcel lane gives 126 rows, with CRLF line ends
and no BOM. Each data row is fully quoted. `Name` is pre-joined on every row. `Order ID` is
present on every row. `Package Weight` is blank on every row.

---

## 3. The work, in order

**The `T0`–`T6` below are work items in this file and NOT the harness's tests.** The harness's
own T6 is `harness/tests/t6_geometry.py` and its T7 is `harness/tests/t7_store_and_seams.py`.
Every reference to one of those says `harness` in front of the number. A bare `T4` is this
section's.

The order below is D69's, and D69 carries the argument. Three claims decide it. A
transport-first session cannot state a Done that this repo accepts. The shipping lane depends on
neither the screen nor the transport. The transport question is one probe and not one session.

### T0 — free, no code. DISCHARGED

- The auth of `order-management-api` is a cookie session, the same `TCGAuthTicket_Production`
  that the admin portal takes. It does not answer a Bearer challenge. So T3 is a Python client
  and not a browser relay. Section 6, and `server/order_transport.py`'s STATUS block.
- Box 2's disposition (all sub-threshold) is not this pipeline's work. It is the oldest thing
  in the store that waits on a person.

### T1 — the order screen. BUILT (D69)

Route `#/orders`. `GET /orders` answers the order list and the resolution out of ONE store
snapshot, so the two cannot disagree. `POST /orders/ingest` accepts the projection and
nothing else. `POST /orders/pull` records the copies and sells them in one `Store.write()`, and carries
its own reversal. Client functions `getOrders`, `ingestOrders`, `fetchOrders`, `pullCopy` and
`undoPull` are in `app/src/server.ts`. The screen is `app/src/Orders.tsx`. The walk is in
`docs/specs/order-walk-plan.md`.

**Three things it does deliberately.**

- The pull is aimed by the row's own `capture_id`. A mid-box delete or a re-shoot between
  render and press is refused, and it never sells whatever is at that slot.
- The receipt reads `places[]`, the labels as they were BEFORE the write. It never reads
  `sales[].card.place.label`, which reads `Box 3 · departed` by the time the answer is
  composed (D58).
- The undo lives on the receipt and not in the row. A successful pull makes the resolver stop
  offering the copy, so the row unmounts.

**The screen is why the transport is second.** The resolver, the labels and the ledger were
built first. A screen fed by pasted JSON is a complete product with no network in it. The
transport is then a better source behind a control that already exists. The alternative ships
an ingest route that no human can reach, whose Done is satisfiable without a screen. That is
the failure this repo keeps recording.

**Unmeasured:** whether a real marketplace's pasted JSON survives the projection.
`app/tests/orders.spec.ts` drives the paste against a stubbed `POST /orders/ingest`, which
proves the projection and nothing more.

### T2 — lanes and the Pirate Ship download. BUILT (D69)

The lane badge, the abstention drawn as a third answer, and the CSV as a download. It depends
on neither T1's engine nor the transport. `Shipment` carries no line items, and `to_parcel`'s
`stamps` argument defaults to empty.

**It has its own surface:** route `#/shipping`, `app/src/Shipping.tsx`, `POST
/shipping/batches`, `GET /shipping/batches/<batch>/file` and `DELETE
/shipping/batches/<batch>`. Two reasons. If the badge and the download shared T1's screen, two
branches would revise one file. And **`server/shipping_routes.py` is the one module in this
server that holds a buyer's name and street address.** Containing that at a FILE boundary is what
`server/tcg_export.py` does for the session cookie. An operator who asks "where does the PII
go" reads one file. Folding the lane into the order screen would have put those routes in
`server/capture_server.py` beside forty that hold none. The screen is typed so that it cannot
draw a buyer: `ShippingRow` carries no name, no street, no city and no postcode. Those details
cross the wire once, as the CSV download.

### T2b — the rubber stamps. BUILT

`POST /shipping/batches/<batch>/stamps` fills Pirate Ship's three Rubber Stamp columns from the
order ledger. **The label in the operator's hand IS the pick instruction.** It changed no type
and no component. The wire carries `stamp` on every row and `stamps` on the batch, and
`app/src/OrdersShipStage.tsx` draws both. The client call is
`app/src/server.ts:fillShippingStamps`, and the control sits beside the download, placed
BEFORE it. The press re-renders the file, and an operator who grabs the CSV first gets blank
corners.

`server/capture_server.py:_engine_order` is THE ONLY adapter from `store.orders.OrderRecord` to
`pipeline.orders.Order`, so the two-branches-one-file collision cannot happen.

**Done:** a batch whose orders are in the ledger renders with its Rubber Stamp columns filled.
One whose orders are not renders them empty and never guesses. Both halves are asserted in
`harness.tests.t7.shipping.check_shipping_stamps`, over the same 331-order export in
one store.

**The seam is a callable, and what crosses it is order numbers and strings.**
`do_shipping_stamps` takes a `locate` function and never sees a `Snapshot`, an `Inventory` or a
`Ledger`. `server/capture_server.py:_order_stamps` is what is passed in. That keeps the module
that answers "where does the PII go" to one subject. It is also forced, because
`capture_server` imports `shipping_routes`, and the reverse import is the cycle that
`ShippingRefusal` exists for.

#### Three determinations, and the second is the one that will get "fixed"

**A stamp is one position label and it comes from `pipeline/join.py:Position` by way of
`_Places`.** There is no second formula.

**It stamps what is still owed, and never what has already been pulled.** The obvious
alternative stamps every copy of the order at the position that the ledger recorded. That is
actively harmful. A pull sells the copy. A sold card renders `join.departed_label`, and the box
closes up behind it (D58). So that index now holds a DIFFERENT card. Under that mutation the
harness draws `Box 4 · departed · B4 #1` into `Rubber Stamp 1`. That is a pick instruction to a
slot whose occupant changed. An order with nothing outstanding has nothing to pick, and empty
corners are the true answer for it.

**All three corners or none.** An order that needs more positions than the label has corners
gets none, and it is counted unstamped. There is no fourth corner to say "and two more", and a
pick list sliced to fit reads as a complete one. That is the wrong-shelf failure that
`pipeline/pirateship.py` refuses to enforce a stamp LENGTH over, one register up. So this rule
leaves some real orders unstamped, and that is the reopening condition and not a defect to
patch. If the ratio holds as the store deepens, the REGISTER changes. It becomes a stop per box in
the walk plan's vocabulary, and not a card per corner. The refusal to truncate never changes.

**Unmeasured:** a press against the owner's real store.

### T3 — the transport. BUILT (D69)

`server/order_transport.py`. The probe in T0 was answered by measurement in the owner's own
logged-in browser and not by a request from this tree. `POST /orders/fetch` answers EXACTLY the
body that `POST /orders/ingest` accepts. So the fetch needs no adapter, and it enters through
the same one door that the paste does. What is NOT established is in section 6.

**`PKMNSCAN_TCG_ORDERS_URL` re-points the base URL, and it is a test seam with a guard on
it.** T7 aims it at a loopback socket so the refusal codes can run without the live portal.
The module refuses to send the session cookie anywhere but https or loopback. A knob that
redirects a session cookie is an exfiltration channel that looks like a test seam. The variable
can move the endpoint and cannot move the credential off this machine.

**A fetch replaces a paste behind the control T1 built.** Ingest writes no card state and no
listing count, so a replay is a no-op. D63 makes that true by construction, because
`store/orders.py` holds no `Inventory` and imports nothing that can reach one.

**The projection is `{source, number, placed_at, status, buyer, lines}`** (D193). `buyer` is a
display name. Address, email, payment and the transaction breakdown are excluded at an
allowlist (`project_summary`, `project_order`). `POST /orders/names` writes names for orders
that the ledger already knows, from search summaries alone. `fetch_open_orders` already parses
`buyerName` off every summary, so a names-only pass costs zero detail calls, and `/orders/fetch`
keeps its `writes_nothing` contract.

**It is two calls, and that is not an optimization failure.** The search result carries no
per-line SKU. Only the order detail does, as `products[].skuId`. The SKU is the join key
(`products[].skuId` is the export's `TCGplayer Id` is `store/master.py:Card.sku`), so an order
without it resolves to nothing. There is no bulk line-item endpoint.

**One credential serves two hosts.** `TCGAuthTicket_Production` is set on `.tcgplayer.com`, so
the same `TCGPLAYER_STORE_COOKIE` that the export reads reaches the order host. A second env
name would be a second thing to rotate. **The body convention does not transfer.** The admin
portal takes Knockout's `model=<json>` form, and this host takes a plain JSON document. A
client that carries D65's shape here fails in a way that reads like an auth problem.

**403 is `order_seller_key_rejected` and not `order_session_expired`.** A missing or wrong
`filters.sellerKey` answers 403 and not 400. Folding it into "sign in again" sends the operator
to re-copy a working cookie over a bug in a request body. That is the defect that D65 recorded
on the other host. The refusal leads with the body and not the credential.

**A count cap on the fetch counts detail calls and not the window** (D91). The summaries are
walked whole and counted by status string. A cap on the window refused every press on a real
account.

**The shape of a second outbound call is `server/tcg_export.py`'s.** It uses stdlib `urllib`
and reaches one host. It reads the secret at call time and leaves it out of every return value,
refusal message and log line. It has named failure codes. It has a control that a person
presses. The order host's cookie session is the admin portal's and does not transfer, so what
carries over is the shape and not the auth.

### T4 — the envelope, and the money gate. NOT BUILT

The tcgtracking call for the sub-$50 lane, under **D33's gate verbatim**. It has a free
preflight, and the count and the premium are on screen. It has an explicit `confirm`. The
spending control is **absent** until the preflight has answered. This is the second route in
this repo that can spend money.

**Done:** harness T7 asserts the refusal without `confirm`, and that replaying one order id
creates nothing.

### T5 — closing the loop. NOT BUILT

Tracking read back and emitted as TCGplayer's Import Shipping Info CSV. T2's byte rules already
govern the file. The order id that T2 carries into Pirate Ship is what makes the match
possible.

**pkmnscan never writes order status back to TCGplayer.** tcgtracking owns mark-shipped, and two
authors on one shipment is D34's problem twice. The two endpoints that would do it were seen on
the wire. They are recorded once, in `server/order_transport.py`'s WHAT IS DELIBERATELY NOT
BUILT block. Read them there. That module cites this section by number for the ruling.

### T6 — the order drives the walk. SUPERSEDED, and deleted (D97 amended)

The envelope form is not in the tree. The want is met by the per-copy walk on `#/orders`
(`docs/specs/order-walk-plan.md`, D97). `_prepare_targets` and `_ledger_pull` are `POST
/orders/pull`'s own two phases. `POST /orders/fill` closes copies of a line that have no card
behind them (D113).

---

## 4. What the order screen holds to, and must keep holding to

These are invariants over shipped code. Each is the kind that a later edit quietly undoes.

**The label formula is `pipeline/join.py:Position`, and there is no second one.** D58 makes
drawing one need the box's whole occupancy. A formula on this screen is the second-renderer
failure that this repo has recorded three times. `server/capture_server.py:_Places` is the walk
that feeds it, one renderer made per request. It is per request because `Inventory.box_fill` is
O(cards), and an uncached one would walk the store for every row.

**`do_mark_sold` opens its own store session**, so the pull uses the snapshot-taking form
extracted beside it. The undo scans the ledger and does not make the client name the line it
undoes.

**All six reasons get drawn**, with the machine string small beneath a human label, **including
the ones that are zero**. `app/tests/orders.spec.ts` asserts this by name. An empty result has
several causes with different remedies, and one blank row for all of them throws away the
resolver's best work.

**PII is projected in the client before the POST**, and the server refuses unknown keys BY NAME
and never trims them. `_reject_unknown` answers `field_not_settable` and lists both what was sent
and what the route accepts. `app/src/orderPaste.ts` is the one place in the app that decides
what leaves the browser about a purchase. It draws the top-level keys that it dropped. Keys
inside a LINE are dropped without being listed, and its header says why. A silent trim would
make a broken projection indistinguishable from a working one.

**Fulfillment is a count, never a list of positions**, and the one identity it holds is a
`capture_id`. D10 lets a mid-box delete slide every higher index down one, so a position
written down today names a different card tomorrow (D63).

**Do not write a route count in prose.** `make docs-audit`'s `route rosters` row reconciles each
spec's pinned roster against `App.tsx`'s `ROUTES` table.

---

## 5. What the shipping lane holds to, and must keep holding to

All three are D61's. Each names the code that enforces it and the test that would catch its
removal, because an invariant with neither is a sentence.

**The abstention is a third answer and is never defaulted into a lane.** Defaulting the
unjudged orders to the envelope ships a playmat in a stamped mailer. Defaulting them to the
parcel spends postage that nobody chose. `pipeline/shipping.py:parcel_lane` leaves them out of
the download entirely. `app/tests/shipping.spec.ts`'s "an unjudged order is not in the parcel
file" case asserts it from the screen's end. `Routing.certain` is the split that the screen
surfaces beside the lane. A published price against a published threshold is a different
quality of claim than an inference off a weight ratio (section 2).

**No weight is ever derived.** `Product Weight` is a catalog constant that counts the cardboard
and not the mailer. Writing it buys postage for less than the parcel weighs, and the bill
arrives weeks later at the far end. No control on the screen can fill it. `app/src/
OrdersShipStage.tsx`'s header says so, and the caption on the download tells the operator that
the column is blank. `Package Weight` ships blank on every row.

**No insurance is ever selected and no label is ever bought.** An insurance-shaped column
raises and is not dropped, and it raises twice over. `pipeline/pirateship.py:render` closes the
column set, so an unknown header is a `MalformedParcel`. A folded deny list stops the
insurance-shaped ones first as `InsuranceRefused`, with a message that says insurance is the
owner's per-order choice inside Pirate Ship. The second is not belt and braces. A refusal that
reads "not a Pirate Ship column" invites the fix of adding it to the column set. One that names
the reason does not. `check_no_insurance` runs over the row's own keys on the way out of
`render`. A row that reached the writer by another path still has to pass it.

---

## 6. Facts this file did not verify

Recorded so that a green harness and a confident table are not mistaken for evidence.

- **The tcgtracking API has never been called from this repo.** `TCG_TRACKING_KEY` is in the
  main checkout's `.env`. Every response shape is documentation-verified. The rate limit, the
  free tier and the per-label price are claims from outside this tree.
- **Unknown: whether Pirate Ship accepts the CSV that `pipeline/pirateship.py` emits.** Their
  importer maps columns on the far side of a seam that no committed fixture can hold. It is
  the same standing as harness T6's synthetic composites. It is why `Name` is pre-joined and
  not left to their mapper.
- **The committed shipping fixture carries no real buyer.** `fixtures/orders-shipping.csv` is
  331 rows in which every buyer is `BuyerNNN Placeholder` at `NNN Example St`. So
  `server/shipping_routes.py` and `pipeline/pirateship.render` have run against placeholders
  shaped like addresses and never against a real one. A real address has never arrived through
  `detail` (below), and one has never left through the CSV.
- **The order transport's status.** `server/order_transport.py`'s STATUS block is the primary
  record. As it stands, the session is proven: a real `search` returned real orders under the
  stored cookie. The paging is proven live. **`detail` is unexercised against the live host.**
  That is the half that carries a buyer's name and address. `project_order`'s drop of
  `buyerName`, `shippingAddress` and `paymentType` is proven against fixtures and against
  nothing that came off the wire.
- **What was measured off the wire, in the owner's logged-in browser:** the two endpoints, their
  methods, the query string and the request bodies. The auth is a cookie session.
  `TCGAuthTicket_Production` is scoped to `.tcgplayer.com` and serves this host and the admin
  portal alike. Omitting `filters.sellerKey` answers 403. `GET /orders` answers 405, because
  `/orders` is a prefix and not a route. Refusals come back as RFC 7807 problem+json. A
  third-party extension that the owner supplied bridges the same flow through
  the same two endpoints. **It is read material and not a component.** It is not in this
  repository, and nothing here calls it or depends on it.
- **A stored cookie can expire.** A session that expires arrives as `order_session_expired`,
  and the message prints the remedy. An agent may not read `.env` in this repo, and
  `.claude/settings.json` denies it. So a live run of the transport is the operator's.
- **Postage economics and account state** (the letter rate, the insurance premium, the seller
  level) are external facts. They decided the lanes, and none of them is checkable from here.
- **Unknown: whether a real order has been pasted, walked and pulled end to end.** The pasted
  JSON being a sufficient input is an argument and not a measurement. Only a session that holds
  a transcript of a real order, pasted or fetched, walked and pulled, may strike this line. It
  is the one event that exercises the ingest, the resolver, the aim check and the ledger in one
  pass. It says nothing about `detail`.

---

## 7. Loose ends found in the store

A count over a store that moves is dated by nature, so none is kept here. Two kinds of loose end
outlive their counts.

- **A sold card can carry an empty `name`.** SKU and number are present, so it resolves. Only
  what a screen would draw is wrong.
- **A live count does not follow a sale, and a reader who expects it will misread both.** A
  sale moves `sold_here` and not `live`, because `live` is the export's READING and a sale is
  not an export (D115). The count that a screen draws is `Listing.live_estimate`, the two
  together. The listing counts are D59's per-SKU quantities and not card states, so a sale
  and a listing stage move for different reasons.

---

## 8. What would reopen this

- **Line items arriving**, which retire D61's weight cut and do not re-fit it.
  `pipeline/orders.py` already answers the same question correctly from declared line kinds.
- **The cookie ceasing to authenticate `order-management-api`.** That is one host policy change
  away, and it would put the browser relay back on the table.
- **tcgtracking answering a real call.** It unblocks T4 and is the only remaining thing in this
  file that would cost money.
- **A real order pulled end to end.** It is the first event that would replace an argument with
  a measurement (section 6).
- **`detail` running against the live host.** It would first put a buyer's name and address
  through `project_order` outside a fixture.
- **Two devices pulling at once.** The write is safe. Phase one re-validates every target
  against the store inside the same `Store.write()` that phase two writes in (D88). A copy that
  the other device already took refuses `copy_already_pulled` or `capture_id_mismatch`. What
  the loser should then see is undecided. The plain sale settled its own version:
  `docs/specs/order-flow.md` §8.1 rules that a second device's `already_sold` is a receipt for
  a card that leaves your list, and not an error. Nothing reopens until two people actually pull
  at once.
