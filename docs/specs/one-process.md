# One process serves the product

D138 (one process serves the product) is the decision. This file is the shape of what it built.
`make up` runs one long-lived child: the capture server. It serves the compiled app out of
`app/dist/` beside its own routes. The supervisor (`scripts/serve.py`) rebuilds `dist/` when the
app's source is newer than it. Vite is the compiler and no longer runs at run time.

`make dev` is the dev loop. It runs Vite on the dev port with hot reload and talks to the same
capture server. §3 and §4 describe code that T7's `check_app_serve` and `make serve-selftest`
cover. §10 lists what only the owner can do.

## 0. What this is

The shape:

```
launchd ─ supervisor ─── python capture_server.py   :8000   API + photos + app/dist/
             │
             └─ vite build   (a child that runs for about a second when the app source is newer)

make dev ──── vite dev server                        :5173   hot reload, talks to :8000
```

The build is a short-lived child that the supervisor runs and waits on, like the parse pre-check
it runs on Python. A worktree's `make up` has the same shape. It serves its own `dist/` on its own
capture port (D43). `server/ports.py`'s `capture_port` derives the port. The bundle bakes only the
capture port and resolves the host from the address bar.

## 1. Three rulings

### 1.1 Cold start — what serves before the build lands?

A cold `vite build` of this app takes about 1.2 seconds. That figure decides the question. The
supervisor builds when stale, and the old bundle answers while it does. With no `dist/` at all
(a fresh clone or worktree), it builds before it opens the port.

The capture route never waits on Node. If there is no `dist/` and the build fails, the API comes up anyway. The app path answers one plain sentence in Python, and no page. A build error must not stop the capture server from serving cards. The other process would hold it hostage.

### 1.2 A build that fails — where do you find out?

A failed build shows in the supervisor log and in `make status`, and nowhere in the app. The last build that worked keeps serving. `make ci-check` runs `lint` and `typecheck` on every PR. The main checkout only advances by `git pull` of a merged commit (D42). So a failed build on the main tree is a moved dependency or a `vite.config.ts` error and not a half-edit. Half-edits happen in worktrees, which serve their own `dist/`.

The supervisor writes `.serve/app-build.json`: a verdict, a stamp and the first error line.
`make status` reads it. No banner and no notification. A macOS notification is dropped by a
sleeping Mac, and it would be the only one this product sends.

### 1.3 The verbs

The verbs are `up`, `down`, `status` and `launch-agent`. `run`, `report` and `guard-foreground`
sit underneath them for launchd and for `make`.

- `make up` starts the server if it is down. If it is up and nothing is stale, it says so and does
  nothing. `ARGS=--restart` stops it first.
- `make down` stops the process. When a launch agent is installed, it says that the agent starts
  the server again at the next login. "Off for now" is what the owner reaches for, and that
  sentence says how to make it permanent.
- `make launch-agent` installs the login note. `ARGS=--remove` takes it down. `up` does not touch it.
- `--restart` keeps `--confirm` on the main checkout. The thing on `:8000` there is the owner's,
  mid-capture. A session that bounced it once cut a write in flight. Fewer words does not mean
  fewer guards.

## 3. The static serve

`server/capture_server.py` serves a file out of `app/dist/` for a `GET` that matched no route.
`app_claims` decides which paths those are, and `do_app_file` serves them.

**Order of resolution.** Routes come first. For a `GET`, a path that names a file under `dist/`
serves that file, and `/` serves `dist/index.html`. The fallback is narrow on purpose. The hash
router owns everything after `#`, which never reaches the server. So the app's only paths are `/`
and its own asset files. A catch-all `index.html` fallback would turn `GET /boxes/abc` into a 200
page and make a dozen named JSON refusals unreachable with nothing failing.

**What is refused.** A path with `..` or a NUL is refused. So is a path that resolves outside
`dist/` after `realpath`, and any method but `GET` and `HEAD`. `dist/` is compiled output. It holds
no photograph, no code-card image and no store. `GET /photo/<box>/<index>` is still the only way
bytes from `captures/` leave.

**Headers.** Vite names every asset with a content hash. So `assets/*` carries `Cache-Control:
public, max-age=31536000, immutable`. `index.html` and `manifest.webmanifest` are `no-store`. They
are what changes on a rebuild, and a cached one would load hashed assets that no longer exist.
`Content-Type` follows the extension, for the eight types Vite emits: `.html`, `.js`, `.css`,
`.svg`, `.png`, `.webmanifest`, `.woff2` and `.json`. The origin gate is untouched, because it
runs on writes and this is a read.

