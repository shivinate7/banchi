## D192 — The inventory route reads one box, and `rows.py` stops re-walking what it already loaded

Item 2 of `docs/specs/store-scaling.md`'s §3 plan. Reopens the refusal at
`server/capture_server.py`'s old `GET /boxes/<n>` comment — "a per-box read would be a second
renderer for one caller that does not exist yet" — because the caller exists now: `#/inventory`
is a real screen fetching the whole store on every box switch and after every write.

**`GET /inventory/<box>`, through `Inventory.records_in`.** `records_in` already existed and
was already box-scoped and lazy (D88) — nothing in `store/master.py` needed to change to serve
one box's cards. The new route (`do_inventory_box`) is the same decoration `do_inventory`
already does, narrowed to the rows `records_in` returns, reusing `asdict(card)` so the two
routes can never drift on what a `Card` serialises to. `GET /inventory` itself is **kept**,
unused by any screen this item touches, on the owner's word recorded in
`docs/specs/store-scaling/00-phases.md`.

**Verified against the tree, correcting the playbook this item was built from.** The new
route's refusal is NOT box-scoped, and an earlier draft of `do_inventory_box`'s docstring said
the opposite. `records_in` calls `Inventory._positions_in(box)` before building anything,
and that function's own docstring says its refusal fires "ANYWHERE in the store" — its second
pass (`self.cards.select(("box","idx"), box=None)` / `idx=None`) is a genuinely unscoped query
for any record whose box or index will not coerce, the same rule
`next_index`/`allocate_capture` have always had. So a single corrupt record anywhere in the
store still raises `BadPosition` out of the new per-box route too, for every box asked about —
a real regression against `do_inventory`'s own per-record `continue`-and-keep-going, which
never calls `_positions_in` at all. Fixing `_positions_in` itself is out of scope for this item
(the playbook's own "Do not touch" section is explicit that
`records_in`/`_positions_in`/`_Places` are not refactored here) and is named as a follow-up
rather than folded into this diff. What IS box-scoped, and what the route's O(cards-in-box)
claim actually rests on, is the row-BUILDING query, `self.cards.where(box=box)` — a healthy
store never touches the refusal at all, which is the case T7's `check_inventory_box_route`
exercises; the corruption case is exercised too, asserting the refusal rather than isolation.

**`store/rows.py`'s degrade, fixed at the cause — and fixed twice, since the first fix was wrong.**
`Rows.where()`/`Rows.select()` already gated their SOURCE query on
`not self._complete`, correctly — but the FINAL filter, after that gate, scanned all of
`self._loaded` unconditionally, so any handler that had already forced a full load in the
same session (`to_payload()`, `.values()`, `.items()`) made every LATER scoped call in that
session pay an O(table) Python scan instead of the index.

