# Slabs

The path of the `slabs` screen, from its view to the server.

## Open the screen

1. `app/src/Slabs.tsx` — The ledger of graded slabs, with each slab's value.
2. `app/src/dates.ts` — A DATE, SAID ONE OF TWO WAYS — `relativeDate` (`5 minutes ago`, `yesterday`, then the absolute form past a week) and `absoluteDate` (`Sep 4, 2026`, no leading zero).
3. `app/src/slabGraders.ts` — The grader list the Add sheet offers: a copy of `store/slabs.GRADERS`, because no route sends the list yet.
4. `app/src/server.ts` — The only module that talks to the capture server, so the stop-the-run failure rule is one decision.

## The server answers

1. `server/capture_server.py` — Answers each call the screen makes through `app/src/server.ts`, and hands the work to its route files.
