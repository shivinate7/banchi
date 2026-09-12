## D-a-refusal-that-reaches-nobody — A refusal that reaches nobody did not happen, and a status line the session wrote is not a reading

**The owner, after the second instance in one session:** *"I'd rather it be mechanical, not a
rule lol."*

**On 2026-09-12 a coordinator session reported work as landed that had not landed, twice, and then reported three pull requests as progressing while nothing merged.** Two shapes, one class,
and this repo already has a name for that class: **a reader that cannot tell "nothing is wrong" from "nothing is known yet"**. Nine instances landed in about twenty-four hours.

### The two shapes

**One — a silenced write.** The command was

```
git commit -q -F - >/dev/null 2>&1 <<'EOF'
...
EOF
```

**The commit was REFUSED by `scripts/githooks/pre-commit`.** The refusal went to `/dev/null`.
The session then read `git log --oneline -1`, saw the **previous** commit — a real commit with a
real subject, indistinguishable at a glance from the one it meant to make — and reported
*"pushed"*. The push that followed said `Everything up-to-date`, and that read as success too.

**Both redirections are load-bearing and neither is sufficient alone.** `2>/dev/null` hides
every byte the hook prints; `>/dev/null` hides `[branch 1a2b3c4] message`, which is the only
positive proof a commit happened — and without it `nothing to commit, working tree clean`, also
stdout, is the same observation as success: none.

**Two — an outcome quoted from a tool's stdout.** A merge driver printed `#300 GREEN — merging`
and the session relayed that as progress for several turns. Two instances of the driver were
racing, and the `pgrep`-based waiter meant to serialise them was matching its own command line,
so it never fired. The owner caught it: *"feel like 3 have been left for a while, just
confirming you're actually checking."*

### Why a rule was not enough, which is the whole decision

**A rule that tells a session to check its work is a rule the session can defer to — and this one was deferred to by the session that wrote it.** That is not a lapse of care; it is what a
rule IS. A rule is read once, at the start, and then competes for attention with the work. The
instruction "read the output of your writes" was already in this repo when the command above was
typed, twice.

**What cannot be deferred to is a shell command that will not run, and a status line the session did not write.** So: the first shape becomes a command that is refused, and the second becomes a
report that is generated. Neither asks anybody to remember anything.

**This is the shape D127 already took for a neighbouring failure** — three session notes warned
about machine-wide `pkill` and it happened anyway, so the note became a hook. The argument
generalises and the owner has since made it the governing rule for the repository.

### Mechanism one: the predicate is an invariant, not a list of spellings

`scripts/silent-write-guard.py --hook`, a PreToolUse hook on Bash.

**A git WRITE must leave a trace the session can read.** stdout carries the proof, stderr carries
the refusal, and discarding either leaves the reader unable to tell the two silences apart. That
is the predicate: **a write whose stdout or stderr goes to `/dev/null`, to a closed descriptor, or to a file the same command never reads back is refused.**

**It is stated as an invariant rather than as a roster of redirection shapes on purpose.** A
roster misses `>>/dev/null`, `&>`, `2>&-` and the next spelling somebody invents, and — worse —
it fires on `git merge-tree`, which is `make revert-guard`'s own engine and writes nothing.

**The file descriptors are walked in ORDER, because the shell walks them in order.**
`cmd >/dev/null 2>&1` discards both streams; `cmd 2>&1 >/dev/null` duplicates stderr onto the
still-live stdout and only then sends stdout away, so the refusal survives and the proof does
not. Both are refused, so the ordering does not change the verdict — it changes what the refusal
is able to tell you, and a refusal that names the wrong stream is one a session argues with.

**The tokenizer is `shlex` with `punctuation_chars`, never a regular expression.** A quoted
`>/dev/null` inside a commit message is a STRING, and the message announcing this very entry
contains one. A regex over the raw string catches the incident and cannot make that distinction;
it was run as a mutation arm and the false-positive cases killed it.

**Heredoc BODIES are cut and everything else is kept.** `reap.py:_segments` truncates at the
first `<<` instead, which is right for its question and wrong for this one: the body of a commit
heredoc is a commit message, and a decision entry quoting the offending command on a line of its
own is an ordinary thing to write. Cutting only the body judges the redirections on both sides
and never reads the prose.