The first draft tracked `_touched` — the keys this session had itself written through
`Rows.__setitem__` — and trusted the source's own index for every other row.
**That is wrong for this codebase, on the class's own documented terms.** `Rows`'s own
docstring states that a caller which reads an object back and mutates its attributes directly
is a SUPPORTED way to write ("a caller that got an object back and mutated it is writing to
the same object the flush will read"), and this pattern is pervasive —
`store/master.py:set_state`, `record_identification`, and `store/submissions.py:release`/
`attach_run` all mutate in place and never reassign through `__setitem__`. `_touched` cannot
see any of those writes, so the first draft made `where()`/`select()` answer a STALE verdict
for such a row for the rest of the session. This was not theoretical: it broke
`submission-selftest.py`'s `case_resume_releases_only_its_own` for real — `release()`'s
in-place `claim.state = STATE_RELEASED` was invisible to a same-session `where(state=LIVE)`
moments later, so a resumed run's own stale claim was reported as still live.

**The fix that actually holds**: every key the source's own indexed query returns as a
candidate is re-validated against the LIVE object when one is already loaded — never trusted
from the source's row, and never trusted from `_touched` either — bounded by what the source
query itself returns rather than by the table. `_touched` is still consulted, narrower now:
only for a brand-new row this session created (`allocate_capture`'s kind of write), which the
source cannot offer as a candidate at all because it does not exist on disk yet.
`store/submissions.py:release`/`attach_run` were also corrected to reassign through
`self.entries[claim.receipt] = claim` after mutating, both for symmetry with every other
mutator in this codebase and because `_touched` is real bookkeeping other callers may come to
rely on.

**A known limitation this fix does not close, pinned by a T7 case rather than rediscovered.**
A row whose indexed column is mutated in
place — never reassigned — INTO a new match, while its on-disk value would not have matched,
is still missed: the source query never offers it as a candidate, so nothing here can pull it
in. Verified against the actual call graph for this item's own subject (`box`/`idx`): every
existing box mutator either reassigns through `__setitem__` (`move_card`'s transplant) or
never changes `box`/`idx` at all (its tombstone), so `do_inventory_box`'s own correctness is
not exposed to this gap today. It is a real, general gap for other indexed columns
(`state`, `sku`) that a future caller could reintroduce by querying immediately after an
in-place mutation of the same column within one session — no call site does that today, and
`check_rows_scoped_after_full_load`'s pinned `not` assertion is what would go red the day one
tries to rely on it working.

**Client: `#/inventory` (`BoxBrowse.tsx`) no longer fetches the whole store.**
`getInventoryBox` replaces `getInventory` for the box on screen, re-fetched on every shelf
switch and on every reload trigger (a sale, a retire, a re-shoot, a box op). The cross-box
search ranking (`order`, `shelves`, `matchesByShelf`) moved off the box's own `rows` — which
no longer holds every box's cards — onto the search's own `SearchCopy` result, which already
carries `place.box`/`place.section`.

**Home's hero deck got a real lean route rather than a narrower DTO.** The playbook's first
sketch for `GET /inventory/recent` returned `{key, box, index, cid, name}` — too narrow, since
`Home.tsx:deckFromCards` reads `name`, `number_display`, `number` and the finish claim
(`metadata_finish`) too. Rebuilding a second, smaller renderer of the same object is exactly
the "second renderer" mistake this item's own goal text warns against, so
`do_inventory_recent` reuses `do_inventory`/`do_inventory_box`'s own decoration verbatim over
the handful of candidates that survive the filter, off a new
`Inventory.newest_captured`/`Rows.top`/`SqliteSource.top`.

**AND THAT QUERY WAS NOT ACTUALLY INDEXED UNTIL A SECOND FIX, CAUGHT ON REVIEW.** The first
`SqliteSource.top` ran `ORDER BY captured_at DESC LIMIT ?` while `captured_at` was absent from
`_INDEXES` — `EXPLAIN QUERY PLAN` on it read `SCAN cards` / `USE TEMP B-TREE FOR ORDER BY`,
the exact O(store) cost this route exists to avoid. Adding the column to `_INDEXES` alone does
not fix an EXISTING store: `_ensure_schema` only runs that loop on a brand-new store's own
branch, and every store already stamped at a schema version takes the `_repair` path and
returns before reaching it — so the index would never have existed on any store that predates
this change, the owner's real one included. The real fix is a schema bump to **6** — reserved
for item 8 by `docs/specs/store-scaling/00-phases.md`, whose own text says the branch that
reaches it FIRST keeps it and the other renumbers; this item is Phase 1 and item 8 is Phase 2,
so by that ordering this item is first. `_add_captured_at_index` is the upgrade step
(`store/db.py`), additive and idempotent like every step beside it. Re-verified after the fix:
`EXPLAIN QUERY PLAN` now reads `SEARCH cards USING INDEX cards_captured_at (captured_at>?)`.

**Fulfillment.tsx and Orders.tsx: one call site each, and neither matches the playbook.** It
described Fulfillment.tsx as having two uses of `getInventory()` — an order-resolution use and
a store-wide browse — and Orders.tsx as having a "Walk the boxes" cross-order walk on
`getInventory()` too.

**Verified against the tree: Fulfillment.tsx's order resolution never called `getInventory()`.**
`GET /orders` already resolves every open order's lines to picks carrying their own
place and capture id — so its one real call site is the store-wide
sellable browse (D5/D6's "no order in hand" fallback), which is genuinely store-wide by
design and left on `getInventory()`, documented in place, matching the playbook's own
permitted option for exactly this shape of gap.

**Orders.tsx's "Walk the boxes" is built entirely from `answer.lines[].picks`** — the
resolver's own already-resolved rows off `GET /orders` — and never touches the card map at
all. Its one actual call site (`indexStore`) is a widening of each order line's copy map to
"every on-hand copy of that SKU the store holds, including copies in far boxes no resolver
pick names" (`copiesOf`'s own comment) — a feature that cannot be safely scoped to "the boxes
an order names" without silently hiding legitimate copies sitting in un-named boxes, which is
a correctness regression and not merely a slower screen. Both are left on `getInventory()`,
documented in place as a named debt for item 6's `do_orders` rebuild or a future lean
"on-hand copies by SKU, store-wide" route — not attempted under this item's own budget, per
the same "fix the cause, don't band-aid it" reasoning the plan already applies to
Fulfillment's browse.

**Measured** (`.backup` copy of the owner's real store, 20x duplicated): `GET /inventory`
unchanged at roughly 78 ms / 1,485 ms (nothing calls it any more except the two documented
debts above); `GET /inventory/<box>` flat across both copies, matching `records_in`'s own
measured ~4 ms; `Rows.where()` after a forced full load drops from an O(table) Python scan to
the indexed query's own cost. Exact figures are in the PR body rather than this entry, since
the `.backup`-copy recipe's numbers are perishable and this entry is not.
