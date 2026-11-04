# D39 — Run scope is a handed-off selection

**Retired** (owner, 2026-11-03 18:16 CST, Cockpit item 188 `oq-run-scope-writer`, pick b). No run starts from a ticked selection any more. D291 (runs fold into Review) replaced it: Review's own "Identify N cards" strip starts a run. The writer `carryScope` and its one caller `BoxRuns.tsx` were removed on the owner's word (ux-2026-09-23 review, recorded in `app/src/runHandoff.ts`). Only readers of the `banchi.run-scope` handoff remain (`carriedScope`, `carriedByBox`, `parseKey`), and nothing writes it, so they read nothing. The text below is the rule as it stood, kept for those readers until a lane removes them.

**A run's scope is a selection: every card still owed a reading, one or more drawers, or ticked cards.** The box picker is re-answered from `GET /boxes`. The ticked selection is never re-implemented, because a second mass-select would disagree with the first about what "the selection" means. `#/runs` opens Review's runs sheet (D291).

- **The handoff is `banchi.run-scope` in `sessionStorage`,** declared in one module (`app/src/runHandoff.ts`), through its functions. A tick list is not where a card is, so it is D27's carve-out and not a breach of D13.
- **It is not cleared by being read.** A reload during a live run must not silently turn "36 ticked cards" into "the whole box", which changes what the next press spends. It is cleared by the operator's own control, by picking any box, and by arriving with nothing ticked. That is why the source control writes on every press.
- **A carried box that no longer exists is dropped whole.** The module can validate a shape and only the screen knows which boxes are real.
- **Nothing is scoped on arrival.** A box chosen for the operator is a box they did not read, and the next press spends money. The free preflight is disabled until a box is picked. The spend button does not exist until the preflight has answered.
- **`#/inventory` mentions no run.** A card is identified from Review's own identify strip. The panel's two queue figures link into `#/review`, since `ReviewQueue.tsx` draws parked and open cards both.
- **A grid item spanning several auto tracks has its height distributed across them.** A last row of `1fr` excludes it.

If a run is never started from a ticked selection, reopen the decision. The coupling is then decoration.
