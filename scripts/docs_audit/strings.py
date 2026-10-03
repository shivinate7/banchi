"""Screen strings: mechanism words, typed interpunct, offender lists and views opsec."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .core import (
    ADVISORY,
    Finding,
    MECHANICAL,
    ROOT,
    Report,
    VIEWS_EXPOSURE_ENABLED,
    _MERGE_BASE_REFERENCE,
    _sibling,
    exists,
    read,
    rel,
)
from .games import game_entries
from .screens import (
    APP_ORIGINS,
    APP_TSX,
    VIEWS_MANIFEST,
    _OFF_RENDER_RE,
    _photo_reach,
    _pooled_exclusion_evidence,
    _render_manifest_findings,
    _routes_table,
)

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

# THE ONE PLACE THIS LIST LIVES IS scripts/machine-words.json, not a Python dict, since D196's
# 2026-09-23 amendment (D284) put a SECOND reader on it: `app/tests/
# machine-words.spec.ts` reads the rendered TEXT every route draws, catching server- and
# demo-composed strings this AST walk cannot (it only sees JSX literals). One file, so growing
# the list edits one dictionary rather than two that can drift apart. `run`, `box`, `export`,
# `listing` and `TCGplayer` are deliberately NOT in it — they are the operator's own words,
# the ones `docs/DESIGN.md`'s Register section and every screen in CLAUDE.md's table are
# written in, and banning them would be the opposite defect.
MACHINE_WORDS_JSON = ROOT / "scripts" / "machine-words.json"


@lru_cache(maxsize=1)
def _machine_words() -> Dict[str, object]:
    return json.loads(MACHINE_WORDS_JSON.read_text(encoding="utf-8"))


NO_MECHANISM_WORDS: Dict[str, str] = _machine_words()["words"]


def _word_pattern(word: str) -> str:
    """A bare identifier-shaped word (`emit`, `sub-threshold`) is wrapped in `\\b`, so it
    matches the word itself and not a substring of a longer one (`emitted`, `unstaged`,
    `reindex`). A phrase with a space, or a path-shaped entry carrying a `/`, is left as a
    plain literal exactly as the original hand-typed dict was — `\\b` either side of a `/`
    checks the wrong transition (word/non-word, not `/`/word) and would refuse to match at
    the very position the entry exists to catch."""
    if re.fullmatch(r"[\w-]+", word):
        return r"\b" + re.escape(word) + r"\b"
    return re.escape(word)


_NO_MECHANISM_RE = re.compile(
    "|".join(_word_pattern(w) for w in NO_MECHANISM_WORDS), re.I
)

# A repository path, never something a person types or reads off a download. Every
# top-level package `docs/map.py` maps, plus `scripts` (where this row itself lives): any
# of them followed by `/` is a filesystem fact about this checkout, not a sentence about a
# card. `docs/decisions/` is covered by the bare `docs` prefix, deliberately — a path INTO
# it is exactly the citation-by-path `cite-decisions-by-id-not-path` already warns against.
# SAME SOURCE `scripts/machine-words.json`'s `repoTopDirs` HOLDS, so the browser-side check
# (`machine-words.spec.ts`, which flags a rendered request-path shape with the identical top
# dirs) cannot drift from this one — a second hand-typed tuple here is exactly the drift this
# file's own header warns against.
_REPO_TOP_DIRS = tuple(_machine_words()["repoTopDirs"])
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
# key for `Pricing.tsx`'s "Run `pkmnscan rescue` to rebind it." — a backticked command
# is not a decision citation, not one of `_REPO_TOP_DIRS` followed by a slash, and not a
# `.json`/`.sqlite`/`.jsonl` filename, so it passed this row clean while naming this
# product's own CLI on screen. `pkmnscan` is the checkout's own name (CLAUDE.md's naming
# rule) and never a word an operator would use to describe what a press does; a subcommand
# beside it (`rescue`, `join`, `emit`, …) is exactly the mechanism this row exists to catch.
_CLI_INVOCATION_RE = re.compile(r"`?\bpkmnscan\b(?:\s+[\w.-]+)*`?", re.I)


UNKNOWN_NO_TOOLCHAIN = "unknown: app/node_modules missing, run make worktree-setup"


def _user_strings_toolchain_missing() -> bool:
    """True only when `node` or the app's own TypeScript is ABSENT (a read that could not run).

    Distinct from a toolchain that is present and broke (bad exit, timeout, bad JSON):
    `_run_user_strings` answers None for both, and only this one is "unknown", never a finding.
    """
    return shutil.which("node") is None or not APP_TS_COMPILER.exists()


def _add_toolchain_row(rows: Report, check: str, peers: str) -> None:
    """The `_run_user_strings` None branch: ADVISORY when absent, MECHANICAL when it broke."""
    if _user_strings_toolchain_missing():
        rows.add(check, ADVISORY, [Finding(rel(USER_STRINGS_SCRIPT), UNKNOWN_NO_TOOLCHAIN)],
                   "toolchain unavailable, so nothing was read", scanned=0)
        return
    rows.add(
        check, MECHANICAL,
        [Finding(rel(USER_STRINGS_SCRIPT),
                 "could not run — `node` and `app/node_modules/typescript` are present but "
                 f"`scripts/user-strings.mjs` failed (exit, timeout or unreadable output); {peers}")],
        "toolchain broke, so nothing was read", scanned=0,
    )


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

# A CASE-INSENSITIVE LOOKUP FROM THE MATCHED TEXT BACK TO ITS OWN ENTRY'S "why", built once
# rather than `.lower()`-ing `NO_MECHANISM_WORDS` at every call site. `NO_MECHANISM_WORDS`
# keeps entries in their own natural case (`Pushed`, `Staged` — proper-noun-shaped internal
# states) beside the original all-lowercase phrases (`the pipeline`), and `_NO_MECHANISM_RE`
# matches case-insensitively (`re.I`) either way, so the "why" lookup has to fold to the same
# case it folds the SEARCH to, or a capitalised entry's own explanation is silently empty —
# measured: before this map existed, a `Staged` hit printed no reason at all.
_WHY_BY_LOWER: Dict[str, str] = {word.lower(): why for word, why in NO_MECHANISM_WORDS.items()}


def _no_mechanism_exempt(where_file: str) -> bool:
    """Matched by basename, not by full path — this file is a leaf name (`Gallery.tsx`),
    never a directory, so a rename under a different parent still resolves correctly and a
    self-test fixture rooted anywhere still matches the same way the real `app/src` tree
    does."""
    return Path(where_file).name in NO_MECHANISM_EXEMPT_FILES


# THE SHRINKING OFFENDER LIST, on `scripts/kit-adoption-allow.json`'s own precedent and the
# owner's Q3 ruling, 2026-09-23: file -> word -> the lane that owes the fix. Growing
# `scripts/machine-words.json`'s word list (D284) put ten new pipeline nouns —
# `emit`, `sub-threshold`, `index`, `span`, `parked`, `Pushed`, `Staged`, `make demo`,
# `/pipeline/`, `manual:c` — in front of this row for the first time, and several of them are
# real, on screens no wave-2 lane has reached yet. A hard gate with no allow list would fail
# every one of THOSE lanes' branches for a defect this lane found and none of them caused.
# `check_no_mechanism_on_screen` fails on a hit this file does not list AND on a listed entry
# that no longer matches any hit — the second half is what keeps the list SHRINKING rather
# than becoming a second, quieter exemption.
MACHINE_WORDS_ALLOW_JSON = ROOT / "scripts" / "machine-words-allow.json"


@lru_cache(maxsize=1)
def _machine_words_allow() -> Dict[str, Dict[str, str]]:
    try:
        raw = json.loads(MACHINE_WORDS_ALLOW_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in raw.items() if k != "_about"}


# THE ONE NAMED EXCEPTION (D196, the owner's word): the matcher control's hover tooltip may name the
# model. The allowance is the constant the code emits, read from its file, never a copy of the text
# (an allow list that restates the string drifts from it). Absent file or constant: no allowance.
MODEL_NAME_CONSTANT_FILE = ROOT / "app" / "src" / "engines.ts"
MODEL_NAME_CONSTANT = "MATCHER_NAME_TOOLTIP"
_MODEL_NAME_CONSTANT_RE = re.compile(
    r"export\s+const\s+" + MODEL_NAME_CONSTANT + r"\s*(?::\s*string\s*)?=\s*(['\"`])(.*?)\1", re.S
)


def _model_name_exception(path: Path = MODEL_NAME_CONSTANT_FILE) -> Optional[str]:
    try:
        found = _MODEL_NAME_CONSTANT_RE.search(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    return found.group(2) if found else None


def _no_mechanism_findings(
    strings: List[Dict[str, object]],
    allow: Optional[Dict[str, Dict[str, str]]] = None,
    exception_text: Optional[str] = None,
) -> Tuple[List[Finding], Set[Tuple[str, str]]]:
    """Returns the findings, and the `(file, word)` allow-list entries a hit actually used —
    the second is how the caller tells a listed entry that is still true from one that has
    gone stale (nothing matches it any more) without a second pass over `strings`."""
    allow = allow or {}
    findings: List[Finding] = []
    used: Set[Tuple[str, str]] = set()
    for item in strings:
        file = str(item["file"])
        if _no_mechanism_exempt(file):
            continue
        text = str(item["text"])
        if exception_text is not None and text == exception_text:
            continue
        where = f"{item['file']}:{item['line']}"
        shown = text if len(text) <= 100 else text[:97] + "..."
        code_hit = (
            _DECISION_CITE_RE.search(text)
            or _REPO_PATH_RE.search(text)
            or _REPO_EXT_RE.search(text)
            or _CLI_INVOCATION_RE.search(text)
        )
        if code_hit is not None:
            # A decision citation or a repository path is never on the allow list — see
            # `machine-words-allow.json`'s own header: it exists for the WORD-LIST growth
            # only, never for the two checks this row has always run.
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
            canon = word_hit.group(0).lower()
            why = _WHY_BY_LOWER.get(canon, "")
            listed_lane = (allow.get(file) or {}).get(canon)
            if listed_lane is not None:
                used.add((file, canon))
                continue
            findings.append(
                Finding(
                    where,
                    f"says {word_hit.group(0)!r}: {shown!r}\n  {why}",
                )
            )
    return findings, used


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
    So the count this row prints is a FLOOR, the same word D177's prune measurement
    uses for its own undercount, and for the identical reason: what is missed
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

    Toolchain-missing is reported as an ADVISORY finding (`UNKNOWN_NO_TOOLCHAIN`) rather than
    a silent `scanned=0`: a read that could not run is unknown, never clear and never broken.
    A toolchain that is PRESENT and fails stays MECHANICAL (`_add_toolchain_row`).
    """
    strings = _run_user_strings([])
    if strings is None:
        _add_toolchain_row(report, "no mechanism on screen",
                           "this row needs the same toolchain `make lint` and `make typecheck` require.")
        return
    allow = _machine_words_allow()
    findings, used = _no_mechanism_findings(strings, allow, _model_name_exception())

    # STALE ENTRIES: an allow-listed (file, word) pair that matched nothing this run. The
    # lane that owns it already fixed the string, and the entry is the only thing left
    # naming a defect that is gone — `scripts/kit-adoption-allow.json`'s own `runtime allow
    # list names only real routes` self-test argues the identical point for its own list.
    for file, words in sorted(allow.items()):
        for word, lane in sorted(words.items()):
            if (file, word) not in used:
                findings.append(
                    Finding(
                        f"{rel(MACHINE_WORDS_ALLOW_JSON)}: {file} / {word!r}",
                        f"is allow-listed for lane {lane!r}, but nothing in {file} says "
                        f"{word!r} any more — the entry is stale. Delete it.",
                    )
                )

    report.add(
        "no mechanism on screen", MECHANICAL, findings,
        (
            f"{len(findings)} of {len(strings)} visible strings name a decision, a "
            "repository path, or pipeline machinery"
        ) if findings else (
            f"{len(strings)} visible strings carry none of it "
            f"({len(used)} allow-listed hit(s) over {sum(len(w) for w in allow.values())} "
            "entries, none stale)" if allow else f"{len(strings)} visible strings carry none of it"
        ),
        scanned=len(strings),
    )


