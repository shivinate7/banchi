## D205 — Tab bar height is named once

**The bug.** The capture screen's shutter sat half under the phone tab bar on first paint at 390 wide. `CaptureScreen.css` sized `.capture-stage` from a hand-written 356px budget. Its own comment counted the tab bar as a flat 64px. The real bar is `calc(64px + env(safe-area-inset-bottom))`, set in `App.css`, where `.bn-tabbar` and `.bn-shell-main`'s clearance padding are both sized. That is about 98px on every phone with a home indicator, which is every phone this product ships to.

The same calc was already written twice in `App.css`: once for `.bn-shell-main`'s padding and once for `.bn-tabbar`'s own height. A third copy, wrongly, was the flat 64px half of CaptureScreen's budget. Three hand-written copies of one fact are three chances for one to drift. The third had already drifted.

**The fix is one property, declared once, where the bar is sized.** `--bn-tabbar-h` is declared in `App.css` inside the `@media (max-width: 767px)` block that draws `.bn-tabbar`. Both of that file's own hard-coded copies now read it. `CaptureScreen.css`'s stage budget reads the same property rather than a literal 64px. A change to the safe-area inset, or to the bar's own height, reaches both files from one declaration.

**The remaining budget was also wrong by a few pixels, before this change.** Subtracting the old flat 64px from the old 356px literal gives a rest-of-page budget of 292px. A mechanical swap would have kept that number. A real render at 390x667 with a 34px safe-area inset (`app/tests/phone.spec.ts`, the new shutter case) showed the problem. At 292px the shutter's bottom edge still reached under one pixel into the bar's top edge. The original 356px literal had never been checked to the pixel, at a bar height nobody had varied. `CaptureScreen.css`'s budget is now 298px. That closes the measured gap and adds 1px of margin against subpixel rounding. Three heights confirm it is clear.

**A property fails in one place, not three.** Staying wrong is now visible in one place instead of hiding in three. `Pricing.css`'s ship bar hard-codes the same `calc(64px + env(safe-area-inset-bottom))` a fourth time, in its own toast-clearance calc. It is a candidate to read `--bn-tabbar-h` too. That file is outside this change's scope. It is named here so the next session reads this entry before it adds a fifth copy.

**Why this is its own entry, not an amendment to D117.** The layout primitive, `--bn-tabbar-h` with CaptureScreen's stage budget reading it, is a fact about the shell's own chrome. D117's "What is NOT decided here" leaves that outside its scope. The sweep change that this bug's guard also required is a fact about the sweep. A covered control's centre now fails on its own. That change is recorded as an amendment to D117, beside the entry that documents `owns()`'s three forgiving clauses.

### Mechanized

`app/tests/phone.spec.ts`, the case "the shutter clears the phone tab bar on first paint, with a real safe-area inset". It overrides Chromium's DevTools `Emulation.setSafeAreaInsetsOverride` to a real 34px bottom inset. Playwright's default is 0px. That is the one phone shape nobody owns, which is why nothing had caught this. The case first asserts the override reached `env(safe-area-inset-bottom)`. Then, at 390x667, 390x740 and 390x844, it asserts `.capture-shutter`'s bounding-box bottom is at or above `.bn-tabbar`'s bounding-box top on a fresh navigation (first paint, no interaction). Against the unfixed tree it is red at all three heights, with 39px of overlap each. Against the fix it is green.

**Seeing the failure needed a second change.** That change is recorded as an amendment to D117, not here. `phone.spec.ts`'s own `owns()` forgives a probe that lands on `.bn-tabbar`. So a control that legitimately scrolls past the bar is not read as crowded. The shutter's corner probes, and its centre, all landed inside the bar and were forgiven. The general thumb-floor sweep (the "every owner screen" case in the same file) therefore reported the route clean, even on the unfixed tree. DEBT22 is partly closed by that amendment. See it and D117 for the mechanism and for what is still open.

### Not mechanized

**Whether a future consumer of the tab bar's height reads `--bn-tabbar-h`, rather than writing a fifth literal.** `Pricing.css`'s own copy is named above and not fixed here, because touching it is outside this change's scope. Nothing stops a sixth copy from being written the same way the third one was.
