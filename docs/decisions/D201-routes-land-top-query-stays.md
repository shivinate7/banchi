## D201 — Routes land at top; query changes stay

**The bug, found live on the phone shell.** Nothing in `App.tsx` or `App.css` ever called
`scrollTo` or set `scrollTop`. `.bn-shell-main` carries no `overflow` rule, so the window is
the one thing that scrolls at every width this shell is verified at (1440, 820, 390). No second
scroller exists to reset. `.bn-view` remounts on every route change, keyed on `path`. But a DOM
remount does not move the browser's own scroll position. Scrolling `#/capture` down and then
leading to `#/runs` landed on the new screen already scrolled to wherever the last one had been
left. So did tapping `#/inventory` from a scrolled screen. Measured at the rig's own 390-wide
viewport, scrolling Capture to 300px and pressing `,I` for Inventory landed Inventory at
`scrollY: 247` rather than `0`. Inventory has 122 cards, reliably taller than the viewport.
Runs, under the shared small fixture, draws no run at all. It is short enough that the browser's
own scroll clamp reads `0` regardless of whether anything reset it. That is why the first attempt
at this guard passed for the wrong reason. It had to be re-pointed at a route tall enough to prove
the fix rather than merely fit the clamp.

**The fix is one hook beside the one already keyed on `path`.** `path` comes from
`currentPath()`, which strips the query string before it is ever compared. `currentPath`
splits on `?` and drops everything after it. So a `useEffect` with `[path]` as its dependency
array fires on `#/capture` -> `#/runs`. It does NOT fire on `#/pricing` -> `#/pricing?band=top`.
That second case is D277's own lens. `?band=top|bottom` is a filter over the same screen, not a
different screen. Staleness there is something the operator dismisses, rather than something a
navigation clears out from under them. A scroll reset keyed on the full hash (path + query) would
have re-broken exactly the thing D277 built. The click that opens the band view would land the
operator back at the top of a list they were already reading. Keying on the query-stripped
`path` gets both halves of the rule. It reuses the one array that `App.tsx` already uses for the
drawer/palette/keys-sheet dismissal effect two lines above it.

**The window is what resets, and that is a fact about this tree, not a shell habit in general.**
A shell that gave its scroll region its own `overflow-y` would need the reset on that element
instead of the window. This one does not. The guard's own comment records the confirmation for
the next screen that DOES grow a second scroller. The confirmation was made before writing the
fix, rather than assuming a "shell main" div is always the scroller.

### Mechanized

`app/tests/phone.spec.ts` — `leaving a scrolled screen lands the next one at the top`. It scrolls
`#/capture` to 300px. The test finds `#/capture` off the drawer's own roster, never a typed hash.
`docs-audit`'s `route
rosters` row refuses a third pinned literal in this file. It confirms the
scroll actually moved. It leads to Inventory with `,I`. It asserts the document is taller than the
viewport plus the old scroll offset. A short destination can never pass this by accident of the
browser's own clamp. It asserts `window.scrollY === 0`. Red on the unfixed tree at `scrollY: 247`;
green with the fix. Run through `make design-check`.

### Not mechanized

**Whether a future scroll region needs the same treatment.** If a screen ever gives
`.bn-shell-main` (or any other ancestor of `.bn-view`) its own `overflow-y`, this fix's
`window.scrollTo(0, 0)` stops being the right target. Nothing here would say so. The guard
asserts `window.scrollY`, which would silently read `0` forever once the window itself stopped
being the scroller. The comment beside the fix names this as the thing to check first.
