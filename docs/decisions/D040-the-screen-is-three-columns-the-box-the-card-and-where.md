## D40 — The screen is three columns: the box, the card, and where its copies are

**`#/inventory` is three columns — the box walk, the card, and its copies — at roughly 22/33/45.** Built 2026-08-29, on the owner's own layout. Their words, after being shown the two-column screen: the run box at the bottom and the whitespace to the right of the card photo and description were seriously triggering. Then the design itself: think rule of thirds, the left third sidebar stays put, the middle gets the photo then the correct-claims and remove-card buttons then the description, and the right gets the card locations — maybe 20/35/45.

**The two complaints were one defect, three days old.** `2ec06f8` deleted the body's third column (D38, amended) and re-created it one level down as `.browse-detail`'s third track — `minmax(0, 1fr)`, a RESIDUAL track, so it absorbed every spare pixel in a 1024px content column and held two buttons in 408 of them. Measured: 408x374 of track holding 408x32 of content, **91% empty**, and that track was 40% of the content column's width. The stacked full-width copies list below it was the other half of the same problem — a band that could not fill 1024px, stacked on a list that needed it.

**The file had already confessed it and bet on a justification that did not hold.** `BoxBrowse.css` called the space the residual, named rather than dressed up, and defended it as the rail's declared growth room for the open-question block. Measured on the owner's store the day this changed: **both queue files were empty**, so that block drew on **0 of 543 cards**. The same comment also asserted that this is not the space the owner named — it guessed the complaint was the photo-facts gap. The owner has now named it, and it was the rail.

**The ratio is 22/33/45 and only the first number is derived.** At 1440 the body is 1408px and two 24px gaps leave 1360, so the owner's 20% is 272px — **8px inside the ~280px wrap cliff** `BoxOps.css` was tuned to clear (D38). 22% is 299px. A 285px floor holds it above the cliff at 1280, where 22% of 1200 would be 264. `fr` rather than percentages, because percentages plus two gaps overflow a container that has no slack to absorb it — `.browse-map` is sticky and would be the thing clipped.

**The description left the middle column, and that is the one place this departs from the owner's spec — at their own suggestion.** They asked for photo, then buttons, then description, stacked. It was built that way and measured, and the arithmetic refuses it: the middle column has 715px above a 900px fold, and photo plus buttons plus eleven fact rows needs ~1050. Capping the photo to fit costs it twice — **311x435 (1.35x today) AND 165px of dead slack beside it**, because a height-capped photograph that keeps 63:88 gets NARROWER than its track. The owner then proposed the answer themselves: the description could sit as an aesthetic thing at the top of the locations on the right third. That is what shipped.

**What it buys, measured at 1440x900 on box 2, card 1:**

| | before | after |
|---|---|---|
| photograph | 268x374 | **449x627**, aspect 0.716, **2.81x area** |
| description | 300x318, one column, in the band | 578x171, **two columns**, capping the copies |
| run line | y=1164, 264px below the fold | **y=62**, in the header |
| copies, first row | y=626, 82px rows, 3.35 visible | y=379, 144px rows, **3.62 visible** |
| ink / void | 33.34% / 41.99% | **47.97% / 26.30%** |
| page | 1230 | 1273 |

**Void is a measured number and the target was missed.** The owner asked for less than a fifth of the whitespace. Against an instrument that rasterizes every text and image rect at 8px and keeps only empty area more than 24px from any ink — so normal line-leading does not count and real holes do — the honest result is **41.99% to 26.30%, a 37% cut, not 80%**. Recorded as a miss rather than rounded up, because the owner's own rule is that a number is evidence. What binds it is the copies rows: the largest surviving void component is inside them.

**The copy-row re-tune was asked for and is refused, on the file's own rule.** The owner approved narrowing the row toward D38's measured 83px. At the 586px this column gives it, the row is `8 + place 51 + gap 12 + bar 65 + 8 = 144`, and line one already uses **583 of 586px** — so the position bar genuinely cannot join it. Lowering `CardLocations.css`'s 860px container threshold to 560 does shorten the row to 129px, and it does it by squeezing `.card-locations-place` to 231px, which **wraps the position label**. That file forbids exactly this: the position label is the string somebody carries to a shelf and it must not break. A row that is 15px shorter and lies about where a card is, is not a trade this repo makes.

