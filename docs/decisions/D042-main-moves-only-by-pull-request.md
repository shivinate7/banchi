# D42 — Main moves only by pull request

**`main` moves only by a merged pull request. Two local git hooks enforce it.** Main moved under live worktrees twice in one day. A commit authored on one session's branch was fast-forwarded into main. Three other sessions were working on branches cut from it. A commit was also pushed straight to `origin/main`. `f5dcc2b` was pushed straight to `origin/main` during the session that wrote this entry. `origin/main`'s reflog is five consecutive `update by push`. Nothing in the repo said a session may not do that, and nothing checked.

### Branch protection is on

**The owner upgraded to GitHub Pro, and protection is on.** A pull request is required. Force pushes and deletions are refused. `enforce_admins` is true, so the rule binds the owner too. `required_approving_review_count` is **0**. GitHub refuses a self-approval, so requiring one on a solo repo would block every merge. `required_status_checks` is null, since nothing ran on a PR at the time. `required_linear_history` is false, since this repo merges with merge commits.

The local hooks stay. Protection bites at `git push`. Both incidents moved main **locally** first. By then every session cut from main was on a different history. A gate at the remote would have caught the second incident and been silent through the first. So the server gate and the local hooks are complementary. Nothing about `make merge`, the two local hooks or `BANCHI_MAIN=off` changes.

The first measurement, before the upgrade, showed both surfaces refusing with 403:

    GET repos/shivinate7/banchi/rulesets                   403
    GET repos/shivinate7/banchi/branches/main/protection   403
    "Upgrade to GitHub Pro or make this repository public to enable this feature."

The repo was private on the free plan. Going public was not an option. `CLAUDE.md`'s opsec rule makes a live unredeemed code card a bearer instrument. So the owner chose the local guard, and later bought Pro. The repo stayed private.

### Two hooks, because there are two ways out

- **`scripts/githooks/reference-transaction`.** Main does not move in this clone. It is a ref hook, not a commit hook, because a fast-forward merge moves a ref and runs no commit hook. `git rebase`, `git reset --hard`, `git branch -f` and `git update-ref` have the same shape. Underneath, they are one ref update. So this is the only place that catches all of them. No porcelain command routes around it. It refuses at the `prepared` phase and prints nothing at `committed`. A report of an unclaimed decision id on main was cut on the owner's word.
- **`scripts/githooks/pre-push`.** Nothing pushes to main. `git push origin HEAD:main` never touches `refs/heads/main` locally, and it still lands the commit. The first hook is blind to it. This hook stands in for branch protection. It is weaker in one nameable way: it lives on this machine, so it protects this clone, not the repository.

**The one legitimate move is to a commit origin already has.** That is the whole allow rule. It makes the pair a workflow, not a wall. A PR is merged on GitHub. `git pull` fast-forwards. The commit was on the remote before it was on your main. A session cannot forge this. A local commit is not on origin until something pushes it. Pushing to main is what the second hook refuses.

### The `old` column is not evidence

The payload is `<old> <new> <ref>`. The obvious rules are *allow a no-op* (`old == new`) and *allow a creation* (`old` all zeros). Both are wrong, and believing them shipped two holes. Measured on git 2.39.3:

    git branch -D main              0000000... 0000000... refs/heads/main
    git branch -f main feature      0000000... 3f5f2cd... refs/heads/main
    git update-ref refs/heads/main  0000000... 8f06f47... refs/heads/main

Git reports zeros whenever the caller did not state an expected value, even where main exists at a real commit. A deletion looks like a no-op. `branch -f` looks like a creation. The first draft waved both through, and main was really deleted in the test rig. The hook decides on `new` alone. It asks git for the pre-update value itself.

**One exemption: packing.** `pack-refs` and `gc` write main into packed-refs. Then they delete the loose main, stating `<sha> 0000`. A delete is allowed only when `old` is nonzero, equals main's value on disk, and a loose file exists. A real delete states zeros first, so it stays refused.

