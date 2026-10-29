# D179 — Shell mistakes are refused by resolving them

A read-only audit asked of every written rule: has it been broken, and can a machine see it? Forty rules were mechanizable. Five are one command away from a session. Each has a measured incident. `scripts/guard-shell.py` enforces those five as a PreToolUse hook on Bash and on Write|Edit, armed in both tools' rosters (D135).

D173 is that audit's ruling: a rule that can be enforced mechanically is enforced mechanically, and a rule with no reader is advice. This entry records which five, what each cost, and where these readers are blind.

### Why a hook, not a rule (D171)

Each of the five was already written down when it was broken. That is not carelessness, and writing the rule a third time is not the remedy. Four were in a memory file the session had loaded. One is in CLAUDE.md twice. The latest: a session ran `git checkout CLAUDE.md` over its own uncommitted work, while `mutation-tests-need-a-bak-not-git-checkout` sat in its context.

D171: a rule is read once, at the start, then competes for attention with the work. So these five are mechanical. The audit's thesis: a rule phrased as an explanation to recall is recalled only when it is not needed.

### Amended: what Claude Code runs

The owner ruled that Claude Code runs `GUARD_SHELL_SKIP=checkout,stash,reset,tree scripts/guard-shell.py --hook` on Bash, and `GUARD_SHELL_SKIP=tree` on Write|Edit. The shared guard (`claude-settings` `hooks/guard.py`, rule 1, shared-tree) owns clauses 1, 2, 7 and 8 there. It refuses a checkout or restore over a modified path, a write into another checkout of this clone, a stash that takes another tree's entry, and a hard reset over uncommitted work. A write to a path in no checkout, such as the Claude app's side-session notes folder, passes there. Each is judged against its subject's state. The Claude-side copy was cut so one refusal speaks once. `.codex/hooks.json` runs all seven, because Codex runs no shared guard (D135). `GUARD_SHELL_SKIP` and its alias `--skip` name clauses by table name. An unknown name skips nothing. Clauses 3 and 4 are gone for both tools.

### The five, and what each cost

**1. `git checkout <path>` / `git restore <path>` over a modified file.** Three mutation cases used `sed -i.bak`. The fourth used `git checkout cli/cmd_reprice.py`. Nothing was committed. So the file reverted to HEAD, and about 240 lines of that session's work were lost. Every other file survived, so the loss first looked smaller than it was. The refusal names the `.bak` copy. The memory file prescribes that shape, and a session reaches for it when refused.

**2. A write outside this checkout.** An absolute-path `cd` prefix wrote about 1,500 lines into the owner's main checkout, on `main`, for most of a session. `make launch-agent`'s supervisor hot-reloaded that uncommitted code into the owner's live `:8000` capture server, repeatedly, while the owner used the app on the real store. The symptom was silent. It read as a different bug: the worktree's own dev server kept serving its unedited `app/`. This is D43's subject. Each checkout has its own store, ports and inventory. D43 left one door open. This clause closes it.

**3 and 4 are retired.** `gh api -f k=v` with no method is one. A field implies that a body exists, so gh sends POST. `ln -s` at an existing path is the other. The owner ruled both retired, with their hatches. The numbers stay as stable ids. Nothing renumbers.

**5. A polling loop.** Twice in one day, a session wrote a loop that never ended. A session that had read the rule four days earlier wrote `until ! pgrep -f 'scratchpad/drive.sh'`. It never went false. Its chained work never ran, and a second driver raced a live one for about 15 minutes. The other was a backgrounded `while`/`sleep` merge driver. It ran **119 rounds over 3 h 58 m**. The session had been compacted during the run. The driver raced that session's own hand-merges and re-resolved branches it was resolving. A person stopped it by noticing a four-hour bash in their own window.

