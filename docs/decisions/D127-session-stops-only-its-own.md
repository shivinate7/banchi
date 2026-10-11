## D127 — A session stops only what it started

**Built after two incidents in a single session.** Both happened while cleaning up dev servers the session had launched itself.

1. `pkill -f "capture_server.py"` targeted a scratch capture server started in a worktree. `pkill -f` is machine-wide. It also matched `/Users/shivinate/Developer/banchi/server/capture_server.py`, the owner's live capture server on :8000 over their real 1,625-card store. That process is the one **D138** keeps alive at login. The supervisor restored it 25 seconds later. **D88** kept the store intact, because every write is one SQLite transaction. Requests in flight were severed.
2. `for p in $(lsof -ti tcp:5439); do kill $p; done` targeted the session's own Vite server. `lsof -ti tcp:PORT` returns every process holding a socket on that port, **including CLIENTS**. The second pid was the Claude desktop app's network-service helper. Electron started it again, and the app's network went down in the meantime.

**Neither was a lapse of care.** Both commands are the obvious spelling of a correct intent. What is wrong with them is not visible in the text. The first has a blast radius that depends on what else is running. The second has a blast radius that depends on who is connected. A more careful session types the same two commands.

**Three session notes already warned about this class, and it happened twice anyway.** The project memory carries `pkill-f-is-machine-wide.md`, `dont-bounce-the-owners-servers.md` and `a-pgrep-waiter-matches-itself.md`. **A note that must be remembered is not a guard.** This repo already acts on that preference everywhere else. D16 checks the docs mechanically rather than asking. D42 refuses a move of `main` in a hook, not in a sentence. The claude-settings sweep, "The janitor is one machine-wide sweep" (claude-settings decisions/the-janitor-is-one-machine-wide-sweep.md), sweeps rather than reminds.

### The rule

**Every process an agent session needs to kill was started BY that session.** It lives under the checkout that session works in. Everything the session must never kill lives somewhere else. That includes the main checkout's capture server. It includes another worktree's servers under a different `.claude/worktrees/<name>/`. It includes the desktop app, Chrome, and everything else on the machine.

This is not a heuristic. It is a property of how this repo is worked in. **D43 makes it true.** D43 gave every checkout its own store and its own ports, so a session's processes are already separated by path. This entry uses that separation a second time.

**So the guard does not read intent. It RESOLVES the command's real targets.** `scripts/reap.py --hook` runs `pgrep` and `lsof` itself, read-only. It judges each pid it gets back. Does any absolute path in that process's argv, or its working directory, live under this checkout? So `pkill -f capture_server.py` is ALLOWED when the only match is the session's own. It is refused when it is not. The same command is right on one day and wrong on another. No reading of the string could carry that fact.

**A loop variable is answered by the clause beside it.** `kill $p` cannot be resolved alone. But `for p in $(lsof -ti tcp:5439); do kill $p; done` has the port in plain sight. So the guard asks what pids the command could be about, not what the kill's argument is. The producers are `pgrep`, `lsof -ti`, a `pkill` pattern and a `killall` name. The guard resolves them wherever they sit in the command.

### What it lets past

A guard that breaks cleanup gets disabled, and a disabled guard protects nothing. So the shapes a session needs are allowed outright. CLAUDE.md's rule on inline lint disables applies here: a guard that is routinely bypassed is worse than none. These shapes were cases in the self-test before the refusals were:

- **its own processes**, which is most of what a session ever kills;
- `kill -0` and `kill -l`, which send no signal. Refusing a liveness probe would break the ordinary way a session waits for a process to exit;
- `%1` and `$!`, which name a job of the one-shot shell running the command, so they are provably the session's own;
- **the body of a heredoc.** Writing a script that mentions `pkill` is ordinary. A guard that reads a document as a command fires on a class of command that can kill nothing at all.

### Two refusals its own rule does not make

**A target it cannot place is refused.** That covers a command with no absolute path in the argv and no readable working directory. Missing evidence is never read as absence of a problem. `janitor.py:_same_process` takes the same direction, for the same asymmetry. A false refusal costs a session one extra sentence. A false permission costs the owner a process they were using.

**The main checkout's supervisor and its children are refused, even from inside it.** The rule above would clear them. This is D138 written as a set of integers. `scripts/serve.py` records each child's pid under `.serve/*.pid`. The guard reads each `.pid` marker and walks down the process tree from it. It walks down because the supervisor re-execs and replaces its children. So a child can run before the pidfile naming it is rewritten. The refusal names `make down ARGS=--confirm`, which **drains**, instead of a harder kill.

### Cost

On a Bash call it has no opinion about, the guard costs 35 ms. Measured over five runs on this machine, almost all of that is Python's own start-up. The first step is a substring test for the three command words, and most commands contain none. A command it must judge costs 103 ms. That cost is `pgrep`, `lsof` and a `ps`, paid only on commands that could kill something. A hook on EVERY Bash call has to justify its floor, so the floor is the number worth writing down.

### The asymmetry that keeps it enabled

**A broken GUARD fails open. An unreadable TARGET fails closed.** The first is `guard-opsec.sh`'s rule, taken here unchanged and for its reason. That guard was disabled inside a day when it blocked on its own bugs. The second is not the same rule. It is the guard being right that it does not know. That is a fact about the world, not a defect in the code.

