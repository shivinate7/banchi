#!/usr/bin/env python3
"""`scripts/demo-record.py:record_walk_plans` — the walk-plan subject list, proved against
two failures: the `2^n` powerset explosion (2026-09-27, first round) and the two-screens-
two-sets mismatch it left behind (2026-09-27, second round).

WHAT HUNG, FIRST ROUND. The old rule recorded every SUBSET of the ticked open orders (`2^n`
sets), refusing outright past `WALK_PLAN_ORDERS = 7`. A 60-card sample never has more than a
handful of open orders, so this never tripped in review. The owner's real store does: 71
open orders is `2^71` sets, not `2^7`.

THE FIX, FIRST ROUND, AND ITS OWN DEFECT. Record every SINGLE open order, plus "the one full
walk all set every screen actually asks for whole" — claiming `Orders.tsx:walkableKeysAll`
and `Fulfillment.tsx`'s `openKeys` were "exactly this same open-order list". THEY ARE NOT.
`Fulfillment.tsx` sends `order.open` alone. `Orders.tsx` sends `walkableKeysAll`, built from
`ownsAWalkableBody` — `open` OR (`terminal` and still owed a copy). Measured on the real
mirror: 71 open orders against 305 walkable ones. Recording only the 71-key set left every
"Walk all N buyers" press on `#/orders` asking for a 305-key set nothing had recorded, so
`demoServer.ts:walkPlan` refused it every time — `WalkList`'s failure branch, deterministic,
reproduced 4/4 with no CI and no contention.

THE FIX, SECOND ROUND. Record BOTH screens' own "walk all" set by name — `open_orders` (71,
`Fulfillment.tsx`) and `walkable_orders` (305, `Orders.tsx`) — plus every single WALKABLE
order (a superset of the open ones, so one loop covers both callers' singles).
`demoServer.ts:walkPlan` still refuses an unrecorded set with the demo's one honest notice
(D269/TXT-46) rather than fabricate a plan, so a partial selection stays an honest gap
rather than a silent lie.

THIS SELF-TEST proves the current rule directly (no server, no store — `take_post` is a
recording counter): the singles are the walkable set, both whole sets are recorded when they
differ, only one is recorded when they are equal, and it re-derives the retired `2**n - 1`
math to keep the first round's own finding on record.
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


def _record(open_orders, walkable_orders):
    calls: List[Dict] = []

    def take_post(path, payload, calls=calls):
        calls.append({"path": path, "keys": tuple(payload["keys"])})

    demo_record.record_walk_plans(open_orders, walkable_orders, take_post)
    return calls


def _new_rule_is_linear() -> None:
    """`open_orders == walkable_orders` (Fulfillment.tsx's set already equal to Orders.tsx's,
    the case every prior sample happened to be in) — one whole set, not two."""
    for n in (0, 1, 7, 71, 834):
        orders = ["order-%d" % i for i in range(n)]
        calls = _record(orders, orders)
        expected = 0 if n == 0 else n + 1
        ok(len(calls) == expected,
           "n=%d equal-set orders records n+1 walk plans" % n,
           "got %d, want %d" % (len(calls), expected))
        if n > 1:
            # n=1's own "single" and "whole" recordings are the identical one-key set, so
            # this shape check only distinguishes them once there are at least two orders.
            singles = [c for c in calls if len(c["keys"]) == 1]
            ok(len(singles) == n, "every single walkable order is its own recording",
               "got %d singles, want %d" % (len(singles), n))
            whole = [c for c in calls if len(c["keys"]) == n]
            ok(len(whole) == 1 and set(whole[0]["keys"]) == set(orders),
               "the one full set is recorded whole")


def _two_screens_two_sets_both_recorded() -> None:
    """THE SECOND-ROUND DEFECT, proved directly: `open_orders` a strict subset of
    `walkable_orders` (as it is on the real store, 71 of 305) must record BOTH whole sets,
    or `Orders.tsx`'s own "Walk all" press finds nothing recorded."""
    walkable = ["order-%d" % i for i in range(5)]
    open_only = walkable[:2]
    calls = _record(open_only, walkable)
    key_sets = [set(c["keys"]) for c in calls]
    ok(set(open_only) in key_sets, "Fulfillment.tsx's open-only set is recorded",
       "got %r" % key_sets)
    ok(set(walkable) in key_sets, "Orders.tsx's walkable set is recorded",
       "got %r" % key_sets)
    singles = [c for c in calls if len(c["keys"]) == 1]
    ok(len(singles) == len(walkable), "every walkable order gets its own single recording",
       "got %d, want %d" % (len(singles), len(walkable)))
    ok(len(calls) == len(walkable) + 2, "exactly n+2 recordings when the two sets differ",
       "got %d" % len(calls))


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
    _two_screens_two_sets_both_recorded()
    _old_rule_would_have_exploded()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
