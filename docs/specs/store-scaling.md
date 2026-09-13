# The store at 50,000 cards

**Status: SPECIFIED 2026-09-12, NOT BUILT.** The owner's inventory is 2,535 cards today and
is expected to reach 50,000 inside two weeks. Every screen but Capture has been getting
slower. This file is the plan the owner agreed to on 2026-09-12, after an interview over
four parallel investigations and three reviews of those investigations — the reviews
reversed two of the six items and added three, which is why the plan below is not the punch
list the investigations produced. Every figure here was measured on a `.backup` copy of the
owner's real store, then on that copy with every `cards` and `events` row duplicated twenty
times; nothing here was taken from a report without being re-run.

**The ordering is the owner's.** Asked whether the mechanical guard or the systemic fix goes
first, they chose the guard first and the systemic fix immediately after it, ahead of the two
half-day wins; asked whether free-text search stays a full walk, they said no. Both are
recorded below with the argument they overruled.

## 0. What is wrong, in one paragraph

`Store().read()` costs 0.14–0.35 ms whatever the store holds; SQLite is not the problem and
D88's benchmark stands. The cost is that almost every non-capture handler in `server/`
materialises the whole `cards` table — `Inventory.to_payload()`, a `.values()`, a
`.items()`, or a column `select` with no filter — and then does per-card work over it.
Capture is exempt because `allocate_capture` reads one box through the indexed `box`
column (`store/master.py:records_in`), measured flat at 3.9 ms at every store size. **Two
mechanisms compound it.** `store/rows.py:177` — once one call in a request has loaded every
row, every later `where()` and `select()` on that collection answers from the Python-side
list rather than from SQL while still looking scoped, so a handler that materialises first
and filters second gets no benefit from the index at all. And `cli/resolve.py:_copies_out`
calls `positions_for_sku` and `copies_not_sold` once per listing, each a pass over the loaded
rows: O(listings × cards), which at 50,000 cards with proportional listings is the single
largest figure in the plan.

## 1. Measured

Five runs each, median, on the owner's store copied with `sqlite3 .backup` and the
worktree's own `PKMNSCAN_HOME`; the 20x column is the same copy with every row of `cards`
and `events` duplicated under new keys.

| Call | today (2,535 cards) | 20x rows | ratio | where it is pressed |
|---|---|---|---|---|
| `Inventory.to_payload()` — `GET /inventory` | 78 ms | 1,485 ms | 19.0x | Home, Inventory, Fulfillment, Orders, on load; Inventory again after **every** sale, retire, move and reshoot |
| `do_orders()` — `GET /orders` | 185 ms | 3,465 ms | 18.7x | Orders and Shipping on load |
| `Store.history()` | 16.5 ms | 345 ms | 20.9x | **every** mark-sold press (`_sale_origin`, `server/capture_server.py:7232`), every queue-answer undo, stand-down undo and retirement reversal |
| `_copies_out` | ~0.9 s / 753 listings (in-repo, `docs/DEBTS.md`) | unmeasured; quadratic by reading | — | `GET /pipeline/pricing`'s default landing, `GET /pipeline/value` |

**`GET /orders` was a named contradiction and it is resolved: the route's comment is stale
and the route is slow anyway.** `_Places.__init__` (`server/capture_server.py:2029`) does
no eager scan, its docstring says "per box since D88, and lazily", and `positions_for_sku`
is an indexed `where(sku=…)`. The comment at 9075 saying it "walks the entire store per
instantiation" is wrong about the mechanism. The measurement says the route is O(cards) all
the same: the store has five boxes, every order's picks span most of them, and a per-box
read of a store that is five boxes is a fifth of a full read, five times.

**`history()` was flagged by one investigation of four and unquantified. It is on the
hottest write path in the product.** `store/db.py:1208` is `SELECT id, payload FROM events
ORDER BY id` with a `json.loads` per row, unconditionally, and `_sell` calls it before the
`if undo:` branch — so a Fulfiller marking cards sold hundreds of times a day pays a
full-table read of an events table that grows with every write ever made, on every press.

**Photo storage is not a finding.** The "near-empty `captures/`" that made one investigation
doubt the 4.45 GB snapshot was a worktree's own store (D43); the main tree's is 5.1 MB of
captures and 16 MB of inventory today, and the projection stands on the snapshot.

## 2. What the punch list got wrong

The plan below is not the six-item list the investigations handed over. Three reviews were
run against it on the owner's instruction — *"review what was built, don't take what was
made for granted"* — and these are the corrections, kept here so the next session does not
re-derive the original list from the investigation's own journal.

- **"Stop BoxBrowse's refetch" has no narrower route to switch to.** `GET /boxes/<n>` is
  deliberately refused at `server/capture_server.py:10687` — *"a per-box read would be a
  second renderer for one caller that does not exist yet"*. The caller exists. So the
  item is the per-box read itself, and it merges with the systemic fix rather than
  preceding it. The write responses already carry the updated `CardSummary`
  (`_card_summary`, `capture_server.py:7757`) and the screen reads one boolean from it.
