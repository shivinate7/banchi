#!/usr/bin/env python3
"""Proves `scripts/tests-for.py <path> [--root DIR]`, the selector that names the suites which reach one product file.

Protects: The suite selector names exactly the suites that reach a product file, and `--root` wins over the cwd it runs in.

Consumer: claude-settings `hooks/mutate_shared.py` `_select_suites`, profile key `select`. It runs the selector
from a checkout root with bare `python3`, and keeps only the changed suites the selector prints.

THE CONTRACT THIS PROVES
- Prints one repo-relative suite per line, exact strings: `harness/tests/tN_*.py` (a module that defines a
  top-level `run`), `harness/tests/t7/<group>.py` (a group that defines a top-level `CHECKS`), and
  `app/tests/unit/*.unit.ts`. No `./`, no absolute path, no duplicate.
- A file no suite reaches: exit 0, empty output. Nonzero exit only on a bad argument.
- Stdlib only. A missing `vendor/`, `demo-assets/` or `node_modules/` is no error.
- Reuses `scripts/guard-scope.py` and `scripts/browser-scope.py`; a copy of either is a defect.

THE REACH RULES DECIDED HERE (the builder implements them; each rule has a case below)
- A file is reached when a suite loads it through an import, a literal path, a literal `importlib` name, a
  literal subprocess argument (`./banchi`, `sys.executable` + script path, `python3 -c "from pkg import m"`), or a
  text read of a file (`readFileSync`, a `src('X.tsx')` helper, `new URL('../src/X', import.meta.url)`, a
  `readdirSync` of a source folder). A text read is a leaf: it reads the file, not what that file imports.
- Every python suite inherits the import-time closure of `harness/tests/home.py`. The runner imports it for every
  suite, and importing `store.files` runs `store/__init__.py` first.
- Every T7 group inherits the import-time closure of `harness/tests/t7/common.py` (the hermetic setup, which
  every group's checks run inside) and of `harness/tests/t7_store_and_seams.py` (the module every group run
  loads). A group that does not import `common` still inherits it.
- A file a group reaches only inside a check body selects that group alone, plus `t7_store_and_seams.py`.
- A `tN_*.py` module with no top-level `run` is not a suite. `t7_box_map.py` is one: its checks run inside
  `t7_store_and_seams.py`, so a file it reaches prints `t7_store_and_seams.py`.

HOW IT IS RUN
    python3 scripts/tests-for-selftest.py
The real-tree cases read the checkout this file lives in, and they read only. The planted-break cases copy real
files into a run folder, and run the suites there. Each run folder is `harness/tests/home.py`'s `run_folder()`,
the one home for run folders; its sweep is proven in `harness/tests/t7/t1_results.py`. A subprocess has a timeout,
and no case sleeps or reads a clock.

COST: one selector run per selector case (about 30 runs), plus four Playwright unit runs of two files (clean, then
planted) and four short Python suite runs for the planted break. The unit legs need `app/node_modules`
(`npm ci --prefix app`), and without it that case fails and names the fix.
"""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.tests.home import run_folder  # noqa: E402  the one home of a run folder (test-temp-standard)

SELECTOR = ROOT / "scripts" / "tests-for.py"
TIMEOUT = 120
UNIT_TIMEOUT = 300
SUITE_FORMAT = re.compile(r"^(harness/tests/t\d+_\w+\.py|harness/tests/t7/\w+\.py|app/tests/unit/[\w-]+\.unit\.ts)$")

FAILED: List[Tuple[str, str]] = []  # (case, one cause)
CASES: List[Tuple[str, object]] = []
CURRENT = ["(none)"]


def case(fn):
    CASES.append((fn.__name__, fn))
    return fn


def expect(ok: bool, cause: str) -> bool:
    if not ok:
        FAILED.append((CURRENT[0], cause))
    return bool(ok)


# --------------------------------------------------------------------------------- oracles, read from the repo
# These read repo files directly, never the selector, so a wrong selector cannot pass by agreeing with itself.


def module_level_imports(path: Path) -> set:
    """`pkg.name` for every import at module level (not inside a def), e.g. `pipeline.walkplan`."""
    out = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            out.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
    return out


def all_imports(path: Path) -> set:
    """Every module an import names, at any depth."""
    out = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            out.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
    return out


def defines_top_level(path: Path, name: str) -> bool:
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == name:
            return True
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return True
    return False


def real_groups() -> List[str]:
    """Every T7 group that defines a top-level CHECKS."""
    return [f"harness/tests/t7/{p.name}" for p in sorted((ROOT / "harness/tests/t7").glob("*.py"))
            if p.name != "__init__.py" and defines_top_level(p, "CHECKS")]


def registered_tests() -> List[str]:
    """The modules `harness/run.py` names in its TESTS list, as repo paths."""
    for node in ast.parse((ROOT / "harness/run.py").read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "TESTS" for t in node.targets):
            return [f"harness/tests/{el.id}.py" for el in node.value.elts if isinstance(el, ast.Name)]
    return []


def real_unit_suites() -> List[str]:
    return [f"app/tests/unit/{p.name}" for p in sorted((ROOT / "app/tests/unit").glob("*.unit.ts"))]


def real_python_suites() -> List[str]:
    return sorted(set(registered_tests()) | set(real_groups()))


# --------------------------------------------------------------------------------- the selector, run as the consumer runs it


def require_selector() -> bool:
    return expect(SELECTOR.is_file(),
                  "scripts/tests-for.py is not in the tree, so there is no selector to run (the builder writes it)")


