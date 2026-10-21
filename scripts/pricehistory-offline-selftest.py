#!/usr/bin/env python3
"""`pipeline/pricehistory.py` retries each network call through one home, and pauses a host only
after a run of failures. Proved against a scripted `urlopen` and one fake clock: no network, and
no sleep spent for real.

Protects: The price-history market stops asking a host that is down, and never gives up on a
product after one bad answer.
Governs: D278

WHAT THIS PROVES. Measured on a real demo-mirror recording: `GET /pipeline/runs/<name>/trends`
over 387 SKUs took 102.2s under the recorder's offline network guard — `cProfile` isolated
`time.sleep` (95.85s of it, 613 calls) as the cause. A request that CANNOT succeed (no socket
connects, `Offline`) was retried, and re-slept for, once per distinct (product, range) pair.

Fixed: a host that fails `PAUSE_AFTER_FAILURES` times in a row, each on a different URL, is refused
for `OFFLINE_WAIT_SECONDS`. Each refused call raises `Unreachable` with no request and no courtesy
delay. One failure, or a run of failures on one URL, pauses nothing. The pause is per host and
shared by every `Market` in the process: a dead host blinds no other host, and the one `Market`
the server holds for the whole process asks again after the wait
(`_paused_host_is_asked_again_after_the_wait`).

A READ TIMEOUT IS NOT A CONNECT FAILURE. `fetch_json` draws the line where its docstring says: a
connection that opened and then stalled reading the body is a plain, non-sticky `Unreachable`
(a live but slow link, and the next product may still answer). A `urlopen` that never returns a
response raises `Offline`. `_read_timeout_does_not_latch` proves it at that boundary.

RETRY (owner ruling: every network call retries, through ONE method). `fetch_json` makes up to 3
attempts on a connection that never opens, a connect timeout, HTTP 429, 502, 503 and 504, pausing
between them, for at most 3.0s of added wait in all (request threads share 4 slots). A `Retry-After`
header in seconds sets its pause. It never retries a plain 500, a 403 (`Blocked`), another 4xx, an
unreadable body, or a read failure after connect. The `_retry_*` cases script `urlopen` and patch
`pricehistory._sleep`, a module attribute that `fetch_json` must look up at CALL time (never bind
it as a default argument). `time.sleep` itself is refused for the length of each case, except
where a case records the courtesy delay on purpose.

BUDGET. One `fetch_json` call, attempts and pauses together, takes no longer than the one attempt
it replaced (`REQUEST_TIMEOUT_SECONDS`). A retry is made only when the time spent, plus the pause,
plus the attempt's timeout still fits, so a `Retry-After` that does not fit is not taken and the
call gives up. The `_net` cases replace that clock, `_sleep` and `urlopen` with one fake clock,
and hand the same clock to every `Market` as `now`. After `PAUSE_AFTER_FAILURES` failures in a
row, `fetch_json` refuses that host for `OFFLINE_WAIT_SECONDS` with no request: 60 gets on one
503 host cost three products of three attempts each, then nothing. A 404 is one product's answer
and never pauses the rest. The client re-asks for about 31 s (`SKU_PHOTO_BACKOFF_MS` in the app's
`server.ts`), so the wait stays inside that window.

The pause state is module-level and keyed by host (`urlsplit(url).netloc`). The runner clears it
before every case with `_clear_host_pauses`, so no case inherits another case's failures.
"""

from __future__ import annotations

import contextlib
import email.message
import io
import json
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import pricehistory  # noqa: E402

PASS = 0
FAIL = 0

# Every count below derives from the contract's threshold, so a changed constant moves the
# expectation. The contract case pins the value itself.
PAUSE_AFTER = getattr(pricehistory, "PAUSE_AFTER_FAILURES", 3)
# One lost call makes this many attempts, and pauses between them this many times.
ATTEMPTS_PER_CALL = len(pricehistory.RETRY_PAUSES) + 1
# Offsets on the fake clock. The wait length is the builder's: INSIDE_WAIT sits under any short
# wait, AFTER_WAIT over any sane one.
INSIDE_WAIT = 1.0
AFTER_WAIT = 600.0
RETRY_BUDGET_SECONDS = 3.0

URL = "https://example.test/x"
PAYLOAD = {"results": [{"productId": 1}]}
HOST_A = "history.example.test"
HOST_B = "tcgcsv.example.test"


