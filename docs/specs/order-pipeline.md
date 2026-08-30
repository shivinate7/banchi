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

| step | state |
|---|---|
| 8 order in | **missing.** No transport of any kind. |
| 9 resolve | **built, runs correctly, unreachable.** `pipeline/orders.py` |
| 10 route | **built, runs correctly, unreachable.** `pipeline/shipping.py` (D61) |
| 11 pull | **missing.** No screen. `do_mark_sold` exists and is reached only by the sell path. |
| 12 ship | **half built, unreachable.** `pipeline/pirateship.py` writes the spreadsheet; the tcgtracking call does not exist. |
| 13 track back | **missing.** |
| 14 tell buyer | **missing.** Deferred behind 13. |

**`store/orders.py` is the one piece that is wired.** `store/session.py` carries `Ledger` in
`Snapshot` and writes it last on every store write. `inventory/orders.json` did not exist before
this session; the re-emit in section 1 created it, empty, with both of D63's maps. The plumbing
is therefore proven and the file has never held an order.

**Three modules have full T7 coverage and no reachability at all** — `pipeline/orders.py`,
`pipeline/shipping.py`, `pipeline/pirateship.py`. No route, no function in `app/src/server.ts`,
no subcommand beyond `identify | join | emit | reconcile`, no screen. Their only importer outside
`harness/tests/t7_store_and_seams.py` is `pipeline/shipping.py` importing `pipeline/pirateship.py`.
`make harness` and `make check` are green over every one of them, which is `CLAUDE.md`'s
route-is-not-a-feature rule and this repo's own recorded failure, at three modules at once.

---

## 1. The store this has to run against

Measured after the re-emit described below.

| | |
|---|---|
| cards | **715** — 703 identified, 11 sold, 1 retired |
| carry a SKU | **216**, across **102 distinct SKUs** |
| stamped by box | 1 → 133/133 · 2 → 45/543 · 3 → **38/39** |
| unstamped | **497**, every one of them in box 2 |
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
measured rather than argued.** Box 3 now has no unstamped card. Before it, an eight-copy order
for Rengar, Trophy Hunter resolved `short` on five picks; after it, `resolved` on eight.

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

### T3 — the transport

Whatever T0's probe returns. **The deliverable is that a fetch replaces a paste behind the control
T1 already built.** Ingest writes no card state and no listing count, so a replay is a no-op — and
D63 makes that true by construction rather than by a guard, because `store/orders.py` holds no
`Inventory` and imports nothing that can reach one.

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

**The route count is updated in five places**: `CLAUDE.md`, `README.md`, `docs/map.py`,
`app/src/App.tsx`, `scripts/views.txt`. `CLAUDE.md` already warns in its own words that this count
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

**No order feed has been read.** The claim that only the browser extension's order detail carries
per-line SKUs comes from testing three CSVs, and this session tested none of them. There is no
extension in this tree, so any relay work is in a codebase `make check` never sees, `docs/map.py`
does not map, and the git hooks do not guard.

**Postage economics, volumes and account state** — the letter rate, the insurance premium, the
347-orders-in-90-days figure, the seller level — are all external facts carried from the planning
session. They decided the lanes and none of them is checkable from here.

**That pasted JSON is a sufficient input for T1** is an argument, not a measurement, until
somebody pastes one.

---

## 7. Loose ends found in the store

- **`3/37` is sold and carries no SKU.** No order line can ever match it, and no re-emit will fix
  it: emit walks `uncommitted_positions`, and a sold copy is not among them. It is the permanent
  residue of the stamping defect, and it is one card.
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
with a measurement.
