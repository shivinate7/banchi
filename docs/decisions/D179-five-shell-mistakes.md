## D179 — Five shell commands are refused by resolving what they would do, not by matching what they say, and each clause carries its own escape hatch

**A fourteen-agent read-only audit, 2026-09-12, asked one question of every rule this repository has written down: has it been broken anyway, and can a machine see it?** Forty rules came back
as mechanizable. Five of them are one command away from a session's fingers and every one of
the five has a measured incident behind it. `scripts/guard-shell.py` is those five, as a
PreToolUse hook on Bash and on Write|Edit, armed in both tools' rosters (D135).

**D173 is that audit's ruling and this entry is one discharge of it**: a rule that can be
enforced mechanically is enforced mechanically, and a rule with no reader is advice. What is
added here is which five, what each cost, and — the part a ruling cannot carry — where these
particular readers are blind.

### Why a hook and not a rule, which D171 already settled

**Every one of these five was already written down when it was broken.** Four were in a memory
file the breaking session had loaded; one is in CLAUDE.md twice. The freshest is the plainest:
on 2026-09-12 a session ran `git checkout CLAUDE.md` over its own uncommitted work with
`mutation-tests-need-a-bak-not-git-checkout` in its context window.

That is not carelessness, and writing the rule a third time is not the remedy. D171 states the
mechanism: **a rule is read once, at the start, and then competes for attention with the work.**
So these are mechanical, and this entry exists because the audit's own thesis — from the memory
file of the session that broke rank 19's rule four days after writing it — is that a rule
*"phrased as an explanation to recall rather than a prohibition to trip over"* will be recalled
exactly when it is not needed.

### The five, and what each cost

**1. `git checkout <path>` / `git restore <path>` over a modified file.** 2026-09-06: three
mutation cases used `sed -i.bak` and the fourth used `git checkout cli/cmd_reprice.py`. Nothing
was committed, so it reverted to HEAD and took ~240 lines of that session's work. *"Every other
file survived, which made it look at first like a smaller problem than it was."* The refusal
names the `.bak` copy, because that is the shape the memory file prescribes and the one a
session reaches for when it is refused.

**2. A write outside this checkout.** 2026-09-06: an absolute-path `cd` prefix wrote ~1,500
lines into the owner's MAIN checkout, on `main`, for most of a session — and
`make launch-agent`'s supervisor hot-reloaded that uncommitted branch code into their live
`:8000` capture server repeatedly while they were using the app over their real store. The
symptom was silent and read as a different bug: the worktree's own dev server went on serving
the worktree's unedited `app/`. This is D43's subject — every checkout has its own store, its
own ports, its own inventory — with the one door D43 did not close.

**3. `gh api -f k=v` with no method.** 2026-09-12: a field implies a body, so gh sends POST. The
call hung past a 120s tool timeout and left a background process to reap, *"which reads as a
network problem rather than as a malformed request"* — and it was hit while building the
SHA-pinned merge wait, so the malformed request blocked a fix.

**4. `ln -s` at a path that already exists.** 2026-08-29:
`ln -s <main>/harness/images harness/images` over an existing directory nested a second
`images` link INSIDE it instead of failing. Copying that back landed a symlink loop,
`Path.mkdir(exist_ok=True)` raised `FileExistsError`, T1 died naming only the symptom, and
iCloud renamed the real 133 MB directory — the largest thing in this tree, with no backup
anywhere — to `images 2`, empty.

**5. A polling loop.** 2026-09-12, twice in one day. A session that had read the rule four days
earlier wrote `until ! pgrep -f 'scratchpad/drive.sh'`; the loop never went false, its chained
work never ran, and a second copy of the driver raced a live one for ~15 minutes. The same day
a backgrounded `while`/`sleep` merge driver ran **119 rounds over 3 h 58 m** — across a
compaction of the session that started it — racing that session's own hand-merges and
re-resolving branches it was resolving. It ended because a person noticed a four-hour bash in
their own window.