def run_selector(args: List[str], cwd: Path) -> Tuple[Optional[int], List[str], str]:
    try:
        done = subprocess.run(["python3", str(SELECTOR), *args], cwd=str(cwd), capture_output=True,
                              text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, [], "timed out after %d seconds" % TIMEOUT
    return done.returncode, done.stdout.splitlines(), done.stderr


def expect_suites(label: str, lines: List[str], want: List[str]) -> None:
    got = sorted(lines)
    expect(len(got) == len(set(got)), f"{label}: a suite is printed twice")
    missing = sorted(set(want) - set(got))
    extra = sorted(set(got) - set(want))
    expect(not missing, f"{label}: a reaching suite is not printed: {missing}")
    expect(not extra, f"{label}: a suite is printed that does not reach the file: {extra}")


def select_expect(label: str, args: List[str], cwd: Path, want: List[str]) -> None:
    code, lines, err = run_selector(args, cwd)
    if code is None:
        expect(False, f"{label}: the selector {err}")
        return
    expect(code == 0, f"{label}: the selector exited {code}, expected 0 ({err.strip()[-200:]})")
    expect_suites(label, lines, want)


# --------------------------------------------------------------------------------- fixture trees


def write_tree(base: Path, files: Dict[str, str]) -> Path:
    for rel, text in files.items():
        target = base / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return base


# One synthetic tree for the rules that need no real repo. Every case below queries it; no case adds files to it.
BASE_TREE = {
    "harness/__init__.py": "",
    "harness/tests/__init__.py": "",
    # class 1: a direct import, and a far suite that must stay out. t1 also reads a path under vendor/, which is
    # absent: the selector must not fail on a path a sparse checkout does not have.
    "harness/tests/t1_direct.py": (
        "from pathlib import Path\n"
        "from pipeline import direct_leaf\n\n"
        "ROOT = Path(__file__).resolve().parents[2]\n"
        "DATA = ROOT / \"vendor\" / \"catalog.json\"\n"
        "PHOTOS = ROOT / \"demo-assets\" / \"cards.json\"\n\n\n"
        "def run():\n    return direct_leaf.VALUE\n"),
    "harness/tests/t2_far.py": "from pipeline import far_leaf\n\n\ndef run():\n    return far_leaf.VALUE\n",
    "pipeline/__init__.py": "",
    "pipeline/direct_leaf.py": "VALUE = 1\n",
    "pipeline/far_leaf.py": "VALUE = 2\n",
    # class 2: store/rows.py reached through a package import (store.db, absolute) and a relative one (store.relay).
    "store/__init__.py": "",
    "store/db.py": "from store import rows\n\n\ndef open_db():\n    return rows.ROWS\n",
    "store/rows.py": "ROWS = 3\n",
    "store/relay.py": "from .rows import ROWS\n",
    "harness/tests/t3_package.py": "import store.db\n\n\ndef run():\n    return store.db.open_db()\n",
    "harness/tests/t4_relative.py": "from store import relay\n\n\ndef run():\n    return relay.ROWS\n",
    # class 3: a subprocess run of a script by literal path, a `./banchi` run, and importlib by literal name.
    "harness/tests/t5_proc.py": (
        "import subprocess\nimport sys\n\n\ndef run():\n"
        "    subprocess.run([sys.executable, 'scripts/tool_proc.py'], check=True)\n"),
    "scripts/tool_proc.py": "from pipeline import proc_leaf\n\nprint(proc_leaf.VALUE)\n",
    "pipeline/proc_leaf.py": "VALUE = 4\n",
    "harness/tests/t6_cli.py": (
        "import subprocess\n\n\ndef run():\n    subprocess.run(['./banchi', 'identify'], check=True)\n"),
    "banchi": "#!/usr/bin/env python3\nfrom cli import cli_leaf\n\nprint(cli_leaf.VALUE)\n",
    "cli/__init__.py": "",
    "cli/cli_leaf.py": "VALUE = 5\n",
    "harness/tests/t8_dyn.py": (
        "import importlib\n\n\ndef run():\n    return importlib.import_module('pipeline.dyn_leaf').VALUE\n"),
    "pipeline/dyn_leaf.py": "VALUE = 6\n",
    # class 3, the product side: a product module that loads a leaf by literal importlib name at import time.
    "harness/tests/t9_host.py": "from pipeline import lazy_host\n\n\ndef run():\n    return lazy_host.LAZY.VALUE\n",
    "pipeline/lazy_host.py": "import importlib\n\nLAZY = importlib.import_module('pipeline.lazy_leaf')\n",
    "pipeline/lazy_leaf.py": "VALUE = 7\n",
    # class 6: a file no suite reaches.
    "scripts/unreached.py": "VALUE = 8\n",
}

# The T7 granularity tree: one aggregator, a group that loads a helper at import time, a group that does not import
# the hermetic setup, a non-suite module, and a helper with no CHECKS.
GROUP_TREE = {
    "harness/__init__.py": "",
    "harness/tests/__init__.py": "",
    "harness/tests/t7_store_and_seams.py": (
        "from harness.tests.t7 import g_a, g_b\n"
        "from harness.tests.t7.common import helper_hermetic\n"
        "from cli import resolve_like\n\n\n"
        "def run(order=None):\n"
        "    from harness.tests import t7_box_map\n"
        "    return t7_box_map.check_box, g_a, g_b, helper_hermetic, resolve_like\n"),
    "harness/tests/t7/__init__.py": "",
    "harness/tests/t7/common.py": (
        "from store import shared\n\n\n"
        "def helper_hermetic():\n    return shared.X\n"),
    "harness/tests/t7/g_a.py": (
        "from harness.tests.t7 import helper\n"
        "from harness.tests.t7.common import helper_hermetic\n\n"
        "CHECKS = (check_a,)\n\n\n"
        "def check_a(checks):\n"
        "    from pipeline import only_a\n"
        "    return only_a.X, helper.HELPER_VALUE, helper_hermetic()\n"),
    "harness/tests/t7/g_b.py": "CHECKS = (check_b,)\n\n\ndef check_b(checks):\n    return None\n",
    # no CHECKS: a helper, never a suite of its own
    "harness/tests/t7/helper.py": "from pipeline import helper_leaf\n\nHELPER_VALUE = helper_leaf.X\n",
    # a non-suite T-module: CHECKS but no top-level run; the aggregator imports it inside run()
    "harness/tests/t7_box_map.py": (
        "from pipeline import boxmap_leaf\n\n\n"
        "def check_box(checks):\n    return boxmap_leaf.X\n\n\n"
        "CHECKS = (check_box,)\n"),
    "pipeline/only_a.py": "X = 1\n",
    "pipeline/helper_leaf.py": "X = 2\n",
    "pipeline/boxmap_leaf.py": "X = 3\n",
    "cli/__init__.py": "",
    "cli/resolve_like.py": "X = 4\n",
    "store/__init__.py": "",
    "store/shared.py": "X = 5\n",
}

PLANT_TREE_TESTS = {
    "harness/__init__.py": "",
    "harness/tests/__init__.py": "",
    "pipeline/__init__.py": "",
    "harness/tests/t9_fast.py": (
        "from collections import namedtuple\n"
        "from pipeline import namefold\n\n"
        "Result = namedtuple('Result', 'passed detail')\n\n\n"
        "def run():\n"
        "    got = namefold.fold_name_typography('a\\u2019b')\n"
        "    return Result(got == \"a'b\", 'folded to %r' % got)\n"),
    "harness/tests/t2_other.py": (
        "from collections import namedtuple\n\n"
        "Result = namedtuple('Result', 'passed detail')\n\n\n"
        "def run():\n    return Result(True, 'unrelated')\n"),
}

RUNNER = (
    "import sys, importlib\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "result = importlib.import_module(sys.argv[2]).run()\n"
    "sys.exit(0 if result.passed else 1)\n")


def suite_green(tree: Path, module: str) -> Tuple[Optional[int], str]:
    """Run one python suite the way the consumer's runner does, in a tree. Returns (exit code, tail of output)."""
    try:
        done = subprocess.run(["python3", "-c", RUNNER, str(tree), module], cwd=str(tree), capture_output=True,
                              text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, "timed out"
    return done.returncode, (done.stdout + done.stderr).strip()[-300:]


# --------------------------------------------------------------------------------- real repo: python


@case
def real_walkplan_reaches_t11_and_every_group() -> None:
    """Class 1 (direct) and class 4 (hermetic inheritance) on a real file: pipeline/walkplan.py."""
    t11 = ROOT / "harness/tests/t11_walk_plan.py"
    capture = ROOT / "server/capture_server.py"
    common = ROOT / "harness/tests/t7/common.py"
    CURRENT[0] = "real_walkplan_reaches_t11_and_every_group"
    scope = [
        expect("pipeline.walkplan" in module_level_imports(t11), "scope: t11_walk_plan.py no longer imports walkplan at module level"),
        expect("pipeline.walkplan" in module_level_imports(capture), "scope: capture_server.py no longer imports walkplan at module level"),
        expect("server.capture_server" in module_level_imports(common), "scope: the hermetic setup no longer imports capture_server at module level"),
    ]
    if not all(scope) or not require_selector():
        return
    want = ["harness/tests/t11_walk_plan.py", "harness/tests/t7_store_and_seams.py"] + real_groups()
    select_expect("pipeline/walkplan.py", ["pipeline/walkplan.py"], ROOT, want)
    code, lines, _ = run_selector(["pipeline/walkplan.py"], ROOT)
    if code == 0:
        bad = [line for line in lines if not SUITE_FORMAT.match(line)]
        expect(not bad, f"format: a line is not a suite string: {bad[:3]}")
        expect(len(lines) < len(real_python_suites()) + len(real_unit_suites()),
               "typical file: it selects every suite, not fewer")


@case
def real_rows_reaches_every_python_suite_through_the_package_init() -> None:
    """Class 2 on a real file: store/rows.py, reached through `store/__init__.py` -> `store.cache` -> `store.rows`,
    which the harness loads for every suite through `harness/tests/home.py`."""
    CURRENT[0] = "real_rows_reaches_every_python_suite_through_the_package_init"
    scope = [
        expect("store.files" in module_level_imports(ROOT / "harness/tests/home.py"),
               "scope: home.py no longer imports store.files at module level"),
        expect("store.cache.Cache" in module_level_imports(ROOT / "store/__init__.py"),
               "scope: store/__init__.py no longer imports store.cache at module level"),
        expect("store.rows.Rows" in module_level_imports(ROOT / "store/cache.py"),
               "scope: store/cache.py no longer imports store.rows at module level"),
        expect("harness.tests.home.isolated_home" in module_level_imports(ROOT / "harness/run.py"),
               "scope: harness/run.py no longer imports home.py at module level"),
    ]
    if not all(scope) or not require_selector():
        return
    # slab-graders.unit.ts runs `from store import slabs` in a subprocess, and store/slabs.py imports store.rows.
    want = sorted(set(registered_tests()) | set(real_groups()) | {"app/tests/unit/slab-graders.unit.ts"})
    select_expect("store/rows.py", ["store/rows.py"], ROOT, want)


@case
def real_pipeline_routes_reaches_groups_that_never_import_the_hermetic_setup() -> None:
    """Class 4, inheritance on a real file: server/pipeline_routes.py. Five groups never import `common`; the
    hermetic setup imports pipeline_routes, and every group's checks run inside it."""
    CURRENT[0] = "real_pipeline_routes_reaches_groups_that_never_import_the_hermetic_setup"
    non_importers = ["drift_homes", "daily_prices", "second_look_counts", "match_claim", "t1_results"]
    scope = [
        expect("server.pipeline_routes" in module_level_imports(ROOT / "harness/tests/t7/common.py"),
               "scope: the hermetic setup no longer imports pipeline_routes at module level"),
    ]
    for name in non_importers:
        path = ROOT / f"harness/tests/t7/{name}.py"
        scope.append(expect(not any("common" in imp.split(".") for imp in all_imports(path)),
                            f"scope: {name}.py now imports the hermetic setup, so it no longer tests inheritance"))
    if not all(scope) or not require_selector():
        return
    want = real_groups() + ["harness/tests/t7_store_and_seams.py"]
    code, lines, err = run_selector(["server/pipeline_routes.py"], ROOT)
    if code is None or code != 0:
        expect(False, f"server/pipeline_routes.py: the selector exited {code}, expected 0 ({err.strip()[-200:]})")
        return
    for group in real_groups():
        if group.split("/")[-1][:-3] in non_importers:
            expect(group in lines, f"inheritance: {group} never imports the hermetic setup but is not printed")
    expect("harness/tests/t7_store_and_seams.py" in lines, "server/pipeline_routes.py: the aggregator is not printed")
    for far in ["harness/tests/t2_round_trip.py", "harness/tests/t8_codes.py", "harness/tests/t9_traces.py"]:
        expect(far not in lines, f"server/pipeline_routes.py: {far} is printed, though no import or read reaches it")


@case
def real_unreached_file_prints_nothing_and_exits_zero() -> None:
    """Class 6, empty state, on a real file: scripts/janitor.py. The control is the case above, which is not empty."""
    CURRENT[0] = "real_unreached_file_prints_nothing_and_exits_zero"
    mentions = []
    for base in (ROOT / "harness", ROOT / "app/tests/unit"):
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".ts"}:
                if "janitor.py" in path.read_text(encoding="utf-8", errors="replace"):
                    mentions.append(str(path.relative_to(ROOT)))
    if not expect(not mentions, f"scope: a suite names janitor.py: {mentions[:3]}") or not require_selector():
        return
    code, lines, err = run_selector(["scripts/janitor.py"], ROOT)
    if code is None:
        expect(False, f"scripts/janitor.py: the selector {err}")
        return
    expect(code == 0, f"scripts/janitor.py: the selector exited {code}, expected 0")
    expect(lines == [], f"scripts/janitor.py: the selector printed {lines[:3]}, expected nothing")


@case
def real_registry_is_the_full_python_set() -> None:
    """Class 6's other end, full-size on a real file: harness/tests/__init__.py. Every registered module and every
    group reaches it, and t7_box_map.py is not a suite."""
    CURRENT[0] = "real_registry_is_the_full_python_set"
    scope = [expect(len(registered_tests()) > 0, "scope: harness/run.py names no TESTS modules")]
    if not all(scope) or not require_selector():
        return
    want = real_python_suites()
    expect("harness/tests/t7_box_map.py" not in want, "scope: t7_box_map.py is listed as a suite")
    select_expect("harness/tests/__init__.py", ["harness/tests/__init__.py"], ROOT, want)


# --------------------------------------------------------------------------------- real repo: unit tests (TypeScript)


@case
def real_tabtitle_reaches_its_one_unit_test() -> None:
    """Class 5, import: app/src/tabTitle.ts is imported by tab-title.unit.ts and by no other unit test."""
    CURRENT[0] = "real_tabtitle_reaches_its_one_unit_test"
    if not expect("../../src/tabTitle" in (ROOT / "app/tests/unit/tab-title.unit.ts").read_text(encoding="utf-8"),
                  "scope: tab-title.unit.ts no longer imports tabTitle") or not require_selector():
        return
    code, lines, err = run_selector(["app/src/tabTitle.ts"], ROOT)
    if code is None:
        expect(False, f"app/src/tabTitle.ts: the selector {err}")
        return
    expect(code == 0, f"app/src/tabTitle.ts: the selector exited {code}, expected 0")
    expect("app/tests/unit/tab-title.unit.ts" in lines, "app/src/tabTitle.ts: tab-title.unit.ts is not printed")
    expect("app/tests/unit/dispenser.unit.ts" not in lines, "app/src/tabTitle.ts: dispenser.unit.ts is printed, though it never reaches tabTitle")


@case
def real_datarules_reaches_a_unit_test_through_dealer() -> None:
    """Class 5, transitive: app/src/kit/dataRules.ts reaches dispenser.unit.ts only through dealer.ts (which
    imports it), and formatter-homes.unit.ts directly."""
    CURRENT[0] = "real_datarules_reaches_a_unit_test_through_dealer"
    scope = [
        expect("from './kit/dataRules'" in (ROOT / "app/src/dealer.ts").read_text(encoding="utf-8"),
               "scope: dealer.ts no longer imports kit/dataRules"),
        expect("../../src/dealer'" in (ROOT / "app/tests/unit/dispenser.unit.ts").read_text(encoding="utf-8"),
               "scope: dispenser.unit.ts no longer imports dealer"),
    ]
    if not all(scope) or not require_selector():
        return
    code, lines, _ = run_selector(["app/src/kit/dataRules.ts"], ROOT)
    if code == 0:
        expect("app/tests/unit/dispenser.unit.ts" in lines, "app/src/kit/dataRules.ts: dispenser.unit.ts is not printed (transitive through dealer.ts)")
        expect("app/tests/unit/formatter-homes.unit.ts" in lines, "app/src/kit/dataRules.ts: formatter-homes.unit.ts is not printed (direct import)")
        # A text read is a leaf: copy-rules reads .tsx text, and a .ts module cannot change that text. The same holds
        # for pricing-send-refusals, which reads SendCard.tsx. Neither imports anything that reaches dataRules.
        expect("app/tests/unit/copy-rules.unit.ts" not in lines, "app/src/kit/dataRules.ts: copy-rules.unit.ts is printed, though its .tsx text reads cannot change with a .ts module")
        expect("app/tests/unit/pricing-send-refusals.unit.ts" not in lines, "app/src/kit/dataRules.ts: pricing-send-refusals.unit.ts is printed, though its one text read cannot change with a .ts module")


@case
def real_orders_helper_read_reaches_formatter_homes() -> None:
    """Class 5, text read through a helper: formatter-homes.unit.ts reads app/src/Orders.tsx as text by
    `src('Orders.tsx')`, and imports nothing that reaches it."""
    CURRENT[0] = "real_orders_helper_read_reaches_formatter_homes"
    if not expect("src('Orders.tsx')" in (ROOT / "app/tests/unit/formatter-homes.unit.ts").read_text(encoding="utf-8"),
                  "scope: formatter-homes.unit.ts no longer reads Orders.tsx by its src() helper") or not require_selector():
        return
    code, lines, _ = run_selector(["app/src/Orders.tsx"], ROOT)
    if code is None:
        expect(False, "app/src/Orders.tsx: the selector did not finish")
        return
    expect(code == 0, f"app/src/Orders.tsx: the selector exited {code}, expected 0")
    expect("app/tests/unit/formatter-homes.unit.ts" in lines, "app/src/Orders.tsx: formatter-homes.unit.ts is not printed (text read by src())")
    expect("app/tests/unit/dispenser.unit.ts" not in lines, "app/src/Orders.tsx: dispenser.unit.ts is printed, though it never reads Orders.tsx")


@case
def real_sendcard_read_by_new_url_reaches_pricing_refusals() -> None:
    """Class 5, text read through `new URL('../../src/SendCard.tsx', import.meta.url)`, which no import rule sees."""
    CURRENT[0] = "real_sendcard_read_by_new_url_reaches_pricing_refusals"
    if not expect("new URL('../../src/SendCard.tsx'" in (ROOT / "app/tests/unit/pricing-send-refusals.unit.ts").read_text(encoding="utf-8"),
                  "scope: pricing-send-refusals.unit.ts no longer reads SendCard.tsx by new URL") or not require_selector():
        return
    code, lines, _ = run_selector(["app/src/SendCard.tsx"], ROOT)
    if code is None:
        expect(False, "app/src/SendCard.tsx: the selector did not finish")
        return
    expect(code == 0, f"app/src/SendCard.tsx: the selector exited {code}, expected 0")
    expect("app/tests/unit/pricing-send-refusals.unit.ts" in lines, "app/src/SendCard.tsx: pricing-send-refusals.unit.ts is not printed (new URL read)")


@case
def real_kit_file_reaches_copy_rules_by_directory_read() -> None:
    """Class 5, directory read: copy-rules.unit.ts reads every .tsx under app/src and app/src/kit by readdirSync."""
    CURRENT[0] = "real_kit_file_reaches_copy_rules_by_directory_read"
    if not expect("readdirSync(resolve(src, 'kit'))" in (ROOT / "app/tests/unit/copy-rules.unit.ts").read_text(encoding="utf-8"),
                  "scope: copy-rules.unit.ts no longer reads the kit folder by readdirSync") or not require_selector():
        return
    code, lines, _ = run_selector(["app/src/kit/index.tsx"], ROOT)
    if code is None:
        expect(False, "app/src/kit/index.tsx: the selector did not finish")
        return
    expect(code == 0, f"app/src/kit/index.tsx: the selector exited {code}, expected 0")
    expect("app/tests/unit/copy-rules.unit.ts" in lines, "app/src/kit/index.tsx: copy-rules.unit.ts is not printed (directory read)")


@case
def real_mjs_script_run_by_subprocess_reaches_tab_title() -> None:
    """Class 3 in TypeScript: tab-title.unit.ts runs scripts/kit-adoption.mjs by a literal path in argv."""
    CURRENT[0] = "real_mjs_script_run_by_subprocess_reaches_tab_title"
    if not expect("'scripts/kit-adoption.mjs'" in (ROOT / "app/tests/unit/tab-title.unit.ts").read_text(encoding="utf-8"),
                  "scope: tab-title.unit.ts no longer runs scripts/kit-adoption.mjs") or not require_selector():
        return
    code, lines, _ = run_selector(["scripts/kit-adoption.mjs"], ROOT)
    if code is None:
        expect(False, "scripts/kit-adoption.mjs: the selector did not finish")
        return
    expect(code == 0, f"scripts/kit-adoption.mjs: the selector exited {code}, expected 0")
    expect("app/tests/unit/tab-title.unit.ts" in lines, "scripts/kit-adoption.mjs: tab-title.unit.ts is not printed (subprocess argv)")
    expect("app/tests/unit/dispenser.unit.ts" not in lines, "scripts/kit-adoption.mjs: dispenser.unit.ts is printed, though it never runs the script")


@case
def real_python_run_by_unit_test_reaches_slab_graders() -> None:
    """Class 3 across languages: slab-graders.unit.ts runs `python3 -c "from store import slabs"` as a subprocess."""
    CURRENT[0] = "real_python_run_by_unit_test_reaches_slab_graders"
    if not expect("from store import slabs" in (ROOT / "app/tests/unit/slab-graders.unit.ts").read_text(encoding="utf-8"),
                  "scope: slab-graders.unit.ts no longer runs store.slabs by a python -c string") or not require_selector():
        return
    code, lines, _ = run_selector(["store/slabs.py"], ROOT)
    if code is None:
        expect(False, "store/slabs.py: the selector did not finish")
        return
    expect(code == 0, f"store/slabs.py: the selector exited {code}, expected 0")
    expect("app/tests/unit/slab-graders.unit.ts" in lines, "store/slabs.py: slab-graders.unit.ts is not printed (python -c subprocess)")


# --------------------------------------------------------------------------------- synthetic trees


_BASE: Dict[str, Path] = {}
_GROUPS: Dict[str, Path] = {}


def base_tree(run: Path) -> Path:
    if "root" not in _BASE:
        _BASE["root"] = write_tree(run / "base", BASE_TREE)
    return _BASE["root"]


def group_tree(run: Path) -> Path:
    if "root" not in _GROUPS:
        _GROUPS["root"] = write_tree(run / "groups", GROUP_TREE)
    return _GROUPS["root"]


@case
def synthetic_direct_import_selects_only_its_module() -> None:
    """Class 1: pipeline/direct_leaf.py is imported by t1 alone; t2 is the far module that must not print. Sparse:
    t1 reads vendor/ and demo-assets/, and the tree has neither."""
    CURRENT[0] = "synthetic_direct_import_selects_only_its_module"
    run = _current_run()
    tree = base_tree(run)
    scope = [expect("pipeline.direct_leaf" in module_level_imports(tree / "harness/tests/t1_direct.py"),
                    "scope: the fixture's t1 lost its direct import")]
    scope.append(expect(not (tree / "vendor").exists() and not (tree / "demo-assets").exists(),
                        "scope: the fixture has a vendor/ or demo-assets/ folder"))
    if not all(scope) or not require_selector():
        return
    select_expect("pipeline/direct_leaf.py", ["pipeline/direct_leaf.py"], tree, ["harness/tests/t1_direct.py"])
    select_expect("pipeline/far_leaf.py", ["pipeline/far_leaf.py"], tree, ["harness/tests/t2_far.py"])


@case
def synthetic_package_import_reaches_through_store_db_and_a_relative_import() -> None:
    """Class 2: store/rows.py is reached by t3 through `store.db` (absolute) and by t4 through `store.relay`
    (relative). t3 never names rows itself."""
    CURRENT[0] = "synthetic_package_import_reaches_through_store_db_and_a_relative_import"
    run = _current_run()
    tree = base_tree(run)
    if not all([
        expect("store.db" in module_level_imports(tree / "harness/tests/t3_package.py"), "scope: t3 no longer imports store.db"),
        expect("store.rows" not in all_imports(tree / "harness/tests/t3_package.py"), "scope: t3 imports store.rows itself, so it does not test the transitive path"),
    ]) or not require_selector():
        return
    select_expect("store/rows.py", ["store/rows.py"], tree,
                  ["harness/tests/t3_package.py", "harness/tests/t4_relative.py"])


@case
def synthetic_subprocess_script_by_literal_path_reaches_its_imports() -> None:
    """Class 3: t5 runs scripts/tool_proc.py through sys.executable and a literal path, and that script imports
    pipeline/proc_leaf.py. The import is reached only through the subprocess."""
    CURRENT[0] = "synthetic_subprocess_script_by_literal_path_reaches_its_imports"
    run = _current_run()
    tree = base_tree(run)
    if not all([expect("'scripts/tool_proc.py'" in (tree / "harness/tests/t5_proc.py").read_text(encoding="utf-8"),
                       "scope: t5 no longer runs scripts/tool_proc.py by literal path")]) or not require_selector():
        return
    select_expect("pipeline/proc_leaf.py", ["pipeline/proc_leaf.py"], tree, ["harness/tests/t5_proc.py"])


@case
def synthetic_banchi_run_reaches_the_cli_it_imports() -> None:
    """Class 3: t6 runs `./banchi`, the extensionless launcher, which imports cli/cli_leaf.py."""
    CURRENT[0] = "synthetic_banchi_run_reaches_the_cli_it_imports"
    run = _current_run()
    tree = base_tree(run)
    if not all([expect("'./banchi'" in (tree / "harness/tests/t6_cli.py").read_text(encoding="utf-8"),
                       "scope: t6 no longer runs ./banchi")]) or not require_selector():
        return
    select_expect("cli/cli_leaf.py", ["cli/cli_leaf.py"], tree, ["harness/tests/t6_cli.py"])


@case
def synthetic_importlib_name_in_a_suite_reaches_the_module_it_names() -> None:
    """Class 3: t8 loads pipeline/dyn_leaf.py with importlib.import_module('...') inside its run()."""
    CURRENT[0] = "synthetic_importlib_name_in_a_suite_reaches_the_module_it_names"
    run = _current_run()
    tree = base_tree(run)
    if not require_selector():
        return
    select_expect("pipeline/dyn_leaf.py", ["pipeline/dyn_leaf.py"], tree, ["harness/tests/t8_dyn.py"])


@case
def synthetic_importlib_name_in_a_product_module_reaches_its_suite() -> None:
    """Class 3, product side: pipeline/lazy_host.py loads pipeline/lazy_leaf.py by importlib at import time, and t9
    imports lazy_host. The name sits in product code, not in the suite."""
    CURRENT[0] = "synthetic_importlib_name_in_a_product_module_reaches_its_suite"
    run = _current_run()
    tree = base_tree(run)
    if not all([expect("import_module('pipeline.lazy_leaf')" in (tree / "pipeline/lazy_host.py").read_text(encoding="utf-8"),
                       "scope: lazy_host.py no longer names lazy_leaf by importlib")]) or not require_selector():
        return
    select_expect("pipeline/lazy_leaf.py", ["pipeline/lazy_leaf.py"], tree, ["harness/tests/t9_host.py"])


@case
def synthetic_unreached_file_is_empty_with_exit_zero() -> None:
    """Class 6: scripts/unreached.py is named by no suite. Its red partner is the full-set case above."""
    CURRENT[0] = "synthetic_unreached_file_is_empty_with_exit_zero"
    run = _current_run()
    tree = base_tree(run)
    if not require_selector():
        return
    code, lines, err = run_selector(["scripts/unreached.py"], tree)
    if code is None:
        expect(False, f"scripts/unreached.py: the selector {err}")
        return
    expect(code == 0, f"scripts/unreached.py: the selector exited {code}, expected 0")
    expect(lines == [], f"scripts/unreached.py: the selector printed {lines[:3]}, expected nothing")


@case
def argument_errors_exit_nonzero() -> None:
    """Only a bad argument exits nonzero: no path, a --root with no value, an unknown flag."""
    CURRENT[0] = "argument_errors_exit_nonzero"
    run = _current_run()
    tree = base_tree(run)
    if not require_selector():
        return
    for label, args in (("no path", []),
                        ("--root with no value", ["pipeline/direct_leaf.py", "--root"]),
                        ("an unknown flag", ["pipeline/direct_leaf.py", "--bogus"])):
        code, _lines, _err = run_selector(args, tree)
        if code is None:
            expect(False, f"{label}: the selector did not finish")
            continue
        expect(code != 0, f"{label}: the selector exited 0, expected nonzero")


@case
def selector_reuses_the_scope_scripts_and_imports_only_the_standard_library() -> None:
    """The contract's reuse rule, read from the selector's source: it loads guard-scope.py and browser-scope.py, it
    defines none of the functions those two already hold, and its imports are standard library plus the two loads."""
    CURRENT[0] = "selector_reuses_the_scope_scripts_and_imports_only_the_standard_library"
    if not require_selector():
        return
    text = SELECTOR.read_text(encoding="utf-8")
    tree = ast.parse(text)
    expect("guard-scope.py" in text, "reuse: the selector does not load scripts/guard-scope.py")
    expect("browser-scope.py" in text, "reuse: the selector does not load scripts/browser-scope.py")
    for copied in ("class _PathCollector", "def derive_subjects", "def _follow_package_imports",
                   "def import_closure", "def file_imports", "def resolve_relative"):
        expect(copied not in text, f"reuse: the selector copies `{copied}` instead of importing it")
    stdlib = set(sys.stdlib_module_names)
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level:
            names = [node.module or ""]
        for name in names:
            top = name.split(".")[0]
            expect(top in stdlib, f"stdlib only: the selector imports `{name}`, which is not standard library")


# --------------------------------------------------------------------------------- T7 granularity (the group tree)


@case
def group_common_import_reaches_every_group_including_ones_that_never_import_it() -> None:
    """Class 4, decided: the hermetic setup's import closure is inherited by every group, so store/shared.py selects
    g_a, g_b and the aggregator. g_b never imports common."""
    CURRENT[0] = "group_common_import_reaches_every_group_including_ones_that_never_import_it"
    run = _current_run()
    tree = group_tree(run)
    if not all([
        expect("harness.tests.t7.common" not in all_imports(tree / "harness/tests/t7/g_b.py"),
               "scope: g_b now imports the hermetic setup, so it no longer tests inheritance"),
        expect("store.shared" in module_level_imports(tree / "harness/tests/t7/common.py"),
               "scope: common.py no longer imports store.shared at module level"),
    ]) or not require_selector():
        return
    select_expect("store/shared.py", ["store/shared.py"], tree,
                  ["harness/tests/t7/g_a.py", "harness/tests/t7/g_b.py", "harness/tests/t7_store_and_seams.py"])


@case
def group_helper_loaded_at_import_time_is_inherited_and_the_helper_is_no_suite() -> None:
    """Class 4, decided: helper.py has no CHECKS, so it is never a suite, but g_a loads it at import time, so
    pipeline/helper_leaf.py reaches every group."""
    CURRENT[0] = "group_helper_loaded_at_import_time_is_inherited_and_the_helper_is_no_suite"
    run = _current_run()
    tree = group_tree(run)
    if not all([expect("CHECKS" not in (tree / "harness/tests/t7/helper.py").read_text(encoding="utf-8"),
                       "scope: helper.py now defines CHECKS")]) or not require_selector():
        return
    select_expect("pipeline/helper_leaf.py", ["pipeline/helper_leaf.py"], tree,
                  ["harness/tests/t7/g_a.py", "harness/tests/t7/g_b.py", "harness/tests/t7_store_and_seams.py"])


@case
def group_check_body_import_reaches_only_its_group() -> None:
    """Class 4, decided: g_a loads pipeline/only_a.py inside check_a. Only g_a, and the aggregator that runs it."""
    CURRENT[0] = "group_check_body_import_reaches_only_its_group"
    run = _current_run()
    tree = group_tree(run)
    if not all([expect("from pipeline import only_a" in (tree / "harness/tests/t7/g_a.py").read_text(encoding="utf-8"),
                       "scope: g_a no longer loads only_a inside a check")]) or not require_selector():
        return
    select_expect("pipeline/only_a.py", ["pipeline/only_a.py"], tree,
                  ["harness/tests/t7/g_a.py", "harness/tests/t7_store_and_seams.py"])


@case
def group_non_suite_module_reaches_the_aggregator_not_itself() -> None:
    """Class 4, decided: t7_box_map.py has CHECKS but no run, so it is no suite. The aggregator imports it inside
    run(), so pipeline/boxmap_leaf.py prints the aggregator alone."""
    CURRENT[0] = "group_non_suite_module_reaches_the_aggregator_not_itself"
    run = _current_run()
    tree = group_tree(run)
    if not all([expect(not defines_top_level(tree / "harness/tests/t7_box_map.py", "run"),
                       "scope: t7_box_map.py now defines run, so it is a suite")]) or not require_selector():
        return
    select_expect("pipeline/boxmap_leaf.py", ["pipeline/boxmap_leaf.py"], tree, ["harness/tests/t7_store_and_seams.py"])


@case
def group_aggregator_module_import_is_inherited_by_every_group() -> None:
    """Class 4, decided: the aggregator loads cli/resolve_like.py at import time, and every group run loads the
    aggregator first, so every group reaches it."""
    CURRENT[0] = "group_aggregator_module_import_is_inherited_by_every_group"
    run = _current_run()
    tree = group_tree(run)
    if not require_selector():
        return
    select_expect("cli/resolve_like.py", ["cli/resolve_like.py"], tree,
                  ["harness/tests/t7/g_a.py", "harness/tests/t7/g_b.py", "harness/tests/t7_store_and_seams.py"])


# --------------------------------------------------------------------------------- --root reads the tree it is pointed at


@case
def root_reads_the_tree_it_is_pointed_at() -> None:
    """Class 8: --root wins over the cwd. With --root naming the fixture, a file the fixture holds and the checkout
    does not selects from the fixture, from an unrelated cwd. With --root naming a tree without the file's importer,
    the same file selects nothing, even from a cwd that is the fixture."""
    CURRENT[0] = "root_reads_the_tree_it_is_pointed_at"
    run = _current_run()
    tree = base_tree(run)
    if not all([
        expect((tree / "pipeline/direct_leaf.py").is_file(), "scope: the fixture lost pipeline/direct_leaf.py"),
        expect(not (ROOT / "pipeline/direct_leaf.py").exists(), "scope: the checkout holds pipeline/direct_leaf.py, so the case proves nothing"),
        expect((ROOT / "pipeline/walkplan.py").is_file() and not (tree / "pipeline/walkplan.py").exists(),
               "scope: the checkout and the fixture do not differ on pipeline/walkplan.py"),
    ]) or not require_selector():
        return
    # --root from a folder that is neither the checkout nor the fixture: the answer comes from --root alone.
    select_expect("--root names the fixture", ["pipeline/direct_leaf.py", "--root", str(tree)], run,
                  ["harness/tests/t1_direct.py"])
    code, lines, err = run_selector(["pipeline/walkplan.py", "--root", str(tree)], run)
    if code is None:
        expect(False, f"--root names the fixture, walkplan.py: the selector {err}")
    else:
        expect(lines == [], f"--root names the fixture: pipeline/walkplan.py is printed from the checkout, not the fixture: {lines[:3]}")
    # --root beats the cwd: run inside the fixture, but name a tree that holds the file and not its importer.
    bare = write_tree(run / "no-importer", {"pipeline/direct_leaf.py": "VALUE = 1\n"})
    code, lines, err = run_selector(["pipeline/direct_leaf.py", "--root", str(bare)], tree)
    if code is None:
        expect(False, f"--root beats the cwd: the selector {err}")
    else:
        expect(code == 0, f"--root beats the cwd: the selector exited {code}, expected 0 ({err.strip()[-200:]})")
        expect(lines == [], f"--root beats the cwd: the selector read the cwd, not --root, and printed {lines[:3]}")


# --------------------------------------------------------------------------------- planted breaks (bounded)


@case
def planted_break_python_selected_red_unselected_green_clean_green() -> None:
    """Class 7, Python leg. A real product file, pipeline/namefold.py, copied verbatim into a run folder with one fast
    suite that loads it (t9_fast) and one unrelated (t2_other). The selector names t9_fast; a raise in namefold turns
    t9_fast red and leaves t2_other green; the clean tree is green. Bounded: two small modules, no store, no server."""
    CURRENT[0] = "planted_break_python_selected_red_unselected_green_clean_green"
    run = _current_run()
    tree = write_tree(run / "plant-py", PLANT_TREE_TESTS)
    real = ROOT / "pipeline/namefold.py"
    clean_text = real.read_text(encoding="utf-8")
    shutil.copyfile(real, tree / "pipeline/namefold.py")
    if not all([expect("def fold_name_typography(text) -> str:" in clean_text,
                       "scope: pipeline/namefold.py no longer defines fold_name_typography")]) or not require_selector():
        return
    code, lines, err = run_selector(["pipeline/namefold.py", "--root", str(tree)], run)
    if code is None or code != 0:
        expect(False, f"planted break: the selector exited {code}, expected 0 ({err.strip()[-160:]})")
        return
    expect(sorted(lines) == ["harness/tests/t9_fast.py"],
           f"planted break: the selector printed {lines[:3]}, expected only harness/tests/t9_fast.py")
    code, out = suite_green(tree, "harness.tests.t9_fast")
    expect(code == 0, f"planted break, clean tree: the selected suite is not green (exit {code}): {out[-160:]}")
    code, out = suite_green(tree, "harness.tests.t2_other")
    expect(code == 0, f"planted break, clean tree: the unselected suite is not green (exit {code}): {out[-160:]}")
    planted = clean_text.replace("def fold_name_typography(text) -> str:",
                                 "def fold_name_typography(text) -> str:\n    raise RuntimeError('planted: pipeline/namefold.py')", 1)
    (tree / "pipeline/namefold.py").write_text(planted, encoding="utf-8")
    code, out = suite_green(tree, "harness.tests.t9_fast")
    expect(code != 0, "planted break: the selected suite t9_fast stayed green with a raise in its module")
    code, out = suite_green(tree, "harness.tests.t2_other")
    expect(code == 0, f"planted break: the unselected suite t2_other went red (exit {code}): {out[-160:]}")


@case
def planted_break_typescript_selected_red_unselected_green_clean_green() -> None:
    """Class 7, TypeScript leg. A copy of app/ (node_modules linked from the checkout) and scripts/kit-adoption.mjs,
    which tab-title.unit.ts runs. The selector names tab-title for app/src/tabTitle.ts; a throw at the end of
    tabTitle.ts turns tab-title red and leaves dispenser green. Needs `npm ci --prefix app`."""
    CURRENT[0] = "planted_break_typescript_selected_red_unselected_green_clean_green"
    run = _current_run()
    node_modules = ROOT / "app/node_modules"
    if not all([expect(node_modules.is_dir(), "app/node_modules is missing: run `npm ci --prefix app` first")]):
        return
    if not require_selector():
        return
    code, lines, err = run_selector(["app/src/tabTitle.ts"], ROOT)
    if code != 0:
        expect(False, f"planted break (TypeScript): the selector exited {code}, expected 0 ({err.strip()[-160:]})")
        return
    selected = [line for line in lines if line.endswith(".unit.ts")]
    if not expect("app/tests/unit/tab-title.unit.ts" in selected, "planted break (TypeScript): the selector did not name tab-title.unit.ts"):
        return
    unselected = ["app/tests/unit/dispenser.unit.ts"]
    copy = run / "plant-ts"
    shutil.copytree(ROOT / "app", copy / "app",
                    ignore=shutil.ignore_patterns("node_modules", "public", "dist", "test-results", "playwright-report"))
    os.symlink(node_modules, copy / "app" / "node_modules", target_is_directory=True)
    (copy / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "scripts/kit-adoption.mjs", copy / "scripts/kit-adoption.mjs")
    for suite in selected + unselected:
        code, out = unit_run(copy, suite)
        expect(code == 0, f"planted break (TypeScript), clean tree: {suite} is not green (exit {code}): {out[-160:]}")
    tab = copy / "app/src/tabTitle.ts"
    tab.write_text(tab.read_text(encoding="utf-8") + "\nthrow new Error('planted: app/src/tabTitle.ts')\n", encoding="utf-8")
    code, out = unit_run(copy, "app/tests/unit/tab-title.unit.ts")
    expect(code != 0, "planted break (TypeScript): the selected suite tab-title.unit.ts stayed green with a throw in tabTitle.ts")
    code, out = unit_run(copy, "app/tests/unit/dispenser.unit.ts")
    expect(code == 0, f"planted break (TypeScript): the unselected suite dispenser.unit.ts went red (exit {code}): {out[-160:]}")


def unit_run(copy: Path, suite: str) -> Tuple[Optional[int], str]:
    """One unit file, run the way the consumer runs it: the Playwright unit config, from the app folder."""
    rel = os.path.relpath(copy / suite, copy / "app")
    try:
        done = subprocess.run(["node", "node_modules/@playwright/test/cli.js", "test", "-c", "playwright.unit.config.ts", rel],
                              cwd=str(copy / "app"), capture_output=True, text=True, timeout=UNIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, "timed out"
    return done.returncode, (done.stdout + done.stderr).strip()


# --------------------------------------------------------------------------------- runner


_RUN: List[Path] = []


def _current_run() -> Path:
    return _RUN[0]


def main() -> int:
    with run_folder() as run:
        _RUN.append(run)
        for name, fn in CASES:
            before = len(FAILED)
            CURRENT[0] = name
            try:
                fn()
            except Exception as exc:  # a bug in this file is a failure of its case, never a pass
                expect(False, f"test error: {exc!r}")
            mine = [cause for case_name, cause in FAILED[before:]]
            print(("FAIL  " if mine else "ok    ") + name)
            for cause in mine:
                print("      " + cause)
    print("%d of %d cases failed" % (len({c for c, _ in FAILED}), len(CASES)) if FAILED else "all %d cases passed" % len(CASES))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
