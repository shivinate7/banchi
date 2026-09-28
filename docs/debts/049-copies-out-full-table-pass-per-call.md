## DEBT49 — `_copies_out` and `_committed_keys` cost a full-table pass per call

`cli/resolve.py:_copies_out` walks every listing — 492 on the owner's store. It runs
`positions_for_sku` plus `copies_not_sold`, per SKU. `store/rows.py:Rows.where` is a pass
over the whole loaded table, on every call. So one `_copies_out` costs roughly 0.9-1.2s. One
`_committed_keys` costs roughly 0.75s.

A route that calls either per-run, rather than once, adds real seconds to a reload. PR #284
(2026-09-11) hit this directly. A per-run call put 9.6s in front of every `#/pricing`
reload. Folding the readings newest-per-SKU, and calling once, brought that down to 2.8s.

Also still true: `pricing.json`'s `add_to_quantity`/`committed`/`listing` fields are the
JOIN's own snapshot, from whenever it last ran. `emit` never rewrites them. Any screen figure
claiming "what can still go out" must re-derive against the live store, on every read. Or it
lies, from the moment after the first `emit`.

**Not built:** a `sku` index on `Rows`. That index is the named fix for the underlying cost.
Until it lands, any new caller of `_copies_out`/`_committed_keys` must call it once per
request. It must run over the narrowed set of SKUs in hand, never inside a per-run loop.
