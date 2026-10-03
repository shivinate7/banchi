"""Invariants read out of code: layering, writers, wire keys, column counts, concurrency."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

from .core import (
    Finding,
    MECHANICAL,
    ROOT,
    Report,
    Row,
    UNSCOPED_WALK_ALLOWED,
    UNSCOPED_WALK_EXPECTED,
    _NUMBER_WORDS,
    _merge_rows,
    _strip_ts_comments,
    _walk,
    exists,
    literals_from_module,
    markdown_files,
    read,
    rel,
)
from .records import _debts_section

_SERVER_CLASS_RE = re.compile(r"^class CaptureServer\((\w+)\):", re.M)
_HANDLER_TIMEOUT_RE = re.compile(r"^    timeout = (\d+)$", re.M)
_BACKLOG_RE = re.compile(r"^    request_queue_size = (\d+)$", re.M)
_SLOTS_RE = re.compile(r"^REQUEST_SLOTS = (\d+)$", re.M)
_PHOTO_SLOTS_RE = re.compile(r"^PHOTO_SLOTS = (\d+)$", re.M)

# WHAT SECTION 11 HAS TO SAY, AND IN WHAT SHAPE. Each row is (what, code pattern, code shape,
# DOC-SIDE ANCHOR, the published form). The anchor is the half that was missing: it captures
# the figure from a position that names the fact, so the comparison is between two CLAIMS
# rather than between a number and a section that happens to contain it.
_CONCURRENCY_FACTS = (
    ("the base class", _SERVER_CLASS_RE, "class CaptureServer(<base>)",
     re.compile(r"class CaptureServer\((\w+)\)"), "class CaptureServer(<base>)"),
    ("the handler's socket timeout", _HANDLER_TIMEOUT_RE, "timeout = <seconds>",
     re.compile(r"CaptureHandler\.timeout = (\d+)"), "CaptureHandler.timeout = <seconds>"),
    ("the accept backlog", _BACKLOG_RE, "request_queue_size = <n>",
     re.compile(r"request_queue_size = (\d+)"), "request_queue_size = <n>"),
    ("the bound on executing requests", _SLOTS_RE, "REQUEST_SLOTS = <n>",
     re.compile(r"REQUEST_SLOTS = (\d+)"), "REQUEST_SLOTS = <n>"),
    ("the bound on the photo lane", _PHOTO_SLOTS_RE, "PHOTO_SLOTS = <n>",
     re.compile(r"PHOTO_SLOTS = (\d+)"), "PHOTO_SLOTS = <n>"),
)


def _close_header_owner() -> Optional[str]:
    """The method that sends `Connection: close`, or None if nothing does.

    A NAME AND NOT A LINE NUMBER, because the name is the fact section 11 rests on. The pool
    is only safe over HTTP/1.1 because a worker's life is one REQUEST rather than one
    connection, and what makes that true is that every response carries this header. Sending
    it from `_send` was not enough — `_photo`'s 304 branch answers a conditional GET by hand
    and never goes through `_send` — so it moved to `end_headers`, which every response
    reaches by construction. Which method it is IS the guarantee: back in `_send`, the same
    header is a convention any new route can forget.
    """
    try:
        tree = ast.parse(read(ROOT / "server" / "capture_server.py"))
    except (SyntaxError, OSError):
        return None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            func = inner.func
            if not isinstance(func, ast.Attribute) or func.attr != "send_header":
                continue
            literals = [
                arg.value.lower()
                for arg in inner.args
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            ]
            if literals[:2] == ["connection", "close"]:
                return node.name
    return None


# Where a claim about the history's readers may live, and where its readers may live. Both
# lists are the production tree only: the harness reads the history constantly and correctly,
# and counting those would make the number meaningless.
_HISTORY_READER_ROOTS = ("server", "store", "pipeline", "cli", "identify", "geometry", "codes")
# BOTH WORD ORDERS. The name comes before the claim in `\`f\` — the only reader of X` and after
# it in `the only reader of X is \`f\``, and the first pattern written here caught only the
# first. Section 8 carried the second form for three weeks after the identical sentence was
# corrected twice elsewhere, which is the whole argument for reading prose by shape rather than
# fixing the instances somebody happened to grep for.
# WHOLE-FILE AND NOT LINE BY LINE, which is the second thing this pattern got wrong. Every
# markdown file in this repo wraps at 96 columns, so a claim of any length is USUALLY split
# across two lines — section 8's instance sat on a wrap with "the" ending one line and "only
# reader" starting the next, and a line-at-a-time reader cannot see it. A checker over prose
# that reads lines is checking typography, not sentences. `.` is excluded so a match cannot
# run past the end of its own sentence.
_SOLE_READER_RE = re.compile(
    r"`([A-Za-z_][A-Za-z0-9_]*)`[^.]{0,40}?the\s+only\s+reader"
    r"|the\s+only\s+reader[^.]{0,60}?is\s+`([A-Za-z_][A-Za-z0-9_]*)`",
    re.S,
)


def _history_readers() -> List[str]:
    """Every production call of the store's `history()`, as `path:line in function`.

    ZERO-ARGUMENT CALLS ONLY, and that is the whole disambiguation rather than a heuristic:
    `Store.history()` takes none, and `pipeline/pricehistory.py`'s unrelated method of the
    same name takes a product and a range. Matching on the name alone counts two price-history
    calls as readers of the card history and makes the number a lie in the other direction.
    """
    readers: List[str] = []
    for root in _HISTORY_READER_ROOTS:
        base = ROOT / root
        if not exists(base):
            continue
        for path in _walk(base, (".py",)):
            try:
                tree = ast.parse(read(path))
            except SyntaxError:
                continue
            owner: Dict[int, str] = {}
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for inner in ast.walk(node):
                        line = getattr(inner, "lineno", None)
                        if line is not None:
                            owner.setdefault(line, node.name)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not isinstance(func, ast.Attribute) or func.attr != "history":
                    continue
                if node.args or node.keywords:
                    continue
                where = owner.get(node.lineno, "<module>")
                if where == "history":  # the definition in store/, not a call of it
                    continue
                readers.append(f"{rel(path)}:{node.lineno} in {where}")
    return sorted(readers)


# The three roots the plan names, in the order they are read. server/ is a FLAT
# directory (no subpackages as of 2026-09-12 — capture_server.py, pipeline_routes.py,
# codes_routes.py, order_transport.py, ports.py, shipping_routes.py, tcg_export.py,
# tcg_import.py), so `_walk(ROOT / "server", (".py",))` is exactly "server/*.py" and
# never needs to recurse into a package that does not exist yet. `store/master.py` and
# `cli/resolve.py` are named as single files because the plan is explicit that only
# `master.py` (the Inventory/Card schema) is in scope inside `store/` — `store/rows.py`,
# `store/db.py` and `store/queues.py` all touch rows too, but not `inventory.cards`
# directly, and widening the walk to all of `store/` would flag `Rows` itself defining
# `.values()`/`.items()` as their OWN implementation, which is not a call site at all.
_UNSCOPED_WALK_ROOTS: Tuple[Path, ...] = (
    ROOT / "server",
)
_UNSCOPED_WALK_SINGLE_FILES: Tuple[Path, ...] = (
    ROOT / "store" / "master.py",
    ROOT / "cli" / "resolve.py",
)

# The three method names that always materialise every row when called on something
# ending in `.cards` (`Rows` is a `MutableMapping`; these three take no filter argument
# under any Rows signature — see `store/rows.Rows`), plus `select`, which only
# materialises everything when called with NO keyword arguments (a keyword is a filter:
# `equals` in `Rows.select`).
_UNSCOPED_METHODS = frozenset({"values", "items", "distinct"})


def _enclosing_functions(tree: ast.AST) -> Dict[int, str]:
    """line number -> the name of the FunctionDef/AsyncFunctionDef that contains it.

    Same shape as `_history_readers`'s own inline dict-building loop above, pulled out
    here because this scanner needs it twice (once per file) and gains nothing from
    inlining it a second time.
    """
    owner: Dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                line = getattr(inner, "lineno", None)
                if line is not None:
                    owner.setdefault(line, node.name)
    return owner


def _cards_chain(node: ast.AST) -> bool:
    """Does this call's receiver end in `.cards`? `inventory.cards`, `self.cards`,
    `store.read().inventory.cards` — any depth, only the last hop matters."""
    return isinstance(node, ast.Attribute) and node.attr == "cards"


def _inventory_like(node: ast.AST) -> bool:
    """Does this call's receiver look like an `Inventory` instance? Heuristic, and named
    as one: matches a bare `inventory` name or a `.inventory` attribute, which is the
    variable name this repo uses everywhere an `Inventory` is bound (`Store().read().inventory`,
    `self.inventory`). This is what keeps `to_payload()` from also matching
    `book.to_payload()` / `entry.to_payload()` elsewhere in the same files, which are a
    different class's method of the same name."""
    if isinstance(node, ast.Name):
        return node.id == "inventory"
    if isinstance(node, ast.Attribute):
        return node.attr == "inventory"
    return False


