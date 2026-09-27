#!/usr/bin/env python3
"""`scripts/demo-record.py:record_walk_plans` — the walk-plan subject list, proved against
the failure a real 71-open-order rebuild hit, 2026-09-27.

WHAT HUNG. The old rule recorded every SUBSET of the ticked open orders (`2^n` sets),
refusing outright past `WALK_PLAN_ORDERS = 7`. A 60-card sample never has more than a
handful of open orders, so this never tripped in review. The owner's real store does:
71 open orders is `2^71` sets, not `2^7`, and the recorder refused with "71 orders is more
than the 7 whose every ticked set this recorder can afford to record."

THE FIX. Record every SINGLE open order, plus the one full "walk all" set every screen
actually asks for whole (`Orders.tsx:walkableKeysAll`, `Fulfillment.tsx`'s `openKeys`) —
`n + 1` recordings, linear in the order count, for any `n`. `demoServer.ts:walkPlan`
already refuses an unrecorded set with the demo's one honest notice (D269/TXT-46) rather
than fabricate a plan, so a partial selection stays an honest gap rather than a silent lie.

THIS SELF-TEST proves the NEW rule directly (no server, no store — `take_post` is a
recording counter) and proves the OLD rule's failure mode by walking the same math the old
code did: `2**n - 1` sets for `n` orders, shown to explode past `WALK_PLAN_ORDERS` for the
71-order case that broke a real build, and to fit only the tiny cases a 60-card sample
could ever produce.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import importlib.util  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "demo_record", ROOT / "scripts" / "demo-record.py"
)
demo_record = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(demo_record)

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


def _new_rule_is_linear() -> None:
    for n in (0, 1, 7, 71, 834):
        calls: List[Dict] = []
        orders = ["order-%d" % i for i in range(n)]

        def take_post(path, payload, calls=calls):
            calls.append({"path": path, "keys": tuple(payload["keys"])})

        demo_record.record_walk_plans(orders, take_post)
        expected = 0 if n == 0 else n + 1
        ok(len(calls) == expected,
           "n=%d open orders records n+1 walk plans" % n,
           "got %d, want %d" % (len(calls), expected))
        if n > 1:
            # n=1's own "single" and "whole" recordings are the identical one-key set, so
            # this shape check only distinguishes them once there are at least two orders.
            singles = [c for c in calls if len(c["keys"]) == 1]
            ok(len(singles) == n, "every single order is its own recording",
               "got %d singles, want %d" % (len(singles), n))
            whole = [c for c in calls if len(c["keys"]) == n]
            ok(len(whole) == 1 and set(whole[0]["keys"]) == set(orders),
               "the one full set is recorded whole")


def _old_rule_would_have_exploded() -> None:
    """The math the OLD code ran — `2**n - 1`, refused outright past 7 — walked here
    directly rather than reintroducing the deleted `itertools.combinations` loop, since
    that loop is gone from the file this self-test is against (it must stay gone)."""
    WALK_PLAN_ORDERS = 7  # the retired constant's own value, for the comparison alone
    for n, should_fit in ((3, True), (7, True), (8, False), (71, False)):
        sets = 2 ** n - 1
        fits = n <= WALK_PLAN_ORDERS
        ok(fits == should_fit, "n=%d fits the old %d-order ceiling" % (n, WALK_PLAN_ORDERS),
           "got fits=%s" % fits)
        if n == 71:
            ok(sets > 10 ** 20, "71 orders is an astronomical set count under the old rule",
               "got %d" % sets)


def main() -> int:
    _new_rule_is_linear()
    _old_rule_would_have_exploded()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
