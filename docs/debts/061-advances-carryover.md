## DEBT61 — eight build proposals are still open

Each item was checked against the code and stays open. None has an owner ruling to build it. The owner picks which to take.

1. `pipeline/join.py`, `Catalog._blank_number_by_name`: the index key is stripped and not case-folded, while D35's name index folds through `_name_compare_key`. A case mismatch in the name-only fallback (`rows_for_blank_number_name`) finds no row. Unmeasured: how often this fires on real cards.
2. `server/pipeline_routes.py`, `do_pipeline_scope`: one GET reads the identifications file twice, because `_scope_counts` reads it and `_scope_for_run` calls `_scope_counts` again.
3. `app/src/RunPanel.tsx`: When `openRun` becomes null, `detail` clears. It does not clear on a switch to a different run. Old numbers stay on screen until the next poll answers (one request). Unmeasured on a slow server.
4. Window-level arrow-key listeners in `app/src/BoxBrowse.tsx` and `app/src/RunsComposer.tsx` skip typing targets and are not guarded against a screen reader's browse mode.
5. String-keyed `getattr` and `setattr` on card fields in `store/master.py` and `server/capture_server.py`: a typo is a silent no-op or a runtime `AttributeError`, and no tool catches it first.
6. `server/capture_server.py` is the largest backend file, ahead of `server/pipeline_routes.py` and `pipeline/join.py`. No split is proposed.
7. `CaptureScreen.tsx`, `ReviewQueue.tsx` and `BoxBrowse.tsx` each mix polling, derived state and JSX in one file. The direction is one hook per screen, so the component file holds only JSX.
8. No Python type checker (`mypy`, `pyright`) is configured. Ruff is adopted (D82) and nobody argued the absence. The cheap first step is `mypy --strict` on one well-typed module (`store/orders.py` or `codes/qr.py`).

Considered and rejected: a router library (about ten stable hash routes, and specs test them end to end), a state-management library (`app/src/server.ts` is already the one network seam) and a component library or CSS framework (styling is token-based and no drift was found).
