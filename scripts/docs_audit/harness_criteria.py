"""Harness tests and the pass criteria and evidence rows."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .core import (
    ADVISORY,
    Finding,
    MECHANICAL,
    ROOT,
    Report,
    _NUMBER_WORDS,
    exists,
    gates_text,
    glob_files,
    read,
    registered_tests,
    rel,
    staged_changes,
)

# ------------------------------------------------------------- harness tests + criteria

_TEST_REF_RE = re.compile(r"\bT([1-9][0-9]?)\b")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def string_assign(source: str, name: str) -> Optional[str]:
    """Value of a module-level string assignment, including implicit concatenation.

    `ast.literal_eval` handles the parenthesized multi-line form several tests use, which
    a regex would either mangle or silently truncate to the first fragment.
    """
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, SyntaxError):
                    return None
                return value if isinstance(value, str) else None
    return None


def gates_sections() -> Dict[str, str]:
    """`### T1 — …` heading text -> that section's body.

    Reads `gates_text()` — the docs/gates/ corpus reassembled — rather than docs/GATES.md
    directly, since the split (Lane D, 2026-09-16). The reassembly is byte-identical to the
    monolith this regex was written against, so nothing else here changed.
    """
    text = gates_text()
    if not text:
        return {}
    sections: Dict[str, str] = {}
    current: Optional[str] = None
    body: List[str] = []
    for line in text.splitlines():
        heading = re.match(r"^#{2,3}\s+(T[1-9][0-9]?)\b", line)
        if heading:
            if current:
                sections[current] = "\n".join(body)
            current = heading.group(1)
            body = [line]
            continue
        if line.startswith("## ") and current:
            sections[current] = "\n".join(body)
            current = None
            body = []
            continue
        if current:
            body.append(line)
    if current:
        sections[current] = "\n".join(body)
    return sections


# EVERY PUBLISHED COUNT OF THE HARNESS, against `harness/run.py:TESTS`. Written the way
# `route census` writes its claims — as the sentence reads, with the number as a word to
# resolve — and anchored on the words either side, because the file that DEFINES the list
# also carries deliberate RANGE and HISTORICAL claims that must be left alone: "T1-T4 are
# the original contract", "T5 (pricing) and T6 (geometry) arrived with batch script v2",
# "T8 (code cards) arrived with C9-C11", and CLAUDE.md's "It said seven until 2026-08-31".
#
# THE DEFENDANT IS THE RUNNER'S OWN DOCSTRING. `TESTS` held nine and the file above it said
# eight three times — the title "Harness runner — T1-T8", "exits 0 only when all eight tests
# pass", and "All eight tests always run" — while the `harness tests` row printed "9
# registered and documented", because its other side was the markdown and never this file.
# CLAUDE.md's own harness block carries the instruction "RECOUNT from harness/run.py's TESTS
# list", which is prose where the identical shape (route counts) has had a reader since D39.
_HARNESS_CLAIMS: Tuple[Tuple[str, str], ...] = (
    # (pattern as the sentence reads, the quantity the captured word must equal)
    (r"Harness runner — T1-T(\d+)", "highest"),
    (r"exits 0 only when all ([A-Za-z]+) tests pass", "registered"),
    (r"All ([A-Za-z]+) tests always run", "registered"),
    (r"all ([A-Za-z]+) verification tests", "registered"),
)

# The files that publish one. `harness/run.py` is NOT markdown and is deliberately in this
# list: a count inside the file that decides the list is the one most worth reading, and the
# one nothing read.
_HARNESS_CLAIM_FILES: Tuple[str, ...] = ("harness/run.py", "CLAUDE.md")


def _harness_claim_findings(names: Set[str]) -> List[Finding]:
    """Every published harness count against the registered set, both directions."""
    if not names:
        return []
    numbers = [int(name[1:]) for name in names if name[1:].isdigit()]
    quantities = {
        "registered": len(names),
        "highest": max(numbers) if numbers else 0,
    }
    findings: List[Finding] = []
    hits: Dict[str, int] = {}
    for name in _HARNESS_CLAIM_FILES:
        target = ROOT / name
        if not exists(target):
            findings.append(Finding(name, "does not exist, and it publishes a harness count."))
            continue
        text = read(target)
        for pattern, kind in _HARNESS_CLAIMS:
            for match in re.finditer(pattern.replace(" ", r"\s+"), text):
                word = match.group(1)
                value = int(word) if word.isdigit() else _NUMBER_WORDS.get(word.lower())
                if value is None:
                    continue
                hits[pattern] = hits.get(pattern, 0) + 1
                if value != quantities[kind]:
                    line = text[: match.start()].count("\n") + 1
                    findings.append(Finding(
                        f"{name}:{line}",
                        f"says {word.lower()} where harness/run.py's TESTS registers "
                        f"{quantities[kind]} ({kind}). The list is the count; recount off it "
                        f"rather than incrementing this sentence.",
                    ))
    for pattern, _kind in _HARNESS_CLAIMS:
        if not hits.get(pattern):
            findings.append(Finding(
                rel(Path(__file__).resolve()),
                f"the harness claim {pattern!r} matched nothing in "
                f"{', '.join(_HARNESS_CLAIM_FILES)}. It covered a published count that has "
                f"since been reworded or deleted, so the sentence it was watching is now "
                f"unwatched. Re-point the pattern, or drop it and say which sentence went — "
                f"a claim reworded into the PAST is still a claim this row has to have seen.",
            ))
    return findings


def check_harness_tests(report: Report, docs: List[Path], allowed: Dict[str, str]) -> None:
    tests = registered_tests()
    names = {name for name, _ in tests}
    sections = gates_sections()

    findings: List[Finding] = _harness_claim_findings(names)
    for name, path in tests:
        if not exists(path):
            findings.append(
                Finding("harness/run.py", f"{name} is in TESTS but {rel(path)} does not exist.")
            )
        if name not in sections:
            findings.append(
                Finding(
                    "docs/GATES.md",
                    f"{name} runs in the harness but has no `### {name}` section here. "
                    f"A test nobody documented is a threshold nobody agreed to.",
                )
            )

    for doc in docs:
        for number, line in enumerate(read(doc).splitlines(), start=1):
            for digits in _TEST_REF_RE.findall(line):
                name = "T" + digits
                # A doc may name a test to say it does not exist — D16 records why there is
                # no T7. That is a deliberate absence with a reason, which is what the
                # allowlist is for, and it goes stale the moment someone builds the test.
                if name in allowed:
                    continue
                if name not in names:
                    findings.append(
                        Finding(
                            f"{rel(doc)}:{number}",
                            f"{name} is referenced but not registered in "
                            f"harness/run.py:TESTS ({', '.join(sorted(names))}).",
                        )
                    )
    report.add("harness tests", MECHANICAL, findings,
               f"{len(names)} registered and documented", scanned=len(names))


def normalize(text: str) -> str:
    """Collapse whitespace. docs/GATES.md wraps at 96 columns, so a criteria line that
    agrees perfectly still arrives split across two lines with two spaces of indent."""
    return " ".join(text.split())


def docstring_pass_claim(source: str) -> Optional[str]:
    """The module docstring's `Pass:` paragraph, whitespace-joined. None if it makes none.

    A paragraph and not a line, because four of the six tests wrap their claim and t6's
    runs past 250 characters unwrapped. Joining to the next blank line is what lets the
    claim stay readable and still be compared whole; anything after that blank line is
    prose about the claim, not the claim.

    **Absence is deliberately not a finding.** Deleting a restatement is the correct answer
    to one going stale (D18), so a guard that reported the missing line would make the right
    fix the expensive one and push tests toward keeping a claim they no longer want.

    The module docstring only. A `Pass:` line there is the headline claim with PASS_CRITERIA
    a few lines below it; the same words inside a function docstring are not that claim, and
    reaching for them buys false positives for nothing.
    """
    try:
        doc = ast.get_docstring(ast.parse(source)) or ""
    except SyntaxError:
        return None
    lines = doc.split("\n")
    for index, line in enumerate(lines):
        if not line.strip().startswith("Pass:"):
            continue
        claim = [line.strip()]
        for follow in lines[index + 1:]:
            if not follow.strip():
                break
            claim.append(follow.strip())
        return " ".join(claim)
    return None


# The two forms `docs/GATES.md` publishes a criterion in. Seven sections use the bullet and
# two use the inline bold; both are legitimate markdown and neither is worth rewriting seven
# or two files to unify. The lifter accepts both so that the CHECK gets stricter without the
# DOCUMENT having to change — the whole doc cost of the equality rewrite was zero.
_PASS_BULLET_RE = re.compile(r"^-\s+\*\*Pass\*\*:\s*(.*)$")
_PASS_INLINE_RE = re.compile(r"\*\*Pass:\s*(.*)$")


def strip_presentation(text: str) -> str:
    """Drop markdown's wrapping so the comparison is about words, not formatting.

    Exactly three wrappers come off, and each one is presentation the author did not choose
    as part of the criterion: the inline form's closing `**`, the code ticks a machine string
    like `holdout_accuracy >= 0.95` is properly written in, and a terminal full stop.

    THE LIST IS DELIBERATELY SHORT AND CLOSED. Every entry added here is a character the two
    sides may now differ by, which is exactly the freedom this check exists to remove — so a
    fourth is an argument to have, not a convenience to add. What must never be stripped is
    anything inside the sentence: a number, a comparison operator, a word.
    """
    stripped = " ".join(text.split())
    stripped = stripped.rstrip("*").strip()
    stripped = stripped.strip("`").strip()
    return stripped.rstrip(".").strip()


def gates_pass_line(section: str) -> List[str]:
    """Every `Pass:` claim in one `### Tn` section, joined across its 96-column wraps.

    Returns a LIST, and the count is load-bearing in both directions. Zero means the section
    publishes no criterion at all and the equality below has nothing to stand on; two or more
    means a reader cannot tell which one governs. Both are findings, and neither was
    detectable while the check asked only whether the criterion appeared SOMEWHERE in the
    section — T8 and T9 have never had a `- **Pass**:` line and passed for it.

    Continuation stops at a blank line, the next bullet, or the next heading, the same rule
    `docstring_pass_claim` uses on the test side. Prose about a claim is not the claim.
    """
    lines = section.split("\n")
    claims: List[str] = []
    for index, line in enumerate(lines):
        text = line.strip()
        match = _PASS_BULLET_RE.match(text) or _PASS_INLINE_RE.search(text)
        if match is None:
            continue
        claim = [match.group(1)]
        for follow in lines[index + 1:]:
            following = follow.strip()
            if not following or following.startswith("- ") or following.startswith("#"):
                break
            claim.append(following)
        claims.append(" ".join(claim))
    return claims


def check_pass_criteria(report: Report) -> None:
    """A test's PASS_CRITERIA must appear in its docs/GATES.md section, word for word.

    harness/tests/__init__.py calls PASS_CRITERIA "the threshold, verbatim from
    docs/GATES.md" and for a long time nothing checked it, so five of six drifted. This
    blocks, because the unacceptable state is the one that produced that drift: a test
    change approved on its own merits that never reached the markdown.

    **Reconciliation runs from the test to the gate, not the other way.** When this fires,
    the test is right and `### Tn` in docs/GATES.md is what gets updated. The test is where
    a threshold is argued about and changed; the gate is where it is published. Rewriting a
    test to satisfy the doc inverts that and makes the tests worse to please a checker.

    Numbers are checked separately and first, so a disagreement about a threshold is never
    reported as a disagreement about wording.

    **The test's own module docstring is held to the same standard**, since that is the copy
    a reader meets first — `harness/tests/t1_id_eval.py` carried "overall_accuracy >= 0.95"
    two lines above the corrected literal, and five more paraphrases were live when this was
    added. Scoped narrowly on purpose: a `Pass:` line in a test module self-identifies as the
    claim and its ground truth is a module-level assignment in the same file, which is the
    bar for policing prose at all. Where that bar is not met, the answer is to delete the
    restatement rather than widen this check to chase it.
    """
    sections = gates_sections()
    mechanical: List[Finding] = []
    wording: List[Finding] = []
    # Two subject counts, because these are two rows. `read_criteria` is the tests whose
    # PASS_CRITERIA string this row managed to read — the wording row's subject — and
    # `compared` is the subset that also had a `### <name>` section in docs/GATES.md to
    # compare against, which is the threshold row's. Either reaching zero means the row
    # judged nothing, and before `scanned` existed both printed the same `ok` either way.
    read_criteria = 0
    compared = 0
    for name, path in registered_tests():
        if not exists(path):
            continue
        source = read(path)
        criteria = string_assign(source, "PASS_CRITERIA")
        if criteria is None:
            mechanical.append(
                Finding(rel(path), "no module-level PASS_CRITERIA string to read.")
            )
            continue
        read_criteria += 1
        claim = docstring_pass_claim(source)
        if claim is not None and normalize(criteria) not in normalize(claim):
            wording.append(
                Finding(
                    rel(path),
                    f"the module docstring's `Pass:` claim is a paraphrase, not the "
                    f"criterion.\n"
                    f"  docstring: {claim}\n"
                    f"  test:      {criteria}\n"
                    f"  Publish the criterion verbatim, or delete the `Pass:` line — both "
                    f"are correct answers. What is not: dropping something the paraphrase "
                    f"knew to satisfy this check. Keep it as its own sentence after the "
                    f"blank line.",
                )
            )

        section = sections.get(name)
        if section is None:
            continue
        compared += 1
        # THE COMPARISON IS AGAINST THE PUBLISHED LINE, BY EQUALITY, and the two legs it
        # replaces were both substring tests against the whole section. That is not a
        # tightening for its own sake — measured on 2026-09-05, lowering T1's
        # `holdout_accuracy >= 0.95` to `>= 0.9` in the TEST left both rows green:
        #
        #   the number leg   `'0.9' in section`  — true, because the section says `0.95`
        #   the wording leg  `'... >= 0.9' in section` — true, for the same reason
        #
        # So the threshold that decides whether it is safe to spend money on a batch could be
        # lowered by deleting one character, and this file would report `ok` twice. Equality
        # against the lifted line cannot be satisfied that way.
        claims = gates_pass_line(section)
        if len(claims) != 1:
            mechanical.append(
                Finding(
                    f"docs/GATES.md `### {name}`",
                    f"publishes {len(claims)} `Pass:` claims; exactly one governs.\n"
                    f"  PASS_CRITERIA: {criteria}\n"
                    f"  Zero means the criterion is not published where a reader looks for "
                    f"it. More than one means nobody can tell which is the gate.",
                )
            )
            continue
        published = strip_presentation(claims[0])
        wanted = strip_presentation(criteria)
        if published == wanted:
            continue
        # Numbers first, so a moved threshold is never reported as a reworded sentence.
        moved = sorted(set(_NUMBER_RE.findall(wanted)) ^ set(_NUMBER_RE.findall(published)))
        if moved:
            mechanical.append(
                Finding(
                    rel(path),
                    f"PASS_CRITERIA and `### {name}` in docs/GATES.md disagree about "
                    f"{', '.join(repr(number) for number in moved)}.\n"
                    f"  test:      {wanted}\n"
                    f"  published: {published}\n"
                    f"  A threshold is the one thing here that costs money to get wrong.",
                )
            )
        else:
            wording.append(
                Finding(
                    rel(path),
                    f"PASS_CRITERIA is not what `### {name}` in docs/GATES.md publishes.\n"
                    f"  test:      {wanted}\n"
                    f"  published: {published}\n"
                    f"  Update the `Pass:` line in `### {name}` to the test's text. The test "
                    f"is the source; the gate publishes it. Do not reword the test to match "
                    f"the doc.",
                )
            )
    # `pass criteria` and `criteria wording` merged into one row by M3 (test-audit-
    # 2026-09-27, L8, Q8 yes) — both questions this function already answers, now one
    # printed verdict. `scanned` takes `read_criteria`, the wider of the two subject
    # counts: every test whose PASS_CRITERIA this function could read, a superset of
    # `compared` (which also needs a docs/GATES.md section to exist).
    report.add("pass criteria", MECHANICAL, mechanical + wording,
               "every threshold matches GATES.md, and every criterion is published verbatim",
               scanned=read_criteria)


# ------------------------------------------------------ the evidence behind a criterion


EVIDENCE_DIR = ROOT / "harness" / "results"

# Changing any of these changes what a score MEANS: the test decides what counts as
# correct, the fixtures decide which cards were scored, the prompt decides what was asked.
# A score recorded before one of them is evidence about a different measurement.
EVIDENCE_SOURCES = (
    "harness/tests/t1_id_eval.py",
    "harness/eval/fixtures.py",
    "identify/prompt.py",
)

# The comparison inside a PASS_CRITERIA sentence — `holdout_accuracy >= 0.95`. Only `>=`
# and `>`: a criterion written the other way round is not this shape and is reported as
# unreadable rather than guessed at, which is the same disposition `pass criteria` takes
# after equality replaced its two substring tests.
_CRITERION_BAR = re.compile(r"(>=|>)\s*([0-9]*\.?[0-9]+)")


def check_criteria_evidence(report: Report) -> None:
    """The criterion must name the field the score file says the gate actually read.

    This catches incident #1's class at the layer it lived: `overall_accuracy >= 0.95` does
    not contain "holdout", and nothing compared the two. `gated_on` is the right thing to
    read because it is **written by the run**, from the same name that selects the split —
    so it reports what the code did, not what a second literal claims it did.

    That property had to be built before this check could rest on it. `gated_on` was an
    independent mention of `fixtures.HOLDOUT` until 2026-08-11, which is the sibling-literal
    anti-pattern one layer down: mutating the selection left `gated_on` unchanged and this
    check would have gone green on a tree whose gate read the tune half. See the premise
    correction in `docs/specs/audit-retirement.md`.

    Zero score files is itself a finding. A criterion with no recorded run behind it is not
    a passing measurement, it is an unmeasured claim.

    **AND THE VALUE IS READ, NOT THE PROSE — three changes, 2026-09-12.** This row tested
    whether the string `holdout_accuracy` occurred inside PASS_CRITERIA's own sentence and
    never opened `payload[field]` at all. So a run recording `holdout_accuracy: null` — or
    0.40 — printed `ok criteria evidence 1 scored run, gate field published`, over the one
    number that decides whether it is safe to spend money on a Batch submission.

    The identical mistake was already measured ONE ROW OVER: `check_pass_criteria` was green
    while a lowered `>= 0.9` sat inside the published `0.95`, and the fix on 2026-09-05 was
    to compare by equality. The lesson did not travel the twenty lines to here.

      1. `payload[field]` is read. Absent or null is `unmeasured`; a number is compared
         against the threshold lifted out of PASS_CRITERIA's own comparison.
      2. A score file naming a test `registered_tests()` does not carry was a silent
         `continue`. It is a finding now, and its remedy is deleting the stale score rather
         than editing a criterion — a retired test's score answers for nothing.
      3. `unmeasured` and `below floor` stay DIFFERENT findings. Conflating them is what
         teaches a reader to skim the row: one is a run that did not happen, the other is a
         run that failed, and they have opposite remedies.
    """
    criteria = {
        name: string_assign(read(path), "PASS_CRITERIA")
        for name, path in registered_tests()
        if exists(path)
    }
    scores = glob_files(EVIDENCE_DIR, "t1*.json")
    findings: List[Finding] = []
    if not scores:
        findings.append(
            Finding(
                "harness/results/",
                "no t1 score file, so no criterion here has a recorded run behind it.\n"
                "  Run `make harness` and commit the result.",
            )
        )
    for score in scores:
        try:
            payload = json.loads(read(score))
        except ValueError:
            findings.append(Finding(rel(score), "is not readable JSON."))
            continue
        gated = payload.get("gated_on")
        if not isinstance(gated, str) or not gated:
            findings.append(
                Finding(
                    rel(score),
                    "records no `gated_on`, so nothing says which field the gate read.",
                )
            )
            continue
        named = str(payload.get("test", "T1"))
        text = criteria.get(named)
        if text is None:
            # WAS A SILENT `continue`. A score file for a test nothing registers is a file
            # whose criterion nobody compared, and the row counted it as a scored run.
            findings.append(
                Finding(
                    rel(score),
                    f"names test `{named}`, which harness/run.py's TESTS does not register, "
                    f"so nothing compared its criterion.\n"
                    f"  registered: {', '.join(sorted(criteria)) or '(none)'}\n"
                    f"  Delete the stale score. A retired test's result answers for nothing, "
                    f"and editing a live criterion to make this row quiet would be the "
                    f"wrong repair.",
                )
            )
            continue
        field = gated + "_accuracy"
        if field not in text:
            findings.append(
                Finding(
                    rel(score),
                    f"the run gated on `{field}`, which PASS_CRITERIA does not name.\n"
                    f"  score file: gated_on = {gated!r}\n"
                    f"  criterion:  {text}\n"
                    f"  The run is the fact. Fix the criterion, or the code that chose the "
                    f"split — never edit the score file to agree.",
                )
            )
            continue

        # THE VALUE, AND THE THRESHOLD THE CRITERION PUBLISHES FOR IT. Lifted from the
        # criterion's own comparison rather than from the score file's `accuracy_floor`:
        # that key is the run's copy of the same number, so comparing one to the other
        # asks a file whether it agrees with itself.
        measured = payload.get(field)
        bar = _CRITERION_BAR.search(text or "")
        if not isinstance(measured, (int, float)) or isinstance(measured, bool):
            findings.append(
                Finding(
                    rel(score),
                    f"gated on `{field}` and recorded no measurement for it "
                    f"({measured!r}).\n"
                    f"  criterion:  {text}\n"
                    f"  This is UNMEASURED, not failing — the run did not produce the number "
                    f"the gate reads. Re-run `make harness` and commit the score; do not "
                    f"read a missing value as a passing one, which is what this row did "
                    f"until 2026-09-12.",
                )
            )
        elif bar is None:
            findings.append(
                Finding(
                    rel(score),
                    f"gated on `{field}` and PASS_CRITERIA publishes no comparison this row "
                    f"can read for it.\n"
                    f"  criterion:  {text}\n"
                    f"  It has to say `{field} >= <number>` for the recorded value to be "
                    f"checked against anything. Without one the score is a number beside a "
                    f"sentence, which is the state this row exists to end.",
                )
            )
        else:
            floor = float(bar.group(2))
            operator = bar.group(1)
            passes = measured > floor if operator == ">" else measured >= floor
            if not passes:
                findings.append(
                    Finding(
                        rel(score),
                        f"records `{field}` at {measured} against a published floor of "
                        f"{operator} {floor}.\n"
                        f"  criterion:  {text}\n"
                        f"  BELOW FLOOR, and this is the number that decides whether it is "
                        f"safe to spend money on a Batch submission. Fix the measurement or "
                        f"argue the floor down in docs/GATES.md — never both in silence.",
                    )
                )
    report.add(
        "criteria evidence", MECHANICAL, findings,
        f"{len(scores)} scored run, gate field published", scanned=len(scores)
    )


def check_evidence_freshness(report: Report, staged_only: bool) -> None:
    """A staged edit to what the score measures, with no re-scored result beside it.

    **Advisory, structurally.** The severity is written at the one `report.add` below and no
    branch raises it, for D16's stated reason: a blocking question teaches you to reach for
    `--no-verify`, which also disarms the three opsec rules in the same hook. Trading a
    bearer-instrument guard for a staleness reminder is a bad trade. Same shape as
    `scripts/audit-history.py` being structurally unable to gate.

    No minimum-lines floor, unlike the coupling row: a two-line threshold edit is exactly
    the dangerous one.

    **Staged only, and the committed half is deliberately absent.** Comparing the last
    commit touching these sources against the last commit touching `harness/results/` was
    designed, built and dropped: `docs/GATES.md` has the score file rewritten *only* when
    the measurement changes, so "re-ran, nothing moved" and "never re-ran" are the same
    history by design. The test therefore fired on every no-measurement-affecting edit and
    could not be cleared except by touching the score file — the exact noise that rule
    exists to prevent. A permanently-lit advisory would have taught us to skip exit 2
    everywhere. See the withdrawn ledger in `docs/specs/audit-retirement.md`; reviving it
    means arguing against the results-file rule first.

    Known limit, so a quiet row is not misread: this sees only what a commit stages. The
    stop gate runs the harness at every turn end, which narrows the rest without closing it.
    """
    findings: List[Finding] = []
    if staged_only:
        staged = set(staged_changes())
        touched = [name for name in EVIDENCE_SOURCES if name in staged]
        if touched and not any(name.startswith("harness/results/") for name in staged):
            findings.append(
                Finding(
                    " ".join(touched),
                    "staged, and nothing under harness/results/ is.\n"
                    "  Still the same measurement? If it moved, re-run `make harness` and "
                    "commit the score with it. Not blocking.",
                )
            )
    report.add(
        "evidence freshness",
        ADVISORY,
        findings,
        "staged score sources bring their result",
        # Its subject is the STAGED set. In full mode there is no staged set, so the
        # row prints `none` rather than a green it did not earn.
        scanned=len(EVIDENCE_SOURCES) if staged_only else 0,
    )
