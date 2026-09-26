## 37 — under `--cap`, a pending copy and an unseen live copy can both be out

**The limit.** `emit --cap N --live-guard F` spends the cap against the larger of two readings.
One is `copies_out`, the store's count of copies live and pending. The other is the live count
in `F`. The code is `pipeline/join.py:SkuMatch.copies_out`, over `guard_live`. The two readings
can count different copies. A copy that the pipeline sent and has not seen land is pending. The
guard file can show other live copies that the store has not read. Then the true count out is
the sum, and the larger reading is less than it.

**Measured by the lane-end review of send-fixes, 2026-09-25.**
- One pending copy, one live copy the store has not read, and a cap of 2. The send adds 1, so
  3 are out, 1 over the cap.
- Three pending copies, four live copies, and a cap of 5. The send adds 1, so 8 are out, 3
  over the cap.

The overshoot can be as large as the pending count, not only one copy.

**Why the larger reading stays: the owner's ruling, 2026-09-25.** *"Take the larger
(Recommended)"*. For the cap, the sum is the safe direction. But a pending copy that has landed
is in both readings. So the sum counts it twice, and it under-sends on each ordinary re-send
after an import. The larger reading never counts a landed copy twice, so it never sends less
than the sum would. It accepts the overshoot above.

**It can still under-send, on a stale store reading.** A store reading above the guard's count
still closes the cap, because the larger reading wins. The delta review's probe: run
`emit --cap 1`. Then `reconcile --live` sets Dunsparce live at 1. Then run
`emit --cap 1 --live-guard` with a guard file that shows 0. Nothing is sent, but TCGplayer holds
no copy.

**What closes it.** One reading that knows which pending copies have landed.

**A second known wording gap: "asked for none" under the store's own cap.** Assume that the
store's own reading closes the cap, and that the guard also trims the card to 0. Then emit names
the card "this send asked for none of this card". `SkuMatch.nothing_to_add` checks `asked == 0`
before the cap, and the guard writes its trim to `asked`. The delta review's probe: run
`emit --cap 1`. Then run `emit --cap 1 --live-guard` with Dunsparce at 2. Main does the same, and
only the CLI reaches it.

**A known wording gap beside it, left on the orchestrator's word (2026-09-25).** An empty send's
headline has no clause for a card that the cap closes. Emit names that card on its own line,
for example "1 live, at the cap of 1". But the headline counts only the other reasons. Only the
CLI reaches it, because the send route passes no `--cap`.

Cites D7 (emit's send controls) and D59 (the live cap is a per-SKU quantity).
