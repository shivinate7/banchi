# Sub-box capture: a picked section fills like a sub-box

**Status: SPECIFIED. Lane A (store, server, harness, records) is BUILT on
`ux/subbox-store`. Lane B (the Capture screen) and Lane C (the Move-to-box section choice) are
NOT BUILT.** Written 2026-09-26 from the plan the owner ruled on the same day. The decision
entry has the slug `sections-are-sub-boxes`.

## 0. The ask, in the owner's words

```
if i am in section 1, and i am capturing away, then section 1 is continuing to expand, if i am
selecting section 2, then i am capturing that fills in section 2, kinda like a subbox
```

The owner's rulings on the plan's three questions are in section 9.

## 1. Wire contract

Lanes B and C build against this. The client names a section by its **divider key**, a
string. The store chooses the position. No request carries an index or an order key.

A divider key is the string that `store/master.py:divider_key` writes. A whole-number key
reads `"31"`. A fractional key reads as Python's `repr`, such as `"5.0009765625"`. Compare
keys as strings. Never parse one and never compose one.

### 1.1 `GET /boxes`

Each `sections_detail[]` item gets one new field.

| Field | Type | Meaning |
|---|---|---|
| `div` | string | The divider key of this section. Section 1 of a box with no declared dividers has `"1"`, or the lowest card key when a card was placed in front of card 1. |

### 1.2 `POST /capture`

| Field | Where | Type | Meaning |
|---|---|---|---|
| `section` | body, optional | string | The divider key of the section to capture into. Missing or `null`: the capture works as before, at the back of the box. |
| `section_div` | response | string or null | The divider key of the section the card went into, read after the write. It is correct after a re-space. It is null only for a pooled card, which has no section. |

Each refusal writes nothing, uses no index and stores no photograph.

| Status | Code | When |
|---|---|---|
| 409 | `section_gone` | The box has no section with that divider key. Read `GET /boxes` again. |
| 400 | `section_invalid` | `section` is not a string. |

A replay of a `capture_id` that is already recorded answers 200 with the first card. It
ignores `section`.

### 1.3 `POST /boxes/<box>/sections` (S)

The body is `{}` or `{"after": "<div>"}`.

- With no `after`, or with `after` naming the last section, S works as before. The divider
  goes in front of the next card at the back of the box.
- With `after` naming a section that is not the last, the owner's Q1 ruling applies. One new
  divider goes directly behind the last card of that section. It stands in front of the next
  section's divider. No card key changes. The sections after it move up one number. Their
  card numbers stay the same.

The response is the box row, as before. The new section is the one directly after the
`after` section in `sections_detail`. Its `div` is the key to capture into next.

| Status | Code | When |
|---|---|---|
| 409 | `section_empty` | The named section has no card record in it yet (as before, for the last section). |
| 409 | `section_gone` | The box has no section with that divider key. |
| 400 | `section_invalid` | `after` is not a string. |

### 1.4 `DELETE /boxes/<box>/sections?div=<div>` (U after S)

`ux/divider-fix` owns the keyed form of this route and its refusal shape. This lane widens it
only as far as I9 needs: a named empty divider that is not the last. The table below changes
to match `ux/divider-fix` when that branch lands.

- With no `div`, it works as before. It removes the last divider if no card on hand stands
  behind it.
- With `div`, it removes that one divider and no other. It refuses the first divider. It
  refuses a section that holds a card on hand. A departed record in the section does not hold
  it.

| Status | Code | When |
|---|---|---|
| 400 | `sections_invalid` | The first section, or a section with a card on hand (as before). |
| 409 | `section_gone` | The box has no section with that divider key. |

### 1.5 The two Move-to-box routes

`POST /inventory/<box>/<index>/move` (one card) and `POST /inventory/<box>/move` (ticked cards,
or a whole box) take one more field, and it is REQUIRED.

| Field | Type | Meaning |
|---|---|---|
| `section` | string | A divider key of `to_box`. Each moved card goes to the tail of that section, in the order sent. It uses the same key rule as a capture. For the back of the box, send the last section's `div`. |

| Status | Code | When |
|---|---|---|
| 400 | `section_required` | The body has no `section`. Nothing moves. |
| 409 | `section_gone` | `to_box` has no section with that divider key. Nothing moves. |
| 400 | `section_invalid` | `section` is not a string. |

