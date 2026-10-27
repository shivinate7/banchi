# D262 — Pricing follows a moved card

**The owner's ruling, 2026-09-23, in the box map interview: pricing follows the card.** When a
card moves to another box, the join follows it to its new place. The match is by the card's
unique name. This amends one sentence of D145 (a run is bound to the box's true index).

The ruling came with the box map (`docs/specs/box-map.md`). It reaches today's "Move to box"
too, because that press already moves cards between boxes.

### The sentence, and the premise that no longer holds

D145 says that `cli/resolve.py:realign` looks only in the boxes the run names. Its reason: "a
join must never follow a card into a drawer nobody asked it about."

That sentence stood on D180 (a send is a cart of boxes, and a run is one box). D180 (a press
names the cards it is over) superseded D180: the box stopped being the unit of work. Two facts
now make a move a certain link, not a guess:

- A moved card's old position is a tombstone that records `moved_to` (D83, a card leaves a
  box through a third door).
- A card's name, `cid`, is unique and frozen at issue (D172, a card's name is the first
  photograph of it).

### The evidence

D145 measured the cost of the old rule on the owner's store. The owner moved 99 cards from box
1 to box 3. They fell off their run and lost their pricing surface. Only a hand repair,
`banchi rescue`, brought them back.

### What D145 protected, and what protects it now

D145's sentence protects one outcome: a join never guesses which card a record is. D36 (the
run says what the model read, the store says which slot it is in) earned that caution. A
re-join of box 2 once wrote 47 queue entries one position off.

The rule keeps that outcome with two doors, and both match by the card's own name:

1. `realign` follows a tombstone's own `moved_to` link, one hop at a time. At the
   destination, the card's `cid` must equal the tombstone's `cid`. On a mismatch, the join
   refuses the card and names it.
2. Where the store disowns a run's drawer (`cli/resolve.py:disowned_boxes`, the rule
   `refuse_reallocated` reads), the drawer's slots are never read, because that number
   belongs to another drawer. `realign` looks up each record's photograph digest in every
   live drawer instead. One match is a certain link. Two matches is a question and refuses.
   No match is a departed card, and the join names it. If no record matches anywhere,
   `refuse_reallocated` still refuses the run, as before.

The second door exists because the first one dies with the tombstone. Deleting a box that a
merge emptied (D134) buries its tombstones, so the run's link was gone from the store and the
run read as stranded. Measured on the owner's store: 105 cards moved from box 5 to box 3 and
box 5 was deleted 3 seconds later. Three runs (99, 65 and 94 sellable cards) came off the
price list that way, and a send then wrote ghost cards into the dead box. A foreign card in a
reused slot is still never adopted: its digest matches no record of the run.

`banchi rescue` and Rebind remain for a run whose cards sit in more than one box. A run that
already has a joined rescue stays out of the pricing roster, so the rescue and its source never
count the same cards twice (D86).

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
`Inventory.move_card` now names every new tombstone `moved:<name>@<its own key>`. A tombstone
already on disk keeps its plain form and reads as before. A first build asked the store whether
the plain form was taken, and the R3 review measured that lookup making a 500-card merge
quadratic (3.8 s under the lock). So no query decides the form.
