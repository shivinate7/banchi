## DEBT49 — `_copies_out` and `_committed_keys` cost a full-table pass per call

`cli/resolve.py:_copies_out` walks every listing (492 on the owner's store) and runs `positions_for_sku` plus `copies_not_sold` per SKU. `store/rows.py:Rows.where` is a pass over the whole loaded table, so one `_copies_out` costs about a second and one `_committed_keys` about 0.75s. A route that calls either per run adds seconds to a reload: a per-run call once put 9.6s in front of every `#/pricing` reload, cut to 2.8s by folding the readings newest-per-SKU and calling once. `pricing.json`'s `add_to_quantity`, `committed` and `listing` are the join's own snapshot and `emit` never rewrites them, so any figure meaning "what can still go out" must re-derive against the live store on every read.

**Outcome at risk.** A slow `#/pricing` reload, or a figure that lies after the first `emit`.

**Closes when.** `Rows` gets a `sku` index. Until then a new caller calls once per request over the narrowed SKU set, never inside a per-run loop.