**`dist/` absent.** Every route answers as usual. `GET /` answers 503 `app_not_built` with one sentence: "The app has not been built yet. Start the app again from the Mac to build it." It is not a page and it is not styled. A screen there would be a second front end kept forever for a few seconds of cold start. `make lan-check` reports this state.

**Proof, in T7's `check_app_serve`.** A build sits under a temporary home. `GET /` returns
`index.html` with `no-store`. A hashed asset returns its bytes with `immutable`. A traversal path
returns 404 and reads nothing. `POST /` is 405. With `dist/` removed, `GET /` is 503 and
`GET /status` is 200.

### 3.1 `HEAD`

`do_HEAD` runs `do_GET` behind a flag that `_send` reads, so it withholds the body. `Content-Length`
is still the length the body would have had. RFC 9110 requires a `HEAD` response to carry the
header values the `GET` would send. Only the shared dispatch can do that truthfully. The boot
header, the CORS block and `Connection: close` are each composed in one place.

`HEAD` works on every `GET` route and not only the app surface. Uptime monitors, link checkers,
proxies and `curl -I` reach for `HEAD` first, and `/status` is the likeliest target. A `405` there
would read as a broken server. The cost is that a `HEAD` does the handler's work and discards the
bytes. No `GET` route writes.

`HEAD` is in `SAFE_METHODS` and in `ALL_METHODS`. This does not weaken the origin gate. The gate is
one `in` against `SAFE_METHODS`, and `do_HEAD` reaches only `do_GET`'s routes. Gating it would
answer 403 to a read.

**The proof reads the "no body" half off a bare socket.** `urllib` cannot see it. `http.client`
knows a `HEAD` response has no content and returns `b""` without reading, so a server that wrote
every byte would still pass. Only the raw-socket arm fails when the suppression is removed.

## 4. The supervisor

`scripts/serve.py` runs the capture child and the build.

**Two watch sets that cannot trip each other.** `WATCH_DIRS` holds the Python trees. A change there
restarts the capture child and never builds the app. The app's set is `APP_SOURCE_DIRS`
(`app/src`, `app/public`) and `APP_SOURCE_FILES` (`index.html`, `vite.config.ts`, `devPort.ts`,
`tsconfig.json`, `package.json` and `package-lock.json`). A change there schedules a build and
restarts nothing. `app/dist/` is absent from the set, because the build writes there and watching
it would schedule the next build forever. A `.tsx` save must never bounce the server that the owner
is capturing with. `SELF_FILES` lists the files the supervisor is made of. A change to any one
re-execs the supervisor.

**Staleness is one comparison.** After a successful build, the supervisor writes `dist/.built`. It
holds the newest source mtime that the build read. Stale means any file in the app's set is newer
than that stamp, or the stamp is missing. On `up` and on every poll tick, stale means build. A
quiet period (`QUIET_SECONDS`) debounces it, because an editor saves twice.

**The build is a child, and the swap is atomic.** `npx vite build --outDir dist.next` runs in `app/`. Its output goes to the supervisor log under a `[build]` prefix. Never build into `dist/` directly. Vite empties its output directory before it writes. A build in place would 404 every asset for the second it takes, and it would race any tab mid-load. On success, `dist/` goes to `dist.prev/`, `dist.next/` goes to `dist/`, and `dist.prev/` is deleted. The stamp lives inside `dist/`, so the swap carries it. A request in flight holds an open file descriptor and finishes. On failure, the supervisor deletes `dist.next/`, leaves `dist/` alone, and writes a `fail` verdict to `.serve/app-build.json`.

**`npm ci` is the supervisor's too.** When the lockfile's content changes, `npm ci` runs before the
build. A pull that bumps a dependency then applies itself. The comparison is a sha256 digest of
`package-lock.json` against a receipt inside `node_modules` (`NPM_RECEIPT`), and not an mtime. Git
rewrites a file's mtime on checkout even when the bytes are the same. An mtime comparison would fire
a thirty-second install on every branch switch. The build compares mtimes, and the asymmetry is
deliberate: a spurious build costs 1.2 seconds. A failed install writes an `install-failed` verdict
and leaves the old `node_modules/` as it was, and `make status` names the fix.

**Node missing.** `npx` off `PATH` is the one thing that can make the app fail while the capture
half is fine. The supervisor treats it as a failed build. The API comes up, the log says why, and
`make status` says so. A launchd start needs the `PATH` that `make launch-agent` bakes into the
plist, because the build needs `npx`.

**The one child is the capture server.** The retry, the fast-failure cap, the drain, the parse
pre-check and the self-watch all apply to it. The state files are `supervisor.pid`, `capture.pid`
and the logs under `.serve/`.