D305 is the other half of that incident. This clause does not duplicate it. D305 teaches the sweep to ask whether anything still owns a process. A loop whose session is gone is offered up, not read as busy. This clause refuses the loop when it is created. D305 finds the one already running. Neither makes the other redundant. A poller started before this hook is D305's. A poller this hook refuses never becomes anybody's to find.

### The predicate is resolution

`git checkout main` and `git checkout CLAUDE.md` are the same verb. The first switches branch. The second destroys work. A backgrounded script's loop is not in the command. It is in the file. So the guard asks the system, read-only, as `scripts/reap.py:hook` does for a kill. `git status --porcelain` decides whether an operand is a modified path. `git rev-parse --verify` decides whether it is a commit. A backgrounded command's shell script is read. `reap.py`'s standard: `pkill -f capture_server.py` is allowed when the only match is yours. Here, `git checkout main` is allowed because `main` is not a file.

The Write|Edit half of clause 2 parses nothing. No shell form can skirt it. The payload carries a path. The path resolves. The comparison is against `checkout_root(cwd)`.

### Fail open on our own bugs, never silently

`reap.py`'s asymmetry holds. A broken guard fails open. An unreadable target is a command this guard has no opinion about. A parse error, a missing `git`, an unreadable payload, or a missing `scripts/shell_parse.py` each exit 0. No case fails closed. None of these five harms is unrecoverable the way a signal to a stranger's process is.

A pass the guard could not decide is printed. An operand that resolves to neither a path nor a commit says so. A checkout root it could not resolve says so. A guard that cannot tell "nothing to object to" from "I could not read this" has D171's failure class.

### Hatches: none is printed to an agent

`BANCHI_CHECKOUT`, `BANCHI_TREE`, `BANCHI_WAIT` and the later clauses' hatches each take `=off`, honoured in the environment. Each is the owner's to set. The owner ruled that a refusal never prints a blocked switch's name to an agent. It prints "owner-only: ask the owner to run this command". `clause_owner_only` refuses an agent's tool call that sets any real `BANCHI_*=off`, read by `_hatches_set`. So a mention passes.

Four recovery levers stay open to an agent. Each frees a stuck session: `BANCHI_KILL`, `BANCHI_SUITE_LOCK`, `BANCHI_SERVE_MAIN` and `BANCHI_SYNC`. They keep their printed names. The owner's terminal and CI are not tool calls, so the clause never sees them. The clause lives in `hook`, not `read_command`. The self-test's older cases call `hook(payload, owner_only=False)`. Only its owner-only cases call `--hook`. There is no switch for this clause.

**Known residual:** a Write of a script, then `bash script.sh`, sets a switch that no stage of a Bash command shows. The clause cannot see it. One switch for the whole hook would disarm the clause that guards uncommitted work, just to make a symlink. A hatch reached for by reflex is a guard already gone. The recovery the `cd` incident needed is one hatch away: `git checkout --` in the main tree, to unwind writes that landed there. The owner holds it.

### The parser is shared

`scripts/shell_parse.py` is `silent-write-guard.py`'s tokenizer, moved unchanged. That file took four defects to get right. A newline is not whitespace. An operator is not a quoted string. A heredoc body is a document. `#` is not always a comment. Each is a defect a second hand-rolled parser would ship again. CLAUDE.md's rule: ask whether the primitive exists before you design around its absence.

What did not move is any decision either guard makes. One is decidable from the string. The other resolves its subjects against the filesystem. Sharing the parse does not share the judgement.

### What this guard cannot see

