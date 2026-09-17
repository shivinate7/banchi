#!/usr/bin/env python3
"""DOES THIS CHANGE REACH WHAT THE SUPERVISOR SELF-TEST READS?

`make serve-selftest` is 70.1 seconds, measured 2026-09-17, which is 37% of `make check`'s
187.5. It is the largest single target in the suite and the one a screen change cannot
possibly break: it copies this checkout into a throwaway tree, gives it a STUB `app/`, and
proves the supervisor's build job against a shell script that writes one file. Nothing under
`app/` is carried into the copy at all.

THE OWNER RULED THIS ONE IN AND THE REST OUT, 2026-09-17. Path gating is not a general policy
here: nine targets in `make check` cost under a tenth of a second each, so thirty-five scope
lists would cost more to maintain than they save. This is the one place where the seconds are
large AND the dependency is crisp. A request for a SECOND entry is evidence the policy is
spreading and needs the owner's word again — that is the ruling, recorded in
`docs/specs/verification-cost.md` §9.

THE LIST IS DERIVED FROM THE SELF-TEST'S OWN `CARRY`, NOT TYPED BESIDE IT. `CARRY` in
`scripts/serve-selftest.py` is the literal list of what gets copied into the throwaway tree,
which is the definition of what that test can observe. `make docs-audit`'s `serve scope` row
reconciles the two in both directions and fails a commit when they drift. The three entries
here that are NOT in `CARRY` each carry `"beyond_carry"` saying why, and the row checks that
too — because a path filter that is too narrow silently stops testing something, and a gate
that quietly stops running is worse than no gate: the green is believed. That sentence is
`scripts/browser-scope.py`'s, about the same failure.

IT REUSES THE MATCHER RATHER THAN COPYING IT. The globbing and the recipe narrowing live in
`scripts/browser-scope.py` and are imported. Two copies of that logic would drift, and the
drift would be invisible: both would answer, and nobody would know which was right.

IT FAILS OPEN, IN EVERY DIRECTION. No merge-base, a diff it cannot compute, an EMPTY diff
(more likely a wrong base than an empty change), a `CARRY` it cannot read, and a recipe it
cannot extract all answer RUN, out loud. Only an explicit skip skips, and `PKMNSCAN_SERVE_SCOPE=off`
turns the whole gate off and is printed every time it skips.

    scripts/serve-scope.py classify [--base REV] [--head REV]
        Prints the reasoning and exits 0 to RUN, 3 to SKIP. `make serve-selftest` reads it.
    scripts/serve-scope.py list
    scripts/serve-scope.py selftest

Stdlib only, and `git`.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import os
import sys
from pathlib import Path
from typing import List, Sequence

ROOT = Path(__file__).resolve().parent.parent
HATCH = "PKMNSCAN_SERVE_SCOPE"

# EVERY PATH `make serve-selftest` READS, AND WHY. Pure literals: `scripts/docs-audit.py`
# reads this tuple with `ast.literal_eval` rather than importing the module. Entries whose
# path is a `CARRY` name carry no `beyond_carry`; the three that are not carried do.
SCOPE = (
    {"path": "scripts/serve.py", "why": "the supervisor itself — what is under test."},
    {"path": "scripts/primary_sync.py",
     "why": "in the supervisor's SELF_FILES and imported at module scope, so a tree without "
            "it cannot start one at all."},
    {"path": "envfile.py", "why": "carried into the copy; the supervisor reads it at start."},
    {"path": "server/**", "why": "the capture server the supervisor re-execs."},
    {"path": "store/**", "why": "carried; the capture server opens the store on boot."},
    {"path": "pipeline/**", "why": "carried; imported by the routes the copy answers on."},
    {"path": "cli/**", "why": "carried into the copy."},
    {"path": "identify/**", "why": "carried into the copy."},
    {"path": "geometry/**", "why": "carried into the copy."},
    {"path": "codes/**", "why": "carried into the copy."},
    {"path": "fixtures/**", "why": "carried into the copy."},
    {
        "path": "scripts/serve-selftest.py",
        "beyond_carry": "the test itself. A change to what it proves is proven only by the "
                        "run it decides about — `browser-scope.py` makes the same argument "
                        "about its own workflow.",
        "why": "the test itself.",
    },
    {
        "path": "scripts/serve-scope.py",
        "beyond_carry": "this classifier. A change to the gate's own reasoning is proven "
                        "only by running what it gates.",
        "why": "the gate's own reasoning.",
    },
    {
        "path": "Makefile",
        "within": "recipe:serve-selftest",
        "beyond_carry": "the recipe that invokes it, narrowed to that recipe and the "
                        "variables it expands. A change to `make up` is not a change to what "
                        "this test reads, and the Makefile is touched by every third merge.",
        "why": "the recipe that runs it.",
    },
)

# `app/**` IS DELIBERATELY ABSENT, AND IT IS THE WHOLE POINT OF THIS FILE.
# `scripts/serve-selftest.py` writes a STUB `app/` into the throwaway tree and never copies
# this one — its own header says so: "a real `app/` means `node_modules` and a real `vite
# build`, which is the one thing this script is deliberately not testing." The day it copies
# a real `app/`, `CARRY` gains the name and the `serve scope` row fails until this list
# follows. That is the reconciliation doing its job, not a surprise.


def _browser_scope():
    """The matcher, imported rather than reimplemented."""
    path = ROOT / "scripts" / "browser-scope.py"
    spec = importlib.util.spec_from_file_location("_browser_scope_for_serve", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_browser_scope_for_serve"] = module
    spec.loader.exec_module(module)
    return module


def carried_names(source: str | None = None) -> List[str]:
    """`CARRY` out of `scripts/serve-selftest.py`, read with `ast` and never imported."""
    text = source if source is not None else (ROOT / "scripts" / "serve-selftest.py").read_text()
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "CARRY" for t in node.targets):
            continue
        value = ast.literal_eval(node.value)
        return [str(name) for name in value]
    raise ValueError("no CARRY list in scripts/serve-selftest.py")


def scope_for(entry: dict) -> str:
    """A SCOPE path as the `CARRY` name it stands for, or itself."""
    return entry["path"][:-3] if entry["path"].endswith("/**") else entry["path"]


def classify(base: str | None, head: str) -> tuple:
    browser = _browser_scope()
    if os.environ.get(HATCH) == "off":
        return True, [f"{HATCH}=off — the self-test RUNS."]
    reference = base or "origin/main"
    # `classify_revisions` would use browser-scope's OWN scope, so the git half is borrowed
    # piece by piece and the pure half is called with ours.
    start = browser.landing_base(reference, head)
    if start is None:
        return True, [f"no merge-base between {reference} and {head} — the self-test RUNS."]
    paths = browser.changed_paths(start, head)
    if paths is None:
        return True, [f"`git diff {start[:12]} {head}` failed — the self-test RUNS."]
    verdict = browser.classify_paths(
        paths, browser.git_reader(start, head), scope=SCOPE,
        subject="what `make serve-selftest` reads", noun="the self-test")
    lines = [f"{len(paths)} changed path(s) from {start[:12]} to {head}:"] + list(verdict.lines)
    if not verdict.run:
        lines.append(f"  ({HATCH}=off runs it anyway.)")
    return verdict.run, lines


def selftest() -> int:
    ok = True

    def check(label: str, got, want) -> None:
        nonlocal ok
        if got == want:
            print(f"  ok   {label}")
        else:
            ok = False
            print(f"  FAIL {label}\n       got  {got!r}\n       want {want!r}")

    browser = _browser_scope()

    def verdict(paths: Sequence[str]) -> bool:
        return browser.classify_paths(
            paths, lambda side, path: "", scope=SCOPE,
            subject="x", noun="y").run

    check("a screen change does not run it", verdict(["app/src/Orders.tsx"]), False)
    check("a spec change does not run it", verdict(["app/tests/orders.spec.ts"]), False)
    check("a doc change does not run it", verdict(["docs/DESIGN.md"]), False)
    check("the supervisor runs it", verdict(["scripts/serve.py"]), True)
    check("a server change runs it", verdict(["server/capture_server.py"]), True)
    check("a store change runs it", verdict(["store/master.py"]), True)
    check("the test itself runs it", verdict(["scripts/serve-selftest.py"]), True)
    check("this classifier runs it", verdict(["scripts/serve-scope.py"]), True)
    check("an empty diff runs it", verdict([]), True)
    check("one in-scope path among many runs it",
          verdict(["docs/DESIGN.md", "app/src/Home.tsx", "store/master.py"]), True)

    # THE RECONCILIATION, PROVED HERE TOO AND NOT ONLY IN THE AUDIT ROW.
    carried = set(carried_names())
    declared = {scope_for(entry) for entry in SCOPE if "beyond_carry" not in entry}
    check("every carried name is in SCOPE", sorted(carried - declared), [])
    check("every SCOPE entry without `beyond_carry` is carried", sorted(declared - carried), [])
    check("`app/` is not carried, which is why it is not in SCOPE", "app" in carried, False)
    check("every entry gives a reason", all(entry.get("why") for entry in SCOPE), True)

    # A DRIFT IS CAUGHT: a CARRY that gained `app` must fail the reconciliation.
    drifted = set(carried_names('CARRY = ("scripts/serve.py", "app")\n'))
    check("a CARRY that gained a name is caught",
          sorted(drifted - declared), ["app"])

    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("classify")
    run.add_argument("--base")
    run.add_argument("--head", default="HEAD")
    sub.add_parser("list")
    sub.add_parser("selftest")
    args = parser.parse_args()

    if args.command == "selftest":
        return selftest()
    if args.command == "list":
        for entry in SCOPE:
            mark = "  (beyond CARRY)" if "beyond_carry" in entry else ""
            print(f"  {entry['path']}{mark}\n      {entry['why']}")
        return 0
    if args.command == "classify":
        should_run, lines = classify(args.base, args.head)
        for line in lines:
            print(line)
        return 0 if should_run else 3
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
