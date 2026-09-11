# One process serves the product

**Status: specified and BUILT 2026-09-11.** D135 is the decision and this file is the plan;
all three PRs in §9 landed the same day, in order, each with the proof it names. What is NOT
done is in §10 — the dock app's reinstall and the LAN check from a phone are both presses on
the owner's own machine and neither has been made.

**Where each section now stands.** §3 and §4 describe code that exists and is covered:
`check_app_serve` in T7 (24 assertions, two mutations) and `serve-selftest` (25 assertions,
five mutations). §5 is written and waiting on the two presses. §1's three rulings are the
owner's own and were taken after the first draft of this file.

## 0. What this is

Today `make up` runs two processes under a supervisor: the Python capture server on `:8000`
and Vite's dev server on `:5173`, which compiles the app and serves it with hot reload. After
this plan, `make up` runs one: the capture server serves the compiled app out of `app/dist/`
beside its own routes, and the supervisor rebuilds `dist/` whenever the app's source is newer
than it. Vite is still the compiler. It no longer runs at run time.

The dev loop is untouched. `make dev` still runs Vite on `:5173` with hot reload, and talks to
the same live `:8000` it talks to today.

## 1. The three answers the interview left open

D135 records the owner's interview. Three questions were asked afterwards and answered with a
question back; the tradeoffs and the ruling for each are here so the entry does not re-argue
them.

### 1.1 Cold start — what serves before the build lands?

**Measured first: a cold `vite build` of this app takes 1.2 seconds wall clock** on this Mac
(715 ms inside Vite, 1.7 MB out). That number decides the question. The three shapes were:

| Shape | What you see | What it costs |
|---|---|---|
| Build first, then open the port | `make up` prints the link only once the app is real | One second on a cold start; a failed build with no `dist/` means no capture until it is fixed |
| Serve the API at once, app when built | The link is live now; the app URL says "building" | A page to write and a state the operator can see; the API never waits on Node |
| Serve whatever `dist/` is there | Stale for a moment after a pull | Only a missing `dist/` blocks anything |

**Ruling: the third, with the first as its cold case.** The supervisor builds when stale and the
old bundle answers while it does, which at 1.2 s is a moment nobody notices. With no `dist/` at
all — a fresh clone, a fresh worktree — it builds before opening the port, because one second
is cheaper than a page. **The capture route never waits on Node in either case**: when there is
no `dist/` AND the build fails, the API comes up anyway and the app path answers one plain
sentence naming the log, written in Python as a string and not a screen. A capture server that
refused to serve cards because a TypeScript file did not compile would be the wrong process
holding the other one hostage.

### 1.2 A build that fails — where do you find out?

The owner's answer was a question: *"it would have had to happen before merge, no?"* Yes, and
that is why this is small. `make ci-check` runs `lint` and `typecheck` on every PR, and the
main checkout only ever advances by `git pull` of a merged one (D42), so the operating form
on the main tree is always at a commit that typechecked. A failed build there is a dependency
that moved or a `vite.config.ts` error, not a half-edit. Half-edits happen in worktrees, which
serve their own `dist/` on their own port (D43).

**Ruling: the supervisor log and `make status`, and nothing in the app.** The same two places
a Python parse failure is reported today, and for the same reason: the last thing that built
keeps serving. The failure is written to `.serve/app-build.json` in the shape
`.serve/design-check.json` already uses — a verdict, a stamp, the first error line — and
`make status` reads it and says `app: stale, build failed 14:02, see .serve/supervisor.log`.
No banner, no notification. A macOS notification was considered and declined because a
sleeping Mac drops it and it would be the only notification this product sends.

### 1.3 The verbs — why so many?

`up`, `down`, `restart`, `status`, `launch-agent`, and `run` underneath them. The owner:
*"I have no clue why we have so many terms if it's not necessary."* Two of them exist only
because the other three were written before the launch agent was, and one exists to be typed
by launchd and never by a person.

