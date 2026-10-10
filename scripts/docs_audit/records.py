"""Decision, gate and debt records: ids, numbering, claims and structure."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from .core import (
    ADVISORY,
    Finding,
    MECHANICAL,
    ROOT,
    Report,
    _GATES_STEP_SLUG,
    _MERGE_BASE_REFERENCE,
    _STEP_SLUG,
    _sibling,
    _walk,
    exists,
    gates_text,
    git,
    python_files,
    read,
    rel,
)

# ---------------------------------------------------------------------- decision ids

# THE CAP IS SPELLED ONCE, BECAUSE IT WAS SPELLED SEVEN TIMES HERE AND NOBODY RECOUNTED IT.
# `[1-9][0-9]?` read decision ids for a year and went vacuous at the hundredth entry: a
# heading stops being a heading to this file and a citation stops being a citation, so
# `decision ids`, `decision ids in code`, `decision index`, `decision structure` and
# `id claims` all report GREEN over a file they can no longer see. docs/debts/ carried
# that as a triggered debt from 2026-08-30 until this landed; the trigger fired at the
# ninetieth entry and the file reached D92 before anyone discharged it. The entry is gone from
# that file rather than rewritten as closed — its own preamble sends closure narrative to git,
# and D140 carries what a reader needs.
#
# PROVED RATHER THAN ASSUMED, which is what the debt entry demanded and why it stayed open:
# a three-digit heading appended to docs/decisions/ left `decision ids` reporting 92 D
# headings over 93, `decision structure` reporting 92 entries over the same 93, `decision
# index` reporting "92 indexed, matching 92 headings" while that entry sat outside the index,
# and a dangling three-digit citation unreported. Four rows, all green, over a file none of
# them could read.
#
# THREE DIGITS AND NO FURTHER, deliberately. A four-digit id matches nothing here — the
# silent-widening failure is not fixed by making the bound infinite, it is fixed by the bound
# living in ONE place with a self-test case behind it. When the thousandth entry comes into
# view, this line is the edit and the cases below are what say so.
#
# A CEILING IN THIS PROSE IS SPELLED AS A WORD AND NEVER AS AN ID. `_DECISION_RE` scans this
# file, so "the hundredth entry" written the other way is a citation of an entry that does not
# exist and `decision ids in code` reports it. That is not hypothetical: D140's reopening
# condition opened with the id, invisibly, for as long as these patterns could not read three
# digits — and failed the audit the moment they could.
_ID_DIGITS = r"[1-9][0-9]{0,2}"

# AND AN ID IS A SLUG WHILE THE BRANCH THAT WRITES IT IS OPEN (D140, rewritten 2026-09-11).
# A number cannot be allocated on a branch, because the allocation's whole input — what main
# has taken — is not knowable until the merge. So a branch writes its heading as a slug and
# cites it that way, the shared merge tool substitutes the number at merge time, and the
# thirteen renumber events in this repo's history have no way to happen.
#
# NEVER NAME A LIVE SLUG IN A COMMENT OR A FIXTURE. The claim is exhaustive text replacement,
# so an illustration that borrows a real slug is rewritten with it — this block named one and
# came back reading "a branch writes `## D140`", and two self-test fixtures below became
# assertions about the number. Compose a fixture's ids from pieces; describe a shape in prose
# rather than spelling an id that exists.
#
# TWO SEGMENTS MINIMUM, AND THAT IS THE WHOLE OF WHAT KEEPS IT OUT OF PROSE. `D-pad` is one
# segment and is not an id; anything with an interior hyphen is. Measured over every `.md`, `.py`,
# `.ts`, `.tsx` and `.css` in this tree the day the vocabulary was chosen: ZERO tokens of
# either shape existed, so nothing had to be renamed to make room for it.
#
# LOWERCASE, because the letter is what says which namespace it is and a mixed-case slug
# would make two spellings of one slug into two ids for one entry with nothing to say so.
_ID_SLUG = r"-[a-z][a-z0-9]*(?:-[a-z0-9]+)+"
_ID_ANY = r"(?:" + _ID_DIGITS + r"|" + _ID_SLUG + r")"

_DECISION_RE = re.compile(r"\bD(" + _ID_ANY + r")\b")
_CODES_DECISION_RE = re.compile(r"\bC(" + _ID_ANY + r")\b")


def is_slug(identifier: str) -> bool:
    """True when `identifier` is an unclaimed slug rather than an allocated number.

    Takes the id WITHOUT its letter — `-merge-time-ids` or `137` — which is what every pattern
    here captures, and what `docs/map.py`'s `governed_by` and the build order both store.
    """
    return not str(identifier).lstrip("-").isdigit()

# A RUFF SUPPRESSION IS NOT A CITATION, AND AT THREE DIGITS IT LOOKS EXACTLY LIKE ONE.
# Three real lines carry a pydocstyle code whose number is three digits long —
# `server/tcg_export`, `server/order_transport` and `server/pipeline_routes` (one each)
# — and mccabe's complexity code joins them the moment anyone writes one. The two-digit cap
# could not reach their third digit, so widening it turns every one into a citation of an
# entry that does not exist. That is exactly why docs/debts/ kept the cap rather than
# fixing it, and why the widen could not land without this.
#
# MEASURED, NOT PREDICTED. With the cap at three and this strip disabled, `decision ids in
# code` reported all three as dangling citations and `repo map` — which is MECHANICAL —
# blocked the commit over four files.
#
# THE DIRECTIVE IS BLANKED, NEVER THE LINE. This repo writes prose after the codes, an
# em-dash and a sentence explaining the suppression, and that prose may cite an entry like
# any other comment. Dropping the whole line would trade a false positive for a blind spot,
# which is the trade this file exists to refuse.
#
# The code list follows ruff's own grammar: the bare directive, one code, or several
# separated by commas or spaces. It ends at the first token that is not a rule code, which
# is what leaves the em-dash prose readable. The directive is deliberately NOT spelled out
# in this comment — ruff parses one wherever it appears, including here, and warns that the
# surrounding prose is not a code list. The self-test below holds the literal forms, in
# string literals, where ruff does not look.
_NOQA_RE = re.compile(
    r"#\s*noqa(?::\s*[A-Za-z]+[0-9]+(?:[,\s]+[A-Za-z]+[0-9]+)*)?",
    re.IGNORECASE,
)


def without_noqa(line: str) -> str:
    """`line` with any ruff/flake8 suppression directive blanked out.

    A space rather than an empty string: nothing here reads column offsets, and a space
    cannot weld the tokens on either side of the directive into one.
    """
    return _NOQA_RE.sub(" ", line)


def decision_headings(path: Path, letter: str) -> Set[str]:
    return {found for found, _ in decision_heading_lines(path, letter)}


def decision_heading_lines(path: Path, letter: str) -> List[Tuple[str, int]]:
    """Every decision heading with the line it is on — a LIST, so duplicates survive.

    `decision_headings` above returns a set and is right to: its callers ask "does this id
    exist", and a set answers that. But a set is also how THREE identically numbered headings became one
    element and reached main with every row green — the count printed the number of DISTINCT
    ids, so it read 51 over a file holding 53 headings, and nothing anywhere compared the two.
    Three sessions each took "the next free number" against the same base and all three merged.

    So the list is the primitive and the set is derived from it, rather than the other way
    around. A reader that collapses its input cannot report on what it collapsed.
    """
    if not exists(path):
        return []
    pattern = re.compile(r"^##\s+(" + letter + _ID_ANY + r")\b")
    out: List[Tuple[str, int]] = []
    for number, line in enumerate(read(path).splitlines(), start=1):
        match = pattern.match(line)
        if match:
            out.append((match.group(1), number))
    return out


# ---------------------------------------------------------------- the corpus as a directory

# THE DECISION CORPUS IS `docs/decisions/`, ONE FILE PER ENTRY, and was one 1.4 MB file until
# the split. Every row below used to open `docs/decisions/`; they open the directory now and
# assert exactly what they asserted before. What changed for the better is WHERE a finding
# points: an over-budget entry names its own file and line 1, rather than an offset into a
# file nobody scrolls to.
#
# READ FAIL-OPEN, deliberately, and this matches `browser scope`'s rule. A missing module or
# manifest makes these rows report that they could not read the corpus, never that the corpus
# is empty — an empty roster would turn every citation in the tree into a dangling-id finding
# and bury the real cause under ten thousand lines.


def _corpus():
    """scripts/decisions_corpus.py, or None."""
    return _sibling("decisions_corpus.py")


def decision_files() -> List[Path]:
    """Every file holding a `## D<id>` entry, in corpus order. Empty if unreadable.

    THE COMPLEMENT, NOT `_ID_ANY`. A file is included the moment its first heading opens
    `## D` followed by a digit or a hyphen — never by first requiring the id to already be a
    clean number or a properly-shaped SLUG. `_ID_ANY` used to gate this list directly, which
    made a MALFORMED heading (mixed case, a doubled hyphen, a digit where a segment was
    meant) invisible a step earlier than the `id claims` row's own loose/strict check could
    ever see it: excluded here, that file never reaches the per-line scan that would have
    reported it as `not a claimable id`, and `decision structure`/`entry budget` silently
    drop it from their own counts too. A properly numbered or properly
    slugged heading still passes `_ID_ANY` downstream wherever that distinction matters;
    this list is only ever asked to be a superset of it.
    """
    corpus = _corpus()
    if corpus is None:
        return []
    try:
        head = re.compile(r"^##\s+D[0-9-]")
        return [p for p in corpus.files() if head.match(read(p).split("\n", 1)[0])]
    except Exception:
        return []


# AN EMPTY CORPUS IS A BROKEN CORPUS, NEVER A CLEAN ONE. This is the guard's own version of
# the failure it exists to catch: `decision structure` and `entry budget` iterate the entry
# files, so an unreadable directory gave them nothing to iterate and they reported `0 entries`
# in green. Measured by deleting one entry file — `decision ids` went red, and it passed
# over nothing while saying so in a sentence that reads like success. A row that cannot tell
# "nothing is wrong" from "nothing is known" is worse than no row, because it is believed.
_EMPTY_CORPUS = ("the decision corpus read as EMPTY. docs/decisions/ holds one file per "
                 "entry and its manifest is ORDER.json; a manifest naming a file that is "
                 "gone, an unreadable directory or a missing scripts/decisions_corpus.py all "
                 "arrive here. This row asserts nothing until that is fixed — which is why it "
                 "fails rather than passing over an empty set. `make decisions-selftest` says "
                 "which file.")


def corpus_is_empty(report: Report, label: str, severity: str) -> bool:
    """Report and return True when there are no entries to check."""
    if decision_files():
        return False
    report.add(label, severity, [Finding("docs/decisions/", _EMPTY_CORPUS)])
    return True


def decisions_text() -> str:
    """The corpus as the one document it used to be. Empty string if unreadable."""
    corpus = _corpus()
    if corpus is None:
        return ""
    try:
        return corpus.text()
    except Exception:
        return ""


def decision_heading_lines_across(paths: Iterable[Path], letter: str) -> List[Tuple[str, Path, int]]:
    """Every heading across several files, carrying the file it is in.

    THE FILE IS PART OF THE ANSWER NOW. One id in two files is the duplicate a directory
    newly permits and a single file never could, so the duplicate row below compares across
    the corpus rather than within one document.
    """
    pattern = re.compile(r"^##\s+(" + letter + _ID_ANY + r")\b")
    out: List[Tuple[str, Path, int]] = []
    for path in paths:
        if not exists(path):
            continue
        for number, line in enumerate(read(path).splitlines(), start=1):
            match = pattern.match(line)
            if match:
                out.append((match.group(1), path, number))
    return out


def decision_id_code_haystack() -> List[Path]:
    """Every non-markdown file `decision ids in code` reads for a D/C citation.

    ITS OWN FUNCTION, SO the claim self-test CAN CALL IT DIRECTLY, rather than
    retyping the suffix list this scan reads. The claimer's own walk once skipped every
    dotted directory (`.claude/skills/`), so a slug cited in
    `.claude/skills/text-density/SKILL.md` survived a claim commit unrewritten and this very
    row refused PR #462's merge over it (commits 34c54259/eaef7ce7) — `check_decision_ids`
    calling this function, and the claimer's self-test importing it too, is what keeps the
    two walks from drifting apart again the way `.js` already once did (see the paragraph
    below).
    """
    return python_files() + _walk(ROOT, (".ts", ".tsx", ".css", ".js"))


def check_decision_ids(report: Report, docs: List[Path]) -> None:
    singles = {i for i, _, _ in decision_heading_lines_across(decision_files(), "D")}
    codes = decision_headings(ROOT / "docs" / "specs" / "code-cards.md", "C")

    def scan(paths: Iterable[Path], severity_findings: List[Finding]) -> None:
        for path in paths:
            for number, raw in enumerate(read(path).splitlines(), start=1):
                # A suppression directive names a rule code, never an entry. See
                # `without_noqa` — the directive goes, the prose after it stays readable,
                # which is why this very sentence is still scanned for citations.
                line = without_noqa(raw)
                for digits in _DECISION_RE.findall(line):
                    if "D" + digits not in singles:
                        severity_findings.append(
                            Finding(
                                f"{rel(path)}:{number}",
                                f"cites D{digits}, which has no `## D{digits}` heading in "
                                f"docs/decisions/.",
                            )
                        )
                for digits in _CODES_DECISION_RE.findall(line):
                    if "C" + digits not in codes:
                        severity_findings.append(
                            Finding(
                                f"{rel(path)}:{number}",
                                f"cites C{digits}, which has no `## C{digits}` heading in "
                                f"docs/specs/code-cards.md.",
                            )
                        )

    in_docs: List[Finding] = []

    # AN ID IS UNIQUE, AND NOTHING ASSERTED THAT UNTIL 2026-08-30 (D16, amended). Three
    # entries in `docs/decisions/` carried ONE number, written by three sessions that each
    # took the next free id against the same base and all merged. Every row here stayed green
    # throughout, because the count above is over a SET: it printed a distinct-id total for a
    # file holding more headings than that, and the citation scan below is satisfied by a
    # heading EXISTING, never by exactly one existing. D16 carries the incident.
    #
    # WHAT A DUPLICATE COSTS is worse than an untidy file. `governed_by` in `docs/map.py`, the
    # decision-context hook and every id in a comment all resolve to an ENTRY, and
    # with three candidates they resolve to whichever a reader happens to find first. The
    # citation is then not wrong in a way anything can see — it points at a real heading, just
    # not the intended one.
    #
    # BLOCKING, because there is no judgement in it: two headings carrying one id is provably
    # wrong however the file got that way, which is D16's own test for mechanical.
    # ACROSS THE CORPUS, not within one file. The split made `docs/decisions/` a directory,
    # so the duplicate this has to catch is now two FILES both declaring one id — which the
    # old within-a-file comparison could not see at all, and which a directory makes easy to
    # create by copying an entry rather than moving it.
    for paths, letter in (
        (decision_files(), "D"),
        ([ROOT / "docs" / "specs" / "code-cards.md"], "C"),
    ):
        seen: Dict[str, List[Tuple[Path, int]]] = {}
        for found, path, number in decision_heading_lines_across(paths, letter):
            seen.setdefault(found, []).append((path, number))
        for found, sites in sorted(seen.items()):
            if len(sites) > 1:
                where = ", ".join(f"{rel(q)}:{n}" for q, n in sites)
                in_docs.append(
                    Finding(
                        f"{rel(sites[0][0])}:{sites[0][1]}",
                        f"`## {found}` appears {len(sites)} times — {where}. An id "
                        f"names one entry: `governed_by`, the decision-context hook and every "
                        f"`({found})` in a comment resolve to whichever heading is found "
                        f"first. Renumber all but one, and every reference to them.",
                    )
                )

    scan(docs, in_docs)
    in_code: List[Finding] = []
    # THE APP WAS NOT SCANNED AT ALL UNTIL 2026-08-30 (D140). `python_files()` is every `.py`
    # in the tree, and the row below said "citations in .py all resolve" — accurately, and
    # over half the citations. `app/` holds hundreds more in `.ts`, `.tsx` and `.css`
    # comments, and a dangling id in one of them resolved to nothing and was reported by
    # nothing. Same severity as the Python row and for the same reason: `D2` could plausibly
    # be a variable, and a false positive that blocks a commit is worse than a printed line.
    # `.js` JOINED THEM ON 2026-09-11, the same way `.ts` did on 2026-08-30 and for the same
    # reason: it was the one real extension in this tree that cites decisions and nothing
    # opened it. `app/eslint.config.js` alone carries six of them, every one valid — so this
    # widen reports nothing today, which is the point. What it would have caught is what a
    # branch found by hand the day the shared merge tool landed: that file was outside the
    # CLAIMER's suffix set too, so a SLUG written there survived the merge and became a
    # citation of an entry that had just been given a number. Both sets gained `.js` together.
    #
    # ONE HAYSTACK, BUILT BEFORE THE SCAN, so the row can declare how many files it read.
    # It was two `scan()` calls with the count nowhere, which is the shape that let this
    # file print `ok` over a walk that had found nothing.
    code_haystack = decision_id_code_haystack()
    scan(code_haystack, in_code)

    # `decision ids in code` folded into this row by the owner's ruling (test-audit-
    # 2026-09-27, row 15 into row 14, "as one blocking row"): a dangling `D<n>` in code used
    # to be ADVISORY on its own (a false positive that blocks a commit is worse than one
    # that prints a line), but the docs-side half of this same function was always
    # MECHANICAL, and one row can carry only one severity — so the merge is BLOCKING now,
    # on the owner's own word rather than by an automatic worst-of-both computation.
    report.add("decision ids", MECHANICAL, in_docs + in_code,
               f"{len(singles)} D + {len(codes)} C headings; citations in .py, .ts, .tsx, "
               f".css and .js all resolve",
               scanned=len(singles) + len(codes) + len(code_haystack))


# `gates structure` is CUT (owner ruling, test-audit TIERS row 48,
# 2026-09-28): gating is retired, and `make gates-selftest` already proves the corpus
# complete from the split side.



# ------------------------------------------------------------------ ids are claimed at merge

# A BRANCH DOES NOT TAKE A NUMBER (D140). The allocation's only input is what main
# has taken, and a branch cannot have that: every renumber in this repo's history is one
# branch reading `origin/main`, taking the next free id, and being wrong the moment another
# branch merged first. Thirteen of those are recorded in D140, and D16 carries three entries
# numbered `## D50` at once. So a branch writes a SLUG and the shared merge tool substitutes
# the number inside `make merge`, against main as it stands then.
#
# THIS ROW REPLACED `renumbered ids` AND `vacated ids`, WHICH ARE DELETED. Both existed to
# repair a renumber — the first named every site and blocked none of them, the second blocked
# the half that was provably the branch's own line. A branch that never takes a number never
# vacates one, so both guarded a path that no longer exists. D140 keeps its account of the
# incidents, which is evidence and is not rewritten to match a later tree; what it stops being
# is a live mechanism.
#
# WHAT THIS ROW CHECKS IS FOUR THINGS, AND THE LAST IS THE ONE THE DESIGN RESTS ON:
#
#   1. a cited slug resolves to a slug heading   — the existence check numbers already get
#   2. a slug heading's id is unique             — D16's duplicate rule, in the new namespace
#   3. a slug is well-formed                     — two lowercase segments, never one
#   4. MAIN CARRIES NO SLUG                      — the invariant
#
# The fourth is the only one that catches a claim that HALF-LANDED, and it is checkable
# exactly where it matters: `check.yml` runs this on main after every merge. On a branch it is
# silent, because a slug on a branch is the ordinary state and the whole point.


# A HEADING THE ID PATTERN REJECTS IS AN ENTRY NOTHING CAN SEE, which is the failure mode a
# new namespace brings with it: `## D-pad — Title` is one segment, so it is not an id, so the
# heading is not an entry, so no row reports on it and no citation of it resolves. Caught by
# reading the heading line as TEXT and asking the pattern afterwards.
_LOOSE_SLUG_HEADING = re.compile(r"^##\s+([DC]-\S+)")
_STRICT_SLUG_HEADING = re.compile(r"^##\s+[DC]" + _ID_SLUG + r"\b")
# DEBT'S OWN PAIR, ONE WORD OVER: `docs/debts/` joined the claim path (D140's scheme, the
# owner's word), so a pending debt slug carries the identical malformed-heading risk one
# letter's worth wider — `## DEBT-pad` is one segment and would be silently invisible to
# the shared merge tool the same way `## D-pad` already is.
_LOOSE_SLUG_HEADING_DEBT = re.compile(r"^##\s+(DEBT-\S+)")
_STRICT_SLUG_HEADING_DEBT = re.compile(r"^##\s+DEBT" + _ID_SLUG + r"\b")
# NOT `\bstep `: a hyphen is a non-word character, so `\b` fires INSIDE `runs-step` and
# a React className pairing two such words reads as a citation of the second one.
# Measured on `app/src/RunPanel.tsx`, which is the only such pair in the tree and was
# enough to make this row wrong on its first run.
_STEP_CITATION = re.compile(r"(?<![-\w])step (" + _STEP_SLUG + r")\b")


def is_main(ref_name: str, named: str, head: str, origin_main: str) -> bool:
    """Whether a checkout described by these four readings IS main.

    PURE, SO `--self-test` CAN DRIVE IT, and that is the point rather than a convenience: this
    decision needs a repository in three different states to be wrong in, so for as long as it
    was welded to `git` nothing could ask it anything and it was wrong for exactly that long.

    Three readings, because the answer has to be right in a CI runner as well as on the rig
    and they fail differently: a runner checks out a DETACHED head so there is no branch name,
    a worktree commonly has no local `main` at all (D42's merge discipline keeps it checked
    out elsewhere), and `GITHUB_REF_NAME` exists only in Actions.

    COMMIT EQUALITY IS THE DETACHED-HEAD RULE AND NOTHING ELSE. A NAMED
    branch is not main however recently it was cut, and this is where a false YES came from: a
    branch cut from main and not yet committed to sits AT origin/main, so equality called it
    main. `id claims` then refused its FIRST commit — the one commit that introduces the slug —
    telling a session that main carried an unclaimed id and sending it to repair main. D140's
    workflow was unusable on a fresh branch, and it was found by doing exactly that.
    `--abbrev-ref` prints the literal `HEAD` when detached, so that is the test.
    """
    if ref_name == "main":
        return True
    if named == "main":
        return True
    if named and named != "HEAD":
        return False
    return bool(head) and head == origin_main


def on_main() -> bool:
    """`is_main` over this checkout's own four readings."""
    return is_main(
        os.environ.get("GITHUB_REF_NAME") or "",
        git("rev-parse", "--abbrev-ref", "HEAD").strip(),
        git("rev-parse", "HEAD").strip(),
        git("rev-parse", "origin/main").strip(),
    )


