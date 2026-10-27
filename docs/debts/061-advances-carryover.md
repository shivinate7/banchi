## DEBT61 — six build proposals are still open

Each open item was checked against the code and stays open. None is ruled to build. The owner picks which to take.

1. `pipeline/join.py`, `Catalog._blank_number_by_name`: the index key is stripped and not case-folded, while D35's name index folds through `_name_compare_key`. A case mismatch in the name-only fallback (`rows_for_blank_number_name`) finds no row. Unmeasured: how often this fires on real cards.
2. `server/pipeline_routes.py`, `do_pipeline_scope`: one GET reads the identifications file twice, because `_scope_counts` reads it and `_scope_for_run` calls `_scope_counts` again.
3. Fixed. `app/src/RunPanel.tsx` takes a run read only when it names the open run, so a late answer for the run just left never replaces the open run's. On a direct switch the panel on screen is drawn from the new run's list row, with the row's own step open and no line that needs the manifest or the console. Its header and body are inert and dimmed, and a failed read still shows its notice. A first open still draws the loading panel. Two limits are accepted for now and not fixed. (a) The stand-in leaves out the log well, so the column holds its height only when the run that lands shows no log. A switch to a run at Identify with a console grows the column once when the answer lands. (b) A step that finishes on the run just left can still set its finished card and console on the newly opened panel (`RunPanel`'s `settle`).
4. Closed, no change. The arrow-key listeners in `app/src/BoxBrowse.tsx` and `app/src/RunsComposer.tsx` skip typing targets only. No web API reports a screen reader's browse mode. NVDA and JAWS hold arrow keys in browse mode, so the page never sees them. Neither was tried with a real screen reader (unmeasured).
5. String-keyed `getattr` and `setattr` on card fields in `store/master.py` and `server/capture_server.py`: a typo is a silent no-op or a runtime `AttributeError`, and no tool catches it first.
6. `server/capture_server.py` is the largest backend file, ahead of `server/pipeline_routes.py` and `pipeline/join.py`. No split is proposed.
7. `CaptureScreen.tsx`, `ReviewQueue.tsx` and `BoxBrowse.tsx` each mix polling, derived state and JSX in one file. The direction is one hook per screen, so the component file holds only JSX.

Considered and rejected: a router library (about ten stable hash routes, and specs test them end to end), a state-management library (`app/src/server.ts` is already the one network seam) and a component library or CSS framework (styling is token-based and no drift was found).
