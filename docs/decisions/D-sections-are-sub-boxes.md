## D-sections-are-sub-boxes — A picked section fills like a sub-box, and the store chooses the key

**The owner's ruling, 2026-09-26**, verbatim: "if i am in section 1, and i am capturing away,
then section 1 is continuing to expand, if i am selecting section 2, then i am capturing that
fills in section 2, kinda like a subbox".

The owner's answers to the plan's three questions, verbatim:

- On S after a picked section: "Right after section 2 (Recommended)".
- On how long the pick lasts: "Until the sitting ends".
- On Move to box: "i need to specify where it goes there no auto default".

`docs/specs/subbox-capture.md` holds the plan, the wire contract and the measurements.

### The premise that no longer holds

D10 (the inventory model) said the next captured card goes on the end of the stack. That was
the only way a card entered a box at capture. D265 (a card's place is an order key apart from
its index) already let a placement put a card between two others. This entry lets a capture do
the same thing, into the section the owner picks.

### The rule

**The client names a section by its divider key. The store chooses the key of the card.** So
no request carries an index or an order key. `store/master.py:Inventory.section_tail_key` is
the one rule. A capture, an S after a section and a Move-to-box all read it.

- The last section takes `next_key`, which is the rule before this entry. A capture that names
  no section, or the last section, is the same capture as before. A box that nothing was placed
  into stays the identity (every key equals its index).
- An empty section takes its divider's own key. D10's empty-last-section rule does the same.
- Otherwise the card takes `int(lo) + 1` while that is below the next divider. `lo` is the
  highest key of any record in the section.
- Otherwise the card takes `lo + (hi - lo) / 1024`. Below `KEY_EPSILON` the box is re-spaced
  once.

**Whole numbers come first because of a planned divider.** `pipeline/join.py:Position` counts
the unfilled slots before a divider as whole numbers. On a box with dividers `[1, 51]` and five
cards, a capture into section 1 with key 6 keeps section 2 at card 51. With a fractional key,
section 2 starts at card 52.

**The step is 1/1024 and not a half.** A half, which `Inventory.place` uses, reaches
`KEY_EPSILON` after about 20 captures into one gap. Then the whole box is re-spaced, which
writes every card key in it. At the feeder's pace that is about once every 12 seconds. A
1/1024 step gives about 7,000 captures before a re-space.

### What this protects, and what protects it now

A key that is wrong files a card where the hand did not put it, and nothing reports it (D10's
named cost). Three things guard it.

1. `harness/tests/t7_box_map.py:check_capture_into_section` holds one named case for each
   invariant in the spec's section 4, and a fuzz. The fuzz captures, presses S and U and moves
   cards into random sections against a physical model of each box. Each mutation in the
   spec's section 4 turns it red.
2. A key the box does not have is refused with `section_gone` (409), and nothing is written.
3. The Capture screen always shows the picked section (Lane B).

### S after a picked section

S with `after` puts one new divider directly behind the last record of that section. No card
key changes. The later sections move up one number, and their card numbers stay the same.
This is the one number that moves. A section that holds no record refuses with
`section_empty`, as S on the last section does. U after such an S names the divider by its
key (`DELETE /boxes/<box>/sections?div=`). It removes that divider only.

### Move to box

The owner ruled that a move has no default destination. So each Move-to-box route takes
`section`, and the card goes to the tail of that section by the same rule. The screen
enforces "no default" (Lane C). The server still sends a move with no `section` to the back of
the box, so a caller from before this entry keeps working. The spec's section 7 argues this.

A move undo refused when any divider stood behind the transplant. A card moved to the tail of
a middle section always has the next section's divider behind it. So the guard now refuses
only a divider that no record stands behind, because only such a divider can have come after
the move.

### What does not change

A remove, a sale, an unsell and a move undo write what they wrote before. A capture undo still
deletes the newest index, in any section. The Map's drag still names an exact gap.
`Inventory.positions_for_sku` and `Inventory.in_state` sort by the order key now, because a
card captured mid-box has a high index and a middle key.
