## D117 — The thumb floor is the kit's, the measurement is the hit area, and a phone-width spec is what reads it

**Built 2026-09-07, on the owner's instruction to review the mobile build.** CLAUDE.md has
published two floors for this width since the Banchi rebuild and neither had a reader: *"Look at
it at 1440, 820 and 390 … No horizontal page scroll at 390"* and *"anything a thumb presses is
40px or more. The control-height tokens raise themselves under 767px and on a coarse pointer, so
do not hand-roll a mouse-sized control on a phone."* Twenty-five controls hand-rolled one.

**NOTHING IN `app/tests/` COULD HAVE SEEN IT.** `nav.spec.ts` scopes itself to `.bn-side` on
purpose. `cursor.spec.ts` harvests its routes from `.bn-side a.bn-nav-link`, which is
`display: none` below 768 — so that file cannot run at a phone width even in principle, and its
own comment names the phone drawer as a second copy it does not walk. Of twenty specs only
`fulfillment.spec.ts` set a phone viewport, for the Fulfiller's one route.
**The owner-side shell had no test at any width**, so every shortfall below was invisible to
`make check` and `make design-check` together.

**THE FLOOR BELONGS TO THE KIT, AND PATCHING IT PER SCREEN IS HOW IT HID.** `.bn-check` has no
height at all — an `inline-flex` label around a fixed 16×16 box, measuring 19.5px at 390 — and
`Markdown.css` lifted its own copy and said so in a comment: *"The check is still somebody
else's."* `BoxBrowse.css` did the same for `.bn-menu-item`. Both are deleted; `kit.css` holds
`.bn-check`, `.bn-seg-item`, `.bn-tab`, `.bn-menu-item`, `.bn-toast-action` and `.bn-toast-close`
now, and every screen gets them rather than the two that happened to notice.

**THE LIFT BLOCK IS LAST IN `kit.css`, AND THAT IS LOAD-BEARING.** Every rule in it lifts a base
rule above it at the same specificity, so it has to come after them or it does nothing. That is
not hypothetical: `Markdown.css` records the same mistake being made and shipped — *"a phone lift
written before the base rules at the same specificity, dead on arrival"* — and the kit's own
`.bn-seg-item` phone rule was written at the top of the sheet, where it lost the cascade at 28px.

**THE ARM IS THE POINTER, NOT THE WIDTH.** `tokens.css` has raised `--bn-control-h*` on
`(max-width: 767px), (hover: none) and (pointer: coarse)` since it was written, and
`docs/DESIGN.md` says why: an iPad in portrait is 820px wide and all thumb. Ten stylesheets
carried width-only blocks full of control heights, so a tablet got none of them.

**THE MEASUREMENT IS THE HIT AREA, NOT THE BOX, WHICH IS WHAT REMOVES THE ALLOW-LIST.**
`BoxBrowse`'s ticks draw at 22px and take the tap at 46 through an `::after`
with a negative inset; the composer's stage chips do the same. A box-only assertion calls both
of those failures and needs a list of names to forgive them — and a list of names is a list
somebody adds to. Probing the four cardinal points of the required 40px box asks the question
the floor is actually about: can a thumb landing 19px off centre still press it.
**It found a pad that was there and did nothing**: the row button is a sibling in the same grid and paints
later, so it took every press in the 12px to the tick's right, and the tick answered 46px tall
and 34px wide until a `z-index` put the pad above the sibling it was drawn to overlap.

**ONE SURFACE IS SWEPT FOR THE BOX INSTEAD, AND IT IS THE ONE THAT MATTERS MOST.** `#/gallery`
draws specimens side by side to be compared, so every probe there lands on the next specimen and
the probe cannot be asked. What can be asked is the box — CLAUDE.md's floor verbatim — and that
sweep is the only thing in the product that draws every kit control. Measured: with the sheet
swept for the box, deleting `.bn-check`'s floor turns `phone.spec.ts` red; swept for the probe,
it does not.

**AND THE SWEEP SCROLLS, because `elementFromPoint` answers about the viewport.** One pass at the
top of a route measures the first 844px of it. `#/gallery` is thirteen thousand pixels long and
its checkbox sits at y=13124, so a single-pass version of this file stayed green through three
mutations that deleted kit floors outright.

**A STICKY BAR MAY NOT LEAVE A CONTROL UNPRESSABLE.** `#/pricing`'s ship bar stood 430px of an 844px viewport — half the screen, four wrapped rows —
with `Pick a run` underneath it: visible, and impossible to press at any scroll position. The cap
sentence is hidden on a phone (the pill beside it already states the scope) and both split
checkboxes have short forms, which is 152px.
**The obvious second fix was built and then refused**: padding the page by the measured
`--pricing-ship-h` added 172px of dead scroll under a
list the operator is walking, and with the bar back to two rows `.bn-page`'s own 64px foot
already leaves the last row 24px clear. `pricing.spec.ts` asserts that clearance geometrically,
so whatever provides it is free to change.

**THE FIXED CHROME IS NOT AN OBSTRUCTION, AND THE LIST IS NAMED RATHER THAN DERIVED.**
Content scrolls under the top bar and the tab bar by design — `.bn-shell-main` pads its foot by
the tab bar's height plus the safe area for exactly that. "Anything sticky" would excuse the ship
bar, which is the case this file exists to catch; "anything fixed" would miss `#/gallery`'s own
sticky index strip. Three strips are written out in the spec and a fourth is a deliberate edit.

**AND THE NAMED LIST WAS THE WRONG SHAPE (amended 2026-09-11).**
It took five weeks and a red `main` to show. `#/inventory` failed this file's own case on the CI
runner and passed on this Mac: the queued notice's `Open the review queue` missed its BOTTOM
probe to `button.browse-boxchip`, a control 450px away from it in document flow. Nothing was
crowding it. `.browse-mobilebar` is `position: sticky; top: var(--bn-topbar-h)`, so the link is
overlapped only while it scrolls UNDER that bar, and which offsets the sweep samples is a
function of font metrics — 143x16 on this rig, 148x16 on the runner.

**THE PROPERTY THIS SWEEP IS FOR IS THE ONE STATED ABOVE, AND WHAT IT ASKED WAS NARROWER.**
"Impossible to press at any scroll position" is the property; what the sweep asked was whether
the control was pressable at whichever offset the 40 scroll steps happened to sample. Measured
on `#/inventory` at 390 at every whole-pixel offset rather than at the sampled ones: the link is
intercepted at 101 of 558 and clean at 457, including where it rests. The failing band is 101
CONSECUTIVE offsets, not a knife edge — it reads as one only because this page has two sample
points, which is what made a font-metric shift enough to move the suite from green to red.

**SO THE MISS IS RE-ASKED WITH THE CONTROL SCROLLED CLEAR.**
Its own centre is put at the middle of the viewport and the four probes are fired again; it is
reported only if it still fails. Real crowding survives that and bar occlusion does not: a
sibling painting over a pad moves WITH the control and crowds it at every offset, while a bar
the page scrolls under is behind it at some offsets and not others. That distinction is derived
rather than named, which is what the three-strip list could never be.

**NAMING `.browse-mobilebar` AS A FOURTH STRIP WOULD HAVE GONE GREEN AND LEFT THE NEXT ONE ARMED.**
`.browse-details-summary` is intercepted by `.browse-actionbar` at 99 of its 197 offsets and
pressable at the other 98 — the same non-defect, on a bar that is `position: fixed`, which is
exactly what that list must not excuse. The 40-step sweep has simply never sampled it. A list of
names is a list somebody adds to, and this is the entry that found out what that costs.

