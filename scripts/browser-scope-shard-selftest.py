#!/usr/bin/env python3
"""`scripts/browser-scope.py`'s shard plan, on a narrowed run, on the CLI line and on the refreshed table.

Protects: A narrowed browser run is never slower or wider than whole-file packing, and a spec that runs no test is never scheduled.
Governs: D136

WHAT THIS PROVES, on the plan the browser matrix reads (`plan_shards`, `shard`, `shard-refresh`):
- A narrowed run costs no more than `pack_shards` costs, in the slowest shard and in runners started.
  `plan_shards` takes its cut threshold from the mean of the specs it is handed, so a short list makes every
  file "heavy". Each case here narrows the real spec table and compares the plan with whole-file packing.
- A spec that declares one test is never cut: `--shard=2/2` of one test runs nothing.
- The CLI line ends in `--shard=I/N` for a half and only for a half. Playwright cuts every file a run names,
  so a flag on a whole-file leg, or a missing flag on a half, changes what runs.
- `shard-refresh` gives a file that appears once whole and once as halves its whole-file time.

WHY THIS IS A FILE OF ITS OWN. The in-file `selftest` of `browser-scope.py` (a 70 s run) holds the older plan
cases, and a test-author cannot edit that product file. This file loads the script beside it, so a checkout
tests its own copy. It has no caller in `make` yet: wiring it is a builder's step (Makefile target, `scripts/checks.py` row,
`docs/map/scripts.md` line, `docs/TESTS.md` via `make tests-page ARGS=--write`).

    python3 scripts/browser-scope-shard-selftest.py
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import re
import sys
from pathlib import Path
from typing import List, Tuple

sys.dont_write_bytecode = True
_SPEC = importlib.util.spec_from_file_location(
    "browser_scope_under_test", Path(__file__).resolve().parent / "browser-scope.py")
bs = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = bs
_SPEC.loader.exec_module(bs)

SHARDS = 12  # the browser matrix `checks.yml` starts
FAILURES: List[str] = []

#: `test(`, `test.skip(` and `test.describe(` at the start of a line. Counting a describe too only
#: makes a file look larger, which keeps a one-test candidate honest.
_DECLARES = re.compile(r"^\s*test(?:\.\w+)*\(", re.MULTILINE)
#: A loop or a `.map(` may declare tests in a body that the line count cannot see.
_LOOPS = re.compile(r"\bfor\s*\(|\.forEach\(|\.map\(")


def ok(condition: bool, label: str) -> None:
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")
    if not condition:
        FAILURES.append(label)


def declared(spec: str) -> Tuple[int, bool]:
    """`(test declarations, has a loop)` read from the spec's own text."""
    text = (bs.ROOT / spec).read_text(encoding="utf-8")
    return len(_DECLARES.findall(text)), bool(_LOOPS.search(text))


def runners(plan) -> int:
    return sum(1 for p in plan if p.specs)


def pack_runners(bins) -> int:
    return sum(1 for b in bins if b[1])


def slowest_pack(specs, times) -> float:
    return max(b[0] for b in bs.pack_shards(specs, SHARDS, times))


def named(specs, *names):
    return [s for s in specs if Path(s).name in names]


def cli_legs(*spec_args: str) -> List[Tuple[int, str]]:
    """Each leg's exit code and printed line, from `browser-scope.py shard I N`, in leg order."""
    legs = []
    for n in range(1, SHARDS + 1):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = bs.main(["shard", str(n), str(SHARDS), *spec_args])
        legs.append((rc, out.getvalue().strip()))
    return legs


def narrowed_slowest_and_runners(times, specs) -> None:
    print("\na narrowed run costs no more than whole-file packing")
    full = bs.plan_shards(specs, SHARDS, times)
    ok(max(p.load for p in full) <= slowest_pack(specs, times),
       "control: on the full suite the plan's slowest shard is no slower than whole-file packing")
    ok(runners(full) <= pack_runners(bs.pack_shards(specs, SHARDS, times)),
       "control: on the full suite the plan starts no more runners than whole-file packing")
    ok(not any(p.specs for p in bs.plan_shards([], SHARDS, times)),
       "control: an empty list plans no spec")

    narrow = [s for s in specs if Path(s).name not in ("pricing.spec.ts", "inventory.spec.ts")]
    ok(len(specs) - len(narrow) == 2,
       f"scope: the narrowed list is the table less pricing and inventory ({len(narrow)} of {len(specs)} specs)")
    plan_slowest = max(p.load for p in bs.plan_shards(narrow, SHARDS, times))
    ok(plan_slowest <= slowest_pack(narrow, times),
       f"{len(narrow)} specs: the plan's slowest shard {plan_slowest:.0f}s is no slower than "
       f"whole-file packing's {slowest_pack(narrow, times):.0f}s")

    few = named(specs, "brand.spec.ts", "cursor.spec.ts", "scaffold.spec.ts")
    ok(len(few) == 3, "scope: brand, cursor and scaffold are three specs of the table")
    started = runners(bs.plan_shards(few, SHARDS, times))
    whole = pack_runners(bs.pack_shards(few, SHARDS, times))
    ok(started <= whole,
       f"a narrowed run of {len(few)} files starts {started} runners; whole-file packing starts {whole}")


