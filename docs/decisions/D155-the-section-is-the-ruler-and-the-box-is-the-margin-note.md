## D155 — The section is the ruler and the box is the margin note, and the bracket between them is deleted

**Settled 2026-09-11, on the owner's two sentences about their own copies list.** *"The interface/view of the box is nicer than section"*, and the lens between the two scales is *"more noise than useful"*. The section scale is promoted to a full-width graduated 26px ruler with a fill, a pin that crosses it and the section's own bounds written inside its two ends; the box scale is demoted to an 8px strip of chips with a caret on the chip the card is in; and the SVG trapezoid is deleted outright with nothing drawn in its place. **The component's total height is unchanged at 73px, so no row on `#/inventory` moves by a pixel.**

**The praise of the box view is a praise of STRUCTURE, and that is what the section is given.** The box track is nicer because it has chips, boundaries, a thing you can point at; the section track was a flat 8px bar with a 2px dot on it. A flip that only made the section TALLER would have produced a bigger flat bar and answered the wrong half of the sentence — so the section gets graduations, a fill, a pin and its own bounds, and the box keeps chips at a smaller scale, which is the honest cost of the instruction.

### The flip is justified by resolution, not by taste

**At the 580px bar the owner's screen draws, the box track is 1.45px a card.** The mark's painted footprint — a 2px body plus its 7px head and 2px ring — covers about 7.6 cards there, and about 14 on the 723-card box they already hold. The box track spends the full width of the row to deliver an answer with three or four distinguishable states, **while the caption 3px above it already says `#51 of 53 · 96% in` exactly.** The section scale over box 2's 85-card section 2 is 6.8px a card and over its 7-card section 5 is 82.9px a card, where a graduated ruler draws seven literal cells you can point at. **One of these two instruments can resolve a card and the other never could at any width this component is drawn at.**

**D41 already won this argument one register up.** That entry refused to draw `Box 2 · Section 1 · Card 14` as three equal parts, because the first two are answered everywhere the eye lands on that screen and `Card N` is the only part the panel uniquely supplies. In the copies row the bar sits directly beneath a `PositionLabel` that renders the box name and the section name and beneath `PlaceNeighbors`: **the box is named twice above the bar, and the bar then spent 12px of full-width proportional track re-stating it.** This is the identical shape, and the same ruling.

### The lens was three defects and two of them were unfixable in principle

**(a) The asymmetry is scale-invariant, so no width and no height reaches it.** The two legs' slope ratio is `lens.left : (100 - lens.right)` and contains neither a width nor a height term. On box 2's real layout `[1, 86, 171, 253, 394]` a card in section 2 gives legs of 123px and 334px over 10px — 4.6° against 1.7°; a card in section 1 gives a left leg that is exactly vertical against a right leg 1.25° off horizontal. **The first and last sections are the common case and the case where the drawing is most needed.**

**(b) Its dominant output was a tint band and not a shape.** The polygon is narrow at the top and FULL WIDTH at the bottom, and at 10px tall almost all of its area is the wide end — filled `--bn-accent-tint`, which was **the same token as the section track 3px below it**. What rendered was 21px of one colour with a 3px sliver in it. That is the noise, and it is measurable rather than aesthetic.

**(c) It pointed at the wrong chip.** `lensOf` computed the segment's edges from card counts as pure percentages; the real segments are flex children with `gap: 2px` and `min-width: 3px`. With N sections the track loses `2(N-1)px` the arithmetic never modelled, and any clamped section desynchronised every edge downstream — 8px of drift on box 2's five sections, **42px on the 22-section box D31 records**. A second calculation that has to agree with a flex layout is a class of bug, not an instance of one.

**What replaces it is placed by the LAYOUT.** An 8x4px caret, `::after` on the current chip itself, so gaps, `min-width` clamps and sub-pixel rounding are accounted for by construction — defect (c) fixed for free rather than modelled a second time. It is `--bn-accent` and not the tint: a 32px triangle at 18% alpha over `--bn-surface-2` is invisible. **It is also the first thing in this tree that makes `docs/DESIGN.md`'s "a hairline indents it beneath the box track" describe the product.**

