## D113 — A line closes three ways

**Before this, an order line could not be closed when the store had never seen its SKU.** The owner found orders they could not close. Their reading was right. The cause was larger than those three orders.

**`record_pull` was the only writer of `fulfilled`, and it requires a `capture_id`.** That requirement is correct. A pull moves a card this store holds. An unidentifiable one is a double shipment waiting to happen. But a sealed Holiday Calendar has no card record and never will. Neither does a single that shipped from a pile this rig never photographed. Such a line could not be closed at all. There was no CLI path, no route and no control. `Ledger.unfulfilled` is `quantity - fulfilled`, so the order stayed open forever.

**The storage model had anticipated this, and nothing had written it.** `LineProgress`'s docstring says `fulfilled` is a subset of the count, not a second spelling of it. It may exceed `len(copies)` when a copy is recorded without a `capture_id`. This entry is the writer that docstring was waiting for.

### What was measured, and why there are two mechanisms

**First reading: 20 orders, 3 open, all three unclosable.** A Pokemon Holiday Calendar 2025 ($77.99, sealed), a One Piece Double Pack Set (x2, sealed), and a Riftbound *Lonely Poro (Overnumbered)* `#221/219` at **$404.44**. The last is a real single that the store has never photographed. No card carries those SKUs, no listing record does either, and the store holds no card named `Poro` and none numbered `221/219`.

**Second reading: the store moved during the build.** A fetch ran mid-build. The second reading had 100 orders: 68 `Shipped - In Transit`, 18 `Shipped - Delivered`, 14 `Ready to Ship`. **83 were open, and 69 of those 83 were orders TCGplayer had already shipped.**

**That was a correctness bug, not noise, and it is the strongest finding here.** `pipeline/orders.py:resolve_all` walks open orders oldest first. `_Draw._taken` stops two orders from claiming one physical copy. So already-shipped orders, being older, took copies before the live ones. **31 physical copies were allocated to already-shipped orders.** Three `Ready to Ship` lines read `short` while their copies sat on the shelf:

```
SKU 9038187  ABE44-BD123 (Shipped - In Transit) took the copy
             49B84-6A2EC (Ready to Ship)        0 picks, `short`
SKU 9422329  51B75-E5DD4 (Shipped - In Transit) took it
             1EF4F-1A670 (Ready to Ship)        0 picks, `short`
SKU 9035516  7F569-38FDC (Shipped - In Transit) resolved
             92F83-8002B (Ready to Ship)        wanted 3, got 1, `short`
```

After the stand-down, 14 lines were open, and two of those three resolve. The third is a genuine shortfall: two copies exist and three were bought.

**Why the 69 are not a fill.** Many of them shipped using copies still sitting in the boxes as `identified`, because the sale never went through this store. A fill adds to `fulfilled`. The count would then read right while the card stayed on the shelf, live, and got offered to the next buyer. The two acts are different sentences, so they get different writers.

### The three ways, and what each claims

| | writes | claims a copy went | reverses with |
|---|---|---|---|
| `record_pull` | `fulfilled` + `copies` | yes, and sells the card | `forget_pull`, by capture id |
| `record_fill` | `fulfilled` + `by_hand` | yes; there is no card to sell | `forget_fill`, by count |
| `close_line` | `closed_at` + `closed_reason` | **no** | `reopen_line` |

`FILL_REASONS` is `sealed` / `off_system` / `sold_separately`. `CLOSE_REASONS` is `shipped_elsewhere` / `not_shipping`.

**`not_shipping` is on the stand-down, not the fill.** A refund or cancellation stops a line owing without anything going anywhere. Closing it through `fulfilled` would put a shipment on record for one that never happened.

### The walk's edge case, and the third fill reason

