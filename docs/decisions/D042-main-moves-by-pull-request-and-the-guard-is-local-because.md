## D42 — main moves by pull request, and the guard is local because the server-side one is not for sale

**`main` moves only by a merged pull request, and two local git hooks enforce it.** Built 2026-08-29, after main moved under live worktrees twice in one day.

`637e2e4` was authored on one session's branch and fast-forwarded into main while three others were working on branches cut from it; `f5dcc2b` was pushed straight to `origin/main` during the session that wrote this entry. `origin/main`'s reflog is five consecutive `update by push`. Nothing in the repo had ever said a session may not do that, and nothing checked.

### Branch protection was not available here, and is now on (amended 2026-09-06)

**AMENDED 2026-09-06: the owner upgraded to GitHub Pro and protection is now on.**
A pull request is required, force pushes and deletions are refused, and `enforce_admins` is
true so it binds the owner as well. `required_approving_review_count` is **0** — GitHub
refuses a self-approval, so requiring one on a solo repo would mean nothing could ever be
merged. `required_status_checks` is null because nothing runs on a PR yet, and
`required_linear_history` is false because this repo merges with merge commits.

**The hooks stay, and the paragraph below is why.**
This entry already argued that a remote gate would have caught one of the two incidents and
been silent through the other; that argument is unchanged, and it is now the reason the two
guards are complementary rather than one superseding the other. Nothing about `make merge`,
the two local hooks or `PKMNSCAN_MAIN=off` changes.

What follows is the measurement as it stood when this entry was written.

Measured rather than assumed — both surfaces answered 403:

    GET repos/shivinate7/pkmnscan/rulesets                   403
    GET repos/shivinate7/pkmnscan/branches/main/protection   403
    "Upgrade to GitHub Pro or make this repository public to enable this feature."

Free plan, private repo. Going public is not an option: `CLAUDE.md`'s opsec rule makes a live unredeemed code card a bearer instrument, and this tree carries the enforcement for it. So the server-side gate costs a subscription, and the owner chose the local guard. **They later bought it** — see the amendment above; the repo stayed private, which is what Pro buys and what going public would have cost.

**It would not have closed this on its own**, which matters if the plan ever changes. Branch protection bites at `git push`. Both incidents moved main **locally** first, by which point every session cut from main is already on a different history. A gate at the remote would have caught the second and been silent through the first.

### Two hooks, because there are two ways out

- **`scripts/githooks/reference-transaction`** — main does not move in this clone. A ref hook rather than a commit hook **because the first incident created no commit**: a fast-forward merge moves a ref and runs no commit hook, and `git rebase`, `git reset --hard`, `git branch -f` and `git update-ref` are the same shape. Underneath they are one ref update, so that is the only place catching all of them and the only one no porcelain command routes around.
- **`scripts/githooks/pre-push`** — nothing pushes to main. `git push origin HEAD:main` never touches `refs/heads/main` locally and lands the commit anyway, so the first hook is blind to it. This stands in for branch protection and is weaker in one nameable way: it lives on this machine, so it protects this clone rather than the repository.

**The one legitimate move is to a commit origin already has.** That is the whole allow rule, and it is what makes the pair a workflow rather than a wall: a PR is merged on GitHub, `git pull` fast-forwards, and the commit was on the remote before it was ever on your main. It cannot be forged from inside a session, because a local commit is not on origin until something pushes it, and pushing to main is what the second hook refuses.

### The `old` column is not evidence

The payload is `<old> <new> <ref>`, so the obvious rules are *allow a no-op* (`old == new`) and *allow a creation* (`old` all zeros). Both are wrong, and believing them shipped two holes. Measured on git 2.39.3:

    git branch -D main              0000000... 0000000... refs/heads/main
    git branch -f main feature      0000000... 3f5f2cd... refs/heads/main
    git update-ref refs/heads/main  0000000... 8f06f47... refs/heads/main

Git reports zeros whenever the caller did not state an expected value, even where main exists at a real commit. A deletion is indistinguishable from a no-op and `branch -f` from a creation — the first draft waved both through, and main was genuinely deleted in the test rig. The hook decides on `new` alone and asks git for the pre-update value itself.

**It fails open on its own bugs, which is a trade rather than a weakness.** This runs on every ref update in every worktree of the clone, so a version exiting non-zero by accident breaks git for every concurrent session at once. The only non-zero exit in the file is the deliberate refusal; an unknown phase, an unparseable line or a missing git allows. Same rule `scripts/docs-audit.py:nested_worktrees` states for itself, and the same one `scripts/guard-opsec.sh` took after it over-triggered (D16).

### Installed into the git common dir

