## D53 — One link, always live, and the restart discipline becomes machinery

**`make up` runs both servers under a supervisor that reloads them when their source changes.** Built 2026-08-30, from the owner asking to stop running the project the way it had always been run: go to a link, get the live version against local storage, and have an edit picked up without remembering to restart.

**The restart shenanigan is a recorded defect, not an inconvenience.** `docs/GATES.md` holds the measurement: `store/master.py:now()` was changed to milliseconds at 20:16, box 95's run at 22:08 still wrote whole-second stamps, and the cause was not the code — the server process serving it had started before 20:16 and was holding the old code in memory, which no commit can reach. That file calls it a restart discipline. A discipline is what you have instead of a guard, and this repo has been here before: D42 exists because it already was a line nobody had written, and main moved under three live worktrees twice in one day. `scripts/serve.py` is that lesson applied to the server.

**`make server` and `make dev` are untouched.** A session wanting a foreground server in a terminal it is watching still has one, and that one still does not watch files, so `docs/GATES.md`'s discipline goes on governing it.

**Rejected, and it led until the owner answered: building the app to `dist` and serving it from the capture server.** It collapses two processes into one, and `app/package.json` has carried an unused `build` script the whole time. It is the wrong answer to *this* request, because a built bundle has to be rebuilt — it would ADD a step to remember in exchange for removing one. Vite stays, and it was already the half that worked.

**Amended 2026-09-11 — that rejection is reversed, on the one ground it gave (D138).** The owner asked for an easier way to package this, and the answer to "a built bundle has to be rebuilt" is that the rebuild is now the SUPERVISOR's job: `app/src` and `app/public` get their own watch set, a change there runs `vite build` into a sibling directory and renames it in, and nothing is added to anybody's memory. Measured before it was built: a cold build of this app is 1.2 seconds, which is what makes the old bundle answering meanwhile a moment nobody notices rather than a window to design around. **Everything else in this entry stands and now governs one child instead of two** — the drain, the parse pre-check, the fast-failure cap, the self-watch, the liveness probe and the launch agent are untouched. What is gone from this file is `spawn_vite`; what is gone from the operator's day is a second port. The full argument is D138 and the plan it names is `docs/specs/one-process.md`.

One thing in this entry's own list changed with it, and it is the guard rather than the list: **`make dev` is no longer refused beside a running supervisor.** That guard existed because both ways of starting wanted the same two ports, and the supervisor no longer holds `:5173` at all. `make server` is still refused, because `:8000` is still the supervisor's and the squatter this entry measured is still exactly what would happen.

### The drain is counted on requests, never on threads

Both halves measured on this machine's Python, and the obvious implementation is a no-op that looks like it works:

- `ThreadingHTTPServer` sets `daemon_threads = True`, and `socketserver._Threads.append` **discards a daemon thread** rather than recording it — so `_threads` is always empty and the join inside `server_close()` already does nothing. A version trusting it would pass every smoke test and lose requests.
- Setting `daemon_threads = False` does not fix it either. `protocol_version` is HTTP/1.1, so a handler thread lives for the whole keep-alive CONNECTION rather than one request, and `BaseHTTPRequestHandler.timeout` is None — the join would block forever on an idle tab.

So a counter wraps `_dispatch`, which every verb funnels through and which is entered after the request line is parsed and before the body is read. **`server_close()` first, then drain** — in the other order the wait races arrivals it cannot refuse and never reaches zero.

**Why it is worth building: `store/session.py:Store.write()` replaces four JSON files in sequence.** Each is atomic alone and none is atomic as a set, so a kill between them leaves a torn store. That risk exists today at Ctrl-C frequency and auto-restart multiplies it, which is why the drain is a PREREQUISITE for the watcher rather than a refinement, and why the two were built and verified in that order.

**`DRAIN_SECONDS` is derived from the lock timeout and was never chosen.** `files.LOCK_TIMEOUT_SECONDS` is 30, and a capture posted while `./pkmnscan identify` holds the store lock legitimately waits that long before answering `store_busy`. A shorter drain would cut a request that was behaving correctly and about to say so — the same argument `app/src/server.ts` makes one process over for having no client timeout below 30s. T7 asserts the arithmetic rather than the number.

**An unhandled SIGTERM was strictly worse than Ctrl-C**, which is what made the handler necessary rather than tidy: with no handler the default disposition terminates the process with no `server_close()` at all. **The hard kill survives and is loud** — after the grace period the supervisor sends SIGKILL, because an unkillable wedged server is worse than a cut request, and it names `history.jsonl` as where to look.

### The watcher

