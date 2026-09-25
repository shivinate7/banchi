## 35 — emit exits differently on one run and several runs

**The defect.** Run `pkmnscan emit --listed-only` after a full send. Over one run, it prints
"nothing new to send" and exits 0. Over several runs, it prints "nothing to write" and exits
1. The two paths answer one question in two ways.

**Why no screen sees it.** The send route answers `nothing_to_send` for both paths, so the
screen reads one answer. Only a shell caller of `emit` sees the split.

**It predates the b-pricing lane.** That lane found it and did not cause it. Its send matrix
(`check_send_matrix`) pins the current behaviour at the case "suball/listed-sent". A change
to either path turns that row red.

**The fix, not built.** Make both paths exit the same way. The recommendation is exit 1 on
both, with one message. Update the matrix row "suball/listed-sent" in the same commit. The
orchestrator deferred this to its own item after PR 2 (the review rulings, 2026-09-25).

Cites D7 (emit's send controls) and D99 (one press writes one spreadsheet).
