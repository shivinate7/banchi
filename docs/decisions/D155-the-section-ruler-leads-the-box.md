# D155 — The section ruler leads the box

**The section scale is the primary instrument of the copies row. The box strip is secondary.** Settled on the owner's two remarks about the copies list. The box view is nicer than the section view. The lens between the two scales is more noise than useful. The section scale becomes a full-width graduated 26px ruler. It has a painted fill, a pin that crosses it, and the section's own bounds written inside its two ends. The box scale becomes an 8px strip of chips, with a caret on the chip the card is in. The SVG trapezoid is deleted, with nothing drawn in its place. **The component's total height is unchanged at 73px, so no row on `#/inventory` moves by a pixel.**

**The praise of the box view is a praise of STRUCTURE, and that is what the section is given.** The box track has chips, boundaries, and a thing you can point at. The section track was a flat 8px bar with a 2px dot on it. A flip that only made the section taller would give a bigger flat bar. So the section gets graduations, a fill, a pin and its own bounds. The box keeps chips at a smaller scale. That is the honest cost of the ruling.

### The flip is justified by resolution, not by taste

**At the 580px bar the owner's screen draws, the box track is 1.45px a card.** The mark's painted footprint (a 2px body, a 7px head and a 2px ring) covers about 7.6 cards there. On the 723-card box the owner holds, it covers about 14. The box track spends the full width of the row to show three or four distinguishable states. **The caption 3px above it already says `#51 of 53 · 96% in` exactly.**

The section scale over box 2's 85-card section 2 is 6.8px a card. Over its 7-card section 5 it is 82.9px a card. A graduated ruler there draws seven literal cells you can point at. **One of these two instruments can resolve a card. The other never could, at any width this component is drawn at.**

**D41 already decided this one register up.** D41 refused to draw `Box 2 · Section 1 · Card 14` as three equal parts. The first two parts are answered everywhere the eye lands on that screen. `Card N` is the only part the panel uniquely supplies. In the copies row, the bar sits directly beneath a `PositionLabel` that renders the box and section names, and beneath `PlaceNeighbors`. **The box is named twice above the bar. The bar then spent 12px of full-width track restating it.** This is the same shape, and the same ruling.

### The lens was three defects, and two were unfixable in principle

**(a) The asymmetry is scale-invariant, so no width and no height reaches it.** The two legs' slope ratio is `lens.left : (100 - lens.right)`. It contains neither a width nor a height term. On box 2's real layout `[1, 86, 171, 253, 394]`, a card in section 2 gives legs of 123px and 334px over 10px. That is 4.6° against 1.7°. A card in section 1 gives a left leg that is exactly vertical. Its right leg is 1.25° off horizontal. **The first and last sections are the common case, and the case where the drawing is most needed.**

**(b) Its dominant output was a tint band, not a shape.** The polygon is narrow at the top and FULL WIDTH at the bottom. At 10px tall, almost all its area is the wide end. It was painted `--bn-accent-tint`, the same token as the section track 3px below it. What rendered was 21px of one colour with a 3px sliver in it. That is the noise, and it is measurable rather than aesthetic.

**(c) It pointed at the wrong chip.** `lensOf` computed each segment's edges from card counts as pure percentages. The real segments are flex children with `gap: 2px` and `min-width: 3px`. With N sections, the track loses `2(N-1)px` that the arithmetic never modelled. Any clamped section desynchronised every edge after it. That is 8px of drift on box 2's five sections, **and 42px on the 22-section box D31 records**. A second calculation that must agree with a flex layout is a class of bug, not a single bug.

**What replaces it is placed by the layout.** An 8x4px caret, a `::after` on the current chip itself, is the replacement. Gaps, `min-width` clamps and sub-pixel rounding are accounted for by construction. Defect (c) is fixed for free, not modelled a second time. The caret is `--bn-accent`, not the tint. A 32px triangle at 18% alpha over `--bn-surface-2` is invisible. **The caret is also the first thing in this tree that makes `docs/DESIGN.md`'s "a hairline indents it beneath the box track" describe the product.**