def unscoped_walk_sites(paths: Sequence[Path]) -> List[Tuple[str, int, str, str]]:
    """Every call in `paths` that materialises the whole `inventory.cards` collection.

    Returns (path relative to ROOT, line number, enclosing function name, shape) tuples,
    where shape is one of "values", "items", "distinct", "select", "to_payload". Pure —
    no Report, no filesystem side effects beyond reading `paths` — so `--self-test` can
    hand it a synthetic fixture file and assert on the return value directly, the same
    shape `_payload_keys` and `mechanism_refs` are tested in already.

    WHAT THIS CANNOT SEE, and it says so rather than pretending completeness:
    `store/rows.Rows`'s `_load_all` degradation — a `where()`/`select()` call that LOOKS scoped but
    answers from a Python-side list because an earlier call in the same request already
    materialised everything — is invisible here. This function reads one file at a time
    with no notion of a request's call order, so it cannot tell a `where()` that hits the
    index from one that is quietly a full scan because of what ran before it in the same
    handler. Item 2 removes the degradation itself; this row is a static shape reader and
    will keep reporting a `where()`-only handler as clean before and after that fix,
    correctly, because the shape on the page never changes — only what it costs at
    runtime does.
    """
    sites: List[Tuple[str, int, str, str]] = []
    for path in paths:
        if not exists(path):
            continue
        try:
            tree = ast.parse(read(path))
        except SyntaxError:
            continue
        owner = _enclosing_functions(tree)
        where = rel(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue
            fname = owner.get(node.lineno, "<module>")
            if func.attr in _UNSCOPED_METHODS and _cards_chain(func.value):
                sites.append((where, node.lineno, fname, func.attr))
            elif func.attr == "select" and _cards_chain(func.value) and not node.keywords:
                sites.append((where, node.lineno, fname, "select"))
            elif func.attr == "to_payload" and _inventory_like(func.value):
                sites.append((where, node.lineno, fname, "to_payload"))
    return sites


def check_unscoped_walk(report: Report) -> None:
    """Every full-table read of `inventory.cards`, against an allowlist that starts at
    the 2026-09-12 census and may only shrink.

    Almost every non-capture handler in `server/` once materialised the whole `cards`
    table and then did per-card work over it, and at 50,000 cards several of those routes
    cost seconds rather than milliseconds. This row checks every removal of a full-table
    read against something, so none lands with no reader — the exact shape
    `docs/GATES.md` step 7's own finding names, one register down.

    THREE KINDS OF DISAGREEMENT, exactly `check_storage_keys`'s shape:
      - a site this file scans and finds, not on the allowlist: a NEW full-table read.
      - an allowlist entry naming a (path, function, shape) this scan does not find: a
        REMOVED site whose allowlist entry was not deleted in the same commit — this is
        the failure mode item 1's own spec text calls out by name ("a removed site is
        removed from the list in the same PR or the row reports a stale allowlist entry").
      - the allowlist's length disagreeing with `UNSCOPED_WALK_EXPECTED`: the same pinned-
        number discipline `check_rule_enforcement` uses, so a mutation cannot silently
        drop an entry and leave the printed count claiming coverage it no longer has.

    `do_inventory`'s `to_payload()` call is the one entry that can never be removed: the
    owner ruled that `GET /inventory` stays on the
    wire, unused, rather than being deleted once the scoped `GET
    /inventory/<box>` landed. Nothing in this function treats it specially — it is simply an
    entry nothing will ever delete, which is why `UNSCOPED_WALK_EXPECTED`'s floor never
    reaches zero.

    WHAT IT CANNOT SEE: `store/rows.Rows`'s `_load_all` runtime degradation (a call that reads
    scoped in the source and answers unscoped at runtime because an earlier call in the
    same request already loaded everything) — see `unscoped_walk_sites`'s own docstring,
    which item 2 is what actually removes. This row reads Python source shapes, never
    request traces.
    """
    server_files = _walk(_UNSCOPED_WALK_ROOTS[0], (".py",))
    found = set(unscoped_walk_sites(server_files + list(_UNSCOPED_WALK_SINGLE_FILES)))
    allowed = UNSCOPED_WALK_ALLOWED
    findings: List[Finding] = []

    for path, line, fname, shape in sorted(found):
        if (path, fname, shape) not in allowed:
            findings.append(Finding(
                f"{path}:{line}",
                f"`{fname}` calls `.{shape}(...)` on a collection that ends in "
                f"`.cards` (or `to_payload()` on an `Inventory`), materialising every "
                f"row in the store.\n"
                f"  If this is a genuine new full-table read, either scope it — a "
                f"`where(...)`/`select(..., **filter)` with an index, or a per-box read "
                f"through `records_in` — or add `(\"{path}\", \"{fname}\", \"{shape}\") "
                f"to `UNSCOPED_WALK_ALLOWED` and raise `UNSCOPED_WALK_EXPECTED` by one, "
                f"with the reason in the commit message. this "
                f"matters: every one of these costs proportionally more as "
                f"the store grows, and none of it shows up until it does.",
            ))

    scanned_keys = {(path, fname, shape) for path, _, fname, shape in found}
    for path, fname, shape in sorted(allowed):
        if (path, fname, shape) not in scanned_keys:
            findings.append(Finding(
                path,
                f"the allowlist names `{fname}` (`.{shape}(...)`) and this scan finds no "
                f"such call there any more.\n"
                f"  Either the function moved to a shape this reader does not recognise, "
                f"or a full-table read was genuinely removed and the allowlist entry was "
                f"not deleted with it. Delete the entry and lower "
                f"`UNSCOPED_WALK_EXPECTED` in the same commit, or say why the shape "
                f"changed and update the tuple.",
            ))

    if len(allowed) != UNSCOPED_WALK_EXPECTED:
        findings.append(Finding(
            "scripts/docs_audit/core.py -> UNSCOPED_WALK_ALLOWED",
            f"has {len(allowed)} entries where {UNSCOPED_WALK_EXPECTED} are pinned. The "
            f"count is the plan's progress meter: raise "
            f"`UNSCOPED_WALK_EXPECTED` only alongside a NEW site you are deliberately "
            f"keeping (say why), and lower it in the same commit that deletes a site the "
            f"tree no longer has.",
        ))

    report.add(
        "unscoped walk",
        MECHANICAL,
        findings,
        f"{len(found)} full-table reads of inventory.cards found, "
        f"{len(allowed)} allowed (pinned at {UNSCOPED_WALK_EXPECTED})",
        scanned=len(found),
    )


def _pipeline_imports(path: Path) -> List[Tuple[int, str]]:
    """`(line, spelling)` for every `import pipeline...` / `from pipeline...` in one file.

    MODULE-LEVEL OR INSIDE A FUNCTION — a lazy `from pipeline import join` hidden in a
    function body is the exact shape the search-index step shipped (`store/db.py:
    _add_search_index`) and it does not show at the top of the file, so `ast.walk` over
    the whole tree (not just `tree.body`) is what a grep-the-top-lines reader would miss.
    A relative import (`from . import x`, `node.level > 0`) is never `pipeline` and is
    skipped without inspecting `node.module`, which is `None` for a bare `from . import x`.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []
    found: List[Tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pipeline" or alias.name.startswith("pipeline."):
                    found.append((node.lineno, f"import {alias.name}"))
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module
            and (node.module == "pipeline" or node.module.startswith("pipeline."))
        ):
            names = ", ".join(alias.name for alias in node.names)
            found.append((node.lineno, f"from {node.module} import {names}"))
    return found


def check_import_layering(report: Report) -> None:
    """`store/` may not import `pipeline/` (D63): the arrow runs one way only.

    `docs/decisions/D063-…md` and `docs/map.py`'s `pipeline/orders.py` entry both record
    it in the same words — "store/ imports nothing from pipeline/, so there is no cycle" —
    because `pipeline/orders.py`, `pipeline/readings.py` and `pipeline/selection.py` all
    import `store`, and a `store -> pipeline -> store` cycle is exactly the shape that
    keeps a session from being able to reason about which module can see which.

    NOTHING ENFORCED THIS MECHANICALLY UNTIL NOW, WHICH IS WHY IT WAS BROKEN THE SAME DAY
    IT WAS WRITTEN DOWN AGAIN. Store-scaling item 8 (search on FTS5) needed
    `pipeline/join.py`'s `join_key`/`display_number` to populate two new indexed columns
    and added `store/master.py: from pipeline import join` (module-level) and
    `store/db.py: from pipeline import join as _join` (inside `_add_search_index`) —
    `make check` was fully green through both, because nothing read this rule. The fix
    (this same PR) moved the three pure functions (`join_key`, `display_number`,
    `strip_set_code`) to a new leaf module, `store/numbers.py` (stdlib only), and
    `pipeline/join.py` imports them back and re-exports under the same names so every
    existing caller of `join.join_key` etc. is unaffected — CLAUDE.md's "a rule with no
    reader is advice" (D173), applied to itself: the fix is not this row alone.

    A LAZY IMPORT INSIDE A FUNCTION IS CAUGHT THE SAME AS A MODULE-LEVEL ONE, because that
    is exactly the shape the defect took (`store/db.py:_add_search_index`'s
    `from pipeline import join as _join`, several hundred lines into the file, inside a
    function body — invisible to a reader who only checks the top of the file).

    WHAT IT CANNOT SEE: an import reached through a third module (`store/x.py` imports
    `store/y.py`, which imports `pipeline/`) — this row scans only the text of `store/*.py`
    files for a direct `pipeline` reference, not the transitive closure of what a module
    ends up able to reach. `store/master.py`/`store/db.py`/`store/numbers.py` are the only
    modules under `store/` this repo has ever needed `pipeline/` symbols from, so a
    transitive leak would still show up as a NEW direct import somewhere the day it
    happens, which this row would catch then.
    """
    store_files = _walk(ROOT / "store", (".py",))
    findings: List[Finding] = []
    for path in store_files:
        for lineno, spelling in _pipeline_imports(path):
            findings.append(Finding(
                f"{rel(path)}:{lineno}",
                f"`{spelling}` — store/ may not import pipeline/ (D63: the arrow runs the "
                f"other way, pipeline/orders.py and friends import store/). Move the "
                f"symbol(s) needed into a leaf module under store/ (store/numbers.py is "
                f"the precedent) and have pipeline/ import them back and re-export, or "
                f"resolve the value in the caller before it reaches store/.",
            ))
    report.add(
        "import layering",
        MECHANICAL,
        findings,
        f"{len(store_files)} store/ files scanned, 0 import pipeline/" if not findings
        else f"{len(store_files)} store/ files scanned, {len(findings)} import pipeline/",
        scanned=len(store_files),
    )


def check_error_words(report: Report) -> None:
    """The refusal messages a screen prints word for word obey D196 too.

    `no mechanism on screen` reads JSX literals and `text-checks.spec.ts` reads loaded
    screens, so neither ever sees a REFUSAL: those strings live in `server/*.py` and in
    `app/src/server.ts`'s `ServerError` calls. `scripts/error-words.py` reads them at the
    source, so this row needs no browser. It fails on a message carrying a backtick, a
    decision id, a repository path, a snake_case token, an HTTP detail, raw exception text or a
    typed dot, and on an allow-list entry that matches nothing (`scripts/error-words-allow.json`).
    """
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "error-words.py")],
        capture_output=True, text=True, cwd=ROOT,
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip() and ln != "error-words: ok"]
    findings = [Finding(ln.split(":", 1)[0], ln) for ln in lines]
    if proc.returncode != 0 and not findings:
        findings.append(Finding("scripts/error-words.py", f"could not run: {proc.stderr.strip()[:200]}"))
    report.add(
        "error words",
        MECHANICAL,
        findings,
        "every refusal message in server/ and server.ts is plain, the allow list has no stale entry"
        if not findings else f"{len(findings)} refusal message(s) break D196",
        scanned=1,
    )


# docs/specs/identity-follows-sku.md §4.1/§4.3 (lane 7): the directories a real card mutation
# can reach — the same six the spec's own text names for this row.
_IDENTITY_WRITERS_ROOTS = ("server", "store", "pipeline", "cli", "codes", "scripts")

# EMPTY, AND PINNED AT ZERO. The two entries lane 7 pinned here were
# `cli/cmd_cards.py:_variants`'s direct `set_name`/`rarity` writes. That press is now a
# stub that refuses and names `cards identity --write` (identity-follows-sku.md §4.2:
# "retired"), so the list is empty. `UNSCOPED_WALK_ALLOWED`'s own idiom: an entry here is a
# debt this row can SEE, never one it hides, and the ratchet below cannot silently grow.
IDENTITY_WRITERS_ALLOWED: FrozenSet[Tuple[str, str, str]] = frozenset()
IDENTITY_WRITERS_ALLOWED_EXPECTED = 0


def _identity_field_assignments(
    path: Path, fields: FrozenSet[str]
) -> List[Tuple[int, Optional[str], Optional[str], str]]:
    """Every `card.<field> = ...` (or `+=`) in `path`, for a `field` in `fields`, tagged with
    the enclosing class and function ('' / None at module scope) — so the caller can tell a
    sanctioned writer's own body from everywhere else, `_pipeline_imports`'s own shape
    (module-level or nested, a lazy write hidden in a function body is exactly the risk).

    ONLY A BASE NAMED EXACTLY `card` COUNTS. Measured over every file under `server/`,
    `store/`, `pipeline/`, `cli/`, `codes/` and `scripts/`: every genuine `Card` mutation in
    the tree already uses that one local name, and filtering on it is what keeps this row
    from flooding on an unrelated class that happens to share a field name — `Row.sku` in
    `scripts/demo-seed.py`, `Box.name`, `Listing.condition`, a test fixture's own
    `automatic_card.rarity` in `scripts/identity-binding-selftest.py`. WHAT IT CANNOT SEE: a
    real `Card` write through a variable named anything else. None exists in the scanned
    roots today — `harness/tests/` fixtures use `resolved`/`ghost`/`transplant` and are not
    scanned at all (outside the six roots) — so this is a live gap, stated rather than
    quietly closed by a cleverer reader that would cost this row its whole simplicity.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []
    found: List[Tuple[int, Optional[str], Optional[str], str]] = []

    def visit(node: ast.AST, cls: Optional[str], func: Optional[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, child.name, None)
                continue
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, cls, child.name)
                continue
            if isinstance(child, (ast.Assign, ast.AugAssign)):
                targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                for target in targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and target.attr in fields
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "card"
                    ):
                        found.append((child.lineno, cls, func, target.attr))
            visit(child, cls, func)

    visit(tree, None, None)
    return found


