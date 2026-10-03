"""Environment variables, hatches, the repo map, hooks and build order."""

from __future__ import annotations

import ast
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .core import (
    ADVISORY,
    Finding,
    MECHANICAL,
    PACKAGE_DIR,
    ROOT,
    Report,
    Row,
    SELF,
    _GATES_STEP_SLUG,
    _NUMBER_WORDS,
    _merge_rows,
    _walk,
    child_names,
    code_haystack,
    exists,
    gates_text,
    literals_from_module,
    markdown_files,
    nested_worktrees,
    python_files,
    read,
    registered_tests,
    rel,
)
from .paths_commands import PROPOSED_SIGIL, ignored_paths, marked_proposed
from .records import (
    _DECISION_RE,
    _ENV_RE,
    decision_files,
    decision_heading_lines_across,
    without_noqa,
)

# `duplicated measurements` is CUT (test-audit plan Q2, 2026-09-28). It reconciled
# copies of three hand-taken measurements (cid lookup latency, the store card total,
# the largest drawer size) scattered across store/, cli/, server/, pipeline/, app/src/,
# CLAUDE.md and docs/map.py against EACH OTHER, never against a live re-measurement.
# The scattered copies are left as each site's own local documentation; a full
# de-duplication across that many product files is a separate, larger pass.



# `work item standing` is CUT (test-audit plan Q2, 2026-09-28). It reconciled
# CLAUDE.md's pointer at docs/specs/order-pipeline.md against that spec's own §3
# headings. Read the spec directly instead of a copy here.
# `router certainty` is CUT (test-audit plan Q2, 2026-09-28). It reconciled
# docs/specs/order-pipeline.md's published split against harness T7's own assertion.

# `not-built endpoints` is CUT (test-audit plan Q2, 2026-09-28). It reconciled
# server/order_transport.py's WHAT IS DELIBERATELY NOT BUILT block against a quoted
# copy in docs/specs/order-pipeline.md, which now points at the module instead.
# `transport standing` is CUT (test-audit plan Q2, 2026-09-28). It reconciled which
# order-transport calls server/order_transport.py's STATUS block marks proven against
# claims in docs/map.py, docs/specs/order-pipeline.md and CLAUDE.md.


def _env_vars(docs: List[Path], allowed: Dict[str, str]) -> Row:
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
    return Row("env vars", MECHANICAL, findings, f"{len(seen)} documented, all real",
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


def _env_names() -> Row:
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
        # THE AUDITOR SORTS LAST when choosing which site to cite. It is a legitimate source —
        # it reads `PKMNSCAN_EXPORTS` — so excluding it would leave a hole exactly where a
        # checker is least watched. But it also NAMES variables in prose, including this
        # docstring, and citing a sentence that describes the problem instead of the code
        # that has it sends the reader to the wrong file.
        where = sorted(sites[name], key=lambda site: site.startswith((rel(SELF), rel(PACKAGE_DIR))))
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
    return Row(
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
# passing vacuously — `docs/debts/` spends a section on the difference between a green row
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
# static `.html` and `.css` drawing sheets, which are drawings of docs/DESIGN.md and
# deliberately not components, into demanding map entries. Per-entry is the only shape that
# lets `app/` declare what it is written in without deciding that for the rest of the tree —
# and a sheet directory stays uncovered by having no entry with a module list at all,
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
    looked at no file it contains — a check gone quiet, which docs/debts/ already names
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


# Files whose bytes are not prose. `cited_decisions` reads every mapped file looking for `D<n>`
# and a compressed image will eventually contain those three bytes by chance — icon-180.png
# "cited" D31 and icon-512.png "cited" D2 on the day they were added.
BINARY_SUFFIXES = frozenset({
    ".png", ".jpg", ".jpeg", ".webp", ".heic", ".gif", ".avif", ".pdf",
    ".ico", ".woff", ".woff2", ".ttf", ".otf", ".zip", ".sqlite", ".onnx",
})


# A PATH INDEX CITED NOTHING, AND THE ONE THERE WAS IS GONE. `PATH_INDEX_FILES` skipped the
# retired per-file prose pin, whose keys were decision FILENAMES. Its replacement,
# `scripts/ste-offenders.json`, keyed a decision entry by its tail and folded every decision id
# in a label (`scripts/ste_measure.py:list_key`, `fold`), so it held no id to skip, and the skip
# was deleted with its only member (D280). That list is itself CUT now (test-audit plan,
# 2026-09-27); `scripts/markdown-spelling-allow.json` keys the same way, through the same
# `list_key`, and needs no skip for the same reason.


def cited_decisions(path: Path) -> Set[str]:
    """Every decision id a file cites, suppressions excluded.

    THE THIRD SITE, and the one docs/debts/ got wrong. That entry judged this reader "not
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


def check_env_vocabulary(report: Report, docs: List[Path], allowed: Dict[str, str]) -> None:
    """`PKMNSCAN_*` names, both directions: documented => real, and real => documented.

    Merged from `env vars` and `env names` by M3 (test-audit-2026-09-27, L8, Q8 yes). Each
    sub-check below is unchanged; only the last line of each moved from `report.add` to
    `return Row`, so both directions still fail this one row exactly as they failed two.
    """
    merged = _merge_rows("env vocabulary", [
        _env_vars(docs, allowed),
        _env_names(),
    ])
    report.add("env vocabulary", merged.severity, merged.findings, merged.summary,
               scanned=merged.scanned)


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
            rel(Path(__file__).resolve()),
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


# -------------------------------------------------- subagent-model override, live vs forgotten

# The owner's global rule (~/Developer/claude-settings/CLAUDE.md, "roles-opus-override-guarded")
# names these two keys verbatim as the pair that raises the subagent worker-model cap above
# Sonnet: `CLAUDE_CODE_SUBAGENT_MODEL` to `opus`, `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` to `1`,
# written into a checkout's `.claude/settings.local.json` "on my word", removed "when the work
# is done". THERE IS NO CONSTANT IN THIS REPO TO POINT AN ALLOW-LIST AT — the rule that names
# these two strings lives one directory up, in a file this repo does not own, commit, or read
# as code. Naming them here, literally, is the nearest this file can come to
# `building-allow-list-is-the-constant` when the thing defining the constant is the harness
# itself and not this tree: an in-repo copy would still be a copy, so this comment is the
# citation instead, and a name change up there is a name this row has to be told about by hand.
_SUBAGENT_MODEL_KEY = "CLAUDE_CODE_SUBAGENT_MODEL"
_SUBAGENT_FORCE_KEY = "CLAUDE_CODE_SUBAGENT_MODEL_FORCE"
_SUBAGENT_OVERRIDE_KEYS = (_SUBAGENT_MODEL_KEY, _SUBAGENT_FORCE_KEY)

# THE LINE THIS ROW DRAWS. `hatch state` above cannot tell a one-shot hatch from a standing
# one because an environment variable carries no metadata about who set it or why — so it is
# ADVISORY, permanently, by argument rather than by oversight. A settings FILE is not an
# environment variable: it is a persistent artifact this repo can require to carry its own
# proof of currency, the way D178 requires a `+` marker to be a claim WITH AN EXPIRY rather
# than a bare assertion. So the override is legitimate exactly when it names the moment it
# stops being current, and this is the sibling key that states it — a top-level key of the same file
# (the parent's `roles-override-carries-expiry` key), beside the `env` block that holds the two keys it governs.
_SUBAGENT_UNTIL_KEY = "_subagentCapUntil"

# Opus-shaped work is the parent rule's own phrase for what earns this override:
# "long-horizon, whole-codebase, or many-hour autonomous work" — hours, named as hours, never
# days. An expiry further out than this reads as a standing exemption wearing a timestamp,
# which is the exact shape D178's own entry rejected an allowlist line for ("meant to be
# unresolvable FOREVER" is a different claim from "not yet"). THIS NUMBER IS A JUDGEMENT, NOT
# A MEASUREMENT, and it is the one part of this row the owner may want to move — say so in the
# same commit that moves it, on `outcomes-stale-decision-protocol`'s own terms.
_SUBAGENT_OVERRIDE_MAX_LOOKAHEAD = timedelta(hours=24)

# The two filenames Claude Code actually writes under `.claude/`. Not a bare `settings*.json`
# glob: D178's own lesson about a broken path applies in reverse here — a loose glob would
# also match a future `settings.local.json.bak` or an editor swap file and report a stranger's
# JSON as this repo's problem. Named one at a time, never by a glob.
_SUBAGENT_SETTINGS_NAMES = ("settings.json", "settings.local.json")


def _parse_subagent_until(value: object) -> Optional[datetime]:
    """`_subagentCapUntil`'s value as an aware UTC datetime, or None.

    `None` covers both "absent" and "present but unreadable" on purpose — the caller reports
    them differently, but this function's only job is "can this be trusted as a clock
    reading," and a string that does not parse trusts exactly as much as no string at all.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _subagent_override_findings(
    settings_paths: Sequence[Path],
    now: Optional[datetime] = None,
) -> List[Finding]:
    """The pure half of `check_subagent_override`: given real settings files, name every
    live override that cannot prove it is current.

    TAKES PATHS AND A CLOCK AS ARGUMENTS rather than reading `ROOT`, `nested_worktrees()` or
    `datetime.now()` itself, on this file's own `--self-test` reasoning (see `_TCG_IMPORT_PATH`
    and its neighbours) — so `scripts/subagent-override-selftest.py` can hand it a fixture
    file list and a fixed instant instead of a real clock racing a real filesystem.

    READS THE DISK DIRECTLY, NEVER THROUGH `exists()`/`read()`. Those two honor `--staged`
    mode by redirecting to the git INDEX, which is correct for markdown claims about committed
    code and actively wrong here: `.claude/settings.local.json` and `.claude/worktrees/` are
    both gitignored (D135's own tracking note), so they are NEVER in the index, in ANY mode,
    by design. Reading them through the staged-mode helpers would make this row report "found
    nothing" on every single commit — the one place this defect actually has to be caught,
    since the file that sat forgotten for hours was never going to be staged either. This is
    `check_hatch_state`'s own choice, applied to a file instead of `os.environ`: that row reads
    live environment variables directly for the same reason.

    A file that does not exist, is not valid JSON, or has no `env` object is silently passed —
    each of those is empty of an override, not evidence of one, and an unparsable
    `.claude/settings.json` is `hatch state`'s finding to report, not this row's to repeat.
    """
    now = now or datetime.now(timezone.utc)
    findings: List[Finding] = []
    for path in settings_paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except ValueError:
            continue
        if not isinstance(data, dict):
            continue
        env = data.get("env")
        if not isinstance(env, dict):
            continue
        present = {key: env[key] for key in _SUBAGENT_OVERRIDE_KEYS if key in env}
        if not present:
            continue

        where = rel(path)
        detail = ", ".join(f"{key}={value!r}" for key, value in present.items())

        if path.name == "settings.json":
            # TRACKED. Every clone and every CI run inherits this, forever, with no
            # session's word behind it and no removal step anyone will ever run — the
            # opposite of "on my word... removed when the work is done." No expiry
            # excuses this; the file it belongs in is the untracked one beside it.
            findings.append(Finding(
                where,
                f"its `env` block sets {detail}. This file is TRACKED, so this raises the "
                f"subagent cap for every session that ever checks this repo out, committed "
                f"to git. The owner's rule puts this override only in the untracked "
                f"`settings.local.json` beside it — move it there, or drop it.",
            ))
            continue

        until_raw = data.get(_SUBAGENT_UNTIL_KEY)
        until = _parse_subagent_until(until_raw)
        if until_raw is None:
            findings.append(Finding(
                where,
                f"its `env` block sets {detail} with no top-level `{_SUBAGENT_UNTIL_KEY}`.\n"
                f"  An override with no stated expiry cannot be told apart from a forgotten "
                f"one — which is exactly what sat here for hours on 2026-09-19. State when "
                f"it stops being current (an ISO-8601 UTC timestamp), or remove the file.",
            ))
            continue
        if until is None:
            findings.append(Finding(
                where,
                f"its `{_SUBAGENT_UNTIL_KEY}` is {until_raw!r}, which does not read as an "
                f"ISO-8601 timestamp. Treated the same as no expiry at all: it proves "
                f"nothing about when this stops being current.",
            ))
            continue
        if until <= now:
            findings.append(Finding(
                where,
                f"its `env` block sets {detail}; `{_SUBAGENT_UNTIL_KEY}` was "
                f"{until.isoformat()}, which is in the past. The task this was for is over "
                f"and the file was not removed. Remove it, or set a new expiry with a fresh "
                f"reason.",
            ))
            continue
        if until - now > _SUBAGENT_OVERRIDE_MAX_LOOKAHEAD:
            findings.append(Finding(
                where,
                f"its `env` block sets {detail}; `{_SUBAGENT_UNTIL_KEY}` is "
                f"{until.isoformat()}, more than {_SUBAGENT_OVERRIDE_MAX_LOOKAHEAD} away. "
                f"Opus-shaped work is hours, not days — an expiry this far out reads as a "
                f"standing exemption, not one task's own end.",
            ))
            continue
        # Present, dated, ahead of `now`, inside the lookahead ceiling: set on purpose,
        # right now. Quiet — the whole argument for building this instead of a bare
        # forbid, and the reason it is MECHANICAL rather than ADVISORY like `hatch state`:
        # this row can actually tell current from forgotten, so it does not have to ask.

    return findings


def _subagent_settings_candidates() -> List[Path]:
    """Every settings file this checkout can see: its own two, and one apiece for every
    nested git worktree `nested_worktrees()` finds — CHECKING WHETHER THE PRIMITIVE ALREADY
    EXISTS FIRST, this repo's own standing instruction. `nested_worktrees()` already asks git
    for the exact case this row exists to catch (`.claude/worktrees/<name>/`, "the case that
    was actually observed breaking a commit," in its own docstring) and, unlike a name-based
    glob, also finds a worktree made by hand anywhere else under this tree — which is exactly
    the gap a root-only reader has and this row is built not to.
    """
    roots = (ROOT,) + nested_worktrees()
    return [root / ".claude" / name for root in roots for name in _SUBAGENT_SETTINGS_NAMES]


def check_subagent_override(report: Report) -> None:
    """A subagent-model override that outlived the work it was for, wherever it is sitting.

    THE INCIDENT. 2026-09-19: a session raised the subagent cap by writing
    `CLAUDE_CODE_SUBAGENT_MODEL=opus` and `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` into a
    checkout's `.claude/settings.local.json`. The owner's rule allows that only on their
    explicit word, and requires the file be removed when the work is done — it was not, and
    it sat for hours in `.claude/worktrees/<name>/`, a worktree nobody was standing in, found
    only because a different hook kept complaining about something else. `hatch state` above
    reads `.claude/settings.json` and the live environment; neither is this file, and neither
    looks inside a nested worktree. THE SECOND HALF OF THE RULE — "removed when the work is
    done" — had no reader anywhere in this repo until this row.

    THE DESIGN QUESTION, ARGUED RATHER THAN ASSUMED. Setting the override is legitimate
    while an Opus-shaped task is actually running (`roles-opus-shaped-say-so`), so a row that
    simply forbade it would be exactly the `verification-cry-wolf-guard-is-spent` guard this
    repo already rules against: a session doing exactly what the owner's word authorized
    would sit red until it hand-removed the file, learn to expect this row to be noise, and
    stop reading it the day it means something. The whole task here was drawing the line
    between "set on purpose, right now" and "forgotten" — three candidates, one taken:

    REJECTED: an escape hatch, `PKMNSCAN_<NAME>=off` in the shape every other clause in this
    repo's shell guard carries. That pattern is deliberately not spelled out as a real name
    here — inventing one would make `env names` demand it be documented as if it existed.
    Every clause in this repo's shell guard carries one, but a hatch answers "should this row
    run at all," never "is what it would find still true." Typing the hatch is a second thing
    to forget alongside removing the file — it does not shrink the forgetting surface, it
    doubles it, and a hatch left standing is `hatch state`'s own defect one level up.

    REJECTED: refusing only on the commit path. `.claude/settings.local.json` and
    `.claude/worktrees/` are BOTH gitignored (D135's tracking note, and see `SKIP_DIRS`
    above) — they can never be staged, so a check gated to "about to be committed" would never
    fire on the one artifact this whole task is about. The 2026-09-19 file was never going to
    reach a commit either; that is exactly why nothing caught it. This candidate does not
    narrow the guard's timing, it deletes its only reason to exist.

    TAKEN: a required, self-stated expiry, on D178's own idiom — "a marker that could be left
    on would turn every proposal into a permanent exemption," read here for a settings key
    instead of a `+` in a document. `_subagentCapUntil`, a top-level key beside the `env` block (the parent's key), alongside the override
    states when it stops being current; this row reads it, compares it to now, and stays quiet
    exactly while the stated window holds. A file with the override and no expiry, an expiry
    already past, an expiry that fails to parse, or an expiry so far out it reads as standing
    rather than task-shaped (`_SUBAGENT_OVERRIDE_MAX_LOOKAHEAD`) — each of those is what this
    row calls forgotten, and each is MECHANICAL rather than `hatch state`'s ADVISORY: unlike a
    bare environment variable, a dated settings key is a claim this row can actually check
    rather than merely ask about, so it does not have to hedge.

    WHAT THE OWNER IS BEING ASKED TO DECIDE. Whether the expiry-key convention is the right
    shape at all (a session must remember to write the additional key, not only the two the
    parent rule already names); whether 24 hours is the right ceiling for "Opus-shaped"; and
    whether this belongs beside `hatch state` as one row or stays separate, as built, because
    the two differ in exactly one way — one of them CAN tell current from forgotten and the
    other structurally cannot.

    D18 applies to this row the way it applies to every check in this file: it gates and it
    writes nothing. `scripts/subagent-override-selftest.py` proves it by violation — a nested
    worktree's own settings file with an undated, an expired and a too-far-dated override each
    made red and named, a currently-dated one made quiet, and a tree with no override at all
    made green — the way `guard-shell-selftest` proves each of its clauses.
    """
    candidates = _subagent_settings_candidates()
    findings = _subagent_override_findings(candidates)
    report.add(
        "subagent override",
        MECHANICAL,
        findings,
        f"{len(candidates)} settings files reachable from this checkout (its own and every "
        f"nested worktree's), none carrying an undated, expired, or too-far-dated override",
        scanned=len(candidates),
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
                findings.append(Finding(where, f"governed_by cites {name}, which has no heading in docs/decisions/."))

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
        # is the exception docs/debts/ records for `scripts/`: an entry with no module
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

    # THE GATE-STATUS RECONCILIATION IS RETIRED. It compared docs/map.py's `GATES` list against
    # the `### Gate X` headings of the Gate A/B/C run records, and those records were deleted
    # (the owner's ruling: old records are deleted and history lives in version control).
    # Nothing is left to reconcile against, so a row over `GATES` would only ever be red.

    # THE STEP-SET RECONCILIATION THAT LIVED HERE MOVED TO `build order mirror` (D80). It
    # scanned docs/GATES.md for `^\d+\.` across the WHOLE FILE, so any numbered list anywhere
    # in it joined the step set, and it knew nothing about which list a step was in — it
    # could not have told a shipped step from an open one, which is now half the claim. The
    # replacement reads the two headings and reconciles each separately, in both directions.

    report.add("repo map", MECHANICAL, findings, f"{claimed} entries match the tree",
               scanned=claimed)


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

    It stopped once. D42 added `reference-transaction` and `pre-push` and wrote both entries;
    two later hooks landed with no entry. Measured: five hooks on disk, three in the map.

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

#: Hooks only Codex runs, on the owner's word: the shared layer's guard (`claude-settings`
#: `hooks/guard.py`, rule 2) owns it for Claude Code, and Codex runs no shared guard.
#: Every other hook must be in both files. An entry here that Claude Code runs again, or that
#: Codex dropped, is a finding, so this list cannot go stale in either direction.
CODEX_ONLY = frozenset({
    ("PreToolUse", "Bash", "scripts/reap.py --hook"),
})

#: The value each file pins for `GUARD_SHELL_SKIP` on a `scripts/guard-shell.py` hook: Claude
#: Code's Bash entry skips the three clauses the shared layer owns, every other entry sets it
#: empty so an inherited value never narrows a guard. The triples below drop the prefix, so a
#: pin that drifts is its own finding, not a hook mismatch.
_SKIP_ENV = re.compile(r"^GUARD_SHELL_SKIP=(\S*)\s+")
CLAUDE_BASH_SKIP = "checkout,stash,reset"

#: The one hook Claude Code runs narrowed by an environment prefix, and Codex runs bare. The
#: row expects the prefix on the Claude entry and its absence on the Codex entry.
NARROWED_ENV = "PKMNSCAN_SILENT_WRITE_ONLY=file,bash-c "
NARROWED_HOOK = ("PreToolUse", "Bash", "scripts/silent-write-guard.py --hook")


def _hook_triples(data: object) -> Set[Tuple[str, str, str]]:
    """(event, matcher, command) out of a settings-shaped `hooks` block.

    Both files share one shape — `hooks.<Event> = [{matcher?, hooks: [{type, command}]}]` —
    because `.codex/hooks.json` was written by copying `.claude/settings.json`'s own block
    out of its wrapper (D135). `matcher` is absent on an event with no tool to match
    (`SessionStart`, `Stop`, `SessionEnd`, `WorktreeRemove`), so it is read as `""` rather
    than skipped — an event that gains a matcher in one file and not the other is exactly
    the drift this reads for, and a triple can only report that by carrying the field.

    The `GUARD_SHELL_SKIP` prefix is dropped for the same reason: the guard is the same
    hook with fewer clauses.

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
                    triples.add((str(event), str(matcher), _SKIP_ENV.sub("", command)))
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
    `WorktreeRemove` (added with the janitor sweep, claude-settings decisions/the-janitor-is-one-machine-wide-sweep.md, "The janitor is one machine-wide sweep") — `.codex/hooks.json` was written a day
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

    for label, data, path in (("claude", claude_data, ".claude/settings.json"),
                              ("codex", codex_data, ".codex/hooks.json")):
        for event, entries in (data.get("hooks") or {}).items():
            for entry in entries or []:
                matcher = entry.get("matcher") or ""
                for hook in entry.get("hooks") or []:
                    command = hook.get("command") or ""
                    if "scripts/guard-shell.py" not in command:
                        continue
                    found = _SKIP_ENV.match(command)
                    want = CLAUDE_BASH_SKIP if label == "claude" and matcher == "Bash" else ""
                    if not found or found.group(1) != want:
                        findings.append(
                            Finding(
                                path,
                                f"{event} (matcher `{matcher}`) must set "
                                f"`GUARD_SHELL_SKIP={want}` before guard-shell.py, got `{command}`.",
                            )
                        )

    # The narrowed hook: Claude's entry carries the prefix and Codex's carries none. Strip the
    # prefix from Claude's side after checking it, so the comparison below sees one hook.
    event, matcher, bare = NARROWED_HOOK
    narrowed = (event, matcher, NARROWED_ENV + bare)
    if narrowed in claude_triples:
        claude_triples = (claude_triples - {narrowed}) | {NARROWED_HOOK}
    elif NARROWED_HOOK in claude_triples:
        findings.append(Finding(".claude/settings.json",
                                f"runs `{bare}` without the `{NARROWED_ENV.strip()}` prefix. "
                                "Claude Code runs the file and bash-c clauses alone (D171)."))
    if narrowed in codex_triples:
        findings.append(Finding(".codex/hooks.json",
                                f"runs `{narrowed[2]}`. Codex runs the full hook, with no "
                                "prefix (D171)."))
        codex_triples = (codex_triples - {narrowed}) | {NARROWED_HOOK}

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
    for event, matcher, command in sorted(CODEX_ONLY - codex_triples):
        findings.append(
            Finding(
                ".codex/hooks.json",
                f"lost {describe(event, matcher, command)}, which CODEX_ONLY says only Codex "
                "runs. Codex has no shared guard, so restore it or drop it from CODEX_ONLY.",
            )
        )
    for event, matcher, command in sorted(CODEX_ONLY & claude_triples):
        findings.append(
            Finding(
                ".claude/settings.json",
                f"runs {describe(event, matcher, command)} again, so CODEX_ONLY is stale. "
                "Drop it from CODEX_ONLY, or drop it here (the shared layer owns it).",
            )
        )
    for event, matcher, command in sorted(codex_triples - claude_triples - CODEX_ONLY):
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
        f".codex/hooks.json, which also runs {len(CODEX_ONLY)} the shared layer owns for Claude Code",
        scanned=len(claude_triples),
    )


def check_map_sections(report: Report) -> None:
    """Every top-level section of docs/map.py is read by something, and the docstring's
    consumer list is true.

    **`TRACKS` is why this row exists.** It sat in that file from 2026-08-07 to 2026-08-31
    with no reader anywhere in the repo and no check over it, and it went wrong twice
    without anything being able to tell: it said `C1-C7` after the codes decisions file
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
# the shared merge tool rewrites both the marker and the token at merge time:
#
#   a `0.` marker, then the slug in backticks after the word `step`, then the title.
#
# D80's ruling that `n` is STABLE and never renumbered is untouched by this and is the reason
# for it: what that entry fears is D140's citation drift over 218 references to `step <n>`, and
# a number claimed at the merge cannot collide, so nothing is ever renumbered to resolve one.
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


# A NOTE ON DOCUMENTING THE SIGIL, because writing it down broke it once. `env vars` reads the
# scripts for a `PKMNSCAN_` token, so spelling a concrete example name in this file put that
# name in its own haystack — and every `+`-marked reference to it in a design document then
# failed as "the code reads it now". The examples above therefore name the PREFIX and stop.
# A mechanism whose documentation is inside its own subject has to be written for that.
