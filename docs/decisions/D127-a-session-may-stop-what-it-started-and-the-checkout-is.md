## D127 — A session may stop what it started, and the checkout is what decides which that is

**Built 2026-09-10, after two incidents in a single session**, both while cleaning up dev
servers the session had itself launched.

1. `pkill -f "capture_server.py"`, meant for a scratch capture server started in a worktree. It
   is machine-wide, so it also matched
   `/Users/shivinate/Developer/pkmnscan/server/capture_server.py` — the owner's live capture
   server on :8000 over their real 1,625-card store, the process **D53** exists to keep alive at
   login. The supervisor restored it 25 seconds later and **D88** meant the store itself survived,
   every write being one SQLite transaction; any request in flight was severed.
2. `for p in $(lsof -ti tcp:5439); do kill $p; done`, meant for the session's own Vite server.
   `lsof -ti tcp:PORT` returns every process holding a socket on that port, **which includes CLIENTS**. The second pid was the Claude desktop app's network-service helper. Electron
   started it again; the app's network went down in between.

**NEITHER WAS A LAPSE OF CARE, AND THAT IS THE ENTIRE ARGUMENT FOR MECHANISM.** Both commands are
the obvious spelling of a correct intent. What is wrong with them is invisible in the text: the
first has a blast radius that depends on what else happens to be running, and the second has a
blast radius that depends on who happens to be connected. A more careful session types the same
two commands.

**THREE SESSION NOTES ALREADY WARNED ABOUT THIS CLASS AND IT HAPPENED TWICE ANYWAY.** This
project's memory carries `pkill-f-is-machine-wide.md` (a worktree cleanup that killed the main
tree's servers), `dont-bounce-the-owners-servers.md` (the `restart` target killing the live capture
server mid-request) and `a-pgrep-waiter-matches-itself.md`. **A note that has to be remembered is not a guard**, which is the preference this repo already acts on everywhere else — D16 checks the
docs mechanically rather than asking, D42 refuses a move of `main` in a hook rather than in a
sentence, D111 sweeps rather than reminding.

### The rule

**Every process an agent session legitimately needs to kill was started BY that session**, and
it lives under the checkout that session is working in. Everything it must never kill lives somewhere else: the
main checkout's capture server, another worktree's servers under a different
`.claude/worktrees/<name>/`, the desktop app, Chrome, and every other thing on the machine.

That is not a heuristic. It is a property of how this repo is worked in, and **D43 is what makes it true** — that entry gave every checkout its own store and its own ports, so a session's own
processes are already segregated by path. This entry spends that segregation a second time.

