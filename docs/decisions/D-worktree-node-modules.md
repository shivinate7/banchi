## D-worktree-node-modules — a worktree's node_modules is provisioned, not reported

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
new path still resolves. Nothing in it
points back at the main tree. The main worktree is found from `git worktree list
--porcelain`'s first entry. That is the same primitive `scripts/worktree-guard.sh` already
uses to find it, never a typed path.

**SLOW PATH, VISIBLE.** The lockfiles may differ. The main tree may hold no install. The
clone itself may fail — a full disk, or `cp -c` unsupported. Any of the three runs `npm
--prefix app ci` in the BACKGROUND, backgrounded and disowned so session start never blocks
on it. One line says so and names the log, `.serve/npm-install.log`. `.serve/` is this
checkout's own gitignored scratch directory, on D43's precedent — every checkout gets its
own.

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
