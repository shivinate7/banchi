## D152 — Every row in the collapsed rail draws one glyph on one spine, and a rule that lists the children it knows about will miss one

**Settled 2026-09-12, on the owner's report of two defects in the collapsed sidebar foot.** Both
were visible in one screenshot of the 64px rail, both had shipped, and the browser suite was green
through both. They are recorded as one entry because they are one cause.

**WHAT THEY WERE, MEASURED.** The rail is 64px and every glyph in it rests on a spine at x = 32 —
the sidebar's 8px gutter plus half of the 48px box each row draws in. Read off the running app at
1440 with the sidebar collapsed:

- **The hand-off row wore two glyphs.** `App.tsx` draws the Fulfiller's link as an 18px `hand`, the
  label, and a 14px `external` mark saying the screen opens in its own tab. The rail folded the
  label away and kept both icons, so that row drew glyphs at **x = 19 and x = 47** — a pair
  straddling the whole rail, in a 48px box, beside three rows carrying one glyph at 32.
- **The server dot was never centred at all.** `.bn-server` kept its OPEN-sidebar layout into the
  rail: `padding: 0 var(--bn-3)` with the label `display: none`, shrink-wrapped to **32px** by the
  foot's `align-items: flex-start`. The dot was therefore placed by the left padding and nothing
  else — 8 (gutter) + 12 (that padding) + 4 (half an 8px dot) = **24**, eight pixels left of the
  spine. Not off by half a border, and not centred against an asymmetric container; those are the
  two other shapes this failure comes in and neither is this one. It is correct in the OPEN
  sidebar, where that row is meant to be left-aligned and the dot lines up under the button icons
  above it. **Collapse-only, and a missing rule rather than a wrong number.**

**THE CAUSE IS THE SHAPE OF THE RULES, NOT EITHER ELEMENT.** `App.css`'s rail block describes the
foot by LISTING what was in it when the block was written. The fold-away is an enumeration of class
names — `.bn-nav-text`, the link's `.bn-kbd`, `.bn-nav-badge`, `.bn-side-foot-text`,
`.bn-brand-chevron` — and the spine rule names `.bn-btn`. The external glyph is in none of those
classes; `.bn-server` is not a `.bn-btn`.
**Anything the list does not name keeps its open-sidebar layout** — silently, and looking like a
rule that is simply doing its job.

**`.bn-btn` NEXT TO BOTH OF THEM NEVER HAD THE DEFECT, AND THAT IS THE ARGUMENT.** Its rule is
`> :not(.bn-icon)` — structural, so it folds away whatever it was not told about. The fix is that
rule's shape applied to the other two: `.bn-nav-link > :not(:first-child)` keeps the leading glyph
and nothing else, and `.bn-server` takes the identical `width: 48px; padding: 0;
justify-content: center` its siblings already had. One declaration repeated, not a second
arithmetic to keep in step.

**THE WIDTH IS FIXED AND THE CENTRING RESOLVES AGAINST THAT**, which is the trap this block is
written around: `justify-content: center` against the SIDEBAR's width resolves against a box that
animates for 320ms, and this file already carries two measured excursions from exactly that. A
48px box pinned at the gutter does not travel; the dot rests on 32 from frame 0.

**IT EXISTED TWICE, BECAUSE THE BLOCK EXISTS TWICE.** The shell is railed two ways — `data-rail`
above 1023px, and a media query at 768-1023px that has no `data-rail` at all and deliberately
copies the block. The copy carried a copy of both defects. A fix or a test that looked only at
1440 would have covered half of it.

**WHY THE SUITE WAS GREEN.** `brand.spec.ts` already asserts the spine, and it asserts TRAVEL: it
samples through the collapse and requires nothing to leave the corridor between its two resting
positions. That is blind by construction to a glyph whose RESTING position is wrong — a sample
sitting between two identical wrong numbers is inside the corridor. Both defects were exactly that.

**THE GUARD IS THE RESTING POSITION, AND THE SPINE IS READ RATHER THAN TYPED.** `every foot row in
the rail draws one glyph, on the nav's own spine` asserts one visible glyph per foot row and every
glyph within 1px of the nav icons above it. Hard-coding 32 would restate `--bn-rail-w` in a second
place and go stale the day the rail is resized; the nav IS the column the foot continues, so it is
what the foot is measured against. It runs at 1440 and at 820, once per rail.

**Observed red before it was kept, four arms**: drop the `:not(:first-child)` rule and the guard
names the link and the two centers it found (`drew 2 at 19, 47`); drop the `.bn-server` rule and it
reports `rests at 24, the nav at 32`. Each fails at both widths.

**WHAT THIS DOES NOT REACH.** The phone drawer below 767px is full-width and draws both glyphs and
every label on purpose; nothing here applies to it, and the guard does not look at it. And the
guard is a floor over the FOOT — a second glyph appearing in the main nav's rows would be caught by
the same rule in the stylesheet but is not asserted, because no nav row draws one today and a test
over an empty set is the failure this repo keeps finding.

