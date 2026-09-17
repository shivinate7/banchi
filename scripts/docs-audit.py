#!/usr/bin/env python3
"""Docs staleness audit — the mechanical half. See docs/DECISIONS.md D16.

This repo's markdown carries its architecture and its rationale. Nothing verified it until
this script existed, so every path, target, subcommand, test id and decision number in it
was true only for as long as someone remembered.

THE AUDIT NEVER WRITES. It opens, compares, prints, and sets an exit code. The only writes
in this file are inside `--self-test`, into a `tempfile.TemporaryDirectory()` it creates
and destroys; nothing on the audit path can touch a tracked file. Adding a `--fix` flag is
a design change, not a knob — a tool that can edit the docs to make its own check pass is
a tool that converts the project's memory into fiction. Same reason it parses with `ast`
instead of importing: importing a project module runs its top-level code, and "read-only"
should mean read-only.

Two severities, split by how knowable each finding is:

  MECHANICAL (exit 1)  a reference is provably wrong. A path that does not resolve, a
                       `make` target that does not exist, a threshold that disagrees with
                       docs/GATES.md. No judgment involved, so it blocks.
  ADVISORY   (exit 2)  a question. Code changed and the doc that describes it did not.
                       Prints and allows: blocking on a question trains you to reach for
                       `git commit --no-verify`, which also disables the opsec guard.
  USAGE      (exit 64) this script was invoked wrongly. NOT 2, and that is the whole point:
                       argparse exits 2 by default, which is the code the pre-commit hook
                       prints-and-allows on. A caller that grew a stale flag would land in
                       the allow branch and read as the routine coupling question — the
                       gate switching itself off while looking entirely normal. 64 falls
                       through to the hook's "the auditor is broken" branch, which is loud.
                       The `audit invocation` check exists so it does not get that far.

Stdlib only, so the git hook can call `python3` directly and never depends on `make venv`
having been run.

    scripts/docs-audit.py              audit the whole tree
    scripts/docs-audit.py --staged     audit the staged set (what the pre-commit hook runs)
    scripts/docs-audit.py --self-test  prove the extractors work before trusting a report

Escape hatch: PKMNSCAN_DOCS=off, honored by the hook, mirroring PKMNSCAN_GATE=off in
scripts/stop-gate.sh. Deliberate, visible in your shell, and unlike editing this file it
does not change what the check means.

One more environment variable, and it is the opposite of an escape hatch:

    PKMNSCAN_EXPORTS   colon-separated paths to extra TCGplayer Filtered CSV exports,
                       absolute or repo-relative. The game-registry rows read the committed
                       fixtures always; this adds files the repo cannot carry — a
                       full-catalog export, a Riftbound one — so their coverage questions
                       get asked. IT WIDENS THE ADVISORY ROW AND NOTHING ELSE. A path that
                       does not resolve is skipped in silence, and nothing read through it
                       can fail a commit: a gate that a file on one person's disk can break
                       is a gate that gets switched off, and a gate that *needs* such a file
                       has already switched itself off for everybody else.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import csv
import io
import json
import os
import re
import shutil
import subprocess
from functools import lru_cache
import sys
import tempfile
import tokenize
import keyword
from fnmatch import fnmatch
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, List, NamedTuple, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent

MECHANICAL = "mechanical"
ADVISORY = "advisory"

# sysexits.h EX_USAGE. Deliberately not 2 — see the exit table in the module docstring.
EXIT_USAGE = 64

# Directories that are not this project's source. `.venv` alone holds hundreds of vendored
# READMEs, and auditing someone else's markdown would be noise with a straight face.
#
# `dist` and `test-results` joined when the repo-map orphan scan learned to recurse: they
# are Vite's build output and Playwright's per-run output, both under `app/`, and a scan
# that descends now has an opinion about them. Pruned here rather than left to the
# gitignore filter in `check_map` because the two do different jobs — this one stops a
# build tree being enumerated at all, and that one stops a finding being *reported* for
# anything git calls local state. Neither subsumes the other: `app/playwright-report/` is
# ignored and not listed here, and a scan of a fresh worktree walks it for nothing.
#
# `worktrees` IS HERE FOR A DIFFERENT REASON FROM THE REST, AND IT IS THE ONLY ONE ABOUT
# CORRECTNESS RATHER THAN WASTE (2026-08-29). Everything above is build output or local state:
# scanning it is pointless. A git worktree under `.claude/worktrees/` is ANOTHER BRANCH'S SOURCE,
# checked out inside this one — so walking it does not merely waste time, it cross-checks one
# branch's prose against a different branch's code and reports the disagreement as a defect in
# yours. Observed: a concurrent session's worktree documented `make worktree-setup`, a target that
# exists on ITS branch, and this script failed the commit on THIS branch because the Makefile here
# has no such target. Two branches are allowed to disagree; that is what a branch is.
#
# It is not covered by the gitignore filter in `check_map` for the reason the paragraph above
# gives — that filter stops a finding being REPORTED and this stops the tree being walked — and
# the finding here was against `make targets`, which never consults it.
SKIP_DIRS = {
    ".venv", ".git", "node_modules", "captures", "runs", "inventory", "__pycache__",
    "dist", "test-results", "worktrees",
}

ALLOWLIST = ROOT / "scripts" / "docs-audit-allow.txt"

# Source group -> the docs that describe it. Layer 2 only; see D16 for why this is a
# question and not a failure.
COUPLING: Sequence[Tuple[Tuple[str, ...], Tuple[str, ...]]] = (
    (
        ("pipeline/", "identify/", "geometry/", "store/", "cli/"),
        ("docs/specs/batch-script.md",),
    ),
    (("harness/tests/", "harness/run.py"), ("docs/GATES.md",)),
    (("Makefile", "cli/__main__.py"), ("README.md", "CLAUDE.md")),
)

# A typo fix must not fire the coupling question. A number, not an adjective — the rule
# docs/GATES.md sets for every threshold in this project.
COUPLING_MIN_LINES = 20


# --------------------------------------------------------------------------- reporting


class Finding(NamedTuple):
    where: str  # "README.md:27", or just a filename
    message: str


class Row(NamedTuple):
    """One check's verdict, and HOW MANY SUBJECTS IT HAD.

    `scanned` is the whole point of this type existing. Before it, `render` printed `ok`
    for any row whose findings list was empty, so "examined 2,964 references, all
    resolve" and "examined none" were the same word — the repo's signature defect, stated
    exactly: a guard that cannot tell "nothing is wrong" from "nothing is known yet".
    Measured on main: `paths 0 references resolve`, `make targets 0 references, 57
    targets` and `env vars 0 documented, all real` all printed green inside a `make
    check` that a session then quoted as verification.

    `None` is not "zero" and not "fine": it is a row that declared no subject count at
    all, which the `subject counts` row below reports as a mechanical failure. Every row
    that can print clean passes one.
    """

    check: str
    severity: str
    findings: List[Finding]
    summary: str
    scanned: Optional[int] = None


# Rows whose subject may legitimately be empty, and the reason beside each name. A
# BLANKET exemption is how a rule stops being one, so this is per-row and per-mode:
#
#   "always"  the row's subject can be empty on a clean tree in any mode
#   "staged"  the row reads the MARKDOWN SET, which `--staged` narrows to the staged
#             files — so a code-only commit legitimately hands it nothing. In FULL mode
#             the same row over zero documents is a broken walk and still fails.
#
# Every other row scanning zero is a mechanical failure: a walk root that moved, a
# renamed directory, an edited suffix list, an emptied corpus. Those are the four ways
# this file has gone quietly vacuous, and `corpus_is_empty` already exists because two
# docs rows reported `0 entries` in green over an unreadable docs/decisions/.
EXPECTED_EMPTY: Dict[str, Tuple[str, str]] = {
    # --- NARROWED BY --staged, and a broken walk in full mode -------------------------
    # Each of these counts something it read OUT OF THE MARKDOWN, so `--staged` over a
    # code-only commit hands it nothing. Every other doc row counts a CODE-side roster
    # instead and cannot reach zero without a real defect, so none of those is pinned:
    # `harness tests` at zero means TESTS is empty, `pkmnscan commands` at zero means
    # COMMANDS is, and `decision ids` at zero means the corpus is unreadable.
    "paths": ("staged", "counts the references it resolved out of the staged documents"),
    "make targets": ("staged", "counts the `make` references it found in the staged documents"),
    "env vars": ("staged", "counts the variables the staged documents name"),
    "doc hygiene": ("staged", "its subject IS the staged markdown list"),
    "check numbering": ("staged", "its subject IS the staged markdown list"),
    "coupling": ("staged", "runs in --staged only, over the source groups this commit touched"),
    # --- LEGITIMATELY EMPTY ON A CLEAN TREE, in every mode ----------------------------
    "allowlist": (
        "always",
        "an empty docs-audit-allow.txt is the ideal state, not a broken reader",
    ),
    "evidence freshness": (
        "always",
        "its subject is the STAGED score sources; in a full run there is no staged set "
        "at all, which is the row's own declared scope",
    ),
    "id claims": (
        "always",
        "its subject is the unclaimed slugs this branch carries, and main carries none "
        "BY THE INVARIANT the row asserts — so on main it examines nothing, every time",
    ),
    "sole reader": (
        "always",
        "its subject is every zero-argument `Store.history()` call in production code, and "
        "D191 repointed all three (`_answer_origin`, `_reverse_stand_down`, "
        "`_origin`) to `Store.history_at(key)` — a call WITH an argument. `_history_readers()` "
        "only counts the zero-argument form on purpose (it is what makes a claim like 'the "
        "only reader' meaningful at all), so it now finds none and stays none: a future "
        "zero-argument `.history()` call in production would be a new full-table read this "
        "item exists to prevent, not a return to what this row used to count",
    ),
}


class Report:
    """Collects every finding, never stops at the first.

    Same reasoning as harness/run.py running every test after one fails: a status
    signal that stops early hides the state of everything behind it.
    """

    def __init__(self) -> None:
        self.checks: List[Row] = []

    def add(
        self,
        check: str,
        severity: str,
        findings: List[Finding],
        summary: str = "",
        scanned: Optional[int] = None,
    ) -> None:
        self.checks.append(Row(check, severity, findings, summary, scanned))

    def counts(self) -> Tuple[int, int]:
        mech = sum(len(r.findings) for r in self.checks if r.severity == MECHANICAL)
        adv = sum(len(r.findings) for r in self.checks if r.severity == ADVISORY)
        return mech, adv

    def as_json(self, exit_code: int) -> str:
        # The machine surface: nothing downstream parses the human render (spec §7 — three
        # parser bugs in one planning session came from regexing it).
        #
        # `scanned` is here because `python3 scripts/docs-audit.py --json` is what a
        # session greps instead of reading ~100 rows, so the distinction between "examined
        # everything" and "examined nothing" has to be an integer on this surface and not
        # a word in the render.
        rows = [
            {"label": row.check, "severity": row.severity, "summary": row.summary,
             "scanned": row.scanned, "vacuous": row.scanned == 0,
             "findings": [finding._asdict() for finding in row.findings]}
            for row in self.checks
        ]
        return json.dumps({"rows": rows, "exit": exit_code}, indent=2)

    def render(self) -> str:
        lines = ["PKMNSCAN docs audit — docs/DECISIONS.md D16", "=" * 72, ""]
        for row in self.checks:
            check, severity, findings, summary = row.check, row.severity, row.findings, row.summary
            if not findings:
                if row.scanned is None:
                    # Not a pass and not a failure — a verdict over a subject nobody
                    # counted. `subject counts` fails the commit on it.
                    lines.append(f"  bare {check:<22} {summary}  [no subject count declared]")
                elif row.scanned == 0:
                    pin = EXPECTED_EMPTY.get(check)
                    why = pin[1] if pin else "NOT pinned as expected-empty — this row examined nothing"
                    lines.append(f"  none {check:<22} examined nothing — {why}")
                else:
                    lines.append(f"  ok   {check:<22} {summary}")
                continue
            tag = "FAIL" if severity == MECHANICAL else "ask "
            noun = "problem" if len(findings) == 1 else "problems"
            if severity == ADVISORY:
                noun = "question" if len(findings) == 1 else "questions"
            lines.append(f"  {tag} {check:<22} {len(findings)} {noun}")
            for finding in findings:
                lines.append(f"       {finding.where}")
                for text in finding.message.splitlines():
                    lines.append(f"         {text}")
        mech, adv = self.counts()
        lines.append("")
        lines.append("=" * 72)
        if mech:
            lines.append(f"{mech} mechanical {'failure' if mech == 1 else 'failures'} — a reference above is provably wrong.")
            lines.append("Fix the reference, or the code it points at. Do not edit a doc")
            lines.append("purely to unblock a commit — see D16.")
        if adv:
            lines.append(f"{adv} {'question' if adv == 1 else 'questions'} — code changed, its doc did not. Not blocking.")
            lines.append("Run /docs-audit to review the prose against the diff.")
        if not mech and not adv:
            lines.append("clean")
        return "\n".join(lines)


# ------------------------------------------------------------------- file discovery


@lru_cache(maxsize=1)
def nested_worktrees() -> Tuple[Path, ...]:
    """Every git worktree checked out INSIDE this one, by absolute path.

    THE NAME-BASED SKIP IS THE CONVENTION AND THIS IS THE RULE. `worktrees` in SKIP_DIRS catches
    Claude Code's own `.claude/worktrees/<name>/`, which is where concurrent sessions put them and
    is the case that was actually observed breaking a commit. It does NOT catch a worktree made by
    hand anywhere else under the repo — `git worktree add ./scratch-branch` reproduces the same
    defect with a directory name nothing can guess. Asking git is the only exact answer.

    WHY THIS IS A CORRECTNESS PRUNE AND NOT A SPEED ONE: a worktree is another BRANCH's source
    inside this tree, so walking it checks one branch's prose against another branch's code and
    reports the disagreement as a defect in yours. Two branches are allowed to disagree.

    FAILS OPEN, like `ignored_paths` above and for the same reason. If git is missing, slow, or
    this is not a repository, the answer is "no nested worktrees" and the name-based skip still
    stands. A discovery helper that can abort the audit would be worse than one that occasionally
    walks too much.
    """
    try:
        out = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=ROOT, capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ()
    if out.returncode != 0:
        return ()
    found: List[Path] = []
    for line in out.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        path = Path(line[len("worktree ") :].strip()).resolve()
        if path == ROOT.resolve():
            continue
        try:
            path.relative_to(ROOT.resolve())
        except ValueError:
            continue  # outside this tree; os.walk never reaches it
        found.append(path)
    return tuple(found)


def _inside_nested_worktree(path: Path) -> bool:
    nested = nested_worktrees()
    if not nested:
        return False
    resolved = path.resolve()
    return any(resolved == root or root in resolved.parents for root in nested)


def _walk(root: Path, suffixes: Tuple[str, ...]) -> List[Path]:
    """Every file under `root` matching a suffix — from the index in staged mode.

    Discovery is an existence question, so it answers from the same tree as `exists()`.
    Walking the worktree here would hand the checks a file list the commit does not have.
    """
    if _INDEX_PATHS is not None:
        prefix = "" if root == ROOT else rel(root).rstrip("/") + "/"
        return sorted(
            ROOT / entry
            for entry in _INDEX_PATHS
            if entry.startswith(prefix)
            and entry.endswith(suffixes)
            and not SKIP_DIRS.intersection(Path(entry).parent.parts)
        )
    found: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in SKIP_DIRS and not _inside_nested_worktree(Path(dirpath) / d)
        ]
        for name in filenames:
            if name.endswith(suffixes):
                found.append(Path(dirpath) / name)
    return sorted(found)


def markdown_files() -> List[Path]:
    return _walk(ROOT, (".md",))


def python_files() -> List[Path]:
    return _walk(ROOT, (".py",))


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


# Populated only in staged mode. A file staged at version A and edited on to version B must
# be audited as A — the content the commit will carry — or the hook checks prose the commit
# does not contain.
#
# CONTENT AND EXISTENCE ARE ONE QUESTION, NOT TWO. Reading staged content while asking the
# worktree what exists audits a tree that will never be committed, and the mixture is worse
# than either half: an untracked file makes a dangling reference resolve, an unstaged doc
# edit satisfies a criterion the commit does not carry, and the hook passes a commit the
# whole-tree audit rejects. `_INDEX_PATHS` is the committed tree's file set — None outside
# staged mode, which is what selects the worktree everywhere below.
_STAGED_PATHS: Set[str] = set()
_INDEX_PATHS: Optional[Set[str]] = None


def _nul_list(*args: str) -> Set[str]:
    return {entry for entry in git(*args).split("\0") if entry}


def enter_staged_mode() -> None:
    """Point every read, existence check and directory listing at the index."""
    global _INDEX_PATHS
    _INDEX_PATHS = _nul_list("ls-files", "-z")
    # Content differs from disk in two cases, and both must come from the index: staged
    # against HEAD, and worktree edited on top of what was staged. The second is the one
    # that used to leak — a doc edited but not staged was read from the worktree and its
    # unstaged text satisfied a check the commit would fail.
    _STAGED_PATHS.update(_nul_list("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"))
    _STAGED_PATHS.update(_nul_list("diff", "--name-only", "-z", "--diff-filter=ACMR"))


def leave_staged_mode() -> None:
    """Back to the worktree. Only the self-test needs this; audit() is one-shot."""
    global _INDEX_PATHS
    _INDEX_PATHS = None
    _STAGED_PATHS.clear()


def read(path: Path) -> str:
    if rel(path) in _STAGED_PATHS:
        return git("show", ":" + rel(path))
    return path.read_text(encoding="utf-8", errors="replace")


def exists(path: Path) -> bool:
    """Existence as the commit will see it, never as the worktree sees it."""
    if _INDEX_PATHS is None:
        return path.exists()
    name = rel(path)
    if name in _INDEX_PATHS:
        return True
    prefix = name.rstrip("/") + "/"  # a directory exists only through the files under it
    return any(entry.startswith(prefix) for entry in _INDEX_PATHS)


def child_names(directory: Path) -> Set[str]:
    """Immediate children of a directory, from the index in staged mode."""
    if _INDEX_PATHS is None:
        return {entry.name for entry in directory.iterdir()} if directory.is_dir() else set()
    prefix = "" if directory == ROOT else rel(directory).rstrip("/") + "/"
    return {
        entry[len(prefix):].split("/", 1)[0]
        for entry in _INDEX_PATHS
        if entry.startswith(prefix) and entry != prefix
    }


def glob_files(directory: Path, pattern: str) -> List[Path]:
    """`Path.glob` semantics, against the index in staged mode.

    The remainder must not contain a separator. `fnmatch`'s `*` crosses `/` and
    `Path.glob`'s does not, so without that guard `harness/results/*.json` would also
    match anything nested below it — a difference the self-test caught.
    """
    if _INDEX_PATHS is None:
        return sorted(directory.glob(pattern)) if directory.is_dir() else []
    prefix = "" if directory == ROOT else rel(directory).rstrip("/") + "/"
    return sorted(
        ROOT / entry
        for entry in _INDEX_PATHS
        if entry.startswith(prefix)
        and "/" not in entry[len(prefix):]
        and fnmatch(entry[len(prefix):], pattern)
    )


def top_level_names() -> Set[str]:
    return child_names(ROOT)


# ----------------------------------------------------------------- path references

# A candidate must contain a slash. That single requirement is what keeps this check
# usable: the docs are full of `161/159`, `SWSH/SV`, `sets/en.json` and
# `zfill(3)(number) + "/" + printedTotal`, and a bare-filename rule would also have to
# judge `decisions.json`, which is pipeline runtime state and deliberately absent.
_CANDIDATE_RE = re.compile(r"@?(?:\.\./)*[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]*")
_TRAILING = ".,;:)]}—"
# Placeholders are documentation, not paths: `t1-<UTC date>.json`, `GET /photo/<box>/…`.
_PLACEHOLDER = re.compile(r"[<>*?{}]")

# A ROUTE IS NOT A PATH, and until 2026-08-24 nothing here knew the difference. Most routes
# in these docs got away with it by accident: `/queues` is one segment and resolves to
# nothing, and `/inventory/<box>/<index>/sold` is broken up by the placeholder rule above. A
# two-segment route whose first segment happens to name a top-level package has neither
# escape — `POST /pipeline/identify` was read as the file `pipeline/identify`, which will
# never exist, and blocked a commit for describing a route correctly.
#
# Removed by the HTTP METHOD in front of it rather than by the shape of the path, because the
# shape is exactly what cannot be told apart: `pipeline/identify` is a plausible module and
# `/pipeline/identify` is a real route, and only the `POST` says which one the sentence means.
# That also keeps the rule narrow — a path mentioned in prose with no method before it is
# still checked, which is every path reference this check exists for.
#
# The allowlist was the other option and is the wrong tool: D16 makes it self-cleaning by
# FAILING when an entry comes true, and `pipeline/identify` is a file that can never come
# true, so the entry would sit there forever being no evidence of anything.
_ROUTE = re.compile(r"\b(?:GET|POST|PUT|DELETE|PATCH|HEAD)\s+(/[A-Za-z0-9_./<>-]*)")
# A QUOTED STRING THAT BEGINS WITH A SLASH IS A ROUTE TOO, since 2026-09-12. The method
# rule above covers prose; code in a fenced block spells the same route the way the
# dispatcher does — `if path == "/pipeline/value":` at capture_server.py:10748, a JS
# template `` `/pipeline/value?${q}` `` in server.ts — and a playbook that mirrors the
# code was blocked for describing it correctly. No repo path is ever spelled with a
# leading slash inside quotes: every reference this check exists for is relative
# (`store/db.py`), and an absolute `/Users/...` never resolves to a top-level name anyway.
_QUOTED_ROUTE = re.compile(r"""(["'`])/[A-Za-z0-9_./<>?$={}()&-]*\1""")


# Suffixes that mean "this is a file". Anything else after the final dot is read as an
# attribute — `pipeline/variant.resolve` names a function, not a file, and the docs use
# that form to point at code precisely.
KNOWN_SUFFIXES = {
    ".py", ".md", ".sh", ".json", ".csv", ".txt", ".js", ".jsx", ".ts", ".tsx",
    ".yaml", ".yml", ".toml", ".html", ".css", ".png", ".jpg", ".jpeg", ".svg",
    ".cfg", ".ini", ".lock", ".example", ".env", ".sample",
}


# ------------------------------------------------------- the proposed-name sigil

PROPOSED_SIGIL = "+"


def marked_proposed(line: str, start: int) -> bool:
    """Is the token at `start` marked as named-before-it-exists?

    **A `+` immediately in front of a path, a `make` target or a `PKMNSCAN_` name says the
    thing does not exist YET** — `+scripts/guard-shell.py`, `+make opsec-selftest`,
    and `+PKMNSCAN_` followed by a name. Three rows here verify that a named thing is real, and a design
    document's whole job is to name what it would create, so without a marker those rows and
    that job cannot both be served.

    **WHY AT THE POINT OF USE RATHER THAN IN THE ALLOWLIST.** `scripts/docs-audit-allow.txt`
    already carries "named before it is built" as one of its reasons, and it is self-cleaning
    — the `allowlist` row fails when a listed path exists. This keeps that property and moves
    it to where a READER is: the status of the name is visible in the sentence that uses it,
    rather than in a registry two directories away. It also stops the allowlist being a
    conflict surface — it is an exact-match roster, and a shelf document naming twenty-one
    unbuilt mechanisms would otherwise add twenty-one lines to one file that every other
    branch also edits.

    **The allowlist keeps a different job**, and the distinction is worth the two mechanisms:
    a path listed there is meant to be unresolvable FOREVER — `app/src/orderWalk.ts` is
    deleted and its references record the deletion. A `+` says *not yet*, which is a claim
    with an expiry.

    **IT IS SELF-CLEANING THE SAME WAY**: every row below FAILS when a marked name exists, so
    the sigil has to come off in the PR that builds the thing. A marker that could be left
    on would turn every proposal into a permanent exemption, which is the failure this repo
    has already paid for once in the allowlist's own header.

    **What it deliberately does not mark**: `+x` (a file mode) and any other `+`-prefixed
    token that is not shaped like a path, a target or an env name. The sigil is only read
    where a row was about to make a claim about existence.
    """
    return start > 0 and line[start - 1] == PROPOSED_SIGIL


def path_candidates(line: str) -> List[str]:
    """Extract path-shaped tokens. Deliberately conservative — see the note above."""
    out: List[str] = []
    # Routes first: a method in front of a slash-path means the sentence is about an HTTP
    # route, and this script has nothing to say about whether one exists. The path check
    # cannot tell a route from a module by shape alone — see `_ROUTE`.
    line = _ROUTE.sub(" ", line)
    line = _QUOTED_ROUTE.sub(" ", line)
    if _PLACEHOLDER.search(line):
        line = _PLACEHOLDER.sub(" ", line)
    for match in _CANDIDATE_RE.finditer(line):
        text = match.group(0).rstrip(_TRAILING)
        if not text or "/" not in text:
            continue
        # A `+` in front says the doc is naming something it would CREATE. The token is
        # still returned, marked, because the row has to fail when it becomes real.
        out.append((PROPOSED_SIGIL if marked_proposed(line, match.start()) else "") + text)
    return out


def module_attributes(path: Path) -> Set[str]:
    """Top-level names a Python module defines, read statically."""
    try:
        tree = ast.parse(read(path))
    except SyntaxError:
        return set()
    names: Set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _git_path(text: str) -> Path:
    """A `.git/...` reference, resolved where git actually keeps it.

    IN A LINKED WORKTREE `.git` IS A FILE, NOT A DIRECTORY, so `ROOT / ".git/config"`
    resolves to nothing and a perfectly true sentence reads as a broken path. Measured
    2026-08-29: `README.md`'s `core.hooksPath` lives in `.git/config` — the line that
    explains why `make hooks` exists — failed this check in a worktree and passed in the
    main clone, which is the shape of finding this script exists to prevent, pointing at
    itself.

    The file holds one line, `gitdir: <path>/.git/worktrees/<name>`, and the config a
    worktree shares lives two levels up from that. Read rather than shelled out to: this
    script does not run project code, and `git rev-parse --git-common-dir` would be a
    subprocess where a 140-byte read answers the same question.

    Falls back to the literal path on anything unexpected, so a malformed pointer reports
    the missing file it always did rather than raising inside the audit.
    """
    dot_git = ROOT / ".git"
    if dot_git.is_dir():
        return ROOT / text
    try:
        pointer = dot_git.read_text(encoding="utf-8").strip()
    except OSError:
        return ROOT / text
    if not pointer.startswith("gitdir:"):
        return ROOT / text
    gitdir = Path(pointer.split(":", 1)[1].strip())
    common = gitdir.parent.parent if gitdir.parent.name == "worktrees" else gitdir
    return common / text[len(".git/"):]


def resolve_candidate(candidate: str, containing: Path, tops: Set[str]) -> Optional[Path]:
    """Repo path for a candidate, or None when it is not ours to check.

    Returning None is the common case and the correct one. A first segment that is not a
    real top-level entry means the string belongs to someone else's namespace —
    `PokemonTCG/pokemon-tcg-data`, `claude.ai/code`, `sets/en.json` — and this script has
    no standing to say whether it exists.
    """
    text = candidate.lstrip("@")
    if text.startswith("../"):
        # A `../` INSIDE A DECISION ENTRY MEANS EITHER `docs/` OR `docs/decisions/`, AND
        # BOTH ARE TRIED. The entries were one file at `docs/DECISIONS.md` until the split;
        # their bytes are unchanged by design, and a pre-split entry writing `../` meant the
        # repo root because that is where it sat. D135 has one. Resolving only from the
        # deeper directory makes a faithful move look like a broken citation.
        #
        # BUT THE RULE MAY NOT BE BLANKET, and that was the review's catch. An entry written
        # AFTER the split, sitting in `docs/decisions/`, may legitimately mean its own
        # parent — and a rule fixed on the historical reading would misresolve it silently,
        # forever. A bound on the id would answer it and rot: the boundary is a date, not a
        # number, and nothing would maintain it.
        #
        # So both are accepted. What is given up is narrow and worth naming: a `../` path
        # that exists under one base and is a typo for something under the other resolves
        # instead of being reported. That is a strictly smaller hole than either rule alone,
        # and it needs no boundary anybody has to keep updating.
        bases = [containing.parent]
        if containing.parent == ROOT / "docs" / "decisions":
            bases.append(ROOT / "docs")
        target = None
        for base in bases:
            candidate_path = (base / text).resolve()
            try:
                candidate_path.relative_to(ROOT)
            except ValueError:
                continue
            target = candidate_path
            if exists(candidate_path):
                break
        return target
    text = text[2:] if text.startswith("./") else text
    first = text.split("/", 1)[0]
    if first not in tops:
        return None
    if first == ".git":
        return _git_path(text)
    return ROOT / text


def ignored_paths(candidates: Sequence[str], root: Optional[Path] = None) -> Set[str]:
    """Which of these git ignores. One batched call, not one per candidate.

    A gitignored path is local state, not repo content: `harness/images/` exists once you
    have run the image fetch and not before. Checking it would make this audit green on
    the owner's machine and red on a fresh clone, which is the opposite of what a
    committed check is for. Same category as `sets/en.json` — not ours to have an opinion
    about.

    Callers probe both `p` and `p/`. .gitignore states most of these as directory-only
    patterns (`harness/images/`), and git cannot match one of those against a path that is
    absent from disk — which is precisely the fresh-clone case this exists to handle, so
    the bare form silently fails exactly when it matters.

    ONE POISONED CANDIDATE USED TO TAKE THE WHOLE BATCH DOWN, SILENTLY, AND THE FINDING
    LANDED ON SOMEBODY ELSE. `git check-ignore --stdin` exits 128 and STOPS on a pathspec it
    refuses — `fatal: pathspec 'app/node_modules/' is beyond a symbolic link`, which is what a
    worktree's provisioning links are — and the answers for every candidate after it are simply
    never printed. Read as a plain result that is "not ignored for all of them", so the first
    unrelated gitignored path further down the list is reported as a dangling reference.
    Measured 2026-08-30: a decision entry naming `app/node_modules` in prose made the batch
    abort, and the audit blocked the commit over `harness/.cache/` in a different file, which
    was correct and had not changed.

    So a batch that did not run cleanly is not evidence about anything. check-ignore's own
    contract is 0 when something matched and 1 when nothing did; ANY other code means it gave
    up, and the answer is to ask again one candidate at a time so a refusal is contained to the
    candidate that caused it. That path is rare and short — it runs only over references that
    are already missing from the index.

    `root` DEFAULTS TO THE REAL REPO AND EXISTS ONLY SO THE SELF-TEST CAN POINT THIS AT A
    THROWAWAY ONE. Every caller in this file omits it; a test builds a real git repo with a
    real symlink to reproduce the exact failure below without touching this checkout's own.
    """
    base = root if root is not None else ROOT
    if not candidates:
        return set()

    def ask(batch: Sequence[str]) -> Tuple[int, Set[str]]:
        try:
            done = subprocess.run(
                ["git", "check-ignore", "--stdin"],
                cwd=str(base),
                input="\n".join(batch).encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except OSError:
            return 1, set()  # no git: fall back to checking everything
        got = {line for line in done.stdout.decode("utf-8", errors="replace").splitlines() if line}
        return done.returncode, got

    code, found = ask(candidates)
    if code in (0, 1):
        return found

    for candidate in candidates:
        one_code, one = ask([candidate])
        if one_code in (0, 1):
            found |= one
            continue
        # A CANDIDATE CAN FAIL ALONE TOO, AND THE RETRY ABOVE CANNOT RESCUE IT — measured
        # 2026-09-12: `harness/images` is a real symlink in a worktree (provisioned by
        # `make worktree-setup`, pointing at the main checkout's own directory), and
        # `git check-ignore` refuses ANY pathspec that walks past it — one candidate,
        # asked alone, still exits 128 with "pathspec '...' is beyond a symbolic link".
        # That is not the poisoned-batch failure this retry loop was built for; it is a
        # single candidate git's pathspec matcher can never answer while the symlink
        # exists on disk, in this worktree or any other.
        #
        # THE FIX READS AN ANCESTOR INSTEAD OF THE CANDIDATE. Gitignore's own directory
        # semantics make this exact, not a guess: a pattern matching a directory ignores
        # everything beneath it, so if `harness/images` (the symlink node itself, asked
        # with no trailing slash — the one form `check-ignore` can still answer past a
        # symlink boundary, confirmed by measurement) is ignored, so is every path under
        # it, symlinked or not. Walking up from the candidate's own parent stops at the
        # first ancestor `check-ignore` can actually answer.
        parts = candidate.rstrip("/").split("/")
        for depth in range(len(parts) - 1, 0, -1):
            ancestor = "/".join(parts[:depth])
            anc_code, anc_found = ask([ancestor])
            if anc_code == 0 and ancestor in anc_found:
                found.add(candidate)
                break
            if anc_code in (0, 1):
                # A real answer that isn't a match: no ancestor closer to root can be
                # narrower, so stop here rather than walk past what git already resolved.
                break
    return found


def check_paths(report: Report, docs: List[Path], allowed: Dict[str, str]) -> None:
    tops = top_level_names()
    findings: List[Finding] = []
    checked = 0

    seen: List[Tuple[Path, int, str, Path]] = []
    for doc in docs:
        for number, line in enumerate(read(doc).splitlines(), start=1):
            for candidate in path_candidates(line):
                mark = candidate.startswith(PROPOSED_SIGIL)
                target = resolve_candidate(candidate.lstrip(PROPOSED_SIGIL), doc, tops)
                if target is None:
                    continue
                # `.git/` IS GIT'S OWN STORAGE AND NOT REPO CONTENT — see this module's
                # header note. Whether `.git/config` or `.git/worktrees/` is there is a fact
                # about how this checkout is arranged: the first is a FILE rather than a
                # directory in a linked worktree, and the second is created with the first
                # worktree and deleted with the last. Both blocked a commit over a true
                # sentence in this session alone. Same category as a gitignored path, which
                # `ignored_paths` already exempts for the same reason and in the same words.
                if rel(target).split("/")[0] == ".git":
                    continue
                checked += 1
                seen.append((doc, number, candidate, target, mark))

    # A MARKED NAME THAT NOW EXISTS IS A FINDING, which is what keeps the sigil honest.
    for doc, number, candidate, target, mark in seen:
        if mark and exists(target):
            findings.append(Finding(
                f"{rel(doc)}:{number}",
                f"`{candidate}` carries the `{PROPOSED_SIGIL}` proposed-name sigil and "
                f"`{rel(target)}` now EXISTS. Drop the sigil — it says *not yet*, and "
                f"leaving it on turns a proposal into a permanent exemption.",
            ))
    missing = [item for item in seen if not exists(item[3]) and not item[4]]
    probe: List[str] = []
    for item in missing:
        probe.append(rel(item[3]))
        probe.append(rel(item[3]) + "/")
    ignored = ignored_paths(probe)

    for doc, number, candidate, target, _ in missing:
        if rel(target) in ignored or rel(target) + "/" in ignored:
            continue
        if rel(target) in allowed or rel(target) + "/" in allowed:
            continue

        # `pipeline/variant.resolve` — a module and one of its names. Verifying the
        # attribute is the point: a doc that points at a function deleted three commits
        # ago is exactly the drift this script exists to catch, and it would otherwise
        # read as a plain missing file.
        suffix = target.suffix
        if suffix and suffix not in KNOWN_SUFFIXES:
            module = target.with_suffix(".py")
            if exists(module):
                attribute = suffix[1:]
                if attribute in module_attributes(module):
                    continue
                findings.append(
                    Finding(
                        f"{rel(doc)}:{number}",
                        f"`{candidate}` — {rel(module)} exists but defines no "
                        f"`{attribute}`.",
                    )
                )
                continue

        findings.append(
            Finding(
                f"{rel(doc)}:{number}",
                f"`{candidate}` does not exist.\n"
                f"Fix the reference, or add it to scripts/docs-audit-allow.txt "
                f"with a reason if it is named before it is built.",
            )
        )
    report.add("paths", MECHANICAL, findings, f"{checked} references resolve",
               scanned=checked)


# ---------------------------------------------------------------------- the allowlist


def load_allowlist() -> Dict[str, str]:
    if not exists(ALLOWLIST):
        return {}
    entries: Dict[str, str] = {}
    for line in read(ALLOWLIST).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        path, _, reason = stripped.partition("#")
        entries[path.strip()] = reason.strip()
    return entries


_IDENTIFIER_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_TEST_ID_RE = re.compile(r"^T[1-9][0-9]?$")


def is_identifier_entry(entry: str) -> bool:
    """An ALL_CAPS entry is an env var or a test id, not a path."""
    return bool(_IDENTIFIER_RE.match(entry))


def check_allowlist(report: Report, allowed: Dict[str, str]) -> None:
    """Self-cleaning: an entry that has come true is stale and must go.

    Same instinct as scripts/stop-gate.sh arming on the absence of NOT_IMPLEMENTED
    markers rather than on a toggle someone has to remember to flip. An allowlist that
    only ever grows becomes a list of things nobody has looked at since.

    Each kind goes stale by the same signal the check it suppresses uses. Anything looser
    misfires: a blanket "appears anywhere in the code" reads a comment explaining why T7
    does not exist as proof that it does.
    """
    findings = []
    for entry, reason in sorted(allowed.items()):
        if _TEST_ID_RE.match(entry):
            arrived = entry in {name for name, _ in registered_tests()}
            what = "is a registered harness test now"
        elif is_identifier_entry(entry):
            arrived = entry in code_haystack()
            what = "is referenced in the code now"
        else:
            arrived = exists(ROOT / entry)
            what = "exists now"
        if arrived:
            findings.append(
                Finding(
                    "scripts/docs-audit-allow.txt",
                    f"`{entry}` {what}, so the entry is stale — delete the line.\n"
                    f"It was allowed because: {reason or '(no reason recorded)'}",
                )
            )
    report.add("allowlist", MECHANICAL, findings, f"{len(allowed)} entries, none stale",
               scanned=len(allowed))


# ----------------------------------------------------------------------- make targets

_MAKE_RULE_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9_-]*):", re.MULTILINE)
_MAKE_REF_RE = re.compile(r"\bmake ([a-z][a-z0-9-]*)")


def iter_code_lines(text: str):
    """Yield (line number, line) for lines where a command reference is a command.

    English is full of `make it` and `make the`, so a bare `make \\w+` match reads prose as
    a build target. A command reference lives in a fenced block or in backticks, and
    nowhere else — requiring that is the difference between this check and noise.
    """
    fenced = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            yield number, line
            continue
        # Outside a fence, keep only the spans between backticks.
        #
        # JOINED BY A NEWLINE, BECAUSE TWO ADJACENT SPANS ARE TWO REFERENCES AND NOT ONE.
        # A space let every caller's regex match straight across a span boundary, so
        # `make` beside `docs/GATES.md` read as a target called `docs` and
        # `~/Developer/pkmnscan` beside `make icloud-sweep` read as a subcommand called
        # `make`. Both are phantoms — nobody wrote either reference — and both blocked a
        # commit. Latent until D60 unwrapped the prose: the docs used to wrap at 96
        # columns, which kept most spans on separate lines and hid it. Every caller here
        # matches a literal space after the command word, so a newline cannot be crossed,
        # and one yield per source line keeps the reported line numbers right.
        spans = re.findall(r"`([^`]+)`", line)
        if spans:
            yield number, "\n".join(spans)


def phony_gaps(text: str) -> Tuple[Set[str], Set[str]]:
    """(rule targets missing from `.PHONY`, `.PHONY` names with no rule).

    `.PHONY` is a second enumeration of the same target list, and make obeys the shorter
    one silently. Every rule in this Makefile is a command, never a file it builds, so a
    name missing from `.PHONY` is always wrong — and when a file or directory of that name
    exists the target stops running altogether: `harness:` has no prerequisites and
    `harness/` is a real directory, so dropping `harness` makes `make harness` print
    "up to date" and exit 0 having run no tests. `make check` and the stop gate inherit it,
    and the docs audit stays clean throughout, because nothing was ever wrong in the prose.

    Both directions. The mirror drift is the same defect from the other side: a `.PHONY`
    name with no rule is dead config that reads as coverage.
    """
    targets = set(_MAKE_RULE_RE.findall(text))
    phony: Set[str] = set()
    for line in text.splitlines():
        if line.startswith(".PHONY:"):
            phony.update(line[len(".PHONY:"):].split())
    return targets - phony, phony - targets


def check_make_targets(report: Report, docs: List[Path]) -> None:
    makefile = ROOT / "Makefile"
    if not exists(makefile):
        report.add("make targets", MECHANICAL, [Finding("Makefile", "does not exist")])
        return
    text = read(makefile)
    targets = set(_MAKE_RULE_RE.findall(text))

    findings: List[Finding] = []
    referenced = 0
    for doc in docs:
        for number, line in iter_code_lines(read(doc)):
            for match in _MAKE_REF_RE.finditer(line):
                name = match.group(1)
                referenced += 1
                if marked_proposed(line, match.start()):
                    # `+make opsec-selftest` — a target a proposal would add. It has to fail
                    # the moment it exists, or the sigil becomes a permanent exemption.
                    if name in targets:
                        findings.append(Finding(
                            f"{rel(doc)}:{number}",
                            f"`{PROPOSED_SIGIL}make {name}` carries the proposed-name sigil "
                            f"and that target NOW EXISTS. Drop the sigil.",
                        ))
                    continue
                if name not in targets:
                    findings.append(
                        Finding(
                            f"{rel(doc)}:{number}",
                            f"`make {name}` — no such target in the Makefile.\n"
                            f"Targets are: {', '.join(sorted(targets))}",
                        )
                    )

    # The reverse direction. `make help` is the front door, and a target missing from it
    # is invisible to anyone who did not read the Makefile.
    help_body = ""
    in_help = False
    for line in text.splitlines():
        if line.startswith("help:"):
            in_help = True
            continue
        if in_help:
            if line and not line[0].isspace():
                break
            help_body += line + "\n"
    for name in sorted(targets):
        if name == "help":
            continue
        if f"make {name}" not in help_body:
            findings.append(
                Finding(
                    "Makefile",
                    f"target `{name}` exists but `make help` never mentions it.",
                )
            )

    unphony, unruled = phony_gaps(text)
    for name in sorted(unphony):
        findings.append(
            Finding(
                "Makefile",
                f"target `{name}` is missing from `.PHONY`.\n"
                f"  A file or directory named `{name}` turns `make {name}` into a no-op "
                f"that exits 0 — a green build that ran nothing.",
            )
        )
    for name in sorted(unruled):
        findings.append(
            Finding(
                "Makefile",
                f"`.PHONY` names `{name}`, which is not a target in this Makefile.",
            )
        )
    report.add("make targets", MECHANICAL, findings,
               f"{referenced} references, {len(targets)} targets", scanned=referenced)


# ----------------------------------------------------------- ./pkmnscan subcommands

_PKMNSCAN_REF_RE = re.compile(r"`?\.?/?pkmnscan ([a-z][a-z-]*)")


def dict_keys_from_assign(source: str, name: str) -> Optional[List[str]]:
    """Literal dict keys of a module-level assignment, without importing the module."""
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Name)
                and target.id == name
                and isinstance(node.value, ast.Dict)
            ):
                keys = []
                for key in node.value.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        keys.append(key.value)
                return keys
    return None


def check_pkmnscan_commands(report: Report, docs: List[Path], all_docs: List[Path]) -> None:
    main = ROOT / "cli" / "__main__.py"
    if not exists(main):
        report.add("pkmnscan commands", MECHANICAL, [Finding("cli/__main__.py", "does not exist")])
        return
    registered = dict_keys_from_assign(read(main), "COMMANDS")
    if registered is None:
        report.add(
            "pkmnscan commands",
            MECHANICAL,
            [Finding("cli/__main__.py", "no module-level COMMANDS dict literal to read")],
        )
        return

    findings: List[Finding] = []
    for doc in docs:
        for number, line in iter_code_lines(read(doc)):
            for name in _PKMNSCAN_REF_RE.findall(line):
                if name not in registered:
                    findings.append(
                        Finding(
                            f"{rel(doc)}:{number}",
                            f"`./pkmnscan {name}` is documented but not registered in "
                            f"cli/__main__.py:COMMANDS ({', '.join(registered)}).",
                        )
                    )

    # Completeness reads every doc, never the staged subset. The two halves ask opposite
    # questions and need opposite scopes: "does this reference resolve" is about the lines
    # you changed, while "is this command documented anywhere" is about the repo. Scoping
    # the second one to the staged set asked whether a command is documented in the files
    # this commit happens to touch — which is not the invariant, and failed every commit
    # that edited a doc other than CLAUDE.md or README.md.
    documented: Set[str] = set()
    for doc in all_docs:
        for _, line in iter_code_lines(read(doc)):
            documented.update(_PKMNSCAN_REF_RE.findall(line))
    for name in registered:
        if name not in documented:
            findings.append(
                Finding(
                    "cli/__main__.py",
                    f"`./pkmnscan {name}` is registered but documented nowhere. "
                    f"CLAUDE.md and README.md both list the commands.",
                )
            )
    report.add(
        "pkmnscan commands",
        MECHANICAL,
        findings,
        f"{len(registered)} registered, all documented",
        scanned=len(registered),
    )


# ------------------------------------------------------------- harness tests + criteria

_TEST_REF_RE = re.compile(r"\bT([1-9][0-9]?)\b")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def list_names_from_assign(source: str, name: str) -> Optional[List[str]]:
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Name)
                and target.id == name
                and isinstance(node.value, (ast.List, ast.Tuple))
            ):
                return [
                    element.id
                    for element in node.value.elts
                    if isinstance(element, ast.Name)
                ]
    return None


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


def registered_tests() -> List[Tuple[str, Path]]:
    runner = ROOT / "harness" / "run.py"
    if not exists(runner):
        return []
    modules = list_names_from_assign(read(runner), "TESTS") or []
    out = []
    for module in modules:
        path = ROOT / "harness" / "tests" / (module + ".py")
        name = module.split("_", 1)[0].upper()
        out.append((name, path))
    return out


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
                rel(SELF),
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
    report.add("pass criteria", MECHANICAL, mechanical, "every threshold matches GATES.md",
               scanned=compared)
    report.add("criteria wording", MECHANICAL, wording,
               "every criterion is published verbatim", scanned=read_criteria)


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


# ---------------------------------------------------------------------- decision ids

# THE CAP IS SPELLED ONCE, BECAUSE IT WAS SPELLED SEVEN TIMES HERE AND NOBODY RECOUNTED IT.
# `[1-9][0-9]?` read decision ids for a year and went vacuous at the hundredth entry: a
# heading stops being a heading to this file and a citation stops being a citation, so
# `decision ids`, `decision ids in code`, `decision index`, `decision structure` and
# `id claims` all report GREEN over a file they can no longer see. docs/DEBTS.md carried
# that as a triggered debt from 2026-08-30 until this landed; the trigger fired at the
# ninetieth entry and the file reached D92 before anyone discharged it. The entry is gone from
# that file rather than rewritten as closed — its own preamble sends closure narrative to git,
# and D72 carries what a reader needs.
#
# PROVED RATHER THAN ASSUMED, which is what the debt entry demanded and why it stayed open:
# a three-digit heading appended to docs/DECISIONS.md left `decision ids` reporting 92 D
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
# exist and `decision ids in code` reports it. That is not hypothetical: D72's reopening
# condition opened with the id, invisibly, for as long as these patterns could not read three
# digits — and failed the audit the moment they could.
_ID_DIGITS = r"[1-9][0-9]{0,2}"

# AND AN ID IS A SLUG WHILE THE BRANCH THAT WRITES IT IS OPEN (D72, rewritten 2026-09-11).
# A number cannot be allocated on a branch, because the allocation's whole input — what main
# has taken — is not knowable until the merge. So a branch writes its heading as a slug and
# cites it that way, `scripts/claim-ids.py` substitutes the number at merge time, and the
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

# The step namespace has no letter in front of it — `step 7`, or the slug form while the
# branch is open — so the slug alone is the token and it carries no leading hyphen. Same floor.
_STEP_SLUG = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+"


def is_slug(identifier: str) -> bool:
    """True when `identifier` is an unclaimed slug rather than an allocated number.

    Takes the id WITHOUT its letter — `-merge-time-ids` or `137` — which is what every pattern
    here captures, and what `docs/map.py`'s `governed_by` and the build order both store.
    """
    return not str(identifier).lstrip("-").isdigit()

# A RUFF SUPPRESSION IS NOT A CITATION, AND AT THREE DIGITS IT LOOKS EXACTLY LIKE ONE.
# Three real lines carry a pydocstyle code whose number is three digits long —
# server/tcg_export.py:332, server/order_transport.py:610 and server/pipeline_routes.py:1643
# — and mccabe's complexity code joins them the moment anyone writes one. The two-digit cap
# could not reach their third digit, so widening it turns every one into a citation of an
# entry that does not exist. That is exactly why docs/DEBTS.md kept the cap rather than
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
# the split. Every row below used to open `docs/DECISIONS.md`; they open the directory now and
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
    """Every file holding a `## D<id>` entry, in corpus order. Empty if unreadable."""
    corpus = _corpus()
    if corpus is None:
        return []
    try:
        head = re.compile(r"^##\s+(D" + _ID_ANY + r")\b")
        return [p for p in corpus.files() if head.match(read(p).split("\n", 1)[0])]
    except Exception:
        return []


# AN EMPTY CORPUS IS A BROKEN CORPUS, NEVER A CLEAN ONE. This is the guard's own version of
# the failure it exists to catch: `decision structure` and `entry budget` iterate the entry
# files, so an unreadable directory gave them nothing to iterate and they reported `0 entries`
# in green. Measured by deleting one entry file — `decision ids` and `decision index` both
# went red, and those two passed over nothing while saying so in a sentence that reads like
# success. A row that cannot tell "nothing is wrong" from "nothing is known" is worse than no
# row, because it is believed.
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


def check_decision_ids(report: Report, docs: List[Path]) -> None:
    singles = {i for i, _, _ in decision_heading_lines_across(decision_files(), "D")}
    codes = decision_headings(ROOT / "docs" / "CODES-DECISIONS.md", "C")

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
                                f"docs/DECISIONS.md.",
                            )
                        )
                for digits in _CODES_DECISION_RE.findall(line):
                    if "C" + digits not in codes:
                        severity_findings.append(
                            Finding(
                                f"{rel(path)}:{number}",
                                f"cites C{digits}, which has no `## C{digits}` heading in "
                                f"docs/CODES-DECISIONS.md.",
                            )
                        )

    in_docs: List[Finding] = []

    # AN ID IS UNIQUE, AND NOTHING ASSERTED THAT UNTIL 2026-08-30 (D16, amended). Three
    # entries in `docs/DECISIONS.md` carried ONE number, written by three sessions that each
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
        ([ROOT / "docs" / "CODES-DECISIONS.md"], "C"),
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
    # THE APP WAS NOT SCANNED AT ALL UNTIL 2026-08-30 (D72). `python_files()` is every `.py`
    # in the tree, and the row below said "citations in .py all resolve" — accurately, and
    # over half the citations. `app/` holds hundreds more in `.ts`, `.tsx` and `.css`
    # comments, and a dangling id in one of them resolved to nothing and was reported by
    # nothing. Same severity as the Python row and for the same reason: `D2` could plausibly
    # be a variable, and a false positive that blocks a commit is worse than a printed line.
    # `.js` JOINED THEM ON 2026-09-11, the same way `.ts` did on 2026-08-30 and for the same
    # reason: it was the one real extension in this tree that cites decisions and nothing
    # opened it. `app/eslint.config.js` alone carries six of them, every one valid — so this
    # widen reports nothing today, which is the point. What it would have caught is what a
    # branch found by hand the day `scripts/claim-ids.py` landed: that file was outside the
    # CLAIMER's suffix set too, so a SLUG written there survived the merge and became a
    # citation of an entry that had just been given a number. Both sets gained `.js` together.
    #
    # ONE HAYSTACK, BUILT BEFORE THE SCAN, so the row can declare how many files it read.
    # It was two `scan()` calls with the count nowhere, which is the shape that let this
    # file print `ok` over a walk that had found nothing.
    code_haystack = python_files() + _walk(ROOT, (".ts", ".tsx", ".css", ".js"))
    scan(code_haystack, in_code)

    report.add("decision ids", MECHANICAL, in_docs,
               f"{len(singles)} D + {len(codes)} C headings",
               scanned=len(singles) + len(codes))
    # Code is advisory: `C1` or `D2` could plausibly be a variable one day, and a false
    # positive that blocks a commit is worse than one that prints a line.
    report.add("decision ids in code", ADVISORY, in_code,
               "citations in .py, .ts, .tsx, .css and .js all resolve",
               scanned=len(code_haystack))


# --------------------------------------------------------- the gates corpus as a directory

# THE GATES CORPUS IS `docs/gates/`, ONE FILE PER RECORD IN ONE FOLDER PER KIND (LANE D,
# 2026-09-16) — `scripts/gates_corpus.py`'s own docstring has the shape. Every row below that
# used to open `docs/GATES.md` opens the corpus's reassembled text instead, through
# `gates_text()`, and asserts exactly what it asserted before: `gates_sections()`,
# `check_id_claims()`, `check_map_gate_status` (folded into `check_build_order`) and
# `check_build_order_mirror()` are unmodified beyond that one substitution, because the
# reassembly is byte-identical to the file they used to read (`scripts/split-gates.py
# --verify`), so every regex written against the monolith keeps matching.
#
# READ FAIL-OPEN, the same rule `_corpus()` states for decisions and `browser scope` states
# for its own module: a missing `scripts/gates_corpus.py` or a broken manifest makes
# `gates_text()` answer "", never a partial or wrong reassembly, so a caller that already
# treated `not exists(docs/GATES.md)` as "nothing to check" keeps that exact behaviour rather
# than crashing on an import it cannot make.


def _gates_corpus():
    """scripts/gates_corpus.py, or None."""
    return _sibling("gates_corpus.py")


def gates_text() -> str:
    """The gates corpus as one text — `docs/GATES.md` in every reader's eyes, whether the
    bytes come from the stub (never, since the split) or from `docs/gates/`'s reassembly."""
    corpus = _gates_corpus()
    if corpus is None:
        return ""
    try:
        return corpus.text()
    except Exception:
        return ""


# THE FLOOR IS PINNED HERE TOO, on the same reasoning `split-gates.py --selftest` gives for
# pinning its own: a parser finding nothing over a renamed heading or a broken manifest must
# read as BROKEN, never as a clean tree with nothing to reconcile. `check_gates_structure`
# is this row's mechanical half; `make gates-selftest` is the corpus's own completeness proof
# and is not duplicated here.
_GATES_MIN_TESTS = 9
_GATES_MIN_RUNS = 5
_GATES_MIN_SHIPPED = 15


def check_gates_structure(report: Report) -> None:
    """The gates corpus reads as non-empty and self-consistent, in both directions.

    Mirrors `decision index`'s own floor: an unreadable corpus, a manifest naming a file that
    is gone, or a regex that stopped matching after a heading moved must never look like a
    corpus with nothing wrong in it. `make gates-selftest` (`scripts/split-gates.py
    --selftest`) proves the same non-vacuity claim from the split side; this row proves it
    from the READER side — `gates_corpus.tests()`/`.runs()`/`.steps()` — so a regression in
    either one is caught by the other.
    """
    corpus = _gates_corpus()
    if corpus is None:
        report.add("gates structure", MECHANICAL,
                   [Finding("scripts/gates_corpus.py",
                             "does not exist or failed to import. docs/GATES.md's corpus "
                             "cannot be read at all, which every row below this one silently "
                             "treats as \"nothing to check\" rather than \"broken\".")])
        return
    findings: List[Finding] = []
    try:
        tests = corpus.tests()
        runs = corpus.runs()
        shipped = corpus.steps("shipped")
        open_steps = corpus.steps("open")
        unregistered = corpus.unregistered()
    except Exception as exc:
        report.add("gates structure", MECHANICAL,
                   [Finding("docs/gates/ORDER.json", f"unreadable: {exc}")])
        return
    if len(tests) < _GATES_MIN_TESTS:
        findings.append(Finding(
            "docs/gates/contract/",
            f"the manifest names only {len(tests)} harness-contract entries; expected at "
            f"least {_GATES_MIN_TESTS} (T1..T9). Either a real test was deleted, or the "
            f"`### Tn` reader stopped matching a renamed heading — both are a broken corpus, "
            f"never a clean one.",
        ))
    if len(runs) < _GATES_MIN_RUNS:
        findings.append(Finding(
            "docs/gates/gate-runs/",
            f"the manifest names only {len(runs)} gate-run entries; expected at least "
            f"{_GATES_MIN_RUNS} (Gate A, Gate B, Box 2, Gate C, the per-run reading).",
        ))
    if len(shipped) < _GATES_MIN_SHIPPED:
        findings.append(Finding(
            "docs/gates/steps/",
            f"the manifest names only {len(shipped)} shipped steps; expected at least "
            f"{_GATES_MIN_SHIPPED}.",
        ))
    overlap = sorted(set(shipped) & set(open_steps))
    if overlap:
        findings.append(Finding(
            "docs/gates/ORDER.json",
            f"step id(s) {overlap} are listed under BOTH shipped and open. A step is in "
            f"exactly one list — the list IS the status, the same rule `build order mirror` "
            f"already applies to docs/map.py's SHIPPED and OPEN.",
        ))
    for name in unregistered:
        head = (corpus.DIRECTORY / name).read_text(encoding="utf-8").split("\n", 1)[0] if \
            (corpus.DIRECTORY / name).exists() else ""
        if not (head.startswith("### ") or head.startswith("## ")):
            findings.append(Finding(
                f"docs/gates/{name}",
                "is on disk but not in ORDER.json, and its first line is not a heading — "
                "this is not a branch adding a new record; the file is malformed.",
            ))
    report.add("gates structure", MECHANICAL, findings,
               f"{len(tests)} contract entries, {len(runs)} run entries, "
               f"{len(shipped)} shipped + {len(open_steps)} open steps",
               scanned=len(tests) + len(runs) + len(shipped) + len(open_steps))


# ------------------------------------------------------------------ ids are claimed at merge

# A BRANCH DOES NOT TAKE A NUMBER (D140). The allocation's only input is what main
# has taken, and a branch cannot have that: every renumber in this repo's history is one
# branch reading `origin/main`, taking the next free id, and being wrong the moment another
# branch merged first. Thirteen of those are recorded in D72, and D16 carries three entries
# numbered `## D50` at once. So a branch writes a SLUG and `scripts/claim-ids.py` substitutes
# the number inside `make merge`, against main as it stands then.
#
# THIS ROW REPLACED `renumbered ids` AND `vacated ids`, WHICH ARE DELETED. Both existed to
# repair a renumber — the first named every site and blocked none of them, the second blocked
# the half that was provably the branch's own line. A branch that never takes a number never
# vacates one, so both guarded a path that no longer exists. D72 keeps its account of the
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
# NOT `\bstep `: a hyphen is a non-word character, so `\b` fires INSIDE `runs-step` and
# a React className pairing two such words reads as a citation of the second one.
# Measured on app/src/RunPanel.tsx:165, which is the only such pair in the tree and was
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

    COMMIT EQUALITY IS THE DETACHED-HEAD RULE AND NOTHING ELSE (D143). A NAMED
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
    codes = ROOT / "docs" / "CODES-DECISIONS.md"

    unclaimed: List[str] = []
    for path in decision_files() + [codes]:
        if not exists(path):
            continue
        for number, line in enumerate(read(path).splitlines(), start=1):
            loose = _LOOSE_SLUG_HEADING.match(line)
            if not loose:
                continue
            if not _STRICT_SLUG_HEADING.match(line):
                findings.append(Finding(
                    f"{rel(path)}:{number}",
                    f"`{loose.group(1)}` is not a claimable id, so this heading is not an "
                    f"entry: no row reports on it, no citation of it resolves, and "
                    f"`scripts/claim-ids.py` will not allocate it a number. A slug is two or "
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
            "docs/decisions/",
            "main carries {0} unclaimed id: {1}.\n"
            "  A slug is a branch's placeholder and `make merge` is what turns it into a "
            "number (D140). One on main means a claim half-landed — every "
            "citation of it now resolves to nothing.\n"
            "  Repair: `python3 scripts/claim-ids.py --ref origin/main --write` on a branch, "
            "then a pull request.".format(
                len(unclaimed), ", ".join(f"`{name}`" for name in unclaimed)),
        ))

    where = "main" if on_main() else "this branch"
    report.add("id claims", MECHANICAL, findings,
               scanned=len(unclaimed),
               summary="{0} unclaimed id(s) on {1}{2}".format(
                   len(unclaimed), where,
                   ", claimed at the merge" if unclaimed and not on_main() else ""))


# --------------------------------------------------- the claimer speaks the same vocabulary

# TWO DECLARATIONS AND A READER, this repo's standing answer to a shape it keeps meeting.
# `scripts/claim-ids.py` cannot be imported here — this file parses rather than imports so it
# never runs project code, and it is what gates every commit — so the slug grammar is written
# once in each and reconciled. A widen that reaches one of them leaves the other refusing an
# id the first just allocated, which is silent in both directions.

CLAIMER = ROOT / "scripts" / "claim-ids.py"


def check_claim_vocabulary(report: Report) -> None:
    findings: List[Finding] = []
    if not exists(CLAIMER):
        report.add("claim vocabulary", MECHANICAL,
                   [Finding(rel(CLAIMER), "does not exist, so no branch can claim an id.")])
        return
    theirs = literals_from_module(CLAIMER).get("SLUG")
    # `_ID_SLUG` is the same grammar with the leading hyphen that separates it from the
    # letter; `_STEP_SLUG` is it bare, because a step wears no letter.
    if theirs != _STEP_SLUG:
        findings.append(Finding(
            rel(CLAIMER),
            "declares SLUG as {0!r}; scripts/docs-audit.py's `_STEP_SLUG` is {1!r}.\n"
            "  The auditor decides what is an id and the claimer decides what gets a number. "
            "Disagreeing, one of them refuses an id the other just allocated.".format(
                theirs, _STEP_SLUG)))
    elif _ID_SLUG != "-" + _STEP_SLUG:
        findings.append(Finding(
            "scripts/docs-audit.py",
            "`_ID_SLUG` is not `_STEP_SLUG` with the separating hyphen in front of it: "
            "{0!r} against {1!r}.".format(_ID_SLUG, _STEP_SLUG)))
    report.add("claim vocabulary", MECHANICAL, findings,
               "one slug grammar, declared in the auditor and in the claimer",
               # Two declarations, and the row exists because they can disagree: the
               # claimer's SLUG and this file's _STEP_SLUG / _ID_SLUG pair.
               scanned=2)


# ------------------------------------------------------------------------- env vars

_ENV_RE = re.compile(r"\b(PKMNSCAN_[A-Z0-9_]+|POKEMONTCG_API_KEY|ANTHROPIC_API_KEY)\b")


_HAYSTACK: Optional[str] = None


def code_haystack() -> str:
    """Everything that is not markdown, concatenated. Built once."""
    global _HAYSTACK
    if _HAYSTACK is not None:
        return _HAYSTACK
    parts: List[str] = []
    for path in python_files():
        parts.append(read(path))
    for name in ("Makefile", ".env.example"):
        candidate = ROOT / name
        if exists(candidate):
            parts.append(read(candidate))
    for path in _walk(ROOT / "scripts", (".sh", "pre-commit")):
        parts.append(read(path))
    for path in _walk(ROOT / ".claude", (".json",)):
        parts.append(read(path))
    _HAYSTACK = "\n".join(parts)
    return _HAYSTACK


# D60's two rows. Both read docs/DECISIONS.md by hard-coded path, so they answer on every
# run rather than only when that file is staged — the same asymmetry check_map and
# check_pass_criteria already have, and for the same reason: a broken heading there breaks
# every consumer, not only the commit that wrote it.
#
# ENTRY_BUDGET is twice the median entry rather than a picked round number. An entry at twice the
# median is one that should have cited a neighbor instead of re-arguing it, which is that entry's
# own rule.
#
# IT TRACKS THE CORPUS DELIBERATELY, AND IT HAS BEEN RE-DERIVED ONCE. Set at 12,000 against a median
# of 6,374; re-derived 2026-09-05 to 15,437 against a median of 7,718, measured over 100 entries with
# `prose-guard.entries()` — which counts CHARACTERS, so a byte count taken with `.encode()` reads
# three entries higher and is the wrong ruler. The corpus grew 21% and the constant did not, so the
# row was reporting 21 entries over when the rule it states would have reported 10.
#
# RE-DERIVING IS NOT THE SAME AS RAISING, and the difference is worth writing down because the next
# session will be tempted by the easier one. The number is a FUNCTION of the corpus and this restores
# it to that function; moving it because a particular entry is inconvenient would be the other thing.
# If it is re-derived again, this comment gains another date rather than losing this one — a ceiling
# that has moved twice with no record of either is a ceiling nobody can argue with.
ENTRY_BUDGET = 15437


def _sibling(name: str):
    """A script under scripts/ as a module, or None.

    Imported rather than reimplemented: prose-guard.py already replicates
    decision-context.py's three selectors, and a second copy here is the drift this file
    exists to catch. The filenames have hyphens, hence importlib. Returns None on any
    failure — a missing sibling must cost the rows that need it, never the whole audit.
    """
    path = ROOT / "scripts" / name
    if not path.exists():
        return None
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(name.replace("-", "_")[:-3], path)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module
    except Exception:  # noqa: BLE001 - a broken sibling must not take the audit down
        return None


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


_ID_UNCLAIMED_RE = re.compile(r"^D" + _ID_SLUG + r"$")


def _is_unclaimed(ident: str) -> bool:
    """A branch's own not-yet-merged slug, never a real number.

    `ident` ALREADY CARRIES ITS LEADING `D` — this function's callers both read it out of
    `want`/`got`, whose own regexes capture the whole `D<id>` token as one group. Prepending
    a second `D` here was the first version's bug: it made every slug fail this match and
    silently disabled the exemption below, in the one place a self-test built against a
    fabricated shape (ids with no leading letter) could not catch it.

    D140: a branch does not take a decision number until `make merge` claims one against
    main as it stands then, and `scripts/index-decisions.py:normalize` regenerates BOTH
    `docs/decisions/ORDER.json` and this index from the headings that exist AFTER that
    substitution, in the same commit. So a slug heading that has not yet been claimed is
    never going to be the thing this row is checking against — the next read of `corpus`
    after a claim sees the number, not the slug — and requiring a session to hand-type a
    line for it into CLAUDE.md before that moment bought nothing but the conflict this
    check exists to prevent: every open PR touching one shared block at once, on every
    single commit that adds an entry.
    """
    return bool(_ID_UNCLAIMED_RE.match(ident))


def _decision_index_findings(
    want: List[Tuple[str, str]], got: List[Tuple[str, str]]
) -> List[Finding]:
    """The comparison itself, pure so `--self-test` can drive it without a filesystem.

    `want` is every `## D<id> — <title>` heading in the corpus, in manifest order; `got` is
    what CLAUDE.md's fenced index block currently lists. An id absent from `got` is only
    ever tolerated when `_is_unclaimed` says so — everything else that used to fail here
    still fails exactly the same way.
    """
    findings: List[Finding] = []
    if not got:
        findings.append(Finding("CLAUDE.md", "no decision index found. D60 requires one."))
        return findings
    want_ids = [i for i, _ in want]
    got_ids = [i for i, _ in got]
    for ident in [i for i in want_ids if i not in got_ids]:
        if _is_unclaimed(ident):
            continue
        findings.append(Finding("CLAUDE.md", f"`{ident}` has a heading but is not in the index."))
    for ident in [i for i in got_ids if i not in want_ids]:
        findings.append(Finding("CLAUDE.md", f"the index lists `{ident}`, which has no heading."))
    titles = dict(want)
    for ident, title in got:
        if ident in titles and titles[ident] != title:
            findings.append(Finding(
                "CLAUDE.md",
                f"`{ident}`'s index line reads {title!r} and its heading reads "
                f"{titles[ident]!r}. The heading is the source.",
            ))
    if got_ids != [i for i in want_ids if i in got_ids]:
        findings.append(Finding("CLAUDE.md", "the index is not in heading order."))
    return findings


def check_decision_index(report: Report) -> None:
    """CLAUDE.md's index against docs/DECISIONS.md's headings.

    D60 dropped the `@` prefix, so that file is no longer loaded in full and the index is
    the only thing a session sees without opening it. An index that has drifted is worse
    than none, because it is believed — the argument D17 makes for auditing docs/map.py
    exactly as hard as it is trusted.

    AN UNCLAIMED SLUG IS EXEMPT FROM "MUST APPEAR", AND THAT IS THE WHOLE FIX. A branch adds
    its entry's heading in its OWN file and nothing else — `docs/decisions/ORDER.json` was
    already tolerant of this (`decisions_corpus.order()`'s docstring: "an unregistered entry
    is corpus content, not an error"), but this row was not, so every branch still had to
    hand-type its slug into CLAUDE.md's shared index to stay green — the second collision the
    directory split (D160) was supposed to remove, wearing a different file's name. Measured
    the day this landed: 25 of the last 40 merges touched `docs/decisions/ORDER.json`, and
    every open PR's own index edit went stale the instant any OTHER PR merged first, because
    each was computed against an `origin/main` that had already moved. The entry recording
    this fix has its own slug and cites itself by filename rather than in prose, for exactly
    the reason its own next paragraph gives.

    A CONCRETE EXAMPLE SLUG IN THIS DOCSTRING WOULD HAVE BECOME A CITATION, so there is none
    here — the same trap D178's own entry records under "It caught its own author twice": an
    example spelled in the shape this file's own extractor reads is read by it. Every id in
    this function's self-test is a synthetic non-slug number instead, for that reason.

    MECHANICAL. Both sides are ids and titles: there is nothing here a later session could
    reasonably disagree with, which is D16's test for what may block.

    NOT a generator, and this deliberately does not open D18's seam list. It computes what
    the index should say and compares; it never writes. That is D18's own write-time versus
    check-time split, with only the check half built.
    """
    claude = ROOT / "CLAUDE.md"
    corpus = decisions_text()
    if not exists(claude) or not corpus:
        report.add("decision index", MECHANICAL,
                   [Finding("CLAUDE.md", "cannot read the index or the entries.")])
        return

    # THE CORPUS IN MANIFEST ORDER, which is the order the entries sat in when they were one
    # file. This row has always reconciled the index against the headings IN ORDER, and the
    # split had to keep that meaning exactly — `docs/decisions/ORDER.json` is the order, not
    # the filesystem's, because three chunks in it are not entries and sorting by name would
    # move them.
    want = [
        (m.group(1), m.group(2).strip())
        for m in (re.match(r"^##\s+(D" + _ID_ANY + r")\s*[—-]\s*(.+)$", line)
                  for line in corpus.split("\n"))
        if m
    ]
    # The index is the first fenced block whose lines all start `D<n> `. Located by shape
    # rather than by a heading, so re-titling the Map section cannot silently unhook it.
    got: List[Tuple[str, str]] = []
    fenced, block = False, []
    for line in read(claude).split("\n"):
        if line.lstrip().startswith("```"):
            if fenced and block and all(re.match(r"^D" + _ID_ANY + r"\s", b) for b in block if b.strip()):
                got = [(b.split(None, 1)[0], b.split(None, 1)[1].strip())
                       for b in block if b.strip()]
                break
            fenced, block = not fenced, []
            continue
        if fenced:
            block.append(line)

    findings = _decision_index_findings(want, got)
    report.add("decision index", MECHANICAL, findings,
               f"{len(got)} indexed, matching {len(want)} headings",
               scanned=len(want))


def check_entry_budget(report: Report) -> None:
    """Entry size, reported and never blocked.

    ADVISORY on D16's own test: a long entry is a judgement call rather than something
    provably wrong, and a blocking row here would teach `--no-verify`, which switches off
    the three opsec rules in the same hook. It exists because a rewrite is spent in two
    days without it — growth over the two days before D60 was +45,580 and +44,460 tokens,
    80% of it new entries.
    """
    guard = _prose_guard()
    if guard is None:
        report.add("entry budget", ADVISORY,
                   [Finding("scripts/prose-guard.py", "not readable; sizes unchecked.")])
        return
    # MECHANICAL here even though the row itself is ADVISORY: a long entry is a judgement
    # call, but a corpus that cannot be read at all is not.
    if corpus_is_empty(report, "entry budget", MECHANICAL):
        return
    findings = [Finding(f.where, f.message)
                for target in decision_files()
                for f in guard.check_budget(target, ENTRY_BUDGET)]
    sized = [e for target in decision_files() for e in guard.entries(read(target))]
    total = sum(len(e.body) for e in sized)
    report.add("entry budget", ADVISORY, findings,
               f"{total:,} bytes of entries, {len(findings)} over {ENTRY_BUDGET:,}",
               scanned=len(sized))


def check_debts_headings(report: Report) -> None:
    """Every `## ` heading in `docs/DEBTS.md` is one `_debts_section` can address.

    That helper matches `## <n> — ` and returns None otherwise, and BOTH its consumers
    tolerate a None — one with `or ""`, one with an early return. So a heading written in
    any other shape is not a failure, it is a section that silently does not exist, and
    every row reading that file inherits it.

    MEASURED 2026-09-11: sections 20 to 24 were written `## <n>. ` — five of the file's
    twenty-three live sections, invisible to the only reader the audit has for it, with
    every row green throughout. Normalized the same day under `D149`;
    this row is what stops the next one being written that way.

    MECHANICAL on D16's test: a heading either parses or it does not, which is the same
    standard `decision structure` is held to. It says nothing about what a section CONTAINS
    — that is the check `docs/DEBTS.md` section 25 measured and declined to build.
    """
    target = ROOT / "docs" / "DEBTS.md"
    if not exists(target):
        report.add("debts headings", MECHANICAL,
                   [Finding("docs/DEBTS.md", "does not exist.")])
        return

    findings: List[Finding] = []
    seen: Dict[int, int] = {}
    total = 0
    for lineno, line in enumerate(read(target).split("\n"), 1):
        if not line.startswith("## "):
            continue
        total += 1
        good = re.match(r"^## (\d+) — \S", line)
        if good is None:
            findings.append(Finding(
                f"docs/DEBTS.md:{lineno}",
                f"`{line[:60]}` is not the `## <n> — <title>` shape "
                f"`_debts_section` matches, so this section cannot be addressed by any "
                f"row that reads this file, and asking for it returns None rather than "
                f"failing.",
            ))
            continue
        number = int(good.group(1))
        if number in seen:
            findings.append(Finding(
                f"docs/DEBTS.md:{lineno}",
                f"section {number} is also the heading at line {seen[number]}; "
                f"`_debts_section({number})` returns the FIRST and the second is "
                f"unreachable.",
            ))
            continue
        seen[number] = lineno

    report.add("debts headings", MECHANICAL, findings,
               f"{total} headings, every one addressable by `_debts_section`",
               scanned=total)


def _debts_section(number: int) -> Optional[str]:
    """The body of one `## <n> — ...` section of `docs/DEBTS.md`, or None if it is not there.

    Matched on the heading's NUMBER rather than its wording: the titles in that file are
    sentences and get edited, and a check keyed to a sentence would fail on a rewrite that
    changed nothing it cares about.
    """
    text = read(ROOT / "docs" / "DEBTS.md")
    start = re.search(rf"^## {number} — ", text, re.M)
    if start is None:
        return None
    rest = text[start.end() :]
    nxt = re.search(r"^## \d+ — ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


_SERVER_CLASS_RE = re.compile(r"^class CaptureServer\((\w+)\):", re.M)
_HANDLER_TIMEOUT_RE = re.compile(r"^    timeout = (\d+)$", re.M)
_BACKLOG_RE = re.compile(r"^    request_queue_size = (\d+)$", re.M)
_SLOTS_RE = re.compile(r"^REQUEST_SLOTS = (\d+)$", re.M)

# WHAT SECTION 11 HAS TO SAY, AND IN WHAT SHAPE. Each row is (what, code pattern, code shape,
# DOC-SIDE ANCHOR, the published form). The anchor is the half that was missing: it captures
# the figure from a position that names the fact, so the comparison is between two CLAIMS
# rather than between a number and a section that happens to contain it.
_CONCURRENCY_FACTS = (
    ("the base class", _SERVER_CLASS_RE, "class CaptureServer(<base>)",
     re.compile(r"class CaptureServer\((\w+)\)"), "class CaptureServer(<base>)"),
    ("the handler's socket timeout", _HANDLER_TIMEOUT_RE, "timeout = <seconds>",
     re.compile(r"CaptureHandler\.timeout = (\d+)"), "CaptureHandler.timeout = <seconds>"),
    ("the accept backlog", _BACKLOG_RE, "request_queue_size = <n>",
     re.compile(r"request_queue_size = (\d+)"), "request_queue_size = <n>"),
    ("the bound on executing requests", _SLOTS_RE, "REQUEST_SLOTS = <n>",
     re.compile(r"REQUEST_SLOTS = (\d+)"), "REQUEST_SLOTS = <n>"),
)


def _close_header_owner() -> Optional[str]:
    """The method that sends `Connection: close`, or None if nothing does.

    A NAME AND NOT A LINE NUMBER, because the name is the fact section 11 rests on. The pool
    is only safe over HTTP/1.1 because a worker's life is one REQUEST rather than one
    connection, and what makes that true is that every response carries this header. Sending
    it from `_send` was not enough — `_photo`'s 304 branch answers a conditional GET by hand
    and never goes through `_send` — so it moved to `end_headers`, which every response
    reaches by construction. Which method it is IS the guarantee: back in `_send`, the same
    header is a convention any new route can forget.
    """
    try:
        tree = ast.parse(read(ROOT / "server" / "capture_server.py"))
    except (SyntaxError, OSError):
        return None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            func = inner.func
            if not isinstance(func, ast.Attribute) or func.attr != "send_header":
                continue
            literals = [
                arg.value.lower()
                for arg in inner.args
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            ]
            if literals[:2] == ["connection", "close"]:
                return node.name
    return None


# Where a claim about the history's readers may live, and where its readers may live. Both
# lists are the production tree only: the harness reads the history constantly and correctly,
# and counting those would make the number meaningless.
_HISTORY_READER_ROOTS = ("server", "store", "pipeline", "cli", "identify", "geometry", "codes")
# BOTH WORD ORDERS. The name comes before the claim in `\`f\` — the only reader of X` and after
# it in `the only reader of X is \`f\``, and the first pattern written here caught only the
# first. Section 8 carried the second form for three weeks after the identical sentence was
# corrected twice elsewhere, which is the whole argument for reading prose by shape rather than
# fixing the instances somebody happened to grep for.
# WHOLE-FILE AND NOT LINE BY LINE, which is the second thing this pattern got wrong. Every
# markdown file in this repo wraps at 96 columns, so a claim of any length is USUALLY split
# across two lines — section 8's instance sat on a wrap with "the" ending one line and "only
# reader" starting the next, and a line-at-a-time reader cannot see it. A checker over prose
# that reads lines is checking typography, not sentences. `.` is excluded so a match cannot
# run past the end of its own sentence.
_SOLE_READER_RE = re.compile(
    r"`([A-Za-z_][A-Za-z0-9_]*)`[^.]{0,40}?the\s+only\s+reader"
    r"|the\s+only\s+reader[^.]{0,60}?is\s+`([A-Za-z_][A-Za-z0-9_]*)`",
    re.S,
)


def _history_readers() -> List[str]:
    """Every production call of the store's `history()`, as `path:line in function`.

    ZERO-ARGUMENT CALLS ONLY, and that is the whole disambiguation rather than a heuristic:
    `Store.history()` takes none, and `pipeline/pricehistory.py`'s unrelated method of the
    same name takes a product and a range. Matching on the name alone counts two price-history
    calls as readers of the card history and makes the number a lie in the other direction.
    """
    readers: List[str] = []
    for root in _HISTORY_READER_ROOTS:
        base = ROOT / root
        if not exists(base):
            continue
        for path in _walk(base, (".py",)):
            try:
                tree = ast.parse(read(path))
            except SyntaxError:
                continue
            owner: Dict[int, str] = {}
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for inner in ast.walk(node):
                        line = getattr(inner, "lineno", None)
                        if line is not None:
                            owner.setdefault(line, node.name)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not isinstance(func, ast.Attribute) or func.attr != "history":
                    continue
                if node.args or node.keywords:
                    continue
                where = owner.get(node.lineno, "<module>")
                if where == "history":  # the definition in store/, not a call of it
                    continue
                readers.append(f"{rel(path)}:{node.lineno} in {where}")
    return sorted(readers)


# The three roots the plan names, in the order they are read. server/ is a FLAT
# directory (no subpackages as of 2026-09-12 — capture_server.py, pipeline_routes.py,
# codes_routes.py, order_transport.py, ports.py, shipping_routes.py, tcg_export.py,
# tcg_import.py), so `_walk(ROOT / "server", (".py",))` is exactly "server/*.py" and
# never needs to recurse into a package that does not exist yet. `store/master.py` and
# `cli/resolve.py` are named as single files because the plan is explicit that only
# `master.py` (the Inventory/Card schema) is in scope inside `store/` — `store/rows.py`,
# `store/db.py` and `store/queues.py` all touch rows too, but not `inventory.cards`
# directly, and widening the walk to all of `store/` would flag `Rows` itself defining
# `.values()`/`.items()` as their OWN implementation, which is not a call site at all.
_UNSCOPED_WALK_ROOTS: Tuple[Path, ...] = (
    ROOT / "server",
)
_UNSCOPED_WALK_SINGLE_FILES: Tuple[Path, ...] = (
    ROOT / "store" / "master.py",
    ROOT / "cli" / "resolve.py",
)

# The three method names that always materialise every row when called on something
# ending in `.cards` (`Rows` is a `MutableMapping`; these three take no filter argument
# under any Rows signature — see store/rows.py:213-266), plus `select`, which only
# materialises everything when called with NO keyword arguments (a keyword is a filter:
# `equals` in `Rows.select`).
_UNSCOPED_METHODS = frozenset({"values", "items", "distinct"})


def _enclosing_functions(tree: ast.AST) -> Dict[int, str]:
    """line number -> the name of the FunctionDef/AsyncFunctionDef that contains it.

    Same shape as `_history_readers`'s own inline dict-building loop above, pulled out
    here because this scanner needs it twice (once per file) and gains nothing from
    inlining it a second time.
    """
    owner: Dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                line = getattr(inner, "lineno", None)
                if line is not None:
                    owner.setdefault(line, node.name)
    return owner


def _cards_chain(node: ast.AST) -> bool:
    """Does this call's receiver end in `.cards`? `inventory.cards`, `self.cards`,
    `store.read().inventory.cards` — any depth, only the last hop matters."""
    return isinstance(node, ast.Attribute) and node.attr == "cards"


def _inventory_like(node: ast.AST) -> bool:
    """Does this call's receiver look like an `Inventory` instance? Heuristic, and named
    as one: matches a bare `inventory` name or a `.inventory` attribute, which is the
    variable name this repo uses everywhere an `Inventory` is bound (`Store().read().inventory`,
    `self.inventory`). This is what keeps `to_payload()` from also matching
    `book.to_payload()` / `entry.to_payload()` elsewhere in the same files, which are a
    different class's method of the same name."""
    if isinstance(node, ast.Name):
        return node.id == "inventory"
    if isinstance(node, ast.Attribute):
        return node.attr == "inventory"
    return False


def unscoped_walk_sites(paths: Sequence[Path]) -> List[Tuple[str, int, str, str]]:
    """Every call in `paths` that materialises the whole `inventory.cards` collection.

    Returns (path relative to ROOT, line number, enclosing function name, shape) tuples,
    where shape is one of "values", "items", "distinct", "select", "to_payload". Pure —
    no Report, no filesystem side effects beyond reading `paths` — so `--self-test` can
    hand it a synthetic fixture file and assert on the return value directly, the same
    shape `_payload_keys` and `mechanism_refs` are tested in already.

    WHAT THIS CANNOT SEE, and it says so rather than pretending completeness:
    `store/rows.py:177`'s degradation — a `where()`/`select()` call that LOOKS scoped but
    answers from a Python-side list because an earlier call in the same request already
    materialised everything — is invisible here. This function reads one file at a time
    with no notion of a request's call order, so it cannot tell a `where()` that hits the
    index from one that is quietly a full scan because of what ran before it in the same
    handler. Item 2 removes the degradation itself; this row is a static shape reader and
    will keep reporting a `where()`-only handler as clean before and after that fix,
    correctly, because the shape on the page never changes — only what it costs at
    runtime does.
    """
    sites: List[Tuple[str, int, str, str]] = []
    for path in paths:
        if not exists(path):
            continue
        try:
            tree = ast.parse(read(path))
        except SyntaxError:
            continue
        owner = _enclosing_functions(tree)
        where = rel(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue
            fname = owner.get(node.lineno, "<module>")
            if func.attr in _UNSCOPED_METHODS and _cards_chain(func.value):
                sites.append((where, node.lineno, fname, func.attr))
            elif func.attr == "select" and _cards_chain(func.value) and not node.keywords:
                sites.append((where, node.lineno, fname, "select"))
            elif func.attr == "to_payload" and _inventory_like(func.value):
                sites.append((where, node.lineno, fname, "to_payload"))
    return sites


def check_unscoped_walk(report: Report) -> None:
    """Every full-table read of `inventory.cards`, against an allowlist that starts at
    the 2026-09-12 census and may only shrink.

    docs/specs/store-scaling.md §0: almost every non-capture handler in `server/`
    materialises the whole `cards` table and then does per-card work over it, and at
    50,000 cards several of those routes cost seconds rather than milliseconds. §3 item 1
    is this row: land the guard BEFORE any of the six PRs that remove a full-table read,
    so each of them is checked against something rather than landing with no reader — the
    exact shape `docs/GATES.md` step 7's own finding names, one register down.

    THREE KINDS OF DISAGREEMENT, exactly `check_storage_keys`'s shape:
      - a site this file scans and finds, not on the allowlist: a NEW full-table read.
      - an allowlist entry naming a (path, function, shape) this scan does not find: a
        REMOVED site whose allowlist entry was not deleted in the same commit — this is
        the failure mode item 1's own spec text calls out by name ("a removed site is
        removed from the list in the same PR or the row reports a stale allowlist entry").
      - the allowlist's length disagreeing with `UNSCOPED_WALK_EXPECTED`: the same pinned-
        number discipline `check_rule_enforcement` uses, so a mutation cannot silently
        drop an entry and leave the printed count claiming coverage it no longer has.

    `do_inventory`'s `to_payload()` call is the one entry that can never be removed: the
    owner ruled (docs/specs/store-scaling/00-phases.md) that `GET /inventory` stays on the
    wire, unused, rather than being deleted once item 2 lands a scoped `GET
    /inventory/<box>`. Nothing in this function treats it specially — it is simply an
    entry nothing will ever delete, which is why `UNSCOPED_WALK_EXPECTED`'s floor never
    reaches zero.

    WHAT IT CANNOT SEE: `store/rows.py:177`'s runtime degradation (a call that reads
    scoped in the source and answers unscoped at runtime because an earlier call in the
    same request already loaded everything) — see `unscoped_walk_sites`'s own docstring,
    which item 2 is what actually removes. This row reads Python source shapes, never
    request traces.
    """
    server_files = _walk(_UNSCOPED_WALK_ROOTS[0], (".py",))
    found = set(unscoped_walk_sites(server_files + list(_UNSCOPED_WALK_SINGLE_FILES)))
    allowed = UNSCOPED_WALK_ALLOWED
    findings: List[Finding] = []

    for path, line, fname, shape in sorted(found):
        if (path, fname, shape) not in allowed:
            findings.append(Finding(
                f"{path}:{line}",
                f"`{fname}` calls `.{shape}(...)` on a collection that ends in "
                f"`.cards` (or `to_payload()` on an `Inventory`), materialising every "
                f"row in the store.\n"
                f"  If this is a genuine new full-table read, either scope it — a "
                f"`where(...)`/`select(..., **filter)` with an index, or a per-box read "
                f"through `records_in` — or add `(\"{path}\", \"{fname}\", \"{shape}\") "
                f"to `UNSCOPED_WALK_ALLOWED` and raise `UNSCOPED_WALK_EXPECTED` by one, "
                f"with the reason in the commit message. docs/specs/store-scaling.md §0 "
                f"is why this matters: every one of these costs proportionally more as "
                f"the store grows, and none of it shows up until it does.",
            ))

    scanned_keys = {(path, fname, shape) for path, _, fname, shape in found}
    for path, fname, shape in sorted(allowed):
        if (path, fname, shape) not in scanned_keys:
            findings.append(Finding(
                path,
                f"the allowlist names `{fname}` (`.{shape}(...)`) and this scan finds no "
                f"such call there any more.\n"
                f"  Either the function moved to a shape this reader does not recognise, "
                f"or a full-table read was genuinely removed and the allowlist entry was "
                f"not deleted with it. Delete the entry and lower "
                f"`UNSCOPED_WALK_EXPECTED` in the same commit, or say why the shape "
                f"changed and update the tuple.",
            ))

    if len(allowed) != UNSCOPED_WALK_EXPECTED:
        findings.append(Finding(
            "scripts/docs-audit.py -> UNSCOPED_WALK_ALLOWED",
            f"has {len(allowed)} entries where {UNSCOPED_WALK_EXPECTED} are pinned. The "
            f"count is the plan's progress meter (docs/specs/store-scaling.md §3): raise "
            f"`UNSCOPED_WALK_EXPECTED` only alongside a NEW site you are deliberately "
            f"keeping (say why), and lower it in the same commit that deletes a site the "
            f"tree no longer has.",
        ))

    report.add(
        "unscoped walk",
        MECHANICAL,
        findings,
        f"{len(found)} full-table reads of inventory.cards found, "
        f"{len(allowed)} allowed (pinned at {UNSCOPED_WALK_EXPECTED})",
        scanned=len(found),
    )


def _pipeline_imports(path: Path) -> List[Tuple[int, str]]:
    """`(line, spelling)` for every `import pipeline...` / `from pipeline...` in one file.

    MODULE-LEVEL OR INSIDE A FUNCTION — a lazy `from pipeline import join` hidden in a
    function body is the exact shape store-scaling item 8 shipped (`store/db.py:
    _add_search_index`) and it does not show at the top of the file, so `ast.walk` over
    the whole tree (not just `tree.body`) is what a grep-the-top-lines reader would miss.
    A relative import (`from . import x`, `node.level > 0`) is never `pipeline` and is
    skipped without inspecting `node.module`, which is `None` for a bare `from . import x`.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []
    found: List[Tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pipeline" or alias.name.startswith("pipeline."):
                    found.append((node.lineno, f"import {alias.name}"))
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module
            and (node.module == "pipeline" or node.module.startswith("pipeline."))
        ):
            names = ", ".join(alias.name for alias in node.names)
            found.append((node.lineno, f"from {node.module} import {names}"))
    return found


def check_import_layering(report: Report) -> None:
    """`store/` may not import `pipeline/` (D63): the arrow runs one way only.

    `docs/decisions/D063-…md` and `docs/map.py`'s `pipeline/orders.py` entry both record
    it in the same words — "store/ imports nothing from pipeline/, so there is no cycle" —
    because `pipeline/orders.py`, `pipeline/readings.py` and `pipeline/selection.py` all
    import `store`, and a `store -> pipeline -> store` cycle is exactly the shape that
    keeps a session from being able to reason about which module can see which.

    NOTHING ENFORCED THIS MECHANICALLY UNTIL NOW, WHICH IS WHY IT WAS BROKEN THE SAME DAY
    IT WAS WRITTEN DOWN AGAIN. Store-scaling item 8 (search on FTS5) needed
    `pipeline/join.py`'s `join_key`/`display_number` to populate two new indexed columns
    and added `store/master.py: from pipeline import join` (module-level) and
    `store/db.py: from pipeline import join as _join` (inside `_add_search_index`) —
    `make check` was fully green through both, because nothing read this rule. The fix
    (this same PR) moved the three pure functions (`join_key`, `display_number`,
    `strip_set_code`) to a new leaf module, `store/numbers.py` (stdlib only), and
    `pipeline/join.py` imports them back and re-exports under the same names so every
    existing caller of `join.join_key` etc. is unaffected — CLAUDE.md's "a rule with no
    reader is advice" (D173), applied to itself: the fix is not this row alone.

    A LAZY IMPORT INSIDE A FUNCTION IS CAUGHT THE SAME AS A MODULE-LEVEL ONE, because that
    is exactly the shape the defect took (`store/db.py:_add_search_index`'s
    `from pipeline import join as _join`, several hundred lines into the file, inside a
    function body — invisible to a reader who only checks the top of the file).

    WHAT IT CANNOT SEE: an import reached through a third module (`store/x.py` imports
    `store/y.py`, which imports `pipeline/`) — this row scans only the text of `store/*.py`
    files for a direct `pipeline` reference, not the transitive closure of what a module
    ends up able to reach. `store/master.py`/`store/db.py`/`store/numbers.py` are the only
    modules under `store/` this repo has ever needed `pipeline/` symbols from, so a
    transitive leak would still show up as a NEW direct import somewhere the day it
    happens, which this row would catch then.
    """
    store_files = _walk(ROOT / "store", (".py",))
    findings: List[Finding] = []
    for path in store_files:
        for lineno, spelling in _pipeline_imports(path):
            findings.append(Finding(
                f"{rel(path)}:{lineno}",
                f"`{spelling}` — store/ may not import pipeline/ (D63: the arrow runs the "
                f"other way, pipeline/orders.py and friends import store/). Move the "
                f"symbol(s) needed into a leaf module under store/ (store/numbers.py is "
                f"the precedent) and have pipeline/ import them back and re-export, or "
                f"resolve the value in the caller before it reaches store/.",
            ))
    report.add(
        "import layering",
        MECHANICAL,
        findings,
        f"{len(store_files)} store/ files scanned, 0 import pipeline/" if not findings
        else f"{len(store_files)} store/ files scanned, {len(findings)} import pipeline/",
        scanned=len(store_files),
    )


# The two routes that write a claim. D70 gives a card a `product`, D101 says a claim a screen
# names is a claim a screen can fix, and these are the two doors that ruling opened.
_CLAIM_WRITERS = ("do_put_card", "do_put_box_claims")


def _payload_keys(function: ast.AST) -> Set[str]:
    """The literal keys this handler decodes out of its request body.

    `if "<key>" in payload:` is the shape every claim in both handlers is written in, so the
    decode table is readable without running anything. It is a narrow reader on purpose: a
    handler that switched to `payload.get(name)` over a loop would present an empty table
    here, which is why the row below reports an EMPTY table as a finding rather than as
    agreement.
    """
    keys: Set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        if not isinstance(node.ops[0], ast.In):
            continue
        if not (isinstance(node.left, ast.Constant) and isinstance(node.left.value, str)):
            continue
        target = node.comparators[0]
        if (getattr(target, "id", None) or getattr(target, "attr", None)) == "payload":
            keys.add(node.left.value)
    return keys


def check_claim_decode(report: Report) -> None:
    """The card writer and the box writer decode the same claim vocabulary.

    `product` was in `do_put_card`'s table from D70 and in `do_put_box_claims`'s from never.
    The route did not refuse it — it decoded every key it knew and answered 200 with
    `"applied": 0, "unchanged": N`, which reads exactly like "the box already said that". So
    a correction typed into the box editor was accepted, reported as a success, and dropped,
    and `#/codes` went on drawing the banner that sent you there.

    Nothing detected it because the two handlers are 160 lines apart and agree about five of
    six keys. The docstring on the second one asserted the tables matched, which is the
    failure D16 is about: a claim of agreement, in prose, beside the disagreement.

    **Set equality, in both directions.** A key one door takes and the other does not is the
    defect regardless of which door is ahead — a claim writable per-card but not per-box is
    the bug that was here, and one writable per-box but not per-card is a box that can assert
    something no card can carry. If a claim genuinely belongs to one scope, the answer is a
    named exception argued in the code, not a silent asymmetry.
    """
    try:
        tree = ast.parse(read(ROOT / "server" / "capture_server.py"))
    except (SyntaxError, OSError):
        report.add("claim decode", MECHANICAL, [
            Finding("server/capture_server.py", "does not parse; the decode tables cannot be read.")
        ], "")
        return

    tables: Dict[str, Set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in _CLAIM_WRITERS:
            tables[node.name] = _payload_keys(node)

    findings: List[Finding] = []
    for name in _CLAIM_WRITERS:
        if name not in tables:
            findings.append(Finding(
                "server/capture_server.py",
                f"`{name}` is gone, and this row reconciles the two claim writers against "
                f"each other. Re-point it, or retire it with the route.",
            ))
        elif not tables[name]:
            findings.append(Finding(
                "server/capture_server.py",
                f"`{name}` decodes no `\"key\" in payload` at all. Either the handler changed "
                f"shape — in which case this reader is now blind and must be re-pointed — or "
                f"it takes nothing, which is not what a claim writer does.",
            ))
    if not findings and len(tables) == len(_CLAIM_WRITERS):
        card, box = (tables[name] for name in _CLAIM_WRITERS)
        for missing, where, other in ((card - box, _CLAIM_WRITERS[1], _CLAIM_WRITERS[0]),
                                      (box - card, _CLAIM_WRITERS[0], _CLAIM_WRITERS[1])):
            for key in sorted(missing):
                findings.append(Finding(
                    "server/capture_server.py",
                    f"`{other}` decodes `{key}` and `{where}` does not.\n"
                    f"  The route that ignores it still answers 200, reporting the write it "
                    f"did not do as a no-op. Add the branch, or argue the exception where a "
                    f"reader of both will see it.",
                ))
    report.add(
        "claim decode",
        MECHANICAL,
        findings,
        f"{len(_CLAIM_WRITERS)} claim writers, one vocabulary "
        f"({len(tables.get(_CLAIM_WRITERS[0], ())) } keys)",
        scanned=len(_CLAIM_WRITERS),
    )


# The client function that writes each server handler's claims. D101 opened the second door;
# this is what keeps both of them speaking the same vocabulary as the route behind them.
_CLAIM_CLIENTS = {"do_put_card": "updateCard", "do_put_box_claims": "applyBoxClaims"}

# Keys a client sends that are SCOPE rather than a claim. `indices` says which positions in
# the box the claim applies to; it is not something a card can carry, and the server reads it
# outside the decode table this row compares against.
_CLIENT_SCOPE_KEYS = {"indices"}

_PAYLOAD_ASSIGN_RE = re.compile(r"payload\.([a-z_][a-z0-9_]*)\s*=")


def _ts_function_body(source: str, name: str) -> Optional[str]:
    """The text of one exported function, comments stripped.

    Bounded by the next top-level `export` rather than by brace counting: a `{` inside a
    template literal or a regex would defeat the counter, and this file has both. The overrun
    a loose bound could cause is a key attributed to the wrong function, which the comparison
    below would report as a finding — so the failure is loud rather than silent.
    """
    stripped = _strip_ts_comments(source)
    start = stripped.find(f"function {name}")
    if start < 0:
        return None
    following = stripped.find("\nexport ", start)
    return stripped[start:following if following > 0 else len(stripped)]


def check_claim_clients(report: Report) -> None:
    """The client sends the keys the route decodes, on both doors.

    D101 ruled that a claim a screen names is a claim a screen can fix, and answered it with
    two doors: the inventory claim editor and an inline correction on `#/codes`. Two doors to
    one claim is two chances for the vocabulary to drift, and the drift is silent in the
    direction that matters — the server decodes what it knows and answers 200 for the rest.

    So this reads the wire keys each client function actually assigns and compares them to the
    handler's own decode table, across the language boundary. `app/src/server.ts` is the only
    place a client call is written (CLAUDE.md), which is what makes one reader enough.

    **A key the client sends and the server does not decode is the worse half**, and it is the
    one a type checker cannot see: `tsc` proves the object is well-formed, never that anything
    on the other end reads it. A key the server decodes and no client sends is the milder
    failure — a capability with no door, which is a rule this repo already has words for.
    """
    client_source = ROOT / "app" / "src" / "server.ts"
    if not exists(client_source):
        report.add("claim clients", MECHANICAL, [
            Finding("app/src/server.ts", "is gone, and it is the only place a client call is written.")
        ], "")
        return
    try:
        tree = ast.parse(read(ROOT / "server" / "capture_server.py"))
    except (SyntaxError, OSError):
        report.add("claim clients", MECHANICAL, [
            Finding("server/capture_server.py", "does not parse; the decode tables cannot be read.")
        ], "")
        return

    handlers = {
        node.name: _payload_keys(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name in _CLAIM_CLIENTS
    }
    source = read(client_source)
    findings: List[Finding] = []
    checked = 0
    for handler, client in _CLAIM_CLIENTS.items():
        body = _ts_function_body(source, client)
        if body is None:
            findings.append(Finding("app/src/server.ts", f"no `{client}` to read."))
            continue
        if handler not in handlers:
            findings.append(Finding("server/capture_server.py", f"no `{handler}` to read."))
            continue
        checked += 1
        sent = set(_PAYLOAD_ASSIGN_RE.findall(body)) - _CLIENT_SCOPE_KEYS
        decoded = handlers[handler]
        for key in sorted(sent - decoded):
            findings.append(Finding(
                "app/src/server.ts",
                f"`{client}` sends `{key}` and `{handler}` decodes no such key.\n"
                f"  The route answers 200 and writes nothing. A type checker cannot see this: "
                f"it proves the body is well-formed, never that anything reads it.",
            ))
        for key in sorted(decoded - sent):
            findings.append(Finding(
                "app/src/server.ts",
                f"`{handler}` decodes `{key}` and `{client}` never sends it.\n"
                f"  A capability no screen can reach is not built (CLAUDE.md's hard rule). "
                f"Send it, or retire the branch.",
            ))
    report.add(
        "claim clients",
        MECHANICAL,
        findings,
        f"{checked} client writers send exactly what their route decodes",
        scanned=checked,
    )


DETECT_RESULT = ROOT / "harness" / "results" / "detect.json"

# What `docs/DEBTS.md` section 6 publishes about the current scan, and where the number lives
# in `harness/results/detect.json`. Each is a (claim pattern, dotted path into the result).
#
# THE PHRASES ARE PART OF THE PIN. "photographs in the owner's six boxes" is THIS scan; D75's
# "three real boxes" is a different corpus measured on a different day, and CLAUDE.md's rule
# is that a measured number is evidence and is never rewritten to match a later tree. Matching
# on a bare integer would drag the 867 into this reconciliation and demand it change, which is
# precisely the corruption the rule forbids.
# EVERY COPY OF A FIGURE, NOT THE FIRST ONE SOMEBODY THOUGHT OF. Section 6 states the corpus
# size twice and the decline count twice, eight lines apart, and until 2026-09-05 this table
# pinned one of each. Measured: setting the twin at "photographs across six boxes" to 1,620 and
# the heading's "59 frames" to 61 leaves the section CONTRADICTING ITSELF about both — and the
# row reported `ok`, because the copies it reads were still right. A pinned figure with an
# unpinned twin is worse than no pin: it licenses the belief that the section is reconciled.
_DETECT_CLAIMS = (
    (re.compile(r"([\d,]+) photographs in the owner's six boxes"), "overall.photographs"),
    (re.compile(r"([\d,]+) photographs across six boxes"), "overall.photographs"),
    (re.compile(r"the crop guard declined ([\d,]+)"), "overall.declined"),
    (re.compile(r"the ([\d,]+) frames nobody has looked at"), "overall.declined"),
    (re.compile(r"\*\*The declines are entirely boxes 3 and 4\*\* \(([\d,]+) of ([\d,]+), and "
                r"([\d,]+) of ([\d,]+)\)"),
     ("per_box.box3.declined", "per_box.box3.photographs",
      "per_box.box4.declined", "per_box.box4.photographs")),
)


def _dotted(data: object, path: str) -> Optional[int]:
    for step in path.split("."):
        if not isinstance(data, dict) or step not in data:
            return None
        data = data[step]
    return data if isinstance(data, int) else None


def check_detector_standing(report: Report) -> None:
    """The detector figures section 6 publishes are the ones its scanner wrote.

    `scripts/score-detect.py` walks the owner's real photographs and writes
    `harness/results/detect.json`. Section 6 quotes that run in prose. Nothing reconciled the
    two, and the prose is what a session reads before deciding whether the crop guard's two
    constants still fit — a decision about whether 59 real cards get cropped or refused.

    **The result file is the authority and the prose is the reader**, which is the same
    direction `check_criteria_evidence` runs and for the same reason: one of them is written
    by a measurement and the other by a person summarising it. A re-run that moves a count
    should fail this row until the sentence moves with it.

    **D75's 867-photograph corpus is deliberately out of scope.** It is a different scan of a
    different set of boxes on a different day, it has no entry in this file, and CLAUDE.md
    forbids rewriting a measured number to match a later tree. The patterns above pin the
    six-box phrasing so the two corpora cannot be confused for each other — which is a real
    risk here, because both are counts of the owner's photographs run through `detect_card`.
    """
    findings: List[Finding] = []
    if not exists(DETECT_RESULT):
        report.add("detector standing", MECHANICAL, [
            Finding("harness/results/detect.json",
                    "is absent, and docs/DEBTS.md section 6 quotes it. Re-run "
                    "`scripts/score-detect.py`, or strike the figures it published.")
        ], "")
        return
    try:
        result = json.loads(read(DETECT_RESULT))
    except ValueError:
        report.add("detector standing", MECHANICAL, [
            Finding("harness/results/detect.json", "is not readable JSON.")
        ], "")
        return

    section = _debts_section(6) or ""
    checked = 0
    for pattern, target in _DETECT_CLAIMS:
        match = pattern.search(section)
        if match is None:
            findings.append(Finding(
                "docs/DEBTS.md",
                f"section 6 no longer publishes the figure this row reads "
                f"(`{pattern.pattern}`). Either the sentence was reworded past its own "
                f"guard, or the claim is gone and this pin should go with it.",
            ))
            continue
        targets = target if isinstance(target, tuple) else (target,)
        for group, path in zip(match.groups(), targets):
            checked += 1
            published = int(group.replace(",", ""))
            measured = _dotted(result, path)
            if measured is None:
                findings.append(Finding(
                    "harness/results/detect.json",
                    f"has no `{path}`, which section 6 publishes as {published}.",
                ))
            elif published != measured:
                findings.append(Finding(
                    "docs/DEBTS.md",
                    f"section 6 says {published} where `{path}` in "
                    f"harness/results/detect.json measured {measured}.\n"
                    f"  The result file is what the scanner wrote; the prose is a person's "
                    f"summary of it. Update the sentence.",
                ))
    report.add(
        "detector standing",
        MECHANICAL,
        findings,
        f"{checked} published figures against harness/results/detect.json",
        scanned=checked,
    )


def check_sole_reader(report: Report) -> None:
    """"The only reader of the history" is a countable claim, and it is wrong.

    Three places say `_state_before_sale` is the only thing in this repo that reads the
    history — two comments in `server/capture_server.py` and one line of
    `docs/specs/order-flow.md`. Measured 2026-09-05 the count is three, and the more useful
    half of the finding is that **`_state_before_sale` is not one of them**: it takes a
    sequence of events as an argument and scans it. The readers are `_answer_origin`,
    `_origin` and `_reverse_stand_down`.

    That distinction is what the claim was load-bearing for. A comment that says one function
    is the only reader is telling the next session it can reason about the history's access
    pattern by reading one function — and D26's reversal, D83's third door and the sale
    origin all go through a different one. The comment was true when it was written and two
    features walked past it.

    **The claim is the subject, not the count.** Nothing here says three readers is too many;
    a checker cannot hold that (D16). It holds that a sentence asserting a number agrees with
    the number, which is the only half that is mechanical.
    """
    readers = _history_readers()
    functions = {reader.rsplit(" in ", 1)[-1] for reader in readers}
    findings: List[Finding] = []
    sources = list(markdown_files())
    for root in _HISTORY_READER_ROOTS:
        base = ROOT / root
        if exists(base):
            sources.extend(_walk(base, (".py",)))
    for path in sources:
        text = read(path)
        for match in _SOLE_READER_RE.finditer(text):
            number = text.count("\n", 0, match.start()) + 1
            named = match.group(1) or match.group(2)
            if named in functions and len(readers) == 1:
                continue
            listed = "\n    ".join(readers) or "(none found)"
            reads = "does not read it at all" if named not in functions else "is one of them"
            findings.append(
                Finding(
                    f"{rel(path)}:{number}",
                    f"claims `{named}` is the only reader of the history; there are "
                    f"{len(readers)}, and `{named}` {reads}.\n"
                    f"    {listed}",
                )
            )
    report.add(
        "sole reader",
        MECHANICAL,
        findings,
        f"{len(readers)} history readers, every claim about them counts right",
        scanned=len(readers),
    )


def check_server_concurrency(report: Report) -> None:
    """`docs/DEBTS.md` section 11 names the capture server's concurrency; the code decides it.

    WHY THIS ROW EXISTS, which is the same argument the section it guards makes about itself.
    Every fact in section 11 was already in the tree, inside two comments in
    `server/capture_server.py`. On 2026-09-04 a session diagnosed a wedge from `.serve/*.log`
    without opening that file, told the owner the server was single-threaded, and proposed
    `ThreadingHTTPServer` as the fix — the class it has been built on all along. Moving the
    argument into a document a session actually reads is only half the repair: a document
    nothing reconciles goes stale exactly the way those comments did, and this file spends a
    section on that difference.

    So the literals the section publishes are read out of the code and compared.

    **THE PARAGRAPH THAT STOOD HERE PREDICTED SOMETHING THAT DID NOT HAPPEN, and it is kept
    as a correction rather than quietly swapped.** It said a worker pool "changes the base
    class, and this row then FAILS until the section is rewritten" — the row built to go red
    on the change it documents. The pool landed on 2026-09-04 and the base class did not
    change: `CaptureServer` still subclasses `ThreadingHTTPServer` and submits from
    `process_request` to a `ThreadPoolExecutor`. The row stayed green through the exact change
    it claimed it would catch. What actually carries the pool's safety is a header, which no
    literal here was reading, so a fifth fact was added below rather than the prediction being
    re-worded into something it could still claim.

    Nothing here judges whether the concurrency is right. It judges whether the document and the
    code agree about what it IS, which is the only half a checker can hold honestly (D16).

    **TWO PUBLICATIONS, AS OF THIS ROW'S SECOND WIDENING. Only `docs/DEBTS.md` §11 had a
    reader, and CLAUDE.md publishes the same four attributed literals** — `class
    CaptureServer(ThreadingHTTPServer)`, `request_queue_size = 128`, `CaptureHandler.timeout
    = 15`, `REQUEST_SLOTS = 4` — in the file every session loads before it touches the server
    whose collapse at 150 connections is measured. A retune that fails this row via §11 while
    CLAUDE.md goes on saying 4 is a document that is wrong in the more-read of the two places.
    Both are compared now, and a finding names WHICH file it is about.

    **The fifth fact stays scoped to §11 on purpose**, and this is a narrowing of the
    proposal that asked for it: the fifth is the METHOD NAME that sends `Connection: close`,
    and CLAUDE.md deliberately publishes the header without naming the method — §11 is where
    the mechanism is argued. Demanding the name in both would have failed on an unchanged
    tree, which is not a defect it found, only prose it wanted. Nothing is uncovered by the
    narrowing: §11 is the only file that makes the claim, so it is the only file that can go
    stale on it.

    The bare integers are safe from both anchors for the reason the comment below records:
    CLAUDE.md:1121's "sized this at 12" and "80 Playwright browsers, 969 threads" are
    measurements, and an ATTRIBUTED anchor can neither be satisfied nor tripped by a loose
    number.
    """
    source = read(ROOT / "server" / "capture_server.py")
    section = _debts_section(11)
    findings: List[Finding] = []
    compared = 0

    if section is None:
        report.add(
            "server concurrency",
            MECHANICAL,
            [
                Finding(
                    "docs/DEBTS.md",
                    "section 11 is gone, and it is what publishes the capture server's "
                    "concurrency. Restore it, or delete this row with it — a check whose "
                    "subject has left is the vacuous green this file is about.",
                )
            ],
            "",
        )
        return

    # The two publications of these facts, in reading order. `where` is what a finding
    # names and `called` is what the sentence calls itself, so a message reads the same
    # whichever file is wrong.
    publications: List[Tuple[str, str, str]] = [
        ("docs/DEBTS.md", "section 11", section),
    ]
    claude_md = ROOT / "CLAUDE.md"
    claude_text = read(claude_md) if exists(claude_md) else None
    if claude_text is None:
        findings.append(
            Finding(
                "CLAUDE.md",
                "is not there, and it publishes this server's concurrency facts to every "
                "session that loads it. Nothing else reconciles that copy.",
            )
        )
    else:
        publications.append(("CLAUDE.md", "the capture-server bullet", claude_text))

    for what, pattern, shape, anchor, published in _CONCURRENCY_FACTS:
        found = pattern.search(source)
        if found is None:
            findings.append(
                Finding(
                    "server/capture_server.py",
                    f"{what} no longer matches `{shape}`, so this row cannot read what "
                    f"`docs/DEBTS.md` section 11 claims. Re-point the pattern, and check the "
                    f"section still describes the server that exists.",
                )
            )
            continue
        value = found.group(1)
        # ATTRIBUTED, NOT MERELY PRESENT — and the two rewrites this line has had are the
        # argument for the shape it is in now.
        #
        # It began as `value in section`, a SUBSTRING test: retuning the handler timeout from
        # 15 to 5 left this row green because `5` occurs inside `15`, `128` and `338%`. That
        # was fixed to a word-boundaried search, and the fix was too narrow to hold. The
        # question `\b4\b` asks is *does this number appear anywhere in section 11*, and that
        # section publishes about fifty-five distinct bare integers — every sweep column, every
        # latency, every thread count. So almost any retune lands on a number the section
        # already says for some other reason.
        #
        # MEASURED, 2026-09-05: swapping the two constants — `CaptureHandler.timeout` to 4 and
        # `REQUEST_SLOTS` to 15 — leaves the document wrong about BOTH and sizes the pool at
        # the value this very section calls "within noise of the unbounded server it was meant
        # to improve on". The row reported `ok`. A guard that passes while the thing it pins is
        # inverted is not a weak guard, it is a decoration.
        #
        # So the section must publish the figure in a form that ATTRIBUTES it to this fact —
        # `REQUEST_SLOTS = 4`, not a 4 in a table of slot counts — and the value it attributes
        # is what gets compared. Coincidence cannot satisfy that; only agreement can.
        for where, called, text in publications:
            compared += 1
            said = anchor.search(text)
            if said is None:
                findings.append(
                    Finding(
                        where,
                        f"{called} never attributes a value to {what}. It has to publish one as "
                        f"`{published}` for this row to tell agreement from coincidence — a bare "
                        f"`{value}` somewhere in it is not a claim about {what}, and this "
                        f"row used to accept one.",
                    )
                )
            elif said.group(1) != value:
                findings.append(
                    Finding(
                        where,
                        f"{called} publishes {what} as `{published.replace('<n>', said.group(1)).replace('<seconds>', said.group(1)).replace('<base>', said.group(1))}` "
                        f"and `server/capture_server.py` says `{value}`. The code is the authority; "
                        f"the document is the published account of this server's concurrency, and it "
                        f"is now describing one that is gone.",
                    )
                )

    # The fifth fact, and the only one that is a NAME rather than a literal. Section 11 already
    # names `Connection: close`; what it did not name is where the header is sent from, and
    # that is the half the pool's safety actually rests on.
    owner = _close_header_owner()
    compared += 1
    if owner is None:
        findings.append(
            Finding(
                "server/capture_server.py",
                "nothing sends `Connection: close` any more. Section 11 says a worker's life "
                "is one REQUEST rather than one connection, and this header is what makes "
                "that true — without it four idle keep-alive connections hold all four "
                "workers and `make harness` does not fail, it HANGS.",
            )
        )
    elif re.search(rf"\b{re.escape(owner)}\b", section) is None:
        findings.append(
            Finding(
                "docs/DEBTS.md",
                f"section 11 does not name `{owner}`, which is where `Connection: close` is "
                f"sent from. The method is the guarantee: every response reaches "
                f"`end_headers` by construction, so no new route can forget the header, "
                f"which is not true of any single send site.",
            )
        )

    report.add(
        "server concurrency",
        MECHANICAL,
        findings,
        f"{compared} published facts against server/capture_server.py",
        scanned=compared,
    )


_SHIPPING_COLUMN_CLAIMS = (
    (Path("docs") / "specs" / "order-pipeline.md",
     re.compile(r"import file — \*\*([A-Za-z]+) columns\*\*")),
    (Path("harness") / "tests" / "t7_store_and_seams.py",
     re.compile(r"the header is the ([a-z]+) columns")),
)


def _pirateship_column_count() -> Optional[int]:
    """How many columns `pipeline/pirateship.py` actually writes, read out of the source.

    Parsed rather than imported: this checker runs from a bare `python3` on the commit path
    (D18) and importing the pipeline drags its dependencies in. Parsed rather than grepped
    because the count is a SUM — a tuple of named columns plus `STAMP_COLUMNS` — and a regex
    over either half alone answers the wrong question, which is the mistake the document made.

    Returns None when the shape is no longer `COLUMNS = (...) + STAMP_COLUMNS`, and the caller
    reports that rather than guessing: a checker that silently falls back to one half of a sum
    is the vacuous green this file exists to refuse.
    """
    try:
        tree = ast.parse(read(ROOT / "pipeline" / "pirateship.py"))
    except SyntaxError:
        return None

    tuples: Dict[str, int] = {}
    total: Optional[int] = None

    def target_name(node: ast.stmt) -> Optional[str]:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            return node.target.id
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            return node.targets[0].id
        return None

    for node in tree.body:
        name = target_name(node)
        if name is None:
            continue
        value = getattr(node, "value", None)
        if isinstance(value, ast.Tuple):
            tuples[name] = len(value.elts)
        elif (name == "COLUMNS" and isinstance(value, ast.BinOp)
              and isinstance(value.op, ast.Add)
              and isinstance(value.left, ast.Tuple)
              and isinstance(value.right, ast.Name)):
            named = len(value.left.elts)
            stamps = tuples.get(value.right.id)
            if stamps is not None:
                total = named + stamps

    return total


_ESTIMATE_READER = ROOT / "server" / "pipeline_routes.py"
_ESTIMATE_WRITER = ROOT / "cli" / "cmd_identify.py"
_ESTIMATE_PATTERN_NAME = "_ESTIMATE"
_ESTIMATE_PRODUCER = "_estimate"
#: What a rendered figure looks like when the sample is built. Any decimal would do; this
#: one is two places, which is what `_estimate` quantizes to.
_ESTIMATE_SAMPLE = "1.23"


def _compiled_assign(tree: ast.AST, name: str) -> Optional[Tuple[str, int]]:
    """(pattern, flags) of a module-level `NAME = re.compile(r"...", FLAG)`, or None.

    Read out of the source and compiled here, never imported: the rule this whole file is
    built on. Only `re.M` / `re.MULTILINE` is resolved, because that is the flag this pair
    turns on and a flag nobody can read is reported rather than guessed.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            continue
        call = node.value
        if not isinstance(call, ast.Call) or not call.args:
            return None
        first = call.args[0]
        if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
            return None
        flags = 0
        for extra in call.args[1:]:
            text = ast.unparse(extra) if hasattr(ast, "unparse") else ""
            if "M" in text or "MULTILINE" in text:
                flags |= re.M
        return first.value, flags
    return None


def _rendered_say(tree: ast.AST, producer: str) -> Optional[str]:
    """The line a `say(f"...")` whose f-string CALLS `producer` would print.

    ANCHORED ON THE CALL AND NEVER ON THE WORDING, which is the whole point: the defect is
    somebody rewording the sentence, so a reader that finds the site BY its wording cannot
    see the change it exists to catch. The producing call is the invariant.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "say") or len(node.args) != 1:
            continue
        joined = node.args[0]
        if not isinstance(joined, ast.JoinedStr):
            continue
        calls = {
            inner.func.id
            for inner in ast.walk(joined)
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name)
        }
        if producer not in calls:
            continue
        out: List[str] = []
        for part in joined.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                out.append(part.value)
            else:
                out.append(_ESTIMATE_SAMPLE)
        return "".join(out)
    return None


def check_estimate_wire(report: Report) -> None:
    """The money button's figure, against the string that produces it.

    **THE ONE PRESS IN THIS PRODUCT THAT SPENDS MONEY CARRIES ITS FIGURE IN THE LABEL
    (D33), AND THE FIGURE TRAVELS AS TEXT.** `cli/cmd_identify.py` prints `estimated cost
    $1.23` in its preflight; `server/pipeline_routes.py` scrapes that line with `_ESTIMATE`
    and serves the number as `estimate_usd`, which is what `#/runs` draws on the button.
    Two declarations of one fact, in two languages, with a regex as the seam.

    Reword that `say` line and `estimate_usd` goes null. Nothing fails: the estimate is not
    an outcome any test asserts, so the money gate loses its figure and every suite stays
    green. `grep -c "estimated cost\\|_ESTIMATE" scripts/docs-audit.py` returned **0**
    before this row — no check reconciled the pair.

    **THE SAMPLE IS BUILT AND MATCHED, rather than the two strings being compared.** The
    row renders what that `say` would print, with the interpolation standing in for a
    figure, and requires the regex to match it AND to capture the number. That is the
    question the wire actually asks; comparing the literal against the pattern's source
    text would be comparing two spellings of an intent.

    **ANCHORED ON THE PRODUCING CALL, never on the wording.** The site is the `say(f"...")`
    whose f-string calls `_estimate` — so a rewording is exactly what the row sees, which a
    reader that FOUND the site by its wording could not. It also keeps the second cost line
    out of it by construction: `cmd_identify` writes an actual invoice too, deliberately not
    anchored at `^estimated cost` (see the comment above it), and that one calls `cost.usd`.

    **Two absences, two findings.** A missing pattern and a missing producer are different
    repairs — one is the server's reader gone, one is the CLI's line gone — and reporting
    either as the other sends a session to the wrong file.
    """
    findings: List[Finding] = []
    compared = 0

    reader_tree = None
    if not exists(_ESTIMATE_READER):
        findings.append(Finding(rel(_ESTIMATE_READER), "does not exist."))
    else:
        try:
            reader_tree = ast.parse(read(_ESTIMATE_READER))
        except SyntaxError as exc:
            findings.append(Finding(rel(_ESTIMATE_READER), f"does not parse.\n{exc}"))

    writer_tree = None
    if not exists(_ESTIMATE_WRITER):
        findings.append(Finding(rel(_ESTIMATE_WRITER), "does not exist."))
    else:
        try:
            writer_tree = ast.parse(read(_ESTIMATE_WRITER))
        except SyntaxError as exc:
            findings.append(Finding(rel(_ESTIMATE_WRITER), f"does not parse.\n{exc}"))

    pattern = _compiled_assign(reader_tree, _ESTIMATE_PATTERN_NAME) if reader_tree else None
    rendered = _rendered_say(writer_tree, _ESTIMATE_PRODUCER) if writer_tree else None

    if reader_tree is not None and pattern is None:
        findings.append(Finding(
            rel(_ESTIMATE_READER),
            f"no module-level `{_ESTIMATE_PATTERN_NAME} = re.compile(r\"...\")` this row can "
            f"read.\n"
            f"  It is the seam the money button's figure travels through — the route scrapes "
            f"the CLI's preflight line with it and serves the number as `estimate_usd`. "
            f"Renamed or restructured, and nothing reconciles the pair while it is "
            f"unreadable.",
        ))
    if writer_tree is not None and rendered is None:
        findings.append(Finding(
            rel(_ESTIMATE_WRITER),
            f"no `say(f\"...\")` whose f-string calls `{_ESTIMATE_PRODUCER}()`.\n"
            f"  That line is what produces the figure `#/runs` puts on the press that spends "
            f"money. Either the print moved, or it stopped going through "
            f"`{_ESTIMATE_PRODUCER}` — and this row is anchored on the CALL precisely so a "
            f"reworded sentence is visible rather than invisible.",
        ))

    if pattern is not None and rendered is not None:
        compared = 1
        source, flags = pattern
        try:
            compiled = re.compile(source, flags)
        except re.error as exc:
            findings.append(Finding(
                rel(_ESTIMATE_READER),
                f"`{_ESTIMATE_PATTERN_NAME}` does not compile: {exc}",
            ))
        else:
            match = compiled.search(rendered)
            if match is None or not match.groups() or match.group(1) != _ESTIMATE_SAMPLE:
                findings.append(Finding(
                    rel(_ESTIMATE_WRITER),
                    "the line this prints is not the line the route can read.\n"
                    f"  prints:  {rendered!r}\n"
                    f"  pattern: {source!r}\n"
                    f"  captured: "
                    f"{(match.group(1) if match and match.groups() else None)!r}\n"
                    "  `estimate_usd` would be null, `#/runs` would draw a money button with "
                    "no figure on it, and every test would stay green — the estimate is not "
                    "an outcome any of them assert. Move both sides together.",
                ))

    report.add(
        "estimate wire",
        MECHANICAL,
        findings,
        "the preflight's cost line is the line `estimate_usd` reads",
        scanned=compared,
    )


def check_shipping_columns(report: Report) -> None:
    """The Pirate Ship import's column count, published in two files, decided by one.

    WHY THIS ROW EXISTS. `docs/specs/order-pipeline.md` said the renderer produced a file of
    TEN columns from 2026-08-30 until 2026-09-05. It produces twelve — nine named plus three
    rubber stamps — and `harness/tests/t7_store_and_seams.py` said twelve the whole time. Two
    documents in this repository disagreed about a number the code settles in one line, and
    nothing compared either to the code or to each other.

    It is `route census`'s argument in another lane: a published count with no reader is a
    claim that can only be contradicted by somebody happening to look. Note which way the
    error ran — the TEST was right and the SPEC was wrong, so "the tests would have caught it"
    is exactly the reasoning that let it stand for a week.

    A REWORD CANNOT SILENCE IT. A file that no longer carries a sentence this row can find is
    reported as unwatched rather than passing quietly, which is the failure mode a pattern-
    matched checker has and the one `route census` had to grow its own answer to.
    """
    total = _pirateship_column_count()
    findings: List[Finding] = []

    if total is None:
        report.add(
            "shipping columns",
            MECHANICAL,
            [
                Finding(
                    "pipeline/pirateship.py",
                    "`COLUMNS` is no longer `(<named>, ...) + STAMP_COLUMNS`, so this row "
                    "cannot count what the documents claim. Re-point it, and check both "
                    "sentences still describe the file the renderer writes.",
                )
            ],
            "",
        )
        return

    for path, pattern in _SHIPPING_COLUMN_CLAIMS:
        text = read(ROOT / path)
        found = pattern.search(text)
        if found is None:
            findings.append(
                Finding(
                    str(path),
                    "no sentence here matches the pattern watching this file's column count. "
                    "It was reworded past its own check, or the claim was removed — either "
                    "way the count is unwatched now. Re-point the pattern or drop the entry.",
                )
            )
            continue
        word = found.group(1).lower()
        said = _NUMBER_WORDS.get(word)
        if said is None:
            findings.append(
                Finding(str(path), f"`{found.group(1)} columns` is not a number this row knows.")
            )
        elif said != total:
            findings.append(
                Finding(
                    str(path),
                    f"says `{found.group(1)} columns` and `pipeline/pirateship.py` writes "
                    f"{total}. The code is the authority; the sentence is describing a file "
                    f"the renderer does not produce.",
                )
            )

    report.add(
        "shipping columns",
        MECHANICAL,
        findings,
        f"{len(_SHIPPING_COLUMN_CLAIMS)} published counts against pipeline/pirateship.py ({total})",
        scanned=len(_SHIPPING_COLUMN_CLAIMS),
    )


# `docs/specs/order-pipeline.md` §3 declares each work item's state in its own heading, and
# CLAUDE.md's pointer at that spec restates some of them. `NOT BUILT` leads the alternation so
# it is never read as a bare `BUILT`.
_WORK_ITEM_SPEC = Path("docs") / "specs" / "order-pipeline.md"
_WORK_ITEM_READER = Path("CLAUDE.md")
_WORK_ITEM_STATES = ("NOT BUILT", "BUILT", "SUPERSEDED", "DISCHARGED")
_WORK_ITEM_HEADING = re.compile(
    r"^### T(\w+) — .*?\.\s+(" + "|".join(_WORK_ITEM_STATES) + r")\b", re.M
)
# The reader's claim form: the item, an optional em-dash aside, then `is <state>`. Anchored on
# `is` because this repo strikes and annotates rather than deleting — "said T6 was BUILT until
# 2026-09-05" is the correction, not the claim, and must not be read as one.
_WORK_ITEM_CLAIM = re.compile(
    r"T(\w+)\b(?:\s*—[^—]*—)?\s+is\s+("
    + "|".join(_WORK_ITEM_STATES)
    + r"|unbuilt|deleted)\b",
    re.S,
)
_WORK_ITEM_SYNONYM = {"unbuilt": "NOT BUILT", "deleted": "SUPERSEDED"}
_WORK_ITEM_BULLET = "- `docs/specs/order-pipeline.md`"


def check_work_item_standing(report: Report) -> None:
    """Whether an order-pipeline work item is built is decided by its spec, not by the pointer.

    WHY THIS ROW EXISTS. `CLAUDE.md`'s pointer said *"Its T6 — an order DRIVING the inventory
    walk — is BUILT as of 2026-09-02 (D90), and the UNIT OF THE WRITE is the envelope"* until
    2026-09-05. D96 superseded that on 2026-09-04 and DELETED the code — `POST /orders/fill`,
    `do_order_fill`, `app/src/orderWalk.ts`, `OrderWalkBanner.tsx`/`.css` and harness T7's
    `check_order_fill` — so for three days the file a session loads first described a feature no
    longer in the tree, and described it in the present tense. `docs/map.py` had it right the
    whole time, which is the same asymmetry `shipping columns` found: one reader wrong, one
    right, nothing comparing them.

    IT IS `transport standing` ONE REGISTER OVER. There a module declares which calls have run;
    here a spec declares which work items are built, in its own §3 headings, and the pointer at
    that spec may not assert otherwise. The direction of the error is the one that costs a
    session: BUILT over deleted code sends somebody looking for a route that answers 404.

    SCOPED TO CLAUDE.md's ORDER-PIPELINE BULLET, WHICH IS NOT TIMIDITY. `T6` is overloaded in
    this repository — `harness/tests/t6_geometry.py` is a different T6 and the spec's own §3
    opens by saying so — and `docs/GATES.md` and `docs/map.py` carry dozens of references to it.
    A row reading a bare `T6` anywhere would be a false-positive machine, and a check that fires
    on correct prose teaches `--no-verify`, which switches off the three opsec rules in the same
    hook (D16).

    HISTORICAL PROSE IS DELIBERATELY NOT CAUGHT. The claim form is `T<n> ... is <state>`; "said
    T6 was BUILT until 2026-09-05" is the correction that replaced the defect and this repo
    strikes and annotates rather than deleting. Silence is allowed too — a bare cross-reference
    like "§3's T2b" asserts nothing. What is not allowed is asserting the opposite.

    A REWORD CANNOT SILENCE IT. A bullet carrying no claim this row can read is reported as
    unwatched rather than passing quietly.
    """
    findings: List[Finding] = []

    declared = {
        item: state for item, state in _WORK_ITEM_HEADING.findall(read(ROOT / _WORK_ITEM_SPEC))
    }
    if not declared:
        report.add(
            "work item standing",
            MECHANICAL,
            [
                Finding(
                    str(_WORK_ITEM_SPEC),
                    "§3's headings no longer end in a state — `### T<n> — <title>. BUILT` and "
                    "the rest — so nothing here declares what is built and the pointer at this "
                    "spec is unwatched. Restore the labels or re-point this row.",
                )
            ],
            "",
        )
        return

    text = read(ROOT / _WORK_ITEM_READER)
    start = text.find(_WORK_ITEM_BULLET)
    bullet = ""
    if start < 0:
        findings.append(
            Finding(
                str(_WORK_ITEM_READER),
                f"carries no `{_WORK_ITEM_BULLET}` bullet, so the pointer this row reads is "
                f"gone or renamed and every work-item claim in this file is unwatched.",
            )
        )
    else:
        end = text.find("\n- `", start + 1)
        bullet = text[start : end if end > 0 else len(text)]

    claims = _WORK_ITEM_CLAIM.findall(bullet)
    if bullet and not claims:
        findings.append(
            Finding(
                str(_WORK_ITEM_READER),
                "the order-pipeline bullet makes no `T<n> ... is <state>` claim this row can "
                "read. It was reworded past its own check, or the claims were dropped — either "
                "way the pointer's account of what is built is unwatched now.",
            )
        )

    for item, said in claims:
        state = _WORK_ITEM_SYNONYM.get(said, said)
        wanted = declared.get(item)
        if wanted is None:
            findings.append(
                Finding(
                    str(_WORK_ITEM_READER),
                    f"claims `T{item}` is {state}, and {_WORK_ITEM_SPEC} §3 declares no `T{item}` "
                    f"at all. It is {', '.join(sorted('T' + k for k in declared))} there.",
                )
            )
        elif state != wanted:
            findings.append(
                Finding(
                    str(_WORK_ITEM_READER),
                    f"says `T{item}` is {state} where {_WORK_ITEM_SPEC} §3 declares it "
                    f"{wanted}. The spec owns that standing; a pointer at it does not.",
                )
            )

    report.add(
        "work item standing",
        MECHANICAL,
        findings,
        f"{len(claims)} claims in {_WORK_ITEM_READER.name} against "
        f"{len(declared)} work items declared in §3",
        scanned=len(claims),
    )

# The spec's own sentence, and the two literals harness T7 asserts. The harness is the
# code-anchored end of this: `check_shipping_lane` runs the real router over the committed
# export and fails if either number moves, so a document reconciled against those literals is
# reconciled against the router by one hop rather than by a second copy of its rule.
_CERTAINTY_SPEC = Path("docs") / "specs" / "order-pipeline.md"
_CERTAINTY_HARNESS = Path("harness") / "tests" / "t7_store_and_seams.py"
_CERTAINTY_SPEC_CLAIMS = (
    re.compile(r"certain:\s+(\d+) of (\d+)\b"),
    re.compile(r"\*\*(\d+) of (\d+)\*\*: a published price"),
)
_CERTAINTY_HARNESS_COUNT = re.compile(r"and that is (\d+) of the (\d+)\b")
_CERTAINTY_DEFINITION = re.compile(r"return\s+self\.reason\s*==\s*VALUE_AT_THRESHOLD\b")


def check_router_certainty(report: Report) -> None:
    """`Routing.certain` over the committed export, published in the spec and asserted in T7.

    WHY THIS ROW EXISTS. `docs/specs/order-pipeline.md` §5 called `Routing.certain` "the split
    worth surfacing" from 2026-08-30 and never said what the split was, so the one number that
    separates a fact from an inference — 112 answered by a published price against a published
    threshold, out of 331 orders and 292 lanes — lived only in a harness assertion nobody
    reading the spec would find. It is stated in two places in that file now, and this row is
    what keeps both equal to what the harness asserts.

    IT IS `shipping columns` WITH ONE MORE HOP, AND THE HOP IS DELIBERATE. That row reads a
    count straight out of the code. This one cannot: the figure is not a literal anywhere in
    `pipeline/shipping.py`, it is the result of running the router over
    `fixtures/orders-shipping.csv`. Recomputing it here would put a second copy of the router's
    first rule in this checker, which is the second-renderer failure the spec's own sections 4
    and 5 spend paragraphs on. So the authority is `harness/tests/t7_store_and_seams.py`, which
    runs the real router over the real fixture and fails if either number moves.

    THE DEFINITION IS CHECKED TOO, because the count alone would survive the change that
    matters most. If `Routing.certain` ever stopped being exactly `reason ==
    VALUE_AT_THRESHOLD` — folding the weight proxy in, say — 112 could keep reading 112 while
    the sentence beside it became false. The fixture is committed and the router reads nothing
    else, so that is the only way this claim can rot without the harness going red first.

    A REWORD CANNOT SILENCE IT. A file carrying no sentence this row can find is reported as
    unwatched rather than passing quietly.
    """
    findings: List[Finding] = []

    source = read(ROOT / "pipeline" / "shipping.py")
    if not _CERTAINTY_DEFINITION.search(source):
        findings.append(
            Finding(
                "pipeline/shipping.py",
                "`Routing.certain` is no longer `return self.reason == VALUE_AT_THRESHOLD`. "
                "The published `112 of 331` is a count of the rows that reason answers, so "
                "widening or narrowing `certain` changes what the sentence means even when "
                "the number holds. Re-check both claims in "
                "docs/specs/order-pipeline.md and re-point this row.",
            )
        )

    harness_text = read(ROOT / _CERTAINTY_HARNESS)
    asserted = _CERTAINTY_HARNESS_COUNT.search(harness_text)
    if asserted is None:
        report.add(
            "router certainty",
            MECHANICAL,
            findings
            + [
                Finding(
                    str(_CERTAINTY_HARNESS),
                    "no longer asserts `and that is <n> of the <total>` for `Routing.certain`, "
                    "so this row has no authority to check the spec against. Re-point it, or "
                    "the two published figures are unwatched.",
                )
            ],
            "",
        )
        return

    certain, total = int(asserted.group(1)), int(asserted.group(2))
    spec_text = read(ROOT / _CERTAINTY_SPEC)
    for pattern in _CERTAINTY_SPEC_CLAIMS:
        found = pattern.search(spec_text)
        if found is None:
            findings.append(
                Finding(
                    str(_CERTAINTY_SPEC),
                    f"no sentence here matches `{pattern.pattern}`. The certainty split was "
                    f"reworded past its own check or removed — either way it is unwatched "
                    f"now. Re-point the pattern or drop the claim.",
                )
            )
            continue
        said, said_total = int(found.group(1)), int(found.group(2))
        if (said, said_total) != (certain, total):
            findings.append(
                Finding(
                    str(_CERTAINTY_SPEC),
                    f"says `{said} of {said_total}` where "
                    f"harness/tests/t7_store_and_seams.py asserts {certain} of {total} over "
                    f"the committed export. The harness runs the router; the sentence does "
                    f"not.",
                )
            )

    report.add(
        "router certainty",
        MECHANICAL,
        findings,
        f"{len(_CERTAINTY_SPEC_CLAIMS)} published splits against harness T7 "
        f"({certain} of {total})",
        scanned=len(_CERTAINTY_SPEC_CLAIMS),
    )


# The block `server/order_transport.py` records them under, and the section that rules on them.
_NOT_BUILT_MODULE = Path("server") / "order_transport.py"
_NOT_BUILT_SPEC = Path("docs") / "specs" / "order-pipeline.md"
_NOT_BUILT_HEADING = "WHAT IS DELIBERATELY NOT BUILT"
_NOT_BUILT_ENDPOINT = re.compile(r"^\s{4}(POST /orders\S*)\s", re.M)


def check_not_built_endpoints(report: Report) -> None:
    """The two TCGplayer writes this repo has ruled it does not make, listed in two files.

    WHY THIS ROW EXISTS. `server/order_transport.py` records two endpoints it deliberately
    does not call, and says in the same breath that it records them "so that adding them is
    visibly a change of policy rather than a change of code". That only works while the list
    is visible from the document that carries the ruling: the module cites
    `docs/specs/order-pipeline.md` §3 T5 for the policy, and §3 T5 quotes the module for the
    endpoints. Neither can be read without the other, and until 2026-09-05 only one of them
    held the list.

    WHAT WOULD ROT WITHOUT IT is not a number but a set. A third write endpoint added to the
    module's block and not to the spec leaves the spec understating what has been ruled
    against; one added to the spec and not the module names a policy over code that does not
    record it. Either way the "visibly a change of policy" claim stops being true, and nothing
    would say so — this is `transport standing`'s failure one register over, a standing the
    module declares against readers that quote it.

    IT COMPARES SETS AND NOT ORDER, because the spec quotes the block for the reader's benefit
    and the module writes it for its own; requiring the same order would fire on a formatting
    choice. A file carrying no block this row can find is reported as unwatched rather than
    passing quietly.
    """
    findings: List[Finding] = []
    module_text = read(ROOT / _NOT_BUILT_MODULE)
    head = module_text.find(_NOT_BUILT_HEADING)
    if head < 0:
        report.add(
            "not-built endpoints",
            MECHANICAL,
            [
                Finding(
                    str(_NOT_BUILT_MODULE),
                    f"carries no `{_NOT_BUILT_HEADING}` block, so the endpoints this repo has "
                    f"ruled against are recorded in the spec alone. Restore the block or "
                    f"re-point this row.",
                )
            ],
            "",
        )
        return

    # The block runs to the end of the module docstring; the endpoints are the indented lines.
    tail = module_text[head:]
    stop = tail.find('"""')
    declared = set(_NOT_BUILT_ENDPOINT.findall(tail[: stop if stop > 0 else len(tail)]))

    spec_text = read(ROOT / _NOT_BUILT_SPEC)
    quoted = set(_NOT_BUILT_ENDPOINT.findall(spec_text))

    if not declared:
        findings.append(
            Finding(
                str(_NOT_BUILT_MODULE),
                f"the `{_NOT_BUILT_HEADING}` block no longer lists an indented "
                f"`POST /orders...` line, so there is nothing for the spec to be checked "
                f"against.",
            )
        )
    if not quoted:
        findings.append(
            Finding(
                str(_NOT_BUILT_SPEC),
                "quotes no `POST /orders...` endpoint. §3 T5 rules on the writes this repo "
                "does not make and the module cites that section for the ruling; without "
                "the list here, adding one is a change of code that reads as nothing.",
            )
        )
    if declared and quoted and declared != quoted:
        only_module = sorted(declared - quoted)
        only_spec = sorted(quoted - declared)
        if only_module:
            findings.append(
                Finding(
                    str(_NOT_BUILT_SPEC),
                    "does not quote "
                    + ", ".join("`%s`" % n for n in only_module)
                    + f", which `{_NOT_BUILT_MODULE}` records as deliberately not built.",
                )
            )
        if only_spec:
            findings.append(
                Finding(
                    str(_NOT_BUILT_MODULE),
                    "does not record "
                    + ", ".join("`%s`" % n for n in only_spec)
                    + ", which the spec quotes as ruled against. A policy over code that does "
                    "not carry it is a policy nobody reading the module can see.",
                )
            )

    report.add(
        "not-built endpoints",
        MECHANICAL,
        findings,
        f"{len(declared)} declared in {_NOT_BUILT_MODULE.name}, {len(quoted)} quoted in "
        f"{_NOT_BUILT_SPEC.name}",
        scanned=len(declared),
    )


_TRANSPORT_PROVEN_RE = re.compile(r"\*\*`(\w+)` HAS (?:NOW )?RUN\b")
_TRANSPORT_UNPROVEN_RE = re.compile(r"\*\*`(\w+)` IS STILL UNEXERCISED\b")
_TRANSPORT_READERS = (
    Path("docs") / "map.py",
    Path("docs") / "specs" / "order-pipeline.md",
    Path("CLAUDE.md"),
)
_TRANSPORT_SUCCESS_CLAIM = "THE AUTHENTICATED SUCCESS PATH IS UNEXERCISED"


def check_transport_standing(report: Report) -> None:
    """Which order-transport calls have run live is decided by the module, not by its readers.

    WHY THIS ROW EXISTS. `server/order_transport.py`'s STATUS block is what
    `docs/specs/order-pipeline.md` itself calls "the primary record" — and then, on the line
    below, contradicted it. Until 2026-09-05 the spec said "`detail` and `fetch_open_orders`
    remain unexercised against the live host" while the module had recorded since 2026-09-02
    that `fetch_open_orders` HAD run and was refused `order_too_many` after paging far enough
    to count 370 orders. `docs/map.py` was worse: "THE AUTHENTICATED SUCCESS PATH IS
    UNEXERCISED ... the stored value has never been sent", against a module recording that
    `search` returned three real orders on 2026-08-30, which `CLAUDE.md` also said.

    THREE DOCUMENTS, TWO OF THEM WRONG, ABOUT A FACT ONE FILE OWNS. It is `shipping columns`
    one register up: there the disagreement was a number a module computes, here it is a
    standing a module declares. Neither could be settled by reading, because being wrong looks
    exactly like being right.

    WHAT IT DOES NOT DO. It does not check that a doc MENTIONS every proven call — a document
    is allowed to be silent. It fires only on a positive claim that a call is still unexercised
    when the module says it has run, which is the direction that misleads: a session reading
    "unexercised" plans a live test that has already happened, and a session reading nothing
    goes and looks.

    HISTORICAL PROSE IS DELIBERATELY NOT CAUGHT. "was named here as unexercised until
    2026-09-05 and it had run" is the correction, not the claim, and this repo's habit is to
    strike and annotate rather than delete. Only the present-tense forms — remains, is still,
    are still — are read as claims.
    """
    source = read(ROOT / "server" / "order_transport.py")
    proven = set(_TRANSPORT_PROVEN_RE.findall(source))
    unproven = set(_TRANSPORT_UNPROVEN_RE.findall(source))
    findings: List[Finding] = []

    if not proven and not unproven:
        report.add(
            "transport standing",
            MECHANICAL,
            [
                Finding(
                    "server/order_transport.py",
                    "its STATUS block no longer declares which calls have run live in a shape "
                    "this row can read (`**`name` HAS RUN...`, `**`name` IS STILL "
                    "UNEXERCISED...`). Re-point the patterns, or drop this row — a check whose "
                    "subject has left is the vacuous green docs/DEBTS.md opens by warning "
                    "about.",
                )
            ],
            "",
        )
        return

    both = proven & unproven
    for name in sorted(both):
        findings.append(
            Finding(
                "server/order_transport.py",
                f"the STATUS block says `{name}` has run live AND that it is still "
                f"unexercised. The module is the authority and it is contradicting itself.",
            )
        )

    for path in _TRANSPORT_READERS:
        text = read(ROOT / path)
        for name in sorted(proven):
            claim = re.compile(
                rf"`{re.escape(name)}`(?:[^`\n]|`[^`\n]*`){{0,90}}?"
                rf"(?:remains?|is still|are still) unexercised"
            )
            if claim.search(text):
                findings.append(
                    Finding(
                        str(path),
                        f"claims `{name}` is still unexercised against the live host. "
                        f"`server/order_transport.py`'s STATUS block — which "
                        f"docs/specs/order-pipeline.md calls the primary record — says it has "
                        f"run. The module is the authority; this sentence sends the next "
                        f"session to prove something already proven.",
                    )
                )
        if proven and _TRANSPORT_SUCCESS_CLAIM in text:
            findings.append(
                Finding(
                    str(path),
                    f"still carries `{_TRANSPORT_SUCCESS_CLAIM}` while "
                    f"`server/order_transport.py` records "
                    f"{', '.join('`%s`' % n for n in sorted(proven))} as having run "
                    f"authenticated.",
                )
            )

    report.add(
        "transport standing",
        MECHANICAL,
        findings,
        f"{len(proven)} proven and {len(unproven)} unexercised calls against "
        f"{len(_TRANSPORT_READERS)} readers",
        scanned=len(proven) + len(unproven),
    )


def check_env_vars(report: Report, docs: List[Path], allowed: Dict[str, str]) -> None:
    haystack = code_haystack()
    findings: List[Finding] = []
    seen: Set[str] = set()
    for doc in docs:
        for number, line in enumerate(read(doc).splitlines(), start=1):
            for _m in _ENV_RE.finditer(line):
                name = _m.group(1)
                if marked_proposed(line, _m.start()):
                    # A `+`-marked hatch a proposal would introduce. Fails once
                    # the code starts reading it, so the sigil cannot outlive the proposal.
                    if name in haystack:
                        findings.append(Finding(
                            f"{rel(doc)}:{number}",
                            f"`{PROPOSED_SIGIL}{name}` carries the proposed-name sigil and "
                            f"the code READS it now. Drop the sigil.",
                        ))
                    continue
                seen.add(name)
                if name in allowed:
                    continue
                if name not in haystack:
                    findings.append(
                        Finding(
                            f"{rel(doc)}:{number}",
                            f"`{name}` is documented but appears nowhere in the code, the "
                            f"Makefile, the scripts or .env.example.\n"
                            f"Add it to scripts/docs-audit-allow.txt with a reason if it "
                            f"is named before it is built.",
                        )
                    )
    report.add("env vars", MECHANICAL, findings, f"{len(seen)} documented, all real",
               scanned=len(seen))


# Every file that is not markdown and can name an environment variable, WITH the extensionless
# git hooks that `code_haystack` cannot see. That omission is not incidental here: the hook
# roster is the one place this repo keeps growing extensionless files, and `PKMNSCAN_SIGIL` —
# printed in every refusal the sigil check makes — lives in exactly such a file.
def _env_sites() -> Dict[str, List[str]]:
    """`PKMNSCAN_*` and friends named outside markdown, mapped to where they are named."""
    sites: Dict[str, List[str]] = {}
    sources: List[Path] = list(python_files())
    for name in ("Makefile", ".env.example"):
        candidate = ROOT / name
        if exists(candidate):
            sources.append(candidate)
    sources.extend(_walk(ROOT / "scripts", (".sh",)))
    sources.extend(_walk(ROOT / ".claude", (".json",)))
    hooks = ROOT / "scripts" / "githooks"
    for hook in sorted(child_names(hooks)):
        candidate = hooks / hook
        if exists(candidate):
            sources.append(candidate)
    for path in sources:
        for number, line in enumerate(read(path).splitlines(), start=1):
            for found in _ENV_RE.findall(line):
                sites.setdefault(found, []).append(f"{rel(path)}:{number}")
    return sites


def check_env_names(report: Report) -> None:
    """A variable the code reads must be named in the markdown somewhere.

    `check_env_vars` above runs the other direction — documented, therefore real — and has
    since D16. Nothing ran this one, and the asymmetry is the whole finding: a variable
    invented in code is invisible to every check in this file, so the way to add an
    undocumented switch to this repo was simply to add it.

    Measured 2026-09-05, four had gone in that way, and the list is not a set of oddities:
    `PKMNSCAN_SIGIL` is the bypass the sigil check PRINTS IN EVERY REFUSAL, so the one
    sentence a blocked commit reads names a variable no document explains. `PKMNSCAN_T1_SPLIT`
    chooses which half of the eval corpus T1 scores; `PKMNSCAN_TCG_ORDERS_URL` points the
    order fetch at an endpoint.

    **Naming it anywhere in markdown is the whole bar**, deliberately low. This cannot judge
    whether the explanation is any good — that is the semantic half D16 gives to a person —
    and a row that demanded a *good* explanation would be a row nobody could satisfy. What it
    can hold is that the variable was written down once, on purpose, where a reader looking
    for it would find it.
    """
    documented: Set[str] = set()
    for doc in markdown_files():
        for found in _ENV_RE.findall(read(doc)):
            documented.add(found)
    findings: List[Finding] = []
    sites = _env_sites()
    for name in sorted(sites):
        if name in documented:
            continue
        # THIS FILE SORTS LAST when choosing which site to cite. It is a legitimate source —
        # it reads `PKMNSCAN_EXPORTS` — so excluding it would leave a hole exactly where a
        # checker is least watched. But it also NAMES variables in prose, including this
        # docstring, and citing a sentence that describes the problem instead of the code
        # that has it sends the reader to the wrong file.
        where = sorted(sites[name], key=lambda site: site.startswith(rel(SELF)))
        shown = ", ".join(where[:3]) + (f", +{len(where) - 3} more" if len(where) > 3 else "")
        findings.append(
            Finding(
                where[0],
                f"`{name}` is read by the code and named in no markdown file.\n"
                f"  named at: {shown}\n"
                f"  Document it where its subject lives — the switch's own document, not a "
                f"list of switches. A variable nothing explains is one only its author can "
                f"use.",
            )
        )
    report.add(
        "env names",
        MECHANICAL,
        findings,
        f"{len(sites)} named in code, all documented",
        scanned=len(sites),
    )


# ------------------------------------------------------- the current-gate check, retired
#
# `check_current_gate` lived here until 2026-08-23. It read `Current gate: X` out of
# CLAUDE.md and reconciled it against the first gate in `docs/GATES.md` not marked PASSED,
# blocking when the two disagreed or when every gate had passed while one was still named.
#
# THE OWNER RETIRED THE GATING SYSTEM, so there is nothing left for it to reconcile: no gate
# is current, `docs/GATES.md` is a record of runs rather than a schedule, and the declaration
# it parsed no longer exists. A check whose subject is gone is deleted rather than left
# passing vacuously — `docs/DEBTS.md` spends a section on the difference between a green row
# and a row that cannot fail, and leaving this one would have manufactured exactly that.
#
# Deleted WITH its call, which is the clean form: `check_dispatch` compares the checks defined
# in this file against the ones `audit()` invokes, so a function left behind without a call
# would fail the commit and a call left behind without a function would raise. Recorded here
# rather than only in git, because the signal this row used to carry — "CLAUDE.md and
# GATES.md disagree about where the project is" — genuinely is gone, and a later session
# wondering why nothing checks that should find the answer at the site.

# ----------------------------------------------------------------------- the repo map

MAP = ROOT / "docs" / "map.py"

# What the orphan scan counts as source when an entry says nothing. Every entry written
# before the key below existed keeps exactly the behavior it had: `.py`, one level deep.
DEFAULT_SOURCE_SUFFIXES: Tuple[str, ...] = (".py",)

# The optional per-entry key that widens it. A single repo-wide suffix set was the obvious
# fix and is the wrong one: adding the web extensions to it would conscript
# `docs/design-refs/*.html` and `*.css`, which are drawings of docs/DESIGN.md and
# deliberately not components, into demanding map entries. Per-entry is the only shape that
# lets `app/` declare what it is written in without deciding that for the rest of the tree —
# and `docs/design-refs/` stays uncovered by having no entry with a module list at all,
# rather than by an exemption someone has to maintain.
SOURCE_SUFFIXES_KEY = "source_suffixes"


def scan_plan(component: Dict[str, object]) -> Tuple[Tuple[str, ...], bool, List[str]]:
    """What this entry's orphan scan covers: (suffixes, recursive, complaints).

    **Declaring the key replaces the default set rather than adding to it.** `app/` holds no
    `.py` and never will, so a union would have it hunting for a language it does not
    contain; the entry is the right place to say what a directory is written in, and saying
    it should not mean saying it twice.

    **A declaration is also what turns the scan recursive, and the coupling is deliberate.**
    A declaring directory keeps its source in subdirectories — `app/src/`, `app/tests/` —
    so a flat scan of one would find nothing whatever suffixes it was handed, which is the
    second half of why tonight's `.tsx` drift landed in silence. Recursing for *every* entry
    was the first draft and was worse: `harness/` lists `run.py` alone, and everything under
    `harness/tests/` and `harness/eval/` is deliberately undescribed (the map says so in a
    comment). Turning a dozen of those into blocking findings is a content decision about
    the map, argued in the map, not a side effect of widening a suffix set in here. So the
    default stays flat and grandfathered, and an entry that declares is an entry that has
    said what its whole tree is made of.

    **A malformed declaration scans nothing and reports that it scanned nothing.** Falling
    back to the `.py` default would leave `app/` printing a clean orphan scan that had
    looked at no file it contains — a check gone quiet, which docs/DEBTS.md already names
    as this auditor's worst failure mode. The complaints are MECHANICAL because the shape of
    a literal is provable: there is no context this script is missing.
    """
    declared = component.get(SOURCE_SUFFIXES_KEY)
    if declared is None:
        return DEFAULT_SOURCE_SUFFIXES, False, []

    # A bare string is the plausible mistake, and it is the dangerous one: `str.endswith`
    # accepts a string as happily as a tuple, so `".tsx"` written without its brackets would
    # scan for one suffix and look entirely correct doing it.
    if isinstance(declared, str) or not isinstance(declared, (list, tuple)):
        return (), False, [
            f"`{SOURCE_SUFFIXES_KEY}` must be a list of suffixes — [\".tsx\", \".css\"] — "
            f"and is {declared!r}. Nothing was scanned for orphans under this entry."
        ]

    complaints: List[str] = []
    suffixes: List[str] = []
    for item in declared:
        if not isinstance(item, str) or not item.startswith(".") or len(item) < 2:
            complaints.append(
                f"`{SOURCE_SUFFIXES_KEY}` lists {item!r}, which is not a file suffix. "
                f"A suffix starts with a dot — `\".tsx\"`, never `\"tsx\"`, which matches no "
                f"filename and would report a clean scan for having looked at nothing."
            )
            continue
        suffixes.append(item)

    if declared and not suffixes:
        complaints.append(
            f"`{SOURCE_SUFFIXES_KEY}` names no usable suffix, so the orphan rule does not "
            f"run over this directory at all."
        )
    if not declared:
        complaints.append(
            f"`{SOURCE_SUFFIXES_KEY}` is an empty list. An entry that declares the key is "
            f"saying what its source is; declaring nothing switches the orphan rule off "
            f"here, which is what leaving the key out already does more honestly."
        )
    if not component.get("modules"):
        complaints.append(
            f"`{SOURCE_SUFFIXES_KEY}` is declared but the entry lists no `modules`, and the "
            f"orphan scan only runs where there is a module list to compare against. Either "
            f"list the modules or drop the key — an inert declaration reads as coverage."
        )
    return tuple(suffixes), True, complaints


def source_names(target: Path, suffixes: Tuple[str, ...], deep: bool) -> Set[str]:
    """Source files under `target`, named the way docs/map.py names them.

    Relative and slash-joined, because the map already keys `app/`'s modules by
    `src/tokens.css` — so a recursive scan needs no translation step, the relative path IS
    the key. `__init__.py` is excluded as package plumbing rather than a module anyone would
    write a `does` for.

    Deep mode reuses `_walk`, which buys two properties that would otherwise have to be
    rebuilt here: it prunes SKIP_DIRS as it descends, so `app/node_modules` is never
    enumerated rather than enumerated and discarded, and it reads the index in staged mode,
    so the hook keeps auditing the tree the commit will carry.
    """
    if not suffixes:
        return set()
    if not deep:
        return {
            name
            for name in child_names(target)
            if name.endswith(suffixes) and name != "__init__.py"
        }
    return {
        path.relative_to(target).as_posix()
        for path in _walk(target, suffixes)
        if path.name != "__init__.py"
    }


def literals_from_module(path: Path) -> Dict[str, object]:
    """Module-level literal assignments, without importing. See docs/map.py."""
    try:
        tree = ast.parse(read(path))
    except SyntaxError:
        return {}
    out: Dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                try:
                    out[target.id] = ast.literal_eval(node.value)
                except (ValueError, SyntaxError):
                    continue
    return out


# Files whose bytes are not prose. `cited_decisions` reads every mapped file looking for `D<n>`
# and a compressed image will eventually contain those three bytes by chance — icon-180.png
# "cited" D31 and icon-512.png "cited" D2 on the day they were added.
BINARY_SUFFIXES = frozenset({
    ".png", ".jpg", ".jpeg", ".webp", ".heic", ".gif", ".avif", ".pdf",
    ".ico", ".woff", ".woff2", ".ttf", ".otf", ".zip", ".sqlite",
})


def cited_decisions(path: Path) -> Set[str]:
    """Every decision id a file cites, suppressions excluded.

    THE THIRD SITE, and the one docs/DEBTS.md got wrong. That entry judged this reader "not
    separately broken — it compares against `decision_headings`", and about the CAP it was
    right: an id it cannot read is one `governed_by` never asks about. About the WIDEN it was
    wrong in the other direction. This is a `repo map` finding, which is MECHANICAL, so the
    three real `# noqa: D102` / `# noqa: D401` lines in server/ turned into four blocked
    commits the moment the third digit came into reach — measured, on the first full run
    after the widen, and the reason `without_noqa` is applied here and not only to the
    citation scan.

    A BINARY FILE CITES NOTHING, and reading one as text is how it comes to. The map gained
    entries for `app/public/icon-*.png` on 2026-09-05 and this reader found `D31` in one and
    `D2` in another — byte sequences inside compressed image data, matched by a regular
    expression that had no reason to expect anything but source. The finding is MECHANICAL, so
    it blocked the commit, and the remedy it names is to add a decision id to `governed_by`
    that the file does not cite and nobody chose. A citation is a thing a person wrote; a file
    with no text to read has written none.
    """
    if path.suffix.lower() in BINARY_SUFFIXES:
        return set()
    lines = (without_noqa(line) for line in read(path).splitlines())
    return {"D" + digits for line in lines for digits in _DECISION_RE.findall(line)}


#: The shape of a hatch's VALUE. Every one of them is `<NAME>=off`, printed in the refusal
#: it lifts, so "set to something" is not the question — "set to off" is.
_HATCH_OFF = "off"


def check_hatch_state(report: Report) -> None:
    """A guard that has been switched off says so where a session already looks.

    **THE PUREST FORM OF THE DEFECT THIS FILE IS ABOUT.** `PKMNSCAN_DOCS=off` exported in a
    shell profile, a launchd plist, a wrapper or a CI environment kills one of the only two
    checks on the commit path in every session, forever — and every refusal message it
    would have printed is never printed, because no refusal ever happens. Every row in this
    file is void in that state, and nothing in the tree could report it. Same for
    `PKMNSCAN_SIGIL`, whose guard runs in the same hook, and for `PKMNSCAN_MAIN`, which is
    the local half of D42.

    **IT REPORTS AND REFUSES NOTHING.** A one-shot hatch typed on the command line for a
    legitimate reason is exactly what those variables are for, and the guard that stands
    down prints its own name while doing it — so the only thing this can surface that the
    session did not already know is a STANDING one, inherited from an environment nobody
    typed it into this turn. ADVISORY for that reason and no other: the finding is a
    question about where the variable came from, which is not something a script can judge.

    **TWO READS.** This one, and the environment `.claude/settings.json` hands every session
    in this project: that file carries no `env` block today, which is exactly when to assert
    it — an `env` key setting a hatch there would disarm the guard for every session in the
    repo, silently, with the disarming committed to git.

    The roster is the one `check_env_names` already builds by reading the code, so a hatch
    invented tomorrow is watched the day it is written and nothing here is hand-kept. A
    roster of zero is a finding: it means the name reader broke, and this row would then be
    reporting "no hatch is set" having looked at no names.
    """
    findings: List[Finding] = []
    roster = sorted(_env_sites())
    if not roster:
        findings.append(Finding(
            rel(SELF),
            "`_env_sites()` found no environment variable named anywhere in the code, so "
            "this row iterated nothing and would report `no hatch set` whatever the "
            "environment holds. The name reader is broken, not the environment.",
        ))

    for name in roster:
        value = os.environ.get(name)
        if value is None or value.strip().lower() != _HATCH_OFF:
            continue
        findings.append(Finding(
            f"environment -> {name}",
            f"`{name}={value}` is set in the environment this audit is running in.\n"
            "  If you typed it for this one command, this line is the receipt and there is "
            "nothing to do. If you did NOT, it is standing — a shell profile, a launchd "
            "plist, a wrapper, a CI env — and the guard it lifts has been refusing nothing "
            "and printing nothing in every session since. Check `env | grep PKMNSCAN`.",
        ))

    settings = ROOT / ".claude" / "settings.json"
    if exists(settings):
        try:
            declared = json.loads(read(settings))
        except ValueError as exc:
            findings.append(Finding(".claude/settings.json", f"does not parse as JSON: {exc}"))
        else:
            block = declared.get("env")
            if isinstance(block, dict):
                for name, value in sorted(block.items()):
                    if name in roster and str(value).strip().lower() == _HATCH_OFF:
                        findings.append(Finding(
                            ".claude/settings.json",
                            f"its `env` block sets `{name}={value}` for every session in this "
                            f"project.\n"
                            "  That is a guard disarmed in git, for everybody, with no "
                            "refusal ever printed to say so. A hatch is a thing a person "
                            "types once; a committed one is a deleted check wearing an "
                            "environment variable.",
                        ))

    report.add(
        "hatch state",
        ADVISORY,
        findings,
        f"{len(roster)} hatches in the roster, none set in this environment or in "
        f".claude/settings.json",
        scanned=len(roster),
    )


def check_map(report: Report, allowed: Dict[str, str]) -> None:
    """docs/map.py claims things about the repo; this is where they are checked.

    The orphan rule is the one that does the work. Everything else here catches a claim
    that went false; the orphan rule catches a claim that was never made — a module added
    without touching the map, which is exactly how an index quietly stops describing the
    thing it indexes.

    What each entry's orphan scan looks at is the entry's own declaration — see `scan_plan`.
    It reached `.py` and one directory deep until 2026-08-13, so `app/` was inert under a
    rule its map entry looked covered by: every step 7a screen landed beside the described
    modules in one evening and the row stayed green.
    """
    findings: List[Finding] = []
    if not exists(MAP):
        report.add("repo map", MECHANICAL, [Finding("docs/map.py", "does not exist")])
        return

    data = literals_from_module(MAP)
    components = data.get("COMPONENTS") or []
    shipped = data.get("SHIPPED") or []
    open_steps = data.get("OPEN") or []
    gates = data.get("GATES") or []
    if not components:
        report.add("repo map", MECHANICAL, [Finding("docs/map.py", "no COMPONENTS list to read")])
        return

    singles = {i for i, _, _ in decision_heading_lines_across(decision_files(), "D")}
    test_names = {name for name, _ in registered_tests()}
    claimed = 0
    # (component path, orphan) pairs, reported after the loop rather than inside it. The
    # gitignore question below is one batched git call for the whole map that way, instead
    # of one per entry that lists modules.
    orphans: List[Tuple[str, str]] = []

    def check_decisions(where: str, names: Sequence[str]) -> None:
        for name in names:
            if name not in singles:
                findings.append(Finding(where, f"governed_by cites {name}, which has no heading in docs/DECISIONS.md."))

    def check_tests(where: str, names: Sequence[str]) -> None:
        for name in names:
            if name not in test_names and name not in allowed:
                findings.append(
                    Finding(
                        where,
                        f"tested_by cites {name}, which is not registered in "
                        f"harness/run.py:TESTS.\n"
                        f"  This field names harness tests and nothing else. A Playwright "
                        f"spec under app/tests/ is run by `make design-check`, not at turn "
                        f"end, and belongs in the entry's `note` — see the two spec entries "
                        f"in docs/map.py, which say so in prose for exactly this reason.",
                    )
                )

    for component in components:
        path = component.get("path", "")
        status = component.get("status", "")
        target = ROOT / path
        claimed += 1
        where = f"docs/map.py -> {path}"

        if status == "planned":
            if exists(target):
                findings.append(
                    Finding(
                        where,
                        f"`{path}` is marked planned but exists now (build-order step "
                        f"{component.get('step', '?')}). Update the entry to built and "
                        f"list its modules.",
                    )
                )
        elif not exists(target):
            findings.append(Finding(where, f"`{path}` is marked {status or 'built'} but does not exist."))

        check_decisions(where, component.get("governed_by") or [])
        check_tests(where, component.get("tested_by") or [])

        suffixes, deep, complaints = scan_plan(component)
        for complaint in complaints:
            findings.append(Finding(where, complaint))

        modules = component.get("modules") or {}
        for name, entry in modules.items():
            module_path = target / name
            module_where = f"docs/map.py -> {path}{name}"
            claimed += 1
            if not exists(module_path):
                findings.append(Finding(module_where, f"`{path}{name}` is listed but does not exist."))
                continue
            declared = set(entry.get("governed_by") or [])
            check_decisions(module_where, sorted(declared))
            check_tests(module_where, entry.get("tested_by") or [])
            # The map must not know less than the code does.
            missing = cited_decisions(module_path) - declared - set(component.get("governed_by") or [])
            if missing:
                findings.append(
                    Finding(
                        module_where,
                        f"{path}{name} cites {', '.join(sorted(missing))} in its own comments "
                        f"but the map does not list it under governed_by.",
                    )
                )

        # Orphans: a source file the map never mentions. Still guarded on `modules`, which
        # is the exception docs/DEBTS.md records for `scripts/`: an entry with no module
        # list has nothing to be an orphan of.
        if modules and exists(target):
            for orphan in sorted(source_names(target, suffixes, deep) - set(modules)):
                orphans.append((path, orphan))

    # A gitignored file is local state and not repo content — the same argument
    # `ignored_paths` makes for a dangling reference, and it lands harder here because this
    # row blocks: refusing a commit over `app/playwright-report/index.html` would be the
    # auditor stopping work on a file the repo does not contain. One batched call, and in
    # staged mode the list is empty by construction, since `_walk` reads the index and the
    # index holds nothing ignored — so the pre-commit path pays nothing for this.
    ignored = ignored_paths([owner + orphan for owner, orphan in orphans])
    for owner, orphan in orphans:
        if owner + orphan in ignored:
            continue
        findings.append(
            Finding(
                f"docs/map.py -> {owner}",
                f"`{owner}{orphan}` exists but no entry describes it. Add it to "
                f"modules, with what it does and what governs it.",
            )
        )

    # THE `status` FIELD IS GONE AND SO IS THE RULE THAT READ IT. This block enforced
    # "exactly one build-order step is `next`", which was right while the build order was a
    # sequence and became the thing forcing a false answer once it was not: step 9 held
    # `next` for nine days while the work went to pricing, orders and the codes track,
    # because the rule required SOMETHING to hold it. The list a step is in is its status
    # now — `SHIPPED` or `OPEN` — and `OPEN` is deliberately unranked (D80).
    #
    # What replaces it is the invariant a two-list shape actually has: an id is in exactly
    # one list, ids are unique, and a shipped step carries the date it landed. Those are the
    # ways this shape can be wrong, and each is decidable.
    seen: Dict[int, str] = {}
    for label, rows in (("SHIPPED", shipped), ("OPEN", open_steps)):
        for row in rows:
            number = row.get("n")
            if number is None:
                findings.append(Finding("docs/map.py", f"a {label} step carries no `n`: {str(row)[:60]}…"))
                continue
            if number in seen:
                findings.append(Finding(
                    "docs/map.py",
                    f"step {number} is in {seen[number]} and in {label}. An id is in exactly "
                    f"one list — the list IS the status.",
                ))
            seen[number] = label
            if label == "SHIPPED" and not row.get("on"):
                findings.append(Finding(
                    "docs/map.py",
                    f"SHIPPED step {number} carries no `on` date. SHIPPED is ordered by when "
                    f"the work landed, so a row with no date cannot be placed in it.",
                ))
            if label == "OPEN" and row.get("on"):
                findings.append(Finding(
                    "docs/map.py",
                    f"OPEN step {number} carries `on: {row.get('on')}` — a landing date on "
                    f"something that has not landed. Move it to SHIPPED or drop the field.",
                ))

    # Gate status has two homes; they must agree.
    gates_corpus_text = gates_text()
    for gate in gates:
        name = gate.get("gate", "")
        heading = re.search(r"^#{2,3}\s+Gate\s+" + re.escape(name) + r"\b(.*)$",
                             gates_corpus_text, re.MULTILINE)
        if not heading:
            findings.append(Finding("docs/map.py", f"Gate {name} has no `### Gate {name}` heading in docs/GATES.md."))
            continue
        passed_in_gates = "PASSED" in heading.group(1)
        passed_in_map = gate.get("status") == "passed"
        if passed_in_gates != passed_in_map:
            findings.append(
                Finding(
                    "docs/map.py",
                    f"Gate {name} is {'passed' if passed_in_map else gate.get('status')} here but "
                    f"{'PASSED' if passed_in_gates else 'not marked PASSED'} in docs/GATES.md.",
                )
            )

    # THE STEP-SET RECONCILIATION THAT LIVED HERE MOVED TO `build order mirror` (D80). It
    # scanned docs/GATES.md for `^\d+\.` across the WHOLE FILE, so any numbered list anywhere
    # in it joined the step set, and it knew nothing about which list a step was in — it
    # could not have told a shipped step from an open one, which is now half the claim. The
    # replacement reads the two headings and reconciles each separately, in both directions.

    report.add("repo map", MECHANICAL, findings, f"{claimed} entries match the tree",
               scanned=claimed)


# ------------------------------------------------------------------- the game registry
#
# `pipeline/games.py` authors one taxonomy per game (D22): the exact `Product Line` cell,
# the ordered `Rarity` cells, the finish enum, the finish -> `Condition` map and the
# rarity -> finish matrix. Nothing generates any of it — every field is ARGUMENT in D18's
# sense — so what is checkable is the authoring against a real export, and only in the
# directions where an export can actually settle the question.
#
# FOUR ROWS RATHER THAN ONE, SPLIT BY WHAT AN EXPORT PROVES. The same reasoning
# `check_positional_references` uses for its two rows: a combined verdict would have to
# take the strictest severity of all four and apply it to findings that are questions.
#
#   game vocabulary   MECHANICAL. The shape of the literal, plus the two export findings
#                     that cannot false-positive: a rarity whose folded form matches an
#                     export cell and whose raw form does not (a typo, provably), and an
#                     export cell no entry accounts for (a gap, provably).
#   game coverage     ADVISORY. Authored strings no export in view contains, and matrix
#                     pairs no export in view stocks. Absence from one set proves nothing —
#                     `Promo` and every pre-SV rarity are legitimately missing from an SV09
#                     fixture, and D23 requires the matrix to exceed its evidence.
#   matrix superset   MECHANICAL. An observed (rarity, finish) pair the matrix is MISSING.
#                     This is the row that keeps D23's unselectable finish chips safe.
#   join key shape    MECHANICAL. A `join_key` that the export's own `Number` cells prove
#                     can never match a row. One direction only — see the check.
#
# BLOCKING ROWS READ ONLY THE EXPORTS THE REPO CARRIES. `PKMNSCAN_EXPORTS` widens the
# advisory row and nothing else, and a path in it that does not resolve is skipped in
# silence rather than reported. A gate that can be failed by a file on one person's disk is
# a gate that gets switched off, and a gate that *requires* such a file has already switched
# itself off for everyone else — which is the same failure the repo-map orphan rule went
# quiet under, arriving from the opposite direction.

GAMES_MODULE = ROOT / "pipeline" / "games.py"

# The one module allowed to build the export request (D64/D65), and the three fields of it
# that are a standing instruction rather than a transcription of the portal's own form.
#
# THE REASON EACH ONE HOLDS IS CARRIED HERE RATHER THAN LEFT TO THE READER, because the person
# this row stops is the person who has just decided the value should be different — and the
# only thing that will change their mind is the argument, not a restatement of the number.
EXPORT_MODULE = ROOT / "server" / "tcg_export.py"
#: The live-inventory download's two query parameters (D104), MEASURED off the portal's own
#: `Export From Live` button rather than designed. That request is a GET with no scope: no
#: category, no sets, no conditions, no `MyInventory`, no `ExcludeListos`.
#:
#: WHY A BLOCKING ROW OVER TWO PARAMETERS. The first build of this path GUESSED a filtered POST
#: with `CategoryId: "0"`, on the reasoning that `"0"` is the portal's all-row everywhere else.
#: It is not — the category select is the one field on that form with no `0=All` option — and
#: the portal answered with a valid CSV header and ZERO rows. So on this endpoint a wrong
#: request is not refused, it is answered emptily, and the only thing standing between that and
#: a store-wide `live: 0` is this row plus `fetch_live`'s own empty-export refusal.
LIVE_QUERY_EXPECTED = (
    (
        "type",
        "Pricing",
        "The LIVE tab rather than Staged. `Export From Staged` is the same endpoint with the "
        "other value and is a different document — D87 reconciles the store against the live "
        "one, so this value decides what `live` means for every SKU.",
    ),
    (
        "exportLowestListingNotMe",
        "true",
        "The portal's own default, checked on that form as 'If me, show next lowest'. It "
        "changes the `TCG Low Price` column this pipeline reads and prices against, so it is "
        "transcription that MATTERS rather than transcription that does not.",
    ),
)

EXPORT_STANDING = (
    (
        "ExcludeListos",
        True,
        "Exclude listings with photos — the owner's standing instruction (2026-08-31, D76). "
        "It holds on the owner's word: what the flag changes in the file is NOT measured, "
        "because the axis leaves no trace in it. NOTHING DOWNSTREAM CAN CATCH A WRONG VALUE: "
        "D64 measured `Photo URL` empty in every export, filtered and unfiltered, so a wrong "
        "value gives a clean join and a green `make check` forever. Do not flip this on a "
        "reading of the field name — take it back to the owner.",
    ),
    (
        "MyInventory",
        False,
        "The CATALOG, not the operator's current listings. With this true the same request "
        "returns only what is already listed, which is useless to a join whose whole job is "
        "listing cards that are not.",
    ),
    (
        "PrintingIds",
        ["0"],
        "All Printings. A number stocked in several finishes must arrive with all of them, "
        "or D3 rung 2 decides it from whichever one survived — which is a silent mislisting "
        "rather than a loud miss.",
    ),
)

# ---------------------------------------------- the transport promise, read off its own file
#
# `server/tcg_export.py` opens with FOUR BULLETS that are, in its own words, the REPLACEMENT
# for a guarantee it deleted rather than qualified — the file that reads the operator's
# `TCGPLAYER_STORE_COOKIE` saying in prose what it is allowed to do with it. The first bullet
# is a count of hosts, methods and routes, and it is the one thing in that block a machine can
# settle: the constants are in the same file, and so is the request construction.
#
# IT WAS WRONG FOR A WEEK AND NOTHING COULD SAY SO. Written 2026-08-30 over a single GET, it
# read `One host, one method, one route` until 2026-09-06 — through D65 turning the download
# into a POST against a different route and promoting the filter list from a probe to a real
# call the same day, and through D104 adding the live download six days later. Three route
# changes and a second method under a sentence that never moved, and `server/pipeline_routes.py`
# had copied the sentence besides.
#
# WHY MECHANICAL RATHER THAN A QUESTION. Nothing here is a judgement. The host of a `https://`
# constant is a fact, the path of one is a fact, and whether a `_open` call carries a body is a
# fact — `_open` builds `method="POST" if data else "GET"`, so the keyword IS the method. A
# finding is a route or a method the code can reach and the promise does not name, or the
# reverse, and either one is provably wrong in the sense D16 asks for.
TRANSPORT_PROMISE_MODULE = ROOT / "server" / "tcg_export.py"

#: The one function every outbound request in that module goes through. Named here because the
#: whole reading hangs off it: a second opener would make this row describe half the traffic.
TRANSPORT_OPENER = "_open"

#: The headline the bullet leads with, whose three numbers are what this row settles. Anchored
#: on the bold run so a rewording is REPORTED rather than silently uncovered — `check census`'s
#: hard-won half, and the failure mode that matters most here: a promise this row stops
#: watching is a promise back in the state it spent a week in.
_TRANSPORT_HEADLINE_RE = re.compile(
    r"\*\*(\w+) hosts?, (\w+) methods?, (\w+) routes?\*\*", re.I
)

#: The routes the bullet tabulates, one `METHOD /path` per line. Indented under the headline
#: as a block, which is how the file writes a captured request everywhere else.
_TRANSPORT_ROUTE_RE = re.compile(r"^\s{4,}(GET|POST|PUT|PATCH|DELETE)\s+(/\S*)", re.M)

#: Number words, because the headline is prose and this repo writes counts in prose. Only as
#: far as anything here could plausibly reach; a count past it is reported rather than guessed.
_TRANSPORT_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
# ------------------------------------------- the set list's refusals, against the screen's map
#
# `GET /pipeline/games/<game>/sets` is the one refusal path in this repo that answers 200 and
# hands the CODE to a screen to re-word. That is argued and right — the operator is mid-capture
# and a failed autocomplete is not a failed capture — but it makes `CaptureScreen.tsx`'s
# `hintReason` the place a transport refusal becomes a sentence, and nothing checked that it
# covered the refusals that can arrive.
#
# IT COVERED TWO OF NINE. Measured 2026-09-06: `tcg_export.filters` can raise nine distinct
# codes and the map named `tcg_session_expired` and `tcg_cookie_missing`, so a WAF block at the
# rig read `Set list unavailable (tcg_blocked)` — a raw machine string on screen, which
# docs/DESIGN.md's register rule forbids, with the module's own remedy (set the user agent in
# `.env`) discarded one function above it.
#
# THE ROUTE CARRIES `message` NOW AND THAT IS THE FLOOR, NOT THIS ROW'S SUBJECT. A fallback
# that is routinely what the operator reads is a fallback nobody widens the map for, which is
# how the two-of-nine state lasted; this row is what keeps the net out from under the screen.
HINT_REASON_SCREEN = ROOT / "app" / "src" / "CaptureScreen.tsx"

#: The transport function the set-list route calls, and the root of the walk. Every refusal
#: reachable from it — through the endpoint accessors, the cookie read, the opener and the
#: status reader — is a code that can land on the capture screen.
HINT_REASON_ROOT = "filters"

#: The screen's map, read as the codes it compares against. Anchored on the function so a
#: rewrite that moves the comparisons elsewhere is REPORTED rather than silently uncovered.
_HINT_REASON_FN_RE = re.compile(r"function hintReason\([^)]*\)[^{]*\{(.*?)\n\}", re.S)
_HINT_REASON_CODE_RE = re.compile(r"code === '([a-z_]+)'")

#: Codes the map may name that no transport refusal produces, each with the reason it is there.
#: Declared rather than inferred: a map allowed to name anything is a map this row cannot read
#: in the second direction, and the dead branch is the finding that direction exists for.
HINT_REASON_NON_TRANSPORT = {
    "no_category": (
        "the route's own, raised before anything is fetched — this game carries no "
        "`tcgplayer_category_id` in pipeline/games.py, which is a fact about the registry "
        "rather than about the portal."
    ),
    "unreachable": (
        "the CLIENT's own, invented in `loadSets`'s catch when the request never reached the "
        "capture server. No server sends it, and the operator cannot tell it from "
        "`tcg_unreachable`, which is why the screen labels them together."
    ),
}
FIXTURES_DIR = ROOT / "fixtures"

# Opt-in extra exports, colon-separated, absolute or repo-relative. For the operator who
# has a full-catalog export or a Riftbound one on disk and wants the coverage questions
# asked against it. Never blocking — see the note above.
EXPORTS_ENV = "PKMNSCAN_EXPORTS"

PRODUCT_LINE_CELL = "Product Line"
RARITY_CELL = "Rarity"
CONDITION_CELL = "Condition"
NUMBER_CELL = "Number"

# Every key a registry entry must carry, and the one it may. Written here rather than read
# out of the module so that deleting a field from every entry at once is still a finding.
GAME_REQUIRED_KEYS = frozenset({
    "key", "display", "product_line", "rarities", "rarities_not_claimed", "finishes",
    "condition_by_finish", "finish_by_rarity", "located", "join_key", "prompt",
    "crop_bands", "card_aspect", "catalogued", "unverified",
})
GAME_OPTIONAL_KEYS = frozenset(
    {
        "product_line_rarities",
        "tcgplayer_category_id",
        "set_aliases",
        "export_scope",
        "export_needs_hint",
        "export_category_bytes",
    }
)

# The `join_key` an uncatalogued game must name. Written here rather than read out of the
# module for the same reason GAME_REQUIRED_KEYS is: renaming the strategy in the registry
# alone would leave this rule matching nothing, silently, and a rule that cannot fire is
# worse than no rule. The existing shape check already proves the name is a member of
# JOIN_KEY_STRATEGIES, so the two together pin both halves.
NOT_JOINED_STRATEGY = "not_joined"

# The `join_key` whose key is COMPOSED as `zfill(3)(number) + "/" + printedTotal`. Named
# here because `check_join_key_shape` reasons about the "/" that composition always
# produces; nothing else in this file cares which strategy is which.
COMPOSED_STRATEGY = "number_and_printed_total"

_FOLD_RE = re.compile(r"[^a-z0-9]")


def fold_cell(text: str) -> str:
    """Case and punctuation removed. Two cells that fold alike are the same cell misspelt."""
    return _FOLD_RE.sub("", str(text).casefold())


class ExportFacts(NamedTuple):
    """What one export file says about product lines, rarities and conditions."""

    source: str
    committed: bool
    rarities: Dict[str, Set[str]]  # product line -> the `Rarity` cells under it
    triples: Set[Tuple[str, str, str]]  # (product line, rarity, condition)
    numbers: Dict[str, Set[str]]  # product line -> the non-blank `Number` cells under it


def _read_export(path: Path, committed: bool) -> Optional[ExportFacts]:
    """Parse one export with the stdlib `csv`, never with `pipeline.tcgcsv`.

    Importing a project module to audit a project data file is the same violation as
    importing one to audit its source, one layer down: it puts project code on the audit
    path, and this file's whole contract is that nothing there runs. The cost is that this
    reader is naive about the byte format — which is correct, because the byte format is
    T2's question and not this one's.

    Returns None for a CSV that is not an export at all. A file without both columns is not
    a malformed export, it is a different kind of file.
    """
    try:
        text = read(path)
    except (OSError, UnicodeError, subprocess.SubprocessError):
        return None
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames:
        return None
    if PRODUCT_LINE_CELL not in reader.fieldnames or RARITY_CELL not in reader.fieldnames:
        return None

    rarities: Dict[str, Set[str]] = {}
    triples: Set[Tuple[str, str, str]] = set()
    numbers: Dict[str, Set[str]] = {}
    try:
        for row in reader:
            line = (row.get(PRODUCT_LINE_CELL) or "").strip()
            rarity = (row.get(RARITY_CELL) or "").strip()
            condition = (row.get(CONDITION_CELL) or "").strip()
            if not line:
                continue
            # `Number` is gathered before the rarity filter below, because the join key is
            # a property of the product line and not of a rarity — and because the rows
            # this file most needs to see the shape of (sealed product, DON!! cards) are
            # exactly the ones with no rarity cell.
            number = (row.get(NUMBER_CELL) or "").strip()
            if number:
                numbers.setdefault(line, set()).add(number)
            if not rarity:
                continue
            rarities.setdefault(line, set()).add(rarity)
            if condition:
                triples.add((line, rarity, condition))
    except csv.Error:
        return None
    return ExportFacts(rel(path), committed, rarities, triples, numbers)


_EXPORTS: Optional[List[ExportFacts]] = None


def export_facts() -> List[ExportFacts]:
    """Every export in view: the committed fixtures always, then the opt-in ones.

    Built once. A `PKMNSCAN_EXPORTS` entry that does not resolve, does not read, or is not
    an export is dropped without a word — see the section note for why that silence is the
    point rather than a gap.
    """
    global _EXPORTS
    if _EXPORTS is not None:
        return _EXPORTS
    found: List[ExportFacts] = []
    for path in glob_files(FIXTURES_DIR, "*.csv"):
        facts = _read_export(path, committed=True)
        if facts is not None:
            found.append(facts)
    for entry in (os.environ.get(EXPORTS_ENV) or "").split(":"):
        entry = entry.strip()
        if not entry:
            continue
        path = Path(entry)
        if not path.is_absolute():
            path = ROOT / entry
        if not path.is_file():
            continue
        facts = _read_export(path, committed=False)
        if facts is not None:
            found.append(facts)
    _EXPORTS = found
    return _EXPORTS


def observed_rarities(committed_only: bool) -> Dict[str, Set[str]]:
    """product line -> every `Rarity` cell seen under it."""
    out: Dict[str, Set[str]] = {}
    for facts in export_facts():
        if committed_only and not facts.committed:
            continue
        for line, cells in facts.rarities.items():
            out.setdefault(line, set()).update(cells)
    return out


# --------------------------------------------------- the map's sections, and its readers

# `Read by four consumers` in docs/map.py's docstring, and the indented block under it. The
# word is checked against the number of entries, and every entry that looks like a path is
# checked to exist — a consumer list is a claim about the tree like any other.
_CONSUMER_HEAD = re.compile(r"Read by ([a-z]+) consumers", re.I)
_CONSUMER_ROW = re.compile(r"^ {2}(\S.*?)\s{2,}\S")

# Files that may be a section's reader. Everything tracked under scripts/ plus the audit's
# own tree walk would be circular here, so this is deliberately the same walk `paths` uses,
# minus the map itself.
_SECTION_SKIP = {"docs/map.py"}


def _map_sections() -> List[str]:
    """Top-level literal names in docs/map.py, in file order."""
    if not exists(MAP):
        return []
    names: List[str] = []
    for node in ast.parse(read(MAP)).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id.isupper():
                names.append(target.id)
    return names


def _consumer_block() -> Tuple[Optional[str], List[str]]:
    """The docstring's declared consumer count word, and the names in the block under it.

    The block is a two-column layout, so the name is taken by COLUMN rather than by a run
    of spaces: the longest path in it — `scripts/decision-context.py` — fills its column
    and is separated from its description by a single space, and one entry is the phrase
    `you, or an agent`, which has spaces of its own. A separator-based reader got both
    wrong in opposite directions.
    """
    if not exists(MAP):
        return None, []
    text = read(MAP)
    head = _CONSUMER_HEAD.search(text)
    if head is None:
        return None, []
    rows: List[str] = []
    column: Optional[int] = None
    for line in text[head.end():].splitlines()[1:]:
        if not line.strip():
            if rows:
                break
            continue
        if line.startswith("   "):  # a description wrapping onto the next line
            continue
        if not line.startswith("  "):
            if rows:
                break
            continue
        if column is None:
            gap = re.search(r"\S\s+(?=\S)", line)
            if gap is None:
                continue
            column = gap.end()
        rows.append(line[:column].strip())
    return head.group(1).lower(), rows


def _map_component(path: str) -> Optional[Dict[str, object]]:
    """One entry out of docs/map.py's COMPONENTS, by its `path`."""
    components = literals_from_module(MAP).get("COMPONENTS")
    if not isinstance(components, list):
        return None
    for entry in components:
        if isinstance(entry, dict) and entry.get("path") == path:
            return entry
    return None


def check_hook_roster(report: Report) -> None:
    """Every file in `scripts/githooks/` has an entry in docs/map.py.

    THE ORPHAN SCAN CANNOT COVER THIS DIRECTORY, and docs/map.py says so in its own comment:
    a git hook is extensionless by git's requirement, `scan_plan` matches entries by suffix,
    and an entry with no suffix is rejected. So the hooks are listed BY HAND, and a list kept
    by hand is a list that stops being kept.

    It stopped twice. D42 added `reference-transaction` and `pre-push` and wrote both entries;
    `post-merge` and `post-checkout` landed later with the `make hooks` staleness reminder and
    neither was written. Measured 2026-09-05: five hooks on disk, three in the map. The map's
    own comment calls this hole hypothetical — it had already fired once when that sentence
    was written, and fired again afterwards.

    **This is the narrowest possible reader of that hole**, and deliberately not a widening of
    `scan_plan` to admit extensionless entries. That was the obvious fix and it is the wrong
    one: the suffix rule is what keeps `views.txt` and a stray `README` from being conscripted
    into demanding entries, and relaxing it repeals a rule that is doing work everywhere else
    to repair one directory. One directory's roster, checked against one directory's entries.

    The commit path is the subject, which is why this blocks. A hook nobody wrote down is a
    thing that runs on every commit and appears in no account of what runs on every commit.
    """
    hooks = ROOT / "scripts" / "githooks"
    if not exists(hooks):
        report.add(
            "hook roster",
            MECHANICAL,
            [
                Finding(
                    "scripts/githooks/",
                    "the directory is gone, and `make hooks` installs from it. Restore it, "
                    "or delete this row with it.",
                )
            ],
            "",
        )
        return

    component = _map_component("scripts/")
    if component is None:
        report.add(
            "hook roster",
            MECHANICAL,
            [Finding("docs/map.py", "no COMPONENTS entry has `path: 'scripts/'` to read.")],
            "",
        )
        return

    listed = set((component.get("modules") or {}).keys())
    on_disk = sorted(child_names(hooks))
    findings: List[Finding] = []
    for hook in on_disk:
        if f"githooks/{hook}" not in listed:
            findings.append(
                Finding(
                    f"scripts/githooks/{hook}",
                    f"runs on the commit path and has no entry in docs/map.py.\n"
                    f"  Add `\"githooks/{hook}\"` to the `scripts/` component's `modules`, "
                    f"with a `does` and its `governed_by`. The orphan scan cannot find this "
                    f"directory — the suffix rule rejects an extensionless key — so this row "
                    f"is the only thing that will.",
                )
            )
    for key in sorted(listed):
        if not key.startswith("githooks/"):
            continue
        if key.split("/", 1)[1] not in set(on_disk):
            findings.append(
                Finding(
                    "docs/map.py",
                    f"`{key}` has an entry but no file. A roster kept by hand goes stale in "
                    f"both directions; this is the half that describes a hook that has left.",
                )
            )
    report.add(
        "hook roster",
        MECHANICAL,
        findings,
        f"{len(on_disk)} hooks, all in docs/map.py",
        scanned=len(on_disk),
    )


# --------------------------------------------------------------------- codex hooks (D135)

CODEX_HOOKS = ROOT / ".codex" / "hooks.json"
CLAUDE_SETTINGS = ROOT / ".claude" / "settings.json"


def _hook_triples(data: object) -> Set[Tuple[str, str, str]]:
    """(event, matcher, command) out of a settings-shaped `hooks` block.

    Both files share one shape — `hooks.<Event> = [{matcher?, hooks: [{type, command}]}]` —
    because `.codex/hooks.json` was written by copying `.claude/settings.json`'s own block
    out of its wrapper (D135). `matcher` is absent on an event with no tool to match
    (`SessionStart`, `Stop`, `SessionEnd`, `WorktreeRemove`), so it is read as `""` rather
    than skipped — an event that gains a matcher in one file and not the other is exactly
    the drift this reads for, and a triple can only report that by carrying the field.

    `timeout` is deliberately not part of the triple. It changes how patient a hook is, not
    which hooks fire, and folding it in would make a slower `session-teardown.sh` in one
    file read as a MISSING hook rather than as a timing difference nobody asked this row to
    referee.
    """
    triples: Set[Tuple[str, str, str]] = set()
    if not isinstance(data, dict):
        return triples
    events = data.get("hooks")
    if not isinstance(events, dict):
        return triples
    for event, entries in events.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            matcher = entry.get("matcher") or ""
            for hook in entry.get("hooks") or []:
                if not isinstance(hook, dict):
                    continue
                if hook.get("type") != "command":
                    continue
                command = hook.get("command")
                if isinstance(command, str) and command:
                    triples.add((str(event), str(matcher), command))
    return triples


def check_codex_hooks(report: Report) -> None:
    """`.codex/hooks.json` and `.claude/settings.json`'s `hooks` block name the same hooks.

    BUILT SO A CODEX SESSION IS NOT A SECOND, UNGUARDED WAY INTO THIS REPO (D135). Codex
    reads `.codex/hooks.json` the way Claude Code reads `.claude/settings.json`'s `hooks`
    key, and until this row nothing compared the two: a guard added to one tool's config and
    not the other's is a guard that only some sessions run, silently, and the file's own
    prose cannot say so — `.codex/hooks.json` carries none of `.claude/settings.json`'s
    `_*_note` fields explaining what each hook is for or why it fails open, because those
    notes are keys JSON tolerates and nothing reads.

    MEASURED AT THE MOMENT THIS ROW WAS WRITTEN: the two files already disagreed.
    `.claude/settings.json` runs `scripts/reap.py --hook` on every `Bash` call (D127, added
    2026-09-10 for the pkill/lsof incidents) and `scripts/session-teardown.sh` on
    `WorktreeRemove` (added with D111's sweep) — `.codex/hooks.json` was written a day
    earlier, on 2026-09-09, and has neither. A Codex session could run an unrestricted
    `pkill` this repo's own Claude sessions cannot, and its `git worktree remove` would
    never notify a supervisor to stop. Both are added to `.codex/hooks.json` in the same
    change that adds this row, which is what makes the row start green rather than start by
    reporting the gap it was built to close.

    EVENT AND MATCHER ARE PART OF THE COMPARISON, NOT ONLY THE COMMAND. A command string
    reused under a different event or a narrowed matcher is a different guard wearing the
    same name — `scripts/guard-opsec.sh` on `Write|Edit` is the opsec check; the same script
    on `Bash` would be a no-op with a name that reads as coverage. Comparing the full triple
    is what catches that; comparing commands alone would not.

    A COMMAND NAMED IN EITHER FILE MUST NAME A REAL FILE IN THE TREE. `.codex/hooks.json`
    is untracked history's copy of a moving target, and a hook whose script has since been
    renamed or deleted is silent in exactly the way `make reap` and `make janitor`'s own
    liveness checks refuse to be — it does not error, it simply never runs.
    """
    findings: List[Finding] = []
    if not exists(CODEX_HOOKS):
        report.add(
            "codex hooks",
            MECHANICAL,
            [
                Finding(
                    ".codex/hooks.json",
                    "does not exist. Codex reads no hooks at all here, which is a silent "
                    "downgrade from what .claude/settings.json enforces for Claude Code — "
                    "restore the file or delete this row with it (D135).",
                )
            ],
            "",
        )
        return
    if not exists(CLAUDE_SETTINGS):
        report.add(
            "codex hooks",
            MECHANICAL,
            [Finding(".claude/settings.json", "does not exist; nothing to reconcile against.")],
            "",
        )
        return

    try:
        codex_data = json.loads(read(CODEX_HOOKS))
    except json.JSONDecodeError as exc:
        report.add(
            "codex hooks",
            MECHANICAL,
            [Finding(".codex/hooks.json", f"does not parse as JSON: {exc}")],
            "",
        )
        return
    try:
        claude_data = json.loads(read(CLAUDE_SETTINGS))
    except json.JSONDecodeError as exc:
        report.add(
            "codex hooks",
            MECHANICAL,
            [Finding(".claude/settings.json", f"does not parse as JSON: {exc}")],
            "",
        )
        return

    codex_triples = _hook_triples(codex_data)
    claude_triples = _hook_triples(claude_data)

    def describe(event: str, matcher: str, command: str) -> str:
        return f"{event}" + (f" (matcher `{matcher}`)" if matcher else "") + f" -> `{command}`"

    for event, matcher, command in sorted(claude_triples - codex_triples):
        findings.append(
            Finding(
                ".codex/hooks.json",
                f"missing {describe(event, matcher, command)}, which .claude/settings.json "
                "runs.\n"
                "  A hook armed for Claude Code and not for Codex is a guard some sessions "
                "skip. Add the same event, matcher and command here.",
            )
        )
    for event, matcher, command in sorted(codex_triples - claude_triples):
        findings.append(
            Finding(
                ".claude/settings.json",
                f"does not run {describe(event, matcher, command)}, which .codex/hooks.json "
                "runs.\n"
                "  Either arm it here too, or drop it from .codex/hooks.json — a hook only "
                "Codex runs is one no Claude Code session's behavior reflects, and the two "
                "tools are meant to read the same guards.",
            )
        )

    for event, _matcher, command in sorted(codex_triples | claude_triples):
        script = command.split()[0] if command else ""
        if script and not exists(ROOT / script):
            findings.append(
                Finding(
                    script,
                    f"the {event} hook names `{command}` and no such file exists in the tree.",
                )
            )

    report.add(
        "codex hooks",
        MECHANICAL,
        findings,
        f"{len(claude_triples)} hooks in .claude/settings.json, all mirrored in "
        f".codex/hooks.json",
        scanned=len(claude_triples),
    )


def check_map_sections(report: Report) -> None:
    """Every top-level section of docs/map.py is read by something, and the docstring's
    consumer list is true.

    **`TRACKS` is why this row exists.** It sat in that file from 2026-08-07 to 2026-08-31
    with no reader anywhere in the repo and no check over it, and it went wrong twice
    without anything being able to tell: it said `C1-C7` after `docs/CODES-DECISIONS.md`
    had reached C11, and it said the codes track's delivery automation was gated on Gate B
    months after that gate passed and the gating system was retired outright. Three weeks
    wrong, in the file whose entire argument — D17 — is that it is audited exactly as hard
    as it is trusted.

    **A section with no consumer is worse than a section that is wrong**, which is the part
    worth stating. Wrong-with-a-reader gets found the first time somebody runs the reader.
    Wrong-with-no-reader is a claim the repo makes about itself that has no way of ever
    being contradicted, and it decays silently while looking exactly like the sections that
    do work. The remedy is the one this repo reaches for everywhere else: give it a job, or
    delete it (D80). `TRACKS` got a job — `scripts/decision-context.py` routes a `codes/` edit to
    C decisions by it, and `scripts/status.py` declares it in SOURCES.

    MECHANICAL. Each of the three conditions is decidable on the committed tree, which is
    D16's test: a name is read or it is not, a count matches or it does not, a path exists
    or it does not. There is no judgement here for a blocking row to settle by fiat.
    """
    findings: List[Finding] = []
    sections = _map_sections()
    if not sections:
        report.add("map sections", MECHANICAL,
                   [Finding(rel(MAP), "no top-level sections could be read.")])
        return

    haystack: Dict[str, str] = {}
    for path in python_files() + list(_walk(ROOT / "scripts", (".mjs", ".sh"))):
        if rel(path) in _SECTION_SKIP or not exists(path):
            continue
        haystack[rel(path)] = read(path)

    readers: Dict[str, List[str]] = {}
    for name in sections:
        hits = sorted(where for where, text in haystack.items() if name in text)
        readers[name] = hits
        if not hits:
            findings.append(Finding(
                f"{rel(MAP)} -> {name}",
                f"`{name}` is a top-level section of the map that NOTHING reads. Give it a "
                f"consumer or delete it: a section no code reads cannot be caught being "
                f"wrong, and `TRACKS` was wrong for three weeks exactly this way (D17, D80).",
            ))

    word, rows = _consumer_block()
    if word is None:
        findings.append(Finding(
            rel(MAP),
            "its docstring no longer says `Read by <word> consumers`, so the consumer list "
            "is reconciled against nothing. Restore the sentence or re-point this check.",
        ))
    else:
        declared = _NUMBER_WORDS.get(word)
        if declared is None:
            findings.append(Finding(rel(MAP), f"`Read by {word} consumers` is not a number this check knows."))
        elif declared != len(rows):
            findings.append(Finding(
                rel(MAP),
                f"the docstring says {word} consumers and lists {len(rows)}: "
                f"{', '.join(rows) or 'none'}.",
            ))
        for row in rows:
            if "/" in row and not row.endswith("/") and not exists(ROOT / row):
                findings.append(Finding(
                    rel(MAP),
                    f"the docstring names `{row}` as a consumer and no such file exists.",
                ))

    covered = sum(1 for name in sections if readers[name])
    report.add("map sections", MECHANICAL, findings,
               f"{covered} of {len(sections)} sections have a reader, consumer list agrees",
               scanned=len(sections))


# ------------------------------------------------- the build order against its own source

# The numbered lists under `## What shipped` and `## What is open` in docs/GATES.md, which
# docs/map.py's SHIPPED and OPEN say in their own header that they mirror. Each is bounded
# at the next `## ` so a numbered list anywhere else in that file cannot join in.
# A STEP IS ITS LIST MARKER, AND AN UNCLAIMED ONE CANNOT BE (D80 amended 2026-09-11).
# Markdown has no ordered-list marker that can hold `merge-time-ids`, so a step whose number is
# not allocated yet is written with a `0.` marker carrying its slug in backticks, and
# `scripts/claim-ids.py` rewrites both the marker and the token at merge time:
#
#   a `0.` marker, then the slug in backticks after the word `step`, then the title.
#
# D80's ruling that `n` is STABLE and never renumbered is untouched by this and is the reason
# for it: what that entry fears is D72's citation drift over 218 references to `step <n>`, and
# a number claimed at the merge cannot collide, so nothing is ever renumbered to resolve one.
_GATES_STEP = re.compile(r"^(\d+)\.\s", re.M)
_GATES_STEP_SLUG = re.compile(r"^0\.\s+`step (" + _STEP_SLUG + r")`", re.M)


def check_build_order_mirror(report: Report) -> None:
    """docs/map.py's SHIPPED and OPEN ids are docs/GATES.md's two lists, in both directions.

    The map has claimed to mirror that file since 2026-08-04 and nothing checked it, which is
    this repo's recurring failure class — two decisions that must agree, only one of which
    moves — sitting on the sentence that says they agree.

    **Ids, and which list they are in. Deliberately not the titles or the prose.** The two
    files word a step differently on purpose and GATES.md marks one done by striking it
    through rather than by a field, so reconciling text would fail on files that are both
    correct. What must be identical is the id set per list, because that is the whole of what
    `mirrors` promises — and a step landing in one file and not the other, or done in one and
    open in the other, is the only drift that has happened here.

    **This row is what made culling step 12 a two-file edit instead of a four-file one.**
    GATES.md used to carry a paragraph explaining that steps were APPENDED rather than
    inserted because renumbering "would have to land in four files at once" and nothing
    watched them. One of those files now watches the other three (D80).
    """
    text = gates_text()
    if not exists(MAP) or not text:
        report.add("build order mirror", MECHANICAL,
                   [Finding("docs/", "docs/map.py is missing, or docs/GATES.md's corpus "
                                     "(docs/gates/) read as empty or unreadable.")])
        return

    data = literals_from_module(MAP)
    findings: List[Finding] = []
    total = 0

    for name, heading in (("SHIPPED", "What shipped"), ("OPEN", "What is open")):
        mine = {row.get("n") for row in (data.get(name) or [])}
        start = re.search(r"^##\s+" + re.escape(heading) + r"\s*$", text, re.M)
        if start is None:
            findings.append(Finding(
                "docs/GATES.md",
                f"has no `## {heading}` heading, so docs/map.py's `{name}` is reconciled "
                f"against nothing.",
            ))
            continue
        rest = text[start.end():]
        stop = re.search(r"^##\s", rest, re.M)
        window = rest[: stop.start() if stop else len(rest)]
        # `0.` is the unclaimed marker and never an id, so it is read as its slug and not as 0.
        listed = {int(n) for n in _GATES_STEP.findall(window) if n != "0"}
        listed |= set(_GATES_STEP_SLUG.findall(window))
        total += len(mine)
        for number in sorted(listed - mine, key=str):
            findings.append(Finding(
                "docs/map.py",
                f"docs/GATES.md lists step {number} under `{heading}`; the map's `{name}` "
                f"has no such id.",
            ))
        for number in sorted(mine - listed, key=str):
            findings.append(Finding(
                "docs/GATES.md",
                f"the map's `{name}` has step {number}; `## {heading}` does not list it.",
            ))

    report.add("build order mirror", MECHANICAL, findings,
               f"{total} steps, the same ids in both files, in the same two lists",
               scanned=total)



def observed_triples(committed_only: bool) -> Set[Tuple[str, str, str]]:
    return {
        triple
        for facts in export_facts()
        if not (committed_only and not facts.committed)
        for triple in facts.triples
    }


def game_entries() -> Tuple[Dict[str, object], List[Finding]]:
    """The registry's literals, or the one finding that says why there are none."""
    if not exists(GAMES_MODULE):
        return {}, [Finding(rel(GAMES_MODULE), "does not exist")]
    data = literals_from_module(GAMES_MODULE)
    if not data.get("GAMES"):
        return {}, [
            Finding(
                rel(GAMES_MODULE),
                "no GAMES literal could be read. The registry is read with "
                "`ast.literal_eval` and never imported, so every entry must be a plain "
                "literal — a name, a call or an f-string inside one makes the whole "
                "registry unreadable to this check rather than only that field.",
            )
        ]
    return data, []


def _claimed_by(entry: Dict[str, object]) -> Set[str]:
    """Every `Rarity` cell this entry accounts for, claimed as a stack or not."""
    return (
        set(entry.get("rarities") or ())
        | set(entry.get("rarities_not_claimed") or ())
        | set(entry.get("product_line_rarities") or ())
    )


def check_game_vocabulary(report: Report) -> None:
    """`pipeline/games.py`'s shape, and the two export findings that cannot false-positive.

    **Structure first, because everything downstream reads these fields.** Required keys
    present, no unknown ones, keys unique, `finish_by_rarity` confined to the rarities and
    finishes the same entry declares, `condition_by_finish` covering exactly the finish
    enum, `join_key` and `prompt` naming a strategy the module publishes, and the entry
    sitting squarely in ONE of the registry's three states rather than between two of them.
    Each of those is the shape of a literal, and the shape of a literal is provable — there
    is no context this script is missing, which is what makes the row blocking.

    **The three states are `catalogued` x `unverified`, and keeping them apart is the
    newest thing this row does.** `unverified: True` is a measurement somebody owes and a
    consumer must refuse until it arrives. `catalogued: False` is the finished answer for a
    game that spans several product lines at once — `misc`, roughly 1% of the shelf — and
    it must never refuse in the same voice, or every one of those captures reads as a fault
    and a genuinely unmeasured game hides among them. So the flags are separate, an entry
    setting both is a finding, and each state pins `product_line`, `rarities`, `join_key`
    and `card_aspect` to a shape the other two cannot wear.

    **Then the two export questions that are not questions.** A rarity whose *folded* form
    matches a cell in a committed export while its raw form matches nothing is a typo:
    `Illustration  Rare` for `Illustration Rare`, `double rare` for `Double Rare`. It can
    never false-positive, because the fold only fires when the export contains the same
    string modulo case and punctuation. And a cell in a committed export that no entry
    accounts for is a gap in the registry, provable in the same direction.

    `rarities_not_claimed` is what makes the second one liveable. `Code Card` is a Pokemon
    rarity that the `pokemon` game never offers as a stack claim — `pokemon_code` claims it
    — so accounting for a cell and claiming it have to be different things, or every entry
    would have to lie about its own picker to keep this row quiet.
    """
    data, findings = game_entries()
    if findings:
        report.add("game vocabulary", MECHANICAL, findings)
        return

    entries = list(data["GAMES"])
    join_keys = set(data.get("JOIN_KEY_STRATEGIES") or ())
    prompts = set(data.get("PROMPT_STRATEGIES") or ())
    bands = set(data.get("CROP_BAND_NAMES") or ())
    where_module = rel(GAMES_MODULE)

    seen: Set[str] = set()
    for entry in entries:
        key = str(entry.get("key", "?"))
        where = f"{where_module} -> {key}"
        if key in seen:
            findings.append(Finding(where, f"two entries claim the key {key!r}."))
        seen.add(key)

        missing = sorted(GAME_REQUIRED_KEYS - set(entry))
        if missing:
            findings.append(Finding(where, f"missing required fields: {', '.join(missing)}."))
        unknown = sorted(set(entry) - GAME_REQUIRED_KEYS - GAME_OPTIONAL_KEYS)
        if unknown:
            findings.append(
                Finding(
                    where,
                    f"unknown fields: {', '.join(unknown)}. A field no consumer reads is a "
                    f"field nothing keeps honest — add it to GAME_REQUIRED_KEYS here when "
                    f"it becomes real, or drop it.",
                )
            )

        rarities = set(entry.get("rarities") or ())
        finishes = set(entry.get("finishes") or ())
        conditions = entry.get("condition_by_finish") or {}
        matrix = entry.get("finish_by_rarity") or {}

        for rarity, allowed in matrix.items():
            if rarity not in rarities:
                findings.append(
                    Finding(where, f"finish_by_rarity keys {rarity!r}, which is not in `rarities`.")
                )
            stray = sorted(set(allowed or ()) - finishes)
            if stray:
                findings.append(
                    Finding(
                        where,
                        f"finish_by_rarity[{rarity!r}] names {', '.join(stray)}, which is "
                        f"not in this entry's `finishes`.",
                    )
                )
        if set(conditions) != finishes:
            findings.append(
                Finding(
                    where,
                    f"condition_by_finish covers {sorted(set(conditions))} but `finishes` is "
                    f"{sorted(finishes)}. Every finish needs exactly one condition string, "
                    f"and a condition string with no finish is unreachable.",
                )
            )

        # D76's per-game fetch width. Two provable things and nothing softer: the value is
        # one of the two the registry publishes, and `category` — the claim that a whole
        # TCGplayer category comes down in one file — cannot be authored for a game naming
        # no category to fetch. Both are the shape of a literal, which is what keeps this row
        # blocking rather than advisory.
        scope = entry.get("export_scope")
        if scope is not None:
            if scope not in set(data.get("EXPORT_SCOPES") or ()):
                findings.append(
                    Finding(
                        where,
                        f"export_scope {scope!r} is not one of "
                        f"{', '.join(sorted(data.get('EXPORT_SCOPES') or ()))}.",
                    )
                )
            elif scope == "category" and not entry.get("tcgplayer_category_id"):
                findings.append(
                    Finding(
                        where,
                        "export_scope is `category` but the entry names no "
                        "`tcgplayer_category_id`, so there is no category to fetch whole.",
                    )
                )

        # THE HINT REQUIREMENT, AND ITS EVIDENCE, WHICH MAY NOT TRAVEL APART.
        #
        # `export_needs_hint` refuses a real run — it is the only field here that can stop
        # an operator mid-pipeline — and it is a JUDGEMENT ABOUT A NUMBER: that this game's
        # whole category is too close to `tcg_export.MAX_BYTES` to widen into on a guess.
        # Authored without `export_category_bytes` beside it, that judgement is unarguable
        # and unre-makeable by the next person to read the entry, so it is refused.
        #
        # AND IT IS REFUSED ON A `category` GAME, which would be a DEAD field rather than a
        # wrong one: `_scope_for_run` only reaches the question where the CARDS widened the
        # scope, and a game that always fetches its whole category widens by policy and
        # never gets there. A rule that cannot fire is worse than no rule, which is the
        # argument `NOT_JOINED_STRATEGY` above is written out for.
        needs_hint = entry.get("export_needs_hint")
        measured = entry.get("export_category_bytes")
        if needs_hint is not None and not isinstance(needs_hint, bool):
            findings.append(
                Finding(
                    where,
                    f"export_needs_hint is {needs_hint!r}, which is not a boolean. It "
                    f"gates a refusal; it may not be a string that is merely truthy.",
                )
            )
        elif needs_hint:
            if not isinstance(measured, int) or isinstance(measured, bool) or measured <= 0:
                findings.append(
                    Finding(
                        where,
                        "export_needs_hint is authored but `export_category_bytes` is not a "
                        "positive integer. The requirement is a judgement about how wide "
                        "this game's whole category is, so the measurement has to sit "
                        "beside it — the refusal quotes it to the operator.",
                    )
                )
            if not entry.get("tcgplayer_category_id"):
                findings.append(
                    Finding(
                        where,
                        "export_needs_hint is authored but the entry names no "
                        "`tcgplayer_category_id`, so there is no export for a hint to "
                        "narrow.",
                    )
                )
            if scope == "category":
                findings.append(
                    Finding(
                        where,
                        "export_needs_hint is authored beside `export_scope: category`. "
                        "That game widens by policy and never reaches the cards, so the "
                        "requirement could never fire.",
                    )
                )
        if measured is not None and (
            not isinstance(measured, int) or isinstance(measured, bool) or measured <= 0
        ):
            findings.append(
                Finding(
                    where,
                    f"export_category_bytes is {measured!r}, which is not a positive "
                    f"integer of bytes.",
                )
            )

        if entry.get("join_key") not in join_keys:
            findings.append(
                Finding(
                    where,
                    f"join_key {entry.get('join_key')!r} is not one of "
                    f"JOIN_KEY_STRATEGIES ({', '.join(sorted(join_keys))}).",
                )
            )
        if entry.get("prompt") not in prompts:
            findings.append(
                Finding(
                    where,
                    f"prompt {entry.get('prompt')!r} is not one of PROMPT_STRATEGIES "
                    f"({', '.join(sorted(prompts))}).",
                )
            )
        stray_bands = sorted(set(entry.get("crop_bands") or ()) - bands)
        if stray_bands:
            findings.append(
                Finding(
                    where,
                    f"crop_bands names {', '.join(stray_bands)}, which geometry/crop.py does "
                    f"not cut. CROP_BAND_NAMES is the list of regions that exist.",
                )
            )

        # THREE STATES, AND THE ROW THAT KEEPS THEM APART. `catalogued` and `unverified`
        # answer different questions and an entry that blurs them is the failure this
        # block exists for: "nobody has measured this yet, refuse until someone does" and
        # "there is no catalog and there never will be" have opposite remedies, and a
        # single flag serving both makes every `misc` capture read as a fault while a
        # genuinely unmeasured game hides among them.
        #
        # Provable from the literal alone, which is why it blocks: an entry is in exactly
        # one of the three states below, and each state fixes the shape of the same four
        # fields.
        catalogued = bool(entry.get("catalogued"))
        unverified = bool(entry.get("unverified"))
        product_line = entry.get("product_line")
        aspect = entry.get("card_aspect")

        if not catalogued:
            if unverified:
                findings.append(
                    Finding(
                        where,
                        "catalogued is False AND unverified is True. These are different "
                        "states with opposite remedies — unverified is a measurement "
                        "somebody owes, uncatalogued is the finished answer for a game "
                        "that spans several product lines at once. An entry claiming both "
                        "tells a consumer to wait for an export that is not coming.",
                    )
                )
            if product_line is not None:
                findings.append(
                    Finding(
                        where,
                        f"catalogued is False but product_line is {product_line!r}. It must "
                        f"be None: a game with no catalog has no `Product Line` cell, and "
                        f"None is not a str, so no export row can ever compare equal to it. "
                        f"An empty string is both a value a row could carry and the value "
                        f"an unverified entry uses, which collapses the two states on the "
                        f"one field that most needs to tell them apart.",
                    )
                )
            for field in ("rarities", "finishes", "finish_by_rarity", "condition_by_finish"):
                if entry.get(field):
                    findings.append(
                        Finding(
                            where,
                            f"catalogued is False but {field} is not empty. There is no "
                            f"export to author it against and none is coming, so a value "
                            f"here was reasoned out rather than measured.",
                        )
                    )
            if entry.get("join_key") != NOT_JOINED_STRATEGY:
                findings.append(
                    Finding(
                        where,
                        f"catalogued is False but join_key is {entry.get('join_key')!r}. It "
                        f"must be {NOT_JOINED_STRATEGY!r} — a game with no catalog never "
                        f"reaches one, and a strategy name that builds a key says the "
                        f"opposite to anything dispatching on it.",
                    )
                )
            if aspect is not None:
                findings.append(
                    Finding(
                        where,
                        f"catalogued is False but card_aspect is {aspect!r}. A game that "
                        f"spans product lines spans card sizes with them, so a single "
                        f"ratio here is a guess about whichever card is in hand. None is "
                        f"the honest value, and nothing detects or crops these cards.",
                    )
                )
        else:
            if aspect is None:
                findings.append(
                    Finding(
                        where,
                        "card_aspect is None on a catalogued game. None is reserved for the "
                        "uncatalogued case, where there is genuinely no single card size; a "
                        "game with one product line has one, measured off the cardboard.",
                    )
                )
            if unverified and rarities:
                findings.append(
                    Finding(
                        where,
                        "unverified is True but `rarities` is not empty. Unverified means no "
                        "export has been seen; a vocabulary that arrived without one is a "
                        "guess, which is the thing D22 refuses.",
                    )
                )
            if not unverified and not rarities:
                findings.append(
                    Finding(
                        where,
                        "`rarities` is empty but unverified is False and catalogued is True. "
                        "An empty vocabulary must say which of the two reasons it is empty "
                        "for, because every consumer refuses on one and a silent empty entry "
                        "reads as a game that works.",
                    )
                )
            if unverified and str(product_line or "").strip():
                findings.append(
                    Finding(
                        where,
                        f"unverified is True but product_line is {product_line!r}. The cell "
                        f"is measured off an export, so an entry that has one has seen one.",
                    )
                )
            if not unverified and not str(product_line or "").strip():
                findings.append(
                    Finding(
                        where,
                        "product_line is empty on a catalogued entry that is not marked "
                        "unverified.",
                    )
                )

    # The two export findings. Committed fixtures only — see the section note.
    by_line = observed_rarities(committed_only=True)
    accounted: Dict[str, Set[str]] = {}
    for entry in entries:
        line = str(entry.get("product_line") or "").strip()
        if not line:
            continue
        accounted.setdefault(line, set()).update(_claimed_by(entry))
        observed = by_line.get(line) or set()
        folded = {fold_cell(cell): cell for cell in observed}
        for authored in sorted(_claimed_by(entry)):
            if authored in observed:
                continue
            match = folded.get(fold_cell(authored))
            if match is not None:
                findings.append(
                    Finding(
                        f"{where_module} -> {entry.get('key')}",
                        f"rarity {authored!r} does not appear in any committed export, but "
                        f"{match!r} does and the two differ only in case or punctuation. "
                        f"The export's cell is the one that has to win — the string is "
                        f"joined on and rendered verbatim.",
                    )
                )

    checked = 0
    for line, cells in sorted(by_line.items()):
        for cell in sorted(cells):
            checked += 1
            if cell in (accounted.get(line) or set()):
                continue
            findings.append(
                Finding(
                    where_module,
                    f"a committed export carries `Product Line` {line!r} with `Rarity` "
                    f"{cell!r}, and no entry accounts for it. Add it to the game that "
                    f"claims it, or to another game's `rarities_not_claimed` if it belongs "
                    f"to a different capture choice sharing this product line.",
                )
            )

    report.add(
        "game vocabulary",
        MECHANICAL,
        findings,
        f"{len(entries)} games, {checked} export rarities accounted for",
        scanned=len(entries),
    )


def check_game_coverage(report: Report) -> None:
    """What the exports in view do not corroborate. Prints; never blocks.

    **Absence from one set proves nothing, and that is the whole reason this row is
    separate.** `Promo`, `Radiant Rare`, `Amazing Rare` and every pre-SV rarity are
    legitimately missing from an SV09 fixture, and D23 REQUIRES `finish_by_rarity` to
    exceed what any one export stocks — SV09 carries no plain Near Mint `Rare` row, and a
    matrix narrowed to that observation would make a real plain-NM `Rare` stack unclaimable
    behind an unselectable chip. So the excess is a question by construction, and the row
    that blocks is `matrix superset`, which asks the same question the other way round.

    Opt-in `PKMNSCAN_EXPORTS` files feed this row and only this row. An operator with a
    full-catalog export gets every question asked against it without any of them being able
    to stop a commit on a machine that does not have the file.
    """
    data, findings = game_entries()
    if findings:
        report.add("game coverage", ADVISORY, findings)
        return

    entries = list(data["GAMES"])
    where_module = rel(GAMES_MODULE)
    sources = export_facts()
    by_line = observed_rarities(committed_only=False)
    triples = observed_triples(committed_only=False)

    accounted: Dict[str, Set[str]] = {}
    for entry in entries:
        key = entry.get("key")
        where = f"{where_module} -> {key}"
        line = str(entry.get("product_line") or "").strip()
        if not line:
            continue  # an unverified game authors nothing to corroborate
        observed = by_line.get(line) or set()
        accounted.setdefault(line, set()).update(_claimed_by(entry))
        if not observed:
            findings.append(
                Finding(
                    where,
                    f"`Product Line` {line!r} appears in no export in view. Set "
                    f"{EXPORTS_ENV} to a colon-separated list of exports to widen this.",
                )
            )
            continue
        for authored in sorted(_claimed_by(entry) - observed):
            findings.append(
                Finding(where, f"rarity {authored!r} appears in no export in view.")
            )
        conditions = entry.get("condition_by_finish") or {}
        for finish, condition in sorted(conditions.items()):
            if not any(
                line_seen == line and cond == condition for line_seen, _, cond in triples
            ):
                findings.append(
                    Finding(
                        where,
                        f"condition {condition!r} (finish {finish!r}) appears in no export "
                        f"in view.",
                    )
                )
        for rarity, allowed in sorted((entry.get("finish_by_rarity") or {}).items()):
            for finish in allowed or ():
                condition = conditions.get(finish)
                if condition is None:
                    continue
                if (line, rarity, condition) not in triples:
                    findings.append(
                        Finding(
                            where,
                            f"finish_by_rarity allows {rarity} / {finish}, and no export in "
                            f"view stocks {rarity!r} as {condition!r}. Expected where the "
                            f"matrix is deliberately a superset (D23); a question, not a "
                            f"defect.",
                        )
                    )

    for facts in sources:
        if facts.committed:
            continue  # the blocking row already answered for these
        for line, cells in sorted(facts.rarities.items()):
            for cell in sorted(cells - (accounted.get(line) or set())):
                findings.append(
                    Finding(
                        facts.source,
                        f"`Product Line` {line!r} / `Rarity` {cell!r} is accounted for by no "
                        f"entry. Read from {EXPORTS_ENV}, so this asks rather than blocks.",
                    )
                )

    committed = sum(1 for facts in sources if facts.committed)
    report.add(
        "game coverage",
        ADVISORY,
        findings,
        f"{committed} committed exports, {len(sources) - committed} opt-in",
        scanned=len(sources),
    )


def check_matrix_superset(report: Report) -> None:
    """An observed (rarity, finish) pair that `finish_by_rarity` does not allow.

    **This is the row that keeps D23's unselectable finish chips honest, and it only ever
    reads in one direction.** The capture screen renders a chip excluded by a rarity claim
    as unselectable rather than hidden; that is safe while the matrix is a superset of
    reality and a trap the moment it is not, because the operator would have no way to say
    what is true about the card in their hand. So a pair an export PROVES exists and the
    matrix omits is a defect and blocks, while a pair the matrix allows and no export
    stocks is a question and belongs to `game coverage`.

    The finish is derived from the export's own `Condition` cell through the entry's
    `condition_by_finish`, inverted. A condition that maps to no finish — a graded or
    vintage string, which D12 puts out of scope — is skipped rather than reported: this row
    is about the matrix, and a condition the entry never claimed is not evidence about it.

    Committed fixtures only, like every blocking row here.
    """
    data, findings = game_entries()
    if findings:
        report.add("matrix superset", MECHANICAL, findings)
        return

    entries = list(data["GAMES"])
    where_module = rel(GAMES_MODULE)
    triples = observed_triples(committed_only=True)
    checked = 0

    for entry in entries:
        line = str(entry.get("product_line") or "").strip()
        rarities = set(entry.get("rarities") or ())
        if not line or not rarities:
            continue
        finish_by_condition = {
            condition: finish
            for finish, condition in (entry.get("condition_by_finish") or {}).items()
        }
        matrix = entry.get("finish_by_rarity") or {}
        for line_seen, rarity, condition in sorted(triples):
            if line_seen != line or rarity not in rarities:
                continue
            finish = finish_by_condition.get(condition)
            if finish is None:
                continue
            checked += 1
            if finish in set(matrix.get(rarity) or ()):
                continue
            findings.append(
                Finding(
                    f"{where_module} -> {entry.get('key')}",
                    f"a committed export stocks {rarity!r} as {condition!r}, so "
                    f"{rarity} / {finish} exists — and finish_by_rarity[{rarity!r}] is "
                    f"{tuple(matrix.get(rarity) or ())}. The matrix may only ever be a "
                    f"SUPERSET of what an export proves: widen it, never narrow it, or the "
                    f"capture screen renders that finish unselectable for a stack that "
                    f"really is that finish.",
                )
            )

    report.add(
        "matrix superset",
        MECHANICAL,
        findings,
        f"{checked} observed rarity/finish pairs, all allowed",
        scanned=checked,
    )


def check_join_key_shape(report: Report) -> None:
    """A `join_key` the export's own `Number` cells prove can never match a row.

    **The one thing about a join strategy an export can settle, and it settles it
    absolutely.** `number_and_printed_total` composes its key as
    `zfill(3)(number) + "/" + printedTotal`, so every key it can ever produce contains a
    `/`. `pipeline/join.py` indexes the catalog on the export's `Number` cell verbatim.
    Therefore: if not one non-blank `Number` cell under a game's `Product Line` contains a
    `/`, that strategy matches nothing, for every card, forever. There is no context this
    script is missing and no export that could make it come out differently — which is
    D16's test for mechanical, so it blocks.

    **One direction only, deliberately.** The reverse — a game on `printed_code` whose
    cells all carry denominators — is NOT a finding, because matching the printed
    identifier verbatim works perfectly well on `179/298`. Riftbound is exactly that case
    and it is the right authoring: 9540 of its rows carry a denominator and 450 do not
    (`R04`, `T02 // T03`), a per-game field holds one strategy, and the verbatim match is
    the only one of the two that covers both shapes. A row that flagged it would be
    punishing the entry for being correct.

    **`name_only` and `not_joined` are skipped rather than reasoned about.** A code card's
    rows are the blank-`Number` ones, so a `Number` column says nothing about them; a
    `misc` card has no product line to look up at all. Neither absence is evidence.

    **This row was written because One Piece would have been authored wrong without it.**
    Its whole catalogue is `OP15-079`, `EB04-042`, `ST26-005`, `P-105` — no denominator
    anywhere, and `printed_total` is a field with no referent for that game. Inheriting
    Pokemon's strategy is the obvious default and it would have produced a run that joined
    zero rows and blamed the export.

    Committed fixtures only, like every blocking row here.
    """
    data, findings = game_entries()
    if findings:
        report.add("join key shape", MECHANICAL, findings)
        return

    entries = list(data["GAMES"])
    where_module = rel(GAMES_MODULE)
    by_line: Dict[str, Set[str]] = {}
    for facts in export_facts():
        if not facts.committed:
            continue
        for line, cells in facts.numbers.items():
            by_line.setdefault(line, set()).update(cells)

    checked = 0
    for entry in entries:
        line = str(entry.get("product_line") or "").strip()
        strategy = entry.get("join_key")
        if not line or strategy != COMPOSED_STRATEGY:
            continue
        observed = by_line.get(line) or set()
        if not observed:
            continue  # no `Number` cells in view: no evidence, no finding
        checked += 1
        if any("/" in cell for cell in observed):
            continue
        findings.append(
            Finding(
                f"{where_module} -> {entry.get('key')}",
                f"join_key is {COMPOSED_STRATEGY!r}, which composes every key it produces "
                f"as `number + \"/\" + printedTotal` — and not one of the "
                f"{len(observed)} non-blank `Number` cells a committed export carries for "
                f"`Product Line` {line!r} contains a `/`. The catalog is indexed on that "
                f"cell verbatim, so this strategy matches nothing for every card of this "
                f"game. A catalogue with no denominator needs the strategy that matches "
                f"the printed identifier as printed.",
            )
        )

    report.add(
        "join key shape",
        MECHANICAL,
        findings,
        f"{checked} composed-key games checked against export Number cells",
        scanned=checked,
    )


# ------------------------------------------------------------------- the reason codes

# The labels moved out of ReviewQueue.tsx on 2026-08-25, when #/inventory's card panel began
# saying whether the selected card has an open question. Extracted rather than copied — the
# vocabulary's own docstring is the argument, and this check is half of what makes it work.
REVIEW_QUEUE_TSX = ROOT / "app" / "src" / "reasons.ts"
REASON_MODULES = ("pipeline/variant.py", "pipeline/routing.py")

_REASON_LABELS_RE = re.compile(r"const\s+REASON_LABELS\b[^{]*\{(.*?)\n\}", re.DOTALL)
_LABEL_KEY_RE = re.compile(r"^\s{2,}([a-z][a-z0-9_]*)\s*:", re.MULTILINE)
_BACKTICKED_RE = re.compile(r"`([a-z][a-z0-9_]*)`")


def self_named_strings(path: Path) -> Set[str]:
    """Module-level `NAME = "name"` constants — the shape every reason string is written in.

    A superset on purpose. `NORMAL = "normal"` and `LISTED = "listed"` match it too, and
    neither is a reason; this function is the ORACLE the published vocabularies are checked
    against, never the roster itself. Asking it "is `low_confidence` defined in
    pipeline/routing.py" is a question it answers exactly; asking it "which of these are
    reasons" is a question it cannot answer, and inventing a heuristic for that would put a
    guess on a blocking row.
    """
    if not exists(path):
        return set()
    try:
        tree = ast.parse(read(path))
    except SyntaxError:
        return set()
    found: Set[str] = set()
    for node in tree.body:
        targets: List[ast.AST] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == node.value.value.upper():
                found.add(node.value.value)
    return found


def design_reason_lists() -> Tuple[Dict[str, str], Optional[str]]:
    """docs/DESIGN.md's enumerated reason codes -> the module it attributes each to.

    The doc enumerates them as two parenthesised lists, each introduced by the module it
    credits. Parsed that way rather than by scraping every backticked snake_case token in
    the file, because the attribution is half of what this row reconciles: a reason moved
    between the ladder and routing without the doc following is exactly the drift D16 is
    for, and a flat set of strings could not see it.
    """
    design = ROOT / "docs" / "DESIGN.md"
    if not exists(design):
        return {}, "docs/DESIGN.md does not exist"
    flat = re.sub(r"\s+", " ", read(design))
    out: Dict[str, str] = {}
    for module in REASON_MODULES:
        pattern = re.escape(f"`{module}`") + r"\s*\(([^)]*)\)"
        lists = [
            match.group(1)
            for match in re.finditer(pattern, flat)
            if len(_BACKTICKED_RE.findall(match.group(1))) >= 2
        ]
        if len(lists) != 1:
            return {}, (
                f"docs/DESIGN.md should introduce exactly one parenthesised list of reason "
                f"codes with `{module}`; found {len(lists)}. This row reads that paragraph "
                f"— if it was rewritten, teach `design_reason_lists` the new shape rather "
                f"than reshaping the prose to suit the parser."
            )
        for name in _BACKTICKED_RE.findall(lists[0]):
            out[name] = module
    return out, None


# The scorer's constants, by the DEFAULT_PARAMS key each one mirrors. Written out rather
# than derived by case conversion, because a rule that turns `dSeed` into `D_SEED` also
# turns a typo into a name that simply is not found — and "not found" is how a mirror stops
# being checked without anyone deciding to stop checking it.
MOTION_MIRROR = {
    "stillK": "STILL_K",
    "moveK": "MOVE_K",
    "dSeed": "D_SEED",
    "dFloor": "D_FLOOR",
    "noiseWindowMs": "NOISE_WINDOW_MS",
    "stillFractionMin": "STILL_FRACTION_MIN",
    "restQuantile": "REST_QUANTILE",
    "stillFrames": "STILL_FRAMES",
    "stillWindow": "STILL_WINDOW",
    "refractoryMs": "REFRACTORY_MS",
    "tNovel": "T_NOVEL",
    "presenceK": "PRESENCE_K",
    "presenceMin": "PRESENCE_MIN",
    "rescueK": "RESCUE_K",
    "rescueAfter": "RESCUE_AFTER",
    "maxMoveMs": "MAX_MOVE_MS",
    "uniformMinShare": "UNIFORM_MIN_SHARE",
    "uniformToe": "UNIFORM_TOE",
    "uniformShoulder": "UNIFORM_SHOULDER",
}

# Parameters the offline scorer deliberately does not carry, each with the reason. The list
# is checked in BOTH directions below: an entry naming a parameter that no longer exists is
# as much a finding as a parameter in neither map, because a stale excuse is how a real gap
# hides.
# EMPTY SINCE 2026-09-12. `tNovel` sat here for as long as the scorer replayed only the
# stillness and presence halves; `score-trace.py gain` now reads the scaled novelty between
# consecutive fires against it, so it is mirrored like the rest. The map stays, checked in
# both directions, so the next parameter the scorer does not need has somewhere to say why.
MOTION_UNMIRRORED: Dict[str, str] = {}

_NUMERIC = re.compile(r"^[\d.\s()*/+-]+$")


def _motion_number(text: str) -> Optional[float]:
    """A parameter's value as a number, or None if it is not plain arithmetic.

    `moveK` is written `(2.0 * 16) / 9` in both files — the same expression, deliberately,
    so the 16:9 argument survives — so this cannot be a literal parse. It refuses anything
    that is not digits and operators rather than widening: an unreadable value is REPORTED
    below, never skipped, because a silently skipped parameter is an unchecked mirror.
    """
    body = text.strip().rstrip(",")
    if not _NUMERIC.match(body):
        return None
    try:
        return float(eval(body, {"__builtins__": {}}, {}))  # noqa: S307 - guarded above
    except (SyntaxError, ValueError, ZeroDivisionError, TypeError):
        return None


def check_motion_params(report: Report) -> None:
    """`app/src/motion.ts`'s DEFAULT_PARAMS and `scripts/score-trace.py`'s mirror agree.

    THE SCORER IS A SECOND IMPLEMENTATION OF THE MACHINE, and it exists because the first
    one runs in a browser at a rig. Every threshold in this subsystem was chosen by replaying
    saved traces through `scripts/score-trace.py`, and T9 asserts its counts — so a constant
    moved in `motion.ts` and not in the scorer does not fail anything. It makes the harness
    grade a machine nobody is running, and grade it GREEN, which is worse than no grade.

    THIS ROW WAS CLAIMED BEFORE IT EXISTED. `score-trace.py` has said since D81 that "`make
    docs-audit`'s `motion params` row is what keeps the two honest"; there was no such row.
    Two constants drifted apart for the length of that claim without consequence, and D84
    widened the mirror by two more. A comment naming a check that does not exist is worse
    than no comment: it is the reason the next session does not write one.

    Provably wrong when it fires, and no judgement to defer — both numbers are literals in
    the tree, and they either match or they do not.
    """
    findings: List[Finding] = []
    ts_path = ROOT / "app/src/motion.ts"
    py_path = ROOT / "scripts/score-trace.py"
    for path in (ts_path, py_path):
        if not exists(path):
            report.add("motion params", MECHANICAL,
                       [Finding(rel(path), f"{rel(path)} is missing.")], "")
            return

    block = re.search(
        r"export const DEFAULT_PARAMS: MotionParams = \{(.*?)\n\}", read(ts_path), re.S
    )
    if block is None:
        report.add("motion params", MECHANICAL, [Finding(
            rel(ts_path),
            "no `export const DEFAULT_PARAMS: MotionParams = {...}` to read. The mirror "
            "check cannot run, which means it is not running — say so here rather than "
            "passing.",
        )], "")
        return

    declared: Dict[str, str] = {}
    for line in block.group(1).splitlines():
        entry = re.match(r"\s*([A-Za-z][A-Za-z0-9_]*)\s*:\s*(.+?),?\s*$", line)
        if entry and not line.lstrip().startswith(("*", "/")):
            declared[entry.group(1)] = entry.group(2)

    scorer: Dict[str, str] = {}
    for line in read(py_path).splitlines():
        entry = re.match(r"^([A-Z][A-Z0-9_]*)\s*=\s*(.+?)\s*$", line)
        if entry:
            scorer[entry.group(1)] = entry.group(2)

    for name in sorted(set(declared) - set(MOTION_MIRROR) - set(MOTION_UNMIRRORED)):
        findings.append(Finding(rel(ts_path), (
            f"DEFAULT_PARAMS carries `{name}`, which is in neither MOTION_MIRROR nor "
            f"MOTION_UNMIRRORED in this file. Mirror it into scripts/score-trace.py, or "
            f"say in MOTION_UNMIRRORED why the offline scorer does not need it."
        )))
    for name in sorted((set(MOTION_MIRROR) | set(MOTION_UNMIRRORED)) - set(declared)):
        findings.append(Finding(rel(ts_path), (
            f"this file's mirror map names `{name}`, which DEFAULT_PARAMS no longer "
            f"declares. Remove the entry — a stale excuse reads as coverage."
        )))

    for name, constant in sorted(MOTION_MIRROR.items()):
        if name not in declared:
            continue
        if constant not in scorer:
            findings.append(Finding(rel(py_path), (
                f"`{constant}` is gone, but motion.ts still declares `{name}`. The offline "
                f"scorer is what chose every threshold in this subsystem and what T9 grades; "
                f"an absent constant makes it grade a different machine."
            )))
            continue
        here, there = _motion_number(declared[name]), _motion_number(scorer[constant])
        if here is None or there is None:
            findings.append(Finding(
                rel(ts_path if here is None else py_path),
                f"`{name}`/`{constant}` is not plain arithmetic, so the two cannot be "
                f"compared: {declared[name]!r} vs {scorer[constant]!r}. Keep both a number "
                f"or an expression over numbers.",
            ))
        elif here != there:
            findings.append(Finding(rel(py_path), (
                f"`{name}` is {declared[name].strip()} in app/src/motion.ts and "
                f"`{constant}` is {scorer[constant].strip()} here. The rig runs the first "
                f"and every saved trace is scored against the second."
            )))

    report.add(
        "motion params",
        MECHANICAL,
        findings,
        f"{len(MOTION_MIRROR)} mirrored constants agree, {len(MOTION_UNMIRRORED)} accounted for",
        scanned=len(MOTION_MIRROR),
    )


def check_supervisor_self_watch(report: Report) -> None:
    """Every project module the supervisor imports is in its own `SELF_FILES`.

    `scripts/serve.py` restarts ITSELF when a file it is made of changes — `os.execv`, same
    pid, children rebuilt. That list is hand-written, and a hand-written list of a file's own
    imports is exactly the thing that goes stale the next time somebody adds one.

    THE FAILURE IT PREVENTS IS SILENT, WHICH IS WHY IT BLOCKS. An import that is watched but
    absent from `SELF_FILES` still restarts the capture CHILD — visibly, in the log, looking
    like the change landing — while the supervisor goes on running the module it imported at
    boot, because Python caches it. Something restarts, so nothing looks wrong. That is how
    `server/ports.py` behaved before D53's amendment.

    Provably wrong when it fires, and no judgement to defer: the import is right there in the
    same file as the list that fails to mention it.
    """
    findings: List[Finding] = []
    path = ROOT / "scripts" / "serve.py"
    if not exists(path):
        report.add("supervisor self-watch", MECHANICAL,
                   [Finding(rel(path), "scripts/serve.py is missing.")], "")
        return

    tree = ast.parse(read(path))

    declared: Set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SELF_FILES":
                    try:
                        declared = set(ast.literal_eval(node.value))
                    except (ValueError, SyntaxError):
                        declared = set()

    # Module-level imports only: something imported inside a handler is not held across the
    # life of the process in the way that makes staleness possible.
    imported: Set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.replace(".", "/") + ".py")
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                imported.add(f"{node.module.replace('.', '/')}/{alias.name}.py")

    # Project-local means "resolves to a file in this repo". Stdlib and third-party do not,
    # and neither can go stale under us anyway — they are not what a `git pull` rewrites.
    local = {name for name in imported if (ROOT / name).is_file()}

    for name in sorted(local - declared):
        findings.append(
            Finding(
                rel(path),
                f"imports `{name}` at module scope but SELF_FILES does not list it. Python "
                f"caches that module, so a change to it leaves this supervisor running the "
                f"old code while its CHILD restarts and looks like the fix landed. Add it to "
                f"SELF_FILES.",
            )
        )

    report.add(
        "supervisor self-watch",
        MECHANICAL,
        findings,
        f"{len(declared)} self-files, every module-scope import accounted for",
        scanned=len(declared),
    )


def check_withhold_reasons(report: Report) -> None:
    """The three withhold reasons, reconciled across the two languages that declare them.

    D49 gives `overrides` a second kind of answer — a SKU the operator is deliberately not
    listing, carrying a reason — and the reason vocabulary is authored in `pipeline/
    decisions.py` and offered by `app/src/holds.ts`. That is two independent declarations of
    one closed set, which is exactly the shape `check_reason_codes` above exists for and
    exactly the drift D16 exists to catch.

    IT MATTERS MORE HERE THAN FOR THE REVIEW REASONS, and the reason is worth stating: `PUT
    /pipeline/runs/<name>/decisions` writes that document with NO VALIDATION AT ALL and says
    so in its own comment. The screen's defence against writing an unparseable file is that it
    builds the document from typed state and cannot construct a shape its own code does not
    know — and that defence is worth exactly as much as the two declarations agreeing.
    A reason the screen offers and the parser refuses is a run the operator cannot join.

    BLOCKING, because a mismatch is provably wrong rather than a question of judgement.

    THE HUMAN LABELS ARE NOT CHECKED and that is deliberate: `WITHHOLD_LABELS` is prose for a
    person, `docs/DESIGN.md` does not enumerate it, and a rule about wording would be this
    audit taking a view on English. What is checked is the machine string, which is the thing
    that has to match a parser.
    """
    findings: List[Finding] = []
    python_path = ROOT / "pipeline" / "decisions.py"
    ts_path = ROOT / "app" / "src" / "holds.ts"

    authored: Set[str] = set()
    for node in ast.walk(ast.parse(read(python_path))):
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "WITHHOLD_REASONS" not in names:
            continue
        try:
            authored = set(ast.literal_eval(node.value))
        except (ValueError, SyntaxError):
            findings.append(
                Finding(
                    "pipeline/decisions.py",
                    "WITHHOLD_REASONS is not a literal this audit can read. It is a "
                    "hand-authored vocabulary in D22's sense and has to stay one.",
                )
            )

    ts_text = read(ts_path)
    match = re.search(r"WITHHOLD_REASONS\s*=\s*\[(.*?)\]", ts_text, re.S)
    offered: Set[str] = set(re.findall(r"'([^']+)'", match.group(1))) if match else set()

    if not authored:
        findings.append(
            Finding("pipeline/decisions.py", "WITHHOLD_REASONS is missing or empty.")
        )
    if match is None:
        findings.append(
            Finding(
                "app/src/holds.ts",
                "no WITHHOLD_REASONS array — the screen has to declare the vocabulary it "
                "offers, in one place, or nothing can reconcile it with the parser.",
            )
        )

    for reason in sorted(offered - authored):
        findings.append(
            Finding(
                "app/src/holds.ts",
                f"{reason!r} is offered by the screen and is not in "
                f"pipeline/decisions.py:WITHHOLD_REASONS — `_withheld` refuses it, so "
                f"choosing it writes an inventory/prices.json the next join cannot read.",
            )
        )
    for reason in sorted(authored - offered):
        findings.append(
            Finding(
                "app/src/holds.ts",
                f"{reason!r} is authored in pipeline/decisions.py and the screen does not "
                f"offer it — legal in the file, unreachable from the product.",
            )
        )

    report.add(
        "withhold reasons",
        MECHANICAL,
        findings,
        f"{len(authored)} authored, offered by the screen, none unreachable",
        scanned=len(authored),
    )


def check_order_reasons(report: Report) -> None:
    """The six order-line reasons, reconciled across the two languages that declare them.

    D69's order screen looks a reason UP rather than re-deriving it from whatever the line
    carries beside it, so `app/src/orderReasons.ts:ORDER_REASONS` is a second independent
    declaration of `pipeline/orders.py:LINE_REASONS`. That is the shape `check_reason_codes`
    and `check_withhold_reasons` above both exist for, and exactly the drift D16 exists to
    catch. `orderReasons.ts`'s own header asserts in writing that this check exists; without
    it that paragraph would name a control that is not there, which is the failure
    `app/eslint.config.js`'s header calls worse than admitting there is none.

    THE COMPILER ALREADY DOES THE OTHER HALF AND CANNOT DO THIS ONE. Within the app,
    `ORDER_REASONS` carries `satisfies readonly OrderLineReason[]` and the two lookup tables
    are `Record<OrderLineReason, string>`, so the array cannot say a word the union does not
    and the tables cannot miss one. What no TypeScript can do is import a Python tuple: a
    reason `pipeline/orders.py` gains and this file does not is invisible until something
    compares the two files as text, and this is that something.

    BLOCKING, because a mismatch is provably wrong rather than a question of judgement. A
    reason the resolver emits and the screen has no entry for renders as its own machine
    string — `orderReasonLabel`'s `?? reason` fallback is deliberate and is not a repair —
    but the row then reads as a raw code to the one person who has to act on it, and the
    remedy beside it is blank.

    THE TUPLE IS READ THROUGH ITS OWN CONSTANTS, which is where this parts company with
    `check_withhold_reasons` one function up. `LINE_REASONS` is a tuple of NAMES
    (`RESOLVED`, `SHORT`, …) rather than of string literals, so `ast.literal_eval` cannot
    read it at all. The module's own `NAME = "literal"` assignments are collected first and
    the tuple's elements are resolved through them; a member that is neither a literal nor a
    name this file assigns a string to is REPORTED rather than skipped, because a silently
    dropped member would make this check quietly smaller than it looks.

    THE HUMAN LABELS AND REMEDIES ARE NOT CHECKED, for `check_withhold_reasons`' reason:
    they are prose for a person, and a rule about wording would be this audit taking a view
    on English. What is checked is the machine string, which is what has to match a resolver.
    """
    findings: List[Finding] = []
    python_path = ROOT / "pipeline" / "orders.py"
    ts_path = ROOT / "app" / "src" / "orderReasons.ts"

    tree = ast.parse(read(python_path))

    # Module-level `NAME = "literal"`, which is how this module spells its vocabulary.
    literals: Dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                literals[target.id] = node.value.value

    authored: Set[str] = set()
    seen_tuple = False
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "LINE_REASONS" for t in node.targets):
            continue
        seen_tuple = True
        if not isinstance(node.value, (ast.Tuple, ast.List)):
            findings.append(
                Finding(
                    "pipeline/orders.py",
                    "LINE_REASONS is not a tuple or list this audit can read. It is a "
                    "hand-authored vocabulary in D22's sense and has to stay one.",
                )
            )
            continue
        for element in node.value.elts:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                authored.add(element.value)
            elif isinstance(element, ast.Name) and element.id in literals:
                authored.add(literals[element.id])
            else:
                findings.append(
                    Finding(
                        "pipeline/orders.py",
                        "LINE_REASONS carries a member that is neither a string literal nor "
                        "a name this module assigns a string to, so this check cannot say "
                        "what the vocabulary is. Spell every member as a module-level "
                        "constant or as a literal.",
                    )
                )

    ts_text = read(ts_path)
    match = re.search(r"ORDER_REASONS\s*=\s*\[(.*?)\]", ts_text, re.S)
    offered: Set[str] = set(re.findall(r"'([^']+)'", match.group(1))) if match else set()

    if not seen_tuple or not authored:
        findings.append(
            Finding("pipeline/orders.py", "LINE_REASONS is missing or empty.")
        )
    if match is None:
        findings.append(
            Finding(
                "app/src/orderReasons.ts",
                "no ORDER_REASONS array — the screen has to declare the vocabulary it "
                "offers, in one place, or nothing can reconcile it with the resolver. A "
                "`Record`'s keys are a type and are erased; a text check needs a list.",
            )
        )

    for reason in sorted(offered - authored):
        findings.append(
            Finding(
                "app/src/orderReasons.ts",
                f"{reason!r} is offered by the screen and is not in "
                f"pipeline/orders.py:LINE_REASONS — no resolved line can ever carry it, so "
                f"it is a label, a remedy and a filter position for a state that cannot "
                f"happen.",
            )
        )
    for reason in sorted(authored - offered):
        findings.append(
            Finding(
                "app/src/orderReasons.ts",
                f"{reason!r} is authored in pipeline/orders.py and the screen does not "
                f"offer it — the resolver emits it and the row draws the raw machine string "
                f"with a blank remedy beside it.",
            )
        )

    report.add(
        "order reasons",
        MECHANICAL,
        findings,
        f"{len(authored)} authored, offered by the screen, none unreachable",
        scanned=len(authored),
    )


def check_terminal_statuses(report: Report) -> None:
    """The terminal-status vocabulary, reconciled between the code and its own published claim.

    D63 amended 2026-09-13 on the owner's two rulings — a Canceled order is never open, and
    an order the feed reports Shipped or Delivered closes on that word — and
    `store/orders.py:is_terminal_status` is where the vocabulary that answers both lives,
    exactly once, in `TERMINAL_STATUSES`. That set is hand-authored in D22's sense: it is not
    derivable from anything else in the tree, so a typo or a dropped entry is invisible to
    every other check here.

    THIS ROW ANSWERS FROM THE TREE ALONE, DELIBERATELY, WHICH IS `make lan-check`'s ARGUMENT
    APPLIED HERE. The honest reconciliation for a vocabulary like this is against the
    DISTINCT statuses a real feed has actually sent — `make docs-audit` cannot do that
    because it never opens `inventory/store.sqlite` and never will (that is what would make
    it `make lan-check`'s problem instead: a live-store dependency this audit's other ninety
    rows deliberately do not carry). So the second declaration this row reconciles against is
    not a store, it is the fenced `terminal-statuses` block inside
    `docs/decisions/D063-…md` itself — the decision entry's own published claim of what the
    set contains, written in a shape this function can parse directly. That fenced block is not decoration: a session amending `TERMINAL_STATUSES` in
    code without moving the block, or the reverse, fails this row rather than silently
    drifting apart, which is the whole of what D16 asks a hand-authored vocabulary to do.

    BLOCKING, for `check_withhold_reasons`' reason and it applies verbatim: whether the
    mechanism is any GOOD (whether the strings are the right ones to treat as terminal) is a
    judgement call the owner already made; whether the code and its own decision entry still
    agree about what was decided is arithmetic.

    THE COMPARISON IS EXACT-STRING, NEVER CASE-FOLDED, on purpose — this row is checking that
    two DECLARATIONS spell the same set the same way, which is a stricter question than
    whether two ORDER STATUSES refer to the same fact (that folding lives in
    `is_terminal_status` itself, at RUN time, and is unrelated to this comparison).
    """
    findings: List[Finding] = []
    python_path = ROOT / "store" / "orders.py"
    doc_path = ROOT / "docs" / "decisions" / "D063-the-order-ledger-is-two-maps-and-the-sync-writes-only-one.md"

    tree = ast.parse(read(python_path))
    authored: Optional[Set[str]] = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "TERMINAL_STATUSES" for t in node.targets):
            continue
        value = node.value
        # `frozenset({...})` — the call's first argument is the literal set this audit reads.
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "frozenset"
            and value.args
        ):
            value = value.args[0]
        try:
            authored = set(ast.literal_eval(value))
        except (ValueError, SyntaxError):
            findings.append(
                Finding(
                    "store/orders.py",
                    "TERMINAL_STATUSES is not a literal this audit can read. It is a "
                    "hand-authored vocabulary in D22's sense and has to stay one.",
                )
            )

    if authored is None:
        findings.append(
            Finding("store/orders.py", "TERMINAL_STATUSES is missing.")
        )
        authored = set()
    elif not authored:
        findings.append(
            Finding("store/orders.py", "TERMINAL_STATUSES is empty.")
        )

    if not exists(doc_path):
        findings.append(
            Finding(str(doc_path.relative_to(ROOT)), "does not exist — D63's amendment "
                    "cannot be checked against code that has moved past it.")
        )
        published: Set[str] = set()
    else:
        match = re.search(r"```terminal-statuses\n(.*?)```", read(doc_path), re.S)
        if match is None:
            findings.append(
                Finding(
                    str(doc_path.relative_to(ROOT)),
                    "carries no fenced `terminal-statuses` block — the decision entry has "
                    "to publish the set it settled on in a shape this script can parse, or "
                    "there is nothing here to reconcile the code against.",
                )
            )
            published = set()
        else:
            published = {line.strip() for line in match.group(1).splitlines() if line.strip()}

    for status in sorted(authored - published):
        findings.append(
            Finding(
                "store/orders.py",
                f"{status!r} is in TERMINAL_STATUSES and not in D63's published "
                f"`terminal-statuses` block — the code recognises a status the decision "
                f"entry never says it does.",
            )
        )
    for status in sorted(published - authored):
        findings.append(
            Finding(
                str(doc_path.relative_to(ROOT)),
                f"{status!r} is published in the `terminal-statuses` block and is not in "
                f"store/orders.py:TERMINAL_STATUSES — the decision entry claims a status "
                f"closes an order and the code does not recognise it.",
            )
        )

    report.add(
        "terminal statuses",
        MECHANICAL,
        findings,
        f"{len(authored)} authored, published in D63, none unreachable",
        scanned=len(authored),
    )


def check_pricing_presets(report: Report) -> None:
    """The three pricing presets, reconciled between the tuple that prices them and the
    table that writes them.

    `pipeline/pricing.py:PRESETS` is `(key, rule, basis)` and prices every SKU under every preset
    so the client performs no arithmetic on money. `app/src/Pricing.tsx:PRESETS` is what a
    press on the pricing screen writes into `inventory/prices.json` — and it has to write the RULE,
    because D49 refuses to write the suggestions themselves: an override is layer 1 of
    `prices_for` and would beat the rule at layer 4, producing a run where changing the preset
    silently changed nothing.

    THE DEFECT THAT PUT THIS ROW HERE IS THAT SAME FAILURE BY THE OTHER ROAD. The press wrote
    `preset: <key>`, a field `pipeline/decisions.py:parse` does not know and `to_payload` does
    not emit — so the next join dropped it and `rule`/`basis` never moved. Measured on the
    owner's riftbound run: `preset: market_undercut_5` beside `rule: match`, 2 overrides across
    50 SKUs, and 48 cards about to list at a price nobody had chosen. Nothing could see it: no
    check compared the two tables, and the screen never drew which rule was live.

    BLOCKING, for the reason `check_withhold_reasons` above gives and which applies here
    nearly verbatim: `PUT /pricing` refuses a rule `pricing.Rule.parse` cannot read, but a
    refused save is an answer that never landed, so two declarations agreeing is still the
    whole defence. A rule the screen writes and the parser refuses is a run `emit` cannot price.

    THE LABELS AND THE BLURBS ARE NOT CHECKED, the same carve-out and the same reason: they are
    prose for a person, and a rule about wording would be this audit taking a view on English.
    What is checked is the triple a parser has to accept.
    """
    findings: List[Finding] = []
    # THE TABLE MOVED TO `pipeline/pricing.py` ON 2026-09-07 AND THIS ROW FOLLOWED IT. Two
    # callers price presets now — a run's `pricing.json` and a markdown's `survey.json` — and
    # the second was shipping `presets: {}`, so every preset button on the lens filled nothing
    # while still writing the store's standing rule. `cli/cmd_join.py` re-exports the name its
    # own callers already spell, and a re-export is not a table this audit can read, which is
    # exactly what it said when the move happened.
    python_path = ROOT / "pipeline" / "pricing.py"
    ts_path = ROOT / "app" / "src" / "Pricing.tsx"

    # `PRESETS` NAMES `pricing.RULE_MATCH` RATHER THAN `"match"`, WHICH IS RIGHT AND IS WHY
    # THIS IS NOT A `literal_eval`. Referring to the constant is what keeps `cmd_join.py` from
    # being a fourth place a rule name is spelled; the cost is that reading it means resolving
    # `pricing.<NAME>` first. Resolved by `ast` out of `pipeline/pricing.py`, never by
    # importing — same rule D22 sets for the game registry and this script keeps for itself.
    constants: Dict[str, object] = {}
    for node in ast.walk(ast.parse(read(ROOT / "pipeline" / "pricing.py"))):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                constants[target.id] = node.value.value

    def resolved(node):
        """One PRESETS cell as its string, or None where this audit cannot say."""
        if isinstance(node, ast.Constant):
            return node.value
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "pricing"
        ):
            return constants.get(node.attr)
        # AND A BARE NAME, BECAUSE THE TABLE NOW LIVES IN THE MODULE THAT DEFINES THOSE
        # CONSTANTS. `cli/cmd_join.py` spelled them `pricing.RULE_MATCH`; inside
        # `pipeline/pricing.py` the same constant is `RULE_MATCH`, and a `pricing.` prefix
        # there would be a module referring to itself. Resolved against the SAME dict, so
        # there is still exactly one place a rule name is spelled and this row still
        # reconciles rather than going quietly green.
        if isinstance(node, ast.Name):
            return constants.get(node.id)
        return None

    authored: Set[tuple] = set()
    for node in ast.walk(ast.parse(read(python_path))):
        if not isinstance(node, ast.Assign):
            continue
        if "PRESETS" not in [t.id for t in node.targets if isinstance(t, ast.Name)]:
            continue
        if not isinstance(node.value, (ast.Tuple, ast.List)):
            findings.append(
                Finding(
                    "cli/cmd_join.py",
                    "PRESETS is not a table this audit can read. It is a hand-authored "
                    "table in D22's sense and has to stay one.",
                )
            )
            continue
        for row in node.value.elts:
            if not isinstance(row, (ast.Tuple, ast.List)) or len(row.elts) != 3:
                continue
            cells = [resolved(cell) for cell in row.elts]
            if all(isinstance(cell, str) for cell in cells):
                authored.add(tuple(cells))
            else:
                findings.append(
                    Finding(
                        "cli/cmd_join.py",
                        "a PRESETS row names something this audit cannot resolve to a "
                        "string. Spell it as a literal or as a `pricing.` constant, or this "
                        "row stops reconciling anything and goes quietly green.",
                    )
                )

    ts_text = read(ts_path)
    block = re.search(r"const PRESETS[^=]*=\s*\[(.*?)\n\]", ts_text, re.S)
    offered: Set[tuple] = set()
    if block is None:
        findings.append(
            Finding(
                "app/src/Pricing.tsx",
                "no PRESETS array — the screen has to declare the rule each preset writes, "
                "in one place, or nothing can reconcile it with the tuple that prices them.",
            )
        )
    else:
        for entry in re.findall(r"\{(.*?)\}", block.group(1), re.S):
            fields = dict(re.findall(r"(key|rule|basis):\s*'([^']*)'", entry))
            if {"key", "rule", "basis"} <= set(fields):
                offered.add((fields["key"], fields["rule"], fields["basis"]))
            elif "key" in fields:
                findings.append(
                    Finding(
                        "app/src/Pricing.tsx",
                        f"preset {fields['key']!r} declares no rule/basis pair. A press has "
                        f"to write one: writing anything else leaves the run at whatever rule "
                        f"it already had, which is the defect this row exists for.",
                    )
                )

    if not authored:
        findings.append(Finding("cli/cmd_join.py", "PRESETS is missing or empty."))

    for entry in sorted(offered - authored):
        findings.append(
            Finding(
                "app/src/Pricing.tsx",
                f"the screen writes {entry!r} and cli/cmd_join.py:PRESETS does not price it — "
                f"so the suggested numbers on screen are not what this rule emits.",
            )
        )
    for entry in sorted(authored - offered):
        findings.append(
            Finding(
                "app/src/Pricing.tsx",
                f"cli/cmd_join.py prices {entry!r} and the screen does not write it — priced "
                f"into every row of the pricing table, reachable from nothing.",
            )
        )

    report.add(
        "pricing presets",
        MECHANICAL,
        findings,
        f"{len(authored)} priced, written by the screen, key rule and basis agree",
        scanned=len(authored),
    )


def _transport_url_constants(tree: ast.AST) -> Dict[str, str]:
    """Module-level `NAME = "https://..."` assignments. The routes, as the code holds them."""
    out: Dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
            continue
        if not value.value.startswith(("http://", "https://")):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                out[target.id] = value.value
    return out


def _carries_a_url(value: ast.AST, accessors: Dict[str, str]) -> bool:
    """Whether an assignment's right-hand side is a URL being BUILT rather than one being USED.

    THE DISTINCTION IS THE WHOLE ACCURACY OF THE ROW, and getting it wrong was measured on the
    first run: `following = _check_status(status, headers, url)` MENTIONS the download's URL,
    so a reader that propagated through any expression containing it decided the redirect hop
    was a fourth route — `GET /admin/pricing/downloadexportcsv`, a request this file cannot
    make. A promise checked against a route that does not exist fails a commit for nothing,
    which is how a row gets switched off.

    So a string expression carries the URL forward — a name, an f-string, a concatenation, a
    literal, a call to one of the endpoint accessors — and a call to anything else does not.
    An accessor is a function that returns one of the constants; nothing here reads a name.
    """
    if isinstance(value, ast.Call):
        return isinstance(value.func, ast.Name) and value.func.id in accessors
    return isinstance(value, (ast.Name, ast.JoinedStr, ast.BinOp, ast.Constant))


def _transport_requests(tree: ast.AST, urls: Dict[str, str]) -> Set[Tuple[str, str]]:
    """(constant name, METHOD) for every request the module can issue against its own routes.

    THE METHOD IS THE KEYWORD, WHICH IS WHY THIS IS A FACT AND NOT A READING. `_open` builds
    `method="POST" if data else "GET"` and there is no other opener in the file, so a call site
    that passes `data=` is a POST and one that does not is a GET. Nothing is inferred from a
    function's name.

    ATTRIBUTION IS BY THE URL A CALL WAS HANDED, walked back through the accessors — `endpoint`,
    `live_endpoint`, `_filters_endpoint` are just functions that return one of the constants, so
    a local assigned from one of them carries that constant, and so does a local assigned from
    such a local (`url = f"{url}?..."` keeps what `url` already meant).

    A REDIRECT HOP IS DELIBERATELY NOT A ROUTE. The second `_open` in each fetch is handed
    `following`, a Location the portal chose, and this module never names it — one hop is
    followed and the cookie does not cross a host change, which is the bullet's own sentence.
    Counting it would make the promise answer for somebody else's server.
    """
    accessors: Dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.Return)
                and isinstance(sub.value, ast.Name)
                and sub.value.id in urls
            ):
                accessors[node.name] = sub.value.id

    pairs: Set[Tuple[str, str]] = set()
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        carries: Dict[str, str] = {}
        for sub in ast.walk(node):
            if isinstance(sub, ast.Assign) and _carries_a_url(sub.value, accessors):
                reached = set()
                for inner in ast.walk(sub.value):
                    if isinstance(inner, ast.Name):
                        if inner.id in urls:
                            reached.add(inner.id)
                        elif inner.id in carries:
                            reached.add(carries[inner.id])
                    elif (
                        isinstance(inner, ast.Call)
                        and isinstance(inner.func, ast.Name)
                        and inner.func.id in accessors
                    ):
                        reached.add(accessors[inner.func.id])
                if len(reached) == 1:
                    for target in sub.targets:
                        if isinstance(target, ast.Name):
                            carries[target.id] = next(iter(reached))
            if not (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Name)
                and sub.func.id == TRANSPORT_OPENER
            ):
                continue
            first = sub.args[0] if sub.args else None
            named = None
            if isinstance(first, ast.Name):
                named = carries.get(first.id) or (first.id if first.id in urls else None)
            elif isinstance(first, ast.Call) and isinstance(first.func, ast.Name):
                named = accessors.get(first.func.id)
            if named is None:
                continue
            body = next((kw for kw in sub.keywords if kw.arg == "data"), None)
            empty = body is not None and isinstance(body.value, ast.Constant) and body.value.value is None
            pairs.add((named, "GET" if body is None or empty else "POST"))
    return pairs


def _refusals_reachable(tree: ast.AST, root: str) -> Optional[Set[str]]:
    """Every `FetchRefusal` code raisable from `root`, following calls within the module.

    A CLOSURE OVER THE CALL GRAPH, not a grep of the file and not a read of one function.
    `filters` raises two of the nine itself; the other seven come out of `_cookie`, `_open`,
    `_check_status` and the endpoint accessors. A reader that stopped at the function the route
    names would have reported two — which is exactly the number the screen already labeled,
    so it would have blessed the defect it was written to find. Measured by removing the
    recursion: seven codes flip to unreachable.

    Returns None when `root` is not defined, which is a finding rather than an empty answer: an
    empty set reads as "nothing can go wrong", and the difference between that and "this reader
    has lost its subject" is the whole value of the row.
    """
    bodies = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    if root not in bodies:
        return None
    seen: Set[str] = set()
    codes: Set[str] = set()
    pending = [root]
    while pending:
        name = pending.pop()
        if name in seen or name not in bodies:
            continue
        seen.add(name)
        for node in ast.walk(bodies[name]):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id == "FetchRefusal":
                first = node.args[0] if node.args else None
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    codes.add(first.value)
            elif node.func.id in bodies:
                pending.append(node.func.id)
    return codes


def check_hint_reasons(report: Report) -> None:
    """The capture screen's refusal labels, against the refusals its route can send.

    **THE ONE PLACE A TRANSPORT REFUSAL BECOMES A SENTENCE ON A SCREEN.** Three of the four
    call sites into `server/tcg_export.py` answer 502 carrying the module's own remedial
    sentence. The fourth — `GET /pipeline/games/<game>/sets` — answers 200 and hands the CODE
    to `CaptureScreen.tsx` to re-word, because the operator is mid-capture and a failed
    autocomplete is not a failed capture. That is argued and it is right. What it means is that
    `hintReason` is the copy for nine refusals, and nothing read it.

    **IT NAMED TWO OF THE NINE.** Measured 2026-09-06. The other seven fell to the map's
    unknown-code tail and printed as `Set list unavailable (tcg_blocked)`. The tail is argued
    and correct — `docs/DESIGN.md` shows reason codes beside names, so what the operator saw
    stays greppable — and a session widening the map wrote over that argument before putting
    it back. THE DEFECT IS THE SEVEN, NOT THE TAIL: a floor is not where nine tenths of a map
    should land. Nothing could say so — the route was green, the screen typechecked, and the
    only way to see it was to make TCGplayer refuse a real client.

    **MECHANICAL, and the reachability is the part that makes it so.** The codes are string
    literals in `FetchRefusal(...)` calls and the map is a run of `code === '...'` comparisons;
    both are read with a parser, and the reachable set is closed over the module's own call
    graph rather than taken from the one function the route names — see `_refusals_reachable`
    for what that difference measured.

    **BOTH DIRECTIONS.** A reachable code the map does not name is an operator reading a
    fallback. A code the map names that nothing can raise is a dead branch, and dead branches
    are how a map stops being readable as the answer to "what can happen here"; those are
    permitted only through `HINT_REASON_NON_TRANSPORT`, which carries the reason for each.

    **THE ROUTE CARRIES `message` NOW, AND THIS ROW IS WHY THAT IS NOT THE FIX.** A fallback
    that is routinely what the operator reads is a fallback nobody ever widens the map for —
    which is how two-of-nine survived. The transport's sentence sits between the map and the
    bare code, and it names `.env`, which this screen deliberately does not; the map is what
    the screen owes.
    """
    findings: List[Finding] = []
    module = rel(TRANSPORT_PROMISE_MODULE)
    screen = rel(HINT_REASON_SCREEN)

    for path in (TRANSPORT_PROMISE_MODULE, HINT_REASON_SCREEN):
        if not exists(path):
            report.add("hint reasons", MECHANICAL, [Finding(rel(path), "does not exist")])
            return

    try:
        tree = ast.parse(read(TRANSPORT_PROMISE_MODULE))
    except SyntaxError as exc:
        report.add("hint reasons", MECHANICAL, [Finding(module, f"cannot be parsed.\n{exc}")])
        return

    reachable = _refusals_reachable(tree, HINT_REASON_ROOT)
    if reachable is None:
        report.add("hint reasons", MECHANICAL, [Finding(module, (
            f"defines no `{HINT_REASON_ROOT}`, which is the call the set-list route makes and "
            f"the root this row walks from.\n  Re-point `HINT_REASON_ROOT`, or drop the row — "
            f"a reader with no subject reports nothing and\n  blesses whatever the screen "
            f"happens to say."
        ))], "")
        return

    block = _HINT_REASON_FN_RE.search(read(HINT_REASON_SCREEN))
    if block is None:
        report.add("hint reasons", MECHANICAL, [Finding(screen, (
            "defines no `hintReason` this row can read. It is the copy for every refusal the "
            "set-list route can send;\n  either it was renamed, or it was restructured past "
            "the pattern watching it. A check that quietly\n  stops covering a screen's copy "
            "is worse than no check."
        ))], "")
        return

    named = set(_HINT_REASON_CODE_RE.findall(block.group(1)))

    for code in sorted(reachable - named):
        findings.append(Finding(screen, (
            f"does not name `{code}`, which `{module}:{HINT_REASON_ROOT}` can raise and the "
            f"set-list route sends\n  straight to this screen. Unnamed, the operator reads the "
            f"transport's own sentence — written for the\n  pipeline's reader, not for "
            f"somebody holding a card over a stand. Give it a clause in the rig's register."
        )))

    for code in sorted(named - reachable - set(HINT_REASON_NON_TRANSPORT)):
        findings.append(Finding(screen, (
            f"names `{code}` and nothing reachable from `{module}:{HINT_REASON_ROOT}` raises "
            f"it, so that branch is dead.\n  Strike it, or record it in "
            f"`HINT_REASON_NON_TRANSPORT` with where it does come from — a map that may name\n"
            f"  anything cannot be read as the answer to what can happen here."
        )))

    for code, why in sorted(HINT_REASON_NON_TRANSPORT.items()):
        if code not in named:
            findings.append(Finding(screen, (
                f"no longer names `{code}`, which is declared as a code this map covers: {why}\n"
                f"  Either the screen stopped labelling it — and it now falls through — or the "
                f"declaration is stale."
            )))

    report.add(
        "hint reasons",
        MECHANICAL,
        findings,
        f"{len(reachable)} refusals reachable from {HINT_REASON_ROOT}(), "
        f"{len(named)} labeled by the screen",
        scanned=len(reachable),
    )


def check_transport_promise(report: Report) -> None:
    """`server/tcg_export.py`'s first bullet, against the constants and calls beneath it.

    **THE FILE THIS ROW WATCHES IS THE ONE THAT READS THE BEARER CREDENTIAL**, and its opening
    four bullets are not description — the module says so itself. `server/capture_server.py`
    promised for months that this process "holds no API key and makes no outbound call"; this
    file broke the second half literally, and rather than narrow the promise to a technicality
    it deleted it and wrote four replacement bullets. A replacement nobody maintains is the
    narrowing arriving late, which is D16's whole subject.

    **AND THE FIRST BULLET HAD ALREADY DONE IT.** `One host, one method, one route` was written
    on 2026-08-30 over a single GET and was true that morning. D65 landed the same day: the
    download became a POST against `/admin/pricing/downloadexportcsv`, and the filter list went
    from a line in the auth measurement table to a call the module makes. D104 added the live
    download on 2026-09-06. Three routes, two methods, and the sentence above them never moved
    — nor did `server/pipeline_routes.py`'s copy of it, which is the shape a claim takes once
    it has a second home and no reader.

    **MECHANICAL, because none of it is a judgement.** The host of a `https://` constant, the
    path of one, and whether an `_open` call carries a body are three facts in one file, and
    `_open` builds `method="POST" if data else "GET"` so the keyword is the method. A finding is
    a (method, route) pair the code can issue and the bullet does not tabulate, or one the
    bullet tabulates and the code cannot issue. Both directions: an unlisted route is the drift
    that happened, and a listed-but-unreachable one is the promise describing a file that has
    moved on.

    **IT REFUSES TO GO QUIET**, which `check census` paid for and this row inherits. A headline
    reworded past the pattern, a table that yields no routes, or a module with no attributable
    request is REPORTED rather than passed — a promise this row stops reading is a promise back
    in exactly the state it spent a week in, and green.

    **WHAT IT DOES NOT CHECK.** The other three bullets. "It cannot cause a charge", "the secret
    never leaves this module" and "every anticipated failure has its own code" are arguments
    about what the code does NOT do, and a check that claimed to settle those would be asserting
    the absence of something rather than the presence of it — the vacuous green docs/DEBTS.md
    opens by warning about. They are verified by reading, and the reading is recorded in the
    bullets themselves.
    """
    findings: List[Finding] = []
    where = rel(TRANSPORT_PROMISE_MODULE)
    if not exists(TRANSPORT_PROMISE_MODULE):
        report.add("transport promise", MECHANICAL, [Finding(where, "does not exist")])
        return

    try:
        tree = ast.parse(read(TRANSPORT_PROMISE_MODULE))
    except SyntaxError as exc:
        report.add(
            "transport promise",
            MECHANICAL,
            [Finding(where, f"cannot be parsed, so neither its promise nor its calls can be "
                            f"read.\n{exc}")],
        )
        return

    promise = ast.get_docstring(tree) or ""
    headline = _TRANSPORT_HEADLINE_RE.search(promise)
    if headline is None:
        report.add(
            "transport promise",
            MECHANICAL,
            [Finding(where, (
                "its module docstring no longer opens with a `**N hosts, N methods, N routes**"
                "` headline, so the promise over the credential this file reads is watched by\n"
                "  nothing. Either the bullet was deleted, or it was reworded past the pattern.\n"
                "  Re-point `_TRANSPORT_HEADLINE_RE`, or take the row out deliberately — a check\n"
                "  whose subject has left is worse than no check."
            ))],
            "",
        )
        return

    tail = promise[headline.end():]
    cut = tail.find("\n  - **")
    bullet = tail if cut < 0 else tail[:cut]

    urls = _transport_url_constants(tree)
    issued = _transport_requests(tree, urls)
    reachable = {(method, urlparse(urls[name]).path) for name, method in issued}
    hosts = {urlparse(value).netloc for value in urls.values()}
    tabulated = {(method.upper(), route) for method, route in _TRANSPORT_ROUTE_RE.findall(bullet)}

    if not urls:
        findings.append(Finding(where, (
            "declares no module-level `https://` URL constant. The bullet promises the routes "
            "are constants rather than\n  anything a request can name; there is nothing here "
            "for that to be true of."
        )))
    if not issued:
        findings.append(Finding(where, (
            f"no `{TRANSPORT_OPENER}` call could be attributed to one of its URL constants, so "
            f"this row cannot say what the\n  module reaches. Either every request moved out of "
            f"`{TRANSPORT_OPENER}`, or the accessors stopped returning\n  the constants — and "
            f"either way the promise above them is unread."
        )))
    if not tabulated:
        findings.append(Finding(where, (
            "its first bullet tabulates no `METHOD /path` lines. The headline counts routes and "
            "nothing names them,\n  which is the state that let `one method, one route` stand "
            "over three of each for a week."
        )))

    for method, route in sorted(reachable - tabulated):
        findings.append(Finding(where, (
            f"reaches `{method} {route}` and the promise does not name it. This is the module "
            f"that carries the operator's\n  session cookie; a route it can open and its own "
            f"header does not list is the narrowing D16 exists to catch."
        )))
    for method, route in sorted(tabulated - reachable):
        findings.append(Finding(where, (
            f"promises `{method} {route}` and no call in this file can issue it. A promise that "
            f"describes a file which has\n  moved on is read as current by the next session; "
            f"strike it, or restore the call."
        )))

    if len(hosts) > 1:
        findings.append(Finding(where, (
            "names more than one host — " + ", ".join(sorted("`%s`" % h for h in hosts)) + ". "
            "The bullet says one, and `server/order_transport.py`\n  exists precisely because "
            "the second host got its own module rather than a second URL in this one."
        )))
    for host in sorted(hosts):
        if host and host not in bullet:
            findings.append(Finding(where, (
                f"opens sockets to `{host}` and its first bullet does not say so. The host is "
                f"the one thing a reader\n  checks before trusting where the cookie goes."
            )))

    claimed = [_TRANSPORT_NUMBERS.get(word.lower()) for word in headline.groups()]
    actual = [len(hosts), len({method for method, _ in reachable}), len(reachable)]
    for word, count, real, noun in zip(headline.groups(), claimed, actual, ("host", "method", "route")):
        if count is None:
            findings.append(Finding(where, (
                f"counts `{word}` {noun}s in its headline and this row cannot read that as a "
                f"number. Write it as a word\n  up to ten, or widen `_TRANSPORT_NUMBERS` — an "
                f"unreadable count is an unchecked one."
            )))
        elif count != real:
            findings.append(Finding(where, (
                f"says `{word}` {noun}{'' if count == 1 else 's'} and the code reaches {real}. "
                f"Recount from the constants and the\n  `{TRANSPORT_OPENER}` calls; never "
                f"adjust the word to end a build."
            )))

    for name in sorted(urls):
        if name not in bullet:
            findings.append(Finding(where, (
                f"binds `{name}` to a URL and its first bullet does not name the constant. The "
                f"bullet lists them so a\n  fourth cannot arrive as an ordinary assignment."
            )))

    report.add(
        "transport promise",
        MECHANICAL,
        findings,
        f"{len(hosts)} host, {len({m for m, _ in reachable})} methods, {len(reachable)} routes, "
        f"as promised and as called",
        scanned=len(reachable),
    )


def check_export_request(report: Report) -> None:
    """The three fields of the export request that are DECISIONS, pinned to their values.

    **THE OTHER ELEVEN FIELDS ARE TRANSCRIPTION AND THIS ROW IGNORES THEM.**
    `server/tcg_export.py:Scope.model` is a body captured off the portal's own form submit,
    so most of it is a shape somebody copied and nothing here should have an opinion about
    it. Three of the fourteen are the operator's standing instruction, they are hoisted into
    `STANDING_FILTERS` for that reason, and this row is what makes the hoisting mean
    something.

    **WHY A BLOCKING ROW AND NOT A COMMENT, WHICH IS WHAT IT ALREADY HAD.** All three are
    invisible downstream. `ExcludeListos` is the worst of them: D64 measured `Photo URL`
    empty in all eleven exports, filtered AND unfiltered, so the axis leaves no trace in the
    file it narrows. A wrong value produces a clean join, a clean reconcile, a green
    `make check` and a mispriced listing, indefinitely — there is no run, no report and no
    later check that could ever disagree with it.

    **And the failure mode is specific rather than hypothetical.** `ExcludeListos` shipped
    `False` in D65 because the capture took whatever the checkbox happened to be set to that
    day, and the next re-capture of that body would paste over all fourteen fields the same
    way. This row is what turns that paste into a stopped commit.

    The finding names the INSTRUCTION rather than the literal, because somebody who has just
    changed the value already knows what the literal is.
    """
    findings: List[Finding] = []
    where = rel(EXPORT_MODULE)
    if not exists(EXPORT_MODULE):
        report.add("export request", MECHANICAL, [Finding(where, "does not exist")])
        return

    held = literals_from_module(EXPORT_MODULE).get("STANDING_FILTERS")
    if not isinstance(held, dict):
        findings.append(
            Finding(
                where,
                "no `STANDING_FILTERS` literal could be read. It is hoisted out of "
                "`Scope.model` precisely so this row can read it with `ast`; folding it back "
                "into the method body puts three standing instructions somewhere nothing "
                "checks.",
            )
        )
    else:
        for field, expected, why in EXPORT_STANDING:
            actual = held.get(field)
            if field not in held:
                findings.append(
                    Finding(where, f"`STANDING_FILTERS` no longer names {field}. {why}")
                )
            elif actual != expected:
                findings.append(
                    Finding(
                        where,
                        f"{field} is {actual!r} and must be {expected!r}. {why}",
                    )
                )

    live = literals_from_module(EXPORT_MODULE).get("LIVE_QUERY")
    if not isinstance(live, dict):
        findings.append(
            Finding(
                where,
                "no `LIVE_QUERY` literal could be read. The live-inventory download's two query "
                "parameters are hoisted for this row's sake (D104), exactly as the catalogue "
                "request's three fields are.",
            )
        )
    else:
        for field, expected, why in LIVE_QUERY_EXPECTED:
            if field not in live:
                findings.append(
                    Finding(where, f"`LIVE_QUERY` no longer names {field}. {why}")
                )
            elif live.get(field) != expected:
                findings.append(
                    Finding(
                        where,
                        f"`LIVE_QUERY`'s {field} is {live.get(field)!r} and must be "
                        f"{expected!r}. {why}",
                    )
                )

    # THE TWO REQUESTS MUST STAY TWO REQUESTS. They are different endpoints, different methods
    # and different documents — a POST of a filtered model against `downloadexportcsv`, and a
    # GET of everything against `DownloadMyExportCSV`. The likeliest future edit is somebody
    # noticing they both "fetch an export" and routing one through the other, which would make
    # the live path scoped again and silently empty (D104's measurement).
    source = read(EXPORT_MODULE)
    if "def fetch_live()" not in source:
        findings.append(
            Finding(
                where,
                "`fetch_live` no longer takes no arguments. It has no scope BECAUSE the live "
                "download has none — a parameter here is a scope creeping back onto a request "
                "the portal answers emptily when it is scoped wrong.",
            )
        )
    if "tcg_export_empty" not in source:
        findings.append(
            Finding(
                where,
                "`fetch_live` no longer refuses an empty export. That refusal is the only thing "
                "between a wrong request and a store-wide `live: 0`: this endpoint answers a "
                "request it cannot satisfy with a valid header and zero rows, measured.",
            )
        )

    report.add(
        "export request",
        MECHANICAL,
        findings,
        f"{len(EXPORT_STANDING)} catalogue filters and {len(LIVE_QUERY_EXPECTED)} live query "
        f"parameters, each at its measured value",
        scanned=len(EXPORT_STANDING) + len(LIVE_QUERY_EXPECTED),
    )


def _reason_labels() -> Optional[Set[str]]:
    """The screen's `REASON_LABELS` keys, or None if the block cannot be read."""
    if not exists(REVIEW_QUEUE_TSX):
        return None
    block = _REASON_LABELS_RE.search(read(REVIEW_QUEUE_TSX))
    if block is None:
        return None
    return set(re.findall(r"^\s*([a-z_][a-z0-9_]*)\s*:", block.group(1), re.M))


def _constant_for(module: str, value: str) -> Optional[str]:
    """The constant NAME a module binds to this reason string."""
    path = ROOT / module
    if not exists(path):
        return None
    try:
        tree = ast.parse(read(path))
    except SyntaxError:
        return None
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (isinstance(target, ast.Name)
                and isinstance(node.value, ast.Constant)
                and node.value.value == value):
            return target.id
    return None


def _emitted_names() -> Set[str]:
    """Every identifier LOADED anywhere in the production tree.

    A load and not a definition: `NO_POSITION = "no_position"` binds the name, and what says
    a reason can reach a card is somebody reading it back out. Attribute access counts, since
    the usual site is `routing.SET_AMBIGUOUS` from another module.

    **THE ROSTER TUPLES THEMSELVES ARE EXCLUDED, and leaving them in made this row vacuous.**
    `ROUTING_REASONS = (LOW_CONFIDENCE, ..., CARD_NOT_DETECTED, ...)` loads every reason name
    by construction, so the declaration alone satisfied the emission test for all thirteen —
    the row went green the moment the rosters landed, including for the one reason measured to
    have no producer at all. A check that is satisfied by the act of declaring the thing it
    checks is the vacuous green this file opens by warning about, and it was reachable here in
    the same commit that added the rosters.
    """
    declarations = {name for _, name in REASON_ROSTERS}
    names: Set[str] = set()
    for root in EMISSION_ROOTS:
        base = ROOT / root
        if not exists(base):
            continue
        for path in _walk(base, (".py",)):
            try:
                tree = ast.parse(read(path))
            except SyntaxError:
                continue
            skip: Set[int] = set()
            for node in tree.body:
                if (isinstance(node, ast.Assign) and len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Name)
                        and node.targets[0].id in declarations):
                    for element in ast.walk(node.value):
                        if isinstance(element, ast.Name):
                            skip.add(id(element))
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    if id(node) not in skip:
                        names.add(node.id)
                elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                    names.add(node.attr)
    return names


# The two tuples that publish the review vocabulary, and where each is declared.
REASON_ROSTERS = (
    ("pipeline/variant.py", "LADDER_REASONS"),
    ("pipeline/routing.py", "ROUTING_REASONS"),
)

# Where a reason may be handed to a card. The harness is excluded deliberately: a test that
# constructs a reason proves the string exists, never that the pipeline can produce it, and
# counting those would make every reason permanently "emitted".
EMISSION_ROOTS = ("pipeline", "server", "cli", "identify", "store", "codes")

# Reasons that are declared and deliberately have no producer: name -> the argument.
#
# THE SAME SHAPE AS `UNDISPATCHED` ABOVE, AND FOR THE SAME REASON. Without it the only ways
# to quiet this row are to delete a reason or to emit one artificially, and both land in a
# diff looking like tidying. An entry here is an argument a reviewer can disagree with.
#
# Self-cleaning: an entry naming a reason that IS emitted is stale and reported, and one
# naming nothing in the rosters is dangling and reported. A list that only grows stops
# being read.
UNEMITTED_REASONS: Dict[str, str] = {
    "card_not_detected": (
        "reachable in principle and has no producer in the repo today — recorded in "
        "docs/specs/capture-app.md, which argues it is not a defect in the screen and costs "
        "no more than a line in a lookup table. The screen must still label it, because a "
        "reason with no label draws the bare machine string on the day something first "
        "emits one."
    ),
}


def _roster(module: str, name: str) -> Optional[List[str]]:
    """One published reason tuple, resolved through the constants beside it.

    `literals_from_module` cannot read these: the tuple's members are NAMES, not string
    literals, which is the whole point of declaring it next to the constants rather than
    repeating their values. So the module's own `NAME = "value"` assignments are collected
    first and the tuple is resolved against them.
    """
    path = ROOT / module
    if not exists(path):
        return None
    try:
        tree = ast.parse(read(path))
    except SyntaxError:
        return None
    constants: Dict[str, str] = {}
    roster: Optional[List[str]] = None
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            constants[target.id] = node.value.value
        elif target.id == name and isinstance(node.value, ast.Tuple):
            roster = [
                constants[element.id]
                for element in node.value.elts
                if isinstance(element, ast.Name) and element.id in constants
            ]
    return roster


def check_reason_emissions(report: Report) -> None:
    """Every published reason is in a roster, and every roster reason has a producer.

    `check_reason_codes` reconciles this vocabulary across the screen, docs/DESIGN.md and the
    constants — but only ever in one direction. It starts from a reason somebody published and
    asks whether the code defines it. Its own docstring records what that cannot see: a reason
    constant no doc and no screen mentions, invisible because the modules never said which of
    their constants are reasons.

    **The fix was in the code, not in a cleverer checker.** `pipeline/variant.py` declares
    fourteen module-level constants and six are reasons; the rest are finishes and ladder
    stages, spelled identically. Any rule for telling them apart is a guess, and the cheapest
    one is wrong about eight of fourteen in that file alone. So the modules publish
    `LADDER_REASONS` and `ROUTING_REASONS`, and this row is a set comparison rather than a
    heuristic — which is the bar this repo now holds a new row to (D16, amended 2026-09-05).

    Two things it asks that nothing asked before:

      the rosters ARE the vocabulary   a reason the screen labels and no roster names, or a
                                       roster entry no screen labels. Either way the code and
                                       the product disagree about what can happen to a card.
      a reason has a producer          a constant nothing assigns is dead vocabulary: it
                                       occupies a label, a doc line and a reader's attention,
                                       and no card can ever carry it.

    The harness is not a producer. A test constructing a reason proves the string exists, not
    that the pipeline can reach it, and counting tests would make every reason permanently
    emitted — the vacuous green this file exists to refuse.
    """
    findings: List[Finding] = []
    published: Set[str] = set()
    missing_roster = False
    for module, name in REASON_ROSTERS:
        roster = _roster(module, name)
        if roster is None:
            missing_roster = True
            findings.append(
                Finding(
                    module,
                    f"declares no `{name}` tuple this row can read. It is what lets the "
                    f"vocabulary be checked from the code outwards; without it only the "
                    f"doc-to-code direction is provable.",
                )
            )
            continue
        published.update(roster)

    labeled = _reason_labels()
    if labeled is None:
        findings.append(
            Finding(rel(REVIEW_QUEUE_TSX), "no `REASON_LABELS` block to read.")
        )
    elif not missing_roster:
        for reason in sorted(labeled - published):
            findings.append(
                Finding(
                    rel(REVIEW_QUEUE_TSX),
                    f"`{reason}` is labeled on the screen and named by no roster.\n"
                    f"  Add it to `LADDER_REASONS` or `ROUTING_REASONS` — whichever module "
                    f"produces it — so the code publishes the vocabulary it can emit.",
                )
            )
        for reason in sorted(published - labeled):
            findings.append(
                Finding(
                    rel(REVIEW_QUEUE_TSX),
                    f"`{reason}` is in a roster and the screen has no label for it.\n"
                    f"  The queue would draw the bare machine string the day something emits "
                    f"one, which is the outcome the label table exists to prevent.",
                )
            )

    emitted = _emitted_names()
    for module, name in REASON_ROSTERS:
        roster = _roster(module, name) or []
        for reason in roster:
            constant = _constant_for(module, reason)
            if constant is None or constant in emitted:
                if reason in UNEMITTED_REASONS and constant in emitted:
                    findings.append(
                        Finding(
                            "scripts/docs-audit.py",
                            f"`UNEMITTED_REASONS` still excuses `{reason}`, which now has a "
                            f"producer. Delete the entry — the argument it carries is spent.",
                        )
                    )
                continue
            if reason in UNEMITTED_REASONS:
                continue
            findings.append(
                Finding(
                    module,
                    f"`{reason}` is declared, labeled and documented, and nothing in "
                    f"{', '.join(EMISSION_ROOTS)} ever assigns it.\n"
                    f"  No card can carry it, so its label and its doc line describe a state "
                    f"the product cannot reach. Emit it, retire it, or argue it into "
                    f"`UNEMITTED_REASONS` with the reason.",
                )
            )
    for reason in sorted(UNEMITTED_REASONS):
        if reason not in published and not missing_roster:
            findings.append(
                Finding(
                    "scripts/docs-audit.py",
                    f"`UNEMITTED_REASONS` names `{reason}`, which is in no roster. A dangling "
                    f"exemption is one nobody can evaluate.",
                )
            )

    report.add(
        "reason emissions",
        MECHANICAL,
        findings,
        f"{len(published)} published reasons, {len(published) - len(UNEMITTED_REASONS)} with "
        f"a producer and {len(UNEMITTED_REASONS)} argued",
        scanned=len(published),
    )


def check_reason_codes(report: Report) -> None:
    """The twelve review reasons, reconciled across the three places they are published.

    They are written down in three independent places and nothing compared them: the
    constants in `pipeline/variant.py` and `pipeline/routing.py`, the keys of
    `REASON_LABELS` in `app/src/ReviewQueue.tsx`, and the enumerated list in
    `docs/DESIGN.md`. That file names the failure itself — showing only a friendly label
    "creates a second vocabulary that nothing audits" — and until this row existed, the
    audit it was appealing to did not check the vocabulary either.

    Four reconciliations, each provable:

      a label with no constant   the screen renders a friendly label for a string the
                                 pipeline cannot emit. Dead code that reads as coverage.
      a documented reason with   the queue would draw the bare machine string the day
      no label                   routing first emits it, which is the outcome the two-size
                                 label rule exists to prevent.
      a label the doc omits      a vocabulary the screen has and the spec does not, which
                                 is the drift in the direction nobody notices.
      a wrong attribution        docs/DESIGN.md credits each reason to the ladder or to
                                 routing; a reason that moved between them without the doc
                                 following is a doc that is confidently wrong.

    **What this could not see, `reason emissions` below now does (2026-09-05).** The gap was a
    reason constant that no doc and no screen mentions: `self_named_strings` answers "is this
    string defined here" and not "which strings here are reasons", and every rule for telling
    them apart was a guess — `pipeline/variant.py` spells finishes, ladder stages and reasons
    identically, and eight of its fourteen constants are not reasons.

    **The fix was in the pipeline, not in a cleverer reader here.** `LADDER_REASONS` and
    `ROUTING_REASONS` publish the set, so the missing direction is a set comparison. This row
    is unchanged and still runs from the published vocabulary inwards; the two are
    complementary, and neither subsumes the other.
    """
    findings: List[Finding] = []
    documented, problem = design_reason_lists()
    if problem:
        findings.append(Finding("docs/DESIGN.md", problem))

    labels: Set[str] = set()
    if not exists(REVIEW_QUEUE_TSX):
        findings.append(Finding(rel(REVIEW_QUEUE_TSX), "does not exist"))
    else:
        block = _REASON_LABELS_RE.search(read(REVIEW_QUEUE_TSX))
        if block is None:
            findings.append(
                Finding(
                    rel(REVIEW_QUEUE_TSX),
                    "no `const REASON_LABELS = { ... }` block could be read. The screen's "
                    "half of this reconciliation is that map; if it was restructured, this "
                    "row has to learn the new shape.",
                )
            )
        else:
            labels = set(_LABEL_KEY_RE.findall(block.group(1)))

    defined = {module: self_named_strings(ROOT / module) for module in REASON_MODULES}
    everywhere = set().union(*defined.values()) if defined else set()

    for reason in sorted(labels):
        if reason not in everywhere:
            findings.append(
                Finding(
                    rel(REVIEW_QUEUE_TSX),
                    f"REASON_LABELS carries {reason!r}, which is not defined as a constant "
                    f"in {' or '.join(REASON_MODULES)}. Nothing can put it on screen.",
                )
            )
        if documented and reason not in documented:
            findings.append(
                Finding(
                    rel(REVIEW_QUEUE_TSX),
                    f"REASON_LABELS carries {reason!r}, which docs/DESIGN.md's enumerated "
                    f"list does not name.",
                )
            )

    for reason, module in sorted(documented.items()):
        if labels and reason not in labels:
            findings.append(
                Finding(
                    "docs/DESIGN.md",
                    f"{reason!r} is enumerated but has no entry in REASON_LABELS, so the "
                    f"review queue would render the raw string.",
                )
            )
        if reason not in everywhere:
            findings.append(
                Finding(
                    "docs/DESIGN.md",
                    f"{reason!r} is enumerated but is defined as a constant in neither "
                    f"{' nor '.join(REASON_MODULES)}.",
                )
            )
        elif reason not in defined.get(module, set()):
            actual = sorted(name for name, strings in defined.items() if reason in strings)
            findings.append(
                Finding(
                    "docs/DESIGN.md",
                    f"{reason!r} is attributed to {module} and is actually defined in "
                    f"{', '.join(actual)}.",
                )
            )

    report.add(
        "reason codes",
        MECHANICAL,
        findings,
        f"{len(documented)} enumerated, {len(labels)} labeled, all defined",
        scanned=len(documented),
    )


# ------------------------------------------------ whether a cited test reaches what it claims

# Where the one-level follow stops, and the reason this row says anything at all.
#
# A test's own scaffolding is part of the test: harness/eval/ holds the fixture loader and
# the run cache, and a test that kept its imports there would otherwise be reported as
# reaching nothing — a false positive, on a blocking row, over a correct claim. So the
# follow reaches modules under here and no further.
#
# PRODUCT PACKAGES ARE DELIBERATELY NOT FOLLOWED, and that is the whole design. Measured on
# this tree: `cli/cmd_identify.py` imports `geometry`, `cli/resolve.py` imports `store`, and
# `harness/tests/t7_store_and_seams.py` imports `cli`. One transitive hop would therefore
# prove "T7 reaches geometry" — a package T7 does not touch and whose two modules correctly
# cite T6. Transitive reachability through the product's own graph makes almost every claim
# true and asserts nothing, which is to say it recreates the unenforced field this row
# exists to enforce, using the machinery meant to enforce it.
FOLLOW_ROOT = "harness/"


def imported_names(source: str) -> Set[str]:
    """Every absolute dotted module name a source imports. The whole tree, not just its body.

    `ast.walk` rather than `tree.body`, because two of the seven tests import the thing they
    are named for from inside a function: `harness/tests/t6_geometry.py` imports `geometry`
    after its Pillow/numpy availability check, and `harness/tests/t7_store_and_seams.py`
    imports `cli.__main__` inside the case that drives it. A module-level read would call
    both of those claims false and block a commit over them.

    `from . import x` is dropped rather than resolved: a relative import names no package
    this check can compare against a map entry, and no test in this repo writes one.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module)
            # `from harness.eval import fixtures, runcache` — each name is a submodule or an
            # attribute, and only the filesystem knows which. Both forms are recorded; the
            # resolver below finds no file for an attribute and moves on.
            for alias in node.names:
                names.add(node.module + "." + alias.name)
    return names


def string_literals(source: str) -> Set[str]:
    """Every string constant in a source that is not a docstring.

    Docstrings are excluded because they are prose, and prose is what this whole script
    treats as unverified. `harness/tests/t2_round_trip.py` opens with "Load
    fixtures/sv09_export_untouched.csv" in its module docstring and then assigns the same
    path to `SOURCE_FIXTURE` two dozen lines down. Only the second is the test reading the
    file; counting the first would let a sentence satisfy the claim.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    docstrings: Set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            docstrings.add(id(body[0].value))
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    }


def follow_target(dotted: str) -> Optional[Path]:
    """A dotted module name as a file under FOLLOW_ROOT, or None for anything else."""
    stem = dotted.replace(".", "/")
    for candidate in (ROOT / (stem + ".py"), ROOT / stem / "__init__.py"):
        if rel(candidate).startswith(FOLLOW_ROOT) and exists(candidate):
            return candidate
    return None


def test_reach(path: Path) -> Tuple[Set[str], Set[str]]:
    """(top-level packages the test imports, path literals it names). One level deep."""
    source = read(path)
    names = imported_names(source)
    literals = string_literals(source)
    # `sorted()` copies, so the sets may grow inside the loop without the new entries being
    # followed in turn. That is not an implementation detail — it IS the one level.
    for dotted in sorted(names):
        helper = follow_target(dotted)
        if helper is None or helper == path:
            continue
        helper_source = read(helper)
        names |= imported_names(helper_source)
        literals |= string_literals(helper_source)
    return {name.split(".", 1)[0] for name in names}, literals


def is_importable(target: Path) -> bool:
    """Does this directory hold Python at all?

    Not `__init__.py`: `server/` and `harness/` have none and are imported anyway, as
    namespace packages. Holding a `.py` child is the property that matters, and it is what
    separates a package from `fixtures/`, which holds CSVs, and `app/`, which holds
    TypeScript. Those two have no import to check, so the claim on them is checked the only
    other way a parse can see — a path literal.
    """
    return any(name.endswith(".py") for name in child_names(target))


def reach_findings(
    components: Sequence[Dict[str, object]], tests: Dict[str, Path]
) -> Tuple[List[Finding], int]:
    """(findings, claims checked). Split out from the check so the self-test can drive it.

    The self-test feeds it the exact false claim docs/DEBTS.md recorded — `store/queues.py`
    citing T3 — against the real harness, rather than a synthetic stand-in for it.
    """
    findings: List[Finding] = []
    claims = 0
    cache: Dict[str, Tuple[Set[str], Set[str]]] = {}

    def reach(name: str) -> Tuple[Set[str], Set[str]]:
        if name not in cache:
            cache[name] = test_reach(tests[name])
        return cache[name]

    for component in components:
        path = str(component.get("path", ""))
        target = ROOT / path
        if not path or not exists(target):
            continue  # the repo map row already reports a component path that is not there
        package = path.strip("/").split("/")[0]
        importable = is_importable(target)

        entries: List[Tuple[str, Sequence[str]]] = [(path, component.get("tested_by") or [])]
        for module_name, entry in (component.get("modules") or {}).items():
            entries.append((path + str(module_name), list(entry.get("tested_by") or [])))

        for where, cited in entries:
            for name in cited:
                # An id that is not a registered test is already a finding on the repo map
                # row, and there is no file here to parse. Reporting it twice under two
                # labels would make one defect read as two.
                if name not in tests or not exists(tests[name]):
                    continue
                claims += 1
                packages, literals = reach(name)

                if importable:
                    if package in packages:
                        continue
                    in_repo = sorted(
                        found
                        for found in packages
                        if exists(ROOT / found) or exists(ROOT / (found + ".py"))
                    )
                    findings.append(
                        Finding(
                            f"docs/map.py -> {where}",
                            f"tested_by claims {name}, and {rel(tests[name])} imports no "
                            f"`{package}`.\n"
                            f"  {name} reaches: {', '.join(in_repo) or '(nothing in this repo)'}\n"
                            f"  Either the claim is false and goes, or the test should import "
                            f"what it is credited with. Do not answer this in prose: the "
                            f"entry's `note` is read by people and this row is not.",
                        )
                    )
                    continue

                if any(literal.startswith(where) for literal in literals):
                    continue
                findings.append(
                    Finding(
                        f"docs/map.py -> {where}",
                        f"tested_by claims {name}, and {rel(tests[name])} names no path "
                        f"under `{where}`.\n"
                        f"  `{path}` holds no Python, so there is no import to check. The "
                        f"only evidence a parse can see is the test naming a path under it "
                        f"in its code — a mention in its docstring is prose and does not "
                        f"count.",
                    )
                )
    return findings, claims


def check_tested_by_reach(report: Report) -> None:
    """A `tested_by` claim in docs/map.py, against what the cited test actually imports.

    The repo-map row proves a cited test id is registered in `harness/run.py:TESTS`. It has
    never proved the test goes anywhere near the module claiming it, and docs/DEBTS.md
    recorded the measurement: of the eleven entries audited by hand on 2026-08-11, ten were
    true and one was false — `store/queues.py` claimed T3 and T4 while nothing under
    `harness/` imported `store` at all. D17 says the map is audited exactly as hard as it is
    trusted, and this was the field where it was trusted and not audited.

    **WHAT A PASSING CLAIM PROVES, EXACTLY**: the cited test's import graph — the test module
    plus one level into its own `harness/` helpers — contains the top-level package the
    entry lives in. For a directory holding no Python, that the test names a path under it in
    a string literal outside its docstrings.

    **WHAT IT DOES NOT PROVE, AND THE DISTANCE IS LARGE**: not that the test imports the
    *module*, not that it calls anything the module defines, and not that any assertion
    depends on it. `from pipeline import join` satisfies every entry in `pipeline/` at once.
    A test could import a package and exercise none of it and this row would stay green.
    Overclaiming here would be the same defect one level up — an unenforced claim about a
    checker for unenforced claims — so the label is `tested_by reach` and not `tested_by
    coverage`, and the summary says "reaches" rather than "tests".

    **Package granularity, not module granularity, and that was measured too.**
    `harness/tests/t6_geometry.py` imports the bare package (`import geometry`) and then uses
    `geometry.detect` through it, so a module-granular rule would call both correct
    `geometry/` entries false. A false positive that blocks is worse than one that prints
    (D16), and this row blocks — so it asks the question it can answer without judgment.

    **Blocking, because an import either is in the parse or is not.** That is D16's test for
    a mechanical finding. The residual risk is a test that reaches code without importing
    it — through a subprocess or a generated file. No harness test does today (`subprocess`
    appears nowhere under `harness/tests/`), and if one ever does the fix is to drop the
    claim or to make the test import what it is credited with. It is deliberately not
    something a `note` can talk its way out of: that is what "unenforced" meant.
    """
    if not exists(MAP):
        return  # the repo map row above already reports a missing map, loudly
    components = literals_from_module(MAP).get("COMPONENTS") or []
    tests = {name: path for name, path in registered_tests()}
    findings, claims = reach_findings(components, tests)
    report.add(
        "tested_by reach",
        MECHANICAL,
        findings,
        f"{claims} claims, every cited test reaches what it names",
        scanned=claims,
    )


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
                for req in requires:
                    if req not in payload:
                        findings.append(Finding(spot, f"`{name}` has no `{req}` key."))

    report.add("status sources", MECHANICAL, findings, f"{checked} declared, all resolve",
               scanned=checked)


# ------------------------------------------------ the palette the app actually renders from

DESIGN = ROOT / "docs" / "DESIGN.md"
TOKENS_CSS = ROOT / "app" / "src" / "tokens.css"

COLOR = "color"
TYPEFACE = "typeface"
LENGTH = "length"

# The two files name the same token differently in exactly two places, and both differences
# are cosmetic: the type rows are headed by the job a face does (`Utility`) where the
# property is abbreviated (`--util`), and the spacing scale is one row of numbers where the
# properties are `--s1`, `--s2` and so on. Renaming one side to match the other was the
# obvious alternative and is the wrong one — app/src/tokens.css says in its own header that
# its property names match docs/design-refs/locked.html, and the doc's block is laid out to
# be read as a palette by a person. A three-line table is cheaper than either file getting
# worse to spare it.
# THE BLOCK NAMES TOKENS; IT NO LONGER SPELLS A PALETTE IN ROWS. What the old reader parsed —
# `Color #FCFCFD bg`, three typeface rows, one spacing row, one radius row — is a format that
# stopped existing when the `--bn-` system landed, and the reader read zero tokens from the new
# block and said so. These four read what the block actually writes.
_BN_NAME_RE = re.compile(r"--bn-[a-z0-9]+(?:-[a-z0-9]+)*")
# `--bn-fs-2xs … --bn-fs-5xl` and `--bn-1 … --bn-10`, in both the ellipsis and the three-dot
# spelling, because a document written by hand carries both.
_BN_RANGE_RE = re.compile(r"(--bn-[a-z0-9-]+)\s*(?:…|\.\.\.)\s*(--bn-[a-z0-9-]+)")
# A bare suffix continuing the name before it: `--bn-r-xs 4 · -sm 6`. Anchored on the separator
# so a hyphen inside a sentence — "9:16 frame" or "light-on-dark" — is not read as a token.
_BN_SUFFIX_RE = re.compile(r"[·/]\s*-([a-z0-9]+(?:-[a-z0-9]+)*)\b")
# `name #hex` pairs on a `·`-separated line, where the name may be a suffix of the one before.
_BN_PAIR_RE = re.compile(r"(--bn-[a-z0-9-]+|-[a-z0-9-]+)\s+(#[0-9A-Fa-f]{3,6})\b")
_HEX_RE = re.compile(r"#[0-9A-Fa-f]{3,6}\b")

# The one definition, shared with strip_css_comments() in the `raw color` section below.
# It was declared twice, identically, once per section — harmless only for as long as the two
# stayed identical, and the second binding silently won for BOTH call sites, so an edit to
# this one would have been discarded without a diff to show for it. Two checks reading the
# same CSS must not be able to disagree about what a comment is.
_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_CSS_PROPERTY_RE = re.compile(r"--([A-Za-z0-9_-]+)\s*:\s*([^;]+);")
_SHORTHAND_RE = re.compile(r"#[0-9a-f]{3}$")


class Token(NamedTuple):
    kind: str
    text: str  # as its own file writes it, so a finding can quote both spellings
    value: str  # normalised, and the only thing ever compared


def token_value(kind: str, text: str) -> str:
    """One normaliser, run over both sides.

    Deliberately not two. A doc-side and a css-side normaliser are two decisions about what
    counts as the same value, and the failure mode of their disagreeing is a permanent
    finding nobody can fix — or worse, a permanent pass. Every difference this collapses is
    a difference CSS itself does not see:

      color     `#FFF` and `#ffffff` are one color. A check that called them a
                 disagreement would be reporting a spelling, and would be worked around by
                 respelling the doc, which is D16's forbidden direction.
      typeface   the stylesheet names the locked face plus a generic fallback. The interview
                 chose a face; `sans-serif` behind it is a rendering nicety nobody locked.
                 Family names are ASCII case-insensitive to CSS, so case is folded too.
      length     whitespace only. `4px` and `4 px` are not the same value to CSS and are not
                 collapsed here.
    """
    if kind == COLOR:
        text = " ".join(text.split()).lower()
        return "#" + "".join(ch * 2 for ch in text[1:]) if _SHORTHAND_RE.match(text) else text
    if kind == TYPEFACE:
        return " ".join(text.split(",")[0].strip().strip("'\"").split()).lower()
    return " ".join(text.split()).lower()


def fenced_block(text: str, heading: str) -> Optional[str]:
    """The first fenced block under a `## ` HEADING (a regex, anchored after the hashes), or None.

    Split out of `design_token_block` when `breakpoints` needed the same reader for its own
    register. The scoping argument below is that row's and still holds for it; the mechanism is
    general, and a second caller is the reason a heading is a parameter rather than a literal.
    """
    collecting = False
    in_section = False
    block: List[str] = []
    for line in text.splitlines():
        if not collecting and line.startswith("## "):
            in_section = bool(re.match(r"^##\s+" + heading, line))
            continue
        if in_section and line.lstrip().startswith("```"):
            if collecting:
                return "\n".join(block)
            collecting = True
            continue
        if collecting:
            block.append(line)
    return None


def design_token_block(text: str) -> Optional[str]:
    """The fenced block under the `## Tokens` heading, or None.

    Scoped to that one section on purpose. docs/DESIGN.md carries a second fenced block —
    step 6's three button states — which restates some of these hexes; it is a doc arguing
    with itself rather than with the code, a different question with a different answer, and
    folding it in here would put two comparisons behind one row's name.

    An unterminated fence returns None, which the caller reports. Falling through to the
    next fence in the file would compare the button states against the stylesheet and find
    nothing wrong with either.
    """
    return fenced_block(text, r"Tokens\b")


class Claims(NamedTuple):
    """What the block locks, in the three shapes it writes them.

    `names` are stated outright. `alts` are the readings of a shorthand whose base is genuinely
    ambiguous — `-sm` after `--bn-r-xs` is `--bn-r-sm`, while `-lg` after `--bn-r` is
    `--bn-r-lg` — and a group is satisfied when ANY of its readings is declared. `prefixes`
    come from a range like `--bn-fs-2xs … --bn-fs-5xl`, which locks a family rather than a
    list, and covers every declared token beginning with it.
    """

    names: Set[str]
    alts: List[Set[str]]
    prefixes: Set[str]
    hexes: Dict[str, Tuple[Optional[str], Optional[str]]]

    def covers(self, name: str) -> bool:
        """Whether the block names this declared token, by any of the three routes."""
        if name in self.names or any(name in group for group in self.alts):
            return True
        return any(name.startswith(prefix + "-") or name == prefix for prefix in self.prefixes)


def design_token_claims(block: str) -> Claims:
    """What the block LOCKS: every token name it names, and the literal hexes it states.

    THE BLOCK IS PROSE LAID OUT AS A PALETTE, NOT A TABLE, and it is deliberately readable
    rather than parseable — `docs/DESIGN.md` says so where it describes the old reader, and
    respelling the palette to suit a script is D16's forbidden direction. So this reads what
    the block unambiguously states and nothing else:

      NAMES        every `--bn-…` identifier, plus two shorthands the block uses for families:
                   `--bn-r-xs 4 · -sm 6` continues the previous name, and `--bn-fs-2xs … --bn-fs-5xl`
                   names every token sharing that prefix.
      HEX VALUES   only where a name is followed by a hex literal. `ink 8%`, `accent 55%`,
                   `white .72` and `= ink in both themes` are alphas and aliases of another
                   token — the block says as much in the paragraphs under it — and there is no
                   second value to keep in step, so there is nothing here to compare.

    WHAT THAT MEANS THE ROW CAN AND CANNOT CATCH, stated rather than left to be discovered.
    It catches a token declared in the stylesheet that no interview ever chose, a token locked
    in the doc that nothing renders, and a hex that disagrees between the two files. It does
    NOT check a duration, a shadow, an easing curve, an alpha, or the value behind a
    `color-mix()` — those are named and checked for existence, and their values are not locked
    anywhere a script can read. `docs/DEBTS.md` carries that gap.
    """
    names: Set[str] = set()
    alts: List[Set[str]] = []
    prefixes: Set[str] = set()
    hexes: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    last_full: Optional[str] = None

    for line in block.splitlines():
        full = _BN_NAME_RE.findall(line)
        for name in full:
            names.add(name)

        # `--bn-fs-2xs … --bn-fs-5xl` names a family. The prefix is what the two ends share up
        # to the last hyphen, and every token under it is locked by the range.
        span = _BN_RANGE_RE.search(line)
        if span:
            names.update(_range_names(span.group(1), span.group(2)))
            if not _range_names(span.group(1), span.group(2)):
                prefixes.add(_family_prefix(span.group(1), span.group(2)))

        # `--bn-r-xs 4 · -sm 6 · --bn-r 8 · -lg 12` — a bare suffix continues the last full
        # name. WHICH name is genuinely ambiguous (`-sm` after `--bn-r-xs` means `--bn-r-sm`,
        # while `-lg` after `--bn-r` means `--bn-r-lg`), so both readings are recorded and the
        # comparison accepts either. Being generous here is the safe direction: it can only
        # fail to report a typo in the DOC, and never wave through a token in the stylesheet
        # that nobody chose, which is the finding that matters.
        for piece in _BN_SUFFIX_RE.findall(line):
            base = last_full if not full else full[-1]
            if base is None:
                continue
            reading = {base + "-" + piece}
            if "-" in base[len("--bn-"):]:
                reading.add(base.rsplit("-", 1)[0] + "-" + piece)
            alts.append(reading)
        if full:
            last_full = full[-1]

        # A hex claim, in the two shapes the block writes. `·` separates several name/value
        # pairs on one line (the stage palette); without it the leading name owns the row's
        # hexes, and a row naming two tokens with `/` gives them to the first — the second is
        # that color's tint, which the block's own paragraph says is an alpha.
        if "·" in line:
            for name, value in _BN_PAIR_RE.findall(line):
                if name.startswith("--bn-"):
                    hexes[name] = (value, None)
                elif last_full is not None:
                    hexes[last_full.rsplit("-", 1)[0] + name] = (value, None)
            continue
        found = _HEX_RE.findall(line)
        if full and found and line.lstrip().startswith("--bn-"):
            hexes[full[0]] = (found[0], found[1] if len(found) > 1 else None)

    return Claims(names, alts, prefixes, hexes)


def _range_names(low: str, high: str) -> Set[str]:
    """`--bn-1 … --bn-10` enumerated, or an empty set where the ends are not numbered.

    A NUMBERED RANGE IS A LIST AND A NAMED ONE IS A FAMILY, and treating the first as a prefix
    was wrong in the way that matters: the shared prefix of `--bn-1` and `--bn-10` is `--bn-1`,
    which covers `--bn-10` and nothing else, so the spacing scale locked one of its ten steps
    and the check passed on it. `--bn-fs-2xs … --bn-fs-5xl` genuinely is a family — the ends are
    words, the members are not enumerable from them — and stays a prefix.
    """
    ends = [re.match(r"^(--bn-[a-z0-9-]*?)(\d+)$", name) for name in (low, high)]
    if not all(ends) or ends[0].group(1) != ends[1].group(1):
        return set()
    stem = ends[0].group(1)
    first, last = int(ends[0].group(2)), int(ends[1].group(2))
    if last < first:
        return set()
    return {f"{stem}{n}" for n in range(first, last + 1)}


def _family_prefix(low: str, high: str) -> str:
    """The prefix two ends of a range share, as a name every member starts with."""
    shared = ""
    for a, b in zip(low, high):
        if a != b:
            break
        shared += a
    return shared.rstrip("-")


def css_token_scopes(text: str) -> Tuple[Dict[str, str], Dict[str, str], Set[str]]:
    """The light palette, the dark one, and every `--bn-` name declared anywhere.

    THE SCOPES ARE KEPT APART, AND THE OLD READER'S MERGING THEM WAS LOSSY RATHER THAN MERELY
    EMPTY. It folded every `:root` in the file into one dictionary, so `--bn-bg`'s dark value
    silently overwrote its light one and the check compared the doc's light column against a
    dark hex. Under a token system where every color has both, that is a check that cannot be
    right — the shape had to change before the parsing did.

    A `:root` inside an at-rule contributes NAMES ONLY. The phone/coarse-pointer query raises
    three control heights, which are a second value for a condition rather than a second theme;
    comparing them against the doc's light column would report a disagreement that is the
    stylesheet working. Comments are stripped first, for `css_root_tokens`' old reason: a token
    commented out during a refactor still reads as a declaration to a regex, and this check
    would then agree with the doc about a value the browser never paints.
    """
    body = _CSS_COMMENT_RE.sub(" ", text)

    conditional: List[Tuple[int, int]] = []
    for at in re.finditer(r"@[a-z-]+[^{;]*\{", body):
        conditional.append((at.start(), _block_end(body, at.end())))

    # SCOPED TO `--bn-`, AND THE EXCLUSION IS ARGUED IN `token_findings`. The legacy aliases at
    # the foot of the stylesheet are named in the prose under the block as a spent migration
    # seam that is to be deleted; a check that demanded they be locked would be fighting the
    # plan it is auditing.
    light: Dict[str, str] = {}
    dark: Dict[str, str] = {}
    every: Set[str] = set()
    for match in re.finditer(r":root\b[^{]*\{", body):
        end = _block_end(body, match.end())
        declared = [
            (name, value)
            for name, value in _CSS_PROPERTY_RE.findall(body[match.end():end])
            if name.startswith("bn-")
        ]
        for name, _value in declared:
            every.add("--" + name)
        if any(start <= match.start() < stop for start, stop in conditional):
            continue
        selector = body[match.start():match.end()]
        table = dark if "data-theme='dark'" in selector or 'data-theme="dark"' in selector else light
        for name, value in declared:
            table["--" + name] = value.strip()
    return light, dark, every


def _block_end(body: str, opened: int) -> int:
    """The index just past the `}` closing a block whose `{` has already been consumed."""
    depth = 1
    index = opened
    while index < len(body) and depth:
        if body[index] == "{":
            depth += 1
        elif body[index] == "}":
            depth -= 1
        index += 1
    return index


def token_findings(
    claims: Claims,
    light: Dict[str, str],
    dark: Dict[str, str],
    every: Set[str],
) -> List[Finding]:
    """Both directions, and every finding names both files and both values.

    Both directions because either half of a drift is the same defect seen from one side. A
    token in the doc and not the stylesheet is a decision the product never implemented; a
    token in the stylesheet and not the doc is a value the owner never chose, which is the more
    dangerous of the two — it renders perfectly and no interview ever saw it.

    SCOPED TO `--bn-` AND NOT TO EVERY CUSTOM PROPERTY. The legacy aliases at the foot of the
    stylesheet — `--ink`, `--s1`, `--radius` and the rest — are named in the prose under the
    block as a migration seam that is already spent and is to be deleted. Locking a name the
    document argues for deleting would make the check fight the plan it is auditing.
    """
    findings: List[Finding] = []

    for name in sorted(claims.names - every):
        findings.append(
            Finding(
                f"{rel(DESIGN)} + {rel(TOKENS_CSS)}",
                f"{rel(DESIGN)} locks `{name}`, and {rel(TOKENS_CSS)} declares no such "
                f"property.\n"
                f"  Nothing renders it, so the locked value is a decision the product does "
                f"not carry.",
            )
        )

    for group in claims.alts:
        if group & every:
            continue
        findings.append(
            Finding(
                f"{rel(DESIGN)} + {rel(TOKENS_CSS)}",
                f"{rel(DESIGN)} continues a name into {' or '.join(sorted(group))}, and "
                f"{rel(TOKENS_CSS)} declares neither.\n"
                f"  A shorthand that reads onto nothing is a token the block believes it "
                f"locked and does not.",
            )
        )

    for prefix in sorted(claims.prefixes):
        if any(name.startswith(prefix + "-") for name in every):
            continue
        findings.append(
            Finding(
                f"{rel(DESIGN)} + {rel(TOKENS_CSS)}",
                f"{rel(DESIGN)} locks the family `{prefix}-…`, and {rel(TOKENS_CSS)} "
                f"declares nothing under it.\n"
                f"  A range that covers no token locks nothing at all.",
            )
        )

    for name in sorted(name for name in every if not claims.covers(name)):
        findings.append(
            Finding(
                f"{rel(TOKENS_CSS)} + {rel(DESIGN)}",
                f"`{name}: {light.get(name, dark.get(name, ''))}` is declared in "
                f"{rel(TOKENS_CSS)}, and the token block in {rel(DESIGN)} names no "
                f"`{name}`.\n"
                f"  Lock it there, or delete it here. A token the doc never chose is a value "
                f"with no argument behind it.",
            )
        )

    for name in sorted(claims.hexes):
        for rendered, locked, theme in (
            (light.get(name), claims.hexes[name][0], "light"),
            (dark.get(name), claims.hexes[name][1], "dark"),
        ):
            if locked is None or rendered is None or not rendered.startswith("#"):
                # A stylesheet value that is not a literal is an alpha or a mix of another
                # token, which the block states in words rather than as a second hex. There is
                # nothing to compare, and reporting it would be reporting the design.
                continue
            if token_value(COLOR, rendered) != token_value(COLOR, locked):
                findings.append(
                    Finding(
                        f"{rel(DESIGN)} + {rel(TOKENS_CSS)}",
                        f"`{name}` disagrees in the {theme} theme.\n"
                        f"  {rel(DESIGN)}:      {locked}\n"
                        f"  {rel(TOKENS_CSS)}: {rendered}\n"
                        f"  The doc is the source — it records what the owner picked from "
                        f"rendered alternatives. Change the stylesheet, or take the value "
                        f"back through an interview and change both.",
                    )
                )
    return findings


def check_design_tokens(report: Report) -> None:
    """The locked palette in docs/DESIGN.md against the custom properties the app renders.

    docs/DESIGN.md's token block is the record of an interview: every value in it was chosen
    by the owner from rendered alternatives, and the paragraphs under it argue for the
    choices. app/src/tokens.css is what the browser actually paints. Nothing compared them
    until this row existed, and docs/DEBTS.md recorded the gap with the reason it matters:
    a wrong hex renders perfectly, so the failure is silent by construction and the document
    is the one nobody re-reads.

    **Blocking, because a disagreement is provable.** Two files state the same value; either
    they match or they do not. There is no context this script is missing, which is D16's
    test for a mechanical finding rather than a printed question.

    **This is a check, not a generator, and the distinction is the whole of D18.** Nothing
    here writes. The temptation it is placed against is a build step that rewrites
    app/src/tokens.css from the block — which would run inside `make check`, make the two
    agree by construction, and turn every wrong hex into a confidently rendered one.
    Checking lets two things disagree in public.

    **What a green row means, exactly**: the values agree. It says nothing about whether the
    palette is any good — contrast is asserted in app/tests/pull-confirm.spec.ts against
    rendered pixels, and taste is what the interview was for.
    """
    missing = [rel(path) for path in (DESIGN, TOKENS_CSS) if not exists(path)]
    if missing:
        report.add(
            "design tokens",
            MECHANICAL,
            [
                Finding(
                    " ".join(missing),
                    "does not exist, so nothing compares the locked palette against what "
                    "the app renders from.",
                )
            ],
        )
        return

    block = design_token_block(read(DESIGN))
    if block is None:
        report.add(
            "design tokens",
            MECHANICAL,
            [
                Finding(
                    rel(DESIGN),
                    "has no fenced block under its `## Tokens` heading, so there is no "
                    "locked palette to compare against.\n"
                    "  The block is the record of the interview that chose these values. "
                    "If it moved, this check has to move with it.",
                )
            ],
        )
        return

    claims = design_token_claims(block)
    light, dark, every = css_token_scopes(read(TOKENS_CSS))
    doc, css = claims.names, every
    if not doc or not css:
        # A side that parses to nothing must never report a clean row — same rule as a
        # malformed `source_suffixes` scanning nothing and saying so. This is the state
        # docs/DEBTS.md calls this auditor's worst failure mode: a check gone quiet.
        report.add(
            "design tokens",
            MECHANICAL,
            [
                Finding(
                    f"{rel(DESIGN)} + {rel(TOKENS_CSS)}",
                    f"read {len(doc)} tokens from the block and {len(css)} from `:root`. "
                    f"A side that parses to nothing compares nothing.",
                )
            ],
        )
        return

    report.add(
        "design tokens",
        MECHANICAL,
        token_findings(claims, light, dark, every),
        f"{len(every)} declared tokens, every one named by the block; "
        f"{len(claims.hexes)} hexes compared across both themes",
        scanned=len(every),
    )


# ------------------------------------------------------------------ naming checks by name


# A check named by position. D17 already ruled against it for the repo-map check — "named
# rather than numbered, because a positional index re-drifts every time a check is added,
# and this one already had" — and the rest of the repo had not caught up: the section
# headers in this file ran 1 to 10 and then jumped, so two numbers in circulation pointed
# at nothing at all.
_POSITIONAL_RE = re.compile(r"\bchecks?\s+\d{1,2}\b", re.IGNORECASE)


APP_STYLES = ROOT / "app" / "src"

_RAW_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def strip_css_comments(text: str) -> str:
    """A comment replaced by as many newlines as it spanned, so line numbers survive.

    `_CSS_COMMENT_RE` is the one declared in the design-tokens section above and is
    deliberately not redeclared here — see the note on it. The newline-preserving
    substitution is this function's business; what counts as a comment is not.
    """
    return _CSS_COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def check_raw_color(report: Report) -> None:
    """A color painted as a literal instead of read from a token.

    The house rule is stated everywhere and was enforced nowhere: stylesheets use
    `var(--token)` and never a raw hex, because the locked palette is only locked if the
    palette is the only place colors come from. `design tokens` above proves
    `app/src/tokens.css` agrees with `docs/DESIGN.md` — it cannot see a stylesheet that
    bypasses both.

    **Found by grep, not by argument.** `app/src/PullConfirm.css` painted `#ffffff` twice,
    in the component the token block is the reference for, and survived a design review, a
    six-lens adversarial review and two integration passes. It was reported three times as a
    style note and refuted twice on the reasonable grounds that there was no token to use
    instead — `--surface` means "raised panel", and saying that where you mean "text on the
    loud button" conflates two things the palette keeps apart. The refutations were right and
    the conclusion was still wrong: the answer was a missing token, not a permitted literal.
    `--on-accent` now exists and names a value `docs/DESIGN.md`'s step 6 block had specified
    from the beginning.

    **Blocking, because there is nothing to judge.** A hex outside `tokens.css` either is or
    is not there, which is D16's test. Comments are stripped first — a paragraph explaining
    why `#000000` is the wrong ground is prose about a color, not a color.

    **Scope is `app/src/*.css` only.** `docs/design-refs/` is full of hex on purpose: those
    sheets are drawings of the spec, they import nothing, and `docs/design-refs/README.md`
    already records that nothing audits the values inside them.
    """
    if not exists(APP_STYLES):
        # A ROW, NOT A RETURN. A silent return deletes the row from the render entirely,
        # and nothing in this file notices a row that is absent rather than green — the
        # same blind spot `check dispatch`'s own comment records about itself. With a
        # subject count of 0 the render says `none` and `subject counts` fails the commit.
        report.add("raw color", MECHANICAL, [],
                   f"{rel(APP_STYLES)} is not there, so no stylesheet was read", scanned=0)
        return

    findings: List[Finding] = []
    sheets = 0
    for path in sorted(APP_STYLES.glob("*.css")):
        if path == TOKENS_CSS:
            continue
        sheets += 1
        for number, line in enumerate(strip_css_comments(read(path)).splitlines(), start=1):
            for literal in _RAW_COLOR_RE.findall(line):
                findings.append(
                    Finding(
                        f"{rel(path)}:{number}",
                        f"paints `{literal}` directly. Read it from a token in "
                        f"app/src/tokens.css — and if no token means what you mean, the "
                        f"missing token is the finding.",
                    )
                )

    report.add("raw color", MECHANICAL, findings,
               f"{len(findings)} literals outside tokens.css" if findings
               else f"every color in {sheets} sheets comes from a token",
               scanned=sheets)



# --------------------------------------------------------------- the breakpoint vocabulary
#
# MEASURED BEFORE IT WAS WRITTEN, 2026-09-07: 124 `@media` and 16 `@container` blocks across
# 31 stylesheets under `app/src`, and nothing had ever read them together. What the reading
# found was NOT a rendering defect — the sheets that disagreed draw different screens, so no
# person ever saw two layouts at once. It was a vocabulary nobody could read:
#
#   FOUR EDGES WERE SPELLED TWICE. `max-width: 559px` and `max-width: 560px` are one intention
#   a pixel apart, and so were 639/640, 899/900 and 1099/1100. Nothing here reflows inside a
#   one-pixel band, so the sheet that lost the coin toss folded a pixel later than the one
#   beside it, forever.
#
#   THREE INTEGERS WERE USED ON BOTH SIDES — 560, 640 and 1100 were each a `min-width`
#   somewhere and a `max-width` elsewhere, so at exactly those widths two blocks written to
#   exclude each other both applied.
#
#   AND THE LADDER'S TOP RULE HAD NO ELEMENT. `@media (max-width: 1599px)` — the single widest
#   breakpoint in the product, and the only thing above 1500 — hid `.pricing-ready-fine`, a
#   class no component in `app/src` renders. It was deleted with the rest of that class.
#
# THE REGISTER IS `docs/DESIGN.md`, NOT THIS FILE, and that is the choice `design tokens`
# makes. A ladder step is a design decision with an argument under it; a constant here would be
# a design decision in a script, which is where they stop being argued.
#
# NO COUNTS ARE PUBLISHED IN THE REGISTER, deliberately. `docs/DESIGN.md` carried "54 media
# blocks ... and six" until this row landed, and the six was seven — `scripts/checks.py`'s own
# rule arriving on schedule. The counts are in this row's summary, taken at run time.

# The sheets that ARE the shell. A width in one of them is asking about the window because the
# window is its subject: `App.css` draws the sidebar, the rail, the phone bar and the tab bar;
# `base.css` and `kit.css` load on every route; `tokens.css` raises the control heights by the
# POINTER and by the width. Everything else under `app/src` is a screen.
SHELL_SHEETS = frozenset({"App.css", "base.css", "kit.css", "tokens.css"})

# At and above this the shell has a sidebar to subtract, and how much depends on `data-rail`.
# Below it `App.css` rails unconditionally between 768 and 1023, so a viewport question and a
# column question differ by a constant and either one is answerable.
COLUMN_FLOOR = 1024

_AT_RE = re.compile(r"@(media|container)([^{]*)\{")
_WIDTH_RE = re.compile(r"\((max|min)-width:\s*(\d+)px\)")
_CONTAINER_AT_RE = re.compile(r"@container\s+([A-Za-z][\w-]*)\s*\(")
_CONTAINER_NAME_RE = re.compile(r"container-name:\s*([A-Za-z][\w-]*)")


class Widths(NamedTuple):
    """Every width condition in one stylesheet, and the container names it uses or declares."""

    media: List[Tuple[str, int, int]]      # (side, value, line)
    container: List[Tuple[str, int, int]]
    blocks: int
    queried: Set[str]
    declared: Set[str]


def read_widths(text: str) -> Widths:
    """The widths and container names in one stylesheet's TEXT. Pure, so `--self-test` can drive
    it with no repository — the filesystem is not where this can be wrong.

    COMMENTS COME OFF FIRST, and here that matters more than anywhere else this file reads CSS:
    these stylesheets argue in prose ABOUT their breakpoints. `App.css` writes "768-1023px" in
    three comments that are not rules. `strip_css_comments` replaces a comment with as many
    newlines as it spanned, so a `file:line` in a finding still points at the rule.
    """
    body = strip_css_comments(text)
    media: List[Tuple[str, int, int]] = []
    container: List[Tuple[str, int, int]] = []
    blocks = 0
    for at in _AT_RE.finditer(body):
        blocks += 1
        line = body[: at.start()].count("\n") + 1
        into = media if at.group(1) == "media" else container
        for side, value in _WIDTH_RE.findall(at.group(2)):
            into.append((side, int(value), line))
    queried = set(_CONTAINER_AT_RE.findall(body))
    declared = set(_CONTAINER_NAME_RE.findall(body))
    return Widths(media, container, blocks, queried, declared)


class Ladder(NamedTuple):
    steps: Dict[int, str]
    refinements: Dict[int, str]
    container: Set[int]
    blind: Dict[str, str]


def read_ladder(block: str) -> Ladder:
    """The four sections of the register. Pure, for `read_widths`' reason.

    THE FENCE IS PROSE LAID OUT AS A TABLE, exactly as the token block is, and this reads what
    it unambiguously states and nothing else: an indented row whose first field is a bare
    integer (LADDER, REFINEMENTS) or a `*.css` filename (COLUMN-BLIND), and whose reason is two
    or more spaces away. A section heading starts at column zero, which is how the sections are
    told apart — so a section RENAMED in the document does not silently become a fifth one and
    take its rows out of the comparison.

    CONTAINER rows carry a container name before the width and only their VALUES are collected:
    a column's width is a measurement against one pane, not a step on a shared ladder, so it
    gets no step arithmetic. Naming it is the whole requirement.
    """
    steps: Dict[int, str] = {}
    refinements: Dict[int, str] = {}
    container: Set[int] = set()
    blind: Dict[str, str] = {}
    into: Optional[str] = None
    for line in block.splitlines():
        head = re.match(r"^([A-Z][A-Z -]+?)\s{2,}", line)
        if head is not None:
            into = head.group(1).strip()
            continue
        row = re.match(r"^\s+(?:\(?[a-z][\w-]*\)?\s+)?(\d{3,4})\s{2,}(\S.*)$", line)
        if row is not None and into in ("LADDER", "REFINEMENTS", "CONTAINER"):
            value, why = int(row.group(1)), row.group(2).strip()
            if into == "LADDER":
                steps[value] = why
            elif into == "REFINEMENTS":
                refinements[value] = why
            else:
                container.add(value)
            continue
        # a CONTAINER line may carry several widths on one row (`520, 640`)
        if into == "CONTAINER":
            many = re.match(r"^\s+\(?[a-z][\w-]*\)?\s+((?:\d{3,4},\s*)+\d{3,4})\s{2,}", line)
            if many is not None:
                container.update(int(v) for v in re.findall(r"\d{3,4}", many.group(1)))
                continue
        row = re.match(r"^\s+([\w.-]+\.css)\s{2,}(\S.*)$", line)
        if row is not None and into == "COLUMN-BLIND":
            blind[row.group(1)] = row.group(2).strip()
    return Ladder(steps, refinements, container, blind)


def breakpoint_subject() -> Tuple[Optional[Tuple[Ladder, Dict[Path, Widths]]], List[Finding]]:
    """The register and the stylesheets, or the findings saying which could not be read.

    RETURNS its findings rather than reporting them, because `defined_checks` marks any
    module-level function that calls `report.add` as a check — on purpose, so a check cannot
    hide behind a helper. This is a helper genuinely shared by two rows, so it hands the
    findings back and each row files them under its own name.

    An unreadable subject is a FINDING and never a skip — the state docs/DEBTS.md calls this
    auditor's worst failure mode, a check gone quiet.
    """
    if not exists(APP_STYLES) or not exists(DESIGN):
        missing = [rel(p) for p in (APP_STYLES, DESIGN) if not exists(p)]
        return None, [Finding(" ".join(missing),
            "does not exist, so no stylesheet's widths are compared against the ladder that "
            "governs them.")]
    fence = fenced_block(read(DESIGN), r"Layout, density, and the widths")
    if fence is None:
        return None, [Finding(rel(DESIGN),
            "has no fenced block under the layout heading, so there is no register to compare "
            "against.\n"
            "  That block is where a width stops being a number somebody typed. If it moved, "
            "this row's reader has to move with it.")]
    ladder = read_ladder(fence)
    sheets = {p: read_widths(read(p)) for p in sorted(APP_STYLES.glob("*.css"))}
    if not (ladder.steps or ladder.refinements) or not sheets:
        return None, [Finding(f"{rel(DESIGN)} + {rel(APP_STYLES)}",
            f"read {len(ladder.steps)} ladder steps and {len(ladder.refinements)} refinements "
            f"from the register, and {len(sheets)} stylesheets. "
            f"A side that parses to nothing compares nothing.")]
    return (ladder, sheets), []


def check_breakpoints(report: Report) -> None:
    """Every `@media` width under `app/src`, against the ladder docs/DESIGN.md publishes.

    **Blocking, on `raw color`'s reasoning exactly.** A width is an integer in a stylesheet and
    the register is an integer in a document; either they agree or they do not, and there is no
    context this script is missing. That is D16's test for a mechanical finding rather than a
    printed question. The clause that WOULD have been a judgement — whether a rule is asking the
    viewport a question only the column can answer — is a separate ADVISORY row below, because
    answering it needs a reading of what the rule does.

    Four claims, and none of them is "this breakpoint is a good idea":

      1. ONE EDGE, ONE SPELLING. `max-width: N` and `max-width: N+1` may not both exist.
      2. ONE SIDE. No integer is both a `max-width` and a `min-width`.
      3. THE FORM. A `min-width` is a step the register names; a `max-width` is a step minus
         one. This is what makes 1 and 2 hold by construction rather than by luck.
      4. EVERY NAMED CONTAINER HAS A READER AND EVERY QUERY HAS A CONTAINER (D80, one register
         down): a `container-name` nothing queries is a declaration with no reader, and an
         `@container copies (...)` with no `copies` declared resolves against the nearest
         container instead — a rule that fires somewhere else and never says so.

    `@media` and `@container` are separate namespaces and 1-3 are asked of each on its own. A
    `pane` of 640px and a viewport of 640px are different quantities, so an integer used as a
    step in one and a measurement in the other is not a collision.

    **What a green row means, exactly**: the vocabulary agrees. It says nothing about whether a
    screen reflows WELL at any of these widths — `app/tests/wide.spec.ts` measures that above
    1280 and `app/tests/phone.spec.ts` below 768.
    """
    subject, unreadable = breakpoint_subject()
    if subject is None:
        report.add("breakpoints", MECHANICAL, unreadable)
        return
    ladder, sheets = subject
    named = dict(ladder.refinements)
    named.update(ladder.steps)
    findings: List[Finding] = []

    for kind in ("media", "container"):
        sides: Dict[Tuple[str, int], List[str]] = {}
        for path, found in sheets.items():
            for side, value, line in getattr(found, kind):
                sides.setdefault((side, value), []).append(f"{rel(path)}:{line}")

        for side, value in sorted(sides):
            if (side, value + 1) in sides:
                findings.append(Finding(", ".join(sides[(side, value)] + sides[(side, value + 1)]), (
                    f"spells one edge two ways in `@{kind}`: `{side}-width: {value}px` and "
                    f"`{side}-width: {value + 1}px`.\n"
                    f"  Nothing in this product reflows inside a one-pixel band, so these are one "
                    f"intention typed twice — and the sheet that loses folds a pixel later than "
                    f"the one beside it, forever, invisibly.\n"
                    f"  Move both onto whichever of the two the register names.")))

        for value in sorted({v for _, v in sides}):
            if ("min", value) in sides and ("max", value) in sides:
                findings.append(Finding(", ".join(sides[("min", value)] + sides[("max", value)][:3]), (
                    f"uses {value}px in `@{kind}` as BOTH a floor and a ceiling, so at exactly "
                    f"{value}px two blocks written to exclude each other both apply.\n"
                    f"  A `max-width` is the step MINUS ONE. Nothing else stops this recurring.")))

        if kind == "container":
            for (side, value), where in sorted(sides.items()):
                if value not in ladder.container:
                    findings.append(Finding(where[0], (
                        f"queries a container at `{side}-width: {value}px`, which the register's "
                        f"CONTAINER section does not name.\n"
                        f"  A column's width is a measurement against one pane, so it needs no "
                        f"step — but it does need naming, with its container and what it is for. "
                        f"A width nobody argued for is a width nobody can move.")))
            continue

        for (side, value), where in sorted(sides.items()):
            step = value if side == "min" else value + 1
            if step in named:
                continue
            findings.append(Finding(where[0], (
                f"opens a regime at `{side}-width: {value}px`, and the register names no "
                f"{step}px step."
                + (f"\n  It names {value}px. A `max-width` is the step MINUS ONE — this is the "
                   f"off-by-one claims 1 and 2 exist to stop, arriving one sheet at a time."
                   if side == "max" and value in named else
                   "\n  Add it under LADDER if any sheet may use it, or under REFINEMENTS with "
                   "the sheet that owns it and its reason."))))

    queried = {n for f in sheets.values() for n in f.queried}
    declared = {n for f in sheets.values() for n in f.declared}
    for name in sorted(queried - declared):
        where = next(rel(p) for p, f in sheets.items() if name in f.queried)
        findings.append(Finding(where, (
            f"queries `@container {name}` and no sheet under app/src declares "
            f"`container-name: {name}`. The query resolves against the nearest container "
            f"instead, or against none — and a rule that fires somewhere else never says so.")))
    for name in sorted(declared - queried):
        where = next(rel(p) for p, f in sheets.items() if name in f.declared)
        findings.append(Finding(where, (
            f"declares `container-name: {name}` and nothing queries it. Delete it or use it "
            f"(D80) — and note `container-type` also makes the element a containing block for "
            f"its `position: fixed` descendants, so an unused one is not free.")))

    blocks = sum(f.blocks for f in sheets.values())
    widths = {v for f in sheets.values() for _, v, _ in f.media}
    report.add("breakpoints", MECHANICAL, findings, (
        f"{blocks} blocks over {len(widths)} media widths in "
        f"{sum(1 for f in sheets.values() if f.blocks)} sheets, all on the ladder; "
        f"{len(declared)} named containers, each with a reader"), scanned=blocks)


def check_breakpoint_columns(report: Report) -> None:
    """A screen sheet asking the VIEWPORT a question only its COLUMN can answer.

    ADVISORY, and the severity is the finding's shape rather than its confidence. Whether a
    `min-width` is asking the wrong thing depends on what the rule DOES: a width that gates a
    `100dvh` stage, a `position: fixed` sheet or an input modality is a viewport question and is
    right as it stands. This row can see the width and not the intent, so it prints the question
    and lets the commit through — D16's line, and the same call `coupling` makes.

    THE MEASUREMENT UNDER IT. Every screen but the Fulfiller's draws inside `.bn-shell-main`,
    which is the viewport minus `--bn-sidebar-w` (236px) or minus `--bn-rail-w` (64px) when the
    rail is collapsed. Those differ by 172px — wider than the gap between two ladder steps — so
    a `min-width: 1024px` fires in a 788px column and in a 960px one and cannot tell them apart.
    Of the five blocks this row names today, `ReviewQueue.css` is the only place in the product
    that ever compensated, and it does it by writing every declaration twice.

    A sheet with a real reason is named under COLUMN-BLIND in the register and drops out here.
    """
    subject, unreadable = breakpoint_subject()
    if subject is None:
        report.add("breakpoint columns", ADVISORY, unreadable)
        return
    ladder, sheets = subject
    findings: List[Finding] = []
    for path, found in sheets.items():
        if path.name in SHELL_SHEETS or path.name in ladder.blind:
            continue
        for side, value, line in found.media:
            if side != "min" or value < COLUMN_FLOOR:
                continue
            findings.append(Finding(f"{rel(path)}:{line}", (
                f"opens a regime at `min-width: {value}px` on the VIEWPORT.\n"
                f"  This sheet draws inside `.bn-shell-main` — the viewport minus 236px, or "
                f"minus 64px when the rail is collapsed. So this fires in a {value - 236}px "
                f"column and in a {value - 64}px one and cannot tell them apart.\n"
                f"  Discharge: ask the column instead — a cap (`--bn-page-max`) or a "
                f"`container-type: inline-size` on an ancestor inside this screen, the way "
                f"`Pricing.css` and `BoxBrowse.css` already do — or, if the rule is genuinely "
                f"about the window (a `100dvh` stage, a fixed sheet, an input modality), name "
                f"this sheet under COLUMN-BLIND in docs/DESIGN.md with that reason.")))
    for name, why in sorted(ladder.blind.items()):
        path = APP_STYLES / name
        if not exists(path):
            findings.append(Finding(rel(DESIGN), (
                f"COLUMN-BLIND names `{name}`, which is not a stylesheet under app/src. "
                f"Remove the line — a stale exemption reads as coverage.")))
        elif not any(s == "min" and v >= COLUMN_FLOOR for s, v, _ in sheets[path].media):
            findings.append(Finding(rel(DESIGN), (
                f"COLUMN-BLIND excuses `{name}` from asking its column, and that sheet no "
                f"longer opens a regime at or above {COLUMN_FLOOR}px. Drop the line: the reason "
                f"it carries — {why} — is an argument nobody is making.")))
    report.add("breakpoint columns", ADVISORY, findings,
               f"{len(sheets)} sheets, {len(ladder.blind)} named column-blind",
               scanned=len(sheets))


# ------------------------------------------------------------------ the mark (D102)

LOGO_SPEC = ROOT / "docs" / "specs" / "logo.md"
MARK_PALETTES = ROOT / "app" / "src" / "kit" / "markPalettes.ts"
LOCKUP_GEOMETRY = ROOT / "app" / "src" / "kit" / "lockupGeometry.ts"
LOCKUP_TSX = ROOT / "app" / "src" / "kit" / "Lockup.tsx"

# Section 9's rows, as they are written: | mark | prism | ground | bracket | card base |
# THE BRACKET LEGEND, WHICH SECTION 9 PUBLISHES AND THIS ROW READ FOR THE FIRST TIME ON
# 2026-09-05. The locked-set table names each mark's bracket as a WORD — `chrome`, `pale gold`,
# `rose` — and resolves it three lines below in a second table. Reading only the word meant the
# four hexes it stands for were compared against nothing: 24 of the 72 hexes in
# `markPalettes.ts` were unread, in the one file CLAUDE.md's color rule takes an exception for.
# Measured: changing bluesteel's `#B8C8D8` to `#B8C8D9` left `logo parity`, `raw color` AND
# `design tokens` all green, so a color nobody approved could reach the app past every reader
# the rule has. The docstring claimed the opposite in so many words.
_S9_BRACKET = re.compile(r"^\|\s*([a-z ]+?)\s*\|\s*`((?:#[0-9A-Fa-f]{6}\s*)+)`\s*\|", re.M)

_S9_ROW = re.compile(
    r"^\|\s*\*{0,2}([a-z ]+?)\*{0,2}(?:\s*—\s*DEFAULT)?\*{0,2}\s*\|"      # the mark's name
    r"\s*`([^`]+)`\s*\|"                                                       # prism stops
    r"\s*`([^`]+)`\s*→\s*`([^`]+)`\s*\|"                                     # ground, two stops
    r"\s*\*{0,2}([a-z ]+?)\*{0,2}\s*\|"                                      # bracket name
    r"\s*`([^`]+)`\s*\|",                                                      # card base
    re.M,
)


def check_logo_parity(report: Report) -> None:
    """`app/src/kit/markPalettes.ts` and docs/specs/logo.md section 9 name the same colors.

    THIS ROW IS WHY THE MARK IS ALLOWED TO NAME COLORS AT ALL. CLAUDE.md's rule is that
    `app/src/tokens.css` is the only file in `app/` that may name one, and D102 takes a
    deliberate exception for the mark: those hexes are an illustration's, locked by another
    document, and must not be theme-overridable — which is exactly what moving them into
    `tokens.css` would invite.

    **`raw color` cannot see the file.** Its scope is `app/src/*.css`, non-recursive, and it
    never opens a `.ts` or `.tsx`, so all 72 hexes in `markPalettes.ts` pass it in silence. An
    exception with no reader is how a rule stops being one, so this row stands in its place.

    **AND IT ONLY BECAME TRUE OF ALL 72 ON 2026-09-05.** Section 9's locked-set table names each
    mark's bracket as a WORD and resolves it in a second table three lines below; this row read
    the word and never the table, so 24 of the 72 — every bracket ramp — were compared against
    nothing. Changing one of them left this row, `raw color` and `design tokens` all green, which
    is a color reaching the app past every reader CLAUDE.md's rule has. The sentence above about
    an exception with no reader was, for those 24, describing this row.

    Both directions, because the two failures are different: a palette here that section 9 does
    not publish is a color nobody approved, and a mark in section 9 that is missing here is a
    locked mark the product cannot draw. A bracket name section 9 uses and does not publish is a
    third, and it is reported rather than skipped.

    Provably wrong when it fires and no judgement to defer — both sides are literals.
    """
    if not exists(LOGO_SPEC) or not exists(MARK_PALETTES):
        # A ROW, NOT A RETURN — see `raw color`. A silent return deletes the row from
        # the render, and an absent row is the one state nothing in this file reads.
        report.add("logo parity", MECHANICAL, [],
                   "the spec or the generated palettes are not there", scanned=0)
        return

    spec = read(LOGO_SPEC)
    # `chrome` -> ['#FFFFFF', '#B8C8D8', '#F2F8FF', '#8FA4B8'], off the legend table.
    ramps = {name.strip(): stops.split() for name, stops in _S9_BRACKET.findall(spec)}

    published: Dict[str, Dict[str, object]] = {}
    unresolved: List[str] = []
    for name, prism, hi, lo, bracket, base in _S9_ROW.findall(spec):
        ramp = ramps.get(bracket.strip())
        if ramp is None:
            unresolved.append(f"{name.strip()} -> {bracket.strip()}")
        published[name.strip()] = {
            "prism": prism.split(),
            "ground": [hi, lo],
            "bracket": ramp if ramp is not None else [],
            "base": base,
        }

    if not published:
        report.add("logo parity", MECHANICAL, [Finding(
            rel(LOGO_SPEC),
            "section 9's locked-set table did not parse, so this row is not comparing "
            "anything. Say so here rather than passing — a check that silently stops "
            "checking is worse than no check.",
        )], "")
        return

    source = read(MARK_PALETTES)
    generated: Dict[str, Dict[str, object]] = {}
    for block in re.finditer(
        r"^  (\w+): \{\n"
        r"\s*label: '([^']+)',\n"
        r"\s*prism: \[([^\]]+)\],\n"
        r"\s*bracket: \[([^\]]+)\],\n"
        r"\s*ground: \['([^']+)', '([^']+)'\],\n"
        r"\s*base: '([^']+)',",
        source,
        re.M,
    ):
        _key, label, prism, bracket, hi, lo, base = block.groups()
        generated[label] = {
            "prism": re.findall(r"'(#[0-9A-Fa-f]{6})'", prism),
            "ground": [hi, lo],
            "bracket": re.findall(r"'(#[0-9A-Fa-f]{6})'", bracket),
            "base": base,
        }

    findings: List[Finding] = []
    for label in sorted(set(published) - set(generated)):
        findings.append(Finding(
            rel(MARK_PALETTES),
            f"section 9 locks `{label}` and no palette here draws it. The product cannot "
            f"render a mark the spec has locked. Re-run `node scripts/build-mark.mjs`.",
        ))
    for label in sorted(set(generated) - set(published)):
        findings.append(Finding(
            rel(MARK_PALETTES),
            f"`{label}` is a palette section 9 does not publish. Every color the mark names "
            f"is approved in docs/specs/logo.md section 9 (D102) — a hex that reaches the app "
            f"without going through that table is one nobody chose.",
        ))

    for pair in unresolved:
        findings.append(Finding(
            rel(LOGO_SPEC),
            f"section 9's locked-set table names the bracket `{pair.split(' -> ')[1]}` and the "
            f"gradient table below it does not publish that name, so the four hexes "
            f"`{pair.split(' -> ')[0]}` actually draws are approved by nothing. Add the ramp, "
            f"or rename the column to one that is published.",
        ))

    for label in sorted(set(published) & set(generated)):
        want, got = published[label], generated[label]
        for field in ("prism", "ground", "bracket", "base"):
            if want[field] != got[field]:
                findings.append(Finding(
                    f"{rel(MARK_PALETTES)} -> {label}",
                    f"{field} is {got[field]!r} here and {want[field]!r} in "
                    f"docs/specs/logo.md section 9. Section 9 is the store of record; "
                    f"re-run `node scripts/build-mark.mjs`, or move section 9 first.",
                ))

    report.add("logo parity", MECHANICAL, findings, scanned=len(published), summary=
               f"{len(published)} locked marks, every prism, ground, bracket and base "
               f"against section 9 ({sum(len(m['prism']) + len(m['ground']) + len(m['bracket']) + 1 for m in published.values())} hexes)"
               if not findings else f"{len(findings)} disagreements with section 9")



BUILD_MARK = ROOT / "scripts" / "build-mark.mjs"
APP_MANIFEST = ROOT / "app" / "public" / "manifest.webmanifest"

_S17_GRID = re.compile(r"\*\*(\d+)pt of artwork, cent(?:er|r)ed on a (\d+)pt canvas")
_MAC_GRID_CONST = re.compile(r"^const MAC_GRID = (\d+) / (\d+)\s*$", re.M)
_APP_SIZES = re.compile(r"^  const APP = \[([0-9, ]+)\]", re.M)


def _png_canvas(path: Path) -> "tuple[int, int] | None":
    """Width and height out of a PNG's IHDR. Stdlib only — this check is on the commit path.

    The pre-commit hook runs a bare `python3` with nothing installed (D18), so Pillow is not
    available here and never will be. The IHDR is the first chunk and its geometry is at a
    fixed offset, which is all this row needs: it reconciles DECLARATIONS, and the one fact it
    takes from the file itself is how big its canvas is.
    """
    try:
        head = path.read_bytes()[:24]
    except OSError:
        return None
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def check_mac_icon_grid(report: Report) -> None:
    """Apple's icon grid is one number in three places, and they must agree.

    docs/specs/logo.md section 17 publishes it, `scripts/build-mark.mjs` insets by it, and
    `app/public/manifest.webmanifest` lists the sizes it was applied to. The mark's own
    geometry is locked by section 3 and is NOT this row's business — what is, is that the
    generator and the spec do not drift apart, which is the failure `motion params` was added
    for one document over.

    **It cannot see the pixels, and says so rather than implying otherwise.** Whether a
    generated PNG's artwork really occupies 80.47% of its canvas needs an alpha bounding box,
    which needs Pillow, which is not on the commit path. So this reconciles the declarations
    and checks the one thing a PNG header can answer — that the file exists at the canvas size
    the manifest claims. A hand-edited PNG whose artwork was moved would pass; re-running the
    generator is what makes that unlikely, and the generator is what this row pins.
    """
    findings: list[Finding] = []
    spec = read(LOGO_SPEC)
    code = read(BUILD_MARK)

    published = _S17_GRID.search(spec)
    const = _MAC_GRID_CONST.search(code)
    if not published:
        findings.append(Finding(
            f"{rel(LOGO_SPEC)}",
            "section 17 no longer publishes the grid as `**<n>pt of artwork, centered on a "
            "<n>pt canvas`. That sentence is what `scripts/build-mark.mjs:MAC_GRID` is "
            "checked against; reword it back, or move this row to the new wording.",
        ))
    if not const:
        findings.append(Finding(
            f"{rel(BUILD_MARK)}",
            "`const MAC_GRID = <n> / <n>` is gone. docs/specs/logo.md section 17 publishes "
            "that ratio and nothing else reconciles the two.",
        ))
    if published and const and (
        (published.group(1), published.group(2)) != (const.group(1), const.group(2))
    ):
        findings.append(Finding(
            f"{rel(BUILD_MARK)} -> MAC_GRID",
            f"insets by {const.group(1)}/{const.group(2)} and docs/specs/logo.md "
            f"section 17 publishes {published.group(1)}/{published.group(2)}. Section 17 "
            f"is the store of record; re-run `node scripts/build-mark.mjs --icons`, or "
            f"move section 17 first.",
        ))

    # The manifest's set and the generator's set are the same set, and every file is there at
    # the canvas the manifest names. An icon listed but never generated is an install with a
    # missing size; one generated but not listed is dead weight Chrome will never read.
    sizes_m = _APP_SIZES.search(code)
    generated = ([int(n) for n in sizes_m.group(1).split(",") if n.strip()]
                 if sizes_m else [])
    try:
        listed = json.loads(read(APP_MANIFEST)).get("icons", [])
    except (ValueError, OSError):
        listed = []
    declared: list[int] = []
    for icon in listed:
        src, sizes = icon.get("src", ""), icon.get("sizes", "")
        if not src.endswith(".png"):
            findings.append(Finding(
                f"{rel(APP_MANIFEST)} -> {src}",
                "is in the manifest's icon list and is not one of the inset PNGs. Section 17 "
                "insets the WHOLE set on purpose: Chrome resizes these into the installed "
                "app's .icns, and one full-bleed entry pads the dock icon at one size and not "
                "the next. Keep it as a `<link rel=\"icon\">` instead.",
            ))
            continue
        try:
            declared.append(int(sizes.split("x")[0]))
        except ValueError:
            findings.append(Finding(f"{rel(APP_MANIFEST)} -> {src}",
                                    f"has an unreadable `sizes` of {sizes!r}."))
    if sizes_m and sorted(declared) != sorted(generated):
        findings.append(Finding(
            f"{rel(APP_MANIFEST)}",
            f"lists {sorted(declared)} and `scripts/build-mark.mjs:APP` generates "
            f"{sorted(generated)}. They are one set — a size listed but never written is a "
            f"404 at install time.",
        ))
    for size in declared:
        path = ROOT / "app" / "public" / f"icon-{size}.png"
        canvas = _png_canvas(path)
        if canvas is None:
            findings.append(Finding(f"{rel(APP_MANIFEST)}",
                                    f"names icon-{size}.png, which is missing or is not a PNG."))
        elif canvas != (size, size):
            findings.append(Finding(
                f"app/public/icon-{size}.png",
                f"is {canvas[0]}x{canvas[1]} and the manifest calls it {size}x{size}. "
                f"Re-run `node scripts/build-mark.mjs --icons`.",
            ))

    report.add("mac icon grid", MECHANICAL, findings, scanned=len(declared), summary=
               (f"{published.group(1)}/{published.group(2)} in section 17 and in build-mark.mjs, "
                f"over {len(declared)} inset icons"
                if published and const and not findings
                else f"{len(findings)} problem(s)"))


LOCKUP_ROUND = ROOT / "docs" / "specs" / "logo" / "sheets" / "lockup-round.html"
SIDEBAR_MORPH = ROOT / "docs" / "specs" / "logo" / "sheets" / "sidebar-morph.html"
MARK_GEOMETRY = ROOT / "app" / "src" / "kit" / "markGeometry.ts"
LOCKUP_TSX_ = ROOT / "app" / "src" / "kit" / "Lockup.tsx"
FAVICON = ROOT / "app" / "public" / "favicon.svg"
MARK_PALETTES = ROOT / "app" / "src" / "kit" / "markPalettes.ts"

_LOCKUP_SPEC_ROW = re.compile(r"^\|\s*`(\w+)`\s*\|\s*([0-9.]+)\s*\|", re.M)


def check_lockup_bracket(report: Report) -> None:
    """The lockup's dark bracket is a LOCKED palette, not a colour the sheet owns.

    §16 settles the dark theme's bracket as the chrome gradient `markPalettes.ts` already gives
    `bluesteel` — the default mark's own bracket — so the lockup and the mark are one object in
    one metal. That means four hexes are written in a sheet as well as in the generated file,
    which is the defect this work keeps finding, so this row reconciles them.

    `raw color` cannot see either side: its scope is `app/src/*.css`, and these are a `.ts` and
    an `.html`. Provably wrong when it fires — both sides are literals.
    """
    if not exists(SIDEBAR_MORPH) or not exists(MARK_PALETTES):
        # A ROW, NOT A RETURN — see `raw color`. A silent return deletes the row from
        # the render, and an absent row is the one state nothing in this file reads.
        report.add("lockup bracket", MECHANICAL, [],
                   "the lockup sheet or the generated palettes are not there", scanned=0)
        return
    sheet, gen = read(SIDEBAR_MORPH), read(MARK_PALETTES)
    # the component reads the palette rather than naming hexes; if it ever stops, say so here
    if exists(LOCKUP_TSX):
        tsx = read(LOCKUP_TSX)
        if "MARKS.bluesteel.bracket" not in tsx and re.search(r"#[0-9A-Fa-f]{6}", tsx):
            report.add("lockup bracket", MECHANICAL, [Finding(
                rel(LOCKUP_TSX),
                "the lockup names a color of its own instead of reading "
                "`MARKS.bluesteel.bracket`. §16 settles the dark bracket as the MARK's metal so "
                "the two are one object; `markPalettes.ts` is the only file in app/ outside "
                "tokens.css allowed to name a hex, and `raw color` cannot see a .tsx.",
            )], "")
            return
    m = re.search(r"bluesteel:\s*\{.*?bracket:\s*\[([^\]]+)\]", gen, re.S)
    if not m:
        report.add("lockup bracket", MECHANICAL, [Finding(
            rel(MARK_PALETTES),
            "`bluesteel`'s bracket is gone from the generated palettes. §16 draws the lockup's "
            "dark bracket from it; with it missing this row compares nothing.",
        )], "")
        return
    want = re.findall(r"#[0-9A-Fa-f]{6}", m.group(1))
    got_block = re.search(r"const DARK_BRACKET = \[(.*?)\]\n", sheet, re.S)
    got = re.findall(r"#[0-9A-Fa-f]{6}", got_block.group(1)) if got_block else []
    problems = []
    if [c.upper() for c in got] != [c.upper() for c in want]:
        problems.append(Finding(
            rel(SIDEBAR_MORPH),
            f"the lockup's dark bracket is {' '.join(got) or 'absent'} and `bluesteel`'s is "
            f"{' '.join(want)}. §16 settles them as the same metal so the lockup and the mark "
            f"are one object; a sheet that drifts from the palette makes them two.",
        ))
    report.add("lockup bracket", MECHANICAL, problems,
               f"{len(want)} stops against `bluesteel`'s locked bracket",
               scanned=len(want))


def check_rail_mark(report: Report) -> None:
    """The sidebar mockup's rail bracket is the mark the app actually ships.

    IT WAS AN INVENTION, and drew four things wrong at once — stroke 11.0 against the mark's
    4.2, radius 14.6 against 8, an inset of 5.5 against 22.6, and a taper §11 had removed from
    the small cut on a measurement. It had been re-derived from the DISPLAY cut's unit rescaled
    into the wrong box, in the one sheet the sidebar's size is decided from.

    The fix copies two constants out of the generated file, which is itself the defect this
    project keeps finding — a value typed a second time. So this row reconciles them. Provably
    wrong when it fires: both sides are literals.
    """
    if not exists(SIDEBAR_MORPH) or not exists(MARK_GEOMETRY):
        # A ROW, NOT A RETURN — see `raw color`. A silent return deletes the row from
        # the render, and an absent row is the one state nothing in this file reads.
        report.add("rail mark", MECHANICAL, [],
                   "the sidebar mockup or the generated mark is not there", scanned=0)
        return
    sheet, gen = read(SIDEBAR_MORPH), read(MARK_GEOMETRY)
    # How many comparisons this row actually made. Two of them are the copied
    # constants and the rest are the tab's, which only exist if the favicon does.
    compared = 0
    want_path = re.search(r"SMALL_BRACKET = '([^']+)'", gen)
    want_stroke = re.search(r"SMALL_STROKE = ([\d.]+)", gen)
    got_path = re.search(r"MARK_SMALL_BRACKET = '([^']+)'", sheet)
    got_stroke = re.search(r"MARK_SMALL_STROKE = ([\d.]+)", sheet)
    if not (want_path and want_stroke):
        report.add("rail mark", MECHANICAL, [Finding(
            rel(MARK_GEOMETRY),
            "SMALL_BRACKET or SMALL_STROKE is gone from the generated mark. The sidebar mockup "
            "copies both; with them missing this row compares nothing, which is worse than failing.",
        )], "")
        return
    problems = []
    compared += 2  # the bracket path and the stroke, both copied out of the generated mark
    if not got_path or got_path.group(1) != want_path.group(1):
        problems.append(Finding(
            rel(SIDEBAR_MORPH),
            "the rail's bracket path is not the mark's. `markGeometry.ts` is generated from "
            "`small-cut.html` and is what every surface below 64px draws (D102); a sheet that "
            "re-derives it is drawing a mark the product does not contain.",
        ))
    if not got_stroke or abs(float(got_stroke.group(1)) - float(want_stroke.group(1))) > 1e-9:
        problems.append(Finding(
            rel(SIDEBAR_MORPH),
            f"the rail's stroke is {got_stroke.group(1) if got_stroke else 'absent'} and the "
            f"mark's is {want_stroke.group(1)}.",
        ))
    # THE SHIPPED COMPONENT IS THE THIRD SIDE, and it is checked differently on purpose.
    # `Lockup.tsx` does not COPY the rail's bracket — it imports `RAIL_ARM`, which
    # `build-lockup.mjs` generates by running the sheet's own `taperParts` at `tip = 1` and then
    # RENDERS against this file's stroked wire, refusing to write if they differ by more than 2%
    # of inked pixels at 10x. That is a stronger check than anything this row could perform, so
    # what is checked here is that it is still the check in force: a component that stops
    # importing the generated end, or grows a path literal, has quietly reintroduced the
    # invention this row was written for, one file further along.
    if exists(LOCKUP_TSX_):
        comp = read(LOCKUP_TSX_)
        if not re.search(r"import\s*\{[^}]*\bRAIL_ARM\b[^}]*\}\s*from\s*'\./lockupGeometry'", comp,
                         re.S):
            problems.append(Finding(
                rel(LOCKUP_TSX_),
                "the lockup no longer takes RAIL_ARM from the generated `lockupGeometry.ts`. That "
                "path is the collapse's rail end and the ONLY thing holding it to markGeometry.ts's "
                "own wire (D102, section 1) is the generator's pixel assertion against it; a "
                "component that draws its own is a second mark that agrees today.",
            ))
        if re.search(r"d=[\"']M[^\"']{40,}", comp):
            problems.append(Finding(
                rel(LOCKUP_TSX_),
                "a path literal is written into the lockup. Every drawing comes from the "
                "generator (D102); nothing about the mark is hand-drawn in app/.",
            ))
    if exists(LOCKUP_GEOMETRY):
        gen = read(LOCKUP_GEOMETRY)
        if "RAIL_ARM" not in gen:
            problems.append(Finding(
                rel(LOCKUP_GEOMETRY),
                "the generated geometry has no RAIL_ARM. The collapse morphs the bracket from the "
                "lockup's tapered frame to the mark's wire and needs both ends at one topology; "
                "without it the shell can only crossfade two drawings, which is what section 16 "
                "recorded as unavoidable and it was not.",
            ))
    # THE BROWSER TAB IS THE FOURTH SIDE, settled in section 18: the empty slot, the mark's own L,
    # no tile and no card. It is generated, so what can go wrong is a regeneration that quietly
    # reverts it to the whole mark — which would look entirely plausible and which no other row
    # here can see. A `<rect>` is the tell: the tile's sheen band and the card are both rects and
    # the bracket pair contains none.
    if exists(FAVICON):
        fav = read(FAVICON)
        compared += 3  # the rect, the settled paint, and the gradient
        if "<rect" in fav:
            problems.append(Finding(
                rel(FAVICON),
                "the browser tab is drawing a rect. Section 18 settles it as the EMPTY SLOT — the "
                "bracket pair alone, no tile, no card, no sheen — and every one of those three is "
                "a rect. The app icons keep the full mark; this file is the tab.",
            ))
        # THE PAINT IS SETTLED IN SECTION 18 AND READ FROM THERE, so the two cannot disagree —
        # `build-mark.mjs` greps that table rather than holding a hex. This row is what makes
        # that arrangement real: the spec is the state of record and the generated file has to
        # show it. The tab is the one Banchi surface NOT in a metal, and a regeneration that
        # quietly put the gradient back would look right on a dark bar and vanish on a light one,
        # which is the defect section 18 exists to record.
        want = re.search(r"\| paint \| \*\*flat `(#[0-9A-Fa-f]{6})`\*\*", read(LOGO_SPEC)) \
            if exists(LOGO_SPEC) else None
        if not want:
            problems.append(Finding(
                rel(LOGO_SPEC),
                "section 18 no longer settles the tab's paint as `| paint | **flat `#RRGGBB`** |`. "
                "`scripts/build-mark.mjs` reads that row and refuses to build without it.",
            ))
        elif want.group(1) not in fav:
            problems.append(Finding(
                rel(FAVICON),
                f"the browser tab is not painted {want.group(1)}, which is what section 18 settles. "
                "Gold is the only paint that reads on a dark browser bar and a light one, and the "
                "tab carries no ground of its own — silver vanishes on light, ink on dark.",
            ))
        if "Gradient" in fav:
            problems.append(Finding(
                rel(FAVICON),
                "the browser tab has a gradient. Section 18 settles it FLAT: at 16px the bracket "
                "pair is about twelve pixels of ink and a four-stop gradient across it resolves to "
                "noise. Every other surface keeps its metal; this one traded it for legibility.",
            ))
    report.add("rail mark", MECHANICAL, problems,
               "the rail bracket is the shipped mark — in the sheet, at both ends of the "
               "morph, and on the tab", scanned=compared)


def check_lockup_params(report: Report) -> None:
    """The lockup sheet's declared holds and docs/specs/logo.md's settled table agree.

    A PARAMETER SETTLED IN A ROUND AND THEN TYPED A SECOND TIME IS HOW THAT SHEET ALREADY WENT
    WRONG, twice, in the same row: a hand-written caption said a value had been rejected in a
    round it had not been. The sheet fixed its own half by deriving every label from one
    `ROUND` object. This row is the other half — the object and the spec are two copies of the
    same decision, and nothing was comparing them.

    The sheet asserts, on every render, that the values it DECLARES as held were the values it
    actually DREW. That is a different claim from this one and neither covers the other: the
    sheet cannot see the spec, and this row cannot see a drawing.

    Provably wrong when it fires — both sides are literals.
    """
    if not exists(LOGO_SPEC) or not exists(LOCKUP_ROUND):
        # A ROW, NOT A RETURN — see `raw color`. A silent return deletes the row from
        # the render, and an absent row is the one state nothing in this file reads.
        report.add("lockup params", MECHANICAL, [],
                   "the spec or the round lockup sheet is not there", scanned=0)
        return

    spec_section = read(LOGO_SPEC)
    marker = "### The settled values, and the one place they live"
    if marker not in spec_section:
        report.add("lockup params", MECHANICAL, [Finding(
            rel(LOGO_SPEC),
            "the settled-values table is gone. This row compares it against the sheet's holds; "
            "with it missing the row is not comparing anything, which is worse than failing.",
        )], "")
        return
    tail = spec_section[spec_section.index(marker):]
    tail = tail[: tail.index("\n### ", 10)] if "\n### " in tail[10:] else tail
    published = {k: float(v) for k, v in _LOCKUP_SPEC_ROW.findall(tail)}

    sheet = read(LOCKUP_ROUND)
    # THE KEY THE ROUND IS SWEEPING CANNOT ALSO BE HELD, and the first version of this row did not
    # know that: it fired the moment a settled parameter came up for its own round. A settled value
    # must be pinned OR be the one under test, and "under test" is a state the sheet declares.
    sweeping = re.search(r"sweeping:\s*'(\w+)'", sheet)
    sweeping = sweeping.group(1) if sweeping else ""
    block = re.search(r"holds:\s*\{([^}]*)\}", sheet)
    if block is None or not published:
        report.add("lockup params", MECHANICAL, [Finding(
            rel(LOCKUP_ROUND),
            "no `holds: {...}` in the round sheet, or no rows in the spec table. Say so here "
            "rather than passing.",
        )], "")
        return
    declared = {
        k: float(v)
        for k, v in re.findall(r"(\w+)\s*:\s*([0-9.]+)", block.group(1))
    }

    findings: List[Finding] = []
    for key in sorted(set(published) - set(declared) - {sweeping}):
        findings.append(Finding(
            rel(LOCKUP_ROUND),
            f"docs/specs/logo.md settles `{key}` at {published[key]} and the sheet neither holds "
            f"it nor is sweeping it. A settled parameter that is neither pinned nor under test is "
            f"one the next round can move without anybody noticing.",
        ))
    for key in sorted(set(declared) - set(published)):
        findings.append(Finding(
            rel(LOGO_SPEC),
            f"the sheet holds `{key}` at {declared[key]} and the settled table does not list it. "
            f"Every value a round holds fixed is a decision, even an inherited one.",
        ))
    for key in sorted(set(declared) & set(published)):
        if abs(declared[key] - published[key]) > 1e-9:
            findings.append(Finding(
                f"{rel(LOCKUP_ROUND)} -> {key}",
                f"held at {declared[key]} in the sheet and settled at {published[key]} in "
                f"docs/specs/logo.md. The spec is the store of record; move the sheet, or move "
                f"the spec first and say which round moved it.",
            ))

    # THE GENERATED FILE IS THE THIRD COPY, and §15 asked for it by name: "once a generated file
    # exists it must reconcile both directions against that too, exactly as `logo parity` does
    # for `markPalettes.ts`". Without this row the app could draw a lockup the spec does not
    # describe and every other check would stay green — which is what `logo parity` exists for.
    if exists(LOCKUP_GEOMETRY):
        gen = read(LOCKUP_GEOMETRY)
        block = re.search(r"export const PARAMS = \{(.*?)\} as const", gen, re.S)
        if block is None:
            findings.append(Finding(
                rel(LOCKUP_GEOMETRY),
                "no `PARAMS` in the generated geometry. The app draws from this file; with the "
                "block missing nothing reconciles what it draws against the spec that settled it.",
            ))
        else:
            built = {k: float(v) for k, v in
                     re.findall(r"(\w+)\s*:\s*([0-9.]+)", block.group(1))}
            for key in sorted(set(published) & set(built)):
                if abs(built[key] - published[key]) > 1e-9:
                    findings.append(Finding(
                        f"{rel(LOCKUP_GEOMETRY)} -> {key}",
                        f"generated at {built[key]} and settled at {published[key]} in "
                        f"docs/specs/logo.md. Re-run `node scripts/build-lockup.mjs`, or move the "
                        f"spec first and say which round moved it.",
                    ))
            for key in sorted(set(published) - set(built)):
                findings.append(Finding(
                    rel(LOCKUP_GEOMETRY),
                    f"docs/specs/logo.md settles `{key}` and the generated geometry does not "
                    f"carry it. A settled value the app never receives is one the drawing can "
                    f"ignore.",
                ))

    report.add("lockup params", MECHANICAL, findings, scanned=len(published), summary=
               f"{len(published)} settled values against the sheet's holds"
               + (" and the generated geometry" if exists(LOCKUP_GEOMETRY) else "")
               + (f", `{sweeping}` under test" if sweeping in published else "")
               if not findings else f"{len(findings)} disagreements")


# ------------------------------------------------------------------ views opsec (D24)

VIEWS_MANIFEST = ROOT / "scripts" / "views.txt"
APP_SRC = ROOT / "app" / "src"
APP_TSX = APP_SRC / "App.tsx"
APP_SERVER_TS = APP_SRC / "server.ts"
APP_TESTS = ROOT / "app" / "tests"

# The one origin `make dev` serves. strictPort in app/vite.config.ts exists so that a busy
# 5173 fails instead of quietly serving on 5174 — "where CLAUDE.md, this target and
# scripts/views.txt would all three be wrong" (Makefile). This set is the same fact.
APP_ORIGINS = {"localhost:5173", "127.0.0.1:5173"}

# A file whose CODE mentions the photo service. `photoUrl` is the single mint of
# `GET /photo/<box>/<index>` URLs (app/src/server.ts, D6); the literal path is the belt for
# a caller that builds the URL by hand. Run against comment-stripped text only — types.ts
# and Gallery.tsx both DISCUSS the route in prose and draw nothing from it.
_PHOTO_USE_RE = re.compile(r"\bphotoUrl\b|/photo/")


def _strip_ts_comments(text: str) -> str:
    """Block and whole-line comments out of a .ts/.tsx file, so prose about the photo
    service is never mistaken for a screen that draws from it. Trailing `// ...` after code
    is kept — over-matching there costs a printed question, never a blocked commit."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", text)


def _resolve_ts_module(from_file: Path, spec: str) -> Optional[Path]:
    base = from_file.parent / spec
    for candidate in (Path(str(base) + ".tsx"), Path(str(base) + ".ts")):
        if exists(candidate):
            return candidate
    return None


def _routes_table() -> Optional[Dict[str, Optional[Path]]]:
    """`app/src/App.tsx`'s ROUTES literal as route path -> component file, or None when the
    table cannot be read at all — which is a finding, not a shrug, because every verdict
    below hangs off it."""
    if not exists(APP_TSX):
        return None
    text = read(APP_TSX)
    table = re.search(r"const ROUTES[^=]*=\s*\[(.*?)\n\]", _strip_ts_comments(text), flags=re.S)
    if table is None:
        return None
    pairs = re.findall(r"path:\s*'([^']*)'[^{}]*?view:\s*([A-Za-z0-9_]+)", table.group(1))
    if not pairs:
        return None
    ident_to_spec: Dict[str, str] = {}
    for names, spec in re.findall(
        r"import\s+(?:type\s+)?([^;]*?)\s+from\s+['\"](\.[^'\"]+)['\"]", text
    ):
        for ident in re.findall(r"[A-Za-z0-9_]+", names):
            ident_to_spec[ident] = spec
    return {
        path: _resolve_ts_module(APP_TSX, ident_to_spec[view]) if view in ident_to_spec else None
        for path, view in pairs
    }


def _photo_reach(entry_file: Path) -> List[str]:
    """Every file in the component's import subtree whose code touches the photo service.

    Import-graph reach, not a judgment about what renders: a screen that imports a
    component that draws stored photos can draw them, and whether its runtime state ever
    does is exactly what this script cannot know. That asymmetry is why the row this feeds
    is advisory — see check_views_opsec.
    """
    seen: Set[Path] = set()
    stack = [entry_file]
    reached: List[str] = []
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        try:
            text = read(current)
        except Exception:
            continue
        if current != APP_SERVER_TS and _PHOTO_USE_RE.search(_strip_ts_comments(text)):
            reached.append(rel(current))
        for spec in re.findall(r"from\s+['\"](\.[^'\"]+)['\"]", text):
            if spec.endswith(".css"):
                continue
            resolved = _resolve_ts_module(current, spec)
            if resolved is not None:
                stack.append(resolved)
    return sorted(reached)


# A Playwright title, and ONLY off a bare `test(`. Every one of this repo's 370 tests is
# written that way, so nothing is lost by refusing `test.skip` and `test.only` — and a
# skipped proof must never go on holding a route out of the exposure list. Anything this
# cannot parse yields no title, which puts a route back IN the list rather than out of it.
_TEST_TITLE_RE = re.compile(
    r"^\s*test\(\s*(?P<q>['\"`])(?P<title>(?:\\.|(?!(?P=q))[^\\])*)(?P=q)",
    re.M,
)
_POOLED_SUBJECT_RE = re.compile(r"\bpooled\b", re.I)
_ABSOLUTE_NEGATIVE_RE = re.compile(r"\bnever\b", re.I)


def _pooled_absence_titles(spec_text: str) -> List[str]:
    """The test titles in a spec that CLAIM a pooled card is never drawn.

    The claim has to be in the TITLE, and that is the whole correction. A title is where
    this repo makes a spec answerable: it is the sentence the runner prints, the one a
    grep finds, and the one a person deletes when the behavior goes away. A spec's BODY
    carries the vocabulary whichever way its assertions run, so matching the body reads
    `pooled` out of a fixture field, a passing comment, or a proof of the OPPOSITE claim.

    MEASURED ON THE COMMITTED TREE, not predicted. The body match `pooled|located` held
    three routes out of the exposure list and not one of them asserted anything:

      - `app/tests/gallery.spec.ts` says `pooled` twelve times while proving the pooled
        row IS drawn — "the pooled row is a second no-bar shell, and it has not left".
        The spec whose subject is the pooled shape was the spec that suppressed the
        question about it.
      - `app/tests/inventory.spec.ts` matched on `located: true`, a fixture field.
      - `app/tests/pricing.spec.ts` contains no `pooled` at all. Its first match is the
        substring inside the word RELOCATED, in a comment about where a test was moved
        from. The pattern was not even word-bounded.

    A qualifying title names the pooled subject and makes an ABSOLUTE negative claim about
    it — `never`, not `not`. The row asks whether ANY render can contain a bearer
    instrument, so a title hedged to one case does not answer it, and `not` is how the two
    presence-asserting titles above happen to read ("has not left"). Two titles qualify
    today: the Fulfillment view's "a pooled card is never on his screen", which is the
    shape D24 asked for by name, and the review queue's "a pooled card never draws a
    photograph here", which cites this row in its own comment.

    What this still cannot do is read the assertions under the title, and a title using
    `never` to claim a pooled card is always drawn would pass it. That residual is a
    sentence a human deliberately wrote about a pooled card in the place this repo puts
    claims it stands behind, and the row is ADVISORY (D16). The defect being repaired is
    not a claim misjudged; it is that no claim was being read at all.
    """
    return [
        match.group("title")
        for match in _TEST_TITLE_RE.finditer(spec_text)
        if _POOLED_SUBJECT_RE.search(match.group("title"))
        and _ABSOLUTE_NEGATIVE_RE.search(match.group("title"))
    ]


def _pooled_exclusion_evidence(route_path: str) -> Optional[str]:
    """Committed proof that a route's screen never draws a pooled card's photo.

    The Fulfillment shape, exactly as D24 demanded it: `app/tests/fulfillment.spec.ts`
    asserts "a pooled card is never on his screen", in a spec `make design-check` runs.
    The tie is mechanical — the spec named after the route, carrying a TEST TITLE that
    makes that claim (`_pooled_absence_titles`, which argues the title/body line) — and
    self-cleaning: delete the assertion, or soften its title off the claim, and the route
    rejoins the exposure list. The root route has no segment to name a spec after, so it
    maps to `capture.spec.ts`: the capture screen is what `/` renders, and the manifest
    has always called it that.
    """
    name = route_path.strip("/") or "capture"
    if "/" in name:
        return None
    spec = APP_TESTS / f"{name}.spec.ts"
    if exists(spec) and _pooled_absence_titles(read(spec)):
        return rel(spec)
    return None


# ------------------------------------------------------- browser storage keys (D27, D94)

INDEX_HTML = ROOT / "app" / "index.html"

# A key literal, in either store. The two prefixes are the whole namespace: `banchi.` for
# anything written since the rebrand and `pkmnscan.` for everything older, frozen at its
# spelling because renaming a live key silently discards what sits under the old one (D94).
_STORAGE_KEY_RE = re.compile(r"""['"]((?:banchi|pkmnscan)\.[A-Za-z0-9._-]+)['"]""")

# The same key as a DOCUMENT writes it — bare, inside a fenced block, with no quotes to
# anchor on. D27's session roster is written that way, and reading it with the code regex
# above found nothing at all, which is a broken reader that reads like a broken entry.
_FENCED_STORAGE_KEY_RE = re.compile(r"\b((?:banchi|pkmnscan)\.[A-Za-z0-9._-]+)")

# Which store a file touches. Member access only — `window.localStorage`, a bare
# `localStorage`, and the `window["localStorage"]` spelling the lint rule also has to cover.
_STORAGE_USE_RE = re.compile(r"""\b(local|session)Storage\b|['"](local|session)Storage['"]""")

# CLAUDE.md's published roster. Anchored on the sentence, not on a line number: the count is
# a WORD there because the sentence is prose, and a digit would read as a heading number.
_ROSTER_RE = re.compile(
    r"\*\*(\w+) keys are stored on the device.*?\*\*(.*?)(?=\n\n)", re.S
)
_ROSTER_FILE_RE = re.compile(r"`(app/src/[A-Za-z0-9_/]+\.tsx?)`")

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}


def _storage_sites() -> Tuple[Dict[str, Dict[str, List[str]]], List[Finding]]:
    """Every browser-storage key the app writes, by store, with the files that hold it.

    KEYS ARE BOUND TO A STORE BY THEIR FILE, not by their call site, and that is the honest
    limit of this reader. `app/src/CaptureScreen.tsx` reaches its keys through one
    `readSession(key)` helper, so the literal and the `sessionStorage` call are in different
    functions and no regex walks from one to the other; `app/src/useCamera.ts` passes consts
    for the same reason `app/eslint.config.js` gives — a selector cannot read a key handed
    over as an identifier. What holds instead is that no file in this app touches both stores,
    which makes the file a sound binding — and a file that starts touching both is reported
    rather than guessed at, because that is the moment this reader would begin to lie.
    """
    findings: List[Finding] = []
    by_store: Dict[str, Dict[str, List[str]]] = {"local": {}, "session": {}}
    sources = sorted(APP_SRC.rglob("*.ts")) + sorted(APP_SRC.rglob("*.tsx"))
    for path in sources + [INDEX_HTML]:
        if not exists(path):
            continue
        text = read(path)
        body = _strip_ts_comments(text) if path.suffix != ".html" else re.sub(
            r"<!--.*?-->", "", text, flags=re.S
        )
        keys = sorted(set(_STORAGE_KEY_RE.findall(body)))
        if not keys:
            continue
        stores = {a or b for a, b in _STORAGE_USE_RE.findall(body)}
        if not stores:
            # A key spelling in a file that opens no store. Nothing does this today; it is
            # most likely a doc comment that survived the strip, so it is passed over rather
            # than reported — a false alarm on a comment is the one thing that would teach
            # somebody to route around this row.
            continue
        if len(stores) > 1:
            findings.append(
                Finding(
                    rel(path),
                    "touches both `localStorage` and `sessionStorage`, so this row cannot say "
                    "which store its keys belong to.\n"
                    f"  keys here: {', '.join('`' + k + '`' for k in keys)}\n"
                    "  Split the device-local keys into their own module the way "
                    "`app/src/deviceMemory.ts` already is, or bind each key to its store some "
                    "way a reader can follow. The binding is by FILE and there is no other.",
                )
            )
            continue
        store = stores.pop()
        for key in keys:
            by_store[store].setdefault(key, []).append(rel(path))
    return by_store, findings


def _decision_entry(number: int) -> Optional[Tuple[str, str]]:
    """(repo-relative path, text) of the entry whose heading is `## D<n> — …`, or None.

    FOUND BY HEADING AND NEVER BY FILENAME. A claim renames the file (D140), so a path
    typed here would go stale at the next merge while still pointing at a real document.
    """
    pattern = re.compile(rf"^##\s+D{number}\s+—", re.M)
    for path in decision_files():
        text = read(path)
        if pattern.search(text):
            return rel(path), text
    return None


def _session_fence_findings(session: Dict[str, List[str]]) -> List[Finding]:
    """D27's fenced session roster against what the app writes, in both directions.

    THE NARROWER PERMISSION HAD THE WEAKER READER. `localStorage` is reconciled against
    CLAUDE.md's count, roster and files in both directions; `sessionStorage` was held only
    to "named in some markdown", so D27's own fenced block could sit stale with the row
    green — and did. Measured 2026-09-12: the fence publishes EIGHT keys and the app writes
    TWO, because D142 moved six capture settings into `deviceMemory.ts`'s
    `banchi.capture.setup` on the operator's report that a shift ends when they stop
    feeding cards, which is neither a new tab nor a closed browser. The entry's next
    sentence still said `SESSION_KEYS` "declares the first seven"; it declares one.

    CLAUDE.md had already been corrected and dated for exactly this. The decision entry had
    not, and nothing could say so — which is the same defect this row was built for on the
    other store, where the sentence said FOUR and listed five for three days.

    **THE FENCE ONLY, NEVER THE SURROUNDING ARGUMENT.** D27 legitimately discusses the
    retired `pkmnscan.*` spellings, the six keys that left, and what each one cost, all in
    prose. Reading the whole entry backwards would fail the commit over every abandoned key
    the entry exists to explain.
    """
    found = _decision_entry(27)
    if found is None:
        return [Finding(
            "docs/decisions/",
            "no entry headed `## D27 — …`, and it is what publishes the `sessionStorage` "
            "carve-out's roster. Renumbered, renamed past the heading grammar, or gone — "
            "either way this leg is reconciling nothing.",
        )]
    where, text = found
    fence = re.search(r"^```\n(.*?)^```", text, flags=re.M | re.S)
    if fence is None:
        return [Finding(
            where,
            "carries no fenced key block, and its roster is what this row reconciles "
            "against `app/src`.\n"
            "  Restore the fence, or say in the entry that the roster lives elsewhere — a "
            "leg with no subject prints green over whatever the app happens to write.",
        )]
    # BARE, not quoted. `_STORAGE_KEY_RE` reads a key literal out of CODE, where it wears
    # quotes; inside a fenced block a key is written as the app spells it and nothing else,
    # so the same regex found none and this leg printed a finding that read like a broken
    # entry rather than a broken reader.
    published = set(_FENCED_STORAGE_KEY_RE.findall(fence.group(1)))
    findings: List[Finding] = []
    if not published:
        return [Finding(
            where, "its fenced key block yields no key this row can read."
        )]
    for key in sorted(published - set(session)):
        findings.append(Finding(
            where,
            f"publishes `{key}` in its session roster and no file in `app/src` writes it to "
            "`sessionStorage`.\n"
            "  A key in the fence that the app does not write is a roster describing a "
            "product that has moved. Amend the entry with what happened to it — the fence "
            "is read, the argument around it is not.",
        ))
    for key in sorted(set(session) - published):
        findings.append(Finding(
            session[key][0],
            f"`{key}` is written to `sessionStorage` and D27's fenced roster does not name "
            "it.\n"
            "  That carve-out is the NARROWER permission: a key is in it because somebody "
            "argued the session scope is right for that value. Add it to the fence.",
        ))
    return findings


def check_storage_keys(report: Report) -> None:
    """Every browser-storage key the app writes, against what the docs publish.

    THIS ROW EXISTS BECAUSE THE PUBLISHED SENTENCE WAS WRONG AND NOTHING COULD SAY SO.
    CLAUDE.md read "**Four keys are stored on the device**" and then listed five, from
    2026-09-03 — the day `banchi.orders.last-check` landed — until 2026-09-06. In the same
    sentence the theme and the rail were attributed to `app/src/kit/index.tsx` and
    `App.tsx`, which is where they are USED; `app/src/deviceMemory.ts` is the module that
    holds them, and it exists precisely so that a reviewer has one file to read. Neither
    error was reachable from any check in this file.

    `app/eslint.config.js` is not that check and cannot become one. It bans the STORE by
    esquery selector and says so at length: a selector cannot read a key passed as a const,
    so the only exception it can express is a named FILE. It answers "may this file open
    `localStorage`" and never "which keys exist, what are they called, and does the
    documentation match" — which is the whole of what went wrong.

    TWO STORES, TWO DIFFERENT BARS, because the docs make two different promises.

     - `localStorage` is RECONCILED. CLAUDE.md publishes a count, a roster and the files, so
       all three are held against `app/src` in both directions. A key that survives closing
       the browser is the one a stale roster costs something for: D27 permits it only for
       facts about THIS MACHINE, and the way that permission erodes is one key at a time
       with nobody counting.
     - `sessionStorage` must only be NAMED IN MARKDOWN SOMEWHERE, the bar `check_env_names`
       sets for environment variables and for the reason given there — nothing mechanical
       can judge whether an explanation is any good, but it can hold that the key was
       written down once, on purpose, where a reader looking for it would find it. D27
       promised its keys were "named here" and named them only as English (*box number, set
       hint, finish claim…*) while the app spelled them `pkmnscan.session.*`. Measured
       2026-09-06: seven of the eight keys under that carve-out appeared in no markdown file
       in this repo, and two of them — `game` and `product` — had never been described in
       any form, having arrived after the entry was written.

    THE PREFIX IS HELD TOO, AS OF 2026-09-06, AND THIS ROW ARGUED THE OTHER WAY FIRST. The
    audit that built it proposed freezing `pkmnscan.*` on the ten keys that carried it —
    D94 keeps every name beneath the product, a key's spelling is fixed on the day it is
    written, and renaming a live one discards whatever a browser holds under the old
    spelling. The owner overruled that after being shown the cost, declined a read-time
    fallback because a fallback can never safely be deleted afterwards, and took the loss:
    two presses on the rig, six on a capture tab left open across the deploy, and one key
    (`captureId`) that can burn a position if a capture was in flight at that moment. So
    there is no frozen set to remember, which is the only reason a prefix rule is checkable
    at all — `banchi.` on every key, with the whole argument in D27's second amendment.

    D94 IS NOT REOPENED BY THAT and this row is not evidence that it is. That entry governs
    the checkout, the CLI, the packages, the store on disk, every route on the wire and
    `PKMNSCAN_HOME`; a storage key is a name this product writes and no other program reads,
    which is what separates it from every item on that list. Nothing here should be read as
    licence to rename anything else.
    """
    by_store, findings = _storage_sites()
    local, session = by_store["local"], by_store["session"]

    # THE PREFIX, over both stores at once. One line, because after the 2026-09-06 rename
    # there is no exception set to carry — the moment there is one, this becomes a list
    # somebody has to maintain and the rule stops being a rule.
    for key in sorted(set(local) | set(session)):
        if not key.startswith("banchi."):
            where = (local.get(key) or session.get(key) or ["app/src"])[0]
            findings.append(
                Finding(
                    where,
                    f"`{key}` does not carry the `banchi.` prefix every browser-storage key "
                    "has carried since 2026-09-06 (D27, second amendment).\n"
                    "  Ten keys were renamed off `pkmnscan.` that day, with no migration and "
                    "the cost accepted in writing. A new key spelled the old way is not "
                    "continuity with them — they are gone — it is a second convention.",
                )
            )

    claude = ROOT / "CLAUDE.md"
    roster = _ROSTER_RE.search(read(claude)) if exists(claude) else None
    if roster is None:
        findings.append(
            Finding(
                "CLAUDE.md",
                "no `**N keys are stored on the device**` sentence found, so the roster this "
                "row reconciles is gone or reworded past the pattern watching it.\n"
                f"  the app writes {len(local)} `localStorage` key(s): "
                f"{', '.join('`' + k + '`' for k in sorted(local))}\n"
                "  Restore the sentence, or delete this row rather than leaving it passing "
                "vacuously — see docs/DEBTS.md on a green row that cannot fail.",
            )
        )
    else:
        word, paragraph = roster.group(1), roster.group(0)
        published = set(_STORAGE_KEY_RE.findall(paragraph.replace("`", "'")))
        count = _NUMBER_WORDS.get(word.lower())
        if count is None:
            findings.append(
                Finding("CLAUDE.md", f"`{word} keys are stored on the device` — not a number word.")
            )
        elif count != len(local):
            findings.append(
                Finding(
                    "CLAUDE.md",
                    f"says `{word}` ({count}) keys are stored on the device; `app/src` writes "
                    f"{len(local)}.\n"
                    f"  in the app: {', '.join('`' + k + '`' for k in sorted(local))}\n"
                    "  This is the exact defect the row was built for: the sentence said four "
                    "and listed five for three days.",
                )
            )
        for key in sorted(published - set(local)):
            findings.append(
                Finding(
                    "CLAUDE.md",
                    f"`{key}` is published as a device-local key and no file in `app/src` "
                    "writes it to `localStorage`.",
                )
            )
        for key in sorted(set(local) - published):
            findings.append(
                Finding(
                    local[key][0],
                    f"`{key}` is written to `localStorage` and CLAUDE.md's roster does not "
                    "name it.\n"
                    "  D27 permits `localStorage` only for facts about THIS MACHINE. Add it "
                    "to that sentence with what it is a fact about, and correct the count.",
                )
            )
        named = set(_ROSTER_FILE_RE.findall(paragraph))
        holding = {f for files in local.values() for f in files if f.startswith("app/src/")}
        for path in sorted(named - holding):
            findings.append(
                Finding(
                    "CLAUDE.md",
                    f"the roster names `{path}` and that file writes no `localStorage` key.\n"
                    "  Name the module that HOLDS the key, not the screen that reads it back. "
                    "`App.tsx` and `kit/index.tsx` were named here and "
                    "`app/src/deviceMemory.ts`, which exists to hold them, was not.",
                )
            )
        for path in sorted(holding - named):
            findings.append(
                Finding(
                    path,
                    "writes a `localStorage` key and CLAUDE.md's roster does not name this "
                    f"file: {', '.join('`' + k + '`' for k in sorted(k for k in local if path in local[k]))}",
                )
            )

    documented = "\n".join(read(doc) for doc in markdown_files())
    for key in sorted(session):
        if key not in documented:
            findings.append(
                Finding(
                    session[key][0],
                    f"`{key}` is written to `sessionStorage` and named in no markdown file.\n"
                    "  D27 says the permitted keys are named there. Spell it — describing a "
                    "key in English is not naming it, and a key nothing spells is one no "
                    "search finds.",
                )
            )

    # ---- and D27's own fence, BOTH DIRECTIONS ------------------------------------------
    findings.extend(_session_fence_findings(session))

    report.add(
        "storage keys",
        MECHANICAL,
        findings,
        f"{len(local)} device-local keys against CLAUDE.md's roster, "
        f"{len(session)} session keys all named in markdown",
        scanned=len(local) + len(session),
    )


#: `# OFF_RENDER #/inventory — <reason>` in scripts/views.txt. A comment, so
#: `make screenshot` skips it and this row reads it — the same arrangement `OFF_NAV` has in
#: `App.tsx`, where the declaration lives beside the thing it is about rather than in a
#: checker. Either dash spelling, because a session writing this line will reach for both.
_OFF_RENDER_RE = re.compile(r"^#\s*OFF_RENDER\s+#?(\S+)\s*[—-]\s*(.+)$")


def _route_names() -> Dict[str, str]:
    """Every name a manifest line could legitimately use for a route -> that route's path.

    A route's SLUG (`/review` -> `review`) and its LABEL lowercased (`Home` -> `/`), both
    read out of the ROUTES table. The label is what makes `/` reachable by name at all: it
    has no slug, and `home` is what the render is called.
    """
    if not exists(APP_TSX):
        return {}
    names: Dict[str, str] = {}
    for path, label in re.findall(
        r"path:\s*'([^']*)'\s*,\s*label:\s*'([^']*)'", read(APP_TSX)
    ):
        slug = path.strip("/")
        if slug:
            names[slug] = path or "/"
        names[label.lower()] = path or "/"
    return names


def _render_manifest_findings(
    entries: List[Tuple[int, str, str]], off_render: Dict[str, str]
) -> Tuple[List[Finding], Set[str]]:
    """A render's filename names the screen it renders, and every absence says why.

    **A WRONG IMAGE WITH A RIGHT FILENAME IS WORSE THAN A MISSING ONE, because it is
    quotable as verification.** `capture http://localhost:5173/#/` sat in this manifest:
    a session rendering `captures/ui/capture.png` to check the capture screen was looking
    at the HOME page, and `make screenshot` exited 0. Home took the root hash when the
    shell was rebuilt and the line's NAME was never moved with its URL.

    **Clause one: a manifest name that names a route must point at that route.** Matched
    against the route's slug or its lowercased label, both read from ROUTES. A name that
    matches neither is left alone on purpose — `pull-confirm` is a kit specimen rendered
    off `#/gallery`, which is a deliberate arrangement and not a mislabelled screen.

    **Clause two: a route with no render says so, by name, with a reason.** It does NOT
    demand a line per route, which would re-arm an opsec leak the owner closed by ruling:
    `#/inventory` was removed from this manifest on 2026-09-05 because it draws a pooled
    card's photograph on purpose, and `#/codes` is the code-card screen. `OFF_RENDER` is
    where that argument lives, so a THIRTEENTH route cannot arrive unrendered and unargued
    — which is how `captures/ui/inventory.png` came to sit in the main checkout dated
    2026-08-29 while `app/src/Inventory.tsx` had moved on 2026-09-11, with no manifest line
    that would ever refresh it.
    """
    findings: List[Finding] = []
    names = _route_names()
    routes = _routes_table() or {}
    rendered: Set[str] = set()

    if not names or not routes:
        findings.append(Finding(
            rel(APP_TSX),
            "the ROUTES table yields no route name this row can read, so no render's "
            "filename is reconciled against the screen it draws and no absence is argued.",
        ))
        return findings, rendered

    for number, name, url in entries:
        route = (urlparse(url).fragment or "/").rstrip("/") or "/"
        rendered.add(route)
        wanted = names.get(name.lower())
        if wanted is None or wanted == route:
            continue
        findings.append(Finding(
            f"{rel(VIEWS_MANIFEST)}:{number}",
            f"is named `{name}`, which is the screen at `#{wanted}`, and renders "
            f"`#{route}`.\n"
            f"  The render lands at captures/ui/{name}.png, so a session opening it to "
            f"check `#{wanted}` is looking at a different screen and `make screenshot` "
            f"exits 0 — a wrong image with a right filename, quotable as verification.\n"
            f"  Point the URL at `#{wanted}`, or rename the line after the screen it "
            f"actually draws.",
        ))

    for route in sorted(routes):
        key = route.rstrip("/") or "/"
        if key in rendered or key in off_render:
            continue
        findings.append(Finding(
            rel(VIEWS_MANIFEST),
            f"`#{key}` is a registered route with no render and no reason given.\n"
            f"  Add a line for it, or declare the absence: "
            f"`# OFF_RENDER #{key} — <why>`. Four routes are deliberately unrendered and "
            f"each says why; a fifth arriving silently is a screen nothing has ever drawn, "
            f"which is how an image of one goes three weeks stale with nothing to refresh "
            f"it.",
        ))

    for route, reason in sorted(off_render.items()):
        if route in rendered:
            findings.append(Finding(
                rel(VIEWS_MANIFEST),
                f"declares `#{route}` OFF_RENDER ({reason}) and also renders it. One of the "
                f"two is stale, and a declaration that outlives its reason is how the list "
                f"stops being read.",
            ))
        elif route.rstrip("/") not in {r.rstrip("/") or "/" for r in routes}:
            findings.append(Finding(
                rel(VIEWS_MANIFEST),
                f"declares `#{route}` OFF_RENDER and no such route is registered. The "
                f"screen went; the declaration exempts nothing.",
            ))
    return findings, rendered


# ------------------------------------------------------------ no mechanism on screen (D196)
#
# The owner's ruling, 2026-09-13: the front end has to be minimal and must never explain
# mechanism on screen. A person at the rig thinks in cards, boxes, runs, exports and
# listings — the operator's own words, all over `docs/DESIGN.md`'s Register section and
# CLAUDE.md's screen table — and never in the vocabulary of THIS REPOSITORY: a decision
# number is a fact about an argument this codebase settled, a file path is a fact about
# where bytes sit on this Mac, and "the resolver" or "the corpus" names an internal
# component rather than an outcome. None of the three belongs in a string a human reads.

USER_STRINGS_SCRIPT = ROOT / "scripts" / "user-strings.mjs"
APP_TS_COMPILER = ROOT / "app" / "node_modules" / "typescript" / "lib" / "typescript.js"

# THE ONE PLACE THIS LIST LIVES, so a session refining it edits one dictionary rather than
# a scattered set of regexes. Every entry is machinery this repo is BUILT FROM, and every
# comment says why it is not something an operator reaches for. `run`, `box`, `export`,
# `listing` and `TCGplayer` are deliberately NOT here — they are the operator's own words,
# the ones `docs/DESIGN.md`'s Register section and every screen in CLAUDE.md's table are
# written in, and banning them would be the opposite defect.
NO_MECHANISM_WORDS: Dict[str, str] = {
    "the pipeline": (
        "D1's two-phase batch process, end to end — an implementation the operator never "
        "chose and the outcome (a price, a queue entry) is what they read instead"
    ),
    "the resolver": (
        "pipeline/join.py's per-order picker (D174, D181) — an internal component name; "
        "the operator sees which copies fill an order, never which module chose them"
    ),
    "the model": (
        "the vision call identify/ makes (D2) — naming the model is naming a vendor and a "
        "technique, not a fact about a card"
    ),
    "the server sent": (
        "server.ts's own phrase for relaying a response — the operator reads a fact about "
        "their store, never about an HTTP exchange with it"
    ),
    "the join": (
        "pipeline/join.py's join step (D11) — a pipeline stage; the operator sees a listed "
        "card or a reason it queued, never the step that produced either"
    ),
    "the corpus": (
        "pipeline/corpus.py's one-file pricing store (D86) — a storage detail; the "
        "operator thinks in prices and holds, never in which file holds them"
    ),
    "the ledger": (
        "the code-card and order ledgers (D24, D63) as STORAGE — codes and orders are the "
        "operator's own words; that either is kept in one file called a ledger is not"
    ),
}

_NO_MECHANISM_RE = re.compile("|".join(re.escape(w) for w in NO_MECHANISM_WORDS), re.I)

# A repository path, never something a person types or reads off a download. Every
# top-level package `docs/map.py` maps, plus `scripts` (where this row itself lives): any
# of them followed by `/` is a filesystem fact about this checkout, not a sentence about a
# card. `docs/decisions/` is covered by the bare `docs` prefix, deliberately — a path INTO
# it is exactly the citation-by-path `cite-decisions-by-id-not-path` already warns against.
_REPO_TOP_DIRS = (
    "inventory", "runs", "captures", "harness", "docs", "app",
    "server", "pipeline", "store", "identify", "geometry", "codes", "cli", "scripts",
)
_REPO_PATH_RE = re.compile(r"\b(?:" + "|".join(_REPO_TOP_DIRS) + r")/[\w./<>-]+")

# A bare filename in a format only this repository's own store speaks. `.csv` is
# deliberately absent: `Pricing.tsx` links a real download by its own name — `import.csv`
# — and CLAUDE.md's own `emit` section names that file the same way, which is exactly the
# "a download's own name" exemption the row was asked to argue. `.sqlite`, `.jsonl` and a
# bare `.json` are never a download; they are always an internal store.
_REPO_EXT_RE = re.compile(r"\b[\w-]+\.(?:sqlite|jsonl|json)\b")

# `D134`, `C7`, `(D-<slug>)`. The bare numeric forms require the letter directly against a
# digit with a word boundary on both sides, so "3D" and "ID" cannot match — measured
# against every one of the ~2,700 strings this row currently extracts from app/src: zero
# false positives from this pattern on the tree as it stands.
_DECISION_CITE_RE = re.compile(r"\bD\d{1,4}\b|\bC\d{1,4}\b|\(D-[A-Za-z0-9][A-Za-z0-9-]*\)")

# A CLI INVOCATION, BACKTICKED OR BARE (D210's own finding). This row had no
# key for `Pricing.tsx:4468`'s "Run `pkmnscan rescue` to rebind it." — a backticked command
# is not a decision citation, not one of `_REPO_TOP_DIRS` followed by a slash, and not a
# `.json`/`.sqlite`/`.jsonl` filename, so it passed this row clean while naming this
# product's own CLI on screen. `pkmnscan` is the checkout's own name (CLAUDE.md's naming
# rule) and never a word an operator would use to describe what a press does; a subcommand
# beside it (`rescue`, `join`, `emit`, …) is exactly the mechanism this row exists to catch.
_CLI_INVOCATION_RE = re.compile(r"`?\bpkmnscan\b(?:\s+[\w.-]+)*`?", re.I)


def _run_user_strings(args: List[str]) -> Optional[List[Dict[str, object]]]:
    """Shell out to scripts/user-strings.mjs; None when the toolchain cannot run it.

    THE SAME SPLIT `scripts/screen-freshness.mjs` ALREADY KEEPS: the AST walk lives in
    node, over the compiler this app itself builds with (`app/node_modules/typescript`),
    because a hand-rolled matcher would be a second, worse opinion about what a JSX text
    node is. Everything that decides whether an extracted string is ALLOWED — the word
    list above — stays in this file, in one place, because that is the part a session
    actually edits.
    """
    # APP_TS_COMPILER is `app/node_modules/typescript/...` — a real toolchain dependency,
    # never a tracked path, so it can never be "in the index" and `exists()`'s staged-mode
    # branch (D16's own rule: read the commit, not the worktree) would report it missing on
    # every `--staged` run regardless of whether `npm install` had been run. Ask the
    # filesystem directly, the way `make lint` and `make typecheck` do when they need the
    # same install. USER_STRINGS_SCRIPT is real repo content, so it keeps the staged check.
    node = shutil.which("node")
    if node is None or not APP_TS_COMPILER.exists() or not exists(USER_STRINGS_SCRIPT):
        return None
    try:
        done = subprocess.run(
            [node, str(USER_STRINGS_SCRIPT), *args],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    try:
        parsed = json.loads(done.stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, list) else None


# THE ONE SCREEN EXEMPTED FROM THIS ROW, BY NAME, AND THE ARGUMENT FOR IT — a set of exactly
# one entry so that widening it is a diff someone has to write and someone else has to read.
# `#/gallery` is the kit's own component sheet: off the nav by declaration (`OFF_NAV` in
# `App.tsx`), reached from the palette only, and rendered to nobody the product is FOR — not
# the owner working the rig, not the Fulfiller. Its job is to document the kit to whoever
# builds the next screen, so naming `docs/specs/logo.md` (the mark's own source) or a
# `banchi emit runs/2026-09-02-box6-01` example (illustrating what a run log line looks like)
# IS its content, not a leak of one — the coordinator's ruling, 2026-09-13.
#
# `Fulfillment.tsx` and `PullConfirm.tsx` are deliberately NOT here and never will be by the
# same argument in reverse: a real person — the Fulfiller — reads those screens while working,
# so a decision citation or a repository path on either of them is exactly the defect this row
# exists to catch. `check_no_mechanism_exempt_is_pinned` below is what keeps a second entry
# from being added quietly.
NO_MECHANISM_EXEMPT_FILES = frozenset({"Gallery.tsx"})


def _no_mechanism_exempt(where_file: str) -> bool:
    """Matched by basename, not by full path — this file is a leaf name (`Gallery.tsx`),
    never a directory, so a rename under a different parent still resolves correctly and a
    self-test fixture rooted anywhere still matches the same way the real `app/src` tree
    does."""
    return Path(where_file).name in NO_MECHANISM_EXEMPT_FILES


def _no_mechanism_findings(strings: List[Dict[str, object]]) -> List[Finding]:
    findings: List[Finding] = []
    for item in strings:
        file = str(item["file"])
        if _no_mechanism_exempt(file):
            continue
        text = str(item["text"])
        where = f"{item['file']}:{item['line']}"
        shown = text if len(text) <= 100 else text[:97] + "..."
        code_hit = (
            _DECISION_CITE_RE.search(text)
            or _REPO_PATH_RE.search(text)
            or _REPO_EXT_RE.search(text)
            or _CLI_INVOCATION_RE.search(text)
        )
        if code_hit is not None:
            findings.append(
                Finding(
                    where,
                    f"names `{code_hit.group(0)}` where a person reads it: {shown!r}\n"
                    "  A decision citation or a repository path is a fact about this "
                    "codebase, never about a card, a box or an order — say the outcome "
                    "instead of the mechanism that produced it.",
                )
            )
            continue
        word_hit = _NO_MECHANISM_RE.search(text)
        if word_hit is not None:
            why = NO_MECHANISM_WORDS.get(word_hit.group(0).lower(), "")
            findings.append(
                Finding(
                    where,
                    f"says {word_hit.group(0)!r}: {shown!r}\n  {why}",
                )
            )
    return findings


def check_no_mechanism_on_screen(report: Report) -> None:
    """No user-visible string in app/src may name a decision, a repository path, or a
    pipeline-internal noun. See D196.

    THE EXTRACTION IS AN AST WALK, NOT A GREP OVER FILE TEXT — `scripts/user-strings.mjs`,
    over `app/node_modules/typescript`, the compiler this app itself builds with. A regex
    over raw source cannot tell a code COMMENT arguing about `D134` from a sentence a
    person reads; this reads the AST, where a comment is trivia and never becomes a
    `JsxText`, a tracked JSX attribute, or a `toast()` argument, so it cannot leak by
    construction — it was measured to leak zero comments across app/src's ~2,700 hits.

    WHAT IS EXTRACTED, and nothing else: JSX text nodes; string or template-literal values
    of the JSX attributes `title`, `aria-label`, `placeholder`, `label`, `alt` and `body`
    (the last for `EmptyState`'s own text prop, which is not one of the other five); a
    literal used directly as a JSX child expression through the shapes this tree actually
    builds one with — a ternary, `??`, `&&`, `+`, parentheses; and `title` / `body` /
    `action.label` passed to `toast()`. `console.*` arguments, `data-*` attributes, class
    names and import paths are never JSX text or a tracked attribute, so none of them can
    be reached by this walk at all — not filtered out, structurally absent.

    WHAT IS NOT: a string returned by an arbitrary helper and interpolated by reference —
    `{formatLabel(x)}` — because that needs data-flow tracing the AST alone does not carry.
    So the count this row prints is a FLOOR, the same word `docs/specs/corpus-pruning.md`
    already uses for its own undercount, and for the identical reason: what is missed
    understates the defect, never invents one.

    `Notice`'s own `code` prop is deliberately NOT extracted — CLAUDE.md's Register
    section says outright that "the pipeline's own string stays available on hover and in
    the run log", which is precisely what that prop is for. A session widening this row's
    attribute list to catch `code` too would be re-litigating that sentence, not fixing a
    gap.

    ONE SCREEN IS EXEMPTED BY NAME: `Gallery.tsx`, see `NO_MECHANISM_EXEMPT_FILES` right
    above `_no_mechanism_findings`. `#/gallery` is the kit's own component sheet — off the
    nav (`OFF_NAV`), reached from the palette only, rendered to nobody the product is FOR —
    so naming `docs/specs/logo.md` or a `banchi emit runs/…` example there is the sheet's
    content, not a leak of one. `Fulfillment.tsx` and `PullConfirm.tsx` stay unexempted: a
    real person reads those while working. The exempt set is pinned at exactly one entry by
    a literal equality assertion in `--self-test`, so a second name added there fails
    `make audit-self-test` until the assertion is deliberately updated to match.

    SEVERITY IS MECHANICAL, ON PURPOSE, matching every other row this file uses the word
    for: a decision citation, a repository path or one of `NO_MECHANISM_WORDS` either is or
    is not in an extracted string, which is D16's test — nothing here is asking a question
    a person has to judge.

    THIS ROW IS EXPECTED RED TODAY. Three sessions are editing `app/src/*.tsx` copy
    concurrently with the one that built this row, clearing the hits it finds; the count in
    its summary is a snapshot of the tree at the moment `make docs-audit` ran, not a claim
    that the front end has already been made to comply.

    Toolchain-missing is reported as a finding rather than a silent `scanned=0`, because
    `make check` already needs `node` and `app/node_modules/typescript` for `lint` and
    `typecheck` — a machine that cannot run those cannot honestly claim this row passed
    either.
    """
    strings = _run_user_strings([])
    if strings is None:
        report.add(
            "no mechanism on screen", MECHANICAL,
            [
                Finding(
                    rel(USER_STRINGS_SCRIPT),
                    "could not run — `node` or `app/node_modules/typescript` is missing. "
                    "`npm install` in app/ first; this row needs the same toolchain "
                    "`make lint` and `make typecheck` already require.",
                )
            ],
            "toolchain unavailable, so nothing was read", scanned=0,
        )
        return
    findings = _no_mechanism_findings(strings)
    report.add(
        "no mechanism on screen", MECHANICAL, findings,
        (
            f"{len(findings)} of {len(strings)} visible strings name a decision, a "
            "repository path, or pipeline machinery"
        ) if findings else f"{len(strings)} visible strings carry none of it",
        scanned=len(strings),
    )




def check_views_opsec(report: Report) -> None:
    """D24's standing sentence: scripts/views.txt may never name a URL whose render can
    contain a code card. Enforcement existed for the images (captures/ is gitignored, both
    hooks block a stray image) and never for the rule, so a URL whose render IS the leak
    could sit in the manifest with every check green.

    The premise is the registry's, not this check's: a game with `located: False` is a
    pooled capture — a code card, a bearer instrument once photographed — and its photo
    lands in the same store, behind the same `GET /photo/<box>/<index>`, as every located
    card (D14: one rig, one photo storage). While such a game exists, any screen that draws
    stored photos can draw a live code, and `make screenshot` would write it into
    captures/ui/ — a screenshot, which CLAUDE.md's opsec rule names alongside listings and
    commits. No pooled game in the registry, no rule to enforce; the row says so and stops.

    **Two rows, split exactly on D16's line.**

    The MECHANICAL row is the part with no judgment in it: a manifest line that
    scripts/screenshot.sh could not render, a hash route that resolves to no entry in
    app/src/App.tsx's ROUTES (the 7b lesson — sixteen confident measurements of an
    unregistered route — as a commit gate), and a URL that addresses the photo service
    itself, whose render is the raw stored bytes under every possible runtime state. Each
    is provably wrong on the committed tree alone.

    The ADVISORY row is the exposure the script can see but not judge: a route whose
    component subtree reaches the photo service (`_photo_reach`). Whether that render
    actually contains a code card depends on runtime state this script cannot have — is
    the capture server up, does the store hold a pooled capture, does the screen's own
    logic filter pooled cards out. Fulfillment filters and PROVES it, in a Playwright
    assertion; this script cannot read React control flow, so treating reach as guilt
    would block the manifest's whole reason to exist over four screens the owner put there
    deliberately. A false positive that blocks is worse than one that prints (D16), so the
    exposure prints, names the files that carry the reach, and names the three discharges:
    drop the line, prove the screen pooled-free the way app/tests/fulfillment.spec.ts
    does, or take the render-conditions question back to D24's owner.
    """
    if not exists(VIEWS_MANIFEST):
        report.add("views opsec", MECHANICAL,
                   [Finding(rel(VIEWS_MANIFEST), "does not exist, and `make screenshot` reads it.")])
        return

    games, _ = game_entries()
    pooled = sorted(
        str(entry.get("key"))
        for entry in (games.get("GAMES") or ())
        if isinstance(entry, dict) and entry.get("located") is False
    )

    routes = _routes_table()
    blocking: List[Finding] = []
    exposure: List[Finding] = []
    if routes is None:
        blocking.append(
            Finding(
                rel(APP_TSX),
                "the ROUTES table could not be read, so no views.txt URL can be checked "
                "against the screens it names. If the table moved or changed shape, this "
                "check's reader has to move with it.",
            )
        )

    manifest_text = read(VIEWS_MANIFEST)
    entries: List[Tuple[int, str, str]] = []
    off_render: Dict[str, str] = {}
    for number, line in enumerate(manifest_text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            declared = _OFF_RENDER_RE.match(stripped)
            if declared is not None:
                off_render[declared.group(1).rstrip("/") or "/"] = declared.group(2).strip()
            continue
        parts = stripped.split()
        if len(parts) < 2:
            blocking.append(
                Finding(
                    f"{rel(VIEWS_MANIFEST)}:{number}",
                    "names a view with no URL — scripts/screenshot.sh refuses this line too.",
                )
            )
            continue
        # THE THIRD FIELD IS NOT OPTIONAL, as of 2026-09-12. This file's own header says a
        # line MAY name the elements its render must prove it drew, and `screenshot.mjs`
        # defaults `require` to the empty string — so a ninth view added with a URL and no
        # selectors silently gets the pre-2026-09-07 behaviour back: a valid,
        # plausible-looking PNG that proves nothing, and `make screenshot` exits 0. A
        # capability whose activation is optional is a guard the next line opts out of with
        # no diff anybody reads. All eight lines already carry one.
        if len(parts) < 3 or not [s for s in parts[2].split(",") if s.strip()]:
            blocking.append(
                Finding(
                    f"{rel(VIEWS_MANIFEST)}:{number}",
                    f"`{parts[0]}` names no element its render must prove it drew.\n"
                    "  Without a third field `scripts/screenshot.mjs` asserts nothing about "
                    "the page: it writes a valid PNG and exits 0, which is exactly the "
                    "defect the column was added to end on 2026-09-07 — a session looked at "
                    "an incomplete render and called the screen fine.\n"
                    "  Name a screen root and its title at minimum, and read this file's "
                    "header first: a selector has to hold in every state (server up, down, "
                    "and up over an empty store).",
                )
            )
            continue
        entries.append((number, parts[0], parts[1]))

    if not entries:
        blocking.append(
            Finding(
                rel(VIEWS_MANIFEST),
                "yields no view this row can parse, and `make screenshot` reads it.\n"
                "  A manifest nothing can read renders nothing and this row would print ok "
                "over it — say so instead.",
            )
        )

    from urllib.parse import urlsplit

    checked = 0
    for number, name, url in entries:
        where = f"{rel(VIEWS_MANIFEST)}:{number}"
        parts = urlsplit(url)
        if pooled and "/photo/" in f"{parts.path}#{parts.fragment}":
            blocking.append(
                Finding(
                    where,
                    f"`{name}` addresses the photo service directly. GET /photo/<box>/"
                    f"<index> serves raw stored bytes, the store accepts pooled captures "
                    f"({', '.join(pooled)}), and a pooled capture's photo is a live code "
                    f"(D24). There is no runtime state under which this render belongs in "
                    f"the screenshot manifest.",
                )
            )
            continue
        if parts.netloc not in APP_ORIGINS:
            exposure.append(
                Finding(
                    where,
                    f"`{name}` is not the Vite app ({' or '.join(sorted(APP_ORIGINS))}), "
                    f"so this check cannot see what it renders. If its render can contain "
                    f"a stored photo, D24's sentence applies to it all the same.",
                )
            )
            continue
        if routes is None:
            continue
        route = (parts.fragment or "/").rstrip("/") or "/"
        if route not in routes:
            blocking.append(
                Finding(
                    where,
                    f"`{name}` names `#{parts.fragment or '/'}`, which resolves to no "
                    f"entry in app/src/App.tsx's ROUTES — the render would be the "
                    f"no-such-view door wearing this view's filename. 7b shipped exactly "
                    f"this shape once; a screen must be routed before it is rendered.",
                )
            )
            continue
        checked += 1
        if not pooled:
            continue
        component = routes[route]
        reach = _photo_reach(component) if component is not None else []
        if not reach:
            continue
        evidence = _pooled_exclusion_evidence(route)
        if evidence is not None:
            continue
        exposure.append(
            Finding(
                where,
                f"`{name}` renders `#{route}`, whose screen can draw stored capture "
                f"photos ({', '.join(reach)}), and the shared store accepts pooled "
                f"captures ({', '.join(pooled)}) whose photo is a live code (D24). A "
                f"render taken while the capture server is up over a store holding one "
                f"writes a bearer instrument into captures/ui/. Not blocking: whether "
                f"that state holds at render time is runtime fact this script cannot "
                f"see. Discharge: drop this line, or prove the screen pooled-free in "
                f"app/tests/{route.strip('/') or 'capture'}.spec.ts the way the "
                f"Fulfillment view does — a `test(...)` whose TITLE names `pooled` and "
                f"claims `never`, because a title is the claim a spec is answerable for "
                f"and a body match reads the same words out of a proof of the opposite — "
                f"or take the render-conditions ruling to D24's owner.",
            )
        )

    render_findings, rendered_routes = _render_manifest_findings(entries, off_render)
    blocking.extend(render_findings)

    report.add(
        "views opsec",
        MECHANICAL,
        blocking,
        f"{checked} of {len(entries)} views resolve in ROUTES, none address the photo "
        f"service; {len(rendered_routes)} routes rendered, {len(off_render)} declared off",
        scanned=len(entries),
    )
    report.add(
        "views exposure",
        ADVISORY,
        exposure,
        ("no pooled game in the registry — a stored photo is not a bearer instrument today"
         if not pooled
         else "no manifest view can draw a stored photo"),
        scanned=len(entries),
    )


# --------------------------------------------------------------- doc hygiene


# An editor's instruction, written to a session and committed as prose. The real one read
# "Leave lines 37-38 exactly as they are. Insert a blank line and this blockquote after line
# 38" — and the edit that pasted it DELETED the sentence it was meant to preserve, leaving a
# decapitated clause behind. Anchored at the start of a line and requiring a literal line
# NUMBER, because "insert a blank line" is ordinary English and "insert ... after line 38" is
# not: prose about a document does not cite the document's own line numbers.
_EDITOR_INSTRUCTION = re.compile(
    r"^\s*(?:Leave|Insert|Replace|Delete|Add|Append|Keep)\b[^.]{0,80}\b(?:line|lines)\s+\d+",
    re.I,
)

_DOC_LINE_CITATION = re.compile(
    r"`([A-Za-z0-9_./-]+\.(?:py|ts|tsx|css|json|sh|txt|md)):(\d+)"
)


def check_doc_hygiene(report: Report, docs: List[Path]) -> None:
    """Three ways a markdown file is malformed as a DOCUMENT, independent of what it claims.

    Every other row here reads a doc's assertions and checks them against the code. This one
    reads the file as a file, and it exists because the 2026-08-30 prose sweep found two
    defects that every row was structurally unable to see: no assertion was wrong, so nothing
    asked.

    THE THREE, all decidable on the committed tree alone:

      an editor's instruction committed as prose  `docs/specs/capture-server.md` carried
          "Leave lines 37-38 exactly as they are. Insert ... after line 38" in the middle of
          a paragraph, from 2026-08-22. The paste that put it there deleted the line it was
          preserving, so the paragraph also lost "Do not add a harness test for the server in
          this plan, and do not register" and ended mid-clause. Green for eight days.

      two level-1 headings  `docs/specs/ui-research.md` was two documents in one file, the
          second titled "PKMNSCAN UI: final design recommendation". A reader's table of
          contents, this project's own heading parsers, and the status line that governs a
          file all assume one title.

      a line citation past the end of its file  `ReviewQueue.css:47` outliving the line it
          named. The `paths` row proves the FILE resolves and stops there, so the number is
          unchecked; this catches only the provable half, where the file is shorter than the
          number. A citation pointing at the wrong line of a long-enough file is invisible
          here and is `docs/DEBTS.md`'s to carry.

    ADVISORY, and the severity is the argument. Each condition is provably true of the tree,
    which is D16's test for a blocking row — but "true" and "wrong" part company on the second
    one: a file that deliberately carries two titles is a judgement, not a defect, and a
    blocking row would settle it by fiat. The first condition alone would qualify to block and
    is not split out, because a row that fires once every eight days does not need two
    severities and `make check` puts an advisory in front of a person anyway. **What would
    earn it a promotion: a second instance of the instruction case reaching main.**

    Fenced blocks are skipped for the heading and instruction conditions — a `#` inside one is
    a shell comment and prose inside one is a quotation. The audit's own convention of quoting
    verbatim doc text in blockquotes rather than fences (`docs/specs/audit-retirement.md` §0)
    is what makes that safe.
    """
    findings: List[Finding] = []
    for doc in docs:
        titles = 0
        fenced = False
        for number, line in enumerate(read(doc).splitlines(), start=1):
            if line.startswith("```"):
                fenced = not fenced
                continue
            if fenced:
                continue
            if line.startswith("# "):
                titles += 1
                if titles == 2:
                    findings.append(
                        Finding(
                            f"{rel(doc)}:{number}",
                            "a second level-1 heading — one file, two document titles. "
                            "Demote it, or split the file.",
                        )
                    )
            if _EDITOR_INSTRUCTION.match(line):
                findings.append(
                    Finding(
                        f"{rel(doc)}:{number}",
                        "reads as an instruction to an editor, committed as prose: "
                        f"{line.strip()[:70]!r}. Check what it replaced.",
                    )
                )
            for match in _DOC_LINE_CITATION.finditer(line):
                target = ROOT / match.group(1)
                if not target.is_file():
                    continue
                # A LINE CITATION OF `docs/DECISIONS.md` MEANT THE CORPUS, and that file is a
                # 38-line stub since the split. Measured against the stub, eight true
                # citations written before the split read as pointing past the end — D149's
                # four among them, landed an hour earlier. The author meant the entries, so
                # the entries are what the number is checked against. Same ruling as the
                # relative-path case in `resolve_candidate`, and for the same reason: the
                # entries' bytes are unchanged by design, so the alternative is editing prose
                # inside a change whose whole claim is that it edited none.
                #
                # WHAT THIS RESTORES IS EXACTLY WHAT EXISTED BEFORE — this row only ever
                # proved the file was long enough, never that the line still says what the
                # citation claims. A number drifting under an edit was invisible here before
                # the split and is invisible now; docs/DEBTS.md carries that half.
                if match.group(1) == "docs/DECISIONS.md":
                    total = len(decisions_text().splitlines())
                    if total and int(match.group(2)) <= total:
                        continue
                total = len(target.read_text(errors="replace").splitlines())
                if int(match.group(2)) > total:
                    findings.append(
                        Finding(
                            f"{rel(doc)}:{number}",
                            f"cites {match.group(1)}:{match.group(2)}, "
                            f"but that file has {total} lines.",
                        )
                    )
    report.add(
        "doc hygiene",
        ADVISORY,
        findings,
        f"{len(docs)} markdown files well-formed as documents",
        scanned=len(docs),
    )



# ------------------------------------------------------- route rosters in the specs

# A `//` or `/* */` comment, so a route named in PROSE is not read as a route the file
# pins. Both spec files below discuss routes they deliberately do not walk — nav.spec.ts
# reasons about `#/fulfillment` at length and asserts nothing on it — and counting those
# would fire this check at a file that is behaving.
TS_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)

# `ROUTE-ROSTER all` or `ROUTE-ROSTER hotkey`, in a comment directly above the literal it
# governs. A marker rather than a filename list inside this script: the spec that pins the
# routes is the file that has to say so, and a registry here would be a second list to keep
# in step with the first — which is the whole defect this check exists for, relocated.
ROSTER_MARK = re.compile(r"ROUTE-ROSTER\s+(all|hotkey)\b")

# `#/`, `#/runs`, and the `/#/runs` form `page.goto` takes. Normalised to the first.
ROUTE_HASH = re.compile(r"'/?(#/[a-z-]*)'")

# How many pinned route hashes make a file a roster. Two is a spec that opens on its own
# screen and one other; three is a list of screens somebody typed out, and a list of
# screens somebody typed out is the thing that goes stale.
ROSTER_FLOOR = 3


def _strip_ts_comments(text: str) -> str:
    return TS_COMMENT.sub(" ", text)


def _balanced(text: str, start: int) -> str:
    """The literal beginning at `start`, to its matching bracket. '' if unbalanced.

    Bracket-matched rather than regexed to the next `]`: `VIEW` below is an object of
    objects in every version of this file that has more than one shape, and a non-greedy
    match to the first closer would silently read half a roster and pass on the half.
    """
    pairs = {"[": "]", "{": "}"}
    opener = text[start]
    closer = pairs.get(opener)
    if closer is None:
        return ""
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def app_routes() -> Tuple[List[Tuple[str, str, bool]], List[str], List[Finding]]:
    """`App.tsx`'s ROUTES table as (path, group, has hotkey), plus GROUP_ORDER.

    Read from the source rather than from a browser, because this check runs at a commit
    and `make design-check` starts a browser (docs/GATES.md's contract keeps that off the
    hook path). The table is the register either way — `App.tsx` routes from it, renders
    its nav from it and derives its Cmd-arrow ring from it, which is the property that
    makes reconciling a test's hand-typed copy against it meaningful.
    """
    findings: List[Finding] = []
    if not exists(APP_TSX):
        return [], [], [Finding(rel(APP_TSX), "is missing, so no route roster can be checked.")]

    source = _strip_ts_comments(read(APP_TSX))

    anchor = re.search(r"const\s+ROUTES\s*:[^=]*=\s*", source)
    if anchor is None:
        return [], [], [
            Finding(
                rel(APP_TSX),
                "defines no `const ROUTES` this reader can find, so the specs below are\n"
                "reconciled against nothing. Reconcile this extractor with the table.",
            )
        ]
    table = _balanced(source, anchor.end())
    if not table:
        return [], [], [Finding(rel(APP_TSX), "`const ROUTES` does not close — unbalanced brackets?")]

    rows: List[Tuple[str, str, bool]] = []
    index = 0
    while True:
        opening = table.find("{", index)
        if opening == -1:
            break
        row = _balanced(table, opening)
        if not row:
            break
        index = opening + len(row)
        path = re.search(r"path:\s*'([^']*)'", row)
        group = re.search(r"group:\s*'([^']*)'", row)
        if path is None or group is None:
            findings.append(
                Finding(
                    rel(APP_TSX),
                    f"a ROUTES row carries no {'path' if path is None else 'group'}: {row[:60]}…",
                )
            )
            continue
        rows.append((path.group(1), group.group(1), "hotkey:" in row))

    # THE NAV'S ORDER, UNDER EITHER OF THE TWO NAMES IT HAS HAD. It was `GROUP_ORDER`, a
    # list of bare strings; the Banchi shell draws from `GROUPS`, a list of `{id, label}`
    # objects, because a group now carries a heading as well as an order. Reading only the
    # old name did not fail loudly — it returned NO groups, which made `expected_rosters()`
    # hand back an empty dict, which made the `route rosters` row skip every roster a spec
    # had pinned. A check that stops checking is worse than one that fails, so both spellings
    # are read and the absence of both is still a finding.
    groups: List[str] = []
    order = re.search(r"const\s+GROUP_ORDER\s*:[^=]*=\s*", source)
    if order is not None:
        groups = re.findall(r"'([^']*)'", _balanced(source, order.end()))
    if not groups:
        modern = re.search(r"const\s+GROUPS\s*:[^=]*=\s*", source)
        if modern is not None:
            # `{ id: 'work', label: 'Workflow' }` — the id is the group, the label is chrome.
            groups = re.findall(r"id:\s*'([^']*)'", _balanced(source, modern.end()))
    if not groups:
        findings.append(
            Finding(rel(APP_TSX), "defines no readable `GROUP_ORDER` or `GROUPS`, so a nav ORDER cannot be derived.")
        )
    # A group the shell deliberately keeps out of the nav list is still a drawn group as far
    # as this row is concerned: its routes are reached from the sidebar foot or the command
    # palette. `App.tsx:OFF_NAV` is where that intent is declared, so it is read rather than
    # guessed. Absent, nothing is added and the row behaves exactly as it did.
    off = re.search(r"const\s+OFF_NAV\s*:[^=]*=\s*", source)
    if off is not None:
        groups = list(groups) + [g for g in re.findall(r"'([^']*)'", _balanced(source, off.end())) if g not in groups]
    return rows, groups, findings


def expected_rosters() -> Tuple[Dict[str, List[str]], List[Finding]]:
    """The two rosters a spec may pin, in the order the nav draws them.

    `all` is every registered route; `hotkey` is the Cmd-arrow ring, which `App.tsx`
    itself derives as `hotkey !== undefined` over GROUP_ORDER-then-table. Both are built
    here the same way the shell builds them, so a re-ordered table moves both together.
    """
    rows, groups, findings = app_routes()
    if not rows or not groups:
        return {}, findings
    drawn = [row for group in groups for row in rows if row[1] == group]
    missing = [row[0] for row in rows if row[1] not in groups]
    if missing:
        findings.append(
            Finding(
                rel(APP_TSX),
                "these routes carry a group GROUP_ORDER does not draw, so the nav renders "
                f"no link for them: {', '.join(missing)}",
            )
        )
    return (
        {
            "all": [f"#{path}" for path, _, _ in drawn],
            "hotkey": [f"#{path}" for path, _, keyed in drawn if keyed],
        },
        findings,
    )


def check_route_rosters(report: Report) -> None:
    """A hand-typed list of routes in a spec, against `App.tsx`'s own table.

    **The failure this exists for, in full, because it happened twice inside two days.**
    `app/tests/cursor.spec.ts` swept "every route" off seven hashes somebody typed out. D69
    added `#/orders` and `#/shipping`; D70 added `#/codes`. None of the three was added to
    that list, so three screens were asserted by nothing — and the spec's own header spends
    a paragraph explaining that a pinned roster is exactly the defect it must not have. The
    list was four lines under the warning. `make design-check` stayed green throughout,
    because a roster that is missing a route does not fail: it simply walks the routes it
    has. `app/tests/nav.spec.ts` pinned the same ring and did go red on D70 — but only
    because its "never a wrap" case happened to step off the end of the list it knew about,
    which is luck rather than coverage.

    **So the guard is at the commit and not in a browser.** `docs/GATES.md`'s contract keeps
    Playwright off the hook path, and this needs no browser: `App.tsx` is the register — it
    routes from ROUTES, renders the nav from ROUTES, and derives the Cmd-arrow ring from
    ROUTES — so a text reconciliation against it answers the question a browser would.

    **Declared, not sniffed.** A spec that pins three or more routes has to say WHICH roster
    it is pinning, in a `ROUTE-ROSTER all` or `ROUTE-ROSTER hotkey` comment above the
    literal, and the literal is then checked in order against the table. Sniffing every
    array of hashes would be the check inventing an intent the file never stated: `#/gallery`
    appears in nav.spec.ts as a route the ring deliberately CANNOT reach, and a check that
    read it as a missing ring member would be wrong in the direction that gets a guard
    disabled. Three is the floor because two is a spec that opens on its own screen and one
    other, and three is a list somebody typed.

    **A spec that derives its roster trips nothing, which is the point.** `cursor.spec.ts`
    now reads the nav strip at run time, so it pins one hash — the way in — and this check
    has nothing to reconcile there. That is the better fix and this row does not replace it;
    it covers the specs where a pinned list is deliberate, and it catches a pinned list
    creeping back into one where it is not.
    """
    expected, findings = expected_rosters()
    specs = sorted(glob_files(APP_TESTS, "*.spec.ts"), key=rel)

    marked = 0
    for spec in specs:
        code = _strip_ts_comments(read(spec))
        pinned = {match for match in ROUTE_HASH.findall(code)}
        text = read(spec)
        marks = list(ROSTER_MARK.finditer(text))

        if not marks:
            if len(pinned) >= ROSTER_FLOOR:
                findings.append(
                    Finding(
                        rel(spec),
                        f"pins {len(pinned)} routes ({', '.join(sorted(pinned))}) and declares no\n"
                        "roster. A list of screens typed by hand goes stale silently — the route\n"
                        "added next month is simply not in it and nothing goes red. Either derive\n"
                        "the list at run time (see cursor.spec.ts), or put `ROUTE-ROSTER all` or\n"
                        "`ROUTE-ROSTER hotkey` in a comment above the literal so this row can\n"
                        "check it against App.tsx's ROUTES table.",
                    )
                )
            continue

        for mark in marks:
            marked += 1
            kind = mark.group(1)
            line = text.count("\n", 0, mark.start()) + 1
            where = f"{rel(spec)}:{line}"
            if not expected:
                continue
            # FROM THE `=`, NOT FROM THE MARKER. `const VIEW: Record<(typeof RING)[number],
            # string> = {` puts a `[` in the TYPE, and a reader that took the first bracket
            # after the comment read `[number]` and reported a roster with no routes in it —
            # a failure that says "you pinned nothing", which is not what is wrong and is not
            # a message anybody could act on. The assignment is the only `=` between a marker
            # and the literal it governs.
            assign = text.find("=", mark.end())
            opening = (
                min(
                    (found for found in (text.find(bracket, assign) for bracket in "[{") if found != -1),
                    default=-1,
                )
                if assign != -1
                else -1
            )
            literal = _balanced(text, opening) if opening != -1 else ""
            if not literal:
                findings.append(
                    Finding(where, "declares a roster with no array or object literal under it.")
                )
                continue
            found = ROUTE_HASH.findall(_strip_ts_comments(literal))
            want = expected[kind]
            if found != want:
                absent = [route for route in want if route not in found]
                extra = [route for route in found if route not in want]
                detail = []
                if absent:
                    detail.append(f"missing: {', '.join(absent)}")
                if extra:
                    detail.append(f"not a `{kind}` route: {', '.join(extra)}")
                if not detail:
                    detail.append("same routes, wrong order")
                findings.append(
                    Finding(
                        where,
                        f"declares `ROUTE-ROSTER {kind}` and does not match App.tsx's table.\n"
                        + "\n".join(detail)
                        + f"\nwant: {', '.join(want)}"
                        + f"\nhave: {', '.join(found)}",
                    )
                )

    report.add(
        "route rosters",
        MECHANICAL,
        findings,
        f"{marked} declared roster{'' if marked == 1 else 's'} against "
        f"{len(expected.get('all', []))} registered routes",
        scanned=marked,
    )

# ------------------------------------------------------ deletions a decision records
#
# A DELETION IS THE ONE KIND OF RULING A MERGE CAN UNDO WITHOUT ANYBODY WRITING A LINE. D119
# deleted `LocationCard` on 2026-09-07 (PR #218, `4bf5a44`) and the very next PR to land put it
# back: `9439765` (PR #221, a cap-wording change) was committed from a tree that still held the
# pre-deletion copy of every file #218 had touched — the component, its stylesheet, the specs
# that asserted its absence and the map rows that recorded it — and the merge carried all of it
# onto main in one commit whose message was about something else. Every guard the deletion had
# was IN the files that came back, so every guard came back with the thing it guarded against,
# and `make check` was green on both sides. Three days later D132's session found the component,
# read the owner's screenshot of it as evidence they wanted it, and wrote that down.
#
# So the guard lives HERE, in a file no screen change touches, and it is the smallest possible
# claim: a decision that records a symbol as deleted is contradicted by that symbol existing
# under app/src. The table is hand-written on purpose — reading DECISIONS.md for the word
# "deleted" would fire on every entry that deletes a sentence — and adding a row to it is how a
# session says a deletion is meant to stay one. A symbol that is meant to come back is removed
# from the table in the same commit that restores it, with the entry amended to say so.

# THE SCAN ROOTS. `app/src` alone until 2026-09-12, which is why the row printed `ok` over
# a resurrection in the OTHER language for a quarter: four of this quarter's five recorded
# deletions took code out of `server/`, `cli/` and `harness/`, and the scan could not look
# at any of them. A deletion is not an app-only kind of ruling.
DELETION_ROOTS: Tuple[str, ...] = (
    "app/src", "server", "store", "pipeline", "cli", "harness",
)
DELETION_SUFFIXES: Tuple[str, ...] = (".ts", ".tsx", ".css", ".py")

# NAMES THAT CAME BACK ON PURPOSE, AND MAY NOT BE NEEDLES. Recorded here rather than left
# out silently, because "not in the table" and "deliberately not in the table" are the same
# absence to a reader, and the next session to widen this row would add them straight back.
#
#   `do_order_fill`, `POST /orders/fill`   D96 deleted D90's envelope fill; D113 REBUILT a
#       route and a handler under both names for a different job — closing copies of a line
#       with no card behind them. Both exist today (server/capture_server.py, app/src/
#       server.ts, app/src/types.ts) and both are correct. A name is not a capability.
#   D110's three dark-only hover overrides   `.bn-nav-link`, `.capture-row` and
#       `.capture-opt` are LIVE classes; what D110 deleted is a declaration inside a
#       `[data-theme='dark']` block. A substring needle for that is either the class name —
#       red on every run — or a string that appears nowhere, which is a needle that can
#       never fire, i.e. the vacuous green this row is about. It wants a CSS-structural
#       reader, not this one.

RECORDED_DELETIONS: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    # (decision, what it deleted, the strings whose presence in the scanned code contradicts it)
    ("D119", "the `#/inventory` location card", ("LocationCard", "inventory-location")),
    ("D96", "D90's envelope fill — the walk, its banner and its harness case",
     ("orderWalk", "OrderWalkBanner", "check_order_fill")),
    ("D132", "`PositionLabel`'s `indexNote`", ("indexNote",)),
    ("D155", "the segment reader that computed edges from card counts", ("lensOf",)),
    # `cadence.ts` is the needle that keeps the prose classifier LIVE: it appears today in
    # exactly one place, a block comment in `app/src/motion.ts` narrating the retirement, so
    # every run exercises the comment/code split rather than leaving it to the self-test
    # alone. A classifier nothing routes through is the vacuous green one register down.
    ("D144", "the beat-locked cadence trigger, its module and its period pin",
     ("cadenceTrigger", "CadenceMachine", "DEFAULT_CADENCE", "periodPin", "pinPeriod",
      "cadence.ts")),
)


def _prose_blanked(path: Path, text: str) -> str:
    """`text` with comments — and, in Python, docstrings — replaced by spaces.

    OFFSETS AND LINE NUMBERS SURVIVE, so a hit found here reports the line it is really on.

    WHY THIS EXISTS: `server/capture_server.py`'s docstring NARRATES one of these
    deletions — "`/orders/fill`, which D96 deleted rather than wired up" — and reading that
    as the symbol existing would make the row red for the prose that is doing its job.
    Prose about a deletion is the record of it; executable code is the contradiction.

    Python docstrings only, never every string literal. Blanking all of them would turn a
    real code hit like `if name == "orderWalk"` into prose, which is the wrong direction to
    be wrong in for a row whose whole subject is a resurrection.
    """
    out = list(text)

    def blank(start: int, end: int) -> None:
        for i in range(max(0, start), min(len(out), end)):
            if out[i] != "\n":
                out[i] = " "

    if path.suffix == ".py":
        try:
            for token in tokenize.generate_tokens(io.StringIO(text).readline):
                if token.type == tokenize.COMMENT:
                    blank(_offset(text, token.start), _offset(text, token.end))
        except (tokenize.TokenError, IndentationError, SyntaxError):
            pass  # fails open: an unparseable file is scanned raw
        try:
            tree = ast.parse(text)
        except SyntaxError:
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                for child in ast.iter_child_nodes(node):
                    if (
                        isinstance(child, ast.Expr)
                        and isinstance(child.value, ast.Constant)
                        and isinstance(child.value.value, str)
                    ):
                        blank(
                            _offset(text, (child.lineno, child.col_offset)),
                            _offset(text, (child.end_lineno or child.lineno,
                                           child.end_col_offset or 0)),
                        )
    else:
        for found in TS_COMMENT.finditer(text):
            blank(found.start(), found.end())
    return "".join(out)


def _offset(text: str, position: Tuple[int, int]) -> int:
    """(1-based line, 0-based column) -> character offset."""
    line, column = position
    offset = 0
    for _ in range(line - 1):
        found = text.find("\n", offset)
        if found == -1:
            return len(text)
        offset = found + 1
    return min(len(text), offset + column)


def check_recorded_deletions(report: Report) -> None:
    """A symbol a decision records as deleted does not exist in the code.

    MECHANICAL: the entry says the thing is gone, and a grep says whether it is. See the banner
    above for the merge that made this row necessary — and for why the guard cannot live in
    the files the deletion touched.

    **SIX ROOTS, NOT ONE.** The scan walked `app/src` and nothing else, so it could not see
    four of the five deletions recorded this quarter — `do_order_fill` and its dispatcher in
    `server/`, harness T7's `check_order_fill`, the cadence module's Python mirror. A row
    whose subject is "does this symbol exist" has to look everywhere the symbol could be.

    **PROSE IS NOT A RESURRECTION.** A hit inside a comment or a docstring is the deletion
    being narrated and is counted in the summary rather than raised: `capture_server.py`
    carries exactly such a sentence about D96. The count is printed so a needle that lives
    only in prose can be told from one with no hits at all — and it is deliberately NOT an
    advisory finding, because `exit 2` in this repo already stands permanently lit and one
    more standing question would teach the next reader to skip the code entirely.

    **ITS OWN DENOMINATORS ARE PUBLISHED.** The roster is hand-kept, so its size is the
    thing most likely to be wrong about this row, and a scan that enumerated zero roots or
    zero needles is a finding rather than an `ok` — the shape a bare `scanned` count cannot
    see, since the row would still have walked hundreds of files to compare nothing.
    """
    findings: List[Finding] = []
    needle_count = sum(len(needles) for _, _, needles in RECORDED_DELETIONS)

    roots = [ROOT / root for root in DELETION_ROOTS if exists(ROOT / root)]
    if not roots:
        findings.append(
            Finding(
                "scripts/docs-audit.py -> DELETION_ROOTS",
                f"names {len(DELETION_ROOTS)} roots and none of them is on disk, so this row "
                f"compared nothing. Re-point the list: a scan with no root reports no "
                f"resurrection however many there are.",
            )
        )
    if not needle_count:
        findings.append(
            Finding(
                "scripts/docs-audit.py -> RECORDED_DELETIONS",
                "holds no needle, so the row is watching nothing. An emptied roster and a "
                "tree with no resurrection in it print the same word otherwise.",
            )
        )

    paths = sorted({path for root in roots for path in _walk(root, DELETION_SUFFIXES)}, key=rel)
    narrated = 0
    for path in paths:
        text = read(path)
        code = None
        for decision, what, needles in RECORDED_DELETIONS:
            for needle in needles:
                if needle not in text:
                    continue
                if code is None:
                    code = _prose_blanked(path, text)
                if needle not in code:
                    narrated += 1
                    continue
                line = code.count("\n", 0, code.index(needle)) + 1
                findings.append(
                    Finding(
                        f"{rel(path)}:{line}",
                        f"names `{needle}`, and {decision} records {what} as deleted.\n"
                        "Either the deletion is being undone — amend the entry and remove the "
                        "row from RECORDED_DELETIONS in the same commit — or a merge has "
                        "carried the pre-deletion file back onto this branch, which is how it "
                        "happened the first time.",
                    )
                )

    report.add(
        "recorded deletions",
        MECHANICAL,
        findings,
        f"{len(RECORDED_DELETIONS)} recorded deletion{'' if len(RECORDED_DELETIONS) == 1 else 's'}, "
        f"{needle_count} needles over {len(roots)} roots and {len(paths)} files"
        + (f"; {narrated} narrated in prose" if narrated else ""),
        scanned=needle_count * len(roots),
    )


# ------------------------------------------------------------- the capture-port seal
#
# `app/src/server.ts` talks to a DIFFERENT ORIGIN from the one the page came off —
# `${location.protocol}//${location.hostname}:${CAPTURE_PORT}` — so a spec that stubs
# everything its own SCREEN asks for still leaks the shell's `GET /status`, which
# `App.tsx:useServerPresence` polls from outside every route boundary and which therefore
# belongs to no screen. Ten specs did, and two of them read boxes, inventory, runs and four
# real card photographs besides. In the main checkout that port is the owner's live capture
# server over their real store, kept alive at login by `make launch-agent`; in a worktree
# nothing answers and the shell draws a 44px banner that moves every geometry floor
# `make design-check` asserts. `app/tests/shell.ts` closes it.
#
# THIS ROW IS THE HALF THAT CANNOT BE CLOSED IN TYPESCRIPT. A missing call fails loudly on
# its own — the spec's reads reach the port and the roster in `sealEveryTest`'s `afterEach`
# names them. A call placed BELOW the file's own `test.beforeEach` does not: hooks run in
# declaration order, so the seal installs after the navigation it was meant to catch, those
# requests reach the real port UNRECORDED, and the assertion passes over an empty list. A
# guard that goes green for having watched nothing is the failure `check dispatch` two
# sections down exists about, in a second place.

SEAL_CALL = re.compile(r"\bsealEveryTest\s*\(")

# THE ANCHOR IS THE HOOK AND NOT `page.goto(`, and that distinction is the whole of what this
# row gets right. A spec's `open()` helper is DEFINED above the seal call and RUNS inside the
# test body, long after every hook has registered — `live-reconcile`, `markdown`, `pricing`
# and `run-panel` are all shaped that way and all correct. Only a hook can register before the
# seal does.
SPEC_HOOK = re.compile(r"^\s*test\.before(?:Each|All)\s*\(", re.M)

# Navigation is what makes a spec need the seal at all. `motion.spec.ts` drives
# `app/src/motion.ts` directly with no page, and must not be dragged in.
SPEC_GOTO = re.compile(r"\bpage\.goto\s*\(")


def _blank_ts_comments(text: str) -> str:
    """TypeScript comments replaced by their own newlines, so ORDER and LINE NUMBERS survive.

    `_strip_ts_comments` collapses a block comment to a single space, which is right for
    `route rosters` — it re-reads the raw text to find line numbers — and wrong here, where
    the whole question is which of two constructs comes first in the file.
    """
    return TS_COMMENT.sub(lambda found: "\n" * found.group(0).count("\n"), text)


# --------------------------------------------------------------- the design-check verdict
#
# `make design-check` is the one target a session cannot wait for inside a tool call: ~2
# minutes clean, 171s measured under load, against a 120s timeout. So it leaves a verdict at
# `.serve/design-check.json` and CLAUDE.md tells the next session to read that file instead
# of the 450-line stream. Four files have to agree for that instruction to be true, and
# THREE OF THE FOUR WAYS THEY CAN DISAGREE ARE SILENT:
#
#   * the reporter dropped from `playwright.config.ts`'s reporter list — the suite runs, is
#     green, and writes nothing;
#   * `RESULT_FILE` moved in the reporter but not in the prose — the suite writes a verdict
#     nobody reads;
#   * the `rm -f` dropped from a Makefile recipe — and this is the worst of the three,
#     because it is what makes a MISSING file mean "died before Playwright loaded its
#     config". Without it a run that never started leaves the PREVIOUS run's `"pass"`
#     sitting there for a session to believe. That is a false green reached by following
#     the documented procedure, which is the shape this repo has the fewest defences
#     against.
#
# Only the fourth is loud: delete `design-check-reporter.ts` while the config still names
# it and Playwright refuses to start.
#
# THIS IS A STATIC AGREEMENT CHECK AND NOT A BEHAVIOURAL ONE, which is a real limit and is
# recorded rather than papered over. It reads four files and reconciles one path and one
# name across them; it cannot tell you the reporter still WORKS. Proving that needs a
# Playwright run, which is the whole reason `design-check` is not in `make check` — a check
# that starts a browser is a different weight of check from the rest. Same bargain
# `check registry` records about itself: this row can only lie about agreement, and it
# fails a commit when it does.
_VERDICT_RESULT_FILE = re.compile(
    r"RESULT_FILE\s*=\s*resolve\(\s*REPO_ROOT\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*\)"
)
_VERDICT_REPORTER = ROOT / "app" / "design-check-reporter.ts"
_VERDICT_CONFIG = ROOT / "app" / "playwright.config.ts"
_VERDICT_RECIPES = ("design-check", "design-check-quiet")


def _make_recipe(text: str, target: str) -> Optional[List[str]]:
    """The recipe lines of one Makefile target, or None where the target has no rule.

    Pure, so `--self-test` can drive it without a Makefile.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith(f"{target}:"):
            continue
        body: List[str] = []
        for following in lines[index + 1:]:
            if following.startswith("\t"):
                body.append(following[1:])
            elif following.strip() == "" or following.startswith("#"):
                continue
            else:
                break
        return body
    return None


def verdict_disagreements(
    reporter: Optional[str],
    config: Optional[str],
    makefile: str,
    published: str,
) -> List[Finding]:
    """The four-way agreement, as a pure function of four file bodies.

    Split out from the file reading so `--self-test` can hand it each way of disagreeing
    without a repository — the same split `check_dispatch` and `phony_gaps` already make.
    """
    findings: List[Finding] = []
    if reporter is None:
        findings.append(
            Finding(
                "app/design-check-reporter.ts",
                "does not exist, but CLAUDE.md tells a session to read the file it writes.",
            )
        )
        return findings

    match = _VERDICT_RESULT_FILE.search(reporter)
    if match is None:
        findings.append(
            Finding(
                "app/design-check-reporter.ts",
                "no `RESULT_FILE = resolve(REPO_ROOT, ...)` to read.\n"
                "  That constant is what every claim below is reconciled against.",
            )
        )
        return findings
    path = f"{match.group(1)}/{match.group(2)}"

    if config is None:
        findings.append(Finding("app/playwright.config.ts", "does not exist."))
    elif "design-check-reporter" not in _blank_ts_comments(config):
        findings.append(
            Finding(
                "app/playwright.config.ts",
                "its `reporter` setting no longer names `./design-check-reporter.ts`.\n"
                "  The suite would run green and write no verdict at all, and a session "
                "following CLAUDE.md would read the absent file as `the run died before "
                "Playwright loaded its config` — a wrong diagnosis reached by following the "
                "documented procedure.\n"
                "  Comments do not count: this reads the config with them blanked.",
            )
        )

    for target in _VERDICT_RECIPES:
        body = _make_recipe(makefile, target)
        if body is None:
            findings.append(Finding("Makefile", f"no `{target}` rule to read."))
            continue
        removes = next((n for n, line in enumerate(body) if "rm -f" in line and path in line), None)
        runs = next((n for n, line in enumerate(body) if "run design-check" in line), None)
        if runs is None:
            findings.append(
                Finding("Makefile", f"`{target}` never invokes the design-check script.")
            )
            continue
        if removes is None:
            findings.append(
                Finding(
                    "Makefile",
                    f"`{target}` does not delete `{path}` before it runs.\n"
                    "  Deleting first is the whole reason a MISSING file means something. "
                    "Without it, a run that dies before Playwright loads its config leaves "
                    "the PREVIOUS run's verdict in place — a stale `\"pass\"` for the next "
                    "session to believe.",
                )
            )
        elif removes > runs:
            findings.append(
                Finding(
                    "Makefile",
                    f"`{target}` deletes `{path}` AFTER running the suite, which throws the "
                    "verdict away instead of clearing a stale one.",
                )
            )

    if path not in published:
        findings.append(
            Finding(
                "CLAUDE.md",
                f"the reporter writes `{path}`, which this file never names.\n"
                "  The path is the whole instruction — a session told to read a verdict file "
                "needs to be told which one.",
            )
        )
    return findings


def check_design_check_verdict(report: Report) -> None:
    """`.serve/design-check.json` is named the same in the reporter, the config, make and the prose."""
    reporter = read(_VERDICT_REPORTER) if exists(_VERDICT_REPORTER) else None
    config = read(_VERDICT_CONFIG) if exists(_VERDICT_CONFIG) else None
    makefile = read(ROOT / "Makefile") if exists(ROOT / "Makefile") else ""
    published = read(ROOT / "CLAUDE.md") if exists(ROOT / "CLAUDE.md") else ""
    findings = verdict_disagreements(reporter, config, makefile, published)
    match = _VERDICT_RESULT_FILE.search(reporter or "")
    where = f"{match.group(1)}/{match.group(2)}" if match else "unreadable"
    report.add(
        "verdict file",
        MECHANICAL,
        findings,
        f"{where} agreed by the reporter, the config, {len(_VERDICT_RECIPES)} recipes and the prose",
        scanned=sum(1 for text in (reporter, config, makefile, published) if text),
    )


def check_spec_seal(report: Report) -> None:
    """Every spec that mounts the app seals this checkout's capture port, and seals it first.

    Two claims, and the second is the one that cannot fail loudly on its own. See the banner
    above for what each costs.
    """
    findings: List[Finding] = []
    sealed = 0
    for spec in sorted(glob_files(APP_TESTS, "*.spec.ts"), key=rel):
        code = _blank_ts_comments(read(spec))
        if SPEC_GOTO.search(code) is None:
            continue
        call = SEAL_CALL.search(code)
        if call is None:
            findings.append(
                Finding(
                    rel(spec),
                    "navigates the app and never calls `sealEveryTest()`.\n"
                    "Its unstubbed reads go to this checkout's capture port — in the main tree "
                    "that is the owner's live server over their real store, and in a worktree it "
                    "is the 44px offline banner that moves every design floor.\n"
                    "Add `import { sealEveryTest } from './shell'` and call it at module scope, "
                    "above the file's first `test.beforeEach`.",
                )
            )
            continue
        sealed += 1
        hook = SPEC_HOOK.search(code)
        if hook is not None and hook.start() < call.start():
            findings.append(
                Finding(
                    f"{rel(spec)}:{code.count(chr(10), 0, call.start()) + 1}",
                    "calls `sealEveryTest()` below the `test.beforeEach` on line "
                    f"{code.count(chr(10), 0, hook.start()) + 1}.\n"
                    "Hooks run in declaration order, so the seal would install AFTER that "
                    "hook's `page.goto` — the requests it exists to catch would reach the real "
                    "port and the roster would still be empty. Move the call above it.",
                )
            )

    report.add(
        "spec seal",
        MECHANICAL,
        findings,
        f"{sealed} spec{'' if sealed == 1 else 's'} sealed against the capture port",
        scanned=sealed,
    )

# ------------------------------------------------------------------------ the route census
#
# CLAUDE.md said, for months: "THE COUNT IN THIS FILE HAS BEEN WRONG MORE OFTEN THAN IT HAS
# BEEN RIGHT, AND NOTHING CHECKS IT." This is the something, and it is the second half of a
# pair — `route rosters` above reconciles a SPEC's hand-typed list of routes against the same
# table, and was written days earlier for the same defect one directory over. Nothing had yet
# read the prose. Seven times the published screen count has
# disagreed with `app/src/App.tsx`'s ROUTES table — five at once between D39 and D49, a
# sixth in README.md's fenced list that D69 had to repair before it could extend, and a
# seventh on 2026-08-30 when D70's `#/codes` reached the table, CLAUDE.md and nothing else,
# leaving docs/map.py claiming NINE routes in one entry and EIGHT in another.
#
# WHY THIS IS A CHECK AND NOT A DELETION, which is the other thing this repo does with a
# number nobody maintains. `docs/GATES.md` step 5 deleted the server's route count on D18's
# test — a verifiable fact with nothing in it a later session could disagree with is not
# load-bearing prose — and CLAUDE.md explicitly rules the other way for this one: the
# sentence is what a session reads to learn the shape of the product, so it stays and gets
# a reader instead. Both are the same principle applied to different sentences; neither
# repeals the other.
#
# THE ORDINALS IN docs/map.py ARE DELIBERATELY NOT CHECKED. "`#/codes` IS THE TENTH" counts
# the order routes were ADDED, not the table's own order, where codes sits eighth of ten.
# A positional reader would fire on correct prose, and a false positive that blocks teaches
# `--no-verify`, which switches off the three opsec rules in the same hook (D16).

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}

# Each entry is (pattern, kind, what the sentence says). `kind` names the quantity the
# captured word must equal, resolved against the ROUTES table below. Anchored on the words
# either side rather than on the number alone, so the many HISTORICAL counts these files
# carry on purpose — "five after D31 merged", "#/boxes WAS the seventh", "It was six until
# D31" — do not match anything and are left as the prose they are.
_CENSUS_CLAIMS = (
    ("has ([A-Za-z]+) screens and ([A-Za-z]+) routes", ("total", "total")),
    ("([A-Za-z]+) the owner's, one the Fulfiller's", ("owner",)),
    # Re-pointed when Home took the root hash and capture moved to `#/capture`: the list this
    # sentence opens with now begins "home, capture" rather than "capture".
    ("([A-Za-z]+) screens — home, capture", ("total",)),
    ("all ([A-Za-z]+) routed", ("total",)),
    ("All ([A-Za-z]+) open at a hash", ("total",)),
    ("the other ([A-Za-z]+) carry", ("total_less_one",)),
    ("([A-Za-z]+) routes behind", ("total",)),
    ("the shell: ([A-Za-z]+) hash routes", ("total",)),
    ("([A-Za-z]+) of them the owner's", ("owner",)),
)

# The manifest is its own quantity: `make screenshot` renders a SUBSET of the routes, so a
# census claim about views.txt must be reconciled against that file and never against the
# table. Kept in this row because it is the same failure — a list grew and the number
# beside it did not (pricing by D49, orders and shipping by D69, against a comment that
# still said five).
_MANIFEST_CLAIM = ("([A-Za-z]+) owner screens and the Fulfiller's", "manifest_owner")


def _census_pattern(readable: str) -> str:
    """A claim's literal spaces, as `\\s+`.

    THE PATTERNS ARE WRITTEN AS THE SENTENCE READS and never as a regex with the whitespace
    hand-rolled, because hand-rolling it is how this row's first draft shipped a pattern
    that matched nothing: `the owner's` with one space cannot match prose whose seam
    `_census_text` has just widened, and a pattern that matches nothing reads exactly like
    a pattern with nothing to say. One transformation, applied to every claim, so the class
    of bug is gone rather than fixed one pattern at a time.
    """
    return readable.replace(" ", r"\s+")


_CENSUS_DOCS = ("CLAUDE.md", "README.md", "docs/map.py")


def _route_personas() -> Optional[List[Tuple[str, str]]]:
    """ROUTES as an ordered [(path, persona)], or None when the table cannot be read.

    Its own reader rather than `_routes_table()`'s: that one answers "which component does
    this route render", which is a different question and drops the persona this row counts
    by.
    """
    if not exists(APP_TSX):
        return None
    table = re.search(
        r"const ROUTES[^=]*=\s*\[(.*?)\n\]", _strip_ts_comments(read(APP_TSX)), flags=re.S
    )
    if table is None:
        return None
    body = table.group(1)
    starts = [m for m in re.finditer(r"path:\s*'([^']*)'", body)]
    if not starts:
        return None
    out: List[Tuple[str, str]] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
        persona = re.search(r"persona:\s*'([^']*)'", body[match.end():end])
        out.append((match.group(1), persona.group(1) if persona else ""))
    return out


def _census_text(target: Path) -> str:
    """The file's text with Python string-literal seams bridged, offsets preserved.

    docs/map.py wraps its prose across adjacent literals, so "NINE of them the " and
    "owner's" are one sentence to a reader and two to a regex — the quote-newline-quote
    between them defeats any `\\s+`. THE OWNER COUNT WENT UNCHECKED THAT WAY on this row's
    first draft: it reported ten published counts and green while the pattern watching the
    owner subcount matched nothing at all, which the per-pattern guard below then caught.

    Both quotes become spaces and every other character — the newlines included — stays
    where it is, so `\\s+` bridges the seam and the line numbers in a finding still point
    at the sentence.
    """
    text = read(target)
    if target.suffix != ".py":
        return text
    return _bridge_literals(text)


def _bridge_literals(text: str) -> str:
    """The seam between two adjacent Python string literals, as whitespace.

    Split out from the file reader so `--self-test` can reach the part with the logic in
    it, the same split the renumber reader makes for the same reason: the filesystem is not
    where this can be wrong.
    """
    return re.sub(r'"(\s*\n\s*)"', lambda m: " " + m.group(1) + " ", text)


def check_route_census(report: Report) -> None:
    """Every published route or screen count, against app/src/App.tsx's ROUTES table.

    MECHANICAL, because each of these is provably wrong on the committed tree alone: the
    table is in the repository, the sentence is in the repository, and they disagree or
    they do not. That is D16's line for a blocking row, and it is the line CLAUDE.md's own
    warning has been sitting on the wrong side of since D39.
    """
    routes = _route_personas()
    if routes is None:
        report.add("route census", MECHANICAL,
                   [Finding(rel(APP_TSX),
                            "the ROUTES table could not be read, so no published count can "
                            "be checked against it. If the table moved or changed shape, "
                            "this row's reader has to move with it.")])
        return

    total = len(routes)
    owner = sum(1 for _, persona in routes if persona == "owner")
    quantities = {
        "total": total,
        "owner": owner,
        "total_less_one": total - 1,
    }

    manifest_owner = None
    if exists(VIEWS_MANIFEST):
        lines = [
            line.strip()
            for line in read(VIEWS_MANIFEST).splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        manifest_owner = sum(1 for line in lines if "#/fulfillment" not in line)
        quantities["manifest_owner"] = manifest_owner

    findings: List[Finding] = []
    checked = 0
    # Per-PATTERN tallies, across every file at once. The per-file guard below catches a
    # doc that stops publishing a count altogether; this catches the subtler half, measured
    # rather than reasoned about: reword ONE of CLAUDE.md's two claims and that file still
    # yields a match, the row still prints green, and coverage has quietly gone from ten
    # counts to eight. A pattern that matches nothing anywhere is not coverage — it is a
    # regex keeping a green row company.
    hits: Dict[str, int] = {}
    for name in _CENSUS_DOCS:
        target = ROOT / name
        if not exists(target):
            findings.append(Finding(name, "does not exist, and it publishes a route count."))
            continue
        text = _census_text(target)
        seen_here = 0
        claims = list(_CENSUS_CLAIMS)
        if manifest_owner is not None:
            claims = claims + [(_MANIFEST_CLAIM[0], (_MANIFEST_CLAIM[1],))]
        for readable, kinds in claims:
            for match in re.finditer(_census_pattern(readable), text):
                for group, kind in enumerate(kinds, start=1):
                    word = match.group(group)
                    value = _NUMBER_WORDS.get(word.lower())
                    if value is None:
                        continue
                    seen_here += 1
                    checked += 1
                    hits[readable] = hits.get(readable, 0) + 1
                    expected = quantities[kind]
                    if value != expected:
                        line = text[:match.start()].count("\n") + 1
                        findings.append(Finding(
                            f"{name}:{line}",
                            f"says {word.lower()} where app/src/App.tsx's ROUTES table has "
                            f"{expected} ({kind.replace('_', ' ')}). The table is the count; "
                            f"recount off it rather than incrementing this sentence.",
                        ))
        if not seen_here:
            findings.append(Finding(
                name,
                "publishes no route or screen count this row can find. Either the sentence "
                "was deleted — which is a decision, and D18's test allows it — or it was "
                "reworded past every pattern in _CENSUS_CLAIMS, which switches this check "
                "off in silence. Add the phrasing to that table, or drop this file from "
                "_CENSUS_DOCS and say why.",
            ))

    for readable, _kinds in claims:
        if not hits.get(readable):
            findings.append(Finding(
                rel(SELF),
                f"the census claim {readable!r} matched nothing in {', '.join(_CENSUS_DOCS)}. "
                "It covered a published count that has since been reworded or deleted, so "
                "the sentence it was watching is now unwatched. Re-point the pattern at the "
                "new phrasing, or drop it and say which sentence went.",
            ))

    summary = f"{checked} published counts against {total} routes ({owner} owner)"
    if manifest_owner is not None:
        summary += f", {manifest_owner} owner renders in the manifest"
    report.add("route census", MECHANICAL, findings, summary, scanned=checked)


def check_positional_references(report: Report, docs: List[Path]) -> None:
    """A check named by its position, in the docs and in the code.

    **Two rows, because they are two different questions.** They do not share a scope and
    they do not share a severity, so a combined verdict would have had to take the widest
    scope and the strictest severity of both and apply them to each:

      check numbering    a check named by position in the markdown. Staged-scoped like
                         every other doc check, so a commit answers for its own lines.
      numbering in code  the same, in `.py` comments and the allowlist. ADVISORY and
                         whole-tree, for the reason `decision ids in code` is: a comment
                         saying it will check N rows is ordinary English, and a false
                         positive that blocks a commit is worse than one that prints a
                         line. This paragraph tripped it while being written, which is
                         about as direct as evidence gets.

    That split is the same reasoning as `check_decision_ids`, which reads the docs and the
    code as two rows rather than one, and it is why nothing here has to choose between
    scanning code at all and scanning it under the docs' rules.

    Named, not numbered: the report's labels are the public contract, and this function's
    name is not. It was `check_registry` while it also checked a published count of the
    checks; that count is gone (D18), the labels it prints did not change.
    """

    def positional(paths: Iterable[Path]) -> List[Finding]:
        found: List[Finding] = []
        for path in paths:
            if not exists(path):
                continue
            for number, line in enumerate(read(path).splitlines(), start=1):
                for hit in _POSITIONAL_RE.findall(line):
                    found.append(
                        Finding(
                            f"{rel(path)}:{number}",
                            f"`{hit}` names a check by its position. Use the label the "
                            f"report prints — `repo map`, `status sources`, and so on "
                            f"(D17). If this is ordinary English about a count, reword it: "
                            f"there is no allowlist for a phrase.",
                        )
                    )
        return found

    report.add("check numbering", MECHANICAL, positional(docs),
               "no check named by position", scanned=len(docs))
    in_code = python_files() + [ALLOWLIST]
    report.add(
        "numbering in code",
        ADVISORY,
        positional(in_code),
        "comments name checks by label",
        scanned=len(in_code),
    )


# ------------------------------------------------------- what `make check` actually runs

CHECKS_REGISTRY = ROOT / "scripts" / "checks.py"
PRE_COMMIT = ROOT / "scripts" / "githooks" / "pre-commit"

# The recipe's own enumeration. `check:` is a block of tab-indented lines and nothing but
# `$(MAKE) --no-print-directory <target>` calls; see the Makefile's own comment for why they
# are calls and not prerequisites (make is free to reorder prerequisites, and with -j it runs
# them in parallel — a check suite has to run in a known order and stop at the first failure).
_CHECK_RECIPE_RE = re.compile(r"\$\(MAKE\)\s+--no-print-directory\s+([a-z][a-z0-9-]*)")

# A path inside the repo that a `runs` command names. Used to ask whether the pre-commit hook
# invokes the same thing, which is the only honest way to check the `commit_path` field: the
# hook runs `python3 scripts/docs-audit.py --staged`, never `make docs-audit`, so matching on
# the target name would answer no for the one entry that is genuinely on the commit path.
_RUNS_PATH_RE = re.compile(r"[A-Za-z0-9_./-]+\.(?:py|sh|mjs)")

# AND ITS FLAGS, BECAUSE ONE SCRIPT IS TWO CHECKS HERE. `docs-audit` and `audit-self-test` run
# the same file in different modes, and the hook runs a third — so a path match alone answers
# "on the commit path" for both, which this row caught on its first run against the tree it
# was written for. A check is on that path when the hook invokes its script IN ITS MODE.
#
# MATCHED PER LINE, AND IT WAS MATCHED OVER THE WHOLE FILE UNTIL D92. The sentence above is
# what this always meant; `path in hook and flag in hook` is not that, because the two can sit
# on different lines and mean nothing about each other. Adding a SECOND self-testing check to
# the hook proved it: `--self-test` then appeared in the file for `sigil-check`, and this row
# immediately reported `audit-self-test` — which the hook does not run, and which D18 requires
# it not to — as being on the commit path. A false negative would be worse than the loose
# match: it would report a check as gating commits when nothing runs it.
_RUNS_FLAG_RE = re.compile(r"--[a-z][a-z-]*")

CHECK_ENTRY_KEYS = (
    "target", "runs", "asserts", "needs", "writes",
    "commit_path", "why_off_commit_path", "gates", "governed_by",
)


def _recipe_targets(rule: str) -> Optional[List[str]]:
    """The targets one `$(MAKE)`-dispatching rule runs, in recipe order, or None."""
    makefile = ROOT / "Makefile"
    if not exists(makefile):
        return None
    block = re.search(rf"^{re.escape(rule)}:\n((?:\t.*\n)+)", read(makefile), flags=re.M)
    if block is None:
        return None
    return _CHECK_RECIPE_RE.findall(block.group(1))


def _check_recipe() -> Optional[List[str]]:
    """The targets `make check` runs, in recipe order, or None if the block cannot be read."""
    return _recipe_targets("check")


def _ci_check_recipe() -> Optional[List[str]]:
    """The targets `make ci-check` runs — the gate `.github/workflows/check.yml` invokes.

    RECONCILED AGAINST NOTHING UNTIL 2026-09-12, while `check registry`, `check census` and
    `commit path` all read the `check:` recipe alone. The Makefile's own header states the
    hazard in capitals — "IT IS A SUBSET AND CAN DRIFT FROM `check`" — and a target dropped
    from this one stops gating every pull request and every push in silence, which is the
    armed-hook defect with a runner in front of it.

    Membership only, deliberately, and never order: `check registry` owns the order of the
    `check:` recipe, and `ci-check` is ordered differently on purpose.
    """
    return _recipe_targets("ci-check")


# The marker a non-gating target's recipe has to print, so a reader of a green `make check`
# is not counting a slot that cannot fail among the ones that can (`gates: False` in
# scripts/checks.py). Paired in BOTH directions: a marker in a gating target's recipe is as
# wrong as a missing one in `vale`'s.
_NOT_A_GATE_MARKER = "NOT A GATE:"


def _checks_registry() -> Optional[Tuple[List[dict], dict]]:
    """(CHECKS, NEEDS) out of scripts/checks.py, by literal_eval and never by import.

    Same access `docs/map.py` and `scripts/status.py`'s SOURCES get, for the same reason: a
    read-only check must not execute the code it is checking.
    """
    if not exists(CHECKS_REGISTRY):
        return None
    values = literals_from_module(CHECKS_REGISTRY)
    entries, needs = values.get("CHECKS"), values.get("NEEDS")
    if not isinstance(entries, (list, tuple)) or not isinstance(needs, dict):
        return None
    return [dict(entry) for entry in entries], dict(needs)


def check_check_registry(report: Report) -> None:
    """scripts/checks.py against the `check:` recipe it describes, both directions.

    THE REGISTRY IS A PARALLEL DECLARATION AND NOT THE DRIVER, which is the shape that makes
    this row necessary and also makes it safe. A registry that drove `make check` could not
    disagree with it — and could silently stop running a check, which is the failure this repo
    has paid for more than any other. A registry that merely describes it can only lie, and a
    lie is what a check can catch.

    ORDER IS CHECKED, not just membership. The file says its entries are in recipe order and
    `make explain` prints them that way, so a reader takes the order as the running order; a
    claim being read is a claim worth verifying, and it costs one comparison.

    **`ci-check` IS RECONCILED HERE TOO, AS OF 2026-09-12, and it had no reader at all.**
    `grep -c ci-check scripts/docs-audit.py` returned 0: three rows read the `check:` recipe
    and none read the gate `.github/workflows/check.yml` actually invokes on every pull
    request and every push. The Makefile's own header says "IT IS A SUBSET AND CAN DRIFT
    FROM `check`", which is a hazard written down and watched by nobody.

    The difference is DECLARED, not tolerated: a target in `check` and not in `ci-check`
    needs a `why_off_ci` sentence on its entry, and a target carrying that sentence while
    sitting in `ci-check` is as wrong as a missing one — the same pairing discipline
    `commit_path` / `why_off_commit_path` already keeps. Membership only, never order.
    Today the sole difference is `vale`, which the Makefile header already argues, so the
    extension starts green.

    **AND A SLOT THAT CANNOT FAIL SAYS SO AT RUN TIME.** `gates: False` was read by nothing:
    the field was declared honestly and the disclosure never reached the run a session
    reads. `vale` swallows its status with `--no-exit` and, with no binary, prints and exits
    0 — so a reader of a green `make check` counts 25 passing rows where 24 are gates. The
    entry's recipe has to print `NOT A GATE:`, in both directions, so `make explain`, the
    run and the reader agree. A GATING target is never forced to print anything; the point
    is disclosure, not removal, and the owner has ruled prose style worth running and not
    worth gating (D74).
    """
    recipe = _check_recipe()
    ci_recipe = _ci_check_recipe()
    loaded = _checks_registry()
    if recipe is None:
        report.add("check registry", MECHANICAL, [Finding(
            "Makefile",
            "the `check:` recipe could not be read, so nothing can be reconciled against it. "
            "If the target changed shape, this row's reader has to move with it.")])
        return
    if loaded is None:
        report.add("check registry", MECHANICAL, [Finding(
            rel(CHECKS_REGISTRY),
            "CHECKS and NEEDS could not be read as module-level literals. They are parsed "
            "with `ast.literal_eval` and never imported, so every entry must stay a plain "
            "literal — no helper class, no call, no comprehension.")])
        return

    entries, needs = loaded
    findings: List[Finding] = []

    declared = [str(entry.get("target", "")) for entry in entries]
    for name in recipe:
        if name not in declared:
            findings.append(Finding(rel(CHECKS_REGISTRY), (
                "`make check` runs `{0}` and no entry describes it.\n"
                "  Add one, or `make explain` and `make help` both under-report the suite."
            ).format(name)))
    for name in declared:
        if name not in recipe:
            findings.append(Finding(rel(CHECKS_REGISTRY), (
                "there is an entry for `{0}`, which `make check` does not run.\n"
                "  An entry for a check nobody runs reads as coverage."
            ).format(name)))
    if not findings and declared != recipe:
        findings.append(Finding(rel(CHECKS_REGISTRY), (
            "the entries are not in recipe order.\n"
            "  recipe:   {0}\n"
            "  registry: {1}"
        ).format(", ".join(recipe), ", ".join(declared))))

    for entry in entries:
        where = "{0} — {1}".format(rel(CHECKS_REGISTRY), entry.get("target", "<unnamed>"))
        missing = [key for key in CHECK_ENTRY_KEYS if key not in entry]
        if missing:
            findings.append(Finding(where, "entry is missing: {0}".format(", ".join(missing))))
            continue
        for token in entry["needs"]:
            if token not in needs:
                findings.append(Finding(where, (
                    "`needs` names `{0}`, which NEEDS does not define.\n"
                    "  A token nobody defined is a token nobody can reason about."
                ).format(token)))

    # NEEDS is a section of this file in D80's sense, and the same rule applies one level
    # down: a vocabulary entry no check claims is a definition with no reader.
    claimed = {token for entry in entries for token in entry.get("needs", ())}
    for token in sorted(set(needs) - claimed):
        findings.append(Finding(rel(CHECKS_REGISTRY), (
            "NEEDS defines `{0}` and no check needs it. Delete it or use it (D80)."
        ).format(token)))

    # ---- the OTHER gate: `make ci-check`, which every PR and push runs ------------------
    if ci_recipe is None:
        findings.append(Finding("Makefile", (
            "the `ci-check:` recipe could not be read, and `.github/workflows/check.yml` "
            "invokes it on every pull request and every push.\n"
            "  A subset nothing reconciles is a gate that can lose a target in silence.")))
    else:
        by_target = {str(entry.get("target", "")): entry for entry in entries}
        for name in ci_recipe:
            if name not in recipe:
                findings.append(Finding("Makefile", (
                    "`make ci-check` runs `{0}` and `make check` does not.\n"
                    "  ci-check is a SUBSET of check by the Makefile's own header. A target "
                    "only CI runs is one a session cannot reproduce before pushing."
                ).format(name)))
        for name in recipe:
            if name in ci_recipe:
                continue
            entry = by_target.get(name)
            reason = str((entry or {}).get("why_off_ci") or "").strip()
            if not reason:
                findings.append(Finding(
                    "{0} — {1}".format(rel(CHECKS_REGISTRY), name),
                    "`make check` runs it and `make ci-check` does not, and the entry says "
                    "nothing about why.\n"
                    "  Either add it to the ci-check recipe, or give the entry a "
                    "`why_off_ci` sentence. A target silently absent from the gate that "
                    "runs on every PR has stopped gating anything, and the run is green "
                    "because it never happened.",
                ))
        for name, entry in sorted(by_target.items()):
            if str(entry.get("why_off_ci") or "").strip() and name in ci_recipe:
                findings.append(Finding(
                    "{0} — {1}".format(rel(CHECKS_REGISTRY), name),
                    "carries `why_off_ci` and `make ci-check` runs it. The sentence explains "
                    "an absence that is over; delete it, or the next reader believes CI does "
                    "not run this.",
                ))

    # ---- a slot in `make check` that cannot fail says so where the run is read ----------
    makefile_text = read(ROOT / "Makefile") if exists(ROOT / "Makefile") else ""
    for entry in entries:
        name = str(entry.get("target", ""))
        if "gates" not in entry:
            continue
        body = _make_recipe(makefile_text, name)
        if body is None:
            continue  # `check registry`'s membership legs above already name a missing rule
        printed = any(_NOT_A_GATE_MARKER in line for line in body)
        if not entry["gates"] and not printed:
            findings.append(Finding(
                "Makefile — {0}".format(name),
                "is declared `gates: False` and its recipe never says so.\n"
                "  It occupies a slot in `make check` that cannot fail, and a reader of a "
                "green run counts it among the ones that can. Print `{0}` in the recipe — "
                "the disclosure is the point, not removing the target.".format(
                    _NOT_A_GATE_MARKER),
            ))
        elif entry["gates"] and printed:
            findings.append(Finding(
                "Makefile — {0}".format(name),
                "prints `{0}` and its entry declares `gates: True`. One of the two is "
                "wrong, and the recipe is what a session reads.".format(_NOT_A_GATE_MARKER),
            ))

    ungated = sum(1 for entry in entries if entry.get("gates") is False)
    report.add("check registry", MECHANICAL, findings,
               "{0} checks in recipe order, {1} in ci-check, {2} declared non-gating".format(
                   len(recipe), len(ci_recipe or ()), ungated),
               scanned=len(recipe))


def check_commit_path(report: Report) -> None:
    """D18, asserted mechanically for the first time.

    **Nothing that writes may run on the path that decides whether a commit proceeds.** That
    rule is quoted in five Makefile comments, in `docs/DECISIONS.md` D18 and D16, and in the
    header of every self-test it governs — and until this row it was enforced by nobody. It is
    the most-cited rule in this repo with the least machinery behind it.

    Three claims, and the third is the one with teeth:

      1. `commit_path` agrees with `scripts/githooks/pre-commit`. Asked of the SCRIPT the
         entry runs and never of the target name: the hook invokes
         `python3 scripts/docs-audit.py --staged`, so a name match would answer no for the one
         entry that is genuinely on that path.
      2. `why_off_commit_path` is present exactly where `commit_path` is false. An entry
         claiming both, or neither, is describing nothing.
      3. Nothing on the commit path writes.

    A check whose `runs` names no repository path — `npm --prefix app run lint`, the vale
    pipeline — cannot be on the commit path, because the hook runs a bare python3 with nothing
    installed. So the absence of a path is itself the answer, rather than a case this row
    declines to judge.
    """
    loaded = _checks_registry()
    if loaded is None:
        report.add("commit path", MECHANICAL, [Finding(
            rel(CHECKS_REGISTRY), "CHECKS could not be read; see the `check registry` row.")])
        return
    if not exists(PRE_COMMIT):
        report.add("commit path", MECHANICAL, [Finding(
            rel(PRE_COMMIT),
            "does not exist, and every entry's `commit_path` is a claim about it.")])
        return

    entries, _ = loaded
    hook = read(PRE_COMMIT)
    findings: List[Finding] = []
    on_path = 0

    for entry in entries:
        if not all(key in entry for key in CHECK_ENTRY_KEYS):
            continue  # `check registry` reports the shape; this row does not repeat it
        name = entry["target"]
        where = "{0} — {1}".format(rel(CHECKS_REGISTRY), name)
        paths = _RUNS_PATH_RE.findall(entry["runs"])
        flags = _RUNS_FLAG_RE.findall(entry["runs"])
        invoked = any(
            any(path in line for path in paths) and all(flag in line for flag in flags)
            for line in hook.splitlines()
        )
        claimed = bool(entry["commit_path"])

        if claimed and not invoked:
            findings.append(Finding(where, (
                "claims the commit path, and {0} invokes none of {1}."
            ).format(rel(PRE_COMMIT), ", ".join(paths) or "the commands it runs")))
        elif invoked and not claimed:
            findings.append(Finding(where, (
                "says it is off the commit path, but {0} runs {1} in that mode.\n"
                "  Whichever is wrong, D18 is being reasoned about from a false premise."
            ).format(rel(PRE_COMMIT), ", ".join(p for p in paths if p in hook))))

        if claimed:
            on_path += 1
            if entry["writes"]:
                findings.append(Finding(where, (
                    "IS ON THE COMMIT PATH AND WRITES: {0}\n"
                    "  D18: nothing that writes may run on the path that decides whether a\n"
                    "  commit proceeds. An agent that can edit what its own gate reads will."
                ).format(entry["writes"])))
            if entry["why_off_commit_path"]:
                findings.append(Finding(where, (
                    "claims the commit path and also carries `why_off_commit_path`.")))
        elif not entry["why_off_commit_path"]:
            findings.append(Finding(where, (
                "is off the commit path and says nothing about why.\n"
                "  D18 or a toolchain — the reason is what a later session needs, and it is\n"
                "  the field that stops one being moved back on to the path by tidiness.")))

    report.add("commit path", MECHANICAL, findings,
               "{0} of {1} on the commit path, none of them writing".format(on_path, len(entries)),
               scanned=len(entries))


# The published claims about what `make check` runs, as the sentence reads. The anchor is
# `make check` followed by whitespace, an optional comment marker and a target name — which is
# the summary form and nothing else. Every OTHER mention in these two files backticks the
# command (``make check` is invoked by a person`, ``make check` green means…`), so the
# backtick is what keeps ordinary prose about the target out of this row.
_CHECK_CLAIM_RE = re.compile(r"make check[ \t]+#?[ \t]*(?=[a-z])")

# The `+`-joined run that follows it. `\s` spans newlines because both claims wrap.
_CHECK_LIST_RE = re.compile(r"(?:[a-z][a-z0-9-]*[ \t\n]*\+[ \t\n]*)*[a-z][a-z0-9-]*")

_CHECK_CLAIM_DOCS = ("Makefile", "CLAUDE.md")


def _check_claim_text(target: Path) -> str:
    """The file's text with each claim's continuation scaffolding removed.

    BOTH PUBLISHED CLAIMS WRAP, AND EACH WRAPS THROUGH A DIFFERENT SCAFFOLD — the Makefile's
    help line through `@echo "` … `"`, CLAUDE.md's through the `#` of a fenced comment.
    Neither is part of the sentence, and the Makefile's puts LETTERS between two target names:
    `@echo` reads as a token to any scanner that does not know better, which would truncate
    the list at every wrap and report the tail as missing.

    Same idea as `_bridge_literals` one row over, for the same class of problem: a sentence a
    human reads as one line and a regex reads as three.
    """
    out = []
    for line in read(target).splitlines():
        line = re.sub(r'^\s*@echo\s+"', "", line)   # Makefile help scaffolding
        line = line.rstrip().rstrip('"')
        line = re.sub(r"^\s*#\s*", "", line)        # a fenced comment's continuation
        out.append(line)
    return "\n".join(out)


# ------------------------------------------------ the browser fleet, and the lock it takes
#
# `make design-check` is the one target here that spends the whole machine — Playwright's
# `fullyParallel` at half the cores, each worker a Chromium context over its own Vite dev
# server. D43 gave every checkout its own ports and its own store; the CPU is what it could
# not copy, and two trees running the fleet at once starve each other into failures that are
# not in the code (D122, and `scripts/suite-lock.py` carries the 2026-09-07 measurement).
#
# THE GUARD IS ONE LINE OF ONE RECIPE, WHICH IS EXACTLY THE KIND OF LINE THAT GOES MISSING.
# A second browser suite landing under its own target would be unguarded and green, and the
# only symptom would be somebody else's re-run. So this row reads the RUNNER rather than the
# target name: any npm script whose command is `playwright test` is a fleet, and every
# Makefile recipe that reaches one has to go through the lock.
SUITE_LOCK_SCRIPT = ROOT / "scripts" / "suite-lock.py"

#: What makes a script a fleet: `playwright test`, the only runner here that draws pages in
#: PARALLEL. `scripts/screenshot.sh` and `scripts/screenshot.mjs` render one page at a time and
#: are deliberately NOT covered — see D122, which argues the exclusion on the SHAPE of the run
#: rather than on a command name, having named a stale one for a day and been corrected.
_FLEET_RUNNER_RE = re.compile(r"\bplaywright\s+test\b")

#: The runners this row reads besides the Makefile and app/package.json. A fleet does not have to
#: arrive as an npm script: `scripts/screenshot.sh` is a shell script that shells out to a node
#: script that drives Playwright, and either could grow `playwright test` without touching a
#: recipe. Reading them is what makes the previous comment a checked claim rather than a promise.
FLEET_RUNNER_SCRIPTS = ("screenshot.sh", "screenshot.mjs")


def _npm_run_re(script: str) -> "re.Pattern[str]":
    """A recipe line reaching an npm script, with or without `--prefix`."""
    return re.compile(r"\bnpm\b[^\n]*\brun\s+" + re.escape(script) + r"\b")


def check_suite_lock(report: Report) -> None:
    """Every Makefile recipe that starts a Playwright fleet goes through the lock.

    MECHANICAL, and in both directions: a fleet script no recipe reaches is reported as much
    as a recipe that reaches one without the lock. The first is the drift that would happen —
    a new browser target, written from the old one, without the line that matters.

    IT REFUSES TO GO QUIET, on `check census`'s reasoning. If `app/package.json` holds no
    script this row recognises as a fleet, that is REPORTED rather than passed: the runner
    was renamed or the suite moved, and either way a guard that silently starts covering
    nothing is the failure it exists to prevent.

    IT READS THE OTHER RUNNERS TOO, AND THAT IS THE DIRECTION D122 GOT WRONG ONCE. A fleet does
    not have to arrive as an npm script — `scripts/screenshot.sh` shells out to
    `scripts/screenshot.mjs`, which drives Playwright directly, and either could grow
    `playwright test` without a recipe changing. D122's first draft excluded that path by NAME
    (`playwright screenshot`), and the name was stale the day it merged. Reading the files is
    what turns "those render one page at a time" from a promise into a checked claim.

    WHAT IT DOES NOT CHECK: that the lock WORKS. `make suite-lock-selftest` does that, by
    violating it. This row settles only that the thing which spends the machine is behind it.
    """
    findings: List[Finding] = []

    if not exists(SUITE_LOCK_SCRIPT):
        report.add("suite lock", MECHANICAL, [Finding(
            rel(SUITE_LOCK_SCRIPT),
            "does not exist, and `make design-check` is written to run through it.")])
        return

    try:
        package = json.loads(read(ROOT / "app" / "package.json"))
        scripts = {str(k): str(v) for k, v in (package.get("scripts") or {}).items()}
    except (OSError, ValueError) as exc:
        report.add("suite lock", MECHANICAL, [Finding(
            "app/package.json", "could not be read, so no fleet can be identified.\n%s" % exc)])
        return

    fleets = sorted(name for name, body in scripts.items() if _FLEET_RUNNER_RE.search(body))
    if not fleets:
        report.add("suite lock", MECHANICAL, [Finding(
            "app/package.json", (
                "holds no script that runs `playwright test`, so this row is watching\n"
                "  nothing. Either the fleet moved or the runner was renamed — the pattern\n"
                "  has to move with it, or the guard covers a suite that no longer exists."))])
        return

    lines = read(ROOT / "Makefile").splitlines()
    for script in fleets:
        pattern = _npm_run_re(script)
        callers = [(n + 1, line) for n, line in enumerate(lines)
                   if line.startswith("\t") and pattern.search(line)]
        if not callers:
            findings.append(Finding("app/package.json", (
                "`{0}` runs a Playwright fleet and no Makefile recipe reaches it.\n"
                "  A fleet nobody can start is dead, and a fleet started from somewhere this\n"
                "  row cannot see is unguarded. Either is worth a look."
            ).format(script)))
            continue
        for line_no, line in callers:
            if "suite-lock.py" not in line:
                findings.append(Finding("Makefile:{0}".format(line_no), (
                    "starts the `{0}` fleet without taking the machine-wide lock.\n"
                    "  Two fleets at once starve each other and BOTH report failures that are\n"
                    "  not in the code. Run it through `python3 scripts/suite-lock.py run -- "
                    "…` (D122)."
                ).format(script)))

    # The direct form, which no npm script mediates: a recipe calling the runner itself.
    for n, line in enumerate(lines):
        if not line.startswith("\t") or not _FLEET_RUNNER_RE.search(line):
            continue
        if "suite-lock.py" not in line:
            findings.append(Finding("Makefile:{0}".format(n + 1), (
                "runs `playwright test` directly without taking the machine-wide lock "
                "(D122).")))

    # The runners D122 excludes by SHAPE. Each is expected to exist and to stay serial; a
    # `playwright test` appearing in one is a fleet that reaches no recipe this row can read.
    for name in FLEET_RUNNER_SCRIPTS:
        target = ROOT / "scripts" / name
        if not exists(target):
            findings.append(Finding("scripts/{0}".format(name), (
                "does not exist, and D122 excludes `make screenshot` from the lock on the\n"
                "  strength of what this file does. Either it moved, or the exclusion needs\n"
                "  re-arguing against whatever replaced it.")))
            continue
        for n, line in enumerate(read(target).splitlines()):
            if _FLEET_RUNNER_RE.search(line) and "suite-lock.py" not in line:
                findings.append(Finding("scripts/{0}:{1}".format(name, n + 1), (
                    "runs `playwright test`, so it is a fleet. D122 excludes this file from\n"
                    "  the machine-wide lock because it renders one page at a time; that\n"
                    "  argument does not survive a parallel runner. Take the lock, or reopen\n"
                    "  D122's exclusion.")))

    report.add("suite lock", MECHANICAL, findings,
               "{0} fleet script{1} behind the lock, {2} serial renderers still serial".format(
                   len(fleets), "" if len(fleets) == 1 else "s", len(FLEET_RUNNER_SCRIPTS)),
               scanned=len(fleets) + len(FLEET_RUNNER_SCRIPTS))


# ------------------------------------------------------------ the browser matrix's scope
#
# `.github/workflows/check.yml` runs its browser matrix on a pull request only when the change
# touches a path `scripts/browser-scope.py:SCOPE` names (D141). A path filter is the one gate
# whose failure is INVISIBLE: too narrow, and the matrix stops running for a class of change,
# the run is green because it never happened, and the green is believed. That is the armed
# hook's defect from `scripts/githooks/pre-commit`'s own header, one level up — and the reason
# D141 rules that the filter does not ship without this row.
#
# THE LIST IS RECONCILED AGAINST WHAT THE SUITE LOADS, NOT AGAINST A SECOND LIST. Each
# dependency below is READ from the thing that creates it: Playwright's `testDir`, its reporter
# and its imports out of `app/playwright.config.ts`; Vite's root out of `app/vite.config.ts`,
# with any relative literal there that reaches outside `app/`; every code string in a spec or
# a module that names a tracked file outside `app/` (how `cadence.spec.ts`'s traces are found);
# every `scripts/` file the `design-check` recipe names; and the gate's own two files. A
# dependency the scope does not cover fails; an entry that covers nothing tracked fails; a
# `within` narrowing that names a recipe the Makefile no longer has fails.
#
# AND THE WIRING IS READ, because a list nothing consults is a list. The workflow must run the
# classifier from some job, `design-check` must need that job and read its answer in the
# FAIL-OPEN spelling — `!= 'false'` under `!cancelled()` — the `on:` block may carry no path
# filter (that would gate `check`, `revert-guard` and `already-passed` too, which D141
# forbids), and `design-check-passed` may not run on a skipped matrix, or a tree no browser
# saw would earn D136's pass record.
#
# WHAT IT CANNOT SEE, by name: a path a spec composes at runtime from pieces; a Vite
# `server.fs.allow` widening written in a form these regexes do not read; and a code string
# on the same line as a `//` inside a URL, which the comment blanker takes with it. Each is a
# miss and never a false finding.
BROWSER_SCOPE_SCRIPT = ROOT / "scripts" / "browser-scope.py"
CHECK_WORKFLOW = ROOT / ".github" / "workflows" / "check.yml"
PLAYWRIGHT_CONFIG = ROOT / "app" / "playwright.config.ts"
VITE_CONFIG = ROOT / "app" / "vite.config.ts"
APP_DIR = ROOT / "app"

#: A code string naming something tracked outside `app/` — the shape `cadence.spec.ts` keys
#: its TRACES table by. The prefixes are the tree's top-level directories a spec could plausibly
#: read; a literal that resolves to nothing tracked is prose and is ignored.
_REPO_LITERAL_RE = re.compile(
    r"""['"`]((?:harness|docs|fixtures|scripts|server|store|pipeline|cli|identify|geometry|"""
    r"""codes|demo-assets|inventory)/[\w./@+-]+)['"`]"""
)
#: A `./x` or `../x` literal in one of the two configs — an import, a `testDir`, a reporter
#: path, an alias target. Resolved against `app/`; the ones that leave it are dependencies.
_RELATIVE_LITERAL_RE = re.compile(r"""['"`](\.\.?/[^'"`\n]*)['"`]""")
_TESTDIR_RE = re.compile(r"\btestDir:\s*['\"]([^'\"]+)['\"]")
_VITE_ROOT_RE = re.compile(r"^\s*root:\s*['\"]([^'\"]+)['\"]", re.M)
_SCOPE_STEP_RE = re.compile(r"python3\s+scripts/browser-scope\.py\s+classify\b")
_YAML_JOB_KEY_RE = re.compile(r"^  ([a-z][\w-]*):\s*$")


def _tracked_paths() -> Set[str]:
    """Every tracked path, from the index in staged mode and from git otherwise."""
    return set(_INDEX_PATHS) if _INDEX_PATHS is not None else _nul_list("ls-files", "-z")


def _app_relative(literal: str, base_dir: Path = APP_DIR) -> str:
    """A relative literal from a file in `base_dir`, as a repo-relative path (never resolved
    through the filesystem, so a target that does not exist still has a name)."""
    return os.path.relpath(os.path.normpath(str(base_dir / literal)), str(ROOT))


def _import_target(name: str, tracked: Set[str]) -> str:
    """`./devPort` is `app/devPort.ts` on disk; try the resolutions Node would."""
    for suffix in ("", ".ts", ".tsx", "/index.ts"):
        candidate = _app_relative(name + suffix)
        if candidate in tracked:
            return candidate
    return _app_relative(name)


def _yaml_top_block(text: str, key: str) -> Optional[str]:
    """The lines of one top-level key of a workflow file, up to the next top-level key."""
    lines = text.split("\n")
    out: List[str] = []
    inside = False
    for line in lines:
        if re.match(r"^" + re.escape(key) + r":", line):
            inside = True
            out.append(line)
            continue
        if inside:
            if re.match(r"^[a-z]", line):
                break
            out.append(line)
    return "\n".join(out) if out else None


def _yaml_job_block(text: str, name: str) -> Optional[str]:
    """One job's lines, from its key to the next job key at the same indent."""
    lines = text.split("\n")
    out: List[str] = []
    inside = False
    for line in lines:
        key = _YAML_JOB_KEY_RE.match(line)
        if key and key.group(1) == name:
            inside = True
            out.append(line)
            continue
        if inside:
            if key:
                break
            out.append(line)
    return "\n".join(out) if out else None


def browser_gate_findings(text: str) -> List[Tuple[str, str]]:
    """The workflow's wiring, as (where, message) pairs. Pure, so `--self-test` can mutate it."""
    where = rel(CHECK_WORKFLOW)
    out: List[Tuple[str, str]] = []

    step = _SCOPE_STEP_RE.search(text)
    job: Optional[str] = None
    if step is None:
        out.append((where, (
            "no job runs `python3 scripts/browser-scope.py classify`, so the scope list is\n"
            "  consulted by nothing and `design-check` is gated by whatever its `if:` says.")))
    else:
        for line in text[: step.start()].split("\n"):
            key = _YAML_JOB_KEY_RE.match(line)
            if key:
                job = key.group(1)
        if job is None:
            out.append((where, "the classifier step is not inside a job this reader can name."))

    on = _yaml_top_block(text, "on")
    if on is None:
        out.append((where, "has no `on:` block."))
    elif re.search(r"^\s*paths(?:-ignore)?:", on, re.M):
        out.append((where, (
            "the `on:` block carries a `paths` filter. That gates EVERY job — `check`,\n"
            "  `revert-guard` and `already-passed` included — and D141 scopes the browser\n"
            "  matrix alone. The filter is `browser-scope`'s output, read by one job's `if:`.")))

    design = _yaml_job_block(text, "design-check")
    if design is None:
        out.append((where, "has no `design-check` job for the scope to gate."))
    elif job is not None:
        needs = re.search(r"^\s*needs:.*?(?=^\s*(?:if|runs-on):)", design, re.M | re.S)
        if needs is None or job not in needs.group(0):
            out.append((where, f"`design-check` does not `need` `{job}`, so its answer is not waited for."))
        cond = re.search(r"^\s*if:\s*(.+)$", design, re.M)
        answer = f"needs.{job}.outputs.run"
        if cond is None or f"{answer} != 'false'" not in cond.group(1):
            out.append((where, (
                f"`design-check`'s `if:` does not read `{answer} != 'false'`.\n"
                "  That spelling is the fail-open one: a classifier that errored, a job that\n"
                "  never ran and an empty output all RUN the matrix. `== 'true'` would skip it\n"
                "  on every one of those, silently (D141).")))
        if cond is not None and "!cancelled()" not in cond.group(1):
            out.append((where, (
                "`design-check`'s `if:` has no `!cancelled()`, so GitHub prepends `success()`\n"
                "  and a FAILED gate job skips the matrix instead of releasing it.")))

    passed = _yaml_job_block(text, "design-check-passed")
    if passed is not None:
        cond = re.search(r"^\s*if:\s*(.+)$", passed, re.M)
        if cond is not None and re.search(r"always\(\)|cancelled\(\)", cond.group(1)):
            out.append((where, (
                "`design-check-passed` runs on a skipped matrix, so a tree no browser saw\n"
                "  would earn D136's pass record and skip the matrix on main too.")))
    return out


def _repo_literals(code: str, tracked: Set[str]) -> List[str]:
    """Tracked paths outside `app/` that a file's CODE names. Comments are blanked first."""
    found: List[str] = []
    for match in _REPO_LITERAL_RE.finditer(_blank_ts_comments(code)):
        candidate = match.group(1)
        # A tracked file, or a directory literal (trailing `/`) with tracked files under it.
        is_dir = candidate.endswith("/") and any(p.startswith(candidate) for p in tracked)
        if candidate in tracked or is_dir:
            found.append(candidate)
    return found


def _browser_requirements(module, tracked: Set[str], makefile: str) -> List[Tuple[str, str]]:
    """Every path the browser suite depends on, with where the dependency was read from.

    A path ending in `/` is a directory and means every tracked file under it.
    """
    out: List[Tuple[str, str]] = [
        (rel(CHECK_WORKFLOW), "the gate's own workflow"),
        (rel(BROWSER_SCOPE_SCRIPT), "the classifier the workflow runs"),
        ("Makefile", "holds the `design-check` recipe the job runs"),
    ]
    recipe = module.recipe_text(makefile, "design-check") or ""
    for name in sorted(set(re.findall(r"scripts/[\w.-]+", recipe))):
        out.append((name, "named in the Makefile's `design-check` recipe"))

    if exists(PLAYWRIGHT_CONFIG):
        code = _blank_ts_comments(read(PLAYWRIGHT_CONFIG))
        out.append((rel(PLAYWRIGHT_CONFIG), "Playwright's config"))
        test_dir = _TESTDIR_RE.search(code)
        if test_dir:
            out.append((_app_relative(test_dir.group(1)).rstrip("/") + "/", "Playwright's `testDir`"))
        for literal in _RELATIVE_LITERAL_RE.findall(code):
            target = _import_target(literal, tracked)
            if target in tracked:
                out.append((target, f"named in app/playwright.config.ts as `{literal}`"))
            elif not target.startswith("app/"):
                out.append((target, f"named in app/playwright.config.ts as `{literal}`, outside app/"))

    if exists(VITE_CONFIG):
        code = _blank_ts_comments(read(VITE_CONFIG))
        out.append((rel(VITE_CONFIG), "Vite's config"))
        root = _VITE_ROOT_RE.search(code)
        root_dir = _app_relative(root.group(1)) if root else "app"
        out.append((root_dir.rstrip("/") + "/", "Vite's root, which is what the dev server serves"))
        for literal in _RELATIVE_LITERAL_RE.findall(code):
            target = _import_target(literal, tracked)
            if not target.startswith("app/"):
                out.append((target, f"named in app/vite.config.ts as `{literal}`, outside app/"))

    for anchor, why in (("app/index.html", "the page Vite serves"),
                        ("app/package.json", "the `dev` and `design-check` scripts and the pins"),
                        ("app/package-lock.json", "what `npm ci` installs, Playwright included")):
        out.append((anchor, why))

    for path in _walk(APP_TESTS, (".ts",)) + _walk(APP_SRC, (".ts", ".tsx")):
        for literal in _repo_literals(read(path), tracked):
            out.append((literal, f"read by {rel(path)}"))
    return out


def check_browser_scope(report: Report) -> None:
    """`scripts/browser-scope.py:SCOPE` against what the browser suite loads, both ways (D141).

    MECHANICAL: a dependency the scope does not cover is a class of change the browser matrix
    has silently stopped running for, and an entry covering nothing tracked is a pattern that
    was renamed away. Neither is a judgement. The wiring findings are the same kind — the
    fail-open spelling either is in the `if:` or it is not.
    """
    if not exists(BROWSER_SCOPE_SCRIPT):
        report.add("browser scope", MECHANICAL, [Finding(
            rel(BROWSER_SCOPE_SCRIPT),
            "does not exist, and `.github/workflows/check.yml` gates its browser matrix on it.")])
        return
    if not exists(CHECK_WORKFLOW):
        report.add("browser scope", MECHANICAL, [Finding(
            rel(CHECK_WORKFLOW), "does not exist, so nothing consults the scope list.")])
        return
    module = _sibling("browser-scope.py")
    scope = literals_from_module(BROWSER_SCOPE_SCRIPT).get("SCOPE")
    if module is None or not isinstance(scope, tuple) or not scope or not all(
        isinstance(entry, dict) and isinstance(entry.get("path"), str) for entry in scope
    ):
        report.add("browser scope", MECHANICAL, [Finding(
            rel(BROWSER_SCOPE_SCRIPT),
            "`SCOPE` is not a tuple of `{\"path\": …}` literals this row can read, or the\n"
            "  module does not import. A list nothing can read gates nothing knowingly.")])
        return

    findings: List[Finding] = []
    tracked = _tracked_paths()
    makefile = read(ROOT / "Makefile") if exists(ROOT / "Makefile") else ""

    def covered(path: str) -> bool:
        return any(module.matches(str(entry["path"]), path) for entry in scope)

    for entry in scope:
        pattern = str(entry["path"])
        if not any(module.matches(pattern, path) for path in tracked):
            findings.append(Finding(rel(BROWSER_SCOPE_SCRIPT), (
                f"`{pattern}` matches nothing tracked. A pattern that covers nothing is one\n"
                "  that was renamed away, and the class of change it named now runs no browser.")))
        within = entry.get("within")
        if within is not None:
            kind, _, target = str(within).partition(":")
            if kind != "recipe":
                findings.append(Finding(rel(BROWSER_SCOPE_SCRIPT), (
                    f"`{pattern}` narrows with `{within}`, which is not a narrowing the\n"
                    "  classifier knows; it will count the whole file, which is safe and unmeant.")))
            elif module.recipe_text(makefile, target) is None:
                findings.append(Finding(rel(BROWSER_SCOPE_SCRIPT), (
                    f"`{pattern}` is narrowed to the `{target}` recipe, and the Makefile has no\n"
                    "  such rule. The classifier answers RUN for every Makefile change until it does.")))

    required = _browser_requirements(module, tracked, makefile)
    seen: Set[str] = set()
    for path, why in required:
        if path in seen:
            continue
        seen.add(path)
        if path.endswith("/"):
            files = [p for p in tracked if p.startswith(path)]
            if not files:
                findings.append(Finding(rel(BROWSER_SCOPE_SCRIPT), (
                    f"the suite depends on `{path}` ({why}) and nothing tracked is under it.")))
                continue
            missing = [p for p in files if not covered(p)]
            if missing:
                findings.append(Finding(rel(BROWSER_SCOPE_SCRIPT), (
                    f"`{path}` is {why}, and {len(missing)} of its {len(files)} tracked files are\n"
                    f"  outside SCOPE — first: `{missing[0]}`. A change there would run no browser.")))
        elif not covered(path):
            findings.append(Finding(rel(BROWSER_SCOPE_SCRIPT), (
                f"`{path}` is {why}, and no SCOPE entry covers it. A change to it would run\n"
                "  no browser, and the green would be believed.")))

    for where, message in browser_gate_findings(read(CHECK_WORKFLOW)):
        findings.append(Finding(where, message))

    report.add("browser scope", MECHANICAL, findings,
               f"{len(scope)} entries cover {len(seen)} derived dependencies, read fail-open",
               scanned=len(scope))


def check_check_census(report: Report) -> None:
    """Every published list of what `make check` runs, against scripts/checks.py.

    MECHANICAL, on `route census`'s reasoning exactly: the recipe is in the repository, the
    sentence is in the repository, and they agree or they do not.

    THIS ROW HAS A LIVE DEFENDANT. `make help` said `harness + docs-audit + the self-tests +
    lint + typecheck` from the day `port-agreement` landed until this row was written — five
    targets running and invisible from the front door, while CLAUDE.md two files over carried
    the full list and noted that *the line above said five of them for months*. Nothing
    compared the two, so the note aged into a description of a defect that was still there.

    IT REFUSES TO GO QUIET, which is `route census`'s hard-won half: an anchor that matches
    nothing in a watched file is reported as an unwatched claim. A check that silently stops
    covering prose is the failure it exists to end, and rewording is how that happens.

    **ORDER, AS OF 2026-09-12, AND THE ROW HAD ALREADY BEEN CITED AS PROOF OF IT.** Both
    claims were parsed into an ORDERED list and then compared as SETS. Commit a6287cb
    reordered the `check:` recipe and `scripts/checks.py` — the product first, the guards'
    selftests last, which is the entire content of D161 — and left both publications in the
    pre-reorder order. Its own message cited this row's "2 lists of 23" as verification. The
    row was green through it and stayed green afterwards, because every member was still
    present.

    The order is what a reader takes from the list: a session reading either publication
    learns which check runs first and therefore which failure hides the rest. `check
    registry` has compared the registry's sequence against the recipe since it was written;
    this is the same comparison one publication further out, and it costs nothing.

    **THE RECIPE IS THE AUTHORITY, not `scripts/checks.py`.** The row's own message has
    always said "recount from the `check:` recipe", and the registry is a parallel
    declaration that can itself be wrong — `check registry` is what holds it honest. If the
    recipe cannot be read at all, the registry stands in and the summary says which.
    """
    loaded = _checks_registry()
    if loaded is None:
        report.add("check census", MECHANICAL, [Finding(
            rel(CHECKS_REGISTRY), "CHECKS could not be read; see the `check registry` row.")])
        return
    entries, _ = loaded
    recipe = _check_recipe()
    expected = recipe if recipe else [str(entry.get("target", "")) for entry in entries]
    authority = "the `check:` recipe" if recipe else "scripts/checks.py"

    findings: List[Finding] = []
    checked = 0
    for name in _CHECK_CLAIM_DOCS:
        target = ROOT / name
        if not exists(target):
            findings.append(Finding(name, "does not exist, and it publishes what `make check` runs."))
            continue
        text = _check_claim_text(target)
        anchors = list(_CHECK_CLAIM_RE.finditer(text))
        if not anchors:
            findings.append(Finding(name, (
                "publishes no list of what `make check` runs that this row can see.\n"
                "  Either the claim was deleted, or it was reworded past the pattern watching\n"
                "  it. A check that quietly stops covering a sentence is worse than no check."
            )))
            continue
        for anchor in anchors:
            run = _CHECK_LIST_RE.match(text, anchor.end())
            claimed = [token.strip() for token in run.group(0).split("+")] if run else []
            if len(claimed) < 2:
                findings.append(Finding(
                    "{0}:{1}".format(name, text.count("\n", 0, anchor.start()) + 1),
                    "reads as a list of checks and yields none. The pattern needs to move."))
                continue
            checked += 1
            line = text.count("\n", 0, anchor.start()) + 1
            for missing in [t for t in expected if t not in claimed]:
                findings.append(Finding("{0}:{1}".format(name, line), (
                    "`make check` runs `{0}` and this list does not name it.\n"
                    "  Recount from the `check:` recipe; never add one to the end."
                ).format(missing)))
            for extra in [t for t in claimed if t not in expected]:
                findings.append(Finding("{0}:{1}".format(name, line), (
                    "this list names `{0}`, which `make check` does not run."
                ).format(extra)))
            # ORDER, once membership agrees. Reported separately and only then, so a missing
            # target is never also reported as a re-ordering — one defect, one finding.
            if sorted(claimed) == sorted(expected) and claimed != expected:
                first = next(
                    (i for i, (got, want) in enumerate(zip(claimed, expected)) if got != want),
                    0,
                )
                findings.append(Finding("{0}:{1}".format(name, line), (
                    "names every check `make check` runs and NOT IN THE ORDER IT RUNS THEM.\n"
                    "  first disagreement at position {0}: this list says `{1}`, {2} runs `{3}`.\n"
                    "  published: {4}\n"
                    "  running:   {5}\n"
                    "  The order is what a reader takes from the list — which check runs first\n"
                    "  is which failure hides the rest. Recount from {2}."
                ).format(
                    first + 1, claimed[first], authority, expected[first],
                    " + ".join(claimed), " + ".join(expected),
                )))

    report.add("check census", MECHANICAL, findings,
               "{0} published lists, {1} checks each, in {2}'s order".format(
                   checked, len(expected), authority),
               scanned=checked)


# -------------------------------------------------------------- how callers invoke this

# Every file that runs this script as a gate or a build step. Each is checked for flags
# this script does not declare.
INVOKERS = ["Makefile", "scripts/githooks/pre-commit", ".claude/commands/docs-audit.md"]

_INVOCATION_RE = re.compile(r"docs-audit\.py((?:\s+--[a-z][a-z-]*)*)")


def check_audit_invocation(report: Report) -> None:
    """Every flag a caller passes this script must be one this script declares.

    The invocation string in the pre-commit hook is a second, independent decision about
    this script's interface, and nothing reconciled it with the argparse definition. That
    is the repo's recurring failure class — two decisions that must agree, only one of
    which moves — sitting on the commit gate itself.

    The consequence is worse than a broken flag. Renaming or dropping an option makes
    argparse reject the hook's command line, and argparse's own exit code for that is 2 —
    which is this script's ADVISORY code, the one the hook prints and allows. So the gate
    would stop running and report the routine coupling question while doing it. `EXIT_USAGE`
    makes that failure loud; this check makes it not happen.

    Flags only. Reconciling positional arguments or values would mean modelling argparse,
    and this script has none to model.

    **The question is asked of argparse, not of a list scraped out of it.** An earlier draft
    read `parser._actions` — a private attribute, and the coupling of a coupling check. It
    was also wrong: argparse accepts unambiguous abbreviations, so `--stag` really does run
    and set membership would have called it a finding. `parse_known_args` returns unmatched
    optionals in its second element, which IS the property this check is about — would this
    command line be rejected — and it is public API. The declared list below is pulled from
    `format_usage()` for the human message only; nothing decides on it.
    """
    parser = build_parser()

    def rejected(flag: str) -> bool:
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                _, extras = parser.parse_known_args([flag])
            except SystemExit:  # a flag that parses but demands a value
                return True
        return flag in extras

    declared = parser.format_usage().split(":", 1)[-1].strip().replace("\n", " ")
    findings: List[Finding] = []
    for name in INVOKERS:
        path = ROOT / name
        if not exists(path):
            continue
        for number, line in enumerate(read(path).splitlines(), start=1):
            for match in _INVOCATION_RE.finditer(line):
                for flag in match.group(1).split():
                    if rejected(flag):
                        findings.append(
                            Finding(
                                f"{name}:{number}",
                                f"invokes `docs-audit.py {flag}`, which argparse rejects.\n"
                                f"  Accepts: {declared}\n"
                                f"  The invocation would exit {EXIT_USAGE}; a caller "
                                f"reading that as a finding would stop gating.",
                            )
                        )
    # THE EXIT CODES THE ARGUMENT ABOVE RESTS ON, READ OUT OF `main()` RATHER THAN TRUSTED.
    #
    # The docstring's whole case for `_Parser` is a COLLISION: argparse's usage exit is 2, and
    # 2 is this script's advisory code, so an undeclared flag would make the gate stop running
    # while reporting the routine coupling question. That case is only true while `main()`
    # still maps advisory to 2 and `EXIT_USAGE` is something else. Nothing read either, so the
    # override could have outlived its reason with the comment still explaining it.
    #
    # A NOTE ON WHAT THIS IS NOT. The plan that scheduled this row expected it to land red on
    # "exit 2 bound to coupling without `--staged`". That was wrong and is recorded rather
    # than quietly dropped: `check_coupling` is not the only ADVISORY row — `entry budget`,
    # `game coverage` and `views exposure` among others emit one on every plain run — so exit
    # 2 is reachable without `--staged` and always was. The row below pins the collision,
    # which is the fact that was actually unread.
    advisory_code: Optional[int] = None
    try:
        for node in ast.walk(ast.parse(read(SELF))):
            if not (isinstance(node, ast.FunctionDef) and node.name == "main"):
                continue
            for inner in ast.walk(node):
                if not isinstance(inner, ast.IfExp):
                    continue
                orelse = inner.orelse
                if isinstance(orelse, ast.IfExp) and isinstance(orelse.body, ast.Constant):
                    advisory_code = orelse.body.value
    except (SyntaxError, OSError):
        advisory_code = None

    if advisory_code is None:
        findings.append(
            Finding(
                "scripts/docs-audit.py",
                "`main()` no longer maps severities to exit codes in a shape this row can "
                "read. `_Parser` exists because argparse's usage exit collides with the "
                "advisory code; re-point this, or the override outlives its reason.",
            )
        )
    elif advisory_code != 2:
        findings.append(
            Finding(
                "scripts/docs-audit.py",
                f"the advisory exit code is {advisory_code}, not 2, so argparse's default no "
                f"longer collides with it — and `_Parser`'s docstring still says it does. "
                f"Either the override is now unnecessary, or its argument needs rewriting.",
            )
        )
    elif advisory_code == EXIT_USAGE:
        findings.append(
            Finding(
                "scripts/docs-audit.py",
                f"`EXIT_USAGE` is {EXIT_USAGE}, which IS the advisory code. A caller cannot "
                f"tell a broken command line from a routine question, which is the exact "
                f"failure `_Parser` was written to prevent.",
            )
        )

    report.add(
        "audit invocation",
        MECHANICAL,
        findings,
        f"{len(INVOKERS)} callers, flags all declared, usage {EXIT_USAGE} clear of advisory "
        f"{advisory_code}",
        scanned=len(INVOKERS),
    )


# ------------------------------------------------- the checks defined here vs the ones run


SELF = Path(__file__).resolve()

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
        "A HELPER THAT EMITS ON BEHALF OF TWO REAL CHECKS, not a check of its own. "
        "`check_decision_structure` and `check_entry_budget` both iterate the entry files "
        "in docs/decisions/, and both reported `0 entries` in GREEN when the corpus could "
        "not be read — measured by deleting one entry file. This writes the row that says "
        "so, under whichever of those two labels called it, which is why it calls "
        "`report.add` and why `audit()` does not call it. Dispatching it directly would "
        "print a third row nobody asked for; leaving it out of this list would report it "
        "as a check that has never run.",
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


def check_dispatch(report: Report, source: Path = SELF) -> None:
    """Every check defined in this file, against the ones `audit()` actually calls.

    The failure: add a check function, forget the call. It never runs, the report still
    looks full, the hook still passes, and nothing in the repo can say the auditor is
    smaller than it looks. `docs/DEBTS.md` carried that as the one entry where a check can
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
    file the commit will carry rather than the file that is executing — stage a new check
    without its call and the hook fails on it, which is the exact moment `docs/DEBTS.md`
    describes.

    `source` is which file to reconcile: this one in every real run, a fixture under
    `--self-test`. The reader's behavior on a shape it cannot read has to be provable
    without restructuring the live script to find out.
    """
    try:
        tree = ast.parse(read(source))
    except (OSError, SyntaxError) as exc:
        report.add(
            "check dispatch",
            MECHANICAL,
            [
                Finding(
                    rel(source),
                    f"cannot be parsed, so nothing can say which checks this file runs.\n"
                    f"{exc}",
                )
            ],
        )
        return

    checks = defined_checks(tree)
    called = dispatched_names(tree, checks)
    findings: List[Finding] = []

    if called is None:
        findings.append(
            Finding(
                rel(source),
                "defines no `audit()`, which is where this file's checks are dispatched "
                "from and where this row reads them.",
            )
        )
    elif checks and not called:
        findings.append(
            Finding(
                rel(source),
                "`audit()` names none of the checks defined in this file. Either nothing "
                "this script reports is running, or dispatch moved out of `audit()` and "
                "this reader has to move with it.\nReported once rather than once per "
                "check: the fault is in the reading, and a wall of findings would each "
                "name the wrong cause.",
            )
        )
    else:
        for name, line in sorted(checks.items(), key=lambda item: item[1]):
            if name in called or name in UNDISPATCHED:
                continue
            findings.append(
                Finding(
                    f"{rel(source)}:{line}",
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
                    rel(source),
                    f"UNDISPATCHED names `{name}` ({why}), which this file does not define. "
                    f"Renamed or deleted; either way the entry now exempts nothing.",
                )
            )
        elif called and name in called:
            findings.append(
                Finding(
                    rel(source),
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
                    f"scripts/docs-audit.py -> {row.check}",
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
                    f"scripts/docs-audit.py -> {row.check}",
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
                    f"scripts/docs-audit.py -> {row.check}",
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
                    "scripts/docs-audit.py -> EXPECTED_EMPTY",
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


# ------------------------------------------------------------------ Layer 2: coupling


def git(*args: str) -> str:
    try:
        done = subprocess.run(
            ["git"] + list(args),
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return ""
    return done.stdout.decode("utf-8", errors="replace")


def staged_changes() -> Dict[str, int]:
    """Staged path -> lines changed. The staged set, never mtimes or commit dates.

    A "doc older than the code" heuristic reads plausible and does not survive contact
    with this repo: markdown gets edited in the same working session as the code it
    describes, so timestamps say nothing about whether the prose kept up.

    **`--no-renames`, and `-z`, both for the same reason.** Left to itself git reports a
    staged rename as one record whose path field is the combined form `docs/{old => new}.md`,
    which is not a path and matches nothing — so a renamed doc was audited by no check at
    all and the run reported clean. `--no-renames` splits it into the add and the delete,
    and `--diff-filter=ACMR` keeps the add: the new path, which is the one that needs
    auditing. `-z` drops git's quoting of unusual names, so the field is always a real path.
    """
    changes: Dict[str, int] = {}
    raw = git("diff", "--cached", "--numstat", "-z", "--no-renames", "--diff-filter=ACMR")
    for record in raw.split("\0"):
        if not record:
            continue
        parts = record.split("\t")
        if len(parts) != 3:
            continue
        added, removed, path = parts
        if added == "-" or removed == "-":  # binary
            changes[path] = 0
            continue
        changes[path] = int(added) + int(removed)
    return changes


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


# ---------------------------------------------------------- identifier spelling (D60)
#
# ONE SPELLING FOR EVERY NAME A SESSION CAN SEARCH FOR. The owner ruled on 2026-09-11 (D60,
# amended) that identifiers are spelled American across the whole repository, and that prose
# and comments are NOT governed here. The reasoning is the difference between reading and
# searching: a model reads `artefact` and `artifact` as one word, and a grep does not. Measured
# before the ruling: 119 British identifiers in 24 files, beside 951 `fulfill`, 868 `catalog`
# and 1,405 `color` — so `_artefacts` was unfindable by the word every other file used, and
# `Fulfillment.tsx` sat over a table spelled `fulfilment`. Comments and docstrings held 869
# British words in 169 files and were left alone: a rewrite there is churn against five open
# branches for no search a session runs.
#
# IDENTIFIERS ONLY, BY CONSTRUCTION. Comments, docstrings, string and template literals, regex
# literals and JSX text are blanked before a token is read, byte for byte so line numbers
# survive. Vale keeps its advisory watch over markdown (`.vale.ini`), which this row never
# reads. A British word that reaches this row is therefore a NAME — a function, a variable, a
# class, a key spelled as an attribute, a CSS class or custom property, a shell variable.
#
# THE -ISE LIST IS CLOSED, DELIBERATELY. An open `\w+ise` pattern flags `raise`, `Promise`,
# `otherwise`, `pairwise` and `exercise`, every one of them -ise in American English too; a
# closed stem list can miss a British verb it has not met, and a miss is the cheaper error on
# a row that blocks a commit. The stems are what this tree showed plus the common programming
# verbs. Add one when a name shows it.
#
# THE ALLOW-LIST IS BY NAME AND CARRIES ITS REASON, and each entry is a name the owner ruled
# out of scope on 2026-09-11 because a rename there is a migration and not a spelling.
SPELLING_SUFFIXES = (".py", ".ts", ".tsx", ".mjs", ".sh", ".css")

# Lower-cased identifier fragment -> why it is allowed. Matched as a substring of the whole
# lower-cased name, so `is_catalogued`, `NotCatalogued` and `_parse_fulfilment` are covered
# by the stem they carry rather than listed one by one — the owner's ruling was that the
# relatives of a wire name stay with it so one file is never split between spellings.
SPELLING_ALLOWED: Dict[str, str] = {
    "catalogued": (
        "the game registry key in pipeline/games.py, a field on the wire in GET /games "
        "(app/src/types.ts declares it) and the stem of the `not_catalogued` reason code; "
        "a rename is a wire change and a reason-code migration, not a spelling (D60, "
        "2026-09-11)"
    ),
    "fulfilment": (
        "a table in inventory/store.sqlite (store/db.py) and the ledger payload key the "
        "legacy-JSON migration reads (store/orders.py); a rename is a store migration under "
        "D88, not a spelling (D60, 2026-09-11)"
    ),
    "labelledby": "`aria-labelledby` is the DOM's own attribute name, spelled by the platform",
}

_ISE_STEMS = (
    "alphabet|anonym|apolog|author|canonical|capital|categor|central|character|civil|colon|"
    "critic|custom|digit|ellips|emphas|energ|equal|external|famil|final|formal|general|global|"
    "harmon|human|hypothes|ideal|immun|initial|internal|item|legal|linear|local|magnet|"
    "material|maxim|mechan|memo|memor|minim|mobil|modern|modular|monet|national|neutral|"
    "normal|optim|organ|oxid|parallel|parameter|parenthes|personal|polar|popular|priorit|"
    "public|quant|random|raster|rational|real|recogn|regular|sanit|scrutin|serial|social|"
    "special|stabil|standard|steril|summar|symbol|synchron|synthes|token|trivial|urban|util|"
    "vapor|vector|verbal|virtual|visual|vocal"
)
_ISE_PREFIX = r"(?:un|re|de|dis|non|pre|auto|mis|over|under)?"

# (pattern over ONE lower-cased word of a name, replacement). The replacement is the
# American form of the matched fragment, so the message can name it.
_BRITISH_FRAGMENTS: Tuple[Tuple["re.Pattern[str]", str], ...] = tuple(
    (re.compile(pattern), american)
    for pattern, american in (
        (r"artefact", "artifact"),
        (r"colour", "color"),
        (r"behaviour", "behavior"),
        (r"honour", "honor"),
        (r"centre", "center"),
        (r"licence", "license"),
        (r"grey", "gray"),
        (r"cataloguing", "cataloging"),
        (r"catalogue", "catalog"),
        (r"favour", "favor"),
        (r"neighbour", "neighbor"),
        (r"judgement", "judgment"),
        (r"defence", "defense"),
        (r"offence", "offense"),
        (r"acknowledgement", "acknowledgment"),
        (r"programme(?![rd])", "program"),
        (r"fulfil(?!l)", "fulfill"),
        (r"cancell(?!ation)", "cancel"),
        (r"aluminium", "aluminum"),
        (r"analys(e|ed|es|ing|er|ers)$", r"analyz\1"),
        (r"paralys(e|ed|es|ing)$", r"paralyz\1"),
        (r"(label|model|travel|signal|total|level|channel|fuel|dial|pencil|marshal)l(ed|ing)$", r"\1\2"),
        (r"^(" + _ISE_PREFIX + r"(?:" + _ISE_STEMS + r"))is(e|es|ed|er|ers|ing|ation|ations|able)$", r"\1iz\2"),
    )
)

_NAME_WORDS = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+")
_JS_REGEX_WORDS = {"return", "typeof", "case", "do", "else", "in", "instanceof", "new", "throw", "void", "delete", "yield", "await"}


def british_spelling(name: str) -> Optional[Tuple[str, str]]:
    """(british word, american word) for the first British fragment in an identifier, or None.

    The name is split into words at `_`, `-`, `$`, digits and camelCase boundaries, so
    `fetchCatalogueRows` and `NEIGHBORLY` are both read, and each fragment pattern sees one
    lower-cased word at a time — which is what lets `$` anchors mean the end of a WORD.
    """
    lowered = name.lower()
    if any(allowed in lowered for allowed in SPELLING_ALLOWED):
        return None
    for word in _NAME_WORDS.findall(name):
        low = word.lower()
        for pattern, american in _BRITISH_FRAGMENTS:
            if pattern.search(low):
                return low, pattern.sub(american, low, count=1)
    return None


def _blank(text: str) -> str:
    """Every character but a newline replaced by a space: positions and lines survive."""
    return re.sub(r"[^\n]", " ", text)


def _js_code_only(text: str) -> str:
    """A .ts/.tsx/.mjs file with every comment, string, template and regex literal blanked.

    A real lexer rather than TS_COMMENT's regex, because a `//` inside a string is not a
    comment and a quote inside a regex is not a string — and either misreading would expose
    part of a literal as code, which is the one error this row must not make. Blanking is
    byte-for-byte so a finding's line number is the file's. A template literal's `${...}`
    expressions are code and are kept, recursively, so `${humanise(x)}` is read.

    The regex-or-division question is answered the way every JS lexer answers it: by the
    token before the slash. `<` is deliberately NOT in the set — a closing JSX tag `</p>`
    read as a regex swallowed the rest of the line, which is how the first draft of this
    reader lost every closing tag in `app/src/Fulfillment.tsx` and read its text as names.
    Nor is `}`: `size={16} />` is a self-closing tag, and the draft read `/>}` as a regex
    and never saw the element close.
    """
    out: List[str] = []
    i, n = 0, len(text)
    last = ""  # last significant character, for the regex-or-division question
    last_at = -1
    last_word = ""
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(_blank(text[i:j]))
            i = j
            continue
        if c == "/" and nxt == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(_blank(text[i:j]))
            i = j
            continue
        if c in "'\"":
            j = i + 1
            while j < n and text[j] not in (c, "\n"):
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(_blank(text[i:j]))
            i, last, last_at = j, c, j - 1
            continue
        if c == "`":
            j, spans = _template_end(text, i)
            piece = list(_blank(text[i:j]))
            for a, b in spans:  # the `${...}` expressions, lexed on their own
                piece[a - i:b - i] = list(_js_code_only(text[a:b]))
            out.append("".join(piece))
            i, last, last_at = j, c, j - 1
            continue
        arrow = last == ">" and last_at > 0 and text[last_at - 1] == "="
        if c == "/" and (
            last == "" or last in "(,=:[!&|?{;+-*%~^" or arrow or last_word in _JS_REGEX_WORDS
        ):
            j = i + 1
            in_class = False
            while j < n and text[j] != "\n":
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == "[":
                    in_class = True
                elif text[j] == "]":
                    in_class = False
                elif text[j] == "/" and not in_class:
                    break
                j += 1
            j = min(j + 1, n)
            while j < n and text[j].isalpha():  # flags
                j += 1
            out.append(_blank(text[i:j]))
            i, last, last_at = j, "/", j - 1
            continue
        out.append(c)
        if not c.isspace():
            if c.isalnum() or c in "_$":
                last_word = last_word + c if last and (last.isalnum() or last in "_$") else c
            last, last_at = c, i
        i += 1
    return "".join(out)


def _template_end(text: str, start: int) -> Tuple[int, List[Tuple[int, int]]]:
    """(index after the closing backtick, [(a, b) of each `${...}` expression's inside]).

    Walks the template from its opening backtick. An expression is code and may itself hold
    strings, comments and nested templates, so its end is found by lexing it — a brace inside
    a nested string is not its closer.
    """
    n = len(text)
    spans: List[Tuple[int, int]] = []
    i = start + 1
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "`":
            return i + 1, spans
        if c == "$" and i + 1 < n and text[i + 1] == "{":
            j = i + 2
            depth = 0
            while j < n:
                d = text[j]
                if d in "'\"":
                    k = j + 1
                    while k < n and text[k] not in (d, "\n"):
                        k += 2 if text[k] == "\\" else 1
                    j = k + 1
                    continue
                if d == "`":
                    j, _ = _template_end(text, j)
                    continue
                if d == "{":
                    depth += 1
                elif d == "}":
                    if depth == 0:
                        break
                    depth -= 1
                j += 1
            spans.append((i + 2, min(j, n)))
            i = j + 1
            continue
        i += 1
    return n, spans


def _jsx_text_blanked(code: str) -> str:
    """JSX children text blanked out of a .tsx file whose literals are already blank.

    A small state machine rather than a regex, because `>` and `<` are also comparison and
    generic-parameter delimiters: a `<` opens a tag only when the character right before it
    is not part of a name (`useState<T>` is a generic, `return <div>` is a tag) and the
    character after it begins a tag name, a `/`, or a fragment. Inside an element's children,
    text runs to the next `<` or `{`; a `{...}` child is code again, to its matching brace.
    A misjudged tag costs recall, never a false finding: the only thing this can do to code
    is blank it.
    """
    out = list(code)
    n = len(code)
    stack: List[Tuple[str, int]] = [("js", 0)]  # ("js", brace depth) | ("jsx", 0)
    i = 0

    def tag_end(start: int) -> Tuple[int, bool, bool]:
        """(index after the tag's `>`, is_closing, is_self_closing) for a tag at `start`."""
        closing = code.startswith("</", start)
        depth = 0
        j = start + 1
        while j < n:
            ch = code[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth = max(0, depth - 1)
            elif ch == ">" and depth == 0:
                return j + 1, closing, code[j - 1] == "/"
            j += 1
        return n, closing, False

    def _generic_not_tag(at: int, end: int) -> bool:
        """`<T,>(x)` and `write: <T>(run)` are type-parameter lists, not elements. A tag
        header never holds a bare comma, and an element is never followed by `(`."""
        header = code[at:end]
        depth = 0
        for ch in header:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            elif ch == "," and depth == 0:
                return True
        after = end
        while after < n and code[after] in " \t":
            after += 1
        return after < n and code[after] == "("

    def opens_tag(at: int) -> bool:
        before = code[at - 1] if at > 0 else " "
        after = code[at + 1] if at + 1 < n else ""
        if before.isalnum() or before in "_$)]":
            return False
        return after.isalpha() or after in "/>_$"

    while i < n:
        state, depth = stack[-1]
        c = code[i]
        if state == "js":
            if c == "{":
                stack[-1] = (state, depth + 1)
            elif c == "}":
                if depth == 0 and len(stack) > 1:
                    stack.pop()
                else:
                    stack[-1] = (state, max(0, depth - 1))
            elif c == "<" and opens_tag(i):
                end, closing, selfclosing = tag_end(i)
                if _generic_not_tag(i, end):
                    i += 1
                    continue
                if not closing and not selfclosing:
                    stack.append(("jsx", 0))
                i = end
                continue
            i += 1
            continue
        # jsx children
        if c == "{":
            stack.append(("js", 0))
            i += 1
            continue
        if c == "<":
            end, closing, selfclosing = tag_end(i)
            if closing:
                stack.pop()
            elif not selfclosing:
                stack.append(("jsx", 0))
            i = end
            continue
        j = i
        while j < n and code[j] not in "<{":
            j += 1
        for k in range(i, j):
            if code[k] != "\n":
                out[k] = " "
        i = j
    return "".join(out)


def _shell_code_only(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        if line.lstrip().startswith("#!"):
            lines.append(_blank(line))
            continue
        line = re.sub(r"'[^']*'|\"[^\"]*\"", lambda m: _blank(m.group(0)), line)
        line = re.sub(r"(^|\s)#(?!\{).*$", lambda m: m.group(1) + _blank(m.group(0)[len(m.group(1)):]), line)
        lines.append(line)
    return "\n".join(lines)


def _css_code_only(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", lambda m: _blank(m.group(0)), text, flags=re.S)
    return re.sub(r"'[^'\n]*'|\"[^\"\n]*\"", lambda m: _blank(m.group(0)), text)


_PY_NAME = re.compile(r"(?<![\w.])[A-Za-z_]\w*")
_JS_NAME = re.compile(r"[A-Za-z_$][\w$]*")
_CSS_NAME = re.compile(r"-{0,2}[A-Za-z_][\w-]*")


def spelling_findings(text: str, suffix: str) -> List[Tuple[int, str, str, str]]:
    """(line, name, british word, american word) for every British identifier in one file's
    text. `suffix` picks the reader; an unknown suffix is read as nothing."""
    found: List[Tuple[int, str, str, str]] = []
    if suffix == ".py":
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
        except (tokenize.TokenError, SyntaxError, IndentationError):
            tokens = []
        for tok in tokens:
            if tok.type == tokenize.NAME and not keyword.iskeyword(tok.string):
                hit = british_spelling(tok.string)
                if hit:
                    found.append((tok.start[0], tok.string, hit[0], hit[1]))
        return found
    if suffix in (".ts", ".tsx", ".mjs"):
        code = _js_code_only(text)
        if suffix == ".tsx":
            code = _jsx_text_blanked(code)
        pattern = _JS_NAME
    elif suffix == ".sh":
        code = _shell_code_only(text)
        pattern = _JS_NAME
    elif suffix == ".css":
        code = _css_code_only(text)
        pattern = _CSS_NAME
    else:
        return found
    for match in pattern.finditer(code):
        hit = british_spelling(match.group(0))
        if hit:
            found.append((code.count("\n", 0, match.start()) + 1, match.group(0), hit[0], hit[1]))
    return found


SHELL_SUFFIXES = (".sh",)
SHELL_EXTRA = ("scripts/githooks/pre-commit", "scripts/githooks/pre-push",
               "scripts/githooks/post-merge", "scripts/githooks/post-checkout",
               "scripts/githooks/reference-transaction")

_DQ = re.compile(r'"(?:[^"\\]|\\.)*"')


def shell_substitution_findings(text: str):
    """Unescaped backticks inside a double-quoted shell string — command substitution."""
    for number, line in enumerate(text.split("\n"), 1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        for match in _DQ.finditer(line):
            body = match.group(0)
            # A backtick the author escaped is a literal and is what every other site here does.
            if re.search(r'(?<!\\)`', body):
                yield number, body.strip()


def check_shell_substitution(report: Report) -> None:
    """A backtick inside a double-quoted shell string RUNS, and every other site here escapes it.

    **Blocking, on D16's test: this is mechanical and there is nothing to judge.** A backtick
    inside double quotes is command substitution, so a message that names a command EXECUTES
    it. `bash -n` is silent — the line is valid shell, it simply does something else.

    **It is kept for one measured incident.** `scripts/reap-selftest.sh:216` carried
    `bad "refused without naming `` `make down` ``, ..."` on a failure path. On the primary
    checkout `make down` stops the capture server `make launch-agent` keeps alive over the
    owner's real store, so a FAILING assertion in the test suite would have taken the owner's
    server down as a side effect of printing why it failed. It fires only when that arm fails,
    which is why it survived every green run; the arm failed repeatedly on 2026-09-11 from an
    unrelated flake.

    **Twelve other sites in this repo already spell it `` \\` ``** — the rule was understood
    everywhere but one line, which is exactly the shape a mechanical check is for.

    **What it cannot see.** A backtick in a heredoc body (not a double-quoted string), and a
    deliberate substitution someone wrote in the modern `$(...)` form, which this never flags.
    """
    findings: List[Finding] = []
    scanned = 0
    paths = list(_walk(ROOT, SHELL_SUFFIXES))
    for extra in SHELL_EXTRA:
        candidate = ROOT / extra
        if candidate.exists():
            paths.append(candidate)
    for path in paths:
        scanned += 1
        for line, body in shell_substitution_findings(read(path)):
            findings.append(
                Finding(
                    f"{rel(path)}:{line}",
                    f"a backtick inside a double-quoted string RUNS as command "
                    f"substitution: {body[:90]}. Escape it (\\`) or single-quote the "
                    f"string. `bash -n` cannot see this — the line is valid shell.",
                )
            )
    report.add(
        "shell substitution",
        MECHANICAL,
        findings,
        f"{len(findings)} unescaped backtick(s) in a double-quoted shell string" if findings
        else f"no double-quoted shell string in {scanned} files runs a command by accident",
        scanned=scanned,
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
PROSE_ONLY_EXPECTED = 6

# BOLD, AND THAT IS NOT COSMETIC. The sentinel has to be a DECLARATION, so it is matched as
# the bold run a rule writes it in — otherwise the rule immediately above, which explains the
# sentinel and quotes it in backticks, would read as having claimed one, and rule 0 would
# count itself as prose. A check that miscounts its own author is not a check.
NOT_MECHANIZED = "**NOT MECHANIZED:**"
_ARGUMENT_MIN_WORDS = 12

# THE ALLOWLIST IS KEYED BY (path, function, shape) AND NEVER BY LINE NUMBER, because a
# line number moves the day somebody edits an unrelated docstring above it and the guard
# would then fail on a site that did not change. `shape` disambiguates a function that
# makes more than one kind of unscoped call (store/master.py's `to_payload` calls
# `.items()` on `self.cards`, `self.boxes` AND `self.listings` — only the `cards` one is
# on this list, matched by `shape="items"` restricted to the `.cards` chain in the
# matcher itself, never by which `.items()` call comes first in the function body).
#
# TAKEN 2026-09-12, docs/specs/store-scaling.md §4, PLUS TWO. `do_inventory`'s
# `to_payload()` call is kept here PERMANENTLY, on the owner's word recorded in
# docs/specs/store-scaling/00-phases.md ("do_inventory is kept, unused, on the
# allowlist") — §4's own table says "Removed by: item 2" for that row and that line is
# stale; the correction lives here and in 00-phases.md, not in store-scaling.md itself.
#
# `store/master.py:next_box_number`'s `.distinct("box")` IS A THIRTEENTH SITE THE
# PLAYBOOK'S OWN CENSUS MISSED — this scanner found it the first time it ran against the
# real tree (docs/specs/store-scaling/01-guard.md's "Call sites" table names twelve and
# §4's table agrees). It is the same shape as `do_boxes`/`counts` right above and below
# it in this list: one indexed column, read once per box CREATION rather than per load or
# per press, which is cheaper than either of those two already-permanent entries. Kept
# here permanently for the same reason they are — the guard names it and moves on — and
# the count is 13, not 12, because the tree already had this site on 2026-09-12; nothing
# added it, this row's own scan just found what the hand census did not.
#
# THIS COUNT MAY ONLY GO DOWN FROM HERE, same rule as `PROSE_ONLY_EXPECTED` above: an item
# that removes a full-table read deletes its tuple from UNSCOPED_WALK_ALLOWED and lowers
# UNSCOPED_WALK_EXPECTED in the SAME commit, or the row reports a stale allowlist entry
# (site not found) rather than silently shrinking. An item that cannot yet remove its
# site for some reason must not touch the count.
#
# STORE-SCALING ITEM 4 REPLACED ONE ENTRY WITH ANOTHER RATHER THAN REMOVING ONE. `_copies_
# out` and `_committed_keys` (`cli/resolve.py`) used to each call `Inventory.positions_for_
# sku`/`copies_not_sold`/`sales_before`/`copies_on_hand` once PER SKU — none of those are
# `.select()`/`.distinct()` on `.cards` directly (they are `Rows.where(sku=sku)` calls one
# level down in `store/master.py`, invisible to this scanner, which is exactly the cost
# `docs/specs/store-scaling/04-copies-out.md` names: the guard sees shapes on the page, not
# runtime cost). The fix is `cli/resolve.py:_cards_by_sku`, ONE deliberate `.select()` with
# no keyword filter — genuinely unscoped by this scanner's own rule, and genuinely cheap for
# the same reason `store/master.py:counts` is: one pass, once per request, never once per
# listing. `server/pipeline_routes.py:_unsent_ledger` also used to run its own `distinct
# ("sku")` scan (the removed entry below) to find SKUs no run's table names; it now shares
# the SAME `_cards_by_sku` dict instead of scanning `cards` a second time, so that site is
# gone rather than merely rewritten. One new site, one old site removed: the count nets to
# zero and stays 13.
#
# STORE-SCALING ITEM 7 REMOVES THREE SITES OUTRIGHT AND RENAMES TWO MORE, WHICH IS NOT THE
# FIVE-SITE REMOVAL THE SPEC'S OWN PLAYBOOK CLAIMED. `_release_plan`, `_box_names` and
# `_on_hand_by_run` are genuinely gone — each now reads through an indexed `equals` filter
# (`box=`, `sku=` or `run=`) with no unscoped call left in the function at all.
# `do_pipeline_value` and `cli/resolve.py:box_views`, by contrast, each front a genuinely
# STORE-WIDE aggregate that D159 requires (a percentile/cut-off ranking over every on-hand
# card; a box-coordinate walk with no bound to offer) — moving the per-row cost off `Card`
# construction and onto a column-only `select()` does not remove the unscoped CALL, it only
# renames the (function, shape) tuple the scanner reports: `do_pipeline_value`'s walk moved
# into a new shared helper, `_value_rows` (`.select()`, no keywords — still a full-table
# read, by design, since the aggregates have to touch every row); `box_views`'s UNBOUNDED
# branch (`boxes=None`, still every existing caller's default) still runs an unscoped
# `.select()` where it used to run `.values()` — same function, new shape. Verified by
# running `unscoped_walk_sites` against the built tree rather than assumed: it reports
# exactly these ten tuples, and the two `do_pipeline_value`/`box_views` rows the item's own
# spec file listed as "removed" are not among them — this comment and the tuple set below
# are the correction, made in the same commit per this row's own rule ("say why the shape
# changed and update the tuple" rather than leaving a stale entry).
UNSCOPED_WALK_ALLOWED: FrozenSet[Tuple[str, str, str]] = frozenset({
    # (path relative to ROOT, enclosing function name, shape)
    ("server/capture_server.py", "do_inventory", "to_payload"),   # kept permanently — owner's word
    ("server/capture_server.py", "_boxes_named", "distinct"),
    ("server/capture_server.py", "do_boxes", "distinct"),
    ("server/pipeline_routes.py", "_value_rows", "select"),   # store-scaling item 7 — renamed from `do_pipeline_value`'s `.values()`; the aggregate pass is unavoidably store-wide (D159), so the CALL survives, only its shape and enclosing function change
    ("store/master.py", "to_payload", "items"),
    ("store/master.py", "counts", "select"),
    ("store/master.py", "next_box_number", "distinct"),   # kept permanently — one indexed column, cheap; missed by the hand census
    ("cli/resolve.py", "box_views", "select"),   # store-scaling item 7 — renamed from `.values()`; the unbounded (`boxes=None`) branch every existing caller still uses is genuinely store-wide, for the same reason `_value_rows` is
    ("cli/resolve.py", "_cards_by_sku", "select"),   # store-scaling item 4 — one pass, replaces per-SKU `_copies_out`/`_committed_keys`/`_unsent_ledger` reads; the `_unsent_ledger` distinct scan above is deleted, not merely moved
    ("server/capture_server.py", "do_inventory_copies", "select"),   # docs/DEBTS.md §27, site 1 — a NEW full-table scan, added rather than removed, and named as a cost paid: `POST /inventory/copies` replaces `Orders.tsx`'s `GET /inventory` (D192's own site 1), and the one unfiltered `_cards_by_sku`-shaped pass here is what lets the box set handed to `_Places.for_keys` be DERIVED from the scan rather than guessed at from the request — the docstring on the function has the full argument for why that is sound where box-scoping the walk itself is not. This is the count going UP by one, on purpose, for a route this file's own item 1 could not have existed to forbid before it existed to write.
})
# STORE-SCALING ITEM 8 REMOVED `do_search`'s ROW: the O(cards) walk over
# `inventory.cards.values()` is deleted, replaced by an FTS5 `MATCH` query
# (`store/db.py:_add_search_index`) that narrows the candidate set before `_match_rank` ever
# runs. Item 7 (phase 2, disjoint functions) landed first and had already removed
# `_release_plan` outright (it now reads through an indexed `equals` filter) and renamed
# `do_pipeline_value`/`box_views` — origin/main's own count was 10 at that point. This merge
# takes main's allowlist and removes only `do_search`: 10 -> 9.
#
# 9 -> 10, THE ONE DIRECTION THIS PIN HAS NEVER MOVED BEFORE, AND IT IS SAID PLAINLY RATHER
# THAN QUIETLY. `POST /inventory/copies` (`do_inventory_copies`) is a NEW full-table scan,
# closing `docs/DEBTS.md` §27 site 1 (`Orders.tsx`'s `GET /inventory`) by replacing a whole-
# store WIRE PAYLOAD with a whole-store SERVER-SIDE scan that answers only the requested
# SKUs — the cost moves, it does not disappear, and this row exists precisely to keep that
# honest. It earns its own allowlist entry rather than folding into an existing one, because
# it is a genuinely new site even though its shape (one unfiltered `.select()`) matches
# `_cards_by_sku`'s — see that entry's own comment, above, for why one unfiltered scan is
# the correct implementation here rather than a shortcut around scoping it.
UNSCOPED_WALK_EXPECTED = 10

_ROW_NAME_RE = re.compile(r'report\.add\(\s*\n?\s*"([^"\n]+)"')
_MECH_PATHS = ("scripts/", "harness/tests/", "app/tests/", "app/eslint.config.js", "ruff.toml",
               ".claude/settings.json", ".codex/hooks.json", ".github/workflows/")


def audit_row_names() -> Set[str]:
    """Every row name this file registers, read out of its own source.

    Self-referential on purpose: a rule that cites `` `raw color` `` as its enforcement is
    citing a row, and the only authority on which rows exist is the file that adds them. A
    hand-kept list here would be a second enumeration of the same thing, which is the drift
    `check census` already exists to catch one level up.
    """
    return set(_ROW_NAME_RE.findall(read(Path(__file__))))


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
    with `>/dev/null 2>&1`. `docs/DEBTS.md` §11 carried a sentence about two observed mutation
    failures that were measured false on both counts. `screen-freshness --self-test` exited 1
    on main while sitting on no make target and printing *"run --self-test"*. Against that:
    `raw color`, `storage keys`, `route census`, `check census`, `codex hooks`, `id claims`
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


def check_identifier_spelling(report: Report) -> None:
    """A name spelled British, anywhere a session might grep for its American twin.

    **Blocking, on D16's test.** Under D60 as amended 2026-09-11 an identifier either carries a
    British fragment or it does not; there is nothing to judge. Prose and comments are not read
    and are not governed — see the section comment above for why the ruling stopped there.

    **What it cannot see, by name.** A British word outside the fragment table (the -ise stems
    are a closed list); a name inside a template literal's `${}` (the whole literal is blanked);
    and code a misjudged JSX tag blanks along with the text. Each of those is a miss, never a
    false finding, and `--self-test` proves the blanking in both directions.
    """
    findings: List[Finding] = []
    scanned = 0
    for path in _walk(ROOT, SPELLING_SUFFIXES):
        scanned += 1
        for line, name, british, american in spelling_findings(read(path), path.suffix):
            findings.append(
                Finding(
                    f"{rel(path)}:{line}",
                    f"`{name}` carries the British `{british}`; D60 (amended 2026-09-11) "
                    f"spells every identifier American — `{american}`. A name that is "
                    f"stored or on the wire is not renamed: allow-list it by name in "
                    f"SPELLING_ALLOWED with the reason.",
                )
            )
    report.add(
        "identifier spelling",
        MECHANICAL,
        findings,
        f"{len(findings)} British identifiers" if findings
        else f"every identifier in {scanned} files is spelled American",
        scanned=scanned,
    )


# ------------------------------------------------------------------------- self-test

# Every string here is real prose from this repo's markdown that a naive path extractor
# eats. The check that this audit is not vacuously green.
NON_PATHS = [
    "secret rares where the number exceeds the denominator (`161/159`)",
    "Modern era only (SWSH/SV), English, all Near Mint",
    "T1's key misses (`051/197` for `031/197`, `271/167` for `211/167`)",
    "Resolve normal / reverse holo / holo per card, in order:",
    '`zfill(3)(number) + "/" + printedTotal`, built from pokemontcg.io data',
    "a committed snapshot of the maintainer's own `PokemonTCG/pokemon-tcg-data` repo",
    "Claude Code is available at claude.ai/code in the browser",
    "`printedTotal` lives only in `sets/en.json`",
    "One file per run: `t1-<UTC date>.json`, carrying the overall accuracy",
    "The capture server serves stored photos at `GET /photo/<box>/<position>`",
    # THE ROUTES WHOSE FIRST SEGMENT IS A REAL PACKAGE, which is the case the placeholder
    # rule above cannot save because there is no placeholder in them. `POST
    # /pipeline/identify` was read as the file `pipeline/identify` and blocked a commit on
    # 2026-08-24 for describing a route correctly; `_ROUTE` is what fixed it, and these are
    # the lines that keep it fixed. Both directions matter: a route is dropped, and the
    # module of the same name in ordinary prose is still found (see REAL_PATHS).
    "- **One route spends and is named for it** — `POST /pipeline/identify`. It refuses",
    "`GET /pipeline/runs/<name>/file` — one artefact's bytes, for download",
    "`GET /pipeline/pricing` — one worklist over several runs",
    "`DELETE /inventory/<box>/<index>` — D10's hard delete of a record",
    # THE SAME ROUTES AS CODE SPELLS THEM, 2026-09-12: a quoted string beginning with a
    # slash, in a fenced block that mirrors the dispatcher. `_QUOTED_ROUTE` is what drops
    # them; the module of the same name unquoted is still found (REAL_PATHS below).
    'if path == "/pipeline/value":',
    "  return (await request(`/pipeline/value?${query.toString()}`, NO_CACHE)) as ValuePage",
    "  page.route('/pipeline/pricing', handler)",
    "Refill on later imports as `Add to Quantity = min(cap - live, backstock)`",
    "The repo sits under `~/Library/Mobile Documents/com~apple~CloudDocs/`",
    "Free at https://dev.pokemontcg.io and sent to api.pokemontcg.io only",
]

# The `@` of a Claude Code import is part of the extracted token; resolve_candidate strips
# it. Kept that way so a finding quotes the doc as written rather than a normalised form.
REAL_PATHS = [
    ("see @docs/DECISIONS.md before proposing", "@docs/DECISIONS.md"),
    ("`harness/run.py` holds the registry", "harness/run.py"),
    ("Enforced by `scripts/githooks/pre-commit`.", "scripts/githooks/pre-commit"),
    ("`fixtures/sv09_export_untouched.csv` — real export", "fixtures/sv09_export_untouched.csv"),
    ("permissions live in `.claude/settings.json`", ".claude/settings.json"),
    ("Rationale: @../docs/CODES-DECISIONS.md", "@../docs/CODES-DECISIONS.md"),
    ("`docs/specs/batch-script.md` — the four commands", "docs/specs/batch-script.md"),
    # THE OTHER HALF OF THE ROUTE RULE. `_ROUTE` drops a slash-path only when an HTTP method
    # stands in front of it, and this is what proves the rule stayed narrow: the same
    # package name in ordinary prose, and even a route path mentioned WITHOUT its method,
    # are still extracted and still checked.
    ("the seam lives in `server/pipeline_routes.py` and refuses", "server/pipeline_routes.py"),
    ("read `pipeline/games.py` for which strategy a game uses", "pipeline/games.py"),
]


def self_test() -> int:
    """Prove the extractors before trusting a report. Failures print and exit 1."""
    failures: List[str] = []

    def ok(condition: bool, label: str, detail: str = "") -> None:
        print(f"  {'ok  ' if condition else 'FAIL'} {label}")
        if not condition:
            failures.append(label)
            if detail:
                for line in detail.splitlines():
                    print(f"       {line}")

    print("docs-audit self-test")
    print("=" * 72)
    print("\nextractor rejects prose that only looks like a path")
    tops = top_level_names()
    for line in NON_PATHS:
        kept = [
            candidate
            for candidate in path_candidates(line)
            if resolve_candidate(candidate, ROOT / "docs" / "X.md", tops) is not None
        ]
        ok(not kept, line[:58], f"extracted: {kept}")

    # A RENUMBER IS A TITLE THAT KEPT ITS NAME AND CHANGED ITS ID, and this is the reader of
    # that. The git walk around it needs a repository; this does not, and it is where the
    # logic that could be wrong lives (D72).
    # WHICH TREE AM I, asked without a repository (D143). The case that was
    # wrong is the third: a NAMED branch sitting at origin/main, which is every branch between
    # `git checkout -b` and its first commit.
    print("\nwhich checkout is main, over the four readings that can say so")
    for ref_name, named, head, origin_main, want, label in [
        ("", "main", "aaa", "aaa", True, "the branch is named main"),
        ("main", "HEAD", "aaa", "bbb", True, "GITHUB_REF_NAME says main, head detached"),
        ("", "HEAD", "aaa", "aaa", True, "detached AT origin/main — the CI runner this rule is for"),
        ("", "HEAD", "aaa", "bbb", False, "detached somewhere else"),
        ("", "", "aaa", "aaa", True, "no name at all, sitting at origin/main"),
        ("", "claude/a-branch", "aaa", "aaa", False,
         "A NAMED BRANCH AT origin/main IS NOT MAIN — every branch before its first commit"),
        ("", "claude/a-branch", "aaa", "bbb", False, "a named branch that has committed"),
    ]:
        got = is_main(ref_name, named, head, origin_main)
        ok(got == want, label, f"wanted {want}, got {got}")

    # THE EQUALITY THAT REPLACED TWO SUBSTRING TESTS. Both legs of check_pass_criteria used
    # to ask whether the criterion appeared SOMEWHERE in the section, which `0.9` satisfies
    # inside `0.95`. These cases are the arithmetic of that, with no filesystem in the way.
    print("\na published criterion is compared by equality, not by containment")
    bullet = "- **Pass**: `holdout_accuracy >= 0.95`\n- **The gate is the holdout**, not all."
    inline = "New 2026-08-30 with C9-C11. **Pass: every decode round-trips its own\ncode.**\n\nProse after."
    ok(gates_pass_line(bullet) == ["`holdout_accuracy >= 0.95`"],
       "the bullet form is lifted and stops at the next bullet",
       f"got: {gates_pass_line(bullet)}")
    ok(gates_pass_line(inline) == ["every decode round-trips its own code.**"],
       "the inline bold form is lifted and joined across its wrap",
       f"got: {gates_pass_line(inline)}")
    ok(gates_pass_line("no claim here at all") == [],
       "a section publishing nothing lifts nothing, which is itself the finding")
    ok(strip_presentation("`holdout_accuracy >= 0.95`") == "holdout_accuracy >= 0.95",
       "code ticks come off a machine string")
    ok(strip_presentation("every decode round-trips.**") == "every decode round-trips",
       "the inline terminator and the full stop come off")
    ok(strip_presentation("a >= 0.9") != strip_presentation("a >= 0.95"),
       "AND THE MEASURED DEFECT: 0.9 no longer satisfies 0.95")
    ok("0.9" in "0.95",
       "which the old containment test could not say, because this is true")

    # The two claim writers' decode tables, read the way check_claim_decode reads them.
    print("\na handler's decode table is read off its `\"key\" in payload` branches")
    tree = ast.parse(
        'def do_put_card(self, payload):\n'
        '    if "game" in payload:\n        pass\n'
        '    if "product" in payload:\n        pass\n'
        '    if "note" in other:\n        pass\n'
    )
    keys = _payload_keys(tree.body[0])
    ok(keys == {"game", "product"}, "every key branched on payload is found", f"got: {sorted(keys)}")
    ok("note" not in keys, "and a branch on a different dict is not one of them")

    # The cross-language half of D101's two doors, and the reader that pins a published
    # figure to the file a scanner wrote.
    print("\nthe client's wire keys are read out of its payload assignments")
    ts = (
        "export async function updateCard(a, fields) {\n"
        "  const payload = {}\n"
        "  if ('product' in fields) payload.product = fields.product ?? null\n"
        "  // payload.commented = 1\n"
        "}\n"
        "export async function other() { payload.elsewhere = 2 }\n"
    )
    body = _ts_function_body(ts, "updateCard")
    keys = set(_PAYLOAD_ASSIGN_RE.findall(body or ""))
    ok(keys == {"product"}, "one function's keys, and not the next function's",
       f"got: {sorted(keys)}")
    ok("commented" not in keys, "and a key that only appears in a comment is not sent")
    ok(_ts_function_body(ts, "noSuchFunction") is None, "a missing function reads as None")

    # The exemption `views exposure` grants, and the ones it used to grant for nothing.
    # EVERY TITLE HERE IS A REAL COMMITTED TITLE, the way moves_across's ids are real
    # history: the two that qualify are the assertions D24 asked for by name, and the two
    # that do not are specs that were suppressing the question while proving the opposite.
    print("\na pooled-free claim is read off a test TITLE, never the spec body")

    proves = ("test('a pooled card is never on his screen — not on the walk, not in a "
              "search, not in a count', async ({\n")
    photo = "test('a pooled card never draws a photograph here', async ({ page }) => {\n"
    presence = ("test('the pooled row is a second no-bar shell, and it has not left', "
                "async ({ page }) => {\n")
    drawn = ("test('a pooled copy is drawn as pooled rather than as a position (D24)', "
             "async ({ page }) => {\n")

    ok(len(_pooled_absence_titles(proves)) == 1,
       "the Fulfillment view's assertion earns the exemption",
       f"got: {_pooled_absence_titles(proves)}")
    ok(len(_pooled_absence_titles(photo)) == 1,
       "and so does the review queue's, which cites this row by name")
    ok(_pooled_absence_titles(presence) == [],
       "THE MEASURED DEFECT: the spec proving the pooled row IS drawn earns nothing",
       "app/tests/gallery.spec.ts held /gallery out of the exposure list on that title")
    ok(_pooled_absence_titles(drawn) == [],
       "nor does a title whose claim is that a pooled copy IS drawn")

    # The body match this replaced, in the three shapes that really bought the exemption:
    # a fixture field, a passing comment, and a substring inside an unrelated word.
    body = ("/* four copies that were all LOCATED and all carried a slot number. */\n"
            "const fixture = { located: true }\n"
            "/* RELOCATED HERE FROM `run-panel.spec.ts` on 2026-08-30 */\n")
    ok(_pooled_absence_titles(body) == [],
       "a fixture field, a comment and the tail of RELOCATED assert nothing")
    ok(re.search(r"pooled|located", body, re.I) is not None,
       "which the old body test could not say, because this is exactly what it matched",
       "it was not word-bounded, so `RELOCATED` alone exempted /pricing")

    # SELF-CLEANING, the property the docstring claims: soften the title off the claim and
    # the route rejoins the list. Same spec, same subject, one word gone.
    ok(_pooled_absence_titles("test('a pooled card is not on his screen', () => {})\n") == [],
       "a title hedged from `never` to `not` stops earning it",
       "the row asks whether ANY render can hold a bearer instrument")
    ok(_pooled_absence_titles("") == [], "and a spec with no tests at all earns nothing")

    # Fail-closed on the forms this repo does not write: a parked proof must not go on
    # holding a route out of the exposure list.
    ok(_pooled_absence_titles(
        "test.skip('a pooled card is never on his screen', () => {})\n") == [],
       "a SKIPPED proof earns nothing")
    ok(_pooled_absence_titles('test("a pooled card is never drawn", () => {})\n')
       == ["a pooled card is never drawn"], "the double-quoted title form is read")
    ok(_pooled_absence_titles("test(`a pooled card is never drawn`, () => {})\n")
       == ["a pooled card is never drawn"], "and the backticked one")

    print("\na published figure is looked up in the result file by path")
    measured = {"overall": {"declined": 59}, "per_box": {"box4": {"declined": 17}}}
    ok(_dotted(measured, "per_box.box4.declined") == 17, "a nested count resolves")
    ok(_dotted(measured, "per_box.box9.declined") is None, "a missing path is None, not zero",
       "zero would read as agreement with a section publishing 0")
    ok(_dotted(measured, "overall") is None, "and a path landing on a dict is not a count")

    # The roster reader, and the vacuity this row nearly shipped with.
    print("\na reason roster is resolved through the constants beside it")
    ok(sorted(_roster("pipeline/variant.py", "LADDER_REASONS") or []) == [
        "ambiguous_no_signal", "detected_finish_not_stocked", "duplicate_condition",
        "metadata_not_stocked", "no_catalog_row", "rarity_claim_mismatch"],
       "the ladder's six resolve to their string values",
       f"got: {sorted(_roster('pipeline/variant.py', 'LADDER_REASONS') or [])}")
    ok(_roster("pipeline/variant.py", "NO_SUCH_TUPLE") is None,
       "a module with no such tuple reads as None, which is its own finding")
    ok("normal" not in (_roster("pipeline/variant.py", "LADDER_REASONS") or []),
       "and a finish sharing the constants' exact shape is not swept in",
       "eight of that file's fourteen constants are not reasons")

    print("\nthe roster declaration is not evidence that a reason is emitted")
    emitted = _emitted_names()
    ok("CARD_NOT_DETECTED" not in emitted,
       "a reason whose only load is the roster tuple counts as unemitted",
       "counting it made the row green for all thirteen the moment the rosters landed")
    ok("SET_AMBIGUOUS" in emitted,
       "while a reason with a real producer still counts")

    # THE FIXTURE'S SLUGS ARE COMPOSED, AND THIS BLOCK IS WHY THE RULE IS WRITTEN DOWN. They
    # were spelled out, borrowed from a real entry so the citations would resolve — and the
    # bootstrap claim substituted them, turning two of these into assertions about a NUMBER.
    # A claim is exhaustive text replacement; it cannot tell a fixture from prose. Composed
    # ids are out of its reach, and out of `decision ids in code`'s reach at the same time.
    print("\nan id is a slug until the merge claims it, and a slug is two segments")
    slug = "-" + "a-worked-example"
    step = "a-worked-example"
    ok(re.match(r"^" + _ID_SLUG + r"$", slug) is not None,
       "a two-segment slug is an id")
    ok(re.match(r"^" + _ID_SLUG + r"$", "-" + "pad") is None,
       "and a one-segment one is ordinary prose, not an entry")
    ok(_DECISION_RE.findall(f"see (D{slug}) and D" + "72") == [slug, "72"],
       "the citation scanner reads both forms out of one line",
       str(_DECISION_RE.findall(f"see (D{slug}) and D" + "72")))
    ok(_DECISION_RE.findall("the D" + "-pad on the controller") == [],
       "and reads neither out of a hyphenated English word")
    ok(is_slug(slug) and not is_slug("137"),
       "is_slug separates an unclaimed id from an allocated one")
    ok(_GATES_STEP_SLUG.findall(f"0. `step {step}` **T** — x") == [step],
       "a pending step is read out of its `0.` marker",
       str(_GATES_STEP_SLUG.findall(f"0. `step {step}` **T** — x")))
    ok(_GATES_STEP_SLUG.findall(f"7. `step {step}` **T** — x") == [],
       "and a marker that is not `0.` is a claimed step, read as its number")

    # EVERY PATTERN THAT READS A DECISION ID, AT THE DIGIT THAT USED TO END THEM (D16).
    # docs/DEBTS.md recorded this as a TRIGGERED debt: seven patterns in this file and four
    # more across scripts/ capped at `[1-9][0-9]?`, so at the hundredth entry a heading stops
    # being a heading and a citation stops being a citation — and every row built on them
    # reports GREEN over a file it can no longer see. The debt named the discharge, and these
    # cases are its second half: a widen with nothing exercising the third digit is the same
    # silence one commit later.
    #
    # THE IDS ARE COMPOSED, NEVER WRITTEN, and that is not cuteness. `_DECISION_RE` scans
    # this file, so a literal three-digit id in a fixture is a citation of an entry that does
    # not exist and `decision ids in code` reports it. Composing is what lets a case name a
    # number the file has not reached yet — and it is the whole reason this section could not
    # simply be typed out.
    # Composing is how a case can name a number the file has not reached yet. It also keeps
    # the cases testing the BOUND rather than whatever is written today, which is the
    # opposite of `moves_across` above, where real history is what makes the data honest.
    print("\na decision id is three digits, and a ruff suppression is not one")

    past_end = f"D{100}"
    four_digits = f"D{1000}"
    leading_zero = f"D{0}"
    codes_past_end = f"C{100}"

    with tempfile.TemporaryDirectory() as tmp:
        entries = Path(tmp) / "DECISIONS.md"
        entries.write_text(
            "## D9 — One digit\n\n## D92 — Two digits\n\n"
            f"## {past_end} — Three digits\n\n"
            f"## {four_digits} — Four digits, which is not an id\n\n"
            f"## {leading_zero} — A leading zero, which is not an id\n",
            encoding="utf-8",
        )
        text = entries.read_text(encoding="utf-8")

        found = [ident for ident, _ in decision_heading_lines(entries, "D")]
        ok(found == ["D9", "D92", past_end], "the heading roster reads one, two and three digits", str(found))
        ok(four_digits not in found and leading_zero not in found,
           "and stops at three digits, and at a leading zero", str(found))

        slugged = Path(tmp) / "SLUGGED.md"
        unclaimed = "D" + "-an-unclaimed-entry"
        slugged.write_text(f"## D9 — One digit\n\n## {unclaimed} — An unclaimed entry\n",
                           encoding="utf-8")
        both = [ident for ident, _ in decision_heading_lines(slugged, "D")]
        ok(both == ["D9", unclaimed],
           "the heading roster reads a number and a slug out of one file", str(both))

        # `check_decision_index` reconciles CLAUDE.md's fenced index against those headings,
        # and BOTH of its patterns are exercised here: the heading side, and the shape that
        # locates the index block by its `D<n> ` lines.
        indexed = [
            m.group(1)
            for m in (re.match(r"^##\s+(D" + _ID_ANY + r")\s*[—-]\s*(.+)$", line)
                      for line in text.split("\n"))
            if m
        ]
        ok(indexed == ["D9", "D92", past_end],
           "the index check's heading side reads three digits", str(indexed))
        ok(all(re.match(r"^D" + _ID_ANY + r"\s", line)
               for line in ("D9  One digit", "D92  Two digits", f"{past_end}  Three digits")),
           "and its fenced-block shape accepts a three-digit index line")

    cited = _DECISION_RE.findall(f"this cites D72 and {past_end} in one line")
    ok(cited == ["72", "100"], "a two-digit citation still resolves, beside a three-digit one", str(cited))
    ok(not _DECISION_RE.findall(f"{four_digits} is not an id"), "four digits is not a citation")
    codes = _CODES_DECISION_RE.findall(f"the code track cites C7 and {codes_past_end}")
    ok(codes == ["7", "100"], "the C-track citation reads three digits too", str(codes))

    # THE COLLISION THAT KEPT THIS DEBT UNFIXED FOR THREE DAYS AFTER ITS TRIGGER FIRED. All
    # three suppressions below are real lines in server/, and they were harmless only because
    # the third digit was out of reach. Widening without `without_noqa` turns every one into
    # a citation of an entry that does not exist — measured, not predicted: with the strip
    # disabled and the cap at three, `decision ids in code` reported all three.
    #
    # These labels quote the directive on purpose. It means each label is itself a line
    # carrying a suppression, so the strip has to work for this section to survive its own
    # row — the case and its evidence are the same string.
    for line, label in (
        ("    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102",
         "`# noqa: D102` is a pydocstyle code, not a citation"),
        ("def _run_owes(manifest: dict) -> List[str]:  # noqa: D401",
         "`# noqa: D401` is not a citation either"),
        ("    if complex_thing():  # noqa: C901",
         "`# noqa: C901` is not a C-track citation"),
        ("from server import ports  # noqa: E402, F401",
         "a multi-code suppression is not a citation"),
    ):
        stripped = without_noqa(line)
        ok(not _DECISION_RE.findall(stripped) and not _CODES_DECISION_RE.findall(stripped),
           label, repr(stripped))

    # The directive goes; the sentence after it does not. Blanking the whole line would trade
    # the false positive for a blind spot, which is the trade this file exists to refuse —
    # and this repo really does write prose after the codes.
    with tempfile.TemporaryDirectory() as tmp:
        module = Path(tmp) / "sample.py"
        module.write_text(
            "from server import ports  # noqa: E402\n"
            "def redirect_request(self):  # noqa: D102\n"
            "    return None  # the renumber rule is D72's\n",
            encoding="utf-8",
        )
        ok(cited_decisions(module) == {"D72"},
           "`governed_by`'s reader excludes suppressions too — the row it feeds is MECHANICAL",
           str(cited_decisions(module)))

    kept = without_noqa("    except Exception as exc:  # noqa: BLE001 — 500 is for bugs, see D72")
    ok(_DECISION_RE.findall(kept) == ["72"],
       "a citation in the prose AFTER a suppression survives", repr(kept))
    ok(without_noqa("no directive here, just D72") == "no directive here, just D72",
       "a line with no suppression is returned unchanged")

    # THE SIBLING READERS, which the rows above depend on and which cannot report for
    # themselves. `decision structure` IS scripts/prose-guard.py's regex, and the
    # decision-context hook is what a session reads before editing a governed file. Both
    # carried the same cap; a widen that stopped at this file would have left the audit
    # reporting a heading count over a file the guard could not read, which is precisely the
    # measured symptom above.
    guard = _prose_guard()
    ok(
        guard is not None
        and bool(guard.ANY_H2_RE.match(f"## {past_end} — Three digits"))
        and bool(guard.HEADING_RE.match(f"## {past_end} — Three digits")),
        "scripts/prose-guard.py reads a three-digit heading",
    )
    ok(
        guard is not None and not guard.ANY_H2_RE.match(f"## {four_digits} — Four digits"),
        "and stops at three, like every pattern above it",
    )

    with tempfile.TemporaryDirectory() as tmp:
        entries = Path(tmp) / "DECISIONS.md"
        entries.write_text(
            f"## {past_end} — Three digits\n\n**A ruling long enough to be picked up.**\n",
            encoding="utf-8",
        )
        context = _sibling("decision-context.py")
        gists = context.decision_gists(path=entries) if context else {}
        ok(past_end in gists, "the decision-context hook resolves a three-digit entry", str(list(gists)))

    print("\nextractor finds real references")
    for line, expected in REAL_PATHS:
        found = path_candidates(line)
        ok(expected in found, expected, f"extracted: {found}")

    # The two forms with their own resolution rule. A `@` import that silently resolved to
    # nothing, or a `../` that escaped the repo, would make the whole check quietly vacuous.
    print("\nthe @ import and ../ forms resolve to real files")
    resolved = resolve_candidate("@docs/DECISIONS.md", ROOT / "CLAUDE.md", tops)
    ok(
        resolved is not None and resolved.exists(),
        "@docs/DECISIONS.md from CLAUDE.md",
        str(resolved),
    )
    resolved = resolve_candidate("@../docs/CODES-DECISIONS.md", ROOT / "code-card-fork" / "CLAUDE.md", tops)
    ok(
        resolved is not None and resolved.exists(),
        "@../docs/CODES-DECISIONS.md from code-card-fork/CLAUDE.md",
        str(resolved),
    )
    ok(
        resolve_candidate("../../../etc/passwd", ROOT / "code-card-fork" / "CLAUDE.md", tops) is None,
        "a ../ path escaping the repo is not ours to check",
    )

    print("\npath check fires on a dangling reference")
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "fake.md"
        doc.write_text("see `harness/no_such_file.py` for details\n", encoding="utf-8")
        report = Report()
        check_paths(report, [doc], {})
        findings = report.checks[0].findings
        ok(len(findings) == 1, "one finding for one dangling path", str(findings))

        doc.write_text("see `harness/run.py` for details\n", encoding="utf-8")
        report = Report()
        check_paths(report, [doc], {})
        findings = report.checks[0].findings
        ok(not findings, "no finding for a path that resolves", str(findings))

    print("\nignored_paths answers a candidate git refuses to walk past a symlink")
    with tempfile.TemporaryDirectory() as tmp:
        # A REAL THROWAWAY REPO WITH A REAL SYMLINK, reproducing 2026-09-12's failure
        # exactly rather than mocking subprocess — `git check-ignore` genuinely refuses a
        # pathspec that walks past a symlink, and no fake can stand in for its exit code.
        repo = Path(tmp) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
        # NO TRAILING SLASH, matching this repo's own .gitignore and for the same reason
        # (see its header comment): a directory-only pattern does not match a SYMLINK at
        # that name, which is exactly what a worktree puts there.
        (repo / ".gitignore").write_text("harness/images\n", encoding="utf-8")
        (repo / "harness").mkdir()
        target = Path(tmp) / "elsewhere"
        (target / "images" / "images").mkdir(parents=True)
        (repo / "harness" / "images").symlink_to(target / "images")

        direct_code = subprocess.run(
            ["git", "check-ignore", "--stdin"],
            cwd=str(repo),
            input=b"harness/images/images",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        ok(direct_code not in (0, 1), "the fixture reproduces the symlink refusal", str(direct_code))

        found = ignored_paths(["harness/images/images"], root=repo)
        ok(
            "harness/images/images" in found,
            "a path beneath a symlinked, gitignored ancestor is recognised as ignored",
            str(found),
        )

        # AND THE OTHER DIRECTION, so the ancestor walk cannot be mistaken for "anything
        # under a symlink is forgiven" — it must still answer NO when the ancestor itself
        # is real content, not an ignore pattern.
        (repo / "harness" / "images" / ".gitignore").unlink(missing_ok=True)
        (repo / ".gitignore").write_text("", encoding="utf-8")
        found_real = ignored_paths(["harness/images/nope"], root=repo)
        ok(
            "harness/images/nope" not in found_real,
            "a symlinked ancestor that is NOT ignored is not swept in with it",
            str(found_real),
        )

    print("\ncommand references need a fence or backticks")
    prose = "T5 and T6 make it **six**. Em-dashes make it a worse OCR target."
    ok(
        not list(iter_code_lines(prose)),
        "`make it` in prose is not a build target",
        str(list(iter_code_lines(prose))),
    )
    backticked = "Run `make harness` before you tell me something works."
    found = [name for _, line in iter_code_lines(backticked) for name in _MAKE_REF_RE.findall(line)]
    ok(found == ["harness"], "backticked `make harness` is", str(found))
    fenced = "```\nmake harness        # all six verification tests\n```"
    found = [name for _, line in iter_code_lines(fenced) for name in _MAKE_REF_RE.findall(line)]
    ok(found == ["harness"], "fenced make harness is", str(found))

    print("\nmodule.attribute references are resolved, not guessed")
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "fake.md"
        doc.write_text("`pipeline/variant.resolve` is used unchanged.\n", encoding="utf-8")
        report = Report()
        check_paths(report, [doc], {})
        findings = report.checks[0].findings
        ok(not findings, "a real module.function resolves", str(findings))

        doc.write_text("`pipeline/variant.no_such_function` does the work.\n", encoding="utf-8")
        report = Report()
        check_paths(report, [doc], {})
        findings = report.checks[0].findings
        ok(len(findings) == 1, "a function that is not defined is reported", str(findings))

    print("\nallowlist is self-cleaning")
    report = Report()
    check_allowlist(report, {"harness/run.py": "pretend this is planned"})
    findings = report.checks[0].findings
    ok(len(findings) == 1, "existing path in the allowlist is reported stale", str(findings))
    report = Report()
    check_allowlist(report, {"harness/not_yet.py": "genuinely planned"})
    findings = report.checks[0].findings
    ok(not findings, "absent path in the allowlist is fine", str(findings))

    print("\nast readers handle the real files")
    runner = ROOT / "harness" / "run.py"
    if runner.exists():
        names = list_names_from_assign(read(runner), "TESTS")
        ok(bool(names) and "t1_id_eval" in (names or []), "TESTS list read from harness/run.py", str(names))
    main = ROOT / "cli" / "__main__.py"
    if main.exists():
        keys = dict_keys_from_assign(read(main), "COMMANDS")
        # WHAT THIS ROW IS FOR IS THE READER, NOT THE ROSTER. It pinned the exact four
        # commands until 2026-08-30, which made it a second copy of a fact
        # `harness/tests/t7_store_and_seams.py` already asserts exactly — including the "and
        # only these" half, which is the part worth having and which belongs in the test that
        # can refuse a command nobody declared. Two copies meant adding `scan` failed a check
        # whose subject is `dict_keys_from_assign`, in a file that has no opinion about what
        # commands should exist. So this asserts what it is actually testing: the reader
        # returns a non-empty list of the real keys.
        ok(
            bool(keys) and "identify" in (keys or []) and "join" in (keys or []),
            "COMMANDS read from cli/__main__.py",
            str(keys),
        )
    t3 = ROOT / "harness" / "tests" / "t3_join_coverage.py"
    if t3.exists():
        criteria = string_assign(read(t3), "PASS_CRITERIA")
        ok(
            isinstance(criteria, str) and len(criteria) > 40,
            "multi-line PASS_CRITERIA reassembled",
            repr(criteria),
        )

    print("\na check named by position is reported, per subset")
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "fake.md"
        # Built with an f-string on purpose: written as a literal, this line would be a
        # finding against this file. Same trick, same reason, as the code pattern that
        # scripts/githooks/pre-commit assembles from parts.
        doc.write_text(f"the orphan rule is check {10} here\n", encoding="utf-8")
        report = Report()
        check_positional_references(report, [doc])
        rows = {row.check: (row.severity, row.findings) for row in report.checks}
        ok(
            len(rows.get("check numbering", ("", []))[1]) == 1,
            "a positional reference in a doc is reported",
            str(rows.get("check numbering")),
        )
        ok(
            rows.get("numbering in code", ("", []))[0] == ADVISORY,
            "the code row is advisory, and the doc row is not",
            str([(row.check, row.severity) for row in report.checks]),
        )

        doc.write_text("the repo-map check owns the orphan rule\n", encoding="utf-8")
        report = Report()
        check_positional_references(report, [doc])
        # By label, not by index. This function emits two rows, so `report.checks[0]` was
        # a check identified by its position — the exact pattern D17 bans in the docs and
        # this row exists to enforce. It read `[1]` until the count row above it was
        # deleted, at which point it silently retargeted and still passed.
        by_label = {row.check: row.findings for row in report.checks}
        findings = by_label["check numbering"]
        ok(not findings, "naming the check by its label is fine", str(findings))

    # THE VERDICT FILE'S FOUR-WAY AGREEMENT. Every case here is a way for the instruction in
    # CLAUDE.md — "read `.serve/design-check.json`" — to become false with nothing else in
    # the repo noticing: the suite still passes, the config still typechecks, and the prose
    # still reads correctly. Three of the four are silent in exactly that way, which is why
    # the row exists; the fourth (a deleted reporter) is loud at Playwright startup and is
    # covered here anyway so the row cannot be half-wired.
    print("\nthe design-check verdict file is named the same in four places")
    good_reporter = "const X = 1\nexport const RESULT_FILE = resolve(REPO_ROOT, '.serve', 'design-check.json')\n"
    good_config = "export default defineConfig({\n  reporter: [['list'], ['./design-check-reporter.ts']],\n})\n"
    good_make = (
        "design-check:\n\t$(NPM_GUARD)\n\t@rm -f .serve/design-check.json\n"
        "\t@npm --prefix app run design-check\n\n"
        "design-check-quiet:\n\t$(NPM_GUARD)\n\t@rm -f .serve/design-check.json\n"
        "\t@DESIGN_CHECK_QUIET=1 npm --prefix app run design-check\n"
    )
    good_prose = "make design-check leaves .serve/design-check.json behind\n"
    ok(
        not verdict_disagreements(good_reporter, good_config, good_make, good_prose),
        "four files agreeing is clean",
        str(verdict_disagreements(good_reporter, good_config, good_make, good_prose)),
    )

    found = verdict_disagreements(good_reporter, "reporter: [['list']],\n", good_make, good_prose)
    ok(
        len(found) == 1 and "no longer names" in found[0].message,
        "a config that stopped naming the reporter is reported — the suite would go green and write nothing",
        str(found),
    )
    commented = "// design-check-reporter.ts writes the verdict\nreporter: [['list']],\n"
    found = verdict_disagreements(good_reporter, commented, good_make, good_prose)
    ok(
        len(found) == 1 and "no longer names" in found[0].message,
        "and a COMMENT naming the reporter does not satisfy it — a header that describes the "
        "wiring is not the wiring",
        str(found),
    )

    no_rm = good_make.replace("\t@rm -f .serve/design-check.json\n", "", 1)
    found = verdict_disagreements(good_reporter, good_config, no_rm, good_prose)
    ok(
        len(found) == 1 and "does not delete" in found[0].message and "design-check`" in found[0].message,
        "a recipe that stopped clearing the stale file is reported, and only that recipe",
        str(found),
    )

    late_rm = good_make.replace(
        "\t@rm -f .serve/design-check.json\n\t@npm --prefix app run design-check\n",
        "\t@npm --prefix app run design-check\n\t@rm -f .serve/design-check.json\n",
        1,
    )
    found = verdict_disagreements(good_reporter, good_config, late_rm, good_prose)
    ok(
        len(found) == 1 and "AFTER running" in found[0].message,
        "a recipe that deletes the verdict AFTER the run is a different fault and says so",
        str(found),
    )

    moved = good_reporter.replace("'design-check.json'", "'verdict.json'")
    found = verdict_disagreements(moved, good_config, good_make, good_prose)
    ok(
        any(f.where == "CLAUDE.md" for f in found),
        "a RESULT_FILE the prose does not name is reported",
        str(found),
    )
    ok(
        all("verdict.json" in f.message for f in found if f.where == "Makefile"),
        "and the Makefile arm is reconciled against the MOVED path, not a hardcoded one",
        str(found),
    )

    found = verdict_disagreements(None, good_config, good_make, good_prose)
    ok(
        len(found) == 1 and "does not exist" in found[0].message,
        "a deleted reporter is one finding about the file, not four about its readers",
        str(found),
    )
    found = verdict_disagreements("const RESULT_FILE = 'somewhere'\n", good_config, good_make, good_prose)
    ok(
        len(found) == 1 and "no `RESULT_FILE" in found[0].message,
        "a reporter whose RESULT_FILE cannot be read reports THAT, rather than an empty agreement",
        str(found),
    )

    # And the live tree, which is what the row actually asserts on every run.
    ok(
        not verdict_disagreements(
            read(_VERDICT_REPORTER) if exists(_VERDICT_REPORTER) else None,
            read(_VERDICT_CONFIG) if exists(_VERDICT_CONFIG) else None,
            read(ROOT / "Makefile"),
            read(ROOT / "CLAUDE.md"),
        ),
        "this repo's own four files agree",
    )

    # A target absent from .PHONY is a green `make` that ran nothing, and nothing in the
    # prose is wrong when it happens — so no other check in this file can see it.
    print("\nevery make target is declared .PHONY")
    complete = ".PHONY: help harness\n\nhelp:\n\t@echo hi\n\nharness:\n\t@run\n"
    ok(phony_gaps(complete) == (set(), set()), "a complete .PHONY is clean", str(phony_gaps(complete)))
    dropped = ".PHONY: help\n\nhelp:\n\t@echo hi\n\nharness:\n\t@run\n"
    ok(
        phony_gaps(dropped) == ({"harness"}, set()),
        "a target missing from .PHONY is reported",
        str(phony_gaps(dropped)),
    )
    stale = ".PHONY: help harness ghost\n\nhelp:\n\t@echo hi\n\nharness:\n\t@run\n"
    ok(
        phony_gaps(stale) == (set(), {"ghost"}),
        "a .PHONY name with no rule is reported",
        str(phony_gaps(stale)),
    )
    ok(
        phony_gaps(read(ROOT / "Makefile")) == (set(), set()),
        "this repo's own Makefile agrees with its .PHONY",
        str(phony_gaps(read(ROOT / "Makefile"))),
    )

    # The orphan scan's reach. Every case here is a way for the rule to look like it ran:
    # the wrong suffixes find nothing, a flat scan of a nested tree finds nothing, and a
    # typo in the declaration finds nothing — all three print the same clean row.
    print("\nthe orphan scan covers what the map entry declares")
    ok(
        scan_plan({}) == (DEFAULT_SOURCE_SUFFIXES, False, []),
        "an entry declaring nothing is scanned as it always was",
        str(scan_plan({})),
    )
    plan = scan_plan({SOURCE_SUFFIXES_KEY: [".tsx", ".css"], "modules": {"src/a.tsx": {}}})
    ok(plan == ((".tsx", ".css"), True, []), "a declaration replaces the default, and recurses", str(plan))
    plan = scan_plan({SOURCE_SUFFIXES_KEY: ["tsx"], "modules": {"src/a.tsx": {}}})
    ok(
        plan[0] == () and len(plan[2]) == 2,
        "a suffix without its dot is reported, not silently matched",
        str(plan),
    )
    plan = scan_plan({SOURCE_SUFFIXES_KEY: ".tsx", "modules": {"src/a.tsx": {}}})
    ok(
        plan[0] == () and len(plan[2]) == 1,
        "a bare string is reported — str.endswith would have accepted it",
        str(plan),
    )
    plan = scan_plan({SOURCE_SUFFIXES_KEY: [".tsx"]})
    ok(
        len(plan[2]) == 1,
        "declaring suffixes with no modules list is an inert declaration",
        str(plan),
    )

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name in ("src/a.tsx", "src/deep/b.tsx", "node_modules/pkg/c.tsx",
                     "dist/d.tsx", "test-results/e.tsx", "src/f.py"):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("", encoding="utf-8")
        found = source_names(root, (".tsx",), True)
        ok(
            found == {"src/a.tsx", "src/deep/b.tsx"},
            "a deep scan reaches subdirectories and skips the build output",
            str(sorted(found)),
        )
        ok(
            source_names(root, (".tsx",), False) == set(),
            "and the flat scan it replaced saw none of it — the defect, measured",
            str(sorted(source_names(root, (".tsx",), False))),
        )
        ok(
            source_names(root, DEFAULT_SOURCE_SUFFIXES, False) == set(),
            "a `.py` entry is unaffected by any of it",
            str(sorted(source_names(root, DEFAULT_SOURCE_SUFFIXES, False))),
        )

    # A tested_by claim. Every case below is a way for this row to pass a claim it should
    # refuse, or refuse one it should pass — and the blocking direction is the expensive one,
    # so the correct claims are asserted first and against the real harness.
    print("\na tested_by claim is checked against what the cited test imports")
    ok(
        "geometry" in imported_names("def run():\n    import geometry\n"),
        "an import inside a function is found — t6's shape, and it is a correct claim",
        str(imported_names("def run():\n    import geometry\n")),
    )
    names = imported_names("from harness.eval import fixtures, runcache\n")
    ok(
        {"harness.eval", "harness.eval.fixtures", "harness.eval.runcache"} <= names,
        "a from-import records the package and each name, since only disk knows which is a module",
        str(sorted(names)),
    )
    ok(
        imported_names("from . import sibling\n") == set(),
        "a relative import names nothing this can resolve, and is dropped",
        str(imported_names("from . import sibling\n")),
    )
    literals = string_literals('"""Load fixtures/doc.csv"""\nA = "fixtures/code.csv"\n')
    ok(
        literals == {"fixtures/code.csv"},
        "a path in a docstring is prose; a path in an assignment is the test reading a file",
        str(sorted(literals)),
    )

    # The follow's boundary, stated as two assertions because the whole value of this row
    # is what it declines to follow.
    ok(
        follow_target("harness.eval.fixtures") is not None
        and follow_target("pipeline.join") is None,
        "the follow reaches a harness helper and stops at a product package",
        f"{follow_target('harness.eval.fixtures')} / {follow_target('pipeline.join')}",
    )
    registry = {name: path for name, path in registered_tests()}
    if "T7" in registry and "T1" in registry:
        packages, _ = test_reach(registry["T7"])
        ok(
            "store" in packages and "geometry" not in packages,
            "T7 reaches store directly and does NOT reach geometry through cli — "
            "the transitive follow that would make this row vacuous is absent",
            str(sorted(packages)),
        )
        packages, _ = test_reach(registry["T1"])
        ok(
            "identify" in packages,
            "T1 reaches identify",
            str(sorted(packages)),
        )

    # The false claim docs/DEBTS.md recorded, replayed against the real harness rather than
    # against a stand-in for it. `store/queues.py` cited T3 and T4 while nothing under
    # harness/ imported store.
    #
    # THE ID IN THIS CASE HAS MOVED TWICE, AND BOTH MOVES ARE THE CASE WORKING RATHER THAN
    # ROTTING. It pinned T3 once T7 arrived and began importing store; then T3 itself began
    # importing store (commit 548515b, when D7's fungibility amendment made it build a real
    # store to exercise rung 0 and the `committed` flag), so the claim stopped being false
    # and this case went red — a RED SELF-TEST WITH A GREEN AUDIT, which is exactly the
    # shape a stale fixture takes. Found on 2026-08-24; nothing runs `--self-test` on the
    # commit path, which is why it sat.
    #
    # Pinned to T5 now, and the requirement is stated rather than left to be rediscovered:
    # THIS CASE NEEDS A TEST THAT REACHES `pipeline` AND NOT `store`. T2 and T5 are the only
    # two left. If a later change gives T5 a store, move it again and add a line here — do
    # not weaken the assertion, which is the whole point of the case: the `tested_by reach`
    # row must be able to catch a claim that a test covers a package it never imports.
    if registry:
        found, claims = reach_findings(
            [{"path": "store/", "modules": {"queues.py": {"tested_by": ["T5"]}}}], registry
        )
        ok(
            len(found) == 1 and claims == 1 and "store" in found[0].message,
            "the historical false claim — store/queues.py citing a pipeline-only test — "
            "is reported",
            str(found),
        )
        found, claims = reach_findings(
            [{"path": "pipeline/", "modules": {"pricing.py": {"tested_by": ["T5"]}}}], registry
        )
        ok(not found and claims == 1, "and the true claim beside it is not", str(found))
        found, _ = reach_findings([{"path": "fixtures/", "tested_by": ["T2"]}], registry)
        ok(
            not found,
            "a directory holding no Python passes on a path literal — fixtures/ from T2",
            str(found),
        )
        # T6 RATHER THAN T7, AND THE SWAP IS THIS SELF-TEST'S OWN ALLOWLIST RULE FIRING.
        # This case named T7 until 2026-08-30, when T7 gained two `fixtures/` literals for the
        # price-history reader and the negative case went green for a reason that had nothing
        # to do with the checker. A negative case whose subject stops being negative is a case
        # that has silently stopped testing anything — the same shape D16 gives
        # `docs-audit-allow.txt`, where an entry coming true is what forces it out. T6 builds
        # synthetic composites and names no path under `fixtures/`, which is what this case
        # needs and is a property of that test rather than an accident of today's tree.
        found, _ = reach_findings([{"path": "fixtures/", "tested_by": ["T6"]}], registry)
        ok(
            len(found) == 1,
            "and fails when the cited test never names a path under it",
            str(found),
        )
        found, claims = reach_findings(
            [{"path": "store/", "modules": {"queues.py": {"tested_by": ["T99"]}}}], registry
        )
        ok(
            not found and claims == 0,
            "an unregistered id is the repo map row's finding, not counted or repeated here",
            str(found),
        )
        found, _ = reach_findings([{"path": "no_such_dir/", "tested_by": ["T3"]}], registry)
        ok(not found, "and a component path that does not exist is the same", str(found))

    report = Report()
    check_tested_by_reach(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label.get("tested_by reach"),
        "every tested_by claim in this repo's own map reaches what it names",
        str(by_label.get("tested_by reach")),
    )

    # The token row's silent failures, in the order they would bite: a normaliser that
    # hides a real difference, a parser that reads a value the browser never sees, and a
    # comparison that runs in one direction only.
    print("\nthe locked palette is compared against the stylesheet, both ways")
    ok(
        token_value(COLOR, "#FFF") == token_value(COLOR, "#ffffff"),
        "case and shorthand are spelling, not disagreement",
        f'{token_value(COLOR, "#FFF")} vs {token_value(COLOR, "#ffffff")}',
    )
    ok(
        token_value(TYPEFACE, "'Cabinet Grotesk', sans-serif") == token_value(TYPEFACE, "Cabinet Grotesk"),
        "the generic fallback in a font stack is not part of the token",
        token_value(TYPEFACE, "'Cabinet Grotesk', sans-serif"),
    )
    ok(
        token_value(LENGTH, "4px") != token_value(LENGTH, "4 px"),
        "a length keeps its unit joined — CSS does not read those as one value",
    )

    sample = "\n".join(
        [
            "NEUTRALS                 light        dark",
            "--bn-bg                  #f4f5f8      #0c0e12     the page",
            "--bn-line                ink 8%       white 8%    the hairline",
            "",
            "SPACING                  --bn-1 … --bn-3 = 4 8 12",
            "RADIUS                   --bn-r-xs 4 · -sm 6 · --bn-r 8",
            "TYPE                     --bn-fs-2xs … --bn-fs-5xl   10 11 12",
            "STAGE                    --bn-stage-bg #0c0e12 · -ink #eef0f4",
        ]
    )
    claims = design_token_claims(sample)
    ok(
        {"--bn-bg", "--bn-line", "--bn-1", "--bn-2", "--bn-3", "--bn-r-xs", "--bn-r"} <= claims.names,
        "a plain row, a numbered range and a full name in a list all yield their token",
        str(sorted(claims.names)),
    )
    ok(
        claims.prefixes == {"--bn-fs"},
        "a WORDED range locks a family, because its members are not enumerable from its ends",
        str(claims.prefixes),
    )
    ok(
        any({"--bn-r-sm"} & group for group in claims.alts),
        "a bare suffix continues the name before it",
        str(claims.alts),
    )
    ok(
        claims.hexes.get("--bn-bg") == ("#f4f5f8", "#0c0e12"),
        "a row states a light value AND a dark one, and both are kept",
        str(claims.hexes.get("--bn-bg")),
    )
    ok(
        "--bn-line" not in claims.hexes,
        "an alpha of another token states no hex, so there is nothing to compare",
        str(claims.hexes),
    )
    ok(
        claims.hexes.get("--bn-stage-ink") == ("#eef0f4", None),
        "a name/value pair mid-line is read, suffix and all",
        str(claims.hexes),
    )

    scoped = "\n".join(
        [
            ":root { --bn-bg: #f4f5f8; --bn-ink: #0f1217; --legacy: var(--bn-bg); }",
            ":root[data-theme='dark'] { --bn-bg: #0c0e12; }",
            "@media (pointer: coarse) { :root { --bn-control-h: 42px; } }",
        ]
    )
    light, dark, every = css_token_scopes(scoped)
    ok(
        light.get("--bn-bg") == "#f4f5f8" and dark.get("--bn-bg") == "#0c0e12",
        "THE TWO THEMES ARE KEPT APART — merging them let a dark hex answer for a light one",
        f"light {light.get('--bn-bg')} / dark {dark.get('--bn-bg')}",
    )
    ok(
        "--legacy" not in every,
        "a legacy alias is not locked, because the doc argues for deleting it",
        str(sorted(every)),
    )
    ok(
        "--bn-control-h" in every and "--bn-control-h" not in light,
        "a token declared only under an at-rule is named but not value-compared",
        f"every={sorted(every)} light={sorted(light)}",
    )

    agreed = design_token_claims(
        "\n".join(["--bn-bg   #f4f5f8   #0c0e12   the page", "--bn-ink  #0f1217   #eef0f4   body text"])
    )
    css_light = {"--bn-bg": "#f4f5f8", "--bn-ink": "#0f1217"}
    css_dark = {"--bn-bg": "#0c0e12", "--bn-ink": "#eef0f4"}
    names = {"--bn-bg", "--bn-ink"}
    ok(
        not token_findings(agreed, css_light, css_dark, names),
        "two files that agree produce no finding",
        str(token_findings(agreed, css_light, css_dark, names)),
    )

    drifted = token_findings(agreed, dict(css_light, **{"--bn-ink": "#0f1218"}), css_dark, names)
    ok(
        len(drifted) == 1 and "#0f1217" in drifted[0].message and "#0f1218" in drifted[0].message,
        "a changed hex is reported, naming both values",
        str(drifted),
    )
    ok(
        len(drifted) == 1 and "docs/DESIGN.md" in drifted[0].message and "app/src/tokens.css" in drifted[0].message,
        "and naming both files",
        str(drifted),
    )
    dark_drift = token_findings(agreed, css_light, dict(css_dark, **{"--bn-bg": "#0c0e13"}), names)
    ok(
        len(dark_drift) == 1 and "dark theme" in dark_drift[0].message,
        "AND A DARK VALUE DRIFTING IS ITS OWN FINDING, which the merged reader could not see",
        str(dark_drift),
    )
    ok(
        len(token_findings(agreed, css_light, css_dark, {"--bn-bg"})) == 1,
        "a locked token the stylesheet never declares is reported",
        str(token_findings(agreed, css_light, css_dark, {"--bn-bg"})),
    )
    ok(
        len(token_findings(agreed, css_light, css_dark, names | {"--bn-shadow-1"})) == 1,
        "and a stylesheet token the block never locked",
        str(token_findings(agreed, css_light, css_dark, names | {"--bn-shadow-1"})),
    )

    commented, _, _ = css_token_scopes(":root {\n  --bn-ink: #08090a; /* was --bn-ink: #fff; */\n}\n")
    ok(
        commented == {"--bn-ink": "#08090a"},
        "a declaration inside a comment is not a token",
        str(commented),
    )
    elsewhere, _, _ = css_token_scopes(".card { --bn-ink: #ffffff; }\n")
    ok(
        elsewhere == {},
        "and a custom property on some other selector is not a locked token",
        str(elsewhere),
    )

    # The extractor against the real file, because the synthetic block above is written to
    # be parseable and docs/DESIGN.md is written to be read.
    if exists(DESIGN):
        block = design_token_block(read(DESIGN))
        # Discriminated on a string only the step-6 fence carries. The obvious marker —
        # `disabled`, one of its three state names — is also the last word of the `muted`
        # row in this fence, so it failed against the correct block. Measured, not guessed.
        # The POSITIVE marker moved with the block: it read `Spacing`, which the `--bn-`
        # rewrite spells `SPACING`, and a self-test pinned to a heading's case is pinned to
        # the wrong thing. A token prefix no other fence in the file uses is the durable one.
        ok(
            block is not None and "--bn-" in block and "44px tall" not in block,
            "the Tokens fence is the one extracted, not step 6's button states",
            (block or "")[:70],
        )
    report = Report()
    check_design_tokens(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label["design tokens"],
        "this repo's own tokens.css agrees with docs/DESIGN.md",
        str(by_label["design tokens"]),
    )

    print("\na breakpoint reader sees rules and not the prose about them")
    _css = ("/* the 768-1023px media rail, and 640 here is wrong on purpose */\n"
            "@media (max-width: 767px) { .a { color: red } }\n"
            "@media (min-width: 768px) and (max-width: 1023px) { .b { color: red } }\n"
            "@container pane (min-width: 560px) { .c { color: red } }\n"
            ".d { container-name: pane; }\n")
    _w = read_widths(_css)
    ok(
        _w.media == [("max", 767, 2), ("min", 768, 3), ("max", 1023, 3)],
        "only the RULES' widths, with the line the rule is on",
        str(_w.media),
    )
    ok(
        not any(v == 640 for _, v, _ in _w.media),
        "AND THE DEFECT: a comment naming 768-1023px and 640 contributes no widths",
        str(_w.media),
    )
    ok(
        _w.container == [("min", 560, 4)] and _w.queried == {"pane"} and _w.declared == {"pane"},
        "a container query is its own namespace, and is read from both sides",
        f"{_w.container} {_w.queried} {_w.declared}",
    )

    print("\nthe register is read as four sections, not as one list")
    _reg = ("LADDER          the shared vocabulary\n"
            "  768           the tablet\n"
            "REFINEMENTS     one screen's own\n"
            "  1500          ReviewQueue — the rail becomes a sheet\n"
            "CONTAINER       measured against a column\n"
            "  pane    560   BoxBrowse — the band splits\n"
            "  (unnamed) 520, 640   RunPanel — the detail's own steps\n"
            "COLUMN-BLIND    the exemptions\n"
            "  Fulfillment.css   draws no shell of its own\n")
    _l = read_ladder(_reg)
    ok(_l.steps == {768: "the tablet"}, "a ladder step keeps its reason", str(_l.steps))
    ok(
        1500 in _l.refinements and 1500 not in _l.steps,
        "AND THE DEFECT: a refinement is not silently promoted to a step every sheet may use",
        str(_l.refinements),
    )
    ok(
        _l.container == {560, 520, 640},
        "a container row contributes its widths, including several on one line",
        str(_l.container),
    )
    ok(
        list(_l.blind) == ["Fulfillment.css"] and not any(
            k in _l.steps or k in _l.refinements for k in (0,)),
        "a sheet name under COLUMN-BLIND is not read as a width",
        str(_l.blind),
    )
    report = Report()
    check_breakpoints(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label["breakpoints"],
        "this repo's own stylesheets agree with the register",
        str(by_label["breakpoints"]),
    )

    print("\na color literal is found in CSS, and not in a comment about one")
    ok(
        strip_css_comments("a { color: #fff; } /* not #000 */").count("#") == 1,
        "a hex inside a block comment is stripped",
        strip_css_comments("a { color: #fff; } /* not #000 */"),
    )
    ok(
        strip_css_comments("/* two\nlines */\n.x{}").splitlines()[2] == ".x{}",
        "stripping preserves line numbers, so a finding points at the right line",
        str(strip_css_comments("/* two\nlines */\n.x{}").splitlines()),
    )
    ok(
        bool(_RAW_COLOR_RE.search("color: #1E40AF;")) and not _RAW_COLOR_RE.search("var(--accent)"),
        "the literal pattern matches a hex and not a token reference",
        "",
    )
    report = Report()
    check_raw_color(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label["raw color"],
        "this repo's own stylesheets read every color from a token",
        str(by_label["raw color"]),
    )

    # ------------------------------------------------------------ identifier spelling
    #
    # Both directions, per language: the name is found, and the same word in every place
    # that is not a name is not. A reader that only proved the first half would go green on
    # a file it had stopped reading.
    print("\na British identifier is found, and the same word in prose is not")
    ok(
        british_spelling("fetchCatalogueRows") == ("catalogue", "catalog"),
        "camelCase is split into words and the American form is named",
        str(british_spelling("fetchCatalogueRows")),
    )
    ok(
        british_spelling("NEIGHBOURLY") == ("neighbourly", "neighborly")
        and british_spelling("_normalise_origin") == ("normalise", "normalize"),
        "an all-caps name and a snake_case name, the second through the -ise list",
        f"{british_spelling('NEIGHBOURLY')} {british_spelling('_normalise_origin')}",
    )
    ok(
        all(british_spelling(w) is None for w in ("cancellation", "pairwise", "Promise", "otherwise", "programmer", "exercised", "color")),
        "words that are -ise, -ll- or -mme in American English too are not findings",
        str([w for w in ("cancellation", "pairwise", "Promise", "otherwise", "programmer", "exercised", "color") if british_spelling(w)]),
    )
    ok(
        all(british_spelling(w) is None for w in ("is_catalogued", "NotCatalogued", "_parse_fulfilment", "labelledby")),
        "an allow-listed stem covers every relative that carries it",
        "",
    )
    ts_text = (
        "const colour = 1 // colour\n"
        "/* colour */ const s = 'colour' + `colour ${humanise(x)}`\n"
        "const r = /colour'/; const d = a / colourless / 2\n"
    )
    found = [(line, name) for line, name, _, _ in spelling_findings(ts_text, ".ts")]
    ok(
        found == [(1, "colour"), (2, "humanise"), (3, "colourless")],
        "a .ts file: a comment, a string and a regex are blank, a template's `${}` and a "
        "division's operand are read",
        str(found),
    )
    tsx_text = (
        "const A = () => (\n"
        "  <p className=\"x\">The box is labelled <b>{labelled}</b> {n} colour</p>\n"
        ")\n"
        "const f = <T,>(x: T) => x\n"
        "const g = <T>(x: T) => colourOf(x)\n"
        "const h = <Icon name=\"pin\" size={22} />\n"
        "const i = <p>{running ? <b size={1} /> : <i />} colour</p>\n"
    )
    found = [(line, name) for line, name, _, _ in spelling_findings(tsx_text, ".tsx")]
    ok(
        found == [(2, "labelled"), (5, "colourOf")],
        "a .tsx file: JSX text is blank, a `{}` child is read, a closing tag is not a regex, "
        "and a generic parameter list is not a tag",
        str(found),
    )
    py_text = '"""colour"""\n# colour\ndef normalise(x):\n    return "colour" + f"{colour}"\n'
    found = [(line, name) for line, name, _, _ in spelling_findings(py_text, ".py")]
    ok(
        found == [(3, "normalise")],
        "a .py file: the docstring, the comment and both strings are skipped",
        str(found),
    )
    found = [(line, name) for line, name, _, _ in spelling_findings(
        "#!/bin/sh\n# colour\nCOLOUR=\"colour\" # colour\necho ${COLOUR}\n", ".sh")]
    ok(found == [(3, "COLOUR"), (4, "COLOUR")], "a .sh file: the comment and the string are blank", str(found))
    found = [(line, name) for line, name, _, _ in spelling_findings(
        "/* colour */\n.bn-colour-chip { color: var(--bn-colour); content: 'colour' }\n", ".css")]
    ok(
        found == [(2, "bn-colour-chip"), (2, "--bn-colour")],
        "a .css file: a class and a custom property are names, `color` and the string are not",
        str(found),
    )
    report = Report()
    check_identifier_spelling(report)
    check_shell_substitution(report)
    check_rule_enforcement(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label["identifier spelling"],
        "every identifier in this tree is spelled American",
        "\n".join(f.where for f in by_label["identifier spelling"][:12]),
    )

    # ------------------------------------------------------------------ storage keys
    #
    # The reader binds a key to a store BY ITS FILE, which is sound only while no file in
    # `app/src` opens both. That is a property of the tree rather than of the code, so it is
    # asserted here: the day it stops holding, this case fails and the row starts reporting
    # the file instead of guessing at it.
    sites, site_findings = _storage_sites()
    ok(
        not site_findings,
        "no file in app/src touches both stores, so the file is a sound binding",
        str(site_findings),
    )
    # `banchi.session.box` STOOD HERE UNTIL 2026-09-11 and is gone (D141): six of D27's seven
    # session keys moved to the device, and `banchi.session.captureId` is the one left — which
    # is the same shape (declared as a const in `SESSION_KEYS` and read through `readSession`'s
    # parameter) and so still exercises both halves this case is named for. A live key has to
    # be named because the point is that the READER resolves it, not that a string appears.
    ok(
        "banchi.capture.deviceId" in sites["local"]
        and "banchi.session.captureId" in sites["session"],
        "keys resolve to the right store through a const and through a helper's parameter",
        str(sorted(sites["local"]) + sorted(sites["session"])),
    )
    ok(
        _NUMBER_WORDS.get((_ROSTER_RE.search(read(ROOT / "CLAUDE.md")) or [None, "x"])[1].lower())
        == len(sites["local"]),
        "CLAUDE.md's count word parses and equals the number of device-local keys",
        str(sorted(sites["local"])),
    )
    report = Report()
    check_storage_keys(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label["storage keys"],
        "every storage key the app writes is published where the docs promise it is",
        str(by_label["storage keys"]),
    )

    # ------------------------------------------------------------------ codex hooks (D135)
    #
    # `_hook_triples` is the extractor, pure and file-free, so the mutation this row exists
    # for can be driven on synthetic dicts rather than on the real tree — the same split
    # `_storage_sites` uses above, for the same reason: the logic that could be wrong lives
    # here, not in which two paths the real check reads.
    print("\ncodex hooks reads (event, matcher, command) out of a settings-shaped dict")
    claude_shaped = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Write|Edit", "hooks": [{"type": "command", "command": "scripts/guard-opsec.sh"}]},
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "scripts/reap.py --hook"}]},
            ],
            "Stop": [{"hooks": [{"type": "command", "command": "scripts/stop-gate.sh"}]}],
        }
    }
    triples = _hook_triples(claude_shaped)
    ok(
        ("PreToolUse", "Write|Edit", "scripts/guard-opsec.sh") in triples
        and ("PreToolUse", "Bash", "scripts/reap.py --hook") in triples,
        "a matcher on the entry is carried into the triple",
        str(sorted(triples)),
    )
    ok(
        ("Stop", "", "scripts/stop-gate.sh") in triples,
        "an event with no tool to match reads its matcher as the empty string, not skipped",
        str(sorted(triples)),
    )
    ok(not _hook_triples({"hooks": "not a dict"}) and not _hook_triples("not even a dict"),
       "a malformed hooks block reads as no hooks, not a crash")
    ok(not _hook_triples({"hooks": {"Stop": [{"hooks": [{"type": "prompt", "text": "x"}]}]}}),
       "a non-command hook (a prompt, say) contributes nothing to the roster")

    # THE MUTATION: drop one hook from the Codex side, prove the row reports exactly the
    # drop, restore it, prove the row is silent again. This is D135's own worked example —
    # `.codex/hooks.json` really did ship a day behind `WorktreeRemove` and `reap.py --hook`
    # — replayed here as data so it never depends on the two files staying out of sync.
    print("\nremoving one hook from one side is reported, and restoring it clears the report")
    codex_shaped = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Write|Edit", "hooks": [{"type": "command", "command": "scripts/guard-opsec.sh"}]},
            ],
            "Stop": [{"hooks": [{"type": "command", "command": "scripts/stop-gate.sh"}]}],
        }
    }
    missing = _hook_triples(claude_shaped) - _hook_triples(codex_shaped)
    ok(
        missing == {("PreToolUse", "Bash", "scripts/reap.py --hook")},
        "the row's own diff finds exactly the hook the mutation removed",
        str(missing),
    )
    codex_shaped["hooks"]["PreToolUse"].append(
        {"matcher": "Bash", "hooks": [{"type": "command", "command": "scripts/reap.py --hook"}]}
    )
    ok(
        not (_hook_triples(claude_shaped) - _hook_triples(codex_shaped))
        and not (_hook_triples(codex_shaped) - _hook_triples(claude_shaped)),
        "restoring the hook clears the diff in both directions",
        str(_hook_triples(claude_shaped) ^ _hook_triples(codex_shaped)),
    )
    ok(
        ("PreToolUse", "Bash", "scripts/reap.py --hook") in _hook_triples(claude_shaped)
        and ("PreToolUse", "Write|Edit", "scripts/decision-context.py")
        not in _hook_triples(claude_shaped),
        "the triple is exact — same event and matcher, a different command is not a match",
    )

    # And the real tree: the two files this row actually reads should already agree, because
    # the change that added the row is the same change that brought .codex/hooks.json to
    # parity (D135) — a self-test that could not pass against its own repository would be
    # asserting a rule this tree does not follow.
    report = Report()
    check_codex_hooks(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label["codex hooks"],
        ".codex/hooks.json and .claude/settings.json name the same hooks in this tree",
        str(by_label["codex hooks"]),
    )

    # The staged-mode primitives, which have no loud failure mode: every one of them
    # answers plausibly against the worktree while auditing a tree the commit will not
    # produce. Driven through the module globals because that is how audit() drives them.
    print("\nstaged mode answers about the index, not the worktree")
    global _INDEX_PATHS
    # A WORKTREE IS ANOTHER BRANCH'S SOURCE INSIDE THIS TREE, and walking it checks one branch's
    # prose against another branch's code. Observed on 2026-08-29: a concurrent session's worktree
    # documented `make worktree-setup`, a target real on ITS branch, and the `make targets` check
    # failed a commit on THIS one. Two branches are allowed to disagree.
    #
    # THE STAGED PATH IS COVERED HERE AND THE ON-DISK PATH IS COVERED BY `nested_worktrees`, which
    # asks git rather than guessing a name. Only the first is reachable from a self-test: the
    # second needs a real repository with a real worktree in it, and was verified by hand — a
    # worktree named `zz-scratch-wt`, which no name rule could guess, walked zero files. That gap
    # is named rather than papered over.
    print("\na worktree inside the tree is another branch, and is not walked")
    _INDEX_PATHS = {
        "docs/GATES.md",
        ".claude/worktrees/other-branch/CLAUDE.md",
        ".claude/worktrees/other-branch/docs/GATES.md",
    }
    walked = [rel(p) for p in _walk(ROOT, (".md",))]
    ok(
        walked == ["docs/GATES.md"],
        "a worktree's markdown is not discovered, however tracked-looking the path",
        str(walked),
    )
    ok("worktrees" in SKIP_DIRS, "the convention is pruned by name as well as by git")
    try:
        _INDEX_PATHS = {"docs/GATES.md", "docs/specs/batch-script.md", "harness/run.py"}
        ok(exists(ROOT / "docs" / "GATES.md"), "a tracked file exists")
        ok(not exists(ROOT / "Makefile"), "an untracked file does not, however real on disk")
        ok(exists(ROOT / "docs"), "a directory exists through the files under it")
        ok(not exists(ROOT / "scripts"), "a directory with nothing tracked under it does not")
        ok(
            child_names(ROOT / "docs") == {"GATES.md", "specs"},
            "children come from the index, one level deep",
            str(child_names(ROOT / "docs")),
        )
        ok(
            [rel(p) for p in _walk(ROOT, (".md",))] == ["docs/GATES.md", "docs/specs/batch-script.md"],
            "discovery enumerates the index",
            str([rel(p) for p in _walk(ROOT, (".md",))]),
        )
        ok(
            [rel(p) for p in glob_files(ROOT / "docs", "*.md")] == ["docs/GATES.md"],
            "glob matches within one directory of the index",
            str([rel(p) for p in glob_files(ROOT / "docs", "*.md")]),
        )
        # The orphan scan's deep mode, through the index. It is the only check in this file
        # that walks a directory tree, so it is the only one that could quietly go back to
        # asking the worktree — and in the hook the worktree is the tree that will not be
        # committed.
        ok(
            source_names(ROOT / "docs", (".md",), True) == {"GATES.md", "specs/batch-script.md"},
            "a deep scan enumerates the index, nested paths and all",
            str(sorted(source_names(ROOT / "docs", (".md",), True))),
        )
    finally:
        leave_staged_mode()
    ok(_INDEX_PATHS is None and exists(ROOT / "Makefile"), "and the worktree comes back")

    # Argparse's own exit for a bad flag is 2 — this script's advisory code, which the
    # pre-commit hook prints and allows. A caller that grew a stale flag would switch the
    # gate off and look routine doing it.
    print("\ninvoking this script wrongly is not mistaken for an advisory")
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            build_parser().parse_args(["--no-such-flag"])
        code: Optional[int] = None
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else None
    ok(code == EXIT_USAGE, f"an unknown flag exits {EXIT_USAGE}, never 2", f"exited {code}")
    report = Report()
    check_audit_invocation(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(not by_label["audit invocation"], "every caller's flags are declared", str(by_label))

    # The reason this check asks argparse instead of reading a list out of it: argparse
    # accepts unambiguous abbreviations, so a caller passing `--stag` really does run and
    # is not a finding. Set membership against the declared options called it one.
    with tempfile.TemporaryDirectory() as tmp:
        caller = Path(tmp) / "caller.sh"
        caller.write_text("python3 scripts/docs-audit.py --stag\n", encoding="utf-8")
        saved, INVOKERS[:] = list(INVOKERS), [rel(caller)]
        try:
            report = Report()
            check_audit_invocation(report)
            rows = {row.check: row.findings for row in report.checks}
            ok(
                not rows["audit invocation"],
                "an abbreviation argparse accepts is not a finding",
                str(rows["audit invocation"]),
            )
            caller.write_text("python3 scripts/docs-audit.py --stagx\n", encoding="utf-8")
            report = Report()
            check_audit_invocation(report)
            rows = {row.check: row.findings for row in report.checks}
            ok(
                len(rows["audit invocation"]) == 1,
                "a flag argparse rejects is",
                str(rows["audit invocation"]),
            )
        finally:
            INVOKERS[:] = saved

    # A check that is defined and never dispatched prints nothing at all, so this row is the
    # only one whose failure mode is an ABSENT row. Every case below is a way for the
    # reconciliation to look like it ran: a reader that cannot see a loop, a check renamed
    # out of the prefix, an exemption nobody re-read.
    print("\nthe route-roster reader survives the shapes the specs actually take")
    # THE `[number]` CASE IS HERE BECAUSE IT SHIPPED BROKEN FOR ONE RUN. `Record<(typeof
    # RING)[number], string>` puts a bracket in the TYPE, and a reader that took the first
    # bracket after the marker read `[number]`, found no routes in it, and reported "you
    # pinned nothing" — a finding that is not what is wrong and that nobody could act on.
    # A reader that reports the wrong defect is worse than one that reports none, because
    # the first thing a person does with it is stop believing the row.
    shaped = (
        "/* ROUTE-ROSTER hotkey */\n"
        "const RING = [\n  '#/',\n  '#/runs',\n] as const\n"
        "/* ROUTE-ROSTER all */\n"
        "const VIEW: Record<(typeof RING)[number], string> = {\n"
        "  '#/': 'main.capture',\n  '#/codes': 'main.codes',\n}\n"
    )
    marks = list(ROSTER_MARK.finditer(shaped))
    ok(len(marks) == 2, "two markers in one file are both found", f"found {len(marks)}")
    read_back = []
    for mark in marks:
        assign = shaped.find("=", mark.end())
        opening = min(
            (found for found in (shaped.find(bracket, assign) for bracket in "[{") if found != -1),
            default=-1,
        )
        read_back.append(ROUTE_HASH.findall(_strip_ts_comments(_balanced(shaped, opening))))
    ok(read_back[0] == ["#/", "#/runs"], "an array roster reads in order", str(read_back[0]))
    ok(
        read_back[1] == ["#/", "#/codes"],
        "an object roster reads its KEYS, past a `[number]` in the type",
        str(read_back[1]),
    )

    # A route named in prose is not a route the file pins. Both specs discuss routes they
    # deliberately do not walk, and counting those would fire the "declare a roster" arm at
    # a file that is behaving.
    ok(
        ROUTE_HASH.findall(_strip_ts_comments("// the ring cannot reach '#/gallery'\nopen('/#/runs')"))
        == ["#/runs"],
        "a route named in a comment is not counted as pinned",
    )

    # The live table, read the way the check reads it. An extractor that silently returns
    # nothing would make every roster below it "missing everything" — loud, but wrong about
    # which side moved.
    live, live_findings = expected_rosters()
    ok(
        bool(live.get("all")) and live["all"][0] == "#/",
        "App.tsx's ROUTES table is readable and starts at the capture screen",
        f"{live.get('all')} / {[f.message for f in live_findings]}",
    )
    ok(
        set(live.get("hotkey", [])) <= set(live.get("all", [])) and live.get("hotkey") != live.get("all"),
        "the hotkey ring is a proper subset of the registered routes",
        f"ring {live.get('hotkey')} of {live.get('all')}",
    )

    print("\nevery check defined is reconciled against the ones audit() calls")
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp) / "fixture.py"

        def dispatch(source: str, exempt: Optional[Dict[str, str]] = None) -> List[Finding]:
            fixture.write_text(source, encoding="utf-8")
            saved_exempt = dict(UNDISPATCHED)
            UNDISPATCHED.clear()
            UNDISPATCHED.update(exempt or {})
            try:
                report = Report()
                check_dispatch(report, fixture)
                return {row.check: row.findings for row in report.checks}["check dispatch"]
            finally:
                UNDISPATCHED.clear()
                UNDISPATCHED.update(saved_exempt)

        emit = "def {0}(report):\n    report.add('{0}', 'mechanical', [])\n\n"
        wired = (
            emit.format("check_one")
            + emit.format("check_two")
            + "def audit():\n    report = Report()\n    check_one(report)\n    check_two(report)\n"
        )
        ok(not dispatch(wired), "two checks defined, both called, is clean", str(dispatch(wired)))

        forgotten = wired.replace("    check_two(report)\n", "")
        found = dispatch(forgotten)
        ok(
            len(found) == 1 and "check_two" in found[0].message,
            "the one whose call was forgotten is named, and only it",
            str(found),
        )
        ok(
            not dispatch(forgotten, {"check_two": "deliberately not run"}),
            "an UNDISPATCHED entry accounts for it — the loud escape route",
            str(dispatch(forgotten, {"check_two": "deliberately not run"})),
        )
        found = dispatch(wired, {"check_two": "stale reason"})
        ok(
            len(found) == 1 and "check_two" in found[0].message,
            "and the entry is reported the moment audit() calls it after all",
            str(found),
        )
        found = dispatch(wired, {"check_ghost": "renamed away"})
        ok(
            len(found) == 1 and "check_ghost" in found[0].message,
            "an entry naming nothing defined here is dangling, so the list cannot only grow",
            str(found),
        )

        # Dispatch through a loop: the exact restructuring whose halfway version defeated the
        # retired statement-reading registry. A name is a name wherever it appears.
        looped = (
            emit.format("check_one")
            + emit.format("check_two")
            + "def audit():\n    report = Report()\n"
            + "    for run in (check_one, check_two):\n        run(report)\n"
        )
        ok(not dispatch(looped), "dispatch through a loop is dispatch", str(dispatch(looped)))

        # The rename hole, closed by reading both signals. `audit_two` emits a row and no
        # longer looks like a check by name — which is what a diff that reads as tidying does.
        renamed = (
            emit.format("check_one")
            + emit.format("audit_two")
            + "def audit():\n    report = Report()\n    check_one(report)\n"
        )
        found = dispatch(renamed)
        ok(
            len(found) == 1 and "audit_two" in found[0].message,
            "a check renamed out of the prefix still emits a row, and is still found",
            str(found),
        )

        moved = (
            emit.format("check_one")
            + "CHECKS = (check_one,)\n\n"
            + "def audit():\n    report = Report()\n    for run in CHECKS:\n        run(report)\n"
        )
        found = dispatch(moved)
        ok(
            len(found) == 1 and "none of the checks" in found[0].message,
            "dispatch moved out of audit() is one finding about the reader, not one per check",
            str(found),
        )
        found = dispatch(emit.format("check_one"))
        ok(
            len(found) == 1 and "no `audit()`" in found[0].message,
            "a file with no audit() at all says so, rather than reporting every check unrun",
            str(found),
        )
        found = dispatch("def audit(:\n")
        ok(
            len(found) == 1 and "cannot be parsed" in found[0].message,
            "and a source that will not parse is a finding, not an empty roster",
            str(found),
        )

    # THE ROUTE CENSUS READS PROSE THAT IS WRAPPED, and both halves of that were wrong in
    # its first draft: the seam between two Python string literals defeated the match, and
    # the claims were written as regexes with the whitespace hand-rolled to one space. The
    # result was a row that printed ten green counts while the owner subcount it named was
    # matched by nothing at all. These three cases are that bug, kept.
    print("\na claim wrapped across two string literals is still one sentence")
    wrapped = '        "a hash router, NINE of them the "\n                "owner\'s — the capture"\n'
    bridged = _bridge_literals(wrapped)
    ok(len(bridged) == len(wrapped), "bridging preserves length, so a finding's line number still points at the sentence")
    ok(bridged.count("\n") == wrapped.count("\n"), "and preserves the newlines it bridges across")
    ok(
        re.search(_census_pattern("([A-Za-z]+) of them the owner's"), bridged) is not None,
        "the owner subcount matches once the seam is whitespace",
        repr(bridged),
    )
    ok(
        re.search(_census_pattern("([A-Za-z]+) of them the owner's"), wrapped) is None,
        "and did not before, which is how it went unchecked",
    )
    ok(
        _census_pattern("has ([A-Za-z]+) screens") == r"has\s+([A-Za-z]+)\s+screens",
        "a claim is written as the sentence reads and compiled to flexible whitespace",
        _census_pattern("has ([A-Za-z]+) screens"),
    )

    # THE CONSUMER BLOCK IS A TWO-COLUMN LAYOUT AND A SEPARATOR-BASED READER GOT IT WRONG
    # TWICE, in opposite directions: a wrapped description ended the block after one entry,
    # and the longest path in it is separated from its description by a SINGLE space, so a
    # `\s{2,}` split dropped that row too. Both misreads made a correct docstring fail.
    print("\nthe map's consumer list is read by column, not by separator")
    _saved = globals()["MAP"]
    try:
        sample = ROOT / "docs" / "map.py"
        globals()["MAP"] = sample
        word, rows = _consumer_block()
        ok(word == "four", "the declared count word is read", str(word))
        ok(len(rows) == 4, "all four rows are found, wrapped descriptions and all", str(rows))
        ok(
            "scripts/decision-context.py" in rows,
            "including the row whose path leaves a single space before its description",
            str(rows),
        )
        ok(
            "you, or an agent" in rows,
            "and the one entry that is a phrase with spaces in it, not a path",
            str(rows),
        )
        ok("TRACKS" in _map_sections(), "TRACKS is a section this check can see", str(_map_sections()))
    finally:
        globals()["MAP"] = _saved

    print("\na figure the section merely contains is not a figure it attributes")
    # The three rows below were each green while the thing they pin was wrong. These cases are
    # the extractors that fixed them, driven on literals rather than on the live documents, so
    # a later edit to either document cannot quietly turn them back into what they were.
    _section = (
        "serves on `class CaptureServer(ThreadingHTTPServer)` with `request_queue_size = 128`\n"
        "and `CaptureHandler.timeout = 15`. `REQUEST_SLOTS = 4` is the bound.\n"
        "| `REQUEST_SLOTS` | 1 | 2 | 3 | **4** | 6 | 8 | 12 | 24 | 48 |\n"
    )
    for _what, _code_re, _shape, _anchor, _published in _CONCURRENCY_FACTS:
        _said = _anchor.search(_section)
        ok(_said is not None, f"the attributed form of {_what} is found", _published)
    _swapped = _section.replace("timeout = 15", "timeout = 4").replace("REQUEST_SLOTS = 4 is", "REQUEST_SLOTS = 15 is")
    ok(
        _CONCURRENCY_FACTS[1][3].search(_swapped).group(1) == "4",
        "and it reads the value beside the NAME, not the first plausible integer in the table",
        _swapped,
    )

    print("\nthe bracket ramp is resolved through section 9's own legend")
    _legend = (
        "| bracket | stops |\n| --- | --- |\n"
        "| chrome | `#FFFFFF #B8C8D8 #F2F8FF #8FA4B8` |\n"
        "| pale gold | `#FFFBEE #E8CE8A #FFFDF6 #C0A254` |\n"
    )
    _ramps = {n.strip(): v.split() for n, v in _S9_BRACKET.findall(_legend)}
    ok(sorted(_ramps) == ["chrome", "pale gold"], "both named ramps are read", str(sorted(_ramps)))
    ok(
        _ramps.get("chrome") == ["#FFFFFF", "#B8C8D8", "#F2F8FF", "#8FA4B8"],
        "and a name resolves to the four hexes it stands for, not to the word",
        str(_ramps.get("chrome")),
    )

    # THE BROWSER MATRIX'S GATE, READ BOTH WAYS (D141). The wiring reader is pure, so each
    # way the workflow could quietly stop gating is mutated into it here; the classifier is
    # imported the way `prose-guard.py` is and asked the two questions the gate exists for.
    print("\nthe browser scope's wiring is read, and each silent failure is mutated in")
    _workflow = read(CHECK_WORKFLOW) if exists(CHECK_WORKFLOW) else ""
    _gate = browser_gate_findings(_workflow)
    ok(not _gate, "the workflow as it stands reads the scope fail-open", "\n".join(m for _, m in _gate))
    _closed = _workflow.replace("outputs.run != 'false'", "outputs.run == 'true'")
    ok(any("fail-open" in m for _, m in browser_gate_findings(_closed)),
       "the fail-closed spelling `== 'true'` is refused by name")
    _gated_on = _workflow.replace("on:\n  pull_request:", "on:\n  pull_request:\n    paths: ['app/**']", 1)
    ok(any("`on:` block" in m for _, m in browser_gate_findings(_gated_on)),
       "a `paths` filter in the `on:` block, which would gate every job, is refused")
    _unwired = _SCOPE_STEP_RE.sub("python3 scripts/other.py classify", _workflow)
    ok(any("consulted by nothing" in m for _, m in browser_gate_findings(_unwired)),
       "a workflow that never runs the classifier is reported as gating nothing")
    _recording = _workflow.replace("if: github.event_name != 'push'", "if: always()")
    ok(any("skipped matrix" in m for _, m in browser_gate_findings(_recording)),
       "a pass record written for a skipped matrix is refused")
    _module = _sibling("browser-scope.py")
    ok(_module is not None, "scripts/browser-scope.py imports")
    if _module is not None:
        _read = lambda side, path: None  # noqa: E731 - no recipe is consulted by these paths
        ok(not _module.classify_paths(["docs/DECISIONS.md"], _read).run, "a docs-only change skips")
        ok(_module.classify_paths(["app/src/App.tsx"], _read).run, "a screen change runs")
    _code = "const T = {\n  'harness/traces/x.json': 1,\n} // docs/DEBTS.md\n"
    ok(_repo_literals(_code, {"harness/traces/x.json", "docs/DEBTS.md"}) == ["harness/traces/x.json"],
       "a code string naming a tracked file is a dependency and a comment naming one is not")

    # THE FIX: a branch's own unclaimed slug is exempt from "must appear in the index";
    # nothing else this row ever caught is weakened. Six cases, each pinning one arm.
    # IDS CARRY THEIR LEADING `D` HERE, matching exactly what `want`/`got` produce in
    # check_decision_index — the shape the first version of this test got wrong, which is
    # exactly how the double-`D` bug in `_is_unclaimed` survived its own self-test.
    # COMPOSED FROM PIECES, NEVER SPELLED WHOLE: a slug-shaped literal sitting in THIS file
    # is exactly what `check_decision_ids`'s line-by-line scan below reads as a real
    # citation to resolve — the trap this file's own `1476` comment already names.
    print("\nthe decision index tolerates an unclaimed slug missing from the block")
    _slug_1 = "D-" + "not" + "-yet" + "-claimed"
    _slug_2 = "D-" + "a" + "-ghost"
    _numbered = [("D42", "Answer"), ("D43", "Question")]
    _with_slug = _numbered + [(_slug_1, "Something unclaimed")]
    ok(_decision_index_findings(_with_slug, _numbered) == [],
       "an unclaimed slug absent from the index is not a finding")
    ok(_decision_index_findings(_numbered + [("D44", "Third")], _numbered) != [],
       "a CLAIMED number absent from the index is still a finding — the exemption is slugs only")
    ok(any("has no heading" in f.message
           for f in _decision_index_findings(_numbered, _numbered + [(_slug_2, "Ghost")])),
       "an index line for a slug with no matching heading is still a finding")
    ok(any("index line reads" in f.message
           for f in _decision_index_findings(_with_slug, [("D42", "Answer"), ("D43", "Wrong title")])),
       "a claimed entry's title mismatch is still caught with a slug in the corpus too")
    ok(bool(_decision_index_findings([], [])
            and "no decision index found" in _decision_index_findings([], [])[0].message),
       "an empty index is still refused outright, corpus present or not")
    ok(not _is_unclaimed("D42") and _is_unclaimed(_slug_1),
       "the exemption test itself: a number is claimed, a slug is not — ids carry their `D`")
    # A ROW THAT EXAMINED NOTHING IS NOT A ROW THAT PASSED. Driven over a synthetic report,
    # because the thing under test is the REPORTING LAYER and a real run cannot pose a row
    # with no subject without breaking a walk. Every arm here is a state the file printed
    # `ok` for before 2026-09-12.
    print("\na row that examined nothing does not print the word a row that examined everything does")

    # ROWS BUILT AS `Row`, NEVER THROUGH `report.add`. `defined_checks` marks any
    # module-level function that emits a row AS A CHECK, deliberately and by union — so a
    # `report.add` anywhere in `self_test` makes `check dispatch` report `self_test` as an
    # undispatched check. Measured, one edit after that row was extended. Appending the
    # tuple is also the more honest fixture: it poses the report a check would leave.
    def _subject(rows, staged=False, drop=""):
        report = Report()
        posed = {check for check, _, _ in rows}
        # Every pinned name present, so the stale-pin leg is satisfied and the arm under
        # test is the only thing being read. `drop` omits one, which is how the stale-pin
        # arm is posed.
        for name in EXPECTED_EMPTY:
            if name not in posed and name != drop:
                report.checks.append(Row(name, MECHANICAL, [], "", 1))
        for check, findings, scanned in rows:
            report.checks.append(Row(check, MECHANICAL, findings, "", scanned))
        check_subject_counts(report, staged)
        return {row.check: row.findings for row in report.checks}["subject counts"]

    _pinned = next(n for n, (when, _) in EXPECTED_EMPTY.items() if when == "always")
    _staged_pin = next(n for n, (when, _) in EXPECTED_EMPTY.items() if when == "staged")
    ok(not _subject([("paths", [], 2964)]), "a row with subjects and no findings is clean")
    ok(any("declared no subject count" in m for _, m in _subject([("paths", [], None)])),
       "a row that declared no subject count is a finding, not an ok")
    ok(any("examined NOTHING" in m for _, m in _subject([("unpinned row", [], 0)])),
       "an UNPINNED row that examined nothing is a finding")
    ok(not _subject([(_pinned, [], 0)]),
       f"a row pinned expected-empty ({_pinned}) may examine nothing")
    ok(any("examined nothing in a FULL run" in m
           for _, m in _subject([(_staged_pin, [], 0)], staged=False))
       and not _subject([(_staged_pin, [], 0)], staged=True),
       "a `staged` pin permits zero under --staged and refuses it in a full run")
    ok(any("no row by that name was emitted" in m
           for _, m in _subject([(_pinned + "-renamed", [], 1)], drop=_pinned)),
       "a pin naming a row the file no longer emits is reported stale")
    ok(not _subject([("with findings", [Finding("x", "y")], 0)]),
       "a row WITH findings is judged on the findings, never on an empty subject")
    _rendered = Report()
    _rendered.checks.append(Row("zero", MECHANICAL, [], "a summary", 0))
    _rendered.checks.append(Row("some", MECHANICAL, [], "a summary", 7))
    _rendered.checks.append(Row("bare", MECHANICAL, [], "a summary", None))
    ok("none zero" in re.sub(r"\s+", " ", _rendered.render()),
       "the render prints `none` for an empty subject")
    ok("ok   some" in _rendered.render(), "and `ok` where there was one")
    ok("bare bare" in re.sub(r"\s+", " ", _rendered.render()),
       "and `bare` where no count was declared")
    ok(json.loads(_rendered.as_json(0))["rows"][0]["vacuous"] is True
       and json.loads(_rendered.as_json(0))["rows"][1]["vacuous"] is False,
       "--json carries the integer and the flag, so nothing parses the render")

    # A DELETION NARRATED IN PROSE IS NOT A RESURRECTION, and `capture_server.py` narrates
    # one. The classifier is what keeps the row off it, so it is exercised here directly.
    print("\na deleted symbol in a comment is the record of the deletion; in code it is the defect")
    _py = 'def f():\n    """Mentions Ghost in a docstring."""\n    # Ghost in a comment\n    return 1\n'
    ok("Ghost" not in _prose_blanked(Path("x.py"), _py),
       "a Python docstring and a comment are both blanked")
    ok("Ghost" in _prose_blanked(Path("x.py"), 'Ghost = 1\n# Ghost\n'),
       "and an assignment to the same name survives")
    ok(_prose_blanked(Path("x.py"), _py).count("\n") == _py.count("\n"),
       "offsets survive, so a reported line number is the real one")
    ok("Ghost" not in _prose_blanked(Path("x.ts"), "/* Ghost */\nconst a = 1\n"),
       "a TypeScript block comment is blanked too")
    ok("Ghost" in _prose_blanked(Path("x.ts"), "const Ghost = 1 /* gone */\n"),
       "and a declaration beside one survives")

    # THE MONEY BUTTON'S FIGURE, over source strings rather than the tree, so the two
    # readers are proved before the row is trusted to compare with them.
    print("\nthe money button's figure is read from the call, never from the wording")
    _reader = ast.parse('import re\n_E = re.compile(r"^cost\\s+\\$([0-9.]+)\\s*$", re.M)\n')
    ok(_compiled_assign(_reader, "_E") == ("^cost\\s+\\$([0-9.]+)\\s*$", re.M),
       "a module-level re.compile is read with its multiline flag")
    ok(_compiled_assign(_reader, "_MISSING") is None, "and a name that is not there is None")
    _writer = ast.parse('say(f"cost  ${_estimate(x)}")\nsay(f"other  ${bill(x)}")\n')
    ok(_rendered_say(_writer, "_estimate") == f"cost  ${_ESTIMATE_SAMPLE}",
       "the line a say() whose f-string calls the producer would print is rendered")
    ok(_rendered_say(_writer, "bill") == f"other  ${_ESTIMATE_SAMPLE}",
       "and the sibling line is a different subject, not the same one")
    ok(_rendered_say(ast.parse('say("cost  $0.00")\n'), "_estimate") is None,
       "a line that no longer calls the producer is reported absent rather than matched")

    print("\na published gate threshold is compared as a number")
    ok(_CRITERION_BAR.search("holdout_accuracy >= 0.95").group(2) == "0.95",
       "the floor is lifted out of the criterion's own comparison")
    ok(_CRITERION_BAR.search("holdout_accuracy > 0.9").group(1) == ">",
       "and the operator with it, so `>` is not read as `>=`")
    ok(_CRITERION_BAR.search("holdout_accuracy is high") is None,
       "a criterion with no comparison is unreadable rather than guessed at")

    print("\nevery published harness count is the length of TESTS")
    ok(not _harness_claim_findings({f"T{n}" for n in range(1, 10)}),
       "nine registered against a tree that publishes nine")
    ok(any("registers 10" in m for _, m in _harness_claim_findings({f"T{n}" for n in range(1, 11)})),
       "ten registered is a finding against every one of the published counts")
    ok(not _harness_claim_findings(set()),
       "and an unreadable TESTS yields nothing here — `harness tests` own legs say so instead")

    print("\nunscoped walk: the matcher, against synthetic fixtures")
    with tempfile.TemporaryDirectory() as tmp:
        # Arm (a): a NEW unscoped call must be found and reported as not-on-the-allowlist.
        fixture = Path(tmp) / "fixture_new_site.py"
        fixture.write_text(
            "def do_something_new():\n"
            "    inventory = Store().read().inventory\n"
            "    for card in inventory.cards.values():\n"
            "        touch(card)\n",
            encoding="utf-8",
        )
        sites = unscoped_walk_sites([fixture])
        ok(
            any(fname == "do_something_new" and shape == "values"
                for _, _, fname, shape in sites),
            "a new `.values()` call on `inventory.cards` is found by the scanner",
            str(sites),
        )

        # Arm (b): a call the scanner does NOT recognise as unscoped — a filtered
        # `select(...)` with a keyword — must not appear, proving the keyword check
        # actually narrows `select` and does not just always fire.
        fixture2 = Path(tmp) / "fixture_scoped_select.py"
        fixture2.write_text(
            "def do_scoped():\n"
            "    for key, row in inventory.cards.select((\"box\",), box=3):\n"
            "        touch(row)\n",
            encoding="utf-8",
        )
        sites2 = unscoped_walk_sites([fixture2])
        ok(
            not sites2,
            "a `select(...)` called WITH a filter keyword is never flagged",
            str(sites2),
        )

        # Arm (c): `to_payload()` is only flagged on something that looks like an
        # Inventory — a differently-typed object's `to_payload()` must not match, proving
        # the guard does not simply grep the method name across the whole file.
        fixture3 = Path(tmp) / "fixture_other_to_payload.py"
        fixture3.write_text(
            "def do_other():\n"
            "    book = load_corpus()\n"
            "    return book.to_payload()\n",
            encoding="utf-8",
        )
        sites3 = unscoped_walk_sites([fixture3])
        ok(
            not sites3,
            "`book.to_payload()` (not an Inventory) is never flagged",
            str(sites3),
        )

    print("\nunscoped walk: the row itself, against the two failure shapes item 1's spec names")

    # These three arms call `check_unscoped_walk(report)` ITSELF, with the module globals
    # it reads patched for the duration — the same save/patch/restore-in-`finally` shape
    # used above for `MAP`. Driving only `unscoped_walk_sites` (the pure matcher) and the
    # comparison arithmetic inline, as the first draft of this block did, proved nothing
    # about the ROW: `check_unscoped_walk` walks the REAL `_UNSCOPED_WALK_ROOTS` regardless
    # of what a fixture computes, so a mutation that broke the row's own comparison loops
    # (e.g. `for path, fname, shape in ():` in place of `sorted(allowed)`, or `if False:`
    # in place of the not-on-the-allowlist test) left every arm below green. Calling the
    # row function directly is what closes that gap.

    # Arm (d): a site not on the allowlist fails the ROW. `_UNSCOPED_WALK_SINGLE_FILES` is
    # patched to add one fixture file the real scan would not otherwise see.
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp) / "fixture_new_site.py"
        fixture.write_text(
            "def do_something_new():\n"
            "    for card in inventory.cards.values():\n"
            "        touch(card)\n",
            encoding="utf-8",
        )
        _saved_files = globals()["_UNSCOPED_WALK_SINGLE_FILES"]
        try:
            globals()["_UNSCOPED_WALK_SINGLE_FILES"] = _saved_files + (fixture,)
            report = Report()
            check_unscoped_walk(report)
        finally:
            globals()["_UNSCOPED_WALK_SINGLE_FILES"] = _saved_files
        by_label = {row.check: row.findings for row in report.checks}
        ok(
            any("do_something_new" in f.message for f in by_label["unscoped walk"]),
            "a site absent from UNSCOPED_WALK_ALLOWED fails the row, naming the function",
            str(by_label["unscoped walk"]),
        )

    # Arm (e): an allowlist entry naming a site the tree no longer has fails the ROW as
    # stale — the "removed site not removed from the list" failure item 1's spec text
    # calls out by name. `UNSCOPED_WALK_ALLOWED`/`UNSCOPED_WALK_EXPECTED` are patched
    # together (adding one entry the real tree does not have, and raising the pinned
    # count to match, so this arm isolates the stale-entry branch from the count-mismatch
    # branch below).
    _saved_allowed = globals()["UNSCOPED_WALK_ALLOWED"]
    _saved_expected = globals()["UNSCOPED_WALK_EXPECTED"]
    try:
        globals()["UNSCOPED_WALK_ALLOWED"] = _saved_allowed | {
            ("server/capture_server.py", "no_such_function", "values"),
        }
        globals()["UNSCOPED_WALK_EXPECTED"] = _saved_expected + 1
        report = Report()
        check_unscoped_walk(report)
    finally:
        globals()["UNSCOPED_WALK_ALLOWED"] = _saved_allowed
        globals()["UNSCOPED_WALK_EXPECTED"] = _saved_expected
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        any("no_such_function" in f.message for f in by_label["unscoped walk"]),
        "an allowlist entry the scan does not find fails the row, naming the function",
        str(by_label["unscoped walk"]),
    )

    # Arm (f'): the pinned-count mismatch fails the ROW on its own, with no other change —
    # `UNSCOPED_WALK_EXPECTED` alone disagreeing with `len(UNSCOPED_WALK_ALLOWED)`.
    _saved_expected = globals()["UNSCOPED_WALK_EXPECTED"]
    try:
        globals()["UNSCOPED_WALK_EXPECTED"] = _saved_expected + 1
        report = Report()
        check_unscoped_walk(report)
    finally:
        globals()["UNSCOPED_WALK_EXPECTED"] = _saved_expected
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        any("UNSCOPED_WALK_ALLOWED" in f.where and "pinned" in f.message
            for f in by_label["unscoped walk"]),
        "UNSCOPED_WALK_EXPECTED disagreeing with the allowlist's length fails the row",
        str(by_label["unscoped walk"]),
    )

    # Arm (f): end-to-end proof against the REAL tree, unpatched — the row itself, not
    # just the comparison logic, reports clean on a clean checkout. This is Step 5's
    # optional end-to-end check, folded in as its own arm rather than left as a manual
    # Measure step.
    report = Report()
    check_unscoped_walk(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label["unscoped walk"],
        "the real tree, scanned end to end, has zero findings on this row",
        str(by_label["unscoped walk"]),
    )

    # `import layering` (D63, store-scaling item 8): a lazy `from pipeline import x` inside
    # a function body must be caught the same as a module-level one — that shape is exactly
    # how the real defect shipped (`store/db.py:_add_search_index`, several hundred lines
    # in, invisible to a top-of-file reader).
    print("\nimport layering: store/ importing pipeline/ is caught, module-level or lazy")
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp) / "fixture_lazy_import.py"
        fixture.write_text(
            "def _add_something(conn):\n"
            "    from pipeline import join as _join\n"
            "    return _join.join_key('1', '2')\n",
            encoding="utf-8",
        )
        findings = _pipeline_imports(fixture)
        ok(
            any("from pipeline import" in spelling for _, spelling in findings),
            "a lazy `from pipeline import x` inside a def is found by the scanner",
            str(findings),
        )

        clean = Path(tmp) / "fixture_no_pipeline.py"
        clean.write_text(
            "from store.numbers import join_key\n\n\ndef f():\n    return join_key('1', '2')\n",
            encoding="utf-8",
        )
        ok(
            not _pipeline_imports(clean),
            "a file that imports nothing from pipeline/ is not flagged",
            str(_pipeline_imports(clean)),
        )

        report = Report()
        _saved_walk = globals()["_walk"]
        try:
            globals()["_walk"] = lambda root, suffixes: [fixture]
            check_import_layering(report)
        finally:
            globals()["_walk"] = _saved_walk
        by_label = {row.check: row.findings for row in report.checks}
        ok(
            any("pipeline" in f.message and "D63" in f.message
                for f in by_label["import layering"]),
            "the row itself fails on a fixture tree, citing D63",
            str(by_label["import layering"]),
        )

    report = Report()
    check_import_layering(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label["import layering"],
        "the real store/ tree, scanned end to end, imports nothing from pipeline/",
        str(by_label["import layering"]),
    )

    report = Report()
    check_dispatch(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label["check dispatch"],
        "this file's own checks are every one of them called by audit()",
        str(by_label["check dispatch"]),
    )

    print("\nno mechanism on screen: the extractor and the word list, over throwaway fixtures")
    with tempfile.TemporaryDirectory() as tmp_name:
        fixture_dir = Path(tmp_name)

        def written(name: str, body: str) -> Path:
            path = fixture_dir / name
            path.write_text(body)
            return path

        written(
            "Positive.tsx",
            "export function Positive() {\n"
            "  return <p>Held back for a reason (D134).</p>\n"
            "}\n",
        )
        written(
            "Comment.tsx",
            "// This screen used to cite (D134) here; it does not any more.\n"
            "/* the same token, (D134), inside a block comment */\n"
            "export function Comment() {\n"
            "  return <p>Held back for a reason.</p>\n"
            "}\n",
        )
        written(
            "DataAttr.tsx",
            "export function DataAttr() {\n"
            '  return <div data-decision="D134">Held back for a reason.</div>\n'
            "}\n",
        )
        written(
            "Jargon.tsx",
            "export function Jargon() {\n"
            "  return <p>Waiting on the pipeline to answer.</p>\n"
            "}\n",
        )
        written(
            "Path.tsx",
            "export function PathHit() {\n"
            "  return <p>See inventory/prices.json for the answer.</p>\n"
            "}\n",
        )
        written(
            "CsvName.tsx",
            "export function CsvName() {\n"
            "  return <a download=\"import.csv\">import.csv</a>\n"
            "}\n",
        )
        written(
            "Toast.tsx",
            "import { toast } from './kit/toast'\n"
            "export function fireToast() {\n"
            "  toast({ kind: 'ok', title: 'Sent to the corpus' })\n"
            "}\n",
        )
        written(
            "NoticeCode.tsx",
            "export function NoticeCode() {\n"
            "  return <Notice code=\"the corpus refused it\">Held back.</Notice>\n"
            "}\n",
        )
        written(
            "OperatorWords.tsx",
            "export function OperatorWords() {\n"
            "  return <p>3 copies across 2 boxes, from this run's export, still listed.</p>\n"
            "}\n",
        )
        written(
            "Gallery.tsx",
            "export function Gallery() {\n"
            "  return <p>Generated by scripts/build-mark.mjs from docs/specs/logo.md — the "
            "pipeline never touches this file.</p>\n"
            "}\n",
        )
        written(
            "Fulfillment.tsx",
            "export function Fulfillment() {\n"
            "  return <p>Waiting on the pipeline to answer.</p>\n"
            "}\n",
        )
        written(
            "CliInvocation.tsx",
            "export function CliInvocation() {\n"
            "  return <span title=\"Run `pkmnscan rescue` to rebind it.\">stranded</span>\n"
            "}\n",
        )
        written(
            "PullConfirm.tsx",
            "export function PullConfirm() {\n"
            "  return <p>Waiting on the pipeline to answer.</p>\n"
            "}\n",
        )

        strings = _run_user_strings(["--dir", str(fixture_dir)])
        ok(strings is not None, "the extractor runs over a throwaway fixture tree",
           "node or app/node_modules/typescript unavailable — install and re-run")
        if strings is not None:
            findings = _no_mechanism_findings(strings)
            hit_files = {f.where.split(":")[0].split("/")[-1] for f in findings}
            ok("Positive.tsx" in hit_files,
               "a decision citation in JSX text is caught")
            ok("Comment.tsx" not in hit_files,
               "the same token inside a comment is not — a comment is trivia, never a JsxText node")
            ok("DataAttr.tsx" not in hit_files,
               "a decision cite in a `data-*` attribute is not — that attribute name is not tracked")
            ok("Jargon.tsx" in hit_files,
               "a forbidden pipeline-internal noun in JSX text is caught")
            ok("Path.tsx" in hit_files,
               "a repository path in JSX text is caught")
            ok("CsvName.tsx" not in hit_files,
               "a bare `.csv` filename with no directory — a download's own name — is exempt")
            ok("Toast.tsx" in hit_files,
               "`toast({ title: … })` carrying a forbidden noun is caught")
            ok("NoticeCode.tsx" not in hit_files,
               "`Notice`'s own `code` prop is the one exempted channel (CLAUDE.md's Register "
               "paragraph) and is never extracted")
            ok("OperatorWords.tsx" not in hit_files,
               "run/box/export/listing — the operator's own words — trip nothing")
            ok("Gallery.tsx" not in hit_files,
               "the kit sheet is exempt BY NAME — it documents the kit to a builder, not the "
               "product to an operator")
            ok("Fulfillment.tsx" in hit_files,
               "the Fulfiller's own screen is NOT exempt — a real person reads it while working")
            ok("PullConfirm.tsx" in hit_files,
               "the pull-confirm screen is NOT exempt, for the same reason")
            ok("CliInvocation.tsx" in hit_files,
               "a backticked `pkmnscan …` invocation is caught — `Pricing.tsx:4468`'s own "
               "defect before D210, and the row had no key for it")

    # THE PIN. `NO_MECHANISM_EXEMPT_FILES` is a set of exactly one entry, named in the
    # coordinator's 2026-09-13 ruling and nowhere else — a session widening it to a second
    # file must edit this literal, which fails `--self-test` (and therefore
    # `make audit-self-test`, which is in `make check`) until the assertion is updated to
    # match, on purpose and in a diff a reviewer sees. This is the mechanism, not a comment
    # promising one: mutate the set to add a second name and this line goes red.
    ok(frozenset({"Gallery.tsx"}) == NO_MECHANISM_EXEMPT_FILES,
       "the no-mechanism-on-screen exemption is pinned to exactly one file, `Gallery.tsx`",
       f"got: {sorted(NO_MECHANISM_EXEMPT_FILES)}")

    print("\n" + "=" * 72)
    if failures:
        print(f"{len(failures)} self-test {'failure' if len(failures) == 1 else 'failures'}")
        return 1
    print("self-test clean")
    return 0


# ------------------------------------------------------------------------------ main


def audit(staged_only: bool) -> Report:
    report = Report()
    # Mode first, and before anything reads or enumerates. Everything below — the
    # allowlist, the markdown list, every existence check inside every check — has to be
    # answered about ONE tree, and in staged mode that tree is the index. Loading any of
    # it beforehand silently mixes the worktree back in.
    if staged_only:
        enter_staged_mode()
    allowed = load_allowlist()
    all_docs = markdown_files()
    docs = all_docs
    if staged_only:
        staged = set(staged_changes())
        docs = [doc for doc in all_docs if rel(doc) in staged]

    check_paths(report, docs, allowed)
    check_allowlist(report, allowed)
    check_make_targets(report, docs)
    check_pkmnscan_commands(report, docs, all_docs)
    check_harness_tests(report, docs, allowed)
    check_pass_criteria(report)
    check_criteria_evidence(report)
    check_evidence_freshness(report, staged_only)
    check_decision_ids(report, docs)
    check_decision_structure(report)
    check_decision_index(report)
    check_id_claims(report)
    check_claim_vocabulary(report)
    check_entry_budget(report)
    check_debts_headings(report)
    check_env_vars(report, docs, allowed)
    check_env_names(report)
    check_hatch_state(report)
    check_claim_decode(report)
    check_claim_clients(report)
    check_detector_standing(report)
    check_sole_reader(report)
    check_server_concurrency(report)
    check_estimate_wire(report)
    check_shipping_columns(report)
    check_router_certainty(report)
    check_work_item_standing(report)
    check_not_built_endpoints(report)
    check_transport_standing(report)
    check_map(report, allowed)
    check_hook_roster(report)
    check_codex_hooks(report)
    check_map_sections(report)
    check_gates_structure(report)
    check_build_order_mirror(report)
    check_game_vocabulary(report)
    check_game_coverage(report)
    check_matrix_superset(report)
    check_join_key_shape(report)
    check_reason_codes(report)
    check_reason_emissions(report)
    check_supervisor_self_watch(report)
    check_motion_params(report)
    check_logo_parity(report)
    check_mac_icon_grid(report)
    check_lockup_params(report)
    check_rail_mark(report)
    check_lockup_bracket(report)
    check_withhold_reasons(report)
    check_order_reasons(report)
    check_terminal_statuses(report)
    check_pricing_presets(report)
    check_export_request(report)
    check_transport_promise(report)
    check_hint_reasons(report)
    check_tested_by_reach(report)
    check_status_sources(report)
    check_design_tokens(report)
    check_raw_color(report)
    check_breakpoints(report)
    check_breakpoint_columns(report)
    check_storage_keys(report)
    check_views_opsec(report)
    check_doc_hygiene(report, docs)
    check_route_rosters(report)
    check_recorded_deletions(report)
    check_spec_seal(report)
    check_design_check_verdict(report)
    check_route_census(report)
    check_check_registry(report)
    check_commit_path(report)
    check_check_census(report)
    check_no_mechanism_on_screen(report)
    check_suite_lock(report)
    check_browser_scope(report)
    check_positional_references(report, docs)
    check_audit_invocation(report)
    check_identifier_spelling(report)
    check_shell_substitution(report)
    check_unscoped_walk(report)
    check_import_layering(report)
    check_rule_enforcement(report)
    # Last, and it is the row that says the rows above are all of them. It reconciles this
    # file's check definitions against the calls in this function.
    #
    # IT DOES NOT ANSWER FOR ITSELF, and an earlier draft of this comment claimed it did.
    # Measured: delete this one line and every other row still prints green, the run exits
    # 0, and the `check dispatch` row is simply absent — the exact silent shrinkage the row
    # exists to catch, one level up. A detector cannot detect its own absence; that is the
    # shape of the thing, not a bug to patch, and no reconciliation added here can close it
    # because
    # the reconciler would need the same single call nothing vouches for. What catches it
    # is `--self-test`, whose last case calls check_dispatch() directly and asserts this
    # function names every check — and `--self-test` runs by hand, on no gate. So this line
    # is the root of the recursion: unwiring anything else fails the commit, and unwiring
    # THIS fails nothing automatic. docs/DEBTS.md records it under the entry that shipped
    # the row; do not delete it on the strength of the audit staying green.
    check_dispatch(report)
    if staged_only:
        check_coupling(report)
    # AFTER EVERYTHING, because its subject is the other rows' subject counts — including
    # `coupling`, which only exists in staged mode. It is the one row that must see the
    # whole report, so it is the one row that cannot be anywhere but here.
    check_subject_counts(report, staged_only)
    return report


class _Parser(argparse.ArgumentParser):
    """Usage errors exit EXIT_USAGE, never argparse's default 2.

    2 is this script's advisory code and the pre-commit hook prints-and-allows on it, so
    argparse's default would let a stale flag in a caller disable the commit gate while
    printing something that reads like the routine coupling question.
    """

    def error(self, message: str):  # pragma: no cover - argparse contract
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog}: error: {message}\n")
        sys.exit(EXIT_USAGE)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="docs-audit",
        description="Audit the markdown for stale references. Never writes.",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="audit the staged set and run the coupling question (what the hook runs)",
    )
    parser.add_argument(
        "--all", action="store_true", help="audit every markdown file (the default)"
    )
    parser.add_argument("--self-test", action="store_true", help="verify the extractors and exit")
    parser.add_argument(
        "--json",
        action="store_true",
        help="print one JSON object — rows plus the exit code — instead of the human render",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.self_test:
        return self_test()

    report = audit(staged_only=args.staged)
    mechanical, advisory = report.counts()
    code = 1 if mechanical else 2 if advisory else 0
    print(report.as_json(code) if args.json else report.render())
    return code


if __name__ == "__main__":
    sys.exit(main())


# A NOTE ON DOCUMENTING THE SIGIL, because writing it down broke it once. `env vars` reads the
# scripts for a `PKMNSCAN_` token, so spelling a concrete example name in this file put that
# name in its own haystack — and every `+`-marked reference to it in a design document then
# failed as "the code reads it now". The examples above therefore name the PREFIX and stop.
# A mechanism whose documentation is inside its own subject has to be written for that.
