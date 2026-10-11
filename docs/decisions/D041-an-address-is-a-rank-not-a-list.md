## D41 — An address is a rank, not a list

**A position renders as a rank: a muted two-line path with the card number beside it at size, and no separator at all.** The owner picked this from a design pass. The owner had disliked the dot theme. Six treatments were rendered against the real store. The owner picked the **terminal-dominant** address and the **census-triad** meta block.

### It was not a font-size problem

`Box 2 · Section 1 · Card 14` is 27 cells at Martian Mono's measured 0.70em advance = **453.6px**. The track is 448.8px at 1440 and **387.1px** at 1280. It overflowed by 4.8px and wrapped. Of those 27 cells, only **four are digits**: 67.2px, **14.8%**. The words, dots and spaces are **386.4px, 85.2%**. The chrome alone is larger than the entire 1280 track. Shrinking to fit needs **17px**. `CardLocations` prints the same string at 13px seven rows below, on the same screen. A shrink would have made the answer 4px louder than its own footnotes.

**The comment that justified the old size was falsified by a layout change.** `BoxBrowse.css` said the worst realistic label, `Box 100 · Section 12 · Card 543`, draws 521px inside a 630px track. The px figure is right (520.8). **The 630px track no longer exists.** D38 made it 448.8px. A later change deleted the premise and left the conclusion standing. That is the failure `docs/DESIGN.md` and D16 are written against. The class matters more than the instance.

**The three parts are not equal.** `Box 2` is the drawer you walk to. `Section 1` narrows it. `Card 14` is the slot. On this screen the first two are already answered everywhere the eye lands. That covers the box strip, the identity block, every section header, and every copies row. The literal string `Box 2` renders nine times in the document. `Card N` is the only part this panel uniquely supplies. So it is the only part drawn at size. The path becomes an 11px muted two-line stack, and the slot a **44px** figure. The payload goes from 24px to 44px, **+83%**. This screen's whole question is *where is this card*.

**The separator is removed, not restyled.** Nothing takes the interpunct's place. With the path stacked and the slot beside it, no seam is left to mark. `.browse-position-joint` is deleted. That rule painted the dots muted so the parts would bind. This treats the joints as the thing to remove.

**The server string is untouched and stays the accessible name.** `pipeline/join.py:Position.label` emits `Box N · Section N · Card N`, and it keeps emitting it. `PositionParts` recomposes it into key and figure pairs for this screen only. It carries the original verbatim on `aria-label`. A screen reader announces exactly what the store said. That makes the client-side split a VIEW, not an edit of the record.

**`app/tests/fulfillment.spec.ts` is not reached.** Its 32px tabular-figure floor probes `.fulfillment-place` and `.card-locations-place-large` inside `view(page)`. `.browse-position` is neither, and no spec selects it. D31's rule that the Fulfilment spec stays unweakened holds.

### The sidebar is the same complaint with the scarce axis inverted

`cards 543 · sold 0 · fill 543 · next index 544` is 46 cells = **354.2px**. The track D38 narrowed to 299px at 1440 and 285px at 1280. It is **not** a digit-count problem. Box 1's line is four characters shorter and wraps the same way. It is four label words and three interpuncts. That is **277.2px of chrome against 77.0px of digits**. Horizontal space is fixed, and **vertical space is about 290px unused** under the column in D31's resting state. So the block flows DOWN instead of across. Three census figures sit at 16px in a row. `next index` sits on its own line in the muted register.

**`next index` leaves the row because it is not a fourth statistic.** `cards`, `sold` and `fill` describe what is in the box. `next index` is D10's high-water mark, what the allocator hands out next. Four peers joined by dots was a false claim about them. The structure now shows the distinction, so no sentence has to explain it.

**D20's two words are on screen once, on the identity line.** D20 names one failure: a denominator whose meaning switches silently between an open box and a sealed one. `fill` is a fill-**so far** while the box is open. Once **sealed**, it is a frozen capacity.

The qualifier first went on `.boxops-meta`'s fill, then came off. The first version made a duplication exact that had been approximate. `BoxIdentity` sixteen pixels above already renders `133 so far`. Adding the same two words put the identical string on screen twice, nine words apart. **The field stays and only the qualifier goes.** `BoxOps.tsx` promises these key names grep to `inventory.json`, so dropping `fill` outright would break one promise to keep another. D20 is discharged either way. Its rule is that the number is unambiguous ON SCREEN, not that it is annotated at every site.

**Field names stay verbatim in the DOM.** The keys are written lowercase and uppercased by `text-transform` at paint only. A copy out of the DOM still matches the store. `app/tests/inventory.spec.ts` asserts the lowercase text. A `toUpperCase()` in the component turns that case red, though the output is identical on screen. That mutation was run.

**What it costs, measured.** The address block goes from **86px wrapped to 70px**, shorter than the state it replaces. The meta block goes from **33px to 62px**. That height is free in D31's resting state. It is not free once a section is open. There, `.browse-map` is at its viewport cap and `.browse-list` is the scroller. The height comes out of the walk at 25.5px per card row, about 1.2 rows. The ledger variant of the meta block rendered at 81px and about 1.9 rows. It was declined on that number.

### Full treatment for all sites

The owner reopened the decision. The capture screen draws the address in **five** more places, three of them inside running sentences. That makes six owner sites, not three. The earlier text named `.review-position` and `.card-locations-label` only.