**This paragraph said something else for about an hour and both its claims were false.** It said to point `core.hooksPath` at the MAIN worktree's `scripts/githooks`, because that setting lives in the common `.git` dir so one value governs every worktree.

**Claim one, falsified within the hour of merging.** A working tree's contents are a function of its branch. The moment this entry landed on main, the main checkout was on another session's WIP branch that predated it, so the directory git read held **one hook out of three**. The guard was armed at zero and nothing said so — the silent-failure class this repo refuses everywhere else, reproduced by the fix for it.

**Claim two, falsified by running the test rather than reading the config.** `extensions.worktreeConfig` is **on** in this clone, and whatever creates `.claude/worktrees/` writes a per-worktree `core.hooksPath` into `.git/worktrees/<name>/config.worktree`, beside a `core.longpaths`, so it is that tooling and not this repo. **A per-worktree value beats the common one.** After an install that printed success, `git config --get core.hooksPath` inside a worktree still answered the old path and all four worktrees were unguarded. It was found by running the nineteen cases against the INSTALLED directory — `PKMNSCAN_HOOKS_DIR` exists for exactly this — and would not have been found by reading the config, because the config that lies is not the one you look at.

So `make hooks` copies the tracked hooks into `<git-common-dir>/hooks-armed`, points the common config there, and UNSETS the per-worktree override everywhere. `.git` is per-clone and no branch can empty it. Verified after: all seven worktrees resolve to the install, the installed copy passes all nineteen cases, and a live `git push --dry-run --force origin <branch>:main` is refused by name.

**It installs what git tracks, not what the directory holds.** The first version copied `scripts/githooks/*`, and this repo lived in iCloud Drive, which had made `pre-push 2` and `reference-transaction 2` beside the originals — so it installed five hooks from three files, two untracked and reviewed by nobody. Git dispatches on exact names so it would not have RUN those two, and the damage was cosmetic; the mechanism is not. `git ls-files` is the only enumeration meaning *the thing someone reviewed*, and untracked files present are reported rather than skipped.

**What is given up: the copy can go stale**, and a new worktree gets handed the per-worktree override again. Neither can be closed by a check without lying — the tracked file legitimately differs between branches, so *installed does not match this tree* is a fact and never a fault, and must never gate a commit. `make status` reports both instead, reading NOT ARMED whenever the effective path is not the install.

### A session may perform the merge when the owner says the word

The owner's amendment, 2026-08-30. The sentence that changes is *the owner merges it on GitHub*, and only that sentence: the two hooks, what they refuse and why are untouched, because none of that is about who presses the button.

**The permission covers both halves of the merge**, which is the owner's second amendment of the same day. An earlier reading granted only `gh pr merge` and left the clone permanently one commit short: a session that merged had to stop and *describe* the `git pull`, which is a handoff in the middle of one operation and leaves every later session cutting branches from a stale main.

**It cannot widen what is mechanically possible, and that is the safety argument.** Allow rule 3 of `scripts/githooks/reference-transaction` is `git merge-base --is-ancestor "$new" refs/remotes/origin/main` — move main to a commit origin already has — and the commit a merged PR produces IS that commit. So this reaches the prose and nothing else: it arms nothing, disarms nothing, edits no file under `scripts/githooks/`, and needs no escape hatch. **`PKMNSCAN_MAIN=off` is not what a session reaches for here** and must not become it; a session typing that variable has left this amendment behind.

### The local half is two states, and one question tells them apart

**The move is two commands and must be.** An earlier draft said `git fetch origin main:main`, which is the right shape for this clone — the hook's own refusal message suggests `git switch main && git pull`, and main is often checked out in no worktree at all here, so there is frequently nowhere to switch. What it missed is that the combined refspec updates both refs **in one transaction**:

    git fetch origin main:main
      255e33b..8e8973f  main -> main
      51492d6..8e8973f  main -> origin/main        <- same transaction

At `prepared` the hook asks `git merge-base --is-ancestor "$new" refs/remotes/origin/main`, and that read of `refs/remotes/origin/main` answers with the PRE-update value — so whenever origin/main has moved since your last fetch, `new` is a DESCENDANT of what the hook can see rather than an ancestor, and it refuses. **The evidence the hook consults is being written by the transaction it is judging.**

**This is not a hook defect and must not be fixed in the hook.** The repair that suggests itself — read the transaction's own `origin/main` line and credit it — is the mistake that file's header refuses for the `old` column: **a transaction may not be a witness for itself.** Trusting a caller-supplied line would let one `git update-ref` naming two refs assert its own permission. The hook asking git for state OUTSIDE the transaction is what makes it sound, and the cost is that the caller fetches first. Observed 2026-08-30 against a main that had moved under it, PR #22 having merged between the write and the run — not a rare alignment but the ordinary state of a clone running seven worktrees.

