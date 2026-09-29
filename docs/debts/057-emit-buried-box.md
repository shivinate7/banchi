## DEBT57 — an emit over a buried box made ghost cards and phantom copies

**Symptom.** The pricing Send of 2026-09-27T16:21:59Z emitted over 12 runs, including
`2026-09-01-box5-01`. Box 5 (bid 5) was buried on 2026-09-16, with a `box_deleted` event, 105
`buried` events (100 with `moved_to`) and no `boxes` row. The emit created 99 ghost cards in
box 5 (cid `nophoto:...`) and published about 96 phantom copies to TCGplayer.

**Cause, confirmed in code.** Two gaps, each enough alone.
1. `Inventory.box_disowns_run` returned None when the box had no registry row, so
   `refuse_reallocated` (D36, D145) never refused a run over a buried box.
2. `cli/cmd_emit.py` `_stamp_single` and `_stamp_merged` called `record_capture` as an upsert
   for every uncommitted position, then `set_state` and `bind_sku`. A position with no card
   was born there, and its copy was counted as pushed.

**Why `realign` (D36) passed the keys through.** Its evidence was gone with the box.
`follow_moved` reads `cards.get(key)` for a `moved` tombstone. `do_delete_box` deletes the
card rows and writes the tombstones only as `buried` events, so no row at `5/n` exists and
the answer is "not a moved card". The per-box photograph check found no box-5 photographs
and answered `unverified`, which passes keys through untouched. `unverified` never refuses.

**Fix.** `Inventory.box_disowns_run` takes the store's `box_deleted` events (`deleted=`) and
refuses a run over a box with no row when the event's `bid` equals the run's `bid`, or, with
no `bid` on either side, when the deletion came after the run started. `refuse_reallocated`
and `cmd_rescue._stranded_because` read the events. `emit` now refuses, before any file is
written, when a position it would send has no card in the store (`_unheld_positions`). The
upsert is removed. No real caller needs it: only a hand-made identifications file did.
Test: `check_emit_buried_box` in `harness/tests/t7_store_and_seams.py`.

**Live state.** On 2026-09-29, on the owner's word, the store was backed up
(`~/pkmnscan-backups/store-before-box5-nuke-20260929T024312Z.sqlite`) and the 99 ghost rows were
removed through `Store().write()`, one `ghost_removed` event each. The store now holds 3510
cards. The live quantities were lowered by 96 copies in 64 SKUs, using negative
`Add to Quantity` pushes (the D100 amendment on another branch records the measurement).
