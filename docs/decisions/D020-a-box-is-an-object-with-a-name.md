## D20 — A box is an object with a name

**A box is an object in the store (`store/master.py:Box`), so it can be created empty, named and listed.** Capacity and seal are gone (D299). Nothing divides by them (D58).

- **The name is the address.** It is unique, folded and stripped to compare, and stored as typed. `_check_name_free` refuses a duplicate as `BoxNameTaken` (409 `name_taken`). It is unique but not required, because requiring a name would invalidate boxes registered before. It never enters `Position.label`, which the Fulfillment floor holds at 32px. It travels as `box_name`.
- **A rename appends `box_renamed` with both names.** The trail is the safety, not a confirm dialog.
- **The number is assigned, not typed.** `next_box_number` is the lowest free integer, and it reads cards as well as the registry, because a box with cards and no registry entry is real. It is not a high-water mark, unlike the card allocator (D10): a box number names a shelf object that nothing else reads. `Box.bid` is the never-reused identity (D145).
- **An empty box is a box.** The inventory strip unions the registry in when nothing is searched, because an empty box is the only state from which it can be renamed, sectioned or deleted. Under a query, a cell for a box with no match is a dead end and stays out. The claim editor is not offered over zero cards (absent, not disabled).
- **Whole-box delete is two presses that both name the box** (`Delete box 6…`, then `Delete box 6 permanently`). A yes/no is answered by the reflex that pressed it, and a typed gate costs more the more boxes are tidied. If a box is deleted by mistake, graduate the gate by what the box holds.
