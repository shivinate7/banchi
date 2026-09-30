## 24 — A zero reading cannot tell a sold-out listing from an import sitting in Staged

`cli/resolve.py:_copies_out` ages a stuck `pushed` claim by the SKU's sales where the export corroborates them. A reading of copies live vouches for every sale of the SKU, and a reading of nothing vouches for the sales taken before it (D150). A SKU whose import landed in TCGplayer's Staged channel and never went live also reads `Total Quantity` 0. A copy marked sold by hand against that state ages a claim it should not, and the next emit offers a copy of a row TCGplayer may already hold. `staged` is written only by `reconcile`, which the operator does not run, so the store cannot tell the two apart even afterwards. How often this happens is unmeasured.

**Outcome at risk.** A duplicate copy is listed on TCGplayer.

**Closes when.** A marker that a copy reached an import file exists (one field on `Card`, written by `cmd_emit`'s push loop beside the `sku` stamp, which is D59's named reopener), or `reconcile --live` runs routinely so `live` and `staged` become facts.
