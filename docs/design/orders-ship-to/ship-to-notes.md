# Ship To: one treatment on four surfaces

Mockup: `ship-to.html` in this folder. Designer kind: informed. Deep links take `#s=<state>&w=<1440|820>&t=<light|dark|abyssal-bloom|carnival-midway>`.
States: `differ`, `same`, `unknown`, `nameless`, `several`. Names come from the fixtures only: ship-to names from
`fixtures/orders-shipping.csv`, buyer names from the `app/tests` orders. The `PROPOSED` block at the foot of the mockup's
CSS is the part a builder copies; everything above it is the repo's own CSS, inlined.

1. **One parcel line, two lines tall.** Line one: "Ship To" and the name. Line two: "Bought By" and the buyer, only when
   the buyer is someone else (`orderBuyers.shipToOf`). UI face, `--bn-fs-md`. The label is `--bn-ink-3`, the name is
   `--bn-ink` at 600, and the buyer line is `--bn-ink-3`.
   Gain: one look on every screen. No separator can lead a wrapped line, and "X bought by Y" never reads backwards.
   Loss: the line is one line taller where a buyer differs. Pick: this.
   Departs from: `.orders-panel-shipto` (small bold), `.orders-ship-to` (plain, inside the meta line) and
   `.shipping-ship-to` (medium bold, buyer joined on one line).
2. **Strings, in title case (the owner's ruling for this lane).** "Ship To", then the name. "Bought By", then the
   buyer. The Ship stage legend reads "Ship To in Bold". Names are drawn as given, under `data-typed`.
   Gain: it follows the ruling. R5's grading of "Ship To X" passes with the name stripped. Loss: none. Pick: this.
3. **A. Order header (`OrderDetail` in the Manage sheet).**
   - `.orders-order-head` becomes a `minmax(0, 1fr) auto` grid, so the pills can never drop under the id.
   - The ship-to moves out of `.orders-order-meta` onto its own line under the number.
   - The number goes from 18px to `--bn-fs-h3` (16px). The sheet's own title is the buyer, so the number is the sheet's second title.
   - The status pill comes first in `.orders-order-side`, and the lane pill sits under it.
   Measured in the mockup at 1440 and 820: the status pill's top is 0px from the number's top. The 21-character
   number fits one line in its 222px column at 16px. The 18px width is unmeasured.
   Gain: the status pill stays beside the number. Loss: the number is one step smaller. Pick: stacked pills.
   Departs from: `Orders.tsx` `OrderDetail` (the ship-to span inside `meta`, lane pill before status) and `Orders.css`
   `.orders-order-head` (flex-wrap) and `.orders-order-number` (18px).
   Option "Lane pill on the Ship To line": the head is one pill wide, but the line gets a second shape. Not picked.
4. **B. Buyer panel (`OrderPanel`).** The line sits directly under the buyer's name, before the order line, which
   matches where the order header puts it (under its title). A buyer with several orders still shows none.
   Gain: one position rule, "under the heading it qualifies". Loss: the order line moves down one line.
   Pick: this. Departs from: `OrderPanel`, where the ship-to came after the order line.
5. **"Bought By" only where the buyer is not already on screen.** It shows on Ship stage rows and the Fulfiller's card.
   It does not show in the panel (the panel's heading is the buyer) or in the sheet's order header (the sheet's title is
   the buyer). Gain: no name is said twice in one view. Loss: the rule has one condition to learn. Pick: this.
6. **C. Ship stage: the label is said once, above the lanes.** The legend leads with "**Ship To** in Bold". Each row draws
   the bold name with "Ship To" in a `.bn-sr` span, so a screen reader still hears it. House rule `ux-label-once` breaks
   the tie. Gain: one label instead of one per row, on up to about 300 rows. Loss: a sighted reader learns the key once.
   Pick: label once. Option "Label on every row" is today's build.
   `label_once.py` on the rendered pick: on the Ship stage, "ship to" is visible once. The other hits are the mockup's
   three screens on one page, plus the panel and the open sheet both naming the same parcel.
7. **D. Fulfiller card: "Ship To" leads.** Line one: "Ship To" and the name, 20px, the name at 700. Line two: "Bought By"
   and the buyer when it differs, then `#<number>` in `.ff-card-order-id` (mono, since it is a machine string).
   Every word is `--bn-ink-2` or darker, which clears 7:1. The buyer's name is never mono.
   - When no ship-to is known, the card keeps today's "For <buyer> #<number>". A buyer's name is not a parcel name, so it is not guessed.
   - The builder needs the raw `ship_to` to tell "same person" from "unknown": `shipToOf` returns null for both.
   Gain: packing reads the parcel name first, and the line no longer wraps at 1440. Loss: the Fulfiller's familiar
   word "For" changes. Pick: 20px bold. Option "Name at 24px": not picked, because two large lines compete with the card name.
   Departs from: `Fulfillment.tsx` `orderLabel` and the `.ff-card-eyebrow` "For <b>name</b>" line.
   **Owner grant: yes.** It changes the copy on the Fulfiller's screen.
8. **Where the shared class lives.** `.bn-shipto` and its parts are used by `Orders.css`, `Shipping.css` and
   `Fulfillment.css`, so one home in `kit.css` (or a small kit component) serves all three
   (`building-one-home-per-capability`). `.ff-shipto` is the Fulfiller's size modifier, in `Fulfillment.css`.
   Gain: one home. Loss: the kit grows by one block. Pick: kit.
9. **Not drawn.** The `inline` variant of `OrderDetail` has no caller today. No fixture name is longer than 20
   characters, so no long name is drawn. Every name line carries `overflow-wrap: anywhere`.
