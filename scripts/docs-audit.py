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
import subprocess
from functools import lru_cache
import sys
import tempfile
from fnmatch import fnmatch
from pathlib import Path
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, Set, Tuple

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


class Report:
    """Collects every finding, never stops at the first.

    Same reasoning as harness/run.py running every test after one fails: a status
    signal that stops early hides the state of everything behind it.
    """

    def __init__(self) -> None:
        self.checks: List[Tuple[str, str, List[Finding], str]] = []

    def add(
        self,
        check: str,
        severity: str,
        findings: List[Finding],
        summary: str = "",
    ) -> None:
        self.checks.append((check, severity, findings, summary))

    def counts(self) -> Tuple[int, int]:
        mech = sum(len(f) for _, sev, f, _ in self.checks if sev == MECHANICAL and f)
        adv = sum(len(f) for _, sev, f, _ in self.checks if sev == ADVISORY and f)
        return mech, adv

    def as_json(self, exit_code: int) -> str:
        # The machine surface: nothing downstream parses the human render (spec §7 — three
        # parser bugs in one planning session came from regexing it).
        rows = [
            {"label": check, "severity": severity, "summary": summary,
             "findings": [finding._asdict() for finding in findings]}
            for check, severity, findings, summary in self.checks
        ]
        return json.dumps({"rows": rows, "exit": exit_code}, indent=2)

    def render(self) -> str:
        lines = ["PKMNSCAN docs audit — docs/DECISIONS.md D16", "=" * 72, ""]
        for check, severity, findings, summary in self.checks:
            if not findings:
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


# Suffixes that mean "this is a file". Anything else after the final dot is read as an
# attribute — `pipeline/variant.resolve` names a function, not a file, and the docs use
# that form to point at code precisely.
KNOWN_SUFFIXES = {
    ".py", ".md", ".sh", ".json", ".csv", ".txt", ".js", ".jsx", ".ts", ".tsx",
    ".yaml", ".yml", ".toml", ".html", ".css", ".png", ".jpg", ".jpeg", ".svg",
    ".cfg", ".ini", ".lock", ".example", ".env", ".sample",
}


def path_candidates(line: str) -> List[str]:
    """Extract path-shaped tokens. Deliberately conservative — see the note above."""
    out: List[str] = []
    # Routes first: a method in front of a slash-path means the sentence is about an HTTP
    # route, and this script has nothing to say about whether one exists. The path check
    # cannot tell a route from a module by shape alone — see `_ROUTE`.
    line = _ROUTE.sub(" ", line)
    if _PLACEHOLDER.search(line):
        line = _PLACEHOLDER.sub(" ", line)
    for match in _CANDIDATE_RE.finditer(line):
        text = match.group(0).rstrip(_TRAILING)
        if not text or "/" not in text:
            continue
        out.append(text)
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
        target = (containing.parent / text).resolve()
        try:
            target.relative_to(ROOT)
        except ValueError:
            return None
        return target
    text = text[2:] if text.startswith("./") else text
    first = text.split("/", 1)[0]
    if first not in tops:
        return None
    if first == ".git":
        return _git_path(text)
    return ROOT / text


def ignored_paths(candidates: Sequence[str]) -> Set[str]:
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
    """
    if not candidates:
        return set()

    def ask(batch: Sequence[str]) -> Tuple[int, Set[str]]:
        try:
            done = subprocess.run(
                ["git", "check-ignore", "--stdin"],
                cwd=str(ROOT),
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
    return found


def check_paths(report: Report, docs: List[Path], allowed: Dict[str, str]) -> None:
    tops = top_level_names()
    findings: List[Finding] = []
    checked = 0

    seen: List[Tuple[Path, int, str, Path]] = []
    for doc in docs:
        for number, line in enumerate(read(doc).splitlines(), start=1):
            for candidate in path_candidates(line):
                target = resolve_candidate(candidate, doc, tops)
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
                seen.append((doc, number, candidate, target))

    missing = [item for item in seen if not exists(item[3])]
    probe: List[str] = []
    for item in missing:
        probe.append(rel(item[3]))
        probe.append(rel(item[3]) + "/")
    ignored = ignored_paths(probe)

    for doc, number, candidate, target in missing:
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
    report.add("paths", MECHANICAL, findings, f"{checked} references resolve")


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
    report.add("allowlist", MECHANICAL, findings, f"{len(allowed)} entries, none stale")


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
            for name in _MAKE_REF_RE.findall(line):
                referenced += 1
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
    report.add("make targets", MECHANICAL, findings, f"{referenced} references, {len(targets)} targets")


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
    """`### T1 — …` heading text -> that section's body."""
    gates = ROOT / "docs" / "GATES.md"
    if not exists(gates):
        return {}
    sections: Dict[str, str] = {}
    current: Optional[str] = None
    body: List[str] = []
    for line in read(gates).splitlines():
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


def check_harness_tests(report: Report, docs: List[Path], allowed: Dict[str, str]) -> None:
    tests = registered_tests()
    names = {name for name, _ in tests}
    sections = gates_sections()

    findings: List[Finding] = []
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
    report.add("harness tests", MECHANICAL, findings, f"{len(names)} registered and documented")