**Ask which working tree, if any, holds main:**

    git worktree list --porcelain | awk '/^worktree /{w=$2} /^branch refs\/heads\/main$/{print w}'

**Nothing printed — main is checked out nowhere:**

    git fetch origin && git fetch origin main:main

**A path printed — main is checked out there.** Added 2026-08-30 after PR #38, because `git fetch origin main:main` is exactly what git will not do to a branch somebody is standing on:

    fatal: refusing to fetch into branch 'refs/heads/main' checked out at '/Users/shivinate/Developer/pkmnscan'

**That refusal is git's and not the hook's**, and telling them apart is most of why this is written down. Everything else here is about a hook that refuses, so a session reading the word `refusing` reaches for `PKMNSCAN_MAIN=off`, which changes nothing because no hook has spoken. `git switch main && git pull` is unaffected and always was: `pull` is a fetch and then a merge, two transactions, in that order. The hook's refusals name themselves and print the variable; this one names a path. Pull in that tree instead:

    git -C <that path> pull --ff-only

**Neither form is newly permitted.** Both are two transactions in the right order, so the hook still asks `merge-base --is-ancestor` against an `origin/main` that demonstrably holds the commit.

**The unconditional shortcut is a footgun.** `git -C <main tree> pull --ff-only` is correct only while main is the branch in that tree. Run without the question above, in the state this entry describes — the main working tree on a feature branch — it fast-forwards **that feature branch**. It moves no protected ref, so no hook has anything to say, and the only symptom is a branch somebody else is working on having quietly advanced.

**Rejected: a `make` target that picks for you.** It would delete the choice, and the choice is not what goes wrong — the two incidents are main moving *unasked*. What it would cost is the thing this entry values: the move is a deliberate act on the owner's word, and a target reads as routine plumbing.

**What it costs is real and is this entry's own subject.** Advancing main reshapes what every live worktree is cut from. What makes it a decision rather than a repeat is the pair of conditions above: an explicit instruction, and only to a commit that was on origin first.

**That rejection is amended, and the sentence moves while the reasoning does not** (owner, 2026-09-01). `make merge` exists — `scripts/merge-pr.py`, `scripts/merge-selftest.sh`.

**The rejection was aimed at automating the decision, and the decision is untouched.** Whether this pull request gets merged stays the owner's word, per *The word* below: a bare `make merge` refuses and says there is no default and will not be one, `ARGS=<n>` is a preview that presses nothing, and only `ARGS="<n> --confirm"` acts. That is D33's instrument one register down — the route that can spend money refuses without an explicit field, and this refuses without an explicit number and flag.

**What is automated is the state lookup, which is not a choice anybody makes.** Which of the two forms above applies is a question with one right answer that git already knows, and *the unconditional shortcut is a footgun* two paragraphs up is the account of what it costs to get wrong: no error, no hook, a branch somebody else is working on quietly advanced. A session was being asked to remember a lookup; it asks git instead, and re-asks with `git rev-parse --abbrev-ref HEAD` before it pulls.

**It widens nothing mechanically, for the same reason the amendment above widens nothing.** It fetches origin first and then asserts `merge-base --is-ancestor <commit> refs/remotes/origin/main` — allow rule 3, evaluated before anything moves rather than discovered when the hook refuses. It never sets `PKMNSCAN_MAIN` and no refusal it prints suggests it. A commit origin does not carry is refused by name.

**`make help` lists it, and the plumbing worry is answered by shape rather than by obscurity.** Hiding the target would be security by not-being-listed, which this repo rejects everywhere else, and `CLAUDE.md`'s own rule is that a capability nobody can find is not done. The two raw commands stay in `CLAUDE.md` beside it: the wrapper must not become the only way anyone knows the answer.

**The footgun has a test that was green for the wrong reason first.** `scripts/merge-selftest.sh` builds an origin, a clone and a linked worktree in a temp directory. Its first draft put the other tree on a branch already at the commit a wrong pull would have brought it to, so the assertion could not fail — found by forcing the picker to always choose the pull form and watching it stay green. The branch is one behind its upstream now, that mutation turns it red, and the fixture asserts its own arming. Same lesson `githooks-selftest` records about git's own refusals scoring as a hook's.

### The main checkout going stale

**The SessionStart hook reports the main working tree left on a feature branch after that branch merged.** Added 2026-08-30. Everything above governs how main MOVES; this is the tree that holds it drifting a different way.

**Measured that day: 70 commits behind, on a branch merged in PR #43, serving the owner's real store.** Nothing was lost, because the branch was fully merged. What it cost was the live rig running behind four merged PRs while `make status` reported `0 ahead of main, 70 behind it` and nobody read it.

