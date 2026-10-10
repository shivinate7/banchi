#!/usr/bin/env python3
"""Harness runner — T1-T11.

`make harness` exits 0 only when all ten tests pass. Nothing in this project is "done"
until it does. See docs/GATES.md for the contract; every threshold there is a number, not
an adjective, and the numbers live in the test modules next to the code that checks them.

EVERY PRESENT-TENSE COUNT IN THIS DOCSTRING HAS A READER AS OF 2026-09-12, and it earned
one: this file said EIGHT in three places — the title, the sentence above and the last
paragraph — while `TESTS` below held nine, and `make docs-audit`'s `harness tests` row
printed "9 registered and documented" throughout, because its other side was the markdown
and never the file that decides the list. The range and historical claims below are
deliberately outside the patterns; see `_HARNESS_CLAIMS` in scripts/docs_audit/harness_criteria.py.

T1-T4 are the original contract. T5 (pricing) and T6 (geometry) arrived with batch script
v2: a wrong price is a distinct failure from a wrong match, and a card the pipeline cannot
find in its own photograph is a third thing again. Each earns its own failing test name.

T8 (code cards) arrived with C9-C11 on 2026-08-30, for the same reason: a code is a
bearer instrument, and reading one wrong, selling one twice, or letting a premium one
leave in a bulk lot are three different failures that must not hide inside one another.

T11 (the order walk plan) arrived with `pipeline/walkplan.py` on 2026-09-17. THERE IS NO
T10 AND THE GAP IS DELIBERATE: T10 is spelled for the Intelligent Mail barcode encoder,
shelved on the owner's ruling with `pipeline/imb.py` on branch
`claude/tcgtracking-in-house-a7cb43` at c9391e1 and named as T10 throughout
`docs/debts/026-*.md`. This repo's rule for a contended id is to renumber your own and never
another's, so the shelf keeps its number. `TESTS` is the count either way, which is what the
sentences above say to recount from — the range in this file's title is the HIGHEST id and
has never been a claim that every id between exists.

All ten tests always run, even after one fails. A runner that stops at the first failure
hides the state of everything behind it, which is the opposite of what a status signal
is for.
"""

import sys
import traceback
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.tests import NotImplementedYet, Result  # noqa: E402
from harness.tests.home import isolated_home  # noqa: E402
from harness.tests import (  # noqa: E402
    t1_id_eval,
    t2_round_trip,
    t3_join_coverage,
    t4_variant_ladder,
    t5_pricing,
    t6_geometry,
    t7_store_and_seams,
    t8_codes,
    t9_traces,
    t11_walk_plan,
)

# Explicit and ordered. No discovery magic: a test that silently stops being collected is
# a green harness that checks nothing.
TESTS = [
    t1_id_eval,
    t2_round_trip,
    t3_join_coverage,
    t4_variant_ladder,
    t5_pricing,
    t6_geometry,
    t7_store_and_seams,
    t8_codes,
    t9_traces,
    t11_walk_plan,
]


# `--part K` runs one of PARTS slices, so CI can shard the harness (T7 is 342 checks and most of
# its time). Part 1 also runs every test but T7; each part runs the T7 checks whose name hashes to it (crc32 spreads the
# slow `check_send_*` run, which a stride put in one part), so the parts together run each check once. `make docs-audit`'s `check registry`
# row reads PARTS and wants one `harness-K` registry entry for every K.
PARTS = 3


def run_one(module, part=None):
    try:
        if part and module is t7_store_and_seams:
            result = module.run(order=lambda todo: [c for c in todo if zlib.crc32(c.__name__.encode()) % PARTS == part - 1])
        else:
            result = module.run()
    except NotImplementedYet as exc:
        return Result(False, str(exc) or "not implemented")
    except Exception:
        return Result(False, "raised:\n" + traceback.format_exc().rstrip())

    if not isinstance(result, Result):
        return Result(False, f"{module.NAME}.run() returned {type(result).__name__}, expected Result")
    return result


def main(part=None):
    print("BANCHI harness — docs/GATES.md" + (f" (part {part} of {PARTS})" if part else ""))
    print("=" * 72)

    results = []
    for module in TESTS:
        if part and part > 1 and module is not t7_store_and_seams:
            continue
        result = run_one(module, part)
        results.append((module, result))

        status = "PASS" if result.passed else "FAIL"
        print(f"\n{status}  {module.NAME} — {module.DESCRIPTION}")
        print(f"      pass: {module.PASS_CRITERIA}")
        for line in str(result.detail).splitlines():
            print(f"      {line}")

    failed = [m.NAME for m, r in results if not r.passed]

    print("\n" + "=" * 72)
    if failed:
        print(f"{len(failed)} of {len(results)} failed: {', '.join(failed)}")
        return 1

    print(f"all {len(results)} passed")
    return 0


if __name__ == "__main__":
    # Every test runs against a throwaway store and no settings file, for the whole process.
    with isolated_home():
        args = sys.argv[1:]
        if args and (len(args) != 2 or args[0] != "--part" or args[1] not in map(str, range(1, PARTS + 1))):
            sys.exit(f"usage: harness/run.py [--part 1..{PARTS}]")
        sys.exit(main(int(args[1]) if args else None))
