# Pick chip: what the second pill says

Mockup: `pick-chip.html` in this folder. Designer kind: informed. It opens from disk.
Deep links take `#s=<state>&o=<option>&t=<light|dark>`, plus `r=1` (draw the reserve), `b=1` (draw the For chip),
`x=1` (the sample walk also holds the extra state) and `h=<ids>` (hidden options).
States: `split` (Pick 4, 3 here), `split2` (Pick 3, 2 here), `one` (Pick 1), `short` (Pick 3, 2 short), `both` (the extra state).
Options: `here`, `hereof`, `elsewhere`, and `main` (the chip on main, for reference).
Every frame is drawn in light and dark at 1440 and 820. Under each frame, a line reads whether the pick chip is whole,
how much of the set name shows, and whether the finish and rarity pills clip.
The repo's CSS is inlined as is: tokens.css, the kit's pill rules, BoxBrowse.css's band, and Orders.css's chip.

Pane widths. 1440: the card pane is 820px. This was measured on the public demo's walk, and its lead figures measured 392px.
820: the card pane is 692px, from the CSS (`.orders-stage.is-walking .orders-layout`, one column while walking). The demo
build is older than the walking layout, so it shows the two-column 408px pane and cannot check this width.

1. **Second pill wording.** The pill says how many copies of the Pick figure this stop holds.
   Three options, each with a Hide control:
   - Here count, "3 here". This is the built form. It is 108px with its reserve. Here is less than Pick, so it reads as
     a part: "of the 4, 3 are here". It is also the number the hand pulls at this stop. The 4th copy is implied, not named.
   - Here of total, "3 of 4 here". It names the whole split, but it repeats the Pick figure. It is 129px, and at 820 the
     row cuts it.
   - Elsewhere count, "1 elsewhere". It names the missing copy. But beside "Pick 4" it can read as one more copy (5 in
     all). It sums the other way from "short", which counts copies outside the Pick figure. And the hand must subtract
     to find how many to pull here. It is 136px, and at 820 the row cuts it.
   Gain of Here count: it is the narrowest, it reads as a part, and it gives the hand its number directly. Loss: the
   reader infers the copy elsewhere from 3 < 4.
   "Another stop" and "later" are not used. Stops have no name on screen. A copy at another stop can sit at an earlier
   stop (`OrdersWalkPane.rowsOf` keeps the solver's stop order), so "later" is not always true.
   Pick: Here count. The built markup matches.
2. **Tone.** Pick is the accent pill, "here" is the default neutral pill, and "short" is the warn pill. Outline is not
   used for "here", because outline pills shrink and clip in this row (`.browse-hero-sub > .bn-pill-outline`). Live
   (vermilion) is reserved. The default tone keeps "here" one step quieter than the accented Pick figure.
   Pick: neutral default. The built markup matches.
3. **Order: Pick, then here, then short. The chip ends the facts row** (D313, nothing moves unless the person moved
   it). Pick: as built. The built markup matches.
4. **Reserve.** There is one invisible reserve for each pill combination that the walk has shown, each at the peak
   figure (`OrderPickPane`'s `peak`). Use the "Reserve outline" control to see it. With the sample walk the chip is
   108px wide. With the extra state in the walk it is 163px. The "here" reserve uses the peak figure, which is one more
   than any real here count can be. That costs a few pixels and never moves anything. Pick: as built. The built markup
   matches. A change to the wording must change both the live text and the reserve's `data-text` strings.
5. **Here and short together (the extra state, `with.both`).** The brief does not name it, but the code draws it:
   "Pick 3", "2 here", "2 short". "Here" counts inside the Pick figure, and "short" counts outside it. The warn tone
   keeps them apart. Unmeasured: whether a stop's `wanted` can be more than the copies on hand. If it can,
   `pickFigureOf`'s `total` (the larger of `wantedLeft` and `of`) puts short copies inside the Pick figure, and
   "Pick 4, 2 short" would mean only 2 can be picked. That is product code. It is reported, not drawn.
6. **Spoken text.** A screen reader reads the live pills as "Pick 4 3 here", with only a space between them. A
   visually hidden comma, or an `aria-label` on `.orders-pick-live` ("Pick 4, 3 here"), would fix it. That is product
   code. It is reported, not drawn.
7. **At 820, the For chip hides the pick chip.** At 820 the band keeps its figures beside the name, so the facts row
   gets about 220px (217px measured in the mockup). When the walk holds several buyers, the For chip comes first, and the row clips the pick chip
   completely. Main's 74px chip clips too, and the built 108px chip clips the same way. Without the For chip, only the
   108px chip fits. The set name and the finish and rarity pills clip at 820 in every option.
   Option "Stack the figures": stack the band in the walk pane, with the figures under the facts, as the band already
   does under 520px (BoxBrowse.css `@container pane (max-width: 520px)`). Drawn in the "Extra" section. Measured: the
   chip, the set name, the finish and the rarity are all whole.
   Gain: the pick chip shows at 820 with any number of buyers. Loss: the band is about 50px taller at 820 (133px to 184px, measured in the mockup).
   Pick: stack it, scoped to the walk's pane (`.orders-cardcol`), so Inventory's pane keeps its shape.
   Departs from: BoxBrowse.css `.browse-hero-head`'s two-column band at pane widths from 521px up.
   Owner grant: yes.
