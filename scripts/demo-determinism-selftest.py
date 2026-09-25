#!/usr/bin/env python3
"""`scripts/demo-determinism.py`'s own matcher, proved on fixtures (identity-follows-sku.md
§4, lane 7).

WHAT THIS PROVES. `ALLOWED_PATTERNS` matches a JSON pointer WHOLE, never a bare key anywhere
in it — the defect this self-test exists to catch by name: the check used to be `ALLOWED_KEYS`,
a flat set of key names tested against `set(pointer.split("/"))`, so a bare `at` excused an
`at` ANYWHERE in the bundle, whatever sat beside it. A moved value under a path this file does
not name, that merely CONTAINS a key this file does name (`at`), must still fail — that is the
one case a segment-matching reader gets wrong and a whole-path reader gets right, and it is
the case this self-test plants.

Every real, measured pointer the two `make demo` runs actually move (12 shapes, from a real
`make demo-determinism` run against the tree this lane landed) is also checked here, so a
pattern that stops matching its own real shape is caught without spending the ~2 minutes two
full seed-and-record passes cost. Pure functions only — no subprocess, no `make demo`, no
write anywhere — which is why this is IN `make check`, unlike `demo-determinism` itself (D18:
that target writes two scratch stores and is a press, run by hand).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import importlib.util  # noqa: E402

# Hyphenated filename: `import scripts.demo-determinism` is not valid Python, so this loads
# it the way `scripts/docs-audit.py:_load_module` loads every hyphenated sibling.
_SPEC = importlib.util.spec_from_file_location(
    "demo_determinism", ROOT / "scripts" / "demo-determinism.py"
)
demo_determinism = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(demo_determinism)

PASS = 0
FAIL = 0


def ok(condition: bool, label: str, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok     {label}")
    else:
        FAIL += 1
        print(f"  FAIL   {label}")
        if detail:
            print(f"         {detail}")


# Every pointer a real `make demo-determinism` run measured moving between two full `make
# demo` passes, over the tree this lane landed on (12 distinct shapes; the run also produces
# several instances of a few of them — the roster below is deduplicated by shape). Each one
# must still match `ALLOWED_PATTERNS` whole.
REAL_MOVED_POINTERS = (
    "/responses//orders/body/orders/0/changed_at",
    "/responses//orders/body/orders/3/progress/0/at",
    "/responses//pipeline/pricing/body/roster/0/updated_at",
    "/responses//pipeline/pricing/body/runs/0/updated_at",
    "/responses//pipeline/pricing/body/written_at/demo-box1",
    "/responses//pipeline/pricing?run=demo-box3&run=demo-box1/body/written_at/demo-box3",
    "/responses//pipeline/runs/body/runs/0/updated_at",
    "/responses//pipeline/runs/demo-box1/body/files/0/modified",
    "/responses//pipeline/runs/demo-box3/body/manifest/updated_at",
    "/responses//pipeline/runs/demo-box1/body/updated_at",
    "/responses//status/body/boot_id",
    "/responses//status/body/started_at",
    "/responses/POST /shipping/batches/body/batch",
)

# Pointers that must NEVER match — each one contains a key `ALLOWED_PATTERNS` legitimately
# excuses SOMEWHERE, but under a path this file does not name. A segment-matching reader
# (the pre-lane-7 `ALLOWED_KEYS`) would wrongly excuse every one of these.
UNLISTED_POINTERS_CONTAINING_AN_ALLOWED_KEY = (
    # `at` is legitimately excused under /orders/.../progress/N/at and under
    # /pipeline/pricing.../written_at/<run> — never under an event line or a review entry.
    "/responses//review/body/entries/0/at",
    "/responses//inventory/body/cards/0/events/2/at",
    # `updated_at` is legitimately excused under /pipeline/runs and /pipeline/pricing —
    # never under a SKU's own stored reading.
    "/responses//product/body/sku/CR-VEN-001/updated_at",
    # `batch` is legitimately excused as POST /shipping/batches' own minted id — never as a
    # box's own batch-of-cards figure.
    "/responses//boxes/body/boxes/0/batch",
)


def main() -> int:
    print("demo-determinism self-test — ALLOWED_PATTERNS matches by path, not by key\n")

    for pointer in REAL_MOVED_POINTERS:
        ok(
            bool(demo_determinism._allowed(pointer)),
            f"real moved pointer excused: {pointer}",
        )

    print()
    for pointer in UNLISTED_POINTERS_CONTAINING_AN_ALLOWED_KEY:
        ok(
            not demo_determinism._allowed(pointer),
            f"unlisted pointer NOT excused, though it contains an allowed key: {pointer}",
        )

    print()
    # End to end, through `_diff` too — the same two-dict comparison `main()` runs, in the
    # real bundle's own shape (a top-level "responses" map keyed by route), so a bug at the
    # seam between `_diff`'s own pointer-building and `_allowed`'s matching is caught here
    # rather than only in each function alone. One leaf moves under a KNOWN pattern (an
    # order's own `changed_at`); one moves under an UNLISTED route that merely contains the
    # key `at` (a fabricated `/review` route) — a segment-matching reader would wrongly
    # excuse the second, which is the exact regression this self-test exists to catch.
    before = {
        "responses": {
            "/orders": {"body": {"orders": [{"changed_at": "2026-09-25T00:00:00+00:00"}]}},
            "/review": {"body": {"entries": [{"at": "2026-09-25T00:00:00+00:00"}]}},
        }
    }
    after = {
        "responses": {
            "/orders": {"body": {"orders": [{"changed_at": "2026-09-25T00:01:00+00:00"}]}},
            "/review": {"body": {"entries": [{"at": "2026-09-25T00:01:00+00:00"}]}},
        }
    }
    moved: list = []
    demo_determinism._diff(before, after, "", moved)
    unexpected = [p for p, _, _ in moved if not demo_determinism._allowed(p)]
    ok(len(moved) == 2, "the fixture diff finds both moved leaves",
       f"found {len(moved)}: {[p for p, _, _ in moved]}")
    ok(
        unexpected == ["/responses//review/body/entries/0/at"],
        "only the /review leaf is unexpected — its `at` is a bare key this file never "
        "names under that route, and it must fail even though /orders' own `changed_at` "
        "passes in the same run",
        f"unexpected: {unexpected}",
    )

    print(f"\ndemo-determinism self-test: {PASS} passed" + (f", {FAIL} FAILED" if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
