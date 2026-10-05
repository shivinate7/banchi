"""Shared readers, the Report type and the package state. Every other module imports from here."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections.abc import MutableMapping
from fnmatch import fnmatch
from functools import lru_cache
from pathlib import Path
from typing import Dict, FrozenSet, List, NamedTuple, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent.parent

MECHANICAL = "mechanical"
ADVISORY = "advisory"

# `views exposure` (below) is OFF as of 2026-09-23. Code cards are DORMANT (CLAUDE.md,
# "Code cards (dormant feature)") — the owner has not run the feature, so no session is
# drawing pooled captures onto a screen this row would flag. `scripts/guard-opsec.sh` stays
# ARMED regardless; it is the mechanism that protects real money, not this advisory. Flip
# this back to True when code-card work resumes, per CLAUDE.md's own note.
VIEWS_EXPOSURE_ENABLED = False

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
GAME_COVERAGE_ALLOWLIST = ROOT / "scripts" / "docs-audit-allow-game-coverage.txt"

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
    where: str  # a file and its line number, or just a filename
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


def _merge_rows(name: str, rows: "List[Row]") -> Row:
    """Combine several sub-checks' verdicts into the one row the report prints.

    M3 (test-audit-2026-09-27, L8): several rows that reconcile the same kind of
    fact — the logo family, the vocabulary family, and a handful of pairs — are one
    printed row now, never more code or a lighter check. Each sub-check keeps its
    own function and its own body untouched; only `report.add` moved out of it, into
    a `Row` it returns instead. This is what turns several of those back into one:
    every finding survives, `scanned` sums what each sub-check scanned, and the row
    is MECHANICAL if any sub-check is — a family is never quieter than its loudest
    member.
    """
    findings: List[Finding] = [f for row in rows for f in row.findings]
    scanned_parts = [row.scanned for row in rows if row.scanned is not None]
    scanned = sum(scanned_parts) if scanned_parts else None
    severity = MECHANICAL if any(row.severity == MECHANICAL for row in rows) else ADVISORY
    summary = (
        "; ".join(f"{row.check}: {row.summary}" for row in rows if row.summary)
        if not findings else ""
    )
    return Row(name, severity, findings, summary, scanned)


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
    "line anchors": ("staged", "counts the staged documents it read for a line anchor"),
    "make targets": ("staged", "counts the `make` references it found in the staged documents"),
    "identifier spelling": (
        "staged",
        "counts the spelling-suffix files THIS COMMIT TOUCHES (test-audit plan S2) — a "
        "commit that touches none of them, and does not touch scripts/docs-audit.py itself, "
        "legitimately scans zero",
    ),
    "spec map": (
        "staged",
        "path-gated (test-audit plan S3) — a staged commit touching neither app/ nor "
        "scripts/browser-scope.py skips the row and scans zero",
    ),
    "env vocabulary": ("staged", "counts the variables the staged documents name"),
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
    "numbered record growth": (
        "always",
        "its subject is the numbered decision/debt files the staged diff (or, in a full "
        "run, the branch's history since the merge-base) changes — most commits and most "
        "branches touch neither corpus, and no merge-base fails open the same way",
    ),
    "views exposure": (
        "always",
        "turned OFF 2026-09-23 while code cards are dormant (CLAUDE.md) — "
        "VIEWS_EXPOSURE_ENABLED is False, so this row examines nothing on purpose",
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
        # A SUMMARY IS A CLEAN VERDICT AND IS WITHHELD WHEN THE ROW HAS FINDINGS.
        # `render()` above already does this — it prints the summary only in the `not
        # findings` branch, and a tag plus a count otherwise. This surface did not, and
        # emitted both, so the row contradicted itself in the one place a session greps.
        # Measured 2026-09-20: `views exposure` published "no manifest view can draw a
        # stored photo" beside 7 findings each naming a view that can, and `doc hygiene`
        # published "373 markdown files well-formed as documents" beside 10 saying they
        # are not. Most rows compose the summary unconditionally, so this is the shape of
        # every row and not a typo in two — which is why it is fixed here, once, rather
        # than in 200-odd `report.add` call sites.
        rows = [
            {"label": row.check, "severity": row.severity,
             "summary": row.summary if not row.findings else None,
             "scanned": row.scanned, "vacuous": row.scanned == 0,
             "findings": [finding._asdict() for finding in row.findings]}
            for row in self.checks
        ]
        return json.dumps({"rows": rows, "exit": exit_code}, indent=2)

    def render(self) -> str:
        lines = ["PKMNSCAN docs audit — docs/decisions/ D16", "=" * 72, ""]
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
    """Every TRACKED markdown file: the index in staged mode, `git ls-files` otherwise.

    A file git does not track is no part of the repo's prose, so a scratch `.md` left in the
    worktree never fails a row. Before this, the worktree walk read it, and a scratch file
    with one semicolon failed `ste offenders` by hand while the pre-commit hook, which reads
    the index, passed. A file that is tracked but deleted from disk is not read either: the
    walk never finds it. With no git answer at all (not a checkout, or git missing), it
    falls back to the walk and reads every file it finds, which is the older behaviour.
    """
    found = _walk(ROOT, (".md",))
    if _INDEX_PATHS is not None:
        return found
    tracked = _nul_list("ls-files", "-z")
    if not tracked:
        return found
    return [path for path in found if rel(path) in tracked]


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


# D60's row. Reads docs/decisions/ by hard-coded path, so it answers on every run rather
# than only when that file is staged — the same asymmetry check_map and check_pass_criteria
# already have, and for the same reason: a broken heading there breaks every consumer, not
# only the commit that wrote it.
#
# `entry budget`, which used to sit beside this row, is CUT (owner ruling, test-audit-
# 2026-09-27/TIERS.md row 20, 2026-09-28): it printed a standing advisory nobody acted on.


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
        # Registered in sys.modules BEFORE exec. A sibling with its own `@dataclass` classes
        # under `from __future__ import annotations` (scripts/ste_measure.py is the first)
        # resolves its field types by looking itself back up in sys.modules mid-definition;
        # skipping this step fails with an unrelated-looking AttributeError on the stdlib's
        # own dataclasses internals rather than on anything this file does.
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module
    except Exception:  # noqa: BLE001 - a broken sibling must not take the audit down
        return None


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


# The step namespace has no letter in front of it — `step 7`, or the slug form while the
# branch is open — so the slug alone is the token and it carries no leading hyphen. Same floor.
_STEP_SLUG = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+"


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


_GATES_STEP_SLUG = re.compile(r"^0\.\s+`step (" + _STEP_SLUG + r")`", re.M)

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}

# ------------------------------------------ shrinking offender lists (D280)
#
# THE OWNER'S RULING, 2026-09-24: no pinned count survives. D284's word ceiling went first
# (D284). D218's typed-dot count and D280's per-file prose ratio follow it
# here. Each is replaced by a RULE check and a SHRINKING OFFENDER LIST in the shape
# `scripts/kit-adoption-allow.json` set: file -> rule -> entries, with the lane that owes the
# fix. Three things fail, and a count is none of them:
#
#   1. an offender the list does not name (a NEW offender, in a listed file or not);
#   2. a listed entry that matches nothing (STALE: the fix landed, so delete the entry);
#   3. an entry the list at the merge-base with `origin/main` did not hold (GROWTH), unless
#      its rule is not defined at the merge-base (a rule born on this branch).
#
# AN ENTRY IS AN IDENTITY, NEVER A NUMBER. The typed-dot list holds the offending string
# itself. The prose list holds a hash of the offending sentence (`scripts/ste_measure.py:
# offender_identity`) and a label for the person who fixes it. A string or sentence that
# occurs twice in one file is listed twice, so a copy of a listed offender is never hidden
# behind the first.
#
# GROWTH IS COUNTED ACROSS THE WHOLE LIST, NOT PER FILE. An identity may sit under a different
# file at HEAD than at the merge-base, so a `git mv` moves its entries with it and adds
# nothing. A copy of a listed sentence into a second file is still growth: the identity now
# occurs once more than the merge-base allowed. And a BRAND-NEW FILE may not be listed at all
# unless its entries moved out of another file in the same branch: a new document or a new
# component starts clean, because its author is writing it now.
#
# D18: the rows only READ. THE ONLY-SHRINKS RULES LIVE IN ONE HELPER, `scripts/only_shrinks.py`
# (`list_at_merge_base`, `growth`), which `scripts/kit-adoption.mjs` runs as a command. The
# merge-base read is `git merge-base` and `git show`, two plain reads. IT FAILS OPEN, AND PRINTS WHY:
# no git, no `origin/main`, no merge-base, or no list at the merge-base (the branch that gives
# the list its birth).

_MERGE_BASE_REFERENCE = "origin/main"

# ------------------------------------------------------- route rosters in the specs

# A `//` or `/* */` comment, so a route named in PROSE is not read as a route the file
# pins. Both spec files below discuss routes they deliberately do not walk — nav.spec.ts
# reasons about `#/fulfillment` at length and asserts nothing on it — and counting those
# would fire this check at a file that is behaving.
TS_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)


def _strip_ts_comments(text: str) -> str:
    return TS_COMMENT.sub(" ", text)


def _check_recipe() -> Optional[List[str]]:
    """The targets `make check` runs, in run order: the registry's, or None if unreadable."""
    registry = ROOT / "scripts" / "checks.py"
    if not exists(registry):
        return None
    entries = literals_from_module(registry).get("CHECKS")
    if not isinstance(entries, (list, tuple)):
        return None
    return [str(entry["target"]) for entry in entries]


