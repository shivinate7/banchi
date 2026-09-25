## D-box-order-is-runs — A box's order is runs of stored indices on the box record, and the dividers count in that order

**The builder's design for D265, 2026-09-25.** D265 (a card's place in its box is an order
key apart from its stored index) left the form of the key open. It asked for the owner's word
before the build. The orchestrator's brief for the box map lane asked for the build now, in PR
3. So the owner sees the design in that PR, before it merges. This entry records the form that
was built and why. It is a proposal until the owner's word.

### The form

A box record holds `order`: a list of runs of stored indices, in the order they physically
stand. The last run is open at the back. `[[1, 3], [11, 12], [4, 10], [13, null]]` says that
indices 11 and 12 stand between 3 and 4. An empty list means that the order is the index. So
every store written before this reads exactly as before, and no migration runs.

The dividers (`Box.sections`) and the section names count in this order. With no runs, that is
the index, so every stored layout is already valid.

### Why runs on the box, and not a key on each card

D265 named three forms. This is its third, "an order within the section object", taken one
level up to the box.

- **A key on each card** (a fraction or an integer with gaps) makes a reorder in one box a write
  to every card that moves. A reorder of runs writes one box record and no card. A card is
  never touched to change its place, and the fence "a move never changes a card" holds by
  construction for a reorder.
- **Runs stay short.** Each placement adds at most three runs. Runs that touch merge. The box
  map deliberation estimated about 40 sections on the owner's store.
- **The mapping is one pass.** `store/master.py:BoxOrder.of` walks the runs.
  `pipeline/join.py:BoxView` maps a whole box once and hands `Position` orders. `Position` is
  still the one label formula, and it never sees an order.

### What protects D10 and D58

The stored index never moves. Queue entries, the cache, listing holds and every write's aim use
it as before. A card that crosses boxes still leaves a tombstone with `moved_to` (D83). A
mid-box delete (D10 ruling 1) slides the indices, and `BoxOrder.without_index` closes the runs
up with them, so every other card keeps its place.

### Undo

A section move writes one `sections_moved` event. It holds both boxes' records as they were,
each card's old state, and a hash of each box after the move. Undo compares the hashes: while
neither box has changed, it puts every card, divider, name and order back exactly. Anything
that wrote to either box since (a capture, a sale, a rename, another move) refuses, and the way
back is a new move. This reads the data, never a clock (`docs/specs/undo.md` section 2).

### What is built

BUILT, 2026-09-25, on `ux/boxmap`. The store half is `Box.order`, `BoxOrder`,
`Inventory.section_runs` and `Inventory.place_sections`. The routes are
`POST /boxes/<box>/sections/move` and `POST /boxes/sections/undo`
(`server/capture_server.py:do_move_sections`, `do_undo_section_move`). The client functions are
`moveSections` and `undoSectionMove`. T7's `check_section_moves` covers the placement, the
reorder, the merge and the split. It also covers the undo and its refusal, the sealed box, the
stale aim, the paid reading, and the mid-box delete. Four mutations each turned it red.
