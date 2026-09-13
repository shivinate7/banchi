## D-one-left-edge — A page is anchored to the shell's own inset, and only its width may vary by screen

**The owner's report, 2026-09-13, with three screenshots:** `#/pricing`'s content started
roughly 330px further right than `#/review` and `#/inventory` at the same window width. *"how
this gap and width of screens is variable"* is wrong — the left edge of every owner screen must
be the same, at every width and in both rail states.

**The cause is `app/src/kit.css`'s `.bn-page`.** It read
`max-width: var(--bn-page-max, var(--bn-page-w)); margin: 0 auto;` — and `margin: 0 auto`
CENTERS the page inside the shell's own column, so a screen with a lower cap — Pricing and
`ValueBands` at 1120px, Codes/Home/Orders at `--bn-page-w-rows` (1344px) — sits in the MIDDLE
of the space the shell handed it rather than against its edge, and the gutter that produces
grows with the window and differs between routes. A screen with no cap (the 1600px default) happened to fill enough of the column that
the gap was invisible on the owner's own rig — which is exactly how this went unnoticed through
every 1440px walk this build was verified at.

**The fix is `margin: 0`, never `auto`.** `--bn-page-max` still exists and still does its job —
a pricing table and a three-column inventory legitimately want different caps — but a cap now
narrows the page from a SHARED LEFT INSET instead of centering a shrunken column inside a wider
one. Nothing about `--bn-page-w` or `--bn-page-w-rows` changes; only which edge a narrower cap
gives up moves, from both (centered) to the right one only (anchored left).

**No screen was found relying on the old centering for its own balance.** Every other
`margin: 0 auto` / `margin-inline: auto` in `app/src/*.css` was read (`grep` across the
directory) and each is a CHILD element balanced inside an already-anchored `.bn-page` — an
empty state's own column (`Shipping.css`, `Orders.css`, `ReviewQueue.css`), a deck illustration
(`Home.css`), a modal's own content — never the page root itself, so none of them changes shape
under this fix.

### The guard is `app/tests/page-edge.spec.ts`

Discovers its routes the way `wide.spec.ts` and `button-stack.spec.ts` already do —
`routesFromNav`, never a pinned list — and excludes `#/fulfillment`, which renders no shell at
all (D5) and has no sidebar-anchored column to compare against. At 1440 and 1920, in both rail
states (`banchi.rail`, seeded before first paint for `wide.spec.ts:withRail`'s own reason: a
keypress races the frame being measured), it reads every route's `.bn-page`
`getBoundingClientRect().left` and asserts it equals the first route's (Home's) within 1px. The
assertion is relative rather than a hard-coded pixel, so it stays right as long as one screen is
right, and it needs no re-deriving when the sidebar width or the page padding changes.

**It failed against the tree exactly as reported before the fix**, `#/pricing` and `#/inventory`
disagreeing by roughly the gap the owner's own screenshots showed, and it is green after
`margin: 0` landed — the run and the numbers are in the PR body.

### What this does not reach

**NOT MECHANIZED:** the guard can only compare `.bn-page` roots that render in the fixture
state `app/tests/shell.ts` puts the store in, the same limit `D-equal-width-action-stacks`
already names for its own sweep — a sector or a page shape reachable only behind a different
store shape is unchecked here. And it asserts the LEFT edge only, on purpose: the ruling is
that width may legitimately vary by screen, so a right-edge or overall-width check would be
asserting the defect's opposite as a new rule nobody made.
