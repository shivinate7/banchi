## D43 — Each checkout gets its own port

**Every checkout derives its own dev and capture ports from its own path, because every checkout already has its own store.** `store/files.py:home()` has always defaulted to `REPO_ROOT`, the checkout the code runs from. So each git worktree has its own `inventory/`, `runs/` and `captures/`. The capture server's port was the constant `8000` in all of them. `app/src/server.ts` asked for `http://localhost:8000` whichever tree served it.

**A shared port over per-checkout stores is a data-loss problem, not a busy-port problem. It runs in both directions.** Whichever server won the bind answered every tree's UI:

- a worktree's screens drove the owner's real 767-card inventory, on a branch, with whatever half-finished route that branch defined; or
- the MAIN checkout's capture screen was answered by a worktree's server. That is the screen the owner shoots a box from. Real card photographs were written into `<worktree>/captures/cards/` and deleted with the branch.

The second case is silent and cannot be undone. Neither screen says which process replied.

**`app/devPort.ts` gave each checkout its own Vite port. The shared PORT was the fault that remained.** The fix stopped at Vite and Playwright. Before it, `make design-check` in a worktree attached to the main tree's dev server, asserted `docs/DESIGN.md`'s floors against code the worktree had never seen, and passed. The capture server writes photographs and inventory to disk, and it kept the shared constant.

**`app/tests/inventory.spec.ts` described the bug in a comment.** An unstubbed read goes to whatever listens on port 8000: the owner's live capture server over the live 767-card inventory.

### One slot, two ports

The slot is the `sha256` of the checkout's canonical path, first four bytes, modulo 300. Dev is `5200 + slot`, and capture is `8100 + slot`. A tree therefore reads as a pair, such as 5276 beside 8176. There is one number to recognize, not two unrelated ones. **The main working tree keeps 5173 and 8000.** So every doc, the Makefile's help and `scripts/views.txt` stay true, and the ordinary single-checkout workflow is unchanged.

**AMENDED by D261: a copied tree never gets the live port.** "The main working tree" is now a tree whose `.git` is a DIRECTORY. A tree with no `.git` used to keep 8000. A scratch copy of main called the owner's live server from it. Such a tree now takes a slot from its path, as a linked worktree does.

**AMENDED by D261: a checkout claims its port slot once.** A hash into 300 slots put two live worktrees on one port. A design check in one tested the other's code, and it passed. A linked checkout now claims its slot once, in a machine-wide registry. The derivation reads that slot before it hashes. A test run also refuses a reused dev server that does not name this checkout.

**Derived, not allocated.** `app/devPort.ts` gives the reason. The same tree gets the same port on every run. That makes a printed URL worth keeping. It also lets `strictPort` tell "someone else is here" from "I moved". Collisions can happen, with 300 slots and a handful of trees. They are loud. Vite refuses to start, and the capture server raises `EADDRINUSE` rather than serving somewhere else. The remedy is to rename the worktree directory, because the port follows the path.

**Two implementations of one algorithm, checked by a test.** Python serves and TypeScript addresses. Neither can import the other. `make port-agreement` runs both over the same real directories and diffs the results. It runs in `make check`, not the git hook, because it needs node and the hook runs bare. It was mutation-tested both ways. Moving the Python band turns the composed-port case red. Changing the slot width turns every path red. A check that cannot fail is not coverage. The multi-game prompt seam already showed this. A differently named identifier field there would have parsed cleanly and joined nothing.

**Canonicalization is part of the algorithm, and it was the one real trap.** Both sides resolve the root before hashing: Node's `realpathSync` and Python's `Path.resolve()`. `/tmp` is a symlink to `/private/tmp` on this machine, and one worktree lives under it. So the agreement test uses **real directories**. A path that does not exist canonicalizes differently in the two languages, and synthetic inputs would test the test. `app/devPort.ts` moved from `resolve()` to `realpathSync`. Every worktree in this clone gives the same slot either way, so **no existing dev port moved.**

**The rule is stated in the three places a session looks.** The owner's complaint was exact. The port reasoning existed only in a source comment, so it was not reliable. Now `CLAUDE.md` carries the rule. `scripts/worktree-guard.sh`, the SessionStart hook, prints this tree's two ports before work begins. `make status` prints them and says outright when you are in a worktree. `make server`'s banner names the store it will serve, and it warns when that store is not the main checkout's.

