# Review

The path of the `review` screen, from its view to the server.

## Open the screen

1. `app/src/ReviewQueue.tsx` — Answer the questions the pipeline parked, and open the runs sheet to identify, join and emit.
2. `app/src/PositionLabel.tsx` — ONE rendering of `pipeline/join.py:Position.label` for every OWNER site.
3. `app/src/keys.ts` — The one question every keyboard handler asks first: is the event target an editable field.
4. `app/src/RunsLog.tsx` — A command's stdout, verbatim, in a well that follows its tail, counts its lines, folds and copies.
5. `app/src/Runs.tsx` — The runs sheet and the redirect from the old runs route: the box picker, the composer, the store-wide reconcile and the stale-listing markdown, with the run panel beneath them.
6. `app/src/RunsComposer.tsx` — THE IDENTIFY COMPOSER: the one press in this product that spends money, as a staged dialog — which boxes, how each is read, what it costs, and a receipt.
7. `app/src/runHandoff.ts` — The one module that reads or writes the run scope carried from #/inventory to #/runs — key `banchi.run-scope`, D27's carve-out.
8. `app/src/server.ts` — The only module that talks to the capture server, so the stop-the-run failure rule is one decision.

## The server answers

1. `server/capture_server.py` — Answers each call the screen makes through `app/src/server.ts`, and hands the work to its route files.