**It fails open on its own bugs. That is a trade, not a weakness.** This runs on every ref update in every worktree of the clone. A version that exits non-zero by accident breaks git for every concurrent session at once. The only non-zero exit in the file is the deliberate refusal. An unknown phase, an unparseable line or a missing git allows. This is the same rule `scripts/docs_audit/core.py:nested_worktrees` states for itself. `scripts/guard-opsec.sh` took it after it over-triggered (D16).

### Installed into the git common dir

**The first version of this paragraph was wrong on both claims.** It said to point `core.hooksPath` at the MAIN worktree's `scripts/githooks`. That setting lives in the common `.git` dir, so one value would govern every worktree.

**Claim one was falsified within the hour.** A working tree's contents follow its branch. Once this entry landed on main, the main checkout sat on another session's WIP branch that predated it. The directory git read held one hook out of three. The guard was armed at zero, and nothing said so. That is the silent-failure class this repo refuses everywhere else.

**Claim two was falsified by running the test, not by reading the config.** `extensions.worktreeConfig` is on in this clone. Whatever creates `.claude/worktrees/` writes a per-worktree `core.hooksPath` into `.git/worktrees/<name>/config.worktree`. It writes a `core.longpaths` there too. That is the tooling, not this repo. **A per-worktree value beats the common one.** After an install that printed success, `git config --get core.hooksPath` inside a worktree still answered the old path. All four worktrees were unguarded. The nineteen cases, run against the INSTALLED directory, found it. `BANCHI_HOOKS_DIR` exists for that. Reading the config would not have found it. The config that lies is not the one you look at.

So `make hooks` copies the tracked hooks into `<git-common-dir>/hooks-armed`. It points the common config there, and it UNSETS the per-worktree override everywhere. `.git` is per clone, and no branch can empty it. Verified after: all seven worktrees resolve to the install. The installed copy passes all nineteen cases. A live `git push --dry-run --force origin <branch>:main` is refused by name.

**It installs what git tracks, not what the directory holds.** The first version copied `scripts/githooks/*`. The repo lived in iCloud Drive, which had made `pre-push 2` and `reference-transaction 2` beside the originals. So it installed five hooks from three files. Two of them were untracked and reviewed by nobody. Git dispatches on exact names, so it would not have run those two. The damage was cosmetic, but the mechanism was not. `git ls-files` is the only enumeration that means *the thing someone reviewed*. Untracked files present are reported, not skipped.

**What is given up: the copy can go stale.** A new worktree gets handed the per-worktree override again. Neither can be closed by a check without lying. The tracked file legitimately differs between branches. So *installed does not match this tree* is a fact, never a fault. It must never gate a commit. `make status` reports both instead. It reads NOT ARMED whenever the effective path is not the install. No hook prints a reminder. `post-merge` and `post-checkout` were removed on the owner's word.

### The batch runner performs the merge when the owner says the word

An owner amendment. The sentence that changes is *the owner merges it on GitHub*. Only that sentence changes. The two hooks, and what they refuse and why, are untouched.

**The permission covers both halves of the merge.** The owner's second amendment of the same day made this explicit. An earlier reading granted only `gh pr merge`. That left the clone one commit short. A session that merged had to stop and describe the `git pull`. That is a handoff in the middle of one operation. It leaves every later session cutting branches from a stale main.

**It cannot widen what is mechanically possible.** Allow rule 3 of `scripts/githooks/reference-transaction` is `git merge-base --is-ancestor "$new" refs/remotes/origin/main`. It moves main to a commit origin already has. The commit a merged PR produces is that commit. So this amendment reaches the prose and nothing else. It arms nothing and disarms nothing. It edits no file under `scripts/githooks/`, and it needs no escape hatch. **`BANCHI_MAIN=off` is not what a session reaches for here, and it must not become that.** A session that types the variable has left this amendment behind.

### The local half is two states, and one question tells them apart