def check_id_claims(report: Report) -> None:
    findings: List[Finding] = []
    codes = ROOT / "docs" / "specs" / "code-cards.md"

    unclaimed: List[str] = []
    debt_corpus = _debts_corpus()
    debt_files = debt_corpus.files() if debt_corpus is not None else []
    for paths, loose_re, strict_re in (
        (decision_files() + [codes], _LOOSE_SLUG_HEADING, _STRICT_SLUG_HEADING),
        (debt_files, _LOOSE_SLUG_HEADING_DEBT, _STRICT_SLUG_HEADING_DEBT),
    ):
        for path in paths:
            if not exists(path):
                continue
            for number, line in enumerate(read(path).splitlines(), start=1):
                loose = loose_re.match(line)
                if not loose:
                    continue
                if not strict_re.match(line):
                    findings.append(Finding(
                        f"{rel(path)}:{number}",
                        f"`{loose.group(1)}` is not a claimable id, so this heading is not an "
                        f"entry: no row reports on it, no citation of it resolves, and "
                        f"the merge tool will not allocate it a number. A slug is two or "
                        f"more lowercase segments, never one — `D-pad` is prose.",
                    ))
                    continue
                unclaimed.append(loose.group(1))

    # A STEP IS CITED BY A SLUG THAT SOME `0.` MARKER DECLARES, or it is a dangling id — the
    # same superset rule the letter namespaces get from `decision ids`, which cannot see this
    # one because a step wears no letter.
    declared_steps = set(_GATES_STEP_SLUG.findall(gates_text()))
    for path in sorted(set(python_files()) | set(_walk(ROOT, (".md", ".ts", ".tsx")))):
        for number, raw in enumerate(read(path).splitlines(), start=1):
            for slug in _STEP_CITATION.findall(without_noqa(raw)):
                if slug not in declared_steps:
                    findings.append(Finding(
                        f"{rel(path)}:{number}",
                        f"cites `step {slug}`, which no `0.` marker in docs/GATES.md "
                        f"declares. An unclaimed step is written "
                        f"``0. `step {slug}` **Title** — ...`` there and in docs/map.py's "
                        f"build order, or it is a citation of nothing.",
                    ))
    unclaimed.extend(f"step {slug}" for slug in sorted(declared_steps))

    # AND MAIN CARRIES NONE. This is the invariant the whole design rests on: a slug that
    # reaches main is a claim that half-landed, and every citation of it now resolves to
    # nothing rather than to the wrong entry — loud, but only if something looks. `check.yml`
    # runs this on main after every merge, which is the one place and moment it can look.
    if on_main() and unclaimed:
        findings.append(Finding(
            "docs/decisions/ or docs/debts/",
            "main carries {0} unclaimed id: {1}.\n"
            "  A slug is a branch's placeholder and `make merge` is what turns it into a "
            "number (D140). One on main means a claim half-landed — every "
            "citation of it now resolves to nothing.\n"
            "  Repair: a pull request off main, merged through `make merge`, which claims "
            "every pending record.".format(
                len(unclaimed), ", ".join(f"`{name}`" for name in unclaimed)),
        ))

    where = "main" if on_main() else "this branch"
    report.add("id claims", MECHANICAL, findings,
               scanned=len(unclaimed),
               summary="{0} unclaimed id(s) on {1}{2}".format(
                   len(unclaimed), where,
                   ", claimed at the merge" if unclaimed and not on_main() else ""))


