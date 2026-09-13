# Item 6 — do_orders per SKU

Source: `docs/specs/store-scaling.md` §3 item 6 and its §1 `GET /orders` paragraph and §4
allowlist. This file is the implementation playbook; it does not itself change code.

**IMPLEMENTATION NOTES, ADDED BY THE PR THAT BUILT THIS ITEM.** Every `file:line` below
predates item 2's merge and has drifted; the corrected anchors are `store/master.py:1492`
(`_positions_in`, unchanged) / `:1522` (`occupied_indices`, new), `server/capture_server.py:1960`
(`class _Places`), `:2078` (`for_keys`), `:8945` (`_order_stamps`), `:9221` (`do_orders`).
Re-read the tree rather than trusting a line number in the sections below.

**ONE THING IN THIS FILE'S DESIGN WAS INCOMPLETE, AND IT IS LOAD-BEARING.** Item 2's merge
moved `_walk`'s occupied-index computation INTO `view()` itself (`server/capture_server.py`
— "ONE WALK, BOTH RENDERERS"), and `_walk` excludes a D24 pooled (code-card) record from
D58's counting space before this item was ever designed. `Inventory.occupied_indices` as
sketched here (Step 1) does not filter on the game claim at all, so `_Places.for_keys` over
a box mixing a pooled card with located ones would silently disagree with the ordinary
constructor on `slot`/`box_total`/`fraction` for every OTHER card in that box — verified
against the tree and against this file's own `check_order_screen` fixture (`3/5` set to
`pokemon_code`). `store/` cannot resolve D24's `located` flag itself (D63: it imports
nothing from `pipeline/`), so the shipped `occupied_indices` returns `(index, game)` pairs
and the filter (`_location_of`, mirroring `_Places._game_of`) lives in `_Places.for_keys`,
which already imports `pipeline.games`. See the PR description for the measured mismatch
(`box_total` 20 vs 19, `fraction` 0.0 vs 0.05263…) with the filter removed.

**`_order_stamps` IS DELIBERATELY NOT TOUCHED IN THIS PR**, and not for the "time budget"
reason this file names below. `_order_stamps`'s per-pick loop catches `BadPosition` /
`BadSections` from `places.of(...)` PER PICK, so one box with an unreadable divider layout
today only empties THAT box's picks' labels — other orders' stamps still render.
`_Places.for_keys` resolves `sections_for` for every touched box EAGERLY, in one loop,
before any pick is rendered; wiring it into `_order_stamps` the way `do_orders` uses it
would turn one bad box's `BadSections` into an uncaught exception that kills the WHOLE
`POST /shipping/batches/<batch>/stamps` response — a real behavior change, not a missed
optimization. `do_orders` has no such per-pick catch today (`_pick_row` lets both
exceptions propagate), so the same eager-vs-lazy timing shift is not observable there. A
future fix for `_order_stamps` needs `for_keys` to degrade per box on `BadSections` too,
matching the per-pick catch it already has — left as the named, unfixed twin this file
itself anticipated.

## Goal and done-when

`do_orders` (`server/capture_server.py:9027-9122`) measured 185 ms at 2,535 cards and
3,465 ms at the 20x-row copy (18.7x) — O(cards) in practice, even though every individual
lookup it makes is indexed. The mechanism (confirmed by reading the code, not assumed):

- `order_engine.resolve_all` picks copies via `Inventory.positions_for_sku`
  (`store/master.py:2366`), which is `self.cards.where(sku=sku)` — an indexed, scoped SQL
  query. This part is already fine and is explicitly OUT OF SCOPE unless research finds it
  walking something unscoped (see "Read first" below — check this before writing any code).
