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
`python3 -c "from pkg import m"` snippet, a module run by `-m` (`[sys.executable, "-m", "cli"]`, or the
`python3 -m cli` line of a shell shim such as `./banchi`), or, for a unit test, a text read (a literal path resolved
against the test's folder, the repo root or a folder the test names, `new URL(...)`, a `readdirSync` of
a folder, narrowed by an `endsWith('.ext')` it finds). A text read is a leaf: it reads the file, not
what the file imports. A script it runs is followed: Python by its imports, `.mjs` by its relative imports. A unit test's `import('./x')` is followed like an import.

THE REACH RULES (each is a case of `scripts/tests-for-selftest.py`):
- Every Python suite inherits the import-time closure of `harness/tests/home.py`, which the runner imports for
  every suite, and the `__init__.py` of each folder above it.
- Every T7 group inherits the import-time closure of `harness/tests/t7/common.py` (the hermetic setup) and of
  `harness/tests/t7_store_and_seams.py` (the module every group run loads), whether it imports them or not.
- What a group loads only inside a check body reaches that group, and the aggregator that runs it, alone.
- A `tN_*.py` module with no top-level `run` is no suite: its checks run inside the aggregator. A module that cannot be
  parsed might be one, so it is printed.

THE HOMES IT REUSES, never copies: `scripts/guard-scope.py` for the Python scan (`_PathCollector`,
`_tree_package_imports` read at any depth or at import time, `derive_subjects` for a script a suite runs) and
`scripts/browser-scope.py` for the TypeScript scan (`import_closure`; strings and comments of a
test are read in one pass here). Both read the module global `ROOT`, which this sets to `--root`.

KNOWN GAPS, each a miss that narrows the answer: a file a suite reaches only through a name built at run time
(an f-string, a variable, an environment lookup); a directory a Python suite reads with `glob`; a file deleted
by the change (nothing resolves it). The TypeScript scan also misses these shapes, each an under-select that no
`.unit.ts` uses today (a scan of 222 app files found none):
- a regex after the `)` of an unbraced if/while/for reads as division;
- `!` before `/` reads as the start of a regex;
- a comment or a backtick specifier inside `import(...)` is not followed;
- no JSX mode: a lone quote in `.tsx` text can mispair.
The consumer runs the full set on a file this prints nothing for only when
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

# The scope scripts are loaded from beside this file. Loading them must leave no bytecode there: the run is a read.
sys.dont_write_bytecode = True

SCRIPTS = Path(__file__).resolve().parent

HOME = "harness/tests/home.py"
HERMETIC = "harness/tests/t7/common.py"
AGGREGATOR = "harness/tests/t7_store_and_seams.py"
UNIT_DIR = "app/tests/unit"

_WEB_SUFFIXES = (".ts", ".tsx", ".js", ".mjs", ".cjs", ".jsx", ".css")
_SCRIPT_SUFFIXES = (".js", ".mjs", ".cjs")  # a literal that is run, so its imports are followed
_SUITE_NAME = re.compile(r"^t\d+_\w+\.py$")
_MAX_PATH = 200
_DASH_M = re.compile(r"(?:^|\s)-m\s+([A-Za-z_][\w.]*)")  # `python3 -m cli`, in a shim or a command string


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


def defines_top_level(path: Path, name: str) -> Optional[bool]:
    """Whether the module defines `name` at its top level; None when it cannot be read or parsed. Bytes go to
    `ast.parse`, which decodes by the PEP 263 cookie as the interpreter does."""
    try:
        body = ast.parse(path.read_bytes()).body
    except (OSError, SyntaxError, ValueError):
        return None
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            return True
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return True
    return False


# --------------------------------------------------------------------------- TypeScript strings, in one pass