# ---------------------------------------------- a numbered record is claimed at merge, never by hand

# `id claims` ABOVE CATCHES A MALFORMED SLUG. It says nothing about a branch that skips the
# slug entirely and writes the number itself — a `docs/decisions/D<n>-*.md` or
# `docs/debts/<n>-*.md` file with a real number in its own name, D140's exact violation
# ("never allocate a numbered record on a branch. Write a slug. Claim the number at merge.").
# That is how a debt entry once collided: lane B2 added
# `docs/debts/048-...md` straight, and the shared merge tool independently planned the
# SAME number for a pending slug.
#
# THE SANCTIONED CLAIM IS ALSO A NUMBERED FILE APPEARING, and the first version of this row
# could not tell the two apart: the shared merge tool's claim step runs the claimer
# (the claimer's rename — a plain filesystem rename, no `git mv`), `git add -A`, then a
# commit through this very pre-commit hook, and that FIRST commit refused itself. So the
# question is never "is a numbered file new", it is "did a slug become this exact file" —
# and git already answers that for free: `--name-status -M` reports a content rename
# (`R<score>`, both paths) wherever a deleted slug file and an added numbered file are
# similar enough, which the claimer's rename's output always is — only the heading line
# and the filename change. `_sanctioned_rename` checks the one thing worth checking beyond
# that: the DESCRIPTIVE TAIL survives unchanged (`D-<tail>.md` -> `D<n>-<tail>.md`,
# `DEBT-<tail>.md` -> `<n>-<tail>.md`), the exact shape the claimer's rename writes.
#
# THE COMPARISON IS SCOPED TO WHAT THIS PASS ACTUALLY DECIDES, never the whole branch
# against `origin/main`: in `--staged` mode that is `git diff --cached`, this commit's own
# change — the shape the pre-commit hook checks, and the reason a claim commit does not
# re-litigate every EARLIER commit's already-sanctioned rename on every commit after it. In
# a full run it is the branch's history since the merge-base, the same question asked over
# every commit at once (a rename mid-history still reads as one `R` between two trees).
# FAILS OPEN exactly like `only_shrinks.list_at_merge_base`: no merge-base scans nothing and
# says so, rather than refusing every numbered file in a tree with no `origin/main` to
# compare against.
_NUMBERED_DECISION_FILE = re.compile(r"^D[0-9]+-")
_NUMBERED_DEBT_FILE = re.compile(r"^[0-9]+-")
_SLUG_SOURCE_DECISION = re.compile(r"^D-(.+)$")
_NUMBERED_TAIL_DECISION = re.compile(r"^D[0-9]+-(.+)$")
_SLUG_SOURCE_DEBT = re.compile(r"^DEBT-(.+)$")
_NUMBERED_TAIL_DEBT = re.compile(r"^[0-9]+-(.+)$")


_NUMBER_OF_DECISION = re.compile(r"^D([0-9]+)-")
_NUMBER_OF_DEBT = re.compile(r"^([0-9]+)-")


def _sanctioned_rename(old_name: str, new_name: str, kind: str,
                       held: Optional[Set[str]] = None) -> bool:
    """Whether `old_name -> new_name` allocates no number: either the claimer's
    OWN rename (the unclaimed slug file becoming the numbered file
    with the IDENTICAL descriptive tail), or a RETITLE, the same number under a new
    descriptive tail. A retitle is sanctioned only when the base already holds that number
    (`held`), so adding a new numbered file and then renaming it is still an allocation.
    """
    slug_re, numbered_re = (
        (_SLUG_SOURCE_DECISION, _NUMBERED_TAIL_DECISION) if kind == "decision"
        else (_SLUG_SOURCE_DEBT, _NUMBERED_TAIL_DEBT)
    )
    slug_match = slug_re.match(old_name)
    numbered_match = numbered_re.match(new_name)
    if slug_match and numbered_match and slug_match.group(1) == numbered_match.group(1):
        return True
    number_re = _NUMBER_OF_DECISION if kind == "decision" else _NUMBER_OF_DEBT
    old_number, new_number = number_re.match(old_name), number_re.match(new_name)
    return bool(old_number and new_number and old_number.group(1) == new_number.group(1)
                and held is not None and old_number.group(1) in held.get(kind, set()))


# A LOW THRESHOLD ON PURPOSE. `-M`'s default (50%) misses a genuine rename over a SHORT
# entry: a two-line slug file becoming a two-line numbered file can measure well under 50%
# similar by git's own heuristic (measured: 7% on a real claim, over a fixture-sized debt
# entry), and that read as a plain add-plus-delete — the exact shape the merge tool's claim step
# produces for a short entry, and the exact shape that refused its OWN claim commit before
# this fix. Correctness never comes from the threshold: `_sanctioned_rename` below still
# demands the EXACT descriptive tail on both sides, so a low threshold only widens which
# pairs git offers as CANDIDATES — it cannot turn an unrelated pair into a false pass.
_RENAME_THRESHOLD = "-M5%"


def _rename_pairs(diff_text: str) -> List[Tuple[str, str]]:
    """Every `(old_path, new_path)` a `--name-status` diff (run with `_RENAME_THRESHOLD`)
    reports as a detected rename or copy."""
    pairs: List[Tuple[str, str]] = []
    for line in diff_text.splitlines():
        if not line:
            continue
        fields = line.split("\t")
        if fields[0][:1] in ("R", "C") and len(fields) == 3:
            pairs.append((fields[1], fields[2]))
    return pairs


def _held_numbers(ref: str) -> Dict[str, Set[str]]:
    """The numbers of the numbered decision and debt files `ref` already holds."""
    held: Dict[str, Set[str]] = {"decision": set(), "debt": set()}
    for directory, kind, number_re in (
        ("docs/decisions", "decision", _NUMBER_OF_DECISION), ("docs/debts", "debt", _NUMBER_OF_DEBT),
    ):
        for path in git("ls-tree", "-r", "--name-only", ref, "--", directory).splitlines():
            match = number_re.match(Path(path).name)
            if match:
                held[kind].add(match.group(1))
    return held


def _sanctioned_new_paths(diff_texts: Iterable[str],
                          held: Optional[Dict[str, Set[str]]] = None) -> Set[str]:
    """Every numbered file path that is the SANCTIONED rename's destination in any one of
    `diff_texts` — one diff per commit in range, never one diff across the whole range.

    A TWO-ENDPOINT DIFF CANNOT SEE A RENAME WHOSE SOURCE NEVER EXISTED AT EITHER ENDPOINT.
    A slug added in one commit and claimed (renamed) in a LATER one is invisible to
    `git diff <merge-base> <HEAD>` alone: the slug file is in NEITHER tree, so there is
    nothing for git to call deleted, and the numbered file reads as a plain add — a false
    positive this row would raise on every legitimately claimed entry, on every `make check`
    run on the branch, from the commit after the claim until the branch merges. Each commit
    diffed against its own parent sees the rename where it actually happened.
    """
    sanctioned: Set[str] = set()
    for diff_text in diff_texts:
        for old_path, new_path in _rename_pairs(diff_text):
            for directory, kind in (
                ("docs/decisions/", "decision"), ("docs/debts/", "debt"),
            ):
                if old_path.startswith(directory) and new_path.startswith(directory):
                    old_name = old_path[len(directory):]
                    new_name = new_path[len(directory):]
                    if _sanctioned_rename(old_name, new_name, kind, held):
                        sanctioned.add(new_path)
        # A RETITLE WITH HEAVY CONTENT CHANGE reads as `D old` + `A new`, never `R`, once it
        # falls under the similarity floor. The number identifies the record: an added file
        # whose number the base holds, with a file of that number deleted in this same diff,
        # allocates nothing. EXACTLY one delete and one add of the number: two adds would hand
        # one number to two records.
        deleted_numbers: List[Tuple[str, str]] = []
        added: List[Tuple[str, str, str]] = []
        for line in diff_text.splitlines():
            fields = line.split("\t")
            if len(fields) != 2 or fields[0] not in ("A", "D"):
                continue
            for directory, kind, number_re in (
                ("docs/decisions/", "decision", _NUMBER_OF_DECISION),
                ("docs/debts/", "debt", _NUMBER_OF_DEBT),
            ):
                if fields[1].startswith(directory):
                    match = number_re.match(fields[1][len(directory):])
                    if match and fields[0] == "D":
                        deleted_numbers.append((kind, match.group(1)))
                    elif match:
                        added.append((kind, match.group(1), fields[1]))
        for kind, number, path in added:
            if ((deleted_numbers.count((kind, number)) == 1
                    and sum(1 for k, n, _ in added if (k, n) == (kind, number)) == 1)
                    and held is not None
                    and number in held.get(kind, set())):
                sanctioned.add(path)
    return sanctioned


def _added_or_renamed_paths(diff_texts: Iterable[str]) -> Set[str]:
    """Every path that is the destination of an ADD, RENAME or COPY in any of `diff_texts` —
    never a plain edit (`M`) of a file that already existed. A claimed entry's PROSE keeps
    changing after it is claimed — every later citation of its slug is exhaustively
    rewritten too (`apply_to_text`) — and reading that as growth is the false positive this
    function exists to rule out: an already-numbered decision or debt, edited for any
    ordinary reason, is not a hand-allocated number just because a numbered filename also
    matches this commit's diff.
    """
    paths: Set[str] = set()
    for diff_text in diff_texts:
        for line in diff_text.splitlines():
            if not line:
                continue
            fields = line.split("\t")
            if fields[0][:1] not in ("A", "R", "C"):
                continue
            paths.add(fields[-1])
    return paths


def _is_main_ancestor(commit: str) -> bool:
    """`git merge-base --is-ancestor <commit> origin/main`: exit 0 is True. Exit 1 is False.
    Any other exit, or no git, is also False, because the caller excuses on True only, so an
    unreadable `origin/main` leaves the numbers unexcused and the row red (`git()` above would
    read the failure as empty, which is the same here but not by name)."""
    try:
        done = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, _MERGE_BASE_REFERENCE],
            cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except OSError:
        return False
    return done.returncode == 0


def _names_from_main(parents: Iterable[str], directory: str) -> Tuple[Set[str], Set[str]]:
    """`(excused, stale)`: the file names under `directory` that the merged-in `parents` hold.
    THE ONE EXCUSAL, read by the staged merge only: a full run needs none, because the
    merge-base with `origin/main` already holds every main-ancestor parent's names. A parent that is an ancestor of `origin/main` excuses
    its names (main's own numbers); any other parent (a feature branch, a PR head, or local
    main ahead of a stale `origin/main`) excuses nothing, and the names `origin/main` lacks
    come back as `stale` so a refusal can say where they came from. An unreadable ref is "not an ancestor"."""
    excused: Set[str] = set()
    stale: Set[str] = set()
    main_held = {Path(p).name for p in
                 git("ls-tree", "-r", "--name-only", _MERGE_BASE_REFERENCE, "--", directory).splitlines()}
    for parent in parents:
        held = {Path(p).name for p in
                git("ls-tree", "-r", "--name-only", parent, "--", directory).splitlines()}
        if _is_main_ancestor(parent):
            excused |= held
        else:
            stale |= held - main_held
    return excused, stale


def check_numbered_record_growth(report: Report, staged_only: bool) -> None:
    findings: List[Finding] = []
    dirs = ["docs/decisions", "docs/debts"]
    stale_paths: Set[str] = set()

    if staged_only:
        # THIS COMMIT'S OWN CHANGE, AND NOTHING EARLIER — exactly what the pre-commit hook
        # decides, and exactly why an earlier, already-sanctioned claim on this same branch
        # is never re-litigated on every commit after it.
        cached_diff = git("diff", _RENAME_THRESHOLD, "--cached", "--name-status", "--", *dirs)
        sanctioned = _sanctioned_new_paths([cached_diff], _held_numbers("HEAD"))
        candidates = _added_or_renamed_paths([cached_diff])
        where = "the staged diff"
        # A MERGE IN PROGRESS stages every number the other side brought as an add against
        # HEAD (the first parent). Main's own are not this branch's.
        merge_head = git("rev-parse", "-q", "--verify", "MERGE_HEAD").strip()
        if merge_head:
            for directory in dirs:
                excused, stale = _names_from_main([merge_head], directory)
                candidates -= {f"{directory}/{n}" for n in excused}
                stale_paths.update(f"{directory}/{n}" for n in stale)
    else:
        base = git("merge-base", _MERGE_BASE_REFERENCE, "HEAD").strip()
        if not base:
            report.add("numbered record growth", MECHANICAL, findings, scanned=0,
                        summary="no merge-base with origin/main — fails open, nothing checked")
            return
        # ONE DIFF PER COMMIT IN RANGE, so a rename lands in the one step that actually made
        # it, plus one trailing diff for whatever is uncommitted (HEAD vs the working tree) —
        # `check_numbered_record_growth` runs in a full pass over the disk, same as every
        # other full-mode row, so an uncommitted the merge tool's claim still reads clean.
        commits = [c for c in git("rev-list", "--reverse", f"{base}..HEAD").splitlines() if c]
        chain = [base] + commits
        diff_texts = [
            git("diff", _RENAME_THRESHOLD, "--name-status", chain[i], chain[i + 1], "--", *dirs)
            for i in range(len(chain) - 1)
        ]
        diff_texts.append(git("diff", _RENAME_THRESHOLD, "--name-status", "HEAD", "--", *dirs))
        sanctioned = _sanctioned_new_paths(diff_texts, _held_numbers(base))
        candidates = set()
        for directory in dirs:
            dirpath = ROOT / directory
            if not dirpath.is_dir():
                continue
            base_names = set(
                Path(p).name for p in
                git("ls-tree", "-r", "--name-only", base, "--", directory).splitlines()
            )
            for path in sorted(dirpath.glob("*.md")):
                if path.name not in base_names:
                    candidates.add(f"{directory}/{path.name}")
        where = f"the branch's history since {base[:9]}"

    scanned = 0
    for directory, pattern, kind in (
        ("docs/decisions", _NUMBERED_DECISION_FILE, "decision"),
        ("docs/debts", _NUMBERED_DEBT_FILE, "debt"),
    ):
        prefix = directory + "/"
        for new_path in sorted(candidates):
            if not new_path.startswith(prefix) or not new_path.endswith(".md"):
                continue
            new_name = new_path[len(prefix):]
            if not pattern.match(new_name):
                continue
            scanned += 1
            if new_path in sanctioned:
                continue
            remedy = (
                " It is in the merged-in commit, which `origin/main` does not yet contain: if "
                "that commit is main's, fetch main (`git fetch origin main`), then commit again."
                if new_path in stale_paths else "")
            findings.append(Finding(
                new_path,
                f"is a NUMBERED {kind} record with no matching slug rename behind it (D140). "
                f"A branch never allocates a number by hand — write a slug instead and "
                f"the merge tool claims the number at the merge, which git sees as a "
                f"RENAME from the slug file with the same descriptive tail." + remedy,
            ))
    report.add("numbered record growth", MECHANICAL, findings,
               scanned=scanned,
               summary=f"{len(findings)} unsanctioned numbered record(s) over {where}, "
                       f"{scanned} numbered file(s) changed there")


# --------------------------------------------------- the claimer speaks the same vocabulary

# TWO DECLARATIONS AND A READER, this repo's standing answer to a shape it keeps meeting.
# The shared merge tool reads its slug grammar from `.github/stamp.json`'s `slugRegex`, and this
# auditor writes it again as `_STEP_SLUG`, so the two are reconciled. A widen that reaches one of
# them leaves the other refusing an id the first just allocated, which is silent in both
# directions.

CLAIMER = ROOT / ".github" / "stamp.json"


def check_claim_vocabulary(report: Report) -> None:
    findings: List[Finding] = []
    if not exists(CLAIMER):
        report.add("claim vocabulary", MECHANICAL,
                   [Finding(rel(CLAIMER), "does not exist, so no branch can claim an id.")])
        return
    try:
        theirs = json.loads(CLAIMER.read_text(encoding="utf-8")).get("slugRegex")
    except ValueError:
        theirs = None
    # `_ID_SLUG` is the same grammar with the leading hyphen that separates it from the
    # letter; `_STEP_SLUG` is it bare, because a step wears no letter.
    if theirs != _STEP_SLUG:
        findings.append(Finding(
            rel(CLAIMER),
            "declares slugRegex as {0!r}; scripts/docs-audit.py's `_STEP_SLUG` is {1!r}.\n"
            "  The auditor decides what is an id and the merge tool decides what gets a number. "
            "Disagreeing, one of them refuses an id the other just allocated.".format(
                theirs, _STEP_SLUG)))
    elif _ID_SLUG != "-" + _STEP_SLUG:
        findings.append(Finding(
            "scripts/docs-audit.py",
            "`_ID_SLUG` is not `_STEP_SLUG` with the separating hyphen in front of it: "
            "{0!r} against {1!r}.".format(_ID_SLUG, _STEP_SLUG)))
    report.add("claim vocabulary", MECHANICAL, findings,
               "one slug grammar, declared in the auditor and in the merge tool's config",
               scanned=2)


# ------------------------------------------------------------------------- env vars

_ENV_RE = re.compile(r"\b(BANCHI_[A-Z0-9_]+|POKEMONTCG_API_KEY|ANTHROPIC_API_KEY)\b")


def _prose_guard():
    """scripts/prose-guard.py, or None."""
    return _sibling("prose-guard.py")


def check_decision_structure(report: Report) -> None:
    """What scripts/decision-context.py needs, which it cannot report for itself.

    That hook is wrapped in `except Exception: sys.exit(0)`, so a heading that loses its
    dash separator or a `**bold**` reflowed across a wrap degrades it in silence. Measured
    before D60: 270 bold runs — 20% of all 1,318 — were invisible to it, and seven entries
    surfaced nothing but their title, with every row of this audit green throughout.

    MECHANICAL, because each finding is provably wrong rather than a judgement: the hook's
    regex either matches or it does not.
    """
    guard = _prose_guard()
    if guard is None:
        report.add("decision structure", ADVISORY,
                   [Finding("scripts/prose-guard.py", "not readable; structure unchecked.")])
        return
    if corpus_is_empty(report, "decision structure", MECHANICAL):
        return
    findings = [Finding(f.where, f.message)
                for target in decision_files() for f in guard.check_structure(target)]
    entries = [e for target in decision_files() for e in guard.entries(read(target))]
    report.add("decision structure", MECHANICAL, findings,
               f"{len(entries)} entries, every heading and bold reaches the hook",
               scanned=len(entries))


# A decision file's slug is the part after `D<n>-` and before `.md`. The owner's ruling caps
# it at 32 characters, the same cap a branch's unclaimed slug carries.
MAX_DECISION_SLUG = 32
_DECISION_FILE_RE = re.compile(r"^D\d+-(.+)\.md$")


def long_decision_slugs(names: Iterable[str]) -> List[Tuple[str, int]]:
    """(file name, slug length) for each decision file name whose slug is over the cap."""
    out: List[Tuple[str, int]] = []
    for name in names:
        match = _DECISION_FILE_RE.match(name)
        if match and len(match.group(1)) > MAX_DECISION_SLUG:
            out.append((name, len(match.group(1))))
    return out


def check_decision_slug_length(report: Report) -> None:
    if corpus_is_empty(report, "decision slug length", MECHANICAL):
        return
    files = decision_files()
    findings = [Finding(rel(p), f"slug is {n} characters; the cap is {MAX_DECISION_SLUG}. "
                                "Rename the file with a shorter slug and keep its D<n>- prefix.")
                for p in files for (_, n) in long_decision_slugs([p.name])]
    report.add("decision slug length", MECHANICAL, findings,
               f"{len(files)} decision files, every slug at most {MAX_DECISION_SLUG} characters",
               scanned=len(files))


# THE DEBT TWIN OF THE (RETIRED) DECISION-SIDE EXEMPTION, ONE LETTER OVER. `docs/debts/`
# joined D140's claim path (the owner's word), so a debt's own unclaimed slug
# (`DEBT-<slug>`) is exempt from "must appear in the index" for the identical reason a
# decision's used to be, before CLAUDE.md's decision index was retired (D60 amended) —
# `make map ARGS=--decisions` renders that one now, off the corpus directly, so there is no
# stub left for a decision-side exemption to guard.
_ID_UNCLAIMED_DEBT_RE = re.compile(r"^DEBT" + _ID_SLUG + r"$")


def _is_unclaimed_debt(ident: str) -> bool:
    return bool(_ID_UNCLAIMED_DEBT_RE.match(ident))


def _decision_index_findings(
    want: List[Tuple[str, str]], got: List[Tuple[str, str]],
    is_unclaimed: Callable[[str], bool], doc: str,
    empty_message: str = "no index found.",
) -> List[Finding]:
    """The comparison itself, pure so `--self-test` can drive it without a filesystem.

    `want` is every heading in the corpus, in manifest order; `got` is what `doc`'s fenced
    index block currently lists. An id absent from `got` is only ever tolerated when
    `is_unclaimed` says so — everything else that used to fail here still fails exactly the
    same way.

    ONE CALLER LEFT: `check_debt_index`, with `_is_unclaimed_debt` and `docs/debts/`. The
    decision-side twin this was built beside (`check_decision_index`, `_is_unclaimed`) is
    retired along with CLAUDE.md's decision index (D60 amended) — `make map
    ARGS=--decisions` renders that list off the corpus now, and a rendered view has nothing
    to drift, so there is no decision-side row left to reuse this comparison.
    """
    findings: List[Finding] = []
    if not got:
        findings.append(Finding(doc, empty_message))
        return findings
    want_ids = [i for i, _ in want]
    got_ids = [i for i, _ in got]
    for ident in [i for i in want_ids if i not in got_ids]:
        if is_unclaimed(ident):
            continue
        findings.append(Finding(doc, f"`{ident}` has a heading but is not in the index."))
    for ident in [i for i in got_ids if i not in want_ids]:
        findings.append(Finding(doc, f"the index lists `{ident}`, which has no heading."))
    titles = dict(want)
    for ident, title in got:
        if ident in titles and titles[ident] != title:
            findings.append(Finding(
                doc,
                f"`{ident}`'s index line reads {title!r} and its heading reads "
                f"{titles[ident]!r}. The heading is the source.",
            ))
    if got_ids != [i for i in want_ids if i in got_ids]:
        findings.append(Finding(doc, "the index is not in heading order."))
    return findings


def _debts_corpus():
    """scripts/debts_corpus.py, or None. The debts twin of `_corpus()`."""
    return _sibling("debts_corpus.py")


_DEBTS_EMPTY = ("the debts corpus read as EMPTY. docs/debts/ holds one file per finding "
                "and its manifest is ORDER.json; a manifest naming a file that is gone, an "
                "unreadable directory or a missing scripts/debts_corpus.py all arrive here. "
                "This row asserts nothing until that is fixed — the same fail-open rule "
                "`decision structure` uses for its own corpus, for the same reason: an "
                "unreadable directory must never read as a clean one.")

# NON-VACUITY FLOOR. The corpus held 27 entries at the split (2026-09-16); a reader that
# finds fewer than this is broken, not tidy, on `decision structure`'s own argument for why
# an empty corpus must fail loudly rather than pass in silence.
_DEBTS_FLOOR = 20


def _debts_corpus_empty(report: Report, label: str) -> bool:
    corpus = _debts_corpus()
    if corpus is None:
        report.add(label, MECHANICAL, [Finding("docs/debts/", _DEBTS_EMPTY)])
        return True
    try:
        n = len(corpus.idents())
    except Exception:
        report.add(label, MECHANICAL, [Finding("docs/debts/", _DEBTS_EMPTY)])
        return True
    if n < _DEBTS_FLOOR:
        report.add(label, MECHANICAL, [Finding(
            "docs/debts/",
            f"the corpus read {n} entries, under the pinned floor of {_DEBTS_FLOOR}. "
            f"{_DEBTS_EMPTY}",
        )])
        return True
    return False


def check_debts_headings(report: Report) -> None:
    """Every `## ` heading in `docs/debts/` is one `_debts_section` can address.

    That helper matches `## <n> — ` and returns None otherwise, and BOTH its consumers
    tolerate a None — one with `or ""`, one with an early return. So a heading written in
    any other shape is not a failure, it is a section that silently does not exist, and
    every row reading the corpus inherits it.

    MEASURED 2026-09-11: sections 20 to 24 were written `## <n>. ` — five of the file's
    twenty-three live sections, invisible to the only reader the audit has for it, with
    every row green throughout. Normalized the same day under `D149`;
    this row is what stops the next one being written that way.

    THE CORPUS IS A DIRECTORY NOW (2026-09-16), one file per entry under `docs/debts/`, with
    `docs/debts/` left as the stub — the same split D160 performed for decisions. This row
    reads the directory rather than the monolith and asserts exactly what it asserted before.

    A DEBT NOW JOINS THE CLAIM PATH TOO (D140's own scheme, the owner's word), so a heading
    may ALSO be an unclaimed slug (`## DEBT-<slug>`, the entry's own placeholder before
    `make merge` allocates it a number) or a newly claimed entry's own `## DEBT<n>` — the
    citation form, since a debt's claimed heading may or may not carry the word (see the
    block comment above `DEBT_HEADING` in the shared merge tool). Every real entry today
    still heads itself bare (`## <n>`), and stays addressable exactly as before. The
    duplicate-number check below only ever compares NUMBERS, so a slug heading is never a
    candidate collision with one — a filename collision between two branches' slugs is
    `duplicate_pending`'s question, not this row's.

    MECHANICAL on D16's test: a heading either parses or it does not, which is the same
    standard `decision structure` is held to. It says nothing about what a section CONTAINS
    — that is the check §25 measured and declined to build.
    """
    if _debts_corpus_empty(report, "debts headings"):
        return

    findings: List[Finding] = []
    seen: Dict[int, str] = {}
    total = 0
    for path in _debts_corpus().files():
        for lineno, line in enumerate(read(path).split("\n"), 1):
            if not line.startswith("## "):
                continue
            total += 1
            good = (re.match(r"^## (?:DEBT)?(\d+) — \S", line)
                    or re.match(r"^## (DEBT" + _ID_SLUG + r") — \S", line))
            if good is None:
                findings.append(Finding(
                    f"{rel(path)}:{lineno}",
                    f"`{line[:60]}` is not the `## <n> — <title>` shape "
                    f"`_debts_section` matches, so this section cannot be addressed by "
                    f"any row that reads it, and asking for it returns None rather than "
                    f"failing.",
                ))
                continue
            token = good.group(1)
            if not token.isdigit():
                continue  # an unclaimed slug — nothing numeric to dedupe against
            number = int(token)
            if number in seen:
                findings.append(Finding(
                    f"{rel(path)}:{lineno}",
                    f"section {number} is also the heading in {seen[number]}; "
                    f"`_debts_section({number})` returns the FIRST and the second is "
                    f"unreachable.",
                ))
                continue
            seen[number] = rel(path)

    report.add("debts headings", MECHANICAL, findings,
               f"{total} headings, every one addressable by `_debts_section`",
               scanned=total)


def check_debt_index(report: Report) -> None:
    """`docs/debts/README.md`'s fenced index against `docs/debts/`'s headings, both directions.

    D160's own argument: an index that has drifted is worse than none, because it is
    believed. Both sides are ids and titles, so this is MECHANICAL — D16's test for what
    may block.

    A DEBT NOW CARRIES THE IDENTICAL CLAIM-AT-MERGE EXEMPTION A DECISION DOES (D140's own
    scheme, the owner's word: "they just get assigned numbers upon merge with CI"). A branch
    adding a finding writes `## DEBT-<slug>` in its own file and cites `DEBT-<slug>`;
    the shared merge tool allocates the number at merge time and rewrites the heading and
    every citation, exactly as it already does for a decision — see `_is_unclaimed_debt` and
    `_decision_index_findings`, which this row now reuses rather than re-implementing its own
    copy of the comparison.
    """
    if _debts_corpus_empty(report, "debt index"):
        return
    stub = ROOT / "docs" / "debts" / "README.md"
    if not exists(stub):
        report.add("debt index", MECHANICAL,
                   [Finding("docs/debts/README.md", "the README does not exist.")])
        return

    corpus = _debts_corpus()
    # THREE HEADING SHAPES: a real entry's bare `## <n>`, a newly claimed `## DEBT<n>` (its
    # heading matches its citation, like a decision's — see the block comment above
    # `DEBT_HEADING` in the shared merge tool), and an unclaimed `## DEBT-<slug>`. The
    # captured id is always normalized to its WITH-`DEBT`-letter form, matching what the
    # index itself always spells.
    heading_re = re.compile(r"^##\s+((?:DEBT)?\d+|DEBT" + _ID_SLUG + r")\s*[—-]\s*(.+)$")
    want: List[Tuple[str, str]] = []
    for path in corpus.files():
        m = heading_re.match(read(path).split("\n", 1)[0])
        if m:
            ident = m.group(1)
            want.append((ident if ident.startswith("DEBT") else f"DEBT{ident}",
                        m.group(2).strip()))

    # The index is the first fenced block whose lines all start `DEBT<id> ` — a number or an
    # unclaimed slug (D182's own tolerance, one letter over: a pending slug MAY be listed).
    line_re = re.compile(r"^DEBT(?:\d+|" + _ID_SLUG + r")\s")
    got: List[Tuple[str, str]] = []
    fenced, block = False, []
    for line in read(stub).split("\n"):
        if line.lstrip().startswith("```"):
            if fenced and block and all(line_re.match(b) for b in block if b.strip()):
                got = [(b.split(None, 1)[0], b.split(None, 1)[1].strip())
                       for b in block if b.strip()]
                break
            fenced, block = not fenced, []
            continue
        if fenced:
            block.append(line)

    findings = _decision_index_findings(
        want, got, is_unclaimed=_is_unclaimed_debt, doc="docs/debts/README.md",
        empty_message="no debts index found.")
    report.add("debt index", MECHANICAL, findings,
               f"{len(got)} indexed, matching {len(want)} headings",
               scanned=len(want))


_DEBT_RE = re.compile(r"\bDEBT(" + _ID_ANY + r")\b")


def debt_heading_idents() -> Set[str]:
    """Every debt id with a heading, WITH its `DEBT` letter — `## <n>`/`## DEBT<n>` (a claimed
    entry, either spelling — see the block comment above `DEBT_HEADING` in
    the shared merge tool) and `## DEBT-<slug>` (a pending one), normalized to `DEBT<n>` /
    `DEBT-<slug>`.

    THE DEBTS TWIN OF `decision_heading_lines_across`, read straight off the corpus files
    rather than through `debts_corpus.idents()` — that function's own `HEADING_RE` answers a
    narrower, numbers-only question for `path_for`/`idents`, which is right for THEM and
    wrong for this: a pending slug's own citation must not read as dangling.
    """
    corpus = _debts_corpus()
    if corpus is None:
        return set()
    heading_re = re.compile(r"^##\s+((?:DEBT)?\d+|DEBT" + _ID_SLUG + r")\b")
    out: Set[str] = set()
    for path in corpus.files():
        m = heading_re.match(read(path).split("\n", 1)[0])
        if m:
            ident = m.group(1)
            out.add(ident if ident.startswith("DEBT") else f"DEBT{ident}")
    return out

# THE PATH FORM, IN EVERY SPELLING THIS SPLIT RETIRED: the stub's path, optionally
# possessive, followed by "section", a section mark or a hash and a number — anything that
# names the FILE and a number in the same breath. Provably wrong once `DEBT<n>` exists:
# there is no reason left to spell a debts citation this way, so a match here is a
# regression, not a judgement call. (Written here without a literal worked example on
# purpose — this file is itself scanned, and an example would be the regression it flags.)
_DEBT_PATH_RE = re.compile(r"docs/DEBTS\.md`?('s)?\s+(?:own\s+)?(?:section\s+|§\s*|#)[0-9]+")


def check_debt_ids(report: Report, docs: List[Path]) -> None:
    """Every `DEBT<n>` citation resolves, and the retired path form has not come back.

    THE DEBTS TWIN OF `decision ids`, NARROWER ON PURPOSE. `decision ids` can require every
    `D<n>` to resolve because `D<n>` is the ONLY numbering scheme that letter names. `§<n>`
    is not: `docs/specs/*.md` alone carries 409 bare `§<n>` references to THEIR OWN sections
    (measured 2026-09-16, `docs/specs/mechanization-backlog.md`, `docs/specs/logo.md`,
    `docs/specs/motion-trigger.md` among them), and `docs/decisions/*.md` and
    `scripts/docs-audit.py` add over a hundred more citing OTHER documents' own sections by
    the same bare sigil — `logo.md §3`, `order-pipeline.md §6`. A rule
    that failed every bare `§<n>` outside `docs/debts/` would be red on all of those, none of
    which are about debts at all. THIS IS WHY THE ID IS `DEBT<n>` AND NOT A BARE `§<n>`
    (the fix this row exists to protect): only a prefixed token can be checked without
    reading the sentence around it, which is exactly D149's own conclusion — "this repo's
    prose cites by narrating, not by quoting" — turned into the two things that ARE
    decidable without narrating:

    1. every `DEBT<n>` in the tree names a real entry (MECHANICAL, like `decision ids`).
    2. the RETIRED PATH FORM — `docs/DEBTS.md` plus a number, in any of the three spellings
       this split found — has not been reintroduced anywhere outside `docs/debts/` itself
       (MECHANICAL: a literal substring match, zero judgement, and it was true of 100% of
       this tree's citations before this fix and should stay true after it).

    NOT MECHANIZED: a bare `§<n>` with no `DEBT` prefix and no `docs/DEBTS.md` nearby, added
    by a future session who means DEBT<n> and does not know to prefix it. Catching that
    requires knowing what a sentence is ABOUT, which is D149's and DEBT25's own conclusion
    about the general form of this problem, not a gap unique to this row.
    """
    if _debts_corpus_empty(report, "debt ids"):
        return
    known = debt_heading_idents()

    def scan(paths: Iterable[Path], out: List[Finding], regressions: List[Finding]) -> None:
        for path in paths:
            if str(rel(path)).replace("\\", "/").startswith("docs/debts/"):
                continue  # a sibling entry may cite another by a bare §<n> — see the stub
            for number, raw in enumerate(read(path).splitlines(), start=1):
                line = without_noqa(raw)
                for ident in _DEBT_RE.findall(line):
                    if f"DEBT{ident}" not in known:
                        out.append(Finding(
                            f"{rel(path)}:{number}",
                            f"cites DEBT{ident}, which has no `## {ident}` heading (or, for a "
                            f"pending slug, no `## DEBT{ident}` heading) in docs/debts/.",
                        ))
                if _DEBT_PATH_RE.search(line):
                    regressions.append(Finding(
                        f"{rel(path)}:{number}",
                        "spells a debts citation the retired way — `docs/DEBTS.md` plus a "
                        "number. Use `DEBT<n>` instead.",
                    ))

    dangling: List[Finding] = []
    regressions: List[Finding] = []
    code_haystack = python_files() + _walk(ROOT, (".ts", ".tsx", ".css", ".js", ".mjs"))
    scan(docs, dangling, regressions)
    scan(code_haystack, dangling, regressions)

    report.add("debt ids", MECHANICAL, dangling + regressions,
               f"{len(known)} entries, citations in docs and code all resolve, "
               f"the retired path form is gone",
               scanned=len(docs) + len(code_haystack))


def _debts_section(number: int) -> Optional[str]:
    """The body of one `## <n> — ...` section of the debts corpus, or None if not there.

    Matched on the heading's NUMBER rather than its wording: the titles are sentences and
    get edited, and a check keyed to a sentence would fail on a rewrite that changed
    nothing it cares about.

    READS THE DIRECTORY, NOT THE MONOLITH, since 2026-09-16 — `scripts/debts_corpus.py`
    hands this function the same bytes `docs/debts/` used to hold, so every caller below
    keeps working across the split unchanged.
    """
    corpus = _debts_corpus()
    if corpus is None:
        return None
    try:
        text = corpus.text()
    except Exception:
        return None
    start = re.search(rf"^## {number} — ", text, re.M)
    if start is None:
        return None
    rest = text[start.end() :]
    nxt = re.search(r"^## \d+ — ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest
