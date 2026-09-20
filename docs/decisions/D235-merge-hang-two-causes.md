## D235 — The heartbeat is refused a pipe, and the wait learns the other half of its own question

`make merge` looked like it hung. It did that twice on 2026-09-20, and to more than one
session. It was not stuck. Two separate causes produced one appearance.

### The waiting itself is correct, and nothing here shortens it

`check.yml` takes four to five minutes. That is measured across 12 consecutive runs on
2026-09-20. `make merge` pushes a claim commit (D140, the number is claimed at the merge). It
then waits for that commit's own checks (D148, an answer it has not got is never a pass). Five
to ten minutes of waiting is the job working.

`CHECK_DEADLINE_SECONDS = 45 * 60`, `CHECK_HEARTBEAT_SECONDS = 60` and
`CHECK_POLL_SECONDS = 10` are unchanged. A red run still refuses unconditionally. Absence is
still never read as a pass.

### Cause 1 — the heartbeat never reached the screen

The loop calls `say(...)` every 60 seconds. It names what it is waiting on. Sessions
habitually type `make merge ARGS="<n> --confirm" 2>&1 | tail -18`.

`scripts/guard-shell-selftest.sh` performs that shape in the fixture, over a real narrator and
a real `tail`. Two measurements:

- **Mid-run the pipe had delivered 0 bytes.** Python block-buffers a stdout that is a pipe.
  Nothing appears until the command exits. That defeats the whole purpose of a heartbeat.
- **`tail -2` kept 2 of the 5 lines.** The same command prints all five when nothing follows
  it.

So correct, narrated waiting is indistinguishable from a hang. The parent rule "never discard
a command's output" covers this in spirit. It stopped nobody. A pipe into `tail` does not read
as discarding. That is the same reason every clause in `scripts/guard-shell.py` exists (D179,
a rule is read once and then competes with the work).

**Clause 9 is `PKMNSCAN_NARRATE`.** It refuses a long, heartbeat-emitting command whose stdout
is lost. Lost means discarded to `/dev/null` or to a closed descriptor. It also means
redirected into a file nothing in the same command reads back. It also means piped into `tail`
or `head`.

**The line is loss, never delay.** That is the decision. `| tee <file>` buffers the heartbeat
too. So does `> <file>` followed by a read of that same file. Neither delivers the narration
while the waiting happens. Neither loses a byte of it. Both pass. Refusing the careful
spelling of "keep the output" is how a guard teaches a session to reach for its hatch. This
line differs from `silent-write-guard.py`'s. That guard asks whether evidence survives. This
one asks whether a stream arrives. The two agree on the file case for different reasons.

**This clause names its subjects instead of resolving them, alone among the nine.** Every
other clause resolves what a command would do. `git status --porcelain` decides whether an
operand is a modified path. `os.path.lexists` decides whether a link destination is there.
"Does this command block for minutes while printing a heartbeat" has no such reader. Neither
the filesystem nor `git` nor the process table can answer it before the command runs.

The alternative was considered and rejected. A general clause over every pipe into a
truncating filter would fire on `git log | tail` and `make check | tail -40` and a dozen
honest lines a day. The house rule is explicit. A guard that goes red when nothing is wrong is
spent, because the reader learns to scroll past it. So this follows
`silent-write-guard.py`'s precedent. The roster is short. One entry per incident. A new entry
when something new goes wrong through one.

**Two things keep the named roster honest.** First, it resolves the one thing it can. A
preview never waits, so `make merge ARGS=<n>` with no `--confirm` is never this clause's
business, piped or not. That carve-out carries its own mutation arm. Second, the self-test
asserts that every command the roster names still carries a heartbeat constant in the file
that runs it. An entry that stops narrating stops being this clause's business. That is a
failing case rather than a stale sentence.

`make design-check` is the nearest candidate for a second entry. It is deliberately absent. It
backgrounds itself and writes `.serve/design-check.json`, so its verdict survives a pipe.

**The remedy never names the forbidden target**, per the house rule. The refusal says to run
the command with nothing after it. No pipe, no redirect, no filter. It also says how long the
wait legitimately takes. Nobody should read the refusal as an invitation to shorten the
waiting.

