# Item 4 — `_copies_out` as one pass

This is one of the eight item files under `docs/specs/store-scaling/`, described by
`00-phases.md`. Read that file's "Phase 1" section first if you have it; this file is
self-contained regardless. Your only write for this item is `cli/resolve.py` — one
rewritten function (`_copies_out`) and one new private helper beside it. Do not touch
`docs/specs/store-scaling.md`, `CLAUDE.md`, `store/rows.py`, `store/db.py`,
`store/master.py`, or `pipeline/join.py` for this item. A possible, NOT required, second
touch to `server/pipeline_routes.py` is discussed under "Allowlist entries removed" below
— read that section before deciding whether to take it.

## Goal and done-when

**Goal:** `cli/resolve.py:_copies_out` (def at line 487) currently calls
`Inventory.positions_for_sku` and `Inventory.copies_not_sold` once per listing the store
holds (2–3 times per listing, once each for `positions_for_sku`, `copies_not_sold`'s own
internal `positions_for_sku` call, and — on the `read <= 0` branch — `sales_before`'s own
internal `positions_for_sku` call). Measured at 0.9 s over 492 listings
(D156, restated in `server/pipeline_routes.py:2306-2308`) and
projected as the plan's single largest per-request cost at 50,000 cards
(`docs/specs/store-scaling.md` §0, §1's table row). Rewrite it to read every card's
SKU-relevant columns in ONE `Rows.select()` call, grouped into an in-memory dict keyed by
SKU, then do the per-listing arithmetic over that dict — O(cards + listings) instead of
O(listings × cards) — while returning byte-identical `(copies_out, live_now)` dicts for
every input this repo's tests already exercise.

**Done when:**
1. `_copies_out`'s signature, return type and every caller's call site are unchanged
   (`cli/resolve.py:1916`, `server/pipeline_routes.py:2405`) — this is an internal rewrite,
   not an API change.
2. `harness/tests/t7_store_and_seams.py`'s `check_committed_copies_are_the_oldest` (starts
   line 16547) and `check_listing_commands` (starts line 16705) pass unmodified, including
   the direct call `resolve._copies_out(inventory, {})` at line 16655.
3. `harness/tests/t3_join_coverage.py`'s `_check_committed_from_counts` (line 448) passes
   unmodified — this is the "six copies, three live, offers 3 uncapped" case CLAUDE.md's D7
   section names.
4. A new equivalence test (this file's "Tests" section, part A below) asserts the rewritten
   function's output equals a reference implementation (the OLD per-listing code, kept only
   inside the test) over a store built to exercise every branch: a SKU with `read > 0`, a
   SKU with `read <= 0` and a sale before `read_at`, a SKU with `read <= 0` and a sale after
   `read_at`, a SKU present in `live_by_sku` but absent from `inventory.listings`, and a SKU
   present in `inventory.listings` but absent from `live_by_sku`.