The owner ruled that a move has no default destination: "i need to specify where it goes there
no auto default". So the server refuses a Move to box that names no section. The undo of a
move (`{"undo": true}` on the tombstone) names no section and is not refused.

**The callers checked (2026-09-26).** Only a Move to box from a screen reaches the two routes
above. No other caller starts to fail.

| Caller | Path | Reaches the rule? |
|---|---|---|
| Move to box, one card (`Inventory.tsx`, `server.ts:moveCard`) | `do_move_card` | Yes. Lane C sends `section`. |
| Move to box, ticked cards or a whole box (`BoxOps.tsx`, `server.ts:moveCards`) | `do_move_cards` | Yes. Lane C sends `section`. |
| Move undo (`{"undo": true}`) | `do_move_card`, then `_unmove_one` | No. It returns before the rule. |
| The Map's section move | `do_move_sections`, then `_cross`, then `_move_one` with its own slot | No. It names its gap. |
| The Map's card or range move | `do_move_range`, then `_cross`, then `Inventory.place` | Its own rule, section 1.6. |
| `Inventory.move_card`, `Inventory.move_cards` | the store, not a route | No. The rule is on the route. |
| The CLI, orders, fulfillment | none of them moves a card | No. |
| The demo server (`demoServer.ts`) | no move route | No. |
| `scripts/cid-selftest.py` and the T7 cases | the two routes | They now send `section`. The T7 cases that meant the back of the box send the last section's key (`t7_store_and_seams.back_of`). |

### 1.6 The Map's drag (`POST /boxes/<box>/cards/move`)

The drag names an exact gap: `before_card` or `section_end`, as before. A body with no gap
used to go to the near end of the box. It is refused now, unless the destination box is
empty. An empty box has one place, so a drop there is exact.

| Status | Code | When |
|---|---|---|
| 400 | `section_required` | No `before_card` and no `section_end`, and `to_box` holds a record or a declared divider. Nothing moves. |

**The callers checked (2026-09-26).** No caller sends a body with no gap into a box that
holds cards.

| Caller | What it sends |
|---|---|
| `app/src/BoxShelf.tsx` `dropAt`, card mode | A `c:` gap sends `before_card`. An `e:` gap sends `section_end`. The `end` gap sends neither, and the Map draws it in card mode only for a box with no sections, which is an empty box. |
| `app/tests/boxmap.spec.ts` | Every recorded body carries `before_card` or `section_end`. |
| `app/src/demoServer.ts` | No move route. |
| `harness/tests/t7_box_map.py` | Every call names a gap, except "item 9", a move into an empty box, which stays legal. The fuzz's `range` kind always names a gap. |

## 2. The physical model

- **Where the card goes.** Card 1 is at the far back, and section 1 is the section farthest
  from the owner (D260, a card counts within its section and card 1 is at the far back). A
  card captured into section 2 of 4 goes to the near end of section 2. That is directly behind
  the plastic divider of section 3.
- **What the hands do.** Find the section 3 divider. Tilt it and the cards in front of it
  toward the body. Drop the new card into the gap on the back side of that divider. Sections 3
  and 4 are not touched.
- **The numbers.** Section 2 grows by one. The new card is the highest number in section 2.
  No other card in section 2 changes number. Every card in sections 3 and 4 keeps its section
  number and its card number, because a card number counts within its section (D260). Only
  the box-level count moves. That is D58's `slot` (a number counts cards, not slots). No screen
  shows it as a card number.
- **The stored index.** It is still the high-water mark (D10, positions are never
  renumbered). It is the card's identity, not its place (D265, the order key is apart from the
  index). A card captured mid-box has the highest index and a middle order key.
- **S in the middle.** If S puts a new divider after section 2 (the owner's Q1 ruling), the
  old sections 3 and 4 become 4 and 5. Their card numbers do not change. This is the one
  number that moves. A label that a screen saved before the S shows the old section number.

## 3. The store

`store/master.py` holds each of these. None of them builds a `Card` for the whole box, because
a capture calls them inside the store lock. They read the `idx` and `ord` columns only.

- `Inventory.dividers_of(box)`: the dividers as `layout_of` draws them, through
  `front_of_box`.
- `Inventory.section_ordinal(box, div)`: the section a divider key names, or `SectionGone`.
- `Inventory.section_tail_key(box, div)`: the key rule, and the only one. It returns
  `(key, ordinal, last)`. D-sections-are-sub-boxes states the rule and argues it.
- `Inventory.section_div_of(box, key)`: the divider key of the section a key stands in. The
  capture response reads it after the write.
- `Inventory.allocate_capture(box, section=...)`: it resolves the section before it allocates
  the index. For the last section it passes no key, so `record_capture` keeps today's rule.
- `Inventory.open_section(box, after=...)` and `Inventory.close_section(box, div=...)`: S and U,
  aimed by key.

## 4. Every writer, and the invariant that proves it

`harness/tests/t7_box_map.py:check_capture_into_section` holds the named cases and the fuzz.

| Writer | Change | Invariant |
|---|---|---|
| capture, no section | none | I1. The same keys and dividers as a capture into the last section. An identity box stays the identity. |
| capture into section j | new | I2. The new key is above every key in j and below the next divider. No other key or divider changes. I3. No card number outside j changes, and no earlier card in j changes. |
| capture into an empty middle section | new | I4. The key equals the divider's key. |
| capture under a planned divider | new | I5. With `[1, 51]` on 5 cards, a capture into section 1 takes key 6, and section 2 stays at card 51. |
| stale aim | new | I6. A refusal writes nothing. `next_index` does not change, and no photograph is stored. |
| re-space | reused | I7. Order and section membership stay. `section_div` names the new key. |
| S after section j | new | I8. One divider goes between j's last card and the next divider. No card key changes. Later sections move up one number. Their card numbers stay. |
| U after S, by key | new | I9. Only that divider goes. It refuses the first divider, a section with a card, and a key the box does not have. |
| capture undo | none | I10. It deletes the newest index even when that card is mid-box. The next capture into the emptied section takes the divider's key. |
| remove | none | I11. Indices slide and keys do not. The fuzz holds it. |
| move, range move, section move | Move to box requires `section` | I12. A move with `section` goes to that section's tail, in the order sent. A move with a key the box does not have, or with no section, moves nothing. |
| move undo | the divider guard is narrowed | I13. A move into a middle section can be undone. The next section's divider was already behind it. |
| sell and unsell | none | I14. No key or divider is written. The fuzz holds it. |
| divider editor | none | I15. After a mid-box S, a save with no edits keeps every divider. |

**The fuzz.** Six seeds of 150 writes (seeds 6 to 11). A capture and an S aim at a random
section. A U takes out a random empty section by key. A Move-to-box aims at a random section.
A sale, and a sale undone at once, join the writes. Every other write from the divider proof
stays in the mix. The divider proof's own fuzz (seeds 0 to 5) replays as before.

**Mutations.** Each one below turns `check_capture_into_section` red. Each ran against a
`.bak` copy of the file, which was put back after the run.

| Mutation | Red on |
|---|---|
| The key equals the next divider | I2, I3 |
| The section is ignored on a capture | I2, I3 |
| The section is ignored on a move | I12 |
| Halving with no re-space guard | I5, I7 |
| `int(lo) + 1` without the test against the next divider | I2, I3 |
| The fractional step without whole numbers first | I5 |
| S ignores `after` | I4, I8 |
| U takes out the last divider, not the named one | I9, the fuzz |
| The re-space is skipped | I7, the fuzz |
| The move undo guard refuses every divider behind the transplant | I13 |
| A SKU's copies sort by index | the copy-order case |
| An empty section's first card takes a key between the dividers | I4, I10 |
| `sections_detail[].div` is off by one | I2, I3 |
| A Move to box with no section is not refused | I12 |
| A drag with no gap into a box that holds cards is not refused | the drag refusal case beside item 9 |

One mutation stayed green, and it is not a defect. Resolving the section after the box is
registered leaves I6 true. The write that raises `SectionGone` discards the new box entry
with everything else.

## 5. The screen (Lane B, not built here)

`app/src/CaptureScreen.tsx` gets a Section row under the Box row. It names the picked section,
its count and its name. `[` and `]` pick the section toward the back or the front. The default
is the last section. The pick lasts until the sitting ends (the owner's Q2 ruling). S sends
`after`, and the screen then picks the new section. U after S sends the divider's key. The
server keeps no pick. Each request carries its own aim.

## 6. Ripple effects

- **Runs and identify.** A run binds positions by index, and realign binds by photo digest
  (D36). A capture into the middle renumbers no index, so nothing changes.
- **Queue labels.** Every route re-renders `QueueEntry.label` at read time and never serves
  the stored one (`server/capture_server.py`, D58). So a mid-box S changes no label on a
  screen. The stored label still reaches CLI text lines, as it did after any divider edit.
- **Walk and fulfillment.** `records_in`, `BoxView` and `walkplan` read keys.
  `Inventory.positions_for_sku` and `Inventory.in_state` sorted by index and called that
  box-walk order. They sort by `(box, order key, index)` now.
- **Demo.** `demoServer.ts` refuses `/capture`. Lane B makes its `openSection` refuse
  `after`, and records the fixtures again so that `sections_detail` carries `div`.

## 7. Where the build differs from the plan

- `section_tail_key` returns `(key, ordinal, last)`, not a bare key. The capture needs `last`
  to keep today's rule for the last section. S needs the ordinal after a re-space.
- **The move undo guard is narrowed** (`Inventory.unmove_card`). It refused any divider above
  the transplant's key. A card moved to the tail of a middle section always has one. So the
  undo of every such move refused. It now refuses only a divider that no record stands behind.
  Only such a divider can have come after the move. What an undo writes does not change.
- **The server refuses a Move to box with no `section`** (400 `section_required`). The plan
  kept the back-of-box answer. The coordinator ruled on 2026-09-26 to refuse, because it is
  the owner's own "no auto default". A caller that forgets the field now fails loudly. It
  cannot file a card at the back of a box without a word. Section 1.5 lists every caller
  checked.

## 8. Measurements

Measured 2026-09-26 on a `.backup` copy of the owner's store, never the live one.

- **M1.** Five boxes hold cards: 1, 2, 3, 4 and 6. Every box is the identity (each key equals
  its index). Every middle section ends one whole number below the next divider. So each
  middle section takes 7,046 captures before a re-space. With halving, it takes about 20.
- **M2.** Boxes 4 and 6 end with an empty section. No other box does.
- **M3.** `_respace` on box 3, the largest box (987 records): 78 ms median of 3 runs, rolled
  back.
- **M4.** `do_capture` on box 3, median of 7 runs: 152 ms with no section. Into section 4 of
  9 it takes 150 ms. `section_tail_key` alone takes 8 ms. The feeder's cadence is 623 ms.
- **M5.** 702 review and parked entries hold a stored label. No route serves one (section 6).
- **M6.** 543 (SKU, box) pairs hold two or more copies on hand. None of them lists in a
  different order by index than by key today. Every box is still the identity. So the sort
  change moves nothing on the live store until a card goes into the middle of a box.

## 9. The owner's rulings, 2026-09-26

- **Q1, S after a picked middle section:** "Right after section 2 (Recommended)". The new
  divider goes right after it. Later sections move up one number, and their card numbers stay.
- **Q2, how long the pick lasts:** "Until the sitting ends". The pick is kept per box on the
  device until the sitting ends (D164, a 30-minute break). Then it goes back to the last
  section. The server keeps no pick.
- **Q3, Move to box:** "i need to specify where it goes there no auto default". A Move to box
  with no drop spot has no default. The owner chooses the section in the target box, and the
  card goes to the end of that section. A Map drag stays exact. This adds Lane C.

## 10. Lanes

| Lane | Owns | State |
|---|---|---|
| A | `store/master.py`, `server/capture_server.py`, `harness/tests/t7_box_map.py`, the decision entry and the amendments to D10, D265, capture-app.md 5.6 and undo.md 11.1 | BUILT |
| B | `CaptureScreen.tsx`, `deviceMemory.ts`, `server.ts`, `types.ts`, `App.tsx` `CAPTURE_KEYS`, `demoServer.ts`, the capture specs | NOT BUILT |
| C | The Move-to-box section choice on `#/inventory` | NOT BUILT |
