## 35 — ~~emit exits differently on one run and several runs~~ — CLOSED 2026-09-25, fixed as recommended

**Closed by the fix this entry recommended.** Both paths now exit 1 with one sentence,
`pipeline/merge.py:NOTHING_NEW`. Each path names every card's own reason under it. The send route
reads that constant to answer `nothing_to_send`, where it read two phrases before. The matrix
row "suball/listed-sent" now asks for exit 1, the sentence and each card's reason, on both paths.
The row was red on the old code.

**No screen changes.** No screen presses emit directly. `RunPanel` never calls its step
function with emit. The client's merged emit function has no caller. The send route answered
`nothing_to_send` before the fix and answers it now.

**The defect, as it was recorded.** Run `pkmnscan emit --listed-only` after a full send. Over one
run, it printed "nothing new to send" and exited 0. Over several runs, it printed "nothing to
write" and exited 1. The two paths answered one question in two ways. The send route answered
`nothing_to_send` for both, so only a shell caller of `emit` saw the split. The b-pricing lane
found it and did not cause it.

Cites D7 (emit's send controls) and D99 (one press writes one spreadsheet).
