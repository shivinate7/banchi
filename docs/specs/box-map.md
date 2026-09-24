# Box map: sections as objects you can see and move

**Status: SPECIFIED, NOT BUILT.** Written 2026-09-23 from the owner's rulings in the UX review
interview and from the box map deliberation of the same day. The decisions it builds on are the
entries with slugs `a-section-is-an-object`, `card-order-key` and
`a-moved-card-keeps-its-price`. The UX plan it sits beside is
`docs/specs/ux-overhaul-2026-09-23.md`.

## 1. The ask, in the owner's words

The first wish:

```
really wish there was an interactive / visual way of seeing my boxes and literally dragging
and dropping sections from one box to another and all the cards are able to seamlessly move
with no difficulties
```

The owner's picture of it:

```
sections being literally like modular building blocks where if i select move sections, i then
select which box i want to move this section into, and after selecting i get a side by side 2d
birds view and i literally can drag and drop the section before or after section i want of the
other box
```

What happens to the divider:

```
the section is deleted from the previous box, think of sections as their own mini objects
```

And how the cards stand in a box:

```
if i have my cards standing up in a vertical row, the one closest to my body is the last card,
and the one all the way in the back is the first card
```

So four things are fixed. Sections are "modular building blocks". The move shows the two boxes
in a "side by side 2d birds view". A section drops "before or after" any section of the other
box. The owner asks to "think of sections as their own mini objects".

## 2. What v1 holds

The owner ruled the scope.

| Capability | In v1? |
|---|---|
| See every box and its sections | Yes |
| Move a section to another box, before or after any of its sections | Yes |
| Reorder the sections within one box | Yes |
| Merge a whole box into another | Yes |
| Split a box into a new box | Yes |
| Move single cards or a range of cards | Right after v1. In v1 only if it is easy on top. |
| Money on the map | No. Counts only. |

Two more answers are the orchestrator's defaults, because the owner had no preference or was
not asked. A drop saves at once, with a receipt and Undo on `U`. Undo restores the move exactly
while neither box has changed since. After that, the way back is a new move.

## 3. What exists today

The box map deliberation read the code on 2026-09-23. The write half mostly exists. Five things
do not.

### 3.1 The primitives

| Primitive | Route or function | What it does |
|---|---|---|
| Move one card | `POST /inventory/<box>/<index>/move`, `Inventory.move_card` | The old position becomes a `moved` tombstone. The card is recorded again at the destination's `next_index`, the back. |
| Move many cards | `POST /inventory/<box>/move` | One `Store.write()` for the list. `indices: null` moves every card on hand, which is a merge. |
| The screen control | `BoxOps.tsx`, "Move to box" | A whole box, or the ticked cards. A native select of destinations. |
| Put a divider in | `POST /boxes/<box>/sections` | A divider at `next_index`. |
| Declare dividers and names | `PUT /boxes/<box>` | Names keep only when the divider count stays the same. |
| Create and delete a box | `POST /boxes`, `DELETE /boxes/<box>` | A new box gets the lowest free number and a `bid` that is never reused (D145, the box index nobody sees). |
| The box row | `GET /boxes` | `on_hand`, `sold`, `moved`, `listed`, `sections_detail` and `bid`. No value. |
| Claims being paid for | `Submissions.overlap` in `store/submissions.py` | Exists. The move does not call it. |

### 3.2 What is missing

1. **The divider and the name do not travel.** A moved section joins the destination's last
   section. The source keeps a divider in front of nothing. The comment on `Box` in
   `store/master.py` says a move carries the name. No code does.
2. **Cards land only at the back.** No front, no place between sections, no reorder in one box.
3. **Nothing draws a box as a box.** `docs/specs/box-drawings.md` parked a plan drawing (J3)
   for this.
4. **No real undo.** Moving back lands at the back of the old box. `docs/specs/undo.md` section
   4 excludes a move from the slow path.
5. **No physical instruction.** The receipt says only "Moved N cards from box A to box B".

### 3.3 Two hazards in today's move

- **A move can lose a paid answer.** A card with a live paid reading can move. The batch then
  writes onto the tombstone, and the moved card stays unidentified. Read in code, not run.
- **A moved card falls off its run.** `realign` looks only in the run's own boxes. D165 (a run binds to the box's true index) records
  99 cards that lost their pricing surface this way.

Both close in slice 0, before any screen change.

## 4. The ordering key

The owner ruled placement before or after any section. The order key below is the
orchestrator's inference and design, not the owner's ruling. The owner has not seen it.