def _offender_list_shape(data: object, rules: Optional[Set[str]] = None) -> Tuple[Dict[str, Dict[str, List[str]]], Dict[str, str], List[str]]:
    """`(files, lanes, errors)` from a list document's `files` block.

    `files` is file -> rule -> entries, `lanes` is file -> lane. A file entry must carry a
    non-empty `lane` and at least one rule. When `rules` is given, every rule key must be one
    of them, so an entry under a misspelt rule is refused rather than read as covering
    nothing."""
    errors: List[str] = []
    files: Dict[str, Dict[str, List[str]]] = {}
    lanes: Dict[str, str] = {}
    block = data.get("files") if isinstance(data, dict) else None
    if not isinstance(block, dict):
        return files, lanes, ["has no `files` object"]
    for file, entry in sorted(block.items()):
        if not isinstance(entry, dict):
            errors.append(f"{file}: is not an object")
            continue
        lane = entry.get("lane")
        if not isinstance(lane, str) or not lane.strip():
            errors.append(f"{file}: names no `lane` (the lane that owes the fix)")
        else:
            lanes[file] = lane
        per_rule: Dict[str, List[str]] = {}
        for rule, entries in entry.items():
            if rule == "lane":
                continue
            if rules is not None and rule not in rules:
                errors.append(f"{file}: `{rule}` is not a rule this row checks ({', '.join(sorted(rules))})")
                continue
            if not isinstance(entries, list) or not entries or not all(isinstance(e, str) for e in entries):
                errors.append(f"{file}: `{rule}` must be a non-empty list of strings")
                continue
            per_rule[rule] = list(entries)
        if not per_rule:
            errors.append(f"{file}: lists no offender. Delete the file's entry")
            continue
        files[file] = per_rule
    return files, lanes, errors


