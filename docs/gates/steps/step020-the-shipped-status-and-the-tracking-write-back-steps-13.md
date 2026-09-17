20. **The shipped status and the tracking write-back** — steps 13 and 14 of
    `docs/specs/order-pipeline.md`, and the only part of that spec that is neither built nor
    merely unproven. Both endpoints were seen on the wire while D69 was being measured and
    were deliberately left alone: writing a tracking number back is the first thing this
    project would do that a **buyer** sees, and D69 ruled that the screen comes before the
    transport. Nothing blocks it but the doing of it.

**Nothing in this list is blocked on a third-party benchmark.** A sub-floor T1 is worked
directly — see the T1 section above. The TCGplayer Scan & Identify comparison was removed
from this list on 2026-08-03 and parked in `docs/DECISIONS.md`; it is available as a
reference point when someone wants it, never as a precondition.
