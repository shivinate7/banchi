## D257 — a worktree's node_modules is provisioned, not reported

**A fresh worktree failed tsc, lint and design-check on day one.** None of the three
messages named `node_modules`. `scripts/worktree-provision.sh` — shared by
`scripts/worktree-guard.sh` (SessionStart) and `make worktree-setup` — has provisioned
`harness/.cache` and `harness/images` since D47. For `app/node_modules` it only ever
printed `npm --prefix app install`. That followed the Makefile's own `NPM_GUARD` argument:
an implicit install hides a slow, network-touching step inside a target that says it
serves, checks or builds. The owner's own words:

```
i think for some reason worktrees don't come preinstalled with this anymore, send an
agent to ensure that's fixed too so that when i spawn worktrees in banchi they don't
get confused
```

**NPM_GUARD's argument is about hiding a step, not about running one.** A step that is
backgrounded, logged and announced is not hidden. The reader sees it start. The reader
knows where to check on it. That reframing is the whole fix.

**FAST PATH, NO NETWORK.** The main tree's `app/node_modules` may exist. Its
`app/package-lock.json` may be byte-identical to this tree's. When both hold, `cp -c -R`
clones it. That is APFS's `clonefile(2)`, copy-on-write. Measured on this Mac: a real
~200 MB `node_modules` clones in under 0.9s. The disk cost stays near zero until the two
copies diverge. `node_modules/.bin` holds RELATIVE symlinks, one level up into a sibling
package's own bin script, confirmed on this tree, 22 of 22, none absolute. A clone at a
new path still resolves. Nothing in it points back at the main tree. The caller passes the
main tree's path as an argument. Both callers derive it the same way, from
`git rev-parse --path-format=absolute --git-common-dir`, dirname'd once. This script
cross-checks that argument against its OWN resolved cwd. It also re-derives the main tree
from its own git metadata, the identical way, rather than trusting the argument alone. See
SELF-INVOCATION below for why.

**SLOW PATH, VISIBLE.** The lockfiles may differ. The main tree may hold no install. The
clone itself may fail — a full disk, or `cp -c` unsupported. Any of the three runs `npm
--prefix app ci` in the BACKGROUND, backgrounded and disowned so session start never blocks
on it. One line says so and names the log, `.serve/npm-install.log`. `.serve/` is this
checkout's own gitignored scratch directory, on D43's precedent — every checkout gets its
own.

**SELF-INVOCATION IS REFUSED, INSIDE THIS SCRIPT, NOT ONLY IN ITS TWO CALLERS.** A review of
this entry's first draft reproduced a real defect on an isolated fixture. Both callers
already refuse to run this script from the main tree. This script itself did not. With main
equal to cwd, every "copy from main" step is a copy onto ITSELF. `cp -c` refuses a
self-copy. The code that followed a failed clone assumed that the failure was a disk
problem. It RECOVERED by `rm -rf app/node_modules` — deleting the real checkout's own
install, not a half-written clone. The fixture proved it: 8,389 files to zero. The fix
checks twice, independently, because either input could be wrong alone. The resolved cwd is
compared against the resolved main argument. It is also compared against what this
checkout's OWN git metadata says the main tree is. That is the same
`git rev-parse --git-common-dir` derivation both callers already use. Either match refuses
the WHOLE script, before any provisioning step runs.

**A SECOND REVIEW FOUND THE GUARD MISSED A SUBDIRECTORY OF MAIN.** Cwd may be `<main>/app`,
not `<main>` itself. A raw `pwd -P` never equals main's own root there. So the first draft
let a run from inside main's own `app/` slip past the guard. The fix resolves cwd to its
git toplevel FIRST, with `git rev-parse --show-toplevel`. It resolves that to a real path
with `pwd -P`, before either comparison runs. A cwd outside any git tree falls back to the
raw path, the same check the guard always had.

**MAIN'S OWN INSTALL IS CHECKED BEFORE IT IS TRUSTED.** The same review found a second real
defect. Byte-identical lockfiles say a clone would be aimed at the right target. They say
nothing about whether main's own `node_modules` was ever installed for that lockfile. The
first draft cloned a stale or receiptless-but-outdated main. It then wrote THIS worktree's
own receipt for it. `npm_install_owed()` would then answer "current" over packages that do
not match the lockfile. That is the exact trap this whole entry exists to close, reproduced
by the fix meant to close it. `main_install_current()` asks the SAME `npm_install_owed()`,
pointed at main's own root, before the fast path may run. A stale main sends this worktree
to the slow path instead. So does a main this check cannot read. Either way this worktree
gets a real `npm ci`, never a borrowed answer.

