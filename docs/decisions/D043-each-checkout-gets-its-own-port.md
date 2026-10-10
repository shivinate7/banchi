## D43 — Each checkout gets its own port

**Every checkout derives its own dev and capture ports from its own path, because every checkout already had its own store.** Built 2026-08-29. `store/files.py:home()` has always defaulted to `REPO_ROOT`, the checkout the code runs from. So every git worktree has its own `inventory/`, `runs/` and `captures/`. The capture server's port was the bare constant `8000` in all of them. `app/src/server.ts` asked for `http://localhost:8000` whatever tree served it.

**A shared port over per-checkout stores is not a busy-port problem. It is a data-loss problem, and it runs in both directions.** Whichever server won the bind answered every tree's UI:

- a worktree's screens drive the owner's real 767-card inventory, on a branch, with whatever half-finished route that branch happens to define; or
- the MAIN checkout's capture screen is answered by a worktree's server. That is the screen the owner actually shoots a box from. Real card photographs are written into `<worktree>/captures/cards/` and deleted with the branch.

The second is unrecoverable and silent. Nothing on either screen says which process replied.

**Half of this was already fixed and the half that was left is the one that writes.** `app/devPort.ts`, earlier the same day, gave every checkout its own **Vite** port. Before that, `make design-check` ran in a worktree attached to the main tree's dev server. It asserted `docs/DESIGN.md`'s floors against code the worktree had never seen, and it passed. That entry's own reasoning is the argument here: the shared PORT is the whole fault. It stopped at Vite and Playwright. The capture server, which is the process that writes photographs and inventory to disk, kept the shared constant.

**`app/tests/inventory.spec.ts` had already written the bug report.** Its stubs are justified in a comment. The comment says an unstubbed read is a request to whatever is listening on port 8000. In this repo, that is the owner's actual capture server over their actual 767-card inventory. That is this defect, observed, worked around locally, and never filed.

### One slot, two ports

`sha256` of the checkout's canonical path, first four bytes, modulo 300. Dev is `5200 + slot`, capture is `8100 + slot`. A tree therefore reads as a pair — 5276 beside 8176. There is one number to recognize rather than two unrelated ones. **The main working tree keeps 5173 and 8000**, so every doc, the Makefile's help and `scripts/views.txt` stay true and the ordinary single-checkout workflow is untouched.

**AMENDED 2026-09-23 by D261, a copied tree never gets the live port.** "The main working tree" is now a tree whose `.git` is a DIRECTORY. A tree with no `.git` used to keep 8000, and a scratch copy of main called the owner's live server from it. It now takes a slot from its path, as a linked worktree does.

**AMENDED 2026-09-24 by D261, a checkout claims its port slot once.** A hash into 300 slots put two live worktrees on one port, and a design-check in one tested the other's code, green. A linked checkout now claims its slot once in a machine-wide registry. The derivation reads that slot before the hash. A test run also refuses a reused dev server that does not name this checkout.

**Derived, not allocated**. The reason `app/devPort.ts` already gives is this: the same tree answers the same port on every run. That is what makes a printed URL worth keeping. It is also what lets `strictPort` tell *someone else is here* from *I moved*. Collisions are possible, with 300 slots and a handful of trees. They are loud. Vite refuses to start, and the capture server raises `EADDRINUSE` rather than serving somewhere else. The remedy is to rename the worktree directory, since the port follows the path.

**Two implementations of one algorithm, asserted rather than trusted.** Python serves and TypeScript addresses, and neither can import the other. `make port-agreement` runs both over the same real directories and diffs them. It is in `make check` rather than the git hook, because it needs node and the hook runs bare. **It was mutation-tested in both directions before it was kept** — moving the Python band takes the composed-port case red. Changing the slot width takes every path red. A check that cannot fail is not coverage. This repo already paid for that lesson at the multi-game prompt seam. A differently-named identifier field there would have parsed cleanly and joined nothing.

**Canonicalization is part of the algorithm and was the one real trap.** Both sides realpath the root before hashing — Node's `realpathSync`, Python's `Path.resolve()` — because `/tmp` is a symlink to `/private/tmp` on this machine. One worktree genuinely lives under it. The agreement test therefore feeds **real directories**. A path that does not exist canonicalizes differently in the two languages. So synthetic inputs would have tested the test rather than the code. `app/devPort.ts` was moved from `resolve()` to `realpathSync` for this. It was measured first: every worktree in this clone answers the same slot either way, so **no existing dev port moved.**

**It is said in the three places a session actually looks**, which is the half that makes it reliable rather than merely correct. The owner's complaint was exact. The port reasoning existed only in a source comment, not in `CLAUDE.md` nor in any hook. So it was not reliable. Now `CLAUDE.md` carries the rule. `scripts/worktree-guard.sh`, the SessionStart hook, prints this tree's two ports before any work begins. `make status` prints them, and says outright when you are in a worktree. `make server`'s banner names the store it is about to serve. It warns when that store is not the main checkout's.

**`BANCHI_PORT` overrides, the same knob and shape as `BANCHI_HOME`.** An unparseable or out-of-range value is **ignored rather than obeyed**. A typo must not put the server on a port no client will look at. That is this entry's own failure arriving by another road. `VITE_CAPTURE_SERVER` still outranks the derived default on the client. That is the operator's explicit override. It is the case `docs/specs/capture-app.md` §11 leaves open: the Fulfiller's device pointed at this Mac by address.

**What this does not do: it does not give worktrees a shared store.** Each still has its own, still usually empty, and that is D13's one-truth-on-the-Mac holding. The truth is the main checkout's. A worktree that wants to work against real data points `BANCHI_HOME` at it deliberately. That is a decision with a visible env var, rather than an accident of which process bound a socket first.

**What would reopen this: wanting one capture server for every tree.** The honest shape then is one server on 8000 with `BANCHI_HOME` pinned to the main checkout. The worktrees' clients would be pointed at it by `VITE_CAPTURE_SERVER`, the knob that already exists. That is a different decision about where the truth lives.

### One file was missed, and it was the one a human looks through

`.claude/launch.json`, found and fixed 2026-08-30. It was tracked, and it hardcoded `"port": 5173`. That is right in the main tree and wrong in every linked worktree. `vite.config.ts`, `playwright.config.ts`, `server/capture_server.py` and `app/src/server.ts` all moved onto the derivation. The Browser pane's own launch config did not. So `preview_start` would start THIS tree's dev server on its own port, and then open a tab on 5173.

**That is this entry's own defect wearing a different hat, and the worse half of it.** A dead tab is a nuisance. A tab on 5173 while the main tree's `make dev` is up is a worktree **previewing main and looking like it worked**. That is the same silent-wrong-answer shape `app/devPort.ts` records for `make design-check`. That file calls it the worst shape a check can fail in, because the only signal it gives is the one you were hoping for.

**A tracked file cannot hold a per-checkout value, so it stopped being tracked.** `.claude/launch.json` is gitignored and written by `make launch-config` from `server/ports.py`. That is the same derivation the other four read, so all five cannot disagree. It hangs off `make venv`, which is already the documented first step in a fresh clone, and which is what `make worktree-setup` calls. It is a standalone target as well, because **the port follows the PATH**, and a renamed worktree needs it written again.

**The precedent is `.claude/settings.local.json`, already gitignored beside it.** The split inside that directory is not new. What every checkout shares is tracked. What one machine or one checkout answers is not. Nothing in the repo reads `launch.json`. No doc names it, and no audit check resolves it. So this cost nothing but the file.

**What this gives up:** a fresh clone has no launch config until `make venv` runs. Before, it had a wrong one immediately. That is the right direction for a file whose only failure mode is pointing somewhere plausible and wrong.

**And that trade was wrong about what an absent file costs, which took twenty-three days and a measurement to see** (2026-08-30). The paragraph above reasons that absent beats wrong. It does not. **Nothing leaves it absent.** The Browser pane's own instructions tell an agent that finds no `launch.json` to create one from a template carrying a literal port. So *absent* is a state that lasts until the first `preview_start`. Then it becomes *wrong*, written by a session that had no way to know this repo derives the number. Absent is not the safe end of that trade. It is the *entrance* to the unsafe end.

**Measured across the five worktrees of this clone**: four correct, one absent, and one holding a hand-written **5173** nobody remembered writing. That is the tree the measurement was taken in. It is a linked worktree whose Browser pane would start its own dev server on 5470, and then open a tab on the MAIN TREE's.

**And the absent one became a 5173 while the fix was being written, which is the measurement that settles it.** `card-sku-stamping-fix-d11945` was the tree with no config at 10:16. At 10:29 it had one naming **5173** against a derived **5313**. A session in that worktree wrote it, from the template, in the twenty minutes between the two readings. Nobody was careless. The port is a fact about the checkout's path, and there is no way to know it from inside a tool that offers a template. **The absent state is not a resting state, and it decays in exactly one direction.**

**The fault was that the fix was a Makefile target, and a target only runs when somebody runs it.** `make launch-config` hangs off `make venv`, which `make worktree-setup` calls. So it reaches a worktree provisioned that way and no other. The five readers this entry moved onto one derivation are all *code*, which runs whether or not anyone remembers. This one was a file somebody had to ask for.

**So `scripts/worktree-guard.sh` writes it, and that is the whole of the repair.** The SessionStart hook already runs before any work starts in every checkout. It already provisions the other gitignored things a tree cannot inherit, and it already imports `server/ports.py` to print the pair. One more provisioned thing, from the one derivation, with nobody required to remember a target. **It runs ABOVE the worktree test**, because `dev_port()` answers 5173 in the main tree by construction. The same call is right in every checkout, and there is no branch to get wrong.

