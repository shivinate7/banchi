## DEBT87 — an Unhold whose store write fails leaves copies off the list with no control

**`send_routes._unhold` writes the receipt before the store, so a failed store write splits the two records.** The receipt keeps `unheld`. The listing keeps `held_copies` and `pushed`, and neither is lowered.

- **Result:** the next live check (`send_routes._hold_removed`) sets `held_copies` to the snapshot's judged figure, when the snapshot can judge the SKU. The receipt's `unheld` lowers that figure (`send_routes._sku_snapshot`), so the count clears. The Pricing row draws its Unhold control only while `held_copies > 0`, so no control is left for those copies.
- **Safe side:** `pushed` stays high, so the worklist does not offer the copies. They are never sent twice. They stay off the list.
- **Not fixed because** the failure needs a store write error between the two writes. Its frequency is unmeasured. `send_routes.do_take_back` writes its receipt before the store commit too, and this follows that order.
- **Closes when** the receipt and the store are written in one transaction.
- **Points to** D273 (one press sends listings live), R-S4.

**Outcome at risk.** Copies stay off the list with no control on screen to restore them. Nothing is sent twice.