**And the re-tune turned out not to be needed for its stated purpose.** The column move alone takes rows-visible from **3.35 to 3.62** — the rows are taller and there are more of them on screen, because they start 247px higher. The owner's *tighter width wise yet longer height* is what a 144px row at 586px IS; it was the goal, not the defect.

**The refusal above was of one mechanism, not of the goal, and a different one shipped the same day.** What is refused, permanently, is lowering the 860px container threshold: it buys 15px by squeezing `.card-locations-place` to 231px and wrapping the position label, which `CardLocations.css` forbids by name.

What was missed while writing it is that the row's dead space is not in its first line at all — it is inside the BAR. The bar is four stacked full-width children (box track 16, its caption 14, the section block's 8px track and its own 14px caption) on 570px lines carrying captions that measure ~120px and ~200px. **Beside their tracks instead of under them, the same four parts are two rows rather than four**: bar **65 to 34px**, row **144 to 114px** at 1440 and **188 to 158px** at 1280, copies visible on landing **3.61 to 4.56**, page 1274 to 1092, and the landing void **26.30% to 22.32%** — which takes the cut from this file's own 41.99% baseline to **47%**.

**Nothing is given up for it, and that is checked rather than asserted.** The box track is still 16px, the section track still 8px, the section block keeps its indent, and the captions keep their `#` and `Section` prefixes — all three cues `docs/DESIGN.md` names for telling the two scales apart. The position label stays on one line at 586px.

**The case that guards it had to be pinned to 1440 to be worth anything**, and that is the finding worth keeping: this suite runs at 1280, where the container is 528px and the rejected threshold change behaves identically to the shipped one. Written at the default viewport, the case passed against the very mutation it exists to catch. It is red at 1440 against that change and green against this one, observed both ways.

**And the fold exposed a cliff pointing the wrong way, which is fixed here (860 to 880).** `CardLocations.css` switches the bar into the row at a container threshold, and 860 was chosen against a 144px narrow row. Once the narrow row was 114px the wide branch was producing **126px at the exact width it engaged**: measured across the sweep, 820 to 114, **860 to 126**, 880 to 85, 900+ to 82. Crossing into the better branch made the row twelve pixels taller.

**It was dormant rather than invisible, and that is the worse condition.** The copies container is 612px at 1440 and 528px at 1280, so `min-width` needs roughly a **1980px viewport** to fire at all — nothing in the suite and nothing on the owner's display would ever have rendered it. 860 was picked because columns 2+3 measured 862px at Playwright's 1280, a layout this very entry deleted, so the number was inherited from a dead premise. That is the same defect D41 found in the position label's own comment, in a rule that had no way to fail while it waited.

**The assertion is the PROPERTY, not the new number**: a container that grows may never make a row taller. Pinning 880 would go green on any later change that moves the cliff somewhere else, which is exactly how this one survived.

**What it costs, named rather than buried.** `.boxops-meta` wraps from one line to two — 17px to 33px — because it needs the full 360px track and now has 299. Measured across 299-360px: it is one line at 360 and two below it, with no intermediate. Accepted rather than fixed: it is a metadata line, not a control, in a sticky column that has ~290px of unused height at the owner's size, and holding 360px for it would cost the description its second column.

**The run line is in the header, which is D39's rule held rather than spent.** `BoxRuns` is box-scope content that was living in the content column, so its y was set by the copy count and by whether the claims editor was open — measured, **y=1164 on a six-copy card and y=1572 on an eleven-copy one**, both below the fold. `docs/DESIGN.md` authorizes the header directly (the page title shares a line with the screen's controls and counts), and it was the one item on this screen missing that file's own first-row-of-content-within-150px floor, by 1014-1422px. D39's *it must never become two rows* stops being a promise in a comment and becomes structural: on a shared line it cannot. The left column — where D38's *the left column IS the box* would point — is **rejected by measurement**, not preference: its content box is ~334px and the ordinary ticked state is 428px, so it would wrap to two lines the moment anything is ticked.

**This is the fifth relocation of that slot in four days** (third column, row 3 of the content column, `#/runs` for the panel, row 3 for the line, header). Said plainly because D38 records the first three and a reader is entitled to count. What moved this time is a 32px status line, not the 625-1143px panel that made the earlier moves expensive.

**What would reopen this: a copies column wide enough for an 83px row.** That needs ~860px of container, which three columns cannot give at 1408px of body. If the owner ever works at a width where 45% exceeds 860 — a 1920px display puts it at 828, still short — the row improves on its own through the container query already there, with no change to this entry.

---
