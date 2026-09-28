# Test audit, slice: check's non-harness targets, git hooks, Claude Code guards

Input for an Opus reviewer. This follows the owner's plan from 2026-09-27. This file reports
facts. It gives a first verdict per item. It does not decide the final plan.

Scope: every `make check` target except `harness` and `docs-audit`. Other slices cover
those two. This also covers four named self-tests kept out of `check` on purpose. It covers
the two path-gate mechanisms. It covers the five git hooks in `scripts/githooks/`. It
covers the guard scripts wired into `.claude/settings.json`.

Head commit at audit time: `103fde97`. Branch: `ux/test-audit-check`. Based on `ux/pr4b`.

Some cost figures carry a date. Those come from `docs/specs/verification-cost.md`. That doc
was measured on the owner's Mac, on two trees, on 2026-09-17 and 2026-09-20. A figure with
no date is one I measured myself, in this worktree, on 2026-09-27. I mark that one
"(measured here)". Everything else reads "unmeasured". Unmeasured does not mean worthless.
D247 makes this point about a zero-cost guard. That guard still stops a real historical
defect.

Path-gating today runs through two mechanisms. `scripts/serve-scope.py` gates one target,
`serve-selftest`. `scripts/guard-scope.py` gates a 22-entry `ROSTER` in that file (D247). I
mark roster membership per item below as "guard-scope: yes" or "guard-scope: no".

---

## Summary table

