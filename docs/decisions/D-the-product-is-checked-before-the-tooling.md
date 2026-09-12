## D-the-product-is-checked-before-the-tooling — `make check` proves the product first and its own guards last, because a failure stops the rest

**`make check` runs 23 targets, stops at the first failing one, and eleven of the twenty-three were the guards' own selftests sitting ahead of every check on the product.** `reap-selftest` was twelfth. `lint`, `vale`, `typecheck`, `screen-freshness`, `sigil-check` and `ignore-check` were all behind it. A red in a guard's own selftest meant six checks on the actual code never ran — and the terminal reported a failure, not an absence.

**It was not hypothetical on the day this was written.** `reap-selftest` failed repeatedly on 2026-09-11 from a machine-wide `pgrep` collision between concurrent worktrees, fixed the same night by D157, and a session verifying a branch reported `make check` red having never reached `typecheck`. A second session, landing D160, recorded that its final run was *"the first run to reach every target"* — and that run caught three `ruff` errors of its own that every earlier run had died before seeing.

**Two sessions, one night, both blind to the same six checks, and neither aware of it.**

### The order, and the principle behind it

The recipe is now the product, then the tooling's proof of itself.

1. `harness` — the nine verification tests. First, because it is what the product does.
2. `docs-audit` — the mechanical rows over the tree.
3. `claim-stale`, `revert-guard`, `port-agreement`, `set-hint-agreement`, `screen-freshness`, `sigil-check`, `ignore-check`, `lint`, `vale`, `typecheck` — every check that reads the code and says something about it.
4. `audit-self-test`, `githooks-selftest`, `merge-selftest`, `revert-selftest`, `claim-selftest`, `decisions-selftest`, `janitor-selftest`, `reap-selftest`, `suite-lock-selftest`, `serve-selftest`, `verdict-selftest` — the eleven that prove a GUARD works.

**The principle: a check that spawns a process can fail for a reason outside the tree, and a check that reads a file cannot.** The eleven in group 4 build throwaway clones, take machine-wide locks, bind ports and send signals; every one can go red because another worktree on this Mac was busy, which D122 and D157 both record happening. The twelve in groups 1 to 3 answer from the tree alone.

**Putting the environment-sensitive targets last means a flake can no longer hide a real defect.** It can only delay news of one already reported.

### What this does not change

**Nothing is added, removed, or made conditional, and nothing moves on or off the commit path.** `make docs-audit`'s `check registry` row reconciles `scripts/checks.py` against the recipe IN ORDER, so that file was reordered identically and the row still reads `23 checks, in recipe order`. `check census` still reads `2 published lists, 23 checks each`. `commit path` still reads `2 of 23 on the commit path, none of them writing`, so D18 is untouched.

**`make ci-check` is deliberately not reordered.** It is a different list for a different question — what a machine can prove on a fresh clone — and CI runs it to completion on a runner with nothing else on it, which is the one place group 4's environment sensitivity does not apply.

**This is not a fix for a flaky check and must not be read as one.** D157 fixed the `reap-selftest` collision at its cause. What this fixes is the ordering that let ANY failure in group 4 — a real one as easily as a flake — conceal six checks behind it. A suite that stops at the first failure is correct; a suite that stops at the first failure with its most fragile targets in the middle reports less the worse things get.