**The one thing the trapezoid reached for goes to the ruler's two ends.** It tried to say how much of the box this slice IS. The caret says only which. The edge labels say how much. They read `86` and `170` against the box caption's `#54 of 400`. They state it **in the box's own unit, as a number a person can check**, at zero height cost. A drawing you had to trust is replaced by a figure you can confirm.

### The height reserve moves off `.position-bar-zoom`, and that is the repair D118 was owed

**D118 kept the second scale mounted through a sale, so the row would not change height. It covered only ONE of the three ways the depth can fail to resolve.** `sectionDepthOf` also returns null on `place.section === null` and on `box_total <= 0`. The whole block was gated on `depth !== null`. So a copy in either state drew a 29px bar in a list of 73px ones, the exact shape D118 forbids.

**So the prop decides the shape, and the card's state decides only the paint.** The zoom block mounts whenever `sectionDepth` is on. No branch is left to take. That is a stronger guarantee than the arithmetic one, and a later fixture cannot break it. In the two states the arithmetic cannot answer, the ruler draws its ground alone. The sentence under it is `sectionBlankSentence`: *which part of the box this sits in is not known yet*. It says "part of the box", not "section", so it does not presuppose the thing it reports as unknown. This stays on the right side of D68. That entry deleted an object drawing a FAILED MEASUREMENT as if it were a position. This one claims nothing.

**Measured on the tree before the change, and the defect was larger than the design said.** The spec for this work claimed `#/gallery` drew "two ~29px bars in a list of ~73px bars". It drew **one 73px bar and five 29px ones**. `NO_FRACTION` and the departed copy exist for the reason above. `OPEN_BOX` and `SINGLE_SECTION` exist for a fourth reason: the `spans.length > 1` gate below. All six are 73px now.

### The `spans.length > 1` gate goes, and a paragraph of DESIGN.md becomes true

**An undivided box gains the ruler.** `docs/DESIGN.md` rules that two agreeing scales in an undeclared box are "the truth rather than a redundancy to design away". The code had not done that since the paragraph was written. `spansOf` returns ONE span for an undeclared box, and the gate failed. Under the flip, keeping the gate would have left the largest undivided box drawing only an 8px strip. That box holds 133 cards and no dividers. The result would be **the biggest box on the smallest picture.** The cost is stated, not reframed. Such a box now spends 26px saying one fact twice. The two objects are told apart only because one has graduations and no chips. The other has chips and no graduations.

### The assertion that encoded the old priority is reversed in place

**`app/tests/inventory.spec.ts` asserted `boxTrackH > sectTrackH`, the literal encoding of the priority the owner asked to flip.** It is amended in place, with the argument, not deleted. D118's own precedent applies. It still refuses a flattened bar, and now refuses a box-dominant one too. **Its figures were already stale when it was reversed.** Its comment said "the box track is 16px and the section track 8px", while the tree shipped `--pb-track: 12px`. `docs/DESIGN.md` carried the same stale 16. Two documents agreed on a number neither of them had read.

**Its comment records a hazard the design is saved from only by discipline.** `el.querySelector('.position-bar-track')` also matches the section ruler, which carries both classes. DOM order is the only thing that makes it return the box strip. **The inversion is done entirely with CSS `order`, never by reordering the JSX.** A later session that inverts the other way silently measures the wrong element, and that assertion goes green over nothing.

### The Fulfiller does not get the flip, and that is the reopening condition

**Every rule here is scoped to `.position-bar-owner` or `[data-depth]`. The Fulfiller has neither.** Neither of his call sites passes `sectionDepth`, and `Fulfillment.css` hides the zoom block besides. His skin overrides `--pb-track`, which under this design still names the box strip. `--pb-rule` is a name he never sets. So **`Fulfillment.css` needs zero lines changed**. His 20px captions clear BODY_FLOOR untouched. PLACE_FLOOR's 32px probes selectors this component does not render. TARGET_FLOOR never sees it, because the bar stays `role="img"` with every descendant `aria-hidden`.

