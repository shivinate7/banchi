# Product History

The path of the `product` screen, from its view to the server.

## Open the screen

1. `app/src/ProductHistory.tsx` — One product's market history, with the owner's own sales marked.
2. `app/src/SearchField.tsx` — The debounced query box. Owner gets a `/` hotkey and a key hint; the Fulfiller gets neither — his screens are touch and show no keys.
3. `app/src/useSearch.ts` — GET /search behind a debounce, with an out-of-order guard so a slow early answer cannot overwrite a fast later one; and `useQueryFilter`, a list the browser holds narrowed by the one matcher in `kit/match.ts`.
4. `app/src/money.ts` — A DOLLAR AMOUNT, SAID THE SAME WAY EVERYWHERE — `money` and `roundsToNothing`.
5. `app/src/dates.ts` — A DATE, SAID ONE OF TWO WAYS — `relativeDate` (`5 minutes ago`, `yesterday`, then the absolute form past a week) and `absoluteDate` (`Sep 4, 2026`, no leading zero).
6. `app/src/PriceHistory.tsx` — The two drawing helpers three screens share: `RANGE_LABEL` and `sparkSegments`, the spark geometry the row trend, the product view and Sales draw with.
7. `app/src/PriceFacts.tsx` — The block at the top of the product sheet and page: prices now, sales over `30` days with a sold-per-day chart, and the shelf.
8. `app/src/server.ts` — The only module that talks to the capture server, so the stop-the-run failure rule is one decision.

## The server answers

1. `server/capture_server.py` — Answers each call the screen makes through `app/src/server.ts`, and hands the work to its route files.