**`make dev` runs beside the supervisor.** `do_guard_foreground` refuses `make server` while this
checkout's supervisor is up, because `:8000` is the supervisor's. It no longer refuses `make dev`.
The supervisor does not hold the dev port. `BANCHI_FOREGROUND=off` bypasses the guard.

**`make up` prints one link**, `http://localhost:<capture port>`, and the LAN name beside it when
`BANCHI_LAN_NAME` is set. **`make status`** reports the app's build: built, building, stale with a
failed build, or not built.

**Proof, in `make serve-selftest`.** It runs against a throwaway checkout with a stub `app/`. The
stub's "build" writes one file, because the test is about the supervisor's behavior and not Vite's.

- `up` with no `dist/` builds before the port opens.
- Touching a source file rebuilds once, and the stamp advances. The capture child's pid does not change.
- A build that exits non-zero leaves the previous `dist/` byte-identical and writes a `fail` verdict.
- During a build, `GET /` answers from the old `dist/`. A build stub that sleeps two seconds asserts it.
- With `npx` off `PATH`, the capture child is up and the verdict names it.
- Touching a Python file restarts the capture child and does not build.

Mutations prove it: a build in place fails the fourth arm, and skipping the stamp fails the second.

The `app build files` row of `make docs-audit` reconciles the names `dist/.built`,
`.serve/app-build.json`, `dist.next/` and the `[build]` log prefix across `serve.py`, `status.py`,
the Makefile and this file. Names that come apart silently are the failure that row exists for.

## 5. The port is part of the origin

The ordinary Chrome tab moved from the dev port to the capture port. That is a different origin.
Two things are keyed by origin in Chrome and both reset once:

- **The camera grant.** D108 measured that the grant lives in the profile's content settings,
  keyed by origin. The first open at the capture port prompts again. It is one press.
- **Every `localStorage` key** (D27): `banchi.capture.deviceId`, `banchi.capture.rotation`,
  `banchi.theme`, `banchi.rail`, `banchi.orders.fetch-filter` and `banchi.orders.last-check`. The rig
  re-picks its camera and rotation once, and the theme and the rail reset once. There is no
  migration, because a fallback across origins is not possible.

`sessionStorage` is per tab. Reinstall between shifts and not mid-capture, for the `captureId`
reason D27 names.

The LAN URL is `banchi.lan:<capture port>`. The owner's DNS record names the host and not the
port. `scripts/lan-check.py` presses the app on the capture port. A phone's home-screen bookmark
moves to that port. No dock app has ever been installed (D108). Installing one from the capture
port is optional, and D108's manifest is already relative.

## 6. What does not move

- `make dev`, the dev port and hot reload. `app/devPort.ts` and `vite.config.ts` keep their port and
  host allow-list.
- `make design-check`. Its `webServer` starts Vite per worker on the suite's own ports and never
  touches the supervisor. `app/tests/shell.ts`'s `sealOutside` allow-list (D124) is the dev port and
  the capture port, and it already admits the capture port.
- `make screenshot` renders `make dev`'s port.
- `make demo-record` spawns its own capture server. `make demo-static` builds under `DEMO_BASE` to
  `dist-demo/`, which this never reads.
- The wire, the store, the packages, `BANCHI_HOME` and the ports' derivation.

## 7. The frozen form, deferred

D138 defers a promoted snapshot until a second person needs the app. It would be a release target
that writes `app/dist/` plus the Python packages into a directory with its own `BANCHI_HOME`. The
launch agent would point at that directory and not at the checkout. §3 and §4 are prerequisites for
it. `server/capture_server.py`'s `APP_DIST` is a call-time read, and not an environment variable,
because only this form would want one. No such person exists, so nothing plans it further.

## 8. Unmeasured

- Whether the build ever fires on the main tree from something other than a `git pull`. That would
  mean the tree is edited in place.
- How often `make status` reports `stale`, and for how long. If it is ever more than a second, the
  debounce or the stamp is wrong.
- Whether the camera grant and the 4K mode carry at the capture port as D108 measured at the dev
  port. It is the one thing here that touches the rig.

## 10. What only the owner can do

Two presses on the owner's own machine, and a session cannot do either:

1. **Open the app at `http://localhost:8000`** and re-bookmark it. Expect one camera prompt and one
   reset of the six device-local keys (§5). Do it between shifts and not mid-capture.
2. **Run `make lan-check` with the phone on the network.** Its rows press the capture port for the
   app.

Until the first press, a bookmark at the dev port answers nothing once `make up` runs. Only
`make dev` serves that port, and only while somebody runs it. Whether the owner has made either
press is unknown.
