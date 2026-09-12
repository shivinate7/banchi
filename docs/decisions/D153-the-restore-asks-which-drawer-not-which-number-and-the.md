## D153 — The restore asks which drawer, not which number, and the picker stops drawing a number nobody reads

**Settled 2026-09-12, on a defect found in merged work and an instruction given the same evening.** Two changes to the capture screen, and they are one change: D145 gave a drawer an identity, so the screen can start asking the question the number was never able to answer — and, having asked it there, can stop putting the number in front of the operator everywhere else.

### The restore kept a box that was not the box

**D142 enumerated three ways a remembered box goes stale and built two.** Its own words: a box can be sealed, deleted, or *"deleted and its number handed to a different physical drawer"* by `next_box_number`'s lowest-free allocation — and, correctly, *"The third is refused nowhere, because box 7 exists and takes cards."* The very next paragraph opened *"So the restore falls back to NO SELECTION, never to a guess"*, which reads as covering all three. **It covered two**, and nothing in the tree could say so:

```ts
const found = boxRecords.find((record) => record.box === wanted)
if (found !== undefined && found.state !== 'closed') return
```

A reallocated number is found, and open, and takes cards. The restore holds, the operator resumes into a drawer that is not the one they left, and every photograph of that sitting is filed at an address that does not match the shelf. **Silently** — there is no refusal, no banner, and the screen is correct about everything it is able to check.

**This repo already knew the hazard by name and had already refused it once.** D36 as amended refuses to JOIN a run over a reallocated box (`cli/resolve.py:refuse_reallocated`, on `store/master.py:box_disowns_run`), and it names the owner's own drawer: box 1 held 53 Pokemon cards on 2026-08-22 and 133 Riftbound cards since 2026-08-29. **What D36 cannot do is undo the photographs.** Its realign re-binds a run to the slots its photographs are at NOW; these photographs are in a drawer the operator never meant, so there is nothing to re-bind them to. The capture screen was the last place the mistake could still be prevented, and it was the one place with no rule about it.

### The signal is the id, and the two plausible alternatives are both wrong

Both were considered and both are worth recording, because each looks serviceable:

**The NAME turns a rename into a false positive.** D20 makes a rename a live edit; a drawer relabelled between two sittings is the same drawer, and a name comparison calls it a different one. It also says nothing at all about an unnamed box, which D20 explicitly permits.

**`next_index` cannot tell a reallocation from an undo.** It does drop when a number is reused — and it drops identically on a capture-undo, which writes `target.index` back in `doUndo`. A decrease proves nothing, and the screen that would read it is the screen that causes the other case.

**`Box.bid` is allocated once at creation and never reused (D145), so a disagreement is a fact rather than an inference.** It reaches the client as `bid` on `BoxRecord` — the spelling `store/master.py`'s column and `server/pipeline_routes.py`'s scope block already use, because this record IS a box; `box_bid` is that module's spelling on a RUN row, where it is one of three facts about some other object. **Nothing draws it.** The owner's ruling that the id is *"not visible anywhere in the app"* is unchanged: what a screen draws is the sentence a comparison of two ids produces.

### The two silences are not the same silence, and that is the migration decision

A comparison needs two values and either can be missing. **They are answered differently, on purpose:**

**A BOX with no id keeps the restore.** `Box.bid` is optional forever, so a box holding cards with no registry entry has none, and neither does a store an older build migrated. The rule that predates the id decides, unchanged — which is D145's own two-arm shape (*"Where it does not, the older rule decides"*). **Clearing here would refuse a good box on every load, for ever, over a fault the operator cannot fix from this screen.** A rule that punishes the operator permanently for the store's silence is not a safety rule.

**A SETUP with no id clears, and says it cannot tell.** This is the browser holding a document written before this landed. Weighed as the asymmetry it is:

| | cost |
|---|---|
| trust the number | the expensive silent failure this entry exists to prevent — and live on the very machine that reported it, since the owner deleted a box 1 and started another this week |
| clear it | one press, once, with a sentence on screen — and the press is the remedy D142 already says the operator *"was about to make"* anyway |

**So it clears.** D142's own rule decides it without needing a new one: a stored number with no id IS *"a guess"*, and that paragraph already says the restore never falls back to one.

**D27's amendment is the precedent for declining a fallback and it is not in tension with this.** There the owner declined a read-time fallback for a renamed key on the ground that *"a fallback can never safely be deleted afterwards"*. This arm has no such problem, and the difference is exact: **it is not a fallback preserving old behaviour, it is the same refusal the unknown-box arm already makes**, self-extinguishing after one pick, and correct whether it is kept for ever or folded into the disagreement arm later.

