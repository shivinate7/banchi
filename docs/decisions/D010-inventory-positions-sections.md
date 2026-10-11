## D10 — Inventory model: positions, sections, stack

**A card gets a sequential position at capture, and positions are never renumbered.** Location is Box N, Section N, Card N. Sold cards leave permanent gaps.

### Sections are per-box and declared at capture time

A box carries its own list of divider indices. `[1, 31, 56]` means section 2 starts at card 31. The operator sets the list when the real divider goes in. `CARDS_PER_SECTION = 25` was a bare module literal. No env var, flag or parameter could reach it. Real boxes have dividers where the operator put them.

**An empty list means undeclared. An undeclared box is one section. There is no automatic divider.** The old 25-rule kept labels byte-identical for undeclared boxes. It cut a divider into every undeclared box every twenty-five cards, whether or not one was in the plastic. Identical labels are worth nothing when they match a boundary nobody put there.

**The measurement is the owner's own store.** Box 1 holds 133 cards and declares no layout. It rendered as six sections, so a person sent to `Section 4 · Card 8` counted for a divider that does not exist. Box 2 declares `[1, 86, 171, 253, 394]` and is untouched, as is every other declared box. The change reaches only the boxes that never declared dividers.

**What replaces the constant is `(1,)`, the one divider every box really has, at its front.** `pipeline/join.py:Position.layout` states the fallback once. `section`, `section_start` and `section_end` all read it. Before, the constant had three branches doing their own arithmetic. So `card` is the index, `section` is 1, and `section_end` is None. That is D20's existing answer for a final section, not a new rule. The caller holding the box's capacity fills it in. `Position` is still the only label formula in the repo. The v1 to v2 migration still writes an empty layout for every box it finds. Only what an empty layout renders as has changed.

**The labels of every undeclared box moved once, on purpose. That is the cost.** It is the risk `harness/tests/t7/store_core.py` names for the migration: every position label in a real inventory shifts at once. Here the shift is deliberate. It is affordable because no label was ever printed. Labels are read live off a screen. T7 pins the new strings, so the next shift is not accidental either.

### The `New section` control is `S` on the capture screen

The owner asked for sectioning the operator can create from the capture screen, the way `C` is capture. The set hint moved to `H`. Before this, the only way to declare a divider was `PUT /boxes/<box>` with a whole layout, typed into a field on `#/inventory`. That was a different operation with the same words. It ran later, from another screen. It needed the operator to remember which card they were on when the divider went in.

**The two halves of that instruction are one design.** Deleting the automatic divider makes the key worth having. A screen that invents a boundary every 25 cards does not need a control to put one in. The key makes deleting it safe.

- **`POST /boxes/<box>/sections` takes NO INDEX.** `store/master.py:open_section` reads `next_index` inside the store lock, so the divider lands in front of the card the next capture takes. A client that computed the index would read a high-water mark across a round trip and send it back. That is the lost update `next_index`'s own docstring exists to prevent. At the feeder's measured 623 ms cadence, the risk is real.
- **It is `next_index`, not count+1.** The difference matters in a box with permanent gaps. A count would put the divider in front of a card that will never be captured.
- **An undeclared box materializes `[1, at]`, not `[at]`.** `check_sections` requires a layout to start at index 1, and it is right to. No card sits before the front of a box. Nothing is invented: section 1 already started at card 1. This is the first time anything needed to write that down.
- **It logs `resectioned` through `set_sections`.** That is the event the dividers editor already writes. The event carries both layouts. A new event name was rejected on D26's evidence. This store already had a state and a history event that shared a word.
- **Refusal codes.** `section_empty` answers a second S press with nothing captured between. The divider wanted is already there. An empty box also gets this code, since card 1 is where the first section starts. `section_ahead` (a divider declared past the next card) is deleted. The next card now goes behind such a divider, so that section is empty, and `section_empty` answers it. `box_closed` (a sealed box took no divider) came with the seal (D299).
- **No confirm. `U` is the undo.** Nothing is spent and nothing is destroyed. Since UN-15, `U` removes S's divider while it is the last one and no card sits behind it (`DELETE /boxes/<box>/sections?div=<key>`, D294). After that, the dividers editor corrects a wrong layout. `resectioned` carries the layout it moved from. A dialog on the screen the owner shoots a box from, at feeder pace, is what `docs/DESIGN.md` refuses in as many words.

**The set hint is `H` now, and the swap cost nothing else.** `S` sat on a field an operator opens a few times a run. It was wanted for an act performed at the box. The option alphabet (`docs/DESIGN.md`) is every key this screen has not spent. It lost `s` and gained `h`. Because `h` sorts after `e`, the first thirteen option keys are `1234567890ade` before and after. `app/tests/capture-claims.spec.ts` pins them.

### The next card goes into an empty last section

**Ruling: the next captured or moved-in card goes into an empty last section, behind its divider.** A box that ends with an empty section (S pressed, no card behind it yet) takes the next card into that section.

