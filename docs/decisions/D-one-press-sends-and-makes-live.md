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
| Q7 | Where does a manual "Check what is live" press live? | On Pricing's send card and on the Live tab, which replaces the Mark-down sheet. |
| Q8 | What happens to copies in a file that was written and never sent? | Pricing names them, with "Take them back". Amended 2026-09-24: "Take them back" is offered only after a live check has run past the wait for that receipt. |

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
- A failed push rolls back at TCGplayer. Its copies go back to the list ONLY when TCGplayer
  answered the rollback, or when no upload was opened (the 2026-09-24 review).
- The one press is the only route that publishes. No session, test or dry run calls it. The
  repo's rule that a block-list fails open applies here: a dry run uses an allow-list.

The owner still decides every price on Pricing before the press. The live check after the lag
reports any copy that did not land.

### Every send first reads what is live, and never doubles a quantity

The owner ruled a double-send guard in the Pricing re-interview, in these words:

```
maybe before submitting prices there's a mandatory reconciliation that auto runs seeing my
sales and live inventory
```

So every Send runs a live reconcile first, by itself, for new listings and for mark-downs
alike. It reads the live export and the sales. Then it sends only the copies TCGplayer does not
already hold. A send that would double a quantity is refused or trimmed, and the screen shows
what it trimmed. When the live check cannot run, because the owner is signed out or TCGplayer
is slow, Send refuses. It says why and offers "Try again". It never sends blind.

This amends D106 further: its two presses were one margin, and this read is another. It amends
D87 (the reconcile is store-wide): the reconcile is no longer only a check after the fact. It
is a gate in front of every send. The guard must go red on a double send before any listing
file uses the transport.

### An open question for the owner: D100's check on the transport

D100 (nothing is deleted to lower a price) makes the transport refuse any row whose Add to
Quantity is not 0. That check is what makes a re-upload of a price file harmless. A listing file
adds quantity, so it cannot pass that check as the transport stands. The send rulings do not say
what happens to the check. This entry does not claim that the guard replaces it. The question
comes from the send rulings, and it goes to the owner. Does the check stay for price-only files
and change for listing files? Or does something else hold D100's outcome for a listing file?

### Four more answers from the Pricing re-interview

- **Unpriced rows.** Send takes every ready copy. A row with no price stays on the list.
- **Mark-downs.** One press sends a mark-down and makes it live, as for listings. There is no
  "Put the old prices back" control. The Live tab on Pricing replaces the Mark-down sheet.
- **Nothing beside Send.** The caps (at most N per card, only above the cut-off) are removed
  from beside Send. "Split in two files" moves under "Download the file instead". Where the caps
  live now is not ruled.
- The screen shape is the entry with slug `pricing-is-one-list-and-one-send`.

### The other decisions this touches

- **D33 (the pipeline is reachable from a screen, and one route can spend).** Kept. The cost
  check starts when the sheet opens. The spend press does not exist before the figure shows.
- **D87 (the reconcile is store-wide).** The live check moves off Runs. It runs after the lag
  and shows a preview only when something needs a decision.
- **D105 (the markdown lives where prices are decided).** Extended: listings are sent from the
  same place. The Live tab on Pricing replaces the Mark-down sheet. The sheet's shell command
  goes, and the "Check what is live" press sits on the Live tab (Q7).
- **D156 (every unsent copy is one worklist).** A run's status names its real next step, for
  example "Ready to write", never "Needs pricing" once pricing is answered.
- **The export fetch and its scope (D64, D65, D76, D166, D170).** The rules stay. The fetch now
  starts when a reading finishes. A refusal becomes the run's next step.
- **D174 (a press claims the cards it is about to buy).** Unchanged for a read. A send now
  claims its SKUs in the same shape (`store/sendclaims.py`, below).

### What is still open

1. D100's check on the transport (above).
2. Where the caps live, now that they are removed from beside Send.
3. The Runs screen's final shape (Q6).
4. Whether a run stays open until its copies are live, or only until they are sent.
5. Five measurements the review listed before any build. The first pushes one real row to
   Staged and rolls it back. It touches the real account, so it needs the owner's word.

