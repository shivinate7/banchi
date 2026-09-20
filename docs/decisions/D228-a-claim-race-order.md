## D228 — The claim is spent only on a merge that can happen, and the loser of a race backs itself out

**MEASURED, 2026-09-19.** Two sessions merged four minutes apart. `make merge ARGS="422
--confirm"` ran from the branch `claude/ste-ratchet`. It allocated three numbers. It rewrote
the entry, the heading, CLAUDE.md's index, `docs/decisions/ORDER.json` and every citation. It
committed that as one commit and pushed it.

It then reached the GitHub half and was refused. The pull request conflicted with its base.
The other session's merge had landed in the meantime and taken all three numbers. The merge
did not happen. The branch was left carrying a pushed commit claiming numbers main already
owned. A person unpicked it, at the cost of two force-pushes.

**The design is not what failed, and this entry changes none of it.** A branch writes an
unclaimed slug. The number is allocated at the merge. No session renumbers another session's
entry (D140, D182, D187). All three held that night. No branch guessed a number, and nothing
of the other session's was touched.

What failed is the ORDER around the claim, and the recovery path from a lost race.

### The claim runs after the pull request is known to be mergeable

`main()` already read the pull request before the claim. It has to, to learn the head branch.
It then threw away the two fields that say whether merging is possible at all. So the claim
committed and pushed against a pull request whose base had already moved. The refusal came
minutes later, after CI.

`mergeable_half` now reads `mergeable` and `mergeStateStatus` out of that same reply, before
`claim_half` is called. A `CONFLICTING` answer refuses with nothing allocated, committed or
pushed. Three orders were weighed:

- **Claim without pushing until the GitHub half succeeds.** NOT AVAILABLE. This was
  established rather than assumed. `gh pr merge` merges what ORIGIN carries. A claim that is
  not pushed is not in the commit that lands. The number has to travel with the entry.
- **Claim, and roll the claim back when the merge is refused.** Taken, as the second half
  below. On its own it pays a full claim, a push and a CI wait for every lost race.
- **Check mergeability before claiming.** Taken. It costs two fields of a reply already in
  hand. It closes every case where the pull request was ALREADY unmergeable when the merge
  was typed. That is tonight's case.

`UNKNOWN` is neither answer. GitHub computes mergeability asynchronously. A pull request read
moments after a push answers `UNKNOWN` for a few seconds. So it is re-read until it answers or
a deadline passes. A deadline that passes REFUSES.

**DECIDED WHILE BUILDING THIS, AND NOT RULED ON.** The first version proceeded on `UNKNOWN`
with the uncertainty printed, on the grounds that the backout covered it. This one waits and
then refuses. The cost of waiting is a slow merge on a slow day. The cost of proceeding is a
claim, a push and a CI wait spent on a state nobody read. That is this same incident, one
remove further out. A claim is never spent on a guess.

**Either reading is defensible and the owner has not picked one.** `MERGEABILITY_DEADLINE` is
where the choice lives. Say the word and it goes back to proceeding.

**The gate does not close the race, and saying so is the point.** The claim's own CI wait is
minutes long. A merge that lands during it turns a `MERGEABLE` answer stale while this is
standing still. That window is what the backout is for. A gate before and a backout after are
two halves of one answer.

### A claim whose merge did not happen is backed out, and says which it did

The GitHub half can refuse after this run has already moved the branch. `rollback_claim` then
reverts the claim commit and pushes the revert. The branch is back to its slugs. Origin
carries no claimed number either. The report says main has not moved, and what to do next.

It is a `git revert` of the claim commit rather than `--unclaim`. The two are the same
operation by different routes, and this one is exact. `claim_half` refuses a dirty tree before
it commits. That single commit is therefore the only thing between the branch and its slug
form. Reversing it restores the heading, the citations, the index, the manifest AND the
entry's filename, with nothing parsed and nothing reconstructed.

A revert rather than a reset, because the claim commit is already on origin. It may already be
somebody's read. A new commit on top says what happened. A rewrite would make an accident look
like it never was.

**It never retries by itself.** Re-claiming needs main merged into the branch and the conflict
resolved. That is a person's judgement rather than a lookup. So it backs out, names what it
did, and stops.

