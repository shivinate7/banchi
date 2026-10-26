## DEBT61 — six build proposals are still open

Each open item was checked against the code and stays open. None is ruled to build. The owner picks which to take.

1. `pipeline/join.py`, `Catalog._blank_number_by_name`: the index key is stripped and not case-folded, while D35's name index folds through `_name_compare_key`. A case mismatch in the name-only fallback (`rows_for_blank_number_name`) finds no row. Unmeasured: how often this fires on real cards.
2. `server/pipeline_routes.py`, `do_pipeline_scope`: one GET reads the identifications file twice, because `_scope_counts` reads it and `_scope_for_run` calls `_scope_counts` again.
3. Fixed. `app/src/RunPanel.tsx` clears `detail` in a layout effect whenever `openRun` changes, so the loading panel draws in place of the old run until the new answer lands.
4. Closed, no change. The arrow-key listeners in `app/src/BoxBrowse.tsx` and `app/src/RunsComposer.tsx` skip typing targets only. No web API reports a screen reader's browse mode. NVDA and JAWS hold arrow keys in browse mode, so the page never sees them. Neither was tried with a real screen reader (unmeasured).
5. String-keyed `getattr` and `setattr` on card fields in `store/master.py` and `server/capture_server.py`: a typo is a silent no-op or a runtime `AttributeError`, and no tool catches it first.
6. `server/capture_server.py` is the largest backend file, ahead of `server/pipeline_routes.py` and `pipeline/join.py`. No split is proposed.
7. `CaptureScreen.tsx`, `ReviewQueue.tsx` and `BoxBrowse.tsx` each mix polling, derived state and JSX in one file. The direction is one hook per screen, so the component file holds only JSX.
8. No Python type checker (`mypy`, `pyright`) is configured. Ruff is adopted (D82) and nobody argued the absence. The cheap first step is `mypy --strict` on one well-typed module (`store/orders.py` or `codes/qr.py`).

Considered and rejected: a router library (about ten stable hash routes, and specs test them end to end), a state-management library (`app/src/server.ts` is already the one network seam) and a component library or CSS framework (styling is token-based and no drift was found).