**The verb roster is deliberately short, because every verb is false-positive surface.** `commit`,
`push`, `pull`, `merge`, `rebase`, `cherry-pick`, a `fetch` carrying a local refspec, `make merge`
and `gh pr merge`. **`git add`, `git tag`, `git reset`, `git checkout` and `git revert` are absent despite all of them writing**: none of them produces a REPORT of landed work, and no session ever
said "pushed" because `git add` printed nothing. A verb goes in when something has gone wrong
through it.

**Two of those nine are in the roster because CLAUDE.md tells a session to type them.**
`git fetch origin main:main` and `git -C <tree> pull --ff-only` are the local half of D42's merge,
they move `refs/heads/main`, and `scripts/githooks/reference-transaction` refuses that move — a
refusal which, silenced, leaves main exactly where it was with nothing saying so. **A bare `git fetch origin -q` is a read and passes**, which is what the colon separates.

### The false positives are the half that decides whether a guard survives

**A guard with a false positive is a guard somebody switches off, and a switched-off guard protects nothing.** So each of these is pinned as PASSING by the self-test, and each is RUN in the
fixture before it is scored — a case that is secretly a typo would sail past the guard for a
reason that has nothing to do with the predicate:

| the command | why it must pass |
|---|---|
| `git rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1` | a TEST whose exit code IS the answer |
| `git fetch origin -q 2>/dev/null` | a read, and run constantly |
| `git merge --abort 2>/dev/null` | an unwind; it has nothing to report |
| `git rebase --abort`, `git cherry-pick --quit` | the same |
| `git push --dry-run`, `git commit --dry-run` | presses nothing, so nothing can be hidden |
| `git merge-tree`, `git merge-base` | reads, and the verb match is EXACT for them |
| `make merge-selftest` | not `make merge`; the goal match is exact |
| `git commit -m 'note: sent >/dev/null'` | a quoted redirect is a string |
| `git commit -m x 2>&1 \| tail -40` | kept and read, which is the recommended spelling |
| `git commit -m x > /tmp/o 2>&1 && cat /tmp/o` | a file the command DOES read back |
| a three-line script whose `>/dev/null` belongs to an `echo` | lines are separate commands |

**That last row is a defect this guard shipped with for an hour.** `shlex.whitespace_split` treats
a newline as ordinary whitespace, so three lines parse as ONE command whose stdout goes to
`/dev/null` and whose argv happens to contain `git commit`. A multi-line script is the ordinary
shape of a session's Bash call, so the guard would have been disabled the first afternoon.

**The asymmetry is `reap.py`'s and it is honoured unchanged: a broken GUARD fails open.** Any
parse error, any bug, any malformed payload exits 0. **There is no fail-CLOSED case here, and that is not an exception to that rule but the same rule** — a command this file cannot tokenize
is a command it has no opinion about. **The escape hatch is `PKMNSCAN_SILENT=off`**, honoured in
the environment and inline, and printed in every refusal.

### Mechanism two: the report is generated, and its floor is read from GitHub

`make coordinator`. **Every figure is read from the repository or from the GitHub API at the moment you run it, and nothing is read from any local tool's output.**

**A verdict is pinned to a HEAD SHA.** `gh pr checks` answers about a pull request; this asks
`commits/<headRefOid>/check-runs`, so a green from a push three commits ago cannot be mistaken
for a green on the code that would merge.

**A commit short of the floor is `not ready`, never clean.** A commit whose checks have not all
reported has every reported check PASSING, which is precisely what the incident read as green.

**The floor is a set of required NAMES and not a count, and that is a measurement rather than a preference.** A count was the obvious spelling and this file was written with one, derived from
`origin/main`'s own tip. Measured against the live repository on 2026-09-12 it is wrong in both
directions:

| commit | runs | why a count fails |
|---|---|---|
| `origin/main` tip `df6ec79` | 10 | includes `build` and `deploy` from `demo.yml`, which run ON PUSH TO MAIN ONLY — no pull request can ever reach 10 |
| PR #309 head `2f9159a` | 6 | `design-check` as ONE gated run rather than main's three shards, because D141 path-gates the browser matrix |