| # | Item | Product or mechanism | Path-gated | Cost | Last red (known) | Verdict |
|---|---|---|---|---|---|---|
| 1 | port-agreement | mechanism, cross-language seam | no | 0.13s (09-20) | unmeasured | KEEP |
| 2 | set-hint-agreement | mechanism, cross-language seam | no | 0.14s (09-20) | unmeasured | KEEP |
| 3 | readiness-agreement | mechanism, cross-language seam | no | in the 0.05-0.08s group (09-20) | unmeasured | KEEP |
| 4 | screen-freshness | product, screens re-read the store | no | 0.76s (09-20) | unmeasured | KEEP |
| 5 | screen-freshness-selftest | guard of a guard | guard-scope: yes | 0.78s (09-20) | unmeasured | KEEP, already gated |
| 6 | sigil-check | product, count against key on screen | no | 0.20s (09-20) | yes, D92, four instances shipped before the rule tightened | KEEP |
| 7 | css-var-check | product, silently-dropped CSS | no | unmeasured | yes, five found by hand on 2026-09-20, before this check existed | KEEP |
| 8 | css-var-check-selftest | guard of a guard | no | unmeasured | unmeasured | KEEP |
| 9 | token-literal-check | product, token or literal drift | no | unmeasured | yes, D256, main already carried several before the ratchet | KEEP |
| 10 | token-literal-check-selftest | guard of a guard | no | unmeasured | unmeasured | KEEP |
| 11 | kit-adoption | product, screens skip the kit | no | unmeasured | recorded through D275 and its offender list | KEEP |
| 12 | kit-adoption-selftest | guard of a guard | no | unmeasured | unmeasured | KEEP |
| 13 | ignore-check | mechanism, worktree hygiene | no | 0.15s (09-20) | yes, D47, a 133MB mirror committed once | KEEP |
| 14 | lint | product, eslint plus ruff | no | 2.09s (09-20) | named in 22 of the last 200 fix commits | KEEP |
| 15 | vale | advisory, never gates | no | 1.72s (09-20) | none by design, it cannot fail | KEEP, do not count as coverage |
| 16 | typecheck | product, tsc --noEmit | no | 3.34s (09-20) | named in 3 of the last 200 fix commits | KEEP |
| 17 | audit-self-test | guard of a guard | guard-scope: yes | 5.04s (09-20) | yes, sat red and unnoticed until 2026-08-24 | KEEP, already gated |
| 18 | mutate-anchors | guard of a guard, anchor freshness | no | about 0.05s (09-20) | unmeasured | KEEP |
| 19 | claim-stale | product, id allocation against main | no | 6.22s (09-20) | named in 15 of the last 200 fix commits | KEEP |
| 20 | revert-guard | product, silent reversion | no | 0.09s (09-20) | none in 200 commits, but a real defect predates the guard, PR #221, D133 | KEEP |
| 21 | githooks-selftest | guard of a guard | guard-scope: yes | 3.48s (09-20) | unmeasured | KEEP, already gated |
| 22 | merge-selftest | guard of a guard | guard-scope: yes | 4.46s (09-20) | unmeasured | KEEP, already gated |
| 23 | revert-selftest | guard of a guard | guard-scope: yes | 1.43s (09-20) | proved by rebuilding PR #218 and #221 | KEEP, already gated |
| 24 | claim-selftest | guard of a guard | guard-scope: yes | 14.86s (09-20) | caught once by hand, a prose count of 16 arms over a file that held 18 | KEEP, already gated |
| 25 | decisions-selftest | guard of a guard, corpus round-trip | no | in the 0.05-0.08s group | unmeasured | KEEP |
| 26 | debts-selftest | guard of a guard, corpus round-trip | no | in the 0.05-0.08s group | unmeasured | KEEP |
| 27 | gates-selftest | guard of a guard, corpus round-trip | no | in the 0.05-0.08s group | unmeasured | KEEP |
| 28 | submission-selftest | guard of a guard | guard-scope: yes | 1.05s (09-20) | proved by racing two presses over one card | KEEP, already gated |
| 29 | cid-selftest | guard of a guard | guard-scope: yes | 0.43s (09-20) | proves five named failure modes, including a -9 mid-transaction | KEEP, already gated |
| 30 | pricearchive-selftest | guard of a guard | guard-scope: yes | unmeasured, landed after 09-20 | unmeasured | KEEP, already gated |
| 31 | archive-review-selftest | guard of a guard | guard-scope: yes | unmeasured, landed after 09-20 | unmeasured | KEEP, already gated |
| 32 | holdings-selftest | guard of a guard | guard-scope: yes | unmeasured, landed after 09-20 | unmeasured | KEEP, already gated |
| 33 | identity-checks-selftest | guard of a guard | guard-scope: yes | unmeasured, landed after 09-20 | unmeasured | KEEP, already gated |
| 34 | price-postings-selftest | guard of a guard | guard-scope: yes | unmeasured, landed after 09-20 | unmeasured | KEEP, already gated |
| 35 | product-history-selftest | guard of a guard | guard-scope: yes | unmeasured, landed after 09-20 | unmeasured | KEEP, already gated |
| 36 | sku-number-contradictions-selftest | guard of a guard | guard-scope: yes | unmeasured, landed after 09-20 | unmeasured | KEEP, already gated |
| 37 | readings-selftest | guard of a guard | no | in the 0.05-0.08s group | unmeasured | KEEP, path-gate candidate |
| 38 | skus-selftest | guard of a guard | no | unmeasured | unmeasured | KEEP, path-gate candidate |
| 39 | identity-store-selftest | guard of a guard | no | unmeasured | unmeasured | KEEP, path-gate candidate |
| 40 | identity-binding-selftest | guard of a guard | no | unmeasured | unmeasured | KEEP, path-gate candidate |
| 41 | identity-readers-selftest | guard of a guard, four mutate arms | no | unmeasured | unmeasured | KEEP, path-gate candidate |
| 42 | identity-cli-selftest | guard of a guard | no | unmeasured | unmeasured | KEEP, path-gate candidate |
| 43 | janitor-selftest | guard of a guard | guard-scope: yes | 4.63s (09-20) | unmeasured | KEEP, already gated |
| 44 | reap-selftest | guard of a guard | guard-scope: yes | 15.04s (09-20) | proved by violating it, the 2026-09-10 kill incident | KEEP, already gated |
| 45 | silent-write-selftest | guard of a guard | guard-scope: yes | 2.53s (09-20) | proved by reproducing the /dev/null refusal incident | KEEP, already gated |
| 46 | guard-shell-selftest | guard of a guard, nine clauses | guard-scope: yes | 12.11s (09-20) | proves nine named real incidents | KEEP, already gated |
| 47 | coordinator-selftest | guard of a guard | no | in the 0.05-0.08s group | unmeasured | KEEP, path-gate candidate |
| 48 | suite-lock-selftest | guard of a guard | guard-scope: yes | 1.32s (09-20) | proves the lock, including a holder killed with -9 | KEEP, already gated |
| 49 | browser-scope-selftest | guard of a guard | no | unmeasured | unmeasured | KEEP, path-gate candidate |
| 50 | serve-selftest | guard of a guard, the largest single cost | serve-scope: yes | 70.12s (09-17), 37 percent of check | none known, no real regression yet | KEEP, already gated. Revisit only on the owner's word |
| 51 | sync-selftest | guard of a guard | guard-scope: yes | 7.42s (09-20) | proved by violating primary_sync.py | KEEP, already gated |
| 52 | verdict-selftest | guard of a guard | guard-scope: yes | 1.99s (09-20) | unmeasured | KEEP, already gated |
| 53 | js-breakpoints-selftest | guard of a guard | no | unmeasured | real defect found, an orphaned 1024px query in Orders.tsx | KEEP, path-gate candidate |
| 54 | subagent-override-selftest | guard of a guard | no | unmeasured | proved by violating it in a real nested worktree | KEEP, path-gate candidate |
| 55 | guard-scope-selftest | guard of the path-gate itself | no, self-exempt | 0.54s (measured here) | mutation-tested, a broken classifier and a roster or wiring mismatch both go red | KEEP |
| 56 | port-slots-selftest | guard of a guard | no | unmeasured | real collision, two worktrees both got port 5218 | KEEP, path-gate candidate |
| 57 | demo-determinism-selftest | guard of a guard, path-matcher only | no | unmeasured | unmeasured | KEEP |
| 58 | match-selftest | product plus guard, server-client agreement | no | unmeasured | unmeasured | KEEP |
| G1 | pre-commit | git hook | not a make target | part of commit time | yes, D92 and docs-audit findings caught before merge | KEEP |
| G2 | pre-push | git hook | not a make target | part of push time | yes, five consecutive pushes to main in the reflog before it existed | KEEP |
| G3 | reference-transaction | git hook | not a make target | part of every ref update | yes, one commit fast-forwarded into main with no commit hook run | KEEP |
| G4 | post-checkout | git hook, advisory only | not a make target | negligible | none by design, it cannot fail | KEEP |
| G5 | post-merge | git hook, advisory only | not a make target | negligible | none by design, it cannot fail | KEEP |
| H1 | scripts/guard-opsec.sh, PreToolUse | Claude Code guard | not a make target | per write | fails open by design | KEEP |
| H2 | scripts/decision-context.py, PreToolUse | Claude Code advisory | not a make target | per write | none, it cannot fail an edit | KEEP |
| H3 | scripts/reap.py --hook, PreToolUse | Claude Code guard | not a make target | per Bash call | yes, two incidents on 2026-09-10 | KEEP |
| H4 | scripts/silent-write-guard.py --hook, PreToolUse | Claude Code guard | not a make target | per Bash call | yes, nine instances in about 24 hours before it existed | KEEP |
| H5 | scripts/guard-shell.py --hook, PreToolUse on Bash and Write/Edit | Claude Code guard | not a make target | per call | yes, nine distinct real incidents named in its own note | KEEP |
| H6 | scripts/typecheck-hook.py, PostToolUse | Claude Code advisory | not a make target | per .tsx write | cannot block, it fires after the write | KEEP |
| H7 | scripts/worktree-guard.sh, SessionStart | Claude Code provisioning | not a make target | per session start | yes, three fresh-worktree failures existed before it | KEEP |
| H8 | scripts/stop-gate.sh, Stop | Claude Code hook, runs harness | not a make target | about the harness cost | see the harness slice | out of scope here |
| H9 | scripts/session-teardown.sh, SessionEnd and WorktreeRemove | Claude Code cleanup | not a make target | drain time | yes, D111, four supervisors once restarted against deleted directories | KEEP |

