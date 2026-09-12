## D-the-undo-stack-is-the-sitting-not-the-drawer — The undo stack is the sitting, not the drawer, and the counter counts the sitting

**Settled 2026-09-12, out of the unbox-the-pipeline survey, which found it in passing.**
Two figures on the capture screen were filtered by `shot.card.box === box` — the CURRENT value
of the Box field. One of them decides what a keypress DELETES.

`CaptureScreen.tsx` held both:

```ts
const mine = shots.filter((shot) => shot.card.box === box)   // undoStack, and runCount
```

The Box field is one free-text control and changing it is `B`, a digit, Enter.
**Capture-undo deletes the record and the photograph (D10 ruling 1)**, so the first of those
two is not a display defect: the thing offered under `U` was aimed at a drawer the hand had
never been in.

### What was measured, on the owner's own store

Read-only, from a copy of `inventory/store.sqlite`, clustering `captured_at` at
`app/src/storeHistory.ts`'s own `GAP_MINUTES` — the same 30 minutes `#/` draws the library
by (D121). **2,535 stamped cards, ten sittings, two of them across drawers:**

| | when | cards | minutes | drawers |
|---|---|---|---|---|
| S5 | 2026-09-01 16:09 | **555** | **23.9** | 3 → 4 → 5, at 394 / 56 / 105 |
| S10 | 2026-09-11 16:42 | **536** | **46.2** | 4 → 1, at 214 / 322 |

**1,091 of 2,535 cards — 43% of the store — sat in a multi-drawer sitting.**
Through S5 the "captured" stat read **394 → 0 → 56 → 0 → 105**; through S10, **214 → 0 → 322**.

**The hiding is measured at 3 of 3 switches.** 394, 56 and 214 shots left the undo stack at
the instant the field changed — **664 photographs** that had been one keypress from a
correction and then were reachable by no control on the screen.

**The sharper arm has not fired on this store, and that is luck rather than design.** All
three real switches went to a drawer that was empty, so the fall-through offered nothing.
Switch instead to a drawer already fed — a top-up, which is most of what a second drawer is
for — and `serverNewest` offered ITS high-water card, labelless, for `U` to delete.
**Box 2 has stood at #543 through nine consecutive sittings**, 6 to 19 days old, with exactly
that exposure; by S7 a switch to any of boxes 2, 3 or 5 would have done it.
**No card is claimed to have been lost here.** What the store shows is nine separate occasions
on which one keystroke would have lost one, with no guard between.

### What is built

1. **A sitting, and it is not a new definition.** `Shot` carries `at` — `Date.now()` when the
   capture response landed, the only field on it the server has no opinion about — and
   `sitting` is the tail of `shots` after the last gap longer than `GAP_MINUTES`, imported
   from `storeHistory.ts` rather than restated.

   **"Since this screen loaded" was the alternative and it is very nearly the same thing**,
   because `shots` is already only what this browser took. They part on one case: a screen
   left open overnight, where the load time would count yesterday's drawer as part of this
   morning's work and put a card from it under `U`. One subtraction per shot removes that, and
   the more important half is this:
   **a word this product already defines does not get a second definition on one screen.**
   Two spellings of "sitting" is how `#/` and `#/capture` come to disagree about what the
   operator just did.

   **What it costs on a reload is the whole sitting**, and that is today's behaviour unchanged:
   `shots` is memory. The undo stack's blind arm is what covers a reload, below.

2. **The stack is the sitting's own shots, newest first, whatever drawer they went in** —
   capped at `UNDO_DEPTH` as before. Not "reset the stack on a box change", which hides the
   card just shot instead of offering it. `Box 3 · 412` and `Box 4 · 1` sit adjacent, which is
   what actually happened.

3. **Every row names its drawer when what is IN VIEW spans more than one**, and then every
   row, not only the rows that differ from the Box field — a label on some rows makes the
   unlabelled ones read as "the current drawer", which is the exact inference the filter
   invited. The label is `Box 3` and not `B3`: the figure beside it is a COUNT out of a
   rendered label, and `B3 #40` would be the key spelling wearing a count, which is the one
   confusion D92 exists to end. **The accessible name needed nothing** — `positionText` is the
   server's own `Box 3 · Section 1 · Card 40` and has always named the drawer. This is the
   visible half catching up with what a screen reader was already told.

