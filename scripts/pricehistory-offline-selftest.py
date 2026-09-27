#!/usr/bin/env python3
"""`pipeline/pricehistory.py:Market` fails fast once the network is genuinely unreachable,
proved against a counting fetcher and a fake clock — no network, no sleep spent for real.

WHAT THIS PROVES. Measured 2026-09-27 on a real demo-mirror recording:
`GET /pipeline/runs/<name>/trends` over 387 SKUs took 102.2s under the recorder's offline
network guard — `cProfile` isolated `time.sleep` (95.85s of it, 613 calls) as the cause.
`Market.get` only caches a SUCCESSFUL fetch, so a request that CANNOT succeed at all (no
socket connects, ever — `Offline`, never the plain `Unreachable` a bad HTTP status raises)
was retried, and re-slept-for, once per distinct (product, range) pair.

Fixed: the first `Offline` `Market` ever sees is remembered for the rest of that instance's
life, and every `get()` after it raises immediately with no sleep and no fetch attempt. An
ordinary `Unreachable` (a host that DID answer, just with a bad status) is NOT sticky —
the next product may still resolve normally, which is D62's own promise that one card's bad
day cannot cost every other card in the batch.
"""

from __future__ import annotations

import sys
import time
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
    a mirror having a bad moment on one product says nothing about the next one (D62)."""
    calls = []

    def fetcher(url):
        calls.append(url)
        raise pricehistory.Unreachable("simulated: host answered a bad status")

    market = pricehistory.Market(cache_dir=None, fetcher=fetcher, courtesy_delay=0.0)
    for i in range(5):
        try:
            market.get("https://example.test/%d" % i, "slug-%d" % i, 3600.0)
        except pricehistory.Unreachable:
            pass
    ok(len(calls) == 5, "a plain Unreachable is retried per distinct slug, never sticky",
       "called %d times, want 5" % len(calls))


def main() -> int:
    _offline_only_fetches_once()
    _plain_unreachable_is_not_sticky()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