**`BANCHI_PORT` overrides, with the same shape as `BANCHI_HOME`.** An unparseable or out-of-range value is **ignored, not obeyed**. A typo must not put the server on a port no client will look at. `VITE_CAPTURE_SERVER` still outranks the derived default on the client. That is the operator's explicit override. It covers the case `docs/specs/capture-app.md` §11 leaves open: the Fulfiller's device pointed at this Mac by address.

**What this does not do: give worktrees a shared store.** Each still has its own, usually empty, store. D13's one truth on the Mac still holds. The truth lives in the main checkout. A worktree that needs real data points `BANCHI_HOME` at it on purpose. That is a decision with a visible env var, not an accident of which process bound a socket first.

**What would reopen this: one capture server for every tree.** The honest shape would be one server on 8000 with `BANCHI_HOME` pinned to the main checkout. The worktrees' clients would point at it through `VITE_CAPTURE_SERVER`, the knob that already exists. That is a different decision about where the truth lives.

### One file was missed, and it is the one a human looks through

`.claude/launch.json` was fixed in a later change. It was tracked, and it hardcoded `"port": 5173`. That is right in the main tree and wrong in every linked worktree. `vite.config.ts`, `playwright.config.ts`, `server/capture_server.py` and `app/src/server.ts` all use the derivation. The Browser pane's launch config did not. So `preview_start` would start THIS tree's dev server on its own port, then open a tab on 5173.

**This is the same defect in a different form, and the worse half.** A dead tab is a nuisance. A tab on 5173 while the main tree's `make dev` runs is a worktree **previewing main and looking like it worked**. `app/devPort.ts` records the same silent-wrong-answer shape for `make design-check`. It calls it the worst shape a check can fail in, because the only signal it gives is the one you were hoping for.

**A tracked file cannot hold a per-checkout value, so the file is no longer tracked.** `.claude/launch.json` is gitignored. `make launch-config` writes it from `server/ports.py`, the same derivation the other four readers use, so all five agree. The target hangs off `make venv`, the documented first step in a fresh clone, and `make worktree-setup` calls it. It is also a standalone target, because **the port follows the PATH**. A renamed worktree needs the file written again.

**The precedent is `.claude/settings.local.json`, which is already gitignored beside it.** What every checkout shares is tracked. What one machine or one checkout answers is not. Nothing in the repo reads `launch.json`. No doc names it, and no audit check resolves it. So removing it from tracking cost nothing.

**What this gives up:** a fresh clone has no launch config until `make venv` runs. Before, it had a wrong one at once. That is the right direction for a file whose only failure is pointing somewhere plausible and wrong.

**The trade was wrong about what an absent file costs. It took twenty-three days and a measurement to see.** The paragraph above reasons that absent beats wrong. It does not. **Nothing leaves the file absent.** The Browser pane's instructions tell an agent that finds no `launch.json` to create one from a template with a literal port. So absent lasts until the first `preview_start`. Then it becomes wrong, written by a session that had no way to know this repo derives the number. Absent is not the safe end of the trade. It is the entrance to the unsafe end.

**Measured across the five worktrees of this clone:** four correct, one absent, and one holding a hand-written **5173**. That linked worktree's Browser pane would start its own dev server on 5470, then open a tab on the MAIN TREE's port.

**An absent file became a wrong one within twenty minutes.** `card-sku-stamping-fix-d11945` had no config, then one naming **5173** against a derived **5313**. A template wrote it. Nothing inside a tool that offers a template can know the port is a fact about the checkout's path. **The absent state is not a resting state. It decays in one direction.**

**The fault was that the fix was a Makefile target, and a target runs only when somebody runs it.** `make launch-config` hangs off `make venv`, which `make worktree-setup` calls. So it reaches only worktrees provisioned that way. The five readers this entry moved onto one derivation are code, and code runs whether or not anyone remembers. This one was a file that somebody had to ask for.

**So `scripts/worktree-guard.sh` writes it, and that is the whole repair.** The SessionStart hook runs before any work starts in every checkout. It already provisions the other gitignored files a tree cannot inherit, and it already imports `server/ports.py` to print the pair. It now writes one more provisioned file, from the one derivation, with no one required to remember a target. **It runs ABOVE the worktree test**, because `dev_port()` answers 5173 in the main tree by construction. The same call is right in every checkout, so there is no branch to get wrong.