**The structure is shared and the size is per site.** The earlier text warned that a 44px figure repeated seven times in a list would be a worse defect. That is now measured. At 44px the copies row goes from 114.17 to **126.48px**, +86px on a seven-copy list. Copies visible on landing drop from 4 to 3. This is the screen whose recorded complaint is that the copies scroll away. So what is shared is the RANK: a muted stacked path, no separator, and the slot as the only thing drawn at size. Each site sets its own figure.

**One component, `app/src/PositionLabel.tsx`, and one declaration per site.** `--pos-slot` is the figure, and `.position-num` is `1em`. A site's whole register is one line in its own stylesheet. The path key is `clamp(var(--pos-path), 0.295em, 13px)`. It is 12.98px at a 44px figure, and 11px at 32, 28 and 20. So `#/inventory` keeps its shipped key to within 0.02px. No other site declares one.

**Proportional scaling was tried and refused.** The shipped ratio is path 11px against 44px, 0.25em. At the review head's 32px, that gives 8px. At the copies row's 28px, it gives 7px. Both are below anything this product draws. Probed independently, **all four new sites landed on the same 11px path against four different figures**. The path tracks each screen's metadata register (`.review-machine` 11px, `.card-locations-boxname` 10px). The figure tracks its payload. Two scales, not one. A single multiplier would claim these screens are scaled copies of each other.

**The figure is free up to 32.3px.** This is one measurement, not five. The two-line path is 33.9px. At `line-height: 1.05`, every figure to 32.3px draws the same 33.9–34.0px block. 20, 24, 28 and 32 cost nothing. 36 costs 4px, and 44 costs 12. This is a property of a THREE-part label. A two-part label has a one-line path, and the plateau collapses. D36 and D24 both contemplate that case.

**Three sites needed a rule the band did not.**

- **The copies list leads with the SLOT, not the path**, because it is a list. Down seven rows, the coarse parts are identical. Path-first would stand seven `BOX 2 / SECTION n` blocks in front of the only thing that differs. That is the dense-gray-table failure `docs/DESIGN.md` names. The layout is height-free **only because the two-line path absorbs `.card-locations-boxname`**. A box with no name pays +17px on every row. D20 made names unique but deliberately NOT required. This is latent today, and nothing warns.
- **An in-sentence label gets the RANK without the geometry.** This is the `run` form. Stacking inside a sentence measured 79px against 23px. It orphaned the trailing period onto its own line. At `inline-flex`, it rendered `BOX 2` above the baseline as a superscript footnote marker.
- **A numeric guard, which the splitter lacked.** `#/inventory` draws only real positions. `#/review` draws D24's pooled label `Pokémon code cards · pooled`. The splitter turned it into a path reading `POKÉMON CODE cards`. It also promoted a lowercase word to a 300.9px figure. Nothing broke geometrically, and no assertion saw it. A promoted slot must be a slot NUMBER, or the label renders whole.

**The Fulfiller's firewall is the component graph, not a selector.** `Fulfillment.tsx` and `CardLocations.tsx:FulfillerCard` do not import the component. So no `.position-*` rule can reach his 32px and 36px labels. Stripping a class prefix cannot breach it. The breach that would happen is somebody lifting the call out of `OwnerCard` into a shared render path. `app/tests/fulfillment.spec.ts` states that as a CAUSE (`.position-parts` count zero). It does not leave the cause to be diagnosed from a font size. Mutation-tested: the lift takes the firewall case red, and eleven other cases with it.

**Two assertions were defective.** Both were written earlier in the same change. `inventory.spec.ts`'s `labelLines` read `getClientRects().length` off a column-flex child. That child is blockified, and it returns exactly ONE rect however many lines it holds. On the shipped tree the label wraps to 2, 3 and 4 real lines at 200, 120 and 80px. The assertion read 1 every time. Its case went red only on a different assertion, which hid the defect. `review.spec.ts`'s `.not.toHaveText(/Card 14$/)` would go vacuous once the DOM text stopped containing that string. It would then pass forever while detecting nothing, the silently weakened shape D16 forbids. Both now assert against `aria-label` or a geometric fact.

**What is not treated, and why.** `.review-row-position` (11px, 23 in the rail), `.review-group-pos` (10px) and the capture screen's bare-integer consumer keep the plain string. The mechanism is RANK. A 10px caption has no rank to spend. Stacking it would cost height in the two lists whose only job is to be scannable. The consequence is stated plainly: **`#/review` renders the address two ways.** `#/inventory` does too. There, the band's 44px figure and the copies list's 28px sit about 500px apart in one idiom. The 1.57 ratio keeps the band dominant. It is the first thing to check if the screen starts to feel noisy.

**One site is untreated for a structural reason.** `CaptureScreen.tsx` at `33126887` composes `Note saved on ${target.card.label}.` as a plain STRING inside a notice payload. There is no element to style, and no JSX to return. It cannot take even the `run` form without changing the notice type across the component. It is named here, because it is the one place the owner's *all* is not met.

**What would reopen this: a two-part label, or a box with no name.** Both collapse a measurement this rests on. The first ends the 32.3px free plateau. The second costs the copies list 17px a row. Neither is hypothetical. D24 pools cards without positions, and D20 leaves names optional.

**The mechanism is reused on the sentence under the label.** See D58, which owns that argument. The one thing it does not share is that its payload takes position rather than size. Two thirty-character names cannot carry a 44px figure.

---

A slotless card ranks like every card, its number column empty.