**`scripts/worktree-guard.sh` carries it because that runs unasked.** D43 puts the ports there for the same reason rather than in a target somebody has to remember.

**It reports and never switches.** `git switch` is the operator's to type, and a hook that moved the branch under a running server would be deciding for them.

**Ahead is the number that decides, not behind.** Zero ahead with a clean tree means the branch holds nothing main does not, so switching can lose nothing. Anything else says so and points at `make status`. A worktree on a feature branch is correct and is never reported.

### The word

**It comes from the owner in the conversation, and it is per-instruction.** Not a standing grant, not a mode, never inferred. It is the same shape as D33's `confirm` field one register down — that route refuses without an explicit field because the next thing that happens costs money, and this refuses without an explicit instruction because the next thing that happens is the branch every other session is cut from.

**The test is whether the owner NAMED THE ACT, not whether they matched a phrase.** Added 2026-08-30, after this paragraph cost a session a round trip: it said *"merge to main" is the word*, and a session reading that literally hesitated over a bare **"Merge"** — the verb itself, as a direct instruction. That is the word. So are *merge it* and *merge the PR*. What is not the word is approval that never names the act: *ship it*, *land it*, *looks good*, an approving review. **The line is naming the operation versus expressing satisfaction with the work.** A phrase list is a worse instrument, because a session matching on phrases both balks at a plain instruction and can be walked into a merge by anyone who says five particular words.

**The merge is one operation, performed whole, and a session does not stop between the halves to ask again.** This is the correction the owner asked for after a session merged on GitHub, reported that local main had not moved, and waited — a session reading the entry correctly, which is what makes it a defect here rather than there. One word, both halves: `gh pr merge`, then the fast-forward. If the second half refuses or cannot run, that is reported as the incomplete operation it is, not re-asked as though permission were missing.

**What it does not license**: a direct push, a force push, `git branch -f`, `git update-ref`, or a merge of a PR the owner did not name. All four are still refused by a hook, and none becomes available by the owner saying this word.

**The local fast-forward is split rather than refused whole.** The incident that list meant is `637e2e4`, a fast-forward to a commit on NOBODY's origin, and that stays refused by the hook rather than merely by this paragraph. What the word licenses is the fast-forward to the merged commit ON ORIGIN, a different move sharing a verb. The hook has always drawn that line; today the prose draws it too.

**Why this is safe to grant and was not safe to assume.** What was missing was never the owner's consent — they had it either time. It was any record that consent was required, and any mechanism that noticed its absence. Both now exist, so an explicit instruction is a decision rather than a default.

### A standing grant to the orchestrating session (amended 2026-09-13)

**"The word" above is still per-PR by default. This is the one exception, and it is scoped rather than a repeal.** After being asked twice to name the act for PR #349, the owner said to the orchestrating session: *"You are the orchestrator -- you have my explicit permission to do merges."* That names the act once for a whole batch instead of once per PR in it.

**The grant is to the ORCHESTRATING session, and only for PRs it stood behind.** It covers a PR only when that session put the PR's plan to the owner and reviewed its diff — never a worker or a peer session merging a PR of its own, which still needs the word exactly as above. It is exercised only through `make merge ARGS="<n> --confirm"`, from a checkout standing on the PR's own branch, only once CI is green, and never with `--admin`. A later session — a new orchestrator, or the same one returned to a fresh batch — re-asks; the grant does not carry forward on its own.

### The escape hatch and the evidence

**`PKMNSCAN_MAIN=off`**, spelled the way `PKMNSCAN_GATE=off` and `PKMNSCAN_DOCS=off` already are. One variable, printed in every refusal, because a guard with no visible way past it gets disarmed at the config instead — and a disarmed `core.hooksPath` takes the three opsec rules with it, the trade D16 already refused for the docs audit.

**`make githooks-selftest` is the evidence, and it runs in `make check` and never in the git hook.** D18's rule: it writes — a bare repo, a clone, commits, pushes. It has a second reason of its own that the docs audit's self-test does not: it exercises the guard by **violating** it, so a version on the commit path would be refusing its own commits. Nineteen cases, two of which were green for the wrong reason until the harness checked whose refusal it was — git declines to delete the branch you are standing on and declines to push what is already up to date, both without consulting a hook. A refusal now has to carry the hook's own marker to count.

**What it does not cover**: one machine's clone. A push from anywhere else, a commit in a different clone, and the GitHub web editor are all outside it — the exact gap branch protection would close.

**What would reopen this: GitHub Pro, or the repository going public.** Either makes rulesets available, and the honest response is to add one requiring a pull request on main and keep both hooks — the server gate for what reaches the repository, these for what reaches this clone's main. Not either/or: the two incidents were one of each.

---
