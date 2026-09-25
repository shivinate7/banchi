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

### D100's check on the transport, answered: one press may be mixed

D100 (nothing is deleted to lower a price) makes the transport refuse any row whose Add to
Quantity is not 0. That check is what makes a re-upload of a price file harmless. A listing file
adds quantity, so it cannot pass that check. The price door keeps D100's zero rule whole. The
listing door (`listing=True`) takes a row that adds copies behind the double-send guard.

The owner asked, on 2026-09-24:

```
why can't a send include zeros? like what if i want to edit some prices while also setting
new ones? seems like an odd restriction?
```

Nothing technical prevents it. The owner chose "Allow mixed": one press lists new copies and reprices live
ones. So the listing door also takes a row with Add to Quantity 0, a price-only row. That row is
D100's own shape, so a second upload of it changes nothing. D100's outcome holds: nothing is
deleted to lower a price, and the quantity is not a variable.

- **Where the price-only rows come from.** Amended in round 6, on the orchestrator's ruling on
  the owner's words. Only the SKUs the owner typed a price for on the worklist, in this visit.
  The screen sends each one with the price its button counted and the live price the row drew
  (`emit --reprice-live <file>`, `pipeline/sendguard.py:price_changes`). A corpus answer the
  owner did not type there never rides: not a Live tab preset, not `reprice apply --write`, not
  a price typed on an earlier visit. A rule price never reaches a live listing this way. The
  Live tab keeps its own mark-down press.
- **A new copy of a card already live (the owner's ruling, 2026-09-24, round 7).** Its
  listing row carries Banchi's stored price, as before, so a mark-down already made still sticks.
  TCGplayer lists every copy of one card at one price, so the live copies move with it. The
  button names every live copy that moves and its new price, for example "Send 1 copy, 2 live
  copies move to $19.99". The press refuses a move the button did not name, and the receipt
  records each move (`pipeline/sendguard.py:live_moves`).
- **The live price the screen shows (round 7).** The worklist reads what TCGplayer holds off
  the newest live export on disk. Every send and every check writes one. A price change and a
  move are named against it. A refusal carries each refused row as data, so the card says
  "TCGplayer shows $22.03 now. Send $30.00?", and one press sends again with that live price
  named. The server still refuses if the price moved again.
- **Each named price, checked against the fresh read.** Under the store's floor
  (`policy.threshold`, the mark-down door's `BELOW_FLOOR`): the press refuses and names it. The
  live price is not the one the screen drew: the press refuses and names it, so a price the
  button did not name is never sent. TCGplayer already shows that price, or holds no copy: the
  row is left out and named, and the press goes on. Qty 0 with a typed price on a live card is
  the owner's price-only edit, and the button counts it.
- **What stays whole for the rows that add copies.** The live read first, the double-send guard,
  the claim, the check past the wait, and Take back.
- **What a price-only row does not do.** It counts no copy and is never taken back. It is
  checked against every live claim, and it is claimed at 0 copies (round 6). So it never races
  a mark-down or a send in flight over the same card. The check past the wait
  releases the claim.
- **The check past the wait** compares TCGplayer's price with the file's price, per row, the
  mark-down's own test. A price it does not find is named. A card with no copy live at the check
  sold out: it is named and settles. Nothing is offered back: the way a live price changes again
  is another price change.
- **A rollback is not proof (round 6).** `rollbackexportcsv` has never run on the real account.
  So a press that Banchi rolled back refuses with its own code, and it never offers a retry.
  It keeps "check the Staged list" until the owner dismisses it. A mark-down's rollback
  is recorded the same way, as not live. Its answers stay in the price file as the owner's
  record. They never ride a send as a price-only row. A listing row for the same card carries
  the stored price, and the button names the live copies it moves (below).
- **A press that died mid-push** leaves a receipt in phase sending or publishing with no record
  of why. It reads as possibly staged, with the Staged warning.
- **The send card** says what the press does in the owner's words: "Send 3 copies and 2 price
  changes".

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

1. D100's check on the transport: ANSWERED 2026-09-24, "Allow mixed" (above).
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
- The transport takes a listing file only through a keyword argument, `listing=True`. Since
  round 5 that door takes a price-only row too (the mixed send, above).

The pricing lane follows, with the rest of the screen and the Live tab.

### The review rounds

Rounds 2 to 6 of the adversarial review, each finding and its fix, are the entry
`D-send-review-rounds` (the send press's review record). Round 5 built the mixed send above.
It also ordered two presses in one second by press time, and it folded the taken-back warning
to one line on a phone. Round 6 limited the price rows to the prices the screen named.
