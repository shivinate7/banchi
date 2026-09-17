## D92 — A bare `#` is the count, the key carries a sigil, and the check is what keeps them apart

**A bare `#` on an owner-side screen draws D58's count of the cards in a box, never the store key; a key is drawn only with the `B<box>` sigil D68 gave it.** Recorded and built 2026-09-02, after the owner reported the index on box 3 card 27 as wrong. It was not wrong. Box 3 was carrying two numbering systems and one sigil, and `#27` named two different cards on one screen.

**The two numbers are D58's and they are both correct** — the store key that every write aims by, and the number a person counts to, which moves as cards leave the box in front of it. D58 argues both; this entry decides only which one owns the `#`, which had never been settled.

### What box 3 measured

| | |
|---|---|
| stored indices in box 3 (`RB Epics`) | 723 |
| cards on hand | 647 |
| departed — sold | **76** |
| index 27 | a sold `Astral Heron` |
| card 27 | index 63, `Master Yi, Unstoppable` |
| the two spaces at the top of the box | **76 apart** |
| on-hand cards in box 3 carrying no name, which is what made the row draw at all | 5 |

**Three renderers spelled both spaces `#`, on one screen.** `BoxBrowse.tsx`'s sticky header drew `Section 1 · #1–#82` in count space while the neighbor row beside it drew `#41` from the key. On box 3 those spaces are 76 apart, so `#27` named two different cards on one screen and nothing said which was which.

### The sigil goes to the count, and D68 is not reopened

**`slot` is what a renderer draws and `index` is what a caller addresses with.** `_company` sends both per neighbor, the slot by the same bisect rather than a second derivation. `index` rides unread: D45 makes a copies list a way back into the walk, and a click target needs the key.

**D68's `B3 #27` is exempt BY NAME, and the exemption is the rule rather than a hole in it.** A departed card has no count — `Position.slot` answers null for one by design — so a key is the only number it has. The `B` is what marks it, which is D68's own argument, and it is why that form is not a bare `#`. The rule is therefore: **a bare `#` is a count; `B<box> #` is a key.**

**A frozen count was proposed, measured, and rejected on the measurement.** The owner's first instinct was to give a departed card the count it held when it left. It collides essentially always: of 105 departed records, **104 carry a number a live card in the same box holds right now**, and box 3 has 26 records sharing 18 numbers. That is structural — any frozen count is below the box's live total, so a live card always holds it — and it is D68's own complaint (*"I'm seeing two box 1's"*) reproduced against LIVE cards, which is the more dangerous direction: a live card is one somebody walks to. **The frozen count survives as a fact and not an identifier**, worth drawing in the card panel where nothing can mistake it for somewhere to reach. That half is NOT BUILT — see the cost below.

### What is checked, and what the check cannot do

**`scripts/sigil-check.py` refuses a `#` composed from an expression naming `index`, on the commit path.** Narrow on purpose: it cannot tell a count from a key in general, and a check claiming to would be worse than none. What it catches is the one repeated mistake — reaching for the field called `index` when drawing a figure a hand is meant to count to.

**It found three sites nobody had looked at, on its first run** — `BoxOps.tsx`'s machine receipt naming skipped terminal rows, and `RunPanel.tsx` twice over a capture-directory preview. All three are legitimate: a departed record is in no slot, and `CropSample` carries no slot at all because nothing there has consulted the store. Each carries a `sigil-ok:` marker with its reason. That is the check's real value — not the violations it refuses, but the renders nobody had asked the question about.

**Two prose statements of these facts were the exact reverse of the truth.** `types.ts` told every reader the neighbor index "is a slot a hand can count to, not a store key". `t7_store_and_seams.py` said `Card 17` "IS THE SEVENTEENTH SLOT, NOT THE SEVENTEENTH CARD YOU CAN COUNT" — true when D30 wrote it, made false by D58. `server.ts` had it right one screen away. A comment that is confidently backwards is worse than none: it answers the question a reader came with.

### Two things this deleted, and one it fixed by accident

**The two stored `entry.label` writes are gone** — the mid-box delete's re-key and D83's move. Both composed a label in INDEX space while every route serves one re-rendered in count space; nothing read them, so no wrong number reached a screen. What they left was a field holding a plausible wrong rendering, one forgotten argument from being served. D56 already rules that a rendering nobody can correct is joined at read time, not stored.

**`docs-audit.py`'s `commit path` row was matching flags across the whole hook file**, so a second self-testing check made `audit-self-test` — which D18 requires the hook NOT to run — report as being on the commit path. The match is per line now. A false positive there is worse than a loose one: it accuses the hook of running something D18 forbids.

### What it costs

**The check is text, so a renamed local walks past it.** A nominal type over the two numbers is the fix that could not be evaded, and it was rejected on blast radius. DEBT9 carries the ceiling and the argument. **`PlaceNeighbor.index` is sent and read by nothing**, which is a deliberate unread field. **And the departed card's frozen count is RECORDED AND NOT BUILT**: it needs the event log, because current state plus `state_at` does not reconstruct it — tested, and 31 of 105 records come out wrong that way. It carries a question nobody has answered: what a re-sold card's frozen count means.

