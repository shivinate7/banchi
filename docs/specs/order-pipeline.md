# The order pipeline — steps 8 to 14

**Every number in this file was measured on 2026-08-30 against the owner's real store**, not
carried forward from a plan. Where a fact came from somewhere this session could not check, it
is in section 7 and labelled as such. That split is the point of the file: an earlier draft
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

| step | state |
|---|---|
| 8 order in | **built, two ways, reachable at `#/orders`.** Paste, projected client-side by `app/src/orderPaste.ts`, and a fetch behind the same control — `POST /orders/fetch`, `server/order_transport.py` (T3). The transport's endpoints, auth kind, body shape and four refusal codes were measured; the stored cookie has never been sent to that host. Section 6. |
| 9 resolve | **built and reachable.** `pipeline/orders.py`, drawn by `GET /orders` out of one store snapshot. |
| 10 route | **built and reachable at `#/shipping`.** `pipeline/shipping.py` (D61), on its own surface (T2 below). |
| 11 pull | **built and reachable.** `POST /orders/pull` writes the ledger and sells in one `Store.write()`, aimed by the row's own `capture_id`, with the undo on a twenty-second receipt. |
| 12 ship | **the spreadsheet is reachable; the tcgtracking call still does not exist.** `pipeline/pirateship.py`'s file downloads from `#/shipping`. Nobody has fed it to Pirate Ship. |
| 13 track back | **missing.** |
| 14 tell buyer | **missing.** Deferred behind 13. |

**`store/orders.py` was the one piece that was wired, and it is now written to by a screen.**
`store/session.py` carries `Ledger` in `Snapshot` and writes it last on every store write.
`inventory/orders.json` did not exist before this session; the re-emit in section 1 created it,
empty, with both of D63's maps. **It has still never held a real order** — nothing below the
paste box has been pressed against one, which is why section 6's last line stands.

**The three modules that had full T7 coverage and no reachability now have both.**
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
| cards | **715** — 703 identified, 11 sold, 1 retired |
| carry a SKU | **217**, across **102 distinct SKUs** |
| stamped by box | 1 → 133/133 · 2 → 45/543 · 3 → **39/39** |
| unstamped | **498**, every one of them in box 2 — 497 identified, 1 retired |
| listing copies | 167 `pushed`, 0 `staged`, 0 `live`, across 117 rows |
| ledger | `inventory/orders.json` present, both maps empty |

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
`short` on five picks; after it, `resolved` on eight.

It left box 3 one card short of stamped — `3/37`, sold, which no emit reaches — and a `sold` line
at 20:43 UTC carried a SKU onto that one too. That is why the table above reads 39/39 and why
section 7 has one fewer loose end than it was written with.

---

## 2. What the built modules do when you actually run them

Neither transcript below is a test fixture. Both are the shipped code against real data.

### The resolver, against the live store

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

### The router and the emitter, against the committed fixture

```
shipments: 331
lanes:   {'envelope': 166, 'parcel': 126, 'unjudged': 39}
reasons: {'value_at_threshold': 112, 'non_card_signal': 14, 'cards_only': 166,
          'no_weight_data': 39, 'no_value_data': 0, 'sub_single_weight': 0}
parcel lane: 126 orders
```

`render()` produced a well-formed Pirate Ship import file — ten columns, `Name` pre-joined,
`Order ID` carried, `Package Weight` correctly blank, three rubber-stamp columns empty and
waiting for a location. **The >=$50 lane is complete apart from a screen.**

---

## 3. The work, in order

The order below is D66's, and D66 carries the argument. Three claims decide it: a transport-first
session cannot state a Done this repo accepts, the shipping lane depends on neither the screen nor
the transport, and the transport question is one probe rather than one session.

### T0 — free, no code, hours

- **Probe `order-management-api` auth** with the cookie already in `.env`. The admin host answers a
  cookie-session 302 and D64 satisfies it with stdlib `urllib`; this host answers a Bearer
  challenge, and the D64 result does not transfer between them. The answer decides whether T3 is a
  Python client or a browser relay, and nothing else in this file depends on it.
- **Rule on box 2's disposition** — 108 SKUs, 497 copies, all sub-threshold. Not this pipeline's
  work, but it is the oldest thing in the store waiting on a person.