Overlap notes sit under each entry below. I do not repeat them in the table.

---

## A. Cross-language seam agreement checks

### 1. port-agreement
Script: `scripts/port-agreement.py`. It protects one fact. `server/ports.py` and
`app/devPort.ts` must compute the same port for a checkout. If they disagree, the app can
open a tab on a dead port. It could also open a tab on another tree's live server. This is
a product check. It asserts two real implementations agree. It is not a guard of a guard.
It was earned by a recorded class of bug in `docs/GATES.md`. Two new game prompts once
named an identifier field differently between a form and `cli/resolve.py`. That mismatch
would have silently produced `no_catalog_row` for every card. D43 governs this. Cost is
0.13s (2026-09-20). It is not path-gated. It overlaps with `port-slots-selftest`, but the
concerns differ. That one tests collision-avoidance across checkouts. This one tests that
two languages' pure functions agree. Last known red is unmeasured. **Verdict: KEEP.** The
cost is near zero. A real class of bug sits behind the pattern. No better substitute
exists.

### 2. set-hint-agreement
Script: `scripts/set-hint-agreement.py`. It protects one fact. `server/tcg_export.py:match_sets`
and `app/src/setHint.ts` must agree on whether a set hint resolves. If they disagree, the
screen can tell the operator a hint matched when the fetch will actually miss it. D65
governs this. Cost is 0.14s (2026-09-20). The script's own header models it on
`port-agreement.py`. **Verdict: KEEP.**

### 3. readiness-agreement
Script: `scripts/readiness-agreement.py`. It protects `app/src/readiness.ts`. That is the
client-side copy kept for instant autosave feedback (D54). It must stay in step with
`pipeline/decisions.py:blocking`, the server-side truth. It checks four subjects. One of
them resolves numbered line citations inside the script's own doc comments. It checks each
citation against the AST node it describes. This is worth a note for the reviewer. It is
the one place in this slice where a line number carries real weight. This repo has a
standing rule against citing a line rather than a symbol, D245. The two cases are not
quite the same. This citation points into the same file being read. It does not point into
a separate markdown file. So it does not plainly break D245. Still, it is worth a second
look. Cost sits in the 0.05-0.08s group (2026-09-20). **Verdict: KEEP**, with that note
flagged for the reviewer.

---

## B. Screen-content and design-system checks (product)

### 4. screen-freshness
Script: `scripts/screen-freshness.mjs`. It protects one property. Every server write that
`app/src/server.ts` makes must have a screen that re-reads after it. A stale row must never
sit on screen showing an answer the store already changed. It was earned by a real bug. It
is described in `Fulfillment.tsx`'s own comment. A stale card list once let an operator tap
Mark sold on a card another device had already sold. Cost is 0.76s (2026-09-20). It needs
node, guarded by `NPM_GUARD`. It is not path-gated itself, unlike its self-test below.
**Verdict: KEEP.**

### 5. screen-freshness-selftest
Same script, run in `--self-test` mode. It proves the checker's own classifier in both
directions. The classifier needs a call-graph closure, not a simple grep. Ten of the
exported writes carry their HTTP method through five module-private helpers. They do not
carry it in their own body. This is a guard of a guard. It is a member of the `guard-scope`
roster. Cost is 0.78s (2026-09-20). Its own header says it sat on no target at all until
2026-09-12. It was red on main once it was wired in for the first time. **Verdict: KEEP,
already correctly path-gated.**

### 6. sigil-check
Script: `scripts/sigil-check.py`. It runs twice per call, once as `--self-test` and once for
real. It protects one rule. A screen must never draw the store's internal `index` key where
a human-facing count belongs (D92). The worked example is box 3. There, `#27` once named
two different cards on one screen. A section header and a neighbouring row drew from two
different number spaces. Cost is 0.20s (2026-09-20). Known red: D92 records that the rule
was tightened after four instances of a second wrong spelling, `Card N`. Those four shipped
past a green run of the first version of this check. **Verdict: KEEP.**

### 7 and 8. css-var-check and css-var-check-selftest
Script: `scripts/css-var-check.py`. It protects against a `var(--x)` with no fallback where
`--x` is defined nowhere. The CSS spec makes that whole declaration silently invalid. There
is no console warning. It was earned directly by five real instances. They were found only
by hand, on 2026-09-20, across four screens. They were confirmed live through
`getComputedStyle`. This is one of the strongest incident-to-check pairings in this slice.
The check exists because the defect was already found. It cost real screen time to track
down by hand. Cost is unmeasured, since the target landed after the 2026-09-20 cost table.
The self-test proves the checker itself on fixtures in both directions. One fixture is
defined only from TSX. Neither is path-gated. **Verdict: KEEP both.**

### 9 and 10. token-literal-check and token-literal-check-selftest
Script: `scripts/token-literal-check.py`. It protects against a CSS literal that duplicates
a design token's value in the same property family. One example: `font-size: 22px` written
next to a token that already equals `22px`. The two values can silently drift apart later.
It is ratcheted per file (`scripts/token-literal-check.json`). That is a ceiling, not a
zero, because main already carried some before the ratchet existed. D256 governs this.
Neither cost is in the 2026-09-20 table, since both landed after it. **Verdict: KEEP
both.** Note for the reviewer: this is a style-drift check. It is softer than a broken
screen. It may belong in a lighter tier than `css-var-check`, which catches silent
breakage.

