"""The check registry, commit path, suite lock, browser, spec, serve and guard scopes, audit invocation."""

from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import re
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

from . import core
from .core import (
    EXIT_USAGE,
    Finding,
    MECHANICAL,
    ROOT,
    Report,
    Row,
    SELF,
    _STAGED_PATHS,
    _check_recipe,
    _nul_list,
    _recipe_targets,
    _sibling,
    _walk,
    entry_parser,
    exists,
    glob_files,
    literals_from_module,
    read,
    rel,
)
from .hygiene import _blank_ts_comments, _make_recipe
from .screens import APP_SRC, APP_TESTS

# ------------------------------------------------------- what `make check` actually runs

CHECKS_REGISTRY = ROOT / "scripts" / "checks.py"
PRE_COMMIT = ROOT / "scripts" / "githooks" / "pre-commit"

# A path inside the repo that a `runs` command names. Used to ask whether the pre-commit hook
# invokes the same thing, which is the only honest way to check the `commit_path` field: the
# hook runs `python3 scripts/docs-audit.py --staged`, never `make docs-audit`, so matching on
# the target name would answer no for the one entry that is genuinely on the commit path.
_RUNS_PATH_RE = re.compile(r"[A-Za-z0-9_./-]+\.(?:py|sh|mjs)")

# AND ITS FLAGS, BECAUSE ONE SCRIPT IS TWO CHECKS HERE. `docs-audit` and `audit-self-test` run
# the same file in different modes, and the hook runs a third — so a path match alone answers
# "on the commit path" for both, which this row caught on its first run against the tree it
# was written for. A check is on that path when the hook invokes its script IN ITS MODE.
#
# MATCHED PER LINE, AND IT WAS MATCHED OVER THE WHOLE FILE UNTIL D92. The sentence above is
# what this always meant; `path in hook and flag in hook` is not that, because the two can sit
# on different lines and mean nothing about each other. Adding a SECOND self-testing check to
# the hook proved it: `--self-test` then appeared in the file for `sigil-check`, and this row
# immediately reported `audit-self-test` — which the hook does not run, and which D18 requires
# it not to — as being on the commit path. A false negative would be worse than the loose
# match: it would report a check as gating commits when nothing runs it.
_RUNS_FLAG_RE = re.compile(r"--[a-z][a-z-]*")

CHECK_ENTRY_KEYS = (
    "target", "runs", "asserts", "needs", "writes",
    "commit_path", "why_off_commit_path", "gates", "governed_by",
)

# The parallel shards `.github/workflows/check.yml` runs in place of one `make ci-check`.
CI_SHARD_RULES = ("ci-check-product", "ci-check-static", "ci-check-guards-1", "ci-check-guards-2")


def _ci_check_recipe() -> Optional[List[str]]:
    """The targets `make ci-check` runs — the gate `.github/workflows/check.yml` invokes.

    RECONCILED AGAINST NOTHING UNTIL 2026-09-12, while `check registry`, `check census` and
    `commit path` all read the `check:` recipe alone. The Makefile's own header states the
    hazard in capitals — "IT IS A SUBSET AND CAN DRIFT FROM `check`" — and a target dropped
    from this one stops gating every pull request and every push in silence, which is the
    armed-hook defect with a runner in front of it.

    Membership only, deliberately, and never order: `check registry` owns the order of the
    `check:` recipe, and `ci-check` is ordered differently on purpose.
    """
    return _recipe_targets("ci-check")


# The marker a non-gating target's recipe has to print, so a reader of a green `make check`
# is not counting a slot that cannot fail among the ones that can (`gates: False` in
# scripts/checks.py). Paired in BOTH directions: a marker in a gating target's recipe is as
# wrong as a missing one in `vale`'s.
_NOT_A_GATE_MARKER = "NOT A GATE:"


def _checks_registry() -> Optional[Tuple[List[dict], dict]]:
    """(CHECKS, NEEDS) out of scripts/checks.py, by literal_eval and never by import.

    Same access `docs/map.py` and `scripts/status.py`'s SOURCES get, for the same reason: a
    read-only check must not execute the code it is checking.
    """
    if not exists(CHECKS_REGISTRY):
        return None
    values = literals_from_module(CHECKS_REGISTRY)
    entries, needs = values.get("CHECKS"), values.get("NEEDS")
    if not isinstance(entries, (list, tuple)) or not isinstance(needs, dict):
        return None
    return [dict(entry) for entry in entries], dict(needs)


def _check_registry() -> Row:
    """scripts/checks.py against the `check:` recipe it describes, both directions.

    THE REGISTRY IS A PARALLEL DECLARATION AND NOT THE DRIVER, which is the shape that makes
    this row necessary and also makes it safe. A registry that drove `make check` could not
    disagree with it — and could silently stop running a check, which is the failure this repo
    has paid for more than any other. A registry that merely describes it can only lie, and a
    lie is what a check can catch.

    ORDER IS CHECKED, not just membership. The file says its entries are in recipe order and
    `make explain` prints them that way, so a reader takes the order as the running order; a
    claim being read is a claim worth verifying, and it costs one comparison.

    **`ci-check` IS RECONCILED HERE TOO, AS OF 2026-09-12, and it had no reader at all.**
    `grep -c ci-check scripts/docs-audit.py` returned 0: three rows read the `check:` recipe
    and none read the gate `.github/workflows/check.yml` actually invokes on every pull
    request and every push. The Makefile's own header says "IT IS A SUBSET AND CAN DRIFT
    FROM `check`", which is a hazard written down and watched by nobody.

    The difference is DECLARED, not tolerated: a target in `check` and not in `ci-check`
    needs a `why_off_ci` sentence on its entry, and a target carrying that sentence while
    sitting in `ci-check` is as wrong as a missing one — the same pairing discipline
    `commit_path` / `why_off_commit_path` already keeps. Membership only, never order.
    Today the sole difference is `vale`, which the Makefile header already argues, so the
    extension starts green.

    **AND A SLOT THAT CANNOT FAIL SAYS SO AT RUN TIME.** `gates: False` was read by nothing:
    the field was declared honestly and the disclosure never reached the run a session
    reads. `vale` swallows its status with `--no-exit` and, with no binary, prints and exits
    0 — so a reader of a green `make check` counts 25 passing rows where 24 are gates. The
    entry's recipe has to print `NOT A GATE:`, in both directions, so `make explain`, the
    run and the reader agree. A GATING target is never forced to print anything; the point
    is disclosure, not removal, and the owner has ruled prose style worth running and not
    worth gating (D18, plus the bare-`python3` toolchain fact — D74's own text argues only
    that vale's file scope now matches `.vale.ini`, never that a prose check must not gate).
    """
    recipe = _check_recipe()
    ci_recipe = _ci_check_recipe()
    loaded = _checks_registry()
    if recipe is None:
        return Row("check registry", MECHANICAL, [Finding(
            "Makefile",
            "the `check:` recipe could not be read, so nothing can be reconciled against it. "
            "If the target changed shape, this row's reader has to move with it.")],
            "the `check:` recipe could not be read, so the registry was not checked")
    if loaded is None:
        return Row("check registry", MECHANICAL, [Finding(
            rel(CHECKS_REGISTRY),
            "CHECKS and NEEDS could not be read as module-level literals. They are parsed "
            "with `ast.literal_eval` and never imported, so every entry must stay a plain "
            "literal — no helper class, no call, no comprehension.")],
            "the registry file is missing or unreadable, so the recipe was not checked")

    entries, needs = loaded
    findings: List[Finding] = []

    declared = [str(entry.get("target", "")) for entry in entries]
    for name in recipe:
        if name not in declared:
            findings.append(Finding(rel(CHECKS_REGISTRY), (
                "`make check` runs `{0}` and no entry describes it.\n"
                "  Add one, or `make explain` and `make help` both under-report the suite."
            ).format(name)))
    for name in declared:
        if name not in recipe:
            findings.append(Finding(rel(CHECKS_REGISTRY), (
                "there is an entry for `{0}`, which `make check` does not run.\n"
                "  An entry for a check nobody runs reads as coverage."
            ).format(name)))
    if not findings and declared != recipe:
        findings.append(Finding(rel(CHECKS_REGISTRY), (
            "the entries are not in recipe order.\n"
            "  recipe:   {0}\n"
            "  registry: {1}"
        ).format(", ".join(recipe), ", ".join(declared))))

    for entry in entries:
        where = "{0} — {1}".format(rel(CHECKS_REGISTRY), entry.get("target", "<unnamed>"))
        missing = [key for key in CHECK_ENTRY_KEYS if key not in entry]
        if missing:
            findings.append(Finding(where, "entry is missing: {0}".format(", ".join(missing))))
            continue
        for token in entry["needs"]:
            if token not in needs:
                findings.append(Finding(where, (
                    "`needs` names `{0}`, which NEEDS does not define.\n"
                    "  A token nobody defined is a token nobody can reason about."
                ).format(token)))

    # NEEDS is a section of this file in D80's sense, and the same rule applies one level
    # down: a vocabulary entry no check claims is a definition with no reader.
    claimed = {token for entry in entries for token in entry.get("needs", ())}
    for token in sorted(set(needs) - claimed):
        findings.append(Finding(rel(CHECKS_REGISTRY), (
            "NEEDS defines `{0}` and no check needs it. Delete it or use it (D80)."
        ).format(token)))

    # ---- the OTHER gate: `make ci-check`, which every PR and push runs ------------------
    if ci_recipe is None:
        findings.append(Finding("Makefile", (
            "the `ci-check:` recipe could not be read, and `.github/workflows/check.yml` "
            "invokes it on every pull request and every push.\n"
            "  A subset nothing reconciles is a gate that can lose a target in silence.")))
    else:
        by_target = {str(entry.get("target", "")): entry for entry in entries}
        for name in ci_recipe:
            if name not in recipe:
                findings.append(Finding("Makefile", (
                    "`make ci-check` runs `{0}` and `make check` does not.\n"
                    "  ci-check is a SUBSET of check by the Makefile's own header. A target "
                    "only CI runs is one a session cannot reproduce before pushing."
                ).format(name)))
        for name in recipe:
            if name in ci_recipe:
                continue
            entry = by_target.get(name)
            reason = str((entry or {}).get("why_off_ci") or "").strip()
            if not reason:
                findings.append(Finding(
                    "{0} — {1}".format(rel(CHECKS_REGISTRY), name),
                    "`make check` runs it and `make ci-check` does not, and the entry says "
                    "nothing about why.\n"
                    "  Either add it to the ci-check recipe, or give the entry a "
                    "`why_off_ci` sentence. A target silently absent from the gate that "
                    "runs on every PR has stopped gating anything, and the run is green "
                    "because it never happened.",
                ))
        for name, entry in sorted(by_target.items()):
            if str(entry.get("why_off_ci") or "").strip() and name in ci_recipe:
                findings.append(Finding(
                    "{0} — {1}".format(rel(CHECKS_REGISTRY), name),
                    "carries `why_off_ci` and `make ci-check` runs it. The sentence explains "
                    "an absence that is over; delete it, or the next reader believes CI does "
                    "not run this.",
                ))

    # ---- CI runs `ci-check` as shards; their union is `ci-check`, target for target -----
    shards = [_recipe_targets(rule) for rule in CI_SHARD_RULES]
    if ci_recipe is not None:
        for rule, body in zip(CI_SHARD_RULES, shards):
            if body is None:
                findings.append(Finding("Makefile", (
                    "the `{0}:` recipe could not be read, and `.github/workflows/check.yml` "
                    "runs it as one of the parallel shards of `ci-check`."
                ).format(rule)))
        if all(body is not None for body in shards):
            ran = [name for body in shards for name in body]
            for name in ci_recipe:
                if name not in ran:
                    findings.append(Finding("Makefile", (
                        "`make ci-check` runs `{0}` and no CI shard does.\n"
                        "  A target in no shard gates nothing on a pull request, and the "
                        "`check` job is green because it never ran."
                    ).format(name)))
            for name in sorted(set(ran)):
                if name not in ci_recipe:
                    findings.append(Finding("Makefile", (
                        "a CI shard runs `{0}` and `make ci-check` does not.\n"
                        "  A session cannot reproduce it before pushing."
                    ).format(name)))
                elif ran.count(name) > 1:
                    findings.append(Finding("Makefile", (
                        "`{0}` is in more than one CI shard, or twice in one.\n"
                        "  Each target runs once."
                    ).format(name)))

    # ---- a slot in `make check` that cannot fail says so where the run is read ----------
    makefile_text = read(ROOT / "Makefile") if exists(ROOT / "Makefile") else ""
    for entry in entries:
        name = str(entry.get("target", ""))
        if "gates" not in entry:
            continue
        body = _make_recipe(makefile_text, name)
        if body is None:
            continue  # `check registry`'s membership legs above already name a missing rule
        printed = any(_NOT_A_GATE_MARKER in line for line in body)
        if not entry["gates"] and not printed:
            findings.append(Finding(
                "Makefile — {0}".format(name),
                "is declared `gates: False` and its recipe never says so.\n"
                "  It occupies a slot in `make check` that cannot fail, and a reader of a "
                "green run counts it among the ones that can. Print `{0}` in the recipe — "
                "the disclosure is the point, not removing the target.".format(
                    _NOT_A_GATE_MARKER),
            ))
        elif entry["gates"] and printed:
            findings.append(Finding(
                "Makefile — {0}".format(name),
                "prints `{0}` and its entry declares `gates: True`. One of the two is "
                "wrong, and the recipe is what a session reads.".format(_NOT_A_GATE_MARKER),
            ))

    ungated = sum(1 for entry in entries if entry.get("gates") is False)
    return Row("check registry", MECHANICAL, findings,
               "{0} checks in recipe order, {1} in ci-check, {2} declared non-gating".format(
                   len(recipe), len(ci_recipe or ()), ungated),
               scanned=len(recipe))