**It says "cannot tell" and never "your drawer changed"**, because it does not hold that fact. D145 forbids an abstention softening a fact; the same care forbids it hardening into one.

### Where the number stays, and it is one sentence

**The reallocation sentence is the one place on this screen that names a box by NUMBER**: *"Box 3 is a different drawer now — the one you last captured into was deleted, and its number went to this one."* The number is the only thing the two drawers share — it is the thing that was handed over, and the subject of the sentence. Naming the box now at it would tell the operator their drawer is `Epics`, which it has never been. **The other three restore sentences keep `captureBoxLabel`** (name, or number where there is none): each of those is about a box that is, or probably is, theirs.

### The picker stops drawing numbers, and D142's reason survives its own amendment

**The owner, looking at the list:** *"on the capture screen, i shouldn't even need to see box. numbers here, it's waste of space"*. Their screenshot: `WB1 R2  Box 4  next index 679` over `ME01 C/UC  Box 2  Sealed` over an already-ellipsised `UNL BBOX C/UC 1…`.

**D142 argued the picker should keep the number and the argument was right:** *"a row that hid the number would answer a search for `9` with nine rows that do not visibly contain a 9."* **It was spent too widely.** That is a claim about a row's answer to a TYPED NUMBER, and it was applied to every row all of the time, including the resting list the owner was looking at — where nothing has been typed and no row is answering anything.

**So the suffix is drawn exactly where that reason applies**: the query is non-empty and this row is in the list because its NUMBER matched it. Type `9` and every row that matched on a 9 shows the 9. Type `com` and no number appears, because no row matched on one. At rest the list is drawer names. **D145 is why this is givable at all** — with identity moved to `bid`, the number here is a label and a search term, and never the thing that says which drawer this is.

**Three things are deliberately unchanged:**

**Searching by number still works, and the placeholder still says so** — `Name or number`, name first because that is what the rows show and what the operator thinks in, number kept because D20 makes this one control over both and a drawer may have no name at all. A placeholder that stopped saying so would make a working search undiscoverable.

**An unnamed box still draws its number and that is not an exception.** `captureBoxLabel` already puts it in the name's place (D142, D56: a placeholder would draw a fault where there is none). What had to be prevented is the doubling — a suffix beside it reads `Box 6 Box 6` — and the test for it is the TRIMMED name, which is what `captureBoxLabel` itself applies. The old test was `option.name === null`, and a whitespace-only name slipped past it into exactly that doubling.

**Nothing is added to the row, and the space this frees is ATTENTION rather than width.** That distinction was checked against the renders rather than assumed, and the first draft of this paragraph had it wrong: the option row is a grid whose name column is `minmax(0, 1fr)`, so it already takes every pixel the trail does not, and dropping a suffix that sat AFTER the name inside that column moves no boundary. `UNL BBOX C/UC 1…` ellipsises at exactly the same character before and after. **What the number was costing is a second thing to read on every row** — the owner's *"waste of space"* about a list of drawers where one fact identifies each. The row already carries `next index N` or `Sealed`, which is the useful half, and adding anything to a row the operator reads at a feeder's pace would spend the instruction on fresh clutter.

### What is guarded

`app/tests/capture-claims.spec.ts` carries seven new cases and **the fixture's ids are deliberately not its numbers** (boxes 1-4 wear 21-24) — against a fixture where box 2 wears id 2, a case comparing the wrong pair passes. Four are the restore's arms, including the two that stop the guard being vacuous: a box the store still calls the same drawer is KEPT, and a store issuing no ids KEEPS the restore. One asserts the pick records the id, without which every restore falls down the "cannot tell" arm for ever while looking exactly like a working guard. Two are the picker, at rest and under a typed number.

### What would reopen it

**A route that takes an id.** D145 forbids it and this does not ask for one: the comparison happens in the client, against a field that rides along on a record it was already fetching.

**A second operator, or a browser profile shared between rigs.** The setup is one device's memory of one hand (D142). Two hands would make "the drawer I left" a question with two answers, and the id would be comparing against somebody else's pick.

**A drawer whose number the operator does read.** The picker assumes the name is what they recognise — D142's own reopening condition, and this spends it further. If drawers start being named by content and referred to by position, the number comes back to the resting list.