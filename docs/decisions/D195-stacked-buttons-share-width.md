## D195 — Stacked same-role buttons share a width

**Ruling: buttons of the same role in the same sector share a width. Make it a guard, and correct every instance in the app.** Read beside D50, this is a fourth thing `base.css` cannot supply. It has the same shape as D118's stability floor. It is a rule about the relationship between controls, not about one control's paint. So a stylesheet cannot carry it. A guard has to look at the rendered page.

**A SECTOR is a panel, not the page.** The rule binds only buttons of the SAME ROLE: identical `Button` variant and size, stacked vertically inside the sector. A primary beside a ghost Cancel is two roles, so it is exempt. A horizontal row is exempt. `.bn-btn-block` is already full-width, so it is already equal. Every member takes the WIDEST sibling's intrinsic width (label plus padding). It is never the sector's full width, and never a hard-coded pixel. It is left-aligned within the sector. Apple HIG, SwiftUI's equal-width button stacks and Firefox's Acorn design system follow the same convention.

### The mechanism is one CSS Grid trick, in two shapes

**A single `max-content` grid column is sized by its widest child.** Every other child in that column fills it. That is the whole mechanism. There is no JS measuring, no `ResizeObserver`, and nothing that runs after paint.

`app/src/kit.css`'s `.bn-actions-stack` is the wrapper form, for buttons that share one parent. It uses `display: inline-grid; grid-template-columns: max-content;`, with `justify-self: stretch` on every child.

`app/src/CaptureScreen.css`'s `.capture-block-list` is the cross-row form, for the capture prerequisites block. Each button lives in its own `<li class="capture-block-row">`, beside an icon and a sentence. The `<li>` is `display: contents`, so its box dissolves. Its children join the LIST's grid. They share one `max-content` column (column 2) across every row. A browser skips an item that spans a flexible (`1fr`) track when it sizes a `max-content` track. Per CSS Grid §12.5, a sentence spanning columns 2–3 does not inflate column 2. It runs the full row width when its blocker has no fix. Only buttons alone in column 2 do inflate it, and column 2 is sized by them.

Both shapes were mutation-tested against the live block, each on a `.bak`-protected copy. One copy of `kit.css` had `.bn-actions-stack`'s `justify-self: stretch` deleted. One copy of `CaptureScreen.css` had `.capture-block-fix`'s `justify-self` reverted to `start`. Together they made the capture block's two fix buttons unequal: "Open the camera" 147.3px against "Pick a box" 107.0px. `make design-check PW_ARGS=tests/button-stack.spec.ts` went red on exactly that sector. Restoring both files from the `.bak` copies turned it green.

### The guard is `app/tests/button-stack.spec.ts`, and it discovers its subjects

The argument `cursor.spec.ts` makes about controls, and `routesFromNav` makes about routes, applies here. A guard that checks only a `.bn-actions-stack` someone remembered to wrap is blind to the exact case the owner pointed at: a stack built with no wrapper.

So the spec sweeps every rendered `.bn-btn` on every route `routesFromNav` discovers. It groups each button by its nearest sector ancestor. Those are `.bn-panel`, `.bn-well`, `.bn-sheet`, `.bn-dialog`, `[role=group]`, `section`, `.capture-block` and `.bn-empty`. It also groups by the FULL set of `bn-btn-*` classes each member carries. It uses no hand-typed roster of variants. A roster once folded a quiet Close beside a plain Reload into one group on #/gallery, because `bn-btn-quiet` was missing from the list.

It keeps groups of two or more whose members are vertically stacked with left edges within 1px. It asserts every member's width equals the group's widest within 1px.

### What this does not reach

**NOT MECHANIZED, the gap D50 and D118 also leave open:** the guard compares only buttons that render together in the fixture state `app/tests/shell.ts` sets. A sector reachable only behind another store shape goes unchecked. Examples are a populated run, an answered queue, or a box with claims. `cursor.spec.ts`'s header names the same gap. Closing it needs the per-screen fixtures that entry asks for.
