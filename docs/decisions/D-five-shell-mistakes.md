## D-five-shell-mistakes — Five shell commands are refused by resolving what they would do, not by matching what they say, and each clause carries its own escape hatch

**A fourteen-agent read-only audit, 2026-09-12, asked one question of every rule this repository has written down: has it been broken anyway, and can a machine see it?** Forty rules came back
as mechanizable. Five of them are one command away from a session's fingers and every one of
the five has a measured incident behind it. `scripts/guard-shell.py` is those five, as a
PreToolUse hook on Bash and on Write|Edit, armed in both tools' rosters (D135).

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
re-resolving branches it was resolving. Nothing in this repository could see it: `make janitor`
reads a live process as live, and `make reap` acts only when asked. It ended because a person
noticed a four-hour bash in their own window.

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
- **`git checkout HEAD -- <path>`.** A named source is allowed, on the ground that it WRITES a
  known version rather than discarding an unknown one — which is the audit's own must-pass. The
  one spelling where that reasoning is thin is `HEAD` itself, whose content is the discard. It
  is allowed today and the hatch is not needed for it.
- **A loop's bound is judged syntactically.** A counter, a deadline, a `break`, a `for` over a
  word list or a wait on a pid all read as bounded, and a `break` that can never be reached
  reads as bounded too. The clause is aimed at a loop with nothing at all to end it.
- **A Python or Node poller in a backgrounded script.** Only shell scripts are read, and only
  for shell loop grammar. `make up`'s supervisor and `make design-check ARGS=--wait` are both
  long-lived loops this repository tells a session to start, so a guard that guessed at another
  language's loops would refuse the documented workflow.
- **Which process a pattern waiter matches.** Measured on this machine: BSD `pgrep` excludes
  itself and all its ancestors unless `-a` is given, so whether the waiter matches ITSELF
  depends on the process tree the harness happens to build. That is the argument for the clause
  rather than a gap in it — a predicate whose answer depends on that is not one a session can
  reason about — and `scripts/guard-shell-selftest.sh` asserts the platform fact instead of
  assuming it.

### Standing

**BUILT and self-tested**: five clauses, `scripts/guard-shell-selftest.sh` with the four
reproductions, the swept allow list, every hatch in both forms, and the fail-open floor.
**RECORDED**: this entry, `docs/map.py`, CLAUDE.md, `scripts/checks.py` and both hook rosters.
**NEITHER**: nothing. What is unproven is what every hook here shares and
`silent-write-selftest.sh` says in as many words — that the harness invokes the hook and that
exit 2 blocks a call are the harness's behaviour, not this repository's.