- `places = _Places(snapshot.inventory)` (`server/capture_server.py:9078`) is instantiated
  ONCE for the whole response, which is correct and stays that way — "ONE RENDERER" is a
  repo-wide rule (`_Places`'s own class docstring, `server/capture_server.py:1939-1985`).
  The class does NOT eagerly scan the store; it is lazy per box, cached per instance
  (`_cache`, `_boxmates` dicts in `__init__`, `server/capture_server.py:2029-2033`).
- The cost is in what "lazy per box" means once it runs. `_Places.of(box, index)`
  (`server/capture_server.py:2266`) calls `self.view(number)` which calls `self._walk(number)`
  (`server/capture_server.py:2130-2168`), and `_walk` reads the ENTIRE box through
  `Inventory.records_in(number)` (`store/master.py`, doc'd at `server/capture_server.py:2151`)
  — every record in the box is hydrated into a full `Card` object (JSON payload parsed,
  every field built) so `_walk` can read that card's `name` and `state`. This is needed for
  D30's neighbor/gap decoration (`neighbors`, `section_gaps`), which needs every card's
  NAME.
- `_walk`'s result is cached per box (`self._boxmates[number]`), so a box is only ever
  fully hydrated ONCE per `_Places` instance no matter how many picks land in it. The O(cards)
  cost is therefore not "the same box re-read many times" — it is "every box an order's
  picks touch gets fully hydrated once, and with five boxes and orders whose picks span
  most of them, that is effectively the whole store, once."
- `do_orders`'s own picks come from `_pick_row` (`server/capture_server.py:8961-8987`),
  called once per pick at `server/capture_server.py:9023`: `"place": places.of(pick.box,
  pick.index)`.

**What `do_orders`'s response actually needs from `place`, verified against the one screen
that reads it** (`app/src/Orders.tsx`, which backs both `#/orders` and `#/shipping` per
D69 — `OrdersShipStage.tsx` renders inside the same `OrdersHub`): `label`, `located`, `box`,
`box_name`, `section`, `slot`, `game`, `game_display`, and `index` (grep results below).
`Orders.tsx` reads NEITHER `neighbors` NOR `section_gaps` — D30's decoration, the one thing
that forces `_walk`'s full-box hydration — anywhere. Grep for confirmation before writing
code (this file's grep at the time of writing found zero hits for either field in
`app/src/Orders.tsx` or `app/src/OrdersShipStage.tsx`):

```
grep -n "neighbors\|section_gaps" app/src/Orders.tsx app/src/OrdersShipStage.tsx
```

**The fix**: give `_Places` a second, leaner construction path that computes `Place.slot`
(D58) and everything derived from it (`label`, `section`, `card`, `fraction`, `box_total`)
from two indexed integer COLUMNS per box — not from hydrating every `Card` object in the
box — and answers `neighbors`/`section_gaps` as `null` (an already-modeled, already-typed
degraded state, not a new one — see "Do not touch" below). `do_orders` collects the
`(box, index)` keys its resolution actually returned BEFORE building `_Places`, and builds
the leaner form scoped to exactly those boxes.

**Done-when**:
1. `_Places` gets an alternate constructor (name below) that produces byte-identical
   `slot`/`label`/`section`/`card`/`box_total`/`fraction`/`box_name`/`box_closed`/
   `section_start`/`section_end` values to today's `_Places(inventory).of(box, index)`, for
   every pick `do_orders` renders, and answers `neighbors: null, section_gaps: null` instead
   of D30's decoration.
2. `do_orders` uses it, scoped to the picks its own resolution produced.
3. The stale comment at `server/capture_server.py:9075-9077` ("ONE `_Places` FOR THE WHOLE
   RESPONSE. It walks the entire store per instantiation...") is replaced with what the
   route now does — it does NOT walk the entire store per instantiation, and never did;
   what it did was hydrate every box the picks touch.
4. T7 proves boxes NOT touched by any pick build zero `Card` objects, and boxes touched
   build only as many as their own live-index column read costs (not `records_in`'s full
   hydration) — see "Tests".
5. The 185 ms / 3,465 ms table in `docs/specs/store-scaling.md` §1 is re-measured on the
   `.backup` copy and both numbers are reported in the PR description (not edited into the
   spec file — that table is dated evidence per `CLAUDE.md`'s rule that measured numbers are
   "never rewritten to match a later tree").

## Depends on / conflicts with

**Item 2** ("the per-box read", `docs/specs/store-scaling.md` §3 item 2) touches
`server/capture_server.py:10687` (`GET /boxes/<n>`, currently refused) and
`store/rows.py:177`'s materialize-then-filter fallback. It does NOT touch `_Places`, `do_orders`,
`_pick_row`, `_line_answer`, or anything under `server/capture_server.py:9027-9130`
(confirmed by reading item 2's own description in the spec — it lists `do_inventory`,
`_boxes_named`, `store/master.py:to_payload`; `do_orders` is explicitly named in item 2's
own text as moving "under item 6", i.e. this item). **No file-level conflict is expected**,
but item 2 changes `store/rows.py:177`'s degrade behavior (a `where`/`select` after a full
load currently answers from the Python-side list rather than SQL). This item's new code
path (a fresh `Rows.select(...)` call inside `Inventory.occupied_indices`, see "Steps")
depends on that call being answered from SQL and not from a materialized Python list —
which holds TODAY inside `do_orders`'s own request (nothing before this item's new call
materializes the whole `cards` table in that route), and holds EVEN BETTER after item 2
lands. **Recommend this item runs after item 2 merges**, per the plan's own ordering (item 2
is listed before item 6 in `docs/specs/store-scaling.md` §3), so that a rebase picks up
item 2's `rows.py:177` fix rather than this item's tests being written against a
soon-to-change fallback rule. If item 2 has not merged yet: this item's own code does not
create a full-store load anywhere in `do_orders`'s call path, so the two are independently
correct; only the ORDER of landing is at stake, not correctness.

**Item 4** (`_copies_out`, `cli/resolve.py`) and **item 7** (`_release_plan`, `box_views`,
`do_pipeline_value`) touch different files entirely (`cli/resolve.py`,
`server/pipeline_routes.py`) and do not intersect this item's files
(`server/capture_server.py`, `store/master.py`).

## Read first

