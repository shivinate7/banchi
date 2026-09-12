## D169 — The blanket sweep asks the question the verdict answers, and a nested worktree is another checkout

**`make reap` with no target could not see a process started by a relative path, so a live capture server under the checkout was resolved as nothing at all — and the fix is to make the sweep's notion of "under this checkout" the same one the verdict already uses, because two notions inside one guard is the failure this file was written to be incapable of.**

### The report, and what it actually was

From a session in the worktree `.claude/worktrees/agent-ad0e31c1fa1389a92` on 2026-09-12, with both `make dev` and `make server` running on that checkout's own derived ports: a bare `make reap ARGS=--confirm` **stopped the Vite pair and did not list the capture server at all**. `make reap ARGS="port:8301 --confirm"` then stopped it.

The report speculated that D53's main-checkout carve-out might be firing inside a worktree. **It is not, and that was established before anything was changed.** `protected_pids` globs `<main checkout>/.serve/*.pid` and nothing else; measured from a worktree with both servers live, the main checkout's supervisor and capture server judged **MAIN** and this worktree's judged **OURS** the moment it was named. The carve-out is keyed exactly where D53 puts it.

**A second session then reported the same symptom and was wrong about it** — its subject was `zsh -c '… make server 2>&1 | tail -20'`, a pipeline that hangs before any server exists, so reap was correct and there was nothing to find. That is a real trap and it is why this entry leads with the reproduction rather than the report.

### The reproduction

In a linked worktree with `make server` started with no pipe after it, its working directory confirmed with `lsof -a -d cwd -p <pid> -Fn`:

```
$ python3 scripts/reap.py
  resolved: everything running under this checkout -> 0 process(es)
  nothing to stop.

$ python3 scripts/reap.py port:8235
  would stop  pid 57983  … Python server/capture_server.py
```

**Three orphaned `capture_server.py` from three different trees were running on the machine at that moment**, one of them under a `/private/tmp` fixture directory. That is what the miss leaves behind, and it is the harm D127 exists to prevent: the next session's `make server` in that tree hits EADDRINUSE, or a stale server goes on answering over a store the branch has since changed.

### The cause: one file, two notions

`verdict_for` places a pid by an argv path under the root **or** by a working directory under it, and `_cwds_of`'s docstring says in as many words why the second arm is there — *"a process launched by a relative path carries no absolute path in its argv at all — `npm` and `node` routinely do"*.

**`pids_under` — the blanket resolver — read argv alone.** So the sweep could only ever offer the verdict those pid values the verdict's FIRST arm would have caught, and every process the second arm exists for was invisible to it before any judgement was reached.

`make server` is exactly such a process. The Makefile runs `$(PYTHON) server/capture_server.py`, and `$(PYTHON)` is `.venv/bin/python` — **neither token is absolute**, so a live capture server's command line carries nothing under any checkout. `make dev` was resolved throughout because npm writes its argv absolutely. **The gap therefore presented as "reap sees Vite and not Python", which reads like a carve-out and is not one.**

This is the disease reap.py's own header names: *"a guard that refuses on one notion of 'safe to kill' while the tool it recommends uses another is a guard people learn to route around."* It had that disease internally.

### The rule, and the two rules it is not

`_placed_under` is now the sweep's one predicate, and it has two arms:

- **arm one** — an ABSOLUTE path in argv under the root. Unchanged, and it stands alone: a process can run this checkout's code from anywhere, and one whose script has since been DELETED still names it.
- **arm two** — a RELATIVE token that, resolved against the process's own working directory, names an existing **FILE** under the root.

**Both halves of "existing file" were measured on the rig's process table, and each rejects a different false positive:**

| rule | what it selects in a worktree with one live server |
|---|---|
| argv absolute only (before) | **0** — the defect |
| working directory under root | 6, including the Claude Code session and the sweep's own shell |
| joined token, no existence test | 4, including the Claude Code session — `2>/dev/null` inside a `zsh -c` script joins onto any working directory |
| joined token, exists | 3 — the bare word `server` in `make server` resolves to the package DIRECTORY |
| **joined token, exists and is a file** | **1 — the capture server, and nothing else** |