**What would reopen it is a measurement, not a preference.** He reads at arm's length off a 26px track. The argument above is about a 1.45px-a-card box scale at a 580px bar. His bar is the full width of a phone-sized card, and his box scale resolves very differently. **Nobody has measured px-a-card on his screen.** Until somebody does, giving him the ruler would be taste, not resolution. His floors are asserted in a browser and are not part of any redesign.

### What is given up

**The box strip is 33% shorter and loses its head.** A 7px dot on an 8px strip is the strip. A 22-section box at a 294px bar gives about 11px chips, which is fine. The retire dialog at 194px gives about 7px, which is marginal. **This is the cost of the ruling, not a side effect of it.** The box caption also drops from `--bn-ink-2` to `--bn-ink-3` where the ruler is drawn. A reader whose first question is "which drawer" reads past two bands to get there.

**The graduations are a countable scale only when the section holds 24 cards or fewer.** On box 2, that is one section of five. Above 24, they are texture. The texture says "this bar has a scale", but it gives no number to read off it. **The fill reads one card short by convention.** `marker` is `(slot - 1) / of`, the server's own `fraction` rule. So the fill means "counted past". A card at slot 1 draws an empty bar.

### Two collisions the design did not predict

**The pin eats the near edge label when the card sits at the front or back of its section. That is accepted, not fixed.** Measured at a 390 viewport in light, card 4 of an 80-card section on a 440px ruler. The pin's 2px knockout took most of the `1`. **No CSS can reach it.** The pin's `left` is a percentage. The label's `left` is a fixed 6px. No selector can compare them. A threshold in the component would be a proxy for a pixel fact. It would be 14% at the narrowest real render (194px) and 4.7% at the owner's 580px. At 580px a single figure would blank the label for the first nineteen cards of a 400-card section. **It is self-limiting, and it lands where the number is redundant.** The caption directly above says `card 4 of 80`, and the fill is visibly empty. So the reader already knows they are at the near bound. Raising the labels over the pin was refused. The pin is 3px and the digits are 6 to 18px, so the label would hide "you are here".

**The caret and the box mark collide when the card sits near its section's midpoint. That one IS fixed.** The caret is centred on the chip. The mark sits at the card's own fraction of the box. So they land on one x far more often than the arithmetic suggests. That happened on the first fixture looked at. The mark's knockout ring ate the caret's right half. The caret now takes `z-index: 2`. They overlap by at most 2px vertically. The caret winning costs the ring and nothing else. The caret is the object that says WHICH chip.

**These two are the receipt for the design's tenth caveat.** That caveat said every figure in the design was arithmetic off the stylesheets, and nothing had been rendered. Six images at three widths in two themes settled the other eight. The gradient aliasing is not visible. In dark, the minor graduations survive over the fill. The 10px edge labels are legible in both themes. The 4px caret is visible. A 26px ruler over an 8px strip reads as one inverted pair.

### The box strip scrolls, and the two scales swap order

**The owner reported that sections can pass the width of their container.** WB1 R2 has 12 sections, but only 11 show on a card's locator. The chip floor was `min-width: 3px`. That is legible for one digit. A two-digit section number loses its second digit instead. At the box's right edge, a clipped chip reads as the ruler running off the card. That is what the owner saw.

**The fix raises the floor to `min-width: 20px` under `[data-depth]`.** That is room for two tabular-nums digits at `--bn-fs-2xs`. Past that floor, `.position-bar-track` scrolls inside itself. It is the box strip only, never `.position-bar-sectiontrack`. `PositionBar.tsx` centres the current section into that scroll on mount and on every place change. It sets the track's own `scrollLeft` directly.

It does not call `Element.scrollIntoView`. That method walks every scrollable ancestor looking for one to move. On this page it reached `window` and broke `inventory.spec.ts`'s "a walk-to scrolls the walk and never the page". `data-fade-back` and `data-fade-front`, measured off the track's real scroll position, mask whichever edge still has sections hidden past it. `app/tests/section-ruler.spec.ts` proves the strip never exceeds its own scroll width at 12 and 30 sections. It also proves that a box past the shrink floor (60 sections) both scrolls and keeps the current section fully in view. This is mutation-checked: reverting the CSS turns the extreme case red.

