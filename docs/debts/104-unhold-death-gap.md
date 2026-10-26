## DEBT104 — a death between an Unhold's receipt write and its store commit leaves the mark without the change

**`send_routes._unhold` and `send_routes._rehold` write the receipt's `unheld` inside the store write, before the commit.** A failed commit puts the old `unheld` back (`send_routes._receipt_undone_on_failure`, under the store's lock). Three cases are not covered. The process dies between the receipt write and the commit. The put-back fails too, for instance on the same disk error (it writes a `log_note` line). Or a writer lands between the store's lock release and the put-back.

- **Unhold, result:** the receipt keeps `unheld`, and the listing keeps `held_copies` and `pushed`. The next live check (`send_routes._hold_removed`) sets `held_copies` to the snapshot's judged figure, which the receipt's `unheld` lowers (`send_routes._sku_snapshot`). The count clears. The Pricing row draws its Unhold control only while `held_copies > 0`, so no control is left for those copies.
- **Re-hold, result:** a death before COMMIT leaves the receipt's `unheld` lowered and the store un-re-held. `pushed` stays low and `held_copies` stays 0, so the worklist offers the copies again.
- **Safe side, both:** nothing is sent twice. Unhold: `pushed` stays high, so the worklist does not offer the copies. Re-hold: the copies left TCGplayer by hand (that is why they were held), so offering them lists each one once.
- **Put-back gap:** between the lock release and the put-back, a Take Back reads the receipt with the mark still on it, so it offers fewer copies. That fails safe: the copies stay off the list.
- **Not fixed because** receipts are JSON files and the store is SQLite, so one transaction over both is not cheap, and the gap needs a process death or a second disk error inside one press. Its frequency is unmeasured. `send_routes.do_take_back` writes its receipt before the store commit too, and this follows that order.
- **Closes when** the receipt and the store are written in one transaction, or a startup pass reconciles a receipt's `unheld` against the listing.
- **Replaces** DEBT87, which this change narrowed. A slug entry stands in for it because re-adding a numbered record trips the numbered-record audit.
- **Points to** D273 (one press sends listings live), R-S4.

**Outcome at risk.** After an Unhold gap, copies stay off the list with no control on screen to restore them. After a Re-hold gap, copies the owner meant to hold are offered. Nothing is sent twice.