# One pass over the source reads comments, strings, templates (a `${...}` is read through, nested) and regex
# literals, so a quote inside a regex or a comment opens no string and a `//` inside a string is no comment.
# A `/` opens a regex when the token before it cannot end a value; a regex that does not close on its line is a
# division. This is the one scanner of TypeScript text in this repo: browser-scope's `strip_comments` is
# regex-only and string-blind, so it cannot serve the read of a literal.
_IMPORT_LEAD = re.compile(r"(?:\bfrom|\bimport)\s*$")
_DYNAMIC_LEAD = re.compile(r"\bimport\s*\(\s*$")
_RUN_GAP = re.compile(r"\s*,\s*")
_WORD = re.compile(r"[A-Za-z_$][\w$]*|\d[\w.]*")
_BEFORE_REGEX = frozenset(["return", "typeof", "case", "in", "of", "delete", "void", "throw", "new", "else", "do", "instanceof", "yield", "await"])
_VALUE = ("v", "")  # the token before a `/` ended a value, so the `/` divides
_Token = Tuple[int, int, str, str]


def _regex_allowed(prev: Optional[Tuple[str, str]]) -> bool:
    if prev is None:
        return True
    kind, word = prev
    if kind == "v":
        return False
    if kind == "w":
        return word in _BEFORE_REGEX
    return word not in (")", "]")


def _template_end(text: str, i: int) -> int:
    """Index after the backtick that closes the template opened at `i`, or -1 when it never closes."""
    j, n = i + 1, len(text)
    while j < n:
        ch = text[j]
        if ch == "\\":
            j += 2
        elif ch == "`":
            return j + 1
        elif text.startswith("${", j):
            j = _walk(text, j + 2, True, None)
        else:
            j += 1
    return -1


def _walk(text: str, i: int, in_expr: bool, out: Optional[List[_Token]]) -> int:
    """Scan code from `i`. In a template expression, stop after its closing `}` and return that index; else read to
    the end. Strings found go to `out` (None while reading a template's expression)."""
    n = len(text)
    depth = 0
    prev: Optional[Tuple[str, str]] = None
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        pair = text[i:i + 2]
        if pair == "//":
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if pair == "/*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in "'\"":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            if j < n and text[j] == c:  # a quote that never closes on its line is text, not a string
                if out is not None:
                    out.append((i, j + 1, text[i + 1:j], c))
                i, prev = j + 1, _VALUE
            else:
                i += 1
            continue
        if c == "`":
            end = _template_end(text, i)
            if end < 0:
                i += 1
                continue
            if out is not None:
                out.append((i, end, text[i + 1:end - 1], "`"))
            i, prev = end, _VALUE
            continue
        if c == "/":
            if _regex_allowed(prev):
                j, in_class = i + 1, False
                while j < n and text[j] != "\n":
                    ch = text[j]
                    if ch == "\\":
                        j += 2
                        continue
                    if ch == "[":
                        in_class = True
                    elif ch == "]":
                        in_class = False
                    elif ch == "/" and not in_class:
                        break
                    j += 1
                if j < n and text[j] == "/":
                    j += 1
                    while j < n and text[j].isalpha():
                        j += 1
                    i, prev = j, _VALUE
                    continue
            i, prev = i + 1, ("p", "/")
            continue
        word = _WORD.match(text, i)
        if word:
            i, prev = word.end(), ("w", word.group(0))
            continue
        if in_expr and c == "{":
            depth += 1
        elif in_expr and c == "}":
            if depth == 0:
                return i + 1
            depth -= 1
        i, prev = i + 1, (_VALUE if c in ")]" else ("p", c))
    return n


def ts_scan(text: str) -> Tuple[List[_Token], List[str]]:
    """(strings, dynamic imports) of one TypeScript source. A string is (start, end, value, quote), and an import
    specifier is left out of it: `from 'x'` and `import 'x'` are modules, not text reads. The specifier of an
    `import('x')` call is returned in the second list, in order."""
    found: List[_Token] = []
    _walk(text, 0, False, found)
    strings: List[_Token] = []
    dynamic: List[str] = []
    for item in found:
        lead = text[max(0, item[0] - 40):item[0]]
        if _DYNAMIC_LEAD.search(lead) and item[3] != "`":
            dynamic.append(item[2])
        elif not _IMPORT_LEAD.search(lead):
            strings.append(item)
    return strings, dynamic