**So the guard does not read intent; it RESOLVES the command's real targets.** `scripts/reap.py
--hook` runs `pgrep` and `lsof` itself, read-only, and judges each pid it gets back:
does any absolute path in that process's argv, or its working directory, live under this
checkout? **`pkill -f capture_server.py` is therefore ALLOWED when the only match is yours**, and refused
when it is not — the same command being right on Monday and wrong on Tuesday, which is
exactly the fact no reading of the string could ever have carried.

**A loop variable is answered by the clause beside it.** `kill $p` cannot be resolved, but
`for p in $(lsof -ti tcp:5439); do kill $p; done` has the port sitting in plain sight, so the
question the guard asks is *what pids could this command be about* rather than *what is this
kill's argument*. The producers — `pgrep`, `lsof -ti`, a `pkill` pattern, a `killall` name — are
resolved wherever they sit in the command.

### What it lets past, because a guard that breaks cleanup is one that gets switched off

CLAUDE.md's own line about inline lint disables applies here: **a guard that is routinely bypassed is worse than none.** So the shapes a session actually needs are allowed outright and
were cases in the self-test before the refusals were:

- **its own processes**, which is most of what a session ever kills;
- `kill -0` and `kill -l`, which send no signal — refusing a liveness probe would break the
  ordinary way a session waits for a process to exit;
- `%1` and `$!`, which name a job of the one-shot shell running the command and are therefore
  provably the session's own;
- **the body of a heredoc**, because writing a script that mentions `pkill` is an ordinary thing
  to do and a guard that reads a document as a command fires on the one class of command that can
  kill nothing at all.

### Two refusals it makes that its own rule does not

**A target it cannot place is refused** — no absolute path in the argv and no readable working
directory. Missing evidence is never read as absence of a problem; `janitor.py:_same_process`
takes the same direction, and for the same asymmetry: a false refusal costs a session one extra
sentence, a false permission costs the owner a process they were using.

**The main checkout's supervisor and its children are refused even from inside it** — where the rule above would clear them. This is D53 written as a set of integers:
`scripts/serve.py` records each child's pid under `.serve/*.pid`, and the guard reads each
`.pid` marker and walks down the process tree from them — down, because the supervisor re-execs and
replaces its children, so a child can be running before the pidfile naming it is rewritten. The
refusal names `make down ARGS=--confirm`, which **drains**, rather than a harder kill.

**IT COSTS 35 ms ON A BASH CALL IT HAS NO OPINION ABOUT**, measured over five runs on this
machine, and that is almost entirely Python's own start-up: the first thing it does is a
substring test for the three command words, and most commands do not contain one. A command it
does have to judge costs 103 ms, which is `pgrep` and `lsof` and a `ps` — paid only on the
commands that could kill something. A hook on EVERY Bash call has to justify its floor, so the
floor is the number worth writing down.

### The asymmetry that keeps it enabled

**A broken GUARD fails open; an unreadable TARGET fails closed.** The first is `guard-opsec.sh`'s
hard-won rule, taken here unchanged and for its reason — that guard was disabled inside a day
when it blocked on its own bugs, and a disabled guard protects nothing. The second is not the
same thing wearing a different hat: it is the guard being *right that it does not know*, which is
a determination about the world and not a defect in the code.

**The escape hatch is `PKMNSCAN_KILL=off` and every refusal prints it**, per the house convention
`PKMNSCAN_MAIN=off` set. It is sized to be reached for rarely rather than made hard: everything
provably yours is already allowed, so a session that wants the hatch is doing something unusual
and should notice that it is.

### One file, two faces, one predicate

`scripts/reap.py` is both the hook and the tool the hook recommends. **That is the point rather than a convenience**: a guard that refuses on one notion of "safe to kill" while the tool it names
uses another is a guard people learn to route around. `make reap` previews everything running
under this checkout, `--confirm` stops it, and `port:N` / `match:X` / `pid:N` narrow it —
**and it prints what it refused and why**, which is the half a `pkill` that quietly does the right
thing on a good day can never do.

**IT DOES NOT DUPLICATE `janitor.py`, AND IT WAS BUILT NOT TO.** D111's sweep owns the
neighbouring question — what a FINISHED session left behind, on its own schedule, across trees
and branches and orphans. This owns one signal at the moment it is sent. What they share is the
reasoning, and where the shapes matched the code was copied WITH its argument rather than
re-derived: `_real` and its symlink trap, the process table, the leader-only `killpg`. Neither
grew a second, disagreeing notion of what is safe to stop.

**It imports nothing from this tree**, for `janitor.py`'s reason: `make janitor-install` copies
both out to the user's own `~/.claude` so a user-level hook covers every project on the machine, and a copy
that imported from this checkout would be broken everywhere else. **The repo's own `.claude/settings.json` carries the hook as well**, so the guard is armed in this tree and in
every worktree cut from it with no per-machine step at all — the two halves being the same
bargain `make hooks` and `make janitor-install` already make, and `make status` compares the
installed copy byte for byte.

### Amended 2026-09-10, the same day: a root may not be a directory that contains everything

**The user-level install exposed a hole the repo-level one structurally could not.** Inside a
clone `git rev-parse --show-toplevel` always answers, so `checkout_root`'s fallback — the current
directory, when there is no git top level — never ran. The moment `make janitor-install` put this
hook in the owner's own `~/.claude/settings.json` it began firing in directories that are not
repositories at all, and there the fallback **adopted the home directory as "this checkout"**.

**Measured from `/Users/shivinate` on the owner's Mac, minutes after the install:** `pgrep -f
capture_server.py` — the literal command of incident 1 — resolved their live `:8000` server to
**OURS**, because `~/Developer/pkmnscan/server/capture_server.py` is under `~`. The guard would
have cleared the exact kill it was built to refuse.

**A root has to be a place work is DONE, not a place work is KEPT.** `_too_broad` rejects the home
directory, every ancestor of it, `/`, and the system directories; with no honest root the answer is
not a wider guess but that this file has nothing to reason with, and `_under` already reads an
empty root as "nothing is under it" — so every target is refused and the hatch is printed, which is
the direction every other unknown here resolves in. An ordinary non-repo directory is still a
workspace, because a session outside a clone must still be able to clean up after itself.

**THE FIRST TWO ATTEMPTS AT THE TEST FOR THIS PASSED WITHOUT SEEING ANYTHING**, and that is worth
recording beside the fix. Both judged `$stranger`, which lives under the fixture's `mktemp -d` —
on a Mac that is `$TMPDIR` in `/var/folders`, under neither `$HOME` nor `/tmp` — so a broad root
would not have claimed it either and the cases were vacuous. Three mutation arms survived, which
is the only reason anyone found out.
**Every case now puts a process inside the directory it is testing**, and `$HOME` is faked into
the fixture rather than used — the only way to have a subject under a home directory without
starting one under the owner's real home.

**A redundancy no test can distinguish is not defense in depth.** The first `_too_broad` had two
arms — a fixed list, and a separate home-and-ancestors check — and on a standard Mac layout every
case either could pose was caught by both, so removing one changed no verdict. They are one set
now, and the cases separate the list (`/private/tmp`) from the walk (a home directory placed
somewhere the list does not reach).

### What it does not cover, said out loud

- **A kill inside a script.** The hook reads the Bash command it is handed; `bash cleanup.sh` is
  one word to it. That is the same limit `guard-opsec.sh` has and is not fixable at this layer.
- **A command that resolves one set and signals another** — `X=$(pgrep -f mine); kill $OTHER`.
  No reading of a string catches that, and no session has written it by accident.
- **A kill placed after a heredoc's terminator**, dropped with the heredoc body. The trade is
  deliberate and costs one extra line in a session's script.
- **`os.kill` in a `python3 -c`**, which is not in the trigger set. Adding it would trade a real
  false-positive rate against a case nobody has hit.

`make reap-selftest` proves the rest against a throwaway checkout, a throwaway sibling standing in
for everywhere-else, a real socket with a real client on it, and a `.serve/` pidfile — both
incidents reproduced rather than asserted about. **Mutation-tested: thirteen guards removed one at a time, all thirteen caught.** D18 keeps it out of the git hook and in `make check`, beside
`janitor-selftest`, for the reason that entry gives — it writes, and it signals.
