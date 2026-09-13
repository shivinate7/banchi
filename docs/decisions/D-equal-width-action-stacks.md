## D-equal-width-action-stacks — Same-role buttons stacked in one sector share a width, and a Playwright sweep finds them rather than reading a declared class

**The owner's ruling, 2026-09-13:** *"Buttons should be the same sizes if they're in the same
sort of sector — make this a guard and correct any/all instances across the app."* Read beside
D50: it is a fourth thing `base.css` cannot supply, the same shape as D118's stability floor —
a rule about the relationship between controls rather than about any one control's own paint,
so a stylesheet cannot carry it and a guard has to look at the rendered page.

**A SECTOR is a panel, not the page**, and the rule binds only buttons of the SAME ROLE —
identical `Button` variant and size — that are STACKED vertically inside it. A primary beside a
ghost Cancel is two roles and exempt; a horizontal row is exempt; `.bn-btn-block` is already
full-width and therefore already equal. The width every member takes is the WIDEST sibling's
own intrinsic (label + padding) width — never the sector's full width, never a hard-coded
pixel — left-aligned within the sector, on the platform convention an equal-width action stack
already follows elsewhere (Apple HIG / SwiftUI's equal-width button stacks, Firefox's Acorn
design system).

### The mechanism is one CSS Grid trick, in two shapes

**A single `max-content` grid column is sized by its widest child**, and every other child in
that column is told to fill it. That is the whole mechanism — no JS measuring, no
`ResizeObserver`, nothing that runs after paint.

`app/src/kit.css`'s `.bn-actions-stack` is the wrapper form, for buttons that can share one
parent: `display: inline-grid; grid-template-columns: max-content;` with `justify-self:
stretch` on every child.

`app/src/CaptureScreen.css`'s `.capture-block-list` is the cross-row form, for the capture
prerequisites block where each button lives in its own `<li class="capture-block-row">`
alongside an icon and a sentence. The `<li>` is `display: contents`, which dissolves its own
box and hands its children — the icon, the sentence, the fix button — to the LIST's grid as if
they were its own direct children, sharing one `max-content` column (column 2) across every
row. Per CSS Grid §12.5, an item spanning a flexible (`1fr`) track is skipped when the browser
sizes a `max-content` track, so a sentence spanning columns 2–3 (to run the full row width when
its blocker has no fix) does not inflate column 2 — only the buttons that sit in column 2 alone
do, and column 2 is sized by them.

Both shapes were mutation-tested against the live block on 2026-09-13: a `.bak`-protected copy
of `kit.css` with `.bn-actions-stack`'s `justify-self: stretch` deleted, and of
`CaptureScreen.css` with `.capture-block-fix`'s `justify-self` reverted to `start`, turned the
capture block's own two fix buttons unequal — "Open the camera" 147.3px against "Pick a box"
107.0px — and `make design-check PW_ARGS=tests/button-stack.spec.ts` went red on exactly that
sector. Restoring both files from the `.bak` copies turned it green again.

### The guard is `app/tests/button-stack.spec.ts`, and it discovers its subjects

The same argument `cursor.spec.ts` already makes about controls and `routesFromNav` already
makes about routes: a guard that only checks a `.bn-actions-stack` someone remembered to wrap
is blind to the exact case the owner pointed at — a stack built with no wrapper at all. So the
spec sweeps every rendered `.bn-btn` on every route `routesFromNav` discovers, groups by the
nearest sector ancestor (`.bn-panel`, `.bn-well`, `.bn-sheet`, `.bn-dialog`, `[role=group]`,
`section`, `.capture-block`, `.bn-empty`) and by the FULL set of `bn-btn-*` classes each member
carries — not a hand-typed roster of variants, which folded a quiet Close beside a plain Reload
into one group on #/gallery the first time this ran, because `bn-btn-quiet` was missing from a
list that should never have existed — keeps groups of two or more whose members are vertically
stacked with left edges within 1px, and asserts every member's width equals the group's widest
within 1px.

### What this does not reach

**NOT MECHANIZED, the part D50 and D118 both leave open too:** the guard can only compare
buttons that render together in the fixture state `app/tests/shell.ts` puts the store in.
A sector reachable only behind a different store shape (a populated run, an answered queue, a
box with claims) is unchecked by this guard exactly as `cursor.spec.ts`'s header already names
for its own sweep, and closing that gap needs the same per-screen fixtures that entry already
asks for.