def normalise(text: str) -> str:
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
        claim = docstring_pass_claim(source)
        if claim is not None and normalise(criteria) not in normalise(claim):
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
        for number in _NUMBER_RE.findall(criteria):
            if number not in section:
                mechanical.append(
                    Finding(
                        rel(path),
                        f"PASS_CRITERIA says {number!r} but `### {name}` in docs/GATES.md "
                        f"never mentions it.\n  PASS_CRITERIA: {criteria}",
                    )
                )
        if normalise(criteria) not in normalise(section):
            wording.append(
                Finding(
                    rel(path),
                    f"PASS_CRITERIA does not appear in `### {name}` in docs/GATES.md.\n"
                    f"  test:  {criteria}\n"
                    f"  Update the `- **Pass**:` line in `### {name}` to this text. The test "
                    f"is the source; the gate publishes it. Do not reword the test to match "
                    f"the doc.",
                )
            )
    report.add("pass criteria", MECHANICAL, mechanical, "every threshold matches GATES.md")
    report.add("criteria wording", MECHANICAL, wording, "every criterion is published verbatim")


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
        text = criteria.get(payload.get("test", "T1"))
        if text is None:
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
    report.add(
        "criteria evidence", MECHANICAL, findings, f"{len(scores)} scored run, gate field published"
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
        "evidence freshness", ADVISORY, findings, "staged score sources bring their result"
    )


# ---------------------------------------------------------------------- decision ids

_DECISION_RE = re.compile(r"\bD([1-9][0-9]?)\b")
_CODES_DECISION_RE = re.compile(r"\bC([1-9][0-9]?)\b")


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
    pattern = re.compile(r"^##\s+(" + letter + r"[1-9][0-9]?)\b")
    out: List[Tuple[str, int]] = []
    for number, line in enumerate(read(path).splitlines(), start=1):
        match = pattern.match(line)
        if match:
            out.append((match.group(1), number))
    return out


def check_decision_ids(report: Report, docs: List[Path]) -> None:
    singles = decision_headings(ROOT / "docs" / "DECISIONS.md", "D")
    codes = decision_headings(ROOT / "docs" / "CODES-DECISIONS.md", "C")

    def scan(paths: Iterable[Path], severity_findings: List[Finding]) -> None:
        for path in paths:
            for number, line in enumerate(read(path).splitlines(), start=1):
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
    for path, letter in (
        (ROOT / "docs" / "DECISIONS.md", "D"),
        (ROOT / "docs" / "CODES-DECISIONS.md", "C"),
    ):
        seen: Dict[str, List[int]] = {}
        for found, number in decision_heading_lines(path, letter):
            seen.setdefault(found, []).append(number)
        for found, numbers in sorted(seen.items()):
            if len(numbers) > 1:
                where = ", ".join(str(n) for n in numbers)
                in_docs.append(
                    Finding(
                        f"{rel(path)}:{numbers[0]}",
                        f"`## {found}` appears {len(numbers)} times — lines {where}. An id "
                        f"names one entry: `governed_by`, the decision-context hook and every "
                        f"`({found})` in a comment resolve to whichever heading is found "
                        f"first. Renumber all but one, and every reference to them.",
                    )
                )

    scan(docs, in_docs)
    in_code: List[Finding] = []
    scan(python_files(), in_code)
    # THE APP WAS NOT SCANNED AT ALL UNTIL 2026-08-30 (D72). `python_files()` is every `.py`
    # in the tree, and the row below said "citations in .py all resolve" — accurately, and
    # over half the citations. `app/` holds hundreds more in `.ts`, `.tsx` and `.css`
    # comments, and a dangling id in one of them resolved to nothing and was reported by
    # nothing. Same severity as the Python row and for the same reason: `D2` could plausibly
    # be a variable, and a false positive that blocks a commit is worse than a printed line.
    scan(_walk(ROOT, (".ts", ".tsx", ".css")), in_code)

    report.add("decision ids", MECHANICAL, in_docs, f"{len(singles)} D + {len(codes)} C headings")
    # Code is advisory: `C1` or `D2` could plausibly be a variable one day, and a false
    # positive that blocks a commit is worse than one that prints a line.
    report.add("decision ids in code", ADVISORY, in_code, "citations in .py, .ts, .tsx and .css all resolve")


# ------------------------------------------------------- a renumbered entry takes its citations

# WHAT THIS CATCHES IS THE ONE THING AN EXISTENCE CHECK STRUCTURALLY CANNOT (D72). Every
# other decision row above asks whether a cited id EXISTS. A renumber breaks none of them:
# the branch's entry moves from D67 to D69, the citations stay on D67, and D67 still names
# a real heading — a DIFFERENT one. `check_decision_ids` says the same about a duplicate id
# in its own comment: "the citation is then not wrong in a way anything can see — it points
# at a real heading, just not the intended one." This is that sentence's other half.
#
# It happened. `docs/map.py` cited D67 in 24 places meaning D69 — "the order transport
# (D67)", "(D67) gave each its own route" — while nine OTHER D67 citations in the same file
# were the real entry, so no sweep could be run blind. Thirteen renumber events are in this
# repo's history and the collisions are structural: several branches take "the next free
# number" against one base and all of them merge.
#
# BRANCH-SCOPED, WHICH IS WHAT MAKES IT QUIET. The renumber that matters is the one THIS
# branch did, and the files that matter are the ones THIS branch touched — a citation of
# D67 that main already had is not this branch's to move. On main, base == HEAD and this
# row is empty for nothing.
#
# NOT `--staged`, DELIBERATELY. The renumber is commonly done while resolving a merge, and
# git runs no pre-commit hook for a merge commit — a staged-only check would have missed
# every event in the history above. Reading the branch's own commits catches it however it
# was committed, and the Stop hook runs this at turn end.
#
# ADVISORY. A branch may legitimately cite the new occupant of the freed number, and only a
# human can tell that from the mistake. What the row is for is naming the sites: the triage
# list is the whole cost of getting this right, and it is what nobody had.


def branch_base() -> str:
    """The commit this branch left main at, or "" when that cannot be answered.

    `origin/main` rather than `main`: a worktree checkout commonly has no local `main` (it
    is checked out elsewhere, and CLAUDE.md's merge discipline moves it by pull), while the
    remote-tracking ref is present in every clone.
    """
    for ref in ("origin/main", "main"):
        base = git("merge-base", "HEAD", ref).strip()
        if base:
            return base
    return ""