**The one thing the trapezoid was reaching for goes to the ruler's two ends.** It was trying to say how much of the box this slice IS; the caret says only which. The edge labels — `86` and `170`, read against the box caption's `#54 of 400` — say it **in the box's own unit, as a number a person can check**, at zero height cost. A drawing you had to trust, replaced by a figure you can confirm.

### The height reserve moves off `.position-bar-zoom`, and that is the repair D118 was owed

**D118 kept the second scale mounted through a sale so the row would not change height, and it covered exactly ONE of the three ways the depth can fail to resolve.** `sectionDepthOf` also returns null on `place.section === null` and on `box_total <= 0`, and the whole block was gated on `depth !== null` — so a copy in either state drew a 29px bar in a list of 73px ones, in the exact shape D118 exists to forbid.

**So the prop decides the shape and the card's state decides only the paint.** The zoom block mounts whenever `sectionDepth` is on. There is no branch left to take, which is a stronger guarantee than the arithmetic one and cannot be broken by a later fixture. In the two states the arithmetic cannot answer, the ruler draws its ground alone under `sectionBlankSentence` — *which part of the box this sits in is not known yet*. **"Part of the box" rather than "section", so the sentence does not presuppose the thing it is saying is unknown.** This stays on the right side of D68: that entry deleted an object drawing a FAILED MEASUREMENT as if it were a position; this one claims nothing.

**MEASURED ON THE TREE BEFORE THE CHANGE, and the defect was larger than the design that found it said.** The spec written for this work claimed `#/gallery` drew "two ~29px bars in a list of ~73px bars". It draws **one 73px bar and five 29px ones**: `NO_FRACTION` and the departed copy for the reason above, and `OPEN_BOX` and `SINGLE_SECTION` for a fourth reason nobody had counted — the `spans.length > 1` gate below. All six are 73px now.

### The `spans.length > 1` gate goes, and a paragraph of DESIGN.md becomes true

**An undivided box gains the ruler.** `docs/DESIGN.md` has ruled since 2026-08-29 that two agreeing scales in an undeclared box are "the truth rather than a redundancy to design away" — and that paragraph has been describing something the code does not do since it was written, because `spansOf` returns ONE span for an undeclared box and the gate failed. Under the flip, keeping the gate would have left the owner's largest undivided box (133 cards, no dividers) drawing only an 8px strip: **the biggest box on the smallest picture.** The cost is named rather than reframed — such a box now spends 26px saying one fact twice, and the two objects are only distinguishable because one has graduations and no chips and the other has chips and no graduations.

### The assertion that encoded the old priority is reversed in place

**`app/tests/inventory.spec.ts` asserted `boxTrackH > sectTrackH`, which is the literal encoding of the priority the owner asked to flip.** It is amended in place with the argument and not deleted — D118's own precedent — and it still refuses a flattened bar while now refusing a box-dominant one too. **Its figures were already stale when it was reversed**: its comment said "the box track is 16px and the section track 8px" and the tree shipped `--pb-track: 12px`; `docs/DESIGN.md` carried the identical stale 16. Two documents agreeing on a number neither of them read.

**Its comment also records the hazard the design is saved from only by discipline.** `el.querySelector('.position-bar-track')` also matches the section ruler, which carries both classes — DOM order is the only thing that makes it return the box strip. **The inversion is done entirely with CSS `order`, never by reordering the JSX**, and a later session that inverts the other way silently measures the wrong element and takes that assertion green over nothing.

### The Fulfiller does not get the flip, and that is the reopening condition

**Every rule here is scoped to `.position-bar-owner` or to `[data-depth]`, and he has neither** — neither of his call sites passes `sectionDepth`, and `Fulfillment.css` hides the zoom block besides. His skin overrides `--pb-track`, which under this design still names the box strip, and `--pb-rule` is a name he never sets, so **`Fulfillment.css` needs zero lines changed**. His 20px captions clear BODY_FLOOR untouched; PLACE_FLOOR's 32px probes selectors this component does not render; TARGET_FLOOR never sees it, because the bar stays `role="img"` with every descendant `aria-hidden`.

