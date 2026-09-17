## 11 — The capture server bounds concurrent requests, not threads, and a Playwright fleet is what finds out

`server/capture_server.py` serves on `class CaptureServer(ThreadingHTTPServer)` with
`request_queue_size = 128`. **`request_queue_size` bounds the ACCEPT BACKLOG, not the thread count**:
once a connection is accepted it gets a thread of its own, `daemon_threads` is true so `socketserver`
does not even record it, and `protocol_version` is HTTP/1.1 — so that thread lives for the whole
keep-alive CONNECTION rather than for one request. Nothing anywhere bounds how many of those exist.

**`CaptureHandler.timeout = 15` is not that bound and does not claim to be.** It is a socket timeout,
so it reaps a thread parked on `readline` for a request that is never coming — every connection a
closed tab leaves behind. Its own comment states what it does not fix, and it is right: an ACTIVE
connection performs socket operations, so no idle timeout touches it.

**Measured three times on this machine, and the third was avoidable.** (A fourth attempt, the load
sweep that was supposed to size the bound below, reproduced nothing — see what is still owed.)

1. **1,178 handler threads alive at 1,318% CPU**, twice in one working day, every one blocked in
   `PyEval_AcquireThread` — waiting for the interpreter lock, not for the store — with the process
   holding its port and answering nothing. This is what bought `timeout = 15`.
2. **80 Playwright browsers under `make design-check`: 969 threads inside ten minutes at 338% CPU**,
   measured immediately after that landed, which is how we know the idle timeout does not cover it.
3. **2026-09-04, a session's own doing.** It ran `make design-check` about eight times against the
   owner's live server while also driving it from hand-rolled Playwright scripts, then ran the
   `restart` target — the spelling of that day, folded into `make up ARGS=--restart` and removed
   by D138. The supervisor's drain — `DRAIN_GRACE_SECONDS`, which is
   `store/files.py:LOCK_TIMEOUT_SECONDS` (30) plus ten — expired with requests still in flight, and
   it killed the server outright: *"capture server did not stop within 40s — killing it. a request in
   flight was cut."* That crashed Python out from under the owner mid-use. No data was lost.

**`make design-check` is therefore a known trigger, not a surprise.** The suite is not the thing to
give up — it is the verification this repo runs on. What follows from this section is narrower and
sharper: **do not restart the owner's capture server to fix it.** `make launch-agent` keeps that
process alive at login over a real store; a wedge is survivable and a kill with a write in flight
is the thing that is not. Run the full suite once at the end rather than after every edit, prefer the
Browser pane over hand-rolled scripts against the live app, and when a browser page must be closed,
navigate it to `about:blank` first — a page closed mid-response leaves the handler writing to a dead
socket, which is why `.serve/capture.log` holds thousands of `BrokenPipeError` traces.

**The FIRST of two bounds landed 2026-09-04, and it is narrower than this section's title.**
`REQUEST_SLOTS` and a `threading.BoundedSemaphore` around `_dispatch` cap how many requests EXECUTE
at once, which is the resource the measurements above say ran out — the interpreter, not sockets and
not threads.

~~A connection parked between keep-alive requests holds no slot, so the idle-worker question a real
pool has to answer never arises here.~~ **That sentence was overtaken thirty lines below, in the
same section, on the same day.** The pool landed too, and the idle-worker question is exactly what it
had to answer — the answer being `Connection: close` on every response, which makes a worker's life
one REQUEST rather than one connection. Both bounds are in the tree: the semaphore still caps
execution, and `CaptureServer.process_request` submits to a `ThreadPoolExecutor(REQUEST_SLOTS)` so
threads are capped too. Read this paragraph as the account of the first bound and the one below as
the account of the second; neither replaced the other.

**`REQUEST_SLOTS = 4`, and this line exists because the sweep table below could not carry that
claim.** The table publishes the whole sweep — 1, 2, 3, **4**, 6, 8, 12, 24, 48, unbounded — so
the live value appears there only as a bolded column heading among nine others. `make
docs-audit`'s `server concurrency` row compared the code's figure against *anything* the section
said, and a bare `4` in a row of slot counts satisfied it. Measured 2026-09-05: swapping the two
constants — `CaptureHandler.timeout` to 4 and `REQUEST_SLOTS` to 15 — left this document wrong
about both, sized the pool at the value this section calls within noise of no bound at all, and
the row still reported `ok`. The row now demands the attributed form, which is this sentence, and
the same is already true of `request_queue_size = 128` and `CaptureHandler.timeout = 15` above.