# ------------------------------------------------- the checks defined here vs the ones run


PACKAGE_DIR = Path(__file__).resolve().parent

# The entry script. `main()` and `build_parser()` live in it; every row lives in the package
# beside it (`PACKAGE_DIR`).
SELF = PACKAGE_DIR.parent / "docs-audit.py"


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


# THE ALLOWLIST IS KEYED BY (path, function, shape) AND NEVER BY LINE NUMBER, because a
# line number moves the day somebody edits an unrelated docstring above it and the guard
# would then fail on a site that did not change. `shape` disambiguates a function that
# makes more than one kind of unscoped call (store/master.py's `to_payload` calls
# `.items()` on `self.cards`, `self.boxes` AND `self.listings` — only the `cards` one is
# on this list, matched by `shape="items"` restricted to the `.cards` chain in the
# matcher itself, never by which `.items()` call comes first in the function body).
#
# `do_inventory`'s `to_payload()` call is kept here PERMANENTLY, on the owner's word
# ("do_inventory is kept, unused, on the allowlist").
#
# `store/master.py:next_box_number`'s `.distinct("box")` IS A THIRTEENTH SITE THE
# HAND CENSUS MISSED — this scanner found it the first time it ran against the
# real tree (the census named twelve). It is the same shape as `do_boxes`/`counts` right above and below
# it in this list: one indexed column, read once per box CREATION rather than per load or
# per press, which is cheaper than either of those two already-permanent entries. Kept
# here permanently for the same reason they are — the guard names it and moves on — and
# the count is 13, not 12, because the tree already had this site; nothing
# added it, this row's own scan just found what the hand census did not.
#
# THIS COUNT MAY ONLY GO DOWN FROM HERE, same rule as `PROSE_ONLY_EXPECTED` above: an item
# that removes a full-table read deletes its tuple from UNSCOPED_WALK_ALLOWED and lowers
# UNSCOPED_WALK_EXPECTED in the SAME commit, or the row reports a stale allowlist entry
# (site not found) rather than silently shrinking. An item that cannot yet remove its
# site for some reason must not touch the count.
#
# THE ONE-PASS COPIES REWRITE REPLACED ONE ENTRY WITH ANOTHER RATHER THAN REMOVING ONE. `_copies_
# out` and `_committed_keys` (`cli/resolve.py`) used to each call `Inventory.positions_for_
# sku`/`copies_not_sold`/`sales_before`/`copies_on_hand` once PER SKU — none of those are
# `.select()`/`.distinct()` on `.cards` directly (they are `Rows.where(sku=sku)` calls one
# level down in `store/master.py`, invisible to this scanner, which is exactly the cost
# the guard sees shapes on the page, not
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
# STORE-WIDE aggregate that D277 requires (a percentile/cut-off ranking over every on-hand
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
    ("server/pipeline_routes.py", "_value_rows", "select"),   # renamed from `do_pipeline_value`'s `.values()`; the aggregate pass is unavoidably store-wide (D277), so the CALL survives, only its shape and enclosing function change
    ("store/master.py", "to_payload", "items"),
    ("store/master.py", "counts", "select"),
    ("store/master.py", "next_box_number", "distinct"),   # kept permanently — one indexed column, cheap; missed by the hand census
    ("cli/resolve.py", "box_views", "select"),   # renamed from `.values()`; the unbounded (`boxes=None`) branch every existing caller still uses is genuinely store-wide, for the same reason `_value_rows` is
    ("cli/resolve.py", "_cards_by_sku", "select"),   # one pass, replaces per-SKU `_copies_out`/`_committed_keys`/`_unsent_ledger` reads; the `_unsent_ledger` distinct scan above is deleted, not merely moved
    ("server/capture_server.py", "do_inventory_copies", "select"),   # §27, site 1 — a NEW full-table scan, added rather than removed, and named as a cost paid: `POST /inventory/copies` replaces `Orders.tsx`'s `GET /inventory` (D192's own site 1), and the one unfiltered `_cards_by_sku`-shaped pass here is what lets the box set handed to `_Places.for_keys` be DERIVED from the scan rather than guessed at from the request — the docstring on the function has the full argument for why that is sound where box-scoping the walk itself is not. This is the count going UP by one, on purpose, for a route this file's own item 1 could not have existed to forbid before it existed to write.
    ("server/capture_server.py", "_facet_cells", "select"),   # D213's inventory filter, moved here from `_card_facets` by FLT-09: `_facet_cells` is now the ONE scan and `_card_facets` folds its answer, so `GET /boxes` still pays one pass for both blocks. Was: — a NEW full-table scan, added rather than removed. It answers "what game/set/rarity values does this store hold, and how many of each" — an aggregate over every distinct value, which by definition cannot be scoped to one `equals` filter the way a lookup can. `GET /boxes` already pays one O(cards) pass per box (`_box_row`'s own docstring); this adds one MORE full pass, on the same route, at the same poll cadence — named here rather than folded into an existing entry because it is a genuinely new site, over three columns rather than the two-or-three `_cards_by_sku`/`do_inventory_copies` already read.
    # `pipeline/` joined this row's roots with the loop guard; its five existing walks are named, not new.
    ("pipeline/holdings.py", "on_hand_quantities", "select"),   # a store-wide on-hand count by SKU, one pass per call
    ("pipeline/holdings.py", "on_hand_names", "select"),   # a store-wide on-hand name lookup, one pass per call
    ("pipeline/holdings.py", "sealed_excluded_count", "select"),   # a store-wide count of excluded sealed cards, one pass per call
    ("pipeline/pricearchive.py", "rows_from_store", "select"),   # the price-history archive sweep reads every card once, by design
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
# closing §27 site 1 (`Orders.tsx`'s `GET /inventory`) by replacing a whole-
# store WIRE PAYLOAD with a whole-store SERVER-SIDE scan that answers only the requested
# SKUs — the cost moves, it does not disappear, and this row exists precisely to keep that
# honest. It earns its own allowlist entry rather than folding into an existing one, because
# it is a genuinely new site even though its shape (one unfiltered `.select()`) matches
# `_cards_by_sku`'s — see that entry's own comment, above, for why one unfiltered scan is
# the correct implementation here rather than a shortcut around scoping it.
#
# 10 -> 11, D213's INVENTORY FILTER (the scan moved to `_facet_cells` with FLT-09, the count
# unchanged). `_card_facets` is a NEW full-table scan, added rather
# than removed, for the same reason `do_inventory_copies` and `_value_rows` are on this
# list already: the question it answers ("what game/set/rarity values exist, and how many
# of each") is a store-wide aggregate by definition, over the same `GET /boxes` route that
# already pays `_box_row`'s O(cards) cost once per box. Named as a cost paid, not hidden.
UNSCOPED_WALK_EXPECTED = 15

