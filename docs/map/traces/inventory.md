# Inventory

The path of the `inventory` screen, from its view to the server.

## Open the screen

1. `app/src/Inventory.tsx` — The one owner view of stored cards: find a card, see where it is, move or retire it.
2. `app/src/BoxBrowse.tsx` — The box walk, D31's default way into #/inventory — was #/pull until the three routes merged.
3. `app/src/BoxShelf.tsx` — The Shelf, the second view of #/inventory (`?view=shelf`): every box drawn from above with its sections as blocks, card `1` at the top, counts only.
4. `app/src/CardLocations.tsx` — One SKU group: every copy, its position, its bar and its sold action.
5. `app/src/CardHero.tsx` — The card pane's shared pieces, lifted out of `BoxBrowse.tsx` so `#/orders`' walk can reuse them (`docs/specs/order-walk-plan.md` §`13`: "Inventory's card pane, unchanged").
6. `app/src/InventorySets.tsx` — THE OWNER'S "BY SET" VIEW (D293), a second view inside #/inventory (D264's own precedent: a view switch lives inside Inventory rather than as a fourth screen, D31).
7. `app/src/TakeOffLine.tsx` — The take-off line on a master-set retire receipt: Take It Off TCGplayer at the pull and the answer in the same place, drawn in the toast kit's changing line.
8. `app/src/server.ts` — The only module that talks to the capture server, so the stop-the-run failure rule is one decision.

## The server answers

1. `server/capture_server.py` — Answers each call the screen makes through `app/src/server.ts`, and hands the work to its route files.
