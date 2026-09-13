# The store at 50,000 cards

**Status: BUILT 2026-09-13, all eight items, in three phases** — #337 (item 1), #341 (2,
D192), #339 (3, D191), #340 (4), #338 (5), #342 (6), #344 (7), #343 (8), merged in that
phase order on the owner's standing word. The `unscoped walk` meter ended at **9, not 6**:
item 2 removed nothing (`_boxes_named` is `do_status`'s), item 4 replaced one entry with its
own one-pass `select`, and item 7 kept a renamed entry each for `GET /pipeline/value`'s
aggregate and `box_views`'s unbounded branch, because a store-wide ranking is O(cards) by
nature and reads two indexed columns rather than building a `Card`. Two screens still read
`GET /inventory` whole and say why (`docs/DEBTS.md` §27). `docs/specs/store-scaling/
00-phases.md` has the per-phase counts and the schema versions as they were actually taken.
The paragraphs below are the plan as agreed; §1's table carries the after-figures each PR
measured. The owner's inventory is 2,535 cards today and
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
mechanisms compound it, and the first was mis-anchored until 2026-09-12's review read the
file.** `store/rows.py:226-228` and `:247-250` — every `where()` and `select()` ends with a
Python pass over EVERYTHING THE SESSION HAS LOADED SO FAR, whether or not a full load
happened (the SQL half at `:220-225` is skipped only once `_complete` is set; the Python
half never is). So a scoped call is cheap only while little is loaded: after
`to_payload()` it scans every card, and a sequence of per-SKU calls scans a cache that
each call grows. The investigation cited `:177` (`__len__`), which is not the mechanism.
And `cli/resolve.py:_copies_out` (`:487`) and `_committed_keys` (`:676`) each make one
`where(sku=…)` per listing, so each is quadratic in listings ON ITS OWN through that pass
— O(listings × copies loaded), which at 50,000 cards with proportional listings is the
single largest figure in the plan.

## 1. Measured

Five runs each, median, on the owner's store copied with `sqlite3 .backup` and the
worktree's own `PKMNSCAN_HOME`; the 20x column is the same copy with every row of `cards`
and `events` duplicated under new keys.

| Call | today (2,535 cards) | 20x rows | ratio | where it is pressed |
|---|---|---|---|---|
| `Inventory.to_payload()` — `GET /inventory` | 78 ms | 1,485 ms | 19.0x | Home, Inventory, Fulfillment, Orders, on load; Inventory again after **every** sale, retire, move and reshoot |
| `do_orders()` — `GET /orders` | 185 ms | 3,465 ms | 18.7x | Orders and Shipping on load |
| `Store.history()` | 16.5 ms | 345 ms | 20.9x | **every** mark-sold press (`_sale_origin`, `server/capture_server.py:7232`), every queue-answer undo, stand-down undo and retirement reversal — **FIXED, see D191: `Store.history_at(key)` scopes the read to the key's own box via the existing `events_position` index. Re-measured on this session's own copy of the owner's store: base 13.68 ms / 20x 309.50 ms for the unscoped read (this store's own numbers, close to the figures above); the new `events_at('3/1')` reads 3.77 ms on the base copy and 3.74 ms on a 20x-larger store where box 3's own size is held fixed (new cards added as new boxes, not by inflating existing ones) — flat, as the fix claims. On the plan's own duplication recipe (every existing box, including box 3, ALSO inflated 20x, which is what "duplicate every row" does when positions aren't remapped), `events_at('3/1')` reads 96.9 ms against `history()`'s 309.5 ms at the same store size — worse than "flat" because that recipe confounds store size with box size, but still ~3.2x faster than the unscoped read it replaces.** |
| `_copies_out` (before item 4) | 1,617 ms / 753 listings, 2,535 cards | 32,478 ms / 753 listings, 50,700 cards | 20.1x | `GET /pipeline/pricing`'s default landing (`pipeline_routes.py:2405`), `cli/resolve.py:1916` |
| `_copies_out` (after item 4 — one `select()` via `_cards_by_sku`) | 6.6 ms | 189 ms | 28.6x | same call sites — 245x and 172x faster than the row above, at 1x and 20x respectively |

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
  `pkmnscan readings adopt --write` press; a join, an export fetch, `reconcile --live`, a deleted
  run and a corpus change all leave it stale, nothing on screen says so, and D189 names
  that as out of scope. Its migration is `CREATE TABLE IF NOT EXISTS` under the store lock,
  idempotent and `-9`-safe; its selftest proves populate and re-populate and never proves
  staleness. It merged as D189 while this plan was written; §3's item 5 finishes it.
- **Two of the three "direct scoped precedents" do not transfer.** `do_search`
  (`capture_server.py:7929`) is free text over several fields and has no column to scope
  on; `_release_plan` (`:4526`) aggregates copies of one SKU across every box and cannot
  be answered by `where(box=…)`. `box_views` (`cli/resolve.py:372`) can. And `do_status` is
  not a scoped precedent either: `Inventory.counts()` (`store/master.py:2374`) is an
  unfiltered column scan, cheap per row and full-table.
- **There is no `docs/DEBTS.md` entry about `_copies_out`'s cost, and the investigation's
  "documented in-repo" figure came from a session's memory note.** DEBTS §24 mentions the
  function about a stuck claim's arithmetic, never its speed. The note asked for a `sku`
  index; `cards_sku` exists (`store/db.py:136`, the `_INDEXES` tuple) and `where(sku=…)`
  uses it. What defeats it is the Python pass at `rows.py:226-228`, which every per-SKU
  `where` pays over the cache the previous ones filled. The fix is one pass, not an index.
- **The investigation's `rows.py:177` anchor was wrong**, and two of the three reviews
  gave different mechanisms for the same slowdown until the file was read: §0 has the
  reading. The playbooks were checked against the tree line by line for this reason.

## 3. The plan, in the order it is built

Effort is days of one session. Every item lands as its own PR with the proof it names, and
every item that removes a full walk removes its entry from the guard's allowlist in the same
PR — that count is the plan's progress meter, and it may only go down.

**Each item has a playbook under `docs/specs/store-scaling/`** — `01-guard.md` through
`08-search-fts5.md`, each written so a session with no other context can implement the
item from the file alone: exact signatures, every call site, the SQL, the test names and
the mutation arms. `00-phases.md` is the map for the session driving them — which items
run in parallel worktrees, which wait, and the allowlist count each phase must reach. The
paragraphs below are the argument; the playbooks are the instructions, and where the two
disagree on a line number the playbook is corrected in the PR that finds it.

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
box alone. **`GET /inventory` itself is kept, unused, on the allowlist** — the owner was
asked whether an unused route was harmless and chose to keep it rather than delete it; it
is named there as "kept on the owner's word, no caller". `#/inventory` loads the box it is standing on and re-reads that box — not the
store — after a sale, retire, move or reshoot; the `reloads` counter
(`app/src/BoxBrowse.tsx:663`) is scoped to it. Home takes `Inventory.counts()` and the
per-stage figures it already reads; Fulfillment reads the boxes the order names; Orders
moves under item 6. **And `rows.py`'s post-load pass is bounded**: `where()`/`select()`
consult only the loaded objects that could have CHANGED since they were read — a
`_touched` set, written by `__setitem__` and cleared by the flush — rather than every
object the session has loaded, so a scoped call costs its SQL plus the session's edits
and never its reads (playbook 02, Step 10). Proof: T7 asserts `GET /inventory/<box>` reads one box (the store copy inflated 20x
answers in the same time as today's), and `app/tests/inventory.spec.ts` asserts a sale
issues no `GET /inventory`. Ordered second on the owner's word: it fixes the most screens,
and the two half-day items behind it are not made worse by waiting three days.

**3. `history()` scoped to the box. ½ day, no migration.** `events.position` is already an
indexed column (`store/db.py:139`) holding `"{box}/{index}"`, so the scoped read is a
`GLOB '<box>/*'` range on the existing index. **The scope is the BOX and never the exact
key**: a mid-box delete writes its `renumbered` event under the DELETED card's position
(`capture_server.py:4196`), and every reversal reader relies on seeing it — a key-scoped
read would silently break D10 ruling 1's undo. Two free wins beside it: `_sell` (`:7232`)
and `do_retire` (`:7508`) both read the origin before checking `undo` and never use it on
the non-undo path. Proof: the 20x copy's mark-sold press costs what today's does.

**4. `_copies_out` and `_committed_keys` as one pass each. 1 day.** One `select` over
`(sku, state, box, index, captured_at)` into a dict keyed by SKU, then the arithmetic per
listing — O(cards + listings). `cli/resolve.py:487` and its per-SKU helpers
(`positions_for_sku`, `copies_not_sold`, `sales_before`), and `_committed_keys` (`:676`),
whose `copies_on_hand(sku)` per listing is the same shape and the same PR — leaving it
would be the plan's own defect one function down. Its two callers (`resolve.py:1916`,
`pipeline_routes.py:2405`) already call once per request. **Nets zero allowlist entries**:
the new filter-less `select` is guard-visible and is allowlisted as "one pass, argued",
replacing `_unsent_ledger`'s `distinct("sku")`. Proof: the 0.9 s figure measured on the
store copy before and after, and the 20x ratio.

**5. The `readings` writer. 1 day.** #333 merged as D189 while this plan was written;
this reopens its manual press (§5). `collect()` reads exactly two inputs — a run's
`pricing.json` (written at `cli/cmd_join.py:685`) and the newest `inventory/.live/*.csv`
(`pipeline_routes.py:3550`) — so those are the two wiring sites; `reconcile --live` writes
neither and there is no run-deletion path, so neither is a site. The refresh is per source
(`Readings.replace_source`), never a full re-collect, so a join does not re-parse a live
export it never touched. `readings adopt` stays as the hand repair. Proof:
a selftest arm that joins, does not press adopt, and reads a fresh figure from
`GET /pipeline/value` — the arm the PR's selftest lacks.

**6. `do_orders` and `_order_stamps` per SKU. 1 day.** `_Places.of()` hydrates every
`Card` in a box (`:2130 _walk`) to answer `slot`, and the neighbor/gap decoration that
needs the objects is read by no field `Orders.tsx` draws. A `_Places.for_keys` over
`Inventory.occupied_indices(box)` — a column select modelled on `_positions_in` — answers
`slot` for the boxes an order's resolved picks touch and no other; the stale comment at
`:9075` is replaced with what the route does. **`_order_stamps` (`:8751`, `_Places` at
`:8829`, the Rubber Stamp fill) is the identical walk over every open order and is the
same PR.** Proof: the 185 ms → 3,465 ms table above, re-run.

**7. `do_pipeline_value`, `box_views`, `_release_plan`. 1–2 days.** `_release_plan` becomes
a `GROUP BY sku` over the boxes' live copies; `box_views` reads per box through
`records_in`; `do_pipeline_value` ranks over a `select` of the columns it ranks on rather
than over built card objects, **and the row list is paginated** — the owner's word, "as
long as it's well planned": every aggregate D159 draws (the drawer totals, the three
unpriced causes, "nothing on hand is dropped") is computed server-side over all rows as a
column select, and only the ranked row list pages, by a cursor stable across pages. D159's
figures stay whole; the list stops being one 50,000-row response. Five allowlist entries
go (`_box_names` and `_on_hand_by_run` beside the three named).

