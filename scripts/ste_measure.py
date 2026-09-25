#!/usr/bin/env python3
"""The STE prose check's one measurer (D226, D-ratchets-become-offender-lists). Read by one
caller: `scripts/docs-audit.py`'s `ste offenders` row (read-only, the commit path). The pinned
per-file ratio this module used to feed (D229's ratchet) is retired. The row now compares the OFFENDERS this module names against `scripts/ste-offenders.json`, a
shrinking list keyed by each offender's identity, never by a count.

WHAT IT MEASURES. The vendored `scripts/ste/ste_lint.py`'s four ERROR-severity rules
(STE001 sentence-length, STE006 semicolon, STE007 Latin abbreviation, STE008 contraction —
computed from the linter's own `RULES` table, never a hand-kept list that could drift from
it), over the tracked markdown a caller hands it, MINUS the findings a named exemption class
recognises as an artifact of the text's SHAPE rather than its prose. See `EXEMPTIONS` below
for what is built today and what is named but deliberately left unbuilt.

WHAT AN OFFENDER IS. One SENTENCE that breaks one rule, named by a hash of its own text (see
`offender_identity`). Two semicolons in one sentence are one STE006 offender. The same
sentence written twice in one file is two offenders, and its entry is listed twice. An edit
that changes the sentence changes its identity, so a sentence cannot be reworded and stay
excused. A reflow cannot move it: whitespace is collapsed first, and a code span, a decision
citation or `VS Code` that crosses a line break is read over the joined paragraph, never
line by line (`join_span_breaks`). Code spans and decision ids are folded before the hash,
so an edit inside a code span, or a claim that turns a slug into a number, moves nothing.

THE RULER IS STILL PRINTED, AND GATES NOTHING. Errors per thousand words, over a PLAIN word
count (`text.split()`, matching `wc -w`), per bucket and repo-wide. It is the ruler
`docs/specs/ste-false-positives.md`'s survey used, so the row can print today's ratio beside
the survey's own floor. No number is pinned.

CALLERS BUILD THE FILE LIST; THIS MODULE NEVER TOUCHES DISK. `measure()` takes
`Sequence[Tuple[str, str]]` — (repo-relative path, text) pairs a caller has already read (via
`scripts/docs-audit.py`'s `read()` in staged mode) — so this file's own logic is exercised by
`docs-audit.py --self-test` with synthetic strings, no filesystem and no staged-mode state
required.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

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
# THREE OF THE FOUR CLASSES BUILT HERE ARE FROM A MEASURED SAMPLE, NOT A GUESS:
# `docs/specs/ste-false-positives.md`, a stratified sample of 265 findings (STE007's 130
# taken whole) hand-classified GENUINE / ARTIFACT / BORDERLINE against a rule stated before
# judging. Only ARTIFACT classes with a class-level MECHANICAL recognition rule are built.
#
# THE FOURTH, `via`, IS EXEMPT BY ARGUMENT RATHER THAN BY ARTIFACT RATE (owner's ruling,
# D226): STE007's own stated reason — different readers read a Latin abbreviation
# differently, and machine translation handles it badly — does not hold for an ordinary
# English preposition every reader reads the same way. `vs`/`vs.` IS a real abbreviation (of
# "versus") and stays a finding; a BORDERLINE class that concedes it needs a person's
# judgment — the sample's `via`/`vs` classification before this ruling — is not exempted for
# that reason alone, which is why this one exemption is argued rather than measured.
#
# A FIFTH CLASS, "verbatim quotation" (a blockquote or a `*"…"*` quoted line), WAS BUILT AND
# WAS REMOVED ON THE OWNER'S RULING (D226): the owner chose to rewrite around a
# quotation that trips a rule rather than exempt it. The cost is named where the pin is
# generated and in the decision entry — most of it lands on STE008 (contraction), whose
# sample was 93.3% this shape. Do not re-add this class without a new ruling.


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
    row (`docs/specs/ste-false-positives.md` §4.1)."""
    ste_lint = load_ste_lint()
    return bool(ste_lint.TABLE_ROW.match(_line_of(finding, lines)))


_DECISION_CITATION = re.compile(r"\(D\d+[,;]")


