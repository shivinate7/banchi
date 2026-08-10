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
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent

MECHANICAL = "mechanical"
ADVISORY = "advisory"

# Directories that are not this project's source. `.venv` alone holds hundreds of vendored
# READMEs, and auditing someone else's markdown would be noise with a straight face.
SKIP_DIRS = {".venv", ".git", "node_modules", "captures", "runs", "inventory", "__pycache__"}

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

    Same reasoning as harness/run.py running all six tests after one fails: a status
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


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def top_level_names() -> Set[str]:
    return {entry.name for entry in ROOT.iterdir()}


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

    missing = [item for item in seen if not item[3].exists()]
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
            if module.exists():
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
    if not ALLOWLIST.exists():
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
            arrived = (ROOT / entry).exists()
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


def check_make_targets(report: Report, docs: List[Path]) -> None:
    makefile = ROOT / "Makefile"
    if not makefile.exists():
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
    if not main.exists():
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
    if not gates.exists():
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
    if not runner.exists():
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
        if not path.exists():
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
    """
    sections = gates_sections()
    mechanical: List[Finding] = []
    wording: List[Finding] = []
    for name, path in registered_tests():
        if not path.exists():
            continue
        criteria = string_assign(read(path), "PASS_CRITERIA")
        if criteria is None:
            mechanical.append(
                Finding(rel(path), "no module-level PASS_CRITERIA string to read.")
            )
            continue
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


# ---------------------------------------------------------------------- decision ids

_DECISION_RE = re.compile(r"\bD([1-9][0-9]?)\b")
_CODES_DECISION_RE = re.compile(r"\bC([1-9][0-9]?)\b")


def decision_headings(path: Path, letter: str) -> Set[str]:
    if not path.exists():
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
        if candidate.exists():
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
    if not claude.exists() or not gates.exists():
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
SOURCE_SUFFIX = ".py"


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
    """
    findings: List[Finding] = []
    if not MAP.exists():
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

    def check_decisions(where: str, names: Sequence[str]) -> None:
        for name in names:
            if name not in singles:
                findings.append(Finding(where, f"governed_by cites {name}, which has no heading in docs/DECISIONS.md."))

    def check_tests(where: str, names: Sequence[str]) -> None:
        for name in names:
            if name not in test_names and name not in allowed:
                findings.append(Finding(where, f"tested_by cites {name}, which is not registered in harness/run.py:TESTS."))

    for component in components:
        path = component.get("path", "")
        status = component.get("status", "")
        target = ROOT / path
        claimed += 1
        where = f"docs/map.py -> {path}"

        if status == "planned":
            if target.exists():
                findings.append(
                    Finding(
                        where,
                        f"`{path}` is marked planned but exists now (build-order step "
                        f"{component.get('step', '?')}). Update the entry to built and "
                        f"list its modules.",
                    )
                )
        elif not target.exists():
            findings.append(Finding(where, f"`{path}` is marked {status or 'built'} but does not exist."))

        check_decisions(where, component.get("governed_by") or [])
        check_tests(where, component.get("tested_by") or [])

        modules = component.get("modules") or {}
        for name, entry in modules.items():
            module_path = target / name
            module_where = f"docs/map.py -> {path}{name}"
            claimed += 1
            if not module_path.exists():
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

        # Orphans: a source file the map never mentions.
        if modules and target.is_dir():
            on_disk = {
                item.name
                for item in target.iterdir()
                if item.is_file() and item.suffix == SOURCE_SUFFIX and item.name != "__init__.py"
            }
            for orphan in sorted(on_disk - set(modules)):
                findings.append(
                    Finding(
                        f"docs/map.py -> {path}",
                        f"`{path}{orphan}` exists but no entry describes it. Add it to "
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
    gates_text = read(ROOT / "docs" / "GATES.md") if (ROOT / "docs" / "GATES.md").exists() else ""
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
    if not STATUS.exists():
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
            targets = sorted((ROOT / parent).glob(glob)) if (ROOT / parent).is_dir() else []
        else:
            target = ROOT / path
            targets = [target] if target.exists() else []

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


# -------------------------------------------------------------------- the check registry


SELF = Path(__file__).resolve()

# The docs that publish how many checks this script runs. That number is prose, so layer 1
# never looked at it: D16 read "twelve" for two commits after there were thirteen. A count
# is the first thing a reader trusts about a tool they have not opened, and it was the one
# claim in this repo whose subject was the auditor itself.
COUNT_CLAIMS = ("docs/DECISIONS.md", ".claude/commands/docs-audit.md")

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}

# Digits or the word, because these files spell small numbers out and a rule that accepted
# only one form would be a rule about house style rather than about the count.
_COUNT_CLAIM_RE = re.compile(
    r"\b(\d{1,2}|" + "|".join(_NUMBER_WORDS) + r")\s+checks\b", re.IGNORECASE
)

# A check named by position. D17 already ruled against it for the repo-map check — "named
# rather than numbered, because a positional index re-drifts every time a check is added,
# and this one already had" — and the rest of the repo had not caught up: the section
# headers in this file ran 1 to 10 and then jumped, so two numbers in circulation pointed
# at nothing at all.
_POSITIONAL_RE = re.compile(r"\bchecks?\s+\d{1,2}\b", re.IGNORECASE)


def claimed_counts(text: str) -> List[Tuple[int, str, int]]:
    """(line number, the words as written, the number they mean) for each published count.

    Its own function so the self-test can feed it the prose that nearly fools it. D8 says
    "Threshold checks and pricing rules run directly against it", which is a sentence about
    prices and must not read as a claim about this script.
    """
    out: List[Tuple[int, str, int]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for raw in _COUNT_CLAIM_RE.findall(line):
            out.append((number, raw, _NUMBER_WORDS.get(raw.lower()) or int(raw)))
    return out


def _report_labels(func: ast.FunctionDef) -> List[str]:
    """Distinct labels a check function hands to Report.add, in source order."""
    labels: List[str] = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Attribute) and node.func.attr == "add"):
            continue
        if not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            if first.value not in labels:
                labels.append(first.value)
    return labels


