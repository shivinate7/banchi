## D139 — Which branch the primary checkout stands on is a fact about the live rig, and a warning is the ceiling

**Settled 2026-09-11, on the owner's instruction**, after `/Users/shivinate/Developer/pkmnscan`
— the primary worktree — was found standing on `claude/env-key-rotation` with three live
sessions in it. Nothing in the tree said so: `make status` printed every section it always
prints, the SessionStart worktree guard printed the ports, and neither mentioned the branch
anywhere near the server it qualifies.

**This is D43's hazard reached through the other door.** D43 was the PORT pointing at the wrong
store, and it was fixed by making the port follow the store. This is the DIRECTORY pointing at
the wrong code, and it cannot be fixed the same way, because the directory is not derived from
anything — somebody types `git switch`.

What makes it a hazard rather than untidiness is D53. `make launch-agent` keeps a supervisor
alive at login out of that **one** directory, over the owner's real `inventory/store.sqlite`,
and the supervisor rebuilds from whatever the directory holds.
**D138 widened this on the day this was written**: the capture server now serves the built app
as well, and the supervisor is
what builds it, so the directory decides the front end a person is looking at and not only the
Python answering it. So the branch that directory
stands on silently decides which code photographs the owner's real cards into their real store.
The repo guards `refs/heads/main` with two hooks and a remote protection rule (D42) and guarded
this not at all.

> **THE CEILING BELOW WAS REOPENED BY THE OWNER ON 2026-09-12.**
> It is no longer this repo's position. The same thing happened a second time —
> `claude/debts-citation-repair`, a
> branch already merged as pull request #282, four live sessions in the tree. The three readers
> in this entry stand and are untouched; what is superseded is "a warning is the ceiling".
> `## D158` is the replacement: the refusal goes where the damage
> is, which is the SERVER and not the checkout, so the supervisor will not adopt a primary
> checkout's code while it is off main.
> **The section below is right that nothing in git can refuse the switch, and it remains true**
> — including `reference-transaction`, which that
> entry measures as firing on no branch switch at all.

### A warning is the ceiling, and that is git's limit rather than a choice

**There is no `pre-checkout` hook.** Git's checkout hooks are `post-checkout`: it is called
after the switch has happened, with the new HEAD already in place and the working tree already
rewritten. Nothing available here can refuse the move, and an entry that promised otherwise
would be promising a hook git does not have.

So what is achievable is a loud, specific warning, and the design question becomes *when*. It
is deliberately **not** made enforceable by some other means — a wrapper script around `git
switch`, a `reference-transaction` arm on `HEAD`, a hook that switches the branch back. The
first is a guard nobody types; the second refuses moves that are legitimate in every linked
worktree of the clone, which is D43's whole point; the third decides for the operator and is
the thing `scripts/worktree-guard.sh` already refuses to do in as many words:
**it reports and never switches.** A session working in that directory is a normal, expected
state. What was missing was that it was invisible.

### Three readers of one fact, because any one of them is missable

1. **`scripts/githooks/post-checkout`** — at the moment of the switch, which is the one moment
   the person responsible is present and reading output. It already fired only on a branch move
   (`$3 = 1`) for the `make hooks` staleness reminder; the branch check is a second block in the
   same file, and the staleness block is untouched. Seen by a person who types `git switch`, and
   by nothing else: a session that arrives later never sees it, and `git pull` does not fire it.
2. **`scripts/status.py`, under SERVING** — beside `capture :8000 answering`, which is the line
   a reader believes and is the same line whether the process was built from main or from a
   branch nobody is reading any more. `repo()` has always named the branch and that is a
   different claim: it says where *you* are, in a section about the tree, which is exactly how a
   reader reads past it. Seen by whoever runs `make status`, which is the thing nobody ran on
   2026-08-30 when it was already reporting `0 ahead of main, 70 behind it`.
3. **`scripts/worktree-guard.sh`, at SessionStart** — to a session that arrives after the fact
   and would otherwise never ask. Seen unasked, before any work.

**The third one already existed** and landed in commit `096de75` on 2026-08-30, written for the
narrower case of the main checkout parked on a *merged* branch. It is not reimplemented here.
What it was missing was the reason: the live server went unmentioned in the arm a working
session actually lands in — a tree somebody is working in has uncommitted files by definition,
so it took the `else` branch, which said only *"Do not switch blind"*. That reads as a tidiness
notice. One line naming D53 was added above both arms, and its header comment was widened to
say what its code always did: any branch that is not main, merged or not.

**Why three and not one.** Each covers a different person at a different moment and none
subsumes another: the switcher, the reader, the arriver. The 2026-08-30 incident is the proof
that one reader is not enough — `make status` had the answer and the tree sat wrong for a day
because nobody ran it. A fourth would be the `#/` screen, and it is refused on the ground that
which branch a directory stands on is not a fact about the store and has no place on a screen
the owner uses to sell cards.

### What is built

