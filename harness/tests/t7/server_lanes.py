"""T7 group: request slots, photo lane, lock-free lane, slow line, connection close.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import base64
import contextlib
import io
import re
import threading
import time

from contextlib import redirect_stderr
from http import HTTPStatus
from harness.tests import Checks
from server import capture_server
from store import files
from store.session import Store
from scripts import serve
from harness.tests.t7.common import (
    QuietHandler,
    _spawn_server,
    error_code,
    error_message,
    isolated_home,
    request,
)

def check_connection_close(checks: Checks) -> None:
    """Every response closes its connection, INCLUDING the 304 — the pool's whole premise.

    `CaptureServer` submits one worker per CONNECTION and its own comment states the trap:
    "a worker holding an idle connection serves nobody, so N idle browser tabs starve a pool
    of N completely. Closing after every response is the answer, and it is why a pool is safe
    here and would not have been before."

    THE ANSWER HAD AN EXCEPTION AND NOTHING SAW IT. `_photo`'s 304 branch answers a conditional
    GET by hand and never touches `_send`, which was the only place `Connection: close` was
    sent. `do_photo` sets `Cache-Control: no-cache`, so a 304 is the NORMAL answer on any
    revisit rather than an edge — `GET /photo` is the app's most-requested route — and four
    concurrent revalidations held all four workers until `timeout = 15` reaped them.

    WHY `request()` CANNOT ASK THIS QUESTION. That helper sends `Connection: close` from the
    CLIENT, so the socket goes away whatever the server does and the starvation is invisible.
    The second leg therefore drives raw `http.client` connections and DELIBERATELY DOES NOT
    CLOSE THEM. Using the helper here would be the vacuous green this file keeps finding.

    THE MUTATION IT IS KEPT FOR: delete the `send_header("Connection", "close")` from
    `CaptureHandler.end_headers`. Before this check that mutation left T7 entirely green and
    showed up only as `make harness` HANGING, with no sentence naming a cause.
    """
    import http.client

    checks.note("")
    checks.note("Connection: close — the invariant one worker per request rests on")

    def blob(i: int) -> str:
        return base64.b64encode(b"\xff\xd8\xff" + bytes([i]) * 64).decode("ascii")

    with isolated_home():
        for i in (1, 2):
            capture_server.do_capture(
                {"box": 3, "capture_id": f"p{i}", "image": blob(i), "set_hint": "sv9"}
            )
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        held: list = []
        try:
            # ------------------------------------------------ leg 1: the header, every path
            status, _, headers = request(port, "GET", "/photo/3/1")
            etag = headers.get("ETag")
            checks.equal(status, 200, "a photo answers 200 with its bytes")
            checks.equal(
                headers.get("Connection"),
                "close",
                "and closes — the 200 photo path goes through `_send`, which always did",
            )

            status, _, headers = request(
                port, "GET", "/photo/3/1", extra_headers={"If-None-Match": etag}
            )
            checks.equal(status, 304, "an unchanged photo revalidates to 304")
            checks.equal(
                headers.get("Connection"),
                "close",
                "AND THE 304 CLOSES TOO — the branch that answers by hand, which sent no "
                "`Connection` header at all while the pool depended on it",
            )

            status, _, headers = request(port, "GET", "/status")
            checks.equal(
                headers.get("Connection"),
                "close",
                "and so does a JSON route, so the invariant is the handler's and not one "
                "route's",
            )

            # -------------------------------------- leg 2: the starvation the header prevents
            # RAW CONNECTIONS, HELD OPEN ON PURPOSE. Each one answers 304 and is not closed by
            # this client, so if the server does not close it the worker that served it is
            # still parked in `handle()` waiting for a second request that never comes.
            for _ in range(capture_server.REQUEST_SLOTS):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                conn.request("GET", "/photo/3/1", headers={"If-None-Match": etag})
                conn.getresponse().read()
                held.append(conn)

            started = time.monotonic()
            fresh = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            answered = True
            try:
                fresh.request("GET", "/status")
                fresh.getresponse().read()
            except Exception:
                answered = False
            finally:
                with contextlib.suppress(Exception):
                    fresh.close()
            elapsed = time.monotonic() - started

            checks.ok(
                answered and elapsed < 2.0,
                "REQUEST_SLOTS revalidations later, a fresh caller is still served at once "
                f"({elapsed:.2f}s) — every worker went back to the pool when its response "
                "closed. Without the close all of them are parked on an idle socket and this "
                "waits out `CaptureHandler.timeout = 15`",
            )
        finally:
            for conn in held:
                with contextlib.suppress(Exception):
                    conn.close()
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

def check_request_slots(checks: Checks) -> None:
    """The bound on concurrently-executing requests holds, and the drain does not see a queue.

    WHAT THIS PROVES AND WHAT IT DOES NOT, because the difference is the whole honesty of this
    check. It proves the MECHANISM: no more than `REQUEST_SLOTS` requests are inside `_dispatch`
    at once, and a request waiting for a slot is not counted as in flight. It does NOT prove the
    bound fixes the failure DEBT11 records — that took 80 real browsers
    against a real store, and the reproduction was attempted and failed on an empty one, where
    every endpoint answers in under ten milliseconds and nothing contends the interpreter.

    THE `_inflight` HALF IS THE ONE WITH TEETH. `drain()` waits on that counter, and a request
    parked on the semaphore has not started and cannot finish — so if the slot were taken after
    the count rather than before it, the supervisor's drain would wait out its whole grace on
    work that is not happening and then kill it. That is the exact shape of the incident this
    bound came from, one layer down.

    THREE LEGS, AND THE SECOND AND THIRD EXIST BECAUSE THE FIRST WAS MEASURED VACUOUS OVER THE
    SEMAPHORE ON 2026-09-08. Leg 1 read the bound through `slots_in_use()`, which is
    `REQUEST_SLOTS - _slots._value` — the semaphore's own counter. Delete the semaphore and that
    instrument reads **0**, so `held <= REQUEST_SLOTS` and `max(seen) <= REQUEST_SLOTS` both pass
    while measuring an absence. Mutation run: `_slots.acquire(...)` replaced by an unconditional
    pass and the matching `release()` removed — the whole check stayed GREEN, reporting
    `held 0`. Section 11's claim that this was "observed failing … with the semaphore removed"
    is corrected there; what fails under that mutation is nothing, and leg 2 is why it does now.

    AND THE POOL IS THE CONFOUND, WHICH IS WHY LEG 2 WIDENS IT. `ThreadPoolExecutor(REQUEST_SLOTS)`
    plus one request per worker means the pool ALREADY bounds execution at four, so an
    independent counter over the shipped transport reads four whether the semaphore exists or
    not — section 11 says exactly this: *"With one request per worker the pool size is also the
    bound on concurrent execution, so `REQUEST_SLOTS` never blocks today."* A guard that cannot
    see the difference is not guarding the semaphore, it is guarding the pool twice. Leg 2 hands
    the server a DELIBERATELY OVERSIZED pool, so the semaphore is the only thing left that can
    hold execution at the bound — which is the invariant section 11 says the semaphore is kept
    for: *"on the day keep-alive returns, the pool bounds threads and the semaphore is the only
    thing still bounding execution."* Leg 2 is that day, staged.
    """
    import concurrent.futures
    import http.client

    checks.equal(
        capture_server.slots_in_use(),
        0,
        "no request holds a slot before one is made — the counter starts where it says it does",
    )

    # ------------------------------------------------------------------ shared instrumentation
    # AN INDEPENDENT COUNTER, NOT `slots_in_use()`. This one is incremented by the route itself
    # on entry and decremented on the way out, so it reports what actually got inside `_dispatch`
    # regardless of what mechanism was supposed to stop it. That is the whole repair: an
    # instrument that is part of the mechanism it measures reports zero when the mechanism is
    # deleted, and zero passes every assertion of the form `<= REQUEST_SLOTS`.
    original = capture_server.do_inventory

    def instrumented(gate: threading.Event, state: dict):
        """Patch `do_inventory` — the route the dispatcher calls AFTER taking a slot.

        PATCHED AT THE ROUTE AND NOT AT `do_GET`, AND THE FIRST DRAFT GOT THAT WRONG. The slot is
        acquired inside `_dispatch`, which `do_GET` calls — so a hold placed in `do_GET` parks the
        thread OUTSIDE the bound, every reading is 0, and the assertions pass while measuring
        nothing. `do_inventory` is invoked by the dispatcher after the slot is taken, so a hold here
        is a hold on a slot.
        """

        def slow_status(*args, **kwargs):
            with state["lock"]:
                state["depth"] += 1
                state["entered"] += 1
                state["peak"] = max(state["peak"], state["depth"])
                state["reported"].append(capture_server.slots_in_use())
            try:
                gate.wait(timeout=5.0)
                return original(*args, **kwargs)
            finally:
                with state["lock"]:
                    state["depth"] -= 1

        return slow_status

    def fresh_state() -> dict:
        return {
            "lock": threading.Lock(),
            "depth": 0,
            "peak": 0,
            "entered": 0,
            "reported": [],
            "outcomes": [],
        }

    def fire(port: int, count: int, state: dict) -> list:
        """`count` callers at `GET /inventory`, each recording the status it was answered with.

        THE OUTCOME IS RECORDED BECAUSE LEG 2 NEEDS THE EXCESS CALLERS TO SAY SOMETHING. A caller
        that is refused 503 has demonstrably reached the semaphore and been turned away; a caller
        that is merely absent from the occupancy count has demonstrated nothing, and telling those
        two apart is the difference between evidence and a wall-clock guess.
        """
        callers = []
        for _ in range(count):

            def one() -> None:
                outcome = "error"
                try:
                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
                    conn.request("GET", "/inventory")
                    response = conn.getresponse()
                    response.read()
                    outcome = int(response.status)
                    conn.close()
                except Exception:  # noqa: BLE001 — the outcome is the assertion, not the raise
                    pass
                with state["lock"]:
                    state["outcomes"].append(outcome)

            caller = threading.Thread(target=one, daemon=True, name="t7-caller")
            caller.start()
            callers.append(caller)
        return callers

    asking = capture_server.REQUEST_SLOTS + 6

    # ------------------------------------------------------- leg 1: the transport, as it ships
    checks.note("")
    checks.note("REQUEST SLOTS — leg 1: the shipped transport bounds THREADS")

    state = fresh_state()
    gate = threading.Event()
    httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
    port = httpd.server_address[1]
    thread = _spawn_server(httpd)
    capture_server.do_inventory = instrumented(gate, state)
    try:
        # EVERY THREAD ALIVE BEFORE THE LOAD, so the ones the SERVER makes can be told from the
        # ones this check makes. Naming the pool's workers and counting those was the first
        # attempt and it was VACUOUS: with the pool removed the server's threads are named
        # `Thread-N`, the filter matched none of them, and `0 <= REQUEST_SLOTS` passed while
        # measuring nothing at all.
        before = set(threading.enumerate())
        callers = fire(port, asking, state)

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and state["peak"] < capture_server.REQUEST_SLOTS:
            time.sleep(0.02)

        inflight = capture_server.inflight()
        # READ WHILE THE LOAD IS ON, beside the other two. Taken after `gate.set()` the callers
        # have finished and the server's threads have gone with them, so the count is 0 whatever
        # the transport does — which is how the first draft of this passed with the pool deleted.
        # THE ONE SORTER THREAD is excluded by name: it is ONE sorter thread shared by ALL
        # connections, a fixed cost of the photo lane and not a worker per connection. A filter on a name that MATCHES NOTHING is
        # the vacuous shape this leg was rebuilt to avoid, so only this one name is dropped.
        serving = [
            t for t in threading.enumerate()
            if t not in before and t.name not in ("t7-caller", "sorter")
        ]
        gate.set()
        for caller in callers:
            caller.join(timeout=10)

        checks.ok(
            inflight <= capture_server.REQUEST_SLOTS,
            f"the queue is NOT counted as in flight — {inflight} in flight against {asking} "
            f"callers, which is what keeps `drain()` from waiting out its grace on requests "
            f"that have not started",
        )
        # AND THE THREADS ARE BOUNDED TOO, which is the half the semaphore deliberately does not
        # do. `ThreadingMixIn` would have one per CONNECTION here — more callers, more threads,
        # without limit. The pool plus `Connection: close` makes a worker's life one REQUEST, so
        # the count cannot exceed the pool. Measured on the owner's store at 150 connections: 5
        # threads against 153 without it, at identical throughput.
        checks.ok(
            len(serving) <= capture_server.REQUEST_SLOTS,
            f"and the SERVER holds no more than REQUEST_SLOTS "
            f"({capture_server.REQUEST_SLOTS}) threads for {asking} callers — {len(serving)}, "
            f"where one per connection would be all of them",
        )
    finally:
        capture_server.do_inventory = original
        gate.set()
        httpd.shutdown()
        httpd.server_close()

    # ------------------------------------- leg 2: the semaphore, with the pool taken out of it
    checks.note("")
    checks.note(
        "REQUEST SLOTS — leg 2: the semaphore bounds EXECUTION, over a pool too wide to help"
    )

    state = fresh_state()
    gate = threading.Event()
    httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
    port = httpd.server_address[1]
    # THE POOL, WIDENED BEFORE THE FIRST CONNECTION. `process_request` builds one lazily only
    # when `_pool` is None, and `_pool` is a CLASS attribute — assigning here binds an INSTANCE
    # attribute, so nothing about this leaks into the server leg 1 built or the one the operator
    # runs. Three times the bound: enough that every caller below could execute at once if the
    # semaphore were not there, which is precisely the case this leg has to be able to see.
    wide = concurrent.futures.ThreadPoolExecutor(
        max_workers=asking, thread_name_prefix="t7-wide"
    )
    httpd._pool = wide  # noqa: SLF001 — the transport is the confound this leg removes
    thread = _spawn_server(httpd)
    capture_server.do_inventory = instrumented(gate, state)
    # THE WAIT FOR A SLOT, SHORTENED FOR THIS LEG, AND IT IS WHAT MAKES THE READING DETERMINISTIC
    # RATHER THAN TIMED. The first draft of this leg slept half a second after the bound was met
    # and then read the occupancy, on the reasoning that an unbounded build would have filled up
    # by then. That is a wall-clock bet on a machine running the rest of this suite, and it can
    # only ever fail SILENTLY — a loaded box where the excess callers are late reports a green
    # bound it never observed. With the timeout short, every excess caller RESOLVES: it is
    # refused 503 rather than parking for thirty seconds, so the condition below is a fact about
    # the callers instead of an interval, and `peak` is read once every one of them is accounted
    # for. `_dispatch` reads this attribute at call time, which is the seam; `files.exclusive`
    # binds it as a DEFAULT ARGUMENT at import and is untouched.
    real_timeout = files.LOCK_TIMEOUT_SECONDS
    files.LOCK_TIMEOUT_SECONDS = 0.3
    try:
        callers = fire(port, asking, state)

        # EVERY CALLER ACCOUNTED FOR, WHICH IS A CONDITION AND NOT A DURATION. In the shipped
        # tree exactly `REQUEST_SLOTS` get inside and hold, and the other six are refused — so
        # this resolves as soon as the last refusal lands. With the semaphore deleted all ten get
        # inside and it resolves on the tenth entry. Either way the count below is read after the
        # last caller has done whatever it was going to do; there is no window to be unlucky in.
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            # A CALLER IS ACCOUNTED FOR WHEN IT IS INSIDE `_dispatch` OR HAS BEEN ANSWERED, and
            # the two are disjoint while the gate is shut: a holder is inside and has answered
            # nobody, a refused caller is answered and is not inside.
            with state["lock"]:
                answered = len(state["outcomes"])
                inside = state["depth"]
            if answered + inside >= asking:
                break
            time.sleep(0.01)

        with state["lock"]:
            peak = state["peak"]
            entered = state["entered"]
            answered = len(state["outcomes"])
            inside = state["depth"]
            reported = list(state["reported"])
        inflight = capture_server.inflight()
        gate.set()
        for caller in callers:
            caller.join(timeout=30)
        with state["lock"]:
            refused = sum(1 for outcome in state["outcomes"] if outcome == 503)

        checks.equal(
            answered + inside,
            asking,
            f"every one of the {asking} callers is accounted for before anything is read — "
            f"{inside} inside `_dispatch` and {answered} already answered. THIS ASSERTION IS THE "
            f"GUARD ON THE ONES BELOW: read on a timer instead, a slow machine reports a bound "
            f"it never watched fill up, and the failure is a silent green",
        )
        checks.ok(
            peak <= capture_server.REQUEST_SLOTS,
            f"no more than REQUEST_SLOTS ({capture_server.REQUEST_SLOTS}) requests are inside "
            f"`_dispatch` at once, with {asking} asking and a pool of {asking} that would let "
            f"every one of them in — peak {peak}, counted by the route itself rather than by "
            f"the semaphore's own counter",
        )
        checks.equal(
            refused,
            asking - capture_server.REQUEST_SLOTS,
            f"and the excess SAID SO — {asking - capture_server.REQUEST_SLOTS} callers reached "
            f"the semaphore and were refused 503, which is evidence that the bound turned them "
            f"away rather than the absence of evidence that they arrived. Entered {entered}, "
            f"refused {refused}",
        )
        checks.ok(
            inflight <= capture_server.REQUEST_SLOTS,
            f"and the queue is still NOT in flight with the transport widened — {inflight} "
            f"against {asking} callers, so the slot is taken BEFORE `_inflight_enter` and the "
            f"drain sees only work that has started",
        )
        checks.ok(
            max(reported, default=0) <= capture_server.REQUEST_SLOTS,
            f"and no handler observed the semaphore's own count above the bound from inside "
            f"itself — {max(reported, default=0)}. Kept as a cross-check on the counter above "
            f"and NOT as the guard: this reading is the mechanism reporting on itself",
        )
    finally:
        files.LOCK_TIMEOUT_SECONDS = real_timeout
        capture_server.do_inventory = original
        gate.set()
        httpd.shutdown()
        httpd.server_close()
        wide.shutdown(wait=False)

    # --------------------------------------- leg 3: the caller that cannot get a slot is REFUSED
    checks.note("")
    checks.note("REQUEST SLOTS — leg 3: a caller that waits out the timeout is refused, not hung")

    # UNREACHABLE OVER THE SHIPPED TRANSPORT, AND THAT IS THE POINT OF SAYING SO. With the pool
    # sized at `REQUEST_SLOTS`, caller five never gets a worker, so it never reaches `_dispatch`
    # and never asks for a slot — it waits in the accept backlog instead. The refusal below is
    # therefore the same staged future leg 2 stages: the branch that answers on the day keep-alive
    # or a wider pool returns. A branch nothing can reach is a branch nothing has ever run.
    checks.ok(
        files.LOCK_TIMEOUT_SECONDS < serve.DRAIN_GRACE_SECONDS,
        f"the wait for a slot ({files.LOCK_TIMEOUT_SECONDS:.0f}s, "
        f"`store/files.py:LOCK_TIMEOUT_SECONDS`) sits inside the supervisor's drain "
        f"({serve.DRAIN_GRACE_SECONDS:.0f}s, `scripts/serve.py:DRAIN_GRACE_SECONDS`), so a "
        f"queued request always resolves one way or the other before the drain gives up and "
        f"kills a write in flight",
    )

    state = fresh_state()
    gate = threading.Event()
    httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
    port = httpd.server_address[1]
    wide = concurrent.futures.ThreadPoolExecutor(
        max_workers=asking, thread_name_prefix="t7-wide"
    )
    httpd._pool = wide  # noqa: SLF001 — as leg 2: the pool must not be what refuses
    thread = _spawn_server(httpd)
    capture_server.do_inventory = instrumented(gate, state)
    # THE TIMEOUT, SHORTENED FOR THE LENGTH OF THIS LEG ONLY. `_dispatch` reads
    # `files.LOCK_TIMEOUT_SECONDS` at call time, so the module attribute is the seam; nothing
    # else picks it up, because `files.exclusive` binds it as a DEFAULT ARGUMENT at import and
    # is therefore untouched by this. Thirty seconds is the shipped figure and is asserted
    # above; waiting it out here would put half a minute on the Stop hook to learn nothing more.
    real_timeout = files.LOCK_TIMEOUT_SECONDS
    files.LOCK_TIMEOUT_SECONDS = 0.3
    try:
        callers = fire(port, capture_server.REQUEST_SLOTS, state)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and state["peak"] < capture_server.REQUEST_SLOTS:
            time.sleep(0.02)

        started = time.monotonic()
        status, body, _ = request(port, "GET", "/inventory")
        waited = time.monotonic() - started

        gate.set()
        for caller in callers:
            caller.join(timeout=10)

        checks.equal(
            status,
            int(HTTPStatus.SERVICE_UNAVAILABLE),
            "with every slot held, the next caller is REFUSED 503 rather than parked forever — "
            "a hang is the failure shape this whole bound exists to avoid, and it is the one a "
            "suite reports as a timeout naming nothing",
        )
        checks.equal(
            error_code(body),
            "server_busy",
            "and it is `server_busy` and not `store_busy` — the two refusals name different "
            "processes, and this one is about THIS server rather than the lock",
        )
        checks.ok(
            str(capture_server.REQUEST_SLOTS) in error_message(body),
            f"and the message says how many it is already answering "
            f"({capture_server.REQUEST_SLOTS}), so the operator is not told to retry against a "
            f"figure nothing on screen names",
        )
        checks.ok(
            waited < 3.0,
            f"and it refused after the wait rather than after the drain — {waited:.2f}s against "
            f"a timeout patched to 0.3s for this leg",
        )
    finally:
        files.LOCK_TIMEOUT_SECONDS = real_timeout
        capture_server.do_inventory = original
        gate.set()
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
        wide.shutdown(wait=False)

    checks.equal(
        capture_server.slots_in_use(),
        0,
        "and every slot is given back — a leak here would wedge the server after N requests, "
        "which is worse than the unbounded server it replaces",
    )

def check_photo_lane(checks: Checks) -> None:
    """The photo lane holds its own bound, apart from the slot pool (owner's ruling, 2026-09-28).

    WHAT IT PROVES: with more photo callers than `PHOTO_SLOTS`, exactly `PHOTO_SLOTS` execute and
    the rest are refused `photo_busy`; `GET /status` still answers while the lane is full; and the
    slot pool's own count stays at zero. WHAT IT DOES NOT: that the lane fixes a real store's
    latency. That is DEBT11's measurement.

    THE PHOTO POOL IS WIDENED, as `check_request_slots` leg 2 widens the slot pool: the pool is a
    confound, so the semaphore has to be the only thing left that can hold the bound. Occupancy is
    counted by the route itself (a patched `do_photo`), never by `photo_slots_in_use()`, which is
    the mechanism reporting on itself.

    THREE MUTATIONS IT IS KEPT FOR. The photo gate removed (unbounded lane): peak equals every
    caller, and no refusal is owed. Photos sent back through the slot gate: `slots_in_use()` reads
    the bound and `/status` is refused. Photos sent back through the slot POOL by the sorter:
    the same `/status` starvation. READ ON A CONDITION, NOT A CLOCK: every caller is inside or
    answered before anything is read, as in leg 2.
    """
    import concurrent.futures
    import http.client

    asking = capture_server.PHOTO_SLOTS + 6
    original = capture_server.do_photo
    lock = threading.Lock()
    state = {"depth": 0, "peak": 0, "outcomes": [], "closes": []}
    gate = threading.Event()

    def held_photo(*args, **kwargs):
        with lock:
            state["depth"] += 1
            state["peak"] = max(state["peak"], state["depth"])
        try:
            gate.wait(timeout=5.0)
            return original(*args, **kwargs)
        finally:
            with lock:
                state["depth"] -= 1

    httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
    port = httpd.server_address[1]
    wide = concurrent.futures.ThreadPoolExecutor(max_workers=asking, thread_name_prefix="t7-wide")
    httpd._photo_pool = wide  # noqa: SLF001 — the pool is the confound this leg removes
    thread = _spawn_server(httpd)
    capture_server.do_photo = held_photo
    real_timeout = files.LOCK_TIMEOUT_SECONDS
    files.LOCK_TIMEOUT_SECONDS = 0.3
    checks.note("")
    checks.note("PHOTO LANE — its own bound, and the slot pool untouched")
    try:
        callers = []
        for _ in range(asking):

            def one() -> None:
                outcome, close, code = "error", None, None
                try:
                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
                    conn.request("GET", "/photo/1/1")
                    response = conn.getresponse()
                    raw = response.read()
                    code = error_code(raw) if response.status == 503 else None
                    outcome, close = int(response.status), response.getheader("Connection")
                    conn.close()
                except Exception:  # noqa: BLE001 — the outcome is the assertion
                    pass
                with lock:
                    state["outcomes"].append((outcome, code))
                    state["closes"].append(close)

            caller = threading.Thread(target=one, daemon=True, name="t7-caller")
            caller.start()
            callers.append(caller)

        # THE LANE IS FULL when `PHOTO_SLOTS` photos hold. `/status` is probed AT THAT MOMENT,
        # while the holders are still holding: probed later, a build that sent photos through the
        # slot pool would have drained its queue by then and answer `/status` at once.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            with lock:
                if state["depth"] >= capture_server.PHOTO_SLOTS:
                    break
            time.sleep(0.01)
        slots_held = capture_server.slots_in_use()
        started = time.monotonic()
        status, _, _ = request(port, "GET", "/inventory")
        status_wait = time.monotonic() - started
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            with lock:
                accounted = len(state["outcomes"]) + state["depth"]
            if accounted >= asking:
                break
            time.sleep(0.01)
        with lock:
            peak, inside, answered = state["peak"], state["depth"], len(state["outcomes"])
            refusals = [code for status, code in state["outcomes"] if status == 503]
        gate.set()
        for caller in callers:
            caller.join(timeout=30)

        checks.equal(
            answered + inside,
            asking,
            f"every one of the {asking} photo callers is accounted for before anything is read "
            f"({inside} inside, {answered} answered) — the guard on the readings below",
        )
        checks.ok(
            peak <= capture_server.PHOTO_SLOTS,
            f"no more than PHOTO_SLOTS ({capture_server.PHOTO_SLOTS}) photo requests execute at "
            f"once, with {asking} asking and a pool that would admit all of them — peak {peak}, "
            f"counted by the route itself",
        )
        checks.equal(
            refusals,
            ["photo_busy"] * (asking - capture_server.PHOTO_SLOTS),
            f"and the {asking - capture_server.PHOTO_SLOTS} excess were refused `photo_busy` — "
            f"the lane's own refusal, in `server_busy`'s shape, not `server_busy`",
        )
        checks.equal(
            status,
            int(HTTPStatus.OK),
            "`GET /inventory` (a slot-pool read; `/status` shares the lane now) answers 200 while "
            "the photo lane is full — a photo flood does not "
            "starve the app's other requests",
        )
        checks.ok(status_wait < 2.0, f"and it answered at once, not after a wait — {status_wait:.2f}s")
        checks.equal(
            slots_held,
            0,
            "and the slot pool's own count is untouched while the lane is full — photos hold no "
            "slot, so a writer parked on the store lock cannot starve them and they cannot starve it",
        )
        checks.ok(
            state["closes"] and all(c == "close" for c in state["closes"]),
            "and every photo response, refusals included, sends `Connection: close`",
        )
    finally:
        files.LOCK_TIMEOUT_SECONDS = real_timeout
        capture_server.do_photo = original
        gate.set()
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
        wide.shutdown(wait=False)

    checks.equal(
        capture_server.photo_slots_in_use(),
        0,
        "and every photo slot is given back",
    )

def check_lockfree_lane(checks: Checks) -> None:
    """Parked writers cannot starve the lock-free reads in the lane (DEBT11).

    WHAT IT PROVES: with the store lock held and `REQUEST_SLOTS` real writers parked on it, each
    route in `PHOTO_LANE_EXACT` still answers 200 within a bound, over the SHIPPED transport
    (nothing widened). WHAT IT DOES NOT: that the heavy lock-free reads answer. They are not in the
    lane and this check says nothing for them.

    THE WRITERS ARE REAL: `POST /boxes` takes the store lock and waits on it, holding a slot. The
    scratch store is opened first, because the first read of a fresh store upgrades it under the
    same lock. Released at the end so the writers finish and join, with no 30s wait.
    """
    import http.client

    checks.note("")
    checks.note("LOCK-FREE LANE — parked writers do not starve the routes in it")
    bound = 3.0
    origin = capture_server.DEFAULT_ALLOWED_ORIGINS[0]
    with isolated_home():
        Store().read()  # the schema upgrade takes the lock; do it before the lock is held
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
        port = httpd.server_address[1]
        thread = _spawn_server(httpd)
        writers = []
        results = {}

        def write(n: int) -> None:
            with contextlib.suppress(Exception):
                request(port, "POST", "/boxes", origin=origin, payload={"name": f"parked {n}"})

        def probe(path: str):
            started = time.monotonic()
            try:
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=bound)
                conn.request("GET", path, headers={"Connection": "close"})
                answer = conn.getresponse()
                answer.read()
                conn.close()
                return int(answer.status), time.monotonic() - started
            except Exception:  # noqa: BLE001 — a timeout is the finding
                return None, time.monotonic() - started

        try:
            with files.exclusive(files.inventory_dir()):
                for n in range(capture_server.REQUEST_SLOTS):
                    writer = threading.Thread(target=write, args=(n,), daemon=True)
                    writer.start()
                    writers.append(writer)
                # READ ON A CONDITION: every slot is held by a writer that is parked on the lock.
                deadline = time.monotonic() + 10.0
                while (
                    time.monotonic() < deadline
                    and capture_server.slots_in_use() < capture_server.REQUEST_SLOTS
                ):
                    time.sleep(0.01)
                held = capture_server.slots_in_use()
                # A FIXED LIST, not the constant: a route dropped from `PHOTO_LANE_EXACT` must go red
                # here rather than leave the probe.
                for path in ("/status", "/queues", "/capture/sitting", "/games"):
                    results[path] = probe(path)
                slot_route = probe("/inventory")
        finally:
            for writer in writers:
                writer.join(timeout=30)
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    checks.equal(
        held,
        capture_server.REQUEST_SLOTS,
        "every request slot is held by a writer parked on the store lock — the guard on the "
        "readings below",
    )
    for path, (status, took) in results.items():
        checks.ok(
            status == int(HTTPStatus.OK) and took < bound,
            f"`GET {path}` answers 200 within {bound:.0f}s with every slot parked on the store "
            f"lock — {status} in {took:.2f}s",
        )
    checks.ok(
        slot_route[0] is None,
        "and a slot-pool read (`/inventory`) is still parked behind them, so the lane is what "
        f"answered and not a lock that never blocked — {slot_route[0]} in {slot_route[1]:.2f}s",
    )
    checks.equal(capture_server.slots_in_use(), 0, "and every slot is given back once the lock frees")

def check_lane_survives_bad_target(checks: Checks) -> None:
    """`photo_lane_path` runs before `_dispatch`'s `try`, so a target `urlparse` rejects must not raise."""
    import http.client

    checks.note("")
    checks.note("LANE PREDICATE — a target that is not a URL")
    try:
        in_lane = capture_server.photo_lane_path("//[")
    except ValueError:
        in_lane = "raised ValueError"
    checks.equal(in_lane, False, "`//[` is not in the lane and does not raise")
    httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
    thread = _spawn_server(httpd)
    try:
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=5)
        conn.request("GET", "//[", headers={"Connection": "close"})
        status = conn.getresponse().status
        conn.close()
    except Exception as caught:  # noqa: BLE001 — a dropped socket is the finding
        status = repr(caught)
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
    checks.ok(isinstance(status, int), f"and the server answers `GET //[` instead of dropping the socket — {status}")