**One writer, three modes, and the difference is who asked.** `scripts/launch-config.py` holds the logic. The Makefile target FORCES the write, because somebody typed it. The hook passes `--if-needed`, because it runs unasked. `make status` passes `--check` and writes nothing. Splitting the modes, not the writers, keeps the two from drifting. Drift is the failure this entry is about.

**It rewrites an absent or stale file. It never touches a hand-edited one.** A stale file has this repo's exact shape at the wrong port. That is what the Browser pane's template produces. A second configuration, a different command, a `url`, or JSON that does not parse are reported and left alone. The asymmetry is deliberate. It deletes only what is provably a duplicate, and it reports only what differs. Guessing is how a cleanup tool destroys work. A tool that runs on every session start, unasked, has more reason to keep that rule.

**`make status` reports a disagreement, because the hook fails open by design.** That is this repo's standing rule for hooks. Its cost is that a skipped hook is silent. The status line closes that gap. It already reports NOT ARMED for the git hooks on the same basis. It stays silent when the two agree, so the ordinary case costs no line.

**What is still open:** a worktree gets the fixed hook only after this lands on the branch it was cut from. The guard is a tracked file. A tree cut from an older main runs the older guard, and it still needs `make launch-config` by hand. Nothing can reach back into a checkout that lacks the code.

### A second file decided whether a worktree could write at all

`server/capture_server.py:DEFAULT_ALLOWED_ORIGINS` was the literal tuple `("http://localhost:5173", "http://127.0.0.1:5173")`. That is the CSRF allowlist for the only origins allowed to POST, PUT or DELETE. This entry moved the dev port, `vite.config.ts`, `playwright.config.ts`, `app/src/server.ts` and later `.claude/launch.json` onto one derivation. It left the allowlist on the constant.

**So a linked worktree served an app whose every write its own server refused.** The app comes from that tree's derived dev port. The gate expects 5173, so the answer is 403 `origin_not_allowed`. It was observed on the worktree at `.claude/worktrees/inventory-delete-feedback-2b96fa`. Capture, undo, mark-sold, retire, the mid-box delete and the claim editor were all refused. **Reads are ungated,** so every screen rendered, the inventory drew, and the walk worked. A branch's app could look at its store and never change it. The only way to find out was to press something. `BANCHI_ALLOWED_ORIGINS` was the workaround, and nothing pointed to it until the refusal appeared.

**It is this entry's own rule with one more reader, and that is the finding.** A tracked constant cannot be right in every checkout. The same is true of a second file nobody had listed. Both misses are readers of the port that are not servers on it. The bind moved because it was obviously about the port. A launch config and an origin allowlist are about the port without looking like it.

**`ports.dev_port()` is read once, at import.** `allowed_origins()` one line below is read fresh on each request. Its input is an environment variable that a running server should pick up without a restart. The port has no input that can change while the process runs.

**Nothing moves in the main tree.** That is why the defect stayed hidden. `dev_port()` answers 5173 there by construction. So the tuple matches the old constant exactly wherever the owner works, and every doc that names the number stays true. Only a linked worktree changes, and only from refusing everything to allowing its own app.

**A checkout allows its own origin, not the main tree's.** Adding 5173 back for worktrees is the obvious generous fix, and it is wrong. It would let a page served by the MAIN checkout write into a branch's store. That is the cross-tree write this entry exists to prevent. Pointing one tree's app at another tree's server is a real need, and it is already deliberate: `VITE_CAPTURE_SERVER`. So it takes the deliberate answer, `BANCHI_ALLOWED_ORIGINS`.

**Covered in `check_origin_gate`, which had the constant written into it too.** That block asserted `["http://127.0.0.1:5173", "http://localhost:5173"]` literally. It would have failed in a worktree for the right reason and passed in the main tree for the wrong one. It now checks the PROPERTY. It checks both spellings, at the port this checkout's app is served on. It checks that a non-worktree root still derives 5173. In a worktree only, it checks that the main tree's origin is NOT in the list. Mutation-tested: restoring the constant turns two of these cases red.

**The limit: none of these cases can fail in the main checkout.** 5173 is correct there whichever way the list is built. So the guard runs only when someone runs the harness from a worktree. `make worktree-setup` and the Stop hook make that routine. That is why the case is worth having. The block says so in a note, so a green run is not misread.