### Cause 2 — the wait could not see that the branch had stopped being mergeable

Inside the check-wait loop, nothing re-read the pull request's mergeability. It watched check
runs only.

This repo runs many concurrent sessions against one main. When another session merges first,
the waiting branch can go `DIRTY`. The claim commit's own checks are unaffected by somebody
else's merge. So they go on passing. The wait then sits for the full 45 minutes on a merge
that can no longer succeed. **Observed on PR #436, 2026-09-20.** It sat for over 17 minutes
while `gh pr view 436` reported `OPEN` and `DIRTY`.

`mergeable_half` already asks this question once, before the claim. D228 (the claim is spent
only on a merge that can happen) says in as many words that a gate there does not close the
race. Its own words: "The claim's own CI wait is minutes long. A merge that lands during it
turns a MERGEABLE answer stale while this is standing still." This is that sentence's other
half.

`wait_for_checks` now takes an optional `mergeability` reader. It asks at most once per
`MERGEABILITY_RECHECK_SECONDS`. That is 60 seconds, six times the check poll. The subject
changes only when somebody else's merge lands. Every reading is a `gh pr view` against a rate
limit.

**It is not a second mechanism.** A conflict returns NOT GREEN. That is the path `claim_half`
already has, so `rollback_claim` backs the claim out exactly as it does for a red check.
D228's loser-backs-itself-out is unchanged. The loser only notices sooner. The report names
main moving, and says to bring `origin/main` in and resolve.

**`UNKNOWN` is never read as conflicted.** That is the arm that matters. GitHub computes
mergeability asynchronously and answers `UNKNOWN` routinely while it does. Reading that as a
conflict would abort every merge this repo makes. It is the obvious way to get this wrong.
Only the literal word `CONFLICTING` ends the wait.

An unreadable answer is no news. So is a `gh` that failed, an answer that is not JSON, and a
reader that raised. The wait continues on the checks. Absence is not evidence here any more
than it is on the check runs. That is D148's own rule, applied to the second question.

### What proves it

**`make guard-shell-selftest`, 302 arms, 0 failed.** The incident is performed in the fixture
(0 bytes mid-run, 2 of 5 lines kept). Then 8 refusal cases, 13 must-never-refuse cases, both
hatch forms, and the roster reconciliation.

**`scripts/claim-selftest.py`, 185 arms, 0 failed.** A branch that goes CONFLICTING under the
wait ends it early and says why. `UNKNOWN` never does, over a roster that never completes, so
the arm really reaches the reader. The same holds for an unreadable answer and for a reader
that throws, and each asserts it was really asked. The recheck interval is checked against the
shipped constants. `mergeability=None` leaves the old arithmetic untouched. The reader's own
five answers are read one by one.

**`make mutate-anchors` and `scripts/mutate-guards.py`, 7 new arms, 35 total.** Three cover
clause 9. A truncating filter that is no longer one turns 9 arms red. A command that is no
longer recognised turns 10 red. Removing the preview carve-out turns the cry-wolf arm red.
Three cover the wait. Never noticing a conflict turns 3 red. Reading `UNKNOWN` as conflicted
turns 8 red. Reading an unreadable answer as a conflict turns 2 red.

A seventh arm covers the two guards contradicting each other. `silent-write-guard.py` told a
session to pipe a refused `make merge` into `tail`, which clause 9 then refuses. That advice
is now conditional on the verb, and `make silent-write-selftest` asserts both branches of it.

`scripts/merge-pr.py` joins that corpus as a sixth guard, with `claim-selftest.py` as its
suite. The fixture mirrors `server/ports.py`. Without that a mutant dies of a
`ModuleNotFoundError` and reads as caught.

**One arm passed for the wrong reason before it was fixed.** It is worth recording. The first
"a reader that throws is no news" arm used a roster whose checks went green in two reads. That
is two seconds of the fake clock, so the mergeability reader was never asked at all. The arm
passed whatever the reader answered. The third mutation survived because of it. That is
`a-guard-must-see-its-subject` in one line. The arm now uses a roster that never completes,
and asserts the reader was asked more than once.
