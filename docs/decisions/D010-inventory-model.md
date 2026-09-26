## D10 — Inventory model

**A card gets a sequential position at capture, and positions are never renumbered.** Location is Box N, Section N, Card N. Sold cards leave permanent gaps.

### Sections are per-box and declared at capture time

Amended 2026-08-23 by the owner. `CARDS_PER_SECTION = 25` was a bare module literal no env var, flag or parameter could reach, and real boxes have dividers where the operator physically put them. A box now carries its own list of divider indices — `[1, 31, 56]` means section 2 starts at card 31 — set at the moment the real divider goes in.

**An empty list means undeclared, an undeclared box is one section, and there is no automatic divider** (amended 2026-08-29, the owner: delete automatic sectioning). This paragraph read that an empty list means undeclared and the 25-rule renders it, defended as keeping every label written before boxes existed byte-identical. That was true and it was the wrong trade. The 25-rule cut a divider into every undeclared box every twenty-five cards whether or not one was in the plastic, and byte-identical labels are worth nothing when what they are identical to is a boundary nobody put there.

**The measurement is the owner's own store.** Box 1 holds 133 cards and declares no layout, so it rendered as six sections and a person sent to `Section 4 · Card 8` would have been counting for a divider that does not exist. Box 2 declares `[1, 86, 171, 253, 394]` and is untouched, as is every other declared box: the change reaches exactly the boxes that never claimed to have dividers.

**What replaces the constant is `(1,)` — the one divider every box really has, at its front.** `pipeline/join.py:Position.layout` states the fallback once and `section`, `section_start` and `section_end` all read it, where the constant had three branches doing their own arithmetic. So `card` is the index, `section` is 1, and `section_end` is None, which is D20's existing answer for a final section rather than a new rule — the caller holding the box's capacity fills it in. `Position` is still the only label formula in the repo, and the v1 to v2 migration still writes an empty layout for every box it finds; only what an empty layout RENDERS AS has moved.

**The labels of every undeclared box moved once, deliberately, and that is the cost.** It is the same risk `harness/tests/t7_store_and_seams.py` names for the migration — every position label in a real inventory shifting at once, with the only symptom a person opening the wrong slot weeks later — realized on purpose instead of by accident. It is affordable because a label was never printed on anything, only ever read live off a screen. T7 pins the new strings so that the next such shift is not accidental either.

### The `New section` control is `S` on the capture screen

Built 2026-08-29. The owner asked for sectioning they could create from the capture screen itself, the way `C` is capture, with the set hint remapped to `H`. Until then the sentence above was aspirational — the only way to declare a divider was `PUT /boxes/<box>` with a whole layout, typed into a field on `#/inventory`, which is a different operation wearing the same words: performed later, from another screen, and needing the operator to remember which card they were on when the divider went in.

**The two halves of that instruction are one design.** Deleting the automatic divider is what makes the key worth having — a screen that invents a boundary every 25 cards does not need a control for putting one in — and the key is what makes deleting it safe.

- **`POST /boxes/<box>/sections` takes NO INDEX.** `store/master.py:open_section` reads `next_index` inside the store lock, so the divider lands in front of the card the next capture will actually take. A client computing it would read a high-water mark across a round trip and send it back — the lost update `next_index`'s own docstring exists to prevent, and at the feeder's measured 623 ms cadence rather than a theoretical one.
- **It is `next_index` and not count+1**, which matters exactly where D10 already matters: a box with permanent gaps in it. A count would put the divider in front of a card that will never be captured.
- **An undeclared box materializes `[1, at]`, not `[at]`.** `check_sections` requires a layout to start at index 1 and is right to — there is no card before the front of a box. Nothing is invented by that: section 1 already started at card 1, and this is the first time anything needed to write it down.
- **It logs `resectioned` through `set_sections`**, the event the dividers editor already writes, carrying both layouts. A new event name was considered and rejected on D26's evidence: this store has already been bitten by a state and a history event sharing a word.
- **One refusal, in its own code**: `section_empty` (pressed twice with nothing captured between — the divider you want is already there, and an empty box takes this too, since card 1 is where the first section starts). A second, `section_ahead` (a divider already declared past the next card), went on 2026-09-25 with the empty-section rule below: the next card now goes behind such a divider, so that section is empty and `section_empty` answers it. A third, `box_closed` (a sealed box took no divider), went with the seal on 2026-09-25 (D-sealed-boxes-removed).
- **No confirm and no undo, and neither is an oversight.** Nothing is spent and nothing is destroyed; the remedy for a mis-press is the dividers editor, which is where a wrong layout is corrected anyway, and `resectioned` carries the layout it moved from. A dialog on the screen the owner shoots a box from at feeder pace is what `docs/DESIGN.md` refuses in as many words.