**Ruling: `up`, `down`, `status`, and `launch-agent` for the login note.** The owner kept
today's split on `down` after the plain-words version — off now, back at login — so the login
agent stays its own verb in both directions, and `up` does not touch it.

- **`make up`** starts it if it is down. If it is already up and nothing is stale, say so and
  do nothing. If it is up and the code is stale — a `git pull` while it ran — the watcher has
  already reloaded what it watches, and `up` says what it found.
- **`make down`** stops the process and, as today, says the agent will start it again at the
  next login when one is installed. That sentence is the whole reason this stays a split:
  "off for now" is what the owner reaches for, and it says how to make it permanent.
- **`make status`** is unchanged.
- **`make launch-agent`** installs the login note; `ARGS=--remove` takes it down. Unchanged.
- **`restart` becomes `make up ARGS=--restart`**, and keeps `--confirm` on the main checkout
  for exactly D53's reason: the thing on `:8000` there is the owner's, mid-capture, and a
  session bouncing it cut a write in flight once. Fewer words does not mean fewer guards.
  `run` stays because launchd execs it; it was never for a person.

What goes, then, is one target (`restart`) and one process. The verbs were asked about
because there were many; the answer was that four of the five are each doing one thing, and
this touches D53's command surface in one place.

## 2. The shape

Before:

```
launchd ─ supervisor ─┬─ python capture_server.py   :8000   API + photos
                      └─ npm run dev (vite)         :5173   app, hot reload
```

After:

```
launchd ─ supervisor ─── python capture_server.py   :8000   API + photos + app/dist/
             │
             └─ vite build   (a child that runs for ~1s when app/src is newer than dist/)

make dev ──── vite dev server                        :5173   hot reload, talks to :8000
```

One long-lived child instead of two. The build is a short-lived child the supervisor runs and
waits on, like the parse pre-check it already runs on Python.

## 3. The static serve — PR 1

`server/capture_server.py` gains one thing: a `GET` that matched no route and starts with no
route prefix serves a file out of `app/dist/`.

**Order of resolution.** Routes first, exactly as today. Then, for `GET` only: if the path names
a file under `dist/`, serve it; otherwise serve `dist/index.html`. The hash router owns
everything after `#`, which never reaches the server, so the fallback is only ever for `/` and
for a path somebody typed.

**What is refused.** A path with `..` or a NUL, a path resolving outside `dist/` after
`realpath`, and any method but `GET`. `dist/` is compiled output and holds no photograph, no
code-card image and no store, which is why serving a directory from this process is not an
opsec question; `GET /photo/<box>/<index>` is still the only way bytes from `captures/` leave.

**Headers.** Vite names every asset with a content hash, so `assets/*` is `Cache-Control:
public, max-age=31536000, immutable`. `index.html` and `manifest.webmanifest` are `no-store`,
because they are what changes on a rebuild and a cached one would load hashed assets that no
longer exist. `Content-Type` by extension for the eight types Vite emits: `.html`, `.js`, `.css`,
`.svg`, `.png`, `.webmanifest`, `.woff2`, `.json`. **The origin gate is untouched**: it runs on writes, and this
is a read.

**The port is the tree's own (D43), and so is the shape** (owner's answer, 2026-09-11: same
shape everywhere). A worktree's `make up` is one process too, serving its own `dist/` on its
own capture port, built from its own source; a session that wants hot reload runs `make dev`
on its own dev port, which is what the Browser pane's `launch.json` already starts. One code
path, one supervisor, nothing forked by tree. Nothing new is derived: `server/ports.py:capture_port` already
answers, and the bundle bakes only the capture port and resolves the host from the address
bar (D53), which under one origin is trivially right.

**`dist/` absent.** Every route answers as today. `GET /` answers 503 with one sentence:
`the app is not built — the supervisor builds it; see .serve/supervisor.log`. Not a page,
not styled, not a screen.

**Proof, in T7:** a build placed under a temporary home; `GET /` returns `index.html` with
`no-store`; `GET /assets/<hashed>.js` returns the bytes with `immutable`; `GET /some/typed/path`
returns `index.html`; `GET /../etc/passwd` and `GET /assets/../../inventory/store.sqlite`
return 404 and read nothing; `POST /` is 405; with `dist/` removed, `GET /` is 503 and
`GET /status` is 200. Nine assertions.

**Nothing else moves in PR 1.** The supervisor still runs Vite; the new route sits unused
until PR 2 because there is no `dist/` on a machine that never built one. That is deliberate:
PR 1 is reviewable as a server change with a harness block, and cannot break the owner's
running product.

## 4. The supervisor — PR 2

`scripts/serve.py` loses the app child and gains the build.

**The watch set grows.** Today it watches `server/ store/ pipeline/ cli/ identify/ geometry/
codes/` for the capture child and its four `SELF_FILES` for itself. It adds a third set, `APP_SOURCES`:
`app/src/`, `app/public/`, `app/index.html`, `app/vite.config.ts`, `app/devPort.ts`,
`app/package.json`, `app/package-lock.json`. A change to any of these does not restart
anything; it schedules a build. **A change to a Python file still restarts the capture child
and never rebuilds the app**, and the reverse, so the two loops cannot trip each other.

**Staleness is one comparison.** `dist/.built` is a stamp the supervisor writes after a
successful build holding the newest source mtime it built from. Stale means any file in
`APP_SOURCES` is newer than that stamp, or the stamp is missing. On `up`, and on every poll
tick, stale means build. The same 300 ms debounce the Python watcher uses, for the same
reason: an editor saves twice.

**The build is a child, and the swap is atomic.** `npx vite build --outDir dist.next`, run in
`app/`, its output to the supervisor log under a `[build]` prefix. **Never into `dist/`
directly**: Vite empties its output directory before writing, so building in place would 404
every asset for the second the build takes and race any tab mid-load. On success:
`dist/ → dist.prev/`, `dist.next/ → dist/`, delete `dist.prev/`. Two renames on one
filesystem; a request in flight holds an open file descriptor and finishes. On failure:
delete `dist.next/`, leave `dist/` alone, write `.serve/app-build.json` with
`{"verdict": "fail", "at": ..., "error": "<first line>"}`, and log it. On success the same
file says `pass` and the stamp.

**The lock file is watched, and `npm ci` is the supervisor's too** (owner's answer, 2026-09-11).
`app/package-lock.json` newer than `app/node_modules/.package-lock.json` means `npm ci` runs
before the build, so a pull that bumps a dependency is fully self-applying. It fires rarely and
costs about thirty seconds when it does; the old bundle serves meanwhile. A failed install is
reported exactly like a failed build, and the old `node_modules/` is left as it was because
`npm ci` removes it first — so the verdict says `install failed` rather than `build failed`, and
`make status` names the fix.

**Node missing.** `npx` not on `PATH` is the one thing that can make the app half fail while
the capture half is fine, and it is the failure D53's plist section already names. The
supervisor treats it like a failed build: the API comes up, the log says `npx: not found —
see make launch-agent`, and `make status` says so. A `make up` from a terminal that has Node
will build; a launchd start without it will not, and will say why.

**The one child is the capture server.** `start()` no longer starts the app; `_note_exit`'s
retry, the fast-failure cap, the drain, the parse pre-check and the self-watch are all
unchanged. `supervisor.pid` and `capture.pid` stay; `app.pid` goes. The plist is regenerated
by `make launch-agent` with the same `PATH` baking, because the build still needs `npx`.

**`make dev`'s refusal narrows.** `do_guard_foreground` today refuses both `make server` and
`make dev` while this checkout's supervisor is up, because the supervisor held `:5173`. It no
longer does. `make server` is still refused, because `:8000` is still the supervisor's.
`make dev` runs beside it and talks to it, which is what a session editing screens wants.

**The verbs change as §1.3 says.** `up` gains `--restart`; `restart` becomes an alias that
prints the new spelling and runs it, for one release, then goes. `down` and `launch-agent` are
untouched.

**`make up` prints one link**, `http://localhost:8000`, and the LAN name beside it when
`PKMNSCAN_LAN_NAME` is set.