def check_identity_writers(report: Report) -> None:
    """docs/specs/identity-follows-sku.md §4.1/§4.3 (lane 7): ONE WRITER, CHECKED BY A
    MACHINE (CLAUDE.md D173: "a rule that can be mechanically enforced must be").
    `store/master.py` exports two constants this row reads — never copies — `IDENTITY_
    FIELDS` (the eleven identity/binding fields) and `IDENTITY_WRITERS` (the method names
    allowed to assign one). A `card.<field> = ...` anywhere else under `server/`, `store/`,
    `pipeline/`, `cli/`, `codes/` or `scripts/` is this row's own defect to report.

    SIX WRITERS ARE SANCTIONED, NOT THE FOUR LANE 7'S OWN BRIEF NAMED (`bind_sku`,
    `unbind_sku`, `restore_identity`, and `hold_sku`, this lane's own addition) — and that
    gap is worth stating rather than quietly resolved either way (CLAUDE.md: "surface
    ambiguity instead of resolving it silently"). Two more are PRE-EXISTING, ALREADY-
    ARGUED holdovers from earlier lanes, each with its own docstring in `store/master.py`
    making the case this row only points at: `record_identification` ("not a second writer
    of the identity — it is the same writer bind_sku becomes the moment a binding exists,
    continuous rather than switched") and `move_card` (D83's tombstone clear, spec §4.2:
    "clears sku and condition on the tombstone... unchanged"). `set_state` WAS A THIRD
    HOLDOVER, ITS OWN DOCSTRING ONCE READING "A DEVIATION... FLAGGED RATHER THAN MADE
    SILENTLY" — commit `66442b32` closed it: its five identity parameters are gone, and it
    is no longer in `IDENTITY_WRITERS`. A row that recognised only the four lane 7's brief
    named would fail the merged tree on sight, over writes two earlier review rounds already
    settled — `IDENTITY_WRITERS` in `store/master.py` is the constant that says so, not this
    file.

    ONLY A `card.<field>` ASSIGNMENT COUNTS — see `_identity_field_assignments`'s own
    docstring for the heuristic and what it cannot see. `IDENTITY_WRITERS_ALLOWED` above is
    a SEPARATE, RATCHETED exception list, `UNSCOPED_WALK_ALLOWED`'s own idiom. It is empty
    and pinned at zero since `cards variants` retired — see that constant's own comment.

    TRUSTED ONLY ONCE IT GOES RED ON THE DEFECT IT GUARDS (owner's rule): a planted
    `card.name = "whatever"` inside `cli/cmd_cards.py`'s `_audit` function is how this row
    was proved, by hand, before this docstring was written — never checked in, because a
    fixture that stayed would be the violation this row exists to catch.
    """
    path = ROOT / "store" / "master.py"
    if not exists(path):
        report.add("identity writers", MECHANICAL,
                   [Finding(rel(path), "store/master.py does not exist.")])
        return
    literals = literals_from_module(path)
    fields, writers = literals.get("IDENTITY_FIELDS"), literals.get("IDENTITY_WRITERS")
    if not fields or not writers:
        report.add("identity writers", MECHANICAL, [Finding(
            rel(path),
            "`IDENTITY_FIELDS`/`IDENTITY_WRITERS` could not be read as module-level "
            "literal tuples. They are parsed with `ast.literal_eval` and never imported, "
            "so each must stay a plain tuple of strings.",
        )])
        return
    fields = frozenset(fields)
    writers = frozenset(writers)

    scanned_files: List[Path] = []
    for name in _IDENTITY_WRITERS_ROOTS:
        root = ROOT / name
        if exists(root):
            scanned_files += _walk(root, (".py",))

    findings: List[Finding] = []
    scanned = 0
    allowed_seen: Set[Tuple[str, str, str]] = set()
    for file in scanned_files:
        for lineno, cls, func, field in _identity_field_assignments(file, fields):
            scanned += 1
            if file == path and cls == "Inventory" and func in writers:
                continue
            key = (rel(file), func or "", field)
            if key in IDENTITY_WRITERS_ALLOWED:
                allowed_seen.add(key)
                continue
            findings.append(Finding(
                f"{rel(file)}:{lineno}",
                f"`{func or '<module scope>'}` assigns `card.{field}` directly. The only "
                f"code identity-follows-sku.md §4.1 allows to do that is one of "
                f"Inventory.{{{', '.join(sorted(writers))}}} in store/master.py — route "
                f"this write through `bind_sku` (the SKU is trusted), `hold_sku` (it is "
                f"known but the read disputes it), or `unbind_sku`/`restore_identity` for "
                f"an undo.",
            ))

    for key in sorted(IDENTITY_WRITERS_ALLOWED - allowed_seen):
        findings.append(Finding(
            "scripts/docs_audit/code_invariants.py -> IDENTITY_WRITERS_ALLOWED",
            f"names {key!r}, and this scan finds no such direct assignment there any more.\n"
            f"  Either the site moved to a shape this reader does not recognise, or it was "
            f"genuinely fixed and the entry was not deleted with it. Delete the entry and "
            f"lower IDENTITY_WRITERS_ALLOWED_EXPECTED in the same commit, or say why the "
            f"shape changed.",
        ))

    if len(IDENTITY_WRITERS_ALLOWED) != IDENTITY_WRITERS_ALLOWED_EXPECTED:
        findings.append(Finding(
            "scripts/docs_audit/code_invariants.py -> IDENTITY_WRITERS_ALLOWED",
            f"has {len(IDENTITY_WRITERS_ALLOWED)} entries where "
            f"{IDENTITY_WRITERS_ALLOWED_EXPECTED} are pinned. Raise the pin only alongside "
            f"a new, deliberately-kept exception named in the commit message, and lower it "
            f"in the same commit that fixes one away.",
        ))

    report.add(
        "identity writers", MECHANICAL, findings,
        f"{scanned} direct card.<field> assignment(s) found, all inside the "
        f"{len(writers)} sanctioned writers or the {len(IDENTITY_WRITERS_ALLOWED)} pinned "
        f"exception(s)" if scanned else "no direct card.<field> assignment found anywhere",
        scanned=scanned,
    )