**The set hint is `H` now, and the swap cost nothing else.** `S` was on a field an operator opens a few times a run and was wanted for an act performed at the box. The option alphabet (`docs/DESIGN.md`) is every key this screen has not spent, so it lost `s` and gained `h` — and because `h` sorts after `e`, the first thirteen option keys are `1234567890ade` before and after, which is why `app/tests/capture-claims.spec.ts` pins them and stayed green.

### The next card goes into an empty last section

**The owner's ruling, 2026-09-25, verbatim: "Into the empty section (Recommended)".** When a
box ends with an empty section (the owner pressed S, and no card is behind it yet), the next
captured or moved-in card goes INTO that section, behind the divider.

`store/master.py:Inventory._behind_empty_section` holds it. `next_key` and `_birth_key` read
it, and every capture and every move-in takes its key from one of the two. So one rule covers
every write the divider proof named. Before this, a write that lowered the box's highest key
(a capture undo, a Manage box remove, a move that takes the last card forward, a section
reorder, a section-move undo or a move undo) left the divider above the next card's key. The next card then went into the section
in front of it (the proof's F1).

**The effect on a hand-typed divider past the last card.** The dividers editor takes `[1, 51]`
on a five-card box. That is the same layout, so the next capture now goes into section 2, at
the divider's key. `S` then refuses with `section_empty`, and `SectionAhead` is deleted,
because no layout can reach it now. Whether any real box holds such a divider is unmeasured.
The divider proof found two boxes (4 and 6) that end with an empty section now.

`harness/tests/t7_box_map.py:check_divider_anchor` guards it (D265, the divider anchor).

### The rule governs the INDEX; the label is a view

These were the same sentence while sections were a global constant and they are not any more. **The index is the identity**: assigned once, surviving a sale as a permanent gap, and nothing renumbers it — unchanged and absolute. Section and Card are a *rendering* of that index against the box's current divider layout, so moving a divider relabels every card behind it without touching a single index.

**Boundaries are freely editable from any screen, and labels always recompute** — the owner's ruling, chosen over freezing a section once a card sits in it. The argument for it: correcting a wrong layout is the whole point, a label was never printed on anything, and the alternative leaves the model permanently unable to describe a box you physically re-divided.

The cost is recorded here rather than designed away, because it is real: **a mis-tap relabels a filled box and nothing flags it**, and the Fulfiller walks to the wrong slot with no error to see. Mitigated by a `resectioned` history event carrying both layouts — not by restricting the operation, which was the other option and which the owner declined. If that failure ever actually happens, the fix to reach for first is a confirm on an edit that moves a divider with cards behind it, not a return to freezing.

### Undo deletes the record; it does not tombstone it

Settled 2026-08-12, before step 7 built it. A tombstone would be a third thing the store has to explain — not captured, not sold, still occupying a position — and every reader would have to learn it. A deleted record is a card that was never captured, which is exactly what the operator means by undo.

**This decides index reuse, which is otherwise the allocator's most surprising behavior.** `next_index` is a high-water mark, `1 + max(index in this box)`, so deleting the newest record hands its index straight back to the next capture. That is the correct outcome and not an accident of the implementation: the position was assigned to a photo that no longer exists, and burning it would put a permanent hole in a box over a mis-tapped button.

**The box-number allocator is a different rule and is not this one** (D20, amended 2026-08-25). `store/master.py:next_box_number` hands out the lowest free integer rather than a high-water mark, because a box number names an object on a shelf and nothing about it is a position a card was assigned to. Cross-referenced here so the paragraph above is not read as a rule about every allocator in the store: this one governs the INDEX inside a box, and that is the only thing it governs.

**Undo is the newest capture in a box, never an arbitrary one.** Deleting a record from the middle leaves a gap the high-water mark cannot reuse — indistinguishable, later, from the permanent gap a sale leaves, and the rule above says those mean different things. Restrict the operation rather than teach the allocator to fill holes: D10's first paragraph is what makes a printed position label worth trusting, and nothing that renumbers may exist.

**The capture screen shows ten of them as of 2026-08-29, and the rule above is why a row is not a delete.** The owner asked for `U` to undo the most recent capture but for the control to be a growing queue — the ten most recent captures, clickable from the sidebar. The control was one card and one button; it is now the session's ten most recent captures into the current box, newest first, every row its own control.

**Pressing row N undoes N cards** — that row and everything captured after it. It is the same route N times, newest first, which is the only thing the sentence above permits: card N-1 is not the newest until card N is gone. A per-row delete of a middle card would be ruling 1's mid-box remove, which slides every higher card down one index — and putting that on this list would renumber the very rows it was pressed from, which is the defect D37 refuses for the review screen's worklist in as many words. That operation exists and stays on `#/inventory`.

**The count is drawn on the row, and that is the whole of the guard.** `docs/DESIGN.md` makes capture-undo the one place a destructive act gets no dialog, on the argument that the deleted photo is of a card still within reach of the hand that fed it — an argument that is about ONE card. A press that deletes five needs the five to be visible before it, not a confirmation after it, so the row carries the number of cards it removes. It is also the row's ordinal, which is what lets one chip say both. The top row carries `U` instead, because that is the key that fires it.

**A walk that is refused partway stops there and says how far it got.** The next delete is only legal because the one before it succeeded, so carrying on would aim at a card that is no longer the newest. The count is the only thing left that says where the operator is: the cards that went and the cards that did not have both left the list either way.

**The stack is this session's captures, and where the server is ahead it collapses to one row.** A capture that committed and lost its response, or a capture the other device made into the same box (D13 permits both), leaves the store holding cards this session never took — no label, no photograph, no count for them. Offering to undo *back to* a row underneath them would be offering to delete somebody else's captures sight unseen, from a list that cannot draw them. So the depth is exactly one until the two agree again, which one ordinary undo restores.

A sale is the opposite case and is unchanged. `sold` is a state, the record stays, and the gap is permanent.

### Three owner rulings, 2026-08-23, each narrowing a line above

1. **Mid-box delete WITH contiguous shift exists now, bounded.** *Nothing that renumbers may exist* is overruled for exactly one case: deleting a junk capture mid-box when **every higher-index card in that box is still `captured` or `identified`, with no listing hold** — the physical truth of pulling a card out of a contiguous stack, where the cards behind it really do slide forward. The boundary is what keeps the old rule's reason alive: a sold or retired gap above the deleted index refuses (`renumber_blocked`), because shifting across it would close a gap that means something, and a listed card's row is already in a file that names its position. Photos and sidecars are renamed inside the same locked operation; a `renumbered` history event maps every old index to its new one, so the log stays true across the shift.

   **That reason weakened with D58 and the refusal stands anyway.** The box already closes up over a departed card on every screen, so there is no gap left for a shift to close — but this route moves the STORED index, which a photograph and an import file are named by, and the records it would move across are departures and commitments. Relaxing it is its own decision and has not been argued. What was corrected is the sentence the screen recites, because a refusal explaining itself with something nobody can check any more teaches an operator to read past it.
2. **Capture-undo narrows to `captured` alone.** *Undo at `identified` is ALLOWED — only the identification fee is lost* is reversed: once a card has been identified it has made it into inventory proper, and the capture screen's undo may not reach it. The remedies for an identified card are the ones built for it — re-shoot, retire, or the mid-box delete above where its bounds allow.
3. **A whole box may be deleted** — records, photos, sidecars, queue entries, cache — gated as the genuinely destructive action it is (`docs/DESIGN.md`'s clause), and refused while the box holds any sold, retired, or listing-held card: those records are history and commitments, not clutter.