def headings_at(rev: str, path: str = "docs/DECISIONS.md") -> Dict[str, str]:
    """title -> id, as of `rev`. Empty when the blob is unreadable at that commit."""
    pattern = re.compile(r"^##\s+(D[1-9][0-9]?)\s+—\s+(.+?)\s*$")
    out: Dict[str, str] = {}
    for line in git("show", f"{rev}:{path}").splitlines():
        match = pattern.match(line)
        if match:
            out[match.group(2)] = match.group(1)
    return out


def headings_now() -> Dict[str, str]:
    pattern = re.compile(r"^##\s+(D[1-9][0-9]?)\s+—\s+(.+?)\s*$")
    out: Dict[str, str] = {}
    for line in read(ROOT / "docs" / "DECISIONS.md").splitlines():
        match = pattern.match(line)
        if match:
            out[match.group(2)] = match.group(1)
    return out


def moves_across(states: Sequence[Dict[str, str]]) -> List[Tuple[str, str, str]]:
    """(old, new, title) for every title whose id changes across a sequence of states.

    Pure, and split out for exactly that: the git walk that produces `states` cannot be
    exercised without a repository, and this is where the logic that could be wrong lives.
    A title that moves twice (D50 -> D51 -> D53 is in this repo's history) reports its
    FIRST id against its last, because the citations that need chasing were written when it
    was still D50.
    """
    moves: Dict[str, Tuple[str, str]] = {}
    for before, after in zip(states, states[1:]):
        for title, new in after.items():
            old = before.get(title)
            if old and old != new:
                first = moves[title][0] if title in moves else old
                moves[title] = (first, new)
    return sorted(
        ((old, new, title) for title, (old, new) in moves.items() if old != new),
        key=lambda move: (int(move[1][1:]), move[2]),
    )


def renumbered_on_branch(base: str) -> List[Tuple[str, str, str]]:
    """Every entry this branch moved to a different number, from the branch's own history.

    Walks only the commits that TOUCHED the file — usually one or two — and compares each
    against the state before it. The title is the identity: a renumber keeps it and changes
    the id, which is exactly the pair no id-based check can see.
    """
    revisions = [line for line in git(
        "log", "--format=%H", f"{base}..HEAD", "--", "docs/DECISIONS.md"
    ).split() if line]
    states = [headings_at(base)]
    for revision in reversed(revisions):
        states.append(headings_at(revision))
    states.append(headings_now())
    return moves_across(states)


def branch_files(base: str) -> List[str]:
    """Paths this branch changed, committed or not. The renumber's own file is not one."""
    names = set(git("diff", "--name-only", base, "HEAD").split("\n"))
    names.update(git("diff", "--name-only", "HEAD").split("\n"))
    names.update(git("diff", "--cached", "--name-only").split("\n"))
    return sorted(
        name for name in names
        if name and name != "docs/DECISIONS.md" and exists(ROOT / name)
    )


def check_renumbered_decisions(report: Report) -> None:
    findings: List[Finding] = []
    base = branch_base()
    if not base or base == git("rev-parse", "HEAD").strip():
        report.add("renumbered ids", ADVISORY, findings, "not a branch off main — nothing to compare")
        return

    moves = renumbered_on_branch(base)
    occupant = {number: title for title, number in headings_now().items()}
    touched = branch_files(base)
    for old, new, title in moves:
        was = re.compile(r"\b" + old + r"\b")
        now = re.compile(r"\b" + new + r"\b")
        sites: List[str] = []
        for name in touched:
            text = read(ROOT / name)
            lines = [
                number
                for number, line in enumerate(text.splitlines(), start=1)
                if was.search(line)
            ]
            if not lines:
                continue
            shown = ", ".join(str(number) for number in lines[:6])
            if len(lines) > 6:
                shown += f", +{len(lines) - 6} more"
            both = "" if now.search(text) else f"   <- and never names {new}"
            sites.append(f"{name}:{shown}{both}")
        if not sites:
            continue
        listed = "\n  ".join(sites)
        findings.append(
            Finding(
                f"docs/DECISIONS.md -> {new}",
                f"`{title}` moved {old} -> {new} on this branch, and {len(sites)} file(s) "
                f"this branch touched still cite {old}.\n"
                f"  {old} now names: {occupant.get(old) or 'nothing — the number is free'}\n"
                f"  {listed}\n"
                f"  Each site is either a citation that must follow the entry to {new}, or a "
                f"real reference to {old}'s current occupant. Nothing mechanical can tell "
                f"them apart — an id-based check sees a citation that resolves. A file that "
                f"names BOTH ids is common and is not evidence either way: docs/map.py "
                f"carried 24 wrong and 9 right in one file.",
            )
        )
    detail = (
        ", ".join(f"{old}->{new}" for old, new, _ in moves)
        if moves else "no entry changed number on this branch"
    )
    report.add("renumbered ids", ADVISORY, findings, detail)

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
# ENTRY_BUDGET is twice the median entry (6,374 bytes on the day it was set) rather than a
# picked round number. D60 itself is 4,967. An entry at twice the median is one that should
# have cited a neighbour instead of re-arguing it, which is that entry's own rule.
ENTRY_BUDGET = 12000


def _prose_guard():
    """scripts/prose-guard.py, or None.

    Imported rather than reimplemented: it already replicates decision-context.py's three
    selectors, and a second copy here is the drift this file exists to catch. The filename
    has a hyphen, hence importlib. Returns None on any failure — a missing guard must cost
    two rows, never the whole audit.
    """
    path = ROOT / "scripts" / "prose-guard.py"
    if not path.exists():
        return None
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("prose_guard", path)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module
    except Exception:  # noqa: BLE001 - a broken guard must not take the audit down
        return None


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
    target = ROOT / "docs" / "DECISIONS.md"
    findings = [Finding(f.where, f.message) for f in guard.check_structure(target)]
    entries = guard.entries(read(target))
    report.add("decision structure", MECHANICAL, findings,
               f"{len(entries)} entries, every heading and bold reaches the hook")


