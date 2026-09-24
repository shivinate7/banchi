## D-a-section-is-an-object — A section is an object that moves whole, and the box map is a view inside Inventory

**The owner's rulings, 2026-09-23, on a new feature: a visual box map.** The first wish, in the
owner's words:

```
really wish there was an interactive / visual way of seeing my boxes and literally dragging
and dropping sections from one box to another and all the cards are able to seamlessly move
with no difficulties
```

Then the owner's picture of it:

```
sections being literally like modular building blocks where if i select move sections, i then
select which box i want to move this section into, and after selecting i get a side by side 2d
birds view and i literally can drag and drop the section before or after section i want of the
other box
```

And on what happens to the divider: "the section is deleted from the previous box, think of
sections as their own mini objects".

The spec is `docs/specs/box-map.md`. This entry records the decisions the spec builds on.

### The rulings

1. **A section is a first-class object.** It keeps its name, its divider and its cards when it
   moves. The source box loses the section. The destination gains it whole.
2. **v1 scope.** Move a section between boxes, before or after any section of the destination.
   Reorder sections within a box. Merge a whole box into another, and split a box. Single cards
   and ranges come right after v1. They join v1 only if they are easy on top of it.
3. **The map lives in Inventory,** as a "Shelf" view. That keeps D31 (one owner-side view of
   stored cards).
4. **The map shows counts only in v1.** No money.
5. **A moved card keeps its price.** A separate entry records it: slug
   `a-moved-card-keeps-its-price`.

Two answers are the orchestrator's defaults, not the owner's rulings. The owner had no
preference on when a drop saves. The default: it saves at once, and a receipt holds the
physical instructions with Undo on `U`. The owner was not asked about undo. The default: an
exact restore while neither box has changed since the move. After that, the way back is a new
move.

### The premise that no longer holds

D83 (a card leaves a box through a third door: moved) built the move as a card-level act. A
card lands at the back of the destination. Its divider and its section name stay behind. D83
says that `Box.section_names` has no write path on a move. `store/master.py:Box` has a comment
that says the opposite. The code does what D83 says, so the comment is false.

The owner does not think of a move as many cards. The owner thinks of a section as one object.
Under D83 a moved section joins the destination's last section. An empty divider stays in the
source box. So after one move the map and the plastic disagree.

D83 also says a box emptied by a merge cannot be reclaimed. D134 (a departed record is buried,
not kept) made that sentence stale. A merged-out box can be deleted now.

### What D83 protected, and what protects it now

D83 protects three outcomes. A move is one transaction. A stored index never moves. A moved
card leaves a record of where it went. All three stay:

- A section move is one `Store.write()`. It removes the source divider, opens a divider at the
  destination with the name, moves the cards and records one group event.
- The stored index stays fixed (D10, the inventory model, and D58, a card's number counts the
  cards). Placement before or after a section needs a card order that is not the index. A
  separate entry records that decision: slug `card-order-key`.
- Every moved card keeps its tombstone with `moved_to`.

New guards come with the section object:

- A write carries an aim: the count and the first and last card names. A mismatch refuses.
- A card with a live paid reading cannot move (D174, a press claims the cards it is about to
  buy).
- A sealed box is not a target (D20, a box is an object).

### What is built

SPECIFIED, NOT BUILT. `docs/specs/box-map.md` lists the slices in build order. The first slice
is a safety fix to today's "Move to box", and it needs no new screen.