1. **`scripts/githooks/post-checkout`'s second block.** On a branch move, in the primary
   checkout, to anything that is not main: what happened, one sentence on why it matters, and
   the exact undo (`git switch -`, with `git switch main` named beside it). A detached HEAD is
   reported as one rather than as a branch called `HEAD`. Gated on `main` existing as a local
   branch, so the hook stays quiet in a foreign repository — the same gate the SessionStart
   guard already used.
2. **`scripts/status.py:serving_branch()`**, leading the SERVING section so it qualifies the
   rest of it, plus `sidecar()` — one loader where `serving()` and `ports_and_store()` each had
   their own copy of the same eight lines. That dedupe is the point and not a tidy-up: the new
   line needs `server/ports.py:is_linked_worktree`, and a third copy of the dance would have
   been a third place for the primary/linked test to be spelled differently.
3. **`scripts/worktree-guard.sh`** — the D53 sentence in both arms, and a widened header.
4. **Six cases in `scripts/githooks-selftest.sh`**, and a pair of assertions beside `expect`.

**The primary/linked test has exactly one spelling**, and it is
`server/ports.py:is_linked_worktree`'s: a linked worktree's `.git` is a FILE, a primary
checkout's is a DIRECTORY. `app/devPort.ts`, `scripts/worktree-guard.sh` and
`scripts/docs-audit.py` all detect on that same one fact. `git rev-parse --git-dir` against
`--git-common-dir` decides it too and is the same fact with a subprocess in front of it; it is
not used, because two answers to one question is the defect this repo keeps declining to add.
**A linked worktree says nothing at all** — it has its own store and its own ports to be wrong
on its own, which is what D43 bought, and warning there would teach the line to be ignored where
it matters.

### What it is tested by, and what that cannot prove

`make githooks-selftest` gained six cases in the throwaway repository it already builds: a
branch switch in a primary checkout warns, a detached HEAD warns, switching back to main is
silent, and both creating a linked worktree and switching branches *inside* one are silent.
**`main` is a real local branch in the worktree cases**, so their silence can only come from the
primary/linked test rather than from the gate beside it — otherwise they would pass for a second
reason and prove nothing.

They assert OUTPUT and not exit status, which is why they are not `expect` cases: the hook exits
0 whichever way it decides, so `expect allow` would pass on a hook that printed nothing at all.
That is the whole failure mode, so the warning leads with a marker (`PRIMARY CHECKOUT:`) for the
same reason the refusing hooks print `REFUSED:`.

**Mutation-tested 2026-09-11, eight arms**, by copying the hooks to a scratch directory and
re-running with `PKMNSCAN_HOOKS_DIR` pointed at the copy. Six are caught: inverting the
primary/linked test (`-d "$top/.git"` → `-f`) fails 4, deleting the `!= "main"` arm fails 2,
deleting the block fails 2, dropping the detached-HEAD naming fails 1, dropping the `main`-exists
gate fails 1, and deleting the **pre-existing** `make hooks` staleness reminder fails 1.

**Two arms survive, and both survive for a reason that is recorded rather than chased.** Removing
`[ -n "$top" ]` changes no behavior — it is a defensive guard whose absence merely tests
`[ -d "/.git" ]`. Removing the `$3 = 1` branch-move gate changes none either, because git passes
the same sha as `$1` and `$2` for a file-level checkout and the `$old != $new` guard beside it
covers the same ground: **the two are redundant, which the sweep is how anyone found out.**
Mutating the pair together fails the file-level-checkout case, so that case is load-bearing for
the pair and for neither alone.
**Three cases in this section were green for the wrong reason before the sweep ran**: two
linked-worktree switches created a branch at the commit already
checked out, so `$1 = $2` and the hook's own no-op guard dropped them before the block under test,
and the detached-HEAD case asserted the warning fired without asserting it named a detached HEAD.
A guard must see its subject, and a mutation arm is the only thing that says whether it did.

**Nothing here blocks a commit.** D18: these are two warnings and a status line, and the
self-test writes, so it stays in `make check` beside the others and out of the git hook.

**It answers "is this main" and not "is this current", and those came apart on the day written.**
`main` is the local ref, and a clone that moves main only by pull request can leave it
well behind origin: measured 2026-09-11 in this checkout, local main at `c34ccdc` against
`origin/main` at `2caa001`, six commits. So returning that directory to current code is two
steps — switch, then advance — and the second is behind the owner's word (D42). The hook names
`git switch main` as the undo of the switch and says in the next line that local main can itself
be behind; `make status` and the SessionStart guard print the ahead/behind counts that answer the
second question.
**A reader who read it as a currency check would be wrong exactly when a tree is stale**, which
is why it is stated rather than left to be inferred.

**What it cannot prove, and the gap is real.** A warning is only as good as the output somebody
reads. `git pull`, `git merge` and `git rebase` do not fire `post-checkout`, so a tree that
drifts without a checkout is caught only by the other two readers; and a session that pipes git
to a log, or an agent that does not read stderr, sees nothing at the moment of the switch. The
warning also cannot distinguish a deliberate ten-minute switch from a tree abandoned on a branch
for a day — `make status` prints the ahead/behind counts that answer that, and no automatic
reader decides it.


---
