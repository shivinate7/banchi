## D201 — A route change lands at the top, and a same-path query change does not

**The bug, found live on the phone shell.** Nothing in `App.tsx` or `App.css` ever called
`scrollTo` or set `scrollTop`. `.bn-shell-main` carries no `overflow` rule, so the window is
the one thing that scrolls at every width this shell is verified at (1440, 820, 390 — no
second scroller exists to reset). `.bn-view` remounts on every route change, keyed on `path`,
but a DOM remount does not move the browser's own scroll position — so scrolling `#/capture`
down and then leading to `#/runs`, or tapping `#/inventory` from a scrolled screen, landed on
the new screen already scrolled to wherever the last one had been left. Measured at the rig's
own 390-wide viewport: scrolling Capture to 300px and pressing `,I` for Inventory (122 cards,
reliably taller than the viewport) landed Inventory at `scrollY: 247` rather than `0` —
Runs, under the shared small fixture, draws no run at all and is short enough that the
browser's own scroll clamp reads `0` regardless of whether anything reset it, which is why
the first attempt at this guard passed for the wrong reason and had to be re-pointed at a
route tall enough to prove the fix rather than merely fit the clamp.

**The fix is one hook beside the one already keyed on `path`.** `path` comes from
`currentPath()`, which strips the query string before it is ever compared — `currentPath`
splits on `?` and drops everything after it — so a `useEffect` with `[path]` as its
dependency array fires on `#/capture` -> `#/runs` and does NOT fire on `#/pricing` ->
`#/pricing?band=top`. That second case is D159's own lens: `?band=top|bottom` is a filter
over the same screen, not a different screen, and staleness there is something the operator
dismisses rather than something a navigation clears out from under them. A scroll reset keyed
on the full hash (path + query) would have re-broken exactly the thing D159 built — the
click that opens the band view landing the operator back at the top of a list they were
already reading. Keying on the query-stripped `path` gets both halves of the rule from the
one array `App.tsx` was already using for the drawer/palette/keys-sheet dismissal effect two
lines above it.

**The window is what resets, and that is a fact about this tree, not a shell habit in general.**
A shell that gave its scroll region its own `overflow-y` would need the reset on that element
instead of the window; this one does not, and confirming that before writing the fix — rather
than assuming a "shell main" div is always the scroller — is what the guard's own comment
records for the next screen that DOES grow a second scroller.

### Mechanized

`app/tests/phone.spec.ts` — `leaving a scrolled screen lands the next one at the top`. Scrolls
`#/capture` (found off the drawer's own roster, never a typed hash — `docs-audit`'s `route
rosters` row refuses a third pinned literal in this file) to 300px, confirms the scroll
actually moved, leads to Inventory with `,I`, asserts the document is taller than the
viewport plus the old scroll offset (so a short destination can never pass this by accident
of the browser's own clamp), and asserts `window.scrollY === 0`. Red on the unfixed tree at
`scrollY: 247`; green with the fix. Run through `make design-check`.

### Not mechanized

**Whether a future scroll region needs the same treatment.** If a screen ever gives
`.bn-shell-main` (or any other ancestor of `.bn-view`) its own `overflow-y`, this fix's
`window.scrollTo(0, 0)` stops being the right target and nothing here would say so — the
guard asserts `window.scrollY`, which would silently read `0` forever once the window itself
stopped being the scroller. The comment beside the fix names this as the thing to check first.
