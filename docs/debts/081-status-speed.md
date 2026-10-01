## DEBT81 — The first `make status` after an edit is slow

**A cold `make status` takes about 20 s.** `audit_run` in `scripts/status.py` replays the last docs-audit answer only when no non-ignored file has changed. The first run after any edit runs all 85 checks again, and that is 21.5 s of a 22 s run.

- **Not fixed because the checks are slow.** No one step is the cause. The two largest are `check_spec_map` (4.8 s) and `check_line_anchors` (4.0 s), and the rest are spread under 1.3 s each. Closing it means speeding up the checks, or running only those whose inputs changed.
- **Closes when** a cold `make status` is under 5 s.

**Outcome at risk.** An owner who reads status after each edit waits 20 s each time and learns to skip it.
