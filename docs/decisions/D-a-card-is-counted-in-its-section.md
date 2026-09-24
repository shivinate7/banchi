## D-a-card-is-counted-in-its-section — A card's number counts within its section, card 1 is at the far back, and the ruler marks the card

**The owner's rulings, 2026-09-23, on how the owner finds a card.** Three rulings, one subject:
the place of a card as the hand uses it.

1. **The card number counts within the section.** "Card 1, Card 2" under each section header,
   and the count starts again at every divider. This amends the display half of D58 (a card's
   number counts the cards in the box, not the slots).
2. **Card 1 is at the far back.** The owner's words:

   ```
   if i have my cards standing up in a vertical row, the one closest to my body is the last
   card, and the one all the way in the back is the first card
   ```

   So the highest number is nearest the owner. Every drawing of a position shows that
   orientation.
3. **The section ruler is redesigned.** It marks the exact card. It uses section numbers
   throughout. It shows the sections before and after. This amends D155 (the section is the
   ruler and the box is the margin note).

The record of the review is `docs/reviews/ux-2026-09-23/`, lens `locating.md`.

### The premises that no longer hold

**D58's display half.** D58 numbers a card by its count in the box. The owner counts from a
divider, not from the front of a 700-card box. The locating lens found the screens already
split. The Inventory list says `#1` for the first card of each section. The panel says
`#12 of 34` for the same card. Cards to pull draws `Card 1` and `Card 12 of 34` on one panel
(LOC-03, UX-012).

**D155's ruler.** D155 writes "the section's own bounds" inside the ruler's two ends. Those
bounds are box counts, and the caption beside them is a section count. So one instrument shows
two scales (LOC-04). D155's caret marks the chip the card is in, not the card. On a box with
one section, the caret sits at the middle for every card (LOC-05).

**No decision named an orientation.** No screen and no entry said which end of a box is card 1
(LOC-06). A hand can count 30 from the wrong end of the box.

### What each decision protected, and what protects it now

**D58** protects a number that a hand can count to, with no holes. That stays. A sale still
makes the card behind it take its number, now within the section. The stored index never moves
(D10, the inventory model). D58's `Position` stays the one place that composes a label.

**D92 (a bare `#` is the count, the key carries a sigil)** protects one rule: one `#` never
names two cards on one screen. With section counts, `#1` exists once per section. So a card
number always travels with its section in the same label. The box number and its store key
leave the screen: a box is shown by its name only (slug `a-box-is-shown-by-its-name`).

**D155** protects a precise place at the section scale, with the box scale kept quiet. The new
ruler keeps that. It draws one scale, section numbers, and one mark on the exact card. Its
two ends say which end is the far back.

### Rules for every position drawing

- One word per count, the same on every screen. "Card" is the count in the section.
- A place reads box, then section, then card. `sayPlace()` in `app/src/position.ts` composes
  every place label that becomes text or an accessible name.
- Each drawing of a box or a section marks the far back (card 1) and the near end (the highest
  number).
- A departed card keeps its place in its label: box name, section and card. A visual mark shows
  that it has left (slug `a-box-is-shown-by-its-name`). It never offers a pull (LOC-01).

### What is built

NOT BUILT. The locating lane builds it (LOC-03 to LOC-07, and the ruler). It moved to wave 1 in
the round-two plan, so the screen lanes use its vocabulary. `docs/specs/box-map.md` uses the same
orientation for its move receipts.

The round-two plan names three locating entries for the same rulings (slugs `section-ruler`,
`card-one-at-back` and `section-card-number`). One copy of each argument must go before either
merges.

### One more word: slots

The orchestrator called it in round two (HIR-05, LOC-22). "Slots" names the box's capacity, and
it appears only in Inventory's box header and strip. Every other place says "cards".