def _offender_diff(
    found: Dict[str, Dict[str, List[str]]],
    listed: Dict[str, Dict[str, List[str]]],
    key=lambda entry: entry,
) -> Tuple[List[Tuple[str, str, str]], List[Tuple[str, str, str]]]:
    """`(unlisted, stale)`, each a list of `(file, rule, entry)`.

    Compared per (file, rule) as a MULTISET of keys: an offender that occurs twice needs two
    entries, and the second occurrence of a listed offender is unlisted. Never a count per
    file: a new offender in a file that also lost an old one is still unlisted, and the old
    entry is still stale."""
    from collections import Counter

    unlisted: List[Tuple[str, str, str]] = []
    stale: List[Tuple[str, str, str]] = []
    for file in sorted(set(found) | set(listed)):
        for rule in sorted(set(found.get(file, {})) | set(listed.get(file, {}))):
            have = found.get(file, {}).get(rule, [])
            allowed = Counter(key(e) for e in listed.get(file, {}).get(rule, []))
            left = Counter(allowed)
            for entry in have:
                k = key(entry)
                if left[k] > 0:
                    left[k] -= 1
                else:
                    unlisted.append((file, rule, entry))
            spare = Counter(k for k, n in left.items() for _ in range(n))
            for entry in listed.get(file, {}).get(rule, []):
                k = key(entry)
                if spare[k] > 0:
                    spare[k] -= 1
                    stale.append((file, rule, entry))
    return unlisted, stale