## ---- commit-path writes, read from the AST rather than from `checks.py`'s own sentence ----
#
# The row below used to take `writes` on faith: an empty string passed, any text failed. That
# reads the registry's OPINION of itself, never the check's actual Python — a check on the
# commit path could open a file for writing and this row would still print "none of them
# writing", because `writes` and this row's verdict were the same claim typed twice.
#
# WHAT COUNTS AS A WRITE, decided here because it is the hard part:
#
#   - `open(...)` (or its `mode=` keyword) with a mode containing "w", "a", "x" or "+".
#   - `Path`-shaped methods, matched BY NAME because AST carries no types: `write_text`,
#     `write_bytes`, `write`, `writelines`, `touch`, `unlink`, `rmdir`, `mkdir`, `rename`,
#     `chmod`, `symlink_to`, `hardlink_to`. `replace` is dropped from this unresolved-name
#     bucket on purpose — `str.replace()` is common through this file and `Path.replace()` is
#     not, so counting it here would fail the row on ordinary string code. It is still caught
#     as `os.replace(...)`, which is unambiguous.
#   - `os.remove/replace/rename/mkdir/makedirs/rmdir/unlink/chmod/symlink/system/popen`, and
#     `shutil.copy*/move/rmtree/make_archive`, resolved through the file's own top-level
#     `import os` / `import shutil` (or `as` alias) so a same-named method on an unrelated
#     object is not mistaken for the stdlib one.
#   - `subprocess.run/call/Popen/check_call/check_output`, but ONLY when every element of its
#     argv is a literal string and one of those literals is a write-shaped git verb (commit,
#     push, checkout, reset, merge, rm, mv, stash, rebase, cherry-pick, apply, clean, gc,
#     prune, init, add). An argv built from a variable, `*args`, or an f-string is invisible
#     to this reader — see the blind spots below, it is not treated as clean.
#
# MODE-SCOPED, NOT WHOLE-FILE: `docs-audit.py` dispatches on `args.self_test` inside `main()`
# and only ONE branch runs for a given invocation. Scanning the whole file would find every
# `write_text` call inside `--self-test`'s own fixtures and blame them on the plain
# `python3 scripts/docs-audit.py` invocation that never reaches that branch — the same shape
# of false claim this row exists to stop, aimed at itself. So this walks `main()`'s own
# top-level `if` statements, keeps only the branch(es) whose test names a flag this
# INVOCATION actually passes (an `if` testing no flag is not a mode gate and both its arms are
# kept), takes the calls named there as seeds, and closes over every LOCALLY DEFINED function
# reachable from those seeds by a plain `name(...)` call, or by a plain reference to the name
# of a MODULE-LEVEL function, recursively. Module top-level statements (imports, regex `re.compile`, constant tables) are
# always included; they run at import time regardless of mode.
#
# A SCRIPT THAT KEEPS ITS CODE IN A PACKAGE BESIDE IT IS READ THROUGH THE PACKAGE. `docs-audit.py`
# is a thin entry point and every row lives in `scripts/docs_audit/`, so reading the entry alone
# would close over three functions and find no write in code it never opened: a pass that proves
# nothing. Every package the entry imports from its own directory is read as one program, each
# function against its own module's imports. The rows are reached by name reference, not by
# call: `rows.ROWS` names each check and `rows.audit` calls it through the table. Every name a
# package module's top-level statements mention seeds the closure, which is how the checks come
# in. A reference counts as reachable because a function handed around as a value runs. Only a
# module-level function is followed by reference: a nested function or a method shares its name
# with variables and modules (`dispatch`, `error`), and a call is the only proof it is meant.
#
# WHAT THIS CANNOT SEE, stated rather than assumed away:
#   - A write behind an alias this file cannot resolve: `f = Path.write_text; f(p, s)`,
#     or a write reached only through a base class's overridden method (argparse calling
#     `self.error()`, which calls `sys.stderr.write()`, is invisible here for exactly that
#     reason — it is never named as a plain call in this file's own control flow).
#   - A write inside a called LIBRARY. `json.dumps` is read, not written; if a project
#     dependency writes a file on its own initiative, nothing here follows it in.
#   - A write performed by a `subprocess` call whose argv is computed — `git(*args)` in this
#     very file is exactly that shape, called throughout with read-only git subcommands, and
#     every one of those calls is invisible to this reader rather than cleared by it.
#   - A dispatch this file's `main()` does not shape as "an `if` testing a flag, calling one
#     function, then returning" — a script with a different mode-switch shape gets read as
#     whole-file, which over-reports rather than under-reports.
#   - Mode-scoping ITSELF only runs on the invoked script's own `main()`. A write two calls
#     deep inside a function that is only reachable from a *different* branch than the one
#     analyzed is correctly excluded; a write reachable from BOTH branches by different
#     names (unusual) is correctly included once either branch is taken.
#
# Measured against the two checks this applies to: `docs-audit` (`python3 scripts/docs-audit.py`,
# no flags) closes over the package's check functions and finds no write evidence — `self_test()`
# and its fixture writers are provably excluded, not merely assumed off-path, and the two opaque
# `subprocess` calls in its reachable set (`git(*args)` and a `node scripts/user-strings.mjs ...`
# invocation whose argv is spread from a `*args` parameter) are named above rather than
# cleared. `sigil-check` (both `--self-test` and its bare invocation, since the hook runs both)
# contains no write-shaped call of any kind — it does not import `os`, `shutil` or `subprocess`
# at all. So `scripts/docs-audit.py`'s own docstring claim, "THE AUDIT NEVER WRITES", HOLDS for
# the reachable code this reads, with the blind spots above never having been asked to clear it.

