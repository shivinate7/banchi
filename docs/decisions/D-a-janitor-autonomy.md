## D-a-janitor-autonomy — The lossless half of the cleanup needs no word, and the schedule is the backstop for the events that miss

**MEASURED ON THIS CLONE, 2026-09-20.** `make janitor` reported 14 items waiting on a word. Five
worktrees with no session and nothing uncommitted. Nine branches whose every commit main
already carries. Some had been waiting for days.

Nothing was going to press it. `make janitor` runs from no hook, no target and no schedule.
`scripts/janitor.py`'s own docstring already said so: the only SessionStart hook is
`worktree-guard.sh`, and nothing anywhere runs `make status` or `make janitor` by itself.

**THE OWNER'S WORD, 2026-09-20: "Both halves."** Four options were put: both halves, the hook
alone, an opt-in switch, or dropping it. The owner named both halves. So the session-end hook
cuts merged branches, and the daily agent runs the full sweep.

**THE PERMISSION IS RECORDED BECAUSE THIS MOVES A GATE.** Deletion that needed a human word
now happens with nobody watching. A guard refused the change four times for that reason and
was right each time. The first word given was a blanket one. This entry then claimed it as
approval of the widest of four options, before anybody had picked one. That was the same
defect D228 records, one lane over. The word above is the narrow one, asked for and given.

### Tier 2 is three acts, and only two of them are a judgement

The word tier 2 waits on was applied to all three at once. They are not alike.

- **Removing a worktree** can cost uncommitted work the sweep failed to see.
- **Stopping a loose process** can cost a run somebody wanted.
- **Cutting a branch** costs nothing. `reapable_branches` puts a branch in its `cut` list only
  when main is a descendant of every commit on it. `git branch -D` there removes a label. Every
  object that label named stays reachable from main.

So the third act is split out as `janitor.py --branches`, and it runs unattended. Holding a
lossless act behind the same word as a lossy one is what left nine merged branches here with
nobody to press it.

**It is branches and nothing else.** It removes no tree and stops no process, whatever it
decides about a branch. The self-test asserts that against an idle worktree the full sweep
would have taken. The only branch this mode cuts has no tree by construction, so without that
subject the claim would pass over an empty set.

**It fails closed on a layout it cannot read.** `held` comes from `git worktree list`. With no
trees, no branch is protected and every one becomes eligible, including one somebody is
standing on. That state is refused rather than swept.

**A held branch is never considered, which is stronger than surviving.** Git refuses to delete
a branch checked out in a linked worktree on its own. So survival alone is not evidence the
protection ran. Measured: dropping the `held` set entirely left every arm green, because git's
own refusal masked it. What only the real protection produces is silence about that branch,
and that is what the self-test now reads.

### The hook runs it, because that is the moment a branch becomes cuttable

`scripts/session-teardown.sh` already runs on `SessionEnd` and `WorktreeRemove`. It gains the
branch cut, after the teardown and tier 1 it already runs.

A tree going is exactly what releases its branch from `held`. So the event that makes a branch
cuttable is now the event that cuts it. The mode is idempotent. That is what lets a hook run it
on every session end with no thought about how many times it has already run.

### The schedule is the backstop, because both events are known to miss

`.claude/settings.json` already calls `SessionEnd` unreliable at app quit and machine sleep.
`WorktreeRemove` fires only when somebody removes a tree, and a tree abandoned by a session
that died is removed by nobody. No event ever fires for it. That is what the five orphaned
trees measured above were.

`make janitor-agent` installs a launch agent that runs the full sweep daily, unattended. Every
act it presses is one a hook would have pressed at the right moment had the hook fired. A
sweep that runs whether or not an event arrived is D111's re-runnability applied to the
trigger rather than to the sweep.

**Generated, never tracked, and main checkout only.** A plist names an absolute path on one
Mac, which is D47's failure verbatim. A plist naming a worktree outlives the worktree. Launchd
then retries a directory that is gone, forever, with nothing on screen to say so. `serve.py`'s
own launch agent refuses a linked worktree for that reason, and this one refuses for the same
reason in the same words.

**A calendar interval, never `KeepAlive`.** This is a sweep that ends, not a service that stays
up. Launchd runs a missed calendar job at the next wake. A Mac asleep at that hour gets its
sweep on waking rather than skipping the day.

### The log is the receipt, and it is what makes an unattended deletion acceptable

Every other destructive target here is read by a person while it runs. This one is not. So it
writes what it did to `.serve/janitor.log`, and what it writes is the same account `make
janitor` prints. A deletion nobody watched and nobody can read afterwards is the thing this
repo does not do.

### What no amount of this will ever touch

About twenty branches carry commits that exist only on this disk. The sweep keeps every one,
correctly, because it holds the only copy of that work. No autonomy changes that. Deciding
their fate is separate work and is not taken here.

### It is on no hook that gates and in no check

D18 at its strongest, and the same standing `icloud-sweep` has. This and that are the only
targets here that can delete a file. `make janitor-agent` also writes to `~/Library`. Neither
may run where a commit is decided. The SELF-TEST gates, and writes nothing outside a temp
directory.
