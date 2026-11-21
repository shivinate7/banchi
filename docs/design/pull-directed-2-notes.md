# Cards to Pull, route first: design notes

Designer kind: directed. Direction: the route first. The physical walk along the boxes is a map,
and the cards sit on it in walking order. Mockup: `docs/design/pull-directed-2.html`. Every name,
card, box and count in it is made up.

Sizes: `layout.py devices` gives no device list for this repo ("unknown"), so 1440 x 900 and
820 x 1180 come from the brief and from `CLAUDE.md` ("Banchi's sizes: 1440 and 820"). Themes:
light, dark, and the two dark palettes `tokens.css` ships.

Behaviour kept from today is cited by file and symbol. Each departure has a "Departs from:" line.
None of these questions blocks the mockup.

1. **The route is the list.** The screen draws the walk plan's own stops (`WalkPlanStop` in
   `app/src/types.ts`, from `POST /orders/walk-plan`) as a map. Each box is a line, back on the
   left and front on the right. Each stop is a numbered station at its section, in walk order.
   A box with nothing to pull is a faint line that he passes. The route line is solid where he
   has walked and dotted ahead. It ends at "Then Pack 4 Envelopes".
   Gain: he sees where to go, in what order, and how far he is. The pull is above the fold at
   1440 and at 820, because one stop is on screen, not one card per screen height.
   Loss: a new map component to build and test. The plan's sections become visible, and the
   walk-plan spec (section 3) says the operator should not have to think in sections. The map
   shows sections as places to open, not as a word to learn.
   Departs from: `owedFrom` in `app/src/Fulfillment.tsx`, which folds the stops into one flat
   list of cards. Pick: yes. Owner grant: yes.

2. **The map at 1440: Shelf Map or Route Strip.** Shelf Map is the full map beside the stop, in
   a 480px column. Route Strip is the stops in one line over the stop, with boxes as brackets
   and a Show the Whole Map press. At 820 the strip is the only form, because the full map
   would push Pull below the fold.
   Gain (Shelf Map): the room's layout is on screen all the time. Loss: 480px of width.
   Gain (Route Strip): one layout for both widths. Loss: the room's shape is one press away.
   Pick: Shelf Map at 1440, Route Strip at 820.

3. **"Pull 2" and the copies at this stop.** Each card at a stop says how many to pull, with one
   pip per copy. With more copies here than wanted, a line says "Any 2 of these 3" and each
   copy is a chip. A sold copy's chip is struck through. When the count is met, a spare copy
   stays in place as a plain mark that cannot be pressed, and the line says "Done. Card 66 stays."
   Nothing in the column changes size, so no press moves the Pull block (D118).
   Gain: fixes the largest pain. The count is the Orders walk's own count (Pick N of M, D279,
   and `docs/specs/order-walk-plan.md` section 8). Over-pulling is no longer the easy path
   (section 1, rule 1).
   Loss: the screen no longer shows every copy in the store at once.
   Departs from: the `Owed` type in `app/src/Fulfillment.tsx`, where every on-hand copy has its
   own Pull, by the owner's ruling cited in that comment. Pick: yes. Owner grant: yes.

4. **Other copies of a card: Behind Not There? or Listed Under the Photo.** Behind Not There?
   shows only the copies at this stop, and a sheet shows the other places. Listed Under the
   Photo shows one line, "Another copy: ...", under the photo all the time.
   Gain (Behind): one place on screen. Loss: the other places need a press.
   Gain (Listed): closer to today's every-copy rule. Loss: a second place on screen invites a
   detour. Pick: Behind Not There?. Owner grant: yes (same ruling as item 3).

5. **Not There?** The sheet says to look two or three cards each way first. If another copy is
   on the route, it names that stop: "Get It at Stop 8" moves the card to that stop, on the
   screen only. The plan is not solved again, so the freeze in `docs/specs/order-walk-plan.md`
   section 8 holds. "Leave It for Now" marks the card left, and its envelope stays open.
   Gain: a short card has a way on (house rule ux-no-dead-end).
   Loss: the "left" mark lives only in the screen's state. A reload drops it, and the envelope's
   Keep Open goes with it. A builder needs a write for it, which no route has today.
   Pick: yes. Owner grant: yes.

