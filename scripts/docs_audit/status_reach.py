"""Closed vocabularies, status sources and the paid-read model."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import List, Optional, Set

from .core import (
    CLAUDE_OR_RULES,
    Finding,
    MECHANICAL,
    ROOT,
    Report,
    _merge_rows,
    claude_and_rules,
    exists,
    glob_files,
    literals_from_module,
    read,
    rel,
)
from .reasons import (
    _order_reasons,
    _pricing_presets,
    _reason_codes,
    _reason_emissions,
    _terminal_statuses,
    _withhold_reasons,
)

def check_closed_vocabularies(report: Report) -> None:
    """Six closed vocabularies, one row: withhold reasons, order reasons, terminal
    statuses, pricing presets, reason codes and reason emissions — each a hand-authored set
    declared twice (once for a parser or resolver, once for a screen or a decision entry)
    and reconciled here so the two copies cannot drift apart in silence.

    Merged from six rows by M3 (test-audit-2026-09-27, L8, Q8 yes). Each sub-check below is
    unchanged; only the last line of each moved from `report.add` to `return Row`, so every
    defect any of the six used to catch still fails this one.
    """
    merged = _merge_rows("closed vocabularies", [
        _reason_codes(),
        _reason_emissions(),
        _withhold_reasons(),
        _order_reasons(),
        _terminal_statuses(),
        _pricing_presets(),
    ])
    report.add("closed vocabularies", merged.severity, merged.findings, merged.summary,
               scanned=merged.scanned)


# ----------------------------------------------------------- status.py's declared sources


STATUS = ROOT / "scripts" / "status.py"


def module_defs(path: Path) -> Set[str]:
    """Module-level `def` names, by parsing — same no-import rule as everything else here."""
    try:
        tree = ast.parse(read(path))
    except (OSError, SyntaxError):
        return set()
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def check_status_sources(report: Report) -> None:
    """`make status` reads a declared list of files. This verifies every one of them.

    status.py derives every value it prints, so its *values* cannot go stale. Its *reader*
    can: rename `harness/results/t1.json` and the glob matches nothing, silently deleting
    the most important line of the output. That is worse than no status tool, because you
    would believe the shorter version.

    It is not hypothetical. The score files were dated until `f86de1a` made them one per
    configuration, and a reader written the week before would have gone quiet rather than
    loud. So this is a check, not a comment asking the next session to remember.

    Reads SOURCES with `ast`, never by importing — a read-only audit must not execute the
    code it audits, which is also why SOURCES has to stay a pure literal.
    """
    if not exists(STATUS):
        report.add("status sources", MECHANICAL, [Finding("scripts/status.py", "does not exist")])
        return

    sources = literals_from_module(STATUS).get("SOURCES")
    if not sources:
        report.add(
            "status sources",
            MECHANICAL,
            [
                Finding(
                    "scripts/status.py",
                    "no SOURCES list to read. It must stay a pure literal — this audit "
                    "parses it with `ast` and never imports it.",
                )
            ],
        )
        return

    findings: List[Finding] = []
    checked = 0
    for entry in sources:
        path = str(entry.get("path", ""))
        kind = str(entry.get("kind", ""))
        requires = list(entry.get("requires") or [])
        where = f"scripts/status.py -> {path}"
        checked += 1

        if any(ch in path for ch in "*?["):
            parent, _, glob = path.rpartition("/")
            targets = glob_files(ROOT / parent, glob)
        else:
            target = ROOT / path
            targets = [target] if exists(target) else []

        if not targets:
            if not entry.get("optional"):
                findings.append(
                    Finding(
                        where,
                        f"`{path}` matches nothing, so `make status` would print MISSING and "
                        f"exit non-zero.\nIt is read for: {entry.get('why', '?')}\n"
                        f"If the file moved, update SOURCES in scripts/status.py.",
                    )
                )
            continue

        for target in targets:
            name = rel(target)
            spot = f"scripts/status.py -> {name}"
            if kind == "literals":
                have = set(literals_from_module(target))
                for req in requires:
                    if req not in have:
                        findings.append(Finding(spot, f"`{name}` no longer defines the literal `{req}`."))
            elif kind == "defs":
                have = module_defs(target)
                for req in requires:
                    if req not in have:
                        findings.append(Finding(spot, f"`{name}` no longer defines `{req}()`."))
            elif kind == "json":
                try:
                    payload = json.loads(read(target))
                except ValueError as exc:
                    findings.append(Finding(spot, f"not valid JSON — {exc}"))
                    continue
                holders = payload if isinstance(payload, list) else [payload]
                for index, holder in enumerate(holders):
                    for req in requires:
                        if not isinstance(holder, dict) or req not in holder:
                            where = f" in item {index}" if isinstance(payload, list) else ""
                            findings.append(Finding(spot, f"`{name}` has no `{req}` key{where}."))

    report.add("status sources", MECHANICAL, findings, f"{checked} declared, all resolve",
               scanned=checked)


# ---------------------------------- the paid-read model named in CLAUDE.md or .claude/rules


_MODEL_RULE = re.compile(r"Batch API, not sequential calls\.\*\*\s*Model: `([^`]+)`")
_MODEL_CODE = re.compile(r'^MODEL\s*=\s*"([^"]+)"', re.M)


def model_disagreement(claude_text: str, prompt_text: str) -> Optional[str]:
    """None when the model CLAUDE.md or a rule file names equals `identify.prompt.MODEL`, else why not."""
    named = _MODEL_RULE.search(claude_text)
    emitted = _MODEL_CODE.search(prompt_text)
    if not named or not emitted:
        return f"the Model line in {CLAUDE_OR_RULES} or identify/prompt.py's MODEL cannot be read"
    if named.group(1) != emitted.group(1):
        return f"{CLAUDE_OR_RULES} names {named.group(1)}, identify/prompt.py MODEL is {emitted.group(1)}"
    return None


def check_paid_read_model(report: Report) -> None:
    why = model_disagreement(claude_and_rules(), read(ROOT / "identify" / "prompt.py"))
    report.add("paid-read model", MECHANICAL, [Finding(CLAUDE_OR_RULES, why)] if why else [], scanned=1)
