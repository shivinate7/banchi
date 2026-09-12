## D111 — Cleanup is a sweep, not a step in the merge, and liveness is read rather than guessed

**Built 2026-09-06, after the owner asked why the janitorial step never works.** The question
was put plainly — *"why is my janitorial cleanup part not better when i have these sessions
merge?"* — and the answer is that the merge is not the last event, and nothing ran after it.

**The measurement, on this clone the same day.** Seven worktrees, 73 local branches, four
supervisor processes whose working trees had been deleted out from under them. Cleaning it by
hand reclaimed 334M and took the branches to nine. The four processes held no port and served
nothing: each was failing to launch a `capture_server.py` in a tree that no longer existed and
recreating the `.serve/` directory it logged the failure into. The oldest had been doing that
since 2026-08-30; one of them pointed at a directory that was not on disk at all.

**37 of the 73 branches were in the IDENTICAL state — merged, deleted at origin, alive here.**
That is not 37 mistakes. `scripts/merge-pr.py:484` deletes the head branch at origin
unconditionally, then returns early for the local half whenever a worktree holds the branch:

```python
held = worktree_holding(root, branch)
if held:
    say("  {0}: kept — checked out in {1}.".format(branch, held))
    return
```

That is correct — git will not delete a checked-out branch — but the condition is
**true by construction** in the ordinary case: a session merges its own PR from its own
worktree. The origin half succeeded 37 times; the local half was refused 37 times for the same
structural reason, and nothing ever came back to ask again.

**THE SHAPE OF THE DEFECT.** Every layer's cleanup is conditional on a layer above it
already being gone, and nothing re-checks. The merge waits on the tree. The tree waits on the
session. The session ends with no teardown — `.claude/settings.json` wires `SessionStart`,
`PreToolUse`, `PostToolUse` and `Stop`, and `Stop` fires at TURN end, so it is a gate and not a
teardown. The supervisor waits on nobody, because D53 makes it outlive the session on purpose.
Every link is individually defensible, which is why this never looked like a bug.

**So the fix is a sweep and not another hook on the merge.** Only something re-runnable at an
arbitrary moment can collect what a one-shot structurally could not. `scripts/janitor.py` is
that, and the merge is left alone: it needs no new state, because a branch becomes reapable the
moment origin's copy is deleted, which the merge already does.

**IT IS NOT BANCHI'S PROBLEM.** Twelve Claude sessions were live on this machine at the time,
across two repositories. Of 50 worktree project histories, 43 trees were already gone and seven
remained — trees mostly DO get cleaned; branches and processes never do. The other repository
was leaking the same way: two dev servers on adjacent ports with the same working directory,
the second started because the first held the first port, and two processes from a session
25 days earlier still listening.

**LIVENESS IS READ, NEVER GUESSED, AND THAT IS THE LOAD-BEARING PART.** File mtimes and
`git status` cannot separate a live worktree from an abandoned one. On the day this was built
two trees showed zero dirty files and no recent writes, then switched branches while they were
being measured. The console app already keeps the answer: one JSON record per session, named
for its pid, in a `sessions` directory under the user's own `~/.claude`. It carries a `cwd` and
a `pid`, and checking that pid alive, against the record's `startedAt`, classified
every one of that day's trees correctly, including the two the mtimes got wrong.

**THE COMPARISON IS ON THE EPOCH, AND THE FAILURE DIRECTION IS THE SAFETY PROPERTY.** The
record also carries a `procStart` string, and comparing that to `ps -o lstart=` looks right and
is wrong: the record renders UTC and `ps` renders local, so on this machine every pair differed
by exactly five hours with identical seconds. The first build did exactly that, judged every
session dead, and offered to reap two trees with sessions in them — including, had it been
clean, the tree the sweep was running in. `startedAt` is epoch milliseconds and carries no
timezone to get wrong. And every unreadable case now resolves to LIVE: a false "live" keeps a
tree somebody runs the sweep over again tomorrow, a false "dead" deletes work.

**TWO TIERS, AND THE LINE BETWEEN THEM IS WHETHER THE THING CAN POSSIBLY BE LIVE.** Tier 1 is
reaped without asking — a process whose own script has been deleted, a registration
`git worktree prune` disowns, a husk directory holding nothing but caches with nothing running
under it. Tier 2 previews and waits for a word — a merged branch no tree holds, a worktree with
no session in it. **The doubtful case is never a flag away from a delete** — it is sorted
into a different list, and only one list has a removal path. That asymmetry is **D44's**, taken
deliberately rather than reinvented, and D18 keeps this off the gate for D44's reason too: with
`icloud-sweep` it is one of the two targets here that can delete a file.

**WHAT IT NEVER TOUCHES**, and these are refusals rather than defaults: the default branch; any
branch that is unmerged AND on no remote — that day it was `backup/logo-lockup-prerebase`, 47
commits that existed on no other disk; a tree with a live session, including its own; a tree
with uncommitted work; and the main checkout's server, which **D53 means to outlive every session**
and which was serving the owner's real inventory throughout.

**Identity is an absolute path — never a pid, never a port.** Pids churn: D53's re-exec
replaced this repo's two server pids inside twenty minutes while this was being written, and
`started_at` in a pidfile is rewritten by that re-exec, so it is not process age. The port
cannot be inverted, being `sha256(path)[:4] % 300` over 300 colliding slots. And every path
that enters from outside is resolved first: `/tmp` is `/private/tmp` on this machine, so
`git worktree list` and a session record spell the same directory differently — which made the
self-test's every tree read as sessionless until it was fixed.

**A defect this found on the way, in code it wanted to reuse.** `scripts/serve.py:297` picked
its identity needle as `argv[-1]`, right for the supervisor and the capture server, whose last
argument IS the path, and degenerate for Vite, whose argv is
`["npm", "--prefix", "/abs/app", "run", "dev"]` — so the needle was `"dev"`, a substring of
essentially any `npm run dev` on the machine, in any tree. `_sweep_orphans` signals a process
group on the strength of that answer. It is the last absolute path now, which keeps the two
that were already right. Found by reading rather than by an incident; there was live material
for it at the time.

**What retires this:** a console app that tears down what a session started, or a merge that can
finish its own local half. Neither is available, and the second one cannot be — the branch is
checked out at the moment the merge runs, which is the whole reason the sweep exists.
