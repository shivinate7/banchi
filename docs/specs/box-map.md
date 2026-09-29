# Box map: sections as objects you can see and move

**Status: BUILT.** The Shelf view on `#/inventory` (`?view=shelf`, labeled "Map" on the switch)
draws it. D264 (a section moves as one object) records the rulings. D294 (each card carries a
fraction order key) records the store half, the move routes and the undo. D262 (a moved card keeps
its price) records the safety step. `app/tests/boxmap.spec.ts` and harness test T7 check it. Two
receipt lines are not built (DEBT38). Section numbers are stable ids, because code cites them.

The owner's picture: sections are modular building blocks. A section is its own small object, and
its divider travels with it. The move shows two boxes side by side from above. A section drops
before or after any section of the other box. Cards stand in a vertical row. The card nearest the
owner's body is the last one.

The scope is: see every box and its sections. Move a section before or after any section of
another box. Reorder within one box. Merge a box into another. Split a box into a new one.
Single cards and ranges use the same write. Money does not appear on the map, only counts. A drop
saves at once with a receipt and Undo on `U`.

## 5. The screen

### 5.1 Where it lives

A "Shelf" view inside `#/inventory`, beside the box walk. That keeps D31 (one owner-side view of
stored cards) and adds no nav row.

### 5.2 The overview

Every box is drawn from above, as it sits on the desk. **The far back of a box, card 1, is at the
top. The end nearest the owner, the highest number, is at the bottom.** The boxes stand side by
side.

- **The box head** shows its name and its cards on hand. No box number shows. A press opens the
  walk at that box.
- **One block per section.** Its height follows its count, with a floor of 44px so a small section
  is still a target. It carries the section name (or "Section 2") and its count. Cards are drawn
  as a CSS pattern and never as one element per card.
- **Departed cards are not holes** (D58, a card's number counts the cards). Sold and moved counts
  go in the box head.
- **Badges appear only when true.** "Being read" means that a card in the section has a live paid
  reading. "3 owed" means that open orders want copies from it.
- **An empty section** (a divider with no card) is a thin dashed block, because the plastic is
  still in the box.
- **A last column, "New box",** is a target that splits a section into a new box. A new box with
  no name gets its stored default name.

### 5.3 The move

The order of acts: press "Move sections", pick the section, pick the box it goes to, and see the
two boxes side by side. Drag the section to a gap before or after any section of the destination.
The gap under the pointer opens, and it shows the numbers the cards will have.

A drop in the same box reorders its sections. A drop on "New box" splits. A merge moves every
section of one box, in order, to the far end or the near end of another.

- **While dragging,** the section lifts with an accent tint and its old place shows a dashed
  outline. A section with a live paid reading cannot lift. The cursor is `not-allowed` (D50,
  feedback is the product's), and the block says why.
- **Touch and small widths.** At 390 and 720, the primary path is tap to pick and tap to place. A
  bar says "Uncommons, 10 cards. Tap a gap to put them there. Cancel." A long-press drag is a
  second path and never the only one, because a drag over a scrolling list fights the page scroll.
- **Keyboard.** The map is a grid. Arrows move between sections, Space lifts the focused section,
  arrows choose the gap, Enter drops and Esc cancels. An `aria-live` line says where it will
  land. Each section also has a "Move to" menu, the path that works for every input. Every new
  binding goes into `SHORTCUTS` in `app/src/keys.ts`.
- **The build is Pointer Events, written in this repo.** No drag library. Native HTML drag and
  drop does not fire on touch.

### 5.4 The receipt is the physical instruction

The move saves at once. A receipt opens under the map. It is the checklist the hand follows, in
the owner's orientation. For a section moved from RB Origins into the middle of Mixed Singles:

> **Move 10 cards from RB Origins to Mixed Singles.**
> 1. In RB Origins, find the divider **Uncommons**. Its first card is **Hextech Anomaly**. Its last
>    card is **Sacred Shears**.
> 2. Take out that divider and the 10 cards on your side of it, up to the next divider.
> 3. In Mixed Singles, find the divider **Rares**. Put the Uncommons divider and its 10 cards
>    just on the far side of it, in the same order, card 1 farthest from you.
>
> In RB Origins, Signatures moves from Section 3 to Section 2. In Mixed Singles, Rares moves
> from Section 2 to Section 3. **Undo** (U)

- **The orientation is the owner's.** Card 1 is at the far back. A section's cards stand on the
  near side of its divider. The receipt never says "behind" or "in front of" alone. It says "on
  your side" or "on the far side". The store's append goes to the end nearest the owner, so
  "the back" is the wrong word for it.
- **Landmarks are card names.** A card with no name is not a landmark (D260, an unnamed card is
  not a landmark), so the receipt counts cards.
- **The renumber line.** A card's number counts within its section, so a section move changes no
  card number. It can change section numbers, and the receipt says which.
- **Two more lines are designed and not built** (DEBT38). One says how many moved cards are owed
  to open orders. The other says which section the next capture joins when the moved section was
  last. Press S first to start a new section.
- **The receipt stays** until the owner closes it or the next move replaces it. Its "Done" press
  writes nothing.

### 5.5 Undo

Undo, on `U` or its button, reverses the whole move exactly. The tombstones come back at their old
indices, the moved records go, and the dividers, the names and the order keys go back. It is
allowed only while nothing else has written to either box since the move. The check reads events
and never a clock (`docs/specs/undo.md` section 2). After another write, the way back is a new
move.

## 6. A drop that crosses something in flight

| Case | Behavior |
| --- | --- |
| A card in the section has a live paid reading | Refuse before the drag starts, and again at the write. It names the reading. |
| The section's cards belong to a run that is matched and not yet sent | Allow. The join follows the card (D262). |
| Cards owed to open orders | Allow. Orders claim no copy (D212, no order claims a copy). The receipt says so. |
| A stale walk or Cards to pull presses sold on a moved card | The server answers `card_moved`. The screen says where the card went, from the tombstone's `moved_to`, and refreshes. |
| Another device changed the section since the map loaded | The write carries an aim: the count and the first and last card names. A mismatch refuses, and the map reloads. |
| The destination is a sealed box | Refuse (D20, a box is an object). |

## Open

- **The side-by-side view at 390.** Two columns of about 170px may hold section names. Draw it and
  show the owner before a change.
- **The Graveyard after a move.** A 40-card move adds 40 rows. One row per move may read better.
  The owner did not ask.
- **A merged-out box.** D83 (a moved card) says a box emptied by a merge cannot be reclaimed. D134
  (a departed record is buried, not kept) may make that sentence stale. The reading awaits the
  owner's word.
