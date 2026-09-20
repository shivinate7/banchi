#!/usr/bin/env python3
"""`pipeline/identity_checks.py`, proved against literal fixtures — no store, no network
(D-a-archive-store-checks).

EACH CHECK IS PROVED THE WAY `CLAUDE.md` DEMANDS: shown to catch its own named defect, and
shown NOT to fire on the clean data beside it. A guard that has never gone red on the thing
it guards is not trusted here. Four positive arms (one per check, each built from the exact
subject the cited decision entry measured — `102/166` in a 298-card `Origins`, `0934` in a
132-card `ME01: Mega Evolution`, `Shadbow Temple` beside `Shadow Temple`, the 152-character
rules-text name) and four negative arms (the same shape, with the defect removed, proving
the check goes quiet). A ninth arm mutates `flag_denominator_outliers` to compare against
the FIRST denominator seen rather than the DOMINANT one, and shows the mutant flags the
common case instead of the rare one — the argument for "dominant, not first" is not free
without this.

Not wired into `make check`, matching `scripts/pricearchive-selftest.py`'s own precedent: a
fast, self-contained proof of a package whose one caller (`cli/cmd_cards.py:checks`) is
already covered by T7's harness sweep over the CLI surface.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.identity_checks import (  # noqa: E402
    CardRecord,
    flag_denominator_outliers,
    flag_digit_count_outliers,
    flag_long_names,
    flag_near_duplicate_names,
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


def keys(flags) -> set:
    return {f.key for f in flags}


# ------------------------------------------------------------- class 1: long name


def test_long_name():
    print("class 1 — a name too long to be a card name")
    rules_text = (
        "While you control this battlefield, when you play a spell, if you spent 4 or "
        "more, PREDICT: (Look at the top card of your Main Deck. You may replace it.)"
    )
    cards = [
        CardRecord(key="box3/1", name=rules_text, set_name="Unleashed"),
        CardRecord(key="box3/2", name="Illaoi, Prophet of the Great Kraken", set_name="Unleashed"),
    ]
    flags = flag_long_names(cards)
    ok(keys(flags) == {"box3/1"}, "flags the rules-text name and only it", str(keys(flags)))

    clean = [CardRecord(key="box3/2", name="Illaoi, Prophet of the Great Kraken", set_name="Unleashed")]
    ok(flag_long_names(clean) == [], "quiet on a real, merely-long name")


# ------------------------------------------------------- class 2: denominator outlier


def test_denominator_outlier():
    print("class 2 — a denominator that disagrees with its set")
    # Origins: 298 is dominant (measured 291 of the real store; a handful here stands in),
    # one card reads 166.
    cards = (
        [CardRecord(key=f"origins/{i}", number=f"{i:03d}/298", set_name="Origins") for i in range(1, 6)]
        + [CardRecord(key="origins/bad", number="102/166", set_name="Origins")]
    )
    flags = flag_denominator_outliers(cards)
    ok(keys(flags) == {"origins/bad"}, "flags only the disagreeing denominator", str(keys(flags)))

    clean = [CardRecord(key=f"origins/{i}", number=f"{i:03d}/298", set_name="Origins") for i in range(1, 6)]
    ok(flag_denominator_outliers(clean) == [], "quiet when every denominator agrees")

    # A genuinely rare-but-real print carrying a different denominator (a special edition,
    # a promo reprint) is flagged exactly the same as a misread — this check cannot and does
    # not try to tell the two apart from stored data alone (D234's own boundary: one
    # disagreeing signal never resolves a claim on its own). It is a signal, never a verdict.
    rare_reprint = clean + [CardRecord(key="origins/reprint", number="1/300", set_name="Origins")]
    ok(
        "origins/reprint" in keys(flag_denominator_outliers(rare_reprint)),
        "a rare-but-real different denominator is flagged too — a signal, not a verdict",
    )


def test_denominator_outlier_mutation():
    print("class 2 mutation — dominant, not first-seen")

    def mutant_flag_denominator_outliers(cards):
        """The wrong fix: compare every denominator against the FIRST one this loop saw,
        instead of the one the majority of the set actually carries. Proves the real
        function's choice of `max(..., key=count)` is load-bearing rather than incidental.
        """
        from store.numbers import strip_set_code
        from pipeline.identity_checks import Flag, _CLEAN_NUMBER, _numbers_by_set

        out = []
        for _set_name, in_set in _numbers_by_set(cards).items():
            first_denom = None
            for card in in_set:
                match = _CLEAN_NUMBER.match(strip_set_code(card.number))
                if not match or not match.group(2):
                    continue
                if first_denom is None:
                    first_denom = match.group(2)
                elif match.group(2) != first_denom:
                    out.append(Flag(card.key, "denominator_outlier", "mutant"))
        return out

    # The one disagreeing card happens to be captured FIRST — the mutant then blames the
    # 298 majority instead of the 166 minority.
    cards = [CardRecord(key="origins/bad", number="102/166", set_name="Origins")] + [
        CardRecord(key=f"origins/{i}", number=f"{i:03d}/298", set_name="Origins") for i in range(1, 6)
    ]
    mutant_flags = mutant_flag_denominator_outliers(cards)
    real_flags = flag_denominator_outliers(cards)
    ok(
        keys(mutant_flags) != {"origins/bad"} and keys(real_flags) == {"origins/bad"},
        "the mutant blames the majority; the real check still finds the minority",
        f"mutant={keys(mutant_flags)} real={keys(real_flags)}",
    )


# ------------------------------------------------------ class 3: digit count outlier


def test_digit_count_outlier():
    print("class 3 — more digits than the set has cards")
    cards = (
        [CardRecord(key=f"me01/{i}", number=f"{i:03d}", set_name="ME01: Mega Evolution") for i in range(1, 6)]
        + [CardRecord(key="me01/bad", number="0934", set_name="ME01: Mega Evolution")]
    )
    flags = flag_digit_count_outliers(cards)
    ok(keys(flags) == {"me01/bad"}, "flags only the 4-digit read in a 3-digit set", str(keys(flags)))

    clean = [CardRecord(key=f"me01/{i}", number=f"{i:03d}", set_name="ME01: Mega Evolution") for i in range(1, 6)]
    ok(flag_digit_count_outliers(clean) == [], "quiet when every digit count agrees")

    # Fewer digits than the dominant count is a different defect and is never flagged here.
    short = clean + [CardRecord(key="me01/short", number="5", set_name="ME01: Mega Evolution")]
    ok(
        "me01/short" not in keys(flag_digit_count_outliers(short)),
        "a SHORTER read is not this check's subject",
    )


# ---------------------------------------------------- class 4: near-duplicate name


def test_near_duplicate_name():
    print("class 4 — a name one edit from a sibling in the same set")
    cards = [
        CardRecord(key="vendetta/1", name="Shadow Temple", set_name="Vendetta"),
        CardRecord(key="vendetta/2", name="Shadbow Temple", set_name="Vendetta"),
        CardRecord(key="vendetta/3", name="Unrelated Card", set_name="Vendetta"),
    ]
    flags = flag_near_duplicate_names(cards)
    # Symmetric: both spellings are "one edit from a different name this store holds."
    ok(
        keys(flags) == {"vendetta/1", "vendetta/2"},
        "flags both sides of the glued misread, and only those",
        str(keys(flags)),
    )

    clean = [
        CardRecord(key="vendetta/1", name="Shadow Temple", set_name="Vendetta"),
        CardRecord(key="vendetta/3", name="Unrelated Card", set_name="Vendetta"),
    ]
    ok(flag_near_duplicate_names(clean) == [], "quiet with no sibling to be close to")

    # A different set's identical near-miss must never cross the boundary.
    cross_set = clean + [CardRecord(key="origins/x", name="Shadbow Temple", set_name="Origins")]
    ok(
        flag_near_duplicate_names(cross_set) == [],
        "a same-name near-miss in a DIFFERENT set is never flagged",
    )


def test_near_duplicate_name_measured_case():
    print("class 4 — the doc's own resolved-fine case is flagged too, honestly")
    # D237 names this pair as a real catch, and separately notes
    # the short title "resolved fine" on its own two other copies — the check cannot tell
    # the two apart from stored data alone, which is exactly why it routes to a human.
    cards = [
        CardRecord(key="sf/1", name="Draven, Glorious Executioner", set_name="Spiritforged"),
        CardRecord(key="sf/2", name="Draven, Glorious Executioner", set_name="Spiritforged"),
        CardRecord(key="sf/bad", name="Glorious Executioner", set_name="Spiritforged"),
    ]
    flags = flag_near_duplicate_names(cards)
    ok("sf/bad" in keys(flags), "the short title is flagged against its own full name")


TESTS = [
    test_long_name,
    test_denominator_outlier,
    test_denominator_outlier_mutation,
    test_digit_count_outlier,
    test_near_duplicate_name,
    test_near_duplicate_name_measured_case,
]


def main() -> int:
    for test in TESTS:
        test()
    print()
    print(f"{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