**The move is two commands, and it must be two.** An earlier draft said `git fetch origin main:main`. That is the right shape for this clone. The hook's refusal message suggests `git switch main && git pull`. But main is often checked out in no worktree at all here, so there is frequently nowhere to switch. The earlier draft missed one thing. The combined refspec updates both refs **in one transaction**:

    git fetch origin main:main
      255e33b..8e8973f  main -> main
      51492d6..8e8973f  main -> origin/main        <- same transaction

At `prepared`, the hook asks `git merge-base --is-ancestor "$new" refs/remotes/origin/main`. That read of `refs/remotes/origin/main` answers with the PRE-update value. So when origin/main has moved since your last fetch, `new` is a DESCENDANT of what the hook can see, not an ancestor. The hook refuses. **The evidence the hook consults is being written by the transaction it is judging.**

**This is not a hook defect, and the hook must not be changed for it.** The repair that suggests itself is to read the transaction's own `origin/main` line and credit it. That is the mistake the file's header refuses for the `old` column. **A transaction may not be a witness for itself.** Trusting a caller-supplied line would let one `git update-ref` naming two refs assert its own permission. The hook asks git for state OUTSIDE the transaction. That is what makes it sound. The cost is that the caller fetches first. This was observed against a main that had moved under it, with PR #22 merged between the write and the run. That is the ordinary state of a clone running seven worktrees.

**Ask which working tree, if any, holds main:**

    git worktree list --porcelain | awk '/^worktree /{w=$2} /^branch refs\/heads\/main$/{print w}'

**Nothing printed means main is checked out nowhere:**

    git fetch origin && git fetch origin main:main

**A path printed means main is checked out there.** This case was added after PR #38. `git fetch origin main:main` is exactly what git will not do to a branch somebody is standing on:

    fatal: refusing to fetch into branch 'refs/heads/main' checked out at '/Users/shivinate/Developer/banchi'

**That refusal is git's, not the hook's.** Telling them apart is most of why this is written down. Everything else here is about a hook that refuses. A session that reads the word `refusing` might reach for `BANCHI_MAIN=off`, which changes nothing, because no hook has spoken. `git switch main && git pull` is unaffected, and always was. `pull` is a fetch and then a merge, two transactions, in that order. The hook's refusals name themselves and print the variable. This one names a path. Pull in that tree instead:

    git -C <that path> pull --ff-only

**Neither form is newly permitted.** Both are two transactions in the right order. The hook still asks `merge-base --is-ancestor` against an `origin/main` that holds the commit.

**The unconditional shortcut is a footgun.** `git -C <main tree> pull --ff-only` is correct only while main is the branch in that tree. Run without the question above, in the state this entry describes (the main working tree on a feature branch), it fast-forwards **that feature branch**. It moves no protected ref, so no hook has anything to say. The only symptom is a branch somebody else is working on having quietly advanced.

**Rejected: a `make` target that picks for you.** It would delete the choice. The choice is not what goes wrong. The two incidents were main moving *unasked*. What a picker would cost is the thing this entry values. The move is a deliberate act on the owner's word. A target reads as routine plumbing.

**That rejection is amended, and the sentence moves while the reasoning does not.** The owner ruled that `make merge` exists. It runs the shared merge tool from claude-settings (D140, merge claims the decision number). The rejection was aimed at automating the decision. The decision is untouched. Whether a PR gets merged stays the owner's word. A bare `make merge` refuses and says there is no default, and it will not get one. `ARGS=<n>` is a preview that presses nothing. Only `ARGS="<n> --confirm"` acts. This is D33's instrument one register down. The route that can spend money refuses without an explicit field. This one refuses without an explicit number and flag.

**What is automated is the state lookup, which is not a choice anybody makes.** Which of the two forms applies has one right answer, and git already knows it. The footgun paragraph above shows what a wrong guess costs: no error, no hook, and a branch somebody else is working on quietly advanced. A session was being asked to remember a lookup. Now it asks git instead. It re-asks with `git rev-parse --abbrev-ref HEAD` before it pulls.

**It widens nothing mechanically.** It fetches origin first. Then it asserts `merge-base --is-ancestor <commit> refs/remotes/origin/main`. That is allow rule 3, evaluated before anything moves, not discovered when the hook refuses. It never sets `BANCHI_MAIN`, and no refusal it prints suggests it. A commit origin does not carry is refused by name.

