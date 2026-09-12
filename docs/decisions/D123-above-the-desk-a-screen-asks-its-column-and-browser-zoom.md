## D123 — Above the desk a screen asks its column, and browser zoom is not the lever it looks like

**Built 2026-09-07, from the owner's question: their Claude Code sessions "look way nicer at like 80% zoom rather than 100%", and did that mean this app should have been drawn denser?**
The question is worth answering precisely, because the intuition behind it is half right and the
half that is wrong points at a real defect.

### Browser zoom is a similarity transform, so the density half is already solved

Chromium zoom multiplies the CSS-px-to-device-px ratio and divides the layout viewport:
`devicePixelRatio` becomes `2 x 0.8 = 1.6`, so a 14px glyph at 80% rasterises to 22.4 device
pixels — exactly what an 11.2px glyph gives at 100%.
**There is no rendering-quality advantage to reclaim and nothing unreproducible about the preference.**
80% zoom is precisely: every length x 0.8, every breakpoint x 1.25.

That settles the density question against changing the scale. Browser zoom already does it,
per-device, reversibly, in 25 steps rather than 2, across every application the owner uses. A
`banchi.density` token would buy exactly three things over it — it would not widen the viewport,
it could be selective (shrink the chrome, keep the photograph; never touch the Fulfiller), and
it would be a decision in the repo rather than a habit on one machine.
**Deferred, not rejected** , and this paragraph is the record so it is a decision rather than an
unwritten follow-up. It reopens if the owner wants the selectivity.

### The layout half is a real defect, and zoom makes it worse

Because zoom widens the effective viewport, the owner's habit buys MORE of the stretch, not
less; it reads as an improvement only because the type shrank at the same rate. Measured before
any of this landed:
**124 `@media` and 16 `@container` blocks across 31 stylesheets, and above 1024 only 13 rules in 7 files.**
The single widest breakpoint in the product, `@media (max-width: 1599px)`, hid
`.pricing-ready-fine` — **a class no component renders.** The top of the ladder was a rule for
an element that does not exist.

The consequence, measured on `#/pricing` at a 1920 viewport with the sidebar open: nine of the
row's ten tracks are fixed, so every pixel the page gains lands in one cell.
**The card identity was 924px wide while the price field it decides — the hero of the row (D49) — was 68px, at the far end of that gap.**
The ink in that cell reaches 257px at the median and 430px at the 90th percentile across 67
rows.

### The rule: below 1024, `@media`. Above 1024, a cap or a container.

Every screen but the Fulfiller's draws inside `.bn-shell-main`, which is the viewport minus
236px — or minus 64px when the rail is collapsed.
**Those differ by 172px, wider than the gap between two ladder steps** , so a `min-width:
1024px` fires in a 788px column and in a 960px one and cannot tell them apart. Below 1024 the
shell is force-railed by media query, so a viewport question and a column question differ by a
constant and either is answerable.

A cap is preferred to a breakpoint wherever it will serve, because it is measured against the
column the shell actually gave: correct beside the sidebar, beside the rail, and at any browser
zoom, with no query to keep in step. `--bn-page-w` (1600) is the ceiling and `--bn-page-w-rows`
(1344) is for a screen whose body is a list of rows; a screen lowers its own with
`--bn-page-max`, which is deliberately **not** a token — it is a screen's word, never the
system's. Pricing sets 1120, sized to the ink measured above rather than chosen.

**`:not([data-rail='true'])` is not the mechanism and does not spread.** `ReviewQueue.css` is
the one place that ever compensated for the rail, and it keeps its pattern only because
`container-type` would capture the `position: fixed` sheet it controls. The attribute *lies*
between 768 and 1023 — `App.css` rails the shell by media query there and sets nothing — it
costs every declaration twice, and it hardcodes the 172px delta into every pair of numbers.

### The vocabulary was unreadable, and that is what blocked a guard

Four edges were spelled twice (559/560, 639/640, 899/900, 1099/1100) and three integers were
used as both a floor and a ceiling. **None of it was a rendering defect** — the sheets that
disagreed draw different screens, so nobody ever saw two layouts at once, and this entry says so
rather than inflating it. What it was is a vocabulary no guard could enforce. The convention is
now: **a `min-width` is the step, a `max-width` is the step minus one** , `@media` and
`@container` are separate namespaces because a `pane` of 640px and a window of 640px are
different quantities, and `docs/DESIGN.md` carries the register.

`make docs-audit` reads it in two rows. **`breakpoints` is MECHANICAL** — a width is an integer
in a stylesheet and the register is an integer in a document, which is D16's test.
**`breakpoint columns` is ADVISORY**, and the severity is the finding's shape rather than its
confidence: whether a `min-width` is asking the wrong thing depends on what the rule does, and
a width that gates a `100dvh` stage or a fixed sheet is right as it stands. It names four
blocks today, in `RunPanel.css` and `CaptureScreen.css`.

### What was checked and found NOT to be a defect

**`app/src/Fulfillment.css` reads `--bn-control-h*` zero times, and the missing coarse-pointer bump changes nothing.**
The coupling is real; the consequence is not. Measured in his view at 820px: 25 controls,
**none under 44px, the shortest 60px** — and the coarse arm raises those tokens only to
42/46/40. Making that sheet read them would move no pixel and would couple his contractual
floors to a token, which `app/tests/pull-confirm.spec.ts` argues against by name (*"a floor that
reads its value from the thing it is checking checks nothing"*). **Left alone deliberately** ,
recorded here so the next reader does not re-derive it.

**What would reopen this** : a screen that genuinely needs more than 1536px of content, or an
operator who wants the density lever after all.

### Amended 2026-09-07: the caps get a re-checker, at the same moment every other browser floor does

`wide.spec.ts` is in `make design-check`, which was in neither `make check` nor CI — so the caps this entry sets, like D50's three floors, D117's thumb floor, D118's stability floor and the Fulfiller's contractual constraints, could only ever be re-read by a person typing the command on one Mac. `.github/workflows/check.yml` runs the suite as a second job now; **D118's amendment carries the argument and what the second platform found**, which was a real movement in the walk that the rig's font metrics had been swallowing. Nothing here changed: the caps, their values and their derivation are untouched.
