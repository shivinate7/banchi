# Home

The path of the `home` screen, from its view to the server.

## Open the screen

1. `app/src/Home.tsx` — The start page, drawn as a picture of the product.
2. `app/src/cardCrop.ts` — THE FETCHING POLICY BEHIND THE CARD CROP, FOR EVERY SCREEN THAT DRAWS A STORED PHOTOGRAPH (D125). kit/index.tsx holds the GEOMETRY and says in its own comment that the fetching is not there because `the hero asks once for one card, the worklist asks for the rows a scroll brings into view, and those are policies, not geometry`.
3. `app/src/dates.ts` — A DATE, SAID ONE OF TWO WAYS — `relativeDate` (`5 minutes ago`, `yesterday`, then the absolute form past a week) and `absoluteDate` (`Sep 4, 2026`, no leading zero).
4. `app/src/standing.ts` — WHAT THE STORE IS WAITING ON, RANKED, AS ONE SENTENCE — the policy behind Home's standing line, in its own module because a ranking buried in a component is one nobody can find, argue with or test.
5. `app/src/storeHistory.ts` — THE STORE'S OWN HISTORY — sittings recovered from `captured_at` by a `30`-minute gap, and the ribbon geometry Home's foot draws from them.
6. `app/src/RunsStage.tsx` — WHERE A RUN IS, in one vocabulary for the list, the run panel and Home.
7. `app/src/position.ts` — The position ARITHMETIC with no component in it — `spansOf`, `sentenceOf`, `sectionDepthOf`, their types and the shared `clamp`.
8. `app/src/server.ts` — The only module that talks to the capture server, so the stop-the-run failure rule is one decision.

## The server answers

1. `server/capture_server.py` — Answers each call the screen makes through `app/src/server.ts`, and hands the work to its route files.
