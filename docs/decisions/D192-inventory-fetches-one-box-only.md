## D192 — Inventory fetches one box only

**Ruling: `#/inventory` fetches the box on screen, not the whole store.** This is the first step of the store-scaling plan. It reopens the refusal in the old `GET /boxes/<n>` comment in `server/capture_server.py`. That comment said a per-box read would be a second renderer for a caller that did not exist. The caller exists now. `#/inventory` fetched the whole store on every box switch and after every write.

### The route

- **`GET /inventory/<box>`** runs through `Inventory.records_in`. That method was already box-scoped and lazy (D88). `store/master.py` needed no change to serve one box. The new handler, `do_inventory_box`, applies the same decoration as `do_inventory`, narrowed to the rows `records_in` returns. It reuses `asdict(card)`, so the two routes cannot drift on what a `Card` serializes to.
- **`GET /inventory` stays.** No screen this item touches calls it. The owner asked for it to stay.

**Corruption refusal is not box-scoped (a known gap).** `records_in` calls `Inventory._positions_in(box)` before it builds anything. That function refuses "anywhere in the store". Its second pass runs an unscoped query for any record whose `box` or `idx` will not coerce. So one corrupt record anywhere makes `BadPosition` escape the per-box route, for every box asked about. `do_inventory` does not have this problem. It has a per-record `continue` and never calls `_positions_in`. Fixing `_positions_in` is out of scope here. The module's own rule keeps `records_in`, `_positions_in` and `_Places` unrefactored. It is a named follow-up. The O(cards-in-box) claim rests on the row-building query, `self.cards.where(box=box)`, which is box-scoped. A healthy store never reaches the refusal. T7's `check_inventory_box_route` covers the healthy case and the corruption case. The corruption case asserts the refusal, not isolation.

### `store/rows.py` degrade: fixed at the cause

`Rows.where()` and `Rows.select()` gate their source query on `not self._complete`. That part is correct. The final filter, after the gate, scanned all of `self._loaded` every time. So a handler that forced a full load (`to_payload()`, `.values()`, `.items()`) made every later scoped call pay an O(table) scan, not the index.

The first fix tracked `_touched`, the keys this session wrote through `Rows.__setitem__`. It trusted the source's index for every other row. That is wrong. `Rows`'s own docstring supports a caller that reads an object back and mutates its attributes. That pattern is common. `store/master.py:set_state`, `record_identification`, and `store/submissions.py:release` and `attach_run` all mutate in place and never reassign through `__setitem__`. `_touched` cannot see those writes. The draft made `where()` and `select()` return a stale verdict for such rows for the rest of the session. It broke `submission-selftest.py`'s `case_resume_releases_only_its_own`. `release()`'s in-place `claim.state = STATE_RELEASED` was invisible to a same-session `where(state=LIVE)`, so a resumed run's own stale claim still read as live.

**The fix that holds.** Each key the source's indexed query returns is re-validated against the live object, when one is loaded. The source row is never trusted, and neither is `_touched`. The work is bounded by what the source query returns, not by the table. `_touched` is still consulted, narrowed to brand-new rows that the source cannot offer, because they are not on disk yet. `store/submissions.py:release` and `attach_run` now reassign through `self.entries[claim.receipt] = claim` after they mutate. That matches every other mutator, and `_touched` is real bookkeeping that other callers may rely on.

**Known limitation, pinned by a T7 case.** A row whose indexed column is mutated in place, and never reassigned, into a new match is still missed. The source query never offers that row as a candidate. For this item's own columns (`box` and `idx`), no current mutator causes it. `move_card` reassigns through `__setitem__`, and the tombstone never changes `box` or `idx`. So `do_inventory_box` is not exposed today. The gap is real for other indexed columns, `state` and `sku` among them. A caller could reintroduce it by querying right after an in-place change to the same column in one session. No call site does that today. `check_rows_scoped_after_full_load`'s pinned `not` assertion goes red the day a caller relies on the fix.

### Client