def _decision_citation(finding: Finding, lines: Sequence[str]) -> bool:
    """The decision-citation shorthand, `(D<n>; gloss)` or `(D<n>, amended)` — the semicolon
    or comma there separates an id from its gloss, not one clause from another. Recognised by
    the same anchored pattern for every occurrence on the line that contains the finding
    (`docs/specs/ste-false-positives.md` §4.3)."""
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
    findings (`docs/specs/ste-false-positives.md` §4.5)."""
    if finding.code != "STE007":
        return False
    line = _line_of(finding, lines)
    idx = finding.col - 1
    return any(match.start() <= idx < match.end() for match in _VS_CODE.finditer(line))


def _via(finding: Finding, lines: Sequence[str]) -> bool:
    """The word "via" itself, on the OWNER'S RULING (D226), by argument rather
    than by a measured artifact rate. STE007's own stated reason for flagging a Latin
    abbreviation is that different readers read it differently, and that machine translation
    handles it badly — true of the rule's genuine abbreviations (a full stop, or a two-word
    Latin phrase), false of "via", an ordinary English preposition every reader reads the
    same way. It sits in the rule's word table by category error, not because it behaves like
    one. `vs`/`vs.` is the opposite case — a real abbreviation, of "versus", with the rule's
    own replacement ("compared with") — and stays a finding. No line context is needed: the
    excerpt alone says whether the match was this word."""
    if finding.code != "STE007":
        return False
    return (finding.excerpt or "").lower() == "via"


EXEMPTIONS: Tuple[Exemption, ...] = (
    Exemption("table row", "a markdown `|` table cell", _table_row),
    Exemption("decision citation", "a `(D<n>; …)` shorthand", _decision_citation),
    Exemption("VS Code", "the editor's proper noun, not the abbreviation `vs.`", _vs_code),
    Exemption("via", "an ordinary preposition, not a Latin abbreviation", _via),
)

# NAMED, NOT BUILT: "enumeration collapsed into one paragraph" (a semicolon-joined checklist,
# or a parenthetical list of file/spec names run into prose). The lane's own sample rule
# concedes this is a PROXY ("3 or more semicolons... very likely an enumeration"), not a
# recognition — "flag rather than auto-exempt, since some genuinely long enumerations should
# still be turned into real bullet lists" (`docs/specs/ste-false-positives.md` §4.4). This
# ratchet exempts only what it can tell apart from ordinary prose without guessing, so this
# class stays a named gap rather than an approximated exemption. It accounted for 4 of 45
# STE006 and 2 of 45 STE001 sample findings.
#
# TWO MORE SHAPES THE SAMPLE NAMED, ALSO NOT BUILT. Both are ARTIFACT calls in the sample
# (`docs/specs/ste-false-positives.md`), and neither gets a recogniser here because neither
# has one this file's own bar calls obvious:
#
# - An UNDER-FENCED SHELL EXAMPLE, where the semicolons are shell syntax leaking out of a
#   command that was never wrapped in a proper code fence (STE006 sample #27,
#   `>/dev/null; do sleep 5; done`). Telling "this text is shell syntax" from "this text is
#   prose with a semicolon" needs the same kind of guess the enumeration proxy above already
#   declines to make — a line full of shell tokens still contains no marker this file can
#   read as "not prose" without a second parser.
# - The ACADEMIC "et al." CITATION CONVENTION (STE007 sample #34, "<Author> et al." naming a
#   paper's authors). A single occurrence in the whole 130-item STE007 population is not
#   enough to justify a class, and the boundary — a capitalized word before "et al." is not
#   reliably a surname rather than an ordinary sentence — is not obvious enough to build on
#   one example.


# ------------------------------------------------------------------ offender identity
#
# THE LIST IS KEYED BY WHAT OFFENDS, NEVER BY HOW MANY (D-ratchets-become-offender-lists). A
# count per file let a new bad sentence hide behind an old one fixed in the same file. An
# identity cannot: a new sentence has a new hash, and the list has no entry for it.

# A DECISION ID IS FOLDED BEFORE THE HASH, because `make merge`'s claim (D140) rewrites every
# slug citation to its number in the same commit that merges it. Without the fold, every
# listed sentence that cites a slug would change identity at the claim, go stale, and come
# back unlisted: red on the one commit that nobody writes by hand. The fold covers both forms
# the claim moves between: `D` plus digits (with an optional file tail) and `D-` plus a slug.
_DECISION_ID = re.compile(r"\bD(?:\d+(?:-[a-z0-9]+)*|-[a-z0-9]+(?:-[a-z0-9]+)*)")
DECISION_FOLD = "D#"

# Ten hex digits of SHA-1: about 10^12 values, so two different sentences in one file share a
# key by chance with a probability far below one in a million at this corpus's size.
IDENTITY_HEX = 10
# The label is for the person who fixes the sentence. It is never compared.
LABEL_CHARS = 72

# A DECISION ENTRY'S FILE IS KEYED BY ITS TAIL, NOT ITS NUMBER, for the same reason as the
# fold above: the claim renames `docs/decisions/D-<slug>.md` to `D<nnn>-<slug>.md`
# (`scripts/claim-ids.py:rename_claimed_entries`). Both names key to
# `docs/decisions/*-<slug>.md`, which holds no decision token for the claim to rewrite.
_DECISION_FILE = re.compile(r"^docs/decisions/D(?:\d+)?-(?P<tail>[^/]+\.md)$")


def list_key(relpath: str) -> str:
    """The key a file's offenders sit under in `scripts/ste-offenders.json`."""
    match = _DECISION_FILE.match(relpath)
    return f"docs/decisions/*-{match.group('tail')}" if match else relpath