_WRITE_METHODS_UNRESOLVED_ROOT = frozenset({
    "write_text", "write_bytes", "write", "writelines", "touch",
    "unlink", "rmdir", "mkdir", "rename", "chmod", "symlink_to", "hardlink_to",
})
_OS_WRITE_FUNCS = frozenset({
    "remove", "replace", "rename", "mkdir", "makedirs", "rmdir", "unlink",
    "chmod", "symlink", "system", "popen",
})
_SHUTIL_WRITE_FUNCS = frozenset({"copy", "copyfile", "copy2", "copytree", "move", "rmtree",
                                 "make_archive"})
_SUBPROCESS_FUNCS = frozenset({"run", "call", "Popen", "check_call", "check_output"})
_SUBPROCESS_WRITE_TOKENS = frozenset({
    "commit", "push", "checkout", "reset", "merge", "rm", "mv", "stash", "rebase",
    "cherry-pick", "apply", "clean", "gc", "prune", "init", "add",
})


def _import_aliases(tree: ast.Module) -> Dict[str, str]:
    """Every `import x` / `import x as y` in the file -> real module name, for `os`/`shutil`/
    etc. Walked over the WHOLE module rather than only its top level, because a local
    `import shutil as _sh` inside a function is exactly as real as one at the top."""
    aliases: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                aliases[alias.asname or root] = root
    return aliases


def _attr_root_module(value: ast.expr, aliases: Dict[str, str]) -> Optional[str]:
    """For `os.remove(...)`'s `os`, the real module name behind the name — or None."""
    if isinstance(value, ast.Name):
        return aliases.get(value.id)
    return None


def _static_str_list(node: Optional[ast.expr]) -> Optional[List[str]]:
    """A `[...]`/`(...)` of only string literals, or None if any element is not one."""
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    out: List[str] = []
    for elt in node.elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            out.append(elt.value)
        else:
            return None
    return out


def _write_evidence(nodes: Iterable[ast.AST], aliases: Dict[str, str]) -> List[str]:
    """Write-shaped `Call` nodes under `nodes`, per the vocabulary argued above."""
    evidence: List[str] = []
    for root in nodes:
        for node in ast.walk(root):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            line = getattr(node, "lineno", "?")
            if isinstance(func, ast.Name) and func.id == "open":
                mode = None
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    mode = node.args[1].value
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        mode = kw.value.value
                if isinstance(mode, str) and any(c in mode for c in "wax+"):
                    evidence.append("open(..., mode={0!r}) at line {1}".format(mode, line))
                continue
            if not isinstance(func, ast.Attribute):
                continue
            attr = func.attr
            root_mod = _attr_root_module(func.value, aliases)
            if root_mod == "os" and attr in _OS_WRITE_FUNCS:
                evidence.append("os.{0}(...) at line {1}".format(attr, line))
            elif root_mod == "shutil" and attr in _SHUTIL_WRITE_FUNCS:
                evidence.append("shutil.{0}(...) at line {1}".format(attr, line))
            elif root_mod == "subprocess" and attr in _SUBPROCESS_FUNCS:
                argv = _static_str_list(node.args[0] if node.args else None)
                if argv is None:
                    continue  # opaque argv — a named blind spot, never counted as clean
                if any(tok in _SUBPROCESS_WRITE_TOKENS for tok in argv):
                    evidence.append("subprocess.{0}({1!r}) at line {2}".format(attr, argv, line))
            elif root_mod is None and attr in _WRITE_METHODS_UNRESOLVED_ROOT:
                evidence.append(".{0}(...) at line {1}".format(attr, line))
    return sorted(set(evidence))


def _mode_test_flags(test: ast.expr) -> Set[str]:
    """Flags an `if` test names, either as a literal (`"--self-test" in argv`) or as an
    `args.<dest>` attribute (`if args.self_test:`), normalized to `--dashed-form`."""
    flags: Set[str] = set()
    for node in ast.walk(test):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value.startswith("--"):
                flags.add(node.value)
        elif isinstance(node, ast.Attribute) and not node.attr.startswith("__"):
            flags.add("--" + node.attr.replace("_", "-"))
    return flags


def _calls_in(stmts: Sequence[ast.stmt]) -> Set[str]:
    """Plain `name(...)` call targets under `stmts` — never `obj.method(...)`, which this
    reader cannot resolve to a local function without running the program."""
    names: Set[str] = set()
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                names.add(node.func.id)
    return names


def _has_return(stmts: Sequence[ast.stmt]) -> bool:
    return any(isinstance(n, ast.Return) for stmt in stmts for n in ast.walk(stmt))


def _entry_point_seeds(main_fn: ast.FunctionDef, invocation_flags: FrozenSet[str]) -> Set[str]:
    """Which of `main()`'s own calls actually run for one invocation, given its flags.

    Reads `main()`'s top-level statements in order. A plain statement always contributes its
    calls. An `if` whose test names no flag (`_mode_test_flags` finds nothing) is not a mode
    gate — both its arms are read, conservatively, since this reader cannot evaluate the
    condition. An `if` that DOES name a flag is a mode gate: its body's calls are taken only
    when that flag is in `invocation_flags`, and if that body contains a `return`, nothing
    after it in `main()` runs for this invocation either (the common `if args.x: return y()`
    early-exit shape both scripts here use).
    """
    seeds: Set[str] = set()
    for stmt in main_fn.body:
        if isinstance(stmt, ast.If):
            flags_here = _mode_test_flags(stmt.test)
            if not flags_here:
                seeds |= _calls_in(stmt.body)
                seeds |= _calls_in(stmt.orelse)
                continue
            if flags_here & invocation_flags:
                seeds |= _calls_in(stmt.body)
                if _has_return(stmt.body):
                    return seeds
            continue
        seeds |= _calls_in([stmt])
    return seeds


def _local_functions(tree: ast.Module) -> Dict[str, ast.AST]:
    return {n.name: n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _call_closure(seed_names: Iterable[str], funcs: Dict[str, List[Tuple[ast.AST, Dict[str, str]]]],
                  module_level: Optional[Set[str]] = None,
                  ) -> List[Tuple[ast.AST, Dict[str, str]]]:
    """Every locally defined function reachable from `seed_names`, transitively, each with the
    import aliases of the module it is defined in. A function is reached by a plain `name(...)`
    call, or, when it is module-level, by a plain reference to its name; `obj.method(...)` is not
    followed — see the blind spots above. Every function of a given name is taken, since two
    modules may define one.
    """
    by_reference = module_level if module_level is not None else set()
    visited: Set[str] = set()
    frontier: Set[str] = set(seed_names)
    nodes: List[Tuple[ast.AST, Dict[str, str]]] = []
    while frontier:
        name = frontier.pop()
        if name in visited:
            continue
        visited.add(name)
        for fn, aliases in funcs.get(name, []):
            nodes.append((fn, aliases))
            for node in ast.walk(fn):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id not in visited):
                    frontier.add(node.func.id)
                elif isinstance(node, ast.Name) and node.id in by_reference and node.id not in visited:
                    frontier.add(node.id)
    return nodes


def _package_trees(script: Path, tree: ast.Module) -> List[ast.Module]:
    """The parsed modules of every package `script` imports from its own directory.

    A package here is a directory beside the script that holds an `__init__.py`. Read through
    `read` and `glob_files`, so `--staged` sees the index, the same as every other source.
    """
    roots: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
    trees: List[ast.Module] = []
    for root in sorted(roots):
        directory = script.parent / root
        if not exists(directory / "__init__.py"):
            continue
        for module_path in glob_files(directory, "*.py"):
            try:
                trees.append(ast.parse(read(module_path)))
            except SyntaxError:
                continue
    return trees


def _split_invocations(runs: str) -> List[Tuple[str, FrozenSet[str]]]:
    """`entry["runs"]` into (script path, flags) pairs, one per `&&`/`;`-joined command.

    `sigil-check` runs its script TWICE in one hook step, once with `--self-test` and once
    bare, and the hook literally executes both — so both are separate invocations to analyze,
    not one union of flags. A `|` pipeline or a subshell would not be split correctly; neither
    shape appears in `scripts/checks.py` today.
    """
    out: List[Tuple[str, FrozenSet[str]]] = []
    for part in re.split(r"&&|;", runs):
        paths = _RUNS_PATH_RE.findall(part)
        script = next((p for p in paths if p.endswith(".py")), None)
        if script is None:
            continue
        flags = frozenset(_RUNS_FLAG_RE.findall(part))
        out.append((script, flags))
    return out


def _commit_path_write_evidence(entry: dict) -> Optional[List[str]]:
    """Write evidence for one `checks.py` entry's `runs`, mode-scoped per invocation.

    None means no `.py` invocation could be read at all (a shell pipeline, a missing file,
    a syntax error) — the caller reports that as its own finding rather than guessing clean.
    """
    invocations = _split_invocations(str(entry.get("runs", "")))
    if not invocations:
        return None
    evidence: List[str] = []
    saw_any = False
    for script, flags in invocations:
        path = ROOT / script
        if not exists(path):
            continue
        try:
            tree = ast.parse(read(path))
        except SyntaxError:
            continue
        saw_any = True
        aliases = _import_aliases(tree)
        own_funcs = _local_functions(tree)
        funcs: Dict[str, List[Tuple[ast.AST, Dict[str, str]]]] = {
            name: [(fn, aliases)] for name, fn in own_funcs.items()}
        main_fn = own_funcs.get("main")
        top_level = [s for s in tree.body
                     if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef,
                                            ast.ClassDef, ast.Import, ast.ImportFrom))]
        package_top: List[Tuple[ast.stmt, Dict[str, str]]] = []
        package_seeds: Set[str] = set()
        module_level: Set[str] = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        for package_tree in _package_trees(path, tree):
            package_aliases = _import_aliases(package_tree)
            module_level.update(n.name for n in package_tree.body if isinstance(n, ast.FunctionDef))
            for name, fn in _local_functions(package_tree).items():
                funcs.setdefault(name, []).append((fn, package_aliases))
            for stmt in package_tree.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                                     ast.Import, ast.ImportFrom)):
                    continue
                package_top.append((stmt, package_aliases))
                package_seeds.update(n.id for n in ast.walk(stmt) if isinstance(n, ast.Name))
        package_seeds &= module_level
        if main_fn is None:
            # No `main()` to mode-scope from — read the whole module rather than guess a mode.
            nodes = [pair for pairs in funcs.values() for pair in pairs]
        else:
            seeds = _entry_point_seeds(main_fn, flags) | package_seeds
            nodes = _call_closure(seeds, funcs, module_level)
        for fn, fn_aliases in nodes:
            evidence.extend(_write_evidence([fn], fn_aliases))
        evidence.extend(_write_evidence(top_level, aliases))
        for stmt, stmt_aliases in package_top:
            evidence.extend(_write_evidence([stmt], stmt_aliases))
    if not saw_any:
        return None
    return sorted(set(evidence))


