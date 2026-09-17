## 19 — The revert guard is exact, and three shapes of reversal walk past it

**Recorded 2026-09-11 with D133, which built the guard and names these in its last section.**
`make revert-guard` refuses a file whose whole change puts it back the way main had it before a
commit in main's last sixty; it is exact by object id and by `-U0` hunk, and exact is the
deliberate choice. What that leaves open:

- **Age.** A branch stale by more than sixty first-parent commits — about twelve days here —
  that merges main keeping `ours` reverses commits outside the window. `scripts/revert-audit.py
  history --window 0` sees them after the fact; nothing sees them at the push.
- **Re-wording.** A restored block with one line altered is a new edit to the guard. A
  similarity threshold was declined: a dial on a gate is turned until the gate is quiet.
- **A widened hunk.** A reversal on lines adjacent to a real edit shares that edit's hunk and
  stops being the reverse of anything — how #221's `docs/map.py` and `docs/DEBTS.md` rows
  escaped. A containment test was measured at seventy-nine coincidences over this history and
  zero of the rows it was written for, and was not kept.

**What is measured:** the guard fires on the #218/#221 sequence rebuilt in a throwaway
repository, ten arms, three of them mutation-tested. **What is not:** any of the three above,
on purpose. The `recorded deletions` audit row covers the one case a session registers by hand,
and D133's whole-file detector covers the keep-ours merge, which restores whole blobs and so
never depends on hunk boundaries.
