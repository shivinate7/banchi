## D-one-press-sends-and-makes-live — Banchi sends the listing file itself, one press makes it live, and the checks after it run by themselves

**The owner's rulings, 2026-09-23, on the flow from captured cards to live listings.** The
owner asked for an agent to review the whole flow in depth, not for a multiple-choice answer.
The agent's report put eight questions (Q1 to Q8). The owner answered each one. This entry
records the answers and the decisions they amend.

The record of the review is `docs/reviews/ux-2026-09-23/`. The plan is
`docs/specs/ux-overhaul-2026-09-23.md`.

### The eight answers

| Q | Question | Ruling |
|---|---|---|
| Q1 | Does Banchi send the listing file to TCGplayer itself? | Yes. "Download the file instead" stays as a second door. |
| Q2 | Is "Put live" its own press? | No. ONE PRESS sends AND makes live. |
| Q3 | How does Banchi check what is live after a publish? | Both ways. An open app checks by itself when the wait ends, with no refresh. A closed app checks on the next visit to Pricing or Home. No server job runs unattended. |
| Q4 | Does matching run by itself when the reading finishes? | Yes. A problem becomes the run's next step. |
| Q5 | Does the cost check run when the Identify sheet opens? | Yes. Open, then spend: two presses. |
| Q6 | What does the Runs screen become? | Decide after the moves land. The route and its name stay. |
| Q7 | Where does a manual "Check what is live" press live? | On Pricing's send card and in the Mark-down sheet. |
| Q8 | What happens to copies in a file that was written and never sent? | Pricing names them, with "Take them back". |

### The premise that no longer holds

D106 (the push and the publish are two presses) says a single button "would spend that margin
for one saved click". The margin is the gap between Import to Staged and Move to Live.

The flow review counted the real cost of the hand path. From capture to live, the owner makes
about 33 presses. The path has 2 trips into the seller portal, 2 downloads and 2 file pickers.
Of 9 steps, 5 hold a real choice. The review also found three hazards in the code:

1. "Write the import file" marks copies `pushed`. Nothing names a file that never left the
   Mac, so its copies stay held out of the next file.
2. A publish by hand in the portal has no lag guard. `cli/cmd_reprice.py` reads markdown
   receipts only.
3. D100 (nothing is deleted to lower a price) records nine SKUs at `2 x pushed - sold`. One
   file went up twice by hand. The app cannot see a hand upload, so it cannot refuse one.

The review recommended two presses. The owner chose one.

### What D106 protected, and what protects it now

D106 protects one outcome: a buyer never sees a price the owner did not mean to publish. The
Staged margin was that protection. For the listing file, the margin is gone, and the owner
accepted that cost. These protections stay, and they are D106's own promises:

- The move is scoped to one upload. `SCOPE_THIS_UPLOAD` is a constant, never a parameter.
- The upload id comes off disk, never off the request.
- A failed push rolls back at TCGplayer. Its copies go back to the list.
- The one press is the only route that publishes. No session, test or dry run calls it. The
  repo's rule that a block-list fails open applies here: a dry run uses an allow-list.

The owner still decides every price on Pricing before the press. The live check after the lag
reports any copy that did not land.

### D100's invariant needs a replacement, and the mechanism is not ruled

D100 makes the transport refuse any row whose Add to Quantity is not 0. That is what makes a
re-upload harmless. A listing file adds quantity, so it cannot pass that check. The outcome D100
protects still holds: one file sent twice must not double a quantity. The review proposed a
receipt guard: the server refuses a second push of a file digest it already pushed.

**The owner has not ruled on the mechanism.** A builder must not send a listing file through
the transport until a mechanism is chosen and proved red on a double send.

### The other decisions this touches

- **D33 (the pipeline is reachable from a screen, and one route can spend).** Kept. The cost
  check starts when the sheet opens. The spend press does not exist before the figure shows.
- **D87 (the reconcile is store-wide).** The live check moves off Runs. It runs after the lag
  and shows a preview only when something needs a decision.
- **D105 (the markdown lives where prices are decided).** Extended: listings are sent from the
  same place. The Mark-down sheet's shell command becomes the "Check what is live" press.
- **D156 (every unsent copy is one worklist).** A run's status names its real next step, for
  example "Ready to send", never "Needs pricing" once pricing is answered.
- **D64, D65, D76, D166, D170 (the export fetch and its scope).** The rules stay. The fetch now
  starts when a reading finishes. A refusal becomes the run's next step.
- **D174 (a press claims the cards it is about to buy).** Unchanged.

### What is still open

1. D100's replacement mechanism (above).
2. Whether the one press also reaches the Mark-down sheet, where D106's two presses live now.
   Q2 names the send, and the sheet is a separate flow. Ask the owner.
3. The Runs screen's final shape (Q6).
4. Whether a run stays open until its copies are live, or only until they are sent.
5. Five measurements the review listed before any build. The first pushes one real row to
   Staged and rolls it back. It touches the real account, so it needs the owner's word.

### What is built

NOT BUILT. The runs lane builds it after the pricing lane frees Pricing's write bar. The
pricing lane waits for the Pricing re-interview.
