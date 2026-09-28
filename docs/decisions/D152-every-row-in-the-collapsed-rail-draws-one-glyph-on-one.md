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
- **The server dot was never centered at all** (drew at **24**, not 32: `.bn-server` kept its
  open-sidebar padding into the rail). **The dot is deleted (owner's ruling, 2026-09-28):** the
  offline banner already says when the server is down. The foot is Pull, Go to and Theme.

**THE CAUSE IS THE SHAPE OF THE RULES, NOT EITHER ELEMENT.** `App.css`'s rail block describes the
foot by LISTING what was in it when the block was written. The fold-away is an enumeration of class
names — `.bn-nav-text`, the link's `.bn-kbd`, `.bn-nav-badge`, `.bn-side-foot-text`,
`.bn-brand-chevron` — and the spine rule names `.bn-btn`. The external glyph is in none of those
classes; the server dot was not a `.bn-btn`.
**Anything the list does not name keeps its open-sidebar layout** — silently, and looking like a
rule that is simply doing its job.

**`.bn-btn` NEXT TO BOTH OF THEM NEVER HAD THE DEFECT, AND THAT IS THE ARGUMENT.** Its rule is
`> :not(.bn-icon)` — structural, so it folds away whatever it was not told about. The fix is that
rule's shape applied to the other two: `.bn-nav-link > :not(:first-child)` keeps the leading glyph
and nothing else.

**THE WIDTH IS FIXED AND THE CENTRING RESOLVES AGAINST THAT**, which is the trap this block is
written around: `justify-content: center` against the SIDEBAR's width resolves against a box that
animates for 320ms, and this file already carries two measured excursions from exactly that. A
48px box pinned at the gutter does not travel; every foot row rests on 32 from frame 0.

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

**Observed red before it was kept**: drop the `:not(:first-child)` rule and the guard
names the link and the two centers it found (`drew 2 at 19, 47`). It fails at both widths.

**WHAT THIS DOES NOT REACH.** The phone drawer below 767px is full-width and draws every label on purpose; nothing here applies to it, and the guard does not look at it. And the
guard is a floor over the FOOT — a second glyph appearing in the main nav's rows would be caught by
the same rule in the stylesheet but is not asserted, because no nav row draws one today and a test
over an empty set is the failure this repo keeps finding.

**Amended 2026-09-28, owner's ruling:** the sidebar's server-status dot is deleted, from the rail, the sidebar and the phone drawer, because the offline banner (`role="alert"`, with Retry) already says when the server is down.
