# Orders

The path of the `orders` screen, from its view to the server.

## Open the screen

1. `app/src/Orders.tsx` — The pull stage of the orders hub: fetch orders and see what to pull.
2. `app/src/dates.ts` — A DATE, SAID ONE OF TWO WAYS — `relativeDate` (`5 minutes ago`, `yesterday`, then the absolute form past a week) and `absoluteDate` (`Sep 4, 2026`, no leading zero).
3. `app/src/CardHero.tsx` — The card pane's shared pieces, lifted out of `BoxBrowse.tsx` so `#/orders`' walk can reuse them (`docs/specs/order-walk-plan.md` §`13`: "Inventory's card pane, unchanged").
4. `app/src/CardLocations.tsx` — One SKU group: every copy, its position, its bar and its sold action.
5. `app/src/orderPaste.ts` — THE ONE PLACE IN THIS APP THAT DECIDES WHAT LEAVES THE BROWSER ABOUT A PURCHASE (D69, amended by `D193`).
6. `app/src/orderReasons.ts` — The order-line vocabulary on this side of the wire — the six reasons pipeline/orders.py:LINE_REASONS enumerates, their human labels and their remedies.
7. `app/src/deviceMemory.ts` — Every `localStorage` key the shell owns — the theme, the rail, which order statuses this device bothers fetching (D91), whether the inventory walk folds sold rows away, when this browser last reached for each box (D132.
8. `app/src/server.ts` — The only module that talks to the capture server, so the stop-the-run failure rule is one decision.

## The server answers

1. `server/capture_server.py` — Answers each call the screen makes through `app/src/server.ts`, and hands the work to its route files.
