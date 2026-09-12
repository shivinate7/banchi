## D176 — The primary checkout syncs itself, both parts, because the thing D42 was protecting is not the thing this moves

**Settled 2026-09-12, on the owner's answer to a refuse-only proposal.** Asked whether the
primary checkout — `/Users/shivinate/Developer/pkmnscan`, the one directory D53 keeps a capture
server alive out of at login over their real store — is mechanically kept on `main` at
`origin/main`, and offered a guard that would only refuse, they said:

> *"why can't both parts sync, remember this is a one man show, it's just me working."*

So it syncs. `git switch main`, then `git merge --ff-only origin/main`, run for them, at the
three moments something in this repository already knows main may have moved.

### The two parts are two defects and each has been observed alone

**Part 1 — the tree stands on `main`.** D139's incident: that directory on
`claude/env-key-rotation`, three live sessions in it. D158's: `claude/debts-citation-repair`,
merged as #282 and already behind `origin/main`, with four.

**Part 2 — `refs/heads/main` is at `refs/remotes/origin/main`.** `make status` reported
`0 ahead of main, 70 behind it` for a day in August and nobody read it.

**Neither subsumes the other, and one hook can see only one of them.** `post-checkout` fires on a
branch switch and **not** on `git pull`, `git merge` or `git rebase` — so it can see the tree go
*off* main and can never see main go *stale*. That is why "on main" and "at origin/main" are
genuinely separate questions here, and why the readers that matter are the ones that run when
main **moves**: `scripts/serve.py`'s four adoption moments, which tick once a second.

### D42 does not forbid this, and the reason is its own allow rule 3

D42 is *"main moves by pull request"*, enforced by `scripts/githooks/reference-transaction` and
`scripts/githooks/pre-push`. **The sentence is not repealed and the hooks are not touched.** What
this entry claims is narrower: the move made here is one that hook has permitted since the day it
was written. Its header, verbatim:

```
#   3. Moving main to a commit ORIGIN ALREADY HAS. This is the whole legitimate path: a PR is
#      merged on GitHub, `git pull` fast-forwards, and the commit was on the remote before it
#      was ever on your main. It cannot be forged by a local session, because a local commit
#      is not on origin until something pushes it — and pushing to main is what the pre-push
#      hook beside this one refuses.
```

and the code that is that rule:

```
  # The one legitimate move: to a commit origin already has. If we cannot ask, we do not
  # guess — a git that cannot answer is not evidence the move is safe, and the escape hatch
  # is one environment variable away.
  if git merge-base --is-ancestor "$new" refs/remotes/origin/main 2>/dev/null; then
    continue
  fi
```

A fast-forward to `origin/main` satisfies that predicate by construction.
**So this decides who runs an already-permitted move, and not which moves run.**
Which is the same sentence D42's own amendment uses about `make merge`: *"It arms nothing."*

**Checked rather than cited.** `scripts/sync-selftest.py` installs that exact hook file in a
throwaway clone via `core.hooksPath`, `PKMNSCAN_MAIN` deliberately unset, and asserts both
directions: the sync's fast-forward goes through, **and** a `git branch -f main <a local commit>`
there is still refused. An arm proving only the first would pass against a hook permitting
everything.

### Which part of D42's argument does not reach this case

**D42's caution was written against a specific hazard, which that entry records at length:** main
moving under three live worktrees on 2026-08-29, twice in one day. The harm was that every session
cut from main was silently on a different history from the one their tree reported.

**That hazard is not this one, on two counts.** This moves main only in the **primary** checkout,
and only to a commit `origin` already carries — so no worktree's history is invented and no
session's base changes behind it; a linked worktree's `refs/heads/<branch>` is not touched at all.
And there is **one developer**, which is the owner's own framing: the coordination problem that
caution is about does not exist on this machine.