**`make help` lists it.** The plumbing worry is answered by shape, not by obscurity. Hiding the target would be security by not being listed, which this repo rejects everywhere else. `CLAUDE.md`'s rule is that a capability nobody can find is not done. The two raw commands stay in `CLAUDE.md` beside it, since the wrapper must not become the only way anyone knows the answer.

**The footgun has a test that was green for the wrong reason first.** The retired merge self-test built an origin, a clone and a linked worktree in a temp directory. Its first draft put the other tree on a branch already at the commit a wrong pull would have brought it to. So the assertion could not fail. Forcing the picker to always choose the pull form exposed it, because the test stayed green. The branch is one behind its upstream now. That mutation turns the test red, and the fixture asserts its own arming. This is the lesson `githooks-selftest` records about git's own refusals scoring as a hook's.

### The main checkout going stale

**The SessionStart hook reports the main working tree left on a feature branch after that branch merged.** The sections above govern how main moves. This is the tree that holds main drifting a different way.

**Measured at the time: 70 commits behind, on a branch merged in PR #43, serving the owner's real store.** Nothing was lost, since the branch was fully merged. What it cost was the live rig running behind four merged PRs. `make status` reported `0 ahead of main, 70 behind it`, and nobody read it.

**`scripts/worktree-guard.sh` carries the check, because it runs unasked.** D43 puts the ports there for the same reason, not in a target somebody has to remember.

**It reports and never switches.** `git switch` is the operator's to type. A hook that moved the branch under a running server would be deciding for them.

**Ahead is the number that decides, not behind.** Zero ahead with a clean tree means that the branch holds nothing main does not have. So switching can lose nothing. Anything else says so and points at `make status`. A worktree on a feature branch is correct, and it is never reported.

### The word

**A merge outside the batch runner's standing grant (below) needs the word, and the batch runner runs it. A lane session never merges.**

**The word comes from the owner in the conversation, and it applies to one instruction.** It is not a standing grant, a mode, or an inference. It has the same shape as D33's `confirm` field one register down. That route refuses without an explicit field, because the next step costs money. This refuses without an explicit instruction, because the next step is the branch every other session is cut from.

**The test is whether the owner NAMED THE ACT, not whether they matched a phrase.** A past paragraph said *"merge to main" is the word*. A session read that literally and hesitated over a bare **"Merge"**. The word is the verb itself, as a direct instruction. *Merge it* and *merge the PR* count too. Approval that never names the act does not count: *ship it*, *land it*, *looks good*, or an approving review. **The line is naming the operation versus expressing satisfaction with the work.** A phrase list is a worse instrument. A session that matches on phrases balks at a plain instruction. It can also be walked into a merge by anyone who says five particular words.

**The merge is one operation, performed whole. The batch runner does not stop between the halves to ask again.** The owner asked for this correction after a session merged on GitHub, reported that local main had not moved, and waited. That session read the entry correctly, which is what made it a defect here. The word covers both halves: `gh pr merge`, then the fast-forward. If the second half refuses or cannot run, the batch runner reports it as the incomplete operation it is. It does not re-ask as though permission were missing.

**What the word does not license:** a direct push, a force push, `git branch -f`, `git update-ref`, or a merge of a PR the owner did not name. A hook refuses all four. The word unlocks none of them.

**The local fast-forward is split, not refused whole.** The incident that list meant is `637e2e4`, a fast-forward to a commit on NOBODY's origin. The hook refuses that. What the word licenses is the fast-forward to the merged commit ON ORIGIN. That is a different move that shares a verb. The hook has always drawn that line, and the prose draws it too.

**Why this is safe to grant, and was not safe to assume.** The owner's consent was never missing. What was missing was any record that consent was required, and any mechanism that noticed its absence. Both now exist. So an explicit instruction is a decision, not a default.

### A standing grant to the batch runner

