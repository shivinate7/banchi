# Pack witness: the packing table witnesses

Idea: the Fulfiller lays an order's cards on a printed slot mat under an iPad and takes one photo; each slot sits beside that copy's capture photo.
The photo is kept, so a dispute weeks later opens one page with the pack photo, each card's pair and an export. Proposal only; nothing ships.

Click through: open `pack-witness.html` from disk. The chips switch states; the buttons on the screen also move between them.
Deep link: `#state=<name>&t=light|dark&w=fit|1440|820&h=<options>&tags=off`. Packing states: `ready`, `match`, `sealed`, `wrong`, `missing`,
`notfound`, `facedown`, `overlap`, `slab`, `slab-manual`, `slab-checked`, `slab-wrong`, `byeye`. Owner states: `dispute`, `dispute-exported`, `dispute-none`.

Reached from: Cards to Pull (`fulfillment`), after the last card of an order is pulled (the "Cards to Pull" back button). The owner reaches the dispute page from Orders' Manage sheet or a Shipping row.
Nearest: `docs/DESIGN.md` "Fulfillment view — hard constraints" and `docs/specs/order-flow.md`; no spec covers packing or disputes.
Departs from: Cards to Pull (`Fulfillment.tsx`), where an order ends at the last "Mark it sold" — a packing step with a photo and a Seal is added after the pull.
Departs from: Orders and Shipping, which keep no photo of what left — each order gains a stored pack photo and a Pack Photo page.

Choices (Gain / Lose / Pick):
1. The mat photo is the hero, with a ring per slot (green, amber, blue for "do this"). Gain: the Fulfiller sees which slot at a glance, with no reading. Lose: the slot numbers are printed on the mat, so they are text inside a photo (Fulfillment bans text over photos). Pick: this.
2. A problem shows the two photos at 320px each, the difference in words, and the place at 32px. Gain: keeps the photo and place floors. Lose: a long panel at 820. Pick: this.
3. Face down and overlap give no verdict on any slot, only "Flip slot 3" or "Spread the cards". Gain: nothing is marked wrong that is not. Pick: this.
4. Missing: "Can't Find It" sends the card to the owner's Review as not found, with Undo for 20 seconds; the order waits. Gain: never dropped. Lose: the word "queue" is banned on his screen, so it reads "the owner will look". Pick: this. Owner grant: yes (new path into Review).
5. Slab: matched by its label; glare asks "Check slot 6 yourself", stored as checked by hand and shown so on the dispute page. Pick: this.
6. Action block reserves two 64px steps (Seal, then Next Order below it), as the pull-confirm does. Gain: a double tap never lands on a new button. Pick: this.
7. Slot list thumbnails are 56px, under the 320px photo floor. Gain: the whole order fits beside the mat. Lose: breaks a Fulfiller floor for a list he does not judge from. Pick: this. Owner grant: yes.
8. The dispute page locks the photo and pairs once exported; the outcome stays settable. Pick: this. Owner grant: yes (the plan says "read-only once exported").
Options, each with a Hide chip: Auto Shutter (takes the photo when the mat is still), By-Eye State (plan section 4: no auto matching, one pair at a time), Image Export (beside PDF), Back to Cards to Pull.

Owner questions (from the plan):
- How many wrong-card or damage claims so far, and what did they cost? It decides automatic matching against the by-eye first version.
- Do slabs and high-value cards always pass through your hands before sealing, or does the Fulfiller seal everything?
- Is the Fulfiller comfortable with hands and table in every photo, and are photos kept forever or for a set number of days?
- Added: is "Sale Upheld" the right word for the third outcome, and may the outcome change after export?

Verdicts (static file, headless Chrome):
- 1440 light (`pack-witness-1440-light.png`, wrong printing): pass. Mat and answer side by side; pair, difference and place all above the fold.
- 820 dark (`pack-witness-820-dark.png`, missing card): pass. One column; the flatter mat puts the answer under it, and both actions sit at the foot.
