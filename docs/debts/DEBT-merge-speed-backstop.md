## DEBT-merge-speed-backstop — the merge-speed guard's 10 s wall-clock backstop can fail on a loaded machine

**What.** `harness/tests/t7_box_map.py:check_merge_speed` can fail through its 10 s wall-clock backstop on a loaded machine, with no defect in the merge.

- **Check.** `check_merge_speed`. Its main measure counts SQLite progress ticks (DEBT43, the merge-speed guard counts SQLite ticks only). Its backstop is wall time, set to 10 s.
- **Measured.** No red of this check is in the 100 most recent completed main check runs (window run numbers 2489 to 3148). The claim that it flakes under load is unmeasured here.
- **Cause.** Found in the source. The backstop is wall-clock time, so a loaded runner can exceed it with the work unchanged.
- **Owner.** shivinate7. **Fix by.** 2026-12-01 (D308, a deadline date is allowed).
- **Outcome at risk.** A guard that goes red for a reason that is not the merge gets scrolled past. Then a real quadratic merge goes unseen (DEBT43).
- **Closes when.** The backstop is measured on a loaded runner and set from that, or the wall-clock backstop is removed for the tick count plus a call count. The choice is the owner's, as DEBT43 says.
- **Points to.** DEBT43 (the merge-speed guard's blind spot).