def check_commit_path(report: Report) -> None:
    """D18, asserted mechanically for the first time.

    **Nothing that writes may run on the path that decides whether a commit proceeds.** That
    rule is quoted in five Makefile comments, in `docs/decisions/` D18 and D16, and in the
    header of every self-test it governs — and until this row it was enforced by nobody. It is
    the most-cited rule in this repo with the least machinery behind it.

    Four claims, and the fourth is the one with teeth — and reads the CODE, not `checks.py`'s
    own sentence about itself (see the block comment above this function for what "reads" is
    defined to mean, and what it cannot see):

      1. `commit_path` agrees with `scripts/githooks/pre-commit`. Asked of the SCRIPT the
         entry runs and never of the target name: the hook invokes
         `python3 scripts/docs-audit.py --staged`, so a name match would answer no for the one
         entry that is genuinely on that path.
      2. `why_off_commit_path` is present exactly where `commit_path` is false. An entry
         claiming both, or neither, is describing nothing.
      3. A commit-path entry whose AST shows write evidence and whose `writes` field is empty
         fails. This is the defect this row exists to fix: `writes` was read as true/false
         with nobody ever inspecting the source it claims to summarize.
      4. A commit-path entry whose `writes` field is non-empty and whose AST shows no write
         evidence fails too — a stale declaration is checked in both directions, the same
         discipline `t3_join_coverage`'s own docstring argues for the join
         ("a one-directional check passes on that bug").

    A check whose `runs` names no repository path — `npm --prefix app run lint`, the vale
    pipeline — cannot be on the commit path, because the hook runs a bare python3 with nothing
    installed. So the absence of a path is itself the answer, rather than a case this row
    declines to judge.
    """
    loaded = _checks_registry()
    if loaded is None:
        report.add("commit path", MECHANICAL, [Finding(
            rel(CHECKS_REGISTRY), "CHECKS could not be read; see the `check registry` row.")])
        return
    if not exists(PRE_COMMIT):
        report.add("commit path", MECHANICAL, [Finding(
            rel(PRE_COMMIT),
            "does not exist, and every entry's `commit_path` is a claim about it.")])
        return

    entries, _ = loaded
    hook = read(PRE_COMMIT)
    findings: List[Finding] = []
    on_path = 0
    verified = 0

    for entry in entries:
        if not all(key in entry for key in CHECK_ENTRY_KEYS):
            continue  # `check registry` reports the shape; this row does not repeat it
        name = entry["target"]
        where = "{0} — {1}".format(rel(CHECKS_REGISTRY), name)
        paths = _RUNS_PATH_RE.findall(entry["runs"])
        flags = _RUNS_FLAG_RE.findall(entry["runs"])
        invoked = any(
            any(path in line for path in paths) and all(flag in line for flag in flags)
            for line in hook.splitlines()
        )
        claimed = bool(entry["commit_path"])

        if claimed and not invoked:
            findings.append(Finding(where, (
                "claims the commit path, and {0} invokes none of {1}."
            ).format(rel(PRE_COMMIT), ", ".join(paths) or "the commands it runs")))
        elif invoked and not claimed:
            findings.append(Finding(where, (
                "says it is off the commit path, but {0} runs {1} in that mode.\n"
                "  Whichever is wrong, D18 is being reasoned about from a false premise."
            ).format(rel(PRE_COMMIT), ", ".join(p for p in paths if p in hook))))

        if claimed:
            on_path += 1
            declared_writes = bool(entry["writes"])
            evidence = _commit_path_write_evidence(entry)
            if evidence is None:
                findings.append(Finding(where, (
                    "claims the commit path, and no `.py` invocation in `runs` could be "
                    "parsed to check it — nothing here says clean, and this row will not "
                    "guess. Fix `runs`, or read it by hand and record why not.")))
            else:
                verified += 1
                code_writes = bool(evidence)
                if code_writes and declared_writes:
                    findings.append(Finding(where, (
                        "IS ON THE COMMIT PATH AND WRITES: {0}\n"
                        "  D18: nothing that writes may run on the path that decides whether "
                        "a\n  commit proceeds. An agent that can edit what its own gate reads "
                        "will."
                    ).format(entry["writes"])))
                elif code_writes and not declared_writes:
                    findings.append(Finding(where, (
                        "IS ON THE COMMIT PATH AND WRITES, AND `writes` SAYS NOTHING: {0}\n"
                        "  This is the defect `commit path` exists to catch: `writes` was "
                        "read\n  as true/false with nobody inspecting the source it claims "
                        "to summarize.\n  D18: nothing that writes may run on the path that "
                        "decides whether a\n  commit proceeds."
                    ).format("; ".join(evidence))))
                elif declared_writes and not code_writes:
                    findings.append(Finding(where, (
                        "declares `writes`: {0!r}, and the AST reads no write on this "
                        "invocation's reachable path.\n"
                        "  A stale declaration is checked in both directions here — see this "
                        "row's own comment for what the read can and cannot see before "
                        "trusting either side."
                    ).format(entry["writes"])))
            if entry["why_off_commit_path"]:
                findings.append(Finding(where, (
                    "claims the commit path and also carries `why_off_commit_path`.")))
        elif not entry["why_off_commit_path"]:
            findings.append(Finding(where, (
                "is off the commit path and says nothing about why.\n"
                "  D18 or a toolchain — the reason is what a later session needs, and it is\n"
                "  the field that stops one being moved back on to the path by tidiness.")))

    report.add("commit path", MECHANICAL, findings,
               "{0} of {1} on the commit path, {2} of them read against source, none "
               "writing".format(on_path, len(entries), verified),
               scanned=len(entries))


# ------------------------------------------------ the browser fleet, and the lock it takes
#
# `make design-check` is the one target here that spends the whole machine — Playwright's
# `fullyParallel` at half the cores, each worker a Chromium context over its own Vite dev
# server. D43 gave every checkout its own ports and its own store; the CPU is what it could
# not copy, and two trees running the fleet at once starve each other into failures that are
# not in the code (D122, and `scripts/suite-lock.py` carries the 2026-09-07 measurement).
#
# THE GUARD IS ONE LINE OF ONE RECIPE, WHICH IS EXACTLY THE KIND OF LINE THAT GOES MISSING.
# A second browser suite landing under its own target would be unguarded and green, and the
# only symptom would be somebody else's re-run. So this row reads the RUNNER rather than the
# target name: any npm script whose command is `playwright test` is a fleet, and every
# Makefile recipe that reaches one has to go through the lock.
SUITE_LOCK_SCRIPT = ROOT / "scripts" / "suite-lock.py"

#: What makes a script a fleet: `playwright test`, the only runner here that draws pages in
#: PARALLEL. `scripts/screenshot.sh` and `scripts/screenshot.mjs` render one page at a time and
#: are deliberately NOT covered — see D122, which argues the exclusion on the SHAPE of the run
#: rather than on a command name, having named a stale one for a day and been corrected.
_FLEET_RUNNER_RE = re.compile(r"\bplaywright\s+test\b")

#: The runners this row reads besides the Makefile and app/package.json. A fleet does not have to
#: arrive as an npm script: `scripts/screenshot.sh` is a shell script that shells out to a node
#: script that drives Playwright, and either could grow `playwright test` without touching a
#: recipe. Reading them is what makes the previous comment a checked claim rather than a promise.
FLEET_RUNNER_SCRIPTS = ("screenshot.sh", "screenshot.mjs")


def _npm_run_re(script: str) -> "re.Pattern[str]":
    """A recipe line reaching an npm script, with or without `--prefix`."""
    return re.compile(r"\bnpm\b[^\n]*\brun\s+" + re.escape(script) + r"\b")