- **`GET /pipeline/pricing` never walked every run.** `do_pipeline_pricing`
  (`pipeline_routes.py:2030`) reads one run's `pricing.json` and the corpus. What walks is
  `do_pipeline_worklist`'s default landing over every open run, and what is slow inside it
  is `_copies_out`. The multi-run walk with the 32 MB CSV re-parse lived in `_readings()`
  alone, which PR #333 moves out of the request.
- **PR #333 is safe and unfinished.** The `readings` table is populated only by a manual
  `readings adopt --write` press (a subcommand that PR adds); a join, an export fetch, `reconcile --live`, a deleted
  run and a corpus change all leave it stale, nothing on screen says so, and the decision entry that PR carries names
  that as out of scope. Its migration is `CREATE TABLE IF NOT EXISTS` under the store lock,
  idempotent and `-9`-safe; its selftest proves populate and re-populate and never proves
  staleness. The owner's orchestrator is merging it; §3's item 5 finishes it.
- **Two of the three "direct scoped precedents" do not transfer.** `do_search`
  (`capture_server.py:7929`) is free text over several fields and has no column to scope
  on; `_release_plan` (`:4526`) aggregates copies of one SKU across every box and cannot
  be answered by `where(box=…)`. `box_views` (`cli/resolve.py:372`) can. And `do_status` is
  not a scoped precedent either: `Inventory.counts()` (`store/master.py:2374`) is an
  unfiltered column scan, cheap per row and full-table.
- **`docs/DEBTS.md`'s `_copies_out` entry names the wrong fix.** It asks for a `sku` index
  on `Rows`; `cards_sku` exists in the schema (`store/db.py:136`) and `where(sku=…)` uses
  it. What defeats it is `rows.py:177`: the callers materialise the store first, so every
  per-SKU `where` after that is a Python pass. The fix is one pass, not an index.

## 3. The plan, in the order it is built

Effort is days of one session. Every item lands as its own PR with the proof it names, and
every item that removes a full walk removes its entry from the guard's allowlist in the same
PR — that count is the plan's progress meter, and it may only go down.

**1. The guard — `make docs-audit`'s `unscoped walk` row. ½ day.** A pass over `server/*.py`
and `store/master.py` that names every `.values()`, `.items()`, `to_payload()` and
filter-less `select`/`distinct` over `inventory.cards`, against an allowlist that is exactly
the census taken 2026-09-12 (twelve sites, §4). A new site fails the commit; a removed site
is removed from the list in the same PR or the row reports an allowlist entry that resolves
to nothing. Shaped like `storage keys`: a `check_unscoped_walk(report)` called from
`audit()`, `report.add` with the count. It goes first because six PRs follow it and each
one is checked against it; landing it last would mean every one of them went in with no
reader. **It cannot see `rows.py:177`** — a scoped-looking call that degrades at run time —
and says so in its docstring; item 2 removes the degradation instead.

**2. The per-box read, and the screens move to it. 2–3 days.** Reopens the refusal at
`capture_server.py:10687` (§5). `GET /inventory/<box>` returns one box's cards in the shape
`GET /inventory` returns them today, through `records_in`, with `_Places` built for that
box alone. `#/inventory` loads the box it is standing on and re-reads that box — not the
store — after a sale, retire, move or reshoot; the `reloads` counter
(`app/src/BoxBrowse.tsx:663`) is scoped to it. Home takes `Inventory.counts()` and the
per-stage figures it already reads; Fulfillment reads the boxes the order names; Orders
moves under item 6. **And `rows.py:177`'s fallback goes**: a `where()`/`select()` after a
full load answers from SQL like one before it, so a scoped call is scoped whatever ran
first. Proof: T7 asserts `GET /inventory/<box>` reads one box (the store copy inflated 20x
answers in the same time as today's), and `app/tests/inventory.spec.ts` asserts a sale
issues no `GET /inventory`. Ordered second on the owner's word: it fixes the most screens,
and the two half-day items behind it are not made worse by waiting three days.

**3. `history()` scoped to the card. ½ day.** `_sale_origin`, `_answer_origin`,
`_clearing_event` and `_retirement_origin` each want the events of one key;
`store/db.py:events_named` is the shape and the `events` table gets the index it needs.
Proof: the 20x copy's mark-sold press costs what today's does.

**4. `_copies_out` as one pass. 1 day.** One `select` over `(sku, state, box, index)` into
a dict, then the arithmetic per listing — O(cards + listings). `cli/resolve.py:487` and its
two per-SKU helpers. The DEBTS entry is corrected to say what the cost was. Proof: the
in-repo 0.9 s figure re-measured on the same store, and the 20x copy's ratio.

**5. The `readings` writer, once #333 has landed. 1 day.** Reopens the manual press #333's own entry rules for (§5).
`readings.replace(*collect())` runs inside `join`'s, `do_live_export`'s and
`reconcile --live`'s own transactions, and `readings adopt` stays as the hand repair. Proof:
a selftest arm that joins, does not press adopt, and reads a fresh figure from
`GET /pipeline/value` — the arm the PR's selftest lacks.

**6. `do_orders` per SKU. 1 day.** The route resolves each order's lines through
`positions_for_sku` and builds `_Places` for the boxes those copies sit in, never for a box
no line touches; the stale comment at `:9075` is replaced with what the route does. Proof:
the 185 ms → 3,465 ms table above, re-run.

**7. `do_pipeline_value`, `box_views`, `_release_plan`. 1–2 days.** `_release_plan` becomes
a `GROUP BY sku` over the boxes' live copies; `box_views` reads per box through
`records_in`; `do_pipeline_value` ranks over a `select` of the columns it ranks on rather
than over built card objects. Three allowlist entries go.

**8. Search gets an index. 2 days.** On the owner's word over the recommendation to record
it as a debt. `do_search`'s docstring calls its full walk deliberate, and it was — at 2,535
cards a single pass is the honest answer. At 50,000 it is not. SQLite's FTS5 over the
fields the walk reads today, maintained in `Store.write()`'s own transaction (D88's
invariant), and the walk stays only as the path a store with no index falls back to, named.
Proof: T7 asserts the same rows come back from the index and the walk on the fixture store.

