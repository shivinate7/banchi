# D29 — Identical queue entries answer as a group

**A queue whose entries share one reason code and offer one identical candidate may be answered as a group.** The server enforces it. Each entry offers exactly ONE candidate, its own, under one shared reason and one shared condition string.

**A shared SKU is not required. It cannot be what "same single candidate" means.** Sixteen cards are sixteen catalog rows. Answering card A with card B's SKU would be corruption that looks like a reading. The write validates everything, then writes everything, in one store session. A refused group (`group_entry_refused` or `group_not_uniform`) exits with zero edits. Every position gets its own `answered` line, tagged `group: N`. The group confirm is the review screen's first solid accent fill. A group is legal because the eligibility conditions reduce the state to one action. Undo reverses per position through the single route. A partial reversal is reported as partial. The system does not pretend to atomicity it does not have.

**This reopens D4's one-card-at-a-time rule, narrowly, on evidence D4 did not have.** Gate B's queue held 16 of 53 cards, **every one with the same reason code**. Detection agreed with itself across every duplicate pair: both Thievuls, both Eiscues, both Pyroars. One systematic fact about the rig's lighting caused sixteen identical taps. The discarded pre-rotation run queued 45 with one shared cause.

**Grouping and filtering are always on. A group write happens only when both conditions hold.** Every entry shares a reason code, **and** every entry offers the same single candidate. Anything looser is a bulk write over cards a human has not compared. D4 exists to prevent that.

D4's digital-only, one-tap choice beside the photo is unchanged for every card that does not meet both conditions. A group write still shows the photographs it is about to answer for.
