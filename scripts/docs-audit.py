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
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import io
import json
import os
import re
import subprocess
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
SKIP_DIRS = {
    ".venv", ".git", "node_modules", "captures", "runs", "inventory", "__pycache__",
    "dist", "test-results",
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
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
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
    """
    if not candidates:
        return set()
    try:
        done = subprocess.run(
            ["git", "check-ignore", "--stdin"],
            cwd=str(ROOT),
            input="\n".join(candidates).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return set()  # no git: fall back to checking everything
    return {line for line in done.stdout.decode("utf-8", errors="replace").splitlines() if line}


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
        spans = re.findall(r"`([^`]+)`", line)
        if spans:
            yield number, " ".join(spans)


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
            if isinstance(target, ast.Name) and target.id == name:
                if isinstance(node.value, ast.Dict):
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
            if isinstance(target, ast.Name) and target.id == name:
                if isinstance(node.value, (ast.List, ast.Tuple)):
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
    if not exists(path):
        return set()
    return set(re.findall(r"^##\s+(" + letter + r"[1-9][0-9]?)\b", read(path), re.MULTILINE))


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
    scan(docs, in_docs)
    in_code: List[Finding] = []
    scan(python_files(), in_code)

    report.add("decision ids", MECHANICAL, in_docs, f"{len(singles)} D + {len(codes)} C headings")
    # Code is advisory: `C1` or `D2` could plausibly be a variable one day, and a false
    # positive that blocks a commit is worse than one that prints a line.
    report.add("decision ids in code", ADVISORY, in_code, "citations in .py all resolve")


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


# ---------------------------------------------------------------------- current gate


def check_current_gate(report: Report) -> None:
    claude = ROOT / "CLAUDE.md"
    gates = ROOT / "docs" / "GATES.md"
    if not exists(claude) or not exists(gates):
        report.add("current gate", MECHANICAL, [Finding("CLAUDE.md", "missing CLAUDE.md or docs/GATES.md")])
        return

    declared = re.search(r"Current gate:\s*([A-Z])", read(claude))
    if not declared:
        report.add(
            "current gate",
            MECHANICAL,
            [Finding("CLAUDE.md", "no `Current gate: X` line to check.")],
        )
        return

    order: List[Tuple[str, bool]] = []
    for line in read(gates).splitlines():
        heading = re.match(r"^#{2,3}\s+Gate\s+([A-Z])\b(.*)$", line)
        if heading:
            order.append((heading.group(1), "PASSED" in heading.group(2)))

    open_gates = [name for name, passed in order if not passed]
    findings: List[Finding] = []
    if not open_gates:
        findings.append(Finding("docs/GATES.md", "every gate is marked PASSED, but CLAUDE.md names one as current."))
    elif declared.group(1) != open_gates[0]:
        findings.append(
            Finding(
                "CLAUDE.md",
                f"says the current gate is {declared.group(1)}, but the first gate in "
                f"docs/GATES.md not marked PASSED is {open_gates[0]}.",
            )
        )
    summary = f"Gate {declared.group(1)}, first open in GATES.md"
    report.add("current gate", MECHANICAL, findings, summary)


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
    build_order = data.get("BUILD_ORDER") or []
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

    # Exactly one thing is next. Two is how "current" stopped meaning anything the first
    # time: step 4 was done, step 5 untouched, and both read as the place work was
    # happening. Zero is just as wrong — it means nothing is unblocked.
    for label, rows in (("build-order step", build_order), ("gate", gates)):
        nxt = [row for row in rows if row.get("status") == "next"]
        if len(nxt) != 1 and rows:
            named = ", ".join(str(row.get("step", row.get("gate", "?"))) for row in nxt) or "none"
            findings.append(
                Finding(
                    "docs/map.py",
                    f"exactly one {label} must be `next`; found {len(nxt)} ({named}).",
                )
            )

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

    # Build-order steps are numbered in docs/GATES.md; the map must cover the same set.
    in_gates = {int(n) for n in re.findall(r"^(\d{1,2})\.\s", gates_text, re.MULTILINE)}
    in_map = {step.get("step") for step in build_order}
    for number in sorted(in_gates - in_map):
        findings.append(Finding("docs/map.py", f"build-order step {number} is in docs/GATES.md but missing here."))
    for number in sorted(n for n in in_map - in_gates if isinstance(n, int)):
        findings.append(Finding("docs/map.py", f"build-order step {number} is listed here but not in docs/GATES.md."))

    report.add("repo map", MECHANICAL, findings, f"{claimed} entries match the tree")


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
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            if isinstance(body[0].value.value, str):
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

# The one definition, shared with strip_css_comments() in the `raw colour` section below.
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

_RAW_COLOUR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def strip_css_comments(text: str) -> str:
    """A comment replaced by as many newlines as it spanned, so line numbers survive.

    `_CSS_COMMENT_RE` is the one declared in the design-tokens section above and is
    deliberately not redeclared here — see the note on it. The newline-preserving
    substitution is this function's business; what counts as a comment is not.
    """
    return _CSS_COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def check_raw_colour(report: Report) -> None:
    """A colour painted as a literal instead of read from a token.

    The house rule is stated everywhere and was enforced nowhere: stylesheets use
    `var(--token)` and never a raw hex, because the locked palette is only locked if the
    palette is the only place colours come from. `design tokens` above proves
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
    why `#000000` is the wrong ground is prose about a colour, not a colour.

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
            for literal in _RAW_COLOUR_RE.findall(line):
                findings.append(
                    Finding(
                        f"{rel(path)}:{number}",
                        f"paints `{literal}` directly. Read it from a token in "
                        f"app/src/tokens.css — and if no token means what you mean, the "
                        f"missing token is the finding.",
                    )
                )

    report.add("raw colour", MECHANICAL, findings, f"{len(findings)} literals outside tokens.css"
               if findings else "every colour comes from a token")


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
        ok(keys == ["identify", "join", "emit", "reconcile"], "COMMANDS read from cli/__main__.py", str(keys))
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
    # harness/ imported store; T7 later arrived and does import it, so the case pins T3 —
    # a test that reaches pipeline and nothing else.
    if registry:
        found, claims = reach_findings(
            [{"path": "store/", "modules": {"queues.py": {"tested_by": ["T3"]}}}], registry
        )
        ok(
            len(found) == 1 and claims == 1 and "store" in found[0].message,
            "the historical false claim — store/queues.py citing T3 — is reported",
            str(found),
        )
        found, claims = reach_findings(
            [{"path": "pipeline/", "modules": {"join.py": {"tested_by": ["T3"]}}}], registry
        )
        ok(not found and claims == 1, "and the true claim beside it is not", str(found))
        found, _ = reach_findings([{"path": "fixtures/", "tested_by": ["T2"]}], registry)
        ok(
            not found,
            "a directory holding no Python passes on a path literal — fixtures/ from T2",
            str(found),
        )
        found, _ = reach_findings([{"path": "fixtures/", "tested_by": ["T7"]}], registry)
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

    print("\na colour literal is found in CSS, and not in a comment about one")
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
        bool(_RAW_COLOUR_RE.search("color: #1E40AF;")) and not _RAW_COLOUR_RE.search("var(--accent)"),
        "the literal pattern matches a hex and not a token reference",
        "",
    )
    report = Report()
    check_raw_colour(report)
    by_label = {check: findings for check, _, findings, _ in report.checks}
    ok(
        not by_label["raw colour"],
        "this repo's own stylesheets read every colour from a token",
        str(by_label["raw colour"]),
    )

    # The staged-mode primitives, which have no loud failure mode: every one of them
    # answers plausibly against the worktree while auditing a tree the commit will not
    # produce. Driven through the module globals because that is how audit() drives them.
    print("\nstaged mode answers about the index, not the worktree")
    global _INDEX_PATHS
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
    check_env_vars(report, docs, allowed)
    check_current_gate(report)
    check_map(report, allowed)
    check_tested_by_reach(report)
    check_status_sources(report)
    check_design_tokens(report)
    check_raw_colour(report)
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