### 11 and 12. kit-adoption and kit-adoption-selftest
Script: `scripts/kit-adoption.mjs`. It protects two rules. Every route must render `<Page>`
from the kit. No screen may hand-roll a primitive the kit already owns, such as a dialog
role, a `<select>`, or a money format. The owner's own words, quoted in the script: a new
page built tomorrow should be able to inherit the other pages' properties. D275 governs
this. The mechanism is a shrinking allow-list. It is the same shape as
`token-literal-check`'s ratchet. Neither cost is in the 2026-09-20 table. **Verdict: KEEP
both.**

---

## C. Repo hygiene and doc-adjacent checks

### 13. ignore-check
Script: `scripts/ignore-check.sh`. It protects one property. Every path a worktree
provisions must be genuinely gitignored, whatever kind of thing sits at that path. Examples:
`harness/.cache/`, `.venv/`, `app/node_modules/`. D47 governs this. It was earned the hard
way. The same defect reopened the same day it was first closed. A hand-provisioned worktree
linked both paths. They went back to being untracked rather than ignored. One `git add -A`
away from committing an absolute path. That is the mistake that cost a 133MB mirror the
first time. Cost is 0.15s (2026-09-20). It stays out of the git hook by design. D18
forbids a commit gate that depends on local, uncommitted state. This question is about
local provisioning. **Verdict: KEEP.**

### 14. lint
`npm run lint`, eslint, plus `ruff check .` over the Python packages. This runs on a slice
this repo measured, not ruff's full default set (D82). This is a core product check. It is
named in 22 of the last 200 non-merge fix commits. That is the third highest hit rate in
the verification-cost table, after docs-audit and harness. Cost is 2.09s (2026-09-20).
**Verdict: KEEP.**

### 15. vale
Prose style over every tracked markdown file. Its own recipe states plainly that it can
never fail `make check`. A missing binary reports and exits 0. `--no-exit` swallows vale's
own status. D18 governs this. Cost is 1.72s (2026-09-20) when the binary is present. Cost
is near zero when it is absent. CI has no `vale` binary. The recipe's own comment names
this row as the one deliberately absent from `ci-check`. **Verdict: KEEP, but flag for the
reviewer.** A check that structurally cannot fail should never be read as coverage. It is a
diagnostic, not a gate. The summary table above lists it that way, not as a pass-or-fail
row.

### 16. typecheck
`npx tsc --noEmit` over `app/`. A core product check. It is named in 3 of the last 200 fix
commits, a low count next to lint and docs-audit. A low catch rate here fits a type system
doing its job upstream of commits. It does not point to a useless check. Cost is 3.34s
(2026-09-20). **Verdict: KEEP.**

### 17. audit-self-test
`scripts/docs-audit.py --self-test`. It proves that the checker behind 60 of the last 200
fix commits actually works. That is the single highest hit rate in this repo. It is a
member of the `guard-scope` roster. It was earned by a real gap. Its own Makefile comment
says it sat red and unnoticed until 2026-08-24. A stale fixture had stopped being false
while `docs-audit` stayed green the whole time. The checker of the checker had rotted
silently once already. Cost is 5.04s (2026-09-20). **Verdict: KEEP, already gated.**

### 18. mutate-anchors
`scripts/mutate-guards.py --verify-anchors`. A fast check, about 0.05s. It proves that
every mutation anchor text still exists in the guard source it targets. It stops the
mutation-testing corpus from silently going stale between real `make mutate-guards` runs.
Those runs cost 186.2s and stay out of `check` by design. This is the cheap, always-on
half of a two-tier mechanism. The expensive half stays out of `check` entirely.
**Verdict: KEEP.**

### 19. claim-stale
`scripts/claim-ids.py --stale`. It protects against a decision or debt id this branch
already claimed. That id could be silently taken by main since (D140, amended). It is
named in 15 of the last 200 fix commits, a real working hit rate. Cost is 6.22s
(2026-09-20). **Verdict: KEEP.**

### 20. revert-guard
`scripts/revert-audit.py branch`. It protects against a branch putting a file back the way
main had it. That is refused when main already carries the commit that changed it (D133).
The verification-cost document's own count says this check has caught nothing in 200
commits. The same document argues it should stay. The one thing it guards against is
recorded in `docs/debts/` as having actually happened. PR #221 silently restored the D119
hero. That was found only by a hand-walk, before this guard existed. Cost is 0.09s
(2026-09-20). The cost document's own words: a zero-cost guard with a real historical
defect behind it is not a tiering candidate. **Verdict: KEEP.**

---

## D. Guard self-tests already inside guard-scope's ROSTER, 22 entries, D247

These 22 all share one shape. Each builds a throwaway fixture, such as a temp repo, a temp
clone, or a process it starts and kills itself. None of them open the real store, the real
server, or a real screen. Each one proves a mechanism. `guard-scope.py` derives each
target's subject files from the test script's own source. It reads that script's imports
and its `Path`-style chains. It does not read a hand-typed list. It gates a target only
when the branch's diff does not touch any of those subjects. It fails open on every edge
case: no merge-base, an unreadable diff, an empty diff, an unscoped target, or any
exception. `PKMNSCAN_GUARD_SCOPE=off` runs every one of them regardless. `make docs-audit`'s
`guard scope` row reconciles the roster against the Makefile wiring, both ways. A dedicated
audit graded all 38 `scripts/checks.py:CHECKS` targets against a live commit or code path
each one names. D247's own text says none was found dead weight, these fifteen included.
That line still holds for the later additions on the same ground.

