## D1 — Capture is dumb; batch identifies later

**Capture is fast, offline and dumb; identification and pricing happen later, in batch.**

Capture is fast, offline, and dumb. Identification and pricing happen later in batch. Keep them apart: speed, cost, and reliability all favor the split.

**One exception, on the owner's word: a free background reader.** It is a separate child process. It never runs inside a capture request. It writes one identification row for a captured card and never changes card state. It holds almost no memory when its queue is empty. `docs/specs/identify-engine-pick.md` section 8 holds the design.
