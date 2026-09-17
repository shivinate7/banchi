## 22 — A control shrunk inside its own sticky bar is invisible to the thumb-floor sweep

**Measured 2026-09-11, while answering the CI failure that PR #252 could not.**
`app/tests/phone.spec.ts` decides whether a probe landed on the control with
`owns = t.contains(n) || n.contains(t) || chrome(n)`. The middle clause — the probe landed on the
control's own ANCESTOR — is what lets a 22px tick answer at 46px through a padded wrapper, and it
is load-bearing for the whole hit-area method (D117): the alternative is the box-only assertion
this file rejects, which needs a list of names to forgive every negative-inset pad.

It also means a control cannot fail because of its own parent. Shrink `.browse-boxchip` from
`--bn-control-h-lg` to 20px and its vertical probes land on `.browse-mobilebar`, the sticky bar it
sits in, which contains it — so the sweep reports nothing and the suite stays green.

**What was checked, because the obvious suspicion is wrong:** the arm is silent against the copy
of the file that PREDATES 2026-09-11's `.browse-mobilebar` chrome entry as well as against the
one that carries it. Naming that bar as chrome did not open this, and removing the name would not
close it. The clause is older than both.

**ONE OF THE TWO FORGIVING CLAUSES IS CLOSED, 2026-09-13, ON A DIFFERENT REPRODUCTION THAN THE
ONE ABOVE** (an amendment to D117, out of
D205). The capture screen's shutter sat
half under the phone tab bar on first paint — `.capture-shutter`'s every corner probe AND its
own centre landed inside `.bn-tabbar`, and `chrome(n)` forgave all of them, so `misses` stayed 0
and this file reported the route clean. That is the THIRD clause, `chrome(n)`, not the
`n.contains(t)` one this entry names — the shutter is not a descendant of `.bn-tabbar`, it is
genuinely behind it. `covered` (the centre hit-test) already existed and already used the same
forgiving `owns()`, and was computed but never asked — `fails` read the corner probes' `misses`
alone. The fix: a second predicate, `centreOwns`, is `owns()` with `chrome(n)` dropped; `covered`
uses it, and `covered` now drives `fails` for probe mode. Proved red against the unfixed
CaptureScreen.css (the shutter case itself), proved green with it, and the other three cases in
this file — every owner route, the shell's three surfaces, the two sheets — still pass, so the
narrowing did not cost a route legitimately scrolling under `.bn-topbar` / `.bn-tabbar` /
`.kit-index` elsewhere in the product.

**THE `n.contains(t)` CLAUSE THIS ENTRY OPENED WITH IS STILL OPEN, RE-MEASURED THE SAME DAY.**
The `.browse-boxchip` / `.browse-mobilebar` reproduction above was re-run against the tightened
file: `.browse-boxchip` shrunk to 20px, every other case in `phone.spec.ts` left alone. Still
green. The reason is geometric and different from the shutter's: a shrunk control's own CENTRE
stays inside the control's own (smaller) box — nothing paints over it, so `centreOwns` finds `t`
itself there and forgives it correctly. It is the four CORNER probes that land outside the
shrunk box and onto `.browse-mobilebar`, an ancestor rather than fixed chrome, forgiven by
`n.contains(t)` — a clause `centreOwns` still carries, deliberately, because D117 calls it
load-bearing for the padded-wrapper case this file exists to tell apart from real shrinkage.
Narrowing THAT clause is still the unmeasured, twelve-route change the paragraph below always
said it was; today's fix closes a different clause on a different reproduction.

**Why the remaining clause is not repaired here.** Narrowing it — say, to ancestors that are not
themselves scroll-independent furniture — is a change to the predicate every case in that file
rests on, and it wants its own measurement across all twelve routes rather than a fix smuggled
into a bug-batch item scoped to one screen. The `mode === 'box'` sweep on `#/gallery` already
asserts the box outright and would catch a shrunken kit component; what escapes is a
screen-level control shrunk inside its own sticky ancestor bar.