| # | Target | Test file it proves | Real caller named in D247 | Cost (09-20) |
|---|---|---|---|---|
| 21 | githooks-selftest | scripts/githooks-selftest.sh | main's own guard | 3.48s |
| 22 | merge-selftest | scripts/merge-selftest.sh | `make merge` | 4.46s |
| 23 | revert-selftest | scripts/revert-audit.py | revert-guard | 1.43s |
| 24 | claim-selftest | scripts/claim-selftest.py | claim-stale and claim-ids | 14.86s |
| 5 | screen-freshness-selftest | scripts/screen-freshness.mjs | screen-freshness | 0.78s |
| 17 | audit-self-test | scripts/docs-audit.py | docs-audit | 5.04s |
| 28 | submission-selftest | scripts/submission-selftest.py | `./pkmnscan identify`'s claim table | 1.05s |
| 29 | cid-selftest | scripts/cid-selftest.py | `cards name`, `audit`, `photos` | 0.43s |
| 30 | pricearchive-selftest | scripts/pricearchive-selftest.py | `archive sweep --write` | unmeasured |
| 31 | archive-review-selftest | scripts/archive-review-selftest.py | the archive review queue | unmeasured |
| 32 | holdings-selftest | scripts/holdings-selftest.py | the `#/revenue` unsold-stock panel | unmeasured |
| 33 | identity-checks-selftest | scripts/identity-checks-selftest.py | `cards checks` | unmeasured |
| 34 | price-postings-selftest | scripts/price-postings-selftest.py | `emit` and `reprice apply` | unmeasured |
| 35 | product-history-selftest | scripts/product-history-selftest.py | `#/product` | unmeasured |
| 36 | sku-number-contradictions-selftest | scripts/sku-number-contradictions-selftest.py | `cards contradictions` | unmeasured |
| 43 | janitor-selftest | scripts/janitor-selftest.sh | `make janitor` | 4.63s |
| 44 | reap-selftest | scripts/reap-selftest.sh | `make reap`, the PreToolUse kill guard | 15.04s |
| 45 | silent-write-selftest | scripts/silent-write-selftest.sh | the silent-write PreToolUse guard | 2.53s |
| 46 | guard-shell-selftest | scripts/guard-shell-selftest.sh | the nine-clause shell guard | 12.11s |
| 48 | suite-lock-selftest | scripts/suite-lock.py | `make design-check`'s machine lock | 1.32s |
| 51 | sync-selftest | scripts/sync-selftest.py | the primary checkout's self-sync, D176 | 7.42s |
| 52 | verdict-selftest | scripts/verdict-selftest.py | design-check's verdict reporter | 1.99s |

Aggregate cost, both measurements: 15 of these cost 76.6s of a 163.85s `make check`. That is
47 percent, on 2026-09-20, before the seven archive, identity, and pricing entries joined on
2026-09-23. A later, third-machine measurement found `make check` at 93.3s with all of them
running. It found 66.4s with them and `serve-selftest` both skipping. That is a 27s cut on
that hardware.

Overlap between entries in this table is low. Each one proves a different script. None of
the 22 tests the same code path as another. The overlap risk sits one level up, at the
mechanism itself. That risk sits between `guard-scope.py`, `serve-scope.py`, and the two
self-tests that prove them. It does not sit within these 22 targets.

**Verdict for all 22: KEEP, already correctly path-gated.** `serve-selftest` is listed
separately below. It is gated by the other mechanism, `serve-scope.py`. It is the single
largest cost in `make check` by a wide margin.

### 50. serve-selftest, listed separately for its size and its own gate
Script: `scripts/serve-selftest.py`, gated by `scripts/serve-scope.py`. That was the first
path-gated target. By the owner's 2026-09-17 ruling it was originally the only one:
revisit if the list grows. It did grow, into `guard-scope.py`, on 2026-09-20, on a fresh
measurement. Cost is 70.12s on 2026-09-17, 37 percent of `make check` on that tree. The
cost document calls it unbreakable by any change under `app/`. The self-test copies the
checkout with a stub `app/`. It is proved on real commits, not only its own self-test. One
commit that touches only `app/` classifies SKIP. A commit that touches the classifier
itself classifies RUN. **Verdict: KEEP, already gated correctly.** No action is needed. The
owner's 2026-09-17 ruling already treats this as the one deliberate, argued exception. It
has since been generalised into `guard-scope.py`, rather than left as a one-off.

---

## E. Guard self-tests not currently in guard-scope's ROSTER

These are the same shape as section D. Each builds a throwaway fixture, with no real store,
server, or screen. But they run unconditionally on every `make check`. That holds whether
or not the branch touches their subject. This is the most concrete, low-risk path-gate
candidate this slice found. It is a placement change, not a cut, on `guard-scope.py`'s own
precedent. D247's own text calls its growth "a placement change, never a pruning."

- **37. readings-selftest** (`scripts/readings-selftest.py`) proves the market-reading
  table, D189. It checks that table against an independent reimplementation of its own
  two-source walk. Real caller: `readings adopt` and `readings show`. Cost sits in the
  0.05-0.08s group (2026-09-20). That is cheap enough that gating it saves little time. It
  is listed here for consistency with the roster's own logic, not for the time saved.
- **38. skus-selftest** (`scripts/skus-selftest.py`) proves the store-owned SKU table,
  identity-follows-sku.md lane 0, D258. Real caller: `skus adopt`.
- **39. identity-store-selftest** (`scripts/identity-store-selftest.py`) proves the one
  writer: `bind_sku`, `unbind_sku`, and `record_identification`, lane 1.
- **40. identity-binding-selftest** (`scripts/identity-binding-selftest.py`) proves the
  migration's classifier. It also proves the merged D242 and D255 report, lane 2.
- **41. identity-readers-selftest** (`scripts/identity-readers-selftest.py`) runs four
  times per invocation. It runs with `--mutate-identity-fields`, `--mutate-no-fallback`,
  and `--mutate-no-refusal`. It already carries its own mutation coverage inline. It does
  not depend on `make mutate-guards`.
- **42. identity-cli-selftest** (`scripts/identity-cli-selftest.py`) proves the CLI
  writers, lane 3b: `emit`, `reconcile --live`, `join --export`.
