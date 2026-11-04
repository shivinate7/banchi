# Sales

The path of the `revenue` screen, from its view to the server.

## Open the screen

1. `app/src/Revenue.tsx` — The gross-revenue retrospective. It leaves out canceled orders and never claims profit.
2. `app/src/money.ts` — A DOLLAR AMOUNT, SAID THE SAME WAY EVERYWHERE — `money` and `roundsToNothing`.
3. `app/src/revenueMath.ts` — The gross arithmetic `Revenue.tsx` draws, moved out unchanged so a test can call it: `salesOf` turns orders into sales, `sum` adds their gross.
4. `app/src/dates.ts` — A DATE, SAID ONE OF TWO WAYS — `relativeDate` (`5 minutes ago`, `yesterday`, then the absolute form past a week) and `absoluteDate` (`Sep 4, 2026`, no leading zero).
5. `app/src/cardCrop.ts` — THE FETCHING POLICY BEHIND THE CARD CROP, FOR EVERY SCREEN THAT DRAWS A STORED PHOTOGRAPH (D125). kit/index.tsx holds the GEOMETRY and says in its own comment that the fetching is not there because `the hero asks once for one card, the worklist asks for the rows a scroll brings into view, and those are policies, not geometry`.
6. `app/src/CardLocations.tsx` — One SKU group: every copy, its position, its bar and its sold action.
7. `app/src/MixView.tsx` — Sales' Mix lens (`#/revenue?lens=mix`, no route of its own): a pivot over the stock the owner captured, holds and sold.
8. `app/src/server.ts` — The only module that talks to the capture server, so the stop-the-run failure rule is one decision.

## The server answers

1. `server/capture_server.py` — Answers each call the screen makes through `app/src/server.ts`, and hands the work to its route files.