def _only_shrinks():
    """`scripts/only_shrinks.py`, the ONE helper for every shrinking list's growth rules, or
    None. `scripts/kit-adoption.mjs` runs the same file as a command."""
    return _sibling("only_shrinks.py")


def _offender_growth(
    base: Dict[str, Dict[str, List[str]]],
    head: Dict[str, Dict[str, List[str]]],
    base_rules: Optional[Set[str]],
    head_rules: Optional[Set[str]],
    key=lambda entry: entry,
) -> Tuple[List[str], List[str]]:
    """`(refused, allowed)`, each a printable line: every (rule, identity) that occurs more
    often in the list at HEAD than in the list at the merge-base, across ALL files.

    THE RULES ARE `only_shrinks.growth`'s, never a copy: a rule born on this branch may list
    its first offenders, a rule set that cannot be read allows nothing, and a rule the
    merge-base defines that is missing at HEAD refuses all growth. This only turns each list
    into `(rule, identity)` pairs and formats the answer. With no helper, nothing is allowed."""
    def pairs(files: Dict[str, Dict[str, List[str]]]) -> List[Tuple[str, str]]:
        return [(rule, key(e)) for per in files.values() for rule, es in per.items() for e in es]

    helper = _only_shrinks()
    if helper is None:
        return (["scripts/only_shrinks.py could not be loaded, so no growth is allowed"]
                if pairs(head) else []), []
    refused, allowed = helper.growth(pairs(base), pairs(head), base_rules, head_rules)
    line = lambda g: f"{g.rule} {g.identity!r} (+{g.extra}): {g.why}"  # noqa: E731
    return [line(g) for g in refused], [line(g) for g in allowed]