- ~~Re-emit `runs/2026-08-30-box3-01`~~ — **done 2026-08-30**, section 1.

### T1 — the order screen. The one that unlocks everything

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

### T2 — lanes and the Pirate Ship download

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

### T3 — the transport

**Built 2026-08-30 as `server/order_transport.py`, and the probe T0 describes was answered by
measurement in the owner's own logged-in browser rather than by a request from this tree.** The
auth is a cookie session and not a Bearer challenge, so T3 is a Python client and not a browser
relay. `POST /orders/fetch` answers EXACTLY the body `POST /orders/ingest` accepts, which is why
the fetch needed no adapter and enters through the same one door the paste does. What is NOT
established is in section 6.

Whatever T0's probe returns. **The deliverable is that a fetch replaces a paste behind the control
T1 already built.** Ingest writes no card state and no listing count, so a replay is a no-op — and
D63 makes that true by construction rather than by a guard, because `store/orders.py` holds no
`Inventory` and imports nothing that can reach one.

**The shape a second fetch should take is already in the tree**, landed by D65 after this file was
written. `server/tcg_export.py` is this server's one outbound call: stdlib `urllib`, one host and
one method reachable from it, the secret read at call time and present in no return value, refusal
message or log line, ten named failure codes because "the fetch failed" is three different
problems, and a control on `#/runs` that a person presses. It is **not** the order host — its
cookie session is the admin portal's and does not transfer — so what carries over is the shape and
not the auth.

### T4 — the envelope, and the money gate

The tcgtracking call for the sub-$50 lane, under **D33's gate verbatim**: a free preflight, the
count and the premium on screen, an explicit `confirm`, and the spending control **absent** until
the preflight has answered. This is the second route in this repo that can spend money.

**Done:** T7 asserts the refusal without `confirm`, and that replaying one order id creates nothing.

### T5 — closing the loop

Tracking read back and emitted as TCGplayer's Import Shipping Info CSV. T2's byte rules already
govern the file, and the order id T2 carries into Pirate Ship is what makes the match possible.

**pkmnscan never writes order status back to TCGplayer** — tcgtracking owns mark-shipped, and two
authors on one shipment is D34's problem twice.

---

## 4. What T1 has to get right

**The label formula is `pipeline/join.py:Position` and there is no second one.** D58 makes drawing
one need the box's whole occupancy, so a formula on this screen is the second-renderer failure
this repo has recorded three times.

**`do_mark_sold` opens its own store session**, so pulling one card at a time needs a
snapshot-taking form extracted first. The undo must scan the ledger rather than making the client
name the line it is undoing.

**All six reasons get drawn**, with the machine string small beneath a human label: `resolved`,
`short`, `no_copies_on_hand`, `sku_unknown`, `sku_unseen`, `not_a_single`. An empty result has
several causes with different remedies, and one blank row for all of them throws away the
resolver's best work — section 2 shows three different empties in a single order.

**PII is projected in the client before the POST**, and unknown keys are refused on the server. A
buyer's address should never become something the server has to remember to drop.

**Fulfilment is a count, never a list of positions**, and the one identity it holds is a
`capture_id`. D10 lets a mid-box delete slide every higher index down one, so a position written
down today names a different card tomorrow — D63 measured exactly that.

**The route count is updated in four places** — `CLAUDE.md`, `README.md`, `docs/map.py`,
`app/src/App.tsx` — and `scripts/views.txt` gains a LINE rather than a number, which is the one a
session looking for a count will not find. `CLAUDE.md` already warns in its own words that this count
has been wrong more often than right and that nothing checks it.

---

## 5. What T2 has to get right

All three are D61's and all three are the kind a screen quietly undoes.

**The abstention is a third answer and is never defaulted into a lane.** Defaulting the 39 to the
envelope ships a playmat in a stamped mailer; defaulting them to the parcel spends postage nobody
chose. `Routing.certain` is the split worth surfacing — a published price against a published
threshold is a different quality of claim from an inference off a weight ratio.

**No weight is ever derived.** `Product Weight` is a catalog constant that counts the cardboard
and not the mailer, so writing it buys postage for less than the parcel weighs, and the bill
arrives weeks later at the far end.

**No insurance is ever selected and no label is ever bought.** An insurance-shaped column raises
rather than being dropped.

---

## 6. Facts this file did not verify