### What is built

BUILT BY THE RUNS LANE, AND NEVER RUN AGAINST THE REAL ACCOUNT. Every path below is proved on a
loopback portal in T7 (`check_send_guard`, `check_send_press`) and in `pricing.spec.ts`. The
first real send needs the owner's word.

- The double-send guard is `pipeline/sendguard.py`. After a send, the live count at TCGplayer
  plus the copies added may never be more than the copies on hand. It reads the fresh live
  export and the shelf. It does not read the store's listing records. `emit --live-guard`
  lowers each card's send quantity to the room that is left, and it names each trim. An export
  with no `TCGplayer Id` or `Total Quantity` column is refused, never read as zero.
- The one press is `POST /pipeline/send` in `server/send_routes.py`. In order, it fetches the
  live export, runs `reconcile --live --write`, runs `emit --live-guard`, pushes the file and
  publishes the file. If the live read fails, the press refuses and nothing is written. With
  `download: true` it stops after the file.
- The check after the lag is `POST /pipeline/live-check`. It runs only when a request asks.
  `app/src/liveCheck.ts` asks on a visit to Pricing or Home. Otherwise one timer in the page
  asks when the wait ends. The first check is due two minutes past the lag, never at it.
- Matching runs by itself (Q4): `POST /pipeline/runs/<name>/match`, called by `#/runs` for
  every run it sees waiting for a match. A refusal is recorded beside the run and is its next
  step, and it is not asked again until its own "Try again" press. T7 `check_run_match`.
- `cli/cmd_reprice.py:published_recently` now reads the send receipts too. Before, a listing
  that went live had no lag guard.
- A mark-down has one press too: `POST /pipeline/markdowns/<stamp>/send`. It keeps D100's
  zero-quantity rule exactly as it was.
- The transport takes a listing file only through a keyword argument, `listing=True`. That is
  the open question above, and it stays open.

The pricing lane follows, with the rest of the screen and the Live tab.

### Round 2: what the adversarial review found, and the fixes (2026-09-24)

The review of round 1 failed. Each finding is fixed at its cause, and each has a T7 case in
`check_send_hazards` that went red on the round-1 build before the fix.

- **Two presses at once.** The server ran four request slots, and nothing stopped two sends.
  Now the server takes one press at a time and refuses a second by name. The rule that holds
  across processes and restarts is a store claim in D174's shape: `emit` checks every live
  claim, and writes its own, in the same store write that counts the copies sent
  (`store/sendclaims.py`, schema 11). A plan whose basis moved while it was deciding is
  refused. Each press writes its file into its own directory, and a stamp can no longer clash
  inside one second.
- **A dropped connection.** The receipt is written before the first byte leaves, and it says
  `sending` while the press runs. The send card reads it after a dropped connection and offers
  no second press.
- **An unclear answer.** A publish that TCGplayer answered 500, a publish that never answered,
  and a rollback that TCGplayer refused are UNKNOWN. The copies stay counted, the claim holds
  their SKUs out of every send, and the card names the upload that may wait in TCGplayer's
  Staged list. Only a live check past the wait resolves it.
- **Take them back (the owner's ruling, 2026-09-24).** Offered only after a live check has run
  past the wait for that receipt, and it returns only the copies the check did not find.
  Before that, the card says when it will be safe.
- **Timeouts.** On this Python, `socket.timeout` is not a `TimeoutError`, so a slow answer
  escaped every caller. Every socket failure on the transport is now `tcg_unreachable`.
- **Counts.** TCGplayer's accepted count is reconciled against the rows sent. The card never
  says more went live than TCGplayer took, and the check names the rows it turned away.
- **Two receipts, one rise.** The check hands one live rise to receipts oldest first, so one
  rise never confirms two sends.
- **The same bytes.** The refusal of a second push of the same file bytes holds only inside
  the upload window, where the live read cannot see the first push yet.

WHAT IS NOT KNOWN, AND WHERE THE CODE DOES NOT GUESS. TCGplayer's upload answer carries a
count of rows it took, not which rows. So a turned-away row is named by the check after the
wait, not at the send. Whether the portal's `Messages` name the rows is not measured.