def check_decision_index(report: Report) -> None:
    """CLAUDE.md's index against docs/DECISIONS.md's headings.

    D60 dropped the `@` prefix, so that file is no longer loaded in full and the index is
    the only thing a session sees without opening it. An index that has drifted is worse
    than none, because it is believed — the argument D17 makes for auditing docs/map.py
    exactly as hard as it is trusted.

    MECHANICAL. Both sides are ids and titles: there is nothing here a later session could
    reasonably disagree with, which is D16's test for what may block.

    NOT a generator, and this deliberately does not open D18's seam list. It computes what
    the index should say and compares; it never writes. That is D18's own write-time versus
    check-time split, with only the check half built.
    """
    claude = ROOT / "CLAUDE.md"
    decisions = ROOT / "docs" / "DECISIONS.md"
    if not exists(claude) or not exists(decisions):
        report.add("decision index", MECHANICAL,
                   [Finding("CLAUDE.md", "cannot read the index or the entries.")])
        return

    want = [
        (m.group(1), m.group(2).strip())
        for m in (re.match(r"^##\s+(D\d{1,2})\s*[—-]\s*(.+)$", line)
                  for line in read(decisions).split("\n"))
        if m
    ]
    # The index is the first fenced block whose lines all start `D<n> `. Located by shape
    # rather than by a heading, so re-titling the Map section cannot silently unhook it.
    got: List[Tuple[str, str]] = []
    fenced, block = False, []
    for line in read(claude).split("\n"):
        if line.lstrip().startswith("```"):
            if fenced and block and all(re.match(r"^D\d{1,2}\s", b) for b in block if b.strip()):
                got = [(b.split(None, 1)[0], b.split(None, 1)[1].strip())
                       for b in block if b.strip()]
                break
            fenced, block = not fenced, []
            continue
        if fenced:
            block.append(line)

    findings: List[Finding] = []
    if not got:
        findings.append(Finding("CLAUDE.md", "no decision index found. D60 requires one."))
    else:
        want_ids = [i for i, _ in want]
        got_ids = [i for i, _ in got]
        for ident in [i for i in want_ids if i not in got_ids]:
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
    report.add("decision index", MECHANICAL, findings,
               f"{len(got)} indexed, matching {len(want)} headings")


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
    target = ROOT / "docs" / "DECISIONS.md"
    findings = [Finding(f.where, f.message) for f in guard.check_budget(target, ENTRY_BUDGET)]
    total = sum(len(e.body) for e in guard.entries(read(target)))
    report.add("entry budget", ADVISORY, findings,
               f"{total:,} bytes of entries, {len(findings)} over {ENTRY_BUDGET:,}")


def check_env_vars(report: Report, docs: List[Path], allowed: Dict[str, str]) -> None:
    haystack = code_haystack()
    findings: List[Finding] = []
    seen: Set[str] = set()
    for doc in docs:
        for number, line in enumerate(read(doc).splitlines(), start=1):
            for name in _ENV_RE.findall(line):
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
    report.add("env vars", MECHANICAL, findings, f"{len(seen)} documented, all real")


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
# before the key below existed keeps exactly the behaviour it had: `.py`, one level deep.
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


def cited_decisions(path: Path) -> Set[str]:
    return {"D" + digits for digits in _DECISION_RE.findall(read(path))}


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

    singles = decision_headings(ROOT / "docs" / "DECISIONS.md", "D")
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
    gates_text = read(ROOT / "docs" / "GATES.md") if exists(ROOT / "docs" / "GATES.md") else ""
    for gate in gates:
        name = gate.get("gate", "")
        heading = re.search(r"^#{2,3}\s+Gate\s+" + re.escape(name) + r"\b(.*)$", gates_text, re.MULTILINE)
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

    report.add("repo map", MECHANICAL, findings, f"{claimed} entries match the tree")


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
    {"product_line_rarities", "tcgplayer_category_id", "set_aliases", "export_scope"}
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
               f"{covered} of {len(sections)} sections have a reader, consumer list agrees")


# ------------------------------------------------- the build order against its own source

# The numbered lists under `## What shipped` and `## What is open` in docs/GATES.md, which
# docs/map.py's SHIPPED and OPEN say in their own header that they mirror. Each is bounded
# at the next `## ` so a numbered list anywhere else in that file cannot join in.
_GATES_STEP = re.compile(r"^(\d+)\.\s", re.M)


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
    gates = ROOT / "docs" / "GATES.md"
    if not exists(MAP) or not exists(gates):
        report.add("build order mirror", MECHANICAL,
                   [Finding("docs/", "docs/map.py or docs/GATES.md is missing.")])
        return

    data = literals_from_module(MAP)
    text = read(gates)
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
        listed = {int(n) for n in _GATES_STEP.findall(rest[: stop.start() if stop else len(rest)])}
        total += len(mine)
        for number in sorted(listed - mine):
            findings.append(Finding(
                "docs/map.py",
                f"docs/GATES.md lists step {number} under `{heading}`; the map's `{name}` "
                f"has no such id.",
            ))
        for number in sorted(mine - listed):
            findings.append(Finding(
                "docs/GATES.md",
                f"the map's `{name}` has step {number}; `## {heading}` does not list it.",
            ))

    report.add("build order mirror", MECHANICAL, findings,
               f"{total} steps, the same ids in both files, in the same two lists")



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
    "stillFrames": "STILL_FRAMES",
    "stillWindow": "STILL_WINDOW",
    "refractoryMs": "REFRACTORY_MS",
    "presenceK": "PRESENCE_K",
    "presenceMin": "PRESENCE_MIN",
    "maxMoveMs": "MAX_MOVE_MS",
}

