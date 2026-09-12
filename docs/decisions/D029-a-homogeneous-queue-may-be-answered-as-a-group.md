## D29 — A homogeneous queue may be answered as a group

**A queue whose entries share one reason code and offer one identical candidate may be answered as a group.** Built 2026-08-23, enforced server-side: each entry offers exactly ONE candidate — its own — under one shared reason and one shared condition string.

**A shared SKU is deliberately not required and cannot be what *same single candidate* means**: sixteen cards are sixteen catalog rows, and answering card A with card B's SKU would be corruption wearing a reading. Validate-everything-then-write-everything in one store session (`group_entry_refused` / `group_not_uniform` exit with zero edits); every position gets its own `answered` line tagged `group: N`; the group confirm is the review screen's first solid accent fill, ruled legal because the eligibility conditions are precisely what reduce the state to one action; and the undo reverses per position through the single route, reporting a partial reversal honestly rather than pretending atomicity it does not have.

**This reopens D4's one-card-at-a-time, narrowly, on evidence D4 did not have.** Gate B's queue was 16 of 53, **every one the same reason code**, and detection agreed with itself across every duplicate pair — both Thievuls, both Eiscues, both Pyroars. One systematic fact about the rig's lighting, sixteen identical taps. The discarded pre-rotation run queued 45 with one shared cause.

**Grouping and filtering, always. A group write only under both conditions:** every entry shares a reason code, **and** every entry offers the same single candidate. Anything looser is a bulk write over cards a human has not actually compared, which is what D4 exists to prevent.

D4's digital-only, one-tap choice beside the photo is unchanged for every card that does not meet both conditions — and a group write still shows the photographs it is about to answer for.
