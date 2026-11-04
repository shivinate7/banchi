# Codes

The path of the `codes` screen, from its view to the server.

## Open the screen

1. `app/src/Codes.tsx` — The dormant code-card screen: read a box's QR codes into the ledger and hand a lane's codes to a buyer.
2. `app/src/dates.ts` — A DATE, SAID ONE OF TWO WAYS — `relativeDate` (`5 minutes ago`, `yesterday`, then the absolute form past a week) and `absoluteDate` (`Sep 4, 2026`, no leading zero).
3. `app/src/server.ts` — The only module that talks to the capture server, so the stop-the-run failure rule is one decision.

## The server answers

1. `server/capture_server.py` — Answers each call the screen makes through `app/src/server.ts`, and hands the work to its route files.
