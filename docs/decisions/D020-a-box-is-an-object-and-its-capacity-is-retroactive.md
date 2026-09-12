## D20 — A box is an object, and its capacity is retroactive

**A box is a real object in the store with a name, a state and a capacity that is only frozen when it is sealed.** Before this, **there was no box object anywhere in the repo** — `docs/specs/capture-server.md` §5.4: there is no box object anywhere in `store/`, only a flat dict keyed by box and index. A box existed only because a card named one. The consequences were all small and all daily: a box could not be created empty, could not be named, could not be listed on any screen but Capture, and a mistyped number was caught only by the `new_box` flag *after* a photo had been written — which `server/capture_server.py` notes catches the first typo only.

`store/master.py:Box` carries `box`, `name`, `sections` (D10), `state`, `capacity`, `created_at`, `closed_at`. A box is `open` or `closed`.

**Capacity is retroactive, and that is the whole of the lifecycle.** It is not asked for when a box is created, because nobody knows it then. While a box is open it has none, and the honest denominator is the fill so far — a screen saying `#40 of 53` has to also say *so far*, because tomorrow it is 54. **Sealing the box freezes `capacity` at the final high-water mark**, and only then does `#40 of 250` · 16% in become a sentence that is still true next week.

That sentence is the reason the object exists. The owner's ask: a bare position tells you nothing about where to put your thumb; a fraction does, and a fraction needs a denominator that does not move.

**A sealed box takes no more cards.** `allocate_capture` refuses with `BoxClosed` before it computes an index, so a refusal burns nothing. Admitting one more card would make every fraction already drawn from that box wrong by one.

**Sold cards do not shrink a box.** D10 makes their gaps permanent and `next_index` is a high-water mark, so a sealed box's capacity never falls as its contents sell. Re-opening a box sets `capacity` back to unknown rather than leaving a stale number standing.

**Amended by D58: `capacity` is no longer the denominator, and the denominator does shrink.** Every word above stays true of `capacity` itself — frozen at the high-water mark, never falling, cleared on re-open — and what changed is that nothing divides by it. A card's number now counts the cards in the box, so a count over a frozen capacity draws a card at a percentage of a box it is not at: on a 543-card box that has sold 200, `#100 of 543` puts a thumb a third of the way from the card. The denominator is the cards on hand, for a sealed box and an open one alike, and `capacity` records how full the box got.

**The moving-denominator hazard this entry exists to prevent is answered rather than ignored.** What made `#40 of 53` dishonest was a denominator that is DIFFERENT TOMORROW for a reason the operator cannot see; this one changes only when a card leaves the box, which is a thing they did. The `so far` / `sealed` split is untouched and still says which kind of box it is, and a sealed box's identity line carries both numbers (`542 of 543 sealed`) so neither can be mistaken for the other.

**The same argument has a second instance one scale down**, which arrived 2026-08-23 with the section-scale position bar. A section has a denominator problem of exactly this shape: `section_end` is a DECLARED bound taken from the box's dividers, not a count of the cards actually behind it. Box 1's section 3 runs 51..75 and holds three cards, so `card 3 of 25` and `card 3 of 3` are both true and mean opposite things.

The rule, and it turns on which bound is final rather than on the box's lid alone:

- **Settled** — a divider with cards behind it, so the width is a fact. Render the declared width and say **`slots`**: `Section 1 · card 1 of 25 slots`.
- **Growing** — the last section of an open box, the one the next capture lands in, where the end is not a divider but the edge of what exists. Render the fill and say **`so far`**, the same two words this entry already puts on an open box's denominator.

**The caption must name which it is.** A denominator that silently switches meaning between a full section and a half-empty one is precisely the failure this entry exists to prevent, and at section scale it is easier to miss because the number is smaller and the operator is already standing at the right box.

### A box has a name, the name is how it is addressed, and names are therefore unique

Built 2026-08-25. This entry authored `name` as an optional label and nothing checked it, which was right while it was decoration: the number was the identifier, and a second box called `commons` cost nothing worse than a confusing row. The capture screen now finds a box BY name — one free-text field searching number and name together — so a duplicate name is an ambiguous *physical address*. That moves the ambiguity off the key the operator has stopped typing and onto the label they navigate by, which is worse than where it started. `store/master.py:_check_name_free` refuses one as `BoxNameTaken`, which `server/capture_server.py` answers as 409 `name_taken`.

**The name does not reach `Position.label`, and it was built and reverted to settle that.** `app/tests/fulfillment.spec.ts` floors that label at 32px with tabular figures wherever one is drawn, and D31 is explicit that the spec stays unweakened. The name already travels as `box_name` in the place block and is already drawn beside the label on `CardLocations` and `Inventory`, so putting it inside the label bought nothing and spent a hard constraint.

**Folded and stripped to compare, stored verbatim.** `Commons`, `commons` and `commons ` are one box to a person standing at a shelf, so they collide; what is written down is what was typed. It is the same split `pipeline/join.py:number_index_key` draws between a matching form and a stored one, for the same reason — a normalized value written back is a value the operator cannot correct.

**Unique, not required, and that boundary was chosen rather than fallen into.** Requiring a name would invalidate every box registered before today and would break `BoxOps`' own *Name (optional)* create form. Uniqueness is the property that matters once a name is an address; existence is not.

