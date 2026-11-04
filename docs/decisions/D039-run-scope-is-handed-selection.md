# D39 — Run scope is a handed-off selection

**Retired** (owner, 2026-11-03 18:16 CST, waiting-page item 188 `oq-run-scope-writer`, pick b). No run starts from a ticked selection. D291 (runs fold into Review) replaced this record: Review's own "Identify N cards" strip starts a run, over D180's (a press names the cards it covers) selection.

- **Nothing writes the handoff.** The writer `carryScope` and its one caller `BoxRuns.tsx` were removed on the owner's word (ux-2026-09-23 review, recorded in `app/src/runHandoff.ts`).
- **Readers remain and read nothing.** `carriedScope`, `carriedByBox` and `parseKey` in `app/src/runHandoff.ts` still have callers (`Runs.tsx`, `RunsComposer.tsx`, `ReviewQueue.tsx`). An absent handoff reads as `null`, so each falls through to its default selection. A code lane removes them.