`store/master.py:Inventory._behind_empty_section` holds it. `next_key` and `_birth_key` read it. Every capture and every move-in takes its key from one of the two. So one rule covers every write the divider proof named. Before this, a write that lowered the box's highest key left the divider above the next card's key. Such writes were a capture undo, a Manage box remove and a move that takes the last card forward. Also a section reorder, a section-move undo and a move undo. The next card then went into the section in front of the divider (the proof's F1).

**A divider typed ahead of the fill is gone.** A section is where captures go once it exists. So `[1, 51]` on a five-card box sends the next capture into section 2. `S` then refuses with `section_empty`, and `SectionAhead` is deleted. The owner's ruling: a section keeps growing while it is selected, and a capture fills the section the operator picks. The real store held no such layout. Only boxes 4 and 6 end with an empty section, one S each.

**A capture goes on the end of its SECTION, not of the box** (D300). The owner picks the section on Capture. The store files the card at that section's tail. S can go right after a picked section. With no section named, the capture is the one above, unchanged.

`harness/tests/t7_box_map.py:check_divider_anchor` guards it (D294, the divider anchor).

### The rule governs the INDEX; the label is a view

**The index is the identity.** It is assigned once and survives a sale as a permanent gap. Nothing renumbers it. Section and Card are a rendering of that index against the box's current divider layout. Moving a divider relabels every card behind it without touching an index.

**Boundaries are freely editable from any screen, and labels always recompute.** The owner chose this over freezing a section once a card sits in it. Correcting a wrong layout is the point. A label was never printed on anything. Freezing would leave the model permanently unable to describe a box that was physically re-divided.

The cost is real, and it is recorded here. **A mis-tap relabels a filled box and nothing flags it.** The Fulfiller walks to the wrong slot with no error to see. A `resectioned` history event carrying both layouts mitigates it. Restricting the operation was the other option, and the owner declined it. If the failure happens, the first fix is a confirm on an edit that moves a divider with cards behind it. It is not a return to freezing.

### Undo deletes the record; it does not tombstone it

A tombstone would be a third thing the store has to explain: not captured, not sold, still occupying a position. Every reader would have to learn it. A deleted record is a card that was never captured. That is what the operator means by undo.

**This decides index reuse.** `next_index` is a high-water mark, `1 + max(index in this box)`. Deleting the newest record hands its index to the next capture. That is correct, not an accident. The position was assigned to a photo that no longer exists. Burning it would leave a permanent hole in a box over a mis-tapped button.

**The box-number allocator follows D20 and is a different rule.** `store/master.py:next_box_number` hands out the lowest free integer, not a high-water mark. A box number names an object on a shelf. Nothing about it is a position a card was assigned to. This rule governs the INDEX inside a box, and nothing else.

**Undo is the newest capture in a box, never an arbitrary one.** Deleting from the middle leaves a gap the high-water mark cannot reuse. Later it looks like the permanent gap a sale leaves, and those two mean different things. Restrict the operation. Do not teach the allocator to fill holes. This entry's first paragraph makes a printed position label worth trusting, and nothing that renumbers may exist.

**The capture screen shows ten rows, clickable from the sidebar.** Each row is one of the session's ten most recent captures into the current box, newest first. Each row is its own control. A row is not a delete, because the rule above forbids a mid-box delete here. Before, the control was one card and one button.

**Pressing row N undoes N cards:** that row and every card captured after it. It is the same route N times, newest first. That is the only thing the sentence above permits. Card N-1 is not the newest until card N is gone. A per-row delete of a middle card would be ruling 1's mid-box remove. That remove slides every higher card down one index, which would renumber the very rows it was pressed from. D37 refuses that for the review screen's worklist. The mid-box remove stays on `#/inventory`.

**The count is drawn on the row. That is the whole guard.** `docs/DESIGN.md` makes capture-undo the one place a destructive act gets no dialog. The reason: the deleted photo is of a card still within reach of the hand that fed it. That argument covers ONE card. A press that deletes five needs the five visible before it, not a confirmation after. So the row carries the number of cards it removes. That number is also the row's ordinal, so one chip says both. The top row carries `U` instead, because that is the key that fires it.

**A walk refused partway stops and says how far it got.** The next delete is legal only because the one before it succeeded. Carrying on would aim at a card that is no longer the newest. The count is the only thing that says where the operator is. The cards that went and the cards that did not both leave the list either way.

**The stack is this session's captures. Where the server is ahead, it collapses to one row.** A capture that committed and lost its response leaves the store holding cards this session never took. So does a capture the other device made into the same box (D13 permits both). Those cards have no label, no photograph and no count. Offering to undo back to a row underneath them would delete somebody else's captures sight unseen. So the depth is exactly one until the two agree. One ordinary undo restores agreement.

A sale is the opposite case. `sold` is a state. The record stays, and the gap is permanent.

### Three rulings that narrow the lines above

1. **Mid-box delete with contiguous shift exists, bounded.** The rule "Nothing that renumbers may exist" is overruled for one case. That case is deleting a junk capture mid-box. Every higher-index card in that box must still be `captured` or `identified`, with no listing hold. The cards behind it slide forward, as in a contiguous stack. The boundary keeps the old rule's reason alive. A sold or retired gap above the deleted index refuses (`renumber_blocked`). Shifting across it would close a gap that means something. A listed card's row is already in a file that names its position. Photos and sidecars are renamed in the same locked operation. A `renumbered` history event maps every old index to its new one, so the log stays true across the shift.

   The reason weakened with D58. The refusal stands anyway. The box already closes up over a departed card on every screen, so no gap is left for a shift to close. But this route moves the STORED index, which a photograph and an import file are named by. The records it would move across are departures and commitments. Relaxing the refusal needs its own decision, not yet argued. The sentence the screen recites was corrected. A refusal that explains itself with something no one can check teaches an operator to read past it.

2. **Capture-undo narrows to `captured` alone.** Undo at `identified` is no longer allowed. Once a card is identified it is in inventory proper, and the capture screen's undo may not reach it. The remedies are the ones built for it: re-shoot, retire, or the mid-box delete above where its bounds allow.

3. **A whole box may be deleted.** Records, photos, sidecars, queue entries and cache go with it. It is gated as the genuinely destructive action it is (`docs/DESIGN.md`'s clause). It is refused while the box holds any sold, retired or listing-held card. Those records are history and commitments, not clutter.
