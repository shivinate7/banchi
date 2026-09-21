#!/usr/bin/env python3
"""DOES THIS CHANGE REACH WHAT ONE OF THE FIFTEEN GUARD SELF-TESTS PROVES?

Measured on this Mac, 2026-09-20: `make check` is 163.85s. Fifteen guard self-tests —
`reap-selftest`, `claim-selftest`, `guard-shell-selftest`, `sync-selftest`, `audit-self-test`,
`janitor-selftest`, `merge-selftest`, `githooks-selftest`, `silent-write-selftest`,
`verdict-selftest`, `revert-selftest`, `suite-lock-selftest`, `submission-selftest`,
`screen-freshness-selftest` and `cid-selftest` — cost 76.6s of that, 47%, against a
ten-test product harness of 21.75s. A guard self-test proves a MECHANISM. It cannot catch a
product defect, and it has something new to say only when the guard it proves, or this
classifier, or the recipe that runs it, changes. D247
is the argument; `docs/specs/verification-cost.md` §11 is the measurement.

THE OWNER RULED A SECOND PATH-GATED TARGET IN, 2026-09-20, on that measurement.
`scripts/serve-scope.py`'s own header says a request for a second entry is "evidence the
policy is spreading and needs the owner's word again" — that word was given, and this file
is what was built on it. Fifteen entries, not one: unlike `serve-selftest`'s single
unbreakable-by-any-`app/`-change case, most of `make check`'s guard self-tests each prove
one guard script, so one classifier serving fifteen is the shape that avoids fifteen
near-identical copies of `serve-scope.py`.

THE SUBJECT LIST IS DERIVED FROM EACH SELF-TEST'S OWN SOURCE, NEVER TYPED BESIDE IT.
`ROSTER` below names which fifteen targets are gated — that selection is a product decision,
on `serve-scope.py`'s own precedent (it names `serve-selftest` the same way). What each
target's SUBJECT is — the files that decide whether it can possibly go red — is computed by
`derive_subjects()` by reading the test's own source on every call: every `from store import
photos`-shaped local-package import wherever it appears in the file (`store`, `cli`,
`pipeline`, `identify`, `geometry`, `codes`, `server` — CLAUDE.md's own package list), every
`ROOT / "scripts" / "guard-shell.py"`-shaped path chain, and — for the four shell scripts,
which have no AST — the same path shapes read with a regex. A hand-typed list beside each
self-test is the exact rot this whole workstream exists to fix, so there is no such list here:
change what a self-test imports, and this reader sees the new subject on its very next call,
with nothing to keep in sync.

IT REUSES THE MATCHER, on `serve-scope.py`'s own precedent: the globbing and the recipe
narrowing are `scripts/browser-scope.py`'s `classify_paths`, imported rather than copied.

IT FAILS OPEN, IN EVERY DIRECTION. No merge-base, a diff it cannot compute, an EMPTY diff,
an unscoped target name, and any exception raised while deriving a subject all answer RUN,
out loud. Only an explicit skip skips, and `PKMNSCAN_GUARD_SCOPE=off` turns the whole gate
off for every target and is printed every time any of them skips.

    scripts/guard-scope.py classify --target <name> [--base REV] [--head REV]
        Prints the reasoning and exits 0 to RUN, 3 to SKIP. Each of the fifteen Makefile
        recipes calls this with its own name.
    scripts/guard-scope.py list [--target <name>]
    scripts/guard-scope.py selftest

Stdlib only, and `git`.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
HATCH = "PKMNSCAN_GUARD_SCOPE"

# CLAUDE.md's own list: "the Python packages (server/ store/ pipeline/ identify/ geometry/
# codes/ cli/)". A local-package import is resolved against this list, never a guess.
LOCAL_PACKAGES = ("store", "cli", "pipeline", "identify", "geometry", "codes", "server")

# THE FIFTEEN — the owner's list, 2026-09-20. Which targets are gated is declared here, on
# `serve-scope.py`'s own precedent (it declares its one target the same way). What each one
# READS is never declared beside it; see `derive_subjects()`.
ROSTER = (
    {"target": "reap-selftest", "test": "scripts/reap-selftest.sh"},
    {"target": "claim-selftest", "test": "scripts/claim-selftest.py"},
    {"target": "guard-shell-selftest", "test": "scripts/guard-shell-selftest.sh"},
    {"target": "sync-selftest", "test": "scripts/sync-selftest.py"},
    {"target": "audit-self-test", "test": "scripts/docs-audit.py", "func": "self_test"},
    {"target": "janitor-selftest", "test": "scripts/janitor-selftest.sh"},
    {"target": "merge-selftest", "test": "scripts/merge-selftest.sh"},
    {"target": "githooks-selftest", "test": "scripts/githooks-selftest.sh"},
    {"target": "silent-write-selftest", "test": "scripts/silent-write-selftest.sh"},
    {"target": "verdict-selftest", "test": "scripts/verdict-selftest.py"},
    {"target": "revert-selftest", "test": "scripts/revert-audit.py"},
    {"target": "suite-lock-selftest", "test": "scripts/suite-lock.py"},
    {"target": "submission-selftest", "test": "scripts/submission-selftest.py"},
    {"target": "screen-freshness-selftest", "test": "scripts/screen-freshness.mjs"},
    {"target": "cid-selftest", "test": "scripts/cid-selftest.py"},
)

TARGETS = {entry["target"] for entry in ROSTER}


def _browser_scope():
    """The matcher, imported rather than reimplemented — `serve-scope.py`'s own pattern."""
    path = ROOT / "scripts" / "browser-scope.py"
    spec = importlib.util.spec_from_file_location("_browser_scope_for_guard", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_browser_scope_for_guard"] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- derivation


def _flatten_div(node: ast.AST) -> Optional[List[str]]:
    """A `Path`-style `A / "b" / "c.py"` chain, as its string parts, left to right.

    The leftmost operand may be anything (`ROOT`, a call, an attribute) — it contributes no
    string of its own, and the chain is still read from there rightward. A right side that is
    not a plain string constant (an f-string, a variable) breaks the chain and this returns
    `None`, so a dynamic path is never guessed at.
    """
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _flatten_div(node.left)
        if left is None:
            if isinstance(node.left, (ast.Name, ast.Attribute, ast.Call)):
                left = []
            else:
                return None
        if isinstance(node.right, ast.Constant) and isinstance(node.right.value, str):
            return left + [node.right.value]
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    return None


class _PathCollector(ast.NodeVisitor):
    """Every local-package import and every `Path`-chain in a module, wherever it sits.

    `ast.walk` would also re-visit every inner `BinOp` of a chain as if it were its own
    top-level one (`ROOT / "scripts"` inside `ROOT / "scripts" / "x.py"`), which would add
    the bare directory `scripts` as a "subject" and defeat the whole point — a change
    anywhere under `scripts/` would then re-arm every target. Overriding `visit_BinOp` and
    skipping `generic_visit` once a chain resolves keeps only the outermost, full chain.
    """

    def __init__(self) -> None:
        self.hits: Set[str] = set()

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, ast.Div):
            parts = _flatten_div(node)
            if parts:
                self.hits.add("/".join(parts))
                return
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            parts = node.module.split(".")
            if parts[0] in LOCAL_PACKAGES:
                if len(parts) > 1:
                    self.hits.add("/".join(parts) + ".py")
                else:
                    for alias in node.names:
                        self.hits.add(f"{parts[0]}/{alias.name}.py")
        self.generic_visit(node)


