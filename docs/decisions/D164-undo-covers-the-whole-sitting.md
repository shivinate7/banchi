# D164 — Undo covers the whole sitting

**Two figures on the capture screen were filtered by `shot.card.box === box`.** That compares against the CURRENT value of the Box field. One of the two decides what a keypress DELETES.

`CaptureScreen.tsx` held both:

```ts
const mine = shots.filter((shot) => shot.card.box === box)   // undoStack, and runCount
```

The Box field is one free-text control. Changing it takes `B`, a digit, and Enter. **Capture-undo deletes the record and the photograph (D10 ruling 1).** So the first of those two figures is not a display defect. The card offered under `U` could belong to a drawer the hand had never been in.

### What was measured, on the owner's store

Read-only, from a copy of `inventory/store.sqlite`. It clusters `captured_at` at `app/src/storeHistory.ts`'s own `GAP_MINUTES`. That is the same 30 minutes `#/` uses to draw the library (D121). **2,535 stamped cards, ten sittings, two of them across drawers:**

| sitting | cards | minutes | drawers |
|---|---|---|---|
| S5 (16:09) | **555** | **23.9** | 3 → 4 → 5, at 394 / 56 / 105 |
| S10 (16:42) | **536** | **46.2** | 4 → 1, at 214 / 322 |

**1,091 of 2,535 cards, 43% of the store, sat in a multi-drawer sitting.** Through S5 the "captured" stat read **394 → 0 → 56 → 0 → 105**. Through S10 it read **214 → 0 → 322**.

**The hiding is measured at 3 of 3 switches.** 394, 56 and 214 shots left the undo stack at the instant the field changed. That is **664 photographs** that had been one keypress from a correction. After the switch, no control on the screen could reach them.

**The sharper arm has not fired on this store, and that is luck, not design.** All three real switches went to an empty drawer, so the fall-through offered nothing. Switch to a drawer that is already fed instead. A top-up is most of what a second drawer is for. Then `serverNewest` offers that drawer's high-water card, with no label, for `U` to delete. **Box 2 has stood at #543 through nine consecutive sittings**, each 6 to 19 days old, with exactly that exposure. By S7, a switch to any of boxes 2, 3 or 5 would have triggered it.

**No card is claimed to have been lost.** The store shows nine occasions on which one keystroke would have lost one card, with no guard between.

### What is built

1. **A sitting is an existing definition, not a new one.** `Shot` carries `at`. That is `Date.now()` when the capture response arrived, and it is the only field the server has no opinion about. `sitting` is the tail of `shots` after the last gap longer than `GAP_MINUTES`. It is imported from `storeHistory.ts`, not restated.

   **"Since this screen loaded" was the alternative, and it is nearly the same.** `shots` already holds only what this browser took. The two differ in one case: a screen left open overnight. The load time would then count yesterday's drawer as part of this morning's work. One subtraction per shot removes that. The stronger reason is that one screen should not hold a second definition of a word the product already defines. Two spellings of "sitting" would let `#/` and `#/capture` disagree about what the operator just did.

   **A reload costs the whole sitting.** That is today's behavior, unchanged. `shots` is memory. The undo stack's blind arm covers a reload, as described below.

2. **The stack is the sitting's own shots, newest first, whatever drawer they went in.** It is not capped at `UNDO_DEPTH` as before. It is not reset on a box change, because that would hide the card just shot instead of offering it. `Box 3 · 412` and `Box 4 · 1` sit next to each other, which is what happened.

3. **Every row names its drawer when the rows in view span more than one.** Then every row gets the drawer name, not only the rows that differ from the Box field. A label on some rows makes the unlabelled rows read as "the current drawer", which is the inference the filter invited. The label is `Box 3`, not `B3`. The figure beside it is a COUNT out of a rendered label. `B3 #40` would be the key spelling wearing a count. That is the one confusion D92 exists to end. The accessible name needed no change. `positionText` is the server's own `Box 3 · Section 1 · Card 40`, and it has always named the drawer. The visible label now matches what a screen reader already hears.

4. **The odometer counts the sitting, with the per-drawer split beneath it.** It reads `Box 3 394 · Box 4 56 · Box 5 105`, ordered by when the hand first opened each drawer, with the current one marked. **The span and the gap count stay in ONE drawer's index space.** That is the only space either one means anything in. Box 3 #394 beside box 4 #1 is not a span of 1 to 394. A subtraction that finds a hole would report 337 holes that do not exist. `span` belongs to the current drawer. `gaps` is summed per drawer. So **a hole left in box 3 stays on screen after the hand moves to box 5**. The old per-box figure could not do that either. `ids` is counted over the whole sitting, because a `capture_id` is per photograph.

### The walk stays correct across drawers, and this is the load-bearing property

`undoBack` walks its plan in order. The route **removes only the newest card in a box**, and refuses anything else (D10, `server/capture_server.py`). Reverse-chronological order over the sitting keeps reverse-chronological order inside each drawer. So every target is still the newest in its own box when it is reached. `B4 #2, B4 #1, B3 #411, B3 #410` is four legal deletes in that order. A target that is not the newest earns a refusal that names the card that is. `undoBack` already shows that refusal. It never does a mid-box delete.

**A stack that sorted itself would break this, and the spec checks for it.** The cross-drawer case uses the owner's S10 shape: box 4, then box 3. Ascending order would not catch a bad sort, because the hand's order and a sort by box number agree there. Mutation-tested: sorting by `(box, index)` survived the ascending case and fails the descending one.

### What is given up, named

**The blind arm is kept, and it is narrowed to an empty sitting.** Its job is to cover a card captured before this session loaded. With no shots in hand, nothing else can be offered. The server's high-water mark is the honest answer, and it covers a reload. With shots in hand, the shots do that job.

What that gives up is one case: **another device writing into the drawer this one is shooting.** The head is then this hand's card. The server refuses it, and the note says which position is undoable. A loud wrong answer replaces a quiet deletion of a card this operator never took. The store is shared by two devices (D13), so this is a real trade.

### D118, and where the drawer label goes

**The label sits in `.capture-undo-pos`, which is already absolute** against the thumbnail (`left: 0; right: 0; bottom: 0`). A second line grows UPWARD over the photograph and reaches no layout. The cell's height comes from the thumbnail's `aspect-ratio`. The existing comment there already allows more photograph to be covered for a wrapped caption. This is the same trade. The caption's gradient gained a third stop. At two lines, the drawer name fell in the faint half of a ramp built for one line.

**The split line has a `min-height` and is always rendered.** So the first capture of a sitting adds a figure to a line that already exists. It does not push the viewfinder down. Measured in the browser at all three widths, the worst real case is three drawers: `Box 3 394 · Box 4 56 · Box 5 105`. It measures **189px against 313px available at 390**, on one line of 17px at every width. A fourth drawer in one sitting would wrap. No sitting has had one yet.

### What this does not touch

The camera, `useCamera.ts`, the motion trigger, the cadence trigger, and everything that runs per frame. `sitting` and `runCount` recompute when `shots` changes. That is once per capture, 623 ms apart at the rig's measured cadence. The list is one sitting long.

### The guard

`app/tests/capture-undo.spec.ts` has five new cases on the file's existing sealed fixture, with a second drawer added. **Each case was seen to fail against the old code before it was kept.** Seven mutation arms were killed:

- the box filter restored on the stack;
- the box filter restored on the counter;
- the blind arm widened with sitting order kept;
- the drawer label dropped;
- the stack sorted by drawer;
- the split's reserved height removed;
- the drawer label moved into normal flow.

Two arms survived the first draft of the spec. That is why the fixture now runs a DESCENDING drawer order and measures the split from zero captures. A sweep that passes because the fixture never reaches the state it tests is this repo's standing trap.

### Amended: the stack is the whole sitting, with no cap of ten

The owner's ruling was to switch all five cases, the recommended option. The sentence "capped at `UNDO_DEPTH` as before" no longer holds. The capture strip lists every card of the sitting. The owner's own example needs capture 24 from capture 36, which is thirteen deep. Undo lasts until the sitting ends or a run identifies the card. `docs/specs/undo.md` section 11 is the plan, and UN-1 builds it.
