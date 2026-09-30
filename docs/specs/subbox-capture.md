# Sub-box capture: a picked section fills like a sub-box

**Status: BUILT.** D300 (a picked section fills like a sub-box) records the ruling. The
server, the capture screen and the Move-to-box section choice are all built.

## 0. The ask

A capture into section 2 fills section 2, the way a sub-box fills. Section 1 keeps growing
while the owner captures into it. The owner's rulings are in section 9.

## 1. Wire contract

The client names a section by its **divider key**, a string. The store chooses the position.
No request carries an index or an order key.

A divider key is the string that `store/master.py:divider_key` writes. A whole-number key
reads `"31"`. A fractional key reads as Python's `repr`, such as `"5.0009765625"`. Compare
keys as strings. Never parse one and never compose one.

**Every aim carries the box's layout token.** A re-space gives every divider a new key. An
old key can then equal the new key of another section, so a key alone can name the wrong
section with no error. The token is a short hash of the box's divider keys, in order.
`GET /boxes` serves it. A request that names a section sends the token it read beside the
key. The server compares it with the box's token under the store lock. A different token is
409 `section_gone`, and nothing is written. The client then reads `GET /boxes` again and
aims again.

**The token is airtight for this reason.** Two equal tokens mean two equal divider lists. In
an equal list, every key names the same ordinal and the same key interval. A re-space keeps
each card in its section, so an equal interval holds the same cards. So a key that passes the
token check names the section the screen drew. A re-space exists to give the keys new values,
so keys cannot stay the same through one.

### 1.1 `GET /boxes`

The box row has one field for this, and each `sections_detail[]` item has one.

| Field | Where | Type | Meaning |
|---|---|---|---|
| `layout_token` | box row | string | The box's layout token. Send it with every aim at this box. |
| `div` | `sections_detail[]` | string | The divider key of this section. Section 1 of a box with no declared dividers has `"1"`, or the lowest card key when a card was placed in front of card 1. |

### 1.2 `POST /capture`

| Field | Where | Type | Meaning |
|---|---|---|---|
| `section` | body, optional | string | The divider key of the section to capture into. Missing or `null`: the capture goes at the back of the box. |
| `layout_token` | body, required with `section` | string | The box's token from `GET /boxes`. |
| `section_div` | response | string or null | The divider key of the section the card went into, read after the write. It is correct after a re-space. It is null only for a pooled card, which has no section. |
| `layout_token` | response | string or null | The box's token after the write. It changes when this capture caused a re-space. Null for a pooled card. |

Each refusal writes nothing, uses no index and stores no photograph.

| Status | Code | When |
|---|---|---|
| 409 | `section_gone` | The token is not the box's token now, or the box has no section with that divider key. Read `GET /boxes` again. |
| 400 | `section_invalid` | `section` is not a string. |
| 400 | `layout_token_required` | `section` is sent without `layout_token`. |

A replay of a `capture_id` that is already recorded answers 200 with the first card. It
ignores `section`.

### 1.3 `POST /boxes/<box>/sections` (S)

The body is `{}` or `{"after": "<div>", "layout_token": "<token>"}`.

- With no `after`, or with `after` naming the last section, the divider goes in front of the
  next card at the back of the box.
- With `after` naming a section that is not the last, one new divider goes directly behind the
  last card of that section. It stands in front of the next section's divider. No card key
  changes. The sections after it move up one number. Their card numbers stay the same.

The response is the box row. The new section is the one directly after the `after` section in
`sections_detail`. Its `div` is the key to capture into next.

| Status | Code | When |
|---|---|---|
| 409 | `section_empty` | The named section has no card record in it yet. |
| 409 | `section_gone` | The token is not the box's token now, or the box has no section with that divider key. |
| 400 | `section_invalid` | `after` is not a string. |
| 400 | `layout_token_required` | `after` is sent without `layout_token`. |

### 1.4 `DELETE /boxes/<box>/sections?div=<div>` (U after S)

`div` is required. The route removes that one divider and moves no other.

