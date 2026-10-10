### T3 — Join coverage

For a batch of identified cards, every card matches exactly one fixture row for its resolved condition string. Report unmatched in **both** directions before any output is written.

Required cases:
- Secret rares where the number exceeds the denominator (`161/159`)
- Blank-`Number` rows (name-matching fallback)
- Names with apostrophes and ampersands (`Billy & O'Nare`)
- 7 identical cards → one row, `Add to Quantity` = 4, 3 recorded as backstock
- Multi-set key collisions: a key that maps to rows in two `Set Name`s resolves by the sidecar set hint. Without the hint, it reviews as `set_ambiguous`. Non-colliding keys are left untouched.
- The condition scope (D137): against a WIDE export, one carrying Lightly Played through Damaged, the catalog holds only this game's Near Mint strings and `Unopened`. No number loses a finish. A number stocked in one finish resolves `catalog_forced` rather than queueing. Asserted against the wide fixtures on purpose. The Near-Mint-only `SOURCE_FIXTURE` cannot see this rule. It was green through the ten days the real catalog carried every grade.

- **Pass**: zero unmatched, or every unmatched card reported both ways and routed to a standing queue with its position, before any output is written

Output is **not** suppressed by a non-empty queue (batch script v2 §5.6). An unresolved card sits at a known position in a box. It is not lost, and it is not urgent. Holding 400 good cards hostage to 7 ambiguous ones is the wrong trade. The pass criterion requires that the report and the queue file both exist *before* the emitter writes anything. A card may leave the pipeline unlisted, never unrecorded. `emit_import` enforces it by refusing to write while any unmatched card has not been routed.

- **The live cap is covered as a QUANTITY as of 2026-08-30 (D59), and the block that guards it had been pinning the defect.** `_check_committed_from_counts` is where the store's per-SKU counts become `SkuMatch.committed_positions`. Three of its assertions were holding `room = live_cap - live_before - len(committed_positions)` in place. That expression was wrong three ways at once. It is RUN-SCOPED against a GLOBAL cap, so a SKU split across two boxes had its cap enforced once per box. It counts a copy that has SOLD, which TCGplayer decremented on the sale and `live_before` had therefore already subtracted. And it reads `pushed`, which has no drawdown, so once an import landed the same copies were subtracted a second time. The cap is now measured against one quantity. That quantity is `cli/resolve.py:_copies_out`, `min(live + pushed + staged, max(live, copies not sold))`. The same number is what `_committed_keys` spends on positions.

  **What the three cases assert instead.** Six copies with three live commit **three** positions, add **one** and leave **two** backstock. The old shape committed none, added one, and called five of the six copies backstock. Yet three of them were for sale. Seven copies with one **sold**, against a `Total Quantity` of zero, offer **four**. A card in the post may not shrink what its SKU is allowed to list.

  **Observed failing first, under TWO separate mutations, because one reversal only exercises half of it.** Restoring the old `room` expression to `pipeline/join.py` takes the add-one, backstock-two and departed-copy cases red. Restoring `_committed_keys` to spend `pushed + staged` alone takes the live-commits-its-own-copies case red, and backstock-two with it. That one goes red under EITHER mutation, which is what a double-count looks like when it is read from both ends. The fix moved `live` out of `add_to_quantity` and into `_copies_out`. So a single reversal leaves the other half green. It reads as coverage it is not.

  **The measurements the change was found by.** 167 copies across 72 SKUs were standing at `pushed` on the owner's store, with `staged` and `live` both zero. They came from an import that landed under an operator who does not run `reconcile`. 83 rows across 64 SKUs would have been handed straight back to the import file by one `reconcile` forward. The reason: no copy TCGplayer had actually LISTED was ever marked held.