**`make status` grows one line**: `app: built 14:02 from 3 minutes ago` / `app: building` /
`app: stale — build failed 14:02, see .serve/supervisor.log` / `app: not built`.

**Proof, in a new self-test target for the supervisor** (`serve-selftest`, which PR 2 adds beside `janitor-selftest` and `merge-selftest` in `check`), against a throwaway checkout the way
`janitor-selftest` and `merge-selftest` already work — a copied tree with a stub `app/` whose
"build" is a script that writes one file, because the point is the supervisor's behavior and
not Vite's:

- up with no `dist/` builds before the port opens; the link prints after `dist/index.html`
  exists.
- touching a source file rebuilds once (debounced) and the stamp advances; the capture child's
  pid does not change.
- a build that exits non-zero leaves the previous `dist/` byte-identical and writes a `fail`
  verdict.
- during a build, `GET /` answers from the old `dist/` — asserted by a build stub that sleeps
  two seconds.
- `npx` removed from `PATH`: the capture child is up, the verdict names it.
- touching a Python file restarts the capture child and does not build.

Mutation-tested like its siblings: build in place instead of `dist.next` fails the fourth
arm; skipping the stamp fails the second.

**A docs-audit row, `app build files`,** reconciles the four names this section fixes —
`dist/.built`, `.serve/app-build.json`, `dist.next/`, the `[build]` log prefix — across
`serve.py`, `status.py`, the Makefile and this file, the way `verdict file` does for
design-check. Names that come apart silently are the failure that row exists for.

## 5. The dock app, the LAN, and what a port change costs — PR 3

**The dock app is reinstalled at `http://localhost:8000`, once.** D108's manifest is already
relative and needs no edit. Chrome's `Install page as app` from the new address writes a new
bundle; the old one at `:5173` is removed by hand.

**A port is part of the origin, and D135 did not say so.** Two things are keyed by origin in
Chrome and both reset once:

- **The camera grant.** D108 measured that the grant lives in the profile's content settings,
  which is true, and those settings are keyed `http://localhost:5173`. The first open at `:8000`
  prompts again. One press.
- **Every `localStorage` key** (D27): `banchi.capture.deviceId`, `banchi.capture.rotation`,
  `banchi.theme`, `banchi.rail`, `banchi.orders.fetch-filter`, `banchi.orders.last-check`.
  The rig re-picks its camera and its rotation once; the theme and the rail reset once. This
  is D27's rename cost repeated, and the same answer applies: no migration, because a
  fallback across origins is not even possible.

**`sessionStorage` is per tab and is lost anyway** on the tab close the reinstall implies.
Do it between shifts, not mid-capture, for the `captureId` reason D27 names.

**The LAN URL moves** from `pkmnscan.lan:5173` to `pkmnscan.lan:8000`. The UniFi record
names the host and not the port, so nothing changes there. `scripts/lan-check.py` presses the
app on the capture port instead of the dev port, and its docstring's URL follows. The phone's
home-screen bookmark, if one exists, is re-added.

**The docs.** `CLAUDE.md`'s `make up` block and the front-end section's opening sentence
("Vite + React 19 + TypeScript over the capture server" stays true; "the Vite app on :5173"
describes `make dev` only). `README.md`'s quick start. D53 gains an amendment paragraph
pointing here for the reversal of its `dist` rejection and `restart` folding into `up`; D108 gains
one for the port and the two origin-keyed resets. `docs/map.py` entries for `serve.py`,
`status.py`, `capture_server.py`, `lan-check.py`. `docs/DEBTS.md` names what §8 leaves
unmeasured.

## 6. What does not move, checked before writing this

- **`make dev`, `:5173`, hot reload.** Untouched. `app/devPort.ts` and `vite.config.ts` keep
  their port and their host allow-list.
- **`make design-check`.** Its `webServer` starts Vite per worker on the suite's own ports and
  never touches the supervisor. `app/tests/shell.ts:sealOutside`'s two-port allow-list (D124)
  is the dev port and the capture port; the app now also loads from the capture port, and
  the seal already admits it.