def ok(condition: bool, label: str, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok     {label}")
    else:
        FAIL += 1
        print(f"  FAIL   {label}  {detail}")


def _fresh_hosts() -> None:
    """Clears the module-level pause state. Guarded, so this file still runs on code that has no
    such reset yet, and the cases then fail on their own counts rather than on a missing name."""
    clear = getattr(pricehistory, "_clear_host_pauses", None)
    if clear is not None:
        clear()


def _u(host: str, name: str) -> str:
    return "https://%s/%s" % (host, name)


def _host_of(url: str) -> str:
    return urllib.parse.urlsplit(url).netloc


def _name(url: str) -> str:
    return url.rsplit("/", 1)[1]


def _contract_names() -> None:
    ok(getattr(pricehistory, "PAUSE_AFTER_FAILURES", None) == 3,
       "contract: PAUSE_AFTER_FAILURES is 3, module-level",
       "is %r" % (getattr(pricehistory, "PAUSE_AFTER_FAILURES", None),))
    ok(callable(getattr(pricehistory, "_clear_host_pauses", None)),
       "contract: _clear_host_pauses() exists and resets the per-host state")


def _offline_only_fetches_once() -> None:
    """A host that never connects, through the REAL fetch_json. The first PAUSE_AFTER distinct URLs
    each lose their retries, then the host is paused: the other gets make no request. The courtesy
    delay is recorded rather than refused, so a paused get that still sleeps shows up as a count."""
    urls = [_u(HOST_A, "offline-%d" % i) for i in range(50)]
    courtesy = []
    with _net(_by_url(lambda url: "down")) as net, contextlib.redirect_stderr(io.StringIO()), \
            mock.patch.object(time, "sleep", courtesy.append):
        market = pricehistory.Market(cache_dir=None, courtesy_delay=0.05, now=lambda: net.clock[0])
        refusals = 0
        for i, url in enumerate(urls):
            try:
                market.get(url, "slug-%d" % i, 3600.0)
            except pricehistory.Unreachable:
                refusals += 1
    ok(refusals == 50, "every call still raises Unreachable", "got %d of 50" % refusals)
    ok(len(net.urls) == PAUSE_AFTER * ATTEMPTS_PER_CALL,
       "the gets after the pause make no request: %d attempts in all, not a burst per URL"
       % (PAUSE_AFTER * ATTEMPTS_PER_CALL),
       "made %d attempts" % len(net.urls))
    ok(len(courtesy) == PAUSE_AFTER - 1,
       "a paused get spends no courtesy delay: only the %d gets that reached the network sleep"
       % (PAUSE_AFTER - 1),
       "slept %d times" % len(courtesy))


def _offline_is_retried_after_the_wait() -> None:
    """The Offline form of case 9, through a Market and the real fetch_json. Three distinct URLs
    that never connect pause the host. A get inside the wait makes no request. After the wait,
    with the network up, a get asks the host again and answers."""
    up = [False]
    with _net(_by_url(lambda url: None if up[0] else "down")) as net, \
            contextlib.redirect_stderr(io.StringIO()):
        market = pricehistory.Market(cache_dir=None, courtesy_delay=0.0, now=lambda: net.clock[0])
        for i in range(PAUSE_AFTER):
            _outcome(lambda i=i: market.get(_u(HOST_A, "down-%d" % i), "slug-down-%d" % i, 3600.0))
        ok(len(net.urls) == PAUSE_AFTER * ATTEMPTS_PER_CALL,
           "three distinct URLs that never connect each lose their retries",
           "made %d attempts" % len(net.urls))
        net.clock[0] += INSIDE_WAIT
        before = len(net.urls)
        inside = _outcome(lambda: market.get(_u(HOST_A, "inside"), "slug-inside", 3600.0))
        ok(isinstance(inside, pricehistory.Unreachable) and len(net.urls) == before,
           "inside the wait a get raises Unreachable with no request",
           "made %d attempts, got %r" % (len(net.urls) - before, inside))
        up[0] = True
        net.clock[0] += AFTER_WAIT
        before = len(net.urls)
        answer = _outcome(lambda: market.get(_u(HOST_A, "after"), "slug-after", 3600.0))
    ok(answer == PAYLOAD, "after the wait a get asks the network again and answers",
       "got %r" % (answer,))
    ok(len(net.urls) - before == 1, "...with exactly one new request",
       "made %d" % (len(net.urls) - before))


def _plain_unreachable_is_not_sticky() -> None:
    """A real HTTP 500 from one host, through the REAL `fetch_json` and the default fetcher, is
    not sticky: five distinct products on that host are each asked for over the network, and
    each product URL is reached. The old version raised a bare `Unreachable` from a fake
    fetcher, which `Market` never latches, so it stayed green while a real 500 latched every
    later product."""
    urls = ["https://example.test/%d" % i for i in range(5)]
    with _net(_host(500)) as net, contextlib.redirect_stderr(io.StringIO()):
        market = pricehistory.Market(
            cache_dir=None, courtesy_delay=0.0, now=lambda: net.clock[0]
        )
        for i, url in enumerate(urls):
            with contextlib.suppress(pricehistory.Unreachable):
                market.get(url, "slug-%d" % i, 3600.0)
    reached = set(net.urls)
    ok(reached == set(urls), "a 500 from one host does not stop the next products: each of 5 is asked for",
       "asked for %d distinct URLs of 5 in %d requests: %r" % (len(reached), len(net.urls), sorted(reached)))


def _a_503_on_one_host_does_not_refuse_another() -> None:
    """A 503 that `fetch_json` retries and loses on host A never refuses a URL on host B: B is
    asked for over the network, and B's payload comes back."""
    host_a, host_b = "history.example.test", "tcgcsv.example.test"

    def answer(net, _timeout):
        net.clock[0] += 0.01
        url = net.urls[-1]
        if urllib.parse.urlsplit(url).hostname == host_a:
            raise urllib.error.HTTPError(url, 503, "simulated", {}, io.BytesIO(b""))
        return _Body(json.dumps(PAYLOAD).encode("utf-8"))

    with _net(answer) as net, contextlib.redirect_stderr(io.StringIO()):
        market = pricehistory.Market(cache_dir=None, courtesy_delay=0.0, now=lambda: net.clock[0])
        lost = _outcome(lambda: market.get("https://%s/x" % host_a, "slug-a", 3600.0))
        answered = _outcome(lambda: market.get("https://%s/x" % host_b, "slug-b", 3600.0))
    ok(isinstance(lost, pricehistory.Unreachable), "host A: a 503 lost after all retries raises Unreachable",
       "got %r" % (lost,))
    asked_b = [u for u in net.urls if urllib.parse.urlsplit(u).hostname == host_b]
    ok(bool(asked_b), "host B is asked for, though host A's 503 was lost",
       "asked for %r" % (net.urls,))
    ok(answered == PAYLOAD, "host B answers with its payload", "got %r" % (answered,))


class _FakeResponse:
    """A `urlopen` context manager whose `.read()` raises — a connection that opened, then
    stalled reading the body. `status`/`headers` are never touched by the failing paths
    this stands in for."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc_info) -> None:
        return None

    def read(self):
        raise self._exc


def _read_timeout_does_not_latch() -> None:
    """`fetch_json` itself, not `Market` — the boundary the finding was actually about."""
    real_urlopen = urllib.request.urlopen

    def urlopen_raises_on_read(*_a, **_k):
        return _FakeResponse(socket.timeout("simulated: read timed out"))

    urllib.request.urlopen = urlopen_raises_on_read
    try:
        try:
            pricehistory.fetch_json("https://example.test/read-timeout")
            ok(False, "a read timeout raises at all", "returned instead of raising")
        except pricehistory.Offline as exc:
            ok(False, "a read timeout is NOT Offline (it is a live, degraded link)",
               "raised Offline: %s" % exc)
        except pricehistory.Unreachable:
            ok(True, "a read timeout stays a plain, non-sticky Unreachable")
    finally:
        urllib.request.urlopen = real_urlopen

    def urlopen_never_connects(*_a, **_k):
        raise urllib.error.URLError("simulated: connection refused")

    urllib.request.urlopen = urlopen_never_connects
    try:
        with mock.patch.object(pricehistory, "_sleep", lambda seconds: None, create=True):
            try:
                pricehistory.fetch_json("https://example.test/never-connects")
                ok(False, "a connect failure raises at all", "returned instead of raising")
            except pricehistory.Offline:
                ok(True, "a connection that never opens still raises Offline")
            except pricehistory.Unreachable as exc:
                ok(False, "a connect failure raises Offline, not a plain Unreachable",
                   "raised plain Unreachable: %s" % exc)
    finally:
        urllib.request.urlopen = real_urlopen


class _Body:
    """A `urlopen` response that reads back `raw`."""

    def __init__(self, raw: bytes) -> None:
        self._raw = raw

    def __enter__(self) -> "_Body":
        return self

    def __exit__(self, *exc_info) -> None:
        return None

    def read(self) -> bytes:
        return self._raw


def _down():
    return urllib.error.URLError("simulated: connection refused")


def _timed_out():
    return socket.timeout("simulated: timed out before the socket opened")


def _http(code: int):
    return lambda: urllib.error.HTTPError("https://example.test/x", code, "simulated", {}, io.BytesIO(b""))


def _http_retry_after(code: int, seconds: str):
    """An HTTP error whose `Retry-After` header is `seconds`. A real response's headers are
    case-insensitive, so this is an `email.message.Message`, not a dict."""
    def make():
        headers = email.message.Message()
        headers["Retry-After"] = seconds
        return urllib.error.HTTPError(URL, code, "simulated", headers, io.BytesIO(b""))
    return make


def _ok(payload: dict):
    return lambda: _Body(json.dumps(payload).encode("utf-8"))


def _fetch(*steps):
    """The REAL `fetch_json` against a scripted `urlopen`: one step per attempt, each a
    zero-argument callable returning an exception to raise or a response to hand back. A
    script that runs out repeats its last step, so an extra attempt shows in the count
    rather than as an `IndexError`. Returns (payload or the exception raised, attempts made,
    the pauses requested)."""
    queue = list(steps)
    attempts = []
    pauses = []

    def urlopen(*_a, **_k):
        attempts.append(1)
        step = (queue.pop(0) if len(queue) > 1 else queue[0])()
        if isinstance(step, BaseException):
            raise step
        return step

    def real_sleep_refused(seconds):
        raise AssertionError("fetch_json slept for real (%r s); pause through pricehistory._sleep" % (seconds,))

    with mock.patch.object(urllib.request, "urlopen", urlopen), \
            mock.patch.object(pricehistory, "_sleep", pauses.append, create=True), \
            mock.patch.object(time, "sleep", real_sleep_refused):
        try:
            outcome = pricehistory.fetch_json("https://example.test/x")
        except Exception as exc:  # noqa: BLE001 - the exception IS what each case inspects
            outcome = exc
    return outcome, len(attempts), pauses


def _plain_unreachable(outcome) -> bool:
    return isinstance(outcome, pricehistory.Unreachable) and not isinstance(outcome, pricehistory.Offline)


def _retry_connection_failure() -> None:
    outcome, attempts, _ = _fetch(_down, _down, _ok({"price": 1}))
    ok(outcome == {"price": 1}, "retry: two connection failures, then an answer, returns the payload",
       "got %r" % (outcome,))
    ok(attempts == 3, "retry: ...on the third attempt", "made %d attempts" % attempts)

    outcome, attempts, _ = _fetch(_down)
    ok(isinstance(outcome, pricehistory.Offline), "retry: three straight connection failures still raise Offline",
       "got %r" % (outcome,))
    ok(attempts == 3, "retry: ...after exactly 3 attempts, no more", "made %d attempts" % attempts)

    outcome, attempts, _ = _fetch(_timed_out, _timed_out, _ok({"price": 2}))
    ok(outcome == {"price": 2} and attempts == 3, "retry: a timeout before the socket opens is retried too",
       "got %r after %d attempts" % (outcome, attempts))


def _retry_http_status() -> None:
    for code in (503, 429, 502, 504):
        outcome, attempts, _ = _fetch(_http(code), _ok({"price": 3}))
        ok(outcome == {"price": 3} and attempts == 2, "retry: HTTP %d then an answer returns the payload" % code,
           "got %r after %d attempts" % (outcome, attempts))


def _retry_never_for() -> None:
    outcome, attempts, _ = _fetch(_http(403))
    ok(isinstance(outcome, pricehistory.Blocked), "no retry: HTTP 403 raises Blocked", "got %r" % (outcome,))
    ok(attempts == 1, "no retry: ...after exactly 1 attempt", "made %d attempts" % attempts)

    for code in (400, 401, 404):
        outcome, attempts, _ = _fetch(_http(code))
        ok(_plain_unreachable(outcome) and attempts == 1, "no retry: HTTP %d is one attempt and a plain Unreachable" % code,
           "got %r after %d attempts" % (outcome, attempts))

    outcome, attempts, _ = _fetch(lambda: _Body(b"<html>not json"))
    ok(_plain_unreachable(outcome) and attempts == 1, "no retry: an unreadable body is one attempt and a plain Unreachable",
       "got %r after %d attempts" % (outcome, attempts))

    outcome, attempts, _ = _fetch(lambda: _FakeResponse(socket.timeout("simulated: read timed out")))
    ok(_plain_unreachable(outcome) and attempts == 1, "no retry: a read failure after connect is one attempt and a plain Unreachable",
       "got %r after %d attempts" % (outcome, attempts))


def _retry_wait_is_capped() -> None:
    _, _, pauses = _fetch(_down)
    ok(len(pauses) == 2 and all(p > 0 for p in pauses), "retry: two retries pause twice, each for a real, positive time",
       "pauses %r" % (pauses,))
    ok(sum(pauses) <= RETRY_BUDGET_SECONDS, "retry: ...and the added wait totals %.1fs or less" % RETRY_BUDGET_SECONDS,
       "pauses %r total %.2fs" % (pauses, sum(pauses)))


def _retry_after_sets_the_pause() -> None:
    outcome, attempts, pauses = _fetch(_http_retry_after(503, "1"), _ok(PAYLOAD))
    ok(outcome == PAYLOAD and attempts == 2 and pauses == [1],
       "retry-after: a 503 with Retry-After: 1 pauses 1s, then the retry answers",
       "got %r after %d attempts, paused %r" % (outcome, attempts, pauses))

    outcome, attempts, pauses = _fetch(_http_retry_after(503, "120"), _ok(PAYLOAD))
    ok(_plain_unreachable(outcome) and attempts == 1 and pauses == [],
       "retry-after: 120s does not fit the budget, so it is not slept and the call gives up after one attempt",
       "got %r after %d attempts, paused %r" % (outcome, attempts, pauses))


def _retry_time_is_bounded() -> None:
    budget = pricehistory.REQUEST_TIMEOUT_SECONDS
    with _net(_hangs) as net:
        outcome = _outcome(lambda: pricehistory.fetch_json(URL))
    ok(isinstance(outcome, pricehistory.Offline), "budget: attempts that all hang still end in Offline",
       "got %r" % (outcome,))
    ok(net.clock[0] <= budget, "budget: when every attempt runs to its timeout the call takes %.0fs or less" % budget,
       "took %.1fs: %d attempts with timeouts %r and pauses %r"
       % (net.clock[0], len(net.timeouts), net.timeouts, net.pauses))

    with _net(_took(30.0, lambda: socket.timeout("simulated: timed out"))) as net:
        _outcome(lambda: pricehistory.fetch_json(URL))
    ok(len(net.timeouts) == 1 and not net.pauses, "budget: a first attempt that took 30s is not retried",
       "made %d attempts, paused %r" % (len(net.timeouts), net.pauses))

    with _net(_took(0.01, lambda: urllib.error.URLError("simulated: refused"))) as net:
        outcome = _outcome(lambda: pricehistory.fetch_json(URL))
    ok(len(net.timeouts) == 3 and isinstance(outcome, pricehistory.Offline),
       "budget: failures that come back in 10 ms are still retried, 3 attempts in all",
       "made %d attempts, got %r" % (len(net.timeouts), outcome))


def _third_failure_pauses_the_host() -> None:
    """Two distinct URLs on host A lose their retries. A third is still asked and loses its own.
    A fourth, distinct, gets no request."""
    with _net(_by_url(lambda url: 503)) as net, contextlib.redirect_stderr(io.StringIO()):
        for name in ("p0", "p1"):
            _call(_u(HOST_A, name))
        ok(len(net.urls) == 2 * ATTEMPTS_PER_CALL, "two distinct URLs on host A each lose their 503 retries",
           "made %d attempts" % len(net.urls))
        before = len(net.urls)
        third = _call(_u(HOST_A, "p2"))
        ok(len(net.urls) - before == ATTEMPTS_PER_CALL and _plain_unreachable(third),
           "a third distinct URL on host A is still asked, and loses its retries",
           "made %d attempts, got %r" % (len(net.urls) - before, third))
        before = len(net.urls)
        fourth = _call(_u(HOST_A, "p3"))
    ok(len(net.urls) == before and isinstance(fourth, pricehistory.Unreachable),
       "the third failure pauses host A: a fourth distinct URL gets no request",
       "made %d attempts, got %r" % (len(net.urls) - before, fourth))


def _one_url_failing_is_not_a_run() -> None:
    """The same URL failing PAUSE_AFTER times is one failure, not a run: host A stays open."""
    same = _u(HOST_A, "same")
    with _net(_by_url(lambda url: 503)) as net, contextlib.redirect_stderr(io.StringIO()):
        for _ in range(PAUSE_AFTER):
            _call(same)
        ok(len(net.urls) == PAUSE_AFTER * ATTEMPTS_PER_CALL,
           "the same URL is asked %d times, each losing its retries" % PAUSE_AFTER,
           "made %d attempts" % len(net.urls))
        before = len(net.urls)
        other = _call(_u(HOST_A, "other"))
    ok(len(net.urls) - before == ATTEMPTS_PER_CALL and _plain_unreachable(other),
       "host A is not paused: a different URL is asked after that",
       "made %d attempts, got %r" % (len(net.urls) - before, other))


def _a_success_resets_the_count() -> None:
    """Fail, fail, succeed, then fail, fail, fail. The success clears the count, so the third
    failure after it is the sixth URL: that one is asked and loses, and the seventh gets no
    request. Without the reset the pause would come at the fourth URL."""
    plan = {"a1": 503, "a2": 503, "a3": None, "a4": 503, "a5": 503, "a6": 503, "a7": 503}
    names = ("a1", "a2", "a3", "a4", "a5", "a6", "a7")
    outcomes, cost = {}, {}
    with _net(_by_url(lambda url: plan[_name(url)])) as net, contextlib.redirect_stderr(io.StringIO()):
        for name in names:
            before = len(net.urls)
            outcomes[name] = _call(_u(HOST_A, name))
            cost[name] = len(net.urls) - before
    ok(outcomes["a3"] == PAYLOAD, "the success on host A answers", "got %r" % (outcomes["a3"],))
    ok(all(cost[n] == ATTEMPTS_PER_CALL for n in ("a1", "a2", "a4", "a5", "a6")),
       "a1, a2, a4, a5 and a6 are each asked: the success reset the count",
       "attempts per URL %r" % (cost,))
    ok(cost["a7"] == 0, "a7 gets no request: host A paused on the third failure after the success",
       "made %d attempts" % cost["a7"])


def _a_plain_error_neither_counts_nor_resets() -> None:
    """Two lost calls, a plain 500 or 404, then a lost call. The 500 or 404 must neither count
    nor reset: the third failure in a row is the 4th URL, so the 5th gets no request."""
    for mid in (500, 404):
        _fresh_hosts()
        plan = {"b1": 503, "b2": 503, "b3": mid, "b4": 503, "b5": 503}
        with _net(_by_url(lambda url: plan[_name(url)])) as net, contextlib.redirect_stderr(io.StringIO()):
            for name in ("b1", "b2", "b3"):
                _call(_u(HOST_A, name))
            before = len(net.urls)
            _call(_u(HOST_A, "b4"))
            asked_b4 = len(net.urls) - before
            before = len(net.urls)
            _call(_u(HOST_A, "b5"))
            asked_b5 = len(net.urls) - before
        ok(asked_b4 == ATTEMPTS_PER_CALL and asked_b5 == 0,
           "HTTP %d between two 503s neither counts nor resets: the 4th URL is the third failure, the 5th gets no request" % mid,
           "attempts for b4 %d, for b5 %d" % (asked_b4, asked_b5))


def _a_plain_500_is_one_request_and_never_counts() -> None:
    urls = [_u(HOST_A, "f%d" % i) for i in range(5)]
    with _net(_by_url(lambda url: 500)) as net, contextlib.redirect_stderr(io.StringIO()):
        outcomes = [_call(url) for url in urls]
    ok(all(_plain_unreachable(o) for o in outcomes), "a 500 is a plain Unreachable, never Offline",
       "got %r" % (outcomes,))
    ok(len(net.urls) == len(urls), "a 500 is one request per call: five calls make five requests, not three each",
       "made %d requests" % len(net.urls))
    ok(set(net.urls) == set(urls), "each of five distinct URLs on the 500 host is asked",
       "asked for %r" % (sorted(set(net.urls)),))


def _a_pause_is_shared_by_every_market() -> None:
    with _net(_by_url(lambda url: 503)) as net, contextlib.redirect_stderr(io.StringIO()):
        first = pricehistory.Market(cache_dir=None, courtesy_delay=0.0, now=lambda: net.clock[0])
        for i in range(PAUSE_AFTER):
            _outcome(lambda i=i: first.get(_u(HOST_A, "m%d" % i), "slug-m%d" % i, 3600.0))
        before = len(net.urls)
        paused = _call(_u(HOST_A, "m-paused"))
        ok(len(net.urls) == before and isinstance(paused, pricehistory.Unreachable),
           "host A is paused for the first Market: a fourth URL gets no request",
           "made %d attempts" % (len(net.urls) - before))
        second = pricehistory.Market(cache_dir=None, courtesy_delay=0.0, now=lambda: net.clock[0])
        before = len(net.urls)
        fresh = _outcome(lambda: second.get(_u(HOST_A, "m-fresh"), "slug-m-fresh", 3600.0))
    ok(len(net.urls) == before and isinstance(fresh, pricehistory.Unreachable),
       "a fresh Market shares the pause: its first get on host A makes no request",
       "made %d attempts" % (len(net.urls) - before))


def _a_paused_host_does_not_pause_another() -> None:
    with _net(_by_url(lambda url: 503 if _host_of(url) == HOST_A else None)) as net, \
            contextlib.redirect_stderr(io.StringIO()):
        for i in range(PAUSE_AFTER):
            _call(_u(HOST_A, "x%d" % i))
        before = len(net.urls)
        refused = _call(_u(HOST_A, "x-next"))
        ok(len(net.urls) == before and isinstance(refused, pricehistory.Unreachable),
           "host A is paused: its next URL gets no request",
           "made %d attempts, got %r" % (len(net.urls) - before, refused))
        before = len(net.urls)
        answered = _call(_u(HOST_B, "y1"))
    ok(_u(HOST_B, "y1") in net.urls[before:] and answered == PAYLOAD,
       "host B is still asked while host A is paused, and answers",
       "got %r, asked %r" % (answered, net.urls[before:]))


def _exhausted_retries_fail_fast_for_the_wait() -> None:
    """Sixty gets on one host that answers 503 or 429. The first PAUSE_AFTER distinct products
    each lose their retries, then host A is paused and the other gets make no request. The counts
    follow the constants: PAUSE_AFTER lost calls of ATTEMPTS_PER_CALL attempts, each call with
    len(RETRY_PAUSES) pauses. A 404 is one product's answer and never pauses the rest."""
    expected_attempts = PAUSE_AFTER * ATTEMPTS_PER_CALL
    expected_pauses = PAUSE_AFTER * len(pricehistory.RETRY_PAUSES)

    def burst(code) -> None:
        _fresh_hosts()
        with _net(_host(code)) as net, contextlib.redirect_stderr(io.StringIO()):
            market = pricehistory.Market(cache_dir=None, courtesy_delay=0.0, now=lambda: net.clock[0])

            def ask(slug):
                try:
                    return market.get("https://example.test/" + slug, slug, 3600.0)
                except pricehistory.Unreachable as exc:
                    return exc

            failures = [ask("slug-%d" % i) for i in range(60)]
            ok(all(isinstance(f, pricehistory.Unreachable) for f in failures),
               "HTTP %d: all 60 gets still raise Unreachable" % code)
            ok(len(net.timeouts) == expected_attempts and len(net.pauses) == expected_pauses,
               "HTTP %d: 60 gets cost %d attempts and %d pauses, then the host is paused"
               % (code, expected_attempts, expected_pauses),
               "made %d attempts and %d pauses (%.1fs)" % (len(net.timeouts), len(net.pauses), sum(net.pauses)))

            net.clock[0] += INSIDE_WAIT
            ask("slug-inside")
            ok(len(net.timeouts) == expected_attempts, "HTTP %d: a get inside the wait makes no request" % code,
               "made %d attempts" % len(net.timeouts))

            net.up = True
            net.clock[0] += AFTER_WAIT
            answer = ask("slug-after")
            ok(answer == PAYLOAD, "HTTP %d: after the wait a get asks the host again and answers" % code,
               "got %r" % (answer,))
            ok(len(net.timeouts) == expected_attempts + 1, "HTTP %d: ...with exactly one new request" % code,
               "made %d attempts" % len(net.timeouts))

    for code in (503, 429):
        burst(code)

    _fresh_hosts()
    with _net(_host(404)) as net:
        market = pricehistory.Market(cache_dir=None, courtesy_delay=0.0)
        for i in range(5):
            with contextlib.suppress(pricehistory.Unreachable):
                market.get("https://example.test/%d" % i, "slug-%d" % i, 3600.0)
    ok(len(net.timeouts) == 5 and not net.pauses,
       "HTTP 404: one product's answer, so each of 5 gets asks for itself, no retry and no pause",
       "made %d attempts, paused %r" % (len(net.timeouts), net.pauses))


def _paused_host_is_asked_again_after_the_wait() -> None:
    """Inside the wait host A gets no request, though it answers 503 to every ask. After the wait,
    with the host up, the next call is asked and answers."""
    up = [False]
    with _net(_by_url(lambda url: None if up[0] else 503)) as net, contextlib.redirect_stderr(io.StringIO()):
        for i in range(PAUSE_AFTER):
            _call(_u(HOST_A, "w%d" % i))
        net.clock[0] += INSIDE_WAIT
        before = len(net.urls)
        inside = _call(_u(HOST_A, "w-inside"))
        ok(len(net.urls) == before and isinstance(inside, pricehistory.Unreachable),
           "host A is paused inside the wait: no request", "made %d attempts" % (len(net.urls) - before))
        up[0] = True
        net.clock[0] += AFTER_WAIT
        before = len(net.urls)
        after = _call(_u(HOST_A, "w-after"))
    ok(after == PAYLOAD and len(net.urls) - before == 1,
       "after the wait host A is asked again and answers",
       "got %r after %d attempts" % (after, len(net.urls) - before))


def _stale_catalog_list_is_refetched_after_the_wait() -> None:
    """A groups list on disk older than a day lacks a set released since. The host fails, so
    `get` serves the stale list (one request, not one per card). Past the wait it must ask
    again, though `_attempted` already holds the slug: that latch bounds requests inside a
    wait, not for the rest of the instance's life."""
    slug, url = "tcgcsv/89/groups", "https://example.test/89/groups"
    old = {"results": [{"name": "Origins", "groupId": 1}]}
    new = {"results": [{"name": "Origins", "groupId": 1}, {"name": "Unleashed", "groupId": 2}]}

    def story(failure) -> None:
        label = failure.__name__
        clock = [1_000_000.0]
        calls = []
        host = {"payload": old, "failure": None}

        def fetcher(asked):
            calls.append(asked)
            if host["failure"] is not None:
                raise host["failure"]("simulated: the host is down")
            return host["payload"]

        with tempfile.TemporaryDirectory() as tmp:
            def market():
                return pricehistory.Market(cache_dir=tmp, fetcher=fetcher, courtesy_delay=0.0, now=lambda: clock[0])

            market().get(url, slug, pricehistory.GROUPS_TTL_SECONDS, catalog=True)
            clock[0] += pricehistory.GROUPS_TTL_SECONDS + 3600.0
            host.update(payload=new, failure=failure)
            fresh = market()
            served = fresh.get(url, slug, pricehistory.GROUPS_TTL_SECONDS, catalog=True)
            ok(served == old, "%s: a failed refresh serves the stale list" % label)
            seen = len(calls)

            clock[0] += INSIDE_WAIT
            served = fresh.get(url, slug, pricehistory.GROUPS_TTL_SECONDS, catalog=True)
            ok(served == old and len(calls) == seen, "%s: inside the wait no new request is made" % label,
               "made %d new requests" % (len(calls) - seen))

            host["failure"] = None
            clock[0] += AFTER_WAIT
            served = fresh.get(url, slug, pricehistory.GROUPS_TTL_SECONDS, catalog=True)
            ok(served == new, "%s: after the wait the list is fetched again and holds the new set" % label,
               "still served the stale list %.0fs after the failure" % AFTER_WAIT)
            ok(len(calls) == seen + 1, "%s: ...with exactly one new request" % label,
               "made %d new requests" % (len(calls) - seen))

    story(pricehistory.Unreachable)
    story(pricehistory.Offline)


def _offline_wait_fits_the_client_window() -> None:
    """The client re-asks for 1+2+4+8+8+8 = 31 s (`SKU_PHOTO_BACKOFF_MS`). A wait longer than
    half of that leaves the client no second ask that a retried fetch could answer."""
    ok(pricehistory.OFFLINE_WAIT_SECONDS <= 15.0,
       "OFFLINE_WAIT_SECONDS is 15s or less, inside the client's 31s of re-asks",
       "is %.0fs" % pricehistory.OFFLINE_WAIT_SECONDS)


# -------------------------------------------------------------------------- fake network


def _refuse_sleep(seconds):
    raise AssertionError("slept for real (%r s); pause through pricehistory._sleep" % (seconds,))


class _Net:
    """The REAL `fetch_json` over a scripted `urlopen`, on ONE fake clock (`clock[0]`, seconds).
    `answer(net, timeout)` runs once per attempt: it advances the clock by what the attempt
    took, then raises or returns a response. A pause (`pricehistory._sleep`) advances the same
    clock. `net.timeouts` holds the timeout each attempt was handed, `net.up` flips a
    `_host` from answering an error to answering `PAYLOAD`."""

    def __init__(self, answer) -> None:
        self.answer = answer
        self.timeouts = []
        self.urls = []
        self.pauses = []
        self.clock = [0.0]
        self.up = False

    def urlopen(self, _request, data=None, timeout=None):
        self.urls.append(_request.full_url)
        self.timeouts.append(timeout)
        return self.answer(self, timeout)

    def pause(self, seconds) -> None:
        self.pauses.append(seconds)
        self.clock[0] += seconds


@contextlib.contextmanager
def _net(answer):
    """`create=True` on the clock lets a case run against code that has no `_monotonic` yet:
    it then fails on its count, not on a missing name."""
    net = _Net(answer)
    with mock.patch.object(urllib.request, "urlopen", net.urlopen), \
            mock.patch.object(pricehistory, "_sleep", net.pause, create=True), \
            mock.patch.object(pricehistory, "_monotonic", lambda: net.clock[0], create=True), \
            mock.patch.object(time, "sleep", _refuse_sleep):
        yield net


def _took(seconds, make_exc):
    def answer(net, _timeout):
        net.clock[0] += seconds
        raise make_exc()
    return answer


def _hangs(net, timeout):
    """Every attempt runs to the timeout it was given, then the connect times out."""
    net.clock[0] += float("inf") if timeout is None else timeout
    raise socket.timeout("simulated: timed out before the socket opened")


def _host(code):
    """A host answering HTTP `code` until `net.up`, then `PAYLOAD`. Each answer takes 10 ms."""
    def answer(net, _timeout):
        net.clock[0] += 0.01
        if net.up:
            return _Body(json.dumps(PAYLOAD).encode("utf-8"))
        raise urllib.error.HTTPError(URL, code, "simulated", {}, io.BytesIO(b""))
    return answer


def _by_url(policy):
    """A `urlopen` for `_net` that answers each URL by `policy(url)`: "down" for a connection that
    never opens, an HTTP status code, or None for PAYLOAD. Each answer takes 10 ms."""
    def answer(net, _timeout):
        net.clock[0] += 0.01
        url = net.urls[-1]
        kind = policy(url)
        if kind == "down":
            raise urllib.error.URLError("simulated: connection refused")
        if kind is None:
            return _Body(json.dumps(PAYLOAD).encode("utf-8"))
        raise urllib.error.HTTPError(url, kind, "simulated", email.message.Message(), io.BytesIO(b""))
    return answer


def _outcome(call):
    try:
        return call()
    except Exception as exc:  # noqa: BLE001 - the exception IS what each case inspects
        return exc


def _call(url: str):
    """One real `fetch_json` call: the payload, or the exception it raised."""
    return _outcome(lambda: pricehistory.fetch_json(url))


# ------------------------------------------------------------------------------- runner


CASES = (
    _contract_names,
    _offline_only_fetches_once,
    _offline_is_retried_after_the_wait,
    _plain_unreachable_is_not_sticky,
    _a_503_on_one_host_does_not_refuse_another,
    _read_timeout_does_not_latch,
    _retry_connection_failure,
    _retry_http_status,
    _retry_never_for,
    _retry_wait_is_capped,
    _retry_after_sets_the_pause,
    _retry_time_is_bounded,
    _third_failure_pauses_the_host,
    _one_url_failing_is_not_a_run,
    _a_success_resets_the_count,
    _a_plain_error_neither_counts_nor_resets,
    _a_plain_500_is_one_request_and_never_counts,
    _a_pause_is_shared_by_every_market,
    _a_paused_host_does_not_pause_another,
    _exhausted_retries_fail_fast_for_the_wait,
    _paused_host_is_asked_again_after_the_wait,
    _stale_catalog_list_is_refetched_after_the_wait,
    _offline_wait_fits_the_client_window,
)


def main() -> int:
    for case in CASES:
        _fresh_hosts()
        print(f"\n{case.__name__.lstrip('_')}")
        try:
            case()
        except Exception as exc:  # noqa: BLE001 - a crash is one red line, and the run goes on
            ok(False, "%s runs to the end" % case.__name__, "raised %r" % (exc,))
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