# Shell has no AST, so the same path shapes are read with a regex instead: a directory this
# repo actually has, then whatever comes after — extension or not, because
# `scripts/githooks/reference-transaction` and its siblings carry none.
_SH_PATH_RE = re.compile(
    r"(?:scripts|server|store|pipeline|cli|identify|geometry|codes|app)/[A-Za-z0-9_./-]+"
)
# A bare sibling filename — `GUARD="$HERE/guard-shell.py"`, `REAP=".../reap.py"` — carries no
# directory at all; every one of these lives beside its selftest, in `scripts/`.
_BARE_PY_RE = re.compile(r"[\"'/]([A-Za-z0-9_-]+\.py)[\"']")


def derive_subjects(test_path: Path, func: Optional[str] = None) -> Tuple[str, ...]:
    """Every local file `test_path` reads, read out of its own source — never hand-typed.

    `func`, when given, narrows the scan to one top-level function's own body instead of the
    whole module — `audit-self-test`'s reason: `scripts/docs-audit.py` is one 20,000-line
    file that both contains `self_test()` (isolated, no filesystem access — its own
    docstring says so) and every `check_*` row's own file constants, so scanning the whole
    module would make audit-self-test "reachable" from nearly everything the audit checks,
    which is not what `--self-test` actually reads. `revert-audit.py` and `suite-lock.py`
    need no such narrowing: each is a normal-sized guard that tests itself, whole.

    Filtered to paths that exist as real files, so a renamed subject falls out on its own
    instead of pointing at nothing, and a false hit (a decorative string that happens to look
    like a path) never survives. A hit under `scripts/githooks/` widens to the whole
    directory: `githooks-selftest.sh` names two of its five hooks as literal paths and the
    rest only in prose ("its pre-push sibling") — a reader that stopped at the two named
    ones would silently narrow what the gate can see, which is the exact failure this
    workstream exists to close.
    """
    if not test_path.exists():
        return ()
    try:
        text = test_path.read_text()
    except OSError:
        return ()
    hits: Set[str] = set()
    if test_path.suffix == ".py":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return ()
        scan_root: ast.AST = tree
        if func is not None:
            found = next(
                (n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func),
                None,
            )
            if found is None:
                return ()
            scan_root = found
        collector = _PathCollector()
        collector.visit(scan_root)
        hits |= collector.hits
    else:
        hits |= set(_SH_PATH_RE.findall(text))
        for name in _BARE_PY_RE.findall(text):
            if (ROOT / "scripts" / name).exists():
                hits.add(f"scripts/{name}")

    resolved: Set[str] = set()
    for hit in hits:
        candidate = hit.rstrip("/")
        if "__pycache__" in candidate:
            continue
        if (ROOT / candidate).is_file():
            resolved.add(candidate)

    if any(h.startswith("scripts/githooks/") for h in resolved):
        resolved = {h for h in resolved if not h.startswith("scripts/githooks/")}
        resolved.add("scripts/githooks/**")

    try:
        rel_test = str(test_path.relative_to(ROOT))
    except ValueError:
        rel_test = ""
    resolved.discard(rel_test)
    return tuple(sorted(resolved))


