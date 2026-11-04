# Cards to Pull

The path of the `fulfillment` screen, from its view to the server.

## Open the screen

1. `app/src/Fulfillment.tsx` — The Fulfiller's whole product: cards to pull in box-walk order, with photo confirm and mark sold.
2. `app/src/PullConfirm.tsx` — Step `6`'s component: the pull modal's confirm button.
3. `app/src/SearchField.tsx` — The debounced query box. Owner gets a `/` hotkey and a key hint; the Fulfiller gets neither — his screens are touch and show no keys.
4. `app/src/CardLocations.tsx` — One SKU group: every copy, its position, its bar and its sold action.
5. `app/src/PositionBar.tsx` — Where a card sits: its SECTION drawn as a ticked (`5`, `10`) ruler that marks the exact card (its own cell filled, the pin at the cell's center) with section numbers at both ends, and under it a strip of the box's sections, numbered, with this section outlined, so the sections before and after show.
6. `app/src/position.ts` — The position ARITHMETIC with no component in it — `spansOf`, `sentenceOf`, `sectionDepthOf`, their types and the shared `clamp`.
7. `app/src/keys.ts` — IsEditableTarget, hoisted at its fourth copy — the one question every keyboard handler asks first.
8. `app/src/server.ts` — The only module that talks to the capture server, so the stop-the-run failure rule is one decision.

## The server answers

1. `server/capture_server.py` — Answers each call the screen makes through `app/src/server.ts`, and hands the work to its route files.