**THE `[DEBUG ...]` SUFFIX ON THE FAILURE LINE IS KEPT, AGAINST ITS AUTHOR'S STATED INTENT.**
#252 added it "diagnostic only, to be reverted once the CI log gives the answer" and the answer
has been got, so the literal reading is that it goes. It stays. It is what made a defect three
sessions had theories about solvable at all: #252 changed a value on a font-metric hypothesis,
could not tell whether it had worked, and wrote "the vertical-margin theory is wrong and the real
cause is unknown"; the next failing run named the intercepting element and the coordinates, and
every session since reasoned from that one string. The clearance retry makes failures that reach
this line RARER, and a rare failure on a runner whose metrics no rig can recreate is one the log
has to carry by itself. Intent stated before the value was known does not bind once it is
measured. The argument is written beside the code, because a PR body is not what the next reader
opens.

**THE SIZE FLOOR IS UNTOUCHED AND SO IS `#/gallery`'s BOX SWEEP.**
Scrolling cannot make a 22px control 40px, so the retry is asked only of the probe.
Mutation-tested, four arms, all red: the notice link's own pad deleted (a real 143x16 hit area),
`.bn-check`'s kit floor deleted, `.browse-rowtick`'s `z-index` removed — this entry's own
crowding case, the one the probe was built for — and a fixed bottom bar grown to 60% of the
viewport over content that cannot be scrolled clear of it.

**AMENDED 2026-09-13: A COVERED CENTRE NOW FAILS ON ITS OWN, WHICH CLOSED HALF OF DEBT22 AND LEFT THE OTHER HALF NAMED.** The capture screen's shutter sat half under
the phone tab bar on first paint — every one of its four corner probes AND its own centre
landed inside `.bn-tabbar`, and `owns()`'s `chrome(n)` clause forgave every one of them, exactly
as it is supposed to for a control legitimately scrolling PAST fixed chrome on its way up a
route. The shutter was not scrolling past it; it was sitting behind it, on first paint, with no
scroll at all — and this file could not tell the two apart, because `covered` (the CENTRE
hit-test) reused the same forgiving `owns()` and its result drove nothing: `fails` read the four
corner probes' `misses` alone, so a control whose centre AND every probe were all forgiven by
`chrome()` reported clean. `centreOwns()` is `owns()` with `chrome(n)` dropped — `t.contains(n)`
and `n.contains(t)` stay, because those cover a legitimate padded wrapper and a control cannot
be COVERED by its own descendant or its own ancestor in the sense this check is for — and
`covered` now uses it and now drives `fails` for probe mode. Proved red against the unfixed
CaptureScreen.css (D205) and green with the fix;
this file's other three cases — every owner route, the shell's three surfaces, the two sheets —
still pass with the tightened predicate, so nothing legitimately scrolling under `.bn-topbar` /
`.bn-tabbar` / `.kit-index` elsewhere in the product got newly flagged.

**THE `n.contains(t)` CLAUSE DEBT22 ACTUALLY OPENED WITH IS UNCHANGED, RE-MEASURED THE SAME DAY.** `.browse-boxchip` shrunk to 20px against the tightened file: still green. A
shrunk control's own centre stays inside its own smaller box — nothing is covering it, so
`centreOwns` correctly finds the control itself there. It is the CORNER probes that land outside
the shrunk box and onto `.browse-mobilebar`, its ancestor, forgiven by `n.contains(t)` — the
clause this entry already calls load-bearing for the padded-wrapper case, and narrowing it is
still the unmeasured, twelve-route change #22 always said it was. Today's amendment closes a
different clause (`chrome(n)`, at the centre) on a different reproduction (fixed chrome, not an
ancestor bar); DEBT22 is updated to record that split rather than marked closed
outright.

**What is NOT decided here.** D50's three interaction floors are still derived from a mouse:
`base.css` has no coarse-pointer arm at all, its response floor argues entirely from a hover
sweep of 315 controls, and its 1px press dip is a mouse-derived number applied to a finger. That
is a real question and it is not this entry's.

**What would reopen this:** a second Playwright project at a device profile rather than
per-test viewports. `playwright.config.ts` has one chromium project today, and the phone width is
set per case; a project would run every existing spec at both. It doubles `design-check`'s
runtime, which is why it is named here rather than taken.
