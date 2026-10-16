## D142 — Setup outlives the browser

**Ruling: the capture setup persists on the device, not per browser session.** The owner gave four instructions in one message. Three concern memory. One concerns what a box is called.

- Capture's box picker orders boxes as Inventory does: most recently selected or most filled first. It does not order by box number.
- Capture remembers the last-used settings, game and camera included, as a session history.
- A quick clear-all-settings button.
- Box numbers are not shown on the capture screen.

### D27's premise was wrong about shifts, and the owner is the authority on that

D27 put seven values in `sessionStorage`, with one reason: "a new tab is a new shift and closing the browser ends one." That is a claim about how the operator works, not about how a browser works. The owner, who works at this screen, says it is false. A shift ends when they stop feeding cards. Closing the browser is a laptop lid. A new tab is a link opened from elsewhere. Neither is a fact about the stack on the desk.

The camera was already the counter-example. `useCamera.ts` has kept `banchi.capture.deviceId` and `banchi.capture.rotation` in `localStorage` from the start. The owner's message names the camera and the game together, as two things that should behave alike. They behaved differently, and nothing explained why.

**Six of the seven move to the device:** box, game, set hint, finish, rarity claim and product. `app/src/deviceMemory.ts` holds them as `banchi.capture.setup`. That key sits under the `banchi.capture.*` prefix the camera already used. Everything this screen remembers about the machine now sits under one name.

### One document, not six keys

"The setup I work at" is one thing. The operator arranges it once and clears it in one press. `banchi.orders.fetch-filter` makes the same argument for its two fields. The argument holds harder at six.

The clear is one removal, not six writes that can fail apart. `localStorage` throws on the accessor in a private window, and it can throw on quota. Six writes have five ways to half-succeed. A half-written setup is neither the old one nor nothing.

The cost is the absent-means-empty trick. Each old key stored "empty" as absent, so a cleared field and an unwritten one read alike. A document is present or absent as a whole. So `storedCaptureSetup` reads a missing field as nothing, the same as a missing document. An empty list can be stored as an empty list. The wire is unchanged. An empty claim is still no claim (D3), and the screen still omits the key from the capture.

### `captureId` does not move

A restored setting is a claim on screen, one press from right. A restored `captureId` is a request for a card nobody is holding. It is the in-flight id of a capture whose response was lost. It is scoped to one page load. It was minted for a photograph taken now, and it is answered or abandoned within seconds. The banner it raises asks the operator to put that card back at the lens.

Restoring it into a new shift would be worse than losing it. The banner would name a capture that resolved yesterday. Feeding that card again burns a position under D10's high-water mark. Session scope keeps the window to "this page load", the only window in which the banner's sentence is true.

D27 is amended, not overturned. Its reason for existing is this value. What it got wrong is the six it generalized to. `banchi.run-scope` (D39) is unaffected and stays for its own reason: reading nothing is its safe answer by construction.

### The box list is ordered by the hand, from the same store as `#/inventory`

The field's old comment sorted by number and took the highest nine. Its reason: "boxes are allocated upward and recency is not a fact either route carries." That stopped being true when D132 began recording which boxes the hand opened. The number proxy fails where it matters. A drawer fed for three weeks sinks below every box made since. The box made last never sinks, and that is the one box nobody needs help finding.

The sort uses D132's rail comparator, in three terms. First, the box this browser last reached for. Then the box holding the most cards. Then the number. The number is the last thing the operator thinks in, so it sorts last. The fill term uses `on_hand`, not `cards`, `fill` or `next_index`, for D132's reason: a box full of sold records is not worth reaching for.

**Ruling: one store, shared.** Capture could have kept a recency store of its own. The argument against it is that one operator has one hand. Photographing into box 7 and then opening `#/inventory` is the same person still thinking about box 7. A rail that opened on another drawer would answer a question nobody asked. The shared store makes the second screen agree with the first, and neither needs to know about the other.

The key is renamed from `banchi.inventory.box-recency` to `banchi.box-recency`. Two screens write it now, and the old name named the screen that wrote it, not the fact. There is no migration. That follows D27's second-amendment rule, which declined a read-time fallback. The cost is one sitting on the fallback order, until the first box is opened or captured into.

**A pick is a reach. A capture is not.** Only `chooseBox` writes the store. A capture fires once per card at a measured 623 ms cadence. Writing there would put a `localStorage` read-modify-write on the feeder's hot path, hundreds of times a box. It would re-record a fact that the pick before each capture already recorded. A page load is not a reach either. `BoxBrowse`'s rule applies: the restore carries the box the operator last picked, and that pick already wrote its stamp.

### A restored box is checked against the store and fails softly