**A bare working-directory match was the obvious fix and is the wrong one.** From the owner's main checkout it proposed **55 processes**, three of the first five being the session doing the sweeping. A flag is not skipped by name: `<root>/-v` is not a file, and every mutation of a `-` skip survived, so it was deleted under `_too_broad`'s own ruling that redundancy no test can distinguish is code whose deletion nothing would notice.

### Two things the widening made acute, both fixed here

**THE SWEEP MAY NOT SIGNAL THE SESSION RUNNING IT.** An agent's shell carries an absolute `cd` into the checkout in its own argv, so **arm one already placed it** — a bare `--confirm` from the main checkout would have stopped the shell it was typed into, and with it the turn and the session. `_ancestors` passes over this process's chain, and only the chain: excluding the whole tree below the top ancestor would exclude the servers themselves, since a `make server` sent to the background from a session's shell is a descendant of that session. The residue is a SIBLING shell — another tool call in the same checkout — which nothing can distinguish from any other process working out of the tree; `make reap` previews by default, so that one is seen before it is signalled.

**A LINKED WORKTREE IS ANOTHER CHECKOUT, THOUGH IT SITS INSIDE THIS ONE.** On this machine they live under `.claude/worktrees/`, so by path they are under the main checkout and by every rule this project has they are separate — D43 gives each its own store, its own `inventory/` and its own derived ports, and `checkout_root` called from inside one answers with the worktree. **Measured from the owner's main checkout on 2026-09-12: a bare sweep proposed to stop four processes and all four were other trees' — two capture servers and a supervisor, one of those trees holding a live session.** Two of the four were reachable before this change, so the hole is older than the widening; it is closed here because closing it is what keeps the widening safe.

### Every skip is printed

The sweep now prints what it passed over and why, grouped by reason, beside the count it resolved. **That is the defect one register up**: a process omitted in silence reads exactly like a process that was never seen, which is the thing this whole file exists to stop a `pkill` from doing.

```
  resolved: everything running under this checkout -> 2 process(es)
  resolved: skipped 1 — this session's own chain: 63991
  resolved: skipped 2 — another checkout of this clone: …/worktrees/dreamy-nobel-883fba: 20951, 40455
```

### What it costs

**A process whose relative-path script has since been deleted is not placed by arm two.** Arm one still places it whenever argv names it absolutely, and `scripts/janitor.py` owns the deleted-script class outright as its Tier 1 — that sweep's whole first tier is *a process whose own script has been deleted*.

**`_all_cwds` reads the machine's whole working-directory table in one `lsof` call** — 0.1s for 1,458 rows on the rig — and an `lsof` that is absent or refuses answers with nothing, whereupon the sweep degrades to arm one alone, which is what shipped before. Less evidence never becomes more permission, which is the direction every unknown in this file already resolves in.

### The guard

`make reap-selftest` gains **eight cases across three blocks**, and its fixture gains the thing it never had: **a subject started the way `make server` starts one.** Every process in that suite was spawned with an absolute script path, which is precisely why thirteen mutation arms and thirty-one cases could not see this.

**A MUTATION SUITE PROVES A GUARD AGAINST THE SHAPES ITS FIXTURES CAN PRODUCE, AND A FIXTURE THAT ONLY EVER PRODUCES ONE SHAPE IS A COVERAGE CLAIM ABOUT ITSELF.** Thirteen arms all passed through one `spawn`, so what they measured was thirteen ways of breaking the handling of an absolute path. This is the same failure `a-guard-must-see-its-subject` records for a Playwright sweep whose fixture never drew the control, and the same one the `route rosters` row exists for — a sweep over "every route" off a hand-typed list silently walks the routes it has. The remedy is the same in all three: **make the fixture pose the shape, then mutate.**

The three blocks: a relative-path subject the bare run must find (and which `--explain pid:` always found, which is what makes the miss the RESOLVER's rather than the verdict's); a directory-token subject it must NOT find, with a file-token twin proving the case is not vacuous; a caller placed under the checkout that the sweep must pass over and say so; and a real `git worktree` nested inside the fixture whose process the parent must skip by name and the worktree itself must still sweep.

**Five of the eight fail against the pre-fix `reap.py`.** Eight mutation arms — each new decision point removed one at a time, plus arm one and the nesting test — are all caught.