def fold(text: str) -> str:
    """The text an identity hashes and a label shows: decision ids folded, whitespace
    collapsed."""
    return " ".join(_DECISION_ID.sub(DECISION_FOLD, text).split())


_COMMENT = re.compile(r"<!--.*?-->")


def _line_content(ste_lint, raw: str) -> str:
    """One source line as the linter's `segment_markdown` reads it before it picks a kind:
    HTML comments removed, right side stripped, a blockquote marker taken off."""
    content = _COMMENT.sub("", raw.rstrip("\n")).rstrip()
    quote = ste_lint.BLOCKQUOTE.match(content)
    return quote.group(1) if quote else content


def _line_spans(joined: str) -> List[Tuple[int, int]]:
    """Every span in one joined paragraph that a line-scoped reader must see whole.

    - A code span, paired as the linter pairs it: a backtick opens, the next one closes.
    - A decision citation, `(D<n>,` or `(D<n>;`, to its first `)`, as `_decision_citation`
      reads it.
    - The editor's name `VS Code`, as `_vs_code` reads it.
    """
    spans = [(m.start(), m.end()) for m in re.finditer(r"`[^`]*`", joined)]
    for match in _DECISION_CITATION.finditer(joined):
        end = joined.find(")", match.start())
        spans.append((match.start(), len(joined) if end == -1 else end + 1))
    spans.extend((m.start(), m.end()) for m in _VS_CODE.finditer(joined))
    return spans


