## 19 — The revert guard is exact, and three shapes of reversal walk past it

`make revert-guard` refuses a file whose whole change restores what main had before a commit in main's last sixty (`scripts/revert-audit.py:WINDOW`). It is exact by object id and by `-U0` hunk (D133). Three shapes pass:

- **Age.** A branch stale by more than sixty first-parent commits that merges main keeping `ours` reverses commits outside the window. `scripts/revert-audit.py history --window 0` sees them after the fact and nothing sees them at the push.
- **Re-wording.** A restored block with one line altered is a new edit. A similarity threshold was declined: a dial on a gate is turned until the gate is quiet.
- **A widened hunk.** A reversal on lines adjacent to a real edit shares that edit's hunk. A containment test found 79 coincidences over this history and none of the rows it was written for.

The `recorded deletions` row covers the one case a session registers by hand, and D133's whole-file detector covers the keep-ours merge.

**Outcome at risk.** A merge silently undoes another branch's work.

**Closes when.** The window widens at a measured cost, or a hunk-level test finds the reversal without the coincidences.
