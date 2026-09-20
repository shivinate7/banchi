#!/usr/bin/env python3
"""`pipeline/pricehistory.py`'s cache lifetimes, proved against a fake clock and a counting
fetcher — no network, no disk cache directory (DEBT34).

THE RULING THIS PROVES. The owner: the set of cards in a catalogue set does not change from
pull to pull, so `CATALOG_TTL_SECONDS` (categories/groups/products) never expires.
`Market.prices` answers CURRENT prices, which move daily, and keeps its own separate,
finite `PRICE_TTL_SECONDS` — the one way to get this change wrong is letting `prices`
silently inherit the catalogue's new infinite lifetime, and this file's second arm is
built specifically to catch that.

TWO ARMS, AND THE SECOND ONE IS THE WHOLE RISK IN THIS CHANGE.

1. A catalogue entry (`groups`) fetched once and asked for again after 20 years of fake
   clock time is served from cache — the fetcher is called exactly once.
2. A price entry (`prices`) fetched once and asked for again after the SAME 20 years is
   NOT served from cache — the fetcher is called a second time. A mutation arm then makes
   `prices` share `CATALOG_TTL_SECONDS` (the bug this entry exists to prevent) and shows
   the same 20-year-later request wrongly reuses the stale cache — the real code's
   `PRICE_TTL_SECONDS` is proved to matter, not merely present.
"""

from __future__ import annotations

import sys
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


class Clock:
    def __init__(self, start: float = 1_000_000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance_years(self, years: float) -> None:
        self.now += years * 365 * 24 * 60 * 60


class CountingFetcher:
    """Answers a canned payload for any URL and counts how many times it was asked."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def __call__(self, url: str):
        self.calls += 1
        return dict(self.payload)


def test_catalog_never_expires():
    print("groups() — never expires, even 20 fake years later")
    clock = Clock()
    fetcher = CountingFetcher({"results": [{"groupId": 1, "name": "Vendetta"}]})
    market = pricehistory.Market(fetcher=fetcher, now=clock, courtesy_delay=0)

    market.groups(1)
    ok(fetcher.calls == 1, "first call fetches once", str(fetcher.calls))

    clock.advance_years(20)
    market.groups(1)
    ok(fetcher.calls == 1, "20 years later, still served from cache", str(fetcher.calls))


def test_prices_do_expire():
    print("prices() — has its own finite lifetime, unlike groups()")
    clock = Clock()
    fetcher = CountingFetcher({"results": []})
    market = pricehistory.Market(fetcher=fetcher, now=clock, courtesy_delay=0)

    market.prices(1, 1)
    ok(fetcher.calls == 1, "first call fetches once", str(fetcher.calls))

    clock.advance_years(20)
    market.prices(1, 1)
    ok(fetcher.calls == 2, "20 years later, prices is re-fetched, never served stale",
       str(fetcher.calls))


def test_mutation_prices_inheriting_catalog_ttl_is_wrong():
    print("mutation — prices sharing CATALOG_TTL_SECONDS silently makes it permanent")
    clock = Clock()
    fetcher = CountingFetcher({"results": []})
    market = pricehistory.Market(fetcher=fetcher, now=clock, courtesy_delay=0)

    # The bug this entry exists to prevent: `prices` calls `self.get(..., ttl=...)` with
    # `CATALOG_TTL_SECONDS` instead of its own `PRICE_TTL_SECONDS`. Reproduced here by
    # calling the cache primitive directly with the WRONG constant, rather than editing the
    # real method — this is the mutant, not the subject.
    market.get(
        f"{pricehistory.CATALOG_HOST}/tcgplayer/1/1/prices",
        "tcgcsv/1/1/prices",
        pricehistory.CATALOG_TTL_SECONDS,
    )
    ok(fetcher.calls == 1, "mutant's first call fetches once", str(fetcher.calls))

    clock.advance_years(20)
    market.get(
        f"{pricehistory.CATALOG_HOST}/tcgplayer/1/1/prices",
        "tcgcsv/1/1/prices",
        pricehistory.CATALOG_TTL_SECONDS,
    )
    mutant_calls = fetcher.calls

    # The real `prices()` method, over the SAME cache slug and clock, correctly re-fetches.
    real_fetcher = CountingFetcher({"results": []})
    real_market = pricehistory.Market(fetcher=real_fetcher, now=clock, courtesy_delay=0)
    real_market.prices(1, 1)
    clock.advance_years(20)
    real_market.prices(1, 1)

    ok(
        mutant_calls == 1 and real_fetcher.calls == 2,
        "the mutant wrongly serves a 20-year-old price from cache; the real prices() "
        "method does not",
        f"mutant_calls={mutant_calls} real_calls={real_fetcher.calls}",
    )


TESTS = [
    test_catalog_never_expires,
    test_prices_do_expire,
    test_mutation_prices_inheriting_catalog_ttl_is_wrong,
]


def main() -> int:
    for test in TESTS:
        test()
    print()
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
