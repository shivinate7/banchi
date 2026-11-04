#!/usr/bin/env python3
"""WHICH TEST SUITES REACH ONE PRODUCT FILE?

    scripts/tests-for.py <path> [--root DIR]

Prints the repo-relative suites that load `<path>`, one per line, sorted:
`harness/tests/tN_*.py` (a module with a top-level `run`), `harness/tests/t7/<group>.py` (a
module with a top-level `CHECKS`) and `app/tests/unit/*.unit.ts`. A file no suite reaches prints
nothing and exits 0. Only a bad argument exits nonzero. When unsure it selects more: an
unparseable module reaches every file of the packages, never none.

`--root` names the checkout to read; without it the selector reads the current directory, which the
consumer sets to a checkout root. It never reads the checkout its own file lives in. The two scope
scripts it loads always come from beside this file, so a tree with no `scripts/` works.

A suite REACHES a file when it loads it by an import (at any depth), a literal path (a `ROOT / "a" / "b"`
chain, a string such as `scripts/x.py` or `./banchi`), a literal `importlib.import_module` name, a
`python3 -c "from pkg import m"` snippet, or, for a unit test, a text read (a literal path resolved
against the test's folder, the repo root or a folder the test names, `new URL(...)`, a `readdirSync` of
a folder, narrowed by an `endsWith('.ext')` it finds). A text read is a leaf: it reads the file, not
what the file imports. A script it runs is followed: Python by its imports, `.mjs` by its relative imports.

THE REACH RULES (each is a case of `scripts/tests-for-selftest.py`):
- Every Python suite inherits the import-time closure of `harness/tests/home.py`, which the runner imports for
  every suite, and the `__init__.py` of each folder above it.
- Every T7 group inherits the import-time closure of `harness/tests/t7/common.py` (the hermetic setup) and of
  `harness/tests/t7_store_and_seams.py` (the module every group run loads), whether it imports them or not.
- What a group loads only inside a check body reaches that group, and the aggregator that runs it, alone.
- A `tN_*.py` module with no top-level `run` is no suite: its checks run inside the aggregator.

THE HOMES IT REUSES, never copies: `scripts/guard-scope.py` for the Python scan (`_PathCollector`,
`_tree_package_imports` read at any depth or at import time, `derive_subjects` for a script a suite runs) and
`scripts/browser-scope.py` for the TypeScript scan (`import_closure`; strings and comments of a
test are read in one pass here). Both read the module global `ROOT`, which this sets to `--root`.

KNOWN GAPS, each a miss that narrows the answer: a file a suite reaches only through a name built at run time
(an f-string, a variable, an environment lookup); a directory a Python suite reads with `glob`; a file deleted
by the change (nothing resolves it). The consumer runs the full set on a file this prints nothing for only when
it chooses to: an empty answer is "no suite reaches it", not "it is safe".

COST: reads and parses each Python file the suites reach once (about 5 seconds on this repo); starts no process.
Stdlib only.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import os
import posixpath
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

SCRIPTS = Path(__file__).resolve().parent

HOME = "harness/tests/home.py"
HERMETIC = "harness/tests/t7/common.py"
AGGREGATOR = "harness/tests/t7_store_and_seams.py"
UNIT_DIR = "app/tests/unit"

_WEB_SUFFIXES = (".ts", ".tsx", ".js", ".mjs", ".cjs", ".jsx", ".css")
_SCRIPT_SUFFIXES = (".js", ".mjs", ".cjs")  # a literal that is run, so its imports are followed
_SUITE_NAME = re.compile(r"^t\d+_\w+\.py$")
_MAX_PATH = 200


def _load(filename: str, alias: str):
    """One of the two scope scripts, imported rather than copied: guard-scope imports browser-scope the same way."""
    path = SCRIPTS / filename
    spec = importlib.util.spec_from_file_location(alias, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


def defines_top_level(path: Path, name: str) -> bool:
    try:
        body = ast.parse(path.read_text(encoding="utf-8")).body
    except (OSError, SyntaxError, UnicodeDecodeError):
        return False
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            return True
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return True
    return False


# --------------------------------------------------------------------------- TypeScript strings, in one pass

# Comments and strings in one scan, so a `//` inside a string is no comment and an apostrophe inside a
# comment opens no string.
_TOKEN = re.compile(r"//[^\n]*|/\*.*?\*/|'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"|`(?:\\.|[^`\\])*`", re.S)
_IMPORT_LEAD = re.compile(r"(?:\bfrom|\bimport|\bimport\s*\()\s*$")
_RUN_GAP = re.compile(r"\s*,\s*")


def ts_strings(text: str) -> List[Tuple[int, int, str, str]]:
    """(start, end, value, quote) of every string literal that is not an import specifier."""
    out: List[Tuple[int, int, str, str]] = []
    for match in _TOKEN.finditer(text):
        token = match.group(0)
        if token[0] == "/":
            continue
        if _IMPORT_LEAD.search(text[max(0, match.start() - 40):match.start()]):
            continue
        out.append((match.start(), match.end(), token[1:-1], token[0]))
    return out


class Reach:
    """The files a suite loads, read from one checkout."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.gs = _load("guard-scope.py", "_guard_scope_for_tests_for")
        self.bs = _load("browser-scope.py", "_browser_scope_for_tests_for")
        self.gs.ROOT = root
        self.bs.ROOT = root
        self.packages = self._packages()
        self._trees: Dict[str, Optional[ast.AST]] = {}
        self._files: Dict[str, bool] = {}
        self._kinds: Dict[str, str] = {}
        self._web: Dict[str, Set[str]] = {}
        self._edges: Dict[Tuple[str, bool], Tuple[Set[str], Set[str], Set[str]]] = {}
        self._ts_hits: Dict[str, Tuple[Set[str], Set[str], Set[str]]] = {}

    def _packages(self) -> Tuple[str, ...]:
        names = {p.name for p in self.root.iterdir() if p.is_dir() and not p.name.startswith(".")}
        names |= {p.stem for p in self.root.glob("*.py")}
        return tuple(sorted(names))

    # ---- files

    def is_file(self, rel: str) -> bool:
        if rel not in self._files:
            ok = bool(rel) and len(rel) <= _MAX_PATH and "\0" not in rel and "\n" not in rel
            try:
                ok = ok and (self.root / rel).is_file()
            except OSError:
                ok = False
            self._files[rel] = ok
        return self._files[rel]

    def is_dir(self, rel: str) -> bool:
        if not rel or len(rel) > _MAX_PATH or "\0" in rel or "\n" in rel:
            return False
        try:
            return (self.root / rel).is_dir()
        except OSError:
            return False

    def inside(self, joined: str) -> Optional[str]:
        """A repo-relative path, or None when it leaves the checkout or names the root itself."""
        norm = posixpath.normpath(joined)
        if norm in (".", "") or norm == ".." or norm.startswith("../") or norm.startswith("/"):
            return None
        return norm

    def kind(self, rel: str) -> str:
        if rel not in self._kinds:
            self._kinds[rel] = self._kind(rel)
        return self._kinds[rel]

    def web_closure(self, rel: str) -> Set[str]:
        if rel not in self._web:
            self._web[rel] = set(self.bs.import_closure([rel]))
        return self._web[rel]

    def _kind(self, rel: str) -> str:
        if rel.endswith(".py"):
            return "py"
        if rel.endswith(_WEB_SUFFIXES):
            return "web"
        if "." not in posixpath.basename(rel):
            try:
                with open(self.root / rel, "rb") as handle:
                    first = handle.readline(200)
            except OSError:
                return "leaf"
            if first.startswith(b"#!") and b"python" in first:
                return "py"
        return "leaf"

    def parse(self, rel: str) -> Optional[ast.AST]:
        if rel not in self._trees:
            try:
                self._trees[rel] = ast.parse((self.root / rel).read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
                self._trees[rel] = None
        return self._trees[rel]

    def file_of(self, rel: str, bucket: Tuple[Set[str], Set[str], Set[str]]) -> None:
        """File one reached path into the (python, web, leaf) bucket by kind."""
        py, web, leaf = bucket
        {"py": py, "web": web}.get(self.kind(rel), leaf).add(rel)

    # ---- Python: what one module loads

    def edges(self, rel: str, import_time: bool) -> Tuple[Set[str], Set[str], Set[str]]:
        """(python files, web files, other files) that module `rel` loads. `import_time` reads only what runs at import."""
        key = (rel, import_time)
        if key in self._edges:
            return self._edges[key]
        bucket: Tuple[Set[str], Set[str], Set[str]] = (set(), set(), set())
        self._edges[key] = bucket
        tree = self.parse(rel)
        if tree is None:  # unreadable: its imports are unknown, so every module of the packages counts (fail safe)
            for imported in self.gs._package_imports(rel, self.packages):
                self.file_of(imported, bucket)
            return bucket
        for imported in self.gs._tree_package_imports(tree, rel, self.packages, import_time):
            self.file_of(imported, bucket)
        collector = self.gs._PathCollector(import_time=import_time)
        collector.visit(tree)
        folder = posixpath.dirname(rel)
        for hit in collector.hits:
            for cand in (hit, posixpath.join(folder, hit)):
                norm = self.inside(cand)
                if norm and self.is_file(norm):
                    self.file_of(norm, bucket)
        for node in (self.gs.walk_import_time(tree) if import_time else ast.walk(tree)):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            value = node.value
            if value and len(value) < _MAX_PATH and not re.search(r"\s", value):
                norm = self.inside(value[2:] if value.startswith("./") else value)
                if norm and self.is_file(norm):
                    self.file_of(norm, bucket)
            elif "import" in value and len(value) < 5000:
                self.snippet(value, bucket)
        if rel.startswith("scripts/") and not import_time:
            # a script a suite runs: the sibling scripts and packages it imports are read too
            for subject in self.gs.derive_subjects(self.root / rel):
                for path in self.expand(subject):
                    self.file_of(path, bucket)
        return bucket

    def snippet(self, value: str, bucket: Tuple[Set[str], Set[str], Set[str]]) -> None:
        """A string that is Python source with an import in it (`python3 -c "from store import slabs"`)."""
        try:
            tree = ast.parse(value)
        except (SyntaxError, ValueError):
            return
        for imported in self.gs._tree_package_imports(tree, "", self.packages):
            self.file_of(imported, bucket)

    def expand(self, subject: str) -> Iterable[str]:
        if subject.endswith("/**"):
            base = self.root / subject[:-3]
            return [p.relative_to(self.root).as_posix() for p in base.rglob("*") if p.is_file()]
        return [subject] if self.is_file(subject) else []

    def closure(self, starts: Iterable[str], import_time: bool) -> Set[str]:
        """Every file `starts` reaches. A Python module is followed; a web file brings its relative-import closure."""
        seen: Set[str] = set()
        queue = [s for s in starts if self.is_file(s)]
        while queue:
            rel = queue.pop()
            if rel in seen:
                continue
            seen.add(rel)
            if self.kind(rel) == "web":
                seen |= self.web_closure(rel)
                continue
            if self.kind(rel) != "py":
                continue
            py, web, leaf = self.edges(rel, import_time)
            queue.extend(py - seen)
            for path in web:
                seen |= self.web_closure(path)
            seen |= leaf
        return seen

    def parent_inits(self, rel: str) -> List[str]:
        out = []
        parts = posixpath.dirname(rel).split("/")
        for i in range(1, len(parts) + 1):
            init = "/".join(parts[:i]) + "/__init__.py"
            if self.is_file(init):
                out.append(init)
        return out

    # ---- Python suites

    def python_suites(self) -> List[str]:
        tests = self.root / "harness/tests"
        found = [f"harness/tests/{p.name}" for p in sorted(tests.glob("t*.py"))
                 if _SUITE_NAME.match(p.name) and defines_top_level(p, "run")]
        found += [f"harness/tests/t7/{p.name}" for p in sorted((tests / "t7").glob("*.py"))
                  if p.name != "__init__.py" and defines_top_level(p, "CHECKS")]
        return found

    def python_reach(self, suite: str, inherited_all: Set[str], inherited_group: Set[str]) -> Set[str]:
        reach = self.closure([suite, *self.parent_inits(suite)], import_time=False)
        reach |= inherited_all
        if suite.startswith("harness/tests/t7/"):
            reach |= inherited_group
        return reach

    # ---- unit tests (TypeScript)

    def unit_suites(self) -> List[str]:
        base = self.root / UNIT_DIR
        if not base.is_dir():
            return []
        return [f"{UNIT_DIR}/{p.name}" for p in sorted(base.glob("*.unit.ts"))]

    def ts_reads(self, rel: str) -> Tuple[Set[str], Set[str], Set[str]]:
        """What the test file `rel` reads by a literal: (python files run, scripts run, text read)."""
        if rel in self._ts_hits:
            return self._ts_hits[rel]
        run_py: Set[str] = set()
        run_script: Set[str] = set()
        text_read: Set[str] = set()
        self._ts_hits[rel] = (run_py, run_script, text_read)
        try:
            text = (self.root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return self._ts_hits[rel]
        strings = ts_strings(text)
        folder = posixpath.dirname(rel)
        runs: List[List[str]] = []
        previous_end: Optional[int] = None
        for start, end, value, quote in strings:
            if "${" in value:
                previous_end = None
                continue
            if previous_end is not None and _RUN_GAP.fullmatch(text[previous_end:start]):
                runs[-1].append(value)
            else:
                runs.append([value])
            previous_end = end
        candidates: List[str] = []
        for run in runs:
            candidates.extend(run)
            if len(run) > 1:
                candidates.append("/".join(run))
        # folders the test names: a navigation run (`'..', '..', 'src'`) or the folder part of a template
        # (`new URL(`../../src/${name}`, ...)`) is a base the test's other literals are read against
        bases = [folder, ""]
        navigation = [("/".join(run)) for run in runs if run[0] in ("..", ".")]
        templates = [value.split("${")[0].rstrip("/") for _s, _e, value, quote in strings
                     if quote == "`" and "${" in value]
        for named in navigation + templates:
            for base in (folder, ""):
                norm = self.inside(posixpath.join(base, named)) if named else None
                if norm and self.is_dir(norm) and norm not in bases:
                    bases.append(norm)
        wants_dir = re.search(r"\breaddir(?:Sync)?\s*\(|\bglob(?:Sync)?\s*\(", text) is not None
        extensions = tuple(re.findall(r"endsWith\(\s*['\"](\.\w+)['\"]", text))
        recursive = "recursive" in text
        for cand in candidates:
            for base in bases:
                norm = self.inside(posixpath.join(base, cand))
                if norm is None:
                    continue
                if self.is_file(norm):
                    kind = self.kind(norm)
                    if kind == "py":
                        run_py.add(norm)
                    elif norm.endswith(_SCRIPT_SUFFIXES):
                        run_script.add(norm)
                    else:
                        text_read.add(norm)
                elif wants_dir and self.is_dir(norm):
                    walk = (self.root / norm).rglob("*") if recursive else (self.root / norm).iterdir()
                    for child in walk:
                        if child.is_file() and (not extensions or child.name.endswith(extensions)):
                            text_read.add(child.relative_to(self.root).as_posix())
        for _s, _e, value, _q in strings:
            if "${" not in value and "import" in value and len(value) < 5000:
                bucket: Tuple[Set[str], Set[str], Set[str]] = (set(), set(), set())
                self.snippet(value, bucket)
                run_py |= bucket[0]
        return self._ts_hits[rel]

    def unit_reach(self, suite: str) -> Set[str]:
        files = set(self.bs.import_closure([suite]))
        reach = set(files)
        for rel in sorted(files):
            if not rel.startswith("app/tests/") or not rel.endswith((".ts", ".tsx")):
                continue
            run_py, run_script, text_read = self.ts_reads(rel)
            reach |= self.closure(run_py, import_time=False)
            for script in run_script:
                reach |= set(self.bs.import_closure([script]))
            reach |= text_read
        return reach


def select(root: Path, target: str) -> List[str]:
    reach = Reach(root)
    suites_py = reach.python_suites()
    inherited_all = reach.closure([HOME, *reach.parent_inits(HOME)], import_time=True)
    inherited_group = reach.closure([HERMETIC, AGGREGATOR], import_time=True)
    chosen: List[str] = []
    for suite in suites_py:
        if target in reach.python_reach(suite, inherited_all, inherited_group):
            chosen.append(suite)
    for suite in reach.unit_suites():
        if target in reach.unit_reach(suite):
            chosen.append(suite)
    return chosen


def repo_relative(root: Path, raw: str) -> Optional[str]:
    path = raw[2:] if raw.startswith("./") else raw
    if os.path.isabs(path):
        try:
            path = Path(path).resolve().relative_to(root).as_posix()
        except ValueError:
            return None
    norm = posixpath.normpath(path)
    return norm if norm not in (".", "") and not norm.startswith("..") else None


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tests-for.py",
        description="Print the test suites that reach one product file, one per line.")
    parser.add_argument("path", help="repo-relative path of the changed file")
    parser.add_argument("--root", default=None,
                        help="the checkout to read (default: the current directory)")
    args = parser.parse_args(argv)
    root = Path(args.root or os.getcwd()).resolve()
    if not root.is_dir():
        parser.error(f"--root {args.root!r} is not a directory")
    target = repo_relative(root, args.path)
    if target is None:
        return 0
    for suite in select(root, target):
        print(suite)
    return 0


if __name__ == "__main__":
    sys.exit(main())
