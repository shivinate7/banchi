#!/usr/bin/env python3
"""The STE ratchet's one measurer (D-a-ste-ratchet). Read by two callers and reimplemented by
neither: `scripts/docs-audit.py`'s `ste ratchet` row (read-only, the commit path) and
`scripts/ste-ratchet-pin.py --pin` (the generator, D18, on no hook). Both language sides are
Python here, unlike D218's typed-interpunct pair, which had to duplicate one regex across a
Python/JS boundary — this repo has no such boundary to cross, so there is exactly one
implementation of "what counts" and both callers call it.

WHAT IT MEASURES. The vendored `scripts/ste/ste_lint.py`'s four ERROR-severity rules
(STE001 sentence-length, STE006 semicolon, STE007 Latin abbreviation, STE008 contraction —
computed from the linter's own `RULES` table, never a hand-kept list that could drift from
it), over the tracked markdown a caller hands it, MINUS the findings a named exemption class
recognises as an artifact of the text's SHAPE rather than its prose. See `EXEMPTIONS` below
for what is built today and what is named but deliberately left unbuilt.

THE RULER. Errors per thousand words, computed from a PLAIN word count (`text.split()`),
matching `wc -w` — not `ste_lint.file_stats()`'s STE-adjusted count, which excludes headings
and tables and folds numbers/quotes/parens into single tokens for its own sentence-length
budget. The two would read as different rulers over the same text and disagree for a reason
that has nothing to do with prose tightness; a plain count is also independently
reproducible with no dependency on the vendored linter's internals, and it is the ruler
`scratchpad/lane2-falsepositives.md`'s corpus survey already used, so the two are the same
unit rather than two numbers a reader has to reconcile by hand.

CALLERS BUILD THE FILE LIST; THIS MODULE NEVER TOUCHES DISK. `measure()` takes
`Sequence[Tuple[str, str]]` — (repo-relative path, text) pairs a caller has already read (via
`scripts/docs-audit.py`'s `read()` in staged mode, or a plain `Path.read_text()` in the pin
script) — so this file's own logic is exercised by `docs-audit.py --self-test` with synthetic
strings, no filesystem and no staged-mode state required.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
STE_LINT_PATH = ROOT / "scripts" / "ste" / "ste_lint.py"

# The four owned corpora that get their own bucket, plus "other" for everything else tracked
# markdown reaches (root docs, code-card-fork, .claude, vendor/, harness/results/…) and
# "repo" for the whole tree. Order matters only for rendering; comparisons are by key.
_BUCKET_PREFIXES: Tuple[Tuple[str, str], ...] = (
    ("docs/decisions", "docs/decisions/"),
    ("docs/specs", "docs/specs/"),
    ("docs/gates", "docs/gates/"),
    ("docs/debts", "docs/debts/"),
)
REPO_BUCKET = "repo"
OTHER_BUCKET = "other"


def bucket_for(relpath: str) -> str:
    for name, prefix in _BUCKET_PREFIXES:
        if relpath.startswith(prefix):
            return name
    return OTHER_BUCKET


def bucket_names() -> Tuple[str, ...]:
    """Every bucket key `measure()` can produce, `other` and `repo` included — the fixed set
    a pin file's `ratio_per_1k_words` is compared key-by-key against."""
    return tuple(name for name, _ in _BUCKET_PREFIXES) + (OTHER_BUCKET, REPO_BUCKET)


_ste_lint_module = None


def load_ste_lint():
    """The vendored linter, imported by path — `scripts/ste/` is not a package and this
    module must not add one just to get a normal import; every other hyphen-or-nested
    script in this repo is loaded the same way (`scripts/docs-audit.py`'s `_sibling`)."""
    global _ste_lint_module
    if _ste_lint_module is None:
        spec = importlib.util.spec_from_file_location("ste_lint", STE_LINT_PATH)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        # Registered in sys.modules BEFORE exec: the vendored file's `@dataclass` classes
        # (under `from __future__ import annotations`) resolve their own field types by
        # looking the module back up in `sys.modules` mid-definition, and a module that
        # cannot find itself there fails with an unrelated-looking AttributeError.
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        _ste_lint_module = module
    return _ste_lint_module


def error_codes(ste_lint) -> Tuple[str, ...]:
    """The rule codes at ERROR severity, read from the linter's own `RULES` table rather
    than hand-copied here — a future rule the vendored copy adds at `error` severity is
    picked up the next time this runs, with no second list to remember to edit."""
    return tuple(sorted(code for code, rule in ste_lint.RULES.items() if rule.severity == "error"))


def plain_word_count(text: str) -> int:
    """`wc -w`'s rule: whitespace-separated tokens, nothing folded or excluded. Deliberately
    NOT `ste_lint.file_stats()`'s word count — see the module docstring."""
    return len(text.split())