**"The word" above is still per-PR by default. This is the one exception, and it is scoped, not a repeal.** After being asked twice to name the act for PR #349, the owner gave the batch runner a standing grant to merge. That names the act once for a whole batch, instead of once per PR in it.

**The grant is to the one session the owner names as the repo's batch runner.** claude-settings decision session-tiers names the tiers. The batch runner owns the integration batch, the CI waits, the merge tool runs and archiving finished lanes. The coordinator starts lanes and talks with the owner. The batch runner batches every reviewed lane the owner set out, across all sessions, into one integration branch and merges it. A lane session hands the batch runner each reviewed lane branch with its head commit and review verdict. It never builds an integration branch, opens an integration PR, marks a PR ready or merges. The grant is exercised only through `make merge ARGS="<n> --confirm"`, only once CI is green, and never with `--admin`. The designation is never inherited. A later session re-asks, a new batch runner included.

### A standing grant to the weekly demo refresh

**One more exception, scoped to a path.** The owner ruled that the demo mirror refreshes weekly with auto-merge (D295, the public demo is the scrubbed real store). A PR merges through the merge tool once CI is green. No word is asked, and no batch runner is needed. Three conditions hold. Its head is `demo/mirror-refresh`. `scripts/demo-mirror-daily.py` opened it after the scrub assert and the fence. Its whole diff is under `demo-assets/mirror/`. `scripts/demo-mirror-daily.py` fences it: it refuses to merge when the diff touches any other path, and it never uses `--admin`. Any other PR keeps the rules above.

### The escape hatch and the evidence

**`BANCHI_MAIN=off`** is spelled the way `BANCHI_DOCS=off` already is. It is one variable, and the owner sets it from the owner's terminal. By the owner's word, no refusal prints a blocked switch's name to an agent. Each refusal prints "owner-only: ask the owner to run this command". `guard-shell.py` refuses an agent's tool call that sets it (D179). A guard with no way past it gets disarmed at the config instead. A disarmed `core.hooksPath` takes the three opsec rules with it. That is the trade D16 already refused for the docs audit. So the way past exists, and the owner holds it. `CLAUDE.md` names the switch for the owner.

**`make githooks-selftest` is the evidence. It runs in `make check`, never in the git hook.** D18's rule applies: it writes. It creates a bare repo, a clone, commits and pushes. It has a second reason of its own, which the docs audit's self-test does not have. It exercises the guard by **violating** it. A version on the commit path would refuse its own commits. Nineteen cases exist. Two of them were green for the wrong reason until the harness checked whose refusal it was. Git declines to delete the branch you are standing on, and declines to push what is already up to date. Both happen without consulting a hook. A refusal now has to carry the hook's own marker to count.

**What it does not cover:** one machine's clone. A push from anywhere else, a commit in a different clone, and the GitHub web editor are all outside it. Those are the exact gap branch protection would close.

**Amended.** The premise here was that the server-side guard was not for sale. That went false, twice over. Both are done, not hypothetical. Branch protection is on. The one check it is to require is `all-jobs-passed`, which rolls up every job, `revert-guard` included (claude-settings decision same-check-kinds). `check` is its alias; a follow-up deletes it after the owner flips protection to the rollup (same-check-kinds). The list protection holds changes only by that flip. And `gh api /repos/shivinate7/banchi` answers `"private": false`. The repository is public, on the owner's own separate decision. The subscription this entry's opening measurement paid to avoid is no longer the question. Server-side rulesets exist and are required now.

What this protected, main moving from inside this clone unreviewed, is caught remotely too. A required check on a PR is the server-side gate this entry once could not buy. **What the two local hooks still cover is the one thing a required check cannot see: a local ref move that never goes through `git push`.** `reference-transaction` catches a fast-forward, a rebase, or a `branch -f` of `refs/heads/main`, before any network call exists to gate. `pre-push` is now the redundant one. A direct push it refuses would also fail remotely. It stays, because a local guard costs nothing to keep. The local guard's ground is narrower now. It is not "the only gate there is". It is "the one gate a `git update-ref` never reaches."