**D175 is the other half of that incident and this clause does not duplicate it.** That entry
teaches the sweep to ask whether anything still OWNS a process, so a loop whose session is gone
is offered up rather than read as busy.
**This clause refuses the loop at the moment it is created**; D175 finds the one already
running. Neither makes the other redundant — a poller
started before this hook existed is D175's, and a poller this hook refuses never becomes
anybody's to find.

### The predicate is resolution, and that is the whole design

`git checkout main` and `git checkout CLAUDE.md` are the same verb; the first is a branch and
the second destroys work. `ln -s a b` is right on Monday and wrong on Tuesday. A backgrounded
script's loop is not in the command at all — it is in the file.
**So the guard asks the system, read-only, exactly as `scripts/reap.py:hook` does for a kill:**
`git status --porcelain` decides
whether an operand is a modified path, `git rev-parse --verify` decides whether it is a commit,
`os.path.lexists` decides whether a link destination is there, and the shell script a
backgrounded command names is READ. `reap.py`'s standard is that `pkill -f capture_server.py` is
allowed when the only match is yours; the same standard here is that `git checkout main` is
allowed because `main` is not a file.

**The Write|Edit half of clause 2 parses nothing at all**, and that is why no shell form can
skirt it: the payload carries a path, the path resolves, and the comparison is against
`checkout_root(cwd)`.

### Fail open on our own bugs, and never silently

`reap.py`'s asymmetry is honoured unchanged: **a broken guard fails OPEN, and an unreadable target is a command this guard has no opinion about.**
A parse error, a missing `git`, an
unreadable payload, even a missing `scripts/shell_parse.py` all exit 0. There is no fail-CLOSED
case, because none of these five harms is unrecoverable in the way a signal to a stranger's
process is.

**But a pass this guard could not decide is PRINTED.** An operand that resolves to neither a
path nor a commit says so; a checkout root it could not resolve says so. A guard that cannot
distinguish "nothing to object to" from "I could not read this" is D171's own failure class
wearing a guard's clothes.

### Five hatches, not one

`PKMNSCAN_CHECKOUT`, `PKMNSCAN_TREE`, `PKMNSCAN_GH`, `PKMNSCAN_LINK`, `PKMNSCAN_WAIT` — each
`=off`, each honoured in the environment and inline, each printed in its own refusal and
nowhere else. **One switch for the whole hook would mean disarming the clause that guards uncommitted work in order to make a symlink**, and a hatch reached for by reflex is a guard
already gone. The recovery the 2026-09-06 incident actually needed — `git checkout --` in the
main tree, to unwind writes that had landed there — is one hatch away and is named in the
refusal.

### The parser is shared, because it already existed

`scripts/shell_parse.py` is `silent-write-guard.py`'s tokenizer, moved unchanged. That file
took four defects to get right — a newline is not whitespace, an operator is not a quoted
string, a heredoc body is a document, `#` is not always a comment — and
**every one of them is a defect a second hand-rolled parser would have shipped again.** CLAUDE.md's rule is to ask
whether the primitive exists before designing around its absence. What did not move is anything
either guard DECIDES: one is decidable from the string, the other must resolve its subjects
against the filesystem, and sharing the parse is not sharing the judgement.

### What this guard cannot see, named rather than left to be discovered

- **`cp`, `mv`, `install`, `rsync` and `sed -i` destinations.** Clause 2 reads redirection
  targets and `tee` operands; those five have positional destinations mixed in with patterns
  and flags, and a clause that guessed would refuse an ordinary copy. The Write|Edit half is
  the one that cannot be skirted.
- **`git checkout HEAD -- <path>` — CLOSED 2026-09-12, amended below.**
- **A loop's bound is judged syntactically.** A counter, a deadline, a `break`, a `for` over a
  word list or a wait on a pid all read as bounded, and a `break` that can never be reached
  reads as bounded too. The clause is aimed at a loop with nothing at all to end it.