The inference: placement needs an order that is not the stored index. D10 (the inventory model)
and D58 (a card's number counts the cards) keep the stored index fixed for good reasons. Queue
entries, the cache, listing holds and every write's aim use it.

The proposed design: each card gets an order key beside its index. The walk, the labels and the
section bounds read the key. A placement changes keys only. The entry with slug
`card-order-key` records the proposal and lists what is open: the form of the key, how dividers
are stored, and the migration. The first key for every card is its index, so the migration
changes no label.

## 5. The screen

### 5.1 Where it lives

A "Shelf" view inside `#/inventory`, beside the box walk, at `#/inventory?view=shelf`. That
keeps D31 (one owner-side view of stored cards) and adds no nav row.

### 5.2 The overview

Every box is drawn from above, as the owner sees it on the desk. **The far back of a box, card
1, is at the top. The end nearest the owner, the highest number, is at the bottom.** The boxes
stand side by side.

- **The box head:** its name, cards on hand, a lock when sealed. No box number shows (slug
  `a-box-is-shown-by-its-name`). A press opens the walk at
  that box.
- **One block per section.** Its height follows its count, with a floor of 44px so a small
  section is still a target. It carries the section name (or "Section 2") and its count. Cards
  are drawn as a pattern in CSS, never one element per card.
- **Departed cards are not holes** (D58, a card's number counts the cards). Sold and moved counts go in the box head.
- **Badges, only when true:** "Being read" when a card in the section has a live paid reading.
  "3 owed" when open orders want copies from it.
- **An empty section** (a divider with no card) is a thin dashed block, because the plastic is
  still in the box.
- **A sealed box** is drawn, and it is not a target (D20, a box is an object).
- **A last column, "New box",** is a target that splits a section into a new box. A new box
  with no name gets its stored default name, "Box" and the count plus one.

The box map deliberation estimated about 7 boxes and 40 sections on the owner's store. It
counted more than 700 cards, and one box of 543 cards in 5 or more sections. This spec did not
measure it. At that size the map needs no canvas.

### 5.3 The move

The owner's order of acts:

1. Press "Move sections".
2. Pick the section.
3. Pick the box it goes to.
4. The two boxes stand side by side. Drag the section to a gap before or after any section of
   the destination. The gap under the pointer opens, and it shows the numbers the cards will
   have.

A drop in the same box reorders its sections. A drop on "New box" splits. A merge moves every
section of one box, in order, to the far end or the near end of another.

**While dragging:** the section lifts with an accent tint. Its old place shows a dashed outline.
A sealed box dims and says "Sealed". A section with a live paid reading cannot lift. The cursor
is `not-allowed` (D50, interactive feedback is the product's), and the block says why.

**Touch and small widths.** At 390 and 720, the primary path is tap to pick and tap to place.
Tap a section to lift it. A bar says "Uncommons, 10 cards. Tap a gap to put them there.
Cancel." Tap a gap to commit. A long-press drag is a second path, never the only one. A drag
over a scrolling list fights the page scroll on a phone. Two taps do not.

**Keyboard.** The map is a grid. Arrows move between sections. Space lifts the focused
section. Arrows choose the gap. An `aria-live` line says where it will land. Enter drops, and
Esc cancels. Each section also has a "Move to" menu, the path for every input. Every new binding
goes into `SHORTCUTS` in `app/src/keys.ts`.

**The build.** Pointer Events, written in this repo. No drag library. Native HTML drag and drop
does not fire on touch.

### 5.4 The receipt is the physical instruction

The move saves at once. A receipt opens under the map. It is the checklist the hand follows,
in the owner's orientation. Example, for a section moved from RB Origins into the middle of Mixed Singles:

> **Move 10 cards from RB Origins to Mixed Singles.**
> 1. In RB Origins, find the divider **Uncommons**. Its first card is **Hextech Anomaly**. Its last
>    card is **Sacred Shears**.
> 2. Take out that divider and the 10 cards on your side of it, up to the next divider.
> 3. In Mixed Singles, find the divider **Rares**. Put the Uncommons divider and its 10 cards
>    just on the far side of it, in the same order, card 1 farthest from you.
>
> In RB Origins, Signatures moves from Section 3 to Section 2. In Mixed Singles, Rares moves
> from Section 2 to Section 3. **Undo** (U)

The rules for the receipt:

- **The orientation is the owner's.** Card 1 is at the far back. A section's cards stand on the
  near side of its divider. "Behind" and "in front of" are never used alone. The receipt says
  "on your side" or "on the far side".
- **The deliberation's example text is wrong on this point.** It said "go to the back" for the
  store's append, and the store's back is the end nearest the owner.
- **Landmarks are card names.** A card with no name is not a landmark (D116, an unnamed card is not a landmark). Then the receipt
  counts cards.
- **The renumber line.** A card's number counts within its section. So a section move changes
  no card number. It can change section numbers, and the receipt says which ones.
- **Cards owed to open orders** add a line: "3 of these are owed to open orders. The pull list
  now says Mixed Singles."
- **A move into the box on the Capture screen** adds a line: the next capture joins the moved
  section when it is last. Press S first to start a new section.
- **The receipt stays** until the owner closes it or the next move replaces it. Its "Done" press
  writes nothing.

### 5.5 Undo

Undo, on `U` or its button, reverses the whole move exactly. The tombstones come back at their
old indices. The moved records go. The dividers, the names and the order keys go back. It is
allowed only while nothing else has written to either box since the move. The check reads
events, not a clock. `docs/specs/undo.md` section 2 says neither undo mechanism is a clock. After
another write, the way back is a new move. This adds a move to the fast path in
`docs/specs/undo.md` section 3. Section 4 still keeps a move out of the slow path.

## 6. A drop that crosses something in flight

| Case | v1 behavior |
|---|---|
| A card in the section has a live paid reading | Refuse before the drag starts, and again at the write. It names the reading. |
| The section's cards belong to a run that is matched and not yet sent | Allow. The join follows the card (slug `a-moved-card-keeps-its-price`). |
| Cards owed to open orders | Allow. Orders claim no copy (D212, no order claims a copy). The receipt says so. |
| A stale walk or Cards to pull presses sold on a moved card | The server answers `card_moved`. The screen says where the card went, from the tombstone's `moved_to`, and refreshes. |
| The destination is sealed | Not a target. |
| Another device changed the section since the map loaded | The write carries an aim: the count and the first and last card names. A mismatch refuses, and the map reloads. |

## 7. Slices, in build order

Each slice ships alone and is useful alone.

0. **Safety (S).** The move refuses a card with a live paid reading (`Submissions.overlap`). The
   join follows a tombstone's `moved_to`, checked by `cid`. This protects today's "Move to box"
   with no new screen. Ship it first, whatever else changes.
1. **The read-only Shelf view (M, front end only).** `GET /boxes` already carries
   `sections_detail`, `on_hand` and `state`. It answers "a visual way of seeing my boxes" with
   no write risk.
2. **The order key (M, store only).** The key, its migration, and `Position` reading it. No
   visible change. Its harness cases prove that no label moves.
3. **The section move, without drag (M).** One store write moves a section as an object. The
   source divider goes. A divider with the name opens at the destination. The cards move. One
   group event records the move. A plan read gives the receipt from the same function.
   Placement before or after any section. Reorder, merge and split use the same write. Each
   section gets a "Move to" menu. The feature is complete for every input here.
4. **Drag, tap to place, the keyboard grid and undo (M).** The feel the owner asked for, on a
   write that is already proven.
5. **Single cards and ranges.** They come right after v1. If slice 3 makes them easy, they
   join v1.

The deliberation sized slices 0, 1, 3 and 4 at 2,500 to 3,000 lines with tests. That figure
does not include the order key. It is three lanes: store and server, front end, tests. The front-end lane is the
largest, and a reviewer must see it.

### 7.1 Harness cases (T7)

- A section lands at the chosen gap, in order, with its divider and name.
- The source loses the divider, and the other names stay.
- Moving section 1 works.
- A sealed destination refuses.
- A card with a live claim refuses.
- A stale aim refuses.
- An injected failure writes nothing.
- Undo restores the exact state, and refuses after a later write.
- `realign` follows `moved_to`, and refuses on a `cid` mismatch.
- Queue and cache entries follow the move.

### 7.2 Browser checks

A spec over a seeded store at 1440, 720 and 390, in both themes. It drags, taps and uses the
keyboard. It checks the sealed target, the receipt text and the orientation. It holds the D50 (interactive feedback is the product's),
D117 (the thumb floor), D118 (a press moves nothing around it) and D195 (same-role buttons share
a width) floors.

## 8. What is still open

1. **The two defaults.** Save at once, and undo only while neither box changed. Show the owner.
2. **The form of the order key,** and how dividers are stored (slug `card-order-key`).
3. **The side-by-side view at 390.** Two columns of about 170px may hold section names. Draw it
   and show the owner before the build.
4. **Single cards and ranges in v1.** Decide after slice 3 shows the cost.
5. **The Graveyard after a move.** Today a 40-card move adds 40 rows. One row per move may read
   better. Not asked.

## 9. Found in passing

- The comment on `Box` in `store/master.py` says a move carries a section's name. No code does.
  Fix the comment when slice 3 makes it true.
- The Manage box sheet's eyebrow draws two separators in a row. An element carries both
  `.bn-eyebrow` and `.bn-facts` in `app/src/kit.css`, and each draws one. Two sites:
  `BoxOps.tsx` and `BoxBrowse.tsx`.
- D83 (a moved card) says a box emptied by a merge cannot be reclaimed. The deliberation reads
  D134 (a departed record is buried, not kept) as making that sentence stale, so that a
  merged-out box can be deleted now. That reading is proposed, and it awaits the owner's word.