def _offender_list_at_merge_base(relpath: str) -> Tuple[Optional[object], str]:
    """`(document, where)`: `only_shrinks.list_at_merge_base`, the list as it stood at the
    merge-base with `origin/main` and a short merge-base id. `(None, reason)` when there is
    none, and the reason says why, so the row fails open and prints it."""
    helper = _only_shrinks()
    if helper is None:
        return None, "scripts/only_shrinks.py could not be loaded"
    document, where, _, _ = helper.list_at_merge_base(relpath, ROOT, _MERGE_BASE_REFERENCE)
    return document, where


def _read_offender_list(path: Path) -> Tuple[Optional[object], Optional[str]]:
    """`(document, None)`, or `(None, why)` when the file is missing or is not JSON."""
    if not exists(path):
        return None, "does not exist"
    try:
        return json.loads(read(path)), None
    except (json.JSONDecodeError, ValueError) as exc:
        return None, f"is not JSON ({exc})"


# ------------------------------------------------------------- typed interpunct (D218)
#
# The owner's ruling, 2026-09-19: "this typed dot needs to be removed everywhere it exists."
# D41 deleted the dot-joined address string from the screen on 2026-08-29 and moved the
# separator into CSS (`.boxops-identity-part::before { content: '·' }` and its siblings) —
# the separator is a STYLE now, drawn beside a fact, never typed INTO one. D218 is the full
# argument. Its pinned count is retired (D280): the row now fails
# on every typed dot that `scripts/typed-interpunct-allow.json` does not name.

# U+00B7 MIDDLE DOT and U+2022 BULLET — the two characters the survey named. Kept as a fixed
# two-code-point class rather than a longer punctuation list on purpose: this row polices ONE
# typed separator shape, not general typography, and a longer list would need the same
# argument D196's own word list already carries for what does and does not belong on it.
_INTERPUNCT_RE = re.compile("[·•]")
_INTERPUNCT_NAME = {"·": "middle dot (U+00B7)", "•": "bullet (U+2022)"}

# THE TWO EXTRACTOR WIDENINGS THIS ROW OPTS INTO, AND NO OTHER ROW DOES. Kept as one constant
# so the row and its own self-test call `_run_user_strings` with the identical argument list —
# see `scripts/user-strings.mjs`'s header for what each flag does and why the no-mechanism-
# on-screen row above stays on the default (unflagged) extraction: widening ITS fixtures'
# behaviour retroactively over a different rule's citation would be exactly the silent-scope-
# creep D196's own exemption comment (`Notice`'s `code` prop, kept OFF by default) warns against.
TYPED_INTERPUNCT_EXTRACT_ARGS: Tuple[str, ...] = ("--join-literals", "--include-code-attr")

# THE ONE RULE THIS LIST CARRIES. A typed dot has no sub-rules, so the list's only rule key is
# this constant, and the row refuses any other key.
TYPED_INTERPUNCT_RULE = "interpunct"
TYPED_INTERPUNCT_ALLOW = ROOT / "scripts" / "typed-interpunct-allow.json"


def _typed_interpunct_hits(strings: List[Dict[str, object]]) -> List[Finding]:
    """One Finding per visible string carrying a typed middle dot or bullet.

    Every one, listed or not — `_typed_interpunct_found` groups them by file for the list
    comparison, and the row reports only the ones the list does not name. Kept as a separate
    function so the row's own `--self-test` fixtures can call it directly, the same split
    `_no_mechanism_findings` uses one section up.
    """
    hits: List[Finding] = []
    for item in strings:
        text = str(item["text"])
        match = _INTERPUNCT_RE.search(text)
        if match is None:
            continue
        where = f"{item['file']}:{item['line']}"
        shown = text if len(text) <= 100 else text[:97] + "..."
        hits.append(
            Finding(
                where,
                f"types a {_INTERPUNCT_NAME[match.group(0)]} where a person reads it: {shown!r}\n"
                "  D41 moved the position separator into CSS "
                "(`::before { content: '·' }`) — a screen may SHOW a separator, "
                "never TYPE one into a string.",
            )
        )
    return hits