- **`cp`, `mv`, `install`, `rsync` and `sed -i` destinations.** Clause 2 reads redirection targets and `tee` operands. Those five have positional destinations mixed with patterns and flags. A clause that guessed would refuse an ordinary copy. The Write|Edit half cannot be skirted.
- **`git checkout HEAD -- <path>`:** closed. See the amendment below.
- **A loop's bound is judged syntactically.** A counter, a deadline, a `break`, a `for` over a word list, or a wait on a pid all read as bounded. A `break` that can never be reached reads as bounded too. The clause aims at a loop with nothing at all to end it.
- **A Python or Node poller in a backgrounded script.** Only shell scripts are read, and only for shell loop grammar. `make up`'s supervisor and `make design-check ARGS=--wait` are long-lived loops this repo tells a session to start. A guard that guessed at other languages' loops would refuse the documented workflow.
- **Which process a pattern waiter matches.** BSD `pgrep` excludes itself and all its ancestors unless `-a` is given. procps excludes only itself. So whether a waiter matches itself depends on the machine. That is the argument for the clause, not a gap in it. A predicate that depends on that is not one a session can reason about. The refusal says so rather than claiming either platform's answer.
- **The self-test failed on one platform.** It passed 165 cases on the author's machine. It went red on the Linux runner in two arms, both fixture defects, not logic. The throwaway repo's default branch is whatever `init.defaultBranch` says: `main` here, `master` there. Two cases asked about a branch that did not exist, so the guard's correct "I have no opinion" read as a failure. The `pgrep` arm asserted BSD's exclusion rule as universal. **A green check proves its own platform, not "anywhere".** The fixture names its branch, asserts it, and refuses to score a case git itself rejected.

### AMENDED: a named source is not a hatch

The repealed sentence:

```
A named source is allowed, on the ground that it WRITES a known version rather than discarding an unknown one — which is the audit's own must-pass. The one spelling where that reasoning is thin is `HEAD` itself... It is allowed today and the hatch is not needed for it.
```

**What no longer holds, found by reproduction.** A coordinating session ran `git checkout origin/main -- .` to inspect a stray file on another ref. Its worktree's tracked files were clean at that instant, so the command passed by the clause's design. With one uncommitted edit, it would have discarded that edit with no refusal and no diffstat. The repealed text flagged this risk only for `HEAD`. It never checked any other source.

**A named source changes what is written, never whether a change is discarded first.** The original argument treated "known replacement" and "safe to overwrite" as one fact. They are not. A known replacement can still destroy an unknown loss. That day the owner's work survived because the tree was clean, not because of the guard. The opening section names the general failure: a rule enforced by memory is bypassed under exactly the conditions it exists for.

**Fix.** `_read_restore` no longer passes a named source automatically. It resolves path operands as the no-source form does. `clause_checkout` runs the existing `_modified` check whether or not a source is named. It refuses a checkout over a modified path for any source: `HEAD`, a branch, or any other ref. The message names the source. It says that naming it did not make the overwrite safe. A checkout over a clean path is unaffected.

**Proved by reproducing the near miss.** The self-test's two "names a source" cases were instances of the bug. Both ran against `work.py`, modified earlier in the fixture, and asserted `allows`. They are now `refuses` cases: `git checkout <sha> --` and `git restore --source=`. A new `allows` case uses their old name against `clean.txt`. The safe path is proven separately. 167 cases pass, up from 165 (2 rewritten, 1 added), with 0 failed.

### AMENDED: a sixth clause, because a named refspec sits outside git's net

Git refuses the bare form of this mistake, which is why it survives. `push.default=simple`, git's modern default, refuses a bare `git push` whose tracked upstream name differs from the current branch's name. It even prints the fix. But the refusal keys on the absence of a refspec, not on the mismatch. Once a caller names one, even the unqualified `HEAD` the printed fix offers, git treats it as an informed choice. It pushes to a branch of that literal name, creating one on the remote if none exists, silently.

That happened. A coordinating session resolving a merge conflict stood on a local branch a background agent had named `pr-h-readings-table-local`. The agent had pushed its squashed commit to the real PR branch under another name. So the local branch tracked `origin/claude/pr-h-readings-table`. Meaning to update the PR branch, the session ran `git push origin HEAD`. Git pushed `[new branch] HEAD -> pr-h-readings-table-local` to origin. The PR branch was untouched. No error was raised. The session caught it only because the next output looked wrong.