# --------------------------------------------------------------------- exemption recognisers
#
# Each class answers one question — "is this ERROR finding sitting on a construct the writer
# cannot change without deleting information or misquoting a source?" — for one line of the
# source file, using only the finding's own code/excerpt/line/col and that line's text. A
# recogniser that needed more than the line it fires on would be a second parser this file
# does not have, so a class that cannot be told apart at that granularity is named below and
# left unbuilt rather than approximated.
#
# THE FOUR CLASSES HERE ARE FROM A MEASURED SAMPLE, NOT A GUESS: `scratchpad/lane2-
# falsepositives.md`, a stratified sample of 265 findings (STE007's 130 taken whole) hand-
# classified GENUINE / ARTIFACT / BORDERLINE against a rule stated before judging. Only
# ARTIFACT classes with a class-level MECHANICAL recognition rule are built; BORDERLINE
# classes (bare `via`/`vs` in ordinary prose — no abbreviation is happening, whether swapping
# them reads better is a style call) are never exempted, because the class itself concedes it
# needs a person's judgment, which is exactly what an exemption must not need.


@dataclass(frozen=True)
class Finding:
    """The slice of `ste_lint.Finding` an exemption recogniser needs. Built here rather than
    passing the vendored `Finding` through, so this module's own public surface does not
    change shape if a future vendor re-pull renames one of that dataclass's fields."""

    code: str
    line: int  # 1-indexed physical line number in the source file
    col: int  # 1-indexed column, aligned to the ORIGINAL line (ste_lint.Block.locate)
    excerpt: Optional[str]


Recognizer = Callable[[Finding, str], bool]


@dataclass(frozen=True)
class Exemption:
    name: str
    reason: str
    recognize: Recognizer


def _line_of(finding: Finding, lines: Sequence[str]) -> str:
    idx = finding.line - 1
    return lines[idx] if 0 <= idx < len(lines) else ""


def _table_row(finding: Finding, lines: Sequence[str]) -> bool:
    """A markdown table row/cell. `ste_lint.py` itself already exempts table rows from every
    SENTENCE-level rule (STE001, STE005, STE014, STE015, STE016) via this same regex
    (`TABLE_ROW`, reused rather than re-typed so the two definitions of "is this a table row"
    cannot drift) — measured NOT extended to the WORD-level rules this ratchet tracks
    (STE006 semicolon, STE007 Latin abbreviation, STE008 contraction), which still fire
    inside a `|`-delimited cell exactly as in prose. 11 of 130 STE007 sample findings (all of
    STE007's population — the sample was a census) and 1 of 45 STE008 findings sat in a table
    row (`scratchpad/lane2-falsepositives.md` §4.1)."""
    ste_lint = load_ste_lint()
    return bool(ste_lint.TABLE_ROW.match(_line_of(finding, lines)))


_ITALIC_QUOTE = re.compile(r'\*"[^"]*"\*')


def _verbatim_quotation(finding: Finding, lines: Sequence[str]) -> bool:
    """A verbatim quotation of someone's own words: a markdown blockquote line (`ste_lint`'s
    own `BLOCKQUOTE` regex, reused) or this repo's own convention for a quoted spoken line,
    `*"…"*` (a run of decision entries quote the product owner this way). Rewriting a
    contraction, a semicolon or an abbreviation INSIDE a quotation misquotes the speaker
    rather than improving the prose — the STE008 sample was 93.3% this class alone
    (`scratchpad/lane2-falsepositives.md` §2, §4.2)."""
    ste_lint = load_ste_lint()
    line = _line_of(finding, lines)
    if ste_lint.BLOCKQUOTE.match(line):
        return True
    idx = finding.col - 1
    for match in _ITALIC_QUOTE.finditer(line):
        if match.start() <= idx < match.end():
            return True
    return False


_DECISION_CITATION = re.compile(r"\(D\d+[,;]")


def _decision_citation(finding: Finding, lines: Sequence[str]) -> bool:
    """The decision-citation shorthand, `(D<n>; gloss)` or `(D<n>, amended)` — the semicolon
    or comma there separates an id from its gloss, not one clause from another. Recognised by
    the same anchored pattern for every occurrence on the line that contains the finding
    (`scratchpad/lane2-falsepositives.md` §4.3)."""
    line = _line_of(finding, lines)
    for match in _DECISION_CITATION.finditer(line):
        # The finding sits inside this citation's parenthetical if it starts at or after the
        # opening paren; the citation's own close is not tracked because a nested paren
        # inside a gloss makes the true close ambiguous, and "at or after the anchor, before
        # the next anchor or end of line" is the same class of construct either way.
        end = line.find(")", match.start())
        end = len(line) if end == -1 else end + 1
        if match.start() <= finding.col - 1 < end:
            return True
    return False


_VS_CODE = re.compile(r"\bvs\s+Code\b", re.I)