def typed_interpunct_entry(item: Dict[str, object]) -> str:
    """One list entry: `"<scope>: <string>"`.

    THE SCOPE IS PART OF THE KEY, so one entry excuses one string in one named function
    (`scripts/user-strings.mjs:scopeOf`: the nearest function, class, arrow binding or
    module-level constant). Keyed by the string alone, a bare separator such as `·` excused
    that string ANYWHERE in the file: remove the listed `.join(' · ')` and type a new one in
    another component, and the row stayed green. A line number would pin the place more
    tightly, and would rot on the next edit above it."""
    return f"{item.get('scope') or '(module)'}: {item['text']}"


def typed_interpunct_growth_key(entry: str) -> str:
    """The key GROWTH is counted by: the string, without its scope.

    The scope stays in the unlisted and stale check (`typed_interpunct_entry`), so a dot
    moved to another function is still a new offender there. Growth drops it, so a function
    RENAME moves its entries the way a file rename does. Re-key the entries to the new name,
    and the row passes: the same strings, the same number of times, in the list. A scope is
    an identifier or `(module)`, so the first `: ` always ends it."""
    return entry.split(": ", 1)[1] if ": " in entry else entry


def _typed_interpunct_growth(
    base: Dict[str, Dict[str, List[str]]],
    head: Dict[str, Dict[str, List[str]]],
    rules: Set[str],
    renames: Sequence[Tuple[str, str]],
) -> Tuple[List[str], List[str]]:
    """`_offender_growth` for typed dots, counted PER FILE, by string without its scope.

    PER FILE, unlike the prose list. Counted over the whole list, a new dot passed in any
    file, a new file included, whenever a dot with the same string was fixed somewhere else:
    the second review's X1 and X2. A dot string is short and repeats across files, where a
    prose hash does not.

    A FILE RENAME STILL MOVES ITS ENTRIES. Each HEAD path is mapped to its merge-base path
    through git's rename pairs, `(old, new)` from `offenders-prune.py:git_renames` (a read, so
    D18 holds). A rename git does not see reads as a new file, and fails closed: its entries
    are growth until the rename is staged.

    The scope is dropped (`typed_interpunct_growth_key`), so a FUNCTION rename moves its
    entries too, once they are re-keyed to the new name."""
    to_base = {new: old for old, new in renames}

    def folded(files: Dict[str, Dict[str, List[str]]], mapped: bool) -> Dict[str, Dict[str, List[str]]]:
        out: Dict[str, Dict[str, List[str]]] = {}
        for file, per in files.items():
            where = to_base.get(file, file) if mapped else file
            for rule, entries in per.items():
                out.setdefault(where, {}).setdefault(rule, []).extend(
                    f"{where} :: {typed_interpunct_growth_key(e)}" for e in entries)
        return out

    return _offender_growth(folded(base, False), folded(head, True), rules, rules)


def _git_renames() -> List[Tuple[str, str]]:
    """git's rename pairs from the merge-base, read by `offenders-prune.py`'s own function."""
    prune = _sibling("offenders-prune.py")
    return prune.git_renames(ROOT, _MERGE_BASE_REFERENCE) if prune is not None else []


def _typed_interpunct_found(strings: List[Dict[str, object]]) -> Dict[str, Dict[str, List[str]]]:
    """file -> {TYPED_INTERPUNCT_RULE: [every offending entry, once per occurrence]}."""
    found: Dict[str, Dict[str, List[str]]] = {}
    for item in strings:
        if _INTERPUNCT_RE.search(str(item["text"])):
            found.setdefault(str(item["file"]), {}).setdefault(TYPED_INTERPUNCT_RULE, []).append(
                typed_interpunct_entry(item))
    return {file: {rule: sorted(texts) for rule, texts in per.items()} for file, per in found.items()}