The walk offers a copy pulled ahead of time. Three of the four cases were already handled. A card pulled physically but not recorded is still `identified`, so the walk offers it, and the record catches up. A copy recorded against another order refuses with `CopyAlreadyPulled` and draws as spoken for. A re-shot copy reads as unseen, and `store/orders.py`'s header names that as an honest limit. The fourth case was a trap. It was the same trap as the unseen SKUs, with a different reason code.

**Reproduced on the owner's store.** An order for 3 copies of `9018548`, resolved, with 3 copies in box 3:

```
before                                wanted 3  picks 3  resolved           fulfilled 0
mark 3/650 sold on #/inventory
after                                 wanted 3  picks 2  short   on_hand 2  fulfilled 0
pull the two the walk still offers
end                                   wanted 3  picks 0  no_copies_on_hand  fulfilled 2, owed 1
```

The line stayed open with the third copy already in the envelope. `#/inventory`'s sale does not touch the ledger. D63 keeps them apart, rightly, because a sale is a fact about a card. A fulfilment is a fact about an order, so nothing counted it. `no_copies_on_hand`'s remedy, "Sold, retired or pooled — the counts beside this line say which", was a dead end. The first build gated its presses to `sku_unseen` and `not_a_single`, so none was offered there.

**`sold_separately` is the third fill reason, and it is not `off_system`.** `off_system` means that this store never photographed the card. `sold_separately` means that it did. The two need telling apart by whoever reads the row later. One is a bookkeeping gap. The other is a blind spot.

**`no_copies_on_hand` gets two presses, because it carries three truths.** `_reason`'s own comment lists them. This order's copy went out by the sale. Another buyer took the last one. Or it was retired damaged. Only the operator knows which. So "I already sent it" fills, and "it is not shipping" stands down. Neither is assumed. That second press is the only place `not_shipping` is reachable. Without it, this entry's own change would leave a server capability that no screen could reach.

**`short` is deliberately excluded.** While copies are on hand, the remedy is to pull them. A fill button there would invite closing a line whose cards sit in box 3.

### The stand-down has two scopes

`Ledger.close_line` was line-shaped from the start. `POST /orders/close` was not. So the first build offered "it is not shipping" only where the order had one line. A refunded line on a multi-line order had no press at all. The order-shaped call would have closed lines nobody answered for, which is worse than offering nothing. The gap was named, then built in the same session.

**One route, two scopes, because only the scope differs.** `orders` stands every line of the orders it names down. This is the backlog press. `lines` stands exactly the lines it names down. Both call `close_line`. A second route would be two spellings of one write. **A body carrying both refuses** as `close_scope_ambiguous` rather than picking one. A SKU the buyer did not order refuses the whole press before any line moves. A stand-down aimed at a line that is not there means that the screen and the store disagree. Standing the others down would leave the operator believing all of them went.

**Measured on a real 4-line order:** closing one line left the other three untouched. The order stayed open, because it still owed them. A stand-down answers for a line, and `unfulfilled` asks about all of them. T7 pins the mixed row that results: 2 pulled copies with their capture ids, 1 by hand, and `fulfilled` 3. A single count could not show that two are traceable to a slot and one is only the operator's word.

**The invariant is `fulfilled == len(copies) + by_hand`.** Four methods maintain it, and nothing else writes it. `Ledger.progress_drift` reports any row where it fails. T7 asserts that the report is empty. Every reader downstream takes `fulfilled` alone, so a number that had come apart would still be trusted.

### Where the operator's claim lives

`ingest` replaces an `OrderRecord` wholesale on any content change (`self.orders[key] = record`). So a `kind` written onto the feed's copy survives only until the marketplace moves the status string. At that point a sealed product silently becomes a single again. The picker is then sent into the boxes after a playmat. This is the header's own argument for the two-map split, in another form. So `kind` goes in the OURS half, beside the counts. T7 asserts it: a claim and a stand-down both survive a sync that moved `status` to `Shipped - Delivered`.

**The feed still wins where it said anything at all.** `_engine_order` reads `line.kind or declared_kind`. Reversed, one stale tick would outrank a marketplace that later learned to classify its own products.