- **A Python or Node poller in a backgrounded script.** Only shell scripts are read, and only
  for shell loop grammar. `make up`'s supervisor and `make design-check ARGS=--wait` are both
  long-lived loops this repository tells a session to start, so a guard that guessed at another
  language's loops would refuse the documented workflow.
- **Which process a pattern waiter matches.** Measured on BOTH platforms: BSD `pgrep` excludes
  itself *and all its ancestors* unless `-a` is given, while procps excludes only itself — so
  whether the waiter matches ITSELF depends on the machine. That is the argument for the clause
  rather than a gap in it — a predicate whose answer depends on that is not one a session can
  reason about — and the refusal says so rather than claiming either platform's answer.

- **This guard's own self-test proved the rule it was written under, on itself.** It passed 165
  cases on the author's machine and went red on the Linux runner in two arms, both of them
  fixture defects rather than logic: the throwaway repo's default branch is whatever
  `init.defaultBranch` says (`main` here, `master` there), so two cases asked about a branch
  that did not exist and the guard's correct *"I have no opinion"* read as a failure; and the
  `pgrep` arm asserted BSD's exclusion rule as though it were universal.
  **A green check proves its own platform, not "anywhere"** — already a memory in this
  repository, and now a measurement inside the thing that exists to make rules mechanical. The fixture names its own
  branch, asserts it, and refuses to score a case git itself rejected.


### AMENDED 2026-09-12 — a named source is not a hatch, measured rather than argued

The sentence this repeals, verbatim: *"A named source is allowed, on the ground that it WRITES
a known version rather than discarding an unknown one — which is the audit's own must-pass.
The one spelling where that reasoning is thin is `HEAD` itself... It is allowed today and the
hatch is not needed for it."*

**What no longer holds, and how it was found rather than argued.**

The coordinator running this session's own merge queue ran `git checkout origin/main -- .` to
inspect a stray file on another ref, in a worktree whose tracked files happened to be clean at
that instant. It passed — the clause's own design, unchanged since D179. Had that tree carried
a single uncommitted edit, the command would have discarded it with no refusal and no
diffstat, for exactly the reason the "thin" note above already flagged for `HEAD` and never
checked for any other source.

**A named source changes what is WRITTEN, never whether a change is discarded first.** The
original argument treated "known replacement" and "safe to overwrite" as the same fact. They
are not — a known replacement can still destroy an unknown loss.

**What protected the owner's work that day was luck — a clean tree — not the guard.** That is
the same shape D179's own opening section names for why a hook exists at all: *"a rule
enforced by memory is a rule that gets bypassed under exactly the conditions it exists for."*

**The fix.** `_read_restore` no longer treats a named source as an automatic pass. It resolves
the path operands the same way the no-source form does, and `clause_checkout` runs the
existing `_modified` check regardless of whether a source was named — refusing a checkout over
a modified path whether the replacement is `HEAD`, a branch, or any other ref, with a message
that names the source and says plainly that naming it did not make the overwrite safe. A
checkout over a genuinely clean path is unaffected — nothing is lost there and nothing
changes.

**Proved by reproducing the near-miss, not only by a synthetic case.** The self-test's two
existing "names a source" cases were themselves instances of the bug — both ran against
`work.py`, modified earlier in the same fixture, and asserted `allows`. They are now `refuses`
cases (a modified path with an explicit source, both `git checkout <sha> --` and `git restore
--source=`), and a new `allows` case takes their old name against `clean.txt`, so the
genuinely-safe path is still proven separately from the fixed one. 167 cases pass, up from
165 (2 rewritten, 1 added), 0 failed.

### AMENDED 2026-09-12 — a sixth clause, because a named refspec sits outside git's own net

**Git already refuses the bare form of this exact mistake, which is precisely why it survives.**
`push.default=simple` — git's own modern default — refuses a bare `git push` whose tracked
upstream branch name differs from the current branch's own, and even prints the fix. But the
refusal is keyed to the ABSENCE of a refspec, not to the mismatch itself: the moment a caller
names one — even the unqualified `HEAD`, one of the two spellings the refusal's own printed fix
offers — git reads that as the caller's informed choice and pushes to a branch of that literal
name, creating one on the remote if none exists, silently.

