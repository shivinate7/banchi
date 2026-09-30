"""Dispatch, subject counts and the coupling question."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .core import (
    ADVISORY,
    COUPLING,
    COUPLING_MIN_LINES,
    EXPECTED_EMPTY,
    Finding,
    MECHANICAL,
    PACKAGE_DIR,
    Report,
    glob_files,
    read,
    rel,
    staged_changes,
)

# Checks defined in this file that `audit()` deliberately does not call: name -> why.
#
# EMPTY, AND THAT IS THE FINISHED STATE, the same shape as D18's seam list and for the same
# reason. It exists so that the escape route is the loud one. Without it, the only ways to
# silence the row below are to delete a check or to rename it out of both of the signals
# `defined_checks` reads, and both of those land in a diff looking like tidying. An entry
# here is an argument somebody had to write down and a reviewer can disagree with.
#
# Self-cleaning in both directions, the property D16 wants of `scripts/docs-audit-allow.txt`:
# an entry naming a check `audit()` does call is stale and reported, and an entry naming
# nothing defined here is dangling and reported. A list that only grows stops being read.
UNDISPATCHED: Dict[str, str] = {
    "corpus_is_empty":
        "A HELPER THAT EMITS ON BEHALF OF A REAL CHECK, not a check of its own. "
        "`check_decision_structure` iterates the entry files in docs/decisions/, and "
        "reported `0 entries` in GREEN when the corpus could not be read — measured by "
        "deleting one entry file. This writes the row that says so, under that check's "
        "label, which is why it calls `report.add` and why `audit()` does not call it. "
        "Dispatching it directly would print a second row nobody asked for; leaving it "
        "out of this list would report it as a check that has never run. It also served "
        "`check_entry_budget`, CUT 2026-09-28 (test-audit plan Q2); the second caller went "
        "with it.",
    "_debts_corpus_empty":
        "The debts twin of `corpus_is_empty`, for the same reason: `check_debts_headings` "
        "and `check_debt_index` both iterate docs/debts/, and both would report a clean "
        "read of nothing under whichever label called it. It also carries the pinned "
        "non-vacuity floor, so it must run under BOTH callers' names rather than once "
        "under its own.",
}


def _emits_row(func: ast.AST) -> bool:
    """True when the body hands a row to `Report.add` — the act that makes it a check."""
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "report"
        ):
            return True
    return False


def defined_checks(tree: ast.Module) -> Dict[str, int]:
    """Every module-level function this source marks as a check -> the line it starts on.

    Two signals, unioned and not intersected. The `check_` prefix can be renamed away in a
    diff that reads as tidying; the `report.add` call can be moved into a helper. Requiring
    both would mean losing either one hides a function from this row, which is precisely the
    silent failure the row exists to catch — so a function is a check if it carries EITHER.
    """
    return {
        node.name: node.lineno
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and (node.name.startswith("check_") or _emits_row(node))
    }


def dispatched_names(tree: ast.Module, names: Iterable[str]) -> Optional[Set[str]]:
    """Which of `names` appear anywhere inside `audit()`. None when there is no `audit()`.

    Every name in the function, not the top-level call statements only. The retired count
    machinery read statements and its own docstring named the failure: restructure some of
    the calls into a loop, leave the rest, and the reader sees fewer checks than there are.
    A walk sees a name in a tuple, a loop, a branch or a `try`, so the only restructuring it
    misses is one that moves dispatch out of `audit()` entirely — which the row reports as
    itself rather than guessing at.

    Scoped to `audit()` on purpose. A file-wide search would be vacuous: `self_test` drives
    check functions by name to prove they fire, so a name it exercises would read as
    accounted for while `audit()` called none of them.
    """
    wanted = set(names)
    audit_fn = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "audit"
        ),
        None,
    )
    if audit_fn is None:
        return None
    return {
        node.id for node in ast.walk(audit_fn) if isinstance(node, ast.Name) and node.id in wanted
    }


def _dispatch_sources() -> List[Path]:
    """The modules whose functions are the checks: the whole package but the self-test cases."""
    return [path for path in glob_files(PACKAGE_DIR, "*.py") if not path.name.startswith("selftest")]


def check_dispatch(report: Report, source: Optional[Path] = None) -> None:
    """Every check defined in the package, against the ones `audit()` actually calls.

    The failure: add a check function, forget the call. It never runs, the report still
    looks full, the hook still passes, and nothing in the repo can say the auditor is
    smaller than it looks. `docs/debts/` carried that as the one entry where a check can
    *vanish* rather than misreport, and it was uncovered from 2026-08-11 — the retired
    count-of-checks machinery had an `unaccounted` set doing this incidentally, and deleting
    the published number (D18, correctly) took the detector out with it.

    **A reconciliation, not a count, and the difference is the whole design.** D18 deleted
    that number because nothing downstream consumed it and keeping one restated number
    honest cost more machinery than any check in the file. Nothing here totals anything: not
    the summary line, not a finding, not the JSON row. A total would be back in circulation
    the moment it were printed — the next session restates it in a doc, and the machinery
    that was deleted has to come back to keep the restatement honest. What this row emits
    instead is the name of a function you can go and call, which is the only output that was
    ever actionable.

    **Blocking, and this is where it parts company with the row it replaces.** That one
    downgraded to ADVISORY when its reader got confused, because publishing a wrong count
    was worse than publishing none. There is no number to publish here, so the confused
    state is not a reason to soften: an unrun check is provably not running, which is D16's
    test for mechanical, and a reader that cannot see how `audit()` dispatches cannot tell
    you whether *anything* runs. Both are things to fix before a commit rather than
    questions to leave for a human, and the second is the more urgent of the two.

    **Read from the source, never from a live `audit()` run.** A registry gathered by
    running the function agrees with itself no matter what the file says. In `--staged` mode
    `read()` returns the staged blob, which makes this the one check whose subject is the
    files the commit will carry rather than the files that are executing — stage a new check
    without its call and the hook fails on it, which is the exact moment `docs/debts/`
    describes.

    `source` is one file to reconcile alone, defining its checks and calling them: a fixture
    under `--self-test`. The reader's behavior on a shape it cannot read has to be provable
    without restructuring the live package to find out. With no `source` the checks are
    every module's functions and the calls are the ones `rows.audit` makes.
    """
    if source is not None:
        sources = [source]
        dispatch_source = source
    else:
        sources = _dispatch_sources()
        dispatch_source = PACKAGE_DIR / "rows.py"
    checks: Dict[str, Tuple[Path, int]] = {}
    try:
        for path in sources:
            for name, line in defined_checks(ast.parse(read(path))).items():
                checks[name] = (path, line)
        dispatch_tree = ast.parse(read(dispatch_source))
    except (OSError, SyntaxError) as exc:
        report.add(
            "check dispatch",
            MECHANICAL,
            [
                Finding(
                    rel(source or PACKAGE_DIR),
                    f"cannot be parsed, so nothing can say which checks this file runs.\n"
                    f"{exc}",
                )
            ],
        )
        return

    called = dispatched_names(dispatch_tree, checks)
    findings: List[Finding] = []

    if called is None:
        findings.append(
            Finding(
                rel(dispatch_source),
                "defines no `audit()`, which is where this file's checks are dispatched "
                "from and where this row reads them.",
            )
        )
    elif checks and not called:
        findings.append(
            Finding(
                rel(dispatch_source),
                "`audit()` names none of the checks defined in this file. Either nothing "
                "this script reports is running, or dispatch moved out of `audit()` and "
                "this reader has to move with it.\nReported once rather than once per "
                "check: the fault is in the reading, and a wall of findings would each "
                "name the wrong cause.",
            )
        )
    else:
        for name, (path, line) in sorted(checks.items(), key=lambda item: (str(item[1][0]), item[1][1])):
            if name in called or name in UNDISPATCHED:
                continue
            findings.append(
                Finding(
                    f"{rel(path)}:{line}",
                    f"`{name}` is defined here and `audit()` never calls it, so it has "
                    f"never run. The row it would print is simply absent from the report, "
                    f"and an absent row is the one failure this file cannot show you.\n"
                    f"Call it from `audit()`, or record it in UNDISPATCHED with the reason "
                    f"it is defined and not dispatched.",
                )
            )

    for name, why in sorted(UNDISPATCHED.items()):
        if name not in checks:
            findings.append(
                Finding(
                    rel(dispatch_source),
                    f"UNDISPATCHED names `{name}` ({why}), which this file does not define. "
                    f"Renamed or deleted; either way the entry now exempts nothing.",
                )
            )
        elif called and name in called:
            findings.append(
                Finding(
                    rel(dispatch_source),
                    f"UNDISPATCHED records `{name}` as deliberately not dispatched ({why}), "
                    f"and `audit()` calls it. Drop the entry: an exemption that outlives its "
                    f"reason is how the list stops being read.",
                )
            )

    report.add(
        "check dispatch", MECHANICAL, findings,
        "every check defined here is called by audit()", scanned=len(checks)
    )


def check_subject_counts(report: Report, staged_only: bool = False) -> None:
    """Every row above declared how many subjects it had, and an empty one is pinned.

    THE ROW THAT MAKES THE OTHER ROWS HONEST. `Report.render` printed `ok` for any row
    whose findings list was empty, so a row that examined 2,964 references and a row that
    examined NONE were the same word. Measured on main inside a green `make check`:
    `paths 0 references resolve`, `make targets 0 references, 57 targets`, `env vars 0
    documented, all real`. The four ways a row goes quietly vacuous are all of them
    invisible that way — a walk root that moved, a renamed directory, an edited suffix
    list, and a corpus that cannot be read.

    Three findings, three different defects, kept apart on purpose:

      no count      the row printed a verdict over a subject nobody counted. Every row
                    that can print clean passes `scanned=`; a new one that does not is
                    stopped here rather than joining the vacuous set.
      unpinned zero the row examined nothing and `EXPECTED_EMPTY` does not say that is
                    legitimate. This is the failure the whole exercise is for.
      stale pin     `EXPECTED_EMPTY` names a row this file no longer emits. A permission
                    that outlives its row is how an exemption stops being read — the same
                    discipline `UNDISPATCHED` and the allowlist are held to.

    **A `staged` pin is a permission in ONE MODE.** The eight rows whose whole subject is
    the markdown set are legitimately empty when `--staged` narrows that set to nothing;
    the same zero in FULL mode is a broken walk and still fails. Pinning them
    unconditionally would have blinded the exact three rows the defect was observed on.

    **MECHANICAL, against the proposal that asked for informational.** A tag nothing can
    fail on is the state this row exists to end: `exit 2` in this repo has 23 standing
    findings and a measured session pushed past three stale citations because of it. The
    pin is what keeps that honest — a row that should be empty says so in one line with a
    reason, and everything else is a defect.

    It cannot itself be vacuous while `audit()` exists: its subject is the other rows, and
    `check dispatch` already refuses an `audit()` that names none of the checks.
    """
    findings: List[Finding] = []
    emitted = {row.check for row in report.checks}

    for row in report.checks:
        if row.check == "subject counts":
            continue
        # A ROW THAT PRINTED A PROBLEM IS NOT THIS ROW'S SUBJECT. The defect is the
        # vacuous `ok`, and a row rendering FAIL or ask is not rendering it — so a
        # findings-bearing row is judged on its findings and nothing else. It also keeps
        # the error paths honest-looking: `make targets` with no Makefile adds a finding
        # and no count, and "declared no subject count" beside it would be noise pointing
        # at the wrong thing. A row whose CLEAN path declares no count is caught the first
        # time that path is taken, which is the first time it could mislead anybody.
        if row.findings:
            continue
        if row.scanned is None:
            findings.append(
                Finding(
                    f"scripts/docs_audit -> {row.check}",
                    "declared no subject count, so nothing can tell a row that examined "
                    "everything from one that examined nothing. Pass `scanned=<n>` at that "
                    "row's `report.add` — the count it already prints in prose is usually "
                    "the number.",
                )
            )
            continue
        if row.scanned:
            continue
        pin = EXPECTED_EMPTY.get(row.check)
        if pin is None:
            findings.append(
                Finding(
                    f"scripts/docs_audit -> {row.check}",
                    "examined NOTHING and printed no problem. Either its subject moved — a "
                    "walk root, a renamed directory, an edited suffix list, an unreadable "
                    "corpus — or an empty subject is legitimate here, in which case pin the "
                    "row by name in `EXPECTED_EMPTY` with the reason beside it. A blanket "
                    "exemption is how a rule stops being one.",
                )
            )
            continue
        when, why = pin
        if when == "staged" and not staged_only:
            findings.append(
                Finding(
                    f"scripts/docs_audit -> {row.check}",
                    f"examined nothing in a FULL run. Its pin is `staged` only — {why} — so "
                    f"a zero here is a broken walk rather than a narrowed one.",
                )
            )

    for name, (when, why) in sorted(EXPECTED_EMPTY.items()):
        if when == "staged" and not staged_only and name not in emitted:
            # `coupling` is the case: a staged-only ROW is legitimately absent from a full
            # run, so its pin cannot be judged stale here. In staged mode it can.
            continue
        if name not in emitted:
            findings.append(
                Finding(
                    "scripts/docs_audit/core.py -> EXPECTED_EMPTY",
                    f"pins `{name}` ({when}: {why}), and no row by that name was emitted. "
                    f"Renamed or deleted; either way the pin now permits nothing, and the "
                    f"row it was written for — if it still exists — is unpinned.",
                )
            )

    empty = sum(1 for row in report.checks if row.scanned == 0)
    report.add(
        "subject counts",
        MECHANICAL,
        findings,
        f"{len(report.checks)} rows, every one declaring its subject; "
        f"{empty} examined nothing, all pinned",
        scanned=len(report.checks),
    )


def check_coupling(report: Report) -> None:
    changes = staged_changes()
    findings: List[Finding] = []
    # The subject is the source GROUPS this commit actually touched, not the size of
    # COUPLING — a commit under none of them asks no question, and the row now says so
    # rather than printing the same `ok` a fully-checked commit gets.
    groups = 0
    for sources, coupled_docs in COUPLING:
        touched = {
            path: count
            for path, count in changes.items()
            if any(path == s or path.startswith(s) for s in sources)
        }
        if touched:
            groups += 1
        if not touched:
            continue
        total = sum(touched.values())
        if total < COUPLING_MIN_LINES:
            continue
        if any(doc in changes for doc in coupled_docs):
            continue
        biggest = sorted(touched.items(), key=lambda item: -item[1])[:3]
        detail = ", ".join(f"{path} ({count} lines)" for path, count in biggest)
        findings.append(
            Finding(
                " ".join(coupled_docs),
                f"{total} lines staged under {'/'.join(s.rstrip('/') for s in sources)} "
                f"and none of these docs changed.\n"
                f"  largest: {detail}\n"
                f"  Still accurate? Not blocking — run /docs-audit to check the prose.",
            )
        )
    report.add("coupling", ADVISORY, findings, "staged code and its docs move together",
               scanned=groups)
