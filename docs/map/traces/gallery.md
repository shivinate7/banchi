# Kit

The path of the `gallery` screen, from its view to the server.

## Open the screen

1. `app/src/Gallery.tsx` — Every primitive the app is built from, on one page.
2. `app/src/PullConfirm.tsx` — Step `6`'s component: the pull modal's confirm button.
3. `app/src/PositionBar.tsx` — Where a card sits: its SECTION drawn as a ticked (`5`, `10`) ruler that marks the exact card (its own cell filled, the pin at the cell's center) with section numbers at both ends, and under it a strip of the box's sections, numbered, with this section outlined, so the sections before and after show.
4. `app/src/PositionLabel.tsx` — ONE rendering of `pipeline/join.py:Position.label` for every OWNER site.
5. `app/src/SearchField.tsx` — The debounced query box. Owner gets a `/` hotkey and a key hint; the Fulfiller gets neither — his screens are touch and show no keys.
6. `app/src/CardLocations.tsx` — One SKU group: every copy, its position, its bar and its sold action.
7. `app/src/HistoryFloat.tsx` — The floating price-history card (spec pricing-suggest `9c`): opens above a row when a price field takes focus or its history door is pressed, draws `ProductHistory.tsx:ProductChart` with the owner's asking step line and the suggestion dot, holds its size while history loads, takes focus only in door mode.
8. `app/src/server.ts` — The only module that talks to the capture server, so the stop-the-run failure rule is one decision.

## The server answers

1. `server/capture_server.py` — Answers each call the screen makes through `app/src/server.ts`, and hands the work to its route files.