def check_slow_request_line(checks: Checks) -> None:
    """A request parked on the store lock past the threshold logs ONE line that names the lock wait.

    WHAT IT PROVES: the slow-request line (`CaptureHandler._note_slow`) exists, carries the route
    without a query string, splits the slot wait from the lock wait, and reports what the
    supervisor's busy file says. WHAT IT DOES NOT: that the supervisor writes that file. A fast
    request writes no line. The log seam is `files.log_note`, replaced for the length of the check.
    """
    checks.note("")
    checks.note("SLOW REQUEST LINE — a stall names its cause")
    lines: list = []
    answer: list = []
    real_note, real_limit = files.log_note, capture_server.SLOW_REQUEST_SECONDS
    real_busy = capture_server.SUPERVISOR_BUSY_FILE
    # ONLY THIS CHECK'S OWN HANDLER'S LINES COUNT. A late `_note_slow` from an earlier check's server
    # (it runs after the response) must not be read as this check's line.
    mine = threading.local()

    class Mine(QuietHandler):
        def _note_slow(self, *args, **kwargs) -> None:
            mine.on = True
            try:
                super()._note_slow(*args, **kwargs)
            finally:
                mine.on = False

    files.log_note = lambda text: lines.append(text) if getattr(mine, "on", False) else None
    capture_server.SLOW_REQUEST_SECONDS = 0.3
    origin = capture_server.DEFAULT_ALLOWED_ORIGINS[0]
    with isolated_home() as home:
        Store().read()
        capture_server.SUPERVISOR_BUSY_FILE = home / "busy"
        capture_server.SUPERVISOR_BUSY_FILE.write_text("app-build\n", "utf-8")
        httpd = capture_server.CaptureServer(("127.0.0.1", 0), Mine)
        thread = _spawn_server(httpd)
        port = httpd.server_address[1]
        try:
            request(port, "GET", "/inventory?q=secret-card")  # fast: no line
            with files.exclusive(files.inventory_dir()):
                writer = threading.Thread(
                    target=lambda: answer.append(
                        request(port, "POST", "/boxes", origin=origin, payload={"name": "slow"})[:2]
                    ),
                    daemon=True,
                )
                writer.start()
                time.sleep(0.8)  # parked on the lock; released on leaving the block
            writer.join(timeout=30)
            # `_note_slow` runs in `_dispatch`'s `finally`, AFTER the response is sent. Wait for
            # the line on a condition, once and bounded, before the seams are put back.
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline and not any(
                str(ln).startswith(capture_server.SLOW_LINE_PREFIX) and "POST /boxes " in str(ln)
                for ln in list(lines)
            ):
                time.sleep(0.01)
        finally:
            files.log_note = real_note
            capture_server.SLOW_REQUEST_SECONDS = real_limit
            capture_server.SUPERVISOR_BUSY_FILE = real_busy
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    slow = [
        ln for ln in lines
        if str(ln).startswith(capture_server.SLOW_LINE_PREFIX) and "POST /boxes " in ln
    ]
    checks.equal(
        len(slow), 1,
        f"exactly one slow-request line for the parked write (log saw {lines!r}, "
        f"write answered {answer!r})",
    )
    line = slow[0] if slow else ""
    waited = re.search(r"lock_wait=([\d.]+)s", line)
    checks.ok(
        "POST /boxes " in line and "secret-card" not in line,
        f"it names the route and no query string — {line!r}",
    )
    checks.ok(
        bool(waited) and float(waited.group(1)) >= 0.3,
        f"it names the lock wait, at least the 0.3s threshold — {waited.group(0) if waited else None}",
    )
    checks.ok("slot_wait=0" in line and "(slot pool)" in line, "and the slot wait apart from it, with its pool")
    checks.ok("supervisor_busy=app-build" in line, "and what the supervisor was doing")