**A second request the same day widened the ask.** The owner said space is used ineffectively. The icons are too small. The card and section view locators should be larger and more intuitive. The card view locator should sit BELOW the section view locator. Three of the four asks are built:

- **Order.** The box strip and its `Section N of M` caption sort ahead of the card-level ruler. Three `order` integers rotate in `PositionBar.css`. DOM order stays untouched, for the reason the comment above gives. The spec's `querySelector('.position-bar-track')` depends on it.
- **Icons.** The row form's `IconButton`s (`Mark sold`, `Retire`, `Move`) rose from `size="sm"` (24px face) to the kit's default `size="md"` (28px face). That change is in `Inventory.tsx`'s `Action`. `sm` was already the phone floor's own number under `tokens.css`'s coarse-pointer media query. So the complaint was read as a desktop one too.
- **Whitespace.** `.card-locations-action` moved from the row's inherited `align-items: center` to its own `align-self: start`. That closes the gap the owner named as *above* the icons. The row's tallest cell is `.card-locations-place`, top-heavy with the big slot numeral. Centring against it left most of the air above the shorter action cell.

**Round one: two duplicates fell, and one is a ruling that stays.** The owner named three. `Section 1` sat in the big header and again in the ruler's own caption head. `#17` sat in `PlaceNeighbors`' "this" row, against `card 17 of 39` in the ruler's tail. The words `back` and `front` sat in both `PlaceNeighbors` and `PositionBar`'s `.position-bar-ends-row`. A first pass found each pinned by an existing test, and it stopped all three there. It treated a test as a ruling. The owner corrected that. The owner's message is the ruling. A spec assertion that pins today's duplicated text is not one. `scripts/decision-context.py` on `PlaceNeighbors.tsx` and `PositionBar.tsx` was checked again. This time it was checked for which duplicate a DECISION pins, not which a spec pins.

**`back` and `front` are pinned by D260, and they stay.** D260's built section reads: `"app/src/PositionBar.tsx: ... back and front are written under both. ... app/src/PlaceNeighbors.tsx draws back, this card, front."` Its rules section reads: `"Each drawing of a box or a section marks the far back (card 1) and the near end (the highest number)."` Two components each marking the far end is the ruling. It is not an accident that two tests happened to pin. Only this one item stays.

**`Section 1` and `#17`/`card N of M` are not pinned by any decision, so they are built.** `position.ts:sectionDepthOf`'s `head` now carries the section's NAME alone when the owner gave one, and nothing when he did not. The bare number is what `PositionLabel`'s header already draws beside it. Its `tail` drops the slot number too, since `PlaceNeighbors` and the header already carry it. The tail states only the section's SIZE (`"39 cards"`, not `"card 17 of 39"`). `PositionBar.css`'s dangling-dot rule (`.position-bar-cap-tail:first-child`) covers a box with no section name. There the head renders nothing, not an empty span. `inventory.spec.ts` lines 2680, 2684, 2714, 2718, 2741, 2824 and the named-section case at 6490 are rewritten to the new text. One fixture there gets a section name, so the flex-shrink proof at 2824 still has a head to measure. `locating.spec.ts` line 242 at `e7aa9497` is likewise rewritten.

**Round two: both rulers are taller, spent from the height freed.** `--pb-track` (the box strip) rises from 14px to 18px. `--pb-rule` (the card-level ruler) rises from 26px to 32px, under `[data-depth]`. That is +12px total on `PositionBar`'s own height. D119's fold assertions are the ground truth here, not a manual pixel count. `inventory.spec.ts`'s `toBeInViewport({ ratio: 1 })` on `.card-locations-row.is-current` stayed green at the new height. So did `the card panel holds one height for the whole walk`. The panel's own band had this much slack to spend. The dedup above argued the size increase would not read as clutter. It did not mechanically produce the twelve pixels. The two are one round because the owner asked for both together.

