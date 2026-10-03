"""Paths, line anchors, make targets and the commands roster."""

from __future__ import annotations

import ast
import importlib.util
import io
import json
import re
import subprocess
import tokenize
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence, Set, Tuple

from .core import (
    ALLOWLIST,
    Finding,
    GAME_COVERAGE_ALLOWLIST,
    MECHANICAL,
    ROOT,
    Report,
    _check_recipe,
    _sibling,
    _walk,
    code_haystack,
    exists,
    read,
    registered_tests,
    rel,
    top_level_names,
)

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
# dispatcher does — `if path == "/pipeline/value":` in `server/capture_server`'s dispatcher, a JS
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


# ------------------------------------------------------------------- line anchors

# `path:N` and `path:N-M` — a citation naming a specific line or range inside a file, and
# `path_candidates` above cannot see the suffix at all: `:` is not in `_CANDIDATE_RE`'s
# character class, so a `docs/GATES.md` citation with a line suffix is extracted as the bare path `docs/GATES.md`
# and the `paths` row above reports "references resolve" having never read the suffix.
# The `line anchors` row further down refuses every one of them.
#
# A NEW EXTRACTOR, NOT A WIDENED `_CANDIDATE_RE`. Three call sites depend on
# `path_candidates` returning a list of plain strings, and folding a line-suffix onto that
# shape would either break them or bolt a second meaning onto the same return type. This
# reuses the same path-shaped character classes and the same three suppressions
# (`_ROUTE`, `_QUOTED_ROUTE`, `_PLACEHOLDER`) so a route or a placeholder is still not a
# path here either, and returns a distinct, richer type instead.
_LINE_ANCHOR_RE = re.compile(
    r"(?P<path>@?(?:\.\./)*[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]*):~?"
    r"(?P<start>[0-9]+)(?:[-–](?P<end>[0-9]+))?"
)


class LineAnchor(NamedTuple):
    """One `path:N` or `path:N-M` citation extracted from a line of prose. `end` is
    `None` for a single-line anchor."""

    path: str
    start: int
    end: Optional[int]


def line_anchor_candidates(line: str) -> List[LineAnchor]:
    """Extract `path:N` / `path:N-M` line-anchored citations from one line.

    Pure — no Report, no filesystem access — so `--self-test` can drive it directly, the
    same shape `unscoped_walk_sites` already uses and for the reason its own docstring
    gives: the return value is the thing under test, not a side effect two frames away.

    The path portion is not stripped or validated here — `resolve_candidate` already does
    that (the `@` and `../` handling), and duplicating it would be the second copy this
    file's own header warns against.
    """
    text = _ROUTE.sub(" ", line)
    text = _QUOTED_ROUTE.sub(" ", text)
    if _PLACEHOLDER.search(text):
        text = _PLACEHOLDER.sub(" ", text)
    out: List[LineAnchor] = []
    for match in _LINE_ANCHOR_RE.finditer(text):
        out.append(
            LineAnchor(
                match.group("path"),
                int(match.group("start")),
                int(match.group("end")) if match.group("end") else None,
            )
        )
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


_TS_SYMBOL_RE = re.compile(
    r"^(?:export\s+default\s+)?(?:export\s+)?(?:declare\s+)?(?:async\s+)?"
    r"(?:function\*?|class|interface|type|const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)"
)