- `#/inventory` (`BoxBrowse.tsx`) calls `getInventoryBox` for the box on screen. It re-fetches on every shelf switch and every reload trigger: a sale, a retirement, a re-shoot, or a box operation.
- The cross-box search ranking (`order`, `shelves`, `matchesByShelf`) moved off the box's own `rows`. Those rows no longer hold every box's cards. The ranking now reads the search's own `SearchCopy` result, which already carries `place.box` and `place.section`.
- **Home's hero deck** uses a lean route, not a narrower DTO. A narrower `GET /inventory/recent` would return `{key, box, index, cid, name}`. `Home.tsx:deckFromCards` also reads `name`, `number_display`, `number` and the finish claim (`metadata_finish`). A smaller second renderer of the same object is the mistake the goal text warns against. So `do_inventory_recent` reuses `do_inventory` and `do_inventory_box`'s decoration over the few candidates that survive the filter. It reads from `Inventory.newest_captured`, `Rows.top` and `SqliteSource.top`.

### The recent query needed a schema bump

The first `SqliteSource.top` ran `ORDER BY captured_at DESC LIMIT ?`. `captured_at` was not in `_INDEXES`. `EXPLAIN QUERY PLAN` read `SCAN cards` and `USE TEMP B-TREE FOR ORDER BY`, the O(store) cost this route exists to avoid. Adding the column to `_INDEXES` does not fix an existing store. `_ensure_schema` runs that loop only on a brand-new store. A store already stamped at a schema version takes the `_repair` path, which returns before reaching the loop. So the index would be missing on every store made before this change, including the owner's.

The fix is a schema bump to **6**. Schema 6 is reserved for the search index (Phase 2). The branch that reaches the bump first keeps it, and the other branch renumbers. This step is Phase 1, so it takes 6. `_add_captured_at_index` is the upgrade step in `store/db.py`. It is additive and idempotent, like every step beside it. After the fix, `EXPLAIN QUERY PLAN` reads `SEARCH cards USING INDEX cards_captured_at (captured_at>?)`.

### Fulfillment and Orders stay on `getInventory()`

The plan named two call sites. Neither matched the plan on checking.

- **`Fulfillment.tsx`.** Order resolution never called `getInventory()`. `GET /orders` already resolves each open order's lines to picks, with their own place and capture id. The one real call site is the store-wide sellable browse. That is the fallback for "no order in hand" (D5 and D6). It is store-wide by design, so it stays on `getInventory()`. The call site is documented in place.
- **`Orders.tsx`.** "Walk the boxes" uses `answer.lines[].picks` from `GET /orders`, and never reads the card map. Its one real call site is `indexStore`. That widens each order line's copy map to every on-hand copy of the SKU, including copies in far boxes that no resolver pick names (`copiesOf`'s own comment). Scoping that to the boxes an order names would hide legitimate copies in unnamed boxes. That is a correctness regression, not only a slower screen. It stays on `getInventory()`. It is a named debt, for the `do_orders` rebuild or a lean "on-hand copies by SKU, store-wide" route.

### Measurements

On a copy of the owner's real store, duplicated 20 times: `GET /inventory` took about 78 ms at 1x and 1,485 ms at 20x. Only the two debts above still call it. `GET /inventory/<box>` stayed flat across both copies, at the about 4 ms `records_in` measured. `Rows.where()` after a forced full load dropped from an O(table) scan to the indexed query's own cost. Exact figures live in the change's PR body, because the recipe's numbers change with the store.

### Amendment: a store with no boxes

This item left a gap. `BoxBrowse.tsx`'s shelf-selecting effect returns when `shelves.length === 0`. On a store with no boxes, `shelf` never leaves `null`. The box-scoped fetch is gated on a numeric shelf, so it never fires. `rows` and `failure` both stay `null`. The screen's lede branches only on those two, so it showed "Reading the inventory…" with nothing left to answer it. The owner's store already had boxes, so this item never gave the case a path. The fix reads `boxesAnswered`, the one registry signal that arrives regardless of `shelves`, together with an empty box registry. Once both hold, it swaps the loading branch for an empty state.