def scope_for(entry: dict) -> Tuple[dict, ...]:
    """The full `classify_paths` scope for one roster entry: subjects, the test, the gate."""
    rel_test = entry["test"]
    subjects = derive_subjects(ROOT / rel_test, func=entry.get("func"))
    scope: List[dict] = [{"path": rel_test, "why": "the test itself."}]
    for subject in subjects:
        scope.append({"path": subject, "why": f"read by `{rel_test}`, derived from its source."})
    scope.append({
        "path": "scripts/guard-scope.py",
        "beyond_carry": "this classifier. A change to the gate's own reasoning is proven only "
                        "by running what it gates.",
        "why": "the gate's own reasoning.",
    })
    scope.append({
        "path": "Makefile",
        "within": f"recipe:{entry['target']}",
        "beyond_carry": "the recipe that invokes it, narrowed to that recipe and the "
                        "variables it expands.",
        "why": "the recipe that runs it.",
    })
    return tuple(scope)


# --------------------------------------------------------------------------- classification


def classify(target: str, base: Optional[str], head: str) -> Tuple[bool, List[str]]:
    if os.environ.get(HATCH) == "off":
        return True, [f"{HATCH}=off — {target} RUNS."]
    if target not in TARGETS:
        return True, [f"{target!r} is not in guard-scope's ROSTER — an unscoped target RUNS."]
    try:
        browser = _browser_scope()
        entry = next(e for e in ROSTER if e["target"] == target)
        scope = scope_for(entry)
        reference = base or "origin/main"
        start = browser.landing_base(reference, head)
        if start is None:
            return True, [f"no merge-base between {reference} and {head} — {target} RUNS."]
        paths = browser.changed_paths(start, head)
        if paths is None:
            return True, [f"`git diff {start[:12]} {head}` failed — {target} RUNS."]
        verdict = browser.classify_paths(
            paths, browser.git_reader(start, head), scope=scope,
            subject=f"what `make {target}` reads", noun=target)
        lines = [f"{len(paths)} changed path(s) from {start[:12]} to {head}:"] + list(
            verdict.lines)
        if not verdict.run:
            lines.append(f"  ({HATCH}=off runs it anyway.)")
        return verdict.run, lines
    except Exception as exc:  # noqa: BLE001 — a scoping bug must cost time, never coverage.
        return True, [f"guard-scope classification raised {exc!r} — {target} RUNS."]


