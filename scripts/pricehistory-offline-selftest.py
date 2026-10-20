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

Fixed: the first `Offline` `Market` ever sees is remembered for the rest of that instance's
life, and every `get()` after it raises immediately with no sleep and no fetch attempt. An
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
"""

from __future__ import annotations

import contextlib
import io
import json
import socket
import sys
import time
import urllib.error
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


def _plain_unreachable_is_not_sticky() -> None:
    """A 500 or similar (Unreachable, not Offline) must NOT poison later, distinct calls —
    a mirror having a bad moment on one product says nothing about the next one (D278)."""
    calls = []

    def fetcher(url):
        calls.append(url)
        raise pricehistory.Unreachable("simulated: host answered a bad status")

    market = pricehistory.Market(cache_dir=None, fetcher=fetcher, courtesy_delay=0.0)
    for i in range(5):
        with contextlib.suppress(pricehistory.Unreachable):
            market.get("https://example.test/%d" % i, "slug-%d" % i, 3600.0)
    ok(len(calls) == 5, "a plain Unreachable is retried per distinct slug, never sticky",
       "called %d times, want 5" % len(calls))


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


def main() -> int:
    _offline_only_fetches_once()
    _plain_unreachable_is_not_sticky()
    _read_timeout_does_not_latch()
    _retry_connection_failure()
    _retry_http_status()
    _retry_never_for()
    _retry_wait_is_capped()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