**What would reopen it is a measurement, not a preference.** He reads at arm's length off a 26px track, and the argument above is about a 1.45px-a-card box scale at a 580px bar — his bar is the full width of a phone-sized card and his box scale resolves very differently. **Nobody has measured px-a-card on his screen**, and until somebody does, giving him the ruler would be taste rather than resolution. His floors are asserted in a browser and are not part of any redesign.

### What is given up

**The box strip is 33% shorter and loses its head**, because a 7px dot on an 8px strip IS the strip. A 22-section box at a 294px bar gives about 11px chips, which is fine; the retire dialog at 194px gives about 7px, which is marginal. **This is the cost of the instruction, not a side effect of it.** The box caption also drops from `--bn-ink-2` to `--bn-ink-3` where the ruler is drawn, so anyone whose first question is "which drawer" reads past two bands to get there. **The graduations are a countable scale only when the section holds 24 cards or fewer** — on box 2 that is one section of five; above it they are a texture that says "this bar has a scale" without letting you read a number off it, and the claim should not be overstated. **And the fill reads one card short by convention**: `marker` is `(slot - 1) / of`, the server's own `fraction` rule, so the fill means "counted past" and a card at slot 1 draws an empty bar.

### Two collisions the design did not predict, found by looking at it

**The pin eats the near edge label when the card is at the front or the back of its section, and that is accepted rather than fixed.** Measured at a 390 viewport in light, card 4 of an 80-card section on a 440px ruler: the pin's 2px knockout took most of the `1`. **No CSS can reach it** — the pin's `left` is a percentage and the label's `left` is a fixed 6px, so the two cannot be compared in a selector, and a threshold in the component would be a proxy for a pixel fact: 14% at the narrowest real render (194px) and 4.7% at the owner's 580px, where a single figure would blank the label for the first nineteen cards of a 400-card section. **It is self-limiting and it lands where the number is redundant** — the caption directly above says `card 4 of 80` and the fill is visibly empty, so the reader already knows they are at the near bound. Raising the labels over the pin was refused outright: the pin is 3px and the digits are 6 to 18px, so the label would hide "you are here".

**The caret and the box mark collide whenever the card sits near its section's midpoint, and that one IS fixed.** The caret is centred on the chip and the mark is at the card's own fraction of the box, so they land on one x far more often than the arithmetic suggests — on the very first fixture looked at. The mark's knockout ring was eating the caret's right half; the caret now takes `z-index: 2`. They overlap by at most 2px vertically, so the caret winning costs the ring and nothing else, and the caret is the object that says WHICH chip.

**These two are the receipt for the design's own tenth caveat**, which said every figure in it was arithmetic off the stylesheets and that nothing had been rendered. Six images at three widths in two themes settled the other eight — the gradient aliasing is not visible, the minor graduations survive over the fill in dark, the 10px edge labels are legible at both themes, the 4px caret is visible, and a 26px ruler over an 8px strip reads as one inverted pair.

### Amendment, 2026-09-25: the box strip could pass its own card, and the two scales swap order

**The owner's report:** `"i notice sections can pass the width of their container (wb1 R2 has 12 sections but only 11 show on a card's locator)."` The chip floor here was `min-width: 3px`. That is legible for one digit. A two-digit section number loses its second digit instead. At the box's own right edge, a clipped chip reads as the ruler running off the card. That is what the owner saw.

**The fix raises the floor to `min-width: 20px` under `[data-depth]`.** That is room for two tabular-nums digits at `--bn-fs-2xs`. Past that floor, `.position-bar-track` (the box strip only, never `.position-bar-sectiontrack`) scrolls inside itself. `PositionBar.tsx` centres the current section into that scroll on mount and on every place change. It sets the track's own `scrollLeft` directly.

It does not call `Element.scrollIntoView`. That method walks every scrollable ancestor looking for one to move. On this page it reached `window` and broke `inventory.spec.ts`'s "a walk-to scrolls the walk and never the page". `data-fade-back`/`data-fade-front`, measured off the track's real scroll position, mask whichever edge still has sections hidden past it. `app/tests/section-ruler.spec.ts` proves the strip never exceeds its own scroll width at 12 and 30 sections. It also proves a box past the shrink floor (60 sections) both scrolls and keeps the current section fully in view. This is mutation-checked: reverting the CSS turns the extreme case red.

**The same day, a second message widened the ask**, verbatim: `"there's in an ineffective use of space here, the icons are small, i think we can make` `the card view locator and section view locator wiithin the box be larger/ more intuitive (also card view locator should be BELOW section view locator)."` Three of the four asks are built:

- **Order**: the box strip and its `Section N of M` caption now sort ahead of the card-level ruler. Three `order` integers rotated in `PositionBar.css`. DOM order stays untouched, for the reason the comment above already gives — the spec's `querySelector('.position-bar-track')` depends on it.
- **Icons**: the row form's `IconButton`s (`Mark sold`, `Retire`, `Move`) rose from `size="sm"` (24px face) to the kit's default `size="md"` (28px face), in `Inventory.tsx`'s `Action`. `sm` was already the phone floor's own number under `tokens.css`'s coarse-pointer media query. So the complaint was read as a desktop one too.
- **Whitespace**: `.card-locations-action` moved from the row's inherited `align-items: center` to its own `align-self: start`. That closes the gap the owner named as *above* the icons. The row's tallest cell is `.card-locations-place`, top-heavy with the big slot numeral. Centring against it left most of the air above the shorter action cell.

**First round: two duplicates fell, one is a ruling and stays.** The owner named three. `Section 1` sat in the big header and again in the ruler's own caption head. `#17` sat in `PlaceNeighbors`' "this" row against `card 17 of 39` in the ruler's tail. The word `back`/`front` sat in both `PlaceNeighbors` and `PositionBar`'s own `.position-bar-ends-row`. A first pass found each pinned by an existing test. It stopped all three there, treating a test as a ruling. The owner corrected that: `"the owner's message IS the word ... a spec assertion that pins today's duplicated text is not a ruling."` `scripts/decision-context.py` on `PlaceNeighbors.tsx` and `PositionBar.tsx` was checked again. This time for which duplicate a DECISION pins, not which a spec pins.

**`back`/`front` IS pinned, by D260, and stays.** D260's own built section: `"app/src/PositionBar.tsx: ... back and front are written under both. ... app/src/PlaceNeighbors.tsx draws back, this card, front."` Its rules section: `"Each drawing of a box or a section marks the far back (card 1) and the near end (the highest number)."` Two components each marking the far end is the ruling. It is not an accident two tests happened to pin. This one item stays, and only this one.

**`Section 1` and `#17`/`card N of M` were NOT pinned by any decision, so they are built.** `position.ts:sectionDepthOf`'s `head` now carries the section's NAME alone when the owner gave one. It carries nothing when he did not. The bare number is what `PositionLabel`'s header already draws beside it. Its `tail` drops the slot number too. `PlaceNeighbors` and the header both already carry it. It states the section's SIZE alone (`"39 cards"`, not `"card 17 of 39"`). `PositionBar.css`'s dangling-dot rule (`.position-bar-cap-tail:first-child`) covers the box with no section name. There the head renders nothing, not an empty span. `inventory.spec.ts:2680`, `2684`, `2714`, `2718`, `2741`, `2824` and the named-section case at `6490` are rewritten to the new text. One fixture there gets a section name, so the flex-shrink proof at `2824` still has a head to measure. `locating.spec.ts:242` likewise.

**Second round: both rulers are taller, spent from the height freed.** `--pb-track` (the box strip) rises from 14px to 18px. `--pb-rule` (the card-level ruler) rises from 26px to 32px, under `[data-depth]`. That is +12px total on `PositionBar`'s own height. D119's fold assertions are the ground truth here, not a manual pixel count. `inventory.spec.ts`'s `toBeInViewport({ ratio: 1 })` on `.card-locations-row.is-current` stayed green at the new height. So did `the card panel holds one height for the whole walk`. The panel's own band had this much slack to spend. The dedup above argued the size increase would not read as clutter. It did not mechanically produce the twelve pixels. The two are one round because the owner asked for both together.
### Amendment, 2026-09-25: Direction B, built into the real components

**The owner reviewed two rendered mockups of the whole locator block.** These covered the
header, BACK/THIS/FRONT, the action icons and both rulers. The owner picked one, verbatim:
`"B, large ruler (Recommended)"`. Direction B keeps both rulers at their larger, graduated
size. It also rebuilds the row's own place line as one sentence. Three corrections came with
the pick.