`clause_push` resolves the fact that git's own safety net already holds. `git rev-parse --abbrev-ref HEAD` gives the current branch. `branch.<name>.remote` and `branch.<name>.merge` give the tracked pair. They are read as git reads them, not re-derived from the command text. A push is refused when three things hold. Its remote matches `branch.<name>.remote`. Its lone refspec is an unqualified `HEAD` or the branch's own literal name. The tracked name differs.

Everything else passes as before. A branch with no configured upstream (an ordinary first push). A name matching its upstream. An explicit `HEAD:<branch>`. A push to a remote the branch does not track (a fork workflow). `--all`, `--mirror`, `--tags` and `--delete`, which push something other than this branch under its own name. `BANCHI_PUSH=off` is its hatch, honoured in both forms.

Reproduced, not argued. `scripts/guard-shell-selftest.sh` builds a real bare origin. It pushes a branch under one name while its tracking points to a differently named branch. That is the incident's mechanism, `git push -u origin <local>:<remote>`. The guard is asked about that mismatch. The cases the ordinary first push, a matching upstream and fork workflows must never trip are asked too.

### AMENDED: the ordinary first push of a feature branch was refused, and its printed remedy pushed to main

The exemption above names "no configured upstream at all (the ordinary first push of a new branch)". A branch cut the way this repo makes one does get an upstream. `git switch -c <name> origin/main` sets `branch.<name>.merge` to `refs/heads/main` at creation. So the most common shape here, cut from `origin/main` and then `git push -u origin <that-name>`, had a tracked-versus-named mismatch. The rule meant to protect it refused it. Its two-line remedy read:

```
git push                       # let git's safety net name the fix
git push origin HEAD:main      # push to the branch actually tracked
```

Both lines push to `main`. The second names it outright. For the ordinary case, the guard told the operator to do what D42, `scripts/githooks/pre-push`, `scripts/githooks/reference-transaction` and GitHub branch protection exist to prevent. Other guards would have caught the result, and this was never a live incident. A refusal whose remedy is the forbidden act teaches the wrong reflex. `no-bandaids` and D171 hold this repo to that standard.

The fix exempts only the shape that was never the incident. `pr-h-readings-table-local` tracked `origin/claude/pr-h-readings-table`, a different feature branch, so it stays refused. `_default_branch(remote, cwd)` answers what this checkout treats as `<remote>`'s default. It prefers git's own record, `refs/remotes/<remote>/HEAD`, which a real `git clone` or `git remote set-head <remote> -a` sets. If that ref was never written, it falls back to the claude-settings sweep's rule for the primary checkout. That rule takes the first of `main`, `master` that exists as a local branch. Nothing is guessed. An unreadable remote and an absent local branch both answer `""`, which never equals a real tracked name. That case is refused as before. `clause_push` exempts a mismatch only when `tracked == _default_branch(remote, where)`. Every other mismatch, including the incident's, reaches the refusal unchanged.

Why git's record comes first: the claude-settings sweep answers this question for the primary checkout, so a hardcoded `"main"` would be a second, divergent answer. `janitor.py`'s answer is local-only. This clause asks about a specific remote, and a fork's default can differ from `origin`'s. So `refs/remotes/<remote>/HEAD` is asked first. The local guess runs only when that ref was never written. That covers this guard's own fixtures and any `git init`-then-`push` clone that never ran `git clone` or `git remote set-head`.

Reproduced red first, in a real throwaway repo. A branch made with `git switch -c feature-x origin/main`, then pushed with `git push -u origin HEAD`, was refused (`exit 2`), with the remedy naming `HEAD:main`. After the fix, the same sequence exits `0`. `scripts/guard-shell-selftest.sh` checks both directions. The fixture switches to a branch cut from `origin/main`. It asserts the upstream is `refs/heads/main` before it trusts the case. It asserts the push is never refused, with or without `-u`. It asserts no still-refused case's remedy names the default branch. It sets `refs/remotes/origin/HEAD` by hand, as a real `git clone` would, so the primary read runs and not only the fallback. The incident reproduction and its five must-never-refuse cases are unchanged and pass. Those five are a fresh branch with no upstream, a matching upstream, a different remote, `--all`, `--tags` and `--delete`, and a detached HEAD.