- **47. coordinator-selftest** (`scripts/coordinator.py --selftest`) proves the merge-queue
  verdict rules. It was earned by a real incident. A coordinator session relayed a green
  merge status for several turns while nothing merged. A `pgrep`-based waiter matched its
  own command line. Cost sits in the 0.05-0.08s group.
- **49. browser-scope-selftest** (`scripts/browser-scope.py selftest`) proves the CI
  browser matrix's own path-gate classifier, D141. It runs on fixtures and on the real
  tree.
- **53. js-breakpoints-selftest** (`scripts/js-breakpoints.py selftest`) proves a real,
  named defect stays fixed. `Orders.tsx` carried a 1024px media query. No stylesheet it
  imports declares that breakpoint. This came from a global search-replace error.
- **54. subagent-override-selftest** (`scripts/subagent-override-selftest.py`) proves the
  `subagent override` docs-audit row. It builds a real nested git worktree for that proof.
  That is the exact shape of `.claude/worktrees/<name>/`, the exact place the 2026-09-19
  incident sat.
- **56. port-slots-selftest** (`scripts/port-slots.py selftest`) proves the per-checkout
  port-slot claim, D261. It was earned by a real, measured collision. Two worktrees hashed
  to the same dev port. A design-check in one reused the other's Vite. That check passed,
  silently.

**Verdict for this group: KEEP all. Path-gate as a batch is the first concrete, low-risk
recommendation in this file.** They share the same shape as the 22 already gated. Cost is
individually unmeasured. The group's aggregate cost is real. `guard-scope.py`'s own
subject-derivation mechanism needs no new design to absorb them. It only needs new
`ROSTER` entries. That is the same growth path D247 already used twice: fifteen to sixteen
to twenty-two. This is offered as a candidate, not a ruling. The 2026-09-17 record states
plainly that a request to extend path-gating is itself evidence the policy is spreading. It
needs the owner's word again.

### 55. guard-scope-selftest, the exception inside this section
This one proves `guard-scope.py` itself. That is the gate that gates the rest of section D.
It cannot sensibly gate itself, since a change to the gate must always be checked. That is
presumably why it sits outside its own `ROSTER`. Nothing in the repo states that reasoning
in words. A future reader would benefit from one comment saying so. I measured this here:
**0.54s**. It is mutation-tested by its own suite. Breaking the classifier turns cases red.
Mismatching the roster against the Makefile wiring turns the `guard scope` docs-audit row
red. **Verdict: KEEP, correctly exempt from its own gate.**

---

## F. The two path-gate mechanisms themselves

### scripts/serve-scope.py
It gates one target, `serve-selftest`. Its `SCOPE` list is hand-curated. It is reconciled
against `serve-selftest.py`'s own `CARRY`. `CARRY` is the literal list of what actually
gets copied into its throwaway tree. `make docs-audit`'s `serve scope` row checks this both
ways. It fails open on no merge-base, an unreadable diff, or an empty diff.
`PKMNSCAN_SERVE_SCOPE=off` is the escape hatch, printed on every skip. It is proved on real
commits, see item 50 above. **Verdict: KEEP.**

### scripts/guard-scope.py
It gates the 22-entry `ROSTER` in section D. It extends `serve-scope.py`'s design, rather
than copying it 22 times. Instead of a hand-curated subject list per target, it derives
each target's subject files from the test script's own source. It reads local-package
imports, `Path`-style chains, and a regex for the four shell-script tests. Only which
targets are gated stays hand-typed, on `serve-scope.py`'s own precedent. It shares the same
fail-open behaviour. It shares the same `PKMNSCAN_GUARD_SCOPE=off` escape hatch. `make
docs-audit`'s `guard scope` row reconciles it both ways. A roster target not wired into the
Makefile fails. A wired recipe missing from the roster also fails. **Verdict: KEEP.** This
is the mechanism that section E's candidates would extend, not a new one.

---

## G. Self-tests deliberately not in make check

### map-fix-selftest
`scripts/map-fix.py --selftest`. It proves the one generator D18 allows to write into a
doc. That doc is the `governed_by` field in `docs/map.py`. It proves this over a throwaway
map it writes and then drops. It is correctly excluded. `map-fix` is a generator, and it
writes. D18 forbids anything that writes from gating a commit. The row that verifies its
output, `make docs-audit`'s `repo map` row, already runs on every commit. The Makefile's
own words say this self-test would be proving the same thing one step further from the
damage. **Verdict: KEEP as-is, correctly excluded.**

### offenders-prune-selftest
`scripts/offenders-prune.py --selftest`. This has the same shape and the same reasoning as
`map-fix`. It proves a deleting generator. That generator removes stale entries from
`ste-offenders.json`, `typed-interpunct-allow.json`, and `line-anchor-offenders.json`. It
follows `map-fix`'s own precedent. **Verdict: KEEP as-is, correctly excluded.**

