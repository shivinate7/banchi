# Shipping

The path of the `shipping` screen, from its view to the server.

## Open the screen

1. `app/src/Shipping.tsx` — The ship stage of the same hub: lanes of envelopes and parcels, joined to orders.
2. `app/src/Orders.tsx` — THE ORDERS HUB: one screen with two stages (D69), rendered at `#/orders` with the pull stage selected.
3. `app/src/server.ts` — The only module that talks to the capture server, so the stop-the-run failure rule is one decision.

## The server answers

1. `server/capture_server.py` — Answers each call the screen makes through `app/src/server.ts`, and hands the work to its route files.