**U takes no layout token.** Its `div` is safe after a re-space for another reason. U goes
only when the box's newest `resectioned` line added `div` and wrote the layout as it stands
now. A re-space rewrites the layout and writes no `resectioned` line, so after one the proof
fails and U refuses. A named case proves it (section 4).

- **The last divider** goes while no card on hand stands behind it.
- **A middle divider** goes only when the box's newest `resectioned` line is the S that added
  it. No card on hand may stand in its section. A divider that an editor save put another one
  behind is not S's own any more, and it stays (the stale U).
- The first divider, a key the box does not have, and every other case refuse.
- **The undo writes the layout from before S.** S on a box with no declared dividers wrote
  `[1, at]` from `[]`, so U writes `[]` back, not `[1]`.

`store/master.py:layout_before_s` is the one reader of the `resectioned` line for both
rules. The route passes it the box's newest line. It answers the layout from before S. It
answers nothing when the line does not prove that S added `div`.

A departed record in the section does not hold the divider in.

| Status | Code | When |
|---|---|---|
| 400 | `div_required` | `div` is missing or is not a number. |
| 404 | `box_not_found` | The box does not exist. |
| 409 | `divider_built_on` | `div` is not S's own to undo, as above, or a card on hand stands behind it. Nothing is written. |
| 503 | `history_unreadable` | The box's log cannot be read. |

### 1.5 The two Move-to-box routes

`POST /inventory/<box>/<index>/move` (one card) and `POST /inventory/<box>/move` (ticked cards,
or a whole box) take two more fields, and both are REQUIRED.

| Field | Type | Meaning |
|---|---|---|
| `section` | string | A divider key of `to_box`. Each moved card goes to the tail of that section, in the order sent. It uses the same key rule as a capture. For the back of the box, send the last section's `div`. |
| `layout_token` | string | `to_box`'s token from `GET /boxes`. |

| Status | Code | When |
|---|---|---|
| 400 | `section_required` | The body has no `section`. Nothing moves. |
| 400 | `layout_token_required` | The body has `section` and no `layout_token`. Nothing moves. |
| 409 | `section_gone` | The token is not `to_box`'s token now, or `to_box` has no section with that divider key. Nothing moves. |
| 400 | `section_invalid` | `section` is not a string. |

A move has no default destination: the owner chooses the section. So the server refuses a
Move to box that names no section. No card is filed at the back of a box without a word. The
undo of a move (`{"undo": true}` on the tombstone) names no section and is not refused.

Which callers reach the rule:

| Caller | Path | Reaches the rule? |
|---|---|---|
| Move to box, one card (`Inventory.tsx`, `server.ts:moveCard`) | `do_move_card` | Yes. It sends `section`. |
| Move to box, ticked cards or a whole box (`BoxOps.tsx`, `server.ts:moveCards`) | `do_move_cards` | Yes. It sends `section`. |
| Move undo (`{"undo": true}`) | `do_move_card`, then `_unmove_one` | No. It returns before the rule. |
| The Map's section move | `do_move_sections`, then `_cross`, then `_move_one` with its own slot | No. It names its gap. |
| The Map's card or range move | `do_move_range`, then `_cross`, then `Inventory.place` | Its own rule, section 1.6. |
| `Inventory.move_card`, `Inventory.move_cards` | the store, not a route | No. The rule is on the route. |
| The CLI, orders, fulfillment | none of them moves a card | No. |
| The demo server (`demoServer.ts`) | no move route | No. |
| `scripts/cid-selftest.py` and the T7 cases | the two routes | They send `section`. A case for the back of the box sends the last section's key (`t7_store_and_seams.back_of`). |

### 1.6 The Map's drag (`POST /boxes/<box>/cards/move`) and section move (`POST /boxes/<box>/sections/move`)

The drag names an exact gap: `before_card` or `section_end`. A body with no gap is refused,
unless the destination box is empty. An empty box has one place, so a drop there is exact.