### Direction B, built into the real components

**The owner reviewed two rendered mockups of the whole locator block.** They covered the header, BACK/THIS/FRONT, the action icons and both rulers. The owner picked Direction B, the large ruler. Direction B keeps both rulers at their larger, graduated size. It also rebuilds the row's own place line as one sentence. Three corrections came with the pick.

**No typed middle dot.** The mockup wrote `"WB1 R2 · Section 1 · Card 5 of 39"` as one string. D218 forbids a typed separator. The build draws each fact as its own `.card-locations-identity-fact` span. `CardLocations.css` draws the dot in CSS, on the sibling selector. It never lives in a string `user-strings.mjs` can find.

**`$` stays the sell glyph.** The mockup's check-circle was a stand-in. The real build calls the kit's own `IconButton icon="sold"`. That icon is already a round seal drawn around a `$` (`kit/Icon.tsx`). Nothing here invented a new glyph.

**"Card 5 of 39" and "39 cards" said the section size twice. Now it is said once.** `position.ts:sectionDepthOf`'s tail fed the ruler's own caption. It is now `[]` in both the live and the departed case. The new `RowIdentity` component (`CardLocations.tsx`) states `Card N of M` on the row itself. It reads `M` from `sectionCountOf(copy.place)`. The ruler's caption now states only the section's rank and name, never its size.

**A one-line replacement for `PositionLabel`, scoped to the owner's row alone.** `RowIdentity` renders three facts. The box is the only one allowed to shrink. The section shows its name if the owner gave one, and the bare number if not. The card shows as `Card N of M`. When the copy has departed, the card figure strikes through, and the group's `aria-label` reads `Was at ...`. The exact `aria-label` `PositionLabel` produced still holds. Every existing accessible-name assertion passed without change.

**Two D118 regressions turned up, and both are fixed at the cause.** First: the ruler's caption rendered only when `head` or `tail` held content. The departed case still carried a tail fact (`was card N`). The live case's tail went empty for that same section. So the caption appeared and disappeared across a sale, changing the row's own height. The fix retires the caption outright, for every state, rather than patching one state at a time.

**Second: the Undo button kept the old, smaller size while its siblings grew.** Every other action icon on the row rose to `size="xl"`. Undo stayed `size="sm"` inside the sale receipt. That shrank the action cell the moment a sale fired. Undo now reads `size="xl"` unconditionally, matching its siblings rather than branching on `primary`.

**The icon fix is mutation-proven against one test.** `"The press that sells a copy moves nothing outside the panel it lands in"` presses a real `Mark sold` and measures the row's own height before and after. It needs a live sale, so it reaches the Undo button's own size. A static-fixture test never does. Reverted to a `.bak` copy of `Inventory.tsx`, the test went red. It read 186px after the sale, against a real 190px before it. Restoring the fix turned it green.

**Corrected by a lane review.** An earlier draft named a different test for both fixes: `"every copy row draws the same bar height, located or not"`. That test's fixture carries no undoable row, so it could never have caught the icon fix. The caption fix needs no mutation-proof of its own. The caption is retired from every render path, and `PositionBar.tsx` has no branch left to take. That is a stronger guarantee than a passing runtime check.

**A third defect, in contrast rather than layout.** `.card-locations-identity`'s ink went through `--bn-ink-3`, which failed the dark theme's axe sweep. `--bn-ink-2` failed light instead. `--bn-ink` passes both. The same sweep (`gallery.spec.ts`) then flagged two stale `AXE_KNOWN` entries, `.position-path` and `.position-key`. They were flagged once the contrast fix removed the violation they were excusing.

**The ruler sizes settle at `--pb-track: 22px`, `--pb-rule: 40px` and `--pb-cap-sect: 18px`.** That is up from the round-two values of `18px`, `32px` and `18px`. A first attempt at `26px`/`48px` broke D119's fold check by roughly 12 to 14 pixels. `.card-locations-row.is-current` no longer held `toBeInViewport({ ratio: 1 })` on `#/inventory`'s seeded screen. Dialing back to `22px`/`40px` passed the same test again.

