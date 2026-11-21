# Cards to Pull: design notes (pull-informed-1)

Designer kind: informed. Mockup: `pull-informed-1.html`. Screen: `#/fulfillment`, drawn by `Fulfillment` in
`app/src/Fulfillment.tsx`. Persona: the Fulfiller (D5, two personas).

Every name, card, box and figure in the mockup is made up.

## How to open it

Deep links: `#s=list`, `#s=envelopes`, `#s=pull`, `#s=pull-first`, `#s=chosen`, `#s=pulled`, `#s=sold`,
`#s=card-done`, `#s=short-end`, `#s=short-top`, `#s=short-open`, `#s=search`, `#s=done` and `#s=empty`.
To change the view, add `&w=820`, `&t=dark` or `&t=light`. With no `t`, the page follows `prefers-color-scheme`. Today/New labels show by default.
`&m=0` hides them. `&h=by-envelope,short-top` hides options. Each press in the frame works: open a card, choose a
place, Pull, Mark it sold, Undo (20s clock), Next Card, the By Box and By Envelope switch, search, photo zoom, and the
box list.

Sizes: the brief named 1440 and 820. `layout.py devices` printed `unknown` for this repo. I chose the heights, 900 and
1180, so that "above the fold" has a meaning. I drew no other device.

Each state's focus element is in the `mk-focus` JSON block at the foot of the page. A scratch check proved these
things in every state, at both widths and in both themes: each focus id exists, every text node is 20px or more,
every text run is 7:1 or more on its own ground, each target is 44px or more and 12px or more apart, and each
photo's short edge is 320px or more.

## The one idea

The list gives one row per card, not one per copy. Each row says "Pull N" and names the envelope that each copy goes
in. The next card opens beside the list, so at 1440 Pull is on the first screen.

## Choices

1. **One row per card, with "Pull N".** The gain: pain point 1 is gone. The screen says how many to pull, and the
   number agrees with the Orders walk's "Pick N of M". At 1440, about five cards show where one showed before. The
   loss: the photo is no longer beside every copy. It shows after one press. My pick: yes.
   Kept: the count is `item.wanted`, summed as `totalWanted` (`Fulfillment`).
   Departs from: `Fulfillment`'s owed list, which draws `CardLocations` with every copy and each copy's own Pull.
2. **Which copy to pull. Options: Any of These, and First Copy Shown.** In Any of These, every place has the same
   weight and none is picked ("Any 2 of these 3 will do."). Pressing a place shows its photo and Pull. In First Copy
   Shown, the first place opens at once, and the others wait under "Not there?". Any of These keeps the ruling that
   no copy is preselected (D97, and the ruling in `Fulfillment.tsx`'s header comment). It costs one press per card
   that has a choice. When there is no choice (copies equal to the need), the first place opens at once. My pick:
   Any of These.
   First Copy Shown departs from: D97 (the screen never picks a copy). Owner grant: yes.
3. **Two panes at 1440: the list on the left, the pull on the right.** The gain: Pull is above the fold, and the list
   stays in view while he pulls. The loss: the layout is new for him. My pick: yes.
   At 820 the pull opens over the list, as today, with "Back to the cards" (`leaveCard`).
   Departs from: the `chosen` view, which replaces the whole list at every width.
4. **List order. Options: By Box, and By Envelope.** By Box is one trip through the boxes, in the walk plan's drawn
   order (order-walk-plan §16, `_drawn_key`). Each row names its envelopes. By Envelope groups the same rows by buyer,
   and each envelope shows a check when it is ready to seal, or "Leave Open". With both options, a switch shows, and
   By Box is first. The gain: fewer trips to the boxes (By Box), and a packing check (By Envelope). The loss: one
   more control. My pick: both, By Box first. Each option can be hidden.
   Departs from: today's screen has no grouping by envelope.
5. **A card not in any box. Options: A Group at the End, and One Line at the Top.** "176 unlocated" becomes a card
   name and an envelope: "Leave June Castellanos's envelope open. Ask for help with it." The Fulfiller can act on
   that: he does not seal the envelope. The count still comes from `plan.shortfall` (`shortfallCount`). My pick: A
   Group at the End.
   Departs from: `ff-today-warn` ("N unlocated").
6. **The receipt names the envelope.** It reads "Marked sold. Put it in Rosa Lindqvist's envelope." The envelope is
   the order that the sale goes through, oldest first (`claim`, `item.refs[0]`). Kept: the receipt sheet at the foot
   of the screen, with Undo and a 20s clock that drains (`Fulfillment` header comment; `UNDO_FLOOR_MS` is 10s, and
   the built window is 20s).
7. **Next Card.** When a card is done, the action slot offers "Next Card: (name)". The gain: no trip back to the
   list. The loss: nothing moves until he presses (D313, nothing moves unless moved). My pick: yes.
   Departs from: today he goes back to the list.
8. **The place on three lines** (box, section, card), each at 32px. This keeps the place floor (`PLACE_FLOOR`) inside
   a 308px side column at 820, with the 408px photo column that DESIGN.md requires.
   Departs from: `PlaceText` on one line.
9. **Kept as today**:
   - The two-step pull. Pull is the quiet first step. "Pulled." and then "Mark it sold" appear below it, in a 152px
     action block (DESIGN.md, the two-step pull row).
   - "Pulled Today", with Undo on each row (`ff-done`).
   - "Or Look Through a Box" (`ff-browse`).
   - Photo zoom (`bigPhoto`).
   - The empty-day sentence (`ff-today-none`).
   - Search across the whole store (`useSearch`). The mockup splits the results into "On Your List" and
     "In the Boxes".
   - The order eyebrow is now "For (buyers)".
10. **One unit and one word for open work: pain point 3.** This screen alone cannot fix it. The counts I measured on
    the other screens:
    - Home banner: "N unfilled across N orders".
    - Home Orders tile: "N owed, N unfilled" (`Home.tsx`).
    - Orders headline: "copies owed", "to pick", "not in boxes" (`HEADLINE_LABELS`).
    - This screen: "N Left" and "N unlocated".
    - Pricing: not read, so unmeasured.

    Proposal: keep copies as the unit everywhere (order-walk-plan §14). Use the words "to pull" and "not in a box". On
    this screen, say "cards", because he holds cards. A builder would change those strings. That work is outside a
    designer's scope.
    Departs from: B23's "N Left". Owner grant: yes.

## Input needed

- Is an envelope one buyer, one order, or one ship-to address? The mockup groups by buyer. A buyer with two open
  orders makes this unclear. `orders-ship-to` exists.
- Owner grant: yes items: 2 (First Copy Shown, if picked) and 10 (one unit across Home, Orders and this screen).

## Critique

The findings from impeccable's critique are in the report. Fixes inside the design folder are in this mockup.