**Both Map routes carry `layout_token` too.** The Map names its gap by a section NUMBER of
`to_box` (`section_end`, `before`). An S after a middle section on the rig renumbers the later
sections. A Map open on another device would then drop the cards into the new, empty section
without a word. So each Map drop sends the `layout_token` of the box the Map drew. The server
compares it with `to_box`'s token now. An empty box, and a new box, need no token, as their
drop needs no gap.

| Field | Type | Meaning |
|---|---|---|
| `layout_token` | string | `to_box`'s token from the `GET /boxes` the Map drew. Required when `to_box` has a section. |

| Status | Code | When |
|---|---|---|
| 400 | `section_required` | No `before_card` and no `section_end`, and `to_box` holds a record or a declared divider. Nothing moves. |
| 400 | `layout_token_required` | `to_box` has a section, and the body has no `layout_token`. Nothing moves. |
| 409 | `section_gone` | The token is not `to_box`'s token now. Nothing moves. The Map shows the server's sentence and reads the boxes again. |

`app/src/BoxShelf.tsx` sends the token of the box it drew (`byBox`), through `moveRange` and
`moveSections` in `app/src/server.ts`. `app/tests/boxmap.spec.ts` asserts the token in each
sent body. It also asserts that a 409 makes the Map show the sentence and read the boxes again.

Which callers send a gap:

| Caller | What it sends |
|---|---|
| `app/src/BoxShelf.tsx` `dropAt`, card mode | A `c:` gap sends `before_card`. An `e:` gap sends `section_end`. The `end` gap sends neither, and the Map draws it in card mode only for a box with no sections, which is an empty box. |
| `app/tests/boxmap.spec.ts` | Every recorded body carries `before_card` or `section_end`. |
| `app/src/demoServer.ts` | No move route. |
| `harness/tests/t7_box_map.py` | Every call names a gap, except a move into an empty box, which stays legal. The fuzz's `range` kind always names a gap. |

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
  renumbered). It is the card's identity, not its place (D294, the order key is apart from the
  index). A card captured mid-box has the highest index and a middle order key.
- **S in the middle.** If S puts a new divider after section 2, the old sections 3 and 4
  become 4 and 5. Their card numbers do not change. This is the one number that moves. A label
  that a screen saved before the S shows the old section number.

## 3. The store

`store/master.py` holds each of these. None of them builds a `Card` for the whole box, because
a capture calls them inside the store lock. They read the `idx` and `ord` columns only.

- `Inventory.dividers_of(box)`: the dividers as `layout_of` draws them, through
  `front_of_box`.
- `Inventory.layout_token(box)`: a short hash of the divider keys, in order (section 1).
- `Inventory.section_ordinal(box, div, token)`: the section a divider key names, or
  `SectionGone`. It refuses a token that is not the box's now before it reads the key.
- `Inventory.section_tail_key(box, div, token, count)`: the key rule, and the only one. It
  returns `(keys, ordinal, last)`: `count` keys, each the rule over the one before it, from
  one read of the box. A Move to box of many cards reads the tail once and takes one key per
  card. D300 states the rule and argues it.
- `Inventory.section_div_of(box, key)`: the divider key of the section a key stands in. The
  capture response reads it after the write.
- `Inventory.allocate_capture(box, section=...)`: it resolves the section before it allocates
  the index. For the last section it passes no key, so `record_capture` keeps the back-of-box
  rule.
- `Inventory.open_section(box, after=...)` and `Inventory.close_section(box, div=...)`: S and U,
  aimed by key.
- `Inventory.unmove_card`: a move records `to_box`'s layout on its arrival line (`sections`).
  The undo refuses a divider behind the card only when the recorded layout did not hold it. A
  divider that was there before the move never refuses. A divider that went in after it always
  refuses. A move line with no recorded layout refuses on any divider behind the card.

## 4. Every writer, and the invariant that proves it

`harness/tests/t7_box_map.py:check_capture_into_section` holds the named cases and the fuzz.

