"""Capability homes: each named capability has one home, and its primitives are called nowhere else.

INCIDENT: the free reader had its own card crop (`geometry.detect_card` alone). It refused 263
cards and sent them to a paid look. PR #729 gave the crop one home, `identify/images.py`
`card_box_for`. This row keeps it there: an AST scan of real calls (never a comment or a string)
to a registered primitive, outside the home and its `allowed_dirs`, is a finding that names the
home. An allow entry needs a reason, a stale entry fails, and the count is pinned and only goes
down (`LOOP_EXPENSIVE_ALLOWED`'s own idiom).
"""

from __future__ import annotations

import ast
from typing import Dict, List, Sequence

from .core import Finding, MECHANICAL, Report, python_files, read, rel

# `home` is "path:function". `helpers` are functions of the home module that count as the home.
CAPABILITY_HOMES = [{
    "capability": "card box",
    "home": "identify/images.py:card_box_for",
    "helpers": ("_guarded_box",),
    "primitives": ("detect_card", "locate_card"),
    "allowed_dirs": ("geometry/",),
}]

# One entry per (file, primitive), each with its reason. Only goes down.
CAPABILITY_HOMES_ALLOWED = [
    {"file": "identify/images.py", "primitive": "locate_card",
     "reason": "`prepare_located` with the crop off reports the finder's raw answer, never cuts"},
    {"file": "harness/tests/t6_geometry.py", "primitive": "detect_card",
     "reason": "the test of geometry/ itself calls the detector it tests"},
    {"file": "harness/tests/t6_geometry.py", "primitive": "locate_card",
     "reason": "the test of geometry/ itself calls the finder it tests"},
    {"file": "harness/tests/t7/preview_crop.py", "primitive": "locate_card",
     "reason": "the preview test wraps the finders to count how often the cut calls them"},
    {"file": "harness/tests/t7/preview_crop.py", "primitive": "detect_card",
     "reason": "the preview test wraps the finders to count how often the cut calls them"},
    {"file": "scripts/score-detect.py", "primitive": "detect_card",
     "reason": "it measures the detector itself, so it cannot go through the guard"},
    {"file": "scripts/demo-photos.py", "primitive": "detect_card",
     "reason": "it pads the raw detector box to its own demo framing, with no model"},
]
CAPABILITY_HOMES_EXPECTED = 7


def _uses(source: str, prims):
    """(line, primitive, top-level function name or None) for each way to reach a primitive:
    a name, an attribute, an import (aliased too), or `getattr(x, "<name>")`. Only a
    module-level `def` counts as a function; a method is not one."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    out = []

    def visit(node, fn, line=0):
        line = getattr(node, "lineno", line)
        hit = None
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            hit = node.id
        elif isinstance(node, ast.Attribute):
            hit = node.attr
        elif isinstance(node, ast.alias):
            hit = node.name.split(".")[-1]
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr"
              and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant)):
            hit = node.args[1].value
        if hit in prims:
            out.append((line, hit, fn))
        for child in ast.iter_child_nodes(node):
            visit(child, child.name if isinstance(node, ast.Module)
                  and isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else fn, line)

    visit(tree, None)
    return out


def home_findings(files: Dict[str, str], registry: Sequence[dict], allow: Sequence[dict]) -> List[Finding]:
    findings: List[Finding] = []
    seen = set()
    for reg in registry:
        home_path, home_fn = reg["home"].split(":")
        in_home = {home_fn, *reg.get("helpers", ())}
        prims = set(reg["primitives"])
        for path, text in sorted(files.items()):
            if path.startswith(tuple(reg.get("allowed_dirs", ()))):
                continue
            for line, name, fn in _uses(text, prims):
                if (path == home_path and fn in in_home):
                    continue
                seen.add((path, name))
                if any(a["file"] == path and a["primitive"] == name for a in allow):
                    continue
                findings.append(Finding(
                    f"{path}:{line}",
                    f"reaches `{name}` outside the {reg['capability']} home. Call "
                    f"`{home_path}` `{home_fn}` instead, or extend it. A second path needs "
                    f"an entry in `CAPABILITY_HOMES_ALLOWED` with the reason."))
    for a in allow:
        if (a["file"], a["primitive"]) not in seen:
            findings.append(Finding(
                a["file"],
                f"`CAPABILITY_HOMES_ALLOWED` names `{a['primitive']}` here and this scan finds "
                f"no such call: the entry is stale. Delete it and lower "
                f"`CAPABILITY_HOMES_EXPECTED`."))
    return findings


def check_capability_homes(report: Report) -> None:
    files = {rel(p): read(p) for p in python_files()}
    findings = home_findings(files, CAPABILITY_HOMES, CAPABILITY_HOMES_ALLOWED)
    n = len(CAPABILITY_HOMES_ALLOWED)
    if n != CAPABILITY_HOMES_EXPECTED:
        findings.append(Finding(
            "scripts/docs_audit/capability_homes.py -> CAPABILITY_HOMES_ALLOWED",
            f"has {n} entries where {CAPABILITY_HOMES_EXPECTED} are pinned. "
            + ("Lower the pin." if n < CAPABILITY_HOMES_EXPECTED
               else "Remove the new entry or use the home. The pin never goes up.")))
    report.add(
        "capability homes", MECHANICAL, findings,
        f"{len(CAPABILITY_HOMES)} capability home held, {n} allowed (pinned at {CAPABILITY_HOMES_EXPECTED})",
        scanned=len(files))