def check_suite_lock(report: Report) -> None:
    """Every Makefile recipe that starts a Playwright fleet goes through the lock.

    MECHANICAL, and in both directions: a fleet script no recipe reaches is reported as much
    as a recipe that reaches one without the lock. The first is the drift that would happen —
    a new browser target, written from the old one, without the line that matters.

    IT REFUSES TO GO QUIET, on `check census`'s reasoning. If `app/package.json` holds no
    script this row recognises as a fleet, that is REPORTED rather than passed: the runner
    was renamed or the suite moved, and either way a guard that silently starts covering
    nothing is the failure it exists to prevent.

    IT READS THE OTHER RUNNERS TOO, AND THAT IS THE DIRECTION D122 GOT WRONG ONCE. A fleet does
    not have to arrive as an npm script — `scripts/screenshot.sh` shells out to
    `scripts/screenshot.mjs`, which drives Playwright directly, and either could grow
    `playwright test` without a recipe changing. D122's first draft excluded that path by NAME
    (`playwright screenshot`), and the name was stale the day it merged. Reading the files is
    what turns "those render one page at a time" from a promise into a checked claim.

    WHAT IT DOES NOT CHECK: that the lock WORKS. `make suite-lock-selftest` does that, by
    violating it. This row settles only that the thing which spends the machine is behind it.
    """
    findings: List[Finding] = []

    if not exists(SUITE_LOCK_SCRIPT):
        report.add("suite lock", MECHANICAL, [Finding(
            rel(SUITE_LOCK_SCRIPT),
            "does not exist, and `make design-check` is written to run through it.")])
        return

    try:
        package = json.loads(read(ROOT / "app" / "package.json"))
        scripts = {str(k): str(v) for k, v in (package.get("scripts") or {}).items()}
    except (OSError, ValueError) as exc:
        report.add("suite lock", MECHANICAL, [Finding(
            "app/package.json", "could not be read, so no fleet can be identified.\n%s" % exc)])
        return

    fleets = sorted(name for name, body in scripts.items() if _FLEET_RUNNER_RE.search(body))
    if not fleets:
        report.add("suite lock", MECHANICAL, [Finding(
            "app/package.json", (
                "holds no script that runs `playwright test`, so this row is watching\n"
                "  nothing. Either the fleet moved or the runner was renamed — the pattern\n"
                "  has to move with it, or the guard covers a suite that no longer exists."))])
        return

    lines = read(ROOT / "Makefile").splitlines()
    for script in fleets:
        pattern = _npm_run_re(script)
        callers = [(n + 1, line) for n, line in enumerate(lines)
                   if line.startswith("\t") and pattern.search(line)]
        if not callers:
            findings.append(Finding("app/package.json", (
                "`{0}` runs a Playwright fleet and no Makefile recipe reaches it.\n"
                "  A fleet nobody can start is dead, and a fleet started from somewhere this\n"
                "  row cannot see is unguarded. Either is worth a look."
            ).format(script)))
            continue
        for line_no, line in callers:
            if "suite-lock.py" not in line:
                findings.append(Finding("Makefile:{0}".format(line_no), (
                    "starts the `{0}` fleet without taking the machine-wide lock.\n"
                    "  Two fleets at once starve each other and BOTH report failures that are\n"
                    "  not in the code. Run it through `python3 scripts/suite-lock.py run -- "
                    "…` (D122)."
                ).format(script)))

    # The direct form, which no npm script mediates: a recipe calling the runner itself.
    for n, line in enumerate(lines):
        if not line.startswith("\t") or not _FLEET_RUNNER_RE.search(line):
            continue
        if "suite-lock.py" not in line:
            findings.append(Finding("Makefile:{0}".format(n + 1), (
                "runs `playwright test` directly without taking the machine-wide lock "
                "(D122).")))

    # The runners D122 excludes by SHAPE. Each is expected to exist and to stay serial; a
    # `playwright test` appearing in one is a fleet that reaches no recipe this row can read.
    for name in FLEET_RUNNER_SCRIPTS:
        target = ROOT / "scripts" / name
        if not exists(target):
            findings.append(Finding("scripts/{0}".format(name), (
                "does not exist, and D122 excludes `make screenshot` from the lock on the\n"
                "  strength of what this file does. Either it moved, or the exclusion needs\n"
                "  re-arguing against whatever replaced it.")))
            continue
        for n, line in enumerate(read(target).splitlines()):
            if _FLEET_RUNNER_RE.search(line) and "suite-lock.py" not in line:
                findings.append(Finding("scripts/{0}:{1}".format(name, n + 1), (
                    "runs `playwright test`, so it is a fleet. D122 excludes this file from\n"
                    "  the machine-wide lock because it renders one page at a time; that\n"
                    "  argument does not survive a parallel runner. Take the lock, or reopen\n"
                    "  D122's exclusion.")))

    report.add("suite lock", MECHANICAL, findings,
               "{0} fleet script{1} behind the lock, {2} serial renderers still serial".format(
                   len(fleets), "" if len(fleets) == 1 else "s", len(FLEET_RUNNER_SCRIPTS)),
               scanned=len(fleets) + len(FLEET_RUNNER_SCRIPTS))


# ------------------------------------------------------------ the browser matrix's scope
#
# `.github/workflows/check.yml` runs its browser matrix on a pull request only when the change
# touches a path `scripts/browser-scope.py:SCOPE` names (D141). A path filter is the one gate
# whose failure is INVISIBLE: too narrow, and the matrix stops running for a class of change,
# the run is green because it never happened, and the green is believed. That is the armed
# hook's defect from `scripts/githooks/pre-commit`'s own header, one level up — and the reason
# D141 rules that the filter does not ship without this row.
#
# THE LIST IS RECONCILED AGAINST WHAT THE SUITE LOADS, NOT AGAINST A SECOND LIST. Each
# dependency below is READ from the thing that creates it: Playwright's `testDir`, its reporter
# and its imports out of `app/playwright.config.ts`; Vite's root out of `app/vite.config.ts`,
# with any relative literal there that reaches outside `app/`; every code string in a spec or
# a module that names a tracked file outside `app/` (how `cadence.spec.ts`'s traces are found);
# every `scripts/` file the `design-check` recipe names; and the gate's own two files. A
# dependency the scope does not cover fails; an entry that covers nothing tracked fails; a
# `within` narrowing that names a recipe the Makefile no longer has fails.
#
# AND THE WIRING IS READ, because a list nothing consults is a list. The workflow must run the
# classifier from some job, `design-check` must need that job and read its answer in the
# FAIL-OPEN spelling — `!= 'false'` under `!cancelled()` — the `on:` block may carry no path
# filter (that would gate `check`, `revert-guard` and `already-passed` too, which D141
# forbids), and `design-check-passed` may not run on a skipped matrix, or a tree no browser
# saw would earn D136's pass record.
#
# WHAT IT CANNOT SEE, by name: a path a spec composes at runtime from pieces; a Vite
# `server.fs.allow` widening written in a form these regexes do not read; and a code string
# on the same line as a `//` inside a URL, which the comment blanker takes with it. Each is a
# miss and never a false finding.
BROWSER_SCOPE_SCRIPT = ROOT / "scripts" / "browser-scope.py"
SERVE_SCOPE_SCRIPT = ROOT / "scripts" / "serve-scope.py"
SERVE_SELFTEST_SCRIPT = ROOT / "scripts" / "serve-selftest.py"
GUARD_SCOPE_SCRIPT = ROOT / "scripts" / "guard-scope.py"
CHECK_WORKFLOW = ROOT / ".github" / "workflows" / "check.yml"
PLAYWRIGHT_CONFIG = ROOT / "app" / "playwright.config.ts"
VITE_CONFIG = ROOT / "app" / "vite.config.ts"
APP_DIR = ROOT / "app"

#: A code string naming something tracked outside `app/` — the shape `cadence.spec.ts` keys
#: its TRACES table by. The prefixes are the tree's top-level directories a spec could plausibly
#: read; a literal that resolves to nothing tracked is prose and is ignored.
_REPO_LITERAL_RE = re.compile(
    r"""['"`]((?:harness|docs|fixtures|scripts|server|store|pipeline|cli|identify|geometry|"""
    r"""codes|demo-assets|inventory)/[\w./@+-]+)['"`]"""
)
#: A `./x` or `../x` literal in one of the two configs — an import, a `testDir`, a reporter
#: path, an alias target. Resolved against `app/`; the ones that leave it are dependencies.
_RELATIVE_LITERAL_RE = re.compile(r"""['"`](\.\.?/[^'"`\n]*)['"`]""")
_TESTDIR_RE = re.compile(r"\btestDir:\s*['\"]([^'\"]+)['\"]")
_VITE_ROOT_RE = re.compile(r"^\s*root:\s*['\"]([^'\"]+)['\"]", re.M)
_SCOPE_STEP_RE = re.compile(r"python3\s+scripts/browser-scope\.py\s+classify\b")
_YAML_JOB_KEY_RE = re.compile(r"^  ([a-z][\w-]*):\s*$")


def _tracked_paths() -> Set[str]:
    """Every tracked path, from the index in staged mode and from git otherwise."""
    return set(core._INDEX_PATHS) if core._INDEX_PATHS is not None else _nul_list("ls-files", "-z")


def _app_relative(literal: str, base_dir: Path = APP_DIR) -> str:
    """A relative literal from a file in `base_dir`, as a repo-relative path (never resolved
    through the filesystem, so a target that does not exist still has a name)."""
    return os.path.relpath(os.path.normpath(str(base_dir / literal)), str(ROOT))


def _import_target(name: str, tracked: Set[str]) -> str:
    """`./devPort` is `app/devPort.ts` on disk; try the resolutions Node would."""
    for suffix in ("", ".ts", ".tsx", "/index.ts"):
        candidate = _app_relative(name + suffix)
        if candidate in tracked:
            return candidate
    return _app_relative(name)


def _yaml_top_block(text: str, key: str) -> Optional[str]:
    """The lines of one top-level key of a workflow file, up to the next top-level key."""
    lines = text.split("\n")
    out: List[str] = []
    inside = False
    for line in lines:
        if re.match(r"^" + re.escape(key) + r":", line):
            inside = True
            out.append(line)
            continue
        if inside:
            if re.match(r"^[a-z]", line):
                break
            out.append(line)
    return "\n".join(out) if out else None


def _yaml_job_block(text: str, name: str) -> Optional[str]:
    """One job's lines, from its key to the next job key at the same indent."""
    lines = text.split("\n")
    out: List[str] = []
    inside = False
    for line in lines:
        key = _YAML_JOB_KEY_RE.match(line)
        if key and key.group(1) == name:
            inside = True
            out.append(line)
            continue
        if inside:
            if key:
                break
            out.append(line)
    return "\n".join(out) if out else None


