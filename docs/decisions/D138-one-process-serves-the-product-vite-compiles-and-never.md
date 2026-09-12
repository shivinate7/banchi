## D138 — One process serves the product, Vite compiles and never serves, and the build is the server's job

**Settled 2026-09-11 by interview, from the owner asking for an easier way to package this.**
Their words: "rather than two servers." The interview started broad and the answers are the
constraints; the ruling is what they leave standing. Nothing is built under this entry.

### What the owner answered

- **Audience: unknown.** Just them today; maybe the Fulfiller's device; maybe another seller
  one day. So: prefer what costs least to reverse.
- **What bothers them: everything.** Not one step but the shape — two processes, a supervisor,
  two ports, a launch agent, and a restart for an expired key the morning this was asked.
- **The dev loop stays untouched.** Hot reload on every `.tsx` edit under `make dev` is not
  something packaging may cost. They alternate building and operating "in split sessions of
  equal time intensities", so neither half is the minor one.
- **Kept, if packaging meant choosing:** self-reload on Python edits, and per-checkout ports
  and stores (D43). Not kept by name: start at login, the LAN name — and then start-at-login was
  kept when asked directly what happens after a reboot.
- **The window is Chrome, as today.** D108's dock app; the camera work is not re-litigated.
- **The build is the server's, when `dist` is stale.** Not a command they type, not a nag.
- **Scope for the session: record the decision and plan the rest.**

### The ruling

**The operating form is ONE process: the capture server, serving the compiled app itself.**
Static files on its own port, beside the API. `app/dist/` is served for any path that is not a route,
and an unknown path serves `index.html` so the hash router works. The port is the one the tree
already has — `:8000` in the main checkout, the slot's own in a worktree — so D43's property
holds with nothing new: the bundle bakes only the capture port and resolves the host from the
address bar (D53's LAN change), and when the page and the API come from one origin that
composition is trivially right.

**Vite compiles and never serves at run time.** That is the answer to the owner's question about
the value of keeping it, and to "everyone says build in Rust": Vite does two jobs, compiling
TypeScript and JSX into a bundle and, in development, serving that bundle with hot reload.
Nobody ships the second job. The Rust tools are replacements for the first — Vite itself is
moving onto one, Rolldown — and swapping compilers changes the process count by zero. Tauri is
Rust for a native window, which D108 already declined and the owner declined again. So the
compiler stays, and `make dev` keeps it on its own port with hot reload exactly as it is.

**The supervisor loses its app child and gains a build.** It watches `app/src` alongside the
Python packages; when a source file is newer than `dist/` it runs `vite build` and serves the old
bundle until the new one lands. That is the one thing D53 held against this shape — *"a built
bundle has to be rebuilt; it would ADD a step to remember in exchange for removing one"* — and
the owner's answer removes the step by giving it to the process that already watches files. D53's
rejection is reopened here and reversed on exactly that ground, and nothing else in D53 moves:
the drain, the parse pre-check, the fast-failure cap, the self-watch and the launch agent all
carry over to a supervisor with one child instead of two.

**The code it runs is the checkout, live.** A frozen copy promoted by a release target was
offered and is deferred: the owner alternates building and operating, wants Python self-reload,
and already operates on the checkout today, so a frozen form protects against nothing that is
happening and adds a promote step that, forgotten, is a rig session on last week's code with no
sign of it. **What reopens the frozen form is a second person needing the app** — then a snapshot with its own store and no worktree in sight is the right shape, and
D108's "signed artifact" clause is the same reopening from the other side.

**The dock app moves to the capture port, once.** D108 stands in every argument — the page
Chrome already renders, the profile's camera grant, the app as a client and never a second
supervisor — and is amended in one fact: the installed URL is `:8000` rather than `:5173`. The
manifest is already relative (D108) and needs no edit; the reinstall is one press in Chrome.

### Rejected

- **A native window** — Tauri, Electron, pywebview. D108's reasons, unchanged, and the owner
  chose Chrome without hesitation.
- **A Rust bundler as the packaging change.** It is a compiler swap; the process count is the
  complaint, and it does not touch that.
- **Keeping Vite's dev server inside the package, hidden.** Two processes behind one icon is
  the current shape with the lid on. It keeps Node as a run-time requirement and keeps every
  failure mode D53 measured.
- **Dropping start-at-login.** Asked twice; "always just there" won over "one icon, quit when
  done" once the reboot case was named.

### What it costs

- **A `.tsx` edit takes a build to reach the operating form** — seconds, run by the supervisor,
  and the old bundle answers in the meantime. A half-finished edit that does not compile leaves
  the last bundle serving, which is the parse pre-check's rule applied to the other language.
- **Node stays a build-time requirement on the operating machine**, and the launch agent's
  baked `PATH` still has to find it. What goes away is Node as a run-time process.
- **`make dev` must coexist with the supervisor rather than refuse it.** D53's guard refuses
  a foreground `make dev` while this checkout's supervisor holds `:5173`; with the supervisor no
  longer holding it, the guard is wrong and must narrow to `make server` alone. The dev app then
  talks to the live `:8000`, which is the same store it talks to today.
- **The key-expiry restart is untouched by this.** One process reads `.env` once exactly as
  two did. The per-press re-read (`envfile.get_live` for `ANTHROPIC_API_KEY`) is the fix for that
  and is a separate, small change the owner declined for now.

### The plan — build order step 22

**The full plan is `docs/specs/one-process.md`**, written the same day after three more
questions: the cold start, a failed build, and the verbs. It also names the one thing this
entry missed — a port is part of the origin, so the camera grant and every `localStorage` key
(D27) reset once at `:8000`. Recorded in `docs/map.py`'s `OPEN` and `docs/GATES.md`'s open
list under one id. In order, and each one a PR:

1. **The static serve.** The capture server serves `app/dist/` for non-route paths with the
   `index.html` fallback, and refuses to start serving the app (API still up) when `dist/` is
   absent, saying so. T7 covers the route, the fallback, and the absence.
2. **The supervisor's second job.** Drop the app child; watch `app/src`, `app/public`,
   `app/index.html` and the Vite config; build when stale, log the build, serve the old bundle
   until it lands. Relax `make dev`'s refusal. `make up` prints one link, on the capture port.
3. **The dock app and the docs.** Reinstall the Chrome app at `:8000`; amend the `make up`
   block in `CLAUDE.md`, `README.md`, D53 and D108 by pointer to here; `make status` reports
   `dist/` staleness beside the ports.

Unaffected and checked before writing this: `make demo-record` spawns its own capture server
and `make demo-static` already builds `dist-demo/` under a base path; `make design-check` starts
a Vite server per worker and never touches the supervisor; `make screenshot` renders `make dev`'s
port, which does not move.

### What is BUILT, RECORDED, and NEITHER

**BUILT:** nothing. **RECORDED:** this entry, `docs/specs/one-process.md`, step 22 in both
build-order lists, and the D138 line in `CLAUDE.md`'s index. **NEITHER:** every line of the plan above.