The slot is taken *before* `_inflight_enter`, deliberately: a request
queued for one has not started and cannot finish, and counting it would make the supervisor's drain
wait out its grace on work that is not happening and then kill it — the incident above, one layer
down. The wait is `files.LOCK_TIMEOUT_SECONDS` (30) and the refusal is `server_busy`, beside
`store_busy`; 30 sits inside the 40s drain by construction, so a queued request always resolves one
way or the other before the drain gives up.

**Measured on the owner's own store, 2026-09-04, on their explicit word** — 1,625 cards, 20 orders,
read-only routes throughout (`/orders`, `/boxes`, `/search`, `/status`; no captures, no writes), 150
concurrent keep-alive connections, 20s per run. The first attempt at this used a scratch store and
proved nothing, because every endpoint there answers in under ten milliseconds and nothing contends
the interpreter. `/orders` on a real store resolves every open order against the whole inventory, and
that is the load this failure needs.

**The collapse reproduces, and the figure that shows it is not throughput.** A single probe request —
one connection, one `GET /status`, the shape of a person pressing something while the fleet runs:

| connections | served | errors | probe |
|---|---|---|---|
| 50 | 199 | 0 | **6.5s** |
| 150 | 216 | 132 | **18.2s** |
| 300 | 187 | 44,267 | **failed outright** |

That is section 11's *"holding the port and answering nothing"*, reproduced on demand. Thread count
peaked at 153 for 150 connections and fell back to 3 within twenty seconds of the load stopping —
**so `CaptureHandler.timeout = 15` does exactly what it claims**, and what accumulates under load is
active connections, which no idle timeout can touch.

**The sweep, at 150 connections, and it has no plateau — it is monotonic.**

| `REQUEST_SLOTS` | 1 | 2 | 3 | **4** | 6 | 8 | 12 | 24 | 48 | unbounded |
|---|---|---|---|---|---|---|---|---|---|---|
| requests/sec | 53.0 | 51.1 | 46.3 | **43.5** | 32.8 | 21.9 | 17.4 | 16.6 | 15.3 | 11.9 |
| probe p50 | 3.3s | 3.4s | 3.6s | **4.2s** | 5.9s | 9.6s | 14.0s | 16.7s | 11.4s | 12.9s |
| errors | 0 | 0 | 0 | **0** | 0 | 2 | 7 | 21 | 121 | 90 |

**Less concurrency is strictly better here, which is what GIL-bound work looks like** and is the
opposite of the intuition that sized the first guess at 12 — a value this table puts within noise of
the unbounded server it was meant to improve on.

**So the benchmark says 1 and the value is 4, and the difference is a hazard the benchmark cannot
see.** A request that blocks on the store lock HOLDS ITS SLOT for up to `LOCK_TIMEOUT_SECONDS` — the
30s a capture legitimately waits out behind a running `./pkmnscan identify`. At 1 slot a single such
writer stalls every read on the server; at 2 it takes two. Four keeps 82% of the best throughput
measured and leaves three slots when one is blocked. **That half is reasoned rather than measured**,
because measuring it means firing real captures at the owner's store while its lock is held, and this
section exists to say that is not something a session does on its own.

**What is proven besides the numbers is the mechanism**, by
`harness/tests/t7_store_and_seams.py:check_request_slots`: with more callers than slots, exactly
`REQUEST_SLOTS` execute, the queue is not counted as in flight, and every slot is given back.

~~It was observed failing twice — with the semaphore removed, and with the slot taken after the
in-flight count rather than before it.~~ **THAT SENTENCE WAS MEASURED FALSE ON 2026-09-08, ON BOTH
COUNTS, AND THE CHECK IS REBUILT BELOW.** Whatever was observed when it was written, neither
mutation failed the check in the tree: the semaphore replaced by an unconditional pass left all six
assertions GREEN, and so did moving `_inflight_enter()` ahead of `_slots.acquire`. Two reasons, and
they compound:

1. **The instrument was part of the mechanism.** Every assertion read `capture_server.slots_in_use()`,
   which is `REQUEST_SLOTS - _slots._value` — the semaphore's own counter. Delete the semaphore and
   that counter is never acquired, so it reads **0**, and `0 <= REQUEST_SLOTS` passes while measuring
   an absence. The check reported `held 0` and called it a pass.