**It refuses to restart into code that does not parse.** Auto-restart *guarantees* the watcher observes half-written code: an editor saves mid-keystroke and a formatter writes again a beat later. Changed files are `compile()`d first, and on failure the last code that parsed keeps running while the log names the file and line.

**Its limit is stated where it is implemented: PARSE errors only.** An `ImportError`, a module-scope `NameError` or a bad constant still kills the new child with no rollback. The containment is the fast-failure cap — after five quick deaths the supervisor **stops respawning and keeps running, still watching**, so a broken commit cannot make it spin and cannot make it die, which under launchd would flap it forever. The next save retries.

The fingerprint is a `{path: (mtime, size)}` dict rather than a digest so the log can NAME the file that caused the restart — the only thing connecting an unasked restart to the save that produced it.

**Mtime polling rather than `watchdog`, for two reasons.** The Makefile's invariant is that the capture server must never NEED `make venv`. And FSEvents coalesces and delivers directory-level events with its own latency, so the debounce would still be needed and the dependency buys nothing.

### The LAN half was never the server

**`HOST = "0.0.0.0"` has been there since it was written**, so the capture server has been reachable from the network the whole time and this adds no new listener. **The client was the broken half**: `app/devPort.ts` composes `http://localhost:${CAPTURE_PORT}` and `vite.config.ts` bakes it into the bundle, and on a phone `localhost` IS THE PHONE.

**So only the PORT is baked and the host is resolved at runtime** from `window.location`. It keeps every property the injected URL had — the port still comes from the same slot as the Vite port, so a worktree's UI still cannot be answered by another tree's server (D43) — and adds the one it lacked: it follows the address bar. This **honors `VITE_CAPTURE_SERVER`** rather than overriding it; that knob exists so the Fulfiller's device can be pointed at this Mac by address, which was necessary only because the default could not follow the address bar. It still wins, and is still the answer for a DIFFERENT machine.

**`server.host` was half the Vite change and the hostname test found the other half.** `host: true` makes Vite LISTEN on every interface; it does not make it ACCEPT every name. Vite refuses a request whose `Host` header it does not recognize — DNS-rebinding protection — so the app answered fine at `http://192.168.1.125:5366` and returned *"Blocked request. This host (\"pkmnscan.lan\") is not allowed"* at the name the operator would actually type. **Reaching it by IP is not a test of reaching it by name**, and only the second is the feature.

`allowedHosts` is `['.lan', '.local']` rather than `true`. A leading dot admits a domain and its subdomains, so the router's local record and Bonjour both work while an arbitrary public hostname pointed at this machine is still refused; both suffixes are non-routable on the public internet, which makes the narrowing meaningful rather than decorative. `true` would switch the protection off for every name and was declined.

**The origin allowlist needed no code change.** `PKMNSCAN_ALLOWED_ORIGINS` already existed, is documented, is read fresh per request, and **extends the defaults rather than replacing them** — and `*` is compared as an exact string, so it refuses everything rather than reopening the hole (T7 asserts this). The supervisor composes the value from this Mac's Bonjour name and `PKMNSCAN_LAN_NAME`. `scripts/serve.py` may not import the capture server, so it lifts `ORIGINS_ENV` with `ast` — the docs audit's own idiom; the alternative was a second hand-written spelling whose only symptom when it drifted would be writes silently 403ing from the LAN.

**What is genuinely widened: writes from a LAN origin are now accepted.** Reads always were. This is the point — D5 puts the Fulfiller on his own device — and it is still a real change to what a machine on the same network can do. Verified both ways: a write from the named host answers 201, one from an unknown origin still answers 403.

**`PKMNSCAN_LAN_NAME` lives in `.env`, not a shell profile**, and D47's amendment is why: an export in `~/.zshenv` fixes an interactive shell and does nothing for a process launchd starts, which reads no profile at all. **The owner's DNS is theirs and this repo does not touch it** — a DHCP reservation and a local DNS record on their UniFi map `pkmnscan.lan` to this Mac, and nothing in the code knows what the name is, which is the property runtime host resolution buys.

### The launch agent

**Generated, written outside the repo, and refused in a worktree.** A plist names an absolute path on one Mac; a tracked one would be D47's failure verbatim. `~/Library` is strictly better than gitignoring it — there is then no file in the tree to commit by accident — and `plistlib.dump` rather than a here-doc for `make launch-config`'s recorded reason: a hand-built plist is one escaping mistake from a file that presents as *the app does not start* rather than as a syntax error. `server/ports.py:agent_label` derives the label from the same slot as the ports, so two checkouts cannot install one label and silently replace each other.

**Main tree only, and the refusal is the design.** A worktree is deleted routinely and its plist would outlive it, leaving launchd retrying a path that is gone. `up`, `down`, `restart` and `status` work in every tree; only login-persistence is refused.

