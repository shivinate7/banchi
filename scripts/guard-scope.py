#!/usr/bin/env python3
"""DOES THIS CHANGE REACH WHAT ONE OF THE ROSTER'S GUARD SELF-TESTS PROVES?

Measured on this Mac, 2026-09-20: `make check` is 163.85s. Fifteen guard self-tests —
`reap-selftest`, `guard-shell-selftest`, `sync-selftest`, `audit-self-test`,
`janitor-selftest`, `githooks-selftest`, `silent-write-selftest`,
`verdict-selftest`, `revert-selftest`, `suite-lock-selftest`, `submission-selftest`,
`screen-freshness-selftest` and `cid-selftest` — cost 76.6s of that, 47%, against a
ten-test product harness of 21.75s. A guard self-test proves a MECHANISM. It cannot catch a
product defect, and it has something new to say only when the guard it proves, or this
classifier, or the recipe that runs it, changes. D247
is the argument and the measurement.

THE OWNER RULED A SECOND PATH-GATED TARGET IN, 2026-09-20, on that measurement.
`scripts/serve-scope.py`'s own header says a request for a second entry is "evidence the
policy is spreading and needs the owner's word again" — that word was given, and this file
is what was built on it. Many entries, not one: unlike `serve-selftest`'s single
unbreakable-by-any-`app/`-change case, most of `make check`'s guard self-tests each prove
one guard script, so one classifier serving the roster below is the shape that avoids a
near-identical copy of `serve-scope.py` per entry.

THE SUBJECT LIST IS DERIVED FROM EACH SELF-TEST'S OWN SOURCE, NEVER TYPED BESIDE IT.
`ROSTER` below names which targets are gated — that selection is a product decision,
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
out loud. Only an explicit skip skips, and `BANCHI_GUARD_SCOPE=all` runs every target
anyway. That adds checks, so it is not a hatch.

    scripts/guard-scope.py classify --target <name> [--base REV] [--head REV]
        Prints the reasoning and exits 0 to RUN, 3 to SKIP. Each roster entry's own
        Makefile recipe calls this with its own name.
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
import types
from pathlib import Path
from typing import List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
HATCH = "BANCHI_GUARD_SCOPE"

# CLAUDE.md's own list: "the Python packages (server/ store/ pipeline/ identify/ geometry/
# codes/ cli/)". A local-package import is resolved against this list, never a guess.
LOCAL_PACKAGES = ("store", "cli", "pipeline", "identify", "geometry", "codes", "server")

# THE ROSTER — the owner's list, grown twice: fifteen entries on 2026-09-20, a sixteenth
# (`pricearchive-selftest`) on 2026-09-23, and six more the same day once that sixteenth's
# own wiring showed each of their "not wired — pricearchive-selftest.py's own precedent"
# notes had gone stale too (D247's own text: "This entry is a placement change, not a
# pruning" — the same word covers every later addition on the same ground). Which targets
# are gated is declared here, on `serve-scope.py`'s own precedent (it declares its one
# target the same way). What each one READS is never declared beside it; see
# `derive_subjects()`. Count it with `len(ROSTER)`, never by re-typing a number in prose.
#
# `guard-scope-selftest` ITSELF IS NOT ON THIS ROSTER. A gate cannot skip its own proof: if
# `guard-scope-selftest` gated itself, a branch that broke this file's own gating logic could
# skip the one test that would catch it, on the strength of that same broken logic saying
# skip.
ROSTER = (
    {"target": "reap-selftest", "test": "scripts/reap-selftest.sh"},
    {"target": "guard-shell-selftest", "test": "scripts/guard-shell-selftest.sh"},
    {"target": "sync-selftest", "test": "scripts/sync-selftest.py"},
    {"target": "audit-self-test", "test": "scripts/docs-audit.py", "package": "scripts/docs_audit"},
    {"target": "janitor-selftest", "test": "scripts/janitor-selftest.sh"},
    {"target": "githooks-selftest", "test": "scripts/githooks-selftest.sh"},
    {"target": "silent-write-selftest", "test": "scripts/silent-write-selftest.sh"},
    {"target": "verdict-selftest", "test": "scripts/verdict-selftest.py"},
    {"target": "revert-selftest", "test": "scripts/revert-audit.py"},
    {"target": "suite-lock-selftest", "test": "scripts/suite-lock.py"},
    {"target": "submission-selftest", "test": "scripts/submission-selftest.py"},
    {"target": "screen-freshness-selftest", "test": "scripts/screen-freshness.mjs"},
    {"target": "cid-selftest", "test": "scripts/cid-selftest.py"},
    {"target": "pricearchive-selftest", "test": "scripts/pricearchive-selftest.py"},
    {"target": "archive-review-selftest", "test": "scripts/archive-review-selftest.py"},
    {"target": "holdings-selftest", "test": "scripts/holdings-selftest.py"},
    {"target": "identity-checks-selftest", "test": "scripts/identity-checks-selftest.py"},
    {"target": "price-postings-selftest", "test": "scripts/price-postings-selftest.py"},
    {"target": "product-history-selftest", "test": "scripts/product-history-selftest.py"},
    {"target": "sku-number-contradictions-selftest",
     "test": "scripts/sku-number-contradictions-selftest.py"},
    {"target": "match-selftest", "test": "scripts/match-selftest.py"},
    {"target": "browser-scope-selftest", "test": "scripts/browser-scope.py"},
    {"target": "port-slots-selftest", "test": "scripts/port-slots.py"},
    # THE PRODUCT HARNESS, on the owner's word (D247, amended). Not a self-test, so its subjects
    # are not read from one file: `harness_subjects()` reads every module under `harness/`.
    {"target": "harness", "test": "harness/run.py", "derive": "harness"},
)

TARGETS = {entry["target"] for entry in ROSTER}

# The exit code that means SKIP. Every other non-zero exit is a crash, and a crash must RUN the
# test. The Makefile's `SKIP_CODE` is checked against this, so the two cannot drift.
SKIP_EXIT = 3


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


def _dotted_to_subject(dotted: str) -> Optional[str]:
    """`"store.db"` -> `"store/db.py"` when the top-level package is local, else `None`.

    A bare package name with no submodule (`"store"` alone) names no single file — that
    shape is `visit_ImportFrom`'s own `from store import x` branch to resolve, which reads
    `node.names` for the part this function is never given.
    """
    parts = dotted.split(".")
    if len(parts) > 1 and parts[0] in LOCAL_PACKAGES:
        return "/".join(parts) + ".py"
    return None


class _PathCollector(ast.NodeVisitor):
    """Every local-package import, every `Path`-chain and every dynamic `import_module`
    string, wherever any of them sits in a module.

    `ast.walk` would also re-visit every inner `BinOp` of a chain as if it were its own
    top-level one (`ROOT / "scripts"` inside `ROOT / "scripts" / "x.py"`), which would add
    the bare directory `scripts` as a "subject" and defeat the whole point — a change
    anywhere under `scripts/` would then re-arm every target. Overriding `visit_BinOp` and
    skipping `generic_visit` once a chain resolves keeps only the outermost, full chain.

    `visit_Call` reads `importlib.import_module("store.db")` (or a bare `import_module(...)`
    reached through `from importlib import import_module`) the same way `visit_ImportFrom`
    reads a static import — the argument is a STRING LITERAL, fully visible to the AST, not
    the runtime-built string D247's own "WHAT THIS DOES NOT COVER" section describes (a
    name assembled from an f-string, a variable, or an environment lookup stays invisible,
    on purpose — this reads only what the source spells out literally). This is why
    `scripts/price-postings-selftest.py` needs no decoy import beside its real, dynamic
    `importlib.import_module("store.db")` / `("store.session")` calls: this visitor now
    resolves those two calls' own literal arguments directly.
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
                subject = _dotted_to_subject(node.module)
                if subject:
                    self.hits.add(subject)
                else:
                    for alias in node.names:
                        self.hits.add(f"{parts[0]}/{alias.name}.py")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        is_import_module = (
            (isinstance(node.func, ast.Attribute) and node.func.attr == "import_module")
            or (isinstance(node.func, ast.Name) and node.func.id == "import_module")
        )
        if is_import_module and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                subject = _dotted_to_subject(first.value)
                if subject:
                    self.hits.add(subject)
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
    whole module, for a test that shares its file with code whose constants it does not read.
    A roster entry's `package` is the other case, and `subjects_for` handles it: the rows of
    `audit-self-test` live in a package, and only the package's `selftest*.py` modules say
    what `--self-test` reads. `revert-audit.py` and `suite-lock.py` need no narrowing: each is
    a normal-sized guard that tests itself, whole.

    Filtered to paths that exist as real files, so a renamed subject falls out on its own
    instead of pointing at nothing, and a false hit (a decorative string that happens to look
    like a path) never survives. A hit under `scripts/githooks/` widens to the whole
    directory: `githooks-selftest.sh` names one of its three hooks as a literal path and the
    rest only in prose ("its pre-push sibling") — a reader that stopped at the one named
    would silently narrow what the gate can see, which is the exact failure this
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

    # A subject that imports a sibling script (`silent-write-guard.py` -> `shell_parse.py`)
    # reads it too, so follow those imports to a fixed point. A sibling PACKAGE (a directory with
    # an `__init__.py`, such as `scripts/docs_audit/`) counts whole as `<dir>/**`, and each of its
    # modules is walked for its own imports. Known gap: importlib-by-path loads and
    # `from . import` inside `scripts/` are not followed (inside LOCAL_PACKAGES they are:
    # see `_package_imports`).
    queue = [h for h in resolved if h.startswith("scripts/") and h.endswith(".py")]
    # The test itself is walked too: a self-test that is a thin script over a package imports it.
    try:
        own = str(test_path.relative_to(ROOT))
    except ValueError:
        own = ""
    if own.startswith("scripts/") and own.endswith(".py") and own not in queue:
        queue.append(own)
    while queue:
        try:
            tree = ast.parse((ROOT / queue.pop()).read_text())
        except (OSError, SyntaxError):
            # unreadable: its imports are unknown, so every script counts as read (fail safe)
            resolved |= {f"scripts/{q.name}" for q in (ROOT / "scripts").glob("*.py")}
            break
        for n in ast.walk(tree):
            mods = ([a.name for a in n.names] if isinstance(n, ast.Import)
                    else [n.module] if isinstance(n, ast.ImportFrom) and n.module else [])
            for m in mods:
                pkg = f"scripts/{m.split('.')[0]}"
                if (ROOT / pkg / "__init__.py").is_file():
                    if pkg + "/**" not in resolved:
                        resolved.add(pkg + "/**")
                        queue.extend(f"{pkg}/{q.name}" for q in (ROOT / pkg).glob("*.py"))
                    continue
                sib = pkg + ".py"
                if sib not in resolved and (ROOT / sib).is_file():
                    resolved.add(sib)
                    queue.append(sib)

    if any(h.startswith("scripts/githooks/") for h in resolved):
        resolved = {h for h in resolved if not h.startswith("scripts/githooks/")}
        resolved.add("scripts/githooks/**")

    try:
        rel_test = str(test_path.relative_to(ROOT))
    except ValueError:
        rel_test = ""
    resolved.discard(rel_test)
    return tuple(sorted(resolved))