4. **The odometer counts the sitting, with the per-drawer split beneath it** —
   `Box 3 394 · Box 4 56 · Box 5 105`, ordered by when the hand first opened each drawer, the
   current one marked. **The span and the gap count stay in ONE drawer's index space**, because
   that is the only space either means anything in: box 3 #394 beside box 4 #1 is not a span of
   1–394, and the subtraction that finds a hole would report 337 of them. `span` is the current
   drawer's; `gaps` is summed per drawer, so
   **a hole left behind in box 3 is still on screen after the hand has moved to box 5** —
   which the old per-box figure could not do either.
   `ids` is counted over the whole sitting, because a `capture_id` is per photograph.

### The walk is still correct across drawers, and this is the load-bearing property

`undoBack` walks its plan in order and the route **removes only the newest card in a box**,
refusing anything else (D10, `server/capture_server.py`). Reverse-chronological over the
sitting preserves reverse-chronological WITHIN each drawer, so every target is still its own
box's newest when it is reached: `B4 #2, B4 #1, B3 #411, B3 #410` is four legal deletes in
that order. A target that is not the newest earns a refusal naming the one that is —
`undoBack` already renders exactly that — and never a mid-box delete.

**A stack that sorted itself would break this**, and the spec is built to see that: the
cross-drawer case runs the owner's own S10 shape, box 4 THEN box 3, because ascending
(S5's 3 → 4 → 5) is the one shape where the hand's order and a sort by box number agree.
Mutation-tested — sorting by `(box, index)` survived the ascending case and is killed by the
descending one.

### What is given up, named rather than discovered

**The blind arm is kept and narrowed to an empty sitting.** Its job, in its own words, is a
card captured before this session loaded: with no shots in hand there is nothing else to offer
and the server's high-water mark is the honest answer, which is what covers a reload. With
shots in hand that job is done by the shots.

What that gives up is one case:
**another device writing into the drawer this one is shooting.** The head is then this hand's
card, the server refuses it, and the note says which position is undoable.
**That is a loud wrong answer in place of a quiet deletion of a card this operator never took**
— and the store is shared by two devices (D13), so this is a real trade, not a hypothetical.

### D118, and where the drawer label had to go

**The label lives in `.capture-undo-pos`, which is already absolute** against the thumbnail
(`left: 0; right: 0; bottom: 0`), so a second line grows UPWARD over the photograph and
reaches no layout — the cell's height is the thumbnail's `aspect-ratio`. The existing comment
there already sanctions covering more photograph for a wrapped caption; this is the same
bargain. The caption's gradient gained a third stop, because at two lines the drawer name sat
in the faint half of a ramp built for one.

**The split line is floored by `min-height` and always rendered**, so the first capture of a
sitting adds a figure to a line that was already there rather than pushing the viewfinder
down. Measured in the browser at all three widths: the owner's worst real case — three
drawers, `Box 3 394 · Box 4 56 · Box 5 105` — is **189px against 313px available at 390**, one
line, 17px, everywhere. A fourth drawer in one sitting would wrap; they have never opened one.

### What this does not touch

The camera, `useCamera.ts`, the motion trigger, the cadence trigger, and anything that runs
per frame. `sitting` and `runCount` recompute when `shots` changes — once per capture, 623 ms
apart at the rig's measured cadence, over a list one sitting long.

### The guard

`app/tests/capture-undo.spec.ts`, five new cases on the file's existing sealed fixture with a
second drawer added, **every one observed to fail against the old code before it was kept**.
Seven mutation arms, all killed: the box filter back on the stack; the box filter back on the
counter; the blind arm widened with sitting order kept; the drawer label dropped; the stack
sorted by drawer; the split's reserved height removed; the drawer label moved into normal
flow. Two of those arms survived the first draft of the spec and are the reason the fixture
now runs a DESCENDING drawer order and measures the split from zero captures — a sweep that
goes green because the fixture never reached the state is this repo's standing trap.
