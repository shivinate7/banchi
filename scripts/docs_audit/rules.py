"""Rule enforcement and identifier spelling."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from . import core
from .core import (
    Finding,
    MECHANICAL,
    PACKAGE_DIR,
    ROOT,
    Report,
    SELF,
    _STAGED_PATHS,
    _sibling,
    _walk,
    exists,
    glob_files,
    markdown_files,
    read,
    rel,
)
from .paths_commands import _MAKE_REF_RE, _MAKE_RULE_RE, iter_code_lines
from .records import _corpus, _debts_corpus
from .spelling import (
    MARKDOWN_SPELLING_ALLOW,
    MARKDOWN_SPELLING_EXCLUDE,
    MARKDOWN_SPELLING_RULE,
    SPELLING_SUFFIXES,
    spelling_findings,
)
from .strings import (
    _offender_diff,
    _offender_growth,
    _offender_list_at_merge_base,
    _offender_list_shape,
    _read_offender_list,
)

# --------------------------------------------------- rule enforcement (mechanise, or argue)

HARD_RULES_HEADING = "## Hard rules"

# THREE PINNED NUMBERS, AND THEY ARE PINNED RATHER THAN DERIVED ON PURPOSE. The whole
# argument of this row is that prose gets skirted, so the only figures it can trust are ones
# a person had to edit in a diff somebody read.
#
# `HARD_RULE_FLOOR` is the NON-VACUITY guard and it is the important one. A parser that finds
# nothing, over a section somebody reworded or renamed, would otherwise print `ok` — which is
# this repo's signature defect in a new costume: a check that cannot tell "nothing is wrong"
# from "nothing is known yet". Nine instances of that shape landed in twenty-four hours on
# 2026-09-12, two of them docs rows that passed while reporting `0 entries` over an emptied
# corpus. So: fewer rules than this reads as a BROKEN READER, never as a clean tree.
#
# `PROSE_ONLY_EXPECTED` is this repo's prose debt, mechanically tracked: the number of hard
# rules that name no mechanism and instead argue why none can exist. **It is an EQUALITY and
# not a ceiling, which a mutation arm taught me.** With a ceiling, arm 2 — deleting rule 5's
# `NOT MECHANIZED:` admission — SURVIVED: that rule's prose also mentions `make harness` as
# EVIDENCE, so with the admission gone it read as mechanized, and the debt silently fell from
# six to five. A number that can only be checked in one direction lets an honest admission be
# deleted for free, which is the precise accounting this row exists to prevent. So both
# directions fail: build a mechanism and you lower the pin in the same commit; add a rule with
# no enforcement and you raise it and say why.
HARD_RULE_FLOOR = 12
PROSE_ONLY_EXPECTED = 5

# BOLD, AND THAT IS NOT COSMETIC. The sentinel has to be a DECLARATION, so it is matched as
# the bold run a rule writes it in — otherwise the rule immediately above, which explains the
# sentinel and quotes it in backticks, would read as having claimed one, and rule 0 would
# count itself as prose. A check that miscounts its own author is not a check.
NOT_MECHANIZED = "**NOT MECHANIZED:**"
_ARGUMENT_MIN_WORDS = 12

_ROW_NAME_RE = re.compile(r'report\.add\(\s*\n?\s*"([^"\n]+)"')
_MECH_PATHS = ("scripts/", "harness/tests/", "app/tests/", "app/eslint.config.js", "ruff.toml",
               ".claude/settings.json", ".codex/hooks.json", ".github/workflows/")


def audit_row_names() -> Set[str]:
    """Every row name the auditor registers, read out of its own source.

    Self-referential on purpose: a rule that cites `` `raw color` `` as its enforcement is
    citing a row, and the only authority on which rows exist is the file that adds them. A
    hand-kept list here would be a second enumeration of the same thing, which is the drift
    `check census` already exists to catch one level up.
    """
    return {
        row
        for path in [*glob_files(PACKAGE_DIR, "*.py"), SELF]
        for row in _ROW_NAME_RE.findall(read(path))
    }


def hard_rule_blocks(text: str) -> List[Tuple[int, str]]:
    """(line number, block text) for every top-level bullet under `## Hard rules`.

    A block is the bullet and everything indented under it, up to the next top-level bullet
    or the end of the section — so a rule's mechanism may be named anywhere in its own prose
    and not only on the first line.
    """
    lines = text.splitlines()
    start = None
    for number, line in enumerate(lines, start=1):
        if line.strip() == HARD_RULES_HEADING:
            start = number
            break
    if start is None:
        return []
    blocks: List[Tuple[int, str]] = []
    current: List[str] = []
    at = 0
    for number in range(start + 1, len(lines) + 1):
        line = lines[number - 1]
        if line.startswith("## "):
            break
        if line.startswith("- "):
            if current:
                blocks.append((at, "\n".join(current)))
            current, at = [line], number
        elif current:
            current.append(line)
    if current:
        blocks.append((at, "\n".join(current)))
    return blocks


def mechanism_refs(block: str, targets: Set[str], rows: Set[str]) -> Tuple[List[str], List[str]]:
    """(references that RESOLVE, references that name something that does not exist).

    Three spellings count as naming a mechanism, and each is checked against the thing it
    names rather than against a pattern — a citation of a deleted guard is worse than no
    citation, because it reads as coverage:

    - `` `make <target>` `` where the target is a real rule in the Makefile
    - a backticked docs-audit row name this file actually registers
    - a path under `scripts/`, `harness/tests/`, `app/tests/` or `.github/workflows/`, or one
      of the four config files that carry a repo rule, that exists on disk

    Prose is read only inside backticks and fences, for `iter_code_lines`' reason: English is
    full of `make it` and `make the`.
    """
    resolves: List[str] = []
    dangling: List[str] = []
    for _, spans in iter_code_lines(block):
        for span in spans.split("\n"):
            token = span.strip().strip("`")
            match = _MAKE_REF_RE.match(token)
            if match:
                (resolves if match.group(1) in targets else dangling).append(f"make {match.group(1)}")
                continue
            if token in rows:
                resolves.append(f"the `{token}` row")
                continue
            if token.startswith(_MECH_PATHS):
                bare = token.split(":")[0].split()[0]
                (resolves if exists(ROOT / bare) else dangling).append(bare)
    return resolves, dangling


def argued_exemption(block: str) -> Tuple[bool, int]:
    """(the block argues its own unenforceability, words of argument it gives).

    The sentinel is a fixed string rather than a pattern because the point is a DELIBERATE
    claim: a session writing it is saying "I looked, and here is what a machine would have to
    be able to see." A bare sentinel with nothing after it is the rubber stamp this row would
    otherwise become, so the argument has a length floor.
    """
    at = block.find(NOT_MECHANIZED)
    if at < 0:
        return False, 0
    return True, len(block[at + len(NOT_MECHANIZED):].split())


_BARE_ID_RE = re.compile(r"\b(DEBT|D)(\d+)(?:-D(\d+))?\b")
_GLOSS_STOPWORDS = frozenset((
    "the", "and", "for", "not", "one", "its", "are", "was", "but", "who", "has", "had", "can",
    "may", "his", "her", "that", "this", "with", "from", "into", "what", "when", "than", "then",
    "them", "they", "their", "there", "where", "which", "while", "will", "would"))


def _entry_heading(kind: str, number: int) -> Optional[str]:
    """The heading line of decision `D<n>` or debt `DEBT<n>`, or None. One home: the corpus."""
    corpus = _corpus() if kind == "D" else _debts_corpus()
    path = corpus.path_for(f"D{number}" if kind == "D" else str(number)) if corpus else None
    return read(path).split("\n", 1)[0] if path else None


def _gloss_words(s: str) -> Set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower())
            if len(w) >= 3 and w not in _GLOSS_STOPWORDS}


def _gloss_matches(gloss: str, heading: str) -> bool:
    """True when at least one gloss word is in the heading (equal, or the same 5-letter stem)."""
    head = _gloss_words(heading)
    for w in _gloss_words(gloss):
        if any(w == h or (len(w) >= 5 and len(h) >= 5 and w[:5] == h[:5]) for h in head):
            return True
    return False


def _gloss_after(rest: str) -> Optional[str]:
    """The gloss that follows an id: ` (gloss)` or `, gloss`. None when neither is there."""
    rest = rest[1:] if rest.startswith("`") else rest
    if rest.startswith(" ("):
        return rest[2:].split(")", 1)[0]
    m = re.match(r",\s+([^,);:.\n]+)", rest)
    return m.group(1) if m else None


def bare_id_findings(text: str) -> List[Finding]:
    """Each decision or debt id in `CLAUDE.md`, at its first use in a paragraph, needs a gloss.

    The gloss is `D43 (short words)` or `D43, short words` (parent rule
    `speak-cite-id-plus-gloss`). A paragraph is a run of lines with no blank line, and each
    bullet starts its own. A later use of the same id in that paragraph may stay bare. At
    least one gloss word must be in the entry's own heading (`docs/decisions/`,
    `docs/debts/`), so `D7, rewritten` fails. A range `D<a>-D<b> (words)` may match any
    heading in it. Whether the gloss is a fair short is a person's judgement.
    """
    found: List[Finding] = []
    seen: Set[str] = set()
    for number, line in enumerate(text.split("\n"), 1):
        if not line.strip() or re.match(r"\s*[-*] ", line):
            seen = set()
        for m in _BARE_ID_RE.finditer(line):
            ident = m.group(0)
            if ident in seen:
                continue
            seen.add(ident)
            kind = m.group(1)
            lo = int(m.group(2))
            hi = int(m.group(3)) if m.group(3) else lo
            gloss = _gloss_after(line[m.end():])
            headings = [_entry_heading(kind, n) for n in range(lo, hi + 1)]
            if gloss is None:
                found.append(Finding(
                    f"CLAUDE.md:{number}",
                    f"`{ident}` has no gloss. Write `{ident} (<2-6 words from its heading>)` "
                    "at its first use in the paragraph."))
            elif not any(h and _gloss_matches(gloss, h) for h in headings):
                found.append(Finding(
                    f"CLAUDE.md:{number}",
                    f"the gloss `{gloss}` for `{ident}` shares no word with the entry's own "
                    "heading. Take the gloss from the heading."))
    return found


def check_rule_enforcement(report: Report) -> None:
    """Every hard rule names the thing that enforces it, or argues why nothing can.

    **Blocking, on D16's test: there is nothing to judge here.** A rule either cites a
    mechanism that resolves, or carries the sentinel and an argument. Whether the mechanism is
    any *good* is a question for a person; whether one is named at all is arithmetic.

    **The owner's instruction, 2026-09-12, is the whole specification**: *"i need this
    everything fucking mechanically fixed im tired of prose being bypassed"* … *"every rule
    for all time, anything that can be mechanically enforced, should be mechanically enforced,
    and make this a rule to enforce going forward too."*

    **Why it is a row and not a sentence in `CLAUDE.md`.** A sentence is the thing being
    complained about. The evidence, all of it from one twenty-four hour stretch: a session
    wrote `a-pgrep-waiter-matches-itself` into its own memory, READ it, and then wrote the
    exact forbidden waiter loop — and its own file now records that the rule failed *because*
    it was phrased as an explanation to recall rather than a prohibition to trip over. The
    same session wrote a rule against silencing a write and then swallowed two commit refusals
    with `>/dev/null 2>&1`. §11 carried a sentence about two observed mutation
    failures that were measured false on both counts. `screen-freshness --self-test` exited 1
    on main while sitting on no make target and printing *"run --self-test"*. Against that:
    `raw color`, `storage keys`, `check registry`, `codex hooks`, `id claims`
    and `shell substitution` have never once been bypassed, because none of them can be.

    **What it cannot see, by name.** Whether the named mechanism actually covers the rule —
    a rule could cite `make lint` and be about something lint never reads, and this row would
    pass it. It reads the citation, not the coverage. It also reads only `CLAUDE.md`'s Hard
    rules section: the Working agreement, the Commands prose, the decision corpus and the
    memory directory are all rule surfaces and none is governed here yet. And it cannot rank —
    a trivial guard and a mutation-tested one count the same.

    **And it cannot detect its own absence.** Deleting the rule-count floor from this function
    leaves the row printing `ok` over a section a rule short — arm 9, which survived by
    definition rather than by oversight. `check dispatch` sees a whole row go missing and
    nothing sees an assertion inside one go missing, which the comment on that row already
    states as the shape of the thing rather than a bug to patch.
    """
    findings: List[Finding] = []
    doc = ROOT / "CLAUDE.md"
    if not exists(doc):
        report.add("rule enforcement", MECHANICAL, [Finding("CLAUDE.md", "does not exist")])
        return
    text = read(doc)
    blocks = hard_rule_blocks(text)
    if not blocks:
        report.add("rule enforcement", MECHANICAL, [Finding(
            "CLAUDE.md",
            f"found no rules under `{HARD_RULES_HEADING}`. Either the heading was reworded or "
            f"this reader is broken — and a reader that finds nothing must never print `ok`, "
            f"which is the whole reason this row has a floor.",
        )])
        return

    makefile = ROOT / "Makefile"
    targets = set(_MAKE_RULE_RE.findall(read(makefile))) if exists(makefile) else set()
    rows = audit_row_names()

    findings.extend(bare_id_findings(text))

    prose_only: List[str] = []
    for line, block in blocks:
        headline = block[2:].strip().split("\n")[0].strip("*").strip()[:64]
        resolves, dangling = mechanism_refs(block, targets, rows)
        argued, words = argued_exemption(block)
        for dead in dangling:
            findings.append(Finding(
                f"CLAUDE.md:{line}",
                f"the rule “{headline}…” names `{dead}` as its enforcement and "
                f"that does not exist. A citation of a deleted guard reads as coverage, which "
                f"is worse than naming nothing.",
            ))
        # THE SENTINEL IS READ FIRST, AND THAT ORDER IS THE HONEST ONE. Several rules here
        # cite a mechanism that covers a PART of what they demand — the join's both-ways
        # report for "never silently drop a card", the stale-map ranking for a decision whose
        # premises have rotted. Counting those as mechanized would let the ceiling fall while
        # the operative demand stayed prose, which is the accounting this row exists to stop.
        if argued:
            prose_only.append(headline)
            if words < _ARGUMENT_MIN_WORDS:
                findings.append(Finding(
                    f"CLAUDE.md:{line}",
                    f"the rule “{headline}…” carries `{NOT_MECHANIZED}` with "
                    f"{words} words after it. Say what a machine would have to be able to SEE "
                    f"— at least {_ARGUMENT_MIN_WORDS} words — or the sentinel is a "
                    f"rubber stamp.",
                ))
            continue
        if resolves:
            continue
        findings.append(Finding(
            f"CLAUDE.md:{line}",
            f"the rule “{headline}…” names no mechanism and argues no exemption. "
            f"Name the `make` target, docs-audit row, hook or test that makes it fail — or "
            f"write `{NOT_MECHANIZED}` and say what a machine would have to be able to see.",
        ))

    if len(blocks) < HARD_RULE_FLOOR:
        findings.append(Finding(
            "CLAUDE.md",
            f"read {len(blocks)} hard rules where {HARD_RULE_FLOOR} are pinned. A rule was "
            f"deleted, or reworded past this reader. Lower `HARD_RULE_FLOOR` deliberately if "
            f"a rule genuinely went — never leave a shrinking reader printing `ok`.",
        ))
    if len(prose_only) != PROSE_ONLY_EXPECTED:
        if len(prose_only) > PROSE_ONLY_EXPECTED:
            what = (f"{len(prose_only)} hard rules argue their own unenforceability where "
                    f"{PROSE_ONLY_EXPECTED} are pinned: {', '.join(prose_only)[:200]}. Build the "
                    f"mechanism, or raise `PROSE_ONLY_EXPECTED` in the same commit and say why "
                    f"in the message.")
        else:
            what = (f"only {len(prose_only)} hard rules argue their own unenforceability where "
                    f"{PROSE_ONLY_EXPECTED} are pinned. If you BUILT a mechanism, lower the pin "
                    f"in this commit. If an admission was deleted, put it back — a rule that "
                    f"stops saying it is unenforced is not a rule that became enforced, and "
                    f"reading this in one direction only is what let a mutation arm delete one "
                    f"for free.")
        findings.append(Finding("CLAUDE.md", what))

    report.add(
        "rule enforcement",
        MECHANICAL,
        findings,
        f"{len(blocks)} hard rules: {len(blocks) - len(prose_only)} name a mechanism that "
        f"resolves, {len(prose_only)} argue why none can (pinned at {PROSE_ONLY_EXPECTED})",
        scanned=len(blocks),
    )


def _spelling_scope() -> Tuple[List[Path], bool]:
    """(paths to read, whole_tree) for `check_identifier_spelling`.

    Full mode (`core._INDEX_PATHS is None`) always reads the whole tree. Staged mode reads only
    the files THIS COMMIT TOUCHES (`_STAGED_PATHS`), unless the auditor itself (`scripts/docs-audit.py` or
    a file under `scripts/docs_audit/`) is staged — a changed fragment table or allow-list can make an untouched file's existing
    word newly non-compliant, or newly excused, so that case reads the whole tree too.
    """
    if core._INDEX_PATHS is None or any(
        entry == rel(SELF) or entry.startswith(rel(PACKAGE_DIR) + "/") for entry in _STAGED_PATHS
    ):
        return _walk(ROOT, SPELLING_SUFFIXES), True
    return (
        sorted(ROOT / entry for entry in _STAGED_PATHS
               if entry.endswith(SPELLING_SUFFIXES) and entry in core._INDEX_PATHS),
        False,
    )


def _spelling_markdown_files() -> Tuple[List[Path], bool]:
    """(markdown paths to read, whole_tree) for the markdown half of `check_identifier_
    spelling` (owner's ruling, test-audit plan, 2026-09-27).

    Full mode reads the whole tracked markdown tree. Staged mode reads ONLY the markdown
    THIS COMMIT TOUCHES — narrower than `_spelling_scope`'s code half on purpose, the
    owner's own words: "Staged mode reads only staged markdown." `docs/gates/` is excluded
    in every mode: its records are evidence of a real run, "never rewritten to match a later
    tree" (CLAUDE.md), so its prose is not this row's to flag.
    """
    if core._INDEX_PATHS is None:
        paths, whole_tree = markdown_files(), True
    else:
        paths = [ROOT / entry for entry in _STAGED_PATHS if entry.endswith(".md")]
        whole_tree = False
    return [p for p in paths if not rel(p).startswith(MARKDOWN_SPELLING_EXCLUDE)], whole_tree


def _markdown_spelling_found(paths: Sequence[Path]) -> Dict[str, Dict[str, List[str]]]:
    """list key -> {MARKDOWN_SPELLING_RULE: every British word found, once per occurrence}.

    A decision entry is keyed by its file tail (`ste_measure.list_key`), as the other two
    shrinking lists are, so a claim that renumbers it moves nothing.
    """
    ste_measure = _sibling("ste_measure.py")
    list_key = ste_measure.list_key if ste_measure is not None else (lambda path: path)
    found: Dict[str, Dict[str, List[str]]] = {}
    for path in paths:
        words = [british for _, _, british, _ in spelling_findings(read(path), ".md")]
        if words:
            found.setdefault(list_key(rel(path)), {}) \
                 .setdefault(MARKDOWN_SPELLING_RULE, []).extend(sorted(words))
    return found


def check_identifier_spelling(report: Report) -> None:
    """A name spelled British, anywhere a session might grep for its American twin — and, in
    markdown PROSE, a British word the shrinking list below does not already excuse.

    **CODE: blocking, on D16's test.** Under D60 as amended 2026-09-11 an identifier either
    carries a British fragment or it does not; there is nothing to judge. Comments and
    docstrings inside code are not read and are not governed — see the section comment above
    for why the ruling stopped there. **STAGED-SCOPED** (test-audit plan S2): see
    `_spelling_scope`.

    **MARKDOWN: a shrinking offender list** (owner's ruling, test-audit plan, 2026-09-27),
    `scripts/markdown-spelling-allow.json`, on D280's pattern: it fails on a British word the
    list does not name, a stale entry, and growth over the merge-base, so a new file starts
    clean. Fenced code, an inline code span and a single-asterisk italic quote are exempt
    (`_md_prose_only`), and `docs/gates/` is excluded outright. **STAGED-SCOPED, narrower
    than the code half**: see `_spelling_markdown_files` — a staged commit reads only the
    markdown it touches, and the diff compares only those same files against the list, so an
    untouched file's entries are never judged stale for having gone unscanned.

    **What it cannot see, by name.** A British word outside the fragment table (the -ise
    stems are a closed list); a name inside a template literal's `${}` (the whole literal is
    blanked); code a misjudged JSX tag blanks along with the text; and a markdown code span
    or italic quote that crosses a line break, read as prose on both sides of the break. Each
    of those is a miss, never a false finding, and `--self-test` proves the blanking in both
    directions.
    """
    findings: List[Finding] = []
    scanned = 0
    code_findings = 0

    paths, whole_tree = _spelling_scope()
    for path in paths:
        scanned += 1
        for line, name, british, american in spelling_findings(read(path), path.suffix):
            code_findings += 1
            findings.append(
                Finding(
                    f"{rel(path)}:{line}",
                    f"`{name}` carries the British `{british}`; D60 (amended 2026-09-11) "
                    f"spells every identifier American — `{american}`. A name that is "
                    f"stored or on the wire is not renamed: allow-list it by name in "
                    f"SPELLING_ALLOWED with the reason.",
                )
            )

    md_paths, md_whole_tree = _spelling_markdown_files()
    scanned += len(md_paths)
    found_md = _markdown_spelling_found(md_paths)
    list_rel = rel(MARKDOWN_SPELLING_ALLOW)
    document, unreadable = _read_offender_list(MARKDOWN_SPELLING_ALLOW)
    md_growth_note = ""
    if document is None:
        findings.append(Finding(
            list_rel,
            f"{unreadable}, so no British word in markdown can be told listed from new. "
            f"Restore the list from git.",
        ))
    else:
        listed_all, lanes, shape_errors = _offender_list_shape(document, {MARKDOWN_SPELLING_RULE})
        findings.extend(Finding(list_rel, error) for error in shape_errors)

        ste_measure = _sibling("ste_measure.py")
        list_key = ste_measure.list_key if ste_measure is not None else (lambda path: path)
        if md_whole_tree:
            listed_for_diff = listed_all
        else:
            scoped_keys = {list_key(rel(p)) for p in md_paths}
            listed_for_diff = {f: v for f, v in listed_all.items() if f in scoped_keys}

        unlisted, stale = _offender_diff(found_md, listed_for_diff)
        for file, _rule, word in unlisted:
            findings.append(Finding(
                file,
                f"types the British `{word}` in prose, and {list_rel} does not list it. "
                f"Rewrite the word American, or list it in {list_rel} for lane "
                f"{lanes.get(file, '?')!r} if it names something that cannot be renamed.",
            ))
        for file, _rule, word in stale:
            findings.append(Finding(
                f"{list_rel}: {file}",
                f"lists `{word}` for lane {lanes.get(file, '?')!r}, and {file} no longer "
                f"spells it that way. Delete the entry: the list only shrinks.",
            ))

        base_doc, where = _offender_list_at_merge_base(list_rel)
        if base_doc is None:
            md_growth_note = f" Only-shrinks not compared: {where}. Failing open."
        else:
            base_listed, _, _ = _offender_list_shape(base_doc, {MARKDOWN_SPELLING_RULE})
            refused, allowed = _offender_growth(
                base_listed, listed_all, {MARKDOWN_SPELLING_RULE}, {MARKDOWN_SPELLING_RULE},
            )
            for line in refused:
                findings.append(Finding(
                    list_rel, f"gained {line} over the merge-base {where}. Rewrite the word "
                              "instead of excusing it.",
                ))
            md_growth_note = f" Only-shrinks compared against the merge-base {where}."

    scope_note = "" if whole_tree else " (staged: only the files this commit touches)"
    md_scope_note = "" if md_whole_tree else " (staged: only the markdown this commit touches)"
    md_found_count = sum(len(es) for per in found_md.values() for es in per.values())
    code_summary = (f"{code_findings} British identifiers" if code_findings
                    else f"every identifier in {len(paths)} files is spelled American")
    report.add(
        "identifier spelling",
        MECHANICAL,
        findings,
        (f"code: {code_summary}{scope_note}; "
         f"markdown: {md_found_count} British word(s) over {len(md_paths)} files, all "
         f"listed{md_growth_note}{md_scope_note}"),
        scanned=scanned,
    )