Mutation-tested. The sixth clause's original count is untouched: six arms over the colon check and refspec resolution, five caught, one equivalent mutant. A colon-bearing refspec can never equal `HEAD` or a bare branch name, so the colon check's guard is never reached. This amendment's logic was mutated eight more ways and re-run against the full selftest. Equality flipped to `!=`: caught, 14 failures. Exemption deleted: caught, 4 failures, the original bug reproduced. `branch` read instead of `tracked`: caught, 4. Always exempt: caught, 10. `main` dropped from the local fallback: caught, 3. The `<remote>/` prefix not stripped from a real `origin/HEAD` symbolic ref: caught, 1. Two survive, and both are equivalent. Swapping the fallback order to `("master", "main")` and corrupting the symbolic-ref path's ref name both still land on `"main"`. Every fixture branch is `main`, never `master`. A repo whose local branch and remote default disagreed would tell them apart. None built here does. Fourteen arms across both amendments: eleven caught, three equivalent-mutant survivors. That replaces the "six arms, five caught" figure CLAUDE.md published before this amendment, which covered only the colon check.

### AMENDED: a quoted script is not a command

Clause 2 refused this command from a real session:

```
node -e '
const hits=s.filter(i=>/[·•]/.test(String(i.text)));
' out.json
```

It named `/[·•]/.test` as a write target. That is a regular expression literal inside a single-quoted script. The command writes nothing. The cause was in the shared reader. `shell_parse.tokenize` fed shlex one line at a time. The middle line of a multi-line quoted argument balances as far as that line can tell. So it tokenized as a command with a `>` in it. A guard that goes red when nothing is wrong is spent. The parent's CLAUDE.md says so. This refusal prints its own hatch.

**The fix is at the resolution point, and it is the parent's.** `~/Developer/claude-settings/hooks/guard.py` solved this in three functions. `split_segments` carries quote state across newlines. `resolve_command` finds the real command word. It skips assignments, wrappers with their flags, and loop keywords. `strip_heredoc_bodies` treats a body as data unless an interpreter runs it. All three are copied into `scripts/shell_parse.py` and marked as lifted. The parent's `a-gates-allow-list-is-the-constant.md`, pattern 1, is the reason not to re-derive. A hand-rolled copy of the resolver there fixed the false positive. It produced a false negative on `git -C <dir> commit`.

Two things are this repo's own, and the code names each. The splitter takes the set of delimiters it cuts on, because the second reader needs the pipe kept. It also carries the shell's comment rule. The parent's loop reads the `'` in `# the driver's shape` as opening a quote. That was measured on this guard's runaway-driver fixture. The fixture went from refused to allowed once the parent's loop replaced the per-line reader. That blind spot is the parent's to fix first.

**Every clause shared the blind spot, because every clause reads the one parse.** Four shapes were allowed before the lift and refused after it. `env -i tee <other>/f` and `xargs tee <other>/f` passed, because `strip_prefixes` stopped at a wrapper's own flag. `if tee <other>/f; then` passed, because a keyword was not a prefix. `bash <<'EOF' … echo x > <other>/f … EOF` passed, because an interpreter's body was stripped as prose. `sudo -n git stash` passed for clause 7. One shape is still allowed, and it is the parent's limit too. A wrapper flag that takes a value, as in `sudo -u root tee f` or `nice -n 10 tee f`, resolves to the value.

