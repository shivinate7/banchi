#!/usr/bin/env python3
"""Run the CURRENT docs auditor against every historical tree. Diagnostic only, forever.

    make audit-history            every commit, oldest first
    scripts/audit-history.py -n 8 the oldest N commits

Answers one question: which checks have ever had something to say? A check that has never
fired on any tree in this repo's history is a candidate for retirement — see the bucket
rule in `docs/specs/audit-retirement.md`, which is the only thing this output feeds.

READ THIS BEFORE READING A ZERO — THE BY-CONSTRUCTION CONFOUND
==============================================================
Every tree authored after the audit landed is clean because the pre-commit hook blocked
anything else. On those trees a zero means "the hook worked", not "the check is dead
weight", and NOTHING CAN SEPARATE THE TWO — not this tool, not a longer history, not a
better classifier. Silent prevention and uselessness look identical from here.

So the only unconfounded window is the trees authored BEFORE the audit existed. For every
check whose subject also postdates those trees, the honest reading is "no record", which
this tool prints as such rather than as 0.

Consequences, stated so nobody has to infer them:

  * This never gates. No hook, no `make check`, no CI. A nonzero exit from this script
    means THE TOOL failed — a missing auditor, an unreadable payload — never that a
    finding was found. There is deliberately no exit code that a hook could grow to
    depend on, because the moment one exists the confound above starts deciding commits.
  * It informs retirement decisions; it never makes them.
  * The classifier below is deliberately conservative: it UNDERCOUNTS substantive
    findings, so a row credited with a real catch has earned it. Read a low number as a
    floor, never as a measurement.

Reads the auditor's `--json`, never the human render. Three parser bugs in one planning
session came from regexing the rendered report; D18's rule about not publishing what
nothing consumes has a sibling here — do not parse what is written for a human.

STANDING HAZARD FOR ANYONE EXTENDING THIS TOOL: injecting current code into an old tree
means part of what you measure is the instrument. Today's docs-audit.py cites D16-D18 in
its own comments, so on trees predating those decisions it reports findings against
itself — which is why `subject_absent` discards anything whose `where` is an injected
file. Add a file to the injection list and you must add it there too.

This is the same bug class as the staged-read defect two commits earlier: logic that is
correct against the wrong scope. Neither is visible by reading the code — both showed up
only against an outside baseline (72 against a known 2; a staged blob against a worktree).
Any future extension needs a comparison from outside itself, or it will look right.

DOES NOT REPRODUCE THE HAND-CLASSIFIED BASELINE, and is not tuned to. The planning
session's figures for the 8 pre-audit trees were criteria wording 16, decision ids in
code 2, env vars 2, harness tests 1. This tool reports 25/6, 0, 5/3, 3/3 (per-tree and
distinct). Neither convention lands on the hand numbers, so the gap is a counting
convention nobody wrote down, not a defect on either side — and the one real correction
runs toward the tool: decision ids in code was all instrument, never tree.

Left as a disagreement on purpose. Fitting the classifier until it emitted 16 would be
building an instrument to confirm a number, which is the failure D16 is about wearing
different clothes. The bucket assignments do not move either way: every affected row is
Bucket 1 or already keeps outright.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "scripts" / "docs-audit.py"

# The absence family, and ONLY it. A finding whose subject is simply not in the archived
# tree says nothing about drift: `git archive` omits every gitignored path, which is what
# produced phantom harness/images/ findings in the hand-run version of this.
#
# Kept literal on purpose. An earlier draft also swallowed "no `## D<n>` heading", which
# silently zeroed the decision-ids-in-code row — a citation pointing at a decision that
# did not exist yet is the check WORKING, and the hand classification scored two of them.
# Widening this regex costs real catches, and costs them invisibly.
_ABSENT = re.compile(r"does not exist")
_TARGET = re.compile(r"`([^`]+)`")


def git(*args: str) -> str:
    done = subprocess.run(
        ["git"] + list(args), cwd=str(ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    return done.stdout.decode("utf-8", errors="replace")


def gitignored(target: str) -> bool:
    done = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", target], cwd=str(ROOT),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    return done.returncode == 0


def subject_absent(where: str, message: str) -> bool:
    """True when the finding is an artefact of the tree, not a claim that drifted."""
    # The injected auditor is not part of the tree being measured. Today's docs-audit.py
    # cites D16-D18 in its own comments, so on any tree predating those decisions it
    # reports nine findings against itself — the instrument, not the subject. Caught only
    # because the total ran 36x over the hand-classified baseline: 72 against a known 2.
    if where.split(":")[0] == "scripts/docs-audit.py":
        return True
    target = _TARGET.search(message)
    if target and gitignored(target.group(1)):
        return True
    return bool(_ABSENT.search(message))


def audit_tree(sha: str) -> Optional[List[dict]]:
    """Archive one commit, drop in today's auditor, run it. None if the auditor died."""
    with tempfile.TemporaryDirectory() as work:
        tree = Path(work)
        archive = subprocess.run(
            ["git", "archive", sha], cwd=str(ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
        )
        if archive.returncode != 0:
            return None
        untar = subprocess.run(
            ["tar", "-x", "-C", str(tree)], input=archive.stdout,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        if untar.returncode != 0:
            return None
        (tree / "scripts").mkdir(parents=True, exist_ok=True)
        (tree / "scripts" / "docs-audit.py").write_bytes(AUDIT.read_bytes())
        done = subprocess.run(
            [sys.executable, str(tree / "scripts" / "docs-audit.py"), "--json"],
            cwd=str(tree), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
        )
        try:
            return json.loads(done.stdout.decode("utf-8", errors="replace"))["rows"]
        except (ValueError, KeyError):
            return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="audit-history",
        description="Run today's docs auditor over historical trees. Diagnostic; never gates.",
    )
    parser.add_argument("-n", "--limit", type=int, default=0,
                        help="only the oldest N commits (default: every commit)")
    args = parser.parse_args(argv)

    if not AUDIT.exists():
        print("audit-history: scripts/docs-audit.py is missing — nothing to run.", file=sys.stderr)
        return 1

    shas = git("rev-list", "--reverse", "HEAD").split()
    if not shas:
        print("audit-history: no commits.", file=sys.stderr)
        return 1
    if args.limit:
        shas = shas[: args.limit]

    substantive: Dict[str, int] = {}
    absent: Dict[str, int] = {}
    distinct: Dict[str, set] = {}
    seen: Dict[str, bool] = {}
    rows: List[Tuple[str, str, int, int, str]] = []
    broken = 0

    for sha in shas:
        subject = git("log", "-1", "--format=%s", sha).strip()[:44]
        result = audit_tree(sha)
        if result is None:
            broken += 1
            rows.append((sha[:8], subject, 0, 0, "auditor did not run"))
            continue
        sub = ab = 0
        for row in result:
            seen[row["label"]] = True
            for finding in row["findings"]:
                if subject_absent(finding["where"], finding["message"]):
                    absent[row["label"]] = absent.get(row["label"], 0) + 1
                    ab += 1
                else:
                    substantive[row["label"]] = substantive.get(row["label"], 0) + 1
                    distinct.setdefault(row["label"], set()).add(
                        (finding["where"], finding["message"])
                    )
                    sub += 1
        rows.append((sha[:8], subject, sub, ab, ""))

    print("Today's auditor against {0} historical trees.".format(len(shas)))
    print("A zero after the audit landed is confounded — see this script's header.\n")
    print("  {0:<10} {1:<44} {2:>5} {3:>7}".format("commit", "subject", "subst", "absent"))
    print("  " + "-" * 70)
    for sha, subject, sub, ab, note in rows:
        tail = note or "{0:>5} {1:>7}".format(sub, ab)
        print("  {0:<10} {1:<44} {2}".format(sha, subject, tail))

    # Both counts, because they answer different questions and neither is "the" number.
    # A false sentence living across eight trees is one defect (distinct) that had eight
    # chances to be caught (per-tree). Publishing one alone invites reading it as the other.
    print("\n  per check, across every tree above:")
    print("  {0:<22} {1:>8} {2:>9}".format("", "per-tree", "distinct"))
    for label in sorted(seen):
        sub, ab = substantive.get(label, 0), absent.get(label, 0)
        uniq = len(distinct.get(label, ()))
        tail = "  {0} subject-absent".format(ab) if ab else ""
        if sub:
            print("  {0:<22} {1:>8} {2:>9}{3}".format(label, sub, uniq, tail))
        else:
            print("  {0:<22} {1:>18}{2}".format(label, "no substantive finding", tail))

    print("\n  Retirement takes an argument, not a zero. Nothing here gates anything.")
    return 1 if broken == len(shas) else 0


if __name__ == "__main__":
    sys.exit(main())