Recorded so a green harness and a confident table are not mistaken for evidence.

**The tcgtracking API has never been called from this repo.** `TCG_TRACKING_KEY` is in the main
checkout's `.env`; every response shape is documentation-verified. The rate limit, the free tier
and the per-label price are all claims from outside this tree.

**Nobody has fed Pirate Ship the CSV `pipeline/pirateship.py` emits.** Their importer maps columns
on the far side of a seam no committed fixture can hold. This is the same standing as T6's
synthetic composites, and it is why `Name` is pre-joined rather than left to their mapper.

**An order feed HAS been read, and the half that matters has not.** Amended 2026-08-30, when
T3 landed. What was MEASURED, in the owner's own logged-in browser: the two endpoints, their
methods, the query string and the request bodies; that the auth is a cookie session and not a
Bearer challenge; that `TCGAuthTicket_Production` is scoped to `.tcgplayer.com` and therefore
serves this host and the admin portal alike; that omitting `filters.sellerKey` answers 403 rather
than 400; that `GET /orders` answers 405 because `/orders` is a prefix and not a route; and that
refusals come back as RFC 7807 problem+json. Corroborated against
`tcgtracking-bridge-v2.4.2/background.js`, a third-party extension the owner supplied, which
bridges the same flow through the same two endpoints.

**What has NOT happened is the authenticated success path.** The `TCGPLAYER_STORE_COOKIE` value
stored in `.env` has never been sent to that host — not by hand, not in a test — because the
harness classifier refuses to let a credential leave a Bash process, and that refusal was
respected rather than routed around. So the MECHANISM is proven and the VALUE is not: the first
real run is what answers whether this particular cookie authenticates there, and a failure
arrives as `order_session_expired` with the remedy in the message. `server/order_transport.py`'s
own STATUS block is the primary record of this and says the same thing at greater length.

**It is also still true that the search result carries no per-line SKU** — only the order detail
does, as `products[].skuId` — which is why the transport is two calls and not one. That is
measured now rather than carried from a planning session.

**The browser extension in `tcgtracking-bridge-v2.4.2/` is READ MATERIAL AND NOT A COMPONENT.** It
is a codebase `make check` never sees, `docs/map.py` does not map, and the git hooks do not
guard. Nothing in this repo calls it or depends on it.

**Postage economics, volumes and account state** — the letter rate, the insurance premium, the
347-orders-in-90-days figure, the seller level — are all external facts carried from the planning
session. They decided the lanes and none of them is checkable from here.

**That pasted JSON is a sufficient input for T1** is an argument, not a measurement, until
somebody pastes one. **It is still an argument as of 2026-08-30, with T1 built and reachable**,
and the screen shipping is not what settles it: `app/tests/orders.spec.ts` drives the paste
against a stubbed `POST /orders/ingest`, which proves the projection and proves nothing about
whether a real marketplace's JSON survives it. **This line may be struck only by a session
holding a transcript of a real order pasted, walked and pulled** — the same standing the two
paragraphs above it have.

---

## 7. Loose ends found in the store

- ~~**`3/37` is sold and carries no SKU.**~~ **Closed 2026-08-30**, and not by a re-emit — emit
  walks `uncommitted_positions` and a sold copy is not among them, so that reasoning held and the
  stamp came from the sale itself. **No sold card in the store now lacks a SKU**, so the stamping
  defect left no residue.
- **`3/13` is sold with an empty `name`.** SKU and number are present, so it resolves; only what a
  screen would draw is wrong.
- **Nothing is `live`.** 167 copies at `pushed`, none staged, none live. `store/master.py` already
  records this state in its own comments, so it is known rather than newly broken — but any screen
  drawing a live count against these SKUs draws zero.

---

## 8. What would reopen this

**Line items arriving**, which retire D61's weight cut rather than re-fitting it —
`pipeline/orders.py` already answers the same question correctly from declared line kinds.

**The probe answering Bearer**, which does not change the order of the work but does change what
T3 is.

**A real order pulled end to end**, which is the first thing here that would replace an argument
with a measurement. **T1 being built does not do it** — the screen is the thing that makes it
possible to try, and section 6's last paragraph says what a session would have to hold to strike
the line.

**The stored cookie reaching `order-management-api` for the first time**, which is the other
half of T3 and is one press away rather than one build away.
