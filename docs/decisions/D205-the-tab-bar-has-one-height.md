## D205 — The phone tab bar has one height, and every layout that leaves room for it reads the same name

**Measured 2026-09-13, closing plan item 3 of the wave-1 bug batch.** The capture screen's
shutter sat half under the phone tab bar on first paint at 390 wide. `CaptureScreen.css`
sized `.capture-stage` off a hand-written 356px budget whose own comment counted the tab bar
as a flat 64px; the real bar is `calc(64px + env(safe-area-inset-bottom))` (`App.css`, where
`.bn-tabbar` and `.bn-shell-main`'s clearance padding are both sized) — ~98px on every phone
with a home indicator, which is every phone this product ships to. The same
`calc(64px + env(safe-area-inset-bottom))` was ALREADY WRITTEN TWICE in `App.css` before this
— once for `.bn-shell-main`'s padding, once for `.bn-tabbar`'s own height — and a third time,
wrongly, as the flat `64px` half of CaptureScreen's budget. Three hand-written copies of one
fact are three chances for one of them to drift, and the third one had already drifted.

**The fix is one property, declared once, where the bar itself is sized.** `--bn-tabbar-h` is
declared in `App.css` inside the same `@media (max-width: 767px)` block that draws
`.bn-tabbar`, and both of that file's own two hard-coded copies now read it instead of
repeating the calc. `CaptureScreen.css`'s stage budget reads the same property rather than a
literal `64px`, so a change to the safe-area inset — or to the bar's own height — reaches both
files from one declaration.

**THE REMAINING BUDGET WAS ALSO WRONG, BY A FEW PIXELS, EVEN BEFORE THIS.** Subtracting the
old flat 64px from the old 356px literal isolates a "rest of the page" budget of 292px, which
is what a purely mechanical swap would have kept. Measured against a real render — 390x667,
a 34px safe-area inset, `app/tests/phone.spec.ts`'s new shutter case — 292px still left the
shutter's bottom edge a fraction of a pixel into the bar's top edge. The original 356px literal
had never been checked to the pixel; it was close enough that nobody had measured it, at a tab
bar height nobody had varied. `CaptureScreen.css`'s budget is 298px now: the measured gap
closed, plus 1px of margin against subpixel rounding, confirmed clear at three heights.

**A property has exactly the failure mode a literal does not: staying wrong is now visible in one place instead of hiding in three.** The next thing that needs the tab bar's height —
`Pricing.css`'s ship bar already hard-codes the same
`calc(64px + env(safe-area-inset-bottom))` a fourth time, in its own toast-clearance calc — is
a candidate to read `--bn-tabbar-h` too; that file is out of this change's scope and is named
here so the next session reads this entry before adding a fifth copy.

**Why this is its own entry rather than an amendment to D117.** The layout primitive
(`--bn-tabbar-h`, and CaptureScreen's stage budget reading it) is not a fact about the
thumb-floor sweep — it is a fact about the shell's own chrome, the same register D117's own
"What is NOT decided here" leaves outside its scope. The sweep change this bug's own guard
also required — a covered control's centre now fails on its own — IS a fact about the sweep,
and is recorded as an amendment to D117 instead, beside the entry that already documents
`owns()`'s three forgiving clauses in full.

### Mechanized

`app/tests/phone.spec.ts`'s `the shutter clears the phone tab bar on first paint, with a real
safe-area inset` case. It overrides Chromium's DevTools `Emulation.setSafeAreaInsetsOverride`
to a real 34px bottom inset — Playwright's default is 0px, which is the one phone shape nobody
owns and which is exactly why nothing had ever caught this — asserts the override actually
reached `env(safe-area-inset-bottom)` before trusting anything else in the case, then at
390x667, 390x740 and 390x844 asserts `.capture-shutter`'s bounding-box bottom is at or above
`.bn-tabbar`'s bounding-box top on a fresh navigation (first paint, no interaction). Red against
the unfixed tree at all three heights (measured: 39px, 39px and 39px of overlap); green against
the fix.

**Seeing the failure at all needed a second change**, recorded as an amendment to D117 rather
than here: `phone.spec.ts`'s own `owns()` forgives a probe landing on `.bn-tabbar` so a control
legitimately scrolling past it is not read as crowded, and the shutter's every corner probe —
as well as its centre — landed inside the bar and were all forgiven, so the general
thumb-floor sweep (the "every owner screen" case in the same file) reported the route clean
even on the unfixed tree. §22 is partly closed by that amendment; see it and
D117 for the mechanism and for what is still open.

### Not mechanized

**Whether a future consumer of the tab bar's height remembers to read `--bn-tabbar-h` rather than writing a fifth literal.** `Pricing.css`'s own copy is named above rather than fixed here,
because touching it is outside this change's stated scope; nothing stops a sixth copy from
being written the same way the third one was.