**~9–11 days.** Items 1–4 are the floor — they fix every per-press cost and the two screens
pressed most. Items 5–8 each stand alone and any of them can slip past the window without
taking another with it.

## 4. The allowlist the guard starts from

Taken 2026-09-12. Per-press means a write handler; per-load means a screen opening.

| Site | Shape | When | Removed by |
|---|---|---|---|
| `server/capture_server.py:3056` `do_inventory` | `to_payload()` | per-load, four screens; per-press on Inventory | item 2 |
| `server/capture_server.py:4549` `_release_plan` | `.items()` | per-press (release preflight) | item 7 |
| `server/capture_server.py:7970` `do_search` | `.values()` | per-keystroke | item 8 |
| `server/capture_server.py:8349` `_boxes_named` | `select(("box",))` | per-load | item 2 |
| `server/capture_server.py:8388` `do_boxes` | `distinct("box")` | per-load | stays — one column, cheap; the guard names it |
| `server/pipeline_routes.py:838` `_box_names` | `select(("box","run"))` | per-load | item 7 |
| `server/pipeline_routes.py:2370` `_unsent_ledger` | `distinct("sku")` | per-load | item 4 |
| `server/pipeline_routes.py:2444` `_on_hand_by_run` | `select(("run","state"))` | per-load | item 7 |
| `server/pipeline_routes.py:3202` `do_pipeline_value` | `.values()` | per-load | item 7 |
| `store/master.py:1447` `to_payload` | `.items()` | called by `do_inventory` | item 2 |
| `store/master.py:2378` `counts` | `select(("state",))` | `do_status`, polled | stays — one column; the guard names it |
| `cli/resolve.py:372` `box_views` | `.values()` | `GET /pipeline/pricing` | item 7 |

`do_graveyard` (`:5208`), `_box_row` (`:8243`) and `do_put_box` (`:8547`) are scoped today
and are not on the list.

## 5. Three settled things this plan reopens, and why each has rotted

The owner's standing instruction, 2026-09-12: think from outcomes, and flag a ruling whose
premise has gone rather than defer to it. These three are flagged, argued, and taken on
their word.

**The refusal of `GET /boxes/<n>`** (`server/capture_server.py:10687`). Its sentence is
*"a second renderer for one caller that does not exist yet."* The caller is every load of
`#/inventory` and every press on it, and the outcome the refusal protected — one renderer
for a card row — is kept by having the per-box route return the same shape as the
store-wide one. What the refusal costs now is 78 ms per press today and 1.5 s at 50,000.

**PR #333's manual `readings adopt` press.** Written the same day as the plan it belongs to,
and honest about itself — it asks for a second pair of eyes. The outcome it serves is a
correct market figure on `#/pricing`; a table no ordinary write refreshes serves the
opposite the moment a join lands, and the repo's own rule — a route no screen reaches is
not built — applies to a cache no write refreshes.

**`do_search`'s deliberate full walk.** True when written, at a size where an index would
have been machinery. The premise was the size.

## 6. Out of the window, on purpose

- **The photograph's content address** (D172, `docs/specs/stable-card-id.md`) — real,
  partially built, and a schema migration plus ~19 client call sites. Not a quick win and
  not what is slow.
- **A hosted, multi-tenant deployment.** Two of the owner's devices on one LAN against one
  server is already the shape (D53, D138) and needs no project. Auth, a multi-writer
  database, TLS and object storage for photographs are absent and are one effort, never
  folded into this one.
- **The codes ledger** — a full file parse per request, self-documented as breaking past
  ~100,000 *code* entries. A different axis from the card count; it gets its own measurement
  when the code-card track has a real card through it (`docs/specs/code-cards.md` §8).
- **Photo cache headers.** `Cache-Control: no-cache` with ETag is D52's deliberate answer to
  a URL that names a mutable slot, and going further reopens the stale-photo defect that
  entry fixed.
