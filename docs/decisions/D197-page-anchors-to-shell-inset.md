## D197 — A page anchors to the shell inset

**The owner reported this with three screenshots.** `#/pricing`'s content started about 330px further right than `#/review` and `#/inventory` at the same window width. A gap that varies by screen is wrong. The left edge of every owner screen must match at every width and in both rail states.

**Cause: `app/src/kit.css`'s `.bn-page`** read `max-width: var(--bn-page-max, var(--bn-page-w)); margin: 0 auto;`. `margin: 0 auto` centers the page inside the shell's column. A screen with a lower cap sits in the middle of that space. Pricing and `ValueBands` are 1120px. Codes, Home and Orders are `--bn-page-w-rows` (1344px). The gutter grew with the window and differed by route.

A screen with no cap (the 1600px default) filled the column. So the gap was invisible on the owner's rig and in every 1440px walk.

**Fix: `margin: 0`, never `auto`.** `--bn-page-max` still does its job. A pricing table and a three-column inventory want different caps. A cap now narrows the page from a shared left inset, not from the center. `--bn-page-w` and `--bn-page-w-rows` are unchanged. Only the edge a narrower cap gives up moves: from both (centered) to the right only (anchored left).

**No screen relied on the old centering.** Every other `margin: 0 auto` / `margin-inline: auto` in `app/src/*.css` was read (grep across the directory). Each is a child element balanced inside an anchored `.bn-page`: an empty state's own column (`Shipping.css`, `Orders.css`, `ReviewQueue.css`), a deck illustration (`Home.css`), or a modal's content. None is the page root, so none changes shape under this fix.

### The guard is `app/tests/page-edge.spec.ts`

It discovers its routes as `wide.spec.ts` and `button-stack.spec.ts` do, with `routesFromNav`, never a pinned list. It excludes `#/fulfillment`, which renders no shell (D5). At 1440 and 1920, in both rail states, it reads each route's `.bn-page` `getBoundingClientRect().left`. It asserts each equals Home's within 1px. The rail state is seeded before first paint (`banchi.rail`), for `wide.spec.ts:withRail`'s reason: a keypress races the frame measured. The assertion is relative, not a hard-coded pixel. It holds while one screen is right, and it needs no change when the sidebar width or page padding changes.

**It failed on the tree before the fix**, as reported: `#/pricing` and `#/inventory` disagreed by about the gap in the owner's screenshots. It is green after `margin: 0` landed. The run and numbers are in the PR body.

### What this does not reach

**NOT MECHANIZED:** The guard compares only the `.bn-page` roots that render in the fixture state `app/tests/shell.ts` sets. D195 names the same limit for its sweep. A page shape reachable only behind a different store shape is unchecked. The guard asserts the LEFT edge only, on purpose. Width may vary by screen. A right-edge or width check would add a rule nobody made.