def join_span_breaks(text: str, mode: str = "descriptive") -> str:
    """`text`, with every line break that falls INSIDE a line-scoped span removed: the lines
    one span runs across are joined into one line, with one space where each break was.

    WHY. Three readers see one LINE at a time. The vendored linter masks a code span per line
    (`ste_lint.Masker`, whose inline-code pattern stops at a newline). The `decision citation`
    and `VS Code` exemptions match on the finding's own line. So a span that crossed a line
    break read one way on one layout and another way on the next. A reflow then changed the
    findings and the identity of a sentence whose prose did not change. The first review of
    D-ratchets-become-offender-lists measured 518 such code-span lines in 95 files. The
    second found a citation's opening parenthesis and comma, then a break, in one decision
    entry's paragraph.

    WHAT IT JOINS, AND NOTHING ELSE. Within one prose or list paragraph, as the linter's own
    `segment_markdown` groups it, the line bodies are joined with one space, and
    `_line_spans` finds each span over that joined text. A break that falls inside a span is
    removed. The first line of a joined run is kept whole. Each later line gives only its
    body, the text the linter would read, so a blockquote marker or an indent does not land
    inside the span. A break outside every span is left alone, so a file with no such span
    comes back unchanged.

    Every caller that feeds the linter reads the SAME joined text (`measure`), so a finding's
    line and column, the exemption recognisers' line, and the sentence `_Sentences` locates
    all agree with each other.
    """
    ste_lint = load_ste_lint()
    lines = text.splitlines()
    paragraphs, _, _ = ste_lint.segment_markdown(lines, mode)
    # line number (1-indexed) -> the line numbers joined onto its end, in order.
    joins: Dict[int, List[int]] = {}
    for paragraph in paragraphs:
        if paragraph.kind not in ("prose", "list") or len(paragraph.segments) < 2:
            continue
        linenos = [seg.lineno for seg in paragraph.segments]
        bodies = [_line_content(ste_lint, lines[n - 1]).lstrip() for n in linenos]
        joined = " ".join(bodies)
        spans = _line_spans(joined)
        head = linenos[0]
        offset = -1
        for index in range(len(linenos) - 1):
            offset += len(bodies[index]) + 1  # the space that stands for this break
            if any(start < offset < end for start, end in spans):
                joins.setdefault(head, []).append(linenos[index + 1])
            else:
                head = linenos[index + 1]
    if not joins:
        return text

    joined_away = {n for tail in joins.values() for n in tail}
    out: List[str] = []
    for lineno, raw in enumerate(lines, start=1):
        if lineno in joined_away:
            continue
        if lineno in joins:
            bodies = [_line_content(ste_lint, lines[n - 1]).lstrip() for n in joins[lineno]]
            raw = " ".join([raw.rstrip()] + bodies)
        out.append(raw)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def offender_identity(sentence: str) -> str:
    """The hash half of an offender's key. `sentence` is the linter's masked text, so a code
    span reads as `CODE` (`ste_lint.strip_placeholders`) and an edit inside one moves
    nothing: the prose is the subject.

    THE CODE SPANS ARE HIDDEN OVER THE JOINED PARAGRAPH, NOT PER LINE. `measure` hands the
    linter `join_span_breaks(text)`, so a span that crossed a line break in the source is
    one placeholder here too, exactly as if it sat on one line."""
    ste_lint = load_ste_lint()
    folded = fold(ste_lint.strip_placeholders(sentence))
    return hashlib.sha1(folded.encode("utf-8")).hexdigest()[:IDENTITY_HEX]


def entry_key(entry: str) -> str:
    """`"<hash> <label>"` -> `"<hash>"`. Only the hash is ever compared: the label is for the
    person who fixes the sentence, and a claim may rewrite it."""
    return entry.split(" ", 1)[0]


class _Sentences:
    """Every sentence of one file, as the linter itself splits it, looked up by the
    (line, column) a finding reports.

    Built from the linter's own `segment_markdown`, `Block` and `split_sentences`, never a
    second splitter: a sentence here is exactly the unit STE001 measured. A heading or a table
    row is one unit, because the linter never splits one.
    """

    def __init__(self, ste_lint, text: str, mode: str):
        self.by_line: Dict[int, Tuple[object, int, object, List[Tuple[int, int]]]] = {}
        paragraphs, _, _ = ste_lint.segment_markdown(text.splitlines(), mode)
        for paragraph in paragraphs:
            if paragraph.kind in ("heading", "table"):
                for seg in paragraph.segments:
                    block = ste_lint.Block([seg], paragraph.kind, paragraph.mode)
                    self._index(block, [(0, len(block.text))])
                continue
            block = ste_lint.Block(paragraph.segments, paragraph.kind, paragraph.mode)
            starts = [offset for offset, _ in ste_lint.split_sentences(
                block.text, in_list=block.kind == "list")] or [0]
            spans = [(start, starts[i + 1] if i + 1 < len(starts) else len(block.text))
                     for i, start in enumerate(starts)]
            self._index(block, spans)

    def _index(self, block, spans: List[Tuple[int, int]]) -> None:
        for start, seg in block.starts:
            self.by_line[seg.lineno] = (block, start, seg, spans)

    def locate(self, line: int, col: int) -> Optional[Tuple[Tuple[int, int], str, str]]:
        """`((first line of the block, sentence start), masked sentence, readable
        sentence)`, or None when the line holds no prose the linter read."""
        hit = self.by_line.get(line)
        if hit is None:
            return None
        block, seg_start, seg, spans = hit
        offset = seg_start + max(0, col - 1 - seg.prefix)
        chosen = spans[0]
        for span in spans:
            if span[0] <= offset:
                chosen = span
            else:
                break
        start, end = chosen
        masked = block.text[start:end]
        # READABLE: each segment's own masker gives its code spans back, so a label shows the
        # sentence as it is written.
        parts = []
        for seg_offset, part in block.starts:
            lo, hi = max(start, seg_offset), min(end, seg_offset + len(part.text))
            if lo < hi:
                parts.append(part.masker.unmask(part.text[lo - seg_offset:hi - seg_offset]))
        return (block.lineno, start), masked, " ".join(" ".join(parts).split())


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
    # list key -> code -> sorted `"<hash> <label>"` entries, one per offender, so a sentence
    # written twice is listed twice. A file with no offender has no key.
    offenders: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)


