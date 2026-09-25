## 36 — The rail collapses a task after a resize, and a layout read taken inside that window is wrong

**What the PR 2 CI trace showed.** On 2026-09-25, `capture-claims.spec.ts`'s "a set hint that
names no set never clips its sub-line" case went red once on the Ubuntu runner (run
36197492833, shard 1). It passed on every local run and on the re-run. At 820px, the trace's
screencast frames show the sidebar still shrinking toward the rail while the case read its boxes.
The case read the row, then its value, about 200ms after the resize. Between the two reads the
main column narrowed and the stack card above the row reflowed. So the value read 25px above
its own row.

**The mechanism.** A resize across 1280px does not collapse the shell at once. `App.tsx`'s
`useRailNarrow` hears the `matchMedia` change and sets React state, so `data-rail` flips one
task later. Then `.bn-shell` animates `grid-template-columns` over `--bn-t-slow`. So for a few
hundred milliseconds after a resize, every column below the shell is still changing width. A
test that reads two boxes in two calls inside that window can see two different layouts.

**What was done.** The case now measures the settled layout. It turns on reduced motion (base.css
ends every transition at once). It reads the row, the value and the sub-line in ONE `evaluate`, so
all three come from one frame. It waits until two reads in a row agree. Its assertions did not
change.

**What was not done, and why.** The shell still collapses through React state and a transition.
That is correct for a person: the layout it settles on is right, and the move is the rail's own
designed motion. A CSS-only default for the rail would remove the one-task gap. It would also
split the rail's state between CSS and `storedRail()`, which is the thing `readRail`'s comment
argues against. Any other spec that resizes across 1280px and then reads layout in more than one
call can still see this window. Such a spec should read in one frame, after the layout holds still.