### The status proposes. It never decides.

The operator asked to close every order in the import that was not ready to ship. The request was refused, for three reasons:

1. **`ingest` may not write fulfilment.** The two maps exist so it cannot. The header says a careful merge inside `ingest` "would be one refactor away from not working".
2. **`fulfilled` counts copies that went.** Writing it from a status would claim pulls that never happened. On 42 lines whose SKU has no card record at all, that is a pull of a card that does not exist.
3. **"Not Ready to Ship" is an open-ended set.** The vocabulary was never published (`server/order_transport.py` argues it at length). So a `Cancelled` would be swallowed the day that word appears, and recorded as handled.

So `BacklogPrompt` reads the statuses off what is open, **names them in its own sentence**, and the operator presses.

**It matches the positive.** The first build made this entry's own mistake. `BacklogPrompt` shipped as `status !== 'Ready to Ship'`, which is reason 3 written by hand one layer up from the server that refuses it. `app/tests/orders.spec.ts` fixes an order at `Ready to ship` with a lower-case `s`. The negative proposed that live order for a bulk close on sight. The rule now matches `startsWith('shipped')` on the folded string, and **fails closed**. A status the rule does not recognise is left open. The two directions are not symmetric. A shipped order left open is the status quo, and it is visible on screen. A live order swept into a bulk close is a card that never gets picked. A spec pins the rule against `Cancelled`, `Pending`, `Awaiting Payment`, `ready to ship` and `""`. This is `make merge`'s bargain exactly: automate the lookup, never the decision.

**The complementary fix is at the door.** It is a standing status filter on the fetch, so shipped orders never arrive. That is separate work. A door filter cannot clear a backlog retroactively, and a stand-down cannot stop the next import.

**The fourth thing: `is_terminal_status` (D63).** It is not a fourth way to close a line. The table above is unchanged. A line still closes only by `record_pull`, `record_fill` or `close_line`, and only two of those claim a copy went. `store/orders.py:is_terminal_status` does not touch `fulfilled`, `copies`, `by_hand` or `closed_at`. `server/capture_server.py:do_orders` reads it, ahead of the ledger, to decide whether an order belongs in `open_keys` at all. A Canceled or already-Shipped-or-Delivered order is never presented as open, so it never enters the resolution pool. It is closer to the door filter named above than to a fourth member of the table. It is that filter's retroactive half: it reaches orders already in the ledger, which a fetch filter cannot.

It is deliberately narrower than `BacklogPrompt`'s rule. `BacklogPrompt` proposes a stand-down for a human to press, so a false close there is recoverable by leaving it unticked. `is_terminal_status` is a server predicate that removes an order from the pool outright. So it recognises only the exact strings D63 published and measured: `shipped - in transit`, `shipped - delivered`, and `canceled`. It answers `False` for a bare `Shipped` or any status it has never seen. That is the same fail-safe direction, one layer down. `Completed - Paid` is outside both rules on purpose. The 513-order backlog at that status is a one-time reconcile. Neither predicate performs it.

### What is reachable

`POST /orders/fill`, `POST /orders/line-kind` and `POST /orders/close` each have a client function and a control. The two line presses sit inside the reason banner of a `sku_unseen` or `not_a_single` line. Those are the two reasons whose remedy was otherwise a dead end. The backlog prompt sits above the list, where it can change the walk it is about rather than arriving after it. All three carry an undo on the toast.

**A row that records nothing is dropped.** `progress` creates on write. The first build left one all-default row per line behind a stand-down and its undo. That is the state `progress`'s docstring calls "a row claiming a pull that never happened". This was measured at 80 rows from one bulk close and undo. Every reversal now prunes.

**What would reopen this:** a refund that must be told apart from a cancellation, or a `not_shipping` line that later ships after all. Both want a state on the line, not a reason string beside a stamp. Neither has happened yet.
