## D142 — The setup outlives the browser, the box list is ordered by the hand, and one value stays on the old clock

**Settled 2026-09-11, on the owner's own words about the screen they spend the most hours in.** Four instructions in one message, three of them about memory and one about what a box is called:

> *same box style sorting in inventory (where most recently selected/most filled go to the top, rather than box #, determines the order of box in Workflow: Capture)*
>
> *ideally let it save my last used on capture on all settings ... so the game i picked, camera i picked, all stay saved in some sorta session history*
>
> *a quick clear all settings button*
>
> *i dont need to see box number in capture screen*

### D27's premise was wrong about shifts, and the owner is the authority on that

**D27 put seven values in `sessionStorage` and gave one reason**: *"a new tab is a new shift and closing the browser ends one."* That is a claim about how the operator works, not about how a browser works, and the person it describes says it is false. A shift ends when they stop feeding cards. The browser closing is a laptop lid; a new tab is a link opened from somewhere else. Neither is a fact about the stack on the desk.

**The camera was already the counter-example and had been since before D27 existed.** `useCamera.ts` has held `banchi.capture.deviceId` and `banchi.capture.rotation` in `localStorage` from the beginning, arguing informally what D27 later generalised — and the owner's message names the camera and the game in one breath, as two things that should behave the same way. They were behaving differently, and nothing about either value explains why.

**So six of the seven move to the device**: box, game, set hint, finish, rarity claim, product. `app/src/deviceMemory.ts` holds them as `banchi.capture.setup`, under the same `banchi.capture.*` prefix the camera already used, so everything this screen remembers about this machine now sits under one name.

### ONE DOCUMENT, NOT SIX KEYS

**It is one habit.** "The setup I work at" is a single thing the operator arranges once and clears in one press. `banchi.orders.fetch-filter` makes this argument already for its own two fields — *"splitting them would put two rows in `CLAUDE.md`'s roster for one habit"* — and it holds harder at six.

**And it makes the clear one removal rather than six that can fail apart.** `localStorage` throws on the accessor in a private window and can throw on quota; six writes have five ways to half-succeed and leave a setup that is neither the old one nor nothing.

**What it gave up is the absent-means-empty trick, and that turned out to be worth nothing.** Each old key stored "empty" as ABSENT so a cleared field and an unwritten one read alike. A document is present or absent as a whole, so `storedCaptureSetup` reads a missing FIELD as the same nothing it reads a missing document as, and an empty list can be stored as an empty list. What the wire carries is unchanged: an empty claim is still no claim (D3), and the screen still omits the key from the capture.

### `captureId` DID NOT MOVE, AND IT IS WHAT THE CARVE-OUT WAS ALWAYS FOR

**A restored setting is a claim on screen that is one press from being right. A restored `captureId` is a request for a card nobody is holding.** It is the in-flight id of a capture whose response was lost; everything about it is scoped to one page load — minted for a photograph being taken now, answered or abandoned within seconds, and the banner it raises asks the operator to put THAT card back at the lens.

**Restoring it into a new shift would be strictly worse than losing it.** The banner would name a capture that resolved yesterday, and the honest answer to it — feed that card again — burns a position under D10's high-water mark. Session scope is what holds the window to "this page load", which is the only window the banner's own sentence is true in.

**D27 is amended rather than overturned.** Its reason for existing is this value; what it got wrong is the six it generalised to. `banchi.run-scope` (D39) is unaffected and stays for its own stated reason: reading nothing is its safe answer by construction.

### THE BOX LIST IS ORDERED BY THE HAND, AND IT IS THE SAME STORE `#/inventory` USES

**The field's own comment had already conceded the point.** It sorted by number and took the highest nine, on the reasoning that *"boxes are allocated upward and recency is not a fact either route carries"*. True of the ROUTES, and it stopped being true of the BROWSER when D132 started recording which boxes the hand opened. The proxy fails exactly where it matters: a drawer fed for three weeks sinks below every box made since, and the one box that can never sink is the one made last — the one case nobody needs help finding.

**Three terms, D132's rail comparator exactly**: the box this browser last reached for, then the box holding the most cards, then the number, which is the last thing the owner thinks in and so the last thing this sorts by. `on_hand` and not `cards`, `fill` or `next_index`, for D132's reason — a box full of sold records is not a box worth reaching for.

**ONE STORE, SHARED, AND THAT IS A RULING RATHER THAN AN ECONOMY.** Capture could have kept a recency store of its own. The argument against it is that there is one operator with one hand: photographing into box 7 and then walking to `#/inventory` is the same person still thinking about box 7, and a rail that opened on some other drawer would be answering a question nobody asked. The shared store is what makes the second screen agree with the first without either knowing about the other.

**So the key is renamed** — `banchi.inventory.box-recency` to `banchi.box-recency`. Two screens write it now, and the old name said which SCREEN had written the fact instead of what the fact is. **No migration**, D27's own second-amendment rule and the reason a read-time fallback was declined there; the cost is one sitting of the fallback order until the first box is opened or captured into.

**A PICK IS A REACH AND A CAPTURE IS NOT.** Only `chooseBox` touches the store. A capture fires once per card at a measured 623 ms cadence, so touching there would put a `localStorage` read-modify-write on the feeder's hot path — hundreds of times a box — to re-record a fact that has not changed since the pick that preceded every one of them. A page LOAD is not a reach either, which is `BoxBrowse`'s own rule: the restore carries the box the operator last picked, and that pick already wrote its stamp.

### A RESTORED BOX IS CHECKED AGAINST THE STORE, AND FAILS SOFTLY

**Photographing into the wrong drawer is the expensive failure on this screen**, and the setup now outlives the browser, so the gap between "the box I last picked" and "a box that still exists and still takes cards" can be days wide. Between two sittings a box can be sealed (D20), deleted (D34's panel), or **deleted and its number handed to a different physical drawer** by `next_box_number`'s lowest-free allocation. The first two are refused at the shutter anyway. **The third was refused nowhere when this entry was written, and this entry BUILT two of the three it had just enumerated** — box 7 exists and takes cards, so a reallocated number passed every test the restore made; it is simply not the box the operator thinks they are looking at. **That gap is closed as of 2026-09-12 (D153), and the closing needed a fact this entry did not have**: a drawer's identity, which D145 gave it. The sentence below described two cases in words that read as three, and is corrected rather than deleted because the overclaim is the defect worth remembering.

**So the restore falls back to NO SELECTION, never to a guess** — for the box that is GONE and the box that is SEALED here, and for the reallocated one since D153. It names the box it let go of, says why, and opens the field with focus in the entry — the state `Pick a box` would have put them in, so the remedy is the press they were about to make.

**It waits for the answer, not for a non-empty list.** `boxRecords` starts `[]` and `[]` is also what a store with no boxes returns; judging on emptiness would clear a good box on every slow fetch, which on a cold capture server is every fetch. A separate flag records that `GET /boxes` actually answered.

### THE CLEAR IS ONE PRESS WITH A RECEIPT AND A WAY BACK

**Quick is the requirement, so there is no confirmation dialog.** The press clears, the screen visibly returns to its empty state, and a receipt toast carries an Undo — D28's shape for the review answer, right here for the same reason: a confirmation ahead of a reversible act buys nothing and costs a press every time.

**It clears choices about CARDS and leaves the RIG alone.** Box, game, set hint, rarity, finish and product are decisions about the stack in front of the operator, and the next stack is a different decision. The camera and the rotation are which hardware is plugged in and which way it is mounted (D13) — the same tomorrow as today. Clearing those would mean re-picking a 4K capture card to start a run that needs none of it re-picked, so the control says on its face what it leaves behind.

**It leaves `banchi.box-recency` alone too**, and that is the same line drawn once more: the clear is about the setup, not about which drawers this hand has been in.

**The game goes to the registry's default, not to null.** A null game draws the blocked reason for a registry that has not ARRIVED — *"Waiting for the game list from the server"* — which after a successful load is simply untrue. A fresh browser does not sit on no game either; `loadGames` puts it on `registry.default`. That IS nothing chosen, for this one field.

**Quiet, not danger.** It destroys nothing, `docs/DESIGN.md` reserves red for acts that do, and the sentence under it names the store explicitly. This is the screen where cards are made and "clear" is a word that could be misread.

**No keyboard binding, deliberately.** Every unmodified letter at rest is spoken for by `FIELD_KEYS` plus `c`/`u`/`s`, and a reset on a bare letter at a rig — where the operator is pressing keys fast with a card in hand — is a mis-press that wipes the setup mid-run. The owner asked for a button. `SHORTCUTS` gains nothing, which is the correct outcome rather than an omission.

### THE BOX NUMBER COMES OFF THIS SCREEN, AND OFF THIS SCREEN ONLY

**D20 is what makes the instruction answerable**: a box is addressed by its name and names are unique, so `RB Epics` identifies a drawer as completely as `Box 3` does and identifies it in the word the operator actually thinks in. At the lens they are not walking a shelf or reading a path; they are putting cards into the box open on the desk, and they named it.

**An unnamed box still draws its number, and that is not an exception.** D20 makes a name unique and deliberately NOT required, so a box with none is an ordinary box and its number is the only thing it has to be called. A placeholder in the name's place would draw a fault where there is none (D56). The number is removed as the thing the operator reads PAST, never as the thing a box is.

**`runScope.ts:captureBoxLabel` is that rule, beside `boxLabel` rather than inside it.** Every other screen keeps `Box 3 · RB Epics` for the reason written there: the number is the shelf, the photograph directory, and what every refusal in `server/pipeline_routes.py` names. The capture screen is the one place the operator is holding the physical box.

**The PICKER keeps the number, inverted.** The name leads and `Box 3` trails as a de-emphasised suffix, because the entry above it searches number and name together — a row that hid the number would answer a search for `9` with nine rows that do not visibly contain a 9. That is the one place on this screen where the number is still doing a job.

**AMENDED 2026-09-12 (D153), ON THE OWNER LOOKING AT THIS VERY LIST**: *"on the capture screen, i shouldn't even need to see box. numbers here, it's waste of space"*. The reason above is correct and was spent too widely — it is about a row's answer to a TYPED NUMBER, and it was applied to every row at all times. The suffix is now drawn only where the row matched BECAUSE of a number the operator typed, so the list is names at rest and the `9` case is untouched. The reason survives the amendment intact; what changed is its scope.

**Nothing else moved.** `pipeline/join.py:Position` is untouched, including on this screen's own filmstrip and receipts: the Fulfiller reads those, and he is walking a shelf he did not pack. Nothing on the wire changed and no route was added.

### What would reopen it

**A second person at a second rig.** Every argument here assumes one operator with one hand and one desk — the shared recency store most of all. Two people feeding two rigs from one browser profile would make "most recently reached for" a question with two answers, and the right shape then is probably per-rig rather than per-device.

**A box whose name is not the word the operator uses.** The rendering assumes the name is what they recognise. If drawers start being named by content and referred to by position, the number comes back.
