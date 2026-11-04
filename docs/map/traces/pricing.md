# Pricing

The path of the `pricing` screen, from its view to the server.

## Open the screen

1. `app/src/Pricing.tsx` — The one worklist of every unsent copy, with its price, its holds and the files to write.
2. `app/src/holds.ts` — The withhold vocabulary on this side of the wire — the three reasons, their human labels and their panel keys.
3. `app/src/keys.ts` — IsEditableTarget, hoisted at its fourth copy — the one question every keyboard handler asks first.
4. `app/src/readiness.ts` — What `emit` would refuse this run for, on this side of the wire — a second implementation of pipeline/decisions.py:blocking, chosen so the pricing screen's readiness line settles on the keystroke that answers it rather than a round trip later.
5. `app/src/standing.ts` — WHAT THE STORE IS WAITING ON, RANKED, AS ONE SENTENCE — the policy behind Home's standing line, in its own module because a ranking buried in a component is one nobody can find, argue with or test.
6. `app/src/PriceTrend.tsx` — The trend strip in a #/pricing row: a daily and a weekly sparkline with a signed percentage under each, in a real `168px` column between the card and MARKET.
7. `app/src/PricesAsOf.tsx` — The header line above #/pricing's list: "Prices as of" the catalog step's finish, and the one press, Refresh now, with its running, done and failed states.
8. `app/src/server.ts` — The only module that talks to the capture server, so the stop-the-run failure rule is one decision.

## The server answers

1. `server/capture_server.py` — Answers each call the screen makes through `app/src/server.ts`, and hands the work to its route files.
