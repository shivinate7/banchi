## D-guard-self-test-scope — Fifteen guard self-tests are path-gated, and no target was found dead

**THE MEASUREMENT THAT REOPENED THE CLOSE.** `scripts/serve-scope.py`'s header says a
second path-gated target needs the owner's word again. That word was asked for and given,
2026-09-20, on a fresh measurement. `make check` is 163.85s on a typical commit. That is
with `serve-selftest` already skipping. Fifteen guard self-tests cost 76.6s of that. That is
47%. The list, each with its wall clock:

| Self-test | Seconds |
|---|---:|
| reap-selftest | 15.04 |
| claim-selftest | 14.86 |
| guard-shell-selftest | 12.11 |
| sync-selftest | 7.42 |
| audit-self-test | 5.04 |
| janitor-selftest | 4.63 |
| merge-selftest | 4.46 |
| githooks-selftest | 3.48 |
| silent-write-selftest | 2.53 |
| verdict-selftest | 1.99 |
| revert-selftest | 1.43 |
| suite-lock-selftest | 1.32 |
| submission-selftest | 1.05 |
| screen-freshness-selftest | 0.78 |
| cid-selftest | 0.43 |

The ten-test product harness covers the actual product for 21.75s. This session measured
it again, on a different tree, at 24.4s. Both figures are real.
`docs/specs/verification-cost.md`'s table now carries the newer one. Four self-tests alone
cost more than double the whole harness.

**WHAT A GUARD SELF-TEST CAN CATCH, AND WHAT IT CANNOT.** Every one of these fifteen proves
a MECHANISM. Each does so against a THROWAWAY FIXTURE it builds for the purpose. That
fixture is a temp repository, a temp clone, or a process it starts and kills itself. None
of them opens the real store, the real capture server, or a real screen. So a guard
self-test cannot catch a product defect. That is `make harness`'s job, and
`make design-check`'s. A guard self-test has something new to say at three moments only.
The guard script it proves may have changed. Its own fixture or assertions may have
changed. The Makefile recipe wiring the two together may have changed. Between those
moments it answers a question nobody asked it again. That is not a flaw in any of the
fifteen. It is what "prove a mechanism" means. It is the same argument `serve-scope.py`'s
own header already made about `serve-selftest` alone.

**A SEPARATE AUDIT GRADED ALL 38, AND NOT ONE WAS DEAD WEIGHT.** Before writing this entry,
every target in `scripts/checks.py:CHECKS` was read against the incident or code path its
own comment cites. Every one of the thirty-eight names a real defect or a real regression.
Or it names a real code path it alone stands in front of. The fifteen here are no
exception. `revert-guard`'s own accounting in `docs/specs/verification-cost.md` §4 makes
the point sharply. It has zero mentions in 200 commits. It stays anyway. The one thing it
guards against happened once, before the guard existed. A hand-walk found it, nothing else.
**This entry is a placement change, not a pruning.** Nothing here argues any of the fifteen
should stop running. They stop running on a commit that cannot reach them. They run in full
on a commit that can. On the evidence above, that is most commits. A guard script changes
far less often than the product beside it.

**THE MAPPING IS DERIVED, NEVER TYPED.** This is `serve-scope.py`'s own argument, turned
against a second kind of rot. `scripts/guard-scope.py:derive_subjects` reads each
self-test's own source. It reads every local-package import — `store`, `cli`, `pipeline`,
`identify`, `geometry`, `codes`, `server`. It reads every `Path`-style `A / "b" / "c.py"`
chain. For the four shell scripts it reads the same shapes with a regex. It resolves every
hit against the real filesystem. A hand-typed list beside each self-test would be the exact
rot this workstream exists to close. `docs/specs/verification-cost.md` was itself opened
over one such case. `scripts/docs-audit.py`'s `governed_by` bookkeeping asks a human to
retype, by hand, a set. A regular expression already computes that same set. This entry
does not repeat that mistake next to fifteen new targets. `serve-scope.py`'s own `SCOPE` is
a hand-curated tuple. It is reconciled against `serve-selftest.py`'s separately
hand-curated `CARRY`. Here there are no two lists to drift apart. The subject set is
recomputed from the test's live source on every call. It cannot go stale between commits.
One thing stays a human decision, on `serve-scope.py`'s own precedent — it names its one
target by hand too. Which targets are worth gating at all is a product judgement.
`guard-scope.py:ROSTER` names these fifteen by hand for that reason. No source-reading can
make that call for us.

**RECONCILED BOTH WAYS.** `make docs-audit`'s `guard scope` row checks two directions.
Every roster target's Makefile recipe must call `guard-scope.py classify --target <name>`.
A roster entry nothing consults is a list, not a gate. That is `serve scope`'s own wiring
check, repeated. Every recipe calling this classifier must name a target on the roster.
That way a sixteenth target, copied from the pattern, cannot silently classify against
nothing. `scripts/guard-scope.py selftest` proves the same two directions on its own. A
broken roster then fails locally, not only in the audit.

**IT FAILS OPEN, IN EVERY DIRECTION**, mirroring `serve-scope.py` exactly. No merge-base
runs it. An unreadable diff runs it. An EMPTY diff runs it. An unscoped target name runs
it. Any exception raised while deriving a subject runs it. `PKMNSCAN_GUARD_SCOPE=off` turns
the whole gate off for every target at once. Every skip prints that it exists.

**WHAT THIS DOES NOT COVER.** A guard script reached only through a path this reader
cannot see is invisible to `derive_subjects`. That includes a dynamic `getattr`. It also
includes a subprocess call built from a runtime string. Or a filename read from an
environment variable. A self-test would then skip on a change that should have run it.
`githooks-selftest.sh` is the one case found where this actually bites. It names two of its
five hooks as literal strings: `reference-transaction`, `post-checkout`. It names the rest
only in prose — "its pre-push sibling". The reader widens any hit under
`scripts/githooks/` to the whole directory for this reason. It does not trust the two names
it can see over the three it cannot. No other roster entry needed that widening. If a
future one does, the same rule applies with no new list. A new guard self-test is not
scoped until it is added to `ROSTER` by hand. That is the same rule `docs/map.py` already
applies. A new file is not covered until an entry names it.

**THE SAVING, MEASURED ON THIS BRANCH.** `make check` on this machine, in this worktree,
measured 93.3s with every guard self-test running. The same tree, one trivial follow-up
commit later, measured 66.4s with all fifteen and `serve-selftest` skipping. That is a
27-second cut on this hardware, on top of the 21.75s the ten-test harness already costs.
The 76.6-second figure at the top of this entry is the orchestrator's own measurement, on
a different Mac. Both are real. Neither restates the other. A commit touching one guard
script, such as `scripts/reap.py`, still runs that one self-test. It skips the other
fourteen.