5. The `.backup`-copy measurement (this file's "Measure" section) shows the in-repo ~0.9 s
   figure collapsing to tens of milliseconds on the same store, and the 20x-row copy's
   ratio is close to 1.0× rather than ~20× (flat against store size, the same shape item 3's
   `events_at` measurement proves for a different table).

## Depends on / conflicts with

- **Depends on nothing.** This is Phase 1 in `00-phases.md`, which runs as four PRs in
  parallel worktrees against disjoint functions. This item's row in that file's grid:
  `cli/resolve.py: resolve.py:_copies_out and its two helpers` — everything else in that
  row is blank for item 4.
- **No conflict with item 2** (`Inventory.to_payload()` / `do_orders()`'s `_Places`) — that
  item touches `server/capture_server.py` and `store/rows.py`'s `_complete` fallback path;
  this item touches neither. It does, however, matter to READ: item 2's fix to
  `store/rows.py:177`'s degradation is a *different* mechanism from the one this item's
  rewrite avoids — see "Read first" below for why both are real and why fixing one does not
  fix the other.
- **No conflict with item 3** (`Store.history()` scoped to the key) — different table
  (`events`, not `cards`/`listings`), confirmed mutually in `docs/specs/store-scaling/
  03-history.md`'s own "Depends on / conflicts with" section, which names this item and
  says the same thing from its side.
- **No conflict with item 5** (the `readings` writer, PR #333) — different file
  (`cli/cmd_join.py`/`cmd_reconcile.py`, not `cli/resolve.py`'s `_copies_out`).
- **Item 7** (`do_pipeline_value`, `box_views`, `_release_plan`) reopens
  `cli/resolve.py:box_views` (line 372) — a different function in the same file. If item 7
  is developed concurrently, both PRs touch `cli/resolve.py` but not the same lines
  (`box_views` is lines 372–426; `_copies_out` and its new helper are placed just above it,
  lines ~487–560 after this rewrite — confirm no overlap by diffing line ranges before
  merging either).
- **If run concurrently with any branch editing `cli/resolve.py` lines 429–735** (the
  `LiveReading`/`_live_by_sku`/`_copies_out`/`_oldest_first`/`_committed_keys` block), check
  `git log --oneline -5 -- cli/resolve.py` and `make coordinator` before starting.

## Read first

- `docs/specs/store-scaling.md` §0 (the one-paragraph diagnosis), §1's table row for
  `_copies_out`, §2's bullet ("`docs/DEBTS.md`'s `_copies_out` entry names the wrong fix"),
  and §3 item 4's own paragraph. **§2's claim needs a correction — read it here before
  trusting it**: `docs/DEBTS.md` was grepped for `_copies_out` (`grep -n "_copies_out"
  docs/DEBTS.md`) and its only hit is section 24 (`## 24 — A zero reading cannot tell a
  sold-out listing from an import sitting in Staged`, starts line 2045), which is about an
  ARITHMETIC ambiguity (D150/D147) and says nothing about an index or a cost. There is no
  paragraph anywhere in `docs/DEBTS.md` today asking for a `sku` index on `Rows`, or naming
  any fix for this function's performance at all. So §2's "the entry names the wrong fix" is
  not verifiable against the file as it stands — either that paragraph was removed by a
  branch that merged between the plan being written and this item opening, or the plan's
  author was thinking of `store-scaling.md` §0 itself (which *is* precise: "`cli/resolve.py:
  _copies_out` calls `positions_for_sku` and `copies_not_sold` once per listing... which at
  50,000 cards with proportional listings is the single largest figure in the plan") and
  misattributed it to DEBTS.md in the summary bullet. Either way: **do not go looking for a
  DEBTS.md paragraph to edit — there is none to correct.** If a future session's `make
  docs-audit` or a stale grep turns one up, the corrected text is: *the `cards_sku` index
  exists (`store/db.py:135`, generated from the `("cards", "sku")` tuple in `_INDEXES` at
  line 135 via the `CREATE INDEX IF NOT EXISTS {table}_{column}` loop at line 272); `Inventory.
  positions_for_sku`'s `self.cards.where(sku=sku)` already uses it. What defeats the index is
  not its absence — it is `store/rows.py`'s `where()`/`select()` re-filtering the ENTIRE
  currently-loaded `_loaded` cache on every call (see below), which grows across the
  ~492–753 calls one `_copies_out` invocation makes. The fix is one pass over the table, not
  a second index.*
- `CLAUDE.md`'s D7, D86 and D156 paragraphs (already quoted to you in full) — D156's own
  decision file, D156, is the actual source of the "0.9s per call on 492 listings, two queries
  each" figure that `server/pipeline_routes.py:2306-2308` restates in a docstring, and that
  `docs/specs/store-scaling.md`'s §1 table (753 listings, a later/different store snapshot)
  restates again with a slightly different count. Both figures describe the same defect;
  the count differs because the store grew between measurements.
- `cli/resolve.py:487-648` — `_copies_out` itself, read in full. The arithmetic you must
  preserve exactly is documented inline in its own docstring (lines 490-524, 554-648) and
  is NOT to be simplified, re-derived, or "cleaned up" beyond what this file's Steps
  section specifies — every comment in that function is there because a wrong version of
  this arithmetic shipped once and cost real money (see the "BRANCH" comment at line
  575-583 and the D59/D87/D115/D147/D150 cross-references throughout). Two call shapes to
  note precisely:
  - Lines 642-646, when `read > 0`:
    ```python
    sold = (
        len(inventory.positions_for_sku(sku)) - len(inventory.copies_not_sold(sku))
        if read > 0
        else inventory.sales_before(sku, read_at)
    )
    ```
    `positions_for_sku(sku)` returns every card carrying this SKU in any state;
    `copies_not_sold(sku)` returns every card carrying this SKU whose state is not `SOLD`
    (`store/master.py:2421`: `return [c for c in self.positions_for_sku(sku) if c.state !=
    SOLD]`) — so the subtraction is exactly "how many of this SKU's cards are SOLD," computed
    by calling `positions_for_sku` TWICE for the same SKU (once directly, once again inside
    `copies_not_sold`).
  - When `read <= 0`, `sales_before(sku, read_at)` (`store/master.py:2423-2447`) calls
    `positions_for_sku(sku)` a third way and counts cards where `card.state == SOLD and
    master.newer_stamp(as_of, card.state_at) is True` — i.e. sold strictly before the
    reading at `read_at`.
- `store/master.py:2366-2447` — `positions_for_sku`, `copies_not_sold`, `sales_before` in
  full, already read above; their bodies are quoted precisely so you can verify the
  replacement dict-based logic below reproduces them exactly. **Do not edit these three
  methods** — they have other callers (`pipeline/orders.py:454`,
  `server/capture_server.py:7986`, and every T7 case listed in "Do not touch" below) that
  must keep working exactly as they do today; this item only stops `_copies_out` from
  calling them in a loop.
- `store/rows.py:213-260` — `Rows.where(**equals)` and `Rows.select(columns, **equals)` in
  full. **This is the actual mechanism, and it is subtler than "the store was already
  materialised":**
  ```python
  def where(self, **equals) -> List[Any]:
      if not self._complete:
          for key, text in self.source.where(equals):
              key = str(key)
              if key in self._deleted or key in self._loaded:
                  continue
              self._remember(key, text)
      found = {
          key: obj for key, obj in self._loaded.items() if self._matches(obj, equals)
      }
      return [found[key] for key in sorted(found)]
  ```
  The `if not self._complete:` block runs one real indexed SQL query
  (`SELECT key, payload FROM cards WHERE sku = ? ORDER BY key`, via `store/db.py:1065-1069`,
  which hits the `cards_sku` index) and calls `_remember` on each returned row — which
  parses it into a `Card` object and inserts it into `self._loaded` (`store/rows.py:118-125`).
  **The line that actually costs O(cards) is the one after that block**: `found = {key:
  obj for key, obj in self._loaded.items() if self._matches(obj, equals)}` runs
  UNCONDITIONALLY, filtering over the WHOLE current `_loaded` dict, not just the rows the
  SQL query just fetched — because a previously-loaded object may have been mutated in
  memory since it was read, so its columns have to be re-derived from the live object
  rather than trusted from the stale row. `_loaded` never shrinks within one snapshot's
  lifetime (only `flush()`/`flushed()` touch it, and a lock-free `Store().read()` snapshot
  is never flushed), and every one of `_copies_out`'s three per-SKU calls (`positions_for_
  sku`, and `copies_not_sold`/`sales_before`'s own re-calls) POPULATES `_loaded` with every
  card sharing that SKU. Across ~492 distinct SKUs, most of the store's cards end up in
  `_loaded` well before the loop finishes, so the LATER calls' `found = {...}` line is a
  near-full-table Python scan even though the SQL half of the SAME call stays a fast
  indexed lookup throughout. This is why `_complete` can remain `False` the whole time (item
  2's fix, which stops `where`/`select` from degrading once `_complete` becomes `True`
  elsewhere in a request, does not touch this) and the cost is still O(listings × cards):
  the compounding happens inside `where()`/`select()` themselves, independent of the
  `_complete` flag. One full-table `select()` avoids this entirely because it is called
  exactly once and its own object-free path (below) never touches `_loaded` at all.
  `select()` (`store/rows.py:231-250`) has the identical shape one level down — same `if not
  self._complete:` SQL branch, same unconditional `for key, obj in self._loaded.items(): if
  self._matches(...)` tail — except it does NOT call `_remember`, so it builds no `Card`
  objects and never writes into `_loaded` at all. That is the path this rewrite uses: one
  `select()` call with NO cards already loaded first, so its SQL half returns everything and
  its Python tail (over an empty or near-empty `_loaded`) costs nothing.
- `store/db.py:1071-1080` (`Source.select`) — confirms `select(columns, equals)` issues
  `SELECT key, {columns} FROM cards {WHERE...} ORDER BY key` and returns `(key, tuple)`
  pairs with no payload parse, no `Card` construction — the cheapest read this store offers,
  the same one `Inventory.counts()` (`store/master.py:2374-2378`) and `next_index`'s
  high-water scan already rely on.
- `store/master.py:2480-2489` — the `CARDS` `TableSpec`, confirming the indexed column names
  are `box`, `idx` (not `index`), `state`, `sku`, `capture_id`, `name`, `number`, `game`,
  `set_hint`, `run`, `captured_at`, `state_at`, `cid` — `select()` must name these exact
  column strings, e.g. `select(("sku", "state", "box", "idx", "captured_at", "state_at"))`.
- `store/db.py:130-141` — confirms `("cards", "sku")` is in `_INDEXES`, so `cards_sku` is a
  real B-tree index (auto-named `{table}_{column}` at line 272), and it is what
  `positions_for_sku`'s existing `.where(sku=sku)` already hits on its SQL half — the index
  was never the problem.
- `cli/resolve.py:676-732` — `_committed_keys`, the function immediately below
  `_copies_out`. It has the IDENTICAL per-listing shape this item fixes
  (`for sku, out in copies_out.items(): for card in _oldest_first(inventory.copies_on_hand
  (sku))[:out]: ...`, line 729-731 — `copies_on_hand` calls `positions_for_sku` internally)
  and is NOT part of this item's scope. See "Do not touch" and "Risks" below — flag it,
  do not fix it here.
- `cli/resolve.py:1889-1923` — the tail of `_resolve` (the shared body of `load` and
  `load_from_store`, NOT a function literally named `_join_common` — confirm the name with
  `grep -n "^def _resolve" cli/resolve.py` before writing anything that refers to it by
  name), which is `_copies_out`'s first caller: `copies_out, live_now = _copies_out(
  snapshot.inventory, _live_by_sku(parsed, ...))` at line 1916, called once per `join`/`emit`
  invocation (there is no loop here).
- `server/pipeline_routes.py:2283-2426` — `_unsent_ledger` in full, `_copies_out`'s second
  caller at line 2405 (`held_out, live_out = run_resolve._copies_out(inventory, readings)`),
  called exactly once per `_unsent_ledger` invocation, which is itself called exactly once
  per `do_pipeline_worklist` request (line 2642: `ledger = _unsent_ledger(snapshot.inventory,
  tables)` — one call site, not a loop). Read lines 2364-2374 too (the `distinct("sku")`
  orphan scan immediately before it) — see "Allowlist entries removed" for why this matters.
- `docs/specs/store-scaling/01-guard.md` — the (not-yet-landed-as-of-this-writing, but
  Phase-0-first per `00-phases.md`) `unscoped walk` guard. Read its `UNSCOPED_WALK_ALLOWED`
  frozenset (that file's own lines ~94-108) and its scanner's `select` rule (`elif func.attr
  == "select" and _cards_chain(func.value) and not node.keywords:` — flags a `select()` call
  ONLY when it carries literally zero keyword arguments, static-AST, per file). Two facts
  from it matter here and are load-bearing for the next section:
  1. `cli/resolve.py` **is** inside the guard's scanned roots (`_UNSCOPED_WALK_SINGLE_FILES`
     names it explicitly, alongside `store/master.py`) — a new filter-less `select()` you
     add to this file WILL be flagged if the guard has landed by the time this item merges.
  2. `("server/pipeline_routes.py", "_unsent_ledger", "distinct")` is one of the 12 pinned
     `UNSCOPED_WALK_ALLOWED` tuples, and `store-scaling.md` §4's table credits removing it
     to "item 4" (this item). `00-phases.md`'s Phase-1 allowlist table repeats that credit
     ("item 4: `_unsent_ledger`", target count 10). **This item's own file-touch grid entry
     in `00-phases.md` lists only `cli/resolve.py` for item 4** — no `server/
     pipeline_routes.py` column. These two things disagree; resolve it per "Allowlist
     entries removed" below rather than picking one silently.

## Steps

### 1. Add a small row type and the one-pass grouping helper, above `_copies_out`

Insert immediately before `_copies_out`'s definition (before line 487), after `_live_by_sku`
ends (line 484):

```python
class _SkuCardRow(NamedTuple):
    """The handful of a card's indexed columns `_copies_out` (and nothing else, yet) needs,
    read without building a `Card` object at all (`Rows.select`, `store/rows.py:231-250`).

    `key` and `box`/`index` are carried even though `_copies_out` itself does not read them,
    because this is the SAME shape `_committed_keys` (`cli/resolve.py:676-732`) and
    `_unsent_ledger`'s orphan scan (`server/pipeline_routes.py:2364-2374`) would need if
    either is ever rewritten onto this helper — see this item's "Allowlist entries removed"
    section for whether that happens in this PR or a later one. Carrying two extra columns
    the current caller does not read costs nothing extra: `select()` reads them off the
    same row in the same query.
    """

    key: str
    state: str
    box: object
    index: object
    captured_at: Optional[str]
    state_at: Optional[str]


def _cards_by_sku(inventory: master.Inventory) -> Dict[str, List[_SkuCardRow]]:
    """Every card's SKU, state and position, in ONE pass, grouped by SKU.

    THIS REPLACES O(listings) REPEATED `Inventory.positions_for_sku` CALLS WITH ONE
    `Rows.select()`. `_copies_out` used to call `positions_for_sku`/`copies_not_sold`/
    `sales_before` — each a `Rows.where(sku=sku)` — 2 to 3 times per listing; measured at
    0.9s over 492 listings (D156). The SQL half of each call was
    already an indexed lookup (`cards_sku`, `store/db.py:135`) and always has been — the
    cost is `Rows.where`'s own closing filter (`store/rows.py:213-229`), which re-scans the
    ENTIRE `_loaded` cache on every call regardless of whether the SQL half found the row via
    the index, and `_loaded` grows with every SKU this loop has already visited. One
    `select()` with no filter touches the underlying table exactly once and — unlike
    `where()` — never writes into `_loaded` at all (`store/rows.py:231-250` builds no `Card`
    objects), so its own cost is a single SQL scan plus one Python pass over the result,
    O(cards), done once rather than once per listing.

    A CARD WITH NO SKU IS EXCLUDED, matching every caller this replaces: `positions_for_sku`
    filters on `sku=sku` and a query for `sku=None` (never issued by `_copies_out`, which
    only ever asks about real SKUs) would not reach these rows anyway; the check here keeps
    the returned dict's keys exactly the set of real, non-empty SKUs the store holds.
    """
    grouped: Dict[str, List[_SkuCardRow]] = {}
    for key, (sku, state, box, index, captured_at, state_at) in inventory.cards.select(
        ("sku", "state", "box", "idx", "captured_at", "state_at")
    ):
        if not sku:
            continue
        grouped.setdefault(str(sku), []).append(
            _SkuCardRow(key, state, box, index, captured_at, state_at)
        )
    return grouped
```

Confirm `NamedTuple`, `Dict`, `List`, `Optional` are already imported (they are — line 31).

### 2. Rewrite `_copies_out` to build the dict once and read it per listing

Replace the body from line 525 (`out: Dict[str, int] = {}`) through line 648 (`return out,
live_now`) — keep the docstring (lines 490-524, 554-648's inline comments) exactly as they
are; only the arithmetic body changes:

```python
def _copies_out(
    inventory: master.Inventory, live_by_sku: Mapping[str, LiveReading]
) -> Tuple[Dict[str, int], Dict[str, int]]:
    """... (docstring unchanged — see Steps §2 above) ..."""
    by_sku = _cards_by_sku(inventory)
    out: Dict[str, int] = {}
    live_now: Dict[str, int] = {}
    for sku in set(live_by_sku) | set(inventory.listings):
        entry = inventory.listings.get(sku)
        reading = live_by_sku.get(sku)
        offered = reading.quantity if reading else None
        as_of = reading.as_of if reading else None
        read = (
            entry.live_reading(offered, as_of)
            if entry is not None
            else (reading.quantity if reading else 0)
        )
        read = max(0, int(read))
        live = max(0, read - (entry.sales_pending(as_of) if entry is not None else 0))
        live_now[sku] = live
        claim = entry.held if entry is not None else 0
        if read <= 0 and claim <= 0:
            continue
        read_at = entry.reading_taken_at(offered, as_of) if entry is not None else as_of
        # THE SAME TWO ARMS `positions_for_sku`/`copies_not_sold`/`sales_before` COMPUTED,
        # over the shared one-pass dict instead of three separate per-SKU store reads.
        rows = by_sku.get(sku, ())
        if read > 0:
            # `len(positions_for_sku(sku)) - len(copies_not_sold(sku))` — every row of this
            # SKU that is SOLD, without building either list twice.
            sold = sum(1 for row in rows if row.state == master.SOLD)
        else:
            # `sales_before(sku, read_at)` exactly: SOLD, and strictly before the reading.
            sold = sum(
                1
                for row in rows
                if row.state == master.SOLD
                and master.newer_stamp(read_at, row.state_at) is True
            )
        out[sku] = max(live, claim - sold)
    return out, live_now
```

Nothing above the `by_sku = _cards_by_sku(inventory)` line and nothing in the `for sku in
set(live_by_sku) | set(inventory.listings):` loop's first eleven lines (through `if read <=
0 and claim <= 0: continue`) changes at all — this is the SAME code, character for
character, as the original lines 527-574; only the `sold = ...` computation and everything
after it is rewritten. Do not touch `Listing.live_reading`, `.sales_pending`, `.held`, or
`.reading_taken_at` (`store/master.py:939-1062`) — none of them read `inventory.cards` and
none of them are part of this cost.

### 3. Confirm the docstring's own claims still hold, word for word

The docstring (lines 490-524, plus every inline comment from 554-648) describes the
ARITHMETIC, not the implementation shape, and nothing about the arithmetic changed — only
where the three counts (`len(positions_for_sku)`, `len(copies_not_sold)`,
`sales_before`) come from. Re-read the docstring once after the rewrite and confirm every
sentence in it is still literally true of the new body (it should be, since the rewrite is a
mechanical substitution) — if any sentence now describes a call that no longer exists (e.g.
"`copies_not_sold` is what says so"), either rephrase that one sentence to name the dict
instead, or leave it if it is describing the RULE rather than the CALL (most of them are).

## Call sites (complete)

Grepped: `grep -rn "_copies_out" --include='*.py' .` across the whole tree. Every
non-comment, non-docstring hit:

1. `cli/resolve.py:1916` — `copies_out, live_now = _copies_out(snapshot.inventory,
   _live_by_sku(parsed, {...}))`, inside `_resolve` (the shared tail of `load`/
   `load_from_store`, cli/resolve.py:1864-1929). Called ONCE per `join`/`emit` invocation —
   confirmed by `cli/cmd_join.py:347` and `cli/cmd_join.py:363` (`resolve.load(...)` /
   `resolve.load_from_store(...)`, one call each) and `cli/cmd_emit.py:466` (`resolve.load(
   ...)`, one call). Signature and return type unchanged by this item; no edit needed here.
2. `server/pipeline_routes.py:2405` — `held_out, live_out = run_resolve._copies_out(
   inventory, readings)`, inside `_unsent_ledger` (`server/pipeline_routes.py:2283-2426`).
   Called ONCE per `_unsent_ledger` invocation, which is itself called ONCE per
   `do_pipeline_worklist` request (`server/pipeline_routes.py:2642`, the only call site of
   `_unsent_ledger` in the tree). No edit needed here either, UNLESS you take the optional
   `_unsent_ledger` refactor described below.
3. `harness/tests/t7_store_and_seams.py:16655` — `copies_out, _ = resolve._copies_out(
   inventory, {})`, a direct test call inside `check_committed_copies_are_the_oldest`
   (starts line 16547). Not a production caller; must keep passing (see "Tests").

**Corrections to the task's own assumption**: `pipeline/join.py:prices_for` (line 2666),
`cli/cmd_emit.py`, and `cli/cmd_reprice.py` do **not** call `_copies_out` directly — grepped
and confirmed. `prices_for` reads the `SkuMatch` objects `_resolve`'s join loop already
built (which carry `copies_out`/`live_out` as attributes, populated once from this
function's return values) rather than calling this function itself; `emit` reaches
`_copies_out` only transitively, through `resolve.load`/`load_from_store`'s single call
(item 1 above); and `reprice` (`cli/cmd_reprice.py`) reads `inventory/prices.json` and the
live export directly (D86/D100) and never calls into `cli/resolve.py`'s join machinery at
all. So there are exactly TWO real call sites in production code, both already calling this
function once per request — the "call it once per request, never per run" rule from the
`copies-out-is-a-full-table-pass.md` memory note is already honoured by both callers today,
and this item does not change call FREQUENCY, only each call's own cost. That memory note's
"~1s per call on the owner's store" figure is what this item makes stale — after this
change, expect the same call to cost tens of milliseconds; the "once per request" half of
the note remains correct and does not need updating.

## Tests (T7 check + assertions; mutation arm)

### A. Functional equivalence — the one-pass answer equals the old per-listing answer

Add a new check function to `harness/tests/t7_store_and_seams.py`, near
`check_committed_copies_are_the_oldest` (line 16547) — same "COMMITTED COPIES" section, or
its own new `checks.note("COPIES OUT — one pass equals the old per-listing arithmetic")`
block immediately after it:

```python
def _copies_out_reference(
    inventory: master.Inventory, live_by_sku: Mapping[str, "resolve.LiveReading"]
) -> Tuple[Dict[str, int], Dict[str, int]]:
    """THE OLD PER-LISTING IMPLEMENTATION, KEPT HERE ONLY, as the equivalence oracle for
    `check_copies_out_one_pass_matches_reference` below. Never import this into `cli/`;
    it exists so a future edit to `_copies_out`'s one-pass body can be checked against the
    arithmetic it must never silently drift from. Copied verbatim from `cli/resolve.py`
    before the item-4 rewrite (docs/specs/store-scaling/04-copies-out.md), with only the
    module prefix (`resolve.` instead of a bare `master`) adjusted for this file's imports.
    """
    out: Dict[str, int] = {}
    live_now: Dict[str, int] = {}
    for sku in set(live_by_sku) | set(inventory.listings):
        entry = inventory.listings.get(sku)
        reading = live_by_sku.get(sku)
        offered = reading.quantity if reading else None
        as_of = reading.as_of if reading else None
        read = (
            entry.live_reading(offered, as_of)
            if entry is not None
            else (reading.quantity if reading else 0)
        )
        read = max(0, int(read))
        live = max(0, read - (entry.sales_pending(as_of) if entry is not None else 0))
        live_now[sku] = live
        claim = entry.held if entry is not None else 0
        if read <= 0 and claim <= 0:
            continue
        read_at = entry.reading_taken_at(offered, as_of) if entry is not None else as_of
        sold = (
            len(inventory.positions_for_sku(sku)) - len(inventory.copies_not_sold(sku))
            if read > 0
            else inventory.sales_before(sku, read_at)
        )
        out[sku] = max(live, claim - sold)
    return out, live_now


def check_copies_out_one_pass_matches_reference(checks: Checks) -> None:
    """`resolve._copies_out`'s one-pass rewrite (item 4,
    docs/specs/store-scaling/04-copies-out.md) must equal the per-listing arithmetic it
    replaced, on a store exercising every branch: `read > 0` with a sale, `read <= 0` with a
    sale before AND after `read_at`, a SKU only in `live_by_sku`, a SKU only in
    `inventory.listings`, and a SKU with no cards at all (a stray export row for a SKU this
    store never captured).
    """
    checks.note("")
    checks.note("COPIES OUT — one pass equals the old per-listing arithmetic")

    with isolated_home():
        # SKU A: read > 0, one sold, one not — exercises the `read > 0` branch.
        for box, idx in ((1, 1), (1, 2)):
            capture_server.do_capture(capture_payload(box))
        with Store().write() as writable:
            writable.inventory.get(master.position_key(1, 1)).sku = "SKU-A"
            writable.inventory.get(master.position_key(1, 2)).sku = "SKU-A"
        capture_server.do_mark_sold(1, 1, {})

        # SKU B: read <= 0, one sale before `read_at`, one after — exercises both arms of
        # the `read <= 0` branch. `state_at` ordering is what `sales_before` reads.
        for box, idx in ((2, 1), (2, 2)):
            capture_server.do_capture(capture_payload(box))
        with Store().write() as writable:
            writable.inventory.get(master.position_key(2, 1)).sku = "SKU-B"
            writable.inventory.get(master.position_key(2, 2)).sku = "SKU-B"
        capture_server.do_mark_sold(2, 1, {})  # before
        read_at = master.now()
        capture_server.do_mark_sold(2, 2, {})  # after

        inventory = Store().read().inventory
        live_by_sku = {
            "SKU-A": resolve.LiveReading(quantity=1, as_of=master.now()),
            "SKU-B": resolve.LiveReading(quantity=0, as_of=read_at),
            "SKU-ONLY-LIVE": resolve.LiveReading(quantity=2, as_of=master.now()),
        }
        # SKU C: only in `inventory.listings` (no export row at all this run).
        inventory.listing("SKU-ONLY-LISTED").bump(master.PUSHED)  # `by=1` is the default

        one_pass = resolve._copies_out(inventory, live_by_sku)
        reference = _copies_out_reference(inventory, live_by_sku)
        checks.equal(
            one_pass, reference,
            "the one-pass rewrite and the old per-listing arithmetic agree on every SKU, "
            "across both `copies_out` and `live_now`",
        )
```

Adjust the fixture calls (`capture_payload`, `Store().write()`, `writable.inventory.get(...)
.sku = ...`, `inventory.listing(...).bump(...)`) to match whatever this file's existing
helpers actually look like — `grep -n "def capture_payload\|\.bump(master\." harness/tests/
t7_store_and_seams.py` before writing this, and prefer copying an existing SKU-stamping
idiom from a nearby check (e.g. inside `check_committed_copies_are_the_oldest`, lines
16547-16670, which already stamps `sku` directly via `Store().write()`) over inventing a new
one. Register the new check function in this file's dispatcher list (grep
`check_committed_copies_are_the_oldest(checks)` and add the new call immediately after it).

### B. Existing regression coverage — confirm both, unmodified

- `harness/tests/t7_store_and_seams.py:check_committed_copies_are_the_oldest` (line 16547)
  — its direct call `resolve._copies_out(inventory, {})` at line 16655 must return the same
  `copies_out` dict this rewrite produces; run this check specifically after the rewrite
  (`python3 harness/run.py t7` or whatever this file's own invocation convention is — grep
  `if __name__` / the harness's per-file runner) and confirm the three assertions right
  after it (`checks.equal(sorted(committed), ["3/1", "3/2"], ...)` at line 16656-16663 and
  the `checks.ok(master.position_key(1, 1) not in committed, ...)` at line 16664-16667)
  still pass — these exercise `_committed_keys`, which is downstream of `_copies_out`'s
  output and therefore an indirect proof this item's return values are unchanged.
- `harness/tests/t3_join_coverage.py:_check_committed_from_counts` (line 448) — the
  "six copies, three live, offers 3 uncapped" case (lines 536-556) and the capped case
  (lines 448-486) both resolve through `_resolve_in` → `resolve.load` → `_resolve` →
  `_copies_out`. No line in this test needs editing; it is a regression guard for this
  item's arithmetic exactly as written.

### Mutation arm

State the one mutation this repo's convention calls for (per `make reap-selftest`,
`make silent-write-selftest`): **revert the `sold` computation's `read > 0` branch to count
`row.state == master.SOLD` OR `row.state in master.TERMINAL_STATES`** (i.e., accidentally
also counting `retired`/`moved` cards as "sold" — the exact wrong generalization
`copies_not_sold`'s own docstring warns against at `store/master.py:2395-2399`: "A RETIREMENT
is the other door... counting it as gone would free a slot under the cap that is not free").
Test A's SKU-A/SKU-B fixtures would need a retired card added to go red on this specific
mutation (neither current fixture has one) — add a third SKU, SKU-D, with one sold and one
retired copy, and assert `copies_out["SKU-D"]` equals the reference implementation's answer
with the retired copy correctly EXCLUDED from `sold`. This is the arm that proves the
rewrite preserves D26's `TERMINAL_STATES` vs. `SOLD`-alone distinction rather than merging
the two the way a naive "how many of this SKU's cards have left the box" reading would.

## Allowlist entries removed

**This needs a decision the task's own template assumed was already settled, and it is
not — read this whole section before choosing.**

`docs/specs/store-scaling.md` §4's table has one row naming this item:

> `server/pipeline_routes.py:2370` `_unsent_ledger` | `distinct("sku")` | per-load |
> Removed by: item 4

`00-phases.md`'s allowlist-progress table repeats the credit: "Phase 1 | 10 | item 2:
`_boxes_named`; item 4: `_unsent_ledger`". But `00-phases.md`'s OWN Phase-1 file-touch grid,
three paragraphs above that table, lists item 4's footprint as `cli/resolve.py:
resolve.py:_copies_out and its two helpers` with **no `server/pipeline_routes.py` column at
all** — unlike item 5, which gets a second explicit row naming
`server/pipeline_routes.py: do_live_export only` because its footprint spans two files. Item
4 gets no such second row. These two parts of the same document disagree about whether this
item touches `server/pipeline_routes.py`.

**Why it is not free to just do both:** `docs/specs/store-scaling/01-guard.md` (item 1, the
guard — Phase 0, lands before this item opens) scans `cli/resolve.py` as one of its named
single-file roots (`_UNSCOPED_WALK_SINGLE_FILES`), and its `select` rule flags a call with
`not node.keywords` — a `select()` invoked with a positional columns tuple and NO keyword
filter, exactly the shape `_cards_by_sku` uses (Steps §1 above). So the new one-pass
`select()` this item adds to `cli/resolve.py` is itself a NEW guard-visible unscoped-walk
site (`("cli/resolve.py", "_cards_by_sku", "select")`), not merely an internal
implementation detail invisible to the guard the way the OLD per-listing `.where(sku=sku)`
calls were (`where()` is never flagged by this guard at all — see `01-guard.md`'s own "Read
first" note: "the plan's own text names only `.values()`, `.items()`, `to_payload()`, and
unfiltered select/distinct — not `where`"). Concretely: this item's rewrite trades N
guard-invisible `.where()` calls for ONE guard-VISIBLE `.select()` call. That new site must
be added to `UNSCOPED_WALK_ALLOWED` as a "stays" entry (the same treatment
`("server/capture_server.py", "do_boxes", "distinct")` and `("store/master.py", "counts",
"select")` already get — "one deliberate pass, cheap, named in the allowlist rather than
removed") in the SAME PR, or `make docs-audit`'s `unscoped walk` row fails the commit on a
new, unlisted site.

**Two honest paths, and this file recommends the first:**

1. **Minimal (recommended): touch only `cli/resolve.py`.** Leave `_unsent_ledger`'s
   `distinct("sku")` exactly as it is in `server/pipeline_routes.py` — it is a single
   indexed column, no different in kind from `do_boxes`'s own `distinct("box")` (which
   `store-scaling.md` §4 explicitly keeps: "stays — one column, cheap; the guard names it").
   Add `("cli/resolve.py", "_cards_by_sku", "select")` to `UNSCOPED_WALK_ALLOWED` (once item
   1 has landed and that constant exists) as a NEW "stays" entry with a one-line reason
   ("one deliberate pass, replaces N per-listing calls; item 4"), and correct
   `UNSCOPED_WALK_EXPECTED` from 12 to **13** (net: +1 new site, 0 removed, since this path
   does not touch `_unsent_ledger`). Correct `00-phases.md`'s Phase-1 table in the same PR:
   its "Phase 1 | 10" line assumed item 4 removes `_unsent_ledger`'s entry AND adds nothing
   new; neither half of that holds under this path, so the honest Phase-1 target becomes
   **13** (12 + this item's new entry − item 2's `_boxes_named` removal), and the
   "item 4: `_unsent_ledger`" credit should be deleted from that line, not fulfilled.
   Correct `docs/specs/store-scaling.md` §4's row for `_unsent_ledger` from "Removed by:
   item 4" to "stays — cheap, single indexed column, no different from `do_boxes`; not
   touched by item 4" in the same PR. This path matches item 4's own footprint as
   `00-phases.md`'s file-touch grid actually describes it, and keeps this item's blast
   radius to one file, which is worth more than a marginally lower allowlist count.
2. **Stretch (only if the owner explicitly wants the count to actually drop): also rewrite
   `_unsent_ledger`'s orphan scan to share `_cards_by_sku`'s output.** This requires
   exporting `_cards_by_sku` (drop the leading underscore is NOT required — the file already
   imports `cli.resolve as run_resolve` and calls several underscore-prefixed functions
   across the module boundary, e.g. `run_resolve._live_by_sku`,`run_resolve._copies_out`,
   `run_resolve._committed_keys` at lines 2238, 2405, 2406 — so `run_resolve._cards_by_sku`
   is consistent with this file's existing convention). Give `_copies_out` an optional
   keyword so a caller that already has the dict does not force a second full scan:
   ```python
   def _copies_out(
       inventory: master.Inventory,
       live_by_sku: Mapping[str, LiveReading],
       *,
       by_sku: Optional[Mapping[str, Sequence[_SkuCardRow]]] = None,
   ) -> Tuple[Dict[str, int], Dict[str, int]]:
       by_sku = _cards_by_sku(inventory) if by_sku is None else by_sku
       ...
   ```
   Then in `server/pipeline_routes.py:_unsent_ledger`, replace lines 2369-2374
   (`orphans: List[str] = []` through the `orphans.append(sku)` loop) with:
   ```python
   by_sku = run_resolve._cards_by_sku(inventory)
   orphans: List[str] = [sku for sku in by_sku if sku not in positions]
   ```
   and change line 2405 to `held_out, live_out = run_resolve._copies_out(inventory,
   readings, by_sku=by_sku)`. This genuinely removes the `distinct("sku")` allowlist entry
   (net: −1 old site, and the NEW `_cards_by_sku` site absorbs both consumers, so it is
   still +1 new site — net effect on the allowlist SIZE is still zero, 12 stays 12, but the
   entry's NAME changes and `_unsent_ledger` itself is genuinely faster too, since it no
   longer runs its own separate full scan). If you take this path, it is a second file
   touched beyond what `00-phases.md`'s grid names for item 4 — say so explicitly in the PR
   description, and correct that grid's row to add a `server/pipeline_routes.py` column for
   item 4, matching the second-row pattern item 5 already uses.

Either way, **the allowlist count this item's PR should claim is never "10"** — that number
in `00-phases.md` is wrong regardless of which path you take, for the reason above. Correct
it to 13 (path 1) or 12 (path 2) in the same PR, and leave a one-line note in the PR body
pointing at this section so a future reader does not re-derive the same analysis.

## Do not touch

- `Inventory.positions_for_sku`, `Inventory.copies_not_sold`, `Inventory.sales_before`
  (`store/master.py:2366-2447`) — their bodies are unchanged; they still have other callers
  (`pipeline/orders.py:454`, `server/capture_server.py:7986` for `positions_for_sku`; T7
  cases at lines 1116, 12652, 14984, 15038, 17312 for `positions_for_sku`; T3 line 215) that
  must keep getting the exact same answers, computed the exact same way, for a single
  point lookup. This item only stops `_copies_out` from calling them in a per-listing loop.
- `cli/resolve.py:_committed_keys` (lines 676-732) — has the identical per-SKU-loop shape
  (`inventory.copies_on_hand(sku)` inside a loop over `copies_out.items()`) and is a real,
  named follow-up opportunity, NOT this item's job. Flag it rather than fixing it — see
  "Risks" below.
- `cli/resolve.py:_live_by_sku` (lines 441-484) and `LiveReading` (lines 429-439) — upstream
  inputs to `_copies_out`, untouched; they read export files, never `inventory.cards`.
- `pipeline/join.py` in its entirety — `SkuMatch`, `add_to_quantity`, and especially
  `uncommitted_positions` (D7's own name for "what actually stops a copy going twice," per
  CLAUDE.md and multiple T7 comments at lines 12607, 12627, 14746, 15013, 17315). None of
  these read `inventory.cards` directly or call `_copies_out`; they consume its two return
  dicts (`copies_out`, `live_now`) as plain `Mapping[str, int]` values, so this item's
  rewrite — which preserves the exact same dicts — cannot affect them. Confirmed by grep:
  `pipeline/join.py`'s only `_copies_out` references (lines 1781, 1786, 1856, 1860) are
  comments, not calls.
- `docs/DEBTS.md` — see "Read first" above; there is no existing paragraph there to edit for
  this item. Do not add one speculatively; if the owner wants the corrected analysis
  recorded as a debt (it is not really a debt any more once this item lands — the cost is
  fixed, not merely documented), that is a separate, small edit outside this item's scope.
- `store/rows.py`, `store/db.py` — no schema change, no new index, no `Rows`/`Source`
  method. The existing `cards_sku` index and the existing `select()`/`where()` methods are
  exactly what this item's rewrite uses; nothing about their contracts changes.
- `docs/specs/store-scaling.md` — update only if you take "Allowlist entries removed"
  path 2's stretch goal (correcting the `_unsent_ledger` row); otherwise leave it, and note
  in the PR body that its `_copies_out` measurement row (§1's table) should be updated with
  this item's real after-figure once measured (a small, separate, low-risk edit — do it in
  this PR since you are the one taking the measurement, but do not treat it as blocking).
- `cli/resolve.py:box_views` (lines 372-426) — item 7's function, a different site in the
  same file; do not touch it here even though it sits just below `_copies_out`.

## Measure

Reproduce the plan's own recipe (`docs/specs/store-scaling.md`'s methodology: a `.backup`
copy of the real store, then the same copy with every row of `cards` and `events`
duplicated 20x — the same recipe `docs/specs/store-scaling/03-history.md`'s own "Measure"
section uses, reused verbatim below with the timing target swapped to `_copies_out`). From
the repo root, with `PKMNSCAN_HOME` pointed at a scratch copy (never the owner's live
store):

```bash
# 1. Take a live backup copy (adjust the source path to wherever the real store's
#    inventory/ directory lives on this machine; never open the original with a write mode).
mkdir -p /tmp/store-scaling-measure/base
python3 - <<'EOF'
import sqlite3, pathlib
src = pathlib.Path("<owner's real inventory dir>/store.sqlite")
dst = pathlib.Path("/tmp/store-scaling-measure/base/store.sqlite")
conn = sqlite3.connect(str(src))
bck = sqlite3.connect(str(dst))
conn.backup(bck)
bck.close(); conn.close()
EOF

# 2. Build the 20x copy alongside it — reuse the existing script from item 3's measurement
#    if one is already sitting in this worktree's /tmp from a prior item's run (check
#    `ls /tmp/store-scaling-measure/20x` first); otherwise this is the same duplication
#    docs/specs/store-scaling/03-history.md's "Measure" section already writes out in full
#    (its Step 2) — copy that block rather than re-deriving it, since the schema it
#    duplicates against (`cards`, `events`) is identical for this item.

# 3. Measure `_copies_out` on both copies, before and after Steps 1-2 above.
for dir in /tmp/store-scaling-measure/base /tmp/store-scaling-measure/20x; do
  PKMNSCAN_HOME="$dir/.." python3 - <<EOF
import time, statistics
from cli import resolve
from store.session import Store

snapshot = Store().read()
inventory = snapshot.inventory

def bench(fn, n=5):
    times = []
    for _ in range(n):
        t0 = time.perf_counter(); fn(); times.append(time.perf_counter() - t0)
    return statistics.median(times) * 1000

print("$dir")
print("  _copies_out(): %.2f ms" % bench(lambda: resolve._copies_out(inventory, {})))
EOF
done
```

**Expected, and what confirms the fix rather than merely running it:**
- Re-run this exact snippet against the CURRENT (pre-rewrite) `_copies_out` first, on the
  base copy, and confirm it lands near the in-repo figure (0.9 s over 492-753 listings,
  scaled to whatever listing count the owner's current store actually holds — the
  `Rows._loaded`-accumulation mechanism this item fixes means the number will scale with
  BOTH cards and listings, so do not expect an exact match to the 2026-09-11/12 figures if
  the store has grown since either measurement).
- After the rewrite, the SAME base-copy call should land in the tens of milliseconds — the
  cost of one `select()` over ~2,500-ish cards plus a Python dict build, comparable to
  `Inventory.counts()`'s own single-column scan (which this file's "Read first" section
  cites as a precedent for `select()`'s cost).
- The 20x copy's ratio is the real proof: **before** the rewrite it should scale roughly
  with (cards × listings) — noticeably worse than the 19-21x ratios item 3's `history()`
  and the plan's `Inventory.to_payload()`/`do_orders()` rows show, since those are "only"
  O(cards) while this was O(cards × listings). **After** the rewrite it should scale like
  every other O(cards) fix in this plan — close to 20x in absolute terms (more cards, more
  dict entries, more listings to iterate), but LINEAR rather than the pre-fix superlinear
  growth. If the 20x copy's post-fix time is not roughly the base time × (its card-count
  ratio), re-check that `_cards_by_sku` is genuinely being called once (add a call counter
  or a `print` during the measurement, remove before committing) rather than once per
  listing by accident.
- Record whatever this session actually measures — the plan's own stated practice — in the
  PR body, and update `docs/specs/store-scaling.md` §1's table row for `_copies_out` with
  the real before/after/ratio figures in the same PR (a small, low-risk documentation edit;
  see "Do not touch" above for why it is optional but recommended).

Clean up `/tmp/store-scaling-measure` when done; it is not part of the repo and must never
be committed.

## Risks

- **`_committed_keys` (`cli/resolve.py:676-732`) has the identical O(listings × cards)
  shape this item fixes, and this item does not touch it.** It loops `copies_out.items()`
  (the SAME dict `_copies_out` now returns in one pass) and calls `inventory.copies_on_hand
  (sku)` per SKU — which calls `positions_for_sku`, which is the exact `Rows.where()`
  `_loaded`-accumulation mechanism this item's "Read first" section documents. After this
  item lands, `_committed_keys` becomes the single remaining O(listings × cards) cost in
  this request path — the plan's own §0 diagnosis and §1 measurement table do not separate
  the two functions' costs, so the "0.9 s" figure this item eliminates may include some
  fraction attributable to `_committed_keys` rather than `_copies_out` alone, which this
  item's own "Measure" section's before/after comparison will reveal (if the after-figure
  is not near-flat, `_committed_keys` is very likely why). This is real, out-of-scope
  follow-up work — name it in the PR description and consider whether it deserves its own
  plan item (it is not one of the eight named in `docs/specs/store-scaling.md` §3 today).
- **The allowlist-count disagreement documented above is not cosmetic.** Landing this item
  without resolving which path (minimal vs. stretch) you took, and without correcting
  `00-phases.md` and `store-scaling.md` §4 to match, leaves the NEXT item's implementer
  reading a plan that promises a count neither path actually delivers — exactly the kind of
  drift `docs/map.py`'s own `--stale` flag and this repo's "a rule with no reader is advice"
  standard (D173) exist to catch. Do not skip the correction because it feels like someone
  else's paperwork; it is this item's own paperwork, created by this item's own rewrite.
- **The equivalence test (Tests §A) is only as good as its fixture's branch coverage.** If a
  future edit to `Listing.live_reading`/`.sales_pending`/`.reading_taken_at` changes what
  `read`/`live`/`claim`/`read_at` can be for some new listing state, the reference
  implementation and the one-pass rewrite would drift together (both call the exact same
  `Listing` methods) and the equivalence test would stay green while diverging from the
  REAL old behavior in a way neither implementation reflects any more. This is not a gap
  this item can close — it is the reason `check_committed_copies_are_the_oldest` and
  `_check_committed_from_counts` (Tests §B) are named as separate, independent regression
  guards rather than folded into the new equivalence test: they assert against FIXED
  expected numbers (`["3/1", "3/2"]`, `add_to_quantity == 1`, etc.), not against a
  parallel implementation, so a shared-cause drift in `Listing`'s methods would be caught by
  them even if it fooled the equivalence test.
- **This item does not address `Inventory.to_payload()`/`do_orders()` (items 2/6), `Store.
  history()` (item 3), or the `readings` writer (item 5)** — separate items in the same
  plan, out of scope here by design, not by oversight, exactly as `docs/specs/store-scaling/
  03-history.md`'s own "Risks" section says of this item from its side.