**THE BACKGROUND LAUNCH IS LOCKED.** Two invocations of this script can race. Two
SessionStart hooks can race, or one can overlap a hand-run `make worktree-setup`. Each could
see no install yet. Each could then background its own `npm ci` into the same
`app/node_modules`, racing each other's writes. `mkdir` is atomic on this filesystem, so
`.serve/npm-install.lock` IS the lock. No `flock` binary ships on this Mac, and a directory
lock needs none. A holder killed `-9` leaves the directory behind, and the next run
reclaims it rather than waiting on it forever. A run that loses the race reports the log
and starts nothing of its own.

**LIVENESS IS `scripts/serve.py:live_pid`, NEVER A BARE `kill -0`.** A third review found
the first draft's liveness check bare: a pid, and nothing else. The OS recycles pids. A
bare `kill -0` on a stale one would misread some OTHER process's pid as this worktree's own
`npm ci`, still running. That is the exact defect `live_pid` already exists to close for
the capture-server supervisor, in a module this script already imports. It checks the pid.
It also checks that the live process's own argv still names THIS launch. The recorded argv
carries the ABSOLUTE `app` path, never the relative one `npm --prefix app ci` types. A
relative path leaves the needle as the bare word `ci` — a weak match, any process could
carry it. `write_pidfile`, `read_pidfile`, `clear_pidfile` and the `Child` record are all
reused as they stand. Nothing here writes a second, narrower version of `live_pid`'s own
check.

**THE STALENESS QUESTION IS NOT ASKED TWICE.** `scripts/serve.py` already answers one
question: does the installed tree match `app/package-lock.json`? That is
`npm_install_owed()`. It reads the receipt `make up`'s own supervisor writes on every
successful build — `NPM_RECEIPT`, `app/node_modules/.pkmnscan-lock`, a bare sha256 digest.
`scripts/worktree-provision.sh` imports `serve` directly, with
`sys.path.insert(0, "scripts")` first. The module sets up its own `sys.path` for `store`
and `server` before this script ever touches it. No packaging is needed. This script asks
the same function rather than building a second marker with a second rule that could
disagree with the first. Reuse buys two things. A worktree this step provisions is never
redundantly reinstalled the first time it runs `make up`. The owner's own trap is a stale
`node_modules` surfacing as a confusing Playwright-version mismatch, instead of a plain
"reinstall". That trap is answered by the SAME read `make up` already trusts, never a fresh
one that could read the tree differently. This script writes the receipt itself on either
path succeeding, a clone or a successful `npm ci`. The supervisor then credits
provisioning it did not do itself.

**`serve.py` IMPORTABLE OR NOT, THIS FAILS OPEN, ALWAYS.** An exception may come from a
broken venv, a missing `serve.py`, or an import that itself fails. Any of them reads as
`unknown`, never as `current`. An `unknown` result falls back to the old report-only line.
Provisioning is never silently skipped over it. A false "current" answer is the one outcome
this entry exists to rule out. That is the exact shape of the confusing-error trap it
replaces.

**`make worktree-setup` gets the identical behaviour for free.** Both callers still share
the one script D47 already made them share. A session's worktree may be made through the
Agent tool's `isolation: 'worktree'`, or through `EnterWorktree`. Either way `make
worktree-setup` covers it. It covers it even on the days SessionStart does not fire for
it — measured in this entry's own proof run.

**WHAT THIS DOES NOT CHANGE.** `.venv/` and the harness cache and mirror steps above this
one in `scripts/worktree-provision.sh` stay untouched. `scripts/serve.py` is read, never
edited. Its receipt format and its `npm_install_owed` predicate are the primitive this
reuses, not a contract this rewrites. `NPM_GUARD` itself, in the Makefile, stays untouched.
Every `make` target that needs `app/node_modules` still refuses with the same one-line fix
rather than installing on the spot. That target keeps its own reason. This entry does not
reopen it.
