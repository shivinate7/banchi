## D-a-key-on-each-card — Every card carries its own order key, a fraction that starts at its index

**The owner's ruling, 2026-09-25, on D265's open question.** Asked the form of the order key,
the owner answered: "A key on each card". The owner did not choose runs of indices on the box
record, which the first build (`ux/boxmap`, 2026-09-25) had used. D265 (a card's place in its
box is an order key apart from its stored index) points here for the form.

### The form

`Card.order` is a number beside `Card.index`, in the payload and in the REAL column
`cards.ord`. The walk, every label and every section bound read it. The stored index never
moves (D10, D58).

**The key is a fraction, and it starts at the index.** The builder chose this over a gapped
integer, for three reasons.

- **Nothing moves on the day it lands.** The schema 13 migration gives every card the key its
  index already is. So every box reads in today's order, every label counts as before, and
  every stored divider (an index) is already a key. No box record is rewritten. A gapped
  integer (the index times 1,024) would rewrite every divider and every section name's key.
- **A capture keeps the identity.** A new card in a box that nothing was placed into takes
  its own index as its key, so such a box stays the identity. The fast path in every reader
  (`BoxOrder.identity`) skips the mapping for it.
- **An insert writes only the cards that move.** A card placed between two others takes a key
  between theirs: `lo + (hi - lo) * n / (count + 1)`. One gap between two whole-number keys
  halves 20 times before two keys come closer than `KEY_EPSILON` (one millionth), as measured
  by the R3 review. Then the box is
  re-spaced once (`Inventory._respace`): every card gets a whole-number key again, in the order
  it stands. That is the one write that touches cards a placement did not move. It is logged
  as `box_respaced`.

### The dividers

A divider is a key: a section starts at the first card whose key is at or above it. The first
divider is the front of the box. It is 1, or it is below 1 after a placement in front of card
1. A divider past the last card is a plan, counted in whole slots (`Position._divider`). Section
names are keyed by the divider's key (`divider_key`). That key is `31` for every divider stored
before the order key.

### The moves

`Inventory.place` is the one placement. It takes what arrives, in order (dividers and cards),
and a gap. The gap is in front of a section, at the near end, in front of a card, or at a
section's end. Only the arriving cards take new keys. A card that crosses boxes still leaves a
tombstone with `moved_to` (D83), and the tombstone keeps its key. A mid-box delete (D10 ruling
1) slides the indices and writes no key: the deleted card leaves a gap in key space, which
nothing counts. The first build slid a key that equalled its index. That crossed the keys of
placed cards, which the R3 review caught. The delete also points each tombstone's `moved_to` at
the card's new index, so the join can still follow it.

### Undo

A move writes one `sections_moved` event. The event holds both boxes' dividers and names as
they were, and every card's old key. It also holds each moved card's old state, and a hash of
each box after the move. Undo compares the hashes. While neither box has changed, it puts every
card, key, divider and name back exactly. Anything that wrote to either box since refuses, and
the way back is a new move. This reads the data, never a clock (`docs/specs/undo.md` section 2).

### Single cards and ranges

The owner's ruling of 2026-09-25 made them the next slice: "Next box-map slice". A lifted
section on the Shelf shows its cards. The owner picks one card or a range. The drop goes in
front of any card, or at the end of any section, of the destination.
`POST /boxes/<box>/cards/move` (`do_move_range`) is the route. It uses the same one write, the
same receipt shape and the same undo. No divider moves with a card. A card placed in front of
the first card of a section joins that section, and the section's divider moves down to it.

### What is built

BUILT on `ux/boxmap`, 2026-09-25. The store half is `Card.order`, `BoxOrder`,
`Inventory.layout_of`, `Inventory.place`, `Inventory.drop_sections` and `_respace`. The
migration is `store/db.py:_add_card_order`, schema 13. It was proved on a copy of the demo
store. All 122 cards got a key equal to their index, and no box record changed. Every label
equals main's index-space formula. The routes are `POST /boxes/<box>/sections/move`,
`POST /boxes/<box>/cards/move` and `POST /boxes/sections/undo`. T7's `t7_box_map.py` covers
the migration, the per-card keys after each kind of move, and the card and range moves.

### The divider editor after a placement

The editor speaks card numbers, and the store keeps keys. A start the operator did not change
keeps the divider already stored, so a save never moves a divider it was not asked to move. An
edited start maps to the key of the card at that number, never `int()` of it (the R4 review).

**An empty section is kept** (the R5 review). A card move can leave a section with no card. Its
divider is still in the box, so an unchanged save keeps it, name and all. The editor draws an
empty section with the start of the section after it. That repeat is taken as the empty
section, and it is not refused. Dropping the section is the owner's act: the operator removes
that start in the editor, and the save removes the divider.

### Planned, not built

- **Two receipt lines** from `docs/specs/box-map.md` section 5.4: the cards owed to open orders,
  and the next capture that joins a moved last section.
- **The public demo** answers no move. Its stub server has no handler for the three routes, so
  a press on the demo is refused.

- **A save moves a divider past departed records** (the R5 review, LOW, older than this lane).
  The cards in front of a divider can have left. Then the editor's number maps to the first
  card on hand, and a save of that edited start lands after the departed records. Not fixed
  here.