**That is exactly what happened.** A coordinating session resolving a merge conflict stood on
a local branch a background agent had named `pr-h-readings-table-local`; the agent had pushed
its finished, squashed commit to the real PR branch under a different name, so the local
branch's configured upstream was `origin/claude/pr-h-readings-table`, never
`origin/pr-h-readings-table-local`. Intending to update the real PR branch, the session ran
`git push origin HEAD`. Git did exactly what that means — `[new branch] HEAD ->
pr-h-readings-table-local`, on origin, the actual PR branch untouched. No error, no refusal;
it was caught only because the next command's output looked wrong.

**The sixth clause, `clause_push`, resolves the identical fact git's own safety net already holds.**
`git rev-parse --abbrev-ref HEAD` is the current branch; `branch.<name>.remote` and
`branch.<name>.merge` are the tracked pair, read exactly as git itself reads them rather than
re-derived from the command's own text. A push whose remote matches `branch.<name>.remote` and
whose lone refspec is an unqualified `HEAD` or the branch's own literal name, where the tracked
branch name differs, is refused. Everything else passes exactly as before: no configured
upstream at all (the ordinary first push of a new branch), a name that already matches its own
upstream, an explicit `HEAD:<branch>` naming the real destination, a push to a remote this
branch does not track (a fork workflow), and `--all`/`--mirror`/`--tags`/`--delete`, which push
something other than "this branch under its own name". `PKMNSCAN_PUSH=off` is its hatch,
honoured in both forms like the other five.

**Reproduced rather than argued, D179's own standard.** `scripts/guard-shell-selftest.sh`
builds a real bare origin, pushes a branch under one name while its tracking is configured to
a differently-named branch on it — the identical mechanism the incident used
(`git push -u origin <local>:<remote>`) — and asks the guard about the resulting mismatch for
real, alongside the cases the ordinary first-push, already-matching and fork workflows must
never trip.

### AMENDED 2026-09-13 — the ordinary first push of a feature branch was refused, and its own printed remedy pushed to main

**The exemption list above did not cover the ordinary case it claimed to.** It reads "no
configured upstream at all (the ordinary first push of a new branch)". A
branch made the way this repo's own workflow makes one —
`git switch -c <name> origin/main` — DOES get an upstream: `branch.<name>.merge` is set to
`refs/heads/main` at the moment the branch is created, not left empty. So the single most common
shape in this repository — cut a branch from `origin/main`, then `git push -u origin
<that-branch-name>` — tracked-vs-named mismatch and all, was refused by the very rule meant to
protect it, and the refusal's own two-line remedy read:

    git push                              # let git's safety net name the fix
    git push origin HEAD:main      # push to the branch actually tracked

**Both lines push to `main`.** The second names it outright. A guard built after a coordinator's
push silently created a stray branch instead of updating the real PR branch was, for the
ordinary case, telling the operator to do the one thing D42, `scripts/githooks/pre-push`,
`scripts/githooks/reference-transaction` and GitHub's own branch protection all exist to
prevent. Other guards would have caught the result — this was never a live incident — but a
refusal whose remedy is the forbidden act teaches exactly the wrong reflex, which is the same
standard `no-bandaids` and D171 already hold this repository to.

**The fix exempts only the shape that was never the incident.**
`pr-h-readings-table-local` tracked `origin/claude/pr-h-readings-table` — a
DIFFERENT FEATURE BRANCH, not the default — and that is what stays refused.
`_default_branch(remote, cwd)` answers what this checkout treats as `<remote>`'s default,
preferring git's own record of it — `refs/remotes/<remote>/HEAD`, the ref a real `git clone` (or
`git remote set-head <remote> -a`) sets — and falling back, when that ref has never been
written, to the same rule `scripts/janitor.py:default_branch` already uses for the primary
checkout: the first of `main`, `master` that exists as a local branch. Nothing here guesses — an
unreadable remote and an absent local branch both answer `""`, which never equals a real tracked
name, so that case is refused exactly as it always was. `clause_push` then exempts a mismatch
only when `tracked == _default_branch(remote, where)`; every other mismatch, including the
incident's own, reaches the refusal unchanged.