def browser_gate_findings(text: str) -> List[Tuple[str, str]]:
    """The workflow's wiring, as (where, message) pairs. Pure, so `--self-test` can mutate it."""
    where = rel(CHECK_WORKFLOW)
    out: List[Tuple[str, str]] = []

    step = _SCOPE_STEP_RE.search(text)
    job: Optional[str] = None
    if step is None:
        out.append((where, (
            "no job runs `python3 scripts/browser-scope.py classify`, so the scope list is\n"
            "  consulted by nothing and `design-check` is gated by whatever its `if:` says.")))
    else:
        for line in text[: step.start()].split("\n"):
            key = _YAML_JOB_KEY_RE.match(line)
            if key:
                job = key.group(1)
        if job is None:
            out.append((where, "the classifier step is not inside a job this reader can name."))

    on = _yaml_top_block(text, "on")
    if on is None:
        out.append((where, "has no `on:` block."))
    elif re.search(r"^\s*paths(?:-ignore)?:", on, re.M):
        out.append((where, (
            "the `on:` block carries a `paths` filter. That gates EVERY job — `check`,\n"
            "  `revert-guard` and `already-passed` included — and D141 scopes the browser\n"
            "  matrix alone. The filter is `browser-scope`'s output, read by one job's `if:`.")))

    design = _yaml_job_block(text, "design-check")
    if design is None:
        out.append((where, "has no `design-check` job for the scope to gate."))
    elif job is not None:
        needs = re.search(r"^\s*needs:.*?(?=^\s*(?:if|runs-on):)", design, re.M | re.S)
        if needs is None or job not in needs.group(0):
            out.append((where, f"`design-check` does not `need` `{job}`, so its answer is not waited for."))
        cond = re.search(r"^\s*if:\s*(.+)$", design, re.M)
        answer = f"needs.{job}.outputs.run"
        if cond is None or f"{answer} != 'false'" not in cond.group(1):
            out.append((where, (
                f"`design-check`'s `if:` does not read `{answer} != 'false'`.\n"
                "  That spelling is the fail-open one: a classifier that errored, a job that\n"
                "  never ran and an empty output all RUN the matrix. `== 'true'` would skip it\n"
                "  on every one of those, silently (D141).")))
        if cond is not None and "!cancelled()" not in cond.group(1):
            out.append((where, (
                "`design-check`'s `if:` has no `!cancelled()`, so GitHub prepends `success()`\n"
                "  and a FAILED gate job skips the matrix instead of releasing it.")))

    passed = _yaml_job_block(text, "design-check-passed")
    if passed is not None:
        cond = re.search(r"^\s*if:\s*(.+)$", passed, re.M)
        if cond is not None and re.search(r"always\(\)|cancelled\(\)", cond.group(1)):
            out.append((where, (
                "`design-check-passed` runs on a skipped matrix, so a tree no browser saw\n"
                "  would earn D136's pass record and skip the matrix on main too.")))
    return out


def _repo_literals(code: str, tracked: Set[str]) -> List[str]:
    """Tracked paths outside `app/` that a file's CODE names. Comments are blanked first."""
    found: List[str] = []
    for match in _REPO_LITERAL_RE.finditer(_blank_ts_comments(code)):
        candidate = match.group(1)
        # A tracked file, or a directory literal (trailing `/`) with tracked files under it.
        is_dir = candidate.endswith("/") and any(p.startswith(candidate) for p in tracked)
        if candidate in tracked or is_dir:
            found.append(candidate)
    return found


def _browser_requirements(module, tracked: Set[str], makefile: str) -> List[Tuple[str, str]]:
    """Every path the browser suite depends on, with where the dependency was read from.

    A path ending in `/` is a directory and means every tracked file under it.
    """
    out: List[Tuple[str, str]] = [
        (rel(CHECK_WORKFLOW), "the gate's own workflow"),
        (rel(BROWSER_SCOPE_SCRIPT), "the classifier the workflow runs"),
        ("Makefile", "holds the `design-check` recipe the job runs"),
    ]
    recipe = module.recipe_text(makefile, "design-check") or ""
    for name in sorted(set(re.findall(r"scripts/[\w.-]+", recipe))):
        out.append((name, "named in the Makefile's `design-check` recipe"))

    if exists(PLAYWRIGHT_CONFIG):
        code = _blank_ts_comments(read(PLAYWRIGHT_CONFIG))
        out.append((rel(PLAYWRIGHT_CONFIG), "Playwright's config"))
        test_dir = _TESTDIR_RE.search(code)
        if test_dir:
            out.append((_app_relative(test_dir.group(1)).rstrip("/") + "/", "Playwright's `testDir`"))
        for literal in _RELATIVE_LITERAL_RE.findall(code):
            target = _import_target(literal, tracked)
            if target in tracked:
                out.append((target, f"named in app/playwright.config.ts as `{literal}`"))
            elif not target.startswith("app/"):
                out.append((target, f"named in app/playwright.config.ts as `{literal}`, outside app/"))

    if exists(VITE_CONFIG):
        code = _blank_ts_comments(read(VITE_CONFIG))
        out.append((rel(VITE_CONFIG), "Vite's config"))
        root = _VITE_ROOT_RE.search(code)
        root_dir = _app_relative(root.group(1)) if root else "app"
        out.append((root_dir.rstrip("/") + "/", "Vite's root, which is what the dev server serves"))
        for literal in _RELATIVE_LITERAL_RE.findall(code):
            target = _import_target(literal, tracked)
            if not target.startswith("app/"):
                out.append((target, f"named in app/vite.config.ts as `{literal}`, outside app/"))

    for anchor, why in (("app/index.html", "the page Vite serves"),
                        ("app/package.json", "the `dev` and `design-check` scripts and the pins"),
                        ("app/package-lock.json", "what `npm ci` installs, Playwright included")):
        out.append((anchor, why))

    for path in _walk(APP_TESTS, (".ts",)) + _walk(APP_SRC, (".ts", ".tsx")):
        for literal in _repo_literals(read(path), tracked):
            out.append((literal, f"read by {rel(path)}"))
    return out


def check_browser_scope(report: Report) -> None:
    """`scripts/browser-scope.py:SCOPE` against what the browser suite loads, both ways (D141).

    MECHANICAL: a dependency the scope does not cover is a class of change the browser matrix
    has silently stopped running for, and an entry covering nothing tracked is a pattern that
    was renamed away. Neither is a judgement. The wiring findings are the same kind — the
    fail-open spelling either is in the `if:` or it is not.
    """
    if not exists(BROWSER_SCOPE_SCRIPT):
        report.add("browser scope", MECHANICAL, [Finding(
            rel(BROWSER_SCOPE_SCRIPT),
            "does not exist, and `.github/workflows/check.yml` gates its browser matrix on it.")])
        return
    if not exists(CHECK_WORKFLOW):
        report.add("browser scope", MECHANICAL, [Finding(
            rel(CHECK_WORKFLOW), "does not exist, so nothing consults the scope list.")])
        return
    module = _sibling("browser-scope.py")
    scope = literals_from_module(BROWSER_SCOPE_SCRIPT).get("SCOPE")
    if module is None or not isinstance(scope, tuple) or not scope or not all(
        isinstance(entry, dict) and isinstance(entry.get("path"), str) for entry in scope
    ):
        report.add("browser scope", MECHANICAL, [Finding(
            rel(BROWSER_SCOPE_SCRIPT),
            "`SCOPE` is not a tuple of `{\"path\": …}` literals this row can read, or the\n"
            "  module does not import. A list nothing can read gates nothing knowingly.")])
        return

    findings: List[Finding] = []
    tracked = _tracked_paths()
    makefile = read(ROOT / "Makefile") if exists(ROOT / "Makefile") else ""

    def covered(path: str) -> bool:
        return any(module.matches(str(entry["path"]), path) for entry in scope)

    for entry in scope:
        pattern = str(entry["path"])
        if not any(module.matches(pattern, path) for path in tracked):
            findings.append(Finding(rel(BROWSER_SCOPE_SCRIPT), (
                f"`{pattern}` matches nothing tracked. A pattern that covers nothing is one\n"
                "  that was renamed away, and the class of change it named now runs no browser.")))
        within = entry.get("within")
        if within is not None:
            kind, _, target = str(within).partition(":")
            if kind != "recipe":
                findings.append(Finding(rel(BROWSER_SCOPE_SCRIPT), (
                    f"`{pattern}` narrows with `{within}`, which is not a narrowing the\n"
                    "  classifier knows; it will count the whole file, which is safe and unmeant.")))
            elif module.recipe_text(makefile, target) is None:
                findings.append(Finding(rel(BROWSER_SCOPE_SCRIPT), (
                    f"`{pattern}` is narrowed to the `{target}` recipe, and the Makefile has no\n"
                    "  such rule. The classifier answers RUN for every Makefile change until it does.")))

    required = _browser_requirements(module, tracked, makefile)
    seen: Set[str] = set()
    for path, why in required:
        if path in seen:
            continue
        seen.add(path)
        if path.endswith("/"):
            files = [p for p in tracked if p.startswith(path)]
            if not files:
                findings.append(Finding(rel(BROWSER_SCOPE_SCRIPT), (
                    f"the suite depends on `{path}` ({why}) and nothing tracked is under it.")))
                continue
            missing = [p for p in files if not covered(p)]
            if missing:
                findings.append(Finding(rel(BROWSER_SCOPE_SCRIPT), (
                    f"`{path}` is {why}, and {len(missing)} of its {len(files)} tracked files are\n"
                    f"  outside SCOPE — first: `{missing[0]}`. A change there would run no browser.")))
        elif not covered(path):
            findings.append(Finding(rel(BROWSER_SCOPE_SCRIPT), (
                f"`{path}` is {why}, and no SCOPE entry covers it. A change to it would run\n"
                "  no browser, and the green would be believed.")))

    for where, message in browser_gate_findings(read(CHECK_WORKFLOW)):
        findings.append(Finding(where, message))

    report.add("browser scope", MECHANICAL, findings,
               f"{len(scope)} entries cover {len(seen)} derived dependencies, read fail-open",
               scanned=len(scope))


