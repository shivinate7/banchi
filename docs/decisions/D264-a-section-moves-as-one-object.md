## D264 — A section moves as one object

**The owner asked for a visual box map.** The owner wanted to drag sections between boxes, with their cards moving along. A section is a building block with its own divider. The map is a side-by-side bird's-eye view. The owner can drop a section before or after any section of the other box. The divider moves with its section, so the section is deleted from the source box.

The spec is `docs/specs/box-map.md`. This entry records the decisions the spec builds on.

### The rulings

1. **A section is a first-class object.** It keeps its name, its divider and its cards when it moves. The source box loses the section. The destination gains it whole.
2. **v1 scope.** Move a section between boxes, before or after any section of the destination. Reorder sections within a box. Merge a whole box into another, and split a box. Single cards and ranges come right after v1. They join v1 only if they are easy on top of it.
3. **The map lives in Inventory,** as a "Shelf" view. That keeps D31 (one owner-side view of stored cards).
4. **The map shows counts only in v1.** No money.
5. **A moved card keeps its price.** A separate entry records it: slug `a-moved-card-keeps-its-price`.

Two answers are the orchestrator's defaults, not the owner's rulings. The owner had no preference on when a drop saves. The default is that it saves at once, and a receipt holds the physical instructions, with Undo on `U`. The owner was not asked about undo. The default is an exact restore while neither box has changed since the move. After that, the way back is a new move.

### The premise that no longer holds

D83 (a card leaves a box through a third door: moved) built the move as a card-level act. A card lands at the back of the destination. Its divider and its section name stay in the source box. D83 says that `Box.section_names` has no write path on a move. The comment on `store/master.py:Box` says the opposite. The code does what D83 says, so the comment is false.

The owner thinks of a section as one object, not as many cards. Under D83, a moved section joins the destination's last section, and an empty divider stays in the source box. So after one move, the map and the physical box disagree.

D83 also says a box emptied by a merge cannot be reclaimed. The box map review read D134 (a departed record is buried, not kept) as making that sentence stale, so a merged-out box could be deleted now. That reading is proposed. It awaits the owner's word.

### What D83 protected, and what protects it now

D83 protects three outcomes. A move is one transaction. A stored index never moves. A moved card leaves a record of where it went. All three stay:

- A section move is one `Store.write()`. It removes the source divider, opens a divider at the destination with the name, moves the cards, and records one group event.
- The stored index stays fixed (D10, the inventory model, and D58, a card's number counts the cards). The orchestrator infers that placement before or after a section needs a card order that is not the index. A separate entry records that proposal: slug `card-order-key`.
- Every moved card keeps its tombstone with `moved_to`.

New guards come with the section object:

- A write carries an aim: the count and the first and last card names. A mismatch refuses.
- A card with a live paid reading cannot move (D174, a press claims the cards it is about to buy).
- A sealed box is not a target (D20, a box is an object).

### What is built

Built on `ux/boxmap` for PR 3. Slice 0 is in D262 (a moved card keeps its price). The section move, the reorder, the merge, the split and the exact undo are in D294, with the order key they need. The Shelf view in `#/inventory` is the screen. The aim, the paid-reading refusal and the sealed box are each refused at the write.

### The switch labels

The owner ruled the labels are "List", "Map" and "Sets". One switch on `#/inventory` serves three views. The box walk is "List". This map is "Map". D293's by-set view is "Sets". The PR 3 integration merged the box map and the set view into one kit `Segmented` control, `BoxShelf.tsx:ShelfSwitch`. The URL values stay `view=walk`, `view=shelf` and `view=sets`. They are machine keys that specs and deep links already carry, so no alias is needed. The record's own name for this view stays "the Shelf" where it names the code.