# Expensive store calls made once per loop item: (path, function, callee). The count only goes down; see `check_loop_expensive`.
LOOP_EXPENSIVE_ALLOWED: FrozenSet[Tuple[str, str, str]] = frozenset({
    ("pipeline/selection.py", "resolve", "sidecar.scan"),   # one directory scan per capture root, bounded by the roots the person named
    ("cli/cmd_join.py", "run", "read_export"),   # one export read per game join, bounded by the games
    ("cli/cmd_match.py", "_write_chunk", "read_export"),   # one re-read per export path on purpose, so the lock re-checks the file as it stands; bounded by games
    ("cli/cmd_match.py", "sweep_worker", "_write_chunk"),   # one call per chunk of results, and each call re-reads the exports by design (the entry above); chunk count grows with the sweep
    ("cli/cmd_pricearchive.py", "_sweep", "Store.write"),   # one write per chunk of SKUs by design, so a long sweep commits as it goes; each write is its own transaction
    ("cli/requeue.py", "catalogs_from", "read_export"),   # one export read per path the caller passed, bounded by games
    ("cli/resolve.py", "_claim_files", "read_export"),   # one export read per distinct export path, bounded by games
    ("cli/resolve.py", "_resolve", "read_export"),   # two sites, one export read per mapped path, cached in `parsed`; bounded by games
    ("pipeline/pricehistory.py", "reading_for_row", "history"),   # one history read per range, and there are a fixed few ranges
    ("pipeline/pricehistory.py", "readings_for_rows", "history"),   # one history read per range, and there are a fixed few ranges
    ("pipeline/setnames.py", "known_sets", "read_export"),   # one read per CSV in the export directory, bounded by the exports kept
    ("pipeline/skus.py", "fill", "read_export"),   # one read per export file in date order, bounded by the exports kept
    ("server/capture_server.py", "_require_group_answers", "Store.read"),   # runs only on the duplicate-position refusal path, once, then raises
    ("server/capture_server.py", "do_boxes", "_layout_digest"),   # one layout read per box row, so the total is one pass over the cards
    ("server/capture_server.py", "do_move_sections_batch", "_box_digest"),   # one records_in read per box the batch touched, a bounded box set
    ("server/capture_server.py", "do_move_sections_batch", "_box_state"),   # one records_in read per box the draft names, a bounded box set
    ("server/capture_server.py", "do_move_sections_batch", "_layout_digest"),   # one layout read per box in the draft, bounded by the boxes the draft names
    ("server/capture_server.py", "do_move_sections_batch", "_move_range_core"),   # one layout read per move in the batch; CANDIDATE if batches grow large
    ("server/capture_server.py", "do_move_sections_batch", "_move_sections_core"),   # one layout read per move in the batch; CANDIDATE if batches grow large
    ("server/capture_server.py", "do_move_sections_batch", "_next_capture_line"),   # one layout read per box the last move touched, at most three
    ("server/capture_server.py", "do_undo_section_move", "_box_digest"),   # one records_in read per box the move recorded, at most three
    ("server/pipeline_routes.py", "_catalog_rows", "read_export"),   # one export read per game of one run, bounded by games
    ("server/pipeline_routes.py", "_run_live_by_sku", "read_export"),   # one export read per distinct export path of one run, bounded by games
    ("server/pipeline_routes.py", "_scanned", "sidecar.scan"),   # one directory scan per capture root, bounded by the roots
    ("server/pipeline_routes.py", "_selection_captures", "sidecar.scan"),   # one directory scan per capture root, bounded by the roots
    ("server/pipeline_routes.py", "_unsent_ledger", "_run_live_by_sku"),   # CANDIDATE: re-reads each run's exports once per run, so it grows with the run count
    ("server/pipeline_routes.py", "do_pipeline_export", "_export_report"),   # one previous-export read per game the answers cover, bounded by games
    ("server/send_routes.py", "_claim_refusal", "_markdown_blocks"),   # the loop returns on its first pass, so the Store().read() runs once
    ("server/send_routes.py", "_credits", "_sold_since"),   # CANDIDATE: one Store().read() per SKU when the receipt has no `sold_before`; read once per request
    ("server/send_routes.py", "_live_check", "_held_stamps"),   # CANDIDATE: one Store().read() per due stamp; read once before the loop
    ("server/send_routes.py", "_live_check", "_release"),   # one store write per due stamp, bounded by pending sends; each write must be its own transaction
    ("server/send_routes.py", "_live_check", "_resolve_markdown"),   # one export read and one store write per pending markdown stamp, bounded by pending sends
    ("server/send_routes.py", "_write_and_send", "_copies"),   # one read per import file this press wrote, at most one per game
    ("server/send_routes.py", "_write_and_send", "_names"),   # one read per import file this press wrote, at most one per game
    ("server/send_routes.py", "_write_and_send", "_price_rows"),   # one read per import file this press wrote, at most one per game
    ("store/master.py", "place", "_respace"),   # the loop is `range(2)`, a fixed two passes
    ("store/master.py", "place", "_try_place"),   # the loop is `range(2)`, a fixed two passes
    ("store/master.py", "section_tail_key", "_respace"),   # the loop is `range(2)`, a fixed two passes
    ("store/orders.py", "record_pull", "holder_of"),   # CANDIDATE: `holder_of` walks the open orders once per capture id pulled
})
LOOP_EXPENSIVE_EXPECTED = 39