**What D42 was protecting, and what still protects it.** It protected main from carrying a commit
that had not been through a pull request. Every guard that does that is untouched: `pre-push`
refuses a push to main, GitHub has required a PR since 2026-09-06 with `enforce_admins` true, and
`reference-transaction` still refuses a local move to a commit origin lacks — including one this
module would make, because **it deliberately does not pass `PKMNSCAN_MAIN=off` to git.** If the
hook ever refuses this file's move, that is a finding and not a thing to route around.

**This is CLAUDE.md's own rule applied to a settled decision's scope rather than its conclusion:**
a settled decision is an argument, not an authority. D158's ceiling is named as reopened below, in
the words D158 used to reopen D139's.

### The fast-forward-only test is this module's own, and rule 3 is not enough

**Rule 3 asks whether the DESTINATION is on `origin/main`, and here the destination IS it.**
So rule 3 is trivially satisfied, and would permit a move that discarded local commits.
A primary checkout whose main is *ahead* of origin — a commit made there directly, which
`PKMNSCAN_MAIN=off` makes possible — would be silently rewound by anything that merely trusted
the hook.

So there is a second predicate, and it is why this module can be trusted with a ref D42 protects:
**`refs/heads/main` must be an ancestor of `refs/remotes/origin/main`.** True exactly when the move
is a fast-forward; false when main is ahead and false when it has diverged, and both refuse.
**Never a merge, never a reset, never `--force`.** Both shapes get their own arm — different
repository states reached different ways, and one predicate covering both is worth proving twice.

### What is built: one module, three callers, and the refusal kept as the fallback

`scripts/primary_sync.py`. Stdlib plus `server.ports`, the budget `scripts/serve.py`'s header sets
for anything the supervisor imports — and it is in `SELF_FILES`, because a supervisor that had
re-read `serve.py` but not the module it decides with would be running half of one version.

- **`scripts/serve.py`'s four adoption moments** — spawn, reload, re-exec, build. D158 made these
  refuse; they **sync first and refuse only if the sync declines**. The refusal is not weakened:
  every D158 arm is still green, because that fixture has no `origin` to sync to and the module
  answers `not-subject` for a clone with none.
  **`_restart_for`'s order is undisturbed, which was the thing to get right**: `off_main` is still
  asked by the image already running, which is main's, so a branch still cannot ship the code
  that disables the guard against it. One attempt per distinct branch, memoised — this loop ticks
  once a second, and a sync retried every tick would run `git switch` at somebody's tree sixty
  times a minute.
- **`scripts/worktree-guard.sh`**, the SessionStart hook, which said a hook moving the branch
  would be *"deciding for the operator, and `git switch` is theirs to type"*.
  **That is the ceiling the owner reopened**, and it is gone. The ahead/behind/dirty report under
  it is **kept and not redundant**: the sync refuses rather than discards, and in a refusal those
  counts are exactly what a session needs.
- **`scripts/merge-pr.py`'s local half**, which closes a hole rather than adding a convenience.
  `local_plan`'s first branch — main checked out in no worktree, the ordinary state of a clone
  with ~30 worktrees on branches — moves `refs/heads/main` with a refspec while standing in no
  tree. So the merge completed, main was current, and the primary checkout was still parked.
  **That is D158's exact state, reached by the command whose job is to leave everything tidy.**
  It is its own half, and **it never changes the merge's exit status** — a rig that would not sync
  because somebody has uncommitted work in it is a message, not a failed merge.

### What it must never do, each one a refusal with a self-test arm

- **A linked worktree is never the subject.** The test is `server/ports.py:is_linked_worktree`,
  **called and not respelled** — D139's rule, which D158 restates, and for its reason: that
  question has exactly one answer in this repo, and a fourth spelling is a fourth place to write
  it backwards. Asserted from *inside* a worktree, which is where `make merge` and a SessionStart
  hook both reach this.
- **Uncommitted tracked work is NAMED, never discarded.** **Untracked files do not block a sync**,
  and that is a measurement: the primary checkout carries an untracked `.preview-check.html`, and
  a guard that read it as work would refuse every sync forever while being right about the bytes.
  A staged addition *does* block, because the rule is "is there work here that is not a commit"
  and not "would this be lost", which is a reimplementation of git.
