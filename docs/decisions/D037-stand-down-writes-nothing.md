## D37 — Stand-down closes a question, writes nothing

**A stand-down closes the queued question and leaves the card unwritten.** Ambiguity never becomes a guess, and a card that can never be answered does not return every session. `POST /review/<box>/<index>/stand-down` sets `store/queues.py`'s `cleared_by_human` flag, which `Queue.upsert`, `release` and `open_entries` already honor, with a reason and nothing else.

It is a third thing beside two others:
- an **answer** (D4) writes `sku` and `condition`, and later joins read it as rung 0;
- a **retirement** (D26) writes a terminal state, because the card left;
- a **stand-down** writes nothing to the card. It keeps its slot, photograph and place in the walk, and stays sellable.

Its reasons are its own, `queues.STAND_DOWN_REASONS` (`wasted_position`, `cannot_settle`, `not_listing`). `RETIRE_REASONS` all say the card is gone, and borrowing them would make "stop asking" read as "this card left". The reason is required, because it is the count `docs/DESIGN.md` says nobody took of skips. If `wasted_position` dominates, the fault is upstream in the rig.

The reversal refuses an answered card (`_clearing_event` reads the log, `not_stood_down`) and inherits `_answer_before`'s `renumbered` stop. It consults no listing hold, since it writes no SKU. The screen offers one keyed panel (`X`) naming what each of the three acts does, and it owns the keyboard while open. Retire sits beside it. The mid-box delete stays on `#/inventory`, because it renumbers the worklist's own positions and has no undo.