# Parameters the offline scorer deliberately does not carry, each with the reason. The list
# is checked in BOTH directions below: an entry naming a parameter that no longer exists is
# as much a finding as a parameter in neither map, because a stale excuse is how a real gap
# hides.
MOTION_UNMIRRORED = {
    "tNovel": "the scorer replays the stillness and presence halves; it does not implement "
              "the novelty gate, so there is no constant to disagree with",
}

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
    )


def check_pricing_presets(report: Report) -> None:
    """The three pricing presets, reconciled between the tuple that prices them and the
    table that writes them.

    `cli/cmd_join.py:PRESETS` is `(key, rule, basis)` and prices every SKU under every preset
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
    python_path = ROOT / "cli" / "cmd_join.py"
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

    report.add(
        "export request",
        MECHANICAL,
        findings,
        f"{len(EXPORT_STANDING)} standing filters, each at its instructed value",
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

    **The one thing it cannot see** is a reason constant that no doc and no screen mentions
    at all. `self_named_strings` deliberately answers "is this string defined here" and not
    "which strings here are reasons" — the latter needs a heuristic, and a heuristic on a
    blocking row is a guess that stops commits. Recorded in docs/DEBTS.md rather than
    papered over.
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
        f"{len(documented)} enumerated, {len(labels)} labelled, all defined",
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

    report.add("status sources", MECHANICAL, findings, f"{checked} declared, all resolve")


# ------------------------------------------------ the palette the app actually renders from

DESIGN = ROOT / "docs" / "DESIGN.md"
TOKENS_CSS = ROOT / "app" / "src" / "tokens.css"

COLOUR = "colour"
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
DOC_TYPE_TOKENS = {"Display": "display", "Body": "body", "Utility": "util"}
SPACING_TOKEN = "s"  # positional: the nth number on the Spacing row is `--s<n>`
RADIUS_TOKEN = "r"

# `Color      #FCFCFD  bg   the page.` and its continuation rows, which carry no label. The
# optional leading word is what lets the first row of the group parse like the rest.
_TOKEN_ROW_RE = re.compile(r"^\s*(?:[A-Z][a-z]*\s+)?(#[0-9A-Fa-f]{3,6})\s+([a-z][a-z0-9-]*)\b")
# Built from the table above rather than beside it: a second enumeration of the same three
# labels is the drift this whole check exists to catch, and there is no excuse for one here.
_TYPE_ROW_RE = re.compile(r"^(" + "|".join(DOC_TYPE_TOKENS) + r")\s+(.+?)\s*\(")
_SPACING_ROW_RE = re.compile(r"^Spacing\s+([\d ]+\d)")
_RADIUS_ROW_RE = re.compile(r"^Radius\s+(\d+px)\b")

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

      colour     `#FFF` and `#ffffff` are one colour. A check that called them a
                 disagreement would be reporting a spelling, and would be worked around by
                 respelling the doc, which is D16's forbidden direction.
      typeface   the stylesheet names the locked face plus a generic fallback. The interview
                 chose a face; `sans-serif` behind it is a rendering nicety nobody locked.
                 Family names are ASCII case-insensitive to CSS, so case is folded too.
      length     whitespace only. `4px` and `4 px` are not the same value to CSS and are not
                 collapsed here.
    """
    if kind == COLOUR:
        text = " ".join(text.split()).lower()
        return "#" + "".join(ch * 2 for ch in text[1:]) if _SHORTHAND_RE.match(text) else text
    if kind == TYPEFACE:
        return " ".join(text.split(",")[0].strip().strip("'\"").split()).lower()
    return " ".join(text.split()).lower()


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
    collecting = False
    in_section = False
    block: List[str] = []
    for line in text.splitlines():
        if not collecting and line.startswith("## "):
            in_section = bool(re.match(r"^##\s+Tokens\b", line))
            continue
        if in_section and line.lstrip().startswith("```"):
            if collecting:
                return "\n".join(block)
            collecting = True
            continue
        if collecting:
            block.append(line)
    return None


def design_tokens(block: str) -> Dict[str, Token]:
    """Every token the block locks: colours by name, the three faces, the scale, the radius.

    A row this cannot read disappears from the doc side rather than being reported here, and
    that is safe in one direction only — the stylesheet still declares the property, so the
    comparison reports it as a token the block does not lock. Reformatting the block into a
    markdown table would therefore fail loudly, one finding per token, rather than passing
    on an empty comparison. The vacuous case, where nothing at all parses, is caught by the
    caller.
    """
    tokens: Dict[str, Token] = {}
    for line in block.splitlines():
        colour = _TOKEN_ROW_RE.match(line)
        if colour:
            tokens[colour.group(2)] = Token(COLOUR, colour.group(1), token_value(COLOUR, colour.group(1)))
            continue
        face = _TYPE_ROW_RE.match(line)
        if face:
            name = DOC_TYPE_TOKENS[face.group(1)]
            tokens[name] = Token(TYPEFACE, face.group(2), token_value(TYPEFACE, face.group(2)))
            continue
        spacing = _SPACING_ROW_RE.match(line)
        if spacing:
            for index, step in enumerate(spacing.group(1).split(), start=1):
                # The block writes the scale bare where the stylesheet writes px. Reading the
                # unit in is an assumption, and it is the one the rest of the file supports:
                # `Radius 4px` on the next row carries its unit, and the Fulfillment table
                # states every other length in px. What would settle it is the Spacing row
                # spelling the unit out. Until then a scale in any other unit reads here as a
                # disagreement, which is the safe direction to be wrong in.
                tokens[f"{SPACING_TOKEN}{index}"] = Token(LENGTH, step, token_value(LENGTH, step + "px"))
            continue
        radius = _RADIUS_ROW_RE.match(line)
        if radius:
            tokens[RADIUS_TOKEN] = Token(LENGTH, radius.group(1), token_value(LENGTH, radius.group(1)))
    return tokens