def ts_symbols(path: Path) -> Set[str]:
    """Top-level TypeScript/TSX symbols, read statically — `module_attributes`'s own
    promise, one language over. Line-anchored regex, no parser, no `tsc`, no subprocess:
    this script does not run project code, the same reason it parses Python with `ast`
    instead of importing it.

    Recognises a top-level (column-0) `export function`, `function`, `export default
    function`, `const`/`let`/`var`, `class`, `interface` and `type` declaration, with or
    without `export`/`declare`/`async` in front. Column-0 only, on purpose — the same
    "top-level names" scope `module_attributes` keeps for Python, so a name nested inside
    a function body is not claimed as a module export just because this reader saw it.

    WHAT THIS CANNOT SEE, and it must not claim otherwise: a symbol built by a generic
    factory (`export const foo = makeThing()` is seen as the NAME `foo`, never what it
    resolves to); a re-export (`export { foo } from "./bar"` is invisible — it never
    starts with one of the keywords above); and a name assembled at runtime (a
    dynamically keyed object, a `Proxy`, `Object.assign(exports, {...})`). A hit here
    means the file's text names this symbol at column 0; a miss means only that this
    static reader could not find it, never that the symbol does not exist by some other
    construction.
    """
    if not exists(path):
        return set()
    names: Set[str] = set()
    for line in read(path).splitlines():
        if not line or line[0].isspace():
            continue
        match = _TS_SYMBOL_RE.match(line)
        if match:
            names.add(match.group(1))
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
        # BOTH ARE TRIED. The entries were one file at `docs/decisions/` until the split;
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
            attribute = suffix[1:]
            module = target.with_suffix(".py")
            if exists(module):
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

            # THE SAME FORM, FOR TYPESCRIPT. `.ts`/`.tsx` are already in KNOWN_SUFFIXES,
            # so `app/src/server.ts.walkPlan` reads its OWN final dot as the attribute
            # (`.walkPlan`) and `app/src/server.ts` as the module — this fallback used to
            # try only `.py` for that module, so every TS `module.attribute` citation fell
            # through to "does not exist" no matter how real the symbol was. `ts_symbols()`
            # is the durable-citation form's TS reader; see its own docstring for what a
            # static reader over TypeScript cannot see.
            #
            # STRIP, NEVER APPEND, WHEN THE MODULE ALREADY CARRIES ITS OWN `.ts`/`.tsx`.
            # `target.with_suffix(".ts")` on `app/src/server.ts.walkPlan` would REPLACE the
            # `.walkPlan` suffix with `.ts` and land on `server.ts.ts` — the bare form
            # (`target.with_suffix("")`) is the module whenever it already ends in `.ts` or
            # `.tsx`; only a module with no extension of its own (`app/src/server.walkPlan`)
            # needs one appended.
            bare = target.with_suffix("")
            ts_candidates = (
                [bare] if bare.suffix in (".ts", ".tsx")
                else [bare.with_suffix(".ts"), bare.with_suffix(".tsx")]
            )
            ts_module = next((candidate for candidate in ts_candidates if exists(candidate)), None)
            if ts_module is not None:
                if attribute in ts_symbols(ts_module):
                    continue
                findings.append(
                    Finding(
                        f"{rel(doc)}:{number}",
                        f"`{candidate}` — {rel(ts_module)} exists but defines no "
                        f"`{attribute}` this static reader can see (a factory-built, "
                        f"re-exported, or runtime-assembled name is invisible to it — "
                        f"see `ts_symbols()`'s own docstring).",
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


def load_game_coverage_allowlist() -> Dict[str, str]:
    """`game key / rarity` pairs `game coverage` may not ask about, one `pair  # reason`
    per line, same self-cleaning shape as `docs-audit-allow.txt`: an entry the row would
    no longer ask about anyway is stale and fails. See `check_game_coverage_allowlist`.
    """
    if not exists(GAME_COVERAGE_ALLOWLIST):
        return {}
    entries: Dict[str, str] = {}
    for line in read(GAME_COVERAGE_ALLOWLIST).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        pair, _, reason = stripped.partition("#")
        entries[pair.strip()] = reason.strip()
    return entries


_IDENTIFIER_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_TEST_ID_RE = re.compile(r"^T[1-9][0-9]?$")


def is_identifier_entry(entry: str) -> bool:
    """An ALL_CAPS entry is an env var or a test id, not a path."""
    return bool(_IDENTIFIER_RE.match(entry))


def check_allowlist(report: Report, allowed: Dict[str, str]) -> None:
    """Self-cleaning: an entry that has come true is stale and must go.

    An allowlist that only ever grows becomes a list of things nobody has looked at since.

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


# --------------------------------------------------------------------- line anchors

# ONE ROW, ONE RULE: NO DOCUMENT AND NO CODE COMMENT CITES A LINE NUMBER. D245 (a citation names a
# symbol, not a line), its amendment, and the owner's ruling of 2026-09-28. The row refuses three
# shapes, in every tracked markdown file and in the COMMENTS of every tracked code file:
#   1. `dir/file.ext:N` and `:N-M` (the extractor `line_anchor_candidates`, above);
#   2. `file.ext:N`, no directory (`_BARE_FILE_ANCHOR_RE`);
#   3. a bare `:N` or `:N-M` in a paragraph (a comment block) that has already named a file
#      (`_FRAGMENT_RE`), which is how a spec writes "`store/db.py` ... at line 1279" in the older, refused form.
# NOT ANCHORS, and proved so by `--self-test`: a time (`10:30`), a ratio (`3:1`), a slice
# (`x[:5]`), a format spec (`{:5d}`), `host:port` (a word before the colon), and a port a
# paragraph names bare (`_is_served_port`, read from `server/ports.py`). A CSS pseudo-selector is not a
# digit run. Code scope is by file type: `#` comments in .py, `//` and block comments in
# .ts/.tsx/.js/.mjs, block comments alone in .css. THERE IS NO EXEMPTION LIST. A record that must
# quote a line writes it in words ("line 182, column 81"). The fix for a refusal is a symbol
# (`module.symbol`, no `.py`; "`module.Class`'s `method`" for a method; a CSS selector), a
# section heading or a decision id.
_ANCHOR_EXTS = r"(?:py|ts|tsx|css|md|mjs|js|json|toml|yml|yaml|sh|html)"
_BARE_FILE_ANCHOR_RE = re.compile(
    r"(?<![\w/.@-])(?P<path>[A-Za-z0-9_-][A-Za-z0-9_.-]*\." + _ANCHOR_EXTS + r"):~?"
    r"(?P<start>[0-9]+)(?:[-–](?P<end>[0-9]+))?(?![\w:])"
)
_FILE_TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]*\." + _ANCHOR_EXTS + r"\b")
_FRAGMENT_RE = re.compile(
    r"(?<![\w:/.)\]\[{-])(?<!\d):(?P<start>[0-9]+)(?:-(?P<end>[0-9]+))?(?![\w:])"
)


@lru_cache(maxsize=None)
def _is_served_port(number: int) -> bool:
    """A bare `:N` that names a port this repo serves, read from `server/ports.py` (the constants
    the code emits, never a copy). Unreadable means no port is exempt: the row fails loud."""
    try:
        spec = importlib.util.spec_from_file_location("_ports_for_audit", ROOT / "server" / "ports.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return number in (mod.CAPTURE_BASE_PORT, mod.DEV_BASE_PORT) or any(
            low <= number < low + mod.SLOTS for low in (mod.CAPTURE_LOW, mod.DEV_LOW)
        )
    except Exception:
        return False

# An APPROXIMATE anchor: `~7199` or `~7199–7232`, three digits or more, which either ends a clause
# (`)`, `,`, `;`, `:`, `.`, `|` or the line) after a cited file, or follows the word "line" or
# "lines". "~5 ms", "~30 worktrees" and "~2x" read as a quantity and are not anchors.
_TILDE_RE = re.compile(r"(?<![\w~:])~(?P<start>[0-9]+)(?:[-–](?P<end>[0-9]+))?(?![\w%]|[.,][0-9])")
_TILDE_TAIL_RE = re.compile(r"\s*(?:[)\]`;:,.|]|$)")
_LINE_WORD_RE = re.compile(r"\blines?\s*\(?$")
_CODE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".mjs", ".css")


def code_files() -> List[Path]:
    return _walk(ROOT, _CODE_SUFFIXES)


def comment_units(path: Path, text: str) -> List[Tuple[int, Optional[str]]]:
    """`(line number, comment or docstring text or None)` per line of a code file. `None` is a line
    with none, which ends a paragraph. Scope by file type: comments, plus Python docstrings, plus
    every string in `docs/map.py`."""
    lines = text.splitlines()
    found: Dict[int, str] = {}
    if path.suffix == ".py":
        try:
            for tok in tokenize.generate_tokens(io.StringIO(text).readline):
                if tok.type == tokenize.COMMENT:
                    found[tok.start[0]] = tok.string
        except (tokenize.TokenError, IndentationError, SyntaxError):
            pass
        # DOCSTRINGS ARE PROSE: every module, class and function docstring, line by line. In
        # `docs/map.py` (the repo as data) every string constant is prose, so all are read.
        try:
            tree = ast.parse(text)
        except SyntaxError:
            tree = None
        if tree is not None:
            spans: List[ast.Constant] = []
            if path.name == "map.py" and path.parent.name == "docs":
                spans = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            else:
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                        body = node.body
                        if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                                and isinstance(body[0].value.value, str)):
                            spans.append(body[0].value)
            rows = {
                row
                for const in spans
                for row in range(const.lineno, (const.end_lineno or const.lineno) + 1)
            }
            for row in rows:
                found[row] = found.get(row, "") + " " + lines[row - 1]
    else:
        pattern = r"/\*.*?\*/" if path.suffix == ".css" else r"/\*.*?\*/|(?<!:)//[^\n]*"
        for m in re.finditer(pattern, text, re.S):
            first = text.count("\n", 0, m.start())
            for offset, piece in enumerate(m.group(0).split("\n")):
                found[first + offset + 1] = found.get(first + offset + 1, "") + " " + piece
    return [(n, found.get(n)) for n in range(1, len(lines) + 1)]


def anchor_hits_in_units(
    units: Sequence[Tuple[int, Optional[str]]], doc: Path, tops: Set[str]
) -> List[Tuple[Path, int, str]]:
    """Every line anchor in `units`, all three shapes. Pure over its arguments plus `tops`."""
    hits: List[Tuple[Path, int, str]] = []
    cited = False
    for number, text in units:
        if text is None or not text.strip():
            cited = False
            continue
        for anchor in line_anchor_candidates(text):
            target = resolve_candidate(anchor.path, doc, tops)
            if target is None or rel(target).split("/")[0] == ".git":
                continue
            hit = f"{anchor.path}:{anchor.start}"
            hits.append((doc, number, hit + (f"-{anchor.end}" if anchor.end is not None else "")))
        clean = _ROUTE.sub(" ", text)
        clean = _QUOTED_ROUTE.sub(" ", clean)
        clean = _PLACEHOLDER.sub(" ", clean)
        for m in _BARE_FILE_ANCHOR_RE.finditer(clean):
            hits.append((doc, number, m.group(0)))
        if _FILE_TOKEN_RE.search(clean):
            cited = True
        for m in _TILDE_RE.finditer(clean):
            after_line_word = _LINE_WORD_RE.search(clean[: m.start()]) is not None
            clause_end = len(m.group("start")) >= 3 and _TILDE_TAIL_RE.match(clean[m.end():])
            if after_line_word or (cited and clause_end):
                hits.append((doc, number, m.group(0)))
        if cited:
            for m in _FRAGMENT_RE.finditer(clean):
                if not _is_served_port(int(m.group("start"))):
                    hits.append((doc, number, m.group(0)))
    return hits


def line_anchor_hits(docs: Sequence[Path], code: Sequence[Path] = ()) -> List[Tuple[Path, int, str]]:
    """`(file, line number, anchor text)` for every line anchor in `docs` (markdown, whole text)
    and in the comments of `code`. Pure over its arguments plus the real repo's
    `top_level_names()`, so `--self-test` can drive it."""
    tops = top_level_names()
    hits: List[Tuple[Path, int, str]] = []
    for doc in docs:
        units = list(enumerate(read(doc).splitlines(), start=1))
        hits += anchor_hits_in_units(units, doc, tops)
    for path in code:
        text = read(path)
        # A file whose raw text holds none of the four shapes has no hit in its comments
        # either; skipping it keeps the row cheap, because tokenizing 440 files is not.
        if not (_LINE_ANCHOR_RE.search(text) or _BARE_FILE_ANCHOR_RE.search(text)
                or _FRAGMENT_RE.search(text) or _TILDE_RE.search(text)):
            continue
        hits += anchor_hits_in_units(comment_units(path, text), path, tops)
    return hits


def check_line_anchors(report: Report, docs: Sequence[Path], code: Sequence[Path] = ()) -> None:
    """No document in `docs` and no comment in `code` may cite a line number. Tier 1."""
    findings = [
        Finding(
            f"{rel(doc)}:{number}",
            f"`{text}` cites a line number, and a line number rots on the next edit above it. "
            "Cite a symbol (`module.symbol`, no `.py`), a section or a decision id instead.",
        )
        for doc, number, text in line_anchor_hits(docs, code)
    ]
    report.add(
        "line anchors", MECHANICAL, findings,
        f"{len(docs)} documents and {len(code)} code files read, no line anchor",
        scanned=len(docs) + len(code),
    )


# `derived numbers` is CUT (test-audit plan Q2, 2026-09-28). It reconciled a
# `<!-- derived:<name> -->`-marked figure in prose against `scripts/derived_numbers.py`.
# The markers and the numbers beside them are deleted from CLAUDE.md instead.


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


# A word that makes "make" the MAIN VERB of a sentence, right before it: an infinitive
# marker or a modal. No real command is ever written "to make X" or "will make X" — a
# command is always the bare word "make" followed by its target, nothing in front of it
# that could take "make" as a verb. This is the ONE thing that disqualifies a match; every
# other position in a span is fair game (a leading `(`, a shell verb like `time`, a quote,
# an ellipsis, "with" — none of them make "make" a verb, so none of them needs its own rule).
_MAKE_VERB_LEAD_WORDS = {
    "to", "will", "can", "could", "would", "should", "might", "must", "shall", "may",
}
_TRAILING_WORD = re.compile(r"[A-Za-z']+$")


def _reads_as_a_command(span: str, start: int) -> bool:
    """Is the `make <word>` at `start` in `span` a command, or an English sentence's verb?

    Everything in a backtick span counts unless the single word right before `start` is one
    of `_MAKE_VERB_LEAD_WORDS`. That is the whole rule (test-audit plan S4, amended after
    review): an owner's prose quote in backticks, `"We just need to make capping..."`, is
    excluded because "to" sits right before "make" — never because the span holds a quote,
    which `` `zsh -c '… make server 2>&1 | tail -20'` `` also does and must still be read.
    """
    prefix = span[:start].rstrip()
    if not prefix:
        return True
    word = _TRAILING_WORD.search(prefix)
    return not (word and word.group(0).lower() in _MAKE_VERB_LEAD_WORDS)


def make_target_refs(text: str):
    """Yield (line number, span, match) for every `make <target>` reference `check_make_
    targets` treats as real (test-audit plan S4, amended after review).

    ANYWHERE in a FENCED block, unchanged — CLAUDE.md's Commands block is one big fence, and
    a target's own description on the same line legitimately names another one in backticks
    (`` `make design-check` asserts... ``), which is not a span out here to require anything
    of.

    ANYWHERE in a backtick SPAN too, outside a fence — see `_reads_as_a_command` for the one
    exclusion. A `+make <name>` proposed reference still resolves: nothing in `_MAKE_VERB_
    LEAD_WORDS` matches a bare `+`, so the sigil is read exactly as before, and
    `marked_proposed` still finds it immediately in front of the match. Two adjacent spans on
    one line are two independent references, each judged on its own text, so
    `` `docs/GATES.md` `` beside `` `make icloud-sweep` `` still finds the second and not a
    target named `docs`. Real references this reads that the first cut of S4 missed:
    `` `Bash(make check)` ``, `` `time make harness` ``, `` `zsh -c '… make server …'` `` and
    `` `Rebuild it with make demo.` `` (quoted screen copy, D248, D305, and the review's own
    copy sheets).
    """
    fenced = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            for match in _MAKE_REF_RE.finditer(line):
                yield number, line, match
            continue
        for span in re.findall(r"`([^`]+)`", line):
            for match in _MAKE_REF_RE.finditer(span):
                if _reads_as_a_command(span, match.start()):
                    yield number, span, match


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
        for number, line, match in make_target_refs(read(doc)):
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
    # is invisible to anyone who did not read the Makefile. `help:`'s own recipe is one
    # line calling scripts/make-help.py (2026-09-27, token-budget audit Q1), so the render
    # is what this reads now, not the recipe's own (now empty) body — importing the sibling
    # rather than reimplementing its comment-association logic a second time.
    help_module = _sibling("make-help.py")
    if help_module is None:
        findings.append(Finding("scripts/make-help.py", "does not import — cannot check "
                                 "`make help`'s own coverage of every target."))
    else:
        try:
            help_body = help_module.render(text)
        except Exception as exc:  # noqa: BLE001 - a broken renderer must not take this row down
            help_body = ""
            findings.append(Finding("scripts/make-help.py",
                                     f"render() raised: {exc}"))
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


# --------------------------------------------------------------- commands roster

COMMANDS_INTERNAL = ROOT / "scripts" / "commands-internal.json"

_COMMANDS_BLOCK_RE = re.compile(r"## Commands\n\n```\n(.*?)\n```", re.S)
_COMMANDS_NAME_RE = re.compile(r"^make ([a-zA-Z0-9_-]+)", re.M)


def _commands_named(text: str) -> Set[str]:
    """Every `make <name>` CLAUDE.md's Commands section documents as its own bullet."""
    match = _COMMANDS_BLOCK_RE.search(text)
    if not match:
        return set()
    return set(_COMMANDS_NAME_RE.findall(match.group(1)))


def _commands_roster_findings(
    targets: Set[str], named: Set[str], check_members: Set[str], allow: Dict[str, str]
) -> List[Finding]:
    """The comparison itself, pure so `--self-test` can drive it without a filesystem."""
    findings: List[Finding] = []
    documented = named | check_members
    for name in sorted(targets - documented - set(allow)):
        findings.append(Finding(
            "Makefile",
            f"target `{name}` is named neither as a `make {name}` bullet in CLAUDE.md's "
            f"Commands section, inside `make check`'s own recipe, nor in "
            f"{rel(COMMANDS_INTERNAL)}. Document it, wire it into `make check`, or add it "
            f"to the allow-list with a reason.",
        ))
    for name in sorted(allow):
        if name not in targets:
            findings.append(Finding(rel(COMMANDS_INTERNAL),
                                     f"lists `{name}`, which is not a real Makefile target."))
        elif name in documented:
            findings.append(Finding(rel(COMMANDS_INTERNAL),
                                     f"lists `{name}`, which CLAUDE.md already documents. "
                                     f"Stale entry — the list only shrinks."))
    for name in sorted(named - targets):
        findings.append(Finding("CLAUDE.md",
                                 f"documents `make {name}`, which is not a real Makefile "
                                 f"target."))
    return findings


def check_commands_roster(report: Report) -> None:
    """CLAUDE.md's Commands section against the real Makefile targets, both ways.

    On `check census`'s own precedent (token-budget audit, 2026-09-27, Q1): two published
    lists reconciled against a real recipe, not against each other. CLAUDE.md's Commands
    section was cut to name plus one short line plus flags, on the owner's ruling, and a
    shrunk section is exactly the shape that goes silently stale — a target renamed or
    retired leaves a dead bullet, and a target ADDED leaves nothing telling a reader it
    exists.

    A TARGET IS "DOCUMENTED" THREE WAYS, not one. Its own `make <name>` bullet in the
    Commands section. Named inside `make check`'s own recipe (read from the Makefile, via
    `_check_recipe()` — the same authority `check census` already trusts, never a second
    copy of it) — a target `make check` runs is findable from `make explain`, so a bullet
    here would only restate what running `check` already shows. Or named in
    `scripts/commands-internal.json`, a SHRINKING allow-list, file -> reason, for a target
    that is neither: a one-off dev tool, a generator, or a self-test with no caller outside
    its own guard. This mirrors `serve scope`/`guard scope`'s roster shape rather than
    inventing a fourth one.

    BOTH WAYS: a real target reaching none of the three fails, naming what it is missing
    from. An allow-list entry for a target that is now documented, or that no longer
    exists, fails too — the list only shrinks. A CLAUDE.md bullet for a target that is not
    real fails (this is also `make targets`'s business; reporting it here as well costs
    nothing over two small sets).
    """
    makefile = ROOT / "Makefile"
    claude = ROOT / "CLAUDE.md"
    if not exists(makefile) or not exists(claude):
        report.add("commands roster", MECHANICAL,
                   [Finding("Makefile", "cannot read the Makefile or CLAUDE.md.")])
        return

    targets = set(_MAKE_RULE_RE.findall(read(makefile))) - {"help"}
    named = _commands_named(read(claude))
    check_members = set(_check_recipe() or []) & targets

    findings: List[Finding] = []
    allow: Dict[str, str] = {}
    if exists(COMMANDS_INTERNAL):
        try:
            allow = json.loads(read(COMMANDS_INTERNAL))
        except Exception as exc:  # noqa: BLE001 - a broken allow-list must not hide every finding
            findings.append(Finding(rel(COMMANDS_INTERNAL), f"does not parse as JSON: {exc}"))
    else:
        findings.append(Finding(rel(COMMANDS_INTERNAL), "does not exist."))

    findings += _commands_roster_findings(targets, named, check_members, allow)

    report.add("commands roster", MECHANICAL, findings,
               f"{len(targets)} targets, {len(named)} bulleted, {len(check_members)} via "
               f"`make check`, {len(allow)} allow-listed",
               scanned=len(targets))


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
