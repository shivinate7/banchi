## D-a-archive-press-priority — Sold value goes first, and sealed product is a named gap

**MEASURED AGAINST THE OWNER'S REAL STORE, 2026-09-19.** An unranked `archive sweep` over
914 SKUs answered for 206 of them before the host throttled it (D-a-archive-press-pace).
Only 37 of those 206 were SKUs the owner had ever actually sold. The owner's ten biggest
sellers by revenue answered zero out of ten. Every one of the ten is sealed product.
Together they total over $26,000, against $66,335 gross excluding canceled orders.

A pass that gets cut off should spend its requests on what the owner has actually sold.
`cards.select` has no declared order. An unranked pass spends its budget in whatever order
SQLite happens to return.

### The subject list is ranked by sold value, ties broken by SKU

`pipeline/pricearchive.py:revenue_by_sku` reads the order ledger directly. It sums
`unit_price * quantity` per SKU. It sums over every line of every order that is not
canceled. This is the same rule `app/src/Revenue.tsx:isCanceled` already draws the owner's
own Sales screen from (D214). Trimmed, case-folded, compared to `"canceled"`.

`rank_by_revenue` sorts a SKU list by that total, highest first. A SKU this ledger never
sold reads as zero. Ties among zeros break on the SKU string. Two runs over an unchanged
store then walk the same order. `rows_from_store` now returns its rows already in this
order. No caller needs a second sort.

### This ranking cannot reach sealed product, and that is a real, named gap

Sealed product is never captured. `pipeline/games.py` says so directly. It has no row in
`cards` and never will. `store/orders.py` says the same of a sealed Holiday Calendar's
fulfilment record. `rows_from_store`'s subject list is `cards.sku`, by
D219's own settled argument. No ranking of that list can put a SKU on
it that was never there.

This is the STALE premise to flag, not repeal. D219 argued the subject
is "the names the owner has sold or holds," read off `cards.sku`. That argument was right
about every SKU a physical card was ever photographed against. It did not anticipate that
the owner's highest-revenue SKUs would be ones with no photograph at all. Measured
2026-09-19: at least $26,000 of $66,335 gross sits entirely outside what this archive can
reach. That is over 39% of gross, and no ordering of the existing subject list can recover
it.

Widening the subject list to include order-ledger SKUs is not done here. `OrderLine`
carries `sku`, `name`, `number`, `printing` and `condition`. It carries no `set_name`. The
resolution path this archive already uses walks Product Line, then Set Name, then Number
or Name (`Market.product_id_for_row`). Guessing a sealed product's set from its name alone
is the guessing `CLAUDE.md` forbids for an identification.

Two fixes are proposed here, not built. `OrderLine` could gain a `set_name` the feed
already sends and this ledger currently drops. Or a separate, named resolver could be built
for sealed product, queued for review rather than guessed — the way D35 already queues an
unreadable number. Either is a schema or scope change past this task's fence. It needs the
owner's word before it is built.

### The coverage figure this ranking produces, honestly bounded

The reachable ceiling, singles only, is at most 61% of $66,335. That is about $40,335,
since the ten sealed sellers alone are 39% or more of gross. The real reachable total is
smaller once other sealed lines past the top ten are subtracted too. This worktree holds no
copy of the owner's real store. The exact figure is unmeasured from here. The ranked
press's own accounting (`archive show`) will report the true number the first time it runs
against the real store.

Within the reachable set, the ranking's own claim is stronger. Every single-card SKU with
sold revenue sorts before every SKU that has only ever sat on hand. D-a-archive-press-pace
measures the host tolerating a few hundred requests before a throttle. That budget
comfortably covers every revenue-bearing single first, given the owner's store holds 914
subjects and only a small fraction have ever sold.

### What this does not touch

`rows_from_store`'s SUBJECT SET is unchanged. It is still `cards.sku`, exactly as
D219 settled it. Only the ORDER those subjects are read in changes. No
SKU is added. No SKU is dropped. `chunk_rows` and the resume logic both depend on the
ranking being stable run to run. That is why ties break on the SKU string, rather than
being left to dict order.