- **A half-finished operation waits** — merge, cherry-pick, revert, bisect, rebase, `am`. Read as
  paths in the git dir, because `--porcelain` v1 says nothing about a rebase and the long form's
  wording is prose that has moved between gits. Two arms, because
  **one marker is a file and one is a directory** — a guard watching only `MERGE_HEAD` misses half.
- **Main held by another worktree refuses and names that tree**, which git's own refusal does only
  at the end of a sync that has already announced itself.
- **A detached HEAD no ref contains refuses.** Switching away from a *named* branch loses nothing
  — the ref survives and one command returns — but a commit reachable from nothing but HEAD
  survives only in the reflog. **This is where the one real bug in the first draft was**, and it
  is worth recording because it failed *open* on the only state here that can lose work: measured
  on git 2.39.3, `git branch --all --contains <that commit>`, asked from a detached HEAD, prints
  `* (HEAD detached from 9e698bd)` — a pseudo-entry for HEAD itself, which is precisely the thing
  whose absence is being tested. So the guard read "some ref holds it" for every orphan there can
  be. `git for-each-ref --contains` lists refs and nothing else.
- **It is never silent.** Every sync is one line naming both parts, with `git -C <tree> switch
  <branch>` on it — nothing was lost and one command returns. Every refusal prints its reason and
  the file or tree holding it back.

### It fails OPEN on its own bugs and CLOSED on a target it cannot read

`scripts/reap.py:hook`'s rule and its reason: *"a guard that blocks every shell command when
`lsof` is missing or its own parser throws is a guard somebody switches off inside a day."*

**Open:** any unexpected exception answers `not-subject`, silently. Three callers run this unasked,
and a bug in it must cost a sync that did not happen — never a session that will not start or a rig
that will not come up. It exits 0 for a refusal for the same reason.

**Closed:** a fact it needs and cannot read — the worktree list, `git status`, HEAD, whether any
ref contains a commit — refuses, **loudly**. Not knowing whether a tree is safe to move is not
evidence that it is.

**Both end in "nothing was moved"; what differs is whether anybody is told.** This file's own
defect is not the operator's business, and its inability to read their tree very much is.

### The hatch stops the mechanism rather than letting something past

`PKMNSCAN_SYNC=off`, printed on every sync **and** every refusal, spelled the way
`PKMNSCAN_MAIN=off`, `PKMNSCAN_KILL=off`, `PKMNSCAN_REVERT=off`, `PKMNSCAN_SUITE_LOCK=off` and
`PKMNSCAN_SERVE_MAIN=off` are.

**It is the first hatch here that turns an act off rather than permitting one.** Every other stands
between a person and something they meant to do; this one acts on their behalf. So what a reader
wants from it is not *do it anyway* but *stop doing it* — which is why it is on the refusals too:
a refusal is the mechanism announcing itself, and the next question is how to stop being asked.

### Proved by violating it, and mutation-tested

`scripts/sync-selftest.py`, `make sync-selftest`, in `make check` and `ci-check` and
**never in the git hook** — D18: it writes, and what it writes are branch switches and ref moves.
Throwaway clones with real bare origins and real linked worktrees, and
**no mock of git and no patched `primary_checkout`**, except in the two arms whose whole subject
is the module's own failure.

**It may never be pointed at this clone** — stronger here than for the self-tests around it,
because the subject of a sync is the *primary* tree, which on this machine is the live rig.

`scripts/serve-selftest.py` gains the end-to-end shape only it can show: a real supervisor, in a
real parked checkout with an origin, coming **up** on main at `origin/main` with nothing typed,
and still refusing when that tree has an uncommitted tracked edit.

**Twenty-one mutations. Eighteen caught and three surviving; then 21 of 21, none surviving.** Each
arm deletes or inverts one guard: the linked-worktree test, the untracked filter, every refusal,
the ancestry predicate, `--ff-only`, the orphan reader, both fail-closed directions, the fail-open
arm, the hatch, `confirm`, and each part alone.