2. **The pool supplied the number the semaphore was supposed to.** `ThreadPoolExecutor(REQUEST_SLOTS)`
   plus one request per worker already bounds execution at four, so even an honest counter reads four
   with the semaphore gone — this section says as much two paragraphs down (*"`REQUEST_SLOTS` never
   blocks today"*). The in-flight assertion was vacuous for the same reason: only four callers ever
   reached `_dispatch`, so `inflight` was 4 whichever side of the acquire the count was taken.

**The check is three legs now, and each names the mutation it is kept for.** Leg 1 is the shipped
transport and asserts THREADS. Leg 2 hands the server a deliberately oversized pool, so the semaphore
is the only thing left that can hold execution at the bound, and counts occupancy with a counter the
route increments itself rather than with `slots_in_use()`. Leg 3 drives the `server_busy` refusal,
which is unreachable over the shipped transport for leg 2's reason and had therefore never run.

**LEG 2 READS ON A CONDITION AND NOT ON A CLOCK, AND ITS FIRST DRAFT DID THE OTHER THING.** That
draft slept half a second after the occupancy reached the bound and then read it, reasoning that an
unbounded build would have filled up by then. That is a wall-clock bet taken on a machine running the
rest of this suite, and its failure direction is the bad one: it can only ever go SILENTLY GREEN — a
loaded box where the excess callers are late reports a bound it never watched fill. It cannot flake
red, which is precisely what would have kept it from ever being noticed. The leg shortens the slot
wait for its own duration instead, so every excess caller RESOLVES rather than parking: in the
shipped tree exactly `REQUEST_SLOTS` get inside and hold, and the rest are refused 503. The read
happens once `inside + answered` covers every caller — a fact about the callers, with no interval to
be unlucky in — and that count is asserted first, so the guard on the guard fails loudly rather than
passing early. **The refusals are also the positive half**: six callers saying they reached the
semaphore and were turned away is evidence, where six callers merely missing from an occupancy count
is the absence of it.

The determinism is the argument and the runs are the corroboration: 12 consecutive runs clean, and 6
more clean with 30 busy-loops pinning a 15-core machine — the contention that would have exposed the
timed draft. Every run reports the same reading, `4` inside and `6` refused, in 1.5s.

Measured 2026-09-08 against the same four mutations:

| mutation | before | after |
|---|---|---|
| `_slots.acquire` replaced by a pass | green | **leg 2 fails: peak 10 inside `_dispatch`, 0 refusals where 6 are owed, and leg 3 gets none either** |
| `_inflight_enter()` moved ahead of the acquire | green | **leg 2 fails: 10 in flight against 10 callers** |
| the pool replaced by a thread per connection | fails | fails (leg 1: more server threads than the bound, 6 observed for 10 callers — the figure is a race and the assertion is `<=` `REQUEST_SLOTS`, not that number) |
| `Connection: close` deleted from `end_headers` | n/a | n/a — `check_connection_close`'s subject, and it fails there in 5s rather than hanging |

**What is still not covered, and it is the same thing as before.** These legs prove the MECHANISM on
an empty store. They do not prove the bound fixes the failure this section records — that took 80 real
browsers against a real store, and the reproduction was attempted and failed on a scratch one, where
every endpoint answers in under ten milliseconds and nothing contends the interpreter. **And nothing
in the browser suite touches this server at all**: `app/tests/shell.ts:sealEveryTest` registers a
catch-all `page.route` on this checkout's capture origin, ABORTS every request to it, and asserts in
`afterEach` that none was attempted. Every spec that drives a page calls it; the one that does not is
`app/tests/motion.spec.ts`, which has no page. Stated as a mechanism rather than as a count on
purpose — a count here would be a claim with no reader, which is what this document is about.
So `make design-check` — the load named at the top of this
section as what found the collapse — is no longer a reader of any of this, by design and correctly.
The Python harness is the only thing watching these bounds, which is why the legs above have to be
falsifiable rather than merely present.

**What the SEMAPHORE does not do is reduce thread count**, and the sweep says so in its own column:
153 threads at every value. Threads park on it instead of thrashing the interpreter, which is the
point, but they are still created.

**So the pool landed too, and this section's title is finally wrong in the right direction.**
`CaptureServer.process_request` submits to a `ThreadPoolExecutor(REQUEST_SLOTS)` instead of spawning
a thread per connection, and **every response sends `Connection: close`** — which is what makes a
worker's life one REQUEST rather than one connection, and therefore what makes a pool safe here at
all. Measured on the owner's store at 150 concurrent connections, against the semaphore alone:

| | requests/sec | probe p50 | peak threads |
|---|---|---|---|
| semaphore only | 45.6 | 3.84s | **153** |
| pool + `Connection: close` | 45.5 | 3.94s | **5** |

Identical within noise on both throughput and responsiveness, and the thread count is the whole
difference. The cost is a TCP handshake per request: microseconds on localhost, a millisecond or two
to a phone, against a capture cadence of ~600 ms per card.

**Where the header is sent from is part of the guarantee, and it moved on 2026-09-05.** It was
sent from `_send`, which is not every response: `_photo`'s 304 branch answers a conditional GET by
hand — `send_response`, the ETag headers, `end_headers` — and never touches `_send`. With
`Cache-Control: no-cache` making 304 the normal answer on a revisit, four concurrent revalidations
held all four workers until the 15s reap. It is sent from **`end_headers`** now, which every
response reaches by construction, so a new route cannot answer without it. That is the difference
between an invariant and a convention, and the convention had already been broken once by the route
that needed it most.

**The starvation this section warned about is real, and removing `Connection: close` demonstrates
it.** With keep-alive restored and the pool kept, four idle connections hold all four workers and
every other caller waits forever: `make harness` does not fail, it **HANGS**. That is worth stating
precisely — the failure mode of a pool over keep-alive is a deadlock, not a slowdown, which is why
the two changes are one change and neither ships without the other.

**`CaptureHandler.timeout = 15` is now unreachable and is kept anyway.** It bounds a thread parked on
`readline` for a request that is not coming, and no connection survives long enough to park.
`protocol_version` is one edit from making it matter again, and a guard that costs nothing is cheaper
than rediscovering why it was deleted.

**The semaphore stays, and it is not a second mechanism for one job.** With one request per worker the
pool size is also the bound on concurrent execution, so `REQUEST_SLOTS` never blocks today. It is the
INVARIANT rather than the implementation: on the day keep-alive returns, the pool bounds threads and
the semaphore is the only thing still bounding execution. T7 asserts both, and leg 2 of
`check_request_slots` stages that day rather than waiting for it — the pool widened past the bound,
so the semaphore is the only thing that can supply the number. The pool removed gives 5 to 10 threads
for 10 callers; the semaphore removed lets all 10 execute at once. Both were observed failing on
2026-09-08, and the paragraph above records what the same sentence claimed before then and what
actually happened when it was tried.

**THE FIRST OF THOSE TWO FIGURES IS A RACE AND THIS SENTENCE SAID `6` UNTIL 2026-09-11**, which is
the mistake this whole section exists to record, made while recording it. `6` was one draw. Measured
eleven times on the rebuilt check: `5, 10, 5, 10, 6, 10, 10, 10, 10, 5` — **10 is the mode**, and 10
is also what the figure said before the rewrite, so a correct published measurement was replaced by a
less representative sample of the same race. The assertion was never on the number: leg 1 asserts
`<= REQUEST_SLOTS`, which is why the table row beside it already named this as a race and why no
check went red over it. **A published figure is evidence and is never rewritten to match a later
draw** — a range is what an honest reading of a race looks like.

**So the real bound on thread COUNT is still open, and a worker pool is still what it needs.**

**The reason a pool is not a swap is written down rather than left to be rediscovered.** A pool of N converts unbounded degradation into back pressure: connection
N+1 waits in the accept queue instead of taking a thread. But over HTTP/1.1 keep-alive **a worker
held by an idle connection is a worker serving nobody**, so N idle browser tabs starve a pool of N
completely, and closing that needs one of: `Connection: close`, which throws away the thing
keep-alive is for; an idle timeout tight enough to free workers faster than tabs accumulate, which
is a constant with no safe value on a rig this repo already argues about elsewhere; or an event loop
where a connection is not a worker, which is a rewrite of the handler. **And refusing connections
rather than queueing them is already known to be dangerous here** — `CaptureServer`'s own docstring
records 20 simultaneous captures with 8 served and 12 reset by the OS. A dropped capture is one the
operator sees fail and retries; a pool must not make that the normal case.

**Why this section exists at all, which is the part worth keeping.** Every fact above was already in
the tree, in two comments inside `server/capture_server.py`. On 2026-09-04 a session diagnosed this
failure from `.serve/supervisor.log` and `.serve/capture.log` without opening that file, told the
owner the server was single-threaded, and then proposed `ThreadingHTTPServer` as the fix — the class
it has been built on all along. **Nothing that session did read would have corrected it**: `CLAUDE.md`
said nothing about concurrency, and `docs/map.py`'s entry for the file describes route shapes by
deliberate choice. Knowledge reachable only from inside the file it is about is knowledge a session
diagnosing from the outside will not have. `make docs-audit`'s `server concurrency` row now pins the
class, the timeout and the backlog in this section against the code, so a future worker pool cannot
land while this section still describes threads.