| Writer | Change | Invariant |
|---|---|---|
| capture, no section | none | I1. The same keys and dividers as a capture into the last section. An identity box stays the identity. |
| capture into section j | new | I2. The new key is above every key in j and below the next divider. No other key or divider changes. I3. No card number outside j changes, and no earlier card in j changes. |
| capture into an empty middle section | new | I4. The key equals the divider's key. |
| capture under a planned divider | new | I5. With `[1, 51]` on 5 cards, a capture into section 1 takes key 6, and section 2 stays at card 51. |
| stale aim | new | I6. A refusal writes nothing. `next_index` does not change, and no photograph is stored. |
| aim read before a re-space | new | I16. A capture, an S or a Move to box aimed before a re-space is refused with `section_gone`, even where the old key is now another section's key. It writes nothing. The fuzz re-spaces between the aim and the write on a quarter of its aims. |
| re-space | reused | I7. Order and section membership stay. `section_div` names the new key. |
| S after section j | new | I8. One divider goes between j's last card and the next divider. No card key changes. Later sections move up one number. Their card numbers stay. |
| U after S, by key | new | I9. Only that divider goes. It refuses the first divider, a section with a card, a key the box does not have, and a divider an editor save came after. |
| capture undo | none | I10. It deletes the newest index even when that card is mid-box. The next capture into the emptied section takes the divider's key. |
| remove | none | I11. Indices slide and keys do not. The fuzz holds it. |
| move, range move, section move | Move to box requires `section` | I12. A move with `section` goes to that section's tail, in the order sent. A move with a key the box does not have, or with no section, moves nothing. |
| move undo | the divider guard asks when | I13. A move into a middle section, or into the section before an empty last section, can be undone: those dividers were there before the move. A divider that went in behind the card after the move refuses. |
| sell and unsell | none | I14. No key or divider is written. The fuzz holds it. |
| divider editor | none | I15. After a mid-box S, a save with no edits keeps every divider. |

**The fuzz.** Six seeds of 150 writes (seeds 6 to 11). A capture and an S aim at a random
section. A U takes out a random empty section by key. A Move-to-box aims at a random section.
A sale, and a sale undone at once, join the writes. Every other write from the divider proof
stays in the mix. The divider proof's own fuzz (seeds 0 to 5) is separate.

## 5. The screen

`app/src/CaptureScreen.tsx` carries a Section row under the Box row, in its own slot
(`.capture-section-slot`). It follows the Box row's own trick: the closed Row stays in flow
and sizes the slot. Its open field overlays that slot, pinned like the Box field's own. So a
pick or an S never moves the shutter or the blocker list (D118).

The row names the picked section, its ordinal, and its own name if it has one. It also names
the next card number within it. That number is `SectionDetail.start + count`.
`patchSectionCount` moves it per capture, the way `patchOnHand` moves the Box row's own
count. When the pick is not the last section, the row also says where the card physically
goes. It reads "behind the section N divider" (the physical model in section 2). Tap or Enter
opens a list of every section. Each row shows its own count. Per D260, the list marks "back"
for section 1 and "front" for the last one.

**`[` and `]`** step the pick toward the back or the front (`stepSection`). Both are in
`CAPTURE_KEYS` in `App.tsx`. Neither is a letter. So neither reaches `RESERVED_KEYS` or
`OPTION_KEYS`, and no option keycap moves.

**The default is the last section.** It is the one value (`selectedDiv === null`) that sends
no `section` field at all. A browser that never picks sends the same capture as before this
feature existed (I1).

