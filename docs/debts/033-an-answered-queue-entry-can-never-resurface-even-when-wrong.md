## 33 — An answered queue entry can never resurface, even when it is wrong

`store/queues.py:Queue.upsert` refuses to re-queue a position that carries `cleared_by_human` (D167: an answer outlives the question that produced it) and has no exception for an answer later shown wrong. A card answered once, then contradicted by a live catalogue lookup or by its own SKU's other copies, cannot reach a person through the standing queue again. When D239 counted the archive sweep's refusals against the real store, all 16 were in this state (13 with an `answered` event, 3 `cleared_by_human` for `no_catalog_row` with no logged event), and each is permanently unarchivable through the review queue. A SKU number contradiction has the same shape and no queue to land in.

**Outcome at risk.** A wrong answer stays wrong, and the card cannot be archived through review. The gap stays in the app on purpose: the app gets no reopen control and no third state.

**Remedy: a back-end repair by an operator session** (Claude Code against the store), not a screen. A repair needs:

- **Finding the cards.** `cleared_by_human` queue entries (`store/queues.py`) that a later fact contradicts: a live catalog lookup that disagrees with the answer, or a SKU whose copies disagree on the number. The archive sweep's refusals list them.
- **What to change.** Reopen the entry or correct the card through the store's own write path (`Store().write()`), never by editing the SQLite file.
- **The owner's word, per repair.** It writes the owner's store, so each repair is named and approved first, with a backup taken before it.
