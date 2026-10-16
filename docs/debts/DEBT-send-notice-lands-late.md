## DEBT-send-notice-lands-late — a send notice joins the bar after the worklist lands

**A send notice can join the send bar after it first draws.** The pending bar in `Pricing.tsx` draws no notice. `SendCard` and its first `GET /pipeline/sends` start only when the worklist lands. A notice stands for a day after a checked send (`STANDS_MS`), and for any open, short or unreadable receipt.

- **Result:** with a standing notice, the sticky bar grows at landing, or one round trip later when the send status is cold, and the list moves down. D313 forbids a move the person did not make (nothing on screen moves unless the person moved it).
- **Not fixed because** reading the sends early puts a fifth read at mount, past the Pricing mount budget of four (`app/tests/request-budget.spec.ts`). Main drew the whole bar at landing, so the notice move is not new.
- **Closes when** the sends read fits the mount budget, or the bar reserves the room of a standing notice before the read lands. A test with a standing receipt then compares the pending and loaded bar heights at 1440 and 820.
- **Points to** D277 (Pricing lists all rows; the slim bar's three tiles), D313 (nothing on screen moves unless the person moved it).

**Outcome at risk.** The list jumps under the person's hand on the day after a send, and every bar test passes, because each uses a store with no standing send.