def file_offenders(text: str, kept: Sequence[Finding], mode: str = "descriptive") -> Dict[str, List[str]]:
    """One file's offenders, per code: one per (sentence, rule), each keyed by identity.

    Several findings of one rule in one sentence are ONE offender. The same sentence twice in
    one file is two, and its entry appears twice, so a copy of a listed sentence needs a second
    entry and never hides behind the first."""
    ste_lint = load_ste_lint()
    sentences = _Sentences(ste_lint, text, mode)
    lines = text.splitlines()
    seen: Dict[Tuple[str, Tuple[int, int]], Tuple[str, str]] = {}
    for finding in kept:
        located = sentences.locate(finding.line, finding.col)
        if located is None:
            # A finding on a line the segmenter did not read as prose. Keyed by the line
            # itself, so it is still an identity and never silently dropped.
            raw = _line_of(finding, lines)
            located = ((finding.line, -1), raw, " ".join(raw.split()))
        where, masked, readable = located
        seen.setdefault((finding.code, where), (masked, readable))

    out: Dict[str, List[str]] = {}
    for (code, _where), (masked, readable) in sorted(seen.items()):
        label = fold(readable)
        if len(label) > LABEL_CHARS:
            label = label[:LABEL_CHARS - 1].rstrip() + "…"
        out.setdefault(code, []).append(f"{offender_identity(masked)} {label}")
    return {code: sorted(entries) for code, entries in out.items()}


def measure(paths: Sequence[Tuple[str, str]]) -> Measurement:
    """`paths`: (repo-relative path, text) pairs — every tracked markdown file a caller has
    already read. Runs the vendored linter once per file, keeps ERROR-severity findings,
    drops the ones an `EXEMPTIONS` class recognises (first match wins, so the classes'
    counts never double up on one finding), names each remaining one by its sentence, and
    reports the ratio ruler per bucket and repo-wide over a plain word count."""
    ste_lint = load_ste_lint()
    codes = error_codes(ste_lint)
    config = dict(ste_lint.DEFAULT_CONFIG)
    linter = ste_lint.Linter(config)
    # The same default mode `Linter.check_text` segments with, so a sentence here is the
    # sentence the linter measured.
    mode = "procedural" if config["mode"] == "procedural" else "descriptive"

    by_code: Dict[str, int] = {code: 0 for code in codes}
    exempted_by_class: Dict[str, int] = {ex.name: 0 for ex in EXEMPTIONS}
    words_by_bucket: Dict[str, int] = {}
    errors_by_bucket: Dict[str, int] = {}
    offenders: Dict[str, Dict[str, List[str]]] = {}

    for relpath, text in paths:
        bucket = bucket_for(relpath)
        words = plain_word_count(text)
        words_by_bucket[bucket] = words_by_bucket.get(bucket, 0) + words
        words_by_bucket[REPO_BUCKET] = words_by_bucket.get(REPO_BUCKET, 0) + words

        # THE LINTER READS THE JOINED TEXT, and so does everything below that turns a finding
        # into a sentence, so a code span or an exempted citation across a line break reads
        # exactly as one on a single line (`join_span_breaks`). The word count above keeps the file as
        # written: joining changes no whitespace-separated token.
        text = join_span_breaks(text, mode)
        lines = text.splitlines()
        kept: List[Finding] = []
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
            kept.append(finding)

        if kept:
            found = file_offenders(text, kept, mode)
            # TWO PATHS THAT SHARE A KEY POOL THEIR OFFENDERS rather than one overwriting the
            # other. Only a decision entry's tail can collide, and none does today.
            pooled = offenders.setdefault(list_key(relpath), {})
            for code, entries in found.items():
                pooled[code] = sorted(pooled.get(code, []) + entries)

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
        offenders=offenders,
    )
