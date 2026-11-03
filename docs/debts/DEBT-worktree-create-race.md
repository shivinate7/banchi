## DEBT-worktree-create-race — parallel worktree creation can fail on a git read of another worktree's commondir

**What.** Parallel worktree creation can fail with a git error reading another worktree's `commondir`, and `make worktree-create-selftest` went red on main once.

- **Job.** `ci-check (ci-check-guards-1)`, run 3256 (id 41593550249), a push run of the merge of PR #1028, on commit 06571635. The step `make worktree-create-selftest` runs five rounds of four parallel creations. Creation w2 exited 1 with `fatal: failed to read .git/worktrees/w1/commondir: Success`. The self-test then printed `trees: want 22, got 21`.
- **Measured.** One first-attempt red after the window, run 3256. The nightly run 3258, on the same commit, passed `ci-check`. The runner's git is 2.56.0.
- **Cause.** Cause unread. The git message names a read of another worktree's `commondir` during parallel `git worktree add`. Not read: whether git 2.56.0 is part of it, and whether a real parallel Agent hits the same read.
- **Owner.** shivinate7. **Fix by.** 2026-12-01 (D308, a deadline date is allowed).
- **Outcome at risk.** The self-test protects that parallel Agents each get their worktree. Four creations racing one `.git/config` must all succeed, and none may leave a config lock behind. A red here fails `ci-check`, and a passing rerun does not show the race is gone. The self-test's header cites D18 (generators may write, writers never gate).
- **Closes when.** The cause is written here. Then the hook is fixed, and the parallel arm passes at its stated defaults on the runner. The defaults are not lowered to reach green.