def _spec_map_should_run() -> bool:
    """Whether `check_spec_map` should run this pass (test-audit plan S3).

    Full mode always runs it, matching CI. Staged mode runs it only when the commit touches
    `app/` or `scripts/browser-scope.py` — its own subjects: the map is BUILT from
    `app/tests/*.spec.ts` and `app/src/`, and it is `scripts/browser-scope.py`'s own data.
    A commit touching neither cannot change what this row would find.

    FAILS OPEN, on `serve-scope.py`'s own precedent: an empty staged set (nothing staged, or
    the diff could not be read) runs the row too, rather than skip on doubt.
    """
    if core._INDEX_PATHS is None:
        return True
    if not _STAGED_PATHS:
        return True
    return any(path == "scripts/browser-scope.py" or path.startswith("app/")
               for path in _STAGED_PATHS)


def check_spec_map(report: Report) -> None:
    """`scripts/browser-scope.py`'s spec map (`specs`), against `app/tests/` and the shared
    surfaces it names, both ways (D215).

    MECHANICAL, `browser scope`'s reasoning one level down. Four things, none of them
    "a spec reaches its own file" — every spec's own closure trivially contains its own
    path, so that check passes on a spec import-graph that resolves nothing real:

    - every spec's closure reaches at least one file under `app/src/` — a spec that only
      ever reaches test helpers and itself is a spec the map cannot narrow FOR, and every
      change to the screen it claims to test would silently widen to every spec instead;
    - every `ROUTES` view file is reached by at least one spec that NAMES its hash
      explicitly (never a `routesFromNav(` sweep alone — `unnamed_route_views()`'s own
      argument, checked here rather than trusted to it);
    - every file the map's reverse index names must still exist;
    - the shell's own closure (`App.tsx`/`main.tsx`, cut off at the screens) must be covered
      by `is_shared_surface`, or a shared file has quietly stopped being treated as one.

    **PATH-GATED IN STAGED MODE** (test-audit plan S3): see `_spec_map_should_run`. A skip
    still emits the row, at `scanned=0`, pinned in `EXPECTED_EMPTY`.
    """
    if not _spec_map_should_run():
        report.add(
            "spec map", MECHANICAL, [],
            "skipped: staged commit touches neither app/ nor scripts/browser-scope.py",
            scanned=0,
        )
        return
    if not exists(BROWSER_SCOPE_SCRIPT):
        report.add("spec map", MECHANICAL, [Finding(
            rel(BROWSER_SCOPE_SCRIPT), "does not exist, so there is no spec map to reconcile.")])
        return
    module = _sibling("browser-scope.py")
    if module is None:
        report.add("spec map", MECHANICAL, [Finding(
            rel(BROWSER_SCOPE_SCRIPT), "does not import, so the spec map cannot be read.")])
        return

    findings: List[Finding] = []
    try:
        specs = module.all_specs()
        module.build_reverse_map()
    except Exception as exc:  # noqa: BLE001 - a broken map must be a finding, not a crash
        report.add("spec map", MECHANICAL, [Finding(
            rel(BROWSER_SCOPE_SCRIPT), f"the spec map raised building it: {exc!r}.")])
        return

    if not specs:
        findings.append(Finding(rel(BROWSER_SCOPE_SCRIPT),
                                "`all_specs()` found no `app/tests/*.spec.ts` files."))

    routes = module.route_views()
    reached_by: Dict[str, Set[str]] = {}
    spec_closures: Dict[str, Set[str]] = {}
    for spec_path in specs:
        files = module.spec_reach(spec_path, routes)
        spec_closures[spec_path] = files
        for path in files:
            reached_by.setdefault(path, set()).add(spec_path)

    for spec_path in specs:
        if not any(path.startswith("app/src/") for path in spec_closures[spec_path]):
            findings.append(Finding(spec_path, (
                "reaches no file under `app/src/` at all — its own path is not that (a "
                "spec's closure always contains itself, which proves nothing). A change to "
                "whatever screen this spec claims to test would never narrow to it.")))

    named_views: Set[str] = set()
    for spec_path in specs:
        named_views |= module.spec_named_views(spec_path, routes)
    for route_path, view in sorted(routes.items()):
        if view not in named_views:
            findings.append(Finding(view, (
                f"the `{route_path}` route's view file is never named by hash in any "
                "spec's own body — only ever, at best, by a `routesFromNav(` sweep. "
                "`unnamed_route_views()` must then cover it as a shared surface (checked "
                "in the shell-closure loop below); either way this is worth seeing.")))

    for path in reached_by:
        if not exists(ROOT / path):
            findings.append(Finding(rel(BROWSER_SCOPE_SCRIPT), (
                f"the map's reverse index names `{path}`, which is not tracked.")))

    # `App.tsx`'s SHELL, cut off at the screens it renders: `shell_closure()`'s own BFS,
    # which stops at a route's view file rather than expanding into it. Every file in that
    # closure must answer `is_shared_surface` — a change to the sidebar or the palette is a
    # change every spec answers to — while the screens themselves are deliberately excluded,
    # because THEY are the whole reason a map exists rather than "App.tsx reaches
    # everything, so everything is shared".
    for path in sorted(module.shell_closure()):
        if module.is_shared_surface(path):
            continue
        findings.append(Finding(path, (
            "is in the shell's own closure (`App.tsx`/`main.tsx`, cut off at the screens) "
            "and `is_shared_surface` does not cover it. A change here would narrow to "
            "whatever spec's closure happens to reach it, when it should select every "
            "spec.")))

    for config in ("app/playwright.config.ts", "app/vite.config.ts"):
        if exists(ROOT / config) and not module.is_shared_surface(config):
            findings.append(Finding(config, (
                "is a config the browser suite reads and `is_shared_surface` does not cover "
                "it, so a change here would narrow instead of selecting every spec.")))

    report.add("spec map", MECHANICAL, findings,
               f"{len(specs)} specs, {len(reached_by)} files reached, shell closure checked",
               scanned=len(specs))


def check_serve_scope(report: Report) -> None:
    """`scripts/serve-scope.py:SCOPE` against `serve-selftest.py:CARRY`, both ways.

    MECHANICAL, on `browser scope`'s reasoning exactly. `CARRY` is the literal list of what
    the self-test copies into its throwaway tree, which IS the definition of what that test
    can observe. A carried name with no SCOPE entry is a class of change the gate has
    silently stopped running for, and a SCOPE entry that is not carried and does not say why
    is a filter covering something the test cannot see. Neither is a judgement.

    THE ONE PATH-GATED TARGET IN THE REPO, and the row exists because of what makes it
    dangerous rather than what makes it useful. `make serve-selftest` is 70.1s of `make
    check`'s 187.5, and the owner ruled it in and path gating in general out
    (D247, guard self-test scope). A second gated target needs the owner's word
    again, so this row is deliberately written about THIS gate and not as a framework.
    """
    if not exists(SERVE_SCOPE_SCRIPT):
        report.add("serve scope", MECHANICAL, [Finding(
            rel(SERVE_SCOPE_SCRIPT),
            "does not exist, and the Makefile gates `serve-selftest` on it.")])
        return
    if not exists(SERVE_SELFTEST_SCRIPT):
        report.add("serve scope", MECHANICAL, [Finding(
            rel(SERVE_SELFTEST_SCRIPT), "does not exist, so there is nothing to scope.")])
        return

    scope = literals_from_module(SERVE_SCOPE_SCRIPT).get("SCOPE")
    carry = literals_from_module(SERVE_SELFTEST_SCRIPT).get("CARRY")
    if not isinstance(scope, tuple) or not scope or not all(
        isinstance(entry, dict) and isinstance(entry.get("path"), str) for entry in scope
    ):
        report.add("serve scope", MECHANICAL, [Finding(
            rel(SERVE_SCOPE_SCRIPT),
            "`SCOPE` is not a tuple of `{\"path\": …}` literals this row can read.")])
        return
    if not isinstance(carry, tuple) or not carry:
        report.add("serve scope", MECHANICAL, [Finding(
            rel(SERVE_SELFTEST_SCRIPT),
            "`CARRY` is not a tuple of names this row can read, so nothing defines what the\n"
            "  self-test observes and the scope list is unreconcilable.")])
        return

    findings: List[Finding] = []
    carried = {str(name) for name in carry}

    def stands_for(entry: dict) -> str:
        path = str(entry["path"])
        return path[:-3] if path.endswith("/**") else path

    declared = {stands_for(entry) for entry in scope if "beyond_carry" not in entry}

    for name in sorted(carried - declared):
        findings.append(Finding(rel(SERVE_SCOPE_SCRIPT), (
            f"`{name}` is carried into the self-test's tree and no SCOPE entry stands for it.\n"
            "  A change to it would skip the self-test, and the green would be believed.")))

    for name in sorted(declared - carried):
        findings.append(Finding(rel(SERVE_SCOPE_SCRIPT), (
            f"`{name}` is in SCOPE but `CARRY` does not carry it. Either add `beyond_carry`\n"
            "  saying why the test depends on something it never copies, or drop the entry.")))

    for entry in scope:
        if not str(entry.get("why") or "").strip():
            findings.append(Finding(rel(SERVE_SCOPE_SCRIPT),
                                    f"`{entry['path']}` gives no reason for being in the list."))
        beyond = entry.get("beyond_carry")
        if beyond is not None and not str(beyond).strip():
            findings.append(Finding(rel(SERVE_SCOPE_SCRIPT), (
                f"`{entry['path']}` declares `beyond_carry` with no argument in it. The whole\n"
                "  point of the field is the sentence.")))

    # THE WIRING. A classifier nothing consults is a list, not a gate.
    makefile = read(ROOT / "Makefile") if exists(ROOT / "Makefile") else ""
    recipe = ""
    for line in makefile.split("\n"):
        if line.startswith("serve-selftest:"):
            recipe = makefile.split("serve-selftest:", 1)[1].split("\n\n", 1)[0]
            break
    if "serve-scope.py" not in recipe:
        findings.append(Finding(
            "Makefile",
            "the `serve-selftest` recipe does not consult `scripts/serve-scope.py`. The scope\n"
            "  list then gates nothing and is a list somebody maintains for no reader."))
    elif "serve-selftest.py" not in recipe:
        findings.append(Finding(
            "Makefile",
            "the `serve-selftest` recipe consults the scope but never runs the self-test."))

    report.add("serve scope", MECHANICAL, findings,
               f"{len(scope)} entries against {len(carry)} carried names, both ways",
               scanned=len(scope))


