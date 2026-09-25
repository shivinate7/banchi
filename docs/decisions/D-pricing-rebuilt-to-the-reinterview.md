## D-pricing-rebuilt-to-the-reinterview — Pricing is one list with the rows that need the owner on top, a slim bar, a Live tab, and the drawer folded into the product view

**What this records.** D277 holds the owner's answers to the Pricing re-interview. This entry
records what the b-pricing lane built to those answers on 2026-09-25. It also records the calls
the build had to make where an answer did not reach the code. Each call is named here so a
reviewer can reverse it. None of them changes what a send writes, how a quantity is computed,
or the double-send guard. Those belong to the send entry, D273.

### What is built, answer by answer

- **Q1, every row.** One list. The rows that need the owner come first under "Needs you". The
  rest follow under "Ready", highest market first. Rows with nothing to add come last, under
  the server's own heading. `app/src/Pricing.tsx:takeArrival` takes the order.
- **Q2, which rows need the owner.** `app/src/Pricing.tsx:flagOf`: no market price, a market of
  $5 or more, or a typed price 25% or more away from today's market. Each flagged row carries
  one chip that says why. The count on the owner's store is not measured here, because this
  lane does not read the live store.
- **Q3, Send with unpriced rows.** The screen sends. The bar says how many rows need a price,
  and those rows stay on the list. The server still refuses the whole file while any row with no
  market price is unanswered (`pipeline/decisions.py:Decisions.blocking`). Changing that changes
  what a send writes, so it is b-runs' work, not this lane's. It is reported as open.
- **Q4, the slim bar.** Sticky at the top of the column at 1440 and 720. On a phone (below the
  shell's 640 step) it is one line pinned above the tab bar: the press and a More press. More
  opens "Download the file instead" and "Check what is live" beneath it.
- **Q5, the rule and the cut-off.** One line above the list: what the rule does, and the
  cut-off once. "Change" opens one sheet with the rule, the custom rule, the cut-off, and a
  run's own cut-off.
- **Q6, mark-down.** A Live tab on Pricing with the same rows. It opens the newest live read,
  or says there is none. Its line says how the read was taken, with "Change" and "Read again".
  The Mark-down sheet (`Markdown.tsx`) is deleted. Its one form became the Live tab's settings
  sheet, and its "drop an export file" door is kept there as a file field.
- **Q7, one press.** The Live tab's Send writes the file, reads what is live, sends and makes
  live in one press. There is no press that puts the old prices back.
- **Q8, the value list.** Deleted from Pricing (`ValueBands.tsx`). The Inventory lane builds the
  sort.

### The calls this build made

1. **The cut-off is not a drift.** A card worth less than the cut-off lists AT the cut-off
   (D99). A typed price at the cut-off on such a card is the floor at work. Nothing can list
   lower. Q2's "25% or more away" would flag every cheap card and put it on top. On the demo
   that was 26 of 28 flagged rows. So a typed price equal to the cut-off on a card whose market
   is under it is not flagged. Reverse it by deleting `clamped` in `flagOf`.
2. **The order is taken once per load (D118, D181).** A typed price can give a row a flag, and
   the chip appears on the row. The row does not move under the hand. The next load re-ranks.
   A held row stays where it was, and a released one too (UX-071).
3. **An empty status slot is not drawn.** Its answers here are states of a load or a failed
   save. A state of a load is a run that could not be read, or cards waiting in Review. The
   trend sentence has a reserved place on the rule line. A preset's note is said in the sheet
   that was pressed. An always-empty slot was a band of nothing above the list.
4. **The drawer folded into the product view (D278).** Every product name is a `ProductLink`
   and opens the one product sheet, which reads by SKU. So the history works on the
   every-run landing too, where the drawer was dead. `T` opens it for the row under the pointer
   or the focused row. It is a press now, not a hold: the sheet is a surface that stays, and
   Escape closes it. The photograph is its own sheet, from the thumb or `P`, with "Next copy".
   `PriceHistory.tsx` keeps only the two drawing helpers that three screens share.
5. **The snap keys are the columns the row draws.** `m` (Market), `l` (Lowest) and `n` (the
   asking price, on the Live tab). `s` and `d` are gone with the Compare toggle. A key that
   reaches a hidden column breaks D49's rule that a letter is a command.
6. **Trends read every row.** Each row asks its own run, so "Load trends" works on the every-run
   landing. Below a 900px column the trend and Lowest columns leave the row, and so does the
   press.
7. **The link opens what it counted (UX-078).** The published demo no longer narrows Pricing to
   its first run on arrival.

### What protects the older decisions now

- **D208, one verdict.** The bar is the verdict. The legend, the deck and the verdict sentence
  are gone.
- **D98, one figure for the cheap half.** The same input, in the Change sheet. The rule line
  states the figure once.
- **D105, mark-downs live where prices are decided.** The Live tab, on Pricing.
- **D49 and D86, a missing price is unknown.** A row with no price cannot go. It leads the list.
- **D156, every unsent copy is one worklist.** Unchanged. The default is still everything unsent.
- **D118, a press never moves the rest.** Undo has a fixed slot. The trend column is always
  reserved. The order is frozen per load.

### Not mechanized

**NOT MECHANIZED:** whether a flag is a row the owner would want to look at is a judgement
about the owner. `app/tests/pricing.spec.ts` asserts the three flags and the order they sort
in, which is what a machine can see.