def one_test_specs(times, specs) -> None:
    print("\na spec that declares one test is never cut")
    solo = [s for s in specs if declared(s) == (1, False)]
    ok(bool(solo), "scope: the table holds a spec that declares one test and no loop")
    tests_in = {s: declared(s)[0] for s in specs}
    many = max((s for s in specs if s not in solo), key=lambda s: (tests_in[s], s))
    ok(tests_in[many] >= 2, f"scope: {Path(many).name} declares {tests_in[many]} tests, so a half of it has tests to run")

    boosted = {**times, Path(many).name: 3000.0}
    plan = bs.plan_shards(specs, SHARDS, boosted)
    ok(bs.spec_cost(specs, boosted)[many] > sum(bs.spec_cost(specs, boosted).values()) / SHARDS,
       "scope: the boosted multi-test spec costs more than a shard's mean, so the cut condition is met")
    ok(sorted(p.part for p in plan if many in p.specs) == [(1, 2), (2, 2)],
       "control: a heavy spec that declares several tests is still cut into halves 1/2 and 2/2")

    # a one-test spec made heavier than the mean: it cannot be split, and its second half runs 0 tests
    twice = []
    for spec in solo:
        heavy = {**times, Path(spec).name: 3000.0}
        ok(bs.spec_cost(specs, heavy)[spec] > sum(bs.spec_cost(specs, heavy).values()) / SHARDS,
           f"scope: {Path(spec).name} is timed above a shard's mean, so the cut condition is met")
        if sum(1 for p in bs.plan_shards(specs, SHARDS, heavy) if spec in p.specs) != 1:
            twice.append(Path(spec).name)
    ok(bool(solo) and not twice, f"a heavy one-test spec is scheduled once, not as a second half that runs no test: {twice or 'none'}")

    alone = [Path(s).name for s in solo if sum(1 for p in bs.plan_shards([s], SHARDS, times) if s in p.specs) != 1]
    ok(bool(solo) and not alone, f"a narrowed run of one one-test spec schedules it once: {alone or 'none'}")


def cli_line(times, specs) -> None:
    print("\nthe shard line carries `--shard=I/N` for a half, and for a half only")
    legs = cli_legs()
    ok(len(legs) == SHARDS and all(rc == 0 for rc, _ in legs), f"scope: the CLI answers {SHARDS} legs, each with exit 0")
    ok({tok for _, line in legs for tok in line.split() if not tok.startswith("--")} == set(specs),
       "scope: the legs between them name every spec")
    pricing = sorted(line for _, line in legs if "app/tests/pricing.spec.ts" in line.split())
    ok(len(pricing) == 2, f"scope: pricing is cut across two legs ({len(pricing)} name it)")
    ok(pricing == ["app/tests/pricing.spec.ts --shard=1/2", "app/tests/pricing.spec.ts --shard=2/2"],
       f"the two pricing legs end in --shard=1/2 and --shard=2/2, and name nothing else: {pricing}")
    halves = sum(1 for p in bs.plan_shards(specs, SHARDS, times) if p.part)
    flagged = sum(1 for _, line in legs if "--shard" in line)
    ok(flagged == halves, f"{flagged} legs carry --shard; the plan has {halves} halves, and a whole-file leg has no flag")


def refresh_table() -> None:
    print("\nshard-refresh keeps a whole file's time when a run listed it whole and another listed halves")
    # two runs: every other spec is listed twice, and pricing once whole (before the cut) and as two halves (after)
    for label, seen in (("whole first", [1100.0, 560.0, 540.0]), ("halves first", [560.0, 540.0, 1100.0])):
        total = bs._refresh_total({"a": [10.0, 12.0], "b": [1.0, 3.0], "c": [7.0, 9.0], "pricing": seen})
        ok(total["a"] == 11.0 and total["b"] == 2.0 and total["c"] == 8.0,
           f"scope ({label}): two runs, and a file listed twice keeps its median")
        ok(abs(total["pricing"] - 1100.0) <= 55.0,
           f"({label}) occurrences {seen} give the whole-file time near 1100, got {total['pricing']:.0f}")
    both_cut = bs._refresh_total({"a": [10.0, 12.0], "pricing": [500.0, 560.0, 520.0, 540.0]})
    ok(both_cut["pricing"] == 1060.0, "control: a file cut in both runs sums its halves and averages the runs")


def main() -> int:
    times, specs = bs.load_spec_times(), bs.all_specs()
    print("browser-scope shard plan self-test\n" + "=" * 72)
    narrowed_slowest_and_runners(times, specs)
    one_test_specs(times, specs)
    cli_line(times, specs)
    refresh_table()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} failed")
        return 1
    print("clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
