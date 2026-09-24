#!/usr/bin/env python3
"""`pipeline/sku_number_contradictions.py`, proved against literal fixtures — no store, no
network (`D242`, kept apart from the four approved stored-data
checks, built as a separate, sibling PR, on the owner's own ruling).

NAME AGREEMENT, NOT MERE EXISTENCE. The owner's own measurement killed the first shape of
this check: in a dense set (Vendetta, 258 products over 100% of numbers 1-166), asking
"does a real product exist at this number" is vacuous — every candidate always resolves.
The fixtures below are built dense on purpose, so a regression back to the existence-only
test would pass every arm here silently unless the negative arms specifically catch it —
which `test_dense_set_existence_is_not_enough` does.

NO REAL `Market`. `FakeIndex`/`FakeMarket` below duck-type the three calls
`pipeline.sku_number_contradictions.resolve` makes
(`category_id`, `group_id`, `products(...).by_number`/`.by_name`), the same technique
`scripts/pricearchive-selftest.py`'s own `FakeMarket` already uses for
`pipeline/pricehistory.py:Market`.

EIGHT ARMS. Denominator mismatch never reaches the network. A name settling exactly one
candidate proposes it as `MISREAD`, naming the confirmed number. A name settling zero or
two-or-more candidates never proposes a single winner (`UNRESOLVED`/`SHARED_SKU`) — proved
BOTH as ordinary cases and as a mutation kill: a broken resolver that proposes MISREAD
whenever a number merely EXISTS (the original, vacuous test) is shown wrong on a dense-set
fixture where the real function correctly refuses. That second arm is the one protecting
`CLAUDE.md`'s own rule against guessing an identification.

PATH GATED, THE TWENTY-SECOND (D247, owner's word 2026-09-23, on the same ground as
`pricearchive-selftest`'s sixteenth entry): `make sku-number-contradictions-selftest`, wired
into `make check` and `make ci-check` through `scripts/guard-scope.py`. `docs/map.py` used to
state this file's exemption as "`pricearchive-selftest.py`'s own precedent, one entry above" —
that precedent is gone, and this module's real caller (`cli/cmd_sku_contradictions.py:run`,
`./pkmnscan cards contradictions`, D242) was tested nowhere else. Once it's done, it only
needs to be tested when touched.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.join import name_index_key  # noqa: E402
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
    """`by_number`/`by_name` shaped exactly like `pipeline/pricehistory.py:ProductIndex` —
    normalized key -> tuple of productIds. `products` is `{normalized_number: name}`, one
    entry per real product this fake group carries.
    """

    def __init__(self, products):
        by_number = {}
        by_name = {}
        for pid, (number_key, name) in enumerate(products.items(), start=1):
            by_number.setdefault(number_key, []).append(pid)
            by_name.setdefault(name_index_key(name), []).append(pid)
        self.by_number = {k: tuple(v) for k, v in by_number.items()}
        self.by_name = {k: tuple(v) for k, v in by_name.items()}


class FakeMarket:
    def __init__(self, products):
        self._index = FakeIndex(products)

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
            NumberRecord(key="a", number="39/166", name="Twilight Reveler", set_name="Vendetta", game="riftbound"),
            NumberRecord(key="b", number="64/166", name="Twilight Reveler", set_name="Vendetta", game="riftbound"),
        ],
        "agrees": [
            NumberRecord(key="c", number="005", name="Exeggutor", set_name="ME01: Mega Evolution", game="pokemon"),
            NumberRecord(key="d", number="5", name="Exeggutor", set_name="ME01: Mega Evolution", game="pokemon"),
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
            NumberRecord(key="a", number="134/166", name="X", set_name="Vendetta", game="riftbound"),
            NumberRecord(key="b", number="134/266", name="X", set_name="Vendetta", game="riftbound"),
        ]
    }
    disagreement = find_disagreements(by_sku)["9422314"]
    ok(disagreement.denominator_mismatch, "the disagreement is flagged as a denominator mismatch")
    resolution = resolve(disagreement, RaisingMarket(), product_line_for_game)
    ok(resolution.outcome == Outcome.DENOMINATOR_MISMATCH, "outcome is DENOMINATOR_MISMATCH",
       str(resolution.outcome))


def test_name_settles_it_misread():
    print("the name settles exactly one candidate -> MISREAD, naming it")
    # Two copies of one SKU: one reads 39/166 "Twilight Reveler", the other reads 64/166
    # "Twilight Reveler" — same name on both, only ONE number is real for that name.
    by_sku = {
        "9422414": [
            NumberRecord(key="a", number="39/166", name="Twilight Reveler", set_name="Vendetta", game="riftbound"),
            NumberRecord(key="b", number="64/166", name="Twilight Reveler", set_name="Vendetta", game="riftbound"),
        ]
    }
    disagreement = find_disagreements(by_sku)["9422414"]
    market = FakeMarket({
        "39/166": "Twilight Reveler",
        "64/166": "Grumpy Rockbear",
    })
    resolution = resolve(disagreement, market, product_line_for_game)
    ok(resolution.outcome == Outcome.MISREAD, "outcome is MISREAD", str(resolution.outcome))
    ok(resolution.confirmed_key == "39/166", "the name-confirmed key is named")
    ok(resolution.misread_keys == ("64/166",), "the other number is named as the misread")


def test_dense_set_existence_is_not_enough():
    print("dense set — every number exists, so ONLY the name can settle it")
    # Both candidate numbers are REAL products (a dense set, like the owner's own Vendetta
    # measurement: 258 products over 100% of 1-166). Existence alone would say "both real",
    # which is exactly the vacuous first-shape bug this rewrite corrects.
    by_sku = {
        "9422109": [
            NumberRecord(key="a", number="54/166", name="Ambessa, the Wolf", set_name="Vendetta", game="riftbound"),
            NumberRecord(key="b", number="84/166", name="Ambessa, the Wolf", set_name="Vendetta", game="riftbound"),
        ]
    }
    disagreement = find_disagreements(by_sku)["9422109"]
    dense_market = FakeMarket({
        "54/166": "Questionable Tome",
        "84/166": "Ambessa, the Wolf",
        # a dense set: every OTHER number in the group is a real, unrelated product too.
        **{f"{n}/166": f"Filler Card {n}" for n in range(1, 166) if n not in (54, 84)},
    })
    resolution = resolve(disagreement, dense_market, product_line_for_game)
    ok(resolution.outcome == Outcome.MISREAD, "the dense set still resolves by NAME", str(resolution.outcome))
    ok(resolution.confirmed_key == "84/166", "the name-confirmed number is the real Ambessa card")
    ok(resolution.misread_keys == ("54/166",), "the OTHER real-but-wrongly-named number is the misread")


def test_dense_set_mutation_existence_only():
    print("mutation — an existence-only resolver is wrong on a dense set; the real one is not")

    def mutant_resolve_existence_only(disagreement, market, product_line_for_game):
        """The original, vacuous test this module shipped with before the owner's
        correction: does a product exist at this number at all. Proves that test alone
        would misreport `shared_sku` for what is really a plain, name-settleable misread.
        """
        category_id = market.category_id(product_line_for_game(disagreement.game))
        group_id = market.group_id(category_id, disagreement.set_name)
        index = market.products(category_id, group_id)
        real = [k for k in disagreement.distinct_keys if k in index.by_number]
        if len(real) == 1:
            return "misread", real[0]
        if len(real) >= 2:
            return "shared_sku", None
        return "unresolved", None

    by_sku = {
        "9422109": [
            NumberRecord(key="a", number="54/166", name="Ambessa, the Wolf", set_name="Vendetta", game="riftbound"),
            NumberRecord(key="b", number="84/166", name="Ambessa, the Wolf", set_name="Vendetta", game="riftbound"),
        ]
    }
    disagreement = find_disagreements(by_sku)["9422109"]
    dense_market = FakeMarket({
        "54/166": "Questionable Tome",
        "84/166": "Ambessa, the Wolf",
    })
    mutant_outcome, mutant_key = mutant_resolve_existence_only(
        disagreement, dense_market, product_line_for_game
    )
    real_resolution = resolve(disagreement, dense_market, product_line_for_game)
    ok(
        mutant_outcome == "shared_sku" and real_resolution.outcome == Outcome.MISREAD
        and real_resolution.confirmed_key == "84/166",
        "the mutant reports shared_sku (both numbers exist); the real check finds the "
        "single name-confirmed misread",
        f"mutant={mutant_outcome} real={real_resolution.outcome}",
    )


def test_name_settles_nothing_unresolved():
    print("the name settles NEITHER candidate -> UNRESOLVED, no winner picked")
    by_sku = {
        "9999999": [
            NumberRecord(key="a", number="1/166", name="Mystery Card", set_name="Vendetta", game="riftbound"),
            NumberRecord(key="b", number="2/166", name="Mystery Card", set_name="Vendetta", game="riftbound"),
        ]
    }
    disagreement = find_disagreements(by_sku)["9999999"]
    market = FakeMarket({"1/166": "Something Else", "2/166": "Something Different"})
    resolution = resolve(disagreement, market, product_line_for_game)
    ok(resolution.outcome == Outcome.UNRESOLVED, "outcome is UNRESOLVED", str(resolution.outcome))
    ok(resolution.confirmed_key is None, "no key is confirmed")


def test_name_settles_both_shared_sku():
    print("the name settles BOTH candidates -> SHARED_SKU, never a winner picked")
    # Two DIFFERENT physical copies of one SKU, each carrying its OWN correct name and
    # number — the genuine "two products share one SKU" shape the owner's Riftbound
    # over-number concern names.
    by_sku = {
        "9422559": [
            NumberRecord(key="a", number="20/166", name="Card Alpha", set_name="Vendetta", game="riftbound"),
            NumberRecord(key="b", number="30/166", name="Card Beta", set_name="Vendetta", game="riftbound"),
        ]
    }
    disagreement = find_disagreements(by_sku)["9422559"]
    market = FakeMarket({"20/166": "Card Alpha", "30/166": "Card Beta"})
    resolution = resolve(disagreement, market, product_line_for_game)
    ok(resolution.outcome == Outcome.SHARED_SKU, "outcome is SHARED_SKU", str(resolution.outcome))
    ok(resolution.confirmed_key is None, "no single key is named as the winner")


TESTS = [
    test_normalize,
    test_find_disagreements,
    test_denominator_mismatch_no_network,
    test_name_settles_it_misread,
    test_dense_set_existence_is_not_enough,
    test_dense_set_mutation_existence_only,
    test_name_settles_nothing_unresolved,
    test_name_settles_both_shared_sku,
]


def main() -> int:
    for test in TESTS:
        test()
    print()
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
