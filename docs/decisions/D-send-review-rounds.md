## D-send-review-rounds — The send press's review record: each round's findings, and the fix for each

The review record of `D-one-press-sends-and-makes-live` (one press sends and makes live). That
entry holds the rulings. This entry holds rounds 2 to 6 of the adversarial review. Each round
failed the build before it, and each finding was fixed at its cause with a case that went red
on the build before the fix. This entry was split out of that one in round 5, so that entry
stays inside the entry budget. Nothing below is a new ruling.

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


### Round 3: what the second review found, and the fixes (2026-09-24)

The review of round 2 failed. Each finding is fixed at its cause, and each has a T7 case in
`check_send_review_r3` that went red on the round-2 build before the fix. F3 is a screen
finding, so its red case is in `app/tests/pricing.spec.ts`.

- **F1, a failure after the receipt.** A step that timed out, or any error before the send,
  left the receipt at `deciding`. It then read `sending` while the server lived, and both
  buttons stayed off. Now every failure after the receipt exists ends known. If the press
  counted copies, the send is UNKNOWN: the copies stay counted, the claim holds them, and the
  check past the wait resolves it. If it counted nothing, it leaves no receipt and no claim.
  A receipt reads `sending` only while its press runs. In this server that is exact: the one
  press lock names the press it runs.
- **F2, a mark-down press that died.** A dead press left a claim that nothing released. Now a
  mark-down claim that no running press holds is an unknown mark-down. The check past the
  wait compares TCGplayer's prices with the file's, and releases the claim. The owner never
  sends a price again to free the cards. An error inside a mark-down press is held when the
  push had started, and released when it had not. A listing send over those cards is refused,
  and the refusal names the price change by the time it was pressed.
- **F3, the Staged warning.** The card keeps "do not publish it there" after the check, beside
  Take back, for as long as it draws the receipt.
- **F4, the baseline.** The receipt records what TCGplayer held before any copy is counted.
  A press that dies after the count leaves the check a real baseline, not zero. Sales since a
  send are dated by the card when the receipt has no figure.
- **F5.** A press that adds no copy writes no claim.
- **F6.** The claim's stale check has its own case: a hand `emit` between a press's plan and
  its save makes the press refuse. The case is red with the check removed.
- **The listing door and D100.** REVERSED IN ROUND 5 on the owner's ruling, "Allow mixed".
  A listing row must add at least one copy. A row adding none
  only moves a price, and a price goes through the price door, where D100's zero rule holds
  whole. The open question above still stands for the listing door as a whole.
- **A mark-down's new price. REMOVED IN ROUND 4: the premise was false.** Round 3 made a
  listing send leave out the cards that a mark-down re-priced inside the publish lag, so that
  a listing row could not put the old price back. But `reprice apply --write` writes the new
  price into the price file (D86), and a listing row takes its price from that file. So a
  listing send always carries the new price, and the wait only held copies back with no
  reason. See round 4.
