## 33 — An answered queue entry can never resurface, even when it is wrong

Found while measuring PR #444's archive-refusal-mechanization analysis, its own 15
subjects, against the real
store, and named again here on the owner's ruling: *"mark this gap known but do not address
right now."*

**The gap.** `store/queues.py:Queue.upsert` refuses to re-queue a position that already
carries `cleared_by_human` (D167's own promise: an answer must outlive the question that
produced it). That refusal has no exception for an answer that later proves wrong. A card
answered on Tuesday, then contradicted by a live catalogue lookup, cannot reach a human
through the standing queue again. The same is true of a card whose own SKU's two copies
disagree about the number (the sku-number-contradictions build, a separate PR, kept
separate on the owner's ruling). The mechanism that stops the queue nagging on a settled answer is the same
mechanism that buries a wrong one.

**What it costs today.** All 16 of the archive sweep's remaining refusals are in exactly
this state, measured against `inventory/store.sqlite`. 13 carry a real `answered` event. 3
carry no logged event, but are `cleared_by_human` with reason `no_catalog_row`, first seen
2026-09-01. Every one of them is permanently unarchivable through the review queue as it
stands. The count will grow. A SKU-contradiction is the same shape of problem, from a
second source, and it has no queue to land in either.

**Two ways out were identified. Neither is chosen here.**

1. Widen `Queue.reopen` (D28's undo window) past the same-sitting reversal it was built
   for. A later run could then reopen a stale answer. This blurs a control built for a
   person reversing themselves while the tap is still warm. It becomes a control a machine
   triggers months later — a different caller, a different risk.
2. Add a third state beside `open` and `cleared_by_human`, something like `contradicted`.
   A disputed answer could then surface without erasing the original one. This is a real
   product decision. A third state touches every reader of the queue's two-state
   assumption, and it is not decided here.

**Why it is not fixed now.** Both fixes change a mechanism (D167, D28) that other code
already trusts to behave exactly as documented. The owner's ruling is to know the gap and
revisit it on purpose, not patch it inside this task's own scope.

**NOT MECHANIZED:** nothing here checks whether an `answered` entry has since been
contradicted. That check is the very capability this entry says does not exist yet. A
future build that closes this gap should add its own guard beside whichever fix it picks.

Cites D167 (the queue's refusal to re-ask an answered entry) and D28 (the undo window
this gap does not widen). Cites PR #444's archive-refusal-mechanization analysis, where
the 16 cards were counted, and the sku-number-contradictions build, whose findings have
nowhere to go while this gap stands.