def check_photo_lane_threads_and_faults(checks: Checks) -> None:
    """The photo pool bounds THREADS, and a sorter fault degrades the server to base.

    LEG A: with more photo callers than `PHOTO_SLOTS`, the server holds no more than
    `PHOTO_SLOTS` threads (the one sorter aside). Kept for a thread per photo connection, which
    `check_photo_lane` cannot see because it widens the pool on purpose. READ ON A CONDITION: the
    read waits until every caller is inside or answered, which a thread-per-connection build
    reaches at once and the shipped pool never does, so the shipped read falls to a short deadline.

    LEG B: a fault in the sorter must never become an outage. Once the selector's `select()`
    raises, and once a route to the photo pool raises for one connection, `/status` and a photo
    still answer afterwards. A sorter that dies on either leaves accept taking connections that
    nothing serves.
    """
    import http.client

    def get(port: int, path: str):
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", path)
            response = conn.getresponse()
            response.read()
            conn.close()
            return int(response.status)
        except Exception:  # noqa: BLE001 — a hang or reset is the finding
            return None

    # ------------------------------------------------------------------ leg A: threads
    checks.note("")
    checks.note("PHOTO LANE — leg A: the photo pool bounds threads")
    asking = capture_server.PHOTO_SLOTS + 6
    original = capture_server.do_photo
    lock = threading.Lock()
    state = {"depth": 0, "answered": 0}
    gate = threading.Event()

    def held_photo(*args, **kwargs):
        with lock:
            state["depth"] += 1
        try:
            gate.wait(timeout=5.0)
            return original(*args, **kwargs)
        finally:
            with lock:
                state["depth"] -= 1

    httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
    port = httpd.server_address[1]
    thread = _spawn_server(httpd)
    capture_server.do_photo = held_photo
    real_timeout = files.LOCK_TIMEOUT_SECONDS
    files.LOCK_TIMEOUT_SECONDS = 0.3
    try:
        before = set(threading.enumerate())

        def one() -> None:
            get(port, "/photo/1/1")
            with lock:
                state["answered"] += 1

        callers = [threading.Thread(target=one, daemon=True, name="t7-caller") for _ in range(asking)]
        for caller in callers:
            caller.start()
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            with lock:
                if state["depth"] >= capture_server.PHOTO_SLOTS:
                    break
            time.sleep(0.01)
        # THE PEAK, sampled through the wait: a refused caller's thread ends the moment it is
        # answered, so a single read at the end would miss it and pass a thread per connection.
        peak_serving = 0
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            peak_serving = max(peak_serving, len([
                t for t in threading.enumerate()
                if t not in before and t.name not in ("t7-caller", "sorter")
            ]))
            with lock:
                if state["depth"] + state["answered"] >= asking:
                    break
            time.sleep(0.005)
        serving = range(peak_serving)
        gate.set()
        for caller in callers:
            caller.join(timeout=30)
        checks.ok(
            len(serving) <= capture_server.PHOTO_SLOTS,
            f"the server holds no more than PHOTO_SLOTS ({capture_server.PHOTO_SLOTS}) threads "
            f"for {asking} photo callers — {len(serving)}, where one per connection would be more",
        )
    finally:
        files.LOCK_TIMEOUT_SECONDS = real_timeout
        capture_server.do_photo = original
        gate.set()
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)

    # ------------------------------------------------------------------ leg B: sorter faults
    checks.note("")
    checks.note("PHOTO LANE — leg B: a sorter fault degrades to base, never to an outage")
    import types

    real_selectors = capture_server.selectors

    class FaultySelector(real_selectors.DefaultSelector):
        def select(self, timeout=None):
            raise RuntimeError("t7: injected select() fault")

    httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
    port = httpd.server_address[1]
    thread = _spawn_server(httpd)
    capture_server.selectors = types.SimpleNamespace(
        DefaultSelector=FaultySelector, EVENT_READ=real_selectors.EVENT_READ
    )
    try:
        with redirect_stderr(io.StringIO()):
            status = [get(port, "/status") for _ in range(2)]
            photo = get(port, "/photo/1/1")
        checks.equal(status, [200, 200], "after `select()` raised, `/status` still answers")
        checks.ok(photo in (200, 404), f"and a photo still gets an answer, not a hang — {photo}")
    finally:
        capture_server.selectors = real_selectors
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)

    class OnceBrokenPool:
        """A photo pool whose first submit raises, as a per-connection routing fault would."""

        def __init__(self, real):
            self.real, self.broken = real, True

        def submit(self, *args, **kwargs):
            if self.broken:
                self.broken = False
                raise RuntimeError("t7: injected per-connection fault")
            return self.real.submit(*args, **kwargs)

        def shutdown(self, *args, **kwargs):
            return self.real.shutdown(*args, **kwargs)

    import concurrent.futures

    httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
    port = httpd.server_address[1]
    httpd._photo_pool = OnceBrokenPool(  # noqa: SLF001 — the fault under test
        concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="t7-photo")
    )
    thread = _spawn_server(httpd)
    try:
        with redirect_stderr(io.StringIO()):
            first = get(port, "/photo/1/1")
            later = [get(port, "/status"), get(port, "/photo/1/1")]
        checks.ok(first in (200, 404), f"the connection whose routing raised is still answered — {first}")
        checks.ok(
            later[0] == 200 and later[1] in (200, 404),
            f"and the sorter goes on: `/status` and a photo answer afterwards — {later}",
        )
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


CHECKS = (
    check_request_slots,
    check_photo_lane,
    check_lockfree_lane,
    check_lane_survives_bad_target,
    check_slow_request_line,
    check_photo_lane_threads_and_faults,
    check_connection_close,
)
