## 36 — A layout read taken while the page still moves is wrong

A spec that reads a layout in two calls while the page is still moving can see two layouts. Two CI reds had this shape, and neither was a product defect.

- **The shell collapses a task after a resize.** A resize across 1280px flips `data-rail` one React task later (`App.tsx`'s `useRailNarrow`), then `.bn-shell` animates `grid-template-columns` over `--bn-t-slow`. For a few hundred milliseconds every column below the shell changes width. The `capture-claims.spec.ts` case for a set hint that names no set now turns on reduced motion, reads row, value and sub-line in one `evaluate`, and waits for two equal reads. Any other spec that resizes across 1280px and reads layout in more than one call can still see the window. A CSS-only rail default would remove the gap, at the cost of splitting the rail's state between CSS and `storedRail()`.
- **A click's own scroll moves a sticky rail.** When Playwright scrolls to reach a button, the sticky walk rail slides. A spec that asserts D118 reads its "before" after every scroll the test itself causes. `inventory.spec.ts`'s sale case now brings Mark sold into view first.

**Outcome at risk.** A correct layout reads as broken on the runner only.

**Closes when.** Every spec that resizes across 1280px reads in one frame after the layout holds still.
