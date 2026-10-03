"""Fixed sleeps in the browser specs: a `waitForTimeout` says why it sleeps, or it waits on a condition.

A fixed sleep is a guess at how long something takes. Too short and the case flakes, too long and
every pass pays for it. Wait on the thing itself: an element state, a response, `expect.poll`,
`settleMotion`, `afterPaint`. A sleep stays only where the case asserts that nothing happens over a
real duration, or where the duration is the measurement, and it says so on the same line.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from .core import Finding, MECHANICAL, ROOT, Report, exists, read, rel
from .strings import _offender_list_at_merge_base, _read_offender_list

TESTS_DIR = ROOT / "app" / "tests"
FIXED_SLEEP_ALLOW = ROOT / "scripts" / "fixed-sleep-allow.json"

# The call itself, with its dot, so prose that names `waitForTimeout` is not a sleep.
_SLEEP_RE = re.compile(r"\.waitForTimeout\(")
# `// keep: <reason>` on the same line, or alone on the line above. The reason may not be empty.
_KEEP_RE = re.compile(r"//\s*keep:\s*\S")
_COMMENT_ONLY_RE = re.compile(r"^\s*(?://|/\*|\*)")


def bare_sleeps(text: str) -> List[int]:
    """1-based lines that call `.waitForTimeout(` with no `keep:` reason beside them."""
    lines = text.split("\n")
    out: List[int] = []
    for i, line in enumerate(lines):
        if _COMMENT_ONLY_RE.match(line) or not _SLEEP_RE.search(line):
            continue
        above = lines[i - 1] if i > 0 else ""
        if _KEEP_RE.search(line) or (_COMMENT_ONLY_RE.match(above) and _KEEP_RE.search(above)):
            continue
        out.append(i + 1)
    return out


def _entries(document: object) -> Tuple[Dict[str, Dict[str, object]], Optional[str]]:
    if not isinstance(document, dict) or not isinstance(document.get("entries"), list):
        return {}, "must be an object with an `entries` list"
    out: Dict[str, Dict[str, object]] = {}
    for entry in document["entries"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("file"), str) or not isinstance(entry.get("count"), int):
            return {}, f"entry {entry!r} needs a `file` and an integer `count`"
        out[entry["file"]] = entry
    return out, None


def sleep_findings(
    counts: Dict[str, List[int]],
    listed: Dict[str, Dict[str, object]],
    base: Optional[Dict[str, Dict[str, object]]],
    allow_rel: str,
    where: str = "",
) -> List[Finding]:
    """`counts` is file -> its bare sleep lines. Each file may carry at most the listed number."""
    findings: List[Finding] = []
    for file, lines in sorted(counts.items()):
        allowed = int(listed.get(file, {}).get("count", 0))
        if len(lines) > allowed:
            for line in lines[allowed:]:
                findings.append(Finding(
                    f"{file}:{line}",
                    "sleeps a fixed time with no reason. Wait on the condition (`expect`, `expect.poll`, `settleMotion`, "
                    "`afterPaint`, a response), or end the line with `// keep: <why nothing else can be waited on>`."))
    for file, entry in sorted(listed.items()):
        if not str(entry.get("reason", "")).strip():
            findings.append(Finding(allow_rel, f"entry for {file} has no reason. Write why it stays, or fix the sleeps."))
        have = len(counts.get(file, []))
        if have < int(entry["count"]):
            findings.append(Finding(allow_rel, f"{file} lists {entry['count']} bare sleeps and holds {have}. Lower the count: the list only shrinks."))
        if base is not None and int(entry["count"]) > int(base.get(file, {}).get("count", 0)):
            findings.append(Finding(allow_rel, f"{file} lists {entry['count']} against {base.get(file, {}).get('count', 0)} at the merge-base {where}. The list only shrinks."))
    return findings


def check_fixed_sleeps(report: Report) -> None:
    """No `waitForTimeout` in `app/tests/` without a `// keep:` reason, past `scripts/fixed-sleep-allow.json`.

    A fixed sleep guesses at a duration. A case that asserts nothing happens over time keeps its
    sleep and says so on the line. Every other wait is on a condition. **The list only shrinks.**
    An entry is a file and a count of bare sleeps it may still hold, with a reason. A count above
    what the file holds is stale, a count above the merge-base's is growth, and a file over its
    count is a finding on each extra line. Comment-only lines are skipped.
    """
    if not exists(TESTS_DIR):
        report.add("fixed sleeps", MECHANICAL, [], f"{rel(TESTS_DIR)} is not there, so no spec was read", scanned=0)
        return
    allow_rel = rel(FIXED_SLEEP_ALLOW)
    document, unreadable = _read_offender_list(FIXED_SLEEP_ALLOW)
    if document is None:
        report.add("fixed sleeps", MECHANICAL, [Finding(allow_rel, f"{unreadable}. Restore the list from git.")], "no allow list", scanned=0)
        return
    listed, bad = _entries(document)
    findings: List[Finding] = [Finding(allow_rel, bad)] if bad else []
    files = sorted(TESTS_DIR.rglob("*.ts"))
    counts = {rel(p): lines for p in files if (lines := bare_sleeps(read(p)))}
    base_document, where = _offender_list_at_merge_base(allow_rel)
    base = _entries(base_document)[0] if base_document is not None else None
    findings += sleep_findings(counts, listed, base, allow_rel, where)
    report.add(
        "fixed sleeps", MECHANICAL, findings,
        f"{len(findings)} fixed sleeps with no reason" if findings
        else f"no spec in {len(files)} files sleeps a fixed time without saying why ({sum(len(v) for v in counts.values())} listed)",
        scanned=len(files),
    )
