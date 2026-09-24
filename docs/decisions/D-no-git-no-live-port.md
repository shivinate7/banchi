## D-no-git-no-live-port — A copied tree never gets the live port, and only a `.git` directory keeps 8000

**Amends D43, the port follows the store.** D43 gave the base ports, 8000 and 5173, to every tree that was NOT a linked worktree. A tree with no `.git` was not a linked worktree, so it got 8000. Now only a tree whose `.git` is a DIRECTORY keeps 8000 and 5173. Every other tree takes a slot from its own path, as a linked worktree does. `server/ports.py:is_primary_checkout` and `app/devPort.ts:isPrimaryCheckout` ask the question. `server/ports.py:is_linked_worktree` keeps its meaning for its other callers.

**The incident, 2026-09-23 (UX-166, S1).** A reviewer copied main into a scratch folder with no `.git` and built the app there. The build baked 8000, the port of the owner's LIVE capture server. The page read the owner's real store on load. A press would have written to it. D43's own comment named "a tarball, a container copy" as the case, and still gave it 8000. It argued that "inventing a port for a checkout with no identity" is worse than the default. That premise is false: the path IS an identity, and D43 already derives a linked worktree's slot from nothing else. `scripts/serve-selftest.py` met the same defect earlier and pinned `PKMNSCAN_PORT` around it. That was a workaround in one file. This is the fix at the cause.

**A slot, not a refusal. The reasons:**

- **Tools build from exported trees.** `vite.config.ts` and `playwright.config.ts` import `app/devPort.ts` when they load. A refusal there stops every build and every test in any tree with no `.git`. A slot costs nothing.
- **The pair stays together.** The server and the app in the copy derive the SAME slot, so the copy's app reaches the copy's own server. `store/files.py:home()` defaults to `REPO_ROOT`, so that server reads the copy's own `inventory/`. That is D43's outcome: the port follows the store.
- **A wrong guess costs a moved port, never a write.** A refusal protects the same thing, but it also breaks work that was never at risk.

**What each runner sees. Measured, not assumed.**

- **CI** (`.github/workflows/check.yml`, `demo.yml`) checks out with `actions/checkout@v4`. The demo run of 2026-09-24 logs `Initialized empty Git repository in /home/runner/work/banchi/banchi/.git/`. So `.git` is a directory, CI is a primary checkout, and it keeps 8000 and 5173 as before. Nothing on CI moves.
- **The GitHub Pages demo** (`make demo-static`, `VITE_DEMO=1`) sends every request through `app/src/server.ts:request`'s `DEMO` branch to `demoServer.ts`. It never fetches the baked port. `scripts/demo-record.py` starts its own server on a free port through `PKMNSCAN_PORT`. The demo does not read this derivation.
- **A copied tree's store** is its own: `home()` answers the copy's `REPO_ROOT`, so its store is `<copy>/inventory/store.sqlite`. It is not the owner's store. But a `cp -r` of the MAIN checkout also copies the gitignored `inventory/`. The copy then holds a copy of the owner's real data. Writes land in the copy and never reach the owner's store.

**What this does not cover.**

- **A copy that brings its `.git` directory.** A `cp -r` of the main checkout WITH `.git`, or a second clone, is a primary checkout of its own and still derives 8000. No local fact tells it apart from the owner's tree. Its server gets `EADDRINUSE` while the owner's server runs, but its app still bakes 8000. The incident case, no `.git`, is closed. This case is open.
- **`app/src/server.ts:FALLBACK_BASE`** is `http://localhost:8000`. A bundle built WITHOUT `vite.config.ts`'s define uses it. Every Vite build has the define, so no build reaches it today.
- **`scripts/screenshot.sh`** falls back to 5173 when Python cannot import `server/ports.py` and `.git` is not a file. That is a second failure on top of this one.

**The reader.** `make port-agreement` copies both files into three throwaway trees: `.git` a directory, `.git` a file, and no `.git`. It asks each copy for its own default ports through the module-location read a real build makes. The no-`.git` arm goes red on the old rule, on either side alone. `harness/tests/t7_store_and_seams.py` asserts that a root with no `.git` does not derive 5173.