def _vs_code(finding: Finding, lines: Sequence[str]) -> bool:
    """The literal proper noun "VS Code" (the editor), a false match on STE007's `vs`/`vs.`
    pattern rather than the comparator or the abbreviation. 4 of 130 STE007 sample/population
    findings (`scratchpad/lane2-falsepositives.md` §4.5)."""
    if finding.code != "STE007":
        return False
    line = _line_of(finding, lines)
    idx = finding.col - 1
    return any(match.start() <= idx < match.end() for match in _VS_CODE.finditer(line))


EXEMPTIONS: Tuple[Exemption, ...] = (
    Exemption("table row", "a markdown `|` table cell", _table_row),
    Exemption("verbatim quotation", "a blockquote or *\"…\"* quoted line", _verbatim_quotation),
    Exemption("decision citation", "a `(D<n>; …)` shorthand", _decision_citation),
    Exemption("VS Code", "the editor's proper noun, not the abbreviation `vs.`", _vs_code),
)

# NAMED, NOT BUILT: "enumeration collapsed into one paragraph" (a semicolon-joined checklist,
# or a parenthetical list of file/spec names run into prose). The lane's own sample rule
# concedes this is a PROXY ("3 or more semicolons... very likely an enumeration"), not a
# recognition — "flag rather than auto-exempt, since some genuinely long enumerations should
# still be turned into real bullet lists" (`scratchpad/lane2-falsepositives.md` §4.4). This
# ratchet exempts only what it can tell apart from ordinary prose without guessing, so this
# class stays a named gap rather than an approximated exemption. It accounted for 4 of 45
# STE006 and 2 of 45 STE001 sample findings.


@dataclass
class Measurement:
    total: int
    by_code: Dict[str, int]
    ratio_per_1k_words: Dict[str, float]
    exempted_by_class: Dict[str, int]
    exempted_total: int
    scanned_files: int
    words_by_bucket: Dict[str, int] = field(default_factory=dict)
    errors_by_bucket: Dict[str, int] = field(default_factory=dict)

    def to_pin(self) -> Dict[str, object]:
        """The shape written to `scripts/ste-ratchet.json` — no slack, no extra fields."""
        return {
            "total": self.total,
            "by_code": dict(sorted(self.by_code.items())),
            "ratio_per_1k_words": dict(sorted(self.ratio_per_1k_words.items())),
        }


def measure(paths: Sequence[Tuple[str, str]]) -> Measurement:
    """`paths`: (repo-relative path, text) pairs — every tracked markdown file a caller has
    already read. Runs the vendored linter once per file, keeps ERROR-severity findings,
    drops the ones an `EXEMPTIONS` class recognises (first match wins, so the classes'
    counts never double up on one finding), and reports the ratio ruler per bucket and
    repo-wide over a plain word count."""
    ste_lint = load_ste_lint()
    codes = error_codes(ste_lint)
    config = dict(ste_lint.DEFAULT_CONFIG)
    linter = ste_lint.Linter(config)

    by_code: Dict[str, int] = {code: 0 for code in codes}
    exempted_by_class: Dict[str, int] = {ex.name: 0 for ex in EXEMPTIONS}
    words_by_bucket: Dict[str, int] = {}
    errors_by_bucket: Dict[str, int] = {}

    for relpath, text in paths:
        bucket = bucket_for(relpath)
        words = plain_word_count(text)
        words_by_bucket[bucket] = words_by_bucket.get(bucket, 0) + words
        words_by_bucket[REPO_BUCKET] = words_by_bucket.get(REPO_BUCKET, 0) + words

        lines = text.splitlines()
        for raw in linter.check_text(relpath, text):
            if raw.severity != "error":
                continue
            finding = Finding(code=raw.code, line=raw.line, col=raw.col, excerpt=raw.excerpt)
            exempted_class = None
            for exemption in EXEMPTIONS:
                if exemption.recognize(finding, lines):
                    exempted_class = exemption.name
                    break
            if exempted_class is not None:
                exempted_by_class[exempted_class] += 1
                continue
            by_code[raw.code] = by_code.get(raw.code, 0) + 1
            errors_by_bucket[bucket] = errors_by_bucket.get(bucket, 0) + 1
            errors_by_bucket[REPO_BUCKET] = errors_by_bucket.get(REPO_BUCKET, 0) + 1

    total = sum(by_code.values())
    exempted_total = sum(exempted_by_class.values())
    ratio: Dict[str, float] = {}
    for bucket, words in words_by_bucket.items():
        if words:
            ratio[bucket] = round(errors_by_bucket.get(bucket, 0) / words * 1000.0, 3)

    return Measurement(
        total=total,
        by_code=by_code,
        ratio_per_1k_words=ratio,
        exempted_by_class=exempted_by_class,
        exempted_total=exempted_total,
        scanned_files=len(paths),
        words_by_bucket=words_by_bucket,
        errors_by_bucket=errors_by_bucket,
    )