def check_guard_scope(report: Report) -> None:
    """`scripts/guard-scope.py:ROSTER` against the Makefile's own wiring, both ways.

    THE SECOND PATH-GATED TARGET, on the owner's word, 2026-09-20 — see
    D247. Unlike `check_serve_scope` above, there is
    no separate subject list to reconcile here: `guard-scope.py` derives each self-test's
    subject from its own source on every call, so the only thing left to drift is which
    targets are gated AT ALL. A roster entry nothing consults is a list, not a gate — `serve
    scope`'s own wiring check, repeated. A recipe calling this classifier for a target the
    roster does not name would classify against an empty scope and always RUN, which is safe
    but silently pointless — the same "green is believed" failure the row exists to catch.
    """
    if not exists(GUARD_SCOPE_SCRIPT):
        report.add("guard scope", MECHANICAL, [Finding(
            rel(GUARD_SCOPE_SCRIPT),
            "does not exist, and fifteen Makefile recipes gate on it.")])
        return

    roster = literals_from_module(GUARD_SCOPE_SCRIPT).get("ROSTER")
    if not isinstance(roster, tuple) or not roster or not all(
        isinstance(entry, dict) and isinstance(entry.get("target"), str)
        and isinstance(entry.get("test"), str) for entry in roster
    ):
        report.add("guard scope", MECHANICAL, [Finding(
            rel(GUARD_SCOPE_SCRIPT),
            "`ROSTER` is not a tuple of `{\"target\": …, \"test\": …}` literals this row can "
            "read.")])
        return

    findings: List[Finding] = []
    targets = {str(entry["target"]) for entry in roster}

    for entry in roster:
        test_path = ROOT / str(entry["test"])
        if not exists(test_path):
            findings.append(Finding(
                rel(GUARD_SCOPE_SCRIPT),
                f"`{entry['target']}`'s `test` names `{entry['test']}`, which does not "
                "exist."))

    makefile = read(ROOT / "Makefile") if exists(ROOT / "Makefile") else ""
    wired = set(re.findall(r"guard-scope\.py classify --target (\S+)", makefile))

    for target in sorted(targets - wired):
        findings.append(Finding(rel(GUARD_SCOPE_SCRIPT), (
            f"`{target}` is on ROSTER and no Makefile recipe calls "
            f"`guard-scope.py classify --target {target}`. The roster entry gates nothing.")))

    for target in sorted(wired - targets):
        findings.append(Finding(
            "Makefile",
            f"a recipe calls `guard-scope.py classify --target {target}`, but `{target}` is "
            "not on ROSTER — it would classify against an unscoped target and always RUN, "
            "which is safe but means the gate was copied without its subject."))

    for entry in roster:
        recipe = ""
        target = str(entry["target"])
        marker = f"\n{target}:"
        if marker in ("\n" + makefile):
            recipe = ("\n" + makefile).split(marker, 1)[1].split("\n\n", 1)[0]
        if recipe and f"guard-scope.py classify --target {target}" not in recipe:
            findings.append(Finding(
                "Makefile",
                f"the `{target}` recipe exists but does not consult `guard-scope.py` — it "
                "always runs, ungated."))

    report.add("guard scope", MECHANICAL, findings,
               f"{len(roster)} roster entries against {len(wired)} wired Makefile recipes, "
               "both ways",
               scanned=len(roster))


# `check census` is CUT (test-audit plan Q2, 2026-09-28): every OTHER published list of
# what `make check` runs, once reconciled against the recipe here, repeated a membership
# question `check registry` already answers for the recipe's own declaration.



# -------------------------------------------------------------- how callers invoke this

# Every file that runs this script as a gate or a build step. Each is checked for flags
# this script does not declare.
INVOKERS = ["Makefile", "scripts/githooks/pre-commit", ".claude/commands/docs-audit.md"]

_INVOCATION_RE = re.compile(r"docs-audit\.py((?:\s+--[a-z][a-z-]*)*)")


def check_check_registry(report: Report) -> None:
    """`scripts/checks.py` against the `check:` recipe it describes, both directions.

    Was merged with `check census` by M3 (test-audit-2026-09-27, L8, Q8 yes). `check
    census`'s own half — every OTHER published list of what `make check` runs, reconciled
    against that same recipe — is CUT (test-audit plan Q2, 2026-09-28): it repeated a
    membership question this row already answers for the recipe's own declaration.
    """
    result = _check_registry()
    report.add("check registry", result.severity, result.findings, result.summary,
               scanned=result.scanned)


def check_audit_invocation(report: Report) -> None:
    """Every flag a caller passes this script must be one this script declares.

    The invocation string in the pre-commit hook is a second, independent decision about
    this script's interface, and nothing reconciled it with the argparse definition. That
    is the repo's recurring failure class — two decisions that must agree, only one of
    which moves — sitting on the commit gate itself.

    The consequence is worse than a broken flag. Renaming or dropping an option makes
    argparse reject the hook's command line, and argparse's own exit code for that is 2 —
    which is this script's ADVISORY code, the one the hook prints and allows. So the gate
    would stop running and report the routine coupling question while doing it. `EXIT_USAGE`
    makes that failure loud; this check makes it not happen.

    Flags only. Reconciling positional arguments or values would mean modelling argparse,
    and this script has none to model.

    **The question is asked of argparse, not of a list scraped out of it.** An earlier draft
    read `parser._actions` — a private attribute, and the coupling of a coupling check. It
    was also wrong: argparse accepts unambiguous abbreviations, so `--stag` really does run
    and set membership would have called it a finding. `parse_known_args` returns unmatched
    optionals in its second element, which IS the property this check is about — would this
    command line be rejected — and it is public API. The declared list below is pulled from
    `format_usage()` for the human message only; nothing decides on it.
    """
    parser = entry_parser()

    def rejected(flag: str) -> bool:
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                _, extras = parser.parse_known_args([flag])
            except SystemExit:  # a flag that parses but demands a value
                return True
        return flag in extras

    declared = parser.format_usage().split(":", 1)[-1].strip().replace("\n", " ")
    findings: List[Finding] = []
    for name in INVOKERS:
        path = ROOT / name
        if not exists(path):
            continue
        for number, line in enumerate(read(path).splitlines(), start=1):
            for match in _INVOCATION_RE.finditer(line):
                for flag in match.group(1).split():
                    if rejected(flag):
                        findings.append(
                            Finding(
                                f"{name}:{number}",
                                f"invokes `docs-audit.py {flag}`, which argparse rejects.\n"
                                f"  Accepts: {declared}\n"
                                f"  The invocation would exit {EXIT_USAGE}; a caller "
                                f"reading that as a finding would stop gating.",
                            )
                        )
    # THE EXIT CODES THE ARGUMENT ABOVE RESTS ON, READ OUT OF `main()` RATHER THAN TRUSTED.
    #
    # The docstring's whole case for `_Parser` is a COLLISION: argparse's usage exit is 2, and
    # 2 is this script's advisory code, so an undeclared flag would make the gate stop running
    # while reporting the routine coupling question. That case is only true while `main()`
    # still maps advisory to 2 and `EXIT_USAGE` is something else. Nothing read either, so the
    # override could have outlived its reason with the comment still explaining it.
    #
    # A NOTE ON WHAT THIS IS NOT. The plan that scheduled this row expected it to land red on
    # "exit 2 bound to coupling without `--staged`". That was wrong and is recorded rather
    # than quietly dropped: `check_coupling` is not the only ADVISORY row — `entry budget`,
    # `game coverage` and `views exposure` among others emit one on every plain run — so exit
    # 2 is reachable without `--staged` and always was. The row below pins the collision,
    # which is the fact that was actually unread.
    advisory_code: Optional[int] = None
    try:
        for node in ast.walk(ast.parse(read(SELF))):
            if not (isinstance(node, ast.FunctionDef) and node.name == "main"):
                continue
            for inner in ast.walk(node):
                if not isinstance(inner, ast.IfExp):
                    continue
                orelse = inner.orelse
                if isinstance(orelse, ast.IfExp) and isinstance(orelse.body, ast.Constant):
                    advisory_code = orelse.body.value
    except (SyntaxError, OSError):
        advisory_code = None

    if advisory_code is None:
        findings.append(
            Finding(
                "scripts/docs-audit.py",
                "`main()` no longer maps severities to exit codes in a shape this row can "
                "read. `_Parser` exists because argparse's usage exit collides with the "
                "advisory code; re-point this, or the override outlives its reason.",
            )
        )
    elif advisory_code != 2:
        findings.append(
            Finding(
                "scripts/docs-audit.py",
                f"the advisory exit code is {advisory_code}, not 2, so argparse's default no "
                f"longer collides with it — and `_Parser`'s docstring still says it does. "
                f"Either the override is now unnecessary, or its argument needs rewriting.",
            )
        )
    elif advisory_code == EXIT_USAGE:
        findings.append(
            Finding(
                "scripts/docs-audit.py",
                f"`EXIT_USAGE` is {EXIT_USAGE}, which IS the advisory code. A caller cannot "
                f"tell a broken command line from a routine question, which is the exact "
                f"failure `_Parser` was written to prevent.",
            )
        )

    report.add(
        "audit invocation",
        MECHANICAL,
        findings,
        f"{len(INVOKERS)} callers, flags all declared, usage {EXIT_USAGE} clear of advisory "
        f"{advisory_code}",
        scanned=len(INVOKERS),
    )