Photographing into the wrong drawer is the expensive failure on this screen. The setup outlives the browser, so the gap between "the box I last picked" and "a box that still exists and takes cards" can be days wide. Between sittings, a box can be sealed (D20) or deleted (D34's panel). It can also be deleted, with its number handed to a different physical drawer by `next_box_number`'s lowest-free allocation.

The first two were refused at the shutter already. The third was refused nowhere when this entry was written, and this entry built two of the three cases it had just listed. Box 7 exists and takes cards, so a reallocated number passed every test the restore made. It was not the box the operator thought they were looking at. D153 closes that gap. The close needed a drawer's identity, which D145 supplies. The earlier text here described two cases in words that read as three. It is corrected, not deleted, because the overclaim is the defect worth remembering.

The restore falls back to no selection, never to a guess. That applies to a box that is gone, a box sealed here, and a reallocated box since D153. The screen names the box it let go of, says why, and opens the field with focus in the entry. That is the state `Pick a box` would have produced, so the remedy is the press the operator was about to make.

The restore waits for the answer, not for a non-empty list. `boxRecords` starts as `[]`. A store with no boxes also returns `[]`. Judging on emptiness would clear a good box on every slow fetch, and on a cold capture server that is every fetch. A separate flag records that `GET /boxes` answered.

### The clear asks first, then gives a receipt and a way back

**Owner ruling (replacing the earlier no-dialog press).** The press opens a confirmation. The confirmation carries the sentence that used to sit under the button, and a Clear button. Esc cancels, and Enter confirms. Only the confirm clears. The screen then shows its empty state. A receipt toast carries an Undo.

The clear covers choices about cards and leaves the rig alone. Box, game, set hint, rarity, finish and product are decisions about the stack in front of the operator. The next stack is a different decision. The camera and the rotation describe which hardware is plugged in and how it is mounted (D13). Those are the same tomorrow as today. Clearing them would make the operator re-pick a 4K capture card for a run that needs no change. So the confirmation says what it leaves behind.

The clear also leaves `banchi.box-recency` alone. That is the same line, drawn again. The clear covers the setup, not the drawers this hand has been in.

The game goes to the registry's default, not to null. A null game shows the blocked reason "Waiting for the game list from the server". After a successful load, that text is untrue. A fresh browser does not sit on no game either, because `loadGames` sets `registry.default`. For this one field, the default means nothing chosen.

**Quiet, not danger.** The clear destroys nothing. `docs/DESIGN.md` reserves red for acts that destroy. The sentence under the button names the store. This is the screen where cards are made, and "clear" could be misread.

**No keyboard binding, on purpose.** Every unmodified letter at rest is taken by `FIELD_KEYS` plus `c`, `u` and `s`. A reset on a bare letter at the rig is a mis-press that wipes the setup mid-run. At the rig the operator presses keys fast, with a card in hand. The owner asked for a button. `SHORTCUTS` gains nothing. That is the correct outcome, not an omission.

### The box number comes off this screen, and off this screen only

D20 lets the instruction work. A box is addressed by its name, and names are unique. So `RB Epics` identifies a drawer as completely as `Box 3` does. It identifies the drawer in the word the operator thinks in. At the lens, the operator is not walking a shelf or reading a path. They are putting cards into the open box, and they named it.

An unnamed box still draws its number. That is not an exception. D20 makes a name unique but does not require one. A box with no name is an ordinary box, and its number is the only thing it can be called. A placeholder in the name's place would draw a fault where there is none (D56). The number leaves this screen as the thing the operator reads past. It is never the thing a box is.

`runScope.ts:captureBoxLabel` holds that rule, beside `boxLabel` rather than inside it. Other screens keep `Box 3 · RB Epics`. The number is the shelf, the photograph directory, and what every refusal in `server/pipeline_routes.py` names. The capture screen is the one place where the operator holds the physical box.

The picker keeps the number, inverted. The name leads, and `Box 3` trails as a de-emphasized suffix. The entry above the list searches number and name together. A row that hid its number would answer a search for `9` with nine rows that do not visibly contain a 9. That is the one place on this screen where the number still does a job.

**Amended (D153), after the owner saw this list.** On the capture screen, box numbers were wasted space. The reason above is correct, but it was applied too widely. It concerns a row's answer to a typed number. It was applied to every row, always. Now the suffix draws only where the row matched because of a number the operator typed. So the list shows names at rest, and the `9` case is unchanged. The reason survives. Its scope changed.

**Nothing else moved.** `pipeline/join.py:Position` is untouched, including on this screen's filmstrip and receipts. The Fulfiller reads those, and walks a shelf they did not pack. The wire is unchanged, and no route was added.

### What would reopen it

- **A second person at a second rig.** Every argument here assumes one operator, one hand and one desk. The shared recency store most of all. Two people feeding two rigs from one browser profile would make "most recently reached for" a question with two answers. The right shape then is probably per rig, not per device.
- **A box whose name is not the word the operator uses.** The rendering assumes that the name is what they recognize. If drawers are named by content and referred to by position, the number comes back.

Capture asks for a box on a fresh device ("No box yet"), and Home's tile says so.
