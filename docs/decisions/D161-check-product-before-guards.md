## D161 — Check the product before its guards

**`make check` runs 23 targets and stops at the first failing one. Eleven of the 23 were the guards' own selftests, sitting ahead of every check on the product.** `reap-selftest` was twelfth. `lint`, `vale`, `typecheck`, `screen-freshness`, `sigil-check` and `ignore-check` were all behind it. A red in a guard's own selftest meant that six checks on the actual code never ran. The terminal reported a failure, not an absence.

**The problem was real.** `reap-selftest` failed repeatedly from a machine-wide `pgrep` collision between concurrent worktrees. D157 fixed it the same night. A session verifying a branch reported `make check` red, having never reached `typecheck`. A second session, landing D160, recorded that its final run was the first to reach every target. That run caught three `ruff` errors of its own. Every earlier run had died before it saw them.

**Two sessions, one night, both blind to the same six checks, and neither aware of it.**

### The order, and the principle behind it

The recipe is now the product, then the tooling's proof of itself.

1. `harness` — the nine verification tests. First, because it is what the product does.
2. `docs-audit` — the mechanical rows over the tree.
3. `claim-stale`, `revert-guard`, `port-agreement`, `set-hint-agreement`, `screen-freshness`, `sigil-check`, `ignore-check`, `lint`, `vale`, `typecheck` — every check that reads the code and says something about it.
4. `audit-self-test`, `githooks-selftest`, `revert-selftest`, `decisions-selftest`, `janitor-selftest`, `reap-selftest`, `suite-lock-selftest`, `serve-selftest`, `verdict-selftest` — the nine that prove a GUARD works.

**The principle: a check that spawns a process can fail for a reason outside the tree. A check that reads a file cannot.** The nine in group 4 build throwaway clones, take machine-wide locks, bind ports and send signals. Each one can go red because another worktree on this Mac was busy. D122 and D157 both record that. The twelve in groups 1 to 3 answer from the tree alone.

**Putting the environment-sensitive targets last means that a flake cannot hide a real defect.** It can only delay news of one already reported.

### What this does not change

**Nothing is added, removed, or made conditional. Nothing moves on or off the commit path.** `make docs-audit`'s `check registry` row reconciles `scripts/checks.py` against the recipe in order. That file was reordered identically, and the row still reads `23 checks, in recipe order`. `check census` still reads `2 published lists, 23 checks each`. `commit path` still reads `2 of 23 on the commit path, none of them writing`, so D18 is untouched.

**`make ci-check` is deliberately not reordered.** It is a different list for a different question: what a machine can prove on a fresh clone. CI runs it to completion on a runner with nothing else on it. That is the one place group 4's environment sensitivity does not apply.

**This is not a fix for a flaky check, and it must not be read as one.** D157 fixed the `reap-selftest` collision at its cause. This entry fixes the ordering that let any failure in group 4 conceal six checks behind it. A real failure hid them as easily as a flake did. A suite that stops at the first failure is correct. A suite that stops at the first failure, with its most fragile targets in the middle, reports less. It reports less the worse things get.

### Claim-stale and vale are out of `make check`

`claim-stale` and `vale` have both left `make check`'s and `make ci-check`'s composition (C1, C2, test-audit lane L3). `make merge` already runs `claim-stale` fresh against `origin/main` (D140). `vale` cannot fail. It printed 1,668 errors that nobody read. The global STE gate covers new prose instead. The order argued above is untouched. The twelve tree-only checks still run before the group that spawns processes.

### CI runs `ci-check` as parallel shards

CI no longer runs `make ci-check` as one serial step. That step took 600s on run 36509895299. CI now runs `ci-check-product` (the harness and unit tier, part 1), `ci-check-static` (docs-audit and the other tree checks), `ci-check-guards-1` and `ci-check-guards-2` as parallel jobs. There are six since the product shard split. Each shard runs in under 150s, though guards-1 later measured 243s. Each shard keeps this entry's order: product checks before self-tests. A required job named `check` needs every shard. It fails unless each one succeeded, so a skipped or canceled shard counts as red. `make ci-check` is unchanged, and it is still what a session runs before pushing. `make docs-audit`'s `check registry` row fails when the shards' union is not `ci-check`'s recipe, target for target.

### The product shard is three

The product shard took 311s on run 38081462471, the PR's critical path. 256s of it was T7 (342 checks, no one dominant). `harness/run.py --part K` (`PARTS` slices) runs part 1's non-T7 tests and the T7 checks whose name hashes (crc32) to K. Shards `ci-check-product`, `-product-2` and `-product-3` run `harness-1`, `harness-2` and `harness-3`. `unit` rides with part 1. There are six shards, and `check` still needs all of them. `make docs-audit`'s `check registry` row reads `PARTS` against the `harness-K` entries. It reads each shard against a Makefile rule.
