## 11 — A writer parked on the store lock still holds a request slot, and the heavy lock-free reads wait behind it

**What is bounded.** `server/capture_server.py` serves on `class CaptureServer(ThreadingHTTPServer)`
with `request_queue_size = 128`. A `ThreadPoolExecutor` runs one request per worker. Every response
sends `Connection: close` from `end_headers`, 304 included. A worker therefore lives for one request
and never for one keep-alive connection. `CaptureHandler.timeout = 15` reaps a socket that never
sends its request line. `REQUEST_SLOTS = 4` bounds executing requests. A semaphore keeps that bound
if the pool is ever widened. The slot is taken before the request counts as in flight, so the
supervisor's drain never waits on a queued request. The wait is `files.LOCK_TIMEOUT_SECONDS`. The
refusal is `server_busy`.

**The lane.** `PHOTO_SLOTS = 4` bounds a second pool with its own semaphore and its own refusal,
`photo_busy`. It carries what needs no store lock: `GET /photo/...`, `GET /assets/...`, and the exact
routes in `PHOTO_LANE_EXACT` (`/status`, `/queues`, `/capture/sitting`, `/games`). The cost of
`/queues` and `/capture/sitting` on a store of 2,500 cards is unmeasured. `photo_lane_path` is the one predicate. One sorter thread peeks each
connection's request line and picks the pool. `_dispatch` gates by the parsed path, so a wrong sort
costs a lane and never the bound. A fault in the sorter degrades the server to the slot pool alone.

**Why 4.** GIL-bound work slows down as concurrency rises. On the owner's store the sweep gave 53
requests per second at one slot and 12 with no bound. The value is 4 and not 1 because a writer
blocked on the store lock keeps its slot for up to `LOCK_TIMEOUT_SECONDS`. One slot would let one
writer stall every read. The lane sweep was flat from 2 to 16 for throughput. The `/status` probe
collapsed at 16.

**The gap.** Four writers parked on the lock still hold all four slots. Every read outside the lane
then waits for a slot. These reads are `/orders`, `/inventory`, `/inventory/<box>`, `/boxes`,
`/search`, `/pricing`, `/graveyard` and `/pipeline/*`. Each answers with the lock held (probed on
a scratch store), and each waits. They stay out of the lane on purpose. They are heavy and
GIL-bound. Sharing the photo bound with them would starve photographs. Before the lane, six looping
`/orders` readers took photo p50 from 5 ms to 136 ms. Two fixes would close the gap. One is a third
bound for heavy reads. The other is a writer that gives its slot back while it waits for the lock.
Neither is built. Unmeasured: how long a parked writer waits on the owner's real store.

**Lock-free has one exception.** The first open after a schema upgrade, a legacy import or a
NULL-cid repair takes the lock (`db.connect`'s `_ensure_schema`, `_upgrade` and `_repair`). A
lane read can wait then too.

**How to measure it now.** A request over `SLOW_REQUEST_SECONDS` (2 s) writes one line to the
server log, starting `slow request:`. It gives the route, the total, the slot wait with its pool,
the store lock wait, and `supervisor_busy`. That field reads `app-build`, `app-change`, `sync`,
`restart` or `source-change` from `.serve/busy`, which the supervisor writes while it works. A
stall with a high `lock_wait` is this gap. A stall with `supervisor_busy` set is a rebuild or a
sync. A high total with neither is the request's own work. `make status` prints the last five
under SERVING. The line holds no query string and no card data.

**Proof.** `harness/tests/t7_store_and_seams.py:check_lockfree_lane` parks `REQUEST_SLOTS` real
writers on a held store lock. It requires `/status` and each `PHOTO_LANE_EXACT` route to answer 200
within 3 s, while a slot-pool read stays parked. It goes red with `PHOTO_LANE_EXACT` emptied.
`check_photo_lane` proves the lane's own bound and refusal. `check_photo_lane_threads_and_faults`
proves the lane's thread bound and the sorter's degrade. `check_request_slots` proves the slot
bound and the in-flight order, on `/inventory`.

**A wedge is not fixed by a restart.** Never restart the owner's server. `make launch-agent` keeps
it alive over a real store, and a kill with a write in flight is not survivable. `make
design-check` on a fleet of browsers is the known trigger. Run the full suite once, at the end.