class Registry(NamedTuple):
    layer1: List[str]  # labels from the calls audit() makes unconditionally
    layer2: List[str]  # labels from the calls inside its staged_only branch
    defined: List[str]  # every label any check_* function in the file emits
    unaccounted: List[str]  # defined, but in neither layer — see registered_labels


def registered_labels(path: Path = SELF) -> Registry:
    """What this script's own source says its checks are. Takes a path so it is testable.

    Parsed with `ast` rather than collected by running `audit()`, for the reason every
    other reader here is: the number has to be true of the file that gets committed. A
    registry gathered at run time agrees with itself no matter what the source says.

    Layer 2 is what `audit()` calls inside its `staged_only` branch — the coupling
    question, which only the pre-commit hook ever runs.

    **`unaccounted` is the part that matters, and it is not a nicety.** Reading the plain
    calls in `audit()` is an inference about the shape of the code, and the dangerous way
    for it to break is halfway: restructure eleven of those calls into a loop, leave three
    behind, and this returns 3 with no complaint. The caller would then report that the
    docs overstate the count — and the obvious way to clear that red commit is to edit D16
    down to three, at which point the docs are wrong, the check is green, and nothing will
    ever notice again. So the labels are counted a second way, from the function
    definitions, which no restructuring of `audit()` moves. A label that exists there and
    turns up in neither layer means this reader can no longer account for every check, and
    the caller must refuse to publish a number rather than argue the docs toward it.
    """
    try:
        tree = ast.parse(read(path))
    except (OSError, SyntaxError):
        return Registry([], [], [], [])
    emits = {
        node.name: _report_labels(node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("check_")
    }
    defined: List[str] = []
    for labels in emits.values():
        defined.extend(label for label in labels if label not in defined)

    audit_fn = next(
        (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "audit"),
        None,
    )
    if audit_fn is None:
        return Registry([], [], defined, defined)

    def called(body: Sequence[ast.stmt]) -> List[str]:
        names: List[str] = []
        for statement in body:
            if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
                continue
            func = statement.value.func
            if isinstance(func, ast.Name) and func.id in emits:
                names.extend(label for label in emits[func.id] if label not in names)
        return names

    layer1 = called([s for s in audit_fn.body if not isinstance(s, ast.If)])
    layer2 = []
    for statement in audit_fn.body:
        if isinstance(statement, ast.If):
            layer2.extend(called(statement.body))
    layer2 = [label for label in layer2 if label not in layer1]
    seen = set(layer1) | set(layer2)
    return Registry(layer1, layer2, defined, [d for d in defined if d not in seen])


def check_registry(report: Report, docs: List[Path], source: Path = SELF) -> None:
    """The count the docs publish, against the registry `audit()` actually builds.

    `source` is which file to read the registry out of. It is this one in every real run,
    and a fixture in `--self-test` — the reader's behaviour on a shape it cannot read has
    to be provable without restructuring the live script to find out.

    Every other check here asks whether a claim about the project is still true. This one
    asks whether the claim about the checker is, which nothing else was ever going to do.

    **Three rows, because there are three different questions here.** They do not share a
    scope and they do not share a severity, so a combined verdict would have had to take
    the widest scope and the strictest severity of the three and apply both to all of them:

      check count        the published number. Reads COUNT_CLAIMS whatever `--staged` says,
                         the way `check_pass_criteria` reads every test — the claim is
                         about this script, not about the diff. Blocks: a wrong count is
                         wrong with no judgment involved. The one exception is below.

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

    **The exception: a confused reader asks, it does not block.** If `registered_labels`
    cannot account for every check it finds defined, the count is not compared at all and
    the row goes ADVISORY. Publishing a number this reader does not stand behind is the one
    outcome worse than publishing none: the docs would get edited to match it, and a wrong
    count that agrees with its checker is invisible forever. Downgrading rather than
    blocking is also the rule `scripts/githooks/pre-commit` already applies one level up —
    "a broken auditor is not evidence the docs are wrong."
    """
    registry = registered_labels(source)
    counts: List[Finding] = []
    severity = MECHANICAL
    summary = ""

    if not registry.layer1 or registry.unaccounted:
        severity = ADVISORY
        summary = "reader could not account for every check — count NOT compared"
        if not registry.layer1:
            detail = (
                "cannot find the check calls in `audit()` at all.\n"
                "This reader parses the plain calls in that function, so restructuring it "
                "into a table or a loop needs the reader updated with it."
            )
        else:
            detail = (
                f"{len(registry.defined)} labels are defined by a `check_*` function, but "
                f"these turn up in neither layer of `audit()`:\n"
                f"  {', '.join(registry.unaccounted)}\n"
                f"Either a check is registered nowhere, or this reader can no longer see "
                f"how `audit()` calls it."
            )
        counts.append(
            Finding(
                "scripts/docs-audit.py",
                f"{detail}\n"
                f"The published count is NOT checked while this is true. Do not edit the "
                f"number in the docs to match anything this row says — fix the reader, or "
                f"wire up the check it lost track of.",
            )
        )
    else:
        expected = len(registry.layer1)
        staged = ", ".join(registry.layer2) or "none"
        roster = f"  layer 1: {', '.join(registry.layer1)}\n  layer 2 (--staged): {staged}"
        summary = f"{expected} registered, {expected} published"
        for name in COUNT_CLAIMS:
            path = ROOT / name
            if not path.exists():
                continue  # a missing file is the path check's finding, not this one's
            claims = claimed_counts(read(path))
            if not claims:
                counts.append(
                    Finding(
                        name,
                        f"publishes no `N checks` count, so nothing here is verifiable.\n"
                        f"Say how many there are — {expected} — or this check is decoration.",
                    )
                )
                continue
            for number, raw, value in claims:
                if value != expected:
                    counts.append(
                        Finding(
                            f"{name}:{number}",
                            f"says `{raw} checks`, but `audit()` registers {expected}.\n"
                            f"{roster}",
                        )
                    )

    def positional(paths: Iterable[Path]) -> List[Finding]:
        found: List[Finding] = []
        for path in paths:
            if not path.exists():
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

    report.add("check count", severity, counts, summary)
    report.add("check numbering", MECHANICAL, positional(docs), "no check named by position")
    report.add(
        "numbering in code",
        ADVISORY,
        positional(python_files() + [ALLOWLIST]),
        "comments name checks by label",
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
    """
    changes: Dict[str, int] = {}
    for line in git("diff", "--cached", "--numstat", "--diff-filter=ACMR").splitlines():
        parts = line.split("\t")
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

    print("\nthe registry reads itself, and the published count is checkable")
    live = registered_labels()
    ok(
        "paths" in live.layer1 and "check count" in live.layer1 and len(live.layer1) > 10,
        "audit()'s layer-1 labels are read from source",
        str(live.layer1),
    )
    ok(live.layer2 == ["coupling"], "the staged-only branch is layer 2", str(live.layer2))
    ok(not live.unaccounted, "every defined check is accounted for", str(live.unaccounted))

    # The reader against a file that is not itself. The second fixture is the failure that
    # matters: audit() restructured into a loop, where inferring from call statements
    # returns a plausible number instead of nothing. `unaccounted` is what refuses it.
    print("\nthe reader is honest about a shape it cannot read")
    with tempfile.TemporaryDirectory() as tmp:
        flat = Path(tmp) / "flat.py"
        flat.write_text(
            "def check_alpha(report):\n"
            "    report.add('alpha', MECHANICAL, [], '')\n"
            "def check_beta(report):\n"
            "    report.add('beta', MECHANICAL, [], '')\n"
            "    report.add('beta extra', MECHANICAL, [], '')\n"
            "def check_late(report):\n"
            "    report.add('late', ADVISORY, [], '')\n"
            "def audit(staged_only):\n"
            "    report = Report()\n"
            "    check_alpha(report)\n"
            "    check_beta(report)\n"
            "    if staged_only:\n"
            "        check_late(report)\n"
            "    return report\n",
            encoding="utf-8",
        )
        parsed = registered_labels(flat)
        ok(
            parsed.layer1 == ["alpha", "beta", "beta extra"],
            "a function emitting two rows contributes both",
            str(parsed.layer1),
        )
        ok(parsed.layer2 == ["late"], "the staged-only call is layer 2", str(parsed.layer2))
        ok(
            not parsed.unaccounted,
            "nothing unaccounted in a shape it can read",
            str(parsed.unaccounted),
        )

        looped = Path(tmp) / "looped.py"
        looped.write_text(
            "def check_alpha(report):\n"
            "    report.add('alpha', MECHANICAL, [], '')\n"
            "def check_beta(report):\n"
            "    report.add('beta', MECHANICAL, [], '')\n"
            "def audit(staged_only):\n"
            "    report = Report()\n"
            "    for check in (check_alpha, check_beta):\n"
            "        check(report)\n"
            "    return report\n",
            encoding="utf-8",
        )
        parsed = registered_labels(looped)
        ok(not parsed.layer1, "a looped audit() yields no inferred count", str(parsed.layer1))
        ok(
            parsed.unaccounted == ["alpha", "beta"],
            "and every label it lost is reported unaccounted",
            str(parsed.unaccounted),
        )

        report = Report()
        check_registry(report, [], looped)
        row = {check: (severity, findings) for check, severity, findings, _ in report.checks}
        severity, findings = row.get("check count", ("", []))
        ok(
            severity == ADVISORY and len(findings) == 1,
            "the count row asks instead of blocking, and compares nothing",
            str(row.get("check count")),
        )
    counts = claimed_counts("Fourteen checks, all deterministic. **Exit 1 blocks**")
    ok(counts == [(1, "Fourteen", 14)], "a spelled-out count is read", str(counts))
    counts = claimed_counts("Threshold checks and pricing rules run directly against it.")
    ok(not counts, "D8's prose is not a claim about this script", str(counts))

    print("\na check named by position is reported, per subset")
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "fake.md"
        # Built with an f-string on purpose: written as a literal, this line would be a
        # finding against this file. Same trick, same reason, as the code pattern that
        # scripts/githooks/pre-commit assembles from parts.
        doc.write_text(f"the orphan rule is check {10} here\n", encoding="utf-8")
        report = Report()
        check_registry(report, [doc])
        rows = {check: (severity, findings) for check, severity, findings, _ in report.checks}
        ok(
            len(rows.get("check numbering", ("", []))[1]) == 1,
            "a positional reference in a doc is reported",
            str(rows.get("check numbering")),
        )
        count_row = rows.get("check count", ("", ["no count row at all"]))
        ok(not count_row[1], "the count row stays clean", str(count_row))
        ok(
            rows.get("numbering in code", ("", []))[0] == ADVISORY,
            "the code row is advisory, and the doc row is not",
            str([(check, severity) for check, severity, _, _ in report.checks]),
        )

        doc.write_text("the repo-map check owns the orphan rule\n", encoding="utf-8")
        report = Report()
        check_registry(report, [doc])
        _, _, findings, _ = report.checks[1]
        ok(not findings, "naming the check by its label is fine", str(findings))

    print("\n" + "=" * 72)
    if failures:
        print(f"{len(failures)} self-test {'failure' if len(failures) == 1 else 'failures'}")
        return 1
    print("self-test clean")
    return 0


# ------------------------------------------------------------------------------ main


def audit(staged_only: bool) -> Report:
    report = Report()
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
    check_decision_ids(report, docs)
    check_env_vars(report, docs, allowed)
    check_current_gate(report)
    check_map(report, allowed)
    check_status_sources(report)
    check_registry(report, docs)
    if staged_only:
        check_coupling(report)
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
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
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    report = audit(staged_only=args.staged)
    print(report.render())
    mechanical, advisory = report.counts()
    if mechanical:
        return 1
    if advisory:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