**So the floor is read from where the requirement actually lives:** `branches/main/protection`'s
required status checks, which are `check` and `revert-guard`. **GitHub enforces that set, the owner configured it, and it survives both path-gating and matrix expansion.** A required context
that is missing is `not ready`; **one that reported `skipped` is also `not ready`, because a required check that did not run is the definition of nothing being known.**

**`check-suites` was tried and is not usable**, recorded so nobody re-derives it: a permanently
`queued` suite belonging to the `claude` app sits on merged PR heads with zero runs, so "every
suite completed" marks every pull request in the repository as still running.

**`conclusion: null` is `running`, never `failed`** — the mirror of this entry's own bug, and a
report that cried failure over an in-flight run is one a session learns to distrust.

**Liveness is read from the console app's own per-session records, and the start time is checked.**
Two pids were recycled into unrelated shells within minutes on 2026-09-12, so a pid is not an
identity; `scripts/janitor.py:_same_process` is the account and its epoch comparison is copied
here with its argument rather than re-derived. **Never an mtime**: a tree with no dirty files and
no recent writes is indistinguishable from an abandoned one.

**Any block it cannot read prints UNKNOWN with the reason and makes the exit non-zero.** It never
omits a block and never guesses a substitute. That is `scripts/status.py`'s rule, and here it is
the same sentence as the guard beside it: an incomplete report must not be relayable as the state
of the queue.

**One block was a permanent false alarm on its first real run and was corrected the same hour.**
Grouping running processes by script BASENAME reported four `serve.py` instances as duplicated —
the main checkout's supervisor, a worktree's, and two temp trees from concurrent
`serve-selftest` runs. **Under D43 four is the CORRECT number**, and a signal that is always on
carries nothing. Grouping by absolute path reports the defect the incident actually was: two
copies of ONE script.

### It reaches the network, so it does not gate

**`make coordinator` is deliberately not in `make check`**, on `make lan-check`'s reasoning:
`check` answers from the tree alone, and a row that fails on a train is a row people learn to
ignore. **What gates is `make coordinator-selftest`**, which runs the verdict rules against
synthetic payloads and needs no network — the split `verdict-selftest` already makes.

**`make silent-write-selftest` gates and is never in the git hook** (D18: it writes a temp
repository), which is exactly `reap-selftest`'s standing.

### What was proved, and what survived

**The self-test reproduces the incident before it asserts anything about it**, which is this
repo's standard: a throwaway repository with a pre-commit hook that refuses, the command run
verbatim, and the proof that `git log --oneline -1` then answers with the previous commit.
**76 arms pass.** The refusal's own TEXT is scored too — a refusal that stops printing
`PKMNSCAN_SILENT=off` fails here.

**Mutation-tested: twenty-one arms, nineteen caught.** Two survived, and they are reported rather
than explained away: **the JSON `try/except` and the bottom-of-file floor each survive alone because the other covers it.** A twenty-first arm removing BOTH goes red, which is what makes
them defence in depth rather than a gap. **Two arms survived for a worse reason and were closed rather than argued with**: the heredoc stripper and the quoted-redirect guarantee had no case
that needed them, so the self-test gained one each.

### What neither mechanism can see

**The guard cannot know whether a session READ the output it was forced to keep.** It removes the
ability to discard a refusal; it cannot compel attention. **That is the residue, and it is smaller than the rule it replaces** — a session that must look at a refusal to get past it is in
a different position from one that was asked to remember to look.

**It sees one command at a time.** A write in one Bash call and a `>/dev/null` in the next is two
calls, and nothing joins them. **A heredoc that is never terminated drops the rest of the command**, which is the fail-open direction and the only honest reading of a string whose quoting
does not close.

**The coordinator cannot tell a check that will never start from one that has not started yet.**
Both are `not ready`, which is the conservative answer and the reason the block names which
required check is missing instead of only counting.

**Neither mechanism has caught a real instance yet**, because both were built the day the
failures happened. **The self-tests are what stand in for that** until one does.