**The net cost against D119's budget is zero.** The row stays inside the fold at the settled size. The settled sizes are still clearly larger than the earlier baseline of `12px`/`26px`, which is what "B, large ruler" asked for.

**The row form's action icons rose to `size="xl"`, the kit's own 40px ceiling.** That is past `md` (28px). The owner's complaint that the icons were small still held after that round. No new pixel value was invented. `xl` is a size the kit already defines.

### Five gaps against the mockup, closed

**The first build was not Direction B.** It kept the old three-row `back`/`this`/`front` ladder. It kept small bare icons with a gap above them. It had a real layout bug, a thin card ruler, and a header in the wrong order. The coordinator named five gaps against `direction-b-1440-dark.png`. Each is closed below.

**One: the ladder collapses into one line.** `PlaceNeighbors` draws `Name → Name`, with an arrow between the two, on one line. It no longer draws three rows with `back`/`this`/`front` words. `RowIdentity` already states the card's own figure once, so `THIS #5` was a plain repeat of `Card 5`. `data-side="back"` and `data-side="front"` still mark the order. No visible word carries it now.

**D260 stays satisfied, and only by the two rulers.** The rulers `PositionBar` draws show `BACK` and `FRONT` in words, on both the box strip and the card-level ruler. That is what "keep it on each ruler" scopes the protection to. `PlaceNeighbors` never carried this protection on its own. It only ever duplicated it.

**Two: the icons are boxed, at the kit's own 40px ceiling.** `CardLocations.css` gives the header's own `IconButton`s a border and a surface fill, scoped to this one cell. Every other icon-only control in the product keeps the kit's ghost look.

**Three: a real bug, not a stray dot.** `.card-locations-identity-box` read `flex: 1 1 auto`. That GROWS the box name to take the row's free width. A short name then pushed the rest of the line to the far right edge, so it read as a separator with nothing before it. D41's own rule only ever asked this fact to shrink under pressure. The fix is `flex: 0 1 auto`: shrink only, never grow. A new test proves it: `"the box fact never grows past its own text..."`. It measures the fact's own rendered width against a `Range` around its text. The viewport is wide, on purpose, so there is free space to grow into. Reverting the fix turns this test red.

**Four: the action icons share the address's own grid row.** The row grid in `CardLocations.css` changes. It was `'place state action' / 'bar bar bar'`. It is now `'place action' / 'neighbors state' / 'bar bar'`. Narrow, each row runs full width instead. The neighbours line moves out from under the address, into its own grid row. That lets the icons sit level with the address text. They use ordinary `align-items: center`, with no override.

**Five: the header states one line, box then section then card, icons on the right.** `RowIdentity` was already built this way. What changed is what sits beside it. The neighbours line moved to its own row beneath. The icons moved to sit level with the address, never below a gap.

**The net cost against D119's own fold budget is negative.** Collapsing the ladder and moving the icons removed roughly 90 to 100 pixels of row height. Nothing here added any back. `#/inventory`'s `toBeInViewport({ ratio: 1 })` on `.card-locations-row.is-current` passed with no ruler dial-back needed this round. That is the opposite of round one. Round one had to trade ruler size back from `26px`/`48px` to stay inside the same budget.

**A phone-width defect, also fixed.** `.card-locations-identity` had `white-space: nowrap` on the whole line. At 390px the icons now share its row, which forced the box name toward zero width instead of letting the line wrap. It is the same shape of bug as the flex-grow one, on the opposite axis. The line now wraps between facts, never inside one. That matches the 390 mockup's two-line header.

**Proof.** `app/tests/inventory.spec.ts`, `locating.spec.ts`, `gallery.spec.ts`, `section-ruler.spec.ts` and `scaffold.spec.ts` all pass. `gallery.spec.ts`'s own container-query proof is updated to the new area strings, not deleted. Screenshots at 1440 and 390, in light and dark, were kept in the scratchpad for review. They are not committed.