**The three survivors are the whole reason to run one**, and two were the same shape — a guard
standing behind another guard, with nothing able to reach it.

- **The linked-worktree test could not decide anything**, because `subject` comes from
  `primary_checkout`, which returns the primary tree.
  **D158's own sweep deleted a line in exactly that position** — a line that cannot change a
  verdict is a sentence about a guard rather than one.
  **This one is kept**: it guards the prohibition the ruling is most absolute about, and
  `primary_checkout`'s obvious refactor — deriving the path from `--git-common-dir` — does not
  generalise to a `--separate-git-dir` checkout, so this test is what still holds if that changes.
  Given a subject by taking away what stands in front of it: `primary_checkout` is neutered to
  hand back a linked worktree, and the sync must still refuse to act on it.
- **`--ff-only` was redundant with the ancestry predicate**, which refuses a diverged main before
  the merge is reached. Same remedy: `_is_ancestor` is neutered, the diverged main reaches the
  merge, and `--ff-only` is all that stands between a background process and a merge commit
  authored in the rig.
- **The `main`-is-a-local-branch gate was masked by the gate beside it** — the lonely and foreign
  fixtures have no `origin/main` either, so they return one gate earlier.
  **The state that reaches it is CI's**: primary checkout, detached HEAD, `origin/main` present,
  no local `main` — and with the gate deleted it prints a `not-a-fast-forward` refusal on every
  session start of every pull request. That arm exists now.

**All three are the finding D158 recorded about its own sweep, arriving again**: a gate no other
arm can reach is a gate nothing is watching.

**A third half broke a neighbour's fixture, and how it broke it is the finding.**
`scripts/merge-selftest.sh` parks its primary checkout on `feature` for nearly every arm, so the
new rig half SUCCEEDED in the first local-half arm, switched that tree onto main — and the footgun
arm two sections later then found main checked out in a worktree, correctly picked the pull form,
and failed an assertion about the refspec form that had nothing wrong with it.
**Four arms red for one state change three sections earlier** — the hardest kind of fixture
failure to read, and it
was invisible in the exit code: `make check > log; echo $?` reports the redirect's status, so the
suite looked green. The arms that assert the LOCAL half now pin `PKMNSCAN_SYNC=off` and keep
meaning what they meant; the rig half has a section of its own, including that a dirty rig is
refused by name **while main still advances** — the merge is not failed by it.

**And one finding from the fixture is worth more than the arms it fixed.** `build_clone` did not
build the state it was asked for: `seedwork` is the repository the bare origin was cloned *from*,
so it has no `origin` remote, `git push -q origin main` failed silently, and every fixture's
`refs/heads/main` was already *at* `refs/remotes/origin/main`. Four arms were green on that,
including "main is fast-forwarded to origin/main" — true before the call.
**A fixture that quietly fails to build the state under test is unreportable by design**, so
`build_clone` now asserts the gap it created. Already in this repo as *"a guard must see its
subject"*.

### What it cannot see, named rather than left to be found

**A primary checkout whose `origin/main` is stale.** The sync does **not** fetch by default: two
of its three callers are a SessionStart hook and a once-a-second supervisor tick, where a hanging
network call is the whole cost. Neither needs one — `make merge` fetches before it moves anything,
so the `origin/main` this clone holds is current when it matters, and `--fetch` is there for a
person who wants to ask first.
**So a rig left untouched is synced to the last `origin/main` anybody fetched, not the true one.**

**A branch cut before this exists, on the login path.** D158 names the same hole for the same
reason and it is unchanged: that branch's `serve.py` carries no sync, launchd runs it, and it
serves. It shrinks on its own as branches are cut and merged.

**It does not decide that the tree should be put back.** It decides that the tree the rig is
served out of is put back **when that can be done losing nothing**, which is a narrower claim, and
every case where it cannot is a refusal above with an arm under it.