**8. Search gets an index. 2 days.** On the owner's word over the recommendation to record
it as a debt. `do_search`'s docstring calls its full walk deliberate, and it was — at 2,535
cards a single pass is the honest answer. At 50,000 it is not — and the cost was never the
text match, it was building 50,000 card objects to get at the text. **FTS5 over `LIKE`, on
the owner's word after a walkthrough**: they chose multi-word any-order matching and
best-match ranking, were told mid-word matching (`izard` → Charizard) is lost, and took it;
the playbook adds prefix matching so a partial word still hits. An external-content FTS5
table over `cards` with the three sync triggers, so the index maintains itself inside the
same transaction as every write (D88's invariant, with no Python hook to forget). FTS5 is
compiled into the rig's SQLite (3.54.0, probed); `cards` has a TEXT key and a stable
implicit rowid because `upsert` is `ON CONFLICT DO UPDATE` (`db.py:1092`), so
`content_rowid='rowid'` holds. Tokenizer `unicode61` with `tokenchars '/-'`, so `039/236`
and `OP15-079` stay one token. **It takes schema version 7** (D189 took 5; item 2's
`cards_captured_at` index reached the 6 this section originally reserved for search first —
D192 — so item 8 renumbers its own, the D140 rule applied to schema versions; item 3 takes
none).
**`scripts/cid-selftest.py:table_bytes` byte-compares every table off `sqlite_master`**
and FTS5's shadow tables are not byte-stable across rebuilds — the playbook carves
`cards_fts*` out of that comparison. **The walk is deleted, not kept as a fallback** — the migration builds the index on first open,
so no store lacks one, and D86's rule against reading a legacy path as a fallback applies.
Proof: T7 asserts the index and the deleted walk agree on single-word and number queries
over the fixture store, that a capture, a sale, a move and a rename are searchable in the
same transaction, and that dropping one trigger fails it.

**~9–11 days of one session; fewer on the wall clock under `00-phases.md`'s layout**, which
runs items 2–5 in parallel worktrees once the guard is in, and 6–8 in parallel once those
four have merged. Items 1–4 are the floor — they fix every per-press cost and the two
screens pressed most. Items 5–8 each stand alone and any of them can slip past the window
without taking another with it.

## 4. The allowlist the guard starts from

Taken 2026-09-12. Per-press means a write handler; per-load means a screen opening.

| Site | Shape | When | Removed by |
|---|---|---|---|
| `server/capture_server.py:3056` `do_inventory` | `to_payload()` | per-load, four screens; per-press on Inventory — until item 2, after which nothing calls it | stays — kept on the owner's word, no caller; the guard names it |
| `server/capture_server.py:4549` `_release_plan` | `.items()` | per-press (release preflight) | item 7 |
| ~~`server/capture_server.py:7970` `do_search`~~ | ~~`.values()`~~ | ~~per-keystroke~~ | **CLOSED by item 8 — `do_search` reads an FTS5 index (`store/db.py:_add_search_index`); row removed from `scripts/docs-audit.py`'s `UNSCOPED_WALK_ALLOWED`, `UNSCOPED_WALK_EXPECTED` 13 -> 12** |
| `server/capture_server.py:8349` `_boxes_named` | `select(("box",))` | per-load | **stays — verified 2026-09-12 by item 2: its only caller is `do_status`, untouched by item 2, so it cannot close this row; a future item scoping `do_status` removes it** |
| `server/capture_server.py:8388` `do_boxes` | `distinct("box")` | per-load | stays — one column, cheap; the guard names it |
| `server/pipeline_routes.py:838` `_box_names` | `select(("box","run"))` | per-load | item 7 |
| `server/pipeline_routes.py:2370` `_unsent_ledger` | `distinct("sku")` | per-load | item 4 |
| `server/pipeline_routes.py:2444` `_on_hand_by_run` | `select(("run","state"))` | per-load | item 7 |
| `server/pipeline_routes.py:3202` `do_pipeline_value` | `.values()` | per-load | item 7 |
| `store/master.py:1447` `to_payload` | `.items()` | called by `do_inventory` alone | stays with `do_inventory` |
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

**D189's manual `readings adopt` press.** Written the same day as the plan it belongs to,
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