# ---------------------------------------------------------------- the package's shared state

def _package_modules():
    """Every loaded module of this package, the self-test modules included."""
    prefix = __package__ + "."
    return [module for name, module in list(sys.modules.items())
            if name.startswith(prefix) and module is not None]


class _Namespace(MutableMapping):
    """The package's module globals as ONE mapping, so a name patched here is patched everywhere.

    The audit was one file, so `globals()["_walk"] = stub` replaced the function for every row.
    Now a name is defined in one module and imported by value into the modules that use it, so
    a patch has to reach every copy. A read answers from the first module that holds the name;
    a write goes to every module that holds it.
    """

    def _homes(self, name):
        return [vars(module) for module in _package_modules() if name in vars(module)]

    def __getitem__(self, name):
        homes = self._homes(name)
        if not homes:
            raise KeyError(name)
        return homes[0][name]

    def __setitem__(self, name, value):
        homes = self._homes(name)
        if not homes:
            raise KeyError(name)
        for home in homes:
            home[name] = value

    def __delitem__(self, name):
        raise TypeError("a package name is patched, never deleted")

    def __iter__(self):
        return iter({name for module in _package_modules() for name in vars(module)})

    def __len__(self):
        return len(set(iter(self)))


def module_globals() -> MutableMapping:
    """The mapping the self-test patches through; see `_Namespace`."""
    return _Namespace()


entry_parser_hook = None  # set by scripts/docs-audit.py when it loads: its `build_parser`


def entry_parser():
    """The argparse parser `scripts/docs-audit.py` declares, which `main()` there parses with.

    The entry script keeps `build_parser` and `main` (`scripts/status.py` reads those two names
    out of it), so the rows that check the command line reach it through the hook the script
    sets on load. A caller that imports the package alone gets it loaded by path instead,
    under a private name, never `docs_audit`, which is this package.
    """
    if entry_parser_hook is not None:
        return entry_parser_hook()

    path = Path(__file__).resolve().parent.parent / "docs-audit.py"
    spec = importlib.util.spec_from_file_location("_docs_audit_entry", path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module.build_parser()


def set_root(path: Path) -> None:
    """Point every row at another tree. ROOT lives here and each module holds an imported copy,
    so the one name is rebound in all of them. `--self-test` and the callers that audit a
    fixture (`subagent-override-selftest.py`) use it."""
    module_globals()["ROOT"] = path