**The incident's own spelling was never refused.** The `cd` incident was `cd <main checkout> && …`, with every write after it relative. A relative target resolved against the session's cwd. The stages are now walked in order. A `cd` moves the directory that later targets resolve against. A `cd` into another checkout is refused as an act too. The Bash tool's cwd persists between calls. `npm run build` writes with no `>` for a redirect reader to see. The predicate is resolution: `git rev-parse` at the target. A temp directory, `~/.claude`, a plain directory and this checkout's own subdirectories pass. `cd -` and `cd $VAR` get no opinion. Only a different checkout is refused. The read-only forms the refusal recommends never need the `cd`. `git -C <other> <write verb>` remains a declared gap.

`scripts/guard-shell-selftest.sh` pins the false positive in four spellings and each real write above. The next edit cannot trade one for the other.

`_sanctioned_outside` lists the folders outside the checkout where a write passes: `/dev`, `~/.claude`, a temp directory that is no checkout, and `~/Library/Application Support/Claude-Work/side-session-notes/`. The notes folder holds a space. Quoted and backslash-escaped spellings both pass, and a sibling folder is still refused.

### Every hatch use is logged, and the push remedy names the branch's own name

The owner ruled: log and surface every `BANCHI_*=off` use. A hatch lifts its guard and prints nothing, so a run of hatch uses was invisible. `guard-shell.py --hook` sees every Bash command, so it is the one home.

A command can set any `BANCHI_<NAME>=off` by env prefix, `export`, or `env`. The hook reads that from the parsed stages. A mention in an argument, a comment or a heredoc is not a use. `_off` reads the same parsed set, so a hatch counts only as a real assignment. Every hatch a command sets is logged. A mention never lifts a guard. The three scope switches take `=all`, not `=off`. They only add checks, so they are not hatches and the log never counts them. A hatch honoured from the environment is not logged here. `make status` names it under `hatches`.

The hook appends one line per name to `banchi-hatches.log` in `git rev-parse --git-common-dir`. Every worktree of the clone shares that file. A line holds the time, the hatch, the checkout, the branch and the first 120 characters of the command. The log never changes a verdict. It fails open on any logging error. `make status` prints the last 24 hours (name, checkout, branch), or nothing when there are none. The self-test pins that a hatch command writes one line and a plain command writes none.

The push clause's printed remedy names the branch's own name. It prints `git push -u <remote> HEAD:<branch>` and never the upstream it refused, since a refusal's remedy never names the forbidden target. A push that names the branch's own name as its destination lands on that name, so the clause allows it. `HEAD` stays refused when the upstream is a different non-default branch.

### Every refusal is logged, so a rule is judged by how often it fires

The owner ruled: log every deny or ask. `scripts/refusal_log.py` is the one helper. Each guard imports it, and the shell hooks call its CLI. It appends one line per refusal to `banchi-refusals.log`, beside the hatch log. A line holds the time, `guard:rule` (one stable id per clause), a snippet of at most 80 characters, the session id and the checkout. The snippet is a heading, a path or a masked verdict, never a whole command.

The guards that write it are `guard-shell.py`, `reap.py --hook`, `silent-write-guard.py`, `guard-opsec.sh`, and the three hooks in `scripts/githooks/` that refuse. One `O_APPEND` write per line keeps concurrent agents apart. The log only records. It fails open. A log that cannot be written never changes a verdict or an output. `BANCHI_REFUSAL_LOG` names a file instead of the common-dir default. Each self-test uses it to point the log at a fixture and at an unwritable path. `make status` prints the last 24 hours per rule on one line, beside the hatch lines.

### Standing

**BUILT and self-tested**: seven clauses, `scripts/guard-shell-selftest.sh` with four reproductions, the swept allow list, every hatch in both forms, and the fail-open floor. **RECORDED**: this entry, `docs/map.py`, CLAUDE.md, `scripts/checks.py` and both hook rosters. **NEITHER**: nothing. What is unproven is what every hook here shares. `silent-write-selftest.sh` says so in as many words. The harness invokes the hook, and exit 2 blocks a call. Both are the harness's behaviour, not this repository's.