- `docs/specs/store-scaling.md` §0 (mechanism), §1 (`GET /orders` paragraph, the measured
  185 ms / 3,465 ms table), §2 ("the punch list got wrong" — confirms `_Places` does no
  eager scan and the comment at `:9075` is stale), §3 item 6, §4 (allowlist — `do_orders` is
  NOT on it; the allowlist's `do_inventory`/`_boxes_named` rows belong to item 2).
- `CLAUDE.md`: D63 (order ledger is two maps; `pipeline/orders.py` resolves and stores
  nothing — this item touches only the RESOLUTION's rendering, never the ledger), D69 (the
  order screen and shipping lane are one hub off one `resolve_all`; "`GET /orders` answers
  from one snapshot" — this item must not introduce a second snapshot or a second `Store()`
  read), D90 (order-driving-the-walk is SUPERSEDED/deleted code — `do_order_fill` is a
  different route under `server/order_transport.py`/inventory fill, not `do_orders`; do not
  confuse the two), D91 (the order fetch/window — unrelated plumbing upstream of the
  ledger, not touched here), D97 (the copy map ranks and never picks — describes
  `#/pricing`'s value band, not `#/orders`; cited by the task prompt for orientation but has
  no code overlap with this item).
- D63 and D69 in full (read via `Read`, not the excerpt above)
  before writing code — they are short and settle exactly the "one snapshot, resolved once"
  invariant this item must preserve.
- `docs/specs/order-pipeline.md` — background on the order screens; confirms steps 8-12 are
  built and step 13/14 (shipped status, tracking write-back) are not, and that D96 deleted
  the envelope-walk code (`orderWalk.ts` etc.) that is unrelated to `do_orders`.
- `server/capture_server.py:1939-2333` (`_Places` in full — class docstring through `.of()`)
  and `pipeline/join.py:104-311` (`Position` in full — the ONE label formula; read this
  before writing anything that could be mistaken for a second one).
- `store/master.py:1492-1519` (`_positions_in`) — the EXISTING precedent for exactly this
  optimization shape, already used by the capture allocator's high-water scan. Read its
  docstring: "Asked of the mapping as three indexed queries rather than a walk (D88)."
- `store/rows.py:1-49` (module docstring) and `:230-250` (`Rows.select`) — the mechanism
  `_positions_in` and this item's new method both use: column values without building
  objects.
- `harness/tests/t7_store_and_seams.py:1074-1090` — the EXISTING test idiom for asserting
  "this call built few `Card` objects, not the whole box/store":
  `snapshot.inventory.cards.loaded_count` and `.complete`. Use this idiom for the new test;
  do not invent a SQL-trace mechanism — none exists in this harness today and the repo's own
  idiom already answers the question this item needs to ask.
- `harness/tests/t7_store_and_seams.py:22280-23260` — the existing `do_orders` test block:
  fixture construction helpers, `answers(checks, capture_server.do_orders, "...")`, and the
  renumber/shift case this item's new test sits beside.
- `app/tests/orders.spec.ts` — stubs the `/orders` response wholesale (fixture JSON), so it
  exercises NOTHING on the server; it is a wire-shape pin on the CLIENT side. Confirm no
  server-shape assumption in it would be violated (see "Do not touch").

## Steps

### 1. Add `Inventory.occupied_indices` — `store/master.py`, beside `_positions_in` (`:1492-1519`)

Insert directly after `_positions_in` (which ends at line 1519 with `return out`):

```python
def occupied_indices(self, box: int) -> Tuple[int, ...]:
    """Every ON-HAND (non-terminal) index in `box`, ascending — D58's `occupied` input for
    a caller that needs `Position.slot`/`label`/`section`/`card`/`fraction` and NOTHING
    else: no name, no photo path, no D30 neighbor walk. `_positions_in`'s own docstring is
    the precedent: two indexed columns read as three `select` queries, never a walk that
    hydrates a `Card` per row.

    `do_orders` is the caller this exists for (`_Places.for_keys`,
    server/capture_server.py). Its picks can span most of the store's boxes, and hydrating
    a full `Card` — JSON payload, name, photo fields — per row, for every record in every
    touched box, to answer a question that only needs an index and a state, is exactly the
    O(cards) cost D88 already fixed once for the capture allocator's high-water scan.

    Refuses on the same records `_positions_in` refuses on — a box/idx column that will not
    coerce, anywhere in the store — for the same reason: `next_index`'s rule that an
    unparsable record stops the read rather than being silently skipped past.
    """
    box = _as_position_int(box, "box")
    live: List[int] = []
    seen = set()
    for key, (raw_index, state) in self.cards.select(("idx", "state"), box=box):
        seen.add(key)
        if raw_index is None:
            card = self.cards[key]
            _as_position_int(card.box, f"box of card {key}")
            _as_position_int(card.index, f"index of card {key}")
            raw_index = card.index
            state = card.state
        if state not in TERMINAL_STATES:
            live.append(int(raw_index))
    for equals in ({"box": None}, {"idx": None}):
        for key, _ in self.cards.select(("box", "idx"), **equals):
            if key in seen:
                continue
            seen.add(key)
            card = self.cards[key]
            _as_position_int(card.box, f"box of card {key}")
            _as_position_int(card.index, f"index of card {key}")
    live.sort()
    return tuple(live)
```

Notes for the implementer:
- `_as_position_int` and `TERMINAL_STATES` are already module-level in `store/master.py`
  (used by `_positions_in` and at `store/master.py:143` respectively) — no new import.
  `List`/`Tuple` are already imported at the top of the file (used throughout
  `store/master.py`; confirm with `grep -n "^from typing" store/master.py`).
- The second loop (the `{"box": None}, {"idx": None}` pair) mirrors `_positions_in`'s own
  refusal-completeness rule: a record whose box or idx column is NULL anywhere in the
  store must still raise, even if it is not in the requested box — that is `next_index`'s
  documented invariant and this method must not weaken it just because its caller (orders)
  only cares about one box. Copy `_positions_in`'s two-loop shape exactly; do not "simplify"
  it to one loop, or a NULL-column record in a DIFFERENT box goes unnoticed here while
  `records_in`/`_walk` would have caught it.
- This function does not sort by calling `select` twice for ordering — `select`'s own
  contract returns `(key, tuple)` in a sequence `Rows.select` sorts by key internally
  (`store/rows.py:249`, `return [(key, out[key]) for key in sorted(out)]`), which is KEY
  order, not INDEX order — hence the explicit `live.sort()` at the end. Verify this by
  reading `Rows.select` again if in doubt; do not assume key order equals index order (it
  does not — keys are `"box/idx"` strings, and string-sorting "3/10" before "3/2" is exactly
  the kind of bug `_positions_in`'s own `int()` coercion exists to avoid elsewhere).

### 2. Add `_Places.for_keys` — `server/capture_server.py`, in the `_Places` class after `__init__` (`:2027-2033`)

```python
@classmethod
def for_keys(
    cls, inventory: "master.Inventory", keys: Iterable[Tuple[int, int]]
) -> "_Places":
    """A `_Places` scoped to exactly the boxes `keys` touches, for `Place.slot` and
    everything derived from it — NOT for D30's neighbor/gap decoration, which needs
    every card's NAME and is exactly the cost this constructor exists to avoid.

    `do_orders` is the one caller. An order's picks can span most of the store's boxes, and
    the ordinary constructor's `_walk` (`records_in`, full `Card` hydration per row) turns
    that into "every box, once" — effectively the whole store, on the route the Orders and
    Shipping screens poll. `Inventory.occupied_indices` answers the same `Position.occupied`
    input from two indexed integer columns instead.

    `neighbors`/`section_gaps` answer null for every position built through this
    constructor, which is the SAME null the ordinary path already answers when `_walk`
    degrades (a record whose position will not read) — an existing, typed, degraded state
    (`PlaceBlock.neighbors?`, `app/src/types.ts`), not a new one. `Orders.tsx` reads neither
    field.
    """
    self = cls(inventory)
    self._sparse = True
    for number in {int(box) for box, _ in keys}:
        entry = inventory.box(number)
        layout = inventory.sections_for(number)
        occupied = inventory.occupied_indices(number)
        self._cache[number] = (entry, layout, len(occupied), occupied)
    return self
```

Add `self._sparse = False` to `__init__` (`server/capture_server.py:2029-2033`, right beside
`self._degraded = False`), so the ordinary constructor path is unaffected and `_company`
(step 3) can tell the two apart.

### 3. Short-circuit `_company` in sparse mode — `server/capture_server.py:2176-2265`

`_company` (D30's neighbor/gap walk) currently opens with:

```python
    def _company(
        self, box: int, at: int, start: int, end: Optional[int]
    ) -> Tuple[Optional[dict], Optional[int]]:
        """..."""
        mates = self._walk(box)
        if mates is None:
            return None, None
```

Change the body's first line to:

```python
        if self._sparse:
            return None, None
        mates = self._walk(box)
        if mates is None:
            return None, None
```

This is the one line that makes `for_keys` actually cheap: without it, `.of()` still calls
`_company`, which calls `self._walk(box)`, which is the exact full-`records_in` hydration
this item exists to avoid — `_boxmates` would not have this box cached (only `_cache` does,
populated by `for_keys` directly), so `_walk` would run in full. Verify this by re-reading
`.of()` (`server/capture_server.py:2266-2333`): it calls `self.view(number)` (reads from
`self._cache`, populated by `for_keys` — fine) and then `self._company(number, at, first,
last)` (must be short-circuited, or the whole optimization is silently defeated while every
test still passes, because the RESULT is identical — only the cost is wrong). Add a comment
at the docstring naming this trap explicitly, since a future edit to `.of()` that adds a new
call into `_walk`/`_boxmates` would reintroduce the same defeat silently.

### 4. Wire it into `do_orders` — `server/capture_server.py:9027-9122`

Replace lines 9074-9078 (currently):

```python
    resolution = order_engine.resolve_all(snapshot.inventory, asked)

    # ONE `_Places` FOR THE WHOLE RESPONSE. It walks the entire store per instantiation, and
    # its own docstring measures what a per-card one costs; the instance never outlives this
    # request, so it cannot serve a stale denominator to the next one.
    places = _Places(snapshot.inventory)
```

with:

```python
    resolution = order_engine.resolve_all(snapshot.inventory, asked)

    # ONE `_Places` FOR THE WHOLE RESPONSE, SCOPED TO THE PICKS THE RESOLUTION ACTUALLY
    # RETURNED. The ordinary constructor is lazy per box but still hydrates a full `Card`
    # per record in every box a pick touches (`_walk`, D30's neighbor decoration), and an
    # order's picks routinely span most of the store's boxes — with five boxes, that is
    # effectively the whole store, once, on the route Orders and Shipping poll. Neither
    # screen draws `neighbors` or `section_gaps` (grep `app/src/Orders.tsx`), so
    # `_Places.for_keys` answers `Place.slot` and everything derived from it — `label`,
    # `section`, `card`, `fraction`, `box_total` — from two indexed columns per box
    # (`Inventory.occupied_indices`) instead of a whole-box hydration, and answers those two
    # decoration fields null, which is an existing degraded state and not a new one.
    keys = {
        (pick.box, pick.index)
        for answer in resolution.orders
        for line in answer.lines
        for pick in line.picks
    }
    places = _Places.for_keys(snapshot.inventory, keys)
```

Verify the exact attribute path `answer.lines[i].picks[j].box`/`.index` against
`order_engine`'s dataclasses before writing this (grep `pipeline/orders.py` for the `Pick`/
`Line`/`Answer` dataclass definitions — `_pick_row`'s own signature at
`server/capture_server.py:8961-8987` already uses `pick.box`, `pick.index`,
`pick.capture_id`, `pick.source`, `pick.run`, so the field names are confirmed there).

An order with NO open lines with picks (a fully-resolved or empty ledger) yields an empty
`keys` set; `_Places.for_keys(inventory, set())`'s `for number in {...}` loop runs zero
times, `self._cache` stays empty, and no `.of()` call ever happens for that response —
already correct, verify with a test (see "Tests").

## Call sites (complete)

Every place `_Places(...)` is instantiated today (`grep -n "_Places(" server/capture_server.py`):

| Line | Route/function | Touches this item? |
|---|---|---|
| 2521 | (helper, single card) | No — single `.of()` call, one box; leave as `_Places(inventory)` |
| 2615 | (helper, single card) | No — same shape |
| 3095 | `do_capture`'s response (`_card_summary`) | No — one card, one box |
| 5360 | (a write route's receipt) | No |
| 7966 | `do_search` | No — item 8's subject (search index), not this item |
| 8235 | `_box_row` (`view(box)` only, no `.of()`) | No |
| 8392 | `do_boxes` | No — item 7's subject |
| 8542 | (`occupied(box)` only) | No |
| 8829 | `_order_stamps` (`server/capture_server.py:8751`) — the Rubber Stamp fill helper behind `POST /shipping/batches/<batch>/stamps` (`docs/specs/order-pipeline.md` §3 T2b) | **YES — same shape, confirmed by reading `:8780-8835`.** It runs the IDENTICAL pattern to `do_orders`: `sequence`/`open_records`/`asked = [_engine_order(record, ledger) for record in open_records]`/`resolution = order_engine.resolve_all(...)`, then `places = _Places(snapshot.inventory)` over EVERY open order in the store to stamp only the numbers in one batch. Its own docstring even says "`_Places` built and dropped inside this call" — same cost, same fix. |
| 9078 | `do_orders` | **YES — this item's subject** |
| 9756 | `do_order_pull` (`server/capture_server.py:9663`) | **No — different shape, confirmed by reading `:9740-9793`.** This is a WRITE route (`Store().write()`), bounded by the request body (`parsed`, capped at `ORDER_FILL_TARGET_LIMIT = 50` per D90) rather than by every open order in the store; `places` here answers `_prepare_targets`'s specific positions, not a store-wide resolution. Lower value and not measured in `docs/specs/store-scaling.md` — leave it on the ordinary constructor for this item; note it as a candidate for the SAME treatment in a follow-up if `_prepare_targets`'s own boxes ever prove slow (it is a write, not a polled GET, so it is off this plan's "per-press"/"per-load" cost table). |

**Recommendation: apply the identical `_Places.for_keys` fix to `_order_stamps`
(`:8829`) in this same PR.** It is not named in `docs/specs/store-scaling.md`'s item 6 text
because that item's own measurement only covers `GET /orders`, but the code path is the
same pattern with the same defect for the same reason, and leaving it unfixed while fixing
`do_orders` beside it would be exactly the kind of half-applied primitive `CLAUDE.md`'s "no
bandaids" rule and its outcomes-over-process rule both argue against ("read for the thing
that would make it unnecessary... an option set in which every entry is a heuristic is
evidence the real fix is upstream"). If the implementing session's time budget does not
allow it, at minimum flag `_order_stamps` by name in the PR description as an identified,
unfixed twin, with its line number, so it is not rediscovered from scratch later.

## Tests

Add to `harness/tests/t7_store_and_seams.py`, near the existing `do_orders` block
(`:22280-23260`) — an `## do_orders scopes to the boxes its picks touch` subsection.

### Assertion 1 — sparse build touches only the boxes with picks

Using the `loaded_count`/`complete` idiom already proven at
`harness/tests/t7_store_and_seams.py:1074-1090`:

```python
# Five boxes, one order whose only line resolves inside box 3.
for box in (1, 2, 3, 4, 5):
    for at in range(1, 21):
        capture_server.do_capture(capture_payload(box, capture_id=f"b{box}c{at}", set_hint="sv9"))
# ... join/identify enough of box 3 that one SKU resolves there (reuse whatever fixture
# helper the existing do_orders block uses to get a real SKU onto a card — grep
# "ingest_order" and the block above line 22280 for the pattern already in this file).
ingest_order(..., sku=<box-3 sku>, quantity=1)

with Store().write() as snapshot:
    pass  # flush any pending session so the read below is clean
before = Store().read()
loaded_before = before.inventory.cards.loaded_count
checks.ok(before.inventory.cards.complete is False, "a fresh read has not hydrated anything yet")

drawn = answers(checks, capture_server.do_orders, "GET /orders scopes its _Places build")
```

`do_orders` opens its OWN `Store().read()` internally, so `loaded_count` must be read from
INSIDE that call's snapshot, not from the `before` snapshot above (which is a separate read
and cannot see what `do_orders` built). The existing test file's pattern for this is to
monkeypatch `Store.read` to capture the snapshot it returns, OR — simpler and matching the
existing idiom exactly — call the pieces `do_orders` calls, directly, in the test, the way
`t7_store_and_seams.py:1074-1090` does inline rather than through a route function:

```python
snapshot = Store().read()
ledger = snapshot.ledger
open_records = [r for r in snapshot.ledger.orders.values() if r.key in
                {rec.key for rec in snapshot.ledger.unfulfilled()}]
asked = [capture_server._engine_order(r, ledger) for r in open_records]
resolution = order_engine.resolve_all(snapshot.inventory, asked)
before_loaded = snapshot.inventory.cards.loaded_count

keys = {(p.box, p.index) for a in resolution.orders for l in a.lines for p in l.picks}
places = capture_server._Places.for_keys(snapshot.inventory, keys)
# force one `.of()` per pick, exactly as `_pick_row` does
for a in resolution.orders:
    for l in a.lines:
        for p in l.picks:
            places.of(p.box, p.index)

after_loaded = snapshot.inventory.cards.loaded_count
checks.ok(
    after_loaded - before_loaded <= 20,
    f"built {after_loaded - before_loaded} card objects to place picks confined to one "
    f"20-card box — not the other four 20-card boxes (80 more cards) the ordinary "
    f"constructor's `_walk` would have hydrated to answer the same picks",
)
checks.ok(
    not snapshot.inventory.cards.complete,
    "and the whole-store table was never fully loaded either",
)
```

Adjust the exact fixture helper names (`capture_payload`, `ingest_order`, `answers`) to
whatever this file already exports — grep them at the top of `t7_store_and_seams.py` and in
the existing `do_orders` block before writing the literal test; the sketch above is the
SHAPE of the assertion, not a drop-in.

### Assertion 2 — slot/label parity against the ordinary constructor (and against `do_inventory`)

For every pick the resolution produces, `_Places.for_keys(...).of(box, index)` must equal
`_Places(inventory).of(box, index)` on every field EXCEPT `neighbors`/`section_gaps` (which
are `None` on the sparse side and may be populated on the ordinary side). Write this as a
direct dict comparison with those two keys popped from both sides before comparing:

```python
ordinary = capture_server._Places(snapshot.inventory)
for a in resolution.orders:
    for l in a.lines:
        for p in l.picks:
            sparse_block = dict(places.of(p.box, p.index))
            ordinary_block = dict(ordinary.of(p.box, p.index))
            for key in ("neighbors", "section_gaps"):
                sparse_block.pop(key, None)
                ordinary_block.pop(key, None)
            checks.equal(
                sparse_block, ordinary_block,
                f"the sparse and whole-box builds agree on everything but D30's decoration "
                f"for {p.box}/{p.index}",
            )
```

Also assert `places.of(p.box, p.index)["slot"]` equals the slot `do_inventory`'s own
`_Places` renders for the same card (a second, independent path to the same number,
matching the task's own instruction — "slot equality against `do_inventory`'s for the same
cards"). Call `capture_server.do_inventory()` in the test, find the matching card in its
`inventory`/box payload, and compare `place.slot`. Confirm `do_inventory`'s response shape
by reading `server/capture_server.py:3056` (`do_inventory`) before writing this half — it
returns boxes/cards nested, not a flat list, so the lookup needs the right traversal.

### Assertion 3 — a section with real dividers

The corpus of existing fixtures likely has at least one multi-section box already (check
the file for `set_sections`/`POST /boxes/<n>/sections` fixture calls); if not, add one
section split inside the test box before ingesting the order, so `layout` has more than the
`(1,)` fallback and `Position.section`/`card`/`section_start`/`section_end` are exercised
for real rather than trivially. This is the case most likely to expose an off-by-one in
`Inventory.occupied_indices` vs. `records_in`'s notion of "on hand" (e.g. a divider placed
past every captured card — `Position._divider`'s "unfilled" branch,
`pipeline/join.py:238-252` — read that method before deciding the fixture needs it; if the
existing test boxes never place a divider past the high-water mark, this assertion can be
skipped with a one-line note saying why, rather than invented against a case that cannot
occur through the routes this repo exposes).

### Assertion 4 — empty resolution

An order whose lines all resolve with zero picks (or a store with no open orders) must not
error. `_Places.for_keys(inventory, set())` — call it directly and assert it returns an
instance with no boxes cached, then confirm the existing "GET /orders answers an empty
store" test (`server/capture_server.py`'s route exercised at
`harness/tests/t7_store_and_seams.py:22867`) still passes unmodified — it already covers
this path through the route; this assertion is a UNIT-level companion for the new
classmethod alone.

### Mutation arm

Revert `do_orders` to the whole-store `_Places(snapshot.inventory)` construction (i.e., run
Assertion 1 against the OLD code path) and confirm it goes red — `after_loaded -
before_loaded` should be close to the total card count in the fixture store (all five
20-card boxes = up to 100, not ≤20). Record this as the mutation-tested arm in the PR
description, the way `docs/DEBTS.md` and the mutation-tested guards elsewhere in this repo
report survivor/kill counts (see e.g. `make reap-selftest`'s "twenty-two arms" framing in
`CLAUDE.md` for the expected report shape — this item is not required to build a formal
mutation harness, just to demonstrate the arm by hand and say so).

### `app/tests/orders.spec.ts`

Read it in full (or at minimum every `place: place({...})` call site, `grep -n "place(" app/tests/orders.spec.ts`)
and confirm the fixture-stubbing helper `place(...)` is a CLIENT-side test fixture that
fabricates whatever `Place` shape the test wants — it does not read anything from the
server this item changes. Run `make design-check ARGS=tests/orders.spec.ts` (per `CLAUDE.md`'s
`PW_ARGS`/`ARGS` split — use `PW_ARGS=tests/orders.spec.ts`, not `ARGS`, per D136) after the
server change lands, backgrounded per the working agreement, to confirm nothing broke. This
spec should be UNAFFECTED because it never talks to the real server.

## Allowlist entries removed

**None expected.** `docs/specs/store-scaling.md` §4's allowlist (the `unscoped walk` guard's
census) does not list `do_orders`, `_Places`, or anything in
`server/capture_server.py:9027-9130` — the paragraph explicitly separates this route out as
"O(cards) all the same" WITHOUT being an unscoped walk (`positions_for_sku` is indexed,
`_Places` is lazy per box). So this item removes zero allowlist rows. If item 1 (the
`unscoped walk` guard) has already landed by the time this item is implemented, run
`make docs-audit` after this item's changes and confirm the `unscoped walk` row is still
`ok` and unchanged — `Inventory.occupied_indices`'s `self.cards.select(...)` calls are
scoped by `box=` exactly as `_positions_in`'s are, so they should not trip a guard modeled
on `_positions_in`'s own precedent. If the guard's allowlist or pattern DOES flag the new
method, that is a bug in the guard (a scoped `select` matching an "unscoped" pattern), not a
reason to add an allowlist entry — read `scripts/checks.py`'s `check_unscoped_walk` (once it
exists) before deciding which.

