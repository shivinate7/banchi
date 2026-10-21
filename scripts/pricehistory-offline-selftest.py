#!/usr/bin/env python3
"""`pipeline/pricehistory.py:Market` fails fast once the network is genuinely unreachable,
proved against a counting fetcher and a fake clock — no network, no sleep spent for real.

Protects: The price-history market fails fast once the network is unreachable instead of sleeping through every retry.
Governs: D278

WHAT THIS PROVES. Measured 2026-09-27 on a real demo-mirror recording:
`GET /pipeline/runs/<name>/trends` over 387 SKUs took 102.2s under the recorder's offline
network guard — `cProfile` isolated `time.sleep` (95.85s of it, 613 calls) as the cause.
`Market.get` only caches a SUCCESSFUL fetch, so a request that CANNOT succeed at all (no
socket connects, ever — `Offline`, never the plain `Unreachable` a bad HTTP status raises)
was retried, and re-slept-for, once per distinct (product, range) pair.

Fixed: the first `Offline` `Market` sees is remembered for a short wait, and every `get()`
inside that wait raises immediately with no sleep and no fetch attempt. After the wait the
next `get()` asks the network again (`_offline_is_retried_after_the_wait`): the server's
`STOCK_IMAGES` holds ONE `Market` for the whole process, so a single DNS failure at start
(`Errno 8`) must not blind it until the next restart. An
ordinary `Unreachable` (a host that DID answer, just with a bad status) is NOT sticky —
the next product may still resolve normally, which is D278's own promise that one card's bad
day cannot cost every other card in the batch.

A READ TIMEOUT IS NOT A CONNECT FAILURE (the orchestrator's finding, 2026-09-27, on an
earlier version of this fix). `fetch_json`'s first cut caught `URLError`/`OSError`/
`TimeoutError` in ONE branch around the whole `urlopen(...)` call, so a slow but LIVE link
— a connection that opened, then stalled reading the body — also latched `Offline` and
refused every other SKU in the same request, dropping readings a retry would have gotten.
`_read_timeout_does_not_latch` proves `fetch_json` itself draws the line where the
docstring says it does: a fake response whose `.read()` raises stays a plain, non-sticky
`Unreachable`; a fake `urlopen` that never returns a response at all raises `Offline`.

RETRY (owner ruling: every network call retries, through ONE method). `fetch_json` makes up
to 3 attempts on a connection failure, a connect timeout, HTTP 429 and HTTP 5xx, pausing
between them, for at most 3.0s of added wait in all (request threads share 4 slots). It never
retries a 403 (`Blocked`), another 4xx, an unreadable body, or a read failure after connect.
The `_retry_*` cases script `urlopen` and patch `pricehistory._sleep`, a module attribute that
`fetch_json` must look up at CALL time (never bind it as a default argument). No case sleeps
for real: `time.sleep` itself is refused for the length of each case.

BUDGET. One `fetch_json` call, attempts and pauses together, takes no longer than the one
attempt it replaced (`REQUEST_TIMEOUT_SECONDS`). It reads the clock `pricehistory._monotonic`
and a retry is made only when the time spent, plus the pause, plus the attempt's timeout
still fits. The `_net` cases replace that clock, `_sleep` and `urlopen` with one fake clock.
After `fetch_json` gives up on HTTP 5xx or 429, `Market` fails fast for the same
`OFFLINE_WAIT_SECONDS` an `Offline` earns, so 60 gets cost one burst of 3 attempts. A 404 is
one product's answer and never fails the rest fast. The client re-asks for about 31 s
(`SKU_PHOTO_BACKOFF_MS` in the app's `server.ts`), so the wait stays inside that window.
"""

from __future__ import annotations

import contextlib
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


def ok(condition: bool, label: str, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok     {label}")
    else:
        FAIL += 1
        print(f"  FAIL   {label}  {detail}")


def _offline_only_fetches_once() -> None:
    calls = []

    def fetcher(url):
        calls.append(url)
        raise pricehistory.Offline("simulated: no socket ever connects")

    market = pricehistory.Market(cache_dir=None, fetcher=fetcher, courtesy_delay=0.05)
    start = time.time()
    refusals = 0
    for i in range(50):
        try:
            market.get("https://example.test/%d" % i, "slug-%d" % i, 3600.0)
        except pricehistory.Offline:
            refusals += 1
    elapsed = time.time() - start

    ok(refusals == 50, "every call still raises", "got %d of 50" % refusals)
    ok(len(calls) == 1, "the fetcher is called exactly ONCE, not once per slug",
       "called %d times" % len(calls))
    ok(elapsed < 0.5, "no courtesy delay is spent once offline is known",
       "took %.2fs for 50 calls at a 0.05s delay (would be ~2.45s unfixed)" % elapsed)


# Offsets on the injected clock. The wait length is the builder's, so these bracket it rather
# than name it: INSIDE_WAIT must sit under any short wait, AFTER_WAIT over it.
INSIDE_WAIT = 1.0
AFTER_WAIT = 600.0


def _offline_is_retried_after_the_wait() -> None:
    """A `Market` that went offline fails fast inside the wait and asks again after it.

    The inside-wait lines are green on the old code on purpose: they pin the behaviour the
    fix must keep (a batch never sleeps the courtesy delay once per URL). Only the after-wait
    lines are red there, because the old latch never lets go."""
    clock = [1_000_000.0]
    calls = []
    network_up = [False]
    payload = {"results": [{"productId": 1}]}

    def fetcher(url):
        calls.append(url)
        if not network_up[0]:
            raise pricehistory.Offline("simulated: Errno 8, no socket ever connects")
        return payload

    market = pricehistory.Market(
        cache_dir=None, fetcher=fetcher, courtesy_delay=0.05, now=lambda: clock[0]
    )
    try:
        market.get("https://example.test/first", "slug-first", 3600.0)
        ok(False, "the first fetch raises Offline", "returned instead of raising")
    except pricehistory.Offline:
        ok(True, "the first fetch raises Offline")

    clock[0] += INSIDE_WAIT
    start = time.time()
    refusals = 0
    for i in range(20):
        try:
            market.get("https://example.test/%d" % i, "slug-%d" % i, 3600.0)
        except pricehistory.Offline:
            refusals += 1
    elapsed = time.time() - start
    ok(refusals == 20, "inside the wait every get still raises Offline", "got %d of 20" % refusals)
    ok(len(calls) == 1, "inside the wait no new request is made",
       "called %d times, want 1" % len(calls))
    ok(elapsed < 0.5, "inside the wait no courtesy delay is spent per URL",
       "took %.2fs for 20 calls at a 0.05s delay (would be ~1.0s if it slept)" % elapsed)

    network_up[0] = True
    clock[0] += AFTER_WAIT
    answer, detail = None, ""
    try:
        answer = market.get("https://example.test/after", "slug-after", 3600.0)
    except pricehistory.Offline as exc:
        detail = "still raised Offline %.0fs after the failure: %s" % (AFTER_WAIT, exc)
    ok(answer == payload, "after the wait a get asks the network again and answers", detail)
    ok(len(calls) == 2, "after the wait exactly one new request is made",
       "called %d times, want 2" % len(calls))


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


RETRY_BUDGET_SECONDS = 3.0


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
    for code in (503, 429):
        outcome, attempts, _ = _fetch(_http(code), _ok({"price": 3}))
        ok(outcome == {"price": 3} and attempts == 2, "retry: HTTP %d then an answer returns the payload" % code,
           "got %r after %d attempts" % (outcome, attempts))

    outcome, attempts, _ = _fetch(_http(500))
    ok(_plain_unreachable(outcome), "retry: HTTP 500 three times raises a plain Unreachable, never Offline",
       "got %r" % (outcome,))
    ok(attempts == 3, "retry: ...after exactly 3 attempts", "made %d attempts" % attempts)


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


URL = "https://example.test/x"
PAYLOAD = {"results": [{"productId": 1}]}


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


def _outcome(call):
    try:
        return call()
    except Exception as exc:  # noqa: BLE001 - the exception IS what each case inspects
        return exc


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


def _exhausted_retries_fail_fast_for_the_wait() -> None:
    def burst(code) -> None:
        market_clock = [1_000_000.0]
        with _net(_host(code)) as net:
            market = pricehistory.Market(cache_dir=None, courtesy_delay=0.0, now=lambda: market_clock[0])

            def ask(slug):
                try:
                    return market.get("https://example.test/" + slug, slug, 3600.0)
                except pricehistory.Unreachable as exc:
                    return exc

            failures = [ask("slug-%d" % i) for i in range(60)]
            ok(all(isinstance(f, pricehistory.Unreachable) for f in failures),
               "HTTP %d: all 60 gets still raise Unreachable" % code)
            ok(len(net.timeouts) == 3 and len(net.pauses) == 2,
               "HTTP %d: 60 gets cost ONE burst, 3 attempts and 2 pauses, not that much per get" % code,
               "made %d attempts and %d pauses (%.1fs)" % (len(net.timeouts), len(net.pauses), sum(net.pauses)))

            market_clock[0] += INSIDE_WAIT
            ask("slug-inside")
            ok(len(net.timeouts) == 3, "HTTP %d: a get inside the wait makes no request" % code,
               "made %d attempts" % len(net.timeouts))

            net.up = True
            market_clock[0] += AFTER_WAIT
            answer = ask("slug-after")
            ok(answer == PAYLOAD, "HTTP %d: after the wait a get asks the host again and answers" % code,
               "got %r" % (answer,))
            ok(len(net.timeouts) == 4, "HTTP %d: ...with exactly one new request" % code,
               "made %d attempts" % len(net.timeouts))

    for code in (503, 429):
        burst(code)

    with _net(_host(404)) as net:
        market = pricehistory.Market(cache_dir=None, courtesy_delay=0.0)
        for i in range(5):
            with contextlib.suppress(pricehistory.Unreachable):
                market.get("https://example.test/%d" % i, "slug-%d" % i, 3600.0)
    ok(len(net.timeouts) == 5 and not net.pauses,
       "HTTP 404: one product's answer, so each of 5 gets asks for itself, no retry and no fail-fast",
       "made %d attempts, paused %r" % (len(net.timeouts), net.pauses))


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


def main() -> int:
    _offline_only_fetches_once()
    _offline_is_retried_after_the_wait()
    _plain_unreachable_is_not_sticky()
    _a_503_on_one_host_does_not_refuse_another()
    _read_timeout_does_not_latch()
    _retry_connection_failure()
    _retry_http_status()
    _retry_never_for()
    _retry_wait_is_capped()
    _retry_time_is_bounded()
    _exhausted_retries_fail_fast_for_the_wait()
    _stale_catalog_list_is_refetched_after_the_wait()
    _offline_wait_fits_the_client_window()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