**The escape hatch is `BANCHI_KILL=off`, and every refusal prints it.** It follows the house convention `BANCHI_MAIN=off` set. It is sized to be reached for rarely. Everything provably the session's own is already allowed. A session that wants the hatch is doing something unusual, and should notice that it is.

### One file, two faces, one predicate

`scripts/reap.py` is both the hook and the tool the hook recommends. **That is the point, not a convenience.** A guard that refuses on one notion of "safe to kill" while the tool it names uses another gets bypassed. `make reap` previews everything running under this checkout. `--confirm` stops it. `port:N`, `match:X` and `pid:N` narrow it. **It prints what it refused and why.** That is the half a `pkill` cannot do.

**It does not duplicate `janitor.py`, and it was built not to.** The claude-settings sweep owns the neighbouring question. That is what a FINISHED session left behind, on its own schedule, across trees, branches and orphans. This entry owns one signal at the moment it is sent. The two share their reasoning. Where the shapes matched, the code was copied WITH its argument, not re-derived. That covers `_real` and its symlink trap, the process table, and the leader-only `killpg`. Neither grew a second, disagreeing notion of what is safe to stop.

**It imports nothing from this tree**, for `janitor.py`'s reason. Both stay repo-agnostic, so a hook can point them at any checkout. **The repo's own `.codex/hooks.json` carries the hook.** The guard is armed in this tree and in every worktree cut from it. No per-machine step is needed. The repo's copy is the only one, and it runs from `scripts/`. `.claude/settings.json` does not carry it, on the owner's word. The shared layer's machine-wide-kill rule owns the Claude side.

### Amendment: a root may not be a directory that contains everything

**The user-level install exposed a hole the repo-level install could not show.** Inside a clone, `git rev-parse --show-toplevel` always answers. So `checkout_root`'s fallback never ran. That fallback is the current directory, used when there is no git top level. Once a user-level hook ran this guard, it fired in directories that are not repositories at all. There, the fallback **adopted the home directory as "this checkout"**.

**Measured from `/Users/shivinate` on the owner's Mac, minutes after the install.** The literal command of incident 1, `pgrep -f capture_server.py`, resolved the owner's live `:8000` server to OURS. `~/Developer/banchi/server/capture_server.py` is under `~`. The guard would have cleared the exact kill it was built to refuse.

**A root must be a place work is DONE, not a place work is KEPT.** `_too_broad` rejects the home directory, every ancestor of it, `/`, and the system directories. With no honest root, the answer is not a wider guess. This file has nothing to reason with. `_under` already reads an empty root as "nothing is under it". So every target is refused, and the hatch is printed. Every other unknown resolves in the same direction. An ordinary non-repo directory is still a workspace. A session outside a clone must still be able to clean up after itself.

**The first two tests for this passed without checking anything.** Both judged `$stranger`, which lives under the fixture's `mktemp -d`. On a Mac that is `$TMPDIR` in `/var/folders`, under neither `$HOME` nor `/tmp`. A broad root would not have claimed it either, so the cases were vacuous. Three mutation arms survived. That is the only reason anyone found out.

**Every case now puts a process inside the directory it tests.** `$HOME` is faked into the fixture, not used. This is the only way to have a subject under a home directory without starting one under the owner's real home.

**A redundancy no test can tell apart is not defense in depth.** The first `_too_broad` had two arms: a fixed list, and a separate home-and-ancestors check. On a standard Mac layout, every case either could pose was caught by both. Removing one changed no verdict. They are one set now. The cases separate the list (`/private/tmp`) from the walk (a home directory placed where the list does not reach).

### What it does not cover

- **A kill inside a script.** The hook reads the Bash command it is handed. `bash cleanup.sh` is one word to it. `guard-opsec.sh` has the same limit, and this layer cannot fix it.
- **A command that resolves one set and signals another**, such as `X=$(pgrep -f mine); kill $OTHER`. No reading of a string catches that. No session has written it by accident.
- **A kill placed after a heredoc's terminator**, dropped with the heredoc body. The trade is deliberate. It costs one extra line in a session's script.
- **`os.kill` in a `python3 -c`**, which is not in the trigger set. Adding it would trade a real false-positive rate against a case nobody has hit.

`make reap-selftest` proves the rest against a throwaway checkout and a throwaway sibling. The sibling stands in for everywhere-else. The test uses a real socket with a real client on it, and a `.serve/` pidfile. Both incidents are reproduced, not asserted about. **Mutation-tested: thirteen guards removed one at a time, and all thirteen were caught.** D18 keeps it out of the git hook and in `make check`, beside `janitor-selftest`, as that entry explains. The guard writes, and it signals.

### Amendment: "under this checkout" is no longer "one session's"

Two sessions can now stand in one checkout. An agent session lost its worktree, carried on inside another session's, and ran a blanket `--confirm` there. That sweep did what this entry describes, and it still stopped a process it should not have. The process was the owning session's own pre-push check. `D305` reads OURS a second way: by WHO started it, not only by WHERE.

This entry's full-checkout sweep stands for the top-level session driving a call by hand. A subagent's blanket sweep is narrowed to its own tag. Read D305 before you change ownership here.
