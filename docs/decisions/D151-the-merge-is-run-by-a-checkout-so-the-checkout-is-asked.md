## D151 — The merge is run by a checkout, so the checkout is asked whether it is current, and main is read for a slug the moment it moves

**Built 2026-09-12, after an unclaimed id reached `main` for the second time.** D140 made a decision number something a branch writes as a slug and `make merge` turns into a number. The claim is a function in `scripts/merge-pr.py` — and `make merge` runs **the `scripts/merge-pr.py` of whatever checkout invoked it.** A checkout cut before that function does not fail: it performs the GitHub half, performs the local half, reports complete success, and main lands carrying a raw `## D-<slug>` heading that no citation can resolve against and no later merge can ever find, because the branch that wrote it is merged and gone. Pull request #270 stranded one, repaired by #273; pull request #280 stranded the next, repaired by #285.

**This is not D143 again.** That entry fixed a precondition that was seven lines too late *inside* the claim — a guard that existed and was unreachable. This one is about a checkout in which **the guard is not present at all**, which no ordering inside the file can reach. D143's own refusal is among the capabilities a stale copy does not have.

### The scale is measurable and it is not two checkouts

**Measured 2026-09-12 across the working trees of this clone: 30 trees, and 24 of them behind `origin/main`'s copy of the merge surface. Sixteen were missing `84c57d7` — the commit that introduced the claim at all.** So on the day this was written, more than half the trees on this machine would have stranded an id had a merge been run from them, and the two that did were the two that happened to be asked.

**The two pull requests' own head branches were current**, which is what took so long to see: neither stranding is visible in the pull request. `18dcf7c^2` carries a complete `claim_half`. The stale copy was a **third tree** — the one the session typed `make merge` in — and nothing in the merge's output, the pull request, or main's history records which that was.

### The predicate is BEHIND, and DIFFERS would have been the wrong one

**A branch developing the merge is supposed to differ from main's copy of it.** #280 was exactly that, and a guard comparing content would have refused the one workflow that keeps this file alive — which is how a guard gets switched off in a week. What is refused is a copy **missing commits main has**: `git log HEAD..origin/main -- <file>` non-empty. A checkout cut before a capability reads behind; a branch carrying main's commits plus its own reads clear.

**A diverged branch reads behind, and that is right rather than harsh.** If this branch has changed the merge AND has not taken main's change to it, it lacks the capability exactly as the stale checkout does. The refusal prints the same one-command fix either way: `git merge origin/main`.

**The surface is derived, not listed.** It is this file plus every `scripts/*.py` a module-level constant in it names — today `scripts/claim-ids.py`, through the `CLAIMER` constant that was already written that way. A guard that only ever checked itself would have been green through the half of the incident that lives in the claimer.

**What it cannot see is named rather than left to be found**: a merge that took `ours` over one of these files. That commit IS an ancestor, so reachability answers *not behind* over content that lost the capability anyway. `make revert-guard` is the guard whose subject that is — and the second half below catches the consequence regardless of cause.

### It has no escape hatch, which is a departure and is meant

**Every other refusal in this repository prints one** — `PKMNSCAN_SUITE_LOCK=off`, `PKMNSCAN_KILL=off`, `PKMNSCAN_REVERT=off`. Those exist because the thing they bypass can cost real minutes or stand between a session and the only route through. **This one costs `git merge origin/main`**, which is seconds and is the right thing to have done anyway. A hatch printed in the refusal is the button a session presses instead of reading, and what it would restore is a command that reports success while doing nothing — the worst failure shape this repository has.

### And the symptom is caught by the symptom, in the one file every checkout shares

**A guard inside `scripts/merge-pr.py` is absent from exactly the checkouts that need it.** That is the whole defect, and it applies to the refusal above as much as to the claim: it protects every checkout cut from this commit onward and reaches none of the twenty-four standing today. So there is a second half, and it is in `scripts/githooks/reference-transaction`:

**`core.hooksPath` is one installed directory in the common `.git` dir, so every working tree of this clone runs the same hook file**, and a local move of `refs/heads/main` is the one event all of them share. At the `committed` phase the hook reads the commit main just moved to and prints, loudly, when it carries a slug heading. It fires for the session that merged and for every session that pulls afterwards.

**It reports and never refuses, and the asymmetry is the argument.** By the time main moves locally the pull request is merged and origin carries the slug whatever happens here; refusing the fast-forward would leave this clone behind a main that is already wrong, repairing nothing and breaking every read downstream. Refusing is right before the damage and wrong after it. It runs at `committed` rather than `prepared` for the same reason the rest of that file fails open: a bug in it must not be able to abort anybody's ref transaction.

**Its pattern is deliberately looser than the claimer's.** `scripts/claim-ids.py` owns the grammar an id is ALLOCATED by; a report only has to notice a heading that is not a number, and a loose reader over-reports, which for a report is the safe direction. The strict answer is one command away and the message names it.

**`make merge` asks the same question itself**, through `scripts/claim-ids.py --landed <rev>` — the first reader in that file whose subject is a commit rather than a checkout — and its exit status becomes the merge's. A claimer that cannot answer is reported rather than read as clean, which is the rule the claim commit's wait is built on, one function along.

### Proved by reproducing the stale checkout, not by asserting about it

`scripts/merge-selftest.sh` builds the progression in a throwaway origin and clone: main moves on something unrelated (allowed — a guard that refused every branch behind main would be off within a day), main takes a capability in the merge (**refused, naming the file, both blobs and the commit**), the branch merges main (allowed), the branch then edits the merge itself (allowed — #280's case), and main moves again underneath it (refused, naming the derived second file). `scripts/githooks-selftest.sh` moves a fixture main onto a slugged commit and asserts the report, its content, that it fires once, and that main moved anyway; `scripts/claim-selftest.py` proves `--landed` reads the commit and not the tree it is standing in, in both directions.

**Ten mutations, none survived.** The one worth naming is the first: rewriting the predicate as *differs from origin/main* turns the AHEAD case red and nothing else — which is the case that chose the predicate, and the only arm that can tell the two apart.

**One case could not be built out of a fetch and the fixture records the measurement.** Whether the hook reads `refs/heads/main` rather than every line of the payload needs a transaction carrying two refs; `git fetch` with two refspecs issues **one transaction per ref** on this machine's git, measured. `git update-ref --stdin` is the porcelain that batches, so that is what the case uses — a real gesture rather than the hook being fed by hand.

### What it does not decide

**Not that `make check` gains a row.** The question is about a checkout's relationship to `origin/main` at the moment of a merge; asked on the commit path it would refuse commits for being behind, which is not a defect. **Not that the surface grows to `scripts/`**: a merge refused because an unrelated script moved is noise, and narrowness is what the unrelated-file arm exists to hold. **Not that the hook learns the strict grammar** — that would be a third declaration of it, and `claim vocabulary` reconciles two. **And not that any of this repairs a stranded id.** Nothing here rewrites main: a substitution made after the merge reaches main's own copy of the entry, which D140 settled and this does not reopen.
