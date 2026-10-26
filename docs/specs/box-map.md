# Box map: sections as objects you can see and move

**Status: BUILT.** The Shelf view on `#/inventory` (`?view=shelf`, labeled "Map" on the switch)
draws it. D264 (a section moves as one object) records the rulings. D294 (each card carries a
fraction order key) records the store half, the move routes and the undo. D262 (a moved card keeps
its price) records the safety step. `app/tests/boxmap.spec.ts` and harness test T7 check it. Section
numbers are stable ids, because code cites them.

Sections are modular building blocks. A section is its own small object, and its divider travels
with it. The move shows the two boxes it is between, stacked at every width, seen from above. A
section drops before or after any section of the other box. Cards stand in a vertical row. The card
nearest the operator's body is the last one.

The scope is: see every box and its sections. Move a section before or after any section of another
box. Reorder within one box. Merge a box into another. Split a box into a new one. Single cards and
ranges use the same write. Money does not appear on the map, only counts. Moves are drafted in Layout
mode. Confirm saves the whole draft at once, with one receipt and one Undo on `U`.

## 5. The screen

### 5.1 Where it lives

A "Shelf" view sits inside `#/inventory`, beside the box walk. That keeps D31 (one owner-side view of
stored cards) and adds no nav row.

### 5.2 The overview

Every box is one row, and the rows stack, one above the next. **Sections run left to right: the far
back of a box, card 1, is at the left, and the end nearest the operator, the highest number, is at
the right.** "Back" and "Front" labels over the rows say which way the shelf reads. The map grows
down as boxes are added. A long row scrolls inside its own frame, so the page never scrolls
sideways. The owner's ruling for this layout is recorded only in a comment in `BoxShelf.css`. No
decision entry holds it.

- **The box head** shows its name and its cards on hand. No box number shows.
- **One block per section.** Its width follows its count against the fullest section on the shelf.
  It has a floor of 7rem so a small section is still a target, and a ceiling of 16rem so one huge
  section cannot push the other rows off screen. It carries the section name (or "Section 2") and
  its count. Cards are drawn as a CSS pattern. They are never one element per card.