- **A downloaded file (the orchestrator's call).** Take them back is offered only after a
  SECOND check, one wait after the first. The wait counts from when Banchi wrote the file, and
  the owner uploads it by hand at an unknown time.


### Round 4: what the third review found, and the fixes (2026-09-24)

The review of round 3 failed. Each finding is fixed at its cause, and each has a T7 case in
`check_send_review_r4` that went red on the round-3 build before the fix. H2 is a screen
finding, so it also has red cases in `app/tests/pricing.spec.ts`.

- **H1, one rise, two credits.** The check gave each SKU's live rise to the OLDEST due
  receipt, of any kind, and each check started again from its own baseline. Two sequences
  proved it on the stand-in portal. (A) A downloaded file that nobody uploaded took the credit
  for a send that went live, so the check offered the live send back. A second press would
  then send its copy again. (B) Two checks, each from a baseline read before the first send
  showed, both read "1 of 1 found" while TCGplayer held one copy. Now the check keeps ONE
  CREDIT LEDGER PER SKU. The ledger is the per-SKU credit that each receipt's own check
  records, so it has no second file to drift from the receipts. The rise is measured once,
  from the oldest baseline of every receipt whose copies can be inside it. The copies that an
  earlier check credited are taken off first, so a rise is never credited twice. The rest goes
  first to sends that Banchi saw go live, then to sends it did not see confirmed, then to
  downloaded files, because their upload time is not known. A send still inside its wait is
  served before a downloaded file, and never before another send.
- **H2, the warning after Take back.** The card did not draw a taken-back receipt, so "do not
  publish it there" went at the moment it matters most. A downloaded file had no warning at
  all. Now a taken-back receipt keeps its warning until the owner dismisses it: a send whose
  upload may still wait in Staged, and a downloaded file, which must not be uploaded now. The
  dismissal is `POST /pipeline/sends/<stamp>/dismiss`, and it changes nothing but the receipt.
  A receipt with a warning stays in the list, whatever its age.
- **H3, the price wait (the orchestrator's call).** Removed, with `--price-wait` and the
  receipt's `waiting_on_price`. The T7 case now proves that a listing send right after a
  mark-down carries the marked-down price.
- **H4, two Take back presses at once.** Both took the copies back. Now Take back reads the
  receipt again inside the store's own write and sets `taken_back_at` there. The store write
  admits one press at a time, from any process, so the second press finds the copies taken.
- **The route shape.** The screen's Take back and file routes matched only the round-1 stamp.
  Every press since round 2 writes a stamp with a random tail, so both routes answered 404
  for every new receipt. The routes now read the send module's own stamp pattern.


### Round 5: the mixed send, and two carry-overs (2026-09-24)

Each case below has a T7 case in `check_send_review_r5`, or a spec case in
`app/tests/pricing.spec.ts`, that went red on the round-4 build before the fix.

- **The mixed send (the owner's ruling, "Allow mixed").** One press lists new copies and
  reprices live cards. `D-one-press-sends-and-makes-live` states the rule and where the rows
  come from.
- **Two presses in one second.** The receipt list sorted by directory name, and a stamp is the
  second then a random tail. So the older press could read as the newer, in the list, in the
  credit ledger's order, and on the send card. Now each receipt records the moment its press
  took its stamp, to the nanosecond (`pressed_ns`). The server runs one press at a time, so
  that figure only rises. The list and the ledger both order by press time, then by that
  figure. The send card no longer compares stamps: it stands on the server's newest receipt
  once the list holds its own press.
- **Two warnings at 390 wide.** Two taken-back warnings made the sticky send bar about half the
  screen high. On a phone each is now one line: its own imperative, a press that opens the full
  sentence, and Dismiss. Only Dismiss takes it off the card, as round 4 ruled.


### Round 6: the fresh review of round 5, and the orchestrator's rulings (2026-09-24)

The review of round 5 failed with three blocking findings. The orchestrator ruled on the
owner's words, "what if i want to edit some prices while also setting new ones?". Each case
below has a T7 case in `check_send_review_r6`, or a spec case in `app/tests/pricing.spec.ts`,
that went red on the round-5 build before the fix. The reviewer's probes P1 to P7 are cases
there, except P6, which found no defect.

- **B1 and B2, a price the button did not name.** The screen compared a typed price with the
  join's old export, the server with a fresh one, and the server counted every corpus answer as
  typed. So a Live tab preset, or a mark-down written and never sent, could go live on the next
  send. Now only a SKU the owner typed on the worklist in this visit rides. The screen sends it
  with the price and the live price it drew, and the server refuses a named price whose live
  price moved since, by name.
- **B3, the Staged test.** The owner's test of Staged is one call by hand to the transport, not
  a press, and nothing is built for it. A mark-down's rollback is now recorded as not live and
  "check the Staged list". Its answers cannot ride a send after B1.
- **S1, the floor.** A named price under `policy.threshold` is refused and named.
- **S2, a crash mid-push.** A receipt in phase sending or publishing with a dead holder and no
  record of why reads as possibly staged.
- **S3, a held price change.** A price-only row is claimed at 0 copies, so a mark-down over the
  same card is refused until the check past the wait releases it.
- **S4, a rollback answer.** It is not proof. The press refuses with `send_rolled_back`, which
  the card never offers to retry, and the receipt keeps "check the Staged list" until dismissed.
- **N1, kept.** Qty 0 with a typed price on a live card is the owner's price-only edit.
- **N2, a card that sold out.** A price row on a card with no copy live at the check settles, and
  the card is named.