def css_root_tokens(text: str) -> Dict[str, str]:
    """Custom properties declared on `:root`, comments stripped first.

    Stripping first is the point: a token commented out during a refactor still reads as a
    declaration to a regex, and this check would then agree with the doc about a value the
    browser never sees. Braces are counted rather than stopping at the first `}` so that a
    `:root` nested inside an at-rule is read whole — docs/DESIGN.md bans a dark theme, and
    an audit that silently truncated at one is an audit that would not notice it arriving.
    """
    body = _CSS_COMMENT_RE.sub(" ", text)
    out: Dict[str, str] = {}
    for match in re.finditer(r":root\b[^{]*\{", body):
        depth = 1
        index = match.end()
        while index < len(body) and depth:
            if body[index] == "{":
                depth += 1
            elif body[index] == "}":
                depth -= 1
            index += 1
        for name, value in _CSS_PROPERTY_RE.findall(body[match.end():index]):
            out[name] = value.strip()
    return out


def token_findings(doc: Dict[str, Token], css: Dict[str, str]) -> List[Finding]:
    """Both directions, and every finding names both files and both values.

    Both directions because either half of a drift is the same defect seen from one side. A
    token in the doc and not the stylesheet is a decision the product never implemented; a
    token in the stylesheet and not the doc is a value the owner never chose, which is the
    more dangerous of the two — it renders perfectly and no interview ever saw it.
    """
    findings: List[Finding] = []
    for name in sorted(set(doc) | set(css)):
        locked = doc.get(name)
        rendered = css.get(name)
        if locked is None:
            findings.append(
                Finding(
                    f"{rel(TOKENS_CSS)} + {rel(DESIGN)}",
                    f"`--{name}: {rendered}` is declared in {rel(TOKENS_CSS)}, and the token "
                    f"block in {rel(DESIGN)} locks no `{name}`.\n"
                    f"  Lock it there, or delete it here. A token the doc never chose is a "
                    f"value with no argument behind it.",
                )
            )
            continue
        if rendered is None:
            findings.append(
                Finding(
                    f"{rel(DESIGN)} + {rel(TOKENS_CSS)}",
                    f"{rel(DESIGN)} locks `{name}` at `{locked.text}`, and "
                    f"{rel(TOKENS_CSS)} declares no `--{name}`.\n"
                    f"  Nothing renders it, so the locked value is a decision the product "
                    f"does not carry.",
                )
            )
            continue
        if token_value(locked.kind, rendered) != locked.value:
            findings.append(
                Finding(
                    f"{rel(DESIGN)} + {rel(TOKENS_CSS)}",
                    f"`{name}` disagrees.\n"
                    f"  {rel(DESIGN)}:      {locked.text}\n"
                    f"  {rel(TOKENS_CSS)}: {rendered}\n"
                    f"  The doc is the source — it records what the owner picked from "
                    f"rendered alternatives. Change the stylesheet, or take the value back "
                    f"through an interview and change both.",
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

    doc = design_tokens(block)
    css = css_root_tokens(read(TOKENS_CSS))
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
        token_findings(doc, css),
        f"{len(doc)} locked tokens, all rendered as locked",
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
        return

    findings: List[Finding] = []
    for path in sorted(APP_STYLES.glob("*.css")):
        if path == TOKENS_CSS:
            continue
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

    report.add("raw color", MECHANICAL, findings, f"{len(findings)} literals outside tokens.css"
               if findings else "every color comes from a token")


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


def _pooled_exclusion_evidence(route_path: str) -> Optional[str]:
    """Committed proof that a route's screen never draws a pooled card's photo.

    The Fulfillment shape, exactly as D24 demanded it: `app/tests/fulfillment.spec.ts`
    asserts "a pooled card is never on his screen", in a spec `make design-check` runs.
    The tie is mechanical — the spec named after the route, mentioning the pooled fact —
    and self-cleaning: delete the assertion and the route rejoins the exposure list. The
    root route has no segment to name a spec after, so it maps to `capture.spec.ts`: the
    capture screen is what `/` renders, and the manifest has always called it that.
    """
    name = route_path.strip("/") or "capture"
    if "/" in name:
        return None
    spec = APP_TESTS / f"{name}.spec.ts"
    if exists(spec) and re.search(r"pooled|located", read(spec), re.I):
        return rel(spec)
    return None


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

    entries: List[Tuple[int, str, str]] = []
    for number, line in enumerate(read(VIEWS_MANIFEST).splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
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
        entries.append((number, parts[0], parts[1]))

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
                f"Fulfillment view does, or take the render-conditions ruling to D24's "
                f"owner.",
            )
        )

    report.add(
        "views opsec",
        MECHANICAL,
        blocking,
        f"{checked} of {len(entries)} views resolve in ROUTES, none address the photo service",
    )
    report.add(
        "views exposure",
        ADVISORY,
        exposure,
        ("no pooled game in the registry — a stored photo is not a bearer instrument today"
         if not pooled
         else "no manifest view can draw a stored photo"),
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

    order = re.search(r"const\s+GROUP_ORDER\s*:[^=]*=\s*", source)
    groups: List[str] = []
    if order is not None:
        groups = re.findall(r"'([^']*)'", _balanced(source, order.end()))
    if not groups:
        findings.append(
            Finding(rel(APP_TSX), "defines no readable `GROUP_ORDER`, so a nav ORDER cannot be derived.")
        )
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
    ("([A-Za-z]+) screens — capture", ("total",)),
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
    report.add("route census", MECHANICAL, findings, summary)


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

    report.add("check numbering", MECHANICAL, positional(docs), "no check named by position")
    report.add(
        "numbering in code",
        ADVISORY,
        positional(python_files() + [ALLOWLIST]),
        "comments name checks by label",
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


def _check_recipe() -> Optional[List[str]]:
    """The targets `make check` runs, in recipe order, or None if the block cannot be read."""
    makefile = ROOT / "Makefile"
    if not exists(makefile):
        return None
    block = re.search(r"^check:\n((?:\t.*\n)+)", read(makefile), flags=re.M)
    if block is None:
        return None
    return _CHECK_RECIPE_RE.findall(block.group(1))


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
    """
    recipe = _check_recipe()
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

    report.add("check registry", MECHANICAL, findings,
               "{0} checks, in recipe order".format(len(recipe)))


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
               "{0} of {1} on the commit path, none of them writing".format(on_path, len(entries)))


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
    """
    loaded = _checks_registry()
    if loaded is None:
        report.add("check census", MECHANICAL, [Finding(
            rel(CHECKS_REGISTRY), "CHECKS could not be read; see the `check registry` row.")])
        return
    entries, _ = loaded
    expected = [str(entry.get("target", "")) for entry in entries]

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

    report.add("check census", MECHANICAL, findings,
               "{0} published lists, {1} checks each".format(checked, len(expected)))


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
    report.add("audit invocation", MECHANICAL, findings, f"{len(INVOKERS)} callers, flags all declared")


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
UNDISPATCHED: Dict[str, str] = {}


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
    `--self-test`. The reader's behaviour on a shape it cannot read has to be provable
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
        "check dispatch", MECHANICAL, findings, "every check defined here is called by audit()"
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
    for sources, coupled_docs in COUPLING:
        touched = {
            path: count
            for path, count in changes.items()
            if any(path == s or path.startswith(s) for s in sources)
        }
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
    report.add("coupling", ADVISORY, findings, "staged code and its docs move together")


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
    print("\na renumbered entry is found by its title, not its id")
    # EVERY PAIR HERE IS REAL HISTORY, not invented ids. `D67 -> D69` is the order-screen
    # entry and the incident this check exists for; `D50 -> D51 -> D53` is the "one link"
    # entry, which moved twice. Using live ids keeps this data out of the illustration
    # problem `governed_by` already carries for `D2` in docs/map.py.
    ORDER = "The order screen and the shipping lane get a route each"
    LINK = "One link, always live"
    moved = moves_across([{ORDER: "D67"}, {ORDER: "D69"}])
    ok(moved == [("D67", "D69", ORDER)], "an id that moves is reported old -> new", str(moved))

    added = moves_across([{ORDER: "D69"}, {ORDER: "D69", LINK: "D53"}])
    ok(not added, "a NEW entry beside an unchanged one is not a renumber", str(added))

    # The citations that need chasing were written while it was D50, so the FIRST id is the
    # one to hunt for. Reporting the middle id would miss every one of them.
    twice = moves_across([{LINK: "D50"}, {LINK: "D51"}, {LINK: "D53"}])
    ok(twice == [("D50", "D53", LINK)], "an entry renumbered twice reports its FIRST id", str(twice))

    gone = moves_across([{ORDER: "D69"}, {}])
    ok(not gone, "an entry that DISAPPEARS is not a renumber — nothing to chase", str(gone))

    one = moves_across([{ORDER: "D67", LINK: "D53"}, {ORDER: "D69", LINK: "D53"}])
    ok(one == [("D67", "D69", ORDER)], "only the entry that moved is reported, not its neighbours", str(one))

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
        _, _, findings, _ = report.checks[0]
        ok(len(findings) == 1, "one finding for one dangling path", str(findings))

        doc.write_text("see `harness/run.py` for details\n", encoding="utf-8")
        report = Report()
        check_paths(report, [doc], {})
        _, _, findings, _ = report.checks[0]
        ok(not findings, "no finding for a path that resolves", str(findings))

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
        _, _, findings, _ = report.checks[0]
        ok(not findings, "a real module.function resolves", str(findings))

        doc.write_text("`pipeline/variant.no_such_function` does the work.\n", encoding="utf-8")
        report = Report()
        check_paths(report, [doc], {})
        _, _, findings, _ = report.checks[0]
        ok(len(findings) == 1, "a function that is not defined is reported", str(findings))

    print("\nallowlist is self-cleaning")
    report = Report()
    check_allowlist(report, {"harness/run.py": "pretend this is planned"})
    _, _, findings, _ = report.checks[0]
    ok(len(findings) == 1, "existing path in the allowlist is reported stale", str(findings))
    report = Report()
    check_allowlist(report, {"harness/not_yet.py": "genuinely planned"})
    _, _, findings, _ = report.checks[0]
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
        rows = {check: (severity, findings) for check, severity, findings, _ in report.checks}
        ok(
            len(rows.get("check numbering", ("", []))[1]) == 1,
            "a positional reference in a doc is reported",
            str(rows.get("check numbering")),
        )
        ok(
            rows.get("numbering in code", ("", []))[0] == ADVISORY,
            "the code row is advisory, and the doc row is not",
            str([(check, severity) for check, severity, _, _ in report.checks]),
        )

        doc.write_text("the repo-map check owns the orphan rule\n", encoding="utf-8")
        report = Report()
        check_positional_references(report, [doc])
        # By label, not by index. This function emits two rows, so `report.checks[0]` was
        # a check identified by its position — the exact pattern D17 bans in the docs and
        # this row exists to enforce. It read `[1]` until the count row above it was
        # deleted, at which point it silently retargeted and still passed.
        by_label = {check: findings for check, _, findings, _ in report.checks}
        findings = by_label["check numbering"]
        ok(not findings, "naming the check by its label is fine", str(findings))

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
    by_label = {check: findings for check, _, findings, _ in report.checks}
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
        token_value(COLOUR, "#FFF") == token_value(COLOUR, "#ffffff"),
        "case and shorthand are spelling, not disagreement",
        f'{token_value(COLOUR, "#FFF")} vs {token_value(COLOUR, "#ffffff")}',
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
            "Color      #FCFCFD  bg        the page. Everything sits on this.",
            "           #1E40AF  accent    unsure, and the only-action fill",
            "",
            "Display    Cabinet Grotesk  (Fontshare)   700/800 only, and only at >= 20px",
            "",
            "Spacing    4 8 12        one scale, no other values",
            "Radius     4px           one value, everywhere",
        ]
    )
    parsed = design_tokens(sample)
    ok(
        set(parsed) == {"bg", "accent", "display", "s1", "s2", "s3", "r"},
        "every row of the block yields its token, labelled row included",
        str(sorted(parsed)),
    )
    ok(parsed["s2"].value == "8px", "the bare spacing scale is read in px", str(parsed["s2"]))
    ok(
        parsed["display"].value == "cabinet grotesk",
        "the face is read without its host parenthetical",
        str(parsed["display"]),
    )

    rendered = {
        "bg": "#fcfcfd",
        "accent": "#1E40AF",
        "display": "'Cabinet Grotesk', sans-serif",
        "s1": "4px",
        "s2": "8px",
        "s3": "12px",
        "r": "4px",
    }
    ok(not token_findings(parsed, rendered), "two files that agree produce no finding", str(token_findings(parsed, rendered)))

    drifted = dict(rendered, accent="#1e40b0")
    findings = token_findings(parsed, drifted)
    ok(
        len(findings) == 1 and "#1E40AF" in findings[0].message and "#1e40b0" in findings[0].message,
        "a changed hex is reported, naming both values",
        str(findings),
    )
    ok(
        len(findings) == 1 and "docs/DESIGN.md" in findings[0].message and "app/src/tokens.css" in findings[0].message,
        "and naming both files",
        str(findings),
    )
    ok(
        len(token_findings(parsed, {name: value for name, value in rendered.items() if name != "r"})) == 1,
        "a locked token the stylesheet never declares is reported",
        str(token_findings(parsed, {name: value for name, value in rendered.items() if name != "r"})),
    )
    ok(
        len(token_findings(parsed, dict(rendered, shadow="#000000"))) == 1,
        "and a stylesheet token the block never locked",
        str(token_findings(parsed, dict(rendered, shadow="#000000"))),
    )

    css = css_root_tokens(":root {\n  --ink: #08090a; /* was --ink: #ffffff; */\n}\n")
    ok(css == {"ink": "#08090a"}, "a declaration inside a comment is not a token", str(css))
    ok(
        css_root_tokens(".card { --ink: #ffffff; }\n") == {},
        "and a custom property on some other selector is not a locked token",
        str(css_root_tokens(".card { --ink: #ffffff; }\n")),
    )

    # The extractor against the real file, because the synthetic block above is written to
    # be parseable and docs/DESIGN.md is written to be read.
    if exists(DESIGN):
        block = design_token_block(read(DESIGN))
        # Discriminated on a string only the step-6 fence carries. The obvious marker —
        # `disabled`, one of its three state names — is also the last word of the `muted`
        # row in this fence, so it failed against the correct block. Measured, not guessed.
        ok(
            block is not None and "Spacing" in block and "44px tall" not in block,
            "the Tokens fence is the one extracted, not step 6's button states",
            (block or "")[:70],
        )
    report = Report()
    check_design_tokens(report)
    by_label = {check: findings for check, _, findings, _ in report.checks}
    ok(
        not by_label["design tokens"],
        "this repo's own tokens.css agrees with docs/DESIGN.md",
        str(by_label["design tokens"]),
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
    by_label = {check: findings for check, _, findings, _ in report.checks}
    ok(
        not by_label["raw color"],
        "this repo's own stylesheets read every color from a token",
        str(by_label["raw color"]),
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
    by_label = {check: findings for check, _, findings, _ in report.checks}
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
            rows = {check: findings for check, _, findings, _ in report.checks}
            ok(
                not rows["audit invocation"],
                "an abbreviation argparse accepts is not a finding",
                str(rows["audit invocation"]),
            )
            caller.write_text("python3 scripts/docs-audit.py --stagx\n", encoding="utf-8")
            report = Report()
            check_audit_invocation(report)
            rows = {check: findings for check, _, findings, _ in report.checks}
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
                return {check: found for check, _, found, _ in report.checks}["check dispatch"]
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

    report = Report()
    check_dispatch(report)
    by_label = {check: findings for check, _, findings, _ in report.checks}
    ok(
        not by_label["check dispatch"],
        "this file's own checks are every one of them called by audit()",
        str(by_label["check dispatch"]),
    )

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
    check_renumbered_decisions(report)
    check_entry_budget(report)
    check_env_vars(report, docs, allowed)
    check_map(report, allowed)
    check_map_sections(report)
    check_build_order_mirror(report)
    check_game_vocabulary(report)
    check_game_coverage(report)
    check_matrix_superset(report)
    check_join_key_shape(report)
    check_reason_codes(report)
    check_supervisor_self_watch(report)
    check_motion_params(report)
    check_withhold_reasons(report)
    check_order_reasons(report)
    check_pricing_presets(report)
    check_export_request(report)
    check_tested_by_reach(report)
    check_status_sources(report)
    check_design_tokens(report)
    check_raw_color(report)
    check_views_opsec(report)
    check_doc_hygiene(report, docs)
    check_route_rosters(report)
    check_route_census(report)
    check_check_registry(report)
    check_commit_path(report)
    check_check_census(report)
    check_positional_references(report, docs)
    check_audit_invocation(report)
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
