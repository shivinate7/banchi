## D153 — Restore asks which drawer

**The capture screen asks which drawer it is. It stops drawing the box number everywhere else.** D145 gave a drawer an identity, so the screen can ask which drawer it is. Having asked there, it can stop drawing the number on the other rows.

### The restore kept a box that was not the box

D142 named three ways a remembered box goes stale, and built handling for two. A box can be sealed, or deleted. Or its number can be handed to a different physical drawer by `next_box_number`'s lowest-free allocation. D142 said that third case is refused nowhere, "because box 7 exists and takes cards". The next paragraph said the restore "falls back to NO SELECTION, never to a guess", which reads as covering all three. It covered two, and nothing in the tree could say so:

```ts
const found = boxRecords.find((record) => record.box === wanted)
if (found !== undefined && found.state !== 'closed') return
```

A reallocated number is found, and open, and takes cards. So the restore holds. The operator resumes into a drawer they did not leave. Every photograph of that sitting is filed at an address that does not match the shelf. This is silent. No refusal and no banner appear. The screen is correct about everything it can check.

**This repo already knew the hazard, and refused it once.** D36 as amended refuses to JOIN a run over a reallocated box (`cli/resolve.py:refuse_reallocated`, on `store/master.py:box_disowns_run`). The owner's own drawer is the example: box 1 first held 53 Pokemon cards, then 133 Riftbound cards. D36 cannot undo the photographs. Its realign re-binds a run to the slots its photographs are at now. Photographs in a drawer the operator never meant have nothing to re-bind to. The capture screen was the last place the mistake could still be prevented. It had no rule about it.

### The signal is the id, and the two plausible alternatives are both wrong

**The name is a poor signal.** D20 makes a rename a live edit. A drawer relabelled between two sittings is the same drawer. A name comparison calls it a different one. A name also says nothing about an unnamed box, which D20 permits.

**`next_index` cannot tell a reallocation from an undo.** It drops when a number is reused. It drops the same way on a capture-undo, which writes `target.index` back in `doUndo`. A decrease proves nothing. The screen that read it would cause the other case.

**`Box.bid` is set once at creation and never reused (D145), so a disagreement is a fact, not an inference.** It reaches the client as `bid` on `BoxRecord`. That is the spelling `store/master.py`'s column and `server/pipeline_routes.py`'s scope block already use, since this record is a box. `box_bid` is that module's spelling on a RUN row. There it is one of three facts about some other object. **Nothing draws it.** The owner's ruling that the id stays invisible is unchanged. A screen draws the sentence a comparison of two ids produces.

### The two silences are not the same silence, and that is the migration decision

A comparison needs two values, and either can be missing. They are answered differently, on purpose.

**A BOX with no id keeps the restore.** `Box.bid` is optional forever. A box holding cards with no registry entry has none, and neither does a store an older build migrated. The rule that predates the id decides, unchanged. This is D145's two-arm shape: "Where it does not, the older rule decides". Clearing here would refuse a good box on every load, over a fault the operator cannot fix from this screen. A rule that punishes the operator for the store's silence is not a safety rule.

**A SETUP with no id clears, and says it cannot tell.** This is the browser holding a document written before this landed. Weighed as the asymmetry it is:

| | cost |
|---|---|
| trust the number | the expensive silent failure this entry exists to prevent. It is live on the very machine that reported it, since the owner deleted a box 1 and started another this week. |
| clear it | one press, once, with a sentence on screen. The press is the remedy D142 already says the operator "was about to make" anyway. |

**So it clears.** D142's own rule decides it without a new one. A stored number with no id IS "a guess". That paragraph already says the restore never falls back to one.

**D27's amendment is the precedent for declining a fallback, and it is not in tension with this.** There the owner declined a read-time fallback for a renamed key, because a fallback can never safely be deleted afterwards. This arm has no such problem. It is not a fallback that preserves old behaviour. It is the same refusal the unknown-box arm already makes. It extinguishes itself after one pick. It stays correct whether it is kept for ever or merged into the disagreement arm later.

**It says "cannot tell" and never "your drawer changed".** It does not hold that fact. D145 forbids an abstention from softening a fact. The same care forbids it hardening into one.

### Where the number stays, and it is one sentence

**The reallocation sentence is the one place on this screen that names a box by NUMBER.** It reads: "Box 3 is a different drawer now — the one you last captured into was deleted, and its number went to this one." The number is the only thing the two drawers share. It is the thing that was handed over, and the subject of the sentence. Naming the box by its name there would tell the operator their drawer is `Epics`, which it has never been. **The other three restore sentences keep `captureBoxLabel`** (name, or number where there is none). Each of those is about a box that is, or probably is, theirs.

### The picker stops drawing numbers, and D142's reason survives its own amendment

**The owner, looking at the list, said the capture screen should not show box numbers.** They waste space. The screenshot showed `WB1 R2  Box 4  next index 679`. Beneath it were `ME01 C/UC  Box 2  Sealed` and an already-ellipsised `UNL BBOX C/UC 1…`.

D142 argued the picker should keep the number, and the argument was right. It said: "a row that hid the number would answer a search for `9` with nine rows that do not visibly contain a 9." That was spent too widely. The claim is about a row's answer to a TYPED NUMBER. It was applied to every row all the time, including the resting list. There, nothing has been typed and no row is answering anything.

**So the suffix is drawn exactly where that reason applies.** The query is non-empty, and the row is in the list because its NUMBER matched it. Type `9` and every row that matched on a 9 shows the 9. Type `com` and no number appears, since no row matched on one. At rest the list shows drawer names. **D145 is why this is givable at all.** With identity moved to `bid`, the number is a label and a search term. It is never the thing that says which drawer this is.

**Three things are deliberately unchanged.**

**Searching by number still works, and the placeholder still says so:** `Name or number`. Name comes first, since that is what the rows show and what the operator thinks in. The number stays, since D20 makes this one control over both, and a drawer may have no name at all. A placeholder that stopped saying so would hide a working search.

**An unnamed box still draws its number, and that is not an exception.** `captureBoxLabel` already puts it in the name's place (D142, D56: a placeholder would draw a fault where there is none). What had to be prevented is the doubling. A suffix beside it reads `Box 6 Box 6`. The test for it is the TRIMMED name, which is what `captureBoxLabel` itself applies. The old test was `option.name === null`. A whitespace-only name slipped past it into exactly that doubling.

**Nothing is added to the row. The space this frees is ATTENTION, not width.** The first draft of this paragraph got that wrong, and the renders showed it. The option row is a grid whose name column is `minmax(0, 1fr)`. It already takes every pixel the trail does not. Dropping a suffix that sat AFTER the name moves no boundary. `UNL BBOX C/UC 1…` ellipsises at exactly the same character before and after. What the number cost was a second thing to read on every row. The owner said the number wastes space in a list of drawers, where one fact identifies each. The row already carries `next index N` or `Sealed`, which is the useful half. Adding anything to a row the operator reads at a feeder's pace would spend the instruction on fresh clutter.

### What is guarded

`app/tests/capture-claims.spec.ts` carries seven new cases. The fixture's ids are deliberately not its numbers: boxes 1-4 wear ids 21-24. Against a fixture where box 2 wears id 2, a case comparing the wrong pair would pass.

Four cases cover the restore's arms. Two of them stop the guard being vacuous. A box the store still calls the same drawer is KEPT. A store issuing no ids KEEPS the restore. One case asserts that the pick records the id. Without it, every restore falls down the "cannot tell" arm for ever while looking like a working guard. Two cases cover the picker, at rest and under a typed number.

### What would reopen it

**A route that takes an id.** D145 forbids it, and this does not ask for one. The comparison happens in the client, against a field that rides along on a record it was already fetching.

**A second operator, or a browser profile shared between rigs.** The setup is one device's memory of one hand (D142). Two hands would make "the drawer I left" a question with two answers. The id would then compare against somebody else's pick.

**A drawer whose number the operator does read.** The picker assumes that the name is what they recognise. That is D142's own reopening condition, and this spends it further. If drawers start being named by content and referred to by position, the number comes back to the resting list.
