## D77 — Hand-pick from the catalog on any entry

**Any queue entry may be answered from the export on the owner's ask (`L`).** It is never offered unasked. The test for whether a person may overrule the pipeline cannot be "the pipeline offered nothing". It cannot, because a misread number joins a real key that belongs to a different card, confidently, with candidates on screen. `rarity_claim_mismatch` fires correctly there and the screen offered only the wrong card's rows.

- **The guard is unchanged and never depended on the candidate count.** `_answer_target` honors `from_catalog` for any entry, and it re-reads the SKU out of this card's own export inside the write lock (`_catalog_for_card`). The condition comes off that row and never off the request. A SKU the export does not carry refuses as `sku_not_in_catalog`. An answer without `from_catalog` may only name an offered row (`sku_not_a_candidate`). `GET /review/<box>/<index>/catalog` was never gated.
- **Nothing changes on arrival.** A card with rows gets no fetch and no panel, because a second looser list beside a good one teaches a screen to be skimmed. The export appears only after `L`.
- **One list at a time.** Both lists are answered on digits, so opening the export replaces the pipeline's rows, and Escape or `L` restores them. The digit handler reads `showCatalog`, the flag the renderer branches on, and not `candidates.length > 0`. The old read would mis-write silently: the operator presses `3` on the export's third row and the pipeline's third row, a different card, is recorded.
- **`from_catalog` on the history line carries no second condition.** It must record the case that matters most, a human overruling a confident offer.
- **The group route does not pass the flag.** A catalog row is found by a person looking at one photograph, and a group answer applies to cards nobody looks at individually.
- **`rarity_claim_mismatch` has its own sentence** in `ReviewQueue.tsx`'s `sentence()`. It is the one reason that can mean the candidate rows are the wrong card. It does not quote the rarities, since `QueueEntry` does not record `rarity_claim`.

Reopen if `from_catalog` lands on entries whose offered rows were right (fix the join upstream), or on entries with candidates at a rate that is not rare (fix the number read, D55).