### catalog-index-selftest
`scripts/catalog-index-selftest.py`. It proves `scripts/catalog-index.py` and
`pipeline/catalog.py`. It proves them against a synthetic two-set fixture, D15, build-order
step 9, piece 2. A contradiction turned up here. The script's own module docstring says it
runs in `make check` through `catalog-index-selftest`. That is false. `make help`, three
separate Makefile comments at lines 106, 417, and 582, and the actual `check:` recipe all
agree it is deliberately not wired in. Lines 417 and 582 even cite this target's own
precedent as the reason two other self-tests are excluded. Those two are
`worktree-provision-selftest` and `map-fix-selftest`. The docstring is simply stale prose.
It never got corrected when the wiring decision was made, or was reverted. This is exactly
the class of drift `docs-audit` polices for markdown. It has no row for a Python docstring
making a false claim about the Makefile. **Verdict: KEEP the target as-is, correctly
excluded from `check`. Flag the docstring as a one-line factual error for whoever picks
this up.** `scripts/catalog-index-selftest.py`'s header should say it is not in `make
check`, matching the Makefile.

### demo-freshness and demo-determinism, "the demo-record selftests"
`scripts/demo-freshness.py` and the now-retired `demo-determinism.py`. Neither
carried a `-selftest` suffix. Both played that role for `make demo-record`'s output.
Neither gated `check`. D18 governs this. `demo-freshness`'s own recipe says it is worth one
command, not worth failing `make check` over. The bundle is not committed, and CI rebuilds
it fresh on every push. `demo-determinism` compared two full `make demo` runs' recorded
content, byte for byte. It found a real, measured defect: 97 `bound_at` timestamp values
differed between runs, before `bind_sku` took an explicit `at` parameter. `demo-freshness`
only checks the wire shape, not the content, and it stayed green throughout that whole
time. This is a real example of one check's blind spot being exactly the reason a second
check exists. **Verdict here: KEEP both as-is, correctly excluded from `check`.**

**SUPERSEDED by the plan's own C4/Q5 synthesis.** Both guards tested only the invented
seed. Nothing ships from that seed (D295). L5 retired both: the selftest's own `make check`
gate, and the demo.yml publish step. `demo-freshness` stayed. It was never gated in either
place this ruling names.

---

## H. Git hooks, scripts/githooks/

`make hooks` installs these into `.git/hooks-armed`, copied rather than symlinked. D42's
own correction in the Makefile explains why. A working tree is per-branch, but `.git` is
per-clone. The install must copy tracked files into the common directory, rather than
point at a working tree. `make status` reports drift between the tracked source and the
installed copy. Nothing gates on that drift, since a mismatch is not always an error.
Branches legitimately differ.

### pre-commit
Five checks run in one hook. Rule zero refuses a commit if the armed copy is stale behind
main. It was earned by a real incident. D92's sigil check merged, and the armed copy kept
the old pre-commit for four days. It silently skipped the new check on every commit in the
clone. Rule one keeps `fixtures/` read-only, since it is ground truth for the round-trip
test. Rule two refuses staged iCloud conflict copies. Rule three refuses staged symlinks
with an absolute or escaping target. Rule four refuses a staged image outside
`captures/`, or one carrying a decodable QR, the code-card opsec rule. Rule five runs
`docs-audit --staged` and fails the commit on a real disagreement, D16. Rule six runs
`sigil-check`. The bypass is `git commit --no-verify`, loud on purpose. Overlap: rules
five and six duplicate `make check`'s own `docs-audit` and `sigil-check` targets, but at
commit time rather than on demand. This is deliberate defense in depth. A commit made
outside an agent session, in an editor, still gets caught. It is not a redundant
duplicate. **Verdict: KEEP.**

### pre-push
It refuses any push whose remote ref is `main`, D42. The real server-side gate GitHub
would provide is unavailable at any price short of Pro, on a private repository. So this
hook is the branch protection, not a backup for one. Its own header states the limit
honestly: a push from anywhere else is unguarded. It also runs D133's revert-guard on
every branch push, not only pushes to main. It reads the checkout's own copy of
`scripts/revert-audit.py`. `PKMNSCAN_MAIN=off` is the escape hatch. **Verdict: KEEP.**

### reference-transaction
It stops main moving locally, by any mechanism: merge, rebase, `reset --hard`, or
`branch -f`. All of them are one ref update underneath. This is the one hook that cannot
be routed around by choosing a different porcelain command. It was earned by a real
incident. One commit, authored on a session's own branch, was fast-forwarded into main.
That creates no commit, and it runs no commit hook at all. Since 2026-09-12 it also prints
what main is carrying once it moves, a non-blocking half. It is the one script every
worktree of the clone is guaranteed to run, since `core.hooksPath` is shared through the
common `.git` directory. **Verdict: KEEP.**

### post-checkout and post-merge
Both are advisory only, D18. They never fail. They only print a reminder that
`scripts/githooks/` changed and `make hooks` should run again. `post-checkout` also
carries the D139 warning about which branch the primary checkout stands on. Neither can
gate anything. Their only job is to shrink the window before someone notices drift.
**Verdict: KEEP.**

---

## I. Claude Code hooks, .claude/settings.json

### scripts/guard-opsec.sh, PreToolUse on Write and Edit
It blocks a write that contains a code-shaped literal. That is the bearer-instrument
opsec rule, under D24 and D70. It fails open on any internal error, by explicit design
choice. Its own settings.json note explains why: a guard that blocks on its own bugs gets
disabled again. The pre-commit hook's broader pattern stays as the commit-time backstop.
It covers the roughly two percent this narrow rule lets through by design.
**Verdict: KEEP.**

### scripts/decision-context.py, PreToolUse on Write and Edit
Advisory only. It prints the governing decisions for the file being edited. It does this
through `hookSpecificOutput.additionalContext`, never through `permissionDecision`. So it
cannot structurally block or auto-approve anything. It exits 0 unconditionally, including
on its own bugs. **Verdict: KEEP**, with the same caveat as `vale`. It should not be
counted as a gate in any tally. It is a nudge.

### scripts/reap.py --hook, PreToolUse on Bash
It refuses a kill whose actual target lives outside this checkout. It resolves that
target through `pgrep` and `lsof`, rather than pattern-matching it. It was earned by two
incidents in one session, on 2026-09-10. A machine-wide `pkill` call killed the owner's
live capture server, over their real store. An `lsof`-based loop killed the desktop app's
network helper, because that command returns clients as well as listeners.
`PKMNSCAN_KILL=off` is the escape hatch, printed on every refusal. Its self-test,
`reap-selftest`, in section D, is deliberately in `make check` and not in this hook, per
D18. **Verdict: KEEP.**

### scripts/silent-write-guard.py --hook, PreToolUse on Bash
It refuses a git write, such as commit, push, pull, merge, rebase, cherry-pick, `make
merge`, or `gh pr merge`, when both its stdout and stderr are discarded. So a session can
never again report a push as landed after a refused commit it silently swallowed. It was
earned by nine instances of this exact class landing in about 24 hours. They were written
by the same session that had already written a rule against it. **Verdict: KEEP.**

### scripts/guard-shell.py --hook, PreToolUse on Bash, and on Write and Edit
Nine clauses. Each one resolves what a command would do, rather than matching what it
says. Each one carries its own named incident and its own escape hatch. A
checkout-over-modified-file destroyed about 240 uncommitted lines, twice. A `cd` prefix
wrote 1,500 lines into the owner's live main tree. A `gh api` call with a bare field
turned a GET into a POST, and it hung past a tool timeout. A pre-existing-path `ln -s`
created a symlink loop that ate a 133MB directory. A `pgrep`-based waiter ran 119 rounds
over about four hours. A push reached a differently named upstream. A bare, or
non-empty-stack, `git stash` risked another session's work on a 27-worktree clone. A `git
reset --hard` ran over uncommitted tracked work. A narrated, multi-minute wait, piped into
`tail`, hid its own heartbeat. All nine hatches are documented, and printed on refusal.
This is the single most incident-dense guard in the repo. Nine clauses, nine measured real
events, each with its own escape hatch. **Verdict: KEEP.**

### scripts/typecheck-hook.py, PostToolUse on Write and Edit
It runs `tsc` directly, not `make typecheck`. That target's `NPM_GUARD` install hint is
noise for a hook. It runs only when the written file is `.ts` or `.tsx` under `app/`. It
cannot block, since PostToolUse fires after the write already landed. Its predecessor ran
`make lint typecheck` unfiltered. It produced five lines of failure text after every edit,
for eight days. It blocked nothing, since both targets were stubs that exit 1 by design at
the time. **Verdict: KEEP** the filtered replacement, with the same advisory caveat as
`vale` and `decision-context.py`.

### scripts/worktree-guard.sh, SessionStart
It provisions `.venv`, T1's cache, and `app/node_modules`, in a fresh worktree, through an
APFS clone or a backgrounded `npm ci`. It was earned by three fresh-worktree failures that
predate it. None of their error messages named the word worktree: a missing numpy, a
fixture's AttributeError, and an empty cache. Each one cost a session a full turn to
diagnose. It writes, so D18 keeps it off the commit path. It runs only at session start.
**Verdict: KEEP.**

### scripts/stop-gate.sh, Stop
It runs `make harness` at turn end. This sits out of this slice's scope, since the harness
slice covers T1 through T9 and T11. Listed here only for completeness.

### scripts/session-teardown.sh, SessionEnd and WorktreeRemove
It stops what the ending session started. `WorktreeRemove` is the primary anchor. It fires
at exactly the moment a tree goes. That is the same moment whose absence once left four
supervisors restarting against deleted directories, D111. `SessionEnd` is the weaker
backup. It is not reliable at app quit or machine sleep. It explicitly skips the clear
reason by name, so it never stops a server someone is still using. It fails open on every
path. `make janitor` is the backstop for whatever it misses. **Verdict: KEEP.**

---

## Counts

- KEEP: 68 items.
- Of those, already correctly path-gated: 24. That is the 22-item ROSTER, plus
  `serve-selftest`, plus `screen-freshness-selftest`. The last one also appears once
  inside the ROSTER table. Do not double-count it when tallying.
- KEEP as-is, correctly excluded from `check`: 5. That is map-fix-selftest,
  offenders-prune-selftest, catalog-index-selftest, demo-freshness, and demo-determinism.
- Path-gate candidate, not yet actioned, offered rather than ruled: 11. That is
  readings-selftest, skus-selftest, identity-store-selftest, identity-binding-selftest,
  identity-readers-selftest, identity-cli-selftest, coordinator-selftest,
  browser-scope-selftest, js-breakpoints-selftest, subagent-override-selftest, and
  port-slots-selftest.
- MERGE candidates found: 0.
- SHRINK candidates found: 0.
- CUT candidates found: 0.

No item in this slice earned a CUT or SHRINK verdict. Every checker has a named, dated,
real incident behind it. Or it is near-zero cost with a real historical defect on record,
such as revert-guard. Or it is a guard of a guard. Its product-level check is one of the
highest-value items in the suite: docs-audit, screen-freshness, css-var-check.

## Top five candidates for the Opus reviewer's attention

1. Path-gate the 11 items in section E as one batch. They share the same shape, and the
   same mechanism, `guard-scope.py`, as the 22 already gated. No new design is needed.
   Offer it as one batch, rather than 11 separate asks, on the owner's own 2026-09-17
   caution: each new request is evidence the policy is spreading.
2. `scripts/catalog-index-selftest.py`'s docstring states a fact about the Makefile that
   is false. This is a one-line doc fix, not a design question. It is worth catching
   before it confuses the next reader the way it could have confused me.
3. `vale`, `decision-context.py`, and `typecheck-hook.py` cannot structurally fail or
   block anything. The corpus-wide review should call a gate a gate, and an advisory an
   advisory. Then a check count for this repo will not hide behind items that never go red.
4. `readiness-agreement.py` cites line numbers into its own file's AST. That is the one
   place in this slice where a line number carries real weight. It is worth one look,
   given the repo-wide rule against citing a line rather than a symbol, D245. The two cases
   are not exactly the same class of citation, though.
5. No CUT, MERGE, or SHRINK candidates turned up in this slice. Every item traces to a
   named, dated, real defect. Or it traces to a documented zero-cost or high-value
   argument. If the corpus-wide review is hunting for bloat, this slice points elsewhere.
   Look at the design-check specs, the docs/map.py machinery, or the harness itself,
   rather than at `check`'s own non-harness, non-docs-audit targets.
