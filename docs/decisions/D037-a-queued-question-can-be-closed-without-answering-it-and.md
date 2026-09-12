## D37 — A queued question can be closed without answering it, and the card is left alone

**A stand-down closes the question and writes nothing to the card.** Built 2026-08-25, settling a question this repo had carried open since the review screen was built. `docs/DESIGN.md` has said, for as long as Skip has existed, that Skip is an OPEN QUESTION rather than a decision: if nothing is ever skipped, delete the control; if most of a queue is, the screen needs a real defer that records a reason, and that is a decision entry rather than a button.

The owner pulled that trigger, asking why they could not mark something as a known skip — a stand-down on the flag — from the review window itself, for a card that is a wasted position.

**There were two ways past a card and both were wrong for this.** An answer writes a SKU onto a real card, which the operator must not do to a card they cannot identify — `CLAUDE.md`'s hard rule is that ambiguity goes to the queue rather than being guessed. Skip writes nothing at all and a reload forgets it, so a card that will never be answerable comes back every session, forever. Between *invent an identification* and *be asked again tomorrow* there was no third move.

**The third move is one flag, and the flag already existed.** `store/queues.py` was built around `cleared_by_human`: `Queue.upsert` refuses to re-queue a cleared position, `Queue.release` refuses to drop one, `open_entries` hides it. The machinery for *stop asking, and keep not asking across every future run* predates the review screen. The only thing that could ever SET it was an answer — and an answer costs a SKU. `POST /review/<box>/<index>/stand-down` sets the same flag with a reason and nothing else.

**It is a third thing, not a softer retirement, and the boundary is the entry:**

- an **answer** (D4) writes `sku` and `condition`. The pipeline is told what the card IS, and every later join reads it back as rung 0.
- a **retirement** (D26) writes a terminal state. The CARD left inventory; the record stays and the gap is permanent.
- a **stand-down** writes nothing to the card at all. It does not move, change, or leave. It keeps its slot, its photograph and its place in the box walk, and stays sellable if it is ever identified properly. What closes is the QUESTION.

**Its own three reasons rather than `master.RETIRE_REASONS`.** Those four — `pulled`, `damaged`, `lost`, `given_away` — all say the card is gone, and borrowing them would make *stop asking me* indexable as *this card has left*, which is the one thing it must never mean. `queues.STAND_DOWN_REASONS` is `wasted_position | cannot_settle | not_listing`, hand-authored in D22's sense and rendered verbatim beneath its human label the way every reason code on that screen is.

**The reason is required, and it is the instrument `docs/DESIGN.md` says was never read.** That file records Gate B's mistake by name: the run produced a real queue, the owner answered all of it, and *nothing counted how many were skipped first* — so the control stayed exactly as unsettled as it began. A stand-down without a reason would repeat that. With one, the log can finally answer which questions get waved off and why, beside `queue_reason`, the queue's own reason for asking.

**The canonical case is real and was found the same day.** Box 2 position 95 holds a photograph whose mean luma is **1.7 out of 255** — a black frame, captured at 3120x4160 where every other card in the box is 2160x3840. Haiku was shown nothing and returned `Mewtwo ex 009/102` at HIGH confidence; it matched no row, so it queued as `no_catalog_row` with zero candidates, which `POST /review/.../answer` refuses outright as `no_candidates`. That card could not be answered, could not be usefully re-shot, and came back every single session. That is `wasted_position`, and it is what this entry is for.

**The reversal refuses an answered card, which is the guard worth naming.** Both directions sit on one path (D28's shape, and `do_mark_sold`'s reason: a reversal reachable without going through the thing it reverses is a route a stale client finds on its own). Reopening a queue entry is the same store operation either way, so `_clearing_event` reads the log to learn which event closed the question and refuses `not_stood_down` when it was an ANSWER — taking back a real identification through the un-dismiss control is the one thing this route may not do. It inherits `_answer_before`'s `renumbered` hard stop for D10 ruling 1's reason: a clearing line older than a mid-box shift belongs to the slot's previous occupant.

**No listing hold is consulted, in either direction.** `undo_too_late` asks whether a SKU this Mac wrote is already out in an import file. A stand-down writes no SKU, changes no SKU and moves no listing count, so nothing downstream can disagree with it.

**The screen offers retirement beside it, and delete deliberately not.** Both were asked for in the same breath. `POST /inventory/<box>/<index>/retire` already existed and already had a client function; what it lacked was a control on the screen the card is actually on, which is `CLAUDE.md`'s route-is-not-a-feature rule in its mildest form. **The mid-box delete stays on `#/inventory`** for two reasons that are about this screen rather than about the operation: it slides every card behind it down one slot, so pressing it from a worklist would renumber the very positions that worklist is drawn from — the defect D36 was written to stop, invited back in by hand — and it is the one operation here with no undo at all. The panel says so on screen rather than leaving someone to hunt for it.

**One panel, keyed, because the difference is the hard part.** The owner's confusion was not about where the buttons are; it was that these are three different acts with three different costs, which no button label conveys alone. `X` raises a panel that names what each one does to the card, and it owns the keyboard while it is up for the group offer's reason — its choices are keyed on digits that mean candidates everywhere else on that screen.

**What would reopen this: the reason counts.** If `wasted_position` dominates, the fix is upstream — a capture that can produce a black frame at a different resolution than the rest of its box is a rig fault, not a queue fault, and no amount of dismissing is the remedy for it. That is the measurement `docs/DESIGN.md` has been asking for since Gate B, and this route is what finally takes it.

---