6. **The two-step pull is kept, with a third slot.** Pull, then "Pulled." in its place, then Mark
   It Sold below it (`actionFor` and `PullConfirm` in `app/src/Fulfillment.tsx`). After the sale,
   the second slot says which envelope the card goes in, and a third slot holds Next. Next is a
   press, so the pane still does not advance by itself (UN-6). Each step lands below the last,
   so a double tap never hits the next control.
   Gain: the answer shows where the press was, and the next card is one press away.
   Loss: the reserved block grows from 152px to 240px (64 + 24 + 64 + 24 + 64).
   Departs from: `docs/DESIGN.md`, "The action block reserves 152px". Pick: yes. Owner grant: yes.

7. **The second press: Mark It Sold or Into the Envelope.** Mark It Sold is today's word, the
   same as Inventory and Orders (D57). Into the Envelope names where the card goes ("Into Mara
   Quill's Envelope") and still records the sale.
   Gain (Into): one press says what his hand does. Loss: one act gets two names.
   Departs from (Into): one act, one name (D57, and the copy rule in `docs/DESIGN.md`).
   Pick: Mark It Sold.

8. **Envelopes.** A dock at the foot lists one envelope per buyer, with "2 of 4", "Keep open" or
   "Ready to seal". The envelope that just got a card lights. A Route / Envelopes switch in the
   bar shows the same cards grouped by envelope. Each stop badge there returns to that stop.
   The envelope a copy goes in comes from the walk's own rule: the open order closest to done
   (`pickOrderFor`, `docs/specs/order-walk-plan.md` section 8). The envelope's name should be the
   name on the parcel (`orderLabel` in `app/src/Fulfillment.tsx`, D193). The mockup shows one
   name per buyer.
   Before the press, one line over the Pull block says "For Mara Quill". It is one line
   always, so a longer name on the next copy moves nothing below it.
   Gain: fixes the second pain. He knows which pile each card goes on. The newest sale's
   receipt with Undo floats just above the dock, as today's receipt sheet does, so its arrival
   moves no envelope. The envelope that lit grows slightly for a moment and moves no other.
   Loss: the dock takes 80px of height. With many buyers it scrolls sideways. The receipt can
   cover the foot of the photo column at 820 until the next press.
   Pick: yes. Owner grant: yes.

9. **No count of cards he cannot act on.** "176 unlocated" is gone. Each card not in any box
   (`plan.shortfall`) is named in its envelope, and that envelope reads "Keep open".
   Gain: the warning becomes an act: do not seal that envelope.
   Loss: the total of cards not in boxes is not on this screen. The owner keeps it on Home and
   Orders.
   Departs from: `shortfallCount` and its "N unlocated" line in `app/src/Fulfillment.tsx`.
   Pick: yes.

10. **One unit for the count.** The bar says "10 Cards Left": copies still to pull on this
    route. Cards not in any box are not in it. Home says "75 orders, 256 owed, 164 unfilled",
    and today's bar says "74 Left". The proposal is one unit, cards, and one word per kind across
    Home, Orders, Pricing and this screen: cards to pull, and cards not in any box.
    Gain: fixes the third pain. Loss: Home, Orders and Pricing must change, outside this mockup.
    Pick: yes. Owner grant: yes.

11. **The photo check is kept.** The photo leads the stop, and a tap enlarges it, as today. The
    photo column is 408px wide, as `docs/DESIGN.md` sets above 768px, so the card is 320px or
    more on its short edge. The position line (Card 58, the section bar, the neighbours) sits
    under the photo, where his eyes already are.
    Pick: yes.

12. **Search is kept and joins the map.** A name finds the card's stop on the route and lights
    its station. A press goes to that stop. On an empty day, it names the place of any card,
    as today (`useSearch` in `app/src/Fulfillment.tsx`).
    Pick: yes.

13. **Empty, failed and done.** An empty day keeps today's sentence, "No orders are waiting for a
    card right now.", and adds one press, Find a Card by Name, which opens the search. A failed
    read says "The cards did not load." with Try Again, and the count keeps its last figure
    (B23 in `docs/DESIGN.md`). Done says how many were pulled, which envelopes to seal and
    which to keep open, with one press to the envelopes.
    Pick: yes.

14. **Floors.** Every word on the screen is 20px or more. Each position label is 32px. Each
    press is 44px or more. Secondary text uses `--bn-ink-2`, never `--bn-ink-3`, to keep 7:1.
    The one solid fill is the pull-confirm fill (`--bn-accent-press` light, `--bn-accent-hover`
    dark). Vermilion is not used. No mark sold reaches a card he has not pulled.
    Pick: yes.