## Do not touch

- **The wire shape.** `PlaceBlock` (`app/src/types.ts:~1200-1272`) is unchanged: every field
  stays present, `neighbors`/`section_gaps` go through the SAME optional-null path the
  degraded case already uses (no new field, no removed field, no renamed field).
  `app/tests/orders.spec.ts`'s stubbed fixtures must keep passing unmodified.
- **`pipeline/orders.py`'s resolution arithmetic** — `_Draw.copies` (`:434-472`),
  `order_engine.resolve_all` (`:582-612`) — UNLESS research (see "Read first" and the "Call
  sites" table's open question about line 8825) finds it iterating `inventory.cards`
  unscoped somewhere this playbook did not catch. If it does NOT walk unscoped (the
  expected finding, since it goes through `positions_for_sku`), leave it untouched; this
  item is about `_Places`, not about the resolver.
- **`store/orders.py` and the ledger** (D63) — this item reads the ledger through the same
  `Store().read()` snapshot `do_orders` already takes; it does not add a write, a lock, or a
  second store read. `do_orders` remains read-only.
- **`_walk`, `_boxmates`, `_company`'s existing behavior for every OTHER caller.** The only
  change to shared `_Places` machinery is: (a) a new `_sparse` flag defaulting to `False`,
  (b) one early-return line in `_company` gated on that flag, (c) a new classmethod. Every
  existing call site (`do_inventory`, `do_search`, `_card_summary`, etc.) uses the ordinary
  constructor and is byte-for-byte unaffected — confirm with `make harness` (all nine
  suites) before and after, not just the new T7 cases.
- **`Position` in `pipeline/join.py`.** This item does not touch it. It only supplies a
  different, cheaper `occupied` tuple as an argument to the SAME `Position(...)` call
  `_Places.of` already makes (`server/capture_server.py:2308`,
  `position = join.Position(number, at, layout, occupied)`) — the one label formula stays
  the only label formula.

## Measure

Follow `docs/specs/store-scaling.md` §1's own recipe: a `.backup` copy of the real store,
and the same copy with every `cards`/`events` row duplicated 20x. Exact commands (adjust
paths to wherever the owner's real `inventory/store.sqlite` and the existing 20x copy from
the plan's own measurement session live — check `docs/specs/store-scaling.md`'s history or
ask, rather than re-deriving the 20x duplication script if one already exists from the
item-1-5 measurement sessions; grep for one before writing a new one):

```bash
# From this worktree, never the owner's live checkout (D43, D158) — always a copy.
cp /path/to/real/inventory/store.sqlite /tmp/store-scaling-06/store.sqlite
PKMNSCAN_HOME=/tmp/store-scaling-06 python3 -c "
import time
from server import capture_server
t0 = time.perf_counter()
for _ in range(5):
    capture_server.do_orders()
print('median-ish single run: measure 5, report the middle one, matching the plan\'s own methodology')
"
```

Run once against the plain `.backup` copy (expect close to the recorded 185 ms baseline —
if this item is a net win, expect it to drop, since even the touched boxes now skip full
`Card` hydration) and once against the 20x copy (expect the 3,465 ms figure to come down
toward something much closer to flat — the whole point of the item — report the actual
number rather than assuming "flat" and stopping there; if it is NOT flat, that is a finding
to write into the PR, not a reason to hide the measurement). Report both numbers, both
copies, five runs each, median, in the PR description in the same table shape
`docs/specs/store-scaling.md` §1 uses. Do not edit that table in place — append the new
figures as a dated addendum in the PR body, and let a follow-up doc session fold the
addendum into the spec (per `CLAUDE.md`'s rule that measured numbers are evidence and are
never rewritten to match a later tree).

If no 20x-duplicated copy exists yet in this worktree, building one is one query:

```sql
-- Illustrative — verify column list against `PRAGMA table_info(cards)` /
-- `PRAGMA table_info(events)` first; do not guess the column list.
INSERT INTO cards (key, box, idx, state, sku, ...)
SELECT key || '-dup' || n.value, box, idx, state, sku, ...
FROM cards, (SELECT value FROM generate_series(1, 19)) AS n;
```

(SQLite's `generate_series` needs the `series` extension or a recursive CTE substitute —
check what the item-1 through item-5 sessions actually used, since they already built this
copy once; re-deriving it independently risks a subtly different duplication shape that
makes this item's numbers incomparable to the other five items'.)

## Risks

- **The biggest risk is silently defeating the optimization while every test still passes**,
  because `_Places.for_keys(...).of(...)` and `_Places(...).of(...)` are designed to return
  the SAME dict (minus two null fields) — a bug that calls `_walk` anyway (e.g. forgetting
  the `self._sparse` check in `_company`, or a future refactor of `.of()` that adds a new
  path into `_walk`/`_boxmates` outside `_company`) produces IDENTICAL output with the old
  cost. Assertion 1 (the `loaded_count` check) is the only thing that catches this — do not
  skip it or weaken it to "the response looks right."
- **`_order_stamps` (`:8751`, call site `:8829`) shares `do_orders`'s exact defect** and is
  not in `docs/specs/store-scaling.md`'s item 6 text, only in this playbook's own reading of
  the code. If the PR fixes `do_orders` alone and leaves `_order_stamps` on the ordinary
  constructor, say so explicitly in the PR rather than letting the omission be found later —
  see "Call sites" above for the recommendation to fix both in one PR.
- **`Inventory.occupied_indices`'s correctness on a box with unreadable records.** The
  two-loop refuse-everywhere pattern is copied from `_positions_in` by hand in this
  playbook's sketch, not verified by running it — the implementing session must add a T7
  case mirroring whatever existing `_positions_in`/`records_in` degrade test exists (grep
  `BadPosition` in `t7_store_and_seams.py`) using `occupied_indices` instead, before trusting
  the sketch's refusal behavior.
- **`Position._divider`'s "unfilled" branch** (a divider declared past the box's captured
  cards, `pipeline/join.py:238-252`) depends on `occupied[-1]` (the max on-hand index) via
  `high_water`. `occupied_indices`'s returned tuple supplies this correctly (it is the real
  sorted tuple of on-hand indices, not a fabricated proxy), so this should be fine by
  construction — flagged here only because Assertion 3 above is the one test that actually
  exercises it, and it must not be skipped without the one-line justification that section
  asks for.
- **Ordering against item 2.** If item 2 lands first and changes `store/rows.py:177`'s
  degrade rule, re-run this item's tests after rebasing — the "Depends on" section argues
  they are independently correct, but re-running costs nothing and the interaction has not
  been observed, only argued.