**What would reopen this: a neighbor row that becomes a click target, a screen that needs to draw a key inside a count column, or the frozen-count panel.** The first is why `index` is still on the wire. The second is what `sigil-ok:` is for. The third is the one piece of this entry that is a want rather than a build.

### Amended 2026-09-04 — the sweep was carried out, it found one violation, and the check could not have found it

**The sweep the Banchi merge deferred is done, and it turned up exactly one real violation.** `CaptureScreen.tsx`'s undo filmstrip drew `#{slotNumber(target)}`, and `slotNumber` fell back to the raw index whenever `target.label` was null. That target is not hypothetical: `undoStack` composes one from the server's high-water mark whenever the session never saw a capture response — every reload mid-run. So the one screen where the number is a store key drew it wearing the count's sigil, on the row a person presses to undo.

**`scripts/sigil-check.py` was green over that line the whole time, and this is not a hole in it.** It matches the text inside a `#{…}`, and the text there was a helper call, not the word `index`. A helper is a renamed local with a longer name — precisely the ceiling this entry named and DEBT9 wrote down. Nothing has changed about what the check can see; a defect reached the tree through the gap that was already recorded, which is the trigger §9 set for revisiting the nominal type.

**The spelling is `app/src/storeKey.ts` now, with `STORE_KEY` beside it.** Two screens composed `B<box> #<index>` by hand from the same two fields, independently — which is `cardNumber.ts`'s lesson (D67) about the other number a card carries. The reader and the writer of one string live in one file, so a respelling in `join.departed_label` lands on two adjacent lines rather than on however many screens reached for a template literal.

**And the sweep closed the red test the merge left behind, which was a layout defect and not a sigil one.** `PositionLabel.css` reserved the slot column by approximating the key's advance width. A departed row draws a void where the figure goes, so it reserved less than a live row's real glyphs and its path started **2.109px left**. The formula mixed two fonts' `ch` with a per-character factor for a four-letter word: 79.95px computed against 82.06px real. A formula cannot know which half it is wrong about, which is why no better factor was the fix. The column became the LIST's — declared once, reserved by every row, because a row cannot see whether its siblings drew a key. That much survives; the mechanism under it does not, and the amendment below replaces it.

### Amended 2026-09-04 — the column's two terms have different provenance, and only one of them may be a constant

**The ruling above is unchanged: the slot column belongs to the LIST, because a row cannot see whether its siblings drew a key.** What moved is one term inside it. `--pos-slot-col: 5.25rem` is deleted; the column is now `--pos-slot-key` plus `--pos-slot-digits`, and `.position-slot` is `max-content` rather than a hard width.

**A shared column's terms are split by provenance. A term that is TYPOGRAPHY may be a measured constant; a term that is DATA may not.** The 2026-09-04 fix put both in one number, so it was right about the fonts forever and could never be right about the digit count. The figure's width is data — how many cards are in the box — and is spent in the figure's own `ch`, where the browser measures it, off a count `src/CardLocations.tsx` reads from the `place.card` of the copies it is drawing. The key's is typography: a four-letter word in a second font, which no CSS unit gives you, and it is the one constant left — 37.594px, `CARD` at 33.594 plus the 4px slot gap, **measured on the real screen rather than derived**, which is the same discipline that made the previous fix right about the fonts.

**What went wrong is that a box passes 999 cards**, and the owner's largest holds 723. Measured at 1440 against the shipped column: a three-digit row leaves 18.8px between the figure's ink and the path, four leave 5.6px, and five OVERLAP by 7.6px. **None of it is visible to an element-box measurement** — the figure is flex-shrunk to an identical width at three, four and five digits and its glyphs paint outside it. The first draft of the test asserted exactly that and was GREEN against the defect it was written for; the case reads `scrollWidth` and a `Range` over the text node instead.

**A second instance of the same class was already live and nobody had hit it.** `--pos-slot-col` was `rem` while every quantity it contained was `px`, and `app/src/base.css` sets no root font size — so a 12px root font overflowed the column **at three digits, today**. `--pos-slot-key` is `px`.

**And the two-fonts'-`ch` error this entry was written about has one more axis.** `.position-void` declared no `font-family`, so it inherited Inter and reserved 41.63px against the figure's 44.47px of Manrope — the original bug, hidden only by the hard width. Giving it the family left it **3.156px short**: `1ch` is the advance of `0` in the element's own FACE, and Manrope is variable, 14.828px at weight 800 against 13.772px at 400. **A `ch` reservation matching another element's must match the whole face, family and weight both.** The void carries the figure's face for its metrics and paints its em-dash at the muted weight through its own `::before`. `box-sizing: content-box` for the same reason: `border-box` made the key's padding subtract from the digits' reservation rather than add to it — 27.3px short, thirteen times the defect this column was built to fix.

**Every threshold above was observed failing before the case was kept**, five mutations in turn: the shipped column whole (6px of overflow, and 5.59px of clearance against a floor of 11), the digit count hardcoded back to three (8.34px of raggedness), the void stripped of the figure's face (3.78px, **which nothing else in the suite guards**), and a hard width put back (13px of overflow).