# --------------------------------------------------------------------------------- selftest


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

    # ---- the roster and the wiring: every declared target has a subject, every subject
    # is a real file, and every Makefile recipe that calls this classifier is on the roster
    # and vice versa. This is the "both ways" reconciliation `make docs-audit`'s `guard
    # scope` row also runs over the real tree; here it runs over THIS tree so a broken
    # roster fails locally too, not only in the audit.
    # Self-testing guards (`revert-audit.py`, `suite-lock.py`) name no OTHER local file — the
    # guard and the test are the same file, already carried as the roster's `test` entry — so
    # "at least one subject" is asserted only where the test wraps a separate guard script.
    SELF_SUBJECT_TARGETS = {"revert-selftest", "suite-lock-selftest", "audit-self-test"}
    for entry in ROSTER:
        test_path = ROOT / entry["test"]
        check(f"{entry['target']}: test file exists", test_path.exists(), True)
        subjects = derive_subjects(test_path, func=entry.get("func"))
        if entry["target"] not in SELF_SUBJECT_TARGETS:
            check(f"{entry['target']}: at least one subject is derived", len(subjects) > 0, True)
        for subject in subjects:
            real = subject.endswith("/**") or (ROOT / subject).is_file()
            check(f"{entry['target']}: subject `{subject}` exists", real, True)

    makefile = (ROOT / "Makefile").read_text() if (ROOT / "Makefile").exists() else ""
    wired = set(re.findall(
        r"guard-scope\.py classify --target (\S+)", makefile))
    check("every roster target is wired into the Makefile", sorted(TARGETS - wired), [])
    check("every wired target is on the roster", sorted(wired - TARGETS), [])

    # ---- a drift IS caught: a subject added to a fixture's imports is picked up with no
    # edit to this file, proving the mapping is read fresh rather than cached anywhere.
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp) / "fixture_selftest.py"
        fixture.write_text("from store import photos\n")
        got = derive_subjects(fixture)
        check("a fresh import is derived with no edit to this file", got, ("store/photos.py",))
        fixture.write_text("from store import photos\nfrom cli import cmd_cards\n")
        got2 = derive_subjects(fixture)
        check("a second import added to the fixture is picked up on the next read",
              set(got2), {"store/photos.py", "cli/cmd_cards.py"})

    # ---- the sub-chain trap: `ROOT / "scripts"` alone must never surface as a subject,
    # or every target would re-arm on any `scripts/` change and scoping would do nothing.
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp) / "fixture_binop.py"
        fixture.write_text('X = ROOT / "scripts" / "guard-shell.py"\n')
        got3 = derive_subjects(fixture)
        check("only the full chain is kept, never the bare directory prefix",
              "scripts" in got3, False)

    # ---- fail-open, exercised for real against this repository's own git history.
    check("an unscoped target runs",
          classify("not-a-real-target", "origin/main", "HEAD")[0], True)
    check("HATCH=off runs a real target regardless", (lambda: (
        os.environ.__setitem__(HATCH, "off"),
        classify("reap-selftest", "origin/main", "HEAD")[0],
        os.environ.pop(HATCH, None),
    )[1])(), True)
    missing_head = "0" * 40
    check("no merge-base with a nonexistent head runs",
          classify("reap-selftest", "origin/main", missing_head)[0], True)

    # ---- the pure half, per target, against `classify_paths` directly — the same shape
    # `serve-scope.py`'s own selftest uses, so a target's derived scope is proved without
    # needing a real commit for every case.
    def verdict(target: str, paths: Sequence[str]) -> bool:
        entry = next(e for e in ROSTER if e["target"] == target)
        scope = scope_for(entry)
        return browser.classify_paths(
            paths, lambda side, path: "", scope=scope, subject="x", noun="y").run

    check("reap-selftest runs on its own subject",
          verdict("reap-selftest", ["scripts/reap.py"]), True)
    check("reap-selftest skips on an unrelated screen change",
          verdict("reap-selftest", ["app/src/Orders.tsx"]), False)
    check("claim-selftest runs on scripts/claim-ids.py",
          verdict("claim-selftest", ["scripts/claim-ids.py"]), True)
    check("cid-selftest runs on store/photos.py",
          verdict("cid-selftest", ["store/photos.py"]), True)
    check("cid-selftest skips on an unrelated screen change",
          verdict("cid-selftest", ["app/src/Orders.tsx"]), False)
    check("githooks-selftest runs on a hook this reader never sees as a literal path",
          verdict("githooks-selftest", ["scripts/githooks/pre-push"]), True)
    check("an empty diff runs every target",
          verdict("submission-selftest", []), True)
    check("every target runs on the test file itself",
          all(verdict(e["target"], [e["test"]]) for e in ROSTER), True)
    check("every target runs on this classifier changing",
          all(verdict(e["target"], ["scripts/guard-scope.py"]) for e in ROSTER), True)

    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


# -------------------------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("classify")
    run.add_argument("--target", required=True)
    run.add_argument("--base")
    run.add_argument("--head", default="HEAD")
    lister = sub.add_parser("list")
    lister.add_argument("--target")
    sub.add_parser("selftest")
    args = parser.parse_args()

    if args.command == "selftest":
        return selftest()
    if args.command == "list":
        targets = [args.target] if args.target else sorted(TARGETS)
        for target in targets:
            entry = next((e for e in ROSTER if e["target"] == target), None)
            if entry is None:
                print(f"{target}: not on the roster")
                continue
            print(f"{target}  (test: {entry['test']})")
            for item in scope_for(entry):
                mark = "  (beyond derived)" if "beyond_carry" in item else ""
                print(f"    {item['path']}{mark}\n        {item['why']}")
        return 0
    if args.command == "classify":
        should_run, lines = classify(args.target, args.base, args.head)
        for line in lines:
            print(line)
        return 0 if should_run else 3
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
