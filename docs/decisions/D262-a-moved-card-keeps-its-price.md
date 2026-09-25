## D262 — A join follows a moved card by its own link, checked by its name

**The owner's ruling, 2026-09-23, in the box map interview: pricing follows the card.** When a
card moves to another box, the join follows it to its new place. The match is by the card's
unique name. This amends one sentence of D165 (a run is bound to the box's true index).

The ruling came with the box map (`docs/specs/box-map.md`). It reaches today's "Move to box"
too, because that press already moves cards between boxes.

### The sentence, and the premise that no longer holds

D165 says that `cli/resolve.py:realign` looks only in the boxes the run names. Its reason: "a
join must never follow a card into a drawer nobody asked it about."

That sentence stood on D48 (a send is a cart of boxes, and a run is one box). D180 (a press
names the cards it is over) superseded D48: the box stopped being the unit of work. Two facts
now make a move a certain link, not a guess:

- A moved card's old position is a tombstone that records `moved_to` (D83, a card leaves a
  box through a third door).
- A card's name, `cid`, is unique and frozen at issue (D172, a card's name is the first
  photograph of it).

### The evidence

D165 measured the cost of the old rule on the owner's store. The owner moved 99 cards from box
1 to box 3. They fell off their run and lost their pricing surface. Only a hand repair,
`pkmnscan rescue`, brought them back.

### What D165 protected, and what protects it now

D165's sentence protects one outcome: a join never guesses which card a record is. D36 (the
run says what the model read, the store says which slot it is in) earned that caution. A
re-join of box 2 once wrote 47 queue entries one position off.

The new rule keeps that outcome with a narrower door:

1. `realign` follows a tombstone's own `moved_to` link, one hop at a time.
2. At the destination, the card's `cid` must equal the tombstone's `cid`. On a mismatch, the
   join refuses the card and names it, as it does today.
3. No other search runs. The join never looks in a box by any other reason.

D36's refusal, `refuse_reallocated` and D165's `bid` binding stay as they are.

### One more guard in the same slice

The box map review found that today's move does not check a live paid reading. A batch that
lands after a move writes onto the tombstone, and the moved card stays unidentified. That was
read in code, not run. `store/submissions.py` already has the check a move needs
(`Submissions.overlap`). The first slice of the box map adds it to the move, so a card with a
live claim cannot move. That keeps D174 (a press claims the cards it is about to buy).

### What is built

BUILT, 2026-09-25, as slice 0 of `docs/specs/box-map.md`. `cli/resolve.py:follow_moved` is
the follow. `realign` calls it before its per-box check, so a box merged away whole does not
read as `unverified`. `server/capture_server.py:_move_one` refuses `card_being_read` on a live
claim. T7's `check_box_map_safety` (in `harness/tests/t7_box_map.py`) moves a joined card,
re-runs the join, and asserts that the card keeps its row. The same case with a name mismatch
refuses. Each assertion was red before its fix.

**One more defect, found by that case.** A card could move only once. The second tombstone took
the first tombstone's `moved:<name>`, and `cards_cid` is UNIQUE, so the commit failed.
`Inventory.move_card` now names a later tombstone `moved:<name>@<its own key>`. The first
tombstone keeps the plain form, so a store written before this reads as before.