def check_typed_interpunct(report: Report) -> None:
    """No user-visible string may TYPE a middle dot or bullet as a separator (D41's own
    ruling, generalised repo-wide 2026-09-19). See D218, and D280
    for the list that replaced its pinned count.

    THE EXTRACTION IS THE SAME AST WALK `no mechanism on screen` USES, `scripts/user-
    strings.mjs`, run with `TYPED_INTERPUNCT_EXTRACT_ARGS` — two widenings that row's own
    fixtures prove stay OFF by default: `--include-code-attr` (`Notice`'s own `code` prop,
    which DOES render) and `--join-literals` (the literal separator argument of any
    `<expr>.join(<literal>)` call, wherever the call's return value ends up).

    WHAT THIS STILL CANNOT SEE, and it is a real gap, not a filtered one: a helper that builds
    a separator WITHOUT `.join` and is interpolated by reference (`{formatThing(x)}`); CSS
    `content:` properties (this walks `.tsx` only); and server-side Python strings. D218 names
    each.

    A RULE, AND A SHRINKING LIST, NEVER A COUNT. Every typed dot is a finding unless
    `scripts/typed-interpunct-allow.json` names that exact string in that file and in that
    named function (`typed_interpunct_entry`), once per occurrence. A listed entry that matches nothing is a finding too (stale: delete it). An
    entry the list at the merge-base did not hold is refused (growth). See the section header.
    """
    strings = _run_user_strings(list(TYPED_INTERPUNCT_EXTRACT_ARGS))
    if strings is None:
        _add_toolchain_row(report, "typed interpunct",
                           "this row needs the same toolchain `no mechanism on screen` requires.")
        return

    hits = _typed_interpunct_hits(strings)
    found = _typed_interpunct_found(strings)
    allow_rel = rel(TYPED_INTERPUNCT_ALLOW)
    document, unreadable = _read_offender_list(TYPED_INTERPUNCT_ALLOW)
    if document is None:
        report.add(
            "typed interpunct", MECHANICAL,
            [Finding(allow_rel, f"{unreadable}, so no typed dot can be told listed from new "
                                f"({len(hits)} typed dots found). Restore the list from git.")],
            "no offender list", scanned=len(strings),
        )
        return
    rules = {TYPED_INTERPUNCT_RULE}
    listed, lanes, shape_errors = _offender_list_shape(document, rules)
    findings = [Finding(allow_rel, error) for error in shape_errors]

    unlisted, stale = _offender_diff(found, listed)
    for file, _rule, text in unlisted:
        lines = sorted({str(item["line"]) for item in strings
                        if str(item["file"]) == file and typed_interpunct_entry(item) == text},
                       key=int)
        findings.append(Finding(
            f"{file}:{lines[0]}" if len(lines) == 1 else file,
            f"types a dot where a person reads it, and {allow_rel} does not list it: {text!r}"
            + (f" (lines {', '.join(lines)})" if len(lines) > 1 else "")
            + "\n  Build the parts as elements and let CSS draw the separator (D41). Never add "
            "an entry to excuse a new dot."))
    for file, _rule, text in stale:
        findings.append(Finding(
            f"{allow_rel}: {file}",
            f"lists {text!r} for lane {lanes.get(file, '?')!r}, and {file} no longer types it. "
            "Delete the entry: the list only shrinks."))

    base_doc, where = _offender_list_at_merge_base(allow_rel)
    growth_note = ""
    if base_doc is None:
        growth_note = f" Only-shrinks not compared: {where}. Failing open."
    else:
        base_listed, _, _ = _offender_list_shape(base_doc, rules)
        refused, allowed = _typed_interpunct_growth(base_listed, listed, rules, _git_renames())
        for line in refused:
            findings.append(Finding(
                allow_rel, f"gained {line} over the merge-base {where}. Fix the string instead "
                           "of excusing it."))
        growth_note = f" Only-shrinks compared against the merge-base {where}."

    listed_count = sum(len(es) for per in listed.values() for es in per.values())
    by_lane: Dict[str, int] = {}
    for file, per in listed.items():
        by_lane[lanes.get(file, "?")] = by_lane.get(lanes.get(file, "?"), 0) + sum(len(es) for es in per.values())
    report.add(
        "typed interpunct", MECHANICAL, findings,
        (f"{len(hits)} typed dots; {listed_count} listed over {len(listed)} files ("
         + ", ".join(f"{lane} {n}" for lane, n in sorted(by_lane.items()))
         + f"); {len(unlisted)} unlisted, {len(stale)} stale.{growth_note}"),
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
    if VIEWS_EXPOSURE_ENABLED:
        report.add(
            "views exposure",
            ADVISORY,
            exposure,
            ("no pooled game in the registry — a stored photo is not a bearer instrument today"
             if not pooled
             else "no manifest view can draw a stored photo"),
            scanned=len(entries),
        )
    else:
        report.add(
            "views exposure",
            ADVISORY,
            [],
            "OFF — code cards are dormant (CLAUDE.md); re-enable VIEWS_EXPOSURE_ENABLED "
            "when code-card work resumes",
            scanned=0,
        )