**`KeepAlive: {SuccessfulExit: false}` and not `true`, which is what lets `make down` win.** A process terminated by a signal is an *unsuccessful* exit to launchd, so `true` would restart the very thing `make down` had just stopped. The SIGTERM handler therefore always exits 0, and `make down` says — before the operator finds out tomorrow morning — that the agent will start it again at the next login.

**It also said `make down` prefers `launchctl bootout` when a plist exists, and that clause is deleted rather than repaired.** Both halves of its reasoning were wrong.

- **Wrong about the premise.** With the handler exiting 0, a signalled supervisor is a SUCCESSFUL exit and launchd leaves it alone, so signalling never needed avoiding. Measured: SIGTERM to a launchd-started supervisor left no process, no pid in `launchctl print`, and no listener on either port.
- **Wrong about which process.** `bootout` acts on the SERVICE, not on whatever is running — so when the live supervisor had been started by `make up`, bootout applied to nothing and `down` printed `stopped.` over a supervisor that was still up. `make launch-agent` then bootstrapped a second one, whose capture child could not bind, gave up after five retries, and overwrote `supervisor.pid` with its own pid. Two supervisors: one serving, one supervising nothing, and the pidfile naming the wrong one.

**It is the same defect as the liveness probe, one commit later.** Both are an action reporting success on the strength of something that did not apply to the process in question — the probe asked the socket instead of the child, this asked launchd about a service instead of the pid that was there. The probe was fixed and this survived, because it sat in a branch nobody re-read while fixing its twin. One path now, acting on the pid that is actually running.

**`EnvironmentVariables.PATH` is baked** because launchd gives an agent a minimal PATH and `npm` is otherwise not found, so the app half never starts while the capture server looks fine. If npm comes from nvm, an `nvm install` moves it and the agent needs regenerating.

### Liveness

**`make status` reports it, which it never has.** `ports_and_store()` printed which ports this tree WOULD use and never knew who holds them. **The third branch is what earns it: a port that answers while no pidfile in THIS checkout claims it** — D43's fault made visible for the first time, and previously undetectable from inside the tree it was happening to.

**The pid guard compares the full path and not the basename, and the first version did not.** `pipeline_routes.py:_live_pid` is the house pattern and only ever READS, so a recycled pid there is a run wrongly reported busy. `make down` SIGNALS a process group, so the same mistake kills an unrelated process tree — and here it is not hypothetical, because every checkout runs a file called `capture_server.py` and an `npm run dev` under a directory called `app`. A basename check answers *yes, that's ours* for another tree's server.