def _package_imports(rel: str) -> Set[str]:
    """Repo files of LOCAL_PACKAGES that the module `rel` imports, absolute or relative.

    Unparseable: every file of the packages, fail safe. Known gap: a module that only a
    subprocess runs (`-m pkg.mod`, or a script path in argv) is not followed, and a literal
    `importlib.import_module("...")` call inside a package module is not followed either
    (the test-level `_PathCollector` does follow them).
    """
    try:
        tree = ast.parse((ROOT / rel).read_text())
    except (OSError, SyntaxError):
        return {str(q.relative_to(ROOT)) for p in LOCAL_PACKAGES for q in (ROOT / p).rglob("*.py")}
    found: Set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            pairs = [(a.name, [""]) for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            base = n.module or ""
            if n.level:  # `from .x import y`: resolve against this file's package
                up = Path(rel).parts[:-1]
                up = up[:len(up) - (n.level - 1)]
                base = ".".join(up + ((n.module,) if n.module else ()))
            pairs = [(base, [a.name for a in n.names])]
        else:
            continue
        for mod, names in pairs:
            if mod.split(".")[0] not in LOCAL_PACKAGES:
                continue
            stem = mod.replace(".", "/")
            parts = stem.split("/")  # Python runs every parent package's `__init__` first
            for i in range(1, len(parts)):
                if (ROOT / "/".join(parts[:i]) / "__init__.py").is_file():
                    found.add("/".join(parts[:i]) + "/__init__.py")
            for cand in [stem] + [f"{stem}/{a}" for a in names]:
                for f in (f"{cand}.py", f"{cand}/__init__.py"):
                    if (ROOT / f).is_file():
                        found.add(f)
    return found


def _follow_package_imports(resolved: Set[str], start: Sequence[str]) -> Set[str]:
    """`resolved` plus every package module reached transitively from `start` and from its own
    .py members: a planted raise in `store/rows.py` reaches a test that only imports `store.db`."""
    out = set(resolved)
    queue = [f for f in [*start, *resolved] if f.endswith(".py")]
    while queue:
        for f in _package_imports(queue.pop()) - out:
            out.add(f)
            queue.append(f)
    return out


def subjects_for(entry: dict) -> Tuple[str, ...]:
    """Every local file one roster entry's test reads.

    The test's own source, narrowed by `func` when the entry names one. When the entry names a
    `package`, also what every `selftest*.py` module in it reads: those hold the cases. The
    package's row modules are not read through their own path chains, which are row constants.
    The package itself is a subject through the import walk in `derive_subjects`.
    """
    if entry.get("derive") == "harness":
        return harness_subjects()
    subjects = set(derive_subjects(ROOT / entry["test"], func=entry.get("func")))
    package = entry.get("package")
    if package:
        for part in sorted((ROOT / package).glob("selftest*.py")):
            subjects.update(derive_subjects(part))
        subjects = {s for s in subjects
                    if not s.startswith(package + "/") or s.endswith("/**")}
    return tuple(sorted(_follow_package_imports(subjects, [entry["test"]])))


# WHAT A GUARD'S TEST READS OF A SUBJECT, WHEN IT IS LESS THAN THE WHOLE FILE (D247, amended).
# `derive_subjects` sees a path and cannot see how it is used, so these narrow a derived subject
# by hand: `within` is `exists` (only `is_file` reads it) or `header` (only the module docstring
# and top-level UPPERCASE names are read); `None` drops a subject that is a command string the
# test never runs. The selftest fails when a key here is no longer a derived subject, so a stale
# entry cannot hide.
NARROW = {
    "audit-self-test": {
        "docs/map.py": ("header", "`_consumer_block` reads its docstring and `_map_sections` its "
                                  "UPPERCASE names; nothing else of it."),
    },
    "browser-scope-selftest": {
        "app/src/kit.css": ("exists", "read only through `is_file`."),
        "app/src/kit/index.tsx": ("exists", "read only through `is_file`."),
    },
    "silent-write-selftest": {
        "scripts/docs-audit.py": ("exists", "a command string the guard parses and never runs."),
        "scripts/docs_audit/**": (None, "reached only through that command string's import."),
    },
}

# SUBJECTS THE DERIVER CANNOT SEE: `browser-scope.py`'s selftest reads these through
# `import_closure` and `classify_specs` over the real tree, never as a `ROOT / ...` chain.
EXTRA_SUBJECTS = {
    "browser-scope-selftest": (
        ("app/src/App.tsx", "its `ROUTES` table is read by `route_views`."),
        ("app/src/Inventory.tsx", "the selftest asserts the specs it reaches."),
        ("app/src/Home.tsx", "the selftest asserts the specs it reaches."),
        ("app/tests/**", "the specs and their helpers are read for route hashes and sweeps."),
    ),
    "port-slots-selftest": (
        ("scripts/ports-machine-selftest.py", "the recipe runs this second test beside it."),
        ("scripts/suite-lock.py", "that second test loads it to check the lock's default dir."),
    ),
}

# Targets whose test executes its subjects, so a docstring or comment edit cannot move a verdict.
# The predicate leaves out what the audit reads as TEXT: `harness/` docstrings carry claims it checks.
def ast_skip_for(target: str):
    """The `ast_skip` predicate for a target, or None. Never for a file the test names (it may
    patch it by text: `sigil-check.py` by the code-invariants self-test), and never `harness/`."""
    if target != "audit-self-test":
        return None
    sources = [ROOT / "scripts" / "docs-audit.py", *sorted((ROOT / "scripts" / "docs_audit").glob("*.py"))]
    named = _browser_scope().skippable_on_ast(sources)
    return lambda path: not path.startswith("harness/") and named(path)


# A directory the harness reaches but never reads in part: a change under it cannot move a verdict.
HARNESS_UNREAD = {"demo-assets": ("mirror",)}


def harness_subjects() -> Tuple[str, ...]:
    """What `harness/run.py` reads, derived from every module under `harness/`.

    From each module: a local package or top-level module it imports; a top-level name a
    `ROOT / "x"` chain or a bare string constant names (`"banchi"`, `"./banchi"`: a
    subprocess target or an opened data path); and the TS import closure of every `app/src/*.ts`
    a chain names (`standing.ts`, `storeHistory.ts`). A `scripts/*.py` file so named is scanned
    the same way, to a fixed point, because it reads on the harness's behalf (`demo-seed.py`
    reads `demo-assets/`). Raises on an unreadable module: `classify` turns that into RUN.
    """
    browser = _browser_scope()
    tops: Set[str] = set()
    ts_roots: Set[str] = set()
    queue = sorted((ROOT / "harness").rglob("*.py"))
    seen: Set[Path] = set()
    while queue:
        module = queue.pop()
        if module in seen:
            continue
        seen.add(module)
        tree = ast.parse(module.read_text())
        collector = _PathCollector()
        collector.visit(tree)
        hits = set(collector.hits)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                tops |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                tops.add(node.module.split(".")[0])
            elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
                  and node.value and len(node.value) < 200 and not re.search(r"\s", node.value)):
                hits.add(node.value[2:] if node.value.startswith("./") else node.value)
        for hit in hits:
            tops.add(hit.split("/")[0])
            if hit.startswith("app/src/") and hit.endswith((".ts", ".tsx")):
                ts_roots.add(hit)
            if hit.startswith("scripts/") and hit.endswith(".py") and (ROOT / hit).is_file():
                queue.append(ROOT / hit)
    subjects: Set[str] = set()
    real = set(os.listdir(ROOT))  # exact names: a case-folding disk must not make "Store" a hit
    for top in sorted(t for t in tops if t in real or f"{t}.py" in real) :
        if top == "app" or top.startswith("."):
            continue
        if (ROOT / top).is_dir():
            unread = HARNESS_UNREAD.get(top, ())
            if unread:
                for child in sorted((ROOT / top).iterdir()):
                    if child.name not in unread:
                        subjects.add(f"{top}/{child.name}" + ("/**" if child.is_dir() else ""))
            else:
                subjects.add(f"{top}/**")
        elif (ROOT / f"{top}.py").is_file():
            subjects.add(f"{top}.py")
        elif (ROOT / top).is_file():
            subjects.add(top)
    for root in ts_roots:
        if (ROOT / root).is_file():
            subjects |= browser.import_closure([root])
    # What no harness source spells: the vendored catalog is data the packages open, and
    # `requirements.txt`, the lockfile and the tsconfigs pin what runs and how `standing.ts` bundles.
    subjects |= {"vendor/**", "requirements.txt", "app/package-lock.json"}
    subjects |= {f"app/{q.name}" for q in (ROOT / "app").glob("tsconfig*.json")}
    return tuple(sorted(subjects))


def scope_for(entry: dict) -> Tuple[dict, ...]:
    """The full `classify_paths` scope for one roster entry: subjects, the test, the gate."""
    rel_test = entry["test"]
    subjects = subjects_for(entry)
    scope: List[dict] = [{"path": rel_test, "why": "the test itself."}]
    narrow = NARROW.get(entry["target"], {})
    for subject in subjects:
        within, why = narrow.get(subject, (False, ""))
        if within is None:
            continue
        item = {"path": subject, "why": f"read by `{rel_test}`, derived from its source."}
        if within:
            item.update(within=within, why=f"{item['why']} Narrowed: {why}")
        scope.append(item)
    for path, why in EXTRA_SUBJECTS.get(entry["target"], ()):
        scope.append({"path": path, "why": f"read by `{rel_test}`: {why}"})
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


DIRTY_LINE = "working tree has uncommitted changes; this verdict covers commits only"


def classify(target: str, base: Optional[str], head: str) -> Tuple[bool, List[str]]:
    if os.environ.get(HATCH) == "all":
        return True, [f"{HATCH}=all — {target} RUNS."]
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
            subject=f"what `make {target}` reads", noun=target,
            ast_skip=ast_skip_for(target))
        lines = [f"{len(paths)} changed path(s) from {start[:12]} to {head}:"] + list(
            verdict.lines)
        if not verdict.run:
            if browser.git("status", "--porcelain", "--untracked-files=no"):
                lines.append(DIRTY_LINE)
            lines.append(f"  ({HATCH}=all runs it anyway.)")
        return verdict.run, lines
    except Exception as exc:  # noqa: BLE001 — a scoping bug must cost time, never coverage.
        return True, [f"guard-scope classification raised {exc!r} — {target} RUNS."]


