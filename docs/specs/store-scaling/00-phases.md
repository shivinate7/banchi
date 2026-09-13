# Phases — how the eight items run under a goal function

This directory is the playbook for `docs/specs/store-scaling.md` §3: one file per item,
each written so a session with no other context can implement it from the file alone.
This file is the map for the session DRIVING them — the owner intends a goal-function run
with ultracode, one phase at a time, compacting between phases. Read it first, then only
the item files of the phase you are in.

**The item files were written by eight parallel sessions and then checked against the
tree** — every file:line and every "X does not exist" that a phase depends on was re-read
before this map was finalised, and the corrections are folded into both this file and the
spec's §3. An implementer who finds a line number moved fixes the item file in the PR.

## The graph

```
Phase 0    [1 guard]
              │
Phase 1    [2 per-box read]  [3 history]  [4 _copies_out]  [5 readings writer]
              │  (all four merged)
Phase 2    [6 orders]  [7 value + aggregates]  [8 search FTS5]
```

**Phase 0 runs alone.** Item 1 is the `unscoped walk` docs-audit row. Every later PR
removes or argues an entry on its allowlist in the same PR, so it must exist before any of
them opens — otherwise a PR that adds a walk while removing one is invisible.

**Phase 1 is four PRs in parallel worktrees.** D189 (the `readings` table, PR #333) is on
`origin/main`, so item 5 does not wait. They touch disjoint functions:

| Item | `server/capture_server.py` | `server/pipeline_routes.py` | `store/` | `cli/` | `app/src` |
|---|---|---|---|---|---|
| 2 | `do_inventory` (~3056), `_Places` (~2029), a new `do_inventory_box` on the unused `_INVENTORY_BOX_RE` (`:546`), a new `do_inventory_recent`, the router table | — | `rows.py`: `where`/`select`/`__setitem__`/`flushed` (the `_touched` set) | — | `server.ts`, `BoxBrowse.tsx`, `Inventory.tsx`, `Home.tsx`, `Fulfillment.tsx`, `Orders.tsx` |
| 3 | `_sell`/`_sale_origin` (~7199–7232), `do_retire` (~7508), `_answer_origin` (~5461), `_reverse_stand_down` (~6478), `_origin` (~7185), the prose comment at ~980 | — | `db.py`: `history` gains a box scope; `session.py` passes it. **No schema step** — `events_position` exists (`db.py:139`) | — | — |
| 4 | — | `_unsent_ledger` (~2370–2405): the call site only | — | `resolve.py`: `_copies_out` (~487), `_committed_keys` (~676), and the helpers they stop calling | — |
| 5 | — | `do_live_export` (~3550) | `readings.py`: `Readings.replace_source` | `cmd_join.py` (~685); `pipeline/readings.py`: `collect` split into per-source readers | — |

Two things to know inside the phase:

- **Item 2 took schema version 6, which this file had reserved for item 8.** This file
  said phase 1 claimed none; item 3 indeed needs none, but item 2's `cards_captured_at`
  index needs an upgrade step, because `_ensure_schema` returns after `_repair` on a store
  already stamped at `SCHEMA_VERSION` and never reaches the `_INDEXES` loop — so a tuple
  entry alone would never have indexed the owner's real store. **Item 8 therefore takes 7.**
  If some other branch on `origin/main` takes 7 first, item 8 renumbers its own — the D140
  rule for decision ids, applied to schema versions.
- **Items 2 and 4 both edit `rows.py`'s consumers' behavior without editing the same
  lines** — item 2 changes `Rows.where`/`select`; item 4 stops calling them per SKU. Item
  4's one-pass `select` is correct whether or not item 2 has merged, which is why they can
  run beside each other. Item 4's measurement must be taken on its own branch WITHOUT item
  2, or the two wins cannot be told apart.

**Phase 2 is three PRs in parallel worktrees, after every phase-1 PR has merged.** Item 6
edits `_Places` again (item 2 must be on main first). Item 7 edits `cli/resolve.py`
beside item 4's function and `pipeline_routes.py` beside item 5's wiring (both on main
first). Item 8 edits `do_search` in `capture_server.py` and takes schema version 7 (item 2
took 6 — see above). Within
the phase they are disjoint:

| Item | `server/capture_server.py` | `server/pipeline_routes.py` | `store/` | `cli/` | `app/src` + `app/tests` |
|---|---|---|---|---|---|
| 6 | `do_orders` (~9027), `_order_stamps` (~8751, its `_Places` at ~8829), a new `_Places.for_keys` | — | `master.py`: a new `Inventory.occupied_indices` beside `_positions_in` (~1492) | — | — |
| 7 | `_release_plan` (~4526) | `do_pipeline_value` (~3117), a new `do_pipeline_value_page`, `_box_names` (~838), `_on_hand_by_run` (~2444) | — | `resolve.py:box_views` (~372, gains `boxes=`) | `server.ts`, `ValueBands.tsx` (`stacks`/`pulls` move server-side), `value-bands.spec.ts` (its `/\/pipeline\/value$/` route regex breaks the moment a query string is added — all 18 tests) |
| 8 | `do_search` (~7929), `_match_rank` (~7814) | — | `db.py`: `_upgrade` step 6, FTS5 DDL, three triggers; `scripts/cid-selftest.py:table_bytes` carves out `cards_fts*` | — | `inventory.spec.ts` if ordering is pinned |

## The goal function, per phase

A phase is done when every one of its PRs is merged to `origin/main` AND
`python3 scripts/docs-audit.py --json` reports the `unscoped walk` row's allowlist at the
expected count. The count is the meter; a phase that merges its PRs and leaves the count
where it was has removed nothing.

| After | Expected allowlist | Change |
|---|---|---|
| Phase 0 | 13 (§4 of the spec, twelve sites; `do_inventory` and `to_payload` stay by the owner's word; PLUS `store/master.py:next_box_number`, a real, currently-existing `.distinct("box")` call the hand census in §4 missed — found by item 1's own scanner on its first end-to-end run against the real tree, and permanent for the same reason `do_boxes`/`counts` are) | — |
| Phase 1 | 13 | **corrected 2026-09-12 by item 2**: `_boxes_named`'s only caller is `do_status`, which item 2 does not touch, so it cannot close that row — item 2 removes NOTHING from the allowlist (see D192). Item 4 REPLACES `_unsent_ledger`'s `distinct("sku")` with its own one-pass `select`, argued, so it nets zero. Count stays at 13 |
| Phase 2 | 9 | **as landed 2026-09-13**: item 7 (#344) removed `_release_plan`, `_box_names`, `_on_hand_by_run` and RENAMED the entries for `do_pipeline_value` (now `_value_rows`, one `select` of indexed columns — the D159 aggregate is over every on-hand row by the owner's own ruling and cannot be scoped) and `box_views`'s unbounded branch (its one caller ranks every box); item 8 (#343) removed `do_search`. 13 − 3 − 1 = 9 |

The nine that remain — `do_inventory`, `to_payload`, `do_boxes`, `counts`,
`next_box_number`, `_boxes_named` (`do_status`'s, one indexed column), item 4's
`_cards_by_sku`, and item 7's two renamed entries (`_value_rows`, `box_views`) — are named
in the allowlist with their reason and are the plan's end state, not a residue. The plan
said six; three of the difference are the two store-wide rankings the owner ruled must be
computed over every row, and the third is `_boxes_named`, which no item ever owned. Each
item's own file has the authoritative "Allowlist entries removed" section; if it disagrees
with this table, the item file wins and this table is corrected in the same PR.

**Every PR also passes the measurement in its own "Measure" section** — the `.backup`-copy
recipe from the spec's §1, run before and after, with the 20x ratio written into the PR
body. A PR whose after-figure still scales with the store is not done whatever the tests
say; the tests prove the behavior and the copy proves the scaling, and they can disagree.

## What the driver holds across compactions

Compact after each phase's last merge. Carry forward, verbatim:

1. This file's phase table and the allowlist count the phase reached.
2. The list of PR numbers merged, per item.
3. Any schema version renumbered, and to what.
4. Any item file that was corrected during the phase.

Nothing else from the phase needs to survive: the item files carry the rest.

## Where each item's decisions came from

The owner's rulings of 2026-09-12, recorded here so an implementer does not re-ask:

- **`GET /inventory` is kept, unused, on the allowlist** — they were asked whether an unused
  route was harmless and chose to keep it. Item 2 adds the scoped route beside it.
- **Search is FTS5, not `LIKE`** — chosen for multi-word any-order matching and best-match
  ranking, having been told mid-word matching is lost. Item 8 adds prefix matching so a
  partial word still hits. The walk is deleted, not kept as a fallback.
- **`GET /pipeline/value` paginates** — "as long as it's well planned": every aggregate D159
  draws is computed over all rows server-side; only the row list pages, by a value cursor
  rather than an offset so a concurrent sale cannot skip or repeat a row.
- **The order** — guard first, the systemic per-box read immediately after, search included
  over the recommendation to defer it.
