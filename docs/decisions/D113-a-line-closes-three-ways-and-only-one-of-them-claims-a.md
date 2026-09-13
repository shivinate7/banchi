## D113 — A line closes three ways, and only one of them claims a copy went

**Built 2026-09-06, on the owner finding orders they could not close.** They put it plainly:
*"there's orders still remaining in open that i can't close out because it's skus banchi has
never seen."* They were right, and the reason turned out to be larger than the three orders
that prompted it.

**`record_pull` WAS THE ONLY WRITER OF `fulfilled`, AND IT REQUIRES A `capture_id`.** That
requirement is correct — a pull moves a card this store holds, and an unidentifiable one is a
double-shipment waiting to happen. But a sealed Holiday Calendar has no card record and never
will, and neither has a single that shipped from a pile this rig never photographed. Such a
line could not be closed **at all**: no CLI path, no route, no control. `Ledger.unfulfilled` is
`quantity - fulfilled`, so the order stayed open forever.

**THE STORAGE MODEL HAD ANTICIPATED THIS AND NOTHING HAD WRITTEN IT.** `LineProgress`'s own
docstring, from the day it was written: *"it is a SUBSET rather than a second spelling of the
count, so `fulfilled` may legitimately exceed `len(copies)` if a copy is ever recorded without
one."* This entry is the writer that sentence was waiting for.

### What was measured, and why the answer is two mechanisms rather than one

**The first reading, 2026-09-06 20:45 — 20 orders, 3 open, all three unclosable.** A Pokemon
Holiday Calendar 2025 ($77.99, sealed), a One Piece Double Pack Set (x2, sealed), and a
Riftbound *Lonely Poro (Overnumbered)* `#221/219` at **$404.44** — a real single the store has
never photographed. No card carries those SKUs, no listing record does either, and the store
holds no card named `Poro` and none numbered `221/219`.

**The store then moved under the session, and the picture got much larger.** The owner pressed
fetch mid-build. Second reading, 100 orders: 68 `Shipped - In Transit`, 18
`Shipped - Delivered`, 14 `Ready to Ship`.
**83 open, and 69 of those 83 were orders TCGplayer had already shipped.**

**THAT WAS A CORRECTNESS BUG, NOT NOISE, AND IT IS THE STRONGEST FINDING HERE.**
`pipeline/orders.py:resolve_all` walks open orders **oldest first** and `_Draw._taken` stops two
orders claiming one physical copy. Already-shipped orders, being older, therefore took copies
**before** the live ones. Measured: **31 physical copies allocated to already-shipped orders**,
and three `Ready to Ship` lines reading `short` while their copies sat on the shelf —

```
SKU 9038187  ABE44-BD123 (Shipped - In Transit, 2026-08-31) took the copy
             49B84-6A2EC (Ready to Ship,        2026-09-06) 0 picks, `short`
SKU 9422329  51B75-E5DD4 (Shipped - In Transit, 2026-08-31) took it
             1EF4F-1A670 (Ready to Ship,        2026-09-07) 0 picks, `short`
SKU 9035516  7F569-38FDC (Shipped - In Transit, 2026-08-31) resolved
             92F83-8002B (Ready to Ship,        2026-09-05) wanted 3, got 1, `short`
```

After the stand-down: 14 open, and two of those three resolve. The third is a genuine shortfall
— two copies exist and three were bought.

**WHY THOSE 69 ARE NOT A FILL, WHICH IS THE TEMPTING ONE-MECHANISM ANSWER.** Many of them
shipped using copies **still sitting in the boxes as `identified`**, because the sale never went
through this store. A fill adds to `fulfilled`, so the count would read right while the card
stayed on the shelf, live, and got offered to the next buyer. The two acts are different
sentences and get different writers.

### The three ways, and what each one claims

| | writes | claims a copy went | reverses with |
|---|---|---|---|
| `record_pull` | `fulfilled` + `copies` | yes, and sells the card | `forget_pull`, by capture id |
| `record_fill` | `fulfilled` + `by_hand` | yes; there is no card to sell | `forget_fill`, by count |
| `close_line` | `closed_at` + `closed_reason` | **no** | `reopen_line` |

`FILL_REASONS` is `sealed` / `off_system` / `sold_separately`. `CLOSE_REASONS` is
`shipped_elsewhere` / `not_shipping`.
**`not_shipping` is deliberately on the stand-down and not the fill.**
A refund or a cancellation stops a line owing without anything going anywhere, and
closing it through `fulfilled` would put a shipment on record for one that never happened.

