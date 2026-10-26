## DEBT-unhold-death-gap — a death between an Unhold's receipt write and its store commit leaves the mark without the change

**`send_routes._unhold` and `send_routes._rehold` write the receipt's `unheld` inside the store write, before the commit.** A failed commit puts the old `unheld` back (`send_routes._receipt_undone_on_failure`, under the store's lock). Two cases are not covered. The process dies between the receipt write and the commit. Or the put-back fails too, for instance on the same disk error.

- **Result:** the receipt keeps `unheld`, and the listing keeps `held_copies` and `pushed`. The next live check (`send_routes._hold_removed`) sets `held_copies` to the snapshot's judged figure, which the receipt's `unheld` lowers (`send_routes._sku_snapshot`). The count clears. The Pricing row draws its Unhold control only while `held_copies > 0`, so no control is left for those copies. A Re-hold that dies the same way leaves the receipt without its mark over copies the store already holds.
- **Safe side:** `pushed` stays high, so the worklist does not offer the copies. They are never sent twice. They stay off the list.
- **Not fixed because** receipts are JSON files and the store is SQLite, so one transaction over both is not cheap, and the gap needs a process death or a second disk error inside one press. Its frequency is unmeasured. `send_routes.do_take_back` writes its receipt before the store commit too, and this follows that order.
- **Closes when** the receipt and the store are written in one transaction, or a startup pass reconciles a receipt's `unheld` against the listing.
- **Points to** D273 (one press sends listings live), R-S4.

**Outcome at risk.** Copies stay off the list with no control on screen to restore them. Nothing is sent twice.