def ts_strings(text: str) -> List[_Token]:
    """(start, end, value, quote) of every string literal that is not an import specifier."""
    return ts_scan(text)[0]


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
        self._ts_dynamic: Dict[str, List[str]] = {}

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
                self._trees[rel] = ast.parse((self.root / rel).read_bytes())
            except (OSError, SyntaxError, ValueError):
                self._trees[rel] = None
        return self._trees[rel]

    def file_of(self, rel: str, bucket: Tuple[Set[str], Set[str], Set[str]]) -> None:
        """File one reached path into the (python, web, leaf) bucket by kind. A shell shim that execs
        `python -m pkg` also files the module it runs."""
        py, web, leaf = bucket
        kind = self.kind(rel)
        {"py": py, "web": web}.get(kind, leaf).add(rel)
        if kind == "leaf":
            py.update(self.shim_modules(rel))

    def module_files(self, dotted: str) -> List[str]:
        """The files `python -m <dotted>` runs: the module or the package's `__main__.py`, and the `__init__.py` of
        each package above it. A name outside the repo's own packages is no file."""
        parts = dotted.split(".")
        if parts[0] not in self.packages:
            return []
        base = "/".join(parts)
        out = [cand for cand in (f"{base}.py", f"{base}/__main__.py", f"{base}/__init__.py") if self.is_file(cand)]
        out += [init for i in range(1, len(parts)) if self.is_file(init := "/".join(parts[:i]) + "/__init__.py")]
        return out

    def shim_modules(self, rel: str) -> List[str]:
        """The modules a shell script runs with `python -m` (`./banchi` is `exec python3 -m cli`); [] for any other file."""
        base = posixpath.basename(rel)
        if "." in base:
            return []
        try:
            with open(self.root / rel, "rb") as handle:
                head = handle.read(20000).decode("utf-8", errors="replace")
        except OSError:
            return []
        if not head.startswith("#!") or "python" not in head:
            return []
        return [path for name in _DASH_M.findall(head) for path in self.module_files(name)]

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
            if isinstance(node, (ast.List, ast.Tuple)):  # argv `[sys.executable, "-m", "cli"]`
                for flag, arg in zip(node.elts, node.elts[1:]):
                    if (isinstance(flag, ast.Constant) and flag.value == "-m"
                            and isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                        for path in self.module_files(arg.value):
                            self.file_of(path, bucket)
                continue
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            value = node.value
            if " -m " in value and len(value) < 5000:  # a command string, `python3 -m cli identify`
                for name in _DASH_M.findall(value):
                    for path in self.module_files(name):
                        self.file_of(path, bucket)
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
                 if _SUITE_NAME.match(p.name) and defines_top_level(p, "run") is not False]
        found += [f"harness/tests/t7/{p.name}" for p in sorted((tests / "t7").glob("*.py"))
                  if p.name != "__init__.py" and defines_top_level(p, "CHECKS") is not False]
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
        strings, dynamic = ts_scan(text)
        self._ts_dynamic[rel] = dynamic
        folder = posixpath.dirname(rel)
        runs: List[List[str]] = []
        previous_end: Optional[int] = None
        for start, end, value, _quote in strings:
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
                        run_py.update(self.shim_modules(norm))
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
        """The suite's static import closure, plus what each test file in it reads, runs or loads by
        `import('...')`. A dynamically loaded module brings its own closure, and its tests are read in turn."""
        files = set(self.bs.import_closure([suite]))
        reach = set(files)
        queue = sorted(files)
        done: Set[str] = set()
        while queue:
            rel = queue.pop()
            if rel in done:
                continue
            done.add(rel)
            if not rel.startswith("app/tests/") or not rel.endswith((".ts", ".tsx")):
                continue
            run_py, run_script, text_read = self.ts_reads(rel)
            reach |= self.closure(run_py, import_time=False)
            for script in run_script:
                reach |= set(self.bs.import_closure([script]))
            reach |= text_read
            for module in self._ts_dynamic.get(rel, []):
                target = self.bs.resolve_relative(rel, module) if module.startswith(".") else None
                if target:
                    loaded = set(self.bs.import_closure([target]))
                    queue.extend(loaded - done)
                    reach |= loaded
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