**ANY CLAIM THAT DOES NOT REACH A MERGE GOES BACK.**
Decided while building this, and not ruled on. The first version backed out only on the GitHub half's refusal. `claim_half` also
refuses for a red check on the claim commit, for a push that failed, and for a sha it could
not read back. None of those is a lost race. Each one left the claim standing, while the text
told the reader to fix the branch and run again. A number held by a branch that is not about
to land is a number another branch can take from under it. That is the whole incident. So
every one of those paths backs the claim out now, and the refusals say so.

**The narrower reading is the alternative, and the owner has not picked between them.** Back
out only on a lost race, and leave a red claim commit standing for a fix-forward push. It
costs a re-claim on every red. It also holds a number while the branch is red.

### `--unclaim` resolves which entry is this branch's

`python3 scripts/claim-ids.py --unclaim D<n> --to-slug <slug>` is the remedy the refusal itself
names. In the state a lost race produces, it REFUSED. It said there is no single entry file in
this tree wearing that number.

Once `origin/main` is merged in, two files carry that number. One is this branch's own. One is
the entry the merge brought. That merge is the documented pre-merge routine, so the state is
reached by following the rules rather than by breaking them.

The refusal is not wrong about what it sees. It is wrong to stop there. The branch knows the
answer: the entry it holds is the one `ref` does not have. `find_decision_file` now filters
the matches by what `ref` itself carries, and answers with the survivor. A single match is
still answered without asking git anything.

### And the substitution leaves the other entry's citations alone

The claim is keyed on the TOKEN, and so was its inverse. In the two-file state that rewrote
main's own entry heading, main's index line and main's prose citations into this branch's slug.
It did so in the same pass that correctly reverted this branch's own.

Measured in the fixture by removing the guard. The OTHER entry's heading came back wearing
this branch's slug. So did a line of main's prose that had nothing to do with this branch. The
note the command printed — "Only this branch's own copy is touched" — was a claim nothing
enforced.

`protected_lines` reads every line `ref` itself carries that spells the id. Those lines are
left exactly as they are. Every transform in the reverse claim is line-local, so a line is the
right unit. The set is empty unless the numbers collided. The ordinary round trip therefore
takes the identical path it always took, byte for byte.

### `--stale` goes blind when the routine says to merge main in

`stale_claims` is a DIFFERENCE. It compares ids the branch adds since the merge base against
ids the ref has taken. Merging `origin/main` into the branch moves that base onto it.

Main's colliding entry is then on both sides. The branch "adds" nothing at that number. The
check that refused five minutes earlier reports `nothing has gone stale`. It says that over a
tree holding two entries under one number. Measured in the fixture.

`duplicate_numbers` is the reader that cannot be blinded. It needs no ref and no base. Two
headings carrying one id is wrong on its own terms. `docs-audit`'s `decision ids` row already
says so, and blocks the commit for it. That backstop is loud, late, and paid by whoever merges
second. This asks the same question in the one place that is early. `make merge` now refuses
before it claims anything, and names the command that now runs.

### Proved by reproducing the state, not by reasoning about it

`scripts/claim-selftest.py` builds tonight's exact shape. Two branches are cut from one
commit. Each honestly claims the next free number for its own entry. The winner merges to
main. The loser MERGES MAIN IN and resolves the conflict. That is what produces two files
under one number.

Every guard above was mutation-tested against it, and each goes red on its own defect.
Removing the ref filter refuses to resolve. Removing `protected_lines` corrupts the other
entry's heading and prose. Removing the duplicate reader reports clean. Removing the
mergeability gate lets the claim run. Removing the backout leaves the claim standing.

### The shared-scalar shape, named once, and one half of it is not built

REPORTED BY THE OWNER, 2026-09-19, and not measured here. The ratchet is on a branch this tree
does not carry. The same evening it forced three re-pins. Every one was caused by an unrelated
merge rather than by the branch's own prose.

That is this defect's shape rather than a second one.
**A whole-repo scalar makes every branch a party to every other branch's merge.**
The branch that merges second pays. An id ceiling and a repo-wide word total are both such a
scalar. A branch that was correct when it was written is wrong by the time it lands, through
nothing it did.

The id half is answered here, and the answer generalizes.
**Derive the shared scalar at the merge, never on the branch, and make losing it recoverable by a command.**
D140 already had the first half for ids. This entry adds the second.

The ratchet half is RECORDED AND NOT BUILT. The same answer would mean one of two things. The
pin is computed at the merge rather than carried on the branch. Or the pin is per-file rather
than repo-wide, so an unrelated merge cannot move it. Both are rule changes to a ratchet the
owner set. Neither is taken here. It waits on the owner's word.