### The walk's own edge case, and the third fill reason

**The owner asked what happens when a copy is pulled ahead of time.** Three of the four answers
were already good: a card pulled physically but not recorded is still `identified`, so the walk
offers it and the record catches up; a copy recorded against another order refuses with
`CopyAlreadyPulled` and draws as spoken for; a re-shot copy reads as unseen and is named as an
honest limit in `store/orders.py`'s header. **The fourth is a trap**, and it was the same trap as
the unseen SKUs wearing a different reason code.

**Reproduced on the owner's store.** An order for 3 copies of `9018548`, resolved, 3 in box 3:

```
before                                wanted 3  picks 3  resolved           fulfilled 0
mark 3/650 sold on #/inventory
after                                 wanted 3  picks 2  short   on_hand 2  fulfilled 0
pull the two the walk still offers
end                                   wanted 3  picks 0  no_copies_on_hand  fulfilled 2, owed 1
```

**Open forever, with the third copy already in the envelope.** `#/inventory`'s sale does not
touch the ledger — D63 keeps them apart, rightly, because a sale is a fact about a card and a
fulfilment is a fact about an order — so nothing ever counted it. `no_copies_on_hand`'s remedy
*"Sold, retired or pooled — the counts beside this line say which"* is a dead end, and the first
build of this entry gated its presses to `sku_unseen` and `not_a_single`, so none was offered.

**`sold_separately` is the third fill reason and it is not `off_system`.** That word means this
store never photographed the card; this card it did, and the two want telling apart by whoever
reads the row later — one is a bookkeeping gap, the other a blind spot.

**`no_copies_on_hand` gets TWO presses, because it carries three truths.** `_reason`'s own
comment says so: this order's copy went out by the sale, another buyer took the last one, or it
was retired damaged. Only the operator knows which, so *"I already sent it"* fills and *"it
isn't shipping"* stands down, and neither is assumed.
**That press is also the only place `not_shipping` is reachable** —
without it, this entry's own change left a server capability no screen could reach, which is the
rule the entry cites.

**`short` is deliberately excluded.** While copies are on hand the remedy really is to pull
them, and a fill button there would invite closing a line whose cards are sitting in box 3.

### The stand-down has two scopes, and the per-line press uses the narrow one

**`Ledger.close_line` was line-shaped from the start; `POST /orders/close` was not.** So the
first build drew *"it isn't shipping"* only where the order had ONE line.
**A refunded line on a multi-line order therefore had no press at all** —
the order-shaped call would have closed lines
nobody answered for, which is worse than offering nothing. Named as a gap, then built on the
owner's word the same session.

**One route, two scopes, because only the scope differs.** `orders` stands every line of the
orders it names down — the backlog press. `lines` stands exactly the lines it names down. Both
call `close_line` and a second route would be two spellings of one write.
**A body carrying both refuses** as `close_scope_ambiguous` rather than picking one,
and a SKU the buyer did not order
refuses the whole press before any line moves — a stand-down aimed at a line that is not there
means the screen and the store disagree, and standing the others down would leave the operator
believing all of them went.

**Measured on a real 4-line order:** closing one line left the other three untouched, and the
order **stayed open** because it still owed them. That last part is the point — a stand-down
answers for a line, and `unfulfilled` asks about all of them.
T7 pins the mixed row that results — 2 pulled copies with their capture ids, 1 by hand,
`fulfilled` 3 — because a single count could not tell the operator that two are traceable to a
slot and one is only their word.

**THE INVARIANT IS `fulfilled == len(copies) + by_hand`**, maintained by four methods and
written by nothing else. `Ledger.progress_drift` reports any row where it fails and T7 asserts
that report is empty — because every reader downstream takes `fulfilled` alone and would be
just as confident about a number that had come apart.

### Where the operator's claim lives, and why it is not on the order record

**`ingest` replaces an `OrderRecord` wholesale on any content change** — `self.orders[key] =
record`. So a `kind` written onto the feed's copy survives exactly until the marketplace moves
the status string, at which point a sealed product silently becomes a single again and starts
sending the picker into the boxes after a playmat. That is the header's own argument for the
two-map split, in a second currency, so `kind` goes in the OURS half beside the counts.
T7 asserts it: a claim and a stand-down both survive a sync that moved `status` to
`Shipped - Delivered`.

**The feed still wins where it said anything at all.** `_engine_order` reads `line.kind or
declared_kind`. Reversed, one stale tick would outrank a marketplace that later learned to
classify its own products.