**A half-started stack is not a started stack, and `make up` reported one as started** (found on the owner's machine 2026-08-30, hours after this entry landed). A bare `make server` held `:8000`; `make up` then started the app, spawned a capture child that could not bind, retried five times, hit the fast-failure cap and stopped. The end state served the app off the SQUATTER — right store, right data, and **no file watching at all**, so a `git pull` would not have been picked up. Everything looked healthy.

**The root defect was the probe: `wait_for_port` asked the SOCKET, not the child.** A port another process holds answers exactly like one of ours does, so `make up` reported the stack up on the strength of the squatter's reply:

    pkmnscan is up
. **A liveness probe another process can satisfy is not a liveness probe** — it now takes the child and returns failure the moment that child is gone.

**The collision itself is untouched and must stay loud.** D43 is why: a server that quietly moved to a free port would serve a DIFFERENT store. What was wrong was never that two things wanted one port; it was that the system settled into a working-looking half of itself and said so. Four guards, none weakening the collision:

- **The probe takes the child**, so a squatter can no longer be mistaken for success.
- **`start()` will not start the app if capture did not come up.** The app alone is not a product, and the half that failed is the whole reason this supervisor exists.
- **A held port is not a retryable crash.** `_refuse_capture` says who holds it and stops; burning five retries and a backoff on a condition that cannot change without a human was the old behavior and it produced the silent end state. `_note_exit`'s retry is for a child that started and died, the opposite case.
- **`make dev` and `make server` refuse while this checkout's supervisor is up**, which is where the squatter comes from. `PKMNSCAN_FOREGROUND=ok` bypasses, the shape `PKMNSCAN_MAIN=off` already uses.

**`make up` preflights the port before spawning anything**, so the refusal costs no processes — and it prints the TAIL of the holder's command line rather than the head, because `ps` leads with a 96-character interpreter path and a head-truncated line identified the process as *Python* and nothing else, on the one output whose whole job is telling you which process to kill.

**`make launch-agent` is not this fix** and was asked about as though it might be. It makes `make up` the canonical starter, so a hand-run `make server` becomes rare — it prevents nothing, and under `KeepAlive` it would restart the supervisor into the same wall.

### The supervisor watches itself

Added 2026-08-30, from the owner asking how they would know whether a change touched `scripts/serve.py` — the one file the watcher did not cover, because it is the watcher. Answering it turned up a worse sibling nobody had noticed.

**`server/ports.py` and `store/files.py` were ALREADY watched, and that made it invisible.** A change to either restarts the capture CHILD — in the log, at the usual speed, looking exactly like the fix landing — while the supervisor goes on running the module it imported at boot, because Python caches an imported module. Something restarts, so nothing looks wrong. The `scripts/serve.py` case at least failed silently in both halves; this one failed while appearing to succeed.

`SELF_FILES` is the four files this supervisor is made of — itself, `envfile.py`, `server/ports.py`, `store/files.py` — and a change to any of them re-execs the process rather than restarting a child.

**`os.execv`, which keeps the PID**, and that is the whole reason to use it rather than spawning a replacement and exiting: `supervisor.pid` stays valid, and launchd sees the same process it started instead of an exit it would race to restart. Children are stopped FIRST, because exec throws away every `Popen` handle — anything still running would be orphaned, holding the ports the new image is about to want. The parse pre-check applies as before; if exec fails anyway the children are rebuilt and the log says the old code is still running.

**The Makefile is not in that set, and saying otherwise was wrong.** It was claimed once in conversation that a Makefile change also needs a restart. Three comments in `scripts/serve.py` mention the Makefile and nothing reads it; `make` re-reads it from disk on every invocation, so it cannot make a running process stale. Corrected here rather than left standing, because a rule that names one file too many is how the real list stops being read.

**`scripts/docs-audit.py`'s `supervisor self-watch` row is what keeps the list honest.** A hand-written list of a file's own imports goes stale the next time somebody adds one, and the failure it would reintroduce is the invisible one above. The row parses `serve.py` with `ast`, resolves its module-scope imports against the tree, and blocks on any project-local import missing from `SELF_FILES`. Mutation-tested: dropping `server/ports.py` from the list takes it red and names the file.

### The screen

**One press fetches and then joins, and the two are reported separately.** `#/runs`' join step carries the control. The fetch draws a receipt naming the file, the rows, the SKUs, the sets and the finishes, and says which games were checked against a previous export and which were not. A fetch that refuses does not join: it wrote nothing, so joining after one would silently re-use the previous export and look exactly like the fetch had worked.

**The join is handed the file by name, not the bytes.** The server already holds them.

**The control that waves a refusal through is absent unless the refusal is one an operator can answer.** `FETCH_ACK` lists the two codes that have an answer, and every other refusal draws its sentence and nothing to press. An expired session, a WAF block and an export for the wrong product line are fixed somewhere other than this screen, so a button there would offer to wave through a refusal the screen does not understand. Absent rather than disabled is D33's rule, for its reason: a disabled button is one attribute away from pressable. Retired 2026-09-02 with the two refusals it listed (D64, amended): every fetch refusal draws a sentence and nothing to press, and `FETCH_ACK` is gone.

**`app/tests/run-panel.spec.ts` asserts that absence at rest and after a clean fetch.** A control appearing once the panel had merely been used would be as wrong as one always there. Two mutations were observed failing: drawing the acknowledgement for every refusal, and joining after a refused fetch.

### What it costs

- **`RunAtLoad` does not survive the Mac sleeping.** A phone hitting a sleeping Mac gets nothing. Inherent to D13, written down now rather than found as a bug in three weeks.
- **An agent session restarts the owner's live server.** With the agent on the main tree, any session editing `store/` or `server/` bounces the server the owner may be capturing with. That is what was asked for, and a further argument for main-tree-only.
- **A request accepted but not yet inside `_dispatch` is uncounted.** Microseconds; closing it means reimplementing `handle_one_request`. Recorded in `docs/DEBTS.md`.
- **The swap gap.** Tens of milliseconds of `ECONNREFUSED` between children, which the client surfaces as `unreachable` because it deliberately has no retry. The fix, named and NOT built: the supervisor holds the listening socket and passes it to the child. Rejected for v1 because it turns a fast honest refusal into a hang when the new child fails to boot.

**D13 is not reopened.** The store, the photographs and the truth stay on this Mac. LAN reach is the tunnel case D13 already names as needing no code change, and the owner deferred off-site access to its own decision.

**What would reopen this: the watcher restarting during real capture work.** If the server bounces under the owner mid-box because a session saved a file, the answer is not to weaken the drain — it is that the agent and an active feeder run should not share a tree, which is one condition on `is_linked_worktree` away from what is already built.

---
