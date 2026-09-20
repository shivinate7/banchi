#!/usr/bin/env python3
"""`pipeline/sku_number_contradictions.py`, proved against literal fixtures — no store, no
network (`D-sku-number-contradictions`, kept apart from the four approved stored-data
checks, built as a separate, sibling PR, on the owner's own ruling).

NO REAL `Market`. `FakeIndex`/`FakeMarket` below duck-type the three calls
`pipeline.sku_number_contradictions.resolve` makes
(`category_id`, `group_id`, `products(...).by_number`), the same technique
`scripts/pricearchive-selftest.py`'s own `FakeMarket` already uses for
`pipeline/pricehistory.py:Market`.

FIVE ARMS. A denominator mismatch is shown to resolve WITHOUT ever calling the fake market
— a `RaisingMarket` that raises on any call proves it. A misread (one side real, one side
not) resolves to `MISREAD` naming the confirmed key. Both sides real resolves to
`SHARED_SKU`, never picking a winner. Neither side real resolves to `UNRESOLVED`. A
mutation arm feeds the real 3-copy `39/166`/`64/166` shape from the owner's own measured
store and shows the check finds it before any catalogue is asked.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.sku_number_contradictions import (  # noqa: E402
    NumberRecord,
    Outcome,
    find_disagreements,
    normalize_number,
    resolve,
)

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


class FakeIndex:
    def __init__(self, real_keys):
        self.by_number = {key: (1,) for key in real_keys}


class FakeMarket:
    """Answers with a fixed set of "real" normalized keys for any group it is asked
    about — enough to exercise `resolve`'s three catalogue-backed outcomes.
    """

    def __init__(self, real_keys):
        self._index = FakeIndex(real_keys)

    def category_id(self, product_line):
        return 1

    def group_id(self, category_id, set_name):
        return 1

    def products(self, category_id, group_id):
        return self._index


class RaisingMarket:
    """Any call is a test failure — proves a denominator mismatch never reaches the
    network at all.
    """

    def category_id(self, product_line):
        raise AssertionError("a denominator mismatch must never call the market")

    def group_id(self, category_id, set_name):
        raise AssertionError("a denominator mismatch must never call the market")

    def products(self, category_id, group_id):
        raise AssertionError("a denominator mismatch must never call the market")


def product_line_for_game(game):
    return "Riftbound League of Legends Trading Card Game"


def test_normalize():
    print("normalize_number folds a glued set code and zero-padding")
    ok(normalize_number("039/166") == normalize_number("SFO • 039/166"),
       "a glued set code folds to the same key as the bare number")
    ok(normalize_number("039/166") == "39/166", "leading zeros strip", normalize_number("039/166"))


def test_find_disagreements():
    print("find_disagreements groups by SKU and keeps only the ones that disagree")
    by_sku = {
        "9422414": [
            NumberRecord(key="a", number="39/166", set_name="Vendetta", game="riftbound"),
            NumberRecord(key="b", number="64/166", set_name="Vendetta", game="riftbound"),
        ],
        "agrees": [
            NumberRecord(key="c", number="005", set_name="ME01: Mega Evolution", game="pokemon"),
            NumberRecord(key="d", number="5", set_name="ME01: Mega Evolution", game="pokemon"),
        ],
    }
    found = find_disagreements(by_sku)
    ok(set(found.keys()) == {"9422414"}, "only the disagreeing SKU is reported", str(found.keys()))
    ok(found["9422414"].distinct_keys == ("39/166", "64/166"),
       "both normalized numbers are carried", str(found["9422414"].distinct_keys))


def test_denominator_mismatch_no_network():
    print("a denominator mismatch resolves without ever calling the market")
    by_sku = {
        "9422314": [
            NumberRecord(key="a", number="134/166", set_name="Vendetta", game="riftbound"),
            NumberRecord(key="b", number="134/266", set_name="Vendetta", game="riftbound"),
        ]
    }
    disagreement = find_disagreements(by_sku)["9422314"]
    ok(disagreement.denominator_mismatch, "the disagreement is flagged as a denominator mismatch")
    resolution = resolve(disagreement, RaisingMarket(), product_line_for_game)
    ok(resolution.outcome == Outcome.DENOMINATOR_MISMATCH, "outcome is DENOMINATOR_MISMATCH",
       str(resolution.outcome))


def test_misread():
    print("one real, one not -> MISREAD, naming the confirmed key")
    by_sku = {
        "9422414": [
            NumberRecord(key="a", number="39/166", set_name="Vendetta", game="riftbound"),
            NumberRecord(key="b", number="64/166", set_name="Vendetta", game="riftbound"),
        ]
    }
    disagreement = find_disagreements(by_sku)["9422414"]
    ok(not disagreement.denominator_mismatch, "same denominator, so this needs the catalogue")
    market = FakeMarket(real_keys={"39/166"})
    resolution = resolve(disagreement, market, product_line_for_game)
    ok(resolution.outcome == Outcome.MISREAD, "outcome is MISREAD", str(resolution.outcome))
    ok(resolution.confirmed_key == "39/166", "the real key is named as confirmed")
    ok(resolution.misread_keys == ("64/166",), "the fake key is named as the misread")


def test_shared_sku():
    print("both real, distinct -> SHARED_SKU, never a winner picked")
    by_sku = {
        "9422109": [
            NumberRecord(key="a", number="54/166", set_name="Vendetta", game="riftbound"),
            NumberRecord(key="b", number="84/166", set_name="Vendetta", game="riftbound"),
        ]
    }
    disagreement = find_disagreements(by_sku)["9422109"]
    market = FakeMarket(real_keys={"54/166", "84/166"})
    resolution = resolve(disagreement, market, product_line_for_game)
    ok(resolution.outcome == Outcome.SHARED_SKU, "outcome is SHARED_SKU", str(resolution.outcome))
    ok(resolution.confirmed_key is None, "no single key is named as the winner")
    ok(resolution.misread_keys == (), "nothing is named as a misread — both sides are real")


def test_unresolved():
    print("neither real -> UNRESOLVED, this check picks no winner")
    by_sku = {
        "9999999": [
            NumberRecord(key="a", number="1/166", set_name="Vendetta", game="riftbound"),
            NumberRecord(key="b", number="2/166", set_name="Vendetta", game="riftbound"),
        ]
    }
    disagreement = find_disagreements(by_sku)["9999999"]
    market = FakeMarket(real_keys=set())
    resolution = resolve(disagreement, market, product_line_for_game)
    ok(resolution.outcome == Outcome.UNRESOLVED, "outcome is UNRESOLVED", str(resolution.outcome))


def test_mutation_naive_first_side_wins():
    print("mutation — a naive 'first side wins' resolver is wrong on the SHARED_SKU case")

    def naive_resolve(disagreement, market, product_line_for_game):
        """The tempting wrong shape: whichever number was captured first wins, with no
        catalogue asked at all. Proves the real function's catalogue-backed three-way
        split is load-bearing rather than decorative.
        """
        return disagreement.distinct_keys[0]

    by_sku = {
        "9422109": [
            NumberRecord(key="a", number="54/166", set_name="Vendetta", game="riftbound"),
            NumberRecord(key="b", number="84/166", set_name="Vendetta", game="riftbound"),
        ]
    }
    disagreement = find_disagreements(by_sku)["9422109"]
    naive_winner = naive_resolve(disagreement, None, product_line_for_game)
    market = FakeMarket(real_keys={"54/166", "84/166"})
    real_resolution = resolve(disagreement, market, product_line_for_game)
    ok(
        naive_winner == "54/166" and real_resolution.outcome == Outcome.SHARED_SKU,
        "the naive resolver silently picks a winner; the real one reports both are real "
        "and picks none",
        f"naive={naive_winner} real={real_resolution.outcome}",
    )


TESTS = [
    test_normalize,
    test_find_disagreements,
    test_denominator_mismatch_no_network,
    test_misread,
    test_shared_sku,
    test_unresolved,
    test_mutation_naive_first_side_wins,
]


def main() -> int:
    for test in TESTS:
        test()
    print()
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