**A rename appends `box_renamed`, carrying both names.** `server/capture_server.py` recorded the absence of this event as a known gap and gave the right reason for leaving it — a name is a label, not a claim the pipeline spends money against — and that sentence stopped being true the moment the name became the address. A rename relabels every card in the box on every screen that draws one, so an unlogged rename leaves no record of what the box used to be called. **This is D10's divider argument at box scale, and it resolves the same way**: D10 chose a `resectioned` event carrying both layouts over restricting the operation, and `box_renamed` carries both names for exactly that reason. The trail is the safety, not a confirm dialog `docs/DESIGN.md` would ban anyway. `ensure_box`'s silent rename routes through `set_name` as well, so a name reached by that path gets the same check and the same line.

**A box number is assigned now, not typed: `next_box_number`, the lowest free integer.** `POST /boxes` takes a name with no number and allocates inside the lock; sending neither refuses `box_or_name_required`. It reads the CARDS as well as the registry, because a box that holds cards and has no registry entry is a real box — `_box_row` renders exactly that case — and handing its number out again would put two boxes' photographs in one directory.

**It is deliberately not a high-water mark, which is the opposite of D10's card allocator, and the two must not be made to match.** `next_index` hands a deleted card's index straight back, because burning it would put a permanent hole in a box over a mis-tapped button. A box number is the other case: it names an object on a shelf, the operator no longer types it, and nothing but the store, the disk and the wire reads it — so the lowest free number is the honest answer and there is no gap for it to close wrongly.

**What this makes stale, named here because the spec is older than the screen**: `docs/specs/capture-app.md` §5.2 said box selection was a list from `GET /status` and that starting a new box is a typed number. Both are overtaken — the field reads `GET /boxes`, and the number is allocated rather than typed — and that section is marked accordingly rather than rewritten, the same way §5.1 was when Pass D landed.

### An empty box is a box, and for one commit it was unreachable

Found and fixed 2026-08-26. `#/inventory`'s box strip was built from the CARD ROWS — `BoxBrowse.tsx:shelvesOf` walked the cards and collected the boxes they named — so a registered box holding no cards produced no row, therefore no shelf, therefore no cell. The strip is the only way to SELECT a shelf, and `BoxIdentity` and `BoxOps` draw for the selected one, so rename, dividers, seal and the whole-box delete were all unreachable for it. Measured on the owner's store the day it was found: **12 of 13 boxes**, including every box they had just created to test with. `Register a box` was a loop — it made a box that immediately vanished.

**It is `CLAUDE.md`'s route-is-not-a-feature rule caught from the far end.** That rule was written for a capability with no control; this is a control, a client function and a tested route, all present and all correct, for a box no screen could be put on. Worth recording as its own shape: the checklist that rule prescribes — route, client function, control on the screen a human would look for it on — was fully satisfied and the feature was still unusable, because nothing in it asks whether the OBJECT the control acts on can be selected.

**And it is a regression with a commit.** `13c397a`, D31's merge, wrote both this strip and retired `#/boxes`, whose entire content was the registry list. The merge carried the cards over and not the registry.

**The registry is unioned in only where nothing is being searched for, and that boundary is the fix rather than a caveat on it.** `shelvesOf` was written so a cell can never lead to an empty list, and that rule is RIGHT about a query: under one, a cell for a box holding no match is a dead end. It was wrong only as a rule about the STORE, where an empty box's empty list is not a dead end but the truth — and it is the only state from which that box can be renamed, sealed or deleted. The walk says so in words rather than rendering a blank column beside a box header.

**The claim editor is not offered over nothing.** `Set claims on all 0 cards in box 6` was a real string on a real screen the moment empty boxes became reachable. It is the one control in `BoxOps` that writes CARDS rather than the box, so it is the only one an empty box can leave with nothing to do. Absent rather than disabled, per `docs/DESIGN.md`.

### The whole-box delete is two presses that both name the box

The owner, 2026-08-26: deleting boxes should require a confirm click, not typing something. D10's ruling 3 gates this operation as the genuinely destructive action it is, and the gate was a typed box number. The argument for typing is worth keeping because it is most of the argument for what replaced it: a yes/no dialog is answered by the same reflex that pressed the button, and this control's whole risk is deleting box 9 while looking at box 95, so a gesture that could not be performed by momentum forced the operator to read which box they were aimed at.

**What it was measured against was eleven empty spam boxes and eleven typed numbers**, in the session that made empty boxes reachable at all. A gate whose cost scales with how many boxes you are tidying up is a gate that gets resented, and a resented gate is read past rather than read.

**So the half that survives is the half that was doing the work: naming the target.** `Delete box 6…` opens the panel and `Delete box 6 permanently` fires it, so the number is printed twice and the second press is on a control that has to be found rather than one sitting under the pointer. What is given up is the momentum guarantee, deliberately and by the owner. **This is still not the *are you sure* `docs/DESIGN.md` bans**: that dialog's confirm says nothing about what it is confirming, and both of these say the box.

**What would reopen it: a box deleted by mistake.** The fix to reach for first is then graduating the gate by what the box HOLDS rather than restoring typing everywhere — an empty box's delete destroys a name and a number, and box 2's destroys 543 photographs. That is one condition on `record.cards`, and it is named here rather than built because the owner asked for the simple thing and no such mistake has happened.