### The status proposes; it never decides

**The owner asked for the obvious shortcut** — *"upon import, close out all orders from the
import if they're not in ready to ship"* — and it is refused, for three reasons they accepted:

1. **`ingest` may not write fulfilment.** The two maps exist so it cannot, and the header says a
   careful merge inside `ingest` *"would be one refactor away from not working"*.
2. **`fulfilled` counts copies that went.** Writing it from a status claims pulls that never
   happened — on 42 lines whose SKU has no card record at all, a pull of a card that does not
   exist.
3. **"Not Ready to Ship" is an open-ended set.** The vocabulary was never published
   (`server/order_transport.py` argues it at length), so a `Cancelled` would be swallowed the
   day that word appears and recorded as handled.

So `BacklogPrompt` reads the statuses off what is open, **names them in its own sentence**, and
the operator presses.

**AND IT MATCHES THE POSITIVE, BECAUSE THE FIRST BUILD MADE THIS ENTRY'S OWN MISTAKE.**
`BacklogPrompt` shipped as `status !== 'Ready to Ship'` — reason 3 above,
written by hand one layer up from the server that refuses it. `app/tests/orders.spec.ts` fixes an
order at `Ready to ship` with a lower-case `s`, and the negative proposed that live order for a
bulk close on sight. It matches `startsWith('shipped')` on the folded string now and
**fails closed** — a status the rule does not recognise is left open. The two directions are not
symmetric — a shipped order left open is the status quo and is visible on screen, while a live
order swept into a bulk close is a card that never gets picked.
A spec pins it against `Cancelled`, `Pending`, `Awaiting Payment`, `ready to ship` and `""`. `make merge`'s bargain exactly: automate the lookup, never the decision.
**The complementary fix is at the door** — a standing status filter on the fetch, so shipped
orders never arrive — and it is separate work; a door filter cannot retroactively clear a
backlog, and a stand-down cannot stop the next import.

**AMENDED 2026-09-13 (`D63`): A FOURTH THING LANDED.** And it is not a fourth way to close a
line — the table three sections up is unchanged. A line still closes only by `record_pull`,
`record_fill` or `close_line`, and only two of those claim a copy went. `store/orders.py:
is_terminal_status` does not touch `fulfilled`, `copies`, `by_hand` or `closed_at` at all: it is
read in `server/capture_server.py:do_orders`, ahead of the ledger, to decide whether an order
belongs in `open_keys` in the first place. A Canceled or already-Shipped-or-Delivered order is
simply never presented as open and never enters the resolution pool — closer to the door filter
this entry names above as separate work than to a fourth member of the table, and it is exactly
that filter's RETROACTIVE half: it reaches orders already in the ledger, which a filter on the
fetch cannot.

**AND IT IS DELIBERATELY NARROWER THAN `BacklogPrompt`'s OWN RULE ABOVE.** That is not a
disagreement: `BacklogPrompt` matches `startsWith('shipped')` on the folded string, because it
is proposing a stand-down for a human to press — false-closed there is recoverable by leaving it
unticked. `is_terminal_status` is a server-side predicate that removes an order from the
resolution pool outright, so it recognises only the exact strings D63 published and measured —
`shipped - in transit`, `shipped - delivered`, `canceled` — and answers `False` for a bare
`Shipped` or any status it has never seen, the same fail-safe direction this entry's own
`BacklogPrompt` fix already argued for one register up. `Completed - Paid` is deliberately
outside both: ruling 3's backlog is a one-time reconcile of the owner's 513 orders at that
status, not an ongoing predicate either mechanism performs.

### What is reachable

`POST /orders/fill`, `POST /orders/line-kind` and `POST /orders/close`, each with a client
function and a control: the two line presses inside the reason banner of a `sku_unseen` or
`not_a_single` line — the two reasons whose remedy was otherwise a dead end — and the backlog
prompt above the list, where it can change the walk it is about rather than arriving after it.
All three carry an undo on the toast.

**A ROW THAT RECORDS NOTHING IS DROPPED.** `progress` creates on write, so the first build left
one all-default row per line behind a stand-down and its undo —
**measured at 80 rows from a single bulk close and undo** —
exactly the state `progress`'s docstring calls *"a row claiming a
pull that never happened"*. Every reversal now prunes.

**What would reopen this:** a refund that needs to be told apart from a cancellation, or a
`not_shipping` line that later ships after all. Both want a state on the line rather than a
reason string beside a stamp, and neither has happened yet.
