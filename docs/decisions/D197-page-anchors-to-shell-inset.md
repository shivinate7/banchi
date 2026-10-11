## D197 — A page anchors to the shell inset

**The owner's report, 2026-09-13, with three screenshots:** `#/pricing`'s content started
roughly 330px further right than `#/review` and `#/inventory` at the same window width. *"how
this gap and width of screens is variable"* is wrong — the left edge of every owner screen must
be the same, at every width and in both rail states.

**The cause is `app/src/kit.css`'s `.bn-page`.** It read
`max-width: var(--bn-page-max, var(--bn-page-w)); margin: 0 auto;`. `margin: 0 auto` CENTERS the page inside the shell's own column. So a screen with a lower cap sits in the MIDDLE of the space the shell handed it, rather than against its edge. Pricing and `ValueBands` are at 1120px, and Codes/Home/Orders are at `--bn-page-w-rows` (1344px). The gutter that produces grows with the window and differs between routes. A screen with no cap (the 1600px default) happened to fill enough of the column that
the gap was invisible on the owner's own rig. That is exactly how this went unnoticed through
every 1440px walk this build was verified at.

**The fix is `margin: 0`, never `auto`.** `--bn-page-max` still exists and still does its job.
A pricing table and a three-column inventory legitimately want different caps. But a cap now
narrows the page from a SHARED LEFT INSET instead of centering a shrunken column inside a wider
one. Nothing about `--bn-page-w` or `--bn-page-w-rows` changes. Only which edge a narrower cap
gives up moves, from both (centered) to the right one only (anchored left).

**No screen was found relying on the old centering for its own balance.** Every other
`margin: 0 auto` / `margin-inline: auto` in `app/src/*.css` was read (`grep` across the
directory). Each is a CHILD element balanced inside an already-anchored `.bn-page`. The examples are an empty state's own column (`Shipping.css`, `Orders.css`, `ReviewQueue.css`), a deck illustration (`Home.css`), and a modal's own content. None is the page root itself, so none of them changes shape under this fix.

### The guard is `app/tests/page-edge.spec.ts`

It discovers its routes the way `wide.spec.ts` and `button-stack.spec.ts` already do. It uses `routesFromNav`, never a pinned list. It excludes `#/fulfillment`, which renders no shell at all (D5). That route has no sidebar-anchored column to compare against. At 1440 and 1920, in both rail states, it reads every route's `.bn-page`
`getBoundingClientRect().left`. It asserts that each equals the first route's (Home's) within 1px. The rail state is seeded before first paint (`banchi.rail`), for `wide.spec.ts:withRail`'s own reason: a keypress races the frame being measured. The assertion is relative rather than a hard-coded pixel. So it stays right as long as one screen is right. It needs no re-deriving when the sidebar width or the page padding changes.

**It failed against the tree exactly as reported before the fix**. `#/pricing` and `#/inventory` disagreed by roughly the gap the owner's own screenshots showed. It is green after `margin: 0` landed. The run and the numbers are in the PR body.

### What this does not reach

**NOT MECHANIZED:** The guard can only compare `.bn-page` roots that render in the fixture
state `app/tests/shell.ts` puts the store in. That is the same limit `D195` already names for its own sweep. A sector or a page shape reachable only behind a different store shape is unchecked here. The guard asserts the LEFT edge only, on purpose. The ruling is that width may legitimately vary by screen. So a right-edge or overall-width check would be asserting the defect's opposite as a new rule nobody made.