# --------------------------------------------------------------------------------- selftest


def selftest() -> int:
    # HERMETIC: a hatch inherited from the environment (CI sets it on every push to main)
    # would make this self-test's own SKIP cases run. Its cases set the hatch themselves.
    os.environ.pop(HATCH, None)
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
        subjects = subjects_for(entry)
        if entry["target"] not in SELF_SUBJECT_TARGETS:
            check(f"{entry['target']}: at least one subject is derived", len(subjects) > 0, True)
        for subject in subjects:
            real = subject.endswith("/**") or (ROOT / subject).is_file()
            check(f"{entry['target']}: subject `{subject}` exists", real, True)

    check("silent-write-selftest reaches shell_parse.py through its guard's import",
          "scripts/shell_parse.py" in derive_subjects(ROOT / "scripts/silent-write-selftest.sh"),
          True)
    for target in ("silent-write-selftest", "audit-self-test"):
        entry = next(e for e in ROSTER if e["target"] == target)
        check(f"{target} reaches the docs_audit package through docs-audit.py's import",
              "scripts/docs_audit/**" in subjects_for(entry), True)

    makefile = (ROOT / "Makefile").read_text() if (ROOT / "Makefile").exists() else ""
    wired = set(re.findall(
        r"guard-scope\.py classify --target (\S+)", makefile))
    check("every roster target is wired into the Makefile", sorted(TARGETS - wired), [])
    check("every wired target is on the roster", sorted(wired - TARGETS), [])

    # ---- the recipes skip on the classifier's skip code and nothing else. A recipe that reads
    # the exit as a boolean turns a crashed classifier into a SKIP, which is a fail-closed
    # gate wearing a fail-open comment.
    calls = re.findall(r"^\t@?(?:if )?python3 scripts/(?:guard|serve)-scope\.py classify",
                       makefile, re.M)
    shaped = re.findall(
        r"^\t@python3 scripts/(?:guard|serve)-scope\.py classify[^\n]*; rc=\$\$\?; \\$\n"
        r"\tif \[ \$\$rc -ne \$\(SKIP_CODE\) \]; then \\$",
        makefile, re.M)
    check("every path-gated recipe skips only on SKIP_CODE", (len(shaped), len(calls)),
          (len(calls), len(calls)))
    check("the Makefile's SKIP_CODE is the classifier's own skip exit",
          f"SKIP_CODE := {SKIP_EXIT}\n" in makefile, True)

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

    # ---- MUTATION ARM: `importlib.import_module("<literal>")` resolution is real, proved
    # by removing it. `scripts/price-postings-selftest.py` needs this exactly — its real
    # subjects (`store/postings.py`, `store/session.py`) are reached only by loading
    # `store.session` by NAME, never by a static `from store import ...`. A `.bak`-shaped
    # copy of THIS file has `visit_Call` deleted by one literal string replacement (the
    # same technique `price-postings-selftest.py`'s own `_mutate_to_upsert` uses on
    # `store/db.py`) and is imported under a throwaway module name, its `ROOT` repointed at
    # the real repo root so the mutant's own file-existence filter still resolves; against a
    # fixture calling `importlib.import_module("store.db")`, the mutant's `derive_subjects`
    # MUST miss the subject the real one catches, or this resolution is not being tested at
    # all.
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp) / "fixture_import_module.py"
        fixture.write_text(
            'import importlib\n'
            'db_module = importlib.import_module("store.db")\n'
        )
        got4 = derive_subjects(fixture)
        check('importlib.import_module("store.db") resolves to store/db.py',
              "store/db.py" in got4, True)

        own_src = Path(__file__).read_text()
        anchor = (
            '    def visit_Call(self, node: ast.Call) -> None:\n'
            '        is_import_module = (\n'
            '            (isinstance(node.func, ast.Attribute) and node.func.attr == '
            '"import_module")\n'
            '            or (isinstance(node.func, ast.Name) and node.func.id == '
            '"import_module")\n'
            '        )\n'
            '        if is_import_module and node.args:\n'
            '            first = node.args[0]\n'
            '            if isinstance(first, ast.Constant) and isinstance(first.value, '
            'str):\n'
            '                subject = _dotted_to_subject(first.value)\n'
            '                if subject:\n'
            '                    self.hits.add(subject)\n'
            '        self.generic_visit(node)\n'
        )
        if own_src.count(anchor) != 1:
            check(
                "MUTATION ANCHOR NOT FOUND EXACTLY ONCE — visit_Call moved, this arm proves "
                "nothing until the anchor is updated to match it",
                False, True,
            )
        else:
            mutant_path = Path(tmp) / "guard_scope_mutant.py"
            mutant_path.write_text(own_src.replace(anchor, ""))
            spec = importlib.util.spec_from_file_location(
                "_guard_scope_mutant", mutant_path)
            mutant = importlib.util.module_from_spec(spec)
            sys.modules["_guard_scope_mutant"] = mutant
            try:
                spec.loader.exec_module(mutant)
                mutant.ROOT = ROOT  # the mutant's own `__file__` sits under `tmp`, not here
                got5 = mutant.derive_subjects(fixture)
                check(
                    "MUTATION: without visit_Call, the same import_module call is "
                    "invisible — store/db.py must NOT be found",
                    "store/db.py" in got5, False,
                )
            finally:
                del sys.modules["_guard_scope_mutant"]

    # ---- fail-open, exercised for real against this repository's own git history.
    check("an unscoped target runs",
          classify("not-a-real-target", "origin/main", "HEAD")[0], True)
    check("HATCH=all runs a real target regardless", (lambda: (
        os.environ.__setitem__(HATCH, "all"),
        classify("reap-selftest", "origin/main", "HEAD")[0],
        os.environ.pop(HATCH, None),
    )[1])(), True)
    missing_head = "0" * 40
    check("no merge-base with a nonexistent head runs",
          classify("reap-selftest", "origin/main", missing_head)[0], True)

    # ---- each fail-open arm, forced through a stub matcher. The real VCS never fails on
    # demand, so without a stub a flipped arm (skip where it must RUN) stays green. The
    # positive control proves the stub can make the gate SKIP at all.
    def with_stub(full=False, target="reap-selftest", **overrides):
        stub = types.SimpleNamespace(
            landing_base=lambda reference, head: "a" * 40,
            changed_paths=lambda start, head: ["app/src/Orders.tsx"],
            git_reader=lambda start, head: (lambda side, path: ""),
            git=lambda *args: "",
            classify_paths=browser.classify_paths, import_closure=browser.import_closure)
        for name, value in overrides.items():
            setattr(stub, name, value)
        real = globals()["_browser_scope"]
        globals()["_browser_scope"] = lambda: stub
        try:
            got = classify(target, "origin/main", "HEAD")
            return got if full else got[0]
        finally:
            globals()["_browser_scope"] = real

    def boom(*args):
        raise RuntimeError("forced")

    check("stub control: an unrelated change SKIPS", with_stub(), False)
    check("no merge-base RUNS", with_stub(landing_base=lambda r, h: None), True)
    check("a failed diff RUNS", with_stub(changed_paths=lambda s, h: None), True)
    check("a classification that raises RUNS", with_stub(changed_paths=boom), True)
    dirty = lambda *a: " M x\n"  # noqa: E731
    check("a dirty tree on a SKIP prints the dirty-tree line",
          DIRTY_LINE in with_stub(full=True, git=dirty)[1], True)
    run_dirty = with_stub(full=True, git=dirty, changed_paths=lambda s, h: ["scripts/reap.py"])
    check("a dirty tree on a RUN prints no dirty-tree line",
          (run_dirty[0], DIRTY_LINE in run_dirty[1]), (True, False))

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
    check("cid-selftest runs on store/photos.py",
          verdict("cid-selftest", ["store/photos.py"]), True)
    check("cid-selftest skips on an unrelated screen change",
          verdict("cid-selftest", ["app/src/Orders.tsx"]), False)
    check("cid-selftest runs on store/rows.py, which it reaches only through imports of imports",
          verdict("cid-selftest", ["store/rows.py"]), True)
    check("identity-checks-selftest runs on pipeline/__init__.py, a parent of what it imports",
          verdict("identity-checks-selftest", ["pipeline/__init__.py"]), True)
    check("reap-selftest still skips on a leaf module it never imports",
          verdict("reap-selftest", ["pipeline/livecheck.py"]), False)
    check("githooks-selftest runs on a hook this reader never sees as a literal path",
          verdict("githooks-selftest", ["scripts/githooks/pre-push"]), True)
    check("an empty diff runs every target",
          verdict("submission-selftest", []), True)
    check("every target runs on the test file itself",
          all(verdict(e["target"], [e["test"]]) for e in ROSTER), True)
    check("every target runs on this classifier changing",
          all(verdict(e["target"], ["scripts/guard-scope.py"]) for e in ROSTER), True)

    # ---- THE HARNESS GATE (D247, amended): its scope is read out of `harness/`, and every
    # fail-open arm that holds for a self-test holds for it.
    harness_entry = next(e for e in ROSTER if e["target"] == "harness")
    harness_subj = set(subjects_for(harness_entry))
    for wanted in ("pipeline/**", "store/**", "fixtures/**", "scripts/**", "vendor/**",
                   "app/src/standing.ts", "app/src/storeHistory.ts"):
        check(f"the harness reads `{wanted}`", wanted in harness_subj, True)
    check("a change to pipeline/ runs the harness", verdict("harness", ["pipeline/join.py"]), True)
    check("a docs-only change skips the harness",
          verdict("harness", ["docs/DESIGN.md", "README.md"]), False)
    check("a screen no harness test reads skips the harness",
          verdict("harness", ["app/src/Orders.tsx"]), False)
    check("a TS file in the standing.ts closure runs the harness",
          verdict("harness", ["app/src/standing.ts"]), True)
    check("an empty diff runs the harness", verdict("harness", []), True)
    check("an unreadable diff runs the harness",
          with_stub(target="harness", changed_paths=lambda s, h: None), True)
    check("no merge-base runs the harness",
          with_stub(target="harness", landing_base=lambda r, h: None), True)
    check("a harness classification that raises runs the harness",
          with_stub(target="harness", changed_paths=boom), True)
    check("stub control: an unrelated change skips the harness",
          with_stub(target="harness"), False)

    # ---- THE NARROWINGS: a key that is no longer a derived subject is a stale entry.
    for target, table in NARROW.items():
        entry = next(e for e in ROSTER if e["target"] == target)
        raw = set(subjects_for(entry))
        check(f"{target}: every NARROW key is still a derived subject",
              sorted(set(table) - raw), [])
    check("silent-write-selftest skips a docs_audit change",
          verdict("silent-write-selftest", ["scripts/docs_audit/rows.py"]), False)
    check("silent-write-selftest skips a docs-audit.py content change",
          verdict("silent-write-selftest", ["scripts/docs-audit.py"]), False)
    check("browser-scope-selftest skips a kit.css content change",
          verdict("browser-scope-selftest", ["app/src/kit.css"]), False)
    for path in ("app/src/App.tsx", "app/src/Inventory.tsx", "app/src/Home.tsx",
                 "app/tests/home.spec.ts"):
        check(f"browser-scope-selftest runs on {path}",
              verdict("browser-scope-selftest", [path]), True)

    # ---- THE COMMENT-ONLY ARM, over a real diff shape: a docstring edit in a subject.
    audit_scope = scope_for(next(e for e in ROSTER if e["target"] == "audit-self-test"))

    def comment_verdict(old: str, new: str) -> bool:
        return browser.classify_paths(
            ["cli/cmd_prices.py"], lambda side, path: old if side == "base" else new,
            scope=audit_scope, subject="x", noun="y", ast_skip=ast_skip_for("audit-self-test")).run

    check("audit-self-test skips a docstring-only edit of a subject",
          comment_verdict('"""a."""\nx = 1\n', '"""b."""\nx = 1  # c\n'), False)
    check("audit-self-test runs on a code edit of a subject",
          comment_verdict('"""a."""\nx = 1\n', '"""a."""\nx = 2\n'), True)
    check("audit-self-test runs when a subject no longer parses",
          comment_verdict('"""a."""\nx = 1\n', "x = (\n"), True)
    check("the harness gate never skips on comments (no ast_skip for it)",
          ast_skip_for("harness"), None)
    check("audit-self-test runs on a quote swap in a file its self-tests name",
          browser.classify_paths(
              ["scripts/sigil-check.py"],
              lambda side, path: "x = 'a'\n" if side == "base" else 'x = "a"\n',
              scope=(*audit_scope, {"path": "scripts/sigil-check.py", "why": "x"}),
              subject="x", noun="y", ast_skip=ast_skip_for("audit-self-test")).run, True)

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
        return 0 if should_run else SKIP_EXIT
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