**What is remembered, and for how long.** The pick is kept per box until the sitting ends. It
is keyed by `bid` where the store gave one, or by the box number otherwise (D145, D153). A
reused box number cannot inherit a stale pick this way. The key lives in
`app/src/deviceMemory.ts`'s `banchi.capture.sections`, a map from that key to
`{div, at, token}`. On a box's first read after `GET /boxes` answers, the screen checks `at`
against `GAP_MINUTES` (`storeHistory.ts`'s own 30-minute sitting gap, D164). It checks the div
and the token too, against the box's current `sections_detail` and `layout_token`. Fresh and
known: the pick restores. Stale, or naming a divider the box no longer has: the entry is
forgotten. The pick falls back to the last section, and one plain sentence says so. **The
server keeps no pick at all.** Every request carries its own aim, so two devices (D13) cannot
disagree.

A stored pick's `token` is read at pick time. It is checked again at restore and on every
capture into the pick. A `div` that is still a real key in `sections_detail` can name a
DIFFERENT section after a re-space. Membership alone cannot see that. The token can. A token
mismatch reads like a missing key: the pick is gone, not merely expired. A pick past
`GAP_MINUTES` reads as EXPIRED, a different sentence. It is checked live on every capture
attempt, not only when the screen mounts. A capture into a picked section refreshes that
pick's own clock. A sitting that keeps capturing into one section never expires mid-stream.

**S sends `after: selectedDiv`**, omitted for the default. The screen reads the new section
off the response as the one directly after the picked ordinal. It is never the array's last
entry. The screen then picks the new section. When the pick was not already the last section,
the note also names which later sections renumbered. It reads "Sections 3 to 5 are now 4 to
6." The strip re-reads `GET /capture/sitting` and patches each shot's own `label`, `section`
and `card` by key (`refreshShotLabels`). A mid-box S renumbers every later section. A stored
label is rendered at read time (D58), so it goes stale the instant the divider ahead of it
moves.

**U after S** carries the divider's own key, `pendingDivider.div`, sent through
`closeSection(box, div)`. `div` is `null` only when a response carried no
`sections_detail[].div` at all. The undo then falls back to the box-only form, which removes
the last divider. `undoDivider` restores the pick the operator had immediately BEFORE that S.
It never restores the divider key U just removed. It never falls back blindly to the last
section. `pendingDivider` carries that prior pick beside the divider's own key and open time.

**Every aim sends the box's `layout_token`** alongside a picked `section` or `after`. It is
read off `BoxRecord.layout_token` at the moment of the press, never composed. It is omitted
along with the section field for the default pick. Against a server that sends no token,
`layoutToken` reads `undefined` and the aim goes with no token.

**A 409 `section_gone` or a 400 `layout_token_required` on a capture HALTS the run.** Nothing
was written, and the halt's copy says that plainly. It never uses the generic server-halt
sentence ("check whether that card was recorded"), which would be a false hedge here.
`handleSectionMismatch` forgets the stale stored pick at once. It then re-reads `GET /boxes`.
It checks whether a section still stands at the SAME ORDINAL the operator picked. The halt
offers one or two named actions, never a bare "Resume". "Keep section N" appears only when one
still stands at that ordinal. "Use the last section" always appears. Pressing either is the
only way past the halt. Both actions compare the box and bid on screen with the box and bid
the halt was raised for. So a box switch while the halt sits on screen cannot apply its answer
to the wrong box.

**A re-space that lands DURING a capture that itself succeeds** is caught a different way. The
response's own `layout_token` and `section_div` are read back. If the token moved, the pick is
re-pointed at `section_div`, the one key the wire contract guarantees still names where the
card went. `GET /boxes` is re-read to refresh the rest of `sections_detail`. The token is
never patched alone. That would leave every other key in `sections_detail` unreconciled
against the new layout.

**The three trigger refs (`fireCaptureRef`, `fireUndoRef`, `fireSectionRef`) are assigned in a
layout effect, not a passive one** (D128's own pattern). An S immediately followed by a U
could otherwise run the trigger seam's STALE closures. A passive effect can still be pending
when the next keypress arrives. `app/tests/capture-section.spec.ts` proves the tight sequence.

**`demoServer.ts`** refuses `after` on `POST /boxes/<box>/sections`, with the demo's own
refusal sentence. A real middle pick is not modelled there. `/capture` is refused
unconditionally, which covers `section` for the same reason.

## 6. Ripple effects

- **Runs and identify.** A run binds positions by index, and realign binds by photo digest
  (D36). A capture into the middle renumbers no index, so nothing changes.
- **Queue labels.** Every route re-renders `QueueEntry.label` at read time and never serves
  the stored one (`server/capture_server.py`, D58). So a mid-box S changes no label on a
  screen. The stored label still reaches CLI text lines, as it does after any divider edit.
- **Walk and fulfillment.** `records_in`, `BoxView` and `walkplan` read keys.
  `Inventory.positions_for_sku` and `Inventory.in_state` sort by `(box, order key, index)`.
- **Demo.** `demoServer.ts` refuses `/capture` and refuses `after` on `openSection`.

## 7. Where the build differs from the plan

It does not differ. The rules live in section 1 (the token, `section_required`,
`history_unreadable`) and section 3 (`section_tail_key`, the move undo).

## 8. Measurements

None are kept. Section 4 holds the invariants. Measure the live store when a number matters.

## 9. The owner's rulings

- **Q1, S after a picked middle section:** the new divider goes right after it. Later sections
  move up one number, and their card numbers stay.
- **Q2, how long the pick lasts:** until the sitting ends. The pick is kept per box on the
  device until the sitting ends (D164, a 30-minute break). Then it goes back to the last
  section. The server keeps no pick.
- **Q3, Move to box:** the owner specifies where it goes, with no auto default. A Move to box
  with no drop spot has no default. The owner chooses the section in the target box, and the
  card goes to the end of that section. A Map drag stays exact.

## 10. Lanes

File ownership is in `docs/map.py`.

## 11. The Move-to-box section choice

Every path on `#/inventory` that moves a card into a box, with no exact drop spot, asks the
owner to pick a destination section (Q3). The two Move-to-box routes (1.5) are the whole
surface. `Inventory.tsx`'s `MovePanel` moves one copy, from its own row. `BoxOps.tsx`'s "Move
to box" moves a ticked selection, or the whole box. D83's range move and the merge are the
same one write. The Map's own drag (`moveSections`, `moveRange`) already names an exact gap and
is out of scope.

- **The picker.** `kit/index.tsx:SectionPicker` is one kit primitive (`.bn-section-pick` in
  `kit.css`). Both screens reuse it. It reads a box's own `sections_detail` (typed with
  `div?: string | null` in `types.ts`, matching 1.1). Each row shows a section's number, name
  and count. The first row says "back" and the last says "front" (D260). A picked row gets a
  check mark. A box with one section still shows that one row, so the owner presses it. No
  code path treats "the only choice" as a default, because a box can grow a second section at
  any time (an S).
- **No default, enforced on the screen.** Both dialogs' Move press stays disabled until a box
  AND a section are picked. `server.ts:moveCard` and `moveCards` both take an optional
  `MoveSection` (a divider key AND the destination box's own `layout_token`, always sent
  together, per 1.5). The disabled check reads whether the picked div is still a real row in
  the box's CURRENT `sections_detail`. It never trusts a bare non-null flag.
- **A stale section re-opens the pick.** `section_gone` (409), `section_required` (400) and
  `layout_token_required` (400) are handled the same way. The dialog stays open. The server's
  own sentence shows in place, behind "What the server said" (D196). The section pick clears.
  The box stays chosen.
- **The receipt and the undo.** A single-card move's toast reads the destination's own
  `place.label` off the response (`MoveResult.card`). That field composes "Section N", the one
  renderer every screen uses. `moveCards`'s batched response carries no per-card place.
  `BoxOps.tsx` names the section from the pick it sent instead. The single-card move's receipt
  carries Undo (`undoMove`, UN-14; `docs/specs/undo.md` §11.3). The undo ignores `section`: it
  returns to the source index. `BoxOps.tsx`'s batched move has no undo.
- **The demo.** Neither Move-to-box route is matched in `demoServer.ts`'s routing table. Both
  fall through to `demo_read_only`, and Move answers "Not in this demo." The recorded
  `GET /boxes` carries `div` for every section, because `make demo-record` runs the live
  server code. The demo picker draws real sections.
- **Checks.** `app/tests/inventory.spec.ts` and `app/tests/boxmap.spec.ts` cover the picker and
  the Map's drag. A D118 rect-diff assertion covers picking a section: nothing outside the
  dialog moves.