# The two routes that write a claim. D70 gives a card a `product`, D101 says a claim a screen
# names is a claim a screen can fix, and these are the two doors that ruling opened.
_CLAIM_WRITERS = ("do_put_card", "do_put_box_claims")


def _payload_keys(function: ast.AST) -> Set[str]:
    """The literal keys this handler decodes out of its request body.

    `if "<key>" in payload:` is the shape every claim in both handlers is written in, so the
    decode table is readable without running anything. It is a narrow reader on purpose: a
    handler that switched to `payload.get(name)` over a loop would present an empty table
    here, which is why the row below reports an EMPTY table as a finding rather than as
    agreement.
    """
    keys: Set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        if not isinstance(node.ops[0], ast.In):
            continue
        if not (isinstance(node.left, ast.Constant) and isinstance(node.left.value, str)):
            continue
        target = node.comparators[0]
        if (getattr(target, "id", None) or getattr(target, "attr", None)) == "payload":
            keys.add(node.left.value)
    return keys


def check_claim_decode(report: Report) -> None:
    """The card writer and the box writer decode the same claim vocabulary.

    `product` was in `do_put_card`'s table from D70 and in `do_put_box_claims`'s from never.
    The route did not refuse it — it decoded every key it knew and answered 200 with
    `"applied": 0, "unchanged": N`, which reads exactly like "the box already said that". So
    a correction typed into the box editor was accepted, reported as a success, and dropped,
    and `#/codes` went on drawing the banner that sent you there.

    Nothing detected it because the two handlers are 160 lines apart and agree about five of
    six keys. The docstring on the second one asserted the tables matched, which is the
    failure D16 is about: a claim of agreement, in prose, beside the disagreement.

    **Set equality, in both directions.** A key one door takes and the other does not is the
    defect regardless of which door is ahead — a claim writable per-card but not per-box is
    the bug that was here, and one writable per-box but not per-card is a box that can assert
    something no card can carry. If a claim genuinely belongs to one scope, the answer is a
    named exception argued in the code, not a silent asymmetry.
    """
    try:
        tree = ast.parse(read(ROOT / "server" / "capture_server.py"))
    except (SyntaxError, OSError):
        report.add("claim decode", MECHANICAL, [
            Finding("server/capture_server.py", "does not parse; the decode tables cannot be read.")
        ], "")
        return

    tables: Dict[str, Set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in _CLAIM_WRITERS:
            tables[node.name] = _payload_keys(node)

    findings: List[Finding] = []
    for name in _CLAIM_WRITERS:
        if name not in tables:
            findings.append(Finding(
                "server/capture_server.py",
                f"`{name}` is gone, and this row reconciles the two claim writers against "
                f"each other. Re-point it, or retire it with the route.",
            ))
        elif not tables[name]:
            findings.append(Finding(
                "server/capture_server.py",
                f"`{name}` decodes no `\"key\" in payload` at all. Either the handler changed "
                f"shape — in which case this reader is now blind and must be re-pointed — or "
                f"it takes nothing, which is not what a claim writer does.",
            ))
    if not findings and len(tables) == len(_CLAIM_WRITERS):
        card, box = (tables[name] for name in _CLAIM_WRITERS)
        for missing, where, other in ((card - box, _CLAIM_WRITERS[1], _CLAIM_WRITERS[0]),
                                      (box - card, _CLAIM_WRITERS[0], _CLAIM_WRITERS[1])):
            for key in sorted(missing):
                findings.append(Finding(
                    "server/capture_server.py",
                    f"`{other}` decodes `{key}` and `{where}` does not.\n"
                    f"  The route that ignores it still answers 200, reporting the write it "
                    f"did not do as a no-op. Add the branch, or argue the exception where a "
                    f"reader of both will see it.",
                ))
    report.add(
        "claim decode",
        MECHANICAL,
        findings,
        f"{len(_CLAIM_WRITERS)} claim writers, one vocabulary "
        f"({len(tables.get(_CLAIM_WRITERS[0], ())) } keys)",
        scanned=len(_CLAIM_WRITERS),
    )


# The client function that writes each server handler's claims. D101 opened the second door;
# this is what keeps both of them speaking the same vocabulary as the route behind them.
_CLAIM_CLIENTS = {"do_put_card": "updateCard", "do_put_box_claims": "applyBoxClaims"}

# Keys a client sends that are SCOPE rather than a claim. `indices` says which positions in
# the box the claim applies to; it is not something a card can carry, and the server reads it
# outside the decode table this row compares against.
_CLIENT_SCOPE_KEYS = {"indices"}

_PAYLOAD_ASSIGN_RE = re.compile(r"payload\.([a-z_][a-z0-9_]*)\s*=")


def _ts_function_body(source: str, name: str) -> Optional[str]:
    """The text of one exported function, comments stripped.

    Bounded by the next top-level `export` rather than by brace counting: a `{` inside a
    template literal or a regex would defeat the counter, and this file has both. The overrun
    a loose bound could cause is a key attributed to the wrong function, which the comparison
    below would report as a finding — so the failure is loud rather than silent.
    """
    stripped = _strip_ts_comments(source)
    start = stripped.find(f"function {name}")
    if start < 0:
        return None
    following = stripped.find("\nexport ", start)
    return stripped[start:following if following > 0 else len(stripped)]


def check_claim_clients(report: Report) -> None:
    """The client sends the keys the route decodes, on both doors.

    D101 ruled that a claim a screen names is a claim a screen can fix, and answered it with
    two doors: the inventory claim editor and an inline correction on `#/codes`. Two doors to
    one claim is two chances for the vocabulary to drift, and the drift is silent in the
    direction that matters — the server decodes what it knows and answers 200 for the rest.

    So this reads the wire keys each client function actually assigns and compares them to the
    handler's own decode table, across the language boundary. `app/src/server.ts` is the only
    place a client call is written (CLAUDE.md), which is what makes one reader enough.

    **A key the client sends and the server does not decode is the worse half**, and it is the
    one a type checker cannot see: `tsc` proves the object is well-formed, never that anything
    on the other end reads it. A key the server decodes and no client sends is the milder
    failure — a capability with no door, which is a rule this repo already has words for.
    """
    client_source = ROOT / "app" / "src" / "server.ts"
    if not exists(client_source):
        report.add("claim clients", MECHANICAL, [
            Finding("app/src/server.ts", "is gone, and it is the only place a client call is written.")
        ], "")
        return
    try:
        tree = ast.parse(read(ROOT / "server" / "capture_server.py"))
    except (SyntaxError, OSError):
        report.add("claim clients", MECHANICAL, [
            Finding("server/capture_server.py", "does not parse; the decode tables cannot be read.")
        ], "")
        return

    handlers = {
        node.name: _payload_keys(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name in _CLAIM_CLIENTS
    }
    source = read(client_source)
    findings: List[Finding] = []
    checked = 0
    for handler, client in _CLAIM_CLIENTS.items():
        body = _ts_function_body(source, client)
        if body is None:
            findings.append(Finding("app/src/server.ts", f"no `{client}` to read."))
            continue
        if handler not in handlers:
            findings.append(Finding("server/capture_server.py", f"no `{handler}` to read."))
            continue
        checked += 1
        sent = set(_PAYLOAD_ASSIGN_RE.findall(body)) - _CLIENT_SCOPE_KEYS
        decoded = handlers[handler]
        for key in sorted(sent - decoded):
            findings.append(Finding(
                "app/src/server.ts",
                f"`{client}` sends `{key}` and `{handler}` decodes no such key.\n"
                f"  The route answers 200 and writes nothing. A type checker cannot see this: "
                f"it proves the body is well-formed, never that anything reads it.",
            ))
        for key in sorted(decoded - sent):
            findings.append(Finding(
                "app/src/server.ts",
                f"`{handler}` decodes `{key}` and `{client}` never sends it.\n"
                f"  A capability no screen can reach is not built (CLAUDE.md's hard rule). "
                f"Send it, or retire the branch.",
            ))
    report.add(
        "claim clients",
        MECHANICAL,
        findings,
        f"{checked} client writers send exactly what their route decodes",
        scanned=checked,
    )


# `detector standing` is CUT (test-audit plan Q2, 2026-09-28). It reconciled
# docs/debts/006's figures against harness/results/detect.json.


def check_sole_reader(report: Report) -> None:
    """"The only reader of the history" is a countable claim, and it is wrong.

    Three places say `_state_before_sale` is the only thing in this repo that reads the
    history — two comments in `server/capture_server.py` and one line of
    `docs/specs/order-flow.md`. Measured 2026-09-05 the count is three, and the more useful
    half of the finding is that **`_state_before_sale` is not one of them**: it takes a
    sequence of events as an argument and scans it. The readers are `_answer_origin`,
    `_origin` and `_reverse_stand_down`.

    That distinction is what the claim was load-bearing for. A comment that says one function
    is the only reader is telling the next session it can reason about the history's access
    pattern by reading one function — and D26's reversal, D83's third door and the sale
    origin all go through a different one. The comment was true when it was written and two
    features walked past it.

    **The claim is the subject, not the count.** Nothing here says three readers is too many;
    a checker cannot hold that (D16). It holds that a sentence asserting a number agrees with
    the number, which is the only half that is mechanical.
    """
    readers = _history_readers()
    functions = {reader.rsplit(" in ", 1)[-1] for reader in readers}
    findings: List[Finding] = []
    sources = list(markdown_files())
    for root in _HISTORY_READER_ROOTS:
        base = ROOT / root
        if exists(base):
            sources.extend(_walk(base, (".py",)))
    for path in sources:
        text = read(path)
        for match in _SOLE_READER_RE.finditer(text):
            number = text.count("\n", 0, match.start()) + 1
            named = match.group(1) or match.group(2)
            if named in functions and len(readers) == 1:
                continue
            listed = "\n    ".join(readers) or "(none found)"
            reads = "does not read it at all" if named not in functions else "is one of them"
            findings.append(
                Finding(
                    f"{rel(path)}:{number}",
                    f"claims `{named}` is the only reader of the history; there are "
                    f"{len(readers)}, and `{named}` {reads}.\n"
                    f"    {listed}",
                )
            )
    report.add(
        "sole reader",
        MECHANICAL,
        findings,
        f"{len(readers)} history readers, every claim about them counts right",
        scanned=len(readers),
    )


def check_server_concurrency(report: Report) -> None:
    """§11 names the capture server's concurrency; the code decides it.

    WHY THIS ROW EXISTS, which is the same argument the section it guards makes about itself.
    Every fact in section 11 was already in the tree, inside two comments in
    `server/capture_server.py`. On 2026-09-04 a session diagnosed a wedge from `.serve/*.log`
    without opening that file, told the owner the server was single-threaded, and proposed
    `ThreadingHTTPServer` as the fix — the class it has been built on all along. Moving the
    argument into a document a session actually reads is only half the repair: a document
    nothing reconciles goes stale exactly the way those comments did, and this file spends a
    section on that difference.

    So the literals the section publishes are read out of the code and compared.

    **THE PARAGRAPH THAT STOOD HERE PREDICTED SOMETHING THAT DID NOT HAPPEN, and it is kept
    as a correction rather than quietly swapped.** It said a worker pool "changes the base
    class, and this row then FAILS until the section is rewritten" — the row built to go red
    on the change it documents. The pool landed on 2026-09-04 and the base class did not
    change: `CaptureServer` still subclasses `ThreadingHTTPServer` and submits from
    `process_request` to a `ThreadPoolExecutor`. The row stayed green through the exact change
    it claimed it would catch. What actually carries the pool's safety is a header, which no
    literal here was reading, so a fifth fact was added below rather than the prediction being
    re-worded into something it could still claim.

    Nothing here judges whether the concurrency is right. It judges whether the document and the
    code agree about what it IS, which is the only half a checker can hold honestly (D16).

    **TWO PUBLICATIONS, AS OF THIS ROW'S SECOND WIDENING. Only §11 had a
    reader, and CLAUDE.md publishes the same four attributed literals** — `class
    CaptureServer(ThreadingHTTPServer)`, `request_queue_size = 128`, `CaptureHandler.timeout
    = 15`, `REQUEST_SLOTS = 4` — in the file every session loads before it touches the server
    whose collapse at 150 connections is measured. A retune that fails this row via §11 while
    CLAUDE.md goes on saying 4 is a document that is wrong in the more-read of the two places.
    Both are compared now, and a finding names WHICH file it is about.

    **The fifth fact stays scoped to §11 on purpose**, and this is a narrowing of the
    proposal that asked for it: the fifth is the METHOD NAME that sends `Connection: close`,
    and CLAUDE.md deliberately publishes the header without naming the method — §11 is where
    the mechanism is argued. Demanding the name in both would have failed on an unchanged
    tree, which is not a defect it found, only prose it wanted. Nothing is uncovered by the
    narrowing: §11 is the only file that makes the claim, so it is the only file that can go
    stale on it.

    The bare integers are safe from both anchors for the reason the comment below records:
    CLAUDE.md's "sized this at 12" and "80 Playwright browsers, 969 threads" are
    measurements, and an ATTRIBUTED anchor can neither be satisfied nor tripped by a loose
    number.
    """
    source = read(ROOT / "server" / "capture_server.py")
    section = _debts_section(11)
    findings: List[Finding] = []
    compared = 0

    if section is None:
        report.add(
            "server concurrency",
            MECHANICAL,
            [
                Finding(
                    "docs/debts/",
                    "section 11 is gone, and it is what publishes the capture server's "
                    "concurrency. Restore it, or delete this row with it — a check whose "
                    "subject has left is the vacuous green this file is about.",
                )
            ],
            "",
        )
        return

    # The two publications of these facts, in reading order. `where` is what a finding
    # names and `called` is what the sentence calls itself, so a message reads the same
    # whichever file is wrong.
    publications: List[Tuple[str, str, str]] = [
        ("docs/debts/", "section 11", section),
    ]
    claude_md = ROOT / "CLAUDE.md"
    claude_text = read(claude_md) if exists(claude_md) else None
    if claude_text is None:
        findings.append(
            Finding(
                "CLAUDE.md",
                "is not there, and it publishes this server's concurrency facts to every "
                "session that loads it. Nothing else reconciles that copy.",
            )
        )
    else:
        publications.append(("CLAUDE.md", "the capture-server bullet", claude_text))

    for what, pattern, shape, anchor, published in _CONCURRENCY_FACTS:
        found = pattern.search(source)
        if found is None:
            findings.append(
                Finding(
                    "server/capture_server.py",
                    f"{what} no longer matches `{shape}`, so this row cannot read what "
                    f"§11 claims. Re-point the pattern, and check the "
                    f"section still describes the server that exists.",
                )
            )
            continue
        value = found.group(1)
        # ATTRIBUTED, NOT MERELY PRESENT — and the two rewrites this line has had are the
        # argument for the shape it is in now.
        #
        # It began as `value in section`, a SUBSTRING test: retuning the handler timeout from
        # 15 to 5 left this row green because `5` occurs inside `15`, `128` and `338%`. That
        # was fixed to a word-boundaried search, and the fix was too narrow to hold. The
        # question `\b4\b` asks is *does this number appear anywhere in section 11*, and that
        # section publishes about fifty-five distinct bare integers — every sweep column, every
        # latency, every thread count. So almost any retune lands on a number the section
        # already says for some other reason.
        #
        # MEASURED, 2026-09-05: swapping the two constants — `CaptureHandler.timeout` to 4 and
        # `REQUEST_SLOTS` to 15 — leaves the document wrong about BOTH and sizes the pool at
        # the value this very section calls "within noise of the unbounded server it was meant
        # to improve on". The row reported `ok`. A guard that passes while the thing it pins is
        # inverted is not a weak guard, it is a decoration.
        #
        # So the section must publish the figure in a form that ATTRIBUTES it to this fact —
        # `REQUEST_SLOTS = 4`, not a 4 in a table of slot counts — and the value it attributes
        # is what gets compared. Coincidence cannot satisfy that; only agreement can.
        for where, called, text in publications:
            compared += 1
            said = anchor.search(text)
            if said is None:
                findings.append(
                    Finding(
                        where,
                        f"{called} never attributes a value to {what}. It has to publish one as "
                        f"`{published}` for this row to tell agreement from coincidence — a bare "
                        f"`{value}` somewhere in it is not a claim about {what}, and this "
                        f"row used to accept one.",
                    )
                )
            elif said.group(1) != value:
                findings.append(
                    Finding(
                        where,
                        f"{called} publishes {what} as `{published.replace('<n>', said.group(1)).replace('<seconds>', said.group(1)).replace('<base>', said.group(1))}` "
                        f"and `server/capture_server.py` says `{value}`. The code is the authority; "
                        f"the document is the published account of this server's concurrency, and it "
                        f"is now describing one that is gone.",
                    )
                )

    # The fifth fact, and the only one that is a NAME rather than a literal. Section 11 already
    # names `Connection: close`; what it did not name is where the header is sent from, and
    # that is the half the pool's safety actually rests on.
    owner = _close_header_owner()
    compared += 1
    if owner is None:
        findings.append(
            Finding(
                "server/capture_server.py",
                "nothing sends `Connection: close` any more. Section 11 says a worker's life "
                "is one REQUEST rather than one connection, and this header is what makes "
                "that true — without it four idle keep-alive connections hold all four "
                "workers and `make harness` does not fail, it HANGS.",
            )
        )
    elif re.search(rf"\b{re.escape(owner)}\b", section) is None:
        findings.append(
            Finding(
                "docs/debts/",
                f"section 11 does not name `{owner}`, which is where `Connection: close` is "
                f"sent from. The method is the guarantee: every response reaches "
                f"`end_headers` by construction, so no new route can forget the header, "
                f"which is not true of any single send site.",
            )
        )

    report.add(
        "server concurrency",
        MECHANICAL,
        findings,
        f"{compared} published facts against server/capture_server.py",
        scanned=compared,
    )


_SHIPPING_COLUMN_CLAIMS = (
    (Path("docs") / "specs" / "order-pipeline.md",
     re.compile(r"import file — \*\*([A-Za-z]+) columns\*\*")),
    (Path("harness") / "tests" / "t7" / "shipping.py",
     re.compile(r"the header is the ([a-z]+) columns")),
)


def _pirateship_column_count() -> Optional[int]:
    """How many columns `pipeline/pirateship.py` actually writes, read out of the source.

    Parsed rather than imported: this checker runs from a bare `python3` on the commit path
    (D18) and importing the pipeline drags its dependencies in. Parsed rather than grepped
    because the count is a SUM — a tuple of named columns plus `STAMP_COLUMNS` — and a regex
    over either half alone answers the wrong question, which is the mistake the document made.

    Returns None when the shape is no longer `COLUMNS = (...) + STAMP_COLUMNS`, and the caller
    reports that rather than guessing: a checker that silently falls back to one half of a sum
    is the vacuous green this file exists to refuse.
    """
    try:
        tree = ast.parse(read(ROOT / "pipeline" / "pirateship.py"))
    except SyntaxError:
        return None

    tuples: Dict[str, int] = {}
    total: Optional[int] = None

    def target_name(node: ast.stmt) -> Optional[str]:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            return node.target.id
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            return node.targets[0].id
        return None

    for node in tree.body:
        name = target_name(node)
        if name is None:
            continue
        value = getattr(node, "value", None)
        if isinstance(value, ast.Tuple):
            tuples[name] = len(value.elts)
        elif (name == "COLUMNS" and isinstance(value, ast.BinOp)
              and isinstance(value.op, ast.Add)
              and isinstance(value.left, ast.Tuple)
              and isinstance(value.right, ast.Name)):
            named = len(value.left.elts)
            stamps = tuples.get(value.right.id)
            if stamps is not None:
                total = named + stamps

    return total


_ESTIMATE_READER = ROOT / "server" / "pipeline_routes.py"
_ESTIMATE_WRITER = ROOT / "cli" / "cmd_identify.py"
_ESTIMATE_PATTERN_NAME = "_ESTIMATE"
_ESTIMATE_PRODUCER = "_estimate"
#: What a rendered figure looks like when the sample is built. Any decimal would do; this
#: one is two places, which is what `_estimate` quantizes to.
_ESTIMATE_SAMPLE = "1.23"


def _compiled_assign(tree: ast.AST, name: str) -> Optional[Tuple[str, int]]:
    """(pattern, flags) of a module-level `NAME = re.compile(r"...", FLAG)`, or None.

    Read out of the source and compiled here, never imported: the rule this whole file is
    built on. Only `re.M` / `re.MULTILINE` is resolved, because that is the flag this pair
    turns on and a flag nobody can read is reported rather than guessed.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            continue
        call = node.value
        if not isinstance(call, ast.Call) or not call.args:
            return None
        first = call.args[0]
        if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
            return None
        flags = 0
        for extra in call.args[1:]:
            text = ast.unparse(extra) if hasattr(ast, "unparse") else ""
            if "M" in text or "MULTILINE" in text:
                flags |= re.M
        return first.value, flags
    return None


def _rendered_say(tree: ast.AST, producer: str) -> Optional[str]:
    """The line a `say(f"...")` whose f-string CALLS `producer` would print.

    ANCHORED ON THE CALL AND NEVER ON THE WORDING, which is the whole point: the defect is
    somebody rewording the sentence, so a reader that finds the site BY its wording cannot
    see the change it exists to catch. The producing call is the invariant.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "say") or len(node.args) != 1:
            continue
        joined = node.args[0]
        if not isinstance(joined, ast.JoinedStr):
            continue
        calls = {
            inner.func.id
            for inner in ast.walk(joined)
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
        }
        if producer not in calls:
            continue
        out: List[str] = []
        for part in joined.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                out.append(part.value)
            else:
                out.append(_ESTIMATE_SAMPLE)
        return "".join(out)
    return None


def check_estimate_wire(report: Report) -> None:
    """The money button's figure, against the string that produces it.

    **THE ONE PRESS IN THIS PRODUCT THAT SPENDS MONEY CARRIES ITS FIGURE IN THE LABEL
    (D33), AND THE FIGURE TRAVELS AS TEXT.** `cli/cmd_identify.py` prints `estimated cost
    $1.23` in its preflight; `server/pipeline_routes.py` scrapes that line with `_ESTIMATE`
    and serves the number as `estimate_usd`, which is what `#/runs` draws on the button.
    Two declarations of one fact, in two languages, with a regex as the seam.

    Reword that `say` line and `estimate_usd` goes null. Nothing fails: the estimate is not
    an outcome any test asserts, so the money gate loses its figure and every suite stays
    green. `grep -c "estimated cost\\|_ESTIMATE" scripts/docs-audit.py` returned **0**
    before this row — no check reconciled the pair.

    **THE SAMPLE IS BUILT AND MATCHED, rather than the two strings being compared.** The
    row renders what that `say` would print, with the interpolation standing in for a
    figure, and requires the regex to match it AND to capture the number. That is the
    question the wire actually asks; comparing the literal against the pattern's source
    text would be comparing two spellings of an intent.

    **ANCHORED ON THE PRODUCING CALL, never on the wording.** The site is the `say(f"...")`
    whose f-string calls `_estimate` — so a rewording is exactly what the row sees, which a
    reader that FOUND the site by its wording could not. It also keeps the second cost line
    out of it by construction: `cmd_identify` writes an actual invoice too, deliberately not
    anchored at `^estimated cost` (see the comment above it), and that one calls `cost.usd`.

    **Two absences, two findings.** A missing pattern and a missing producer are different
    repairs — one is the server's reader gone, one is the CLI's line gone — and reporting
    either as the other sends a session to the wrong file.
    """
    findings: List[Finding] = []
    compared = 0

    reader_tree = None
    if not exists(_ESTIMATE_READER):
        findings.append(Finding(rel(_ESTIMATE_READER), "does not exist."))
    else:
        try:
            reader_tree = ast.parse(read(_ESTIMATE_READER))
        except SyntaxError as exc:
            findings.append(Finding(rel(_ESTIMATE_READER), f"does not parse.\n{exc}"))

    writer_tree = None
    if not exists(_ESTIMATE_WRITER):
        findings.append(Finding(rel(_ESTIMATE_WRITER), "does not exist."))
    else:
        try:
            writer_tree = ast.parse(read(_ESTIMATE_WRITER))
        except SyntaxError as exc:
            findings.append(Finding(rel(_ESTIMATE_WRITER), f"does not parse.\n{exc}"))

    pattern = _compiled_assign(reader_tree, _ESTIMATE_PATTERN_NAME) if reader_tree else None
    rendered = _rendered_say(writer_tree, _ESTIMATE_PRODUCER) if writer_tree else None

    if reader_tree is not None and pattern is None:
        findings.append(Finding(
            rel(_ESTIMATE_READER),
            f"no module-level `{_ESTIMATE_PATTERN_NAME} = re.compile(r\"...\")` this row can "
            f"read.\n"
            f"  It is the seam the money button's figure travels through — the route scrapes "
            f"the CLI's preflight line with it and serves the number as `estimate_usd`. "
            f"Renamed or restructured, and nothing reconciles the pair while it is "
            f"unreadable.",
        ))
    if writer_tree is not None and rendered is None:
        findings.append(Finding(
            rel(_ESTIMATE_WRITER),
            f"no `say(f\"...\")` whose f-string calls `{_ESTIMATE_PRODUCER}()`.\n"
            f"  That line is what produces the figure `#/runs` puts on the press that spends "
            f"money. Either the print moved, or it stopped going through "
            f"`{_ESTIMATE_PRODUCER}` — and this row is anchored on the CALL precisely so a "
            f"reworded sentence is visible rather than invisible.",
        ))

    if pattern is not None and rendered is not None:
        compared = 1
        source, flags = pattern
        try:
            compiled = re.compile(source, flags)
        except re.error as exc:
            findings.append(Finding(
                rel(_ESTIMATE_READER),
                f"`{_ESTIMATE_PATTERN_NAME}` does not compile: {exc}",
            ))
        else:
            match = compiled.search(rendered)
            if match is None or not match.groups() or match.group(1) != _ESTIMATE_SAMPLE:
                findings.append(Finding(
                    rel(_ESTIMATE_WRITER),
                    "the line this prints is not the line the route can read.\n"
                    f"  prints:  {rendered!r}\n"
                    f"  pattern: {source!r}\n"
                    f"  captured: "
                    f"{(match.group(1) if match and match.groups() else None)!r}\n"
                    "  `estimate_usd` would be null, `#/runs` would draw a money button with "
                    "no figure on it, and every test would stay green — the estimate is not "
                    "an outcome any of them assert. Move both sides together.",
                ))

    report.add(
        "estimate wire",
        MECHANICAL,
        findings,
        "the preflight's cost line is the line `estimate_usd` reads",
        scanned=compared,
    )


def _shipping_columns() -> Row:
    """The Pirate Ship import's column count, published in two files, decided by one.

    WHY THIS ROW EXISTS. `docs/specs/order-pipeline.md` said the renderer produced a file of
    TEN columns from 2026-08-30 until 2026-09-05. It produces twelve — nine named plus three
    rubber stamps — and `harness/tests/t7/shipping.py` said twelve the whole time. Two
    documents in this repository disagreed about a number the code settles in one line, and
    nothing compared either to the code or to each other.

    It is `route census`'s argument in another lane: a published count with no reader is a
    claim that can only be contradicted by somebody happening to look. Note which way the
    error ran — the TEST was right and the SPEC was wrong, so "the tests would have caught it"
    is exactly the reasoning that let it stand for a week.

    A REWORD CANNOT SILENCE IT. A file that no longer carries a sentence this row can find is
    reported as unwatched rather than passing quietly, which is the failure mode a pattern-
    matched checker has and the one `route census` had to grow its own answer to.
    """
    total = _pirateship_column_count()
    findings: List[Finding] = []

    if total is None:
        return Row(
            "shipping columns",
            MECHANICAL,
            [
                Finding(
                    "pipeline/pirateship.py",
                    "`COLUMNS` is no longer `(<named>, ...) + STAMP_COLUMNS`, so this row "
                    "cannot count what the documents claim. Re-point it, and check both "
                    "sentences still describe the file the renderer writes.",
                )
            ],
            "",
        )

    for path, pattern in _SHIPPING_COLUMN_CLAIMS:
        text = read(ROOT / path)
        found = pattern.search(text)
        if found is None:
            findings.append(
                Finding(
                    str(path),
                    "no sentence here matches the pattern watching this file's column count. "
                    "It was reworded past its own check, or the claim was removed — either "
                    "way the count is unwatched now. Re-point the pattern or drop the entry.",
                )
            )
            continue
        word = found.group(1).lower()
        said = _NUMBER_WORDS.get(word)
        if said is None:
            findings.append(
                Finding(str(path), f"`{found.group(1)} columns` is not a number this row knows.")
            )
        elif said != total:
            findings.append(
                Finding(
                    str(path),
                    f"says `{found.group(1)} columns` and `pipeline/pirateship.py` writes "
                    f"{total}. The code is the authority; the sentence is describing a file "
                    f"the renderer does not produce.",
                )
            )

    return Row(
        "shipping columns",
        MECHANICAL,
        findings,
        f"{len(_SHIPPING_COLUMN_CLAIMS)} published counts against pipeline/pirateship.py ({total})",
        scanned=len(_SHIPPING_COLUMN_CLAIMS),
    )


# ------------------------------------------------------------ code-side agreements
#
# Every row above reconciles a MARKDOWN claim against the code it describes. Nothing in
# this file reads a claim written INSIDE code — a comment spelling out a tuple's length in
# words, or a constant copied by hand into a second module, so it can drift the exact way a
# markdown sentence drifts and no reader here would ever see it. These four rows are that
# reader, over the four such claims found in a sweep of `server/`, `pipeline/` and `app/`.
#
# `CODE_AGREEMENT_ARM_COUNT` is `HARD_RULE_FLOOR`'s own precedent: a NUMBER pinned in code,
# never a sentence in a comment, so `--self-test` can assert against it rather than a
# person re-reading this section to count how many mutation arms it is supposed to have.
# The four rows are `check_column_count`, `check_threshold_agreement`,
# `check_dist_path_agreement` and `check_import_filename_agreement`, one arm each.
# `check_duplicated_measurements`'s three arms are CUT with the row (test-audit plan Q2,
# 2026-09-28). Each remaining arm mutates its subject via a `.bak`-protected temporary edit
# or a throwaway fixture and asserts the row goes red. Lowering this without removing an
# arm is a lie the constant makes visible in the diff; raising it with no matching arm
# added fails `--self-test` outright.
CODE_AGREEMENT_ARM_COUNT = 4

# Path constants, each patchable in isolation by --self-test (the same shape used
# above for `MAP`), so a mutation arm can point one row at a throwaway fixture
# without ever touching a file this repository tracks.
_TCG_IMPORT_PATH = ROOT / "server" / "tcg_import.py"
_REVIEWQUEUE_PATH = ROOT / "app" / "src" / "ReviewQueue.tsx"
_PRICING_PATH = ROOT / "pipeline" / "pricing.py"
_SERVE_PATH = ROOT / "scripts" / "serve.py"
_CAPTURE_SERVER_PATH = ROOT / "server" / "capture_server.py"
_VITE_CONFIG_PATH = ROOT / "app" / "vite.config.ts"
_SHIPPING_ROUTES_PATH = ROOT / "server" / "shipping_routes.py"

_TCG_IMPORT_COLUMNS_COMMENT_RE = re.compile(
    r"The ([A-Za-z]+) fields `PricingStagedPrice` reads"
)


def _tcg_import_columns_count() -> Optional[int]:
    """How many `(source, header)` pairs `server/tcg_import.py:COLUMNS` actually holds.

    Parsed rather than imported, on `_pirateship_column_count`'s own reasoning: this
    checker runs from a bare `python3` on the commit path (D18), and `server/tcg_import.py`
    is server code that need not be importable without the venv it never asks for.
    """
    try:
        tree = ast.parse(read(_TCG_IMPORT_PATH))
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.target.id == "COLUMNS" and isinstance(node.value, ast.Tuple):
            return len(node.value.elts)
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "COLUMNS" \
                and isinstance(node.value, ast.Tuple):
            return len(node.value.elts)
    return None


def _column_count() -> Row:
    """`server/tcg_import.py`'s own comment against the tuple it describes.

    THE DEFECT IS ALREADY IN THE TREE. The comment above `COLUMNS` says "The eleven fields
    `PricingStagedPrice` reads"; the tuple it introduces holds ten `(source, header)` pairs.
    Nothing compared the spelled-out word to `len(COLUMNS)`, the same gap `shipping columns`
    closes for `pipeline/pirateship.py` one file over — a comment inside code is a claim the
    same as a sentence in a markdown file, and this file audits markdown claims and nothing
    written in a docstring or a `#` line.

    REFUSES TO GO QUIET: a `COLUMNS` no longer shaped as a bare tuple of pairs, or a comment
    no longer matching the pattern, is reported by name rather than skipped.
    """
    findings: List[Finding] = []
    total = _tcg_import_columns_count()
    text = read(_TCG_IMPORT_PATH)
    match = _TCG_IMPORT_COLUMNS_COMMENT_RE.search(text)

    if total is None:
        findings.append(Finding(
            "server/tcg_import.py",
            "`COLUMNS` is no longer a bare tuple of `(source, header)` pairs, so this row "
            "cannot count what the comment above it claims. Re-point it.",
        ))
    if match is None:
        findings.append(Finding(
            "server/tcg_import.py",
            "no sentence here matches the pattern watching the column-count comment. It was "
            "reworded past its own check, or the comment was removed — either way the count "
            "is unwatched now. Re-point the pattern or drop the entry.",
        ))
    if total is not None and match is not None:
        word = match.group(1).lower()
        said = _NUMBER_WORDS.get(word)
        line = text.count("\n", 0, match.start()) + 1
        if said is None:
            findings.append(Finding(
                "server/tcg_import.py:{0}".format(line),
                "`{0} fields` is not a number this row knows.".format(match.group(1)),
            ))
        elif said != total:
            findings.append(Finding(
                "server/tcg_import.py:{0}".format(line),
                "says `{0} fields` and `COLUMNS` holds {1} pairs. The tuple is the "
                "authority; the comment is describing a shape the code does not have."
                .format(match.group(1), total),
            ))

    return Row(
        "column count",
        MECHANICAL,
        findings,
        "the comment's word against COLUMNS's length ({0})".format(total),
        scanned=1,
    )


_THRESHOLD_TSX_RE = re.compile(r"const THRESHOLD = ([0-9.]+)")
_THRESHOLD_PY_RE = re.compile(r'THRESHOLD = Decimal\("([0-9.]+)"\)')


def check_column_counts(report: Report) -> None:
    """Two published column counts, each against the one file that settles it: the
    Pirate Ship import's own columns, and `server/tcg_import.py`'s own comment.

    Merged from `column count` and `shipping columns` by M3 (test-audit-2026-09-27, L8, Q8
    yes) — both are "a published count against `len(...)` somewhere in the tree" and neither
    changes what the other judges. Each sub-check below is unchanged; only the last line of
    each moved from `report.add` to `return Row`.
    """
    merged = _merge_rows("column counts", [
        _column_count(),
        _shipping_columns(),
    ])
    report.add("column counts", merged.severity, merged.findings, merged.summary,
               scanned=merged.scanned)


def check_threshold_agreement(report: Report) -> None:
    """D9's threshold, spelled once in Python and copied once into JSX, against each other.

    `app/src/ReviewQueue.tsx`'s own comment names `pipeline/pricing.py:THRESHOLD` as the
    authority — the two constants are supposed to be the same value read by two languages
    that cannot import from one another, the same shape `port-agreement.py` and
    `set-hint-agreement.py` already reconcile for a port number and a game vocabulary. Read
    for style, not extended: this is a different pair of files with no `make` target of its
    own, so a docs-audit row is the right shape.

    A copied constant is a claim written IN CODE rather than in a markdown sentence, so
    nothing before this row ever compared the two sides.

    REFUSES TO GO QUIET: either constant going unreadable — renamed, reshaped, moved to a
    different declaration form — is reported by name rather than skipped.
    """
    findings: List[Finding] = []
    tsx_text = read(_REVIEWQUEUE_PATH)
    py_text = read(_PRICING_PATH)
    tsx_match = _THRESHOLD_TSX_RE.search(tsx_text)
    py_match = _THRESHOLD_PY_RE.search(py_text)

    if tsx_match is None:
        findings.append(Finding(
            "app/src/ReviewQueue.tsx",
            "no `const THRESHOLD = <number>` found. It was renamed or reshaped past the "
            "pattern watching it, so this row can no longer see the copy it is meant to "
            "check against `pipeline/pricing.py:THRESHOLD`.",
        ))
    if py_match is None:
        findings.append(Finding(
            "pipeline/pricing.py",
            "no `THRESHOLD = Decimal(\"...\")` found. It was renamed, reshaped, or moved off "
            "the `Decimal` construction this row watches.",
        ))
    if tsx_match is not None and py_match is not None:
        try:
            tsx_value = float(tsx_match.group(1))
            py_value = float(py_match.group(1))
        except ValueError:
            findings.append(Finding(
                "app/src/ReviewQueue.tsx",
                "THRESHOLD values are not both parseable numbers: {0!r} / {1!r}."
                .format(tsx_match.group(1), py_match.group(1)),
            ))
        else:
            if tsx_value != py_value:
                line = tsx_text.count("\n", 0, tsx_match.start()) + 1
                findings.append(Finding(
                    "app/src/ReviewQueue.tsx:{0}".format(line),
                    "`THRESHOLD = {0}` and `pipeline/pricing.py:THRESHOLD` is `{1}` — its "
                    "own comment names that constant as the authority, and the two no "
                    "longer agree.".format(tsx_match.group(1), py_match.group(1)),
                ))

    report.add(
        "threshold agreement",
        MECHANICAL,
        findings,
        "app/src/ReviewQueue.tsx:THRESHOLD against pipeline/pricing.py:THRESHOLD",
        scanned=1,
    )


_SERVE_DIST_RE = re.compile(r'^DIST = "([^"]+)"', re.M)
_CAPTURE_APP_DIST_RE = re.compile(
    r'APP_DIST = Path\(__file__\)\.resolve\(\)\.parent\.parent / "app" / "dist"'
)
_VITE_OUTDIR_RE = re.compile(r"\boutDir\s*:")


def check_dist_path_agreement(report: Report) -> None:
    """The built-bundle path, spelled independently in two Python modules and once by
    Vite's default, reconciled against each other.

    `scripts/serve.py:DIST` (the build-and-swap side) and `server/capture_server.py:APP_DIST`
    (what the server actually reads from) each spell `app/dist` on their own — one as a
    string literal, one as a `Path` join — and if either moves while the other does not, the
    server serves nothing D138 promised it would. `app/vite.config.ts` sets `base` but
    declares no `outDir`, which is the THIRD side: Vite's own default output directory is
    `dist` under its project root (`app/`), i.e. `app/dist`, and that side of the agreement
    is checked only by absence — an `outDir` key appearing in `vite.config.ts` would
    silently move the bundle Vite writes without moving either Python constant, so its
    presence is itself the finding.

    NOT FULLY MECHANIZED ON THE VITE SIDE: this row cannot run Vite and read back its
    resolved `outDir`, so it reads the config file's own text for the key that would
    override the default. That is real coverage of the failure this row exists for — a
    session adding `build: { outDir: ... }` — but it is not proof of Vite's default itself,
    which is documented behaviour this row takes on faith.

    REFUSES TO GO QUIET: either Python constant going unreadable is reported by name.
    """
    findings: List[Finding] = []
    serve_text = read(_SERVE_PATH)
    capture_text = read(_CAPTURE_SERVER_PATH)

    serve_match = _SERVE_DIST_RE.search(serve_text)
    if serve_match is None:
        findings.append(Finding(
            "scripts/serve.py",
            "no `DIST = \"...\"` found. It was renamed or reshaped past the pattern watching "
            "it, so this row can no longer check it against `server/capture_server.py:APP_DIST`.",
        ))
    elif serve_match.group(1) != "app/dist":
        findings.append(Finding(
            "scripts/serve.py",
            "`DIST = {0!r}`, not `\"app/dist\"` — `server/capture_server.py:APP_DIST` "
            "still expects the build at `app/dist`.".format(serve_match.group(1)),
        ))

    capture_match = _CAPTURE_APP_DIST_RE.search(capture_text)
    if capture_match is None:
        findings.append(Finding(
            "server/capture_server.py",
            "`APP_DIST` is no longer `Path(__file__).resolve().parent.parent / \"app\" / "
            "\"dist\"`, the join this row watches to confirm it names the same directory as "
            "`scripts/serve.py:DIST`. Re-point the pattern or confirm the new form still "
            "resolves to `app/dist`.",
        ))

    if exists(_VITE_CONFIG_PATH):
        vite_text = read(_VITE_CONFIG_PATH)
        if _VITE_OUTDIR_RE.search(vite_text):
            findings.append(Finding(
                "app/vite.config.ts",
                "declares its own `outDir`, which moves the bundle Vite writes off its "
                "default (`dist` under the project root, i.e. `app/dist`) without moving "
                "`scripts/serve.py:DIST` or `server/capture_server.py:APP_DIST` — the build "
                "and the server would then disagree about where the bundle lives.",
            ))
    else:
        findings.append(Finding(
            "app/vite.config.ts",
            "does not exist, and it is the third side of this agreement.",
        ))

    report.add(
        "dist path agreement",
        MECHANICAL,
        findings,
        "scripts/serve.py:DIST, server/capture_server.py:APP_DIST and vite.config.ts's outDir",
        scanned=1,
    )


_SHIPPING_IMPORT_FILENAME_RE = re.compile(r'IMPORT_FILENAME = "([^"]+)"')
_CAPTURE_CONTENT_DISPOSITION_RE = re.compile(
    r'"Content-Disposition",\s*\'attachment; filename="([^"]+)"\''
)


def check_import_filename_agreement(report: Report) -> None:
    """The Pirate Ship import's filename, named once as a constant and once hardcoded in a
    response header, reconciled against each other.

    `server/shipping_routes.py:IMPORT_FILENAME`'s own comment says "membership of that one
    name IS the shape check `do_shipping_file` makes" — and `server/capture_server.py`
    spells the same name a second time, by hand, inside the `Content-Disposition` header it
    sends alongside the file. Renaming the constant leaves the browser saving the download
    under the old name, silently, because nothing reads the two together.

    REFUSES TO GO QUIET: either side going unreadable is reported by name rather than
    skipped.
    """
    findings: List[Finding] = []
    shipping_text = read(_SHIPPING_ROUTES_PATH)
    capture_text = read(_CAPTURE_SERVER_PATH)

    shipping_match = _SHIPPING_IMPORT_FILENAME_RE.search(shipping_text)
    if shipping_match is None:
        findings.append(Finding(
            "server/shipping_routes.py",
            "no `IMPORT_FILENAME = \"...\"` found. It was renamed or reshaped past the "
            "pattern watching it, so this row can no longer check it against the "
            "`Content-Disposition` header in `server/capture_server.py`.",
        ))
    capture_match = _CAPTURE_CONTENT_DISPOSITION_RE.search(capture_text)
    if capture_match is None:
        findings.append(Finding(
            "server/capture_server.py",
            "no `Content-Disposition: attachment; filename=\"...\"` literal found for the "
            "Pirate Ship import. It was reworded or moved past the pattern watching it.",
        ))

    if shipping_match is not None and capture_match is not None \
            and shipping_match.group(1) != capture_match.group(1):
        line = capture_text.count("\n", 0, capture_match.start()) + 1
        findings.append(Finding(
            "server/capture_server.py:{0}".format(line),
            "sends `Content-Disposition: attachment; filename=\"{0}\"`, and "
            "`server/shipping_routes.py:IMPORT_FILENAME` is `{1!r}` — the constant is the "
            "authority and the header names a file `do_shipping_file` does not produce."
            .format(capture_match.group(1), shipping_match.group(1)),
        ))

    report.add(
        "import filename agreement",
        MECHANICAL,
        findings,
        "server/shipping_routes.py:IMPORT_FILENAME against the Content-Disposition header",
        scanned=1,
    )