- **`make screenshot`.** Renders `make dev`'s port, which does not move.
- **`make demo-record`** spawns its own capture server on its own port; **`make demo-static`**
  already builds under `DEMO_BASE` to `dist-demo/`, which this never reads. The demo has no
  server and gains nothing from this.
- **The wire, the store, the packages, `PKMNSCAN_HOME`, the ports' derivation.** Nothing.
- **The worktree guard and the SessionStart hook.** They print the same two ports; only the
  sentence about which one the app is on changes.
- **The key-expiry restart.** One process reads `.env` once as two did. `envfile.get_live`
  for `ANTHROPIC_API_KEY` is the separate fix and is not in this plan.

## 7. The frozen form, deferred

D135 defers a promoted snapshot until a second person needs the app. If that day comes, the
shape is: a release target writes `app/dist/` plus the Python packages into a directory with
its own `PKMNSCAN_HOME`, and the launch agent points at that directory instead of the
checkout. Everything in §3 and §4 is a prerequisite for it and nothing in it is wasted. It is
recorded here so it is not re-derived, and not planned further because no such person exists.

## 8. What the first real week would measure

- Whether the build ever fires on the main tree from something other than a `git pull`, which
  would mean the tree is being edited in place.
- How often `make status` reports `stale`, and for how long. If it is ever more than a
  second, the debounce or the stamp is wrong.
- Whether the camera grant and the 4K mode carry at `:8000` exactly as D108 measured at
  `:5173`. Same engine, same profile, new origin. There is no reason they would not, and it
  is the one thing here that touches the rig, so it is measured rather than assumed.

## 9. The PRs, in order, and what each showed

| PR | Landed | Proof | What the owner sees |
|---|---|---|---|
| 1 | The static serve in `capture_server.py` | T7's `check_app_serve`, 24 assertions; `make harness` green | Nothing changed on their machine |
| 2 | The supervisor's build, the verbs, `make status`'s line, the guard narrowed | `serve-selftest`, 25 assertions over two throwaway trees; `make check` green | `make up` prints one link; two processes become one |
| 3 | `lan-check` on the capture port, the docs, D53 and D108 amended | `make docs-audit` green; `make lan-check` still to run from the phone | One reinstall, one camera prompt, one theme reset |

**PR 1 narrowed as it was built, and the narrowing is the interesting part.** The plan said the
fallback would serve `index.html` for any unmatched path, which is what every SPA host does. Written
that way and measured against this server, it turned `GET /boxes/abc` into 200 HTML and would have
made a dozen named JSON refusals unreachable with nothing failing. The hash router is why it is not
needed: `App.tsx` never puts a screen in the path, so the only paths the app has are `/` and its own
asset files, and `app_claims` is exactly that. The catch-all was withdrawn.

**PR 2 changed one of the plan's own mechanisms.** `npm ci` was to fire when `package-lock.json`
was newer than npm's receipt. Measured in this worktree: it was, with identical content, because
git rewrites a file's modification time on checkout — so every branch switch would have spent thirty seconds
re-installing a current tree. The comparison is a content digest now. The BUILD still compares
those times, and the asymmetry is deliberate: a spurious build costs 1.2 seconds.

## 10. What is NEITHER built nor recorded: the two presses

Both are the owner's, on their own machine, and neither can be done from a session:

1. **Reinstall the dock app at `http://localhost:8000`** and remove the old one at `:5173`.
   Expect one camera prompt and one reset of the six device-local keys; §5 says why and D108's
   amendment records it. Between shifts, not mid-capture.
2. **Run `make lan-check` with the phone on the network.** The rows now press `:8000` for the
   app; nothing about the UniFi record changes, and the phone's bookmark moves to that port.

Until the first of those, the main checkout serves the app on `:8000` and the dock icon still
points at `:5173`, which after a `make up` on the new code is a Chrome error page. That is the
one moment this change is visible as a chore, and it is one press.
