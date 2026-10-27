## DEBT61 — build proposals are still open

**What.** Build proposals carried over from earlier work are still open. Each open item was checked against the code and stays open. Item 6 has a plan and no build ruling.

3. Fixed. `app/src/RunPanel.tsx` takes a run read only when it names the open run, so a late answer for the run just left never replaces the open run's. On a direct switch the panel on screen is drawn from the new run's list row, with the row's own step open and no line that needs the manifest or the console. Its header and body are inert and dimmed, and a failed read still shows its notice. A first open still draws the loading panel. Two limits are accepted for now and not fixed. (a) The stand-in leaves out the log well, so the column holds its height only when the run that lands shows no log. A switch to a run at Identify with a console grows the column once when the answer lands. (b) A step that finishes on the run just left can still set its finished card and console on the newly opened panel (`RunPanel`'s `settle`).
4. Closed, no change. The arrow-key listeners in `app/src/BoxBrowse.tsx` and `app/src/RunsComposer.tsx` skip typing targets only. No web API reports a screen reader's browse mode. NVDA and JAWS hold arrow keys in browse mode, so the page never sees them. Neither was tried with a real screen reader (unmeasured).
6. Split plan for `server/capture_server.py` (planned at the owner's word; no code is built). Measured: 18088 lines, 270 top-level functions and classes, 57 `do_*` route functions, and `CaptureHandler` at about 1750 lines. The harness, app specs, scripts and other packages name `capture_server.<name>` 1630 times over 137 distinct names. Five route modules already split off the same way (`pipeline_routes`, `send_routes`, `shipping_routes`, `slabs_routes`, `codes_routes`). The rule they keep: `capture_server` imports them and they never import it.

   Seams, cheapest first, one lane and one PR each:
   - Step 0, measure and prepare. Measure the helpers used by two or more families below (`BadRequest`-style errors, `_optional_section`, box and index parsing). Move those to a module under `server/` that imports nothing from `capture_server`. Unmeasured: how many there are.
   - Step 1, orders: `do_orders` and the `do_order_*` functions, about 1100 lines. The engine (`pipeline/orders.py`) and the transport (`server/order_transport.py`) are already outside, so this is the leaf-most family.
   - Step 2, review: `do_review_*`, `do_correct_answer`, `do_queues`, about 900 lines.
   - Step 3, moves and sections: `do_move_*`, `do_undo_section_move`, `do_open_section`, `do_close_section` and the section helpers, about 1500 lines. The most tangled family: it shares helpers with the writes below, so it follows step 0.
   - Step 4, card and box writes: `do_put_*`, `do_delete_*`, `do_remove_card`, `do_retire`, `do_reshoot`, `do_create_box`, `do_box_*`.
   - Step 5, reads: `do_inventory*`, `do_search`, `do_status`, `do_skus_photos`, `do_games`, `do_graveyard`, `do_photo*`.
   - Not split: `CaptureHandler`, `CaptureServer`, the dispatch and the request-slot figures. The `server concurrency` row of `make docs-audit` reads them in this file.

   Method per step: move the functions unchanged to `server/<family>_routes.py`, leave a one-line alias in `capture_server` for each moved name tests use, then repoint tests and delete the aliases in the same PR when the diff stays readable. Each PR adds its repo-map entries and runs the full `make check`. A reviewer reads that the diff is a pure move.

   Cost: six PRs. Each is a large diff in the file the owner calls fragile, with no behavior change. Gain: smaller files, and a clear home per route family. Stop if step 0 finds a helper tangle that cannot move without changing behavior.

   Restarts: no step needs one to pass its checks, because the harness starts its own server. The running server loads moved code only at a restart. Ask the owner for exactly two: one after step 1 to prove the method live, one after step 5. Never restart to fix a wedge (CLAUDE.md).
7. Ruled when-touched. `CaptureScreen.tsx`, `ReviewQueue.tsx` and `BoxBrowse.tsx` each mix polling, derived state and JSX in one file. No stand-alone refactor: a lane that next edits one of them moves that screen's polling and state into a hook, so the component file holds only JSX.
8. No Python type checker (`mypy`, `pyright`) is configured. Ruff is adopted (D82) and nobody argued the absence. The cheap first step is `mypy --strict` on one well-typed module (`store/orders.py` or `codes/qr.py`).

Considered and rejected: a router library (about ten stable hash routes, and specs test them end to end), a state-management library (`app/src/server.ts` is already the one network seam) and a component library or CSS framework (styling is token-based and no drift was found).