- **Departed cards leave no holes** (D58, a card's number counts the cards).
- **An empty section** (a divider with no card) is a thin dashed block, because the plastic is still in
  the box.
- **"New Box"** is a destination row while a move to a new box is open. It splits a section into a new
  box. A new box with no name gets its stored default name.

### 5.3 The move

The map is read-only until the operator presses "Layout". That press reads the boxes again, with a
content digest for each (see Confirm below), and opens an empty draft. The switch for the other views
leaves the page while the draft is open. A drag or a pressed gap queues one move into the draft and
writes nothing. The map redraws as the draft would leave it, and the page says how many changes are
queued. "Cancel" throws the draft away. "Confirm" stays disabled until one move is queued.

There are two ways to queue the same move:

- **Drag the grip.** Each section that holds cards carries a grip. A press that travels under 4px is a
  click and says "Drag to move it, or press the arrow." A drag drops the section in front of the first
  section whose middle is right of the pointer, in whichever real box the pointer is over, or at that
  box's near end. A drop where the section already stands queues nothing. The drop mark is a bar inside
  the target box, and the box takes an accent border. Nothing else on the map moves (D313). The page
  scrolls near the window's top and bottom edge while a section is held. Esc ends the drag.
- **Press the arrow beside the grip ("Move Section").** A bar opens with the section's name and card
  count. It offers what moves: "This Section", "This and the Next" (or "This and the N After It"), "The
  Whole Box" (a merge) and "Some Cards". Then it offers where: each other box, "Another Place in" the
  same box (a reorder), and "New Box" (a split). With a place chosen, the two boxes show stacked and
  every gap is a plus button. Pressing one queues the move, and so does a drag onto it. Esc
  cancels the bar. Enter or Space on the grip opens the same bar. Every control is a button, so the
  path needs no drag, which is the path for touch and for the keyboard.

"Some Cards" moves one card or a range of cards in one section, with a gap in front of every card of the
destination and one at each section's end. A range moves no divider. A range can only be picked up
from, or aimed at, a box the draft has not touched yet, because the real card list it reads would
disagree with an earlier queued move. It cannot go to "New Box".

A box emptied by a merge holds only tombstones and may be deleted (D83, D134).

**Confirm** sends the whole draft to `POST /boxes/sections/move-batch`. The moves apply in the order
queued, in one store transaction, or none of them applies (D88). Before any write, each box the draft
touched is checked against the digest read when Layout was pressed. The digest covers the box's
dividers and each card's identity, order key, section and state. A card captured, sold, retired,
removed or moved since then refuses the whole draft with `draft_stale`, and the map reads the boxes
again. A note, photo, SKU or price edit does not change the digest. A later move in the draft may aim
at a box an earlier one changed, so a queued move carries no aim of its own.

- **A lifted or dragged section takes an accent tint.** The tint is a border and a ground, never a
  fill.
- **The build uses Pointer Events, written in this repo.** It uses no drag library. Native HTML drag and
  drop does not fire on touch.

### 5.4 The receipt is the physical instruction

Confirm saves the draft, and a receipt opens under the map. It is the checklist the hand follows, in the
operator's orientation. Its heading reads "1 change to make." or "N changes to make.", and its numbered
steps are every queued move's steps in order. For a draft of one section moved from RB Origins into the
middle of Mixed Singles:

> **1 change to make.**
> 1. In RB Origins, find the divider **Uncommons**. Its first card is **Hextech Anomaly**. Its last
>    card is **Sacred Shears**.
> 2. Take out that divider and the 10 cards on your side of it, up to the next divider.
> 3. In Mixed Singles, find the divider **Rares**. Put them just on the far side of it, in the same
>    order.
>
> In RB Origins, Signatures moves from Section 3 to Section 2. In Mixed Singles, Rares moves
> from Section 2 to Section 3. **Undo** (U)

- **The orientation is the operator's.** Card 1 is at the far back. A section's cards stand on the near
  side of its divider. The receipt never says "behind" or "in front of" alone. It says "on your side" or
  "on the far side". The store's append goes to the end nearest the operator, so "the back" is the wrong
  word for it.
- **Landmarks are card names.** A card with no name is not a landmark (D260, an unnamed card is not a
  landmark), so the receipt counts cards.
- **The renumber line.** A card's number counts within its section, so a section move changes no card
  number. It can change section numbers, and the receipt says which.
- **Two more lines, each absent at zero.** One line states how many moved cards are owed to open orders
  (`receipt.owed`), over the whole draft. It counts, per SKU, the lesser of the copies moved and the
  copies owed, because a copy is fungible (D212). The other lines name, for each box whose last section
  moved or that a same-box move made last, the section that the next capture joins
  (`receipt.next_capture`). Press S first to start a new section. The Shelf draws them under the steps.
- **The receipt stays** until the operator presses "Done" or presses "Layout" again. "Done" writes
  nothing.

### 5.5 Undo

Undo, on `U` or the receipt's Undo button (named "Undo this layout"), reverses the whole draft exactly, in every box it
touched. The tombstones come back at their old indices. The moved records go. The dividers, the names
and the order keys go back to each box's state from before the draft's first move reached it. A box
the draft created goes too, if it holds no card. The receipt then reads "Put back. Nothing needs to
move." Undo is allowed only while nothing else has written to a touched box since Confirm. It compares
each touched box's records with the hash that Confirm wrote, and reads no clock. A capture, a sale, a
rename or another move in a touched box refuses it (`box_changed_since`), and so does a paid run
reading a card it would move back (`card_being_read`). After another write, the way back is a new move.

## 6. A drop that crosses something in flight

| Case | Behavior |
| --- | --- |
| A card in the section has a live paid reading | Refuse at Confirm and at Undo. Nothing in the draft is applied. The refusal names the reading (`card_being_read`). |
| The section's cards belong to a run that is matched and not yet sent | Allow. The join follows the card (D262). |
| Cards owed to open orders | Allow. Orders claim no copy (D212, no order claims a copy). The receipt says so. |
| A stale walk or Cards to pull presses sold on a moved card | The server answers `card_moved`. The screen says where the card went, from the tombstone's `moved_to`, and refreshes. |
| A box in the draft changed since Layout was pressed (a capture, a sale, a retirement, a removal or a move, from this screen or another) | Confirm refuses the whole draft with `draft_stale`. Nothing moves, and the map reads the boxes again. |
| The destination is a sealed box | Refuse at Confirm (D20, a box is an object). |
