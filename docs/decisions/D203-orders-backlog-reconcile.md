## D203 — The two-year backlog is stood down by one press over a cutoff the operator sees, never by a rule that runs on every fetch

**The owner's ruling, 2026-09-13:** a ONE-TIME reconcile that marks today's stale open orders
fulfilled. A single explicit press with a preview and the count in its label — not a rule that
runs on every fetch.

**`Completed - Paid` cannot join `TERMINAL_STATUSES`, and that is the gap this fills.**
`store/orders.py:is_terminal_status`'s own docstring already says why: a marketplace's payment
clearing is not proof a card shipped, so treating that status as terminal on an ongoing basis
would close a live order the moment TCGplayer marks it paid, before anything has gone out.
Measured after D63's amendment narrowed `open` to exclude Canceled and Shipped/Delivered: 527
orders remain open, 513 of them `Completed - Paid` — two years of history that was fulfilled
through `#/inventory` before this screen existed — and 14 `Ready to Ship`, live work.

**The predicate is never the status string.** A candidate is an order that is OPEN (post-D63's
narrowing), has RECORDED NOTHING AT ALL against any of its lines — no pull, no hand-fill, on any
line — and was placed before a cutoff the operator sees before pressing. Zero-recorded is load
bearing: an order the operator has part-pulled is live work and must never be swept into a bulk
close alongside a two-year-old one. The 14 `Ready to Ship` orders also carry zero recorded
copies and are also open, so a naive cutoff could sweep them too — the guard against that is not
a hard-coded status exclusion (which would reintroduce the branching D114 already refused in the
client, one layer up) but the breakdown itself: the preview groups candidates by the feed's own
status string with counts, so a live order about to be swept is visible before the press.

**The write is `Ledger.close_line` with `CLOSE_SHIPPED_ELSEWHERE` and nothing else** —
`store/orders.py`'s own comment beside that constant is these 513 orders by name: *"it went out;
this store did not track it."* Not `record_fill`: many of them shipped using copies still
sitting in the boxes as `identified`, and a fill would claim a copy left while it stays on a
shelf offered to the next buyer. The stand-down claims no copy, touches no count, and the
physical reconcile is `#/inventory`'s job, unchanged.

**One route, `do_order_reconcile`, two bodies — `do_order_fetch`'s own shape**: `{preview: true,
cutoff?}` walks the same ledger and writes nothing; `{cutoff?}` performs it, closing every line
of every candidate inside one `Store().write()`. `cutoff` defaults to today (UTC date) and is
compared against the first ten characters of `placed_at`; an order with no `placed_at` is never
a candidate, because there is no date to test and the safe answer to an unknown one is no.

**Idempotent by construction, not by a guard.** Standing an order down removes it from `Ledger.unfulfilled()` (a closed line owes
nothing), so a second press over the same cutoff recomputes the identical predicate against a
ledger that no longer counts those orders as open, finds none, and reports it rather than
re-stamping anything.

**The reversal is the one D113 already built.** `reopenOrders` — `POST /orders/close` with
`undo: true` — puts a stood-down order back on the open list exactly as it was, which is why
this entry needed no new undo mechanism: the receipt this press draws hands the closed
`{source, number}` pairs to that existing call.

### Mechanized

`harness/tests/t7_store_and_seams.py` asserts: the preview writes nothing; a part-pulled order
is never a candidate; a terminal-status order is never a candidate; the press closes with
`shipped_elsewhere` and the inventory table is byte-identical before and after (no copy is ever
claimed); a second press over the same cutoff is a no-op and reports it; the reversal reopens.

### Not mechanized

Whether the operator reads the breakdown before pressing. The screen draws it above the button
and puts the count in the button's own label, and nothing here can make a person look — the same
limit `no-bandaids` and `D196` both name for a control that can be built right and still be
walked past.
