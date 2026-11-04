## DEBT83 — Off-screen rail tiles still cost a little per capture

**What.** With the full rail drawn (not dealing), every tile of the sitting is still built, and each far tile costs two layout objects and its DOM nodes on every capture, so a capture's cost still grows a little with the sitting. A tile out of the rail's view keeps only its row button (`capture-undo-far`), so the layout cost per tile fell from about 20 objects to 2. Style recalculation, the DOM nodes of the tile's `li`, cell and row, and `writeTile` on each tile in view are not removed.

- **Measured limit.** `app/tests/capture-freeze.spec.ts` bounds the layout objects each added tile costs at 3, over captures 21 to 60. Unmeasured: the blocked time per added tile, on the owner's Mac or the CI runner. Before the far class, 60 hand-fed captures cost 174 to 206 ms blocked (first 10 to last 10) at 4x CPU throttle, on the owner's Mac.
- **Not fixed because** the rest of the cost needs the tiles not built at all, and every tile must stay a real row (D164, the undo stack is the sitting): in the tab order, counted by a screen reader, never blank.
- **The fix.** Build only the tiles near the view, with a spacer for the rest, and keep each capture reachable by scroll, Tab and a screen reader. The `capture-undo` cases that count every `.capture-undo-row` re-point to "each capture can be scrolled to".
- **Closes when** the rail builds only nearby tiles, or the blocked time per added tile is measured and found flat.

**Outcome at risk.** On a very long sitting or a slower computer, each capture blocks the screen a little longer than the last.
