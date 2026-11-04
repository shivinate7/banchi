# Runs

The path of the `runs` screen, from its view to the server.

## Open the screen

1. `app/src/Runs.tsx` — Opens Review's runs sheet. The route stays so an old link still works.
2. `app/src/LiveReconcile.tsx` — The store-wide reconcile panel on #/runs (D87) — upload one live export, preview, settle.
3. `app/src/RunPanel.tsx` — THE RUNS, AS MASTER AND DETAIL, on #/runs since D39 and in #/inventory's content column before it.
4. `app/src/RunsComposer.tsx` — THE IDENTIFY COMPOSER: the one press in this product that spends money, as a staged dialog — which boxes, how each is read, what it costs, and a receipt.
5. `app/src/SubmissionClaims.tsx` — The panel on #/runs saying what a live send is holding, and the ONE way out of a stuck claim (D174).
6. `app/src/runHandoff.ts` — The one module that reads or writes the run scope carried from #/inventory to #/runs — key `banchi.run-scope`, D27's carve-out.
7. `app/src/server.ts` — The only module that talks to the capture server, so the stop-the-run failure rule is one decision.

## The server answers

1. `server/capture_server.py` — Answers each call the screen makes through `app/src/server.ts`, and hands the work to its route files.