**No typed middle dot.** The mockup wrote `"WB1 R2 · Section 1 · Card 5 of 39"` as one string.
D218 forbids a typed separator. The build draws each fact as its own
`.card-locations-identity-fact` span. `CardLocations.css` then draws the dot in CSS, on the
sibling selector, never in a string `user-strings.mjs` can find.

**`$` stays the sell glyph.** The mockup's check-circle was a stand-in only. The real build
calls the kit's own `IconButton icon="sold"`. That icon is already a round seal drawn around a
`$` (`kit/Icon.tsx`). Nothing here invented a new glyph.

**"Card 5 of 39" and "39 cards" said the section size twice. Now it is said once.**
`position.ts:sectionDepthOf`'s tail fed the ruler's own caption. It is now `[]` in both the live
and the departed case. The new `RowIdentity` component (`CardLocations.tsx`) states
`Card N of M` on the row itself. It reads `M` from `sectionCountOf(copy.place)`. The ruler's
own caption now states only the section's rank and name, never its size.

**A one-line replacement for `PositionLabel`, scoped to the owner's row alone.** `RowIdentity`
renders three facts: the box (the only one allowed to shrink), the section (name if the owner
gave one, the bare number if not) and the card (`Card N of M`). The card figure strikes
through, and the group's `aria-label` reads `Was at ...`, when the copy departed. The exact
`aria-label` `PositionLabel` produced still holds. Every existing accessible-name assertion
passed without being changed.

**Two real D118 regressions turned up, and both are fixed at the cause.** First: the ruler's
caption rendered only when `head` or `tail` held content. The departed case still carried a
tail fact (`was card N`) after the live case's tail went empty for that same section. So the
caption appeared and disappeared across a sale, changing the row's own height. The fix retires
the caption outright, for every state, rather than patching one state at a time.

**Second: the Undo button kept the old, smaller size while its siblings grew.** Every other
action icon on the row rose to `size="xl"`. Undo stayed `size="sm"` inside the sale receipt.
That shrank the action cell the moment a sale fired. Undo now reads `size="xl"`
unconditionally, matching its siblings rather than branching on `primary`.

**One test caught both bugs: `"every copy row draws the same bar height, located or not"`.**
Each fix was reverted to a `.bak` copy in turn. The test went red at 200px against
212px for the icon bug, and 221px against 212px for the caption bug. Restoring each fix turned
the test green again. This is the mutation-proof.

**A third defect, in contrast rather than layout, turned up along the way.**
`.card-locations-identity`'s ink went through `--bn-ink-3`, and that failed the dark theme's
axe sweep. `--bn-ink-2` failed light instead. `--bn-ink` passes both. The same sweep
(`gallery.spec.ts`) then flagged two stale `AXE_KNOWN` entries, `.position-path` and
`.position-key`, once the contrast fix removed the violation they were excusing.

**The ruler sizes settle at `--pb-track: 22px`, `--pb-rule: 40px`, `--pb-cap-sect: 18px`.**
That is up from this file's 2026-09-23 amendment, `18px`/`32px`/`18px`. A first attempt at
`26px`/`48px` broke D119's fold check by roughly 12 to 14 pixels. `.card-locations-row.is-current` no longer held `toBeInViewport({ ratio: 1 })` on `#/inventory`'s seeded screen.
Dialing back to `22px`/`40px` passed the same test again.

**The net cost against D119's budget is zero.** The row stays inside the fold at the settled
size, so nothing here trades away silently. The settled sizes are still clearly larger than the
pre-2026-09-23 baseline, `12px`/`26px` — what "B, large ruler" asked for.

**The row form's action icons rose to `size="xl"`, the kit's own 40px ceiling.** That is past
the first round's `md` (28px). The owner's plain "the icons are small" still read true after
that round. No new pixel value was invented. `xl` is a size the kit already defines.

**Proof.** `app/tests/section-ruler.spec.ts`, `inventory.spec.ts`, `locating.spec.ts`,
`scaffold.spec.ts` and `gallery.spec.ts` all pass after this amendment. Screenshots at 1440 and
390, in light and dark, sit in `scratchpad/report/after-b/` for this round's own review. They
were not committed.
