## 33 — An answered queue entry can never resurface, even when it is wrong

`store/queues.py:Queue.upsert` refuses to re-queue a position that carries `cleared_by_human` (D167: an answer outlives the question that produced it) and has no exception for an answer later shown wrong. A card answered once, then contradicted by a live catalogue lookup or by its own SKU's other copies, cannot reach a person through the standing queue again. When D239 counted the archive sweep's refusals against the real store, all 16 were in this state (13 with an `answered` event, 3 `cleared_by_human` for `no_catalog_row` with no logged event), and each is permanently unarchivable through the review queue. A SKU number contradiction has the same shape and no queue to land in.

**Outcome at risk.** A wrong answer stays wrong, and the card cannot be corrected or archived through review.

**Closes when.** The owner picks one of two designs. Either widen `Queue.reopen` (D28's undo window) so a later run can reopen a stale answer, which turns a person's undo into a control a machine fires. Or add a third state beside `open` and `cleared_by_human` (say `contradicted`), which touches every reader of the queue's two-state assumption. Nothing checks whether an `answered` entry has since been contradicted, so the build adds its own guard.
