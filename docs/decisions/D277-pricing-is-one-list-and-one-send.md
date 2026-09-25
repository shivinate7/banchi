## D277 — Pricing shows every row with the rows that need the owner on top, one slim bar holds Send, and the value list moves to Inventory

**The owner's rulings, 2026-09-23, in the Pricing re-interview.** The first round of the UX
review held Pricing back for its own interview. A deliberation walked the screen, drew a
proposal and put ten questions (Q1 to Q10). The owner answered all ten. The owner also ruled
the double-send guard and the refusal when the live check cannot run. The send entry records
those two.

The record is `docs/reviews/ux-2026-09-23/`, file `RULINGS.md`. The plan is
`docs/specs/ux-overhaul-2026-09-23.md`. The send itself is the entry with slug
`one-press-sends-and-makes-live`.

### The answers

| Q | Question | The owner's answer |
|---|---|---|
| Q1 | What does Pricing show first? | Every row. The rows that need the owner go on top, then the rest by value. |
| Q2 | Which rows need the owner? | No market price, or worth $5 or more, or a typed price 25% or more away from today's market. Count these on the owner's store first. |
| Q3 | What does Send do when some rows have no price? | It sends every ready copy. The rows with no price stay on the list. |
| Q4 | Where does the slim bar sit? | At the top and sticky at 1440 and 720. On a phone, one line pinned above the tab bar. |
| Q5 | Where do the store rule and the cut-off live? | One line above the list, with "Change". Change opens one sheet: the rule, the cut-off, and a box's own cut-off. |
| Q6 | How does the owner mark down live listings? | A "Live" tab on Pricing, with the same rows. The Mark-down sheet goes. |
| Q7 | Does one press also send a mark-down? | Yes, one press. There is no "Put the old prices back" control. |
| Q8 | Where does the value list go? | To Inventory, as a "by value" sort in the shared sort control. It leaves Pricing. |
| Q9 | Does Pricing offer to make the owner's pattern the rule? | Measure the typed prices first. If most follow one pattern, Pricing offers "Make this the rule" once. |
| Q10 | What sits beside Send? | Nothing. The caps (at most N per card, only above the cut-off) are removed from beside Send. "Split in two files" moves under "Download the file instead". |

### The premises that no longer hold

**D208 (Pricing states its verdict once).** D208 kept a four-word legend and a verdict sentence.
The header now reads "22 of 22 decided", so the legend explains words that are not beside it
(TXT-06). The figures have their own lines, so the sentence repeats the heading (TXT-10). The
sticky phone bar is 174px to 186px, a third of the screen (UX-007).

**The screen as a form.** The deliberation measured the demo. The first row sits at y = 680px
at 1440 and 1.4 screens down at 390. A row is 260px tall on a phone. The rule already prices
most rows, and the screen draws every row at full weight. So the owner cannot see which rows
need a hand.

**D98 (the cheap-card figure is the control).** D98 made the cut-off figure a large input on its
own panel. The panel costs the first screen. How often the owner changes the figure is
unmeasured.

**D159 (the band is copies, and the drawer is the first answer).** D159 put the value list on
Pricing as a lens. It prices nothing. It finds cards to pull, and each row already links to
Inventory.

**D105 (the markdown lives where prices are decided).** D105 kept a Mark-down sheet with its own
steps. The sheet opens with 92 words and a shell command (UX-017, UX-120).

### What each decision protected, and what protects it now

- **D208** protects one statement of where pricing stands. The slim bar is that statement, and
  the deck, the legend and the sentence go.
- **D98** protects one figure for the cheap half, typed at display size, never a coupling to a
  moving floor. The figure stays the same input. It moves into the one "Change" sheet, beside
  the rule and a box's own cut-off. The line above the list says it in words.
- **D159** protects a list of cards by value, to pull for bulk sale. It becomes a sort on
  Inventory, where the cards are.
- **D105** protects one place where prices are decided and sent. The Live tab keeps mark-downs
  on Pricing, with the same rows and the same Send.
- **D49 and D86 (a missing price is unknown, not low).** A row with no price still cannot go.
  Q3 lets the other rows go without it.
- **D156 (every unsent copy is one worklist).** Kept. The default is still everything unsent.
- **D7 (duplicates aggregate by SKU).** Its per-send cap is removed from beside Send. Where the
  caps live now is not ruled.

### What is still open

- The count of rows that need the owner on the real store (Q2). If it is short, the review
  proposed a one-card-at-a-time pass instead. The owner sees the count first.
- The share of typed prices that follow one pattern (Q9).
- Where the caps live, now that they are removed from beside Send (Q10). Ask the owner.
- Whether a mark-down with no way back needs a guard of its own. Q7 removed the control, and
  the send guard in the send entry reads what is live before any send.

### What is built

NOT BUILT. The owner released the pricing and runs lanes once this re-interview and the flow
interview were done. Both touch Pricing's write bar, so they run in sequence. The runs lane goes
first, with the send, live and reconcile plumbing. The pricing lane follows, with this screen.
The Pricing drawer folds into the one product view in the pricing lane.
