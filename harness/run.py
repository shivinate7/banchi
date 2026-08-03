#!/usr/bin/env python3
"""Harness runner — T1-T4.

`make harness` exits 0 only when all four tests pass. Nothing in this project is "done"
until it does. See docs/GATES.md for the contract; every threshold there is a number, not
an adjective, and the numbers live in the test modules next to the code that checks them.

All four tests always run, even after one fails. A runner that stops at the first failure
hides the state of the other three, which is the opposite of what a status signal is for.
"""

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.tests import NotImplementedYet, Result  # noqa: E402
from harness.tests import t1_id_eval, t2_round_trip, t3_join_coverage, t4_variant_ladder  # noqa: E402

# Explicit and ordered. No discovery magic: a test that silently stops being collected is
# a green harness that checks nothing.
TESTS = [t1_id_eval, t2_round_trip, t3_join_coverage, t4_variant_ladder]


def run_one(module):
    try:
        result = module.run()
    except NotImplementedYet as exc:
        return Result(False, str(exc) or "not implemented")
    except Exception:
        return Result(False, "raised:\n" + traceback.format_exc().rstrip())

    if not isinstance(result, Result):
        return Result(False, f"{module.NAME}.run() returned {type(result).__name__}, expected Result")
    return result


def main():
    print("PKMNSCAN harness — docs/GATES.md")
    print("=" * 72)

    results = []
    for module in TESTS:
        result = run_one(module)
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
    sys.exit(main())
