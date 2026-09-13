## D204 — The phone drawer's nav scrolls in the space above its foot, for any row count, and the CSS says so explicitly rather than relying on it

**The report:** on a phone, the More drawer's footer block (`.bn-side-foot`: Cards to pull, the
theme toggle, the server line) sits on the row Codes renders in — the last row of the last nav
group — so Codes cannot be tapped. Plan `2-bugs.md` item 4 named the cause as probable rather
than confirmed and asked for a live `elementFromPoint` check before anything else.

**The owner's ruling: drawer fix only.** Codes does not get a tab-bar slot and the five-slot bar
is unchanged; whatever the drawer needs, it gets inside the drawer.

### What was confirmed, and what was not

`elementFromPoint` at the Codes row's own centre, and a real `.click()`, were run against the
UNCHANGED tree across every phone height this file's own comments name as a boundary — 844,
812, 780, 754, 753, 740, 722, 700, 667, 640, 620, 600, 577 — in Chromium (both a live browser and
`npx playwright test`, the engine `make design-check` actually runs), and again under WebKit with
`devices['iPhone 13']` after installing it for the purpose. Every one of those 24 runs resolved
Codes and navigated to `#/codes`. `env(safe-area-inset-top)` was also forced to 59px (an iPhone
with a Dynamic Island) by overriding `.bn-drawer`'s computed padding-top directly, at the 754px
breakpoint — still no overlap.

**This is not because the layout happens to be safe by luck.** `.bn-nav` is `flex: 1 1 auto`
inside `.bn-drawer`'s flex column, with `overflow-y: auto`; per the flexbox spec, a flex item's
automatic minimum size resolves to 0 on an axis where its own `overflow` is not `visible` — which
this already satisfies — so `.bn-nav` is capped at its flex-computed box and `.bn-side-foot`,
its sibling, is a normal block below it. Two mutations proved the harness that checks this has
real teeth: removing `overflow-y: auto` from `.bn-nav` alone did NOT reproduce the bug (scrolling
just moved to the outer `.bn-sheet`, which also clips correctly); giving `.bn-side-foot`
`position: absolute; bottom: 0` DID — the guard below caught it immediately, naming the exact
route and the exact element sitting over it.

**So the literal defect could not be reproduced with the tools available in this session.** It
may be a real device/WebKit quirk this environment's WebKit (no OS chrome, no dynamic toolbar)
cannot recreate, or the plan's diagnosis may have been wrong about where the overlap comes from.
Either way, per CLAUDE.md's own instruction to CONFIRM live rather than assume, that is reported
here rather than papered over with a fabricated red run.

### What was built anyway, and why it is not a bandaid

The fix is real hardening, not a hand-typed pixel count reacting to a row count:

- `.bn-nav { min-height: 0; }` is now explicit. It changes no rendering today (the browser
  already resolves it), but it removes this layout's correctness from an implicit spec
  resolution that a documented class of cross-engine flexbox bugs gets wrong — exactly the shape
  a nested `overflow: auto` inside a `position: fixed` ancestor is.
- `--bn-drawer-foot-h`, on `.bn-drawer`, is the foot's own fixed height — three 44px rows plus
  their gaps, padding and border. This is a property of the FOOT (how many rows it draws), never
  of the nav (how many routes exist), so it does not need to be re-derived when a route is added
  — unlike the two breakpoint steps below it in `App.css`, which are cosmetic row-count
  arithmetic and are now commented as such. `.bn-drawer .bn-nav` reads it via
  `scroll-padding-bottom`, so a programmatic scroll (a jump key, a focus move) lands with a hair
  of daylight above the foot rather than flush on the boundary.
- The two existing breakpoint comments (754px, 820px) are amended in place to say what they now
  are: they trade fewer visible rows for a shorter list, never reachability. Reachability is the
  guard's job.

### Mechanized

`app/tests/phone.spec.ts`, `every drawer route is reachable by tap, at two phone heights` — run
by `make design-check`. It harvests the roster off the drawer's own DOM (`phoneRoutes`, already
used by this file, never a hand-typed list — `route rosters`' own rule), so a route added to
`ROUTES` tomorrow is swept automatically. At 390x844 and 360x780 it opens the drawer, and for
every owner route: scrolls the link into view inside `.bn-nav`, asserts `elementFromPoint` at the
link's own centre does not resolve inside `.bn-side-foot`, then performs a real `.click()` and
asserts the hash changed. Mutation-tested: forcing `.bn-side-foot` to `position: absolute;
bottom: 0` turns it red, naming `#/codes at 390x844: the drawer's foot (DIV.bn-side-foot) sits
over this row's centre`; reverting the mutation turns it green again. Removing `overflow-y: auto`
from `.bn-nav` alone does not turn it red (see above) — this guard is honest that it did not
independently discover the original report's root cause, only that it can catch the failure
shape described.

### Not mechanized

**Whether the original report describes a real device-only bug.** No tool available in this
session can emulate mobile Safari's dynamic toolbar or `env(safe-area-inset-*)` from actual OS
chrome; WebKit-the-engine without WebKit-the-browser-shell reports 0 for both. If this recurs on
the rig, the next session's first move should be the walker's own trace (a DOM dump plus
`elementFromPoint` taken ON the device, not emulated), not another round of viewport guessing.