**One writer, three appetites, and the difference is who asked.** `scripts/launch-config.py` holds the shape. The Makefile target FORCES, because somebody typed it. The hook passes `--if-needed`, because it runs unasked. `make status` passes `--check` and writes nothing. Splitting the appetites rather than the writers is what stops the two from drifting, which is the failure this entry is otherwise entirely about.

**It rewrites an absent or a stale file and never a hand-edited one.** Stale is the narrow case: this repo's exact shape at the wrong port, which is precisely what the Browser pane's template produces. A second configuration, a different command, a `url`, or JSON that does not parse are all reported, and none touched. The asymmetry is deliberate. It deletes only what is provably a duplicate. It only reports what differs. The grounds are that guessing is the one way a cleanup tool destroys work. Something that runs on every session start without being asked has more reason to keep that rule, not less.

**`make status` reports a disagreement, because the hook fails open by design.** That is this repo's standing rule for hooks, and it is right. Its cost is that a skipped hook is silent. The status line closes exactly that gap. It is the surface whose whole job is saying what state you are actually in. It already reports NOT ARMED for the git hooks on the same argument. It is silent when the two agree, so the ordinary case costs no line.

**What is still not closed**: a worktree gets the fixed hook only once this lands on the branch it was cut from. The guard is a tracked file, so a tree cut from an older main runs the older guard. It goes on needing `make launch-config` by hand. Nothing can reach backwards into a checkout that does not have the code.

### And a second file decided whether a worktree could write at all

`server/capture_server.py:DEFAULT_ALLOWED_ORIGINS` was the literal tuple `("http://localhost:5173", "http://127.0.0.1:5173")`. That is the CSRF allowlist naming the only origins permitted to POST, PUT or DELETE. This entry moved the dev port itself, `vite.config.ts`, `playwright.config.ts`, `app/src/server.ts` and eventually `.claude/launch.json` onto one derivation. It left the allowlist on the constant.

**So a linked worktree served an app whose every write its own server then refused.** The app comes off that tree's derived dev port. The gate expects 5173. The answer is 403 `origin_not_allowed`. Observed on the worktree at `.claude/worktrees/inventory-delete-feedback-2b96fa`: capture, undo, mark-sold, retire, the mid-box delete and the claim editor all refused. **Reads are ungated.** So every screen rendered, the inventory drew, and the walk worked. A branch's app could look at its store and never change it. The only way to find out was to press something. `BANCHI_ALLOWED_ORIGINS` was the workaround, and nothing pointed at it until the refusal arrived.

**It is this entry's own rule with one more reader, and that is the finding rather than the fix.** The paragraph above says it about `launch.json` in as many words. A tracked constant cannot be right in every checkout. The same sentence was true of a second file nobody had enumerated. What both misses have in common is that they are readers of the port that are not *servers* on it. The bind moved because it was obviously about the port. A launch config and an origin allowlist are about the port without looking like it.

**`ports.dev_port()` is asked once, at import.** Unlike `allowed_origins()` one line below. That one is read fresh per request. Its input is an environment variable a running server should pick up without a restart. This has no input that can change while the process lives.

**Nothing moves in the main tree**, which is the property that makes this safe and also the reason it hid. `dev_port()` answers 5173 there by construction. So the tuple is byte-identical to the constant it replaces wherever the owner actually works, and every doc naming that number stays true. Only a linked worktree changes, and only from *refuses everything* to *allows its own app*.

**A checkout allows its own origin and not the main tree's.** Adding 5173 back for worktrees was the obvious way to be generous, and it is the wrong one. It would let a page served by the MAIN checkout write into a branch's store. That is the cross-tree write this entry exists to prevent. It arrives through the one control in this repo whose job is to stop a page writing where it should not. Pointing one tree's app at another tree's server is a real thing to want, and it is already deliberate: `VITE_CAPTURE_SERVER`. So it takes the deliberate answer, `BANCHI_ALLOWED_ORIGINS`.

**Covered in `check_origin_gate`, which had the constant written into it too.** That block asserted `["http://127.0.0.1:5173", "http://localhost:5173"]` literally. So it would have gone red in a worktree for the right reason, and green in the main tree for the wrong one. It now asserts the PROPERTY. It checks both spellings, at the port this checkout's app is actually served on. It checks that a non-worktree root still derives 5173. And, in a worktree only, it checks that the main tree's origin is NOT in the list. Mutation-tested: restoring the constant takes two of them red.

**The honest limit, named because it is how the defect survived: none of those cases can fail in the main checkout.** 5173 is correct there whichever way the list is built. So the whole guard is only ever exercised by somebody running the harness from a worktree. `make worktree-setup` and the Stop hook make that ordinary, and it is why the case is worth having at all. The block says so in a note rather than leaving a green run to be misread.

---
