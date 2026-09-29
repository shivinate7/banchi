## DEBT61 — eight build proposals from the 2026-08-31 review are still open

**Source.** A review on 2026-08-31 listed candidate build directions in a file that has been
deleted. The owner ruled that old records are deleted. Each proposal was checked against the
code on 2026-09-29. The three that follow are already closed, and they are dropped:

- Set-hint narrowing in `Catalog.candidates` now chooses the set first, then filters its rows.
- `aria-live` now appears in `app/src` (for example in `App.tsx` and `Pricing.tsx`).
- The four big screens no longer call `fetch` directly, so the seam gap named for them is gone.

**Still open, one file each.**

1. `pipeline/join.py`, `Catalog._blank_number_by_name`. The index key is stripped and not
   case-folded. The name index of D35 (name fallback) folds through `_name_compare_key`. A case
   mismatch in the name-only fallback (`rows_for_blank_number_name`) finds no row. Unmeasured:
   how often this fires on real cards.
2. `server/pipeline_routes.py`, `do_pipeline_scope`. One GET reads the identifications file
   twice. `_scope_counts` reads it, then `_scope_for_run` calls `_scope_counts` again.
3. `app/src/RunPanel.tsx`. When `openRun` becomes null, `detail` clears. It never clears on a
   switch to a different run. The old numbers stay on screen until the next poll answers. The
   poll restarts at once, so the window is one request. Unmeasured on a slow server.
4. Window-level arrow-key listeners in `app/src/BoxBrowse.tsx` and `app/src/RunsComposer.tsx`.
   Each one skips typing targets. Neither one is guarded against a screen reader's browse mode.
5. String-keyed `getattr` and `setattr` on card fields, in `store/master.py` and
   `server/capture_server.py`. A typo in a field name is a silent no-op or a runtime
   `AttributeError`. No tool in the repo catches it first (see item 8).
6. `server/capture_server.py` is 17,673 lines, the largest backend file (`server/pipeline_routes.py`
   is 8,118 and `pipeline/join.py` is 3,490). No split is proposed. The entry records the size.
7. `CaptureScreen.tsx` (5,637 lines), `ReviewQueue.tsx` (3,066) and `BoxBrowse.tsx` (3,222)
   each mix polling, derived state and JSX in one file. The direction is one hook per screen,
   so the component file holds only JSX.
8. The repo has no type checker. No `mypy` or `pyright` config exists. Ruff is adopted (D82),
   and nobody argued the absence of a type checker. The cheap first step is `mypy --strict` on
   one well-typed module, `store/orders.py` or `codes/qr.py`, before any wider gate.

**Considered and rejected.** A router library: the app has about ten stable hash routes, and
specs test them end to end. A state-management library: `app/src/server.ts` is already the one
network seam. A component library or CSS framework: styling is token-based, and no drift was
found. None of the three has a measured problem to solve.

**Why not fixed now.** Each item is small, and none has an owner ruling to build it. The owner
picks which one to take.
