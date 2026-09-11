#!/usr/bin/env python3
"""The two guards a prose rewrite of docs/DECISIONS.md needs, and one it does not have.

D60 densifies the four docs CLAUDE.md names, and drops the `@` from three of them. Two
things can go wrong and neither had a guard:

  --structure   the prose is machine-parsed by scripts/decision-context.py, whose failure
                mode is `except Exception: sys.exit(0)`. A heading that loses its dash
                separator, a `**bold**` reflowed across a line break, or a ruling that
                drops its trailing period all degrade the hook SILENTLY while
                `make docs-audit` stays green. This mode asserts what that hook needs.

  --facts       a rewrite can drop a fact. Nothing else in this repo compares two versions
                of a doc, and `make docs-audit` cannot: it proves a path RESOLVES, never
                that the rewrite still mentions it. This mode diffs the hard tokens of an
                entry before and after and reports what went missing.

**These are not the same kind of check and are deliberately not one mode.** `--structure`
is a statement about the tree as it stands and is wired into scripts/docs-audit.py as the
`decision structure` row. `--facts` needs two versions and is only meaningful while a
rewrite is in flight, so it lives here and on no gate.

**Stdlib only, and it reads rather than writes.** The first is because the pre-commit hook
runs a bare `python3` (D18). The second is D16's rule at its strongest: this file exists to
make a docs change reviewable, and something that could edit the docs to satisfy itself
would be the exact failure that rule is written against.

WHAT NEITHER MODE CAN SEE: a dropped ARGUMENT. Both compare tokens — paths, identifiers,
decision ids, measurements, dates. A rewrite that keeps every backtick and loses the reason
the entry exists passes both, silently and completely. That is the residual risk of the
whole exercise and it is recorded in docs/DEBTS.md rather than papered over here.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
DECISIONS = ROOT / "docs" / "DECISIONS.md"

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 64

# The hook's own three selectors, replicated rather than imported. scripts/status.py
# imports scripts/decision-context.py through a resolve() helper and that is the right
# call there — it wants the hook's ANSWER. This wants to assert the hook's PRECONDITIONS,
# including on files that are not docs/DECISIONS.md, so it needs the rules rather than the
# reader. Kept in step by `decision structure`'s own case in --self-test.
MIN_RULING_CHARS = 12
MAX_RULINGS = 3

# Exactly scripts/decision-context.py's heading regex. The em-dash separator is the half
# scripts/docs-audit.py does NOT require — its roster regex is `^##\s+(D[1-9][0-9]{0,2})\b` —
# so a heading rewritten to `## D57: Title` passes the audit and blanks the hook. That
# asymmetry is the single most dangerous edit this rewrite can make, and it is why this
# check exists at all.
#
# THREE DIGITS SINCE 2026-09-02, and this file is why the widen could not stop at
# scripts/docs-audit.py. Capped at two, both patterns below stop matching at the hundredth
# entry — and `check_structure` then reports nothing wrong with a file it cannot read, so
# the audit's `decision structure` row goes green over an entry count that is not the file's.
# Measured before the fix: a three-digit heading appended to docs/DECISIONS.md left that row
# reporting "92 entries" over a file holding 93. The bound is docs-audit's `_ID_DIGITS`,
# spelled out here rather than imported because that script imports THIS one.
#
# THE CEILING IS WRITTEN AS A WORD AND NEVER AS AN ID, here and in scripts/docs-audit.py:
# this file is scanned for citations, so an id past the end of docs/DECISIONS.md is a
# dangling one wherever it is written, comment or not.
# AND AN ID IS A SLUG UNTIL THE MERGE CLAIMS IT (D72, rewritten 2026-09-11). A branch cannot
# allocate a number — what main will take is not knowable until the merge — so it writes
# `## D139` and `scripts/claim-ids.py` substitutes at merge time. This file is
# scanned for citations by the audit, so the two shapes are spelled once here and the id
# bound stays docs-audit's `_ID_ANY`; widening one of the two and not the other is how the
# three-digit ceiling went silently vacuous once already.
_ID = r"(?:[1-9][0-9]{0,2}|-[a-z][a-z0-9]*(?:-[a-z0-9]+)+)"
HEADING_RE = re.compile(r"^##\s+(D" + _ID + r")\s*[—-]\s*(.+)$")
ANY_H2_RE = re.compile(r"^##\s+(D" + _ID + r")\b")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
# Fenced blocks are lifted out BEFORE inline backticks are read, and this was a real
# defect rather than a refinement. The inline pattern is `` `([^`]+)` ``, so a ``` fence
# shifts backtick PARITY for everything after it in the entry — D42 reported eighteen
# tokens dropped that were sitting in the rewrite untouched. The blocks are compared in
# their own right, so nothing is given up by removing them first.
FENCE_RE = re.compile(r"```.*?```", re.S)


class Finding(NamedTuple):
    where: str
    message: str


class Entry(NamedTuple):
    ident: str
    title: str
    line: int
    body: str


# ------------------------------------------------------------------ reading the entries


def entries(text: str) -> List[Entry]:
    """Every `## D<n>` block, by the audit's looser regex rather than the hook's.

    Deliberately the LOOSE one for the HEADING: an entry whose heading no longer matches
    the hook is exactly what `--structure` has to report, and splitting on the strict
    regex would make such an entry invisible to the check written to catch it.

    **An entry ends at the next `## ` of ANY kind, which is the hook's own rule and not a
    detail.** scripts/decision-context.py stores and clears on `line.startswith("## ")`,
    so ending only at the next `## D<n>` would hand the LAST entry every trailing section
    in the file. Measured while this was written: D60 read 17,775 bytes against its real
    4,976, having absorbed Deferred, Someday and the v1 bug table — which would have put
    the final entry permanently over budget and attributed three sections' facts to it.
    """
    found: List[Entry] = []
    lines = text.split("\n")
    starts: List[Tuple[int, str]] = []
    stops: List[int] = []
    for number, line in enumerate(lines, start=1):
        if not line.startswith("## "):
            continue
        stops.append(number)
        match = ANY_H2_RE.match(line)
        if match:
            starts.append((number, match.group(1)))
    for number, ident in starts:
        later = [stop for stop in stops if stop > number]
        end = (later[0] - 1) if later else len(lines)
        body = "\n".join(lines[number - 1 : end])
        title = lines[number - 1][3:].strip()
        found.append(Entry(ident, title, number, body))
    return found


def rulings(body: str) -> List[str]:
    """What scripts/decision-context.py would surface for this entry.

    Per LINE, which is the whole point — `re.findall` in that file runs inside a `for line
    in` loop, so a bold spanning a wrap is not merely mis-ranked, it is invisible.
    """
    bolds: List[str] = []
    for line in body.split("\n"):
        for bold in BOLD_RE.findall(line):
            text = bold.strip()
            if len(text) > MIN_RULING_CHARS and text not in bolds:
                bolds.append(text)
    sentences = [text for text in bolds if text.endswith(".")]
    labels = [text for text in bolds if not text.endswith(".")]
    return (sentences + labels)[:MAX_RULINGS]


# --------------------------------------------------------------------------- --structure


def wrapped_bolds(text: str) -> List[int]:
    """Line numbers carrying an unbalanced `**`, so a bold run spans the wrap.

    An odd count of `**` on a line means the run opened and did not close there. Counting
    per line rather than diffing a whole-file match against a per-line one because this has
    to NAME the line — a count tells you 270 are lost and not one of them where.
    """
    bad: List[int] = []
    for number, line in enumerate(text.split("\n"), start=1):
        if line.count("**") % 2:
            bad.append(number)
    return bad


def check_structure(path: Path) -> List[Finding]:
    text = path.read_text(encoding="utf-8")
    name = path.relative_to(ROOT) if path.is_absolute() else path
    found: List[Finding] = []

    for number in wrapped_bolds(text):
        found.append(
            Finding(
                f"{name}:{number}",
                "a `**bold**` run opens and does not close on this line. "
                "scripts/decision-context.py scans per line, so the run is invisible to "
                "it and to `make status`. Keep a bold on one line.",
            )
        )

    for entry in entries(text):
        heading = text.split("\n")[entry.line - 1]
        if not HEADING_RE.match(heading):
            found.append(
                Finding(
                    f"{name}:{entry.line}",
                    f"`{entry.ident}`'s heading does not match "
                    f"`## <id> — <title>`. scripts/docs-audit.py accepts it and "
                    f"scripts/decision-context.py drops the entry, so this fails "
                    f"nowhere else.",
                )
            )
            continue
        if not rulings(entry.body):
            found.append(
                Finding(
                    f"{name}:{entry.line}",
                    f"`{entry.ident}` surfaces no ruling. The hook shows its title and "
                    f"nothing else. Open the entry with a bold sentence over "
                    f"{MIN_RULING_CHARS} characters ending in a period, on one line.",
                )
            )
    return found


def check_budget(path: Path, budget: int) -> List[Finding]:
    text = path.read_text(encoding="utf-8")
    name = path.relative_to(ROOT) if path.is_absolute() else path
    return [
        Finding(
            f"{name}:{entry.line}",
            f"`{entry.ident}` is {len(entry.body):,} bytes against a {budget:,} budget. "
            f"A session that opens this entry reads all of it, and D60 dropped the `@` so it is "
            f"opened deliberately. Cite a related entry instead of re-arguing it (D60).",
        )
        for entry in entries(text)
        if len(entry.body) > budget
    ]


# ------------------------------------------------------------------------------ --facts

# Normalise whitespace BEFORE extracting, or a token wrapped across a line reads as
# dropped. Measured while this was written: the first version reported
# `Undo the sale at <place>` missing from a rewrite that contained it, purely because the
# original wrapped it. A guard that cries wolf is one whose findings get skimmed.
FACT_PATTERNS: Dict[str, str] = {
    "code": r"`([^`]+)`",
    "paths": r"\b[\w./-]+\.(?:py|tsx|ts|css|md|json|csv|sh|txt)\b",
    "decisions": r"\bD\d{1,3}\b",
    "measures": r"\b\d[\d,.]*\s?(?:x|px|%|ms|KB|MB|GB|s)\b",
    "dates": r"\b20\d\d-\d\d-\d\d\b",
}


def facts(text: str) -> Dict[str, Set[str]]:
    """Every hard token, whitespace-insensitive on both axes.

    Flattening the document is what stops a wrapped token reading as dropped. Flattening
    INSIDE a code span is the second half of the same problem and was missed first:
    docs/DECISIONS.md wrapped `GET /pipeline/runs/<name>/pricing` mid-token, so the
    original normalises with a space the rewrite has no reason to reproduce, and the
    checker called a present token missing. A guard whose findings need triage is one
    whose findings get skimmed.
    """
    fenced = [re.sub(r"\s+", " ", block).strip() for block in FENCE_RE.findall(text)]
    flat = re.sub(r"\s+", " ", FENCE_RE.sub(" ", text))
    # Close a code span's internal wraps BEFORE any pattern reads the text, not just the
    # code one. docs/DECISIONS.md wrapped `scripts/ docs-audit.py` mid-token, so the PATH
    # pattern found a bare `docs-audit.py` that a correctly-written rewrite never produces
    # and reported it dropped. Repairing the text once is right where repairing each
    # pattern's output is a rule that has to be remembered per pattern.
    flat = re.sub(r"`([^`]*)`", lambda m: "`" + re.sub(r"\s+", "", m.group(1)) + "`", flat)
    found: Dict[str, Set[str]] = {"fenced": set(fenced)}
    for name, pattern in FACT_PATTERNS.items():
        found[name] = set(re.findall(pattern, flat))
    return found


def check_facts(before: str, after: str, label: str) -> List[Finding]:
    old, new = facts(before), facts(after)
    found: List[Finding] = []
    for kind in FACT_PATTERNS:
        for token in sorted(old[kind] - new[kind]):
            found.append(
                Finding(f"{label}:{kind}", f"dropped {token!r}")
            )
    return found


def entry_map(text: str) -> Dict[str, str]:
    return {entry.ident: entry.body for entry in entries(text)}


def check_facts_per_entry(before: str, after: str) -> List[Finding]:
    """Entry by entry, so a token moved between entries still reports.

    Whole-file would forgive exactly the mistake worth catching: D58 restating a fact and
    D10 losing it nets to zero across the file and is a real loss inside D10.
    """
    old, new = entry_map(before), entry_map(after)
    found: List[Finding] = []
    for ident, body in old.items():
        if ident not in new:
            found.append(Finding(ident, "entry is gone from the rewritten file"))
            continue
        found.extend(check_facts(body, new[ident], ident))
    return found


# --------------------------------------------------------------------------------- main


def render(findings: Sequence[Finding], clean: str) -> int:
    if not findings:
        print(f"  ok    {clean}")
        return EXIT_OK
    print(f"  FAIL  {len(findings)} finding(s)\n")
    for finding in findings:
        print(f"  {finding.where}\n      {finding.message}\n")
    return EXIT_FINDINGS


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Guards for the four docs CLAUDE.md names (D60).",
    )
    parser.add_argument(
        "--structure",
        nargs="?",
        const=str(DECISIONS),
        metavar="FILE",
        help="assert what scripts/decision-context.py needs (default: docs/DECISIONS.md)",
    )
    parser.add_argument(
        "--budget",
        type=int,
        metavar="BYTES",
        help="report entries larger than this, with --structure's file",
    )
    parser.add_argument(
        "--facts",
        nargs=2,
        metavar=("BEFORE", "AFTER"),
        help="diff the hard tokens of every entry between two versions of a file",
    )
    args = parser.parse_args(argv)

    if not args.structure and not args.facts:
        parser.print_help()
        return EXIT_USAGE

    worst = EXIT_OK
    if args.structure:
        path = Path(args.structure)
        if not path.exists():
            print(f"no such file: {path}", file=sys.stderr)
            return EXIT_USAGE
        print(f"structure  {path}")
        worst = max(worst, render(check_structure(path), "every entry reaches the hook"))
        if args.budget:
            print(f"budget     {args.budget:,} bytes")
            worst = max(worst, render(check_budget(path, args.budget), "every entry inside budget"))
    if args.facts:
        before, after = (Path(p) for p in args.facts)
        for path in (before, after):
            if not path.exists():
                print(f"no such file: {path}", file=sys.stderr)
                return EXIT_USAGE
        print(f"facts      {before} -> {after}")
        findings = check_facts_per_entry(
            before.read_text(encoding="utf-8"), after.read_text(encoding="utf-8")
        )
        worst = max(worst, render(findings, "every fact survives the rewrite"))
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