**Why git's own record first, and a documented constant never.**
`janitor.py:default_branch` already answers this question for the
primary checkout, so a hardcoded `"main"` here would have been a second, divergent answer to a
question this tree had already settled once — the "ask whether the primitive exists" rule this
same file's own opening section restates from CLAUDE.md. But `janitor.py`'s answer is local-only
and this clause's question is about a specific REMOTE, which matters the moment a fork's default
differs from `origin`'s — so `refs/remotes/<remote>/HEAD`, git's own per-remote record, is
asked first and the local guess is what runs only when that ref was never written (this guard's
own throwaway fixtures, and any `git init`-then-`push` clone that never ran `git clone` or
`git remote set-head`).

**Reproduced red-first, D179's own standard.** Before this fix, in a real throwaway repo: a
branch made with `git switch -c feature-x origin/main`, pushing `git push -u origin HEAD`, was
refused (`exit 2`) with the remedy above naming `HEAD:main`. After the fix the identical command
sequence exits `0`. `scripts/guard-shell-selftest.sh` poses both directions for real: the fixture
switches to a branch cut from `origin/main` (asserting the upstream really is
`refs/heads/main` before trusting the case), asserts the push is never refused with or without
`-u`, asserts no still-refused case's remedy ever names the default branch, and separately sets
`refs/remotes/origin/HEAD` by hand — the way a real `git clone` would, which this fixture's own
`git init`-then-`push` construction never does on its own — so the PRIMARY read is exercised and
not only its local-branch fallback. The pre-existing incident reproduction and its five
"must never refuse" cases (a fresh branch with no upstream at all, a matching upstream, a
different remote, `--all`/`--tags`/`--delete`, a detached HEAD) are unchanged and still pass.

**Mutation-tested, and the count below replaces the stale one.** The original sixth clause's own
count — six arms over the colon-check and refspec resolution, five caught, one equivalent
mutant (a colon-bearing refspec can never equal `HEAD` or a bare branch name, so the guard the
colon check adds is never actually reached) — is untouched, because none of that code moved.
This amendment's own logic — `_default_branch` and the exemption it feeds — was mutated eight
more ways and re-run against the full selftest: inverting the equality to `!=` (caught, 14
failures), deleting the exemption outright (caught, 4 failures — the original bug, reproduced
again as its own mutant), reading `branch` instead of `tracked` (caught, 4 failures), always
exempting regardless of the comparison (caught, 10 failures), dropping `main` from the local
fallback tuple (caught, 3 failures), and refusing to strip the `<remote>/` prefix off a real
`origin/HEAD` symbolic ref (caught, 1 failure — the arm added specifically to exercise that
read). **Two survive, and both are equivalent mutants rather than holes.**
Swapping the local fallback order to `("master", "main")` and corrupting
the symbolic-ref path's ref name both still land on `"main"`, because every fixture branch in
this file is named `main` and never `master` — a repo whose local branch and remote default
genuinely disagreed would tell the two mutants apart, and none built here does.
**Fourteen arms across both amendments, eleven caught, three equivalent-mutant survivors.**
That replaces the "six arms, five caught" figure `CLAUDE.md` published for this clause before
the amendment, which described only the colon-check half.

### Standing

**BUILT and self-tested**: six clauses, `scripts/guard-shell-selftest.sh` with five
reproductions, the swept allow list, every hatch in both forms, and the fail-open floor.
**RECORDED**: this entry, `docs/map.py`, CLAUDE.md, `scripts/checks.py` and both hook rosters.
**NEITHER**: nothing. What is unproven is what every hook here shares and
`silent-write-selftest.sh` says in as many words — that the harness invokes the hook and that
exit 2 blocks a call are the harness's behaviour, not this repository's.
