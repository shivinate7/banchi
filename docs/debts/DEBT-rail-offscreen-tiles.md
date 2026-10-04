## DEBT-rail-offscreen-tiles — Off-screen rail tiles still cost a little per capture

**With the full rail drawn (not dealing), each capture costs slightly more as the sitting grows.** Every tile stays in the DOM, and the browser re-lays and re-paints the whole grid when a tile lands. `content-visibility: auto` skips none of them, because Chrome judges it against the page viewport and not the rail's scroller.

- **Measured limit.** On the owner's Mac, 60 hand-fed captures cost 174 to 206 ms blocked (first 10 to last 10) at 4x CPU throttle, and 369 to 463 ms at 8x. About 8 ms of growth at full speed. On the CI runner, 590 to 928 ms. JS time is flat. The growth is layout, style and paint: the visible area filling, which saturates near 20 tiles, plus 50 to 70 ms at 8x from off-screen tiles.
- **Not fixed because the owner deferred it.** The freeze case compares captures 21 to 30 with the last 10, so the fill-up is not counted as growth.
- **The fix.** Build only the tiles near the view, with a spacer for the rest. Every capture stays reachable by scroll (D164, the undo stack is the sitting). The `capture-undo` cases that count every `.capture-undo-row` re-point to "each capture can be scrolled to".
- **Closes when** the rail builds only nearby tiles and the freeze case passes against the first 10 again.

**Outcome at risk.** On a very long sitting or a slower computer, each capture blocks the screen a little longer than the last.
