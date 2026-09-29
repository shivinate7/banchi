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
"""

from __future__ import annotations

import contextlib
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

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


def main() -> int:
    _offline_only_fetches_once()
    _plain_unreachable_is_not_sticky()
    _read_timeout_does_not_latch()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
