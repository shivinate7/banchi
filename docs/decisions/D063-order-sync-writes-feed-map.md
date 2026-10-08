## D63 — Order sync writes only the feed's map

**The order ledger (`store/orders.py`, one record per `{source}:{order_number}`) has two top-level maps.** `orders` is what the feed said and is replaced wholesale on every sync. `fulfilment` is what we did, and `ingest` cannot reach it. The resolver's answer (which copies fill a line) is recomputed on every read, because it is true of one snapshot (D36). An order happened outside this machine, cannot be re-derived, and is stored.

- **One record holding both is the defect.** Ingest replaces by key, so a fulfilment count inside it is destroyed on the next sync. The resolver then hands out a copy already in an envelope, and the same card is sold twice. A careful merge inside `ingest` was refused: "two maps, and this method touches one" is verifiable by reading, and "this merge preserves everything" needs a list of fields that grows. Two fields ride across an ingest, `first_seen` and `buyer`, because each is something a re-sync cannot recover.
- **Ingest writes no card state and no listing count.** The module holds no `Inventory` and imports nothing that does, so syncing twice is a no-op by construction. An unchanged re-ingest rewrites no bytes: `changed_at` is stamped only where the feed differs, and there is no `last_synced_at`. T7 asserts byte equality of `orders.json`, `inventory.json` and `history.jsonl`, since a row count goes green on a ledger that threw its fulfilment away.
- **`LineProgress.fulfilled` is a count and never a list of positions.** `LineProgress.copies` carries `capture_id`s, the one identity that survives a renumber: minted once per `POST /capture`, unique store-wide, and rewritten by no shift. A mid-box delete slides pulled copies down, so a ledger storing `["3/2", "3/3"]` would ship a card that was never pulled (T7 measures it). A re-shoot writes a new id, which is the honest limit.
- **No order state joins `master.STATES` and no history line is written.** `_state_before_sale` scans history for the last event whose name is in that tuple, so a new member makes reversals restore a card to a non-state. Ingest changes no card, so it has nothing to log.
- **`record_pull` validates everything, then writes everything (D29).** It refuses `CopyAlreadyPulled`, `CopyNotIdentifiable` (no `capture_id`), `OverFulfilled` (refused, never clamped, though `Ledger.over` reports a later ingest that reduced a quantity under a legitimate pull), `DuplicateOrderLine` (fulfilment is keyed by SKU, the one line identity stable across ingests, and summing loses which line was filled), `UnknownOrder`, `UnknownOrderLine` and `BadOrderKey` (the key splits on the first colon). The key folds case and strips to compare and is stored verbatim.
- **Nothing clears an order.** `status` is the feed's own word, verbatim. `Ledger.unfulfilled` answers which orders still owe copies from the two maps. On top of it, `store/orders.py:is_terminal_status` closes an order the feed calls Canceled or Shipped/Delivered, because a marketplace has answered what no pull record can contradict. It answers `False` for `None` and for any word outside its set. Recognizing too little leaves an order visible, and too much closes one that owes a copy, so the vocabulary grows only when the owner rules on a new word, never by substring. `do_orders` keeps a terminal order out of `open_keys`. `Completed - Paid` is absent on purpose, since a cleared payment says nothing about a shipment. The set is published here, and `make docs-audit`'s `terminal statuses` row reconciles it with `TERMINAL_STATUSES` exactly:

```terminal-statuses
canceled
shipped - in transit
shipped - delivered
```

- **The module imports nothing from `pipeline/`,** so `OrderLine` is declared twice, as `QueueEntry` is. `kind` is carried verbatim, because `pipeline/orders.py` owns `LINE_KINDS`. `parse` filters on `__annotations__` at all three levels, since a field written but not declared is silently dropped on reload.
- **No address, no email, no payment.** A buyer's display name is allowed, because a hand walking drawers per person needs one.
- **It does no i/o and holds no lock.** The fetch belongs to the caller, above the lock, because `files.exclusive` polls for up to 30 seconds while the feeder captures every 623 ms. T7 asserts it as an import check.

Reopen if a feed issues its own per-line id: a better key, worth a migration.
