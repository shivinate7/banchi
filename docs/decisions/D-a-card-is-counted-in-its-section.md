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

**D58** protects a number that a hand can count to, with no holes. That stays. Renumbering on
departure still holds, within the section. When a card is sold, retired or moved, each later
card in its section counts down by one. The stored index never moves
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

BUILT in the locating lane:

- The server's label counts the card within its section, and a departed card is counted in the
  section it left (`pipeline/join.py:Position.section`, in index space).
- `app/src/position.ts:placePartsOf` is the one reader of the label. `sentencePartsOf` says
  `Card 5 of 12` for both personas. `sectionDepthOf` gives the ruler section numbers at both
  ends and the card's own cell.
- `app/src/PositionBar.tsx`: the ruler fills the card's cell and puts the pin at its centre. The
  strip under it numbers the box's sections and outlines this one. `back` and `front` are
  written under both. The caret is gone.
- `app/src/PlaceNeighbors.tsx` draws back, this card, front. A departed card reads `was here`,
  and its accessible name is `Was between ...`.
- `app/tests/locating.spec.ts` asserts it at 1440, 820, 720 and 390, in both themes.

### An unread card is a neighbour (amends D116)

**The owner's ruling, 2026-09-24 (LOC-28):** unread cards count as neighbours, said as
"an unread card" or "N unread cards".

**The premise that no longer holds.** D116 (a card nobody has named is not a landmark) walked
past an unnamed card to the nearest named one, because the bare `#270` it drew read as a sold
card. The walk dropped a real card from the sentence (UX-264): "after Galio" named a card
three along.

**What D116 protected, and what protects it now.** D116 protected a sentence with no bare
figure in it. The words "an unread card" keep that. D30 protected a sentence that never sends a
hand to the wrong card. The adjacent card is now always the neighbour, so nothing is skipped.

**What is built.** `server/capture_server.py:_Places._company` sends the adjacent on-hand card
on each side, and `unread`, the run of unread cards from it to the next named card. The wire
field `skipped` is gone. `app/src/server.ts:neighborWords` says the run.

### The neighbour sentence says back and front (UX-186)

"Between X and Y" did not say which card is at the back. The sentence is now "It sits in front
of X and behind Y.", composed once in `app/src/server.ts:placeParts`. X is toward the back and
Y toward the front, so the words agree with card 1 at the far back. A departed card reads "It
was ...". The Fulfiller reads this sentence, and it is the accessible name of the owner's
neighbour ladder. Review's place pill draws back, the two neighbours and front on one line
under the label.

### One more word: slots

The owner ruled it in the final interview (HIR-05, LOC-22). "Slots" names the box's capacity, and
it appears only in Inventory's box header and strip. Every other place says "cards".
