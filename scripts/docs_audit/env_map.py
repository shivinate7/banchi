"""Environment variables, hatches, the git and Claude hooks, and the build order."""

from __future__ import annotations

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
    _merge_rows,
    _walk,
    child_names,
    code_haystack,
    exists,
    gates_steps,
    gates_text,
    markdown_files,
    nested_worktrees,
    python_files,
    read,
    rel,
)
from .paths_commands import PROPOSED_SIGIL, marked_proposed
from .registry_scopes import _tracked_paths
from .records import _ENV_RE

# How a hook command names the project root. `:-.` keeps a session that does not set it at cwd.
PROJECT_DIR_PREFIX = "${CLAUDE_PROJECT_DIR:-.}/"

# `duplicated measurements` is CUT (test-audit plan Q2, 2026-09-28). It reconciled
# copies of three hand-taken measurements (cid lookup latency, the store card total,
# the largest drawer size) scattered across store/, cli/, server/, pipeline/, app/src/,
# CLAUDE.md against EACH OTHER, never against a live re-measurement.
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
# claims in docs/specs/order-pipeline.md and CLAUDE.md.


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
# roster is the one place this repo keeps growing extensionless files, and `BANCHI_SIGIL` —
# printed in every refusal the sigil check makes — lives in exactly such a file.
def _env_sites() -> Dict[str, List[str]]:
    """`BANCHI_*` and friends named outside markdown, mapped to where they are named.

    Only tracked files are read: an ignored file (`.claude/settings.local.json`) is one
    machine's override, so a variable named only there is not the repo's vocabulary.
    """
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
    tracked = _tracked_paths()  # empty without a repo (a no-git copy): read everything
    for path in sources:
        if tracked and rel(path) not in tracked:
            continue
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
    `BANCHI_SIGIL` is the bypass the sigil check PRINTS IN EVERY REFUSAL, so the one
    sentence a blocked commit reads names a variable no document explains. `BANCHI_T1_SPLIT`
    chooses which half of the eval corpus T1 scores; `BANCHI_TCG_ORDERS_URL` points the
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
        # it reads `BANCHI_EXPORTS` — so excluding it would leave a hole exactly where a
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

#: The shape of a hatch's VALUE. Every one of them is `<NAME>=off`, printed in the refusal
#: it lifts, so "set to something" is not the question — "set to off" is.
_HATCH_OFF = "off"


def check_env_vocabulary(report: Report, docs: List[Path], allowed: Dict[str, str]) -> None:
    """`BANCHI_*` names, both directions: documented => real, and real => documented.

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

    **THE PUREST FORM OF THE DEFECT THIS FILE IS ABOUT.** `BANCHI_DOCS=off` exported in a
    shell profile, a launchd plist, a wrapper or a CI environment kills one of the only two
    checks on the commit path in every session, forever — and every refusal message it
    would have printed is never printed, because no refusal ever happens. Every row in this
    file is void in that state, and nothing in the tree could report it. Same for
    `BANCHI_SIGIL`, whose guard runs in the same hook, and for `BANCHI_MAIN`, which is
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
            "and printing nothing in every session since. Check `env | grep BANCHI`.",
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

    REJECTED: an escape hatch, `BANCHI_<NAME>=off` in the shape every other clause in this
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


_HOOK_LINE = re.compile(r"^- `(scripts/githooks/[^`]+)` — ", re.M)


def _hooks_in_map() -> Set[str]:
    """The `scripts/githooks/<file>` names that a docs/map/ page has a map line for."""
    listed: Set[str] = set()
    for page in sorted((ROOT / "docs" / "map").glob("*.md")):
        listed.update(name.rsplit("/", 1)[1] for name in _HOOK_LINE.findall(read(page)))
    return listed


def check_hook_roster(report: Report) -> None:
    """Every file in `scripts/githooks/` has a map line in docs/map/.

    THE SHARED MAP CHECK DOES NOT COVER THIS DIRECTORY: a git hook is extensionless by git's
    requirement, and `map.config.json` lists code files by extension. So the hooks are listed
    BY HAND, and a list kept by hand is a list that stops being kept.

    It stopped once. D42 added `reference-transaction` and `pre-push` and wrote both lines;
    two later hooks landed with no line. Measured: five hooks on disk, three in the map.

    **This is the narrowest possible reader of that hole**, and deliberately not a widening of
    the extension list to admit extensionless files, which would conscript `views.txt` and a
    stray `README` into demanding entries. One directory's roster, checked against one
    directory's entries.

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

    listed = _hooks_in_map()
    on_disk = sorted(child_names(hooks))
    findings: List[Finding] = []
    for hook in on_disk:
        if hook not in listed:
            findings.append(
                Finding(
                    f"scripts/githooks/{hook}",
                    f"runs on the commit path and has no map line in docs/map/.\n"
                    f"  Add `- `scripts/githooks/{hook}` — <what it does>` to docs/map/scripts.md, "
                    f"and a decisions line under it. The shared map check (`make map-check`) cannot "
                    f"see an extensionless file, so this row is the only thing that will.",
                )
            )
    for hook in sorted(listed - set(on_disk)):
        findings.append(
            Finding(
                "docs/map/scripts.md",
                f"`scripts/githooks/{hook}` has a map line but no file. A roster kept by hand "
                f"goes stale in both directions; this is the half that describes a hook that "
                f"has left.",
            )
        )
    report.add(
        "hook roster",
        MECHANICAL,
        findings,
        f"{len(on_disk)} hooks, all with a map line in docs/map/",
        scanned=len(on_disk),
    )


# --------------------------------------------------------------------- claude hooks

CLAUDE_SETTINGS = ROOT / ".claude" / "settings.json"

_ENV_WORD = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

#: The one hook Claude Code runs narrowed by an environment prefix: the file and bash-c clauses
#: alone (D171). The row expects the prefix on the entry.
NARROWED_ENV = "BANCHI_SILENT_WRITE_ONLY=file,bash-c "
NARROWED_HOOK = ("PreToolUse", "Bash", "scripts/silent-write-guard.py --hook")


def _hook_triples(data: object) -> Set[Tuple[str, str, str]]:
    """(event, matcher, command) out of a settings-shaped `hooks` block.

    `hooks.<Event> = [{matcher?, hooks: [{type, command}]}]`. `matcher` is absent on an event
    with no tool to match (`SessionStart`, `Stop`, `SessionEnd`, `WorktreeRemove`), so it is read
    as `""` rather than skipped. `timeout` is not part of the triple: it changes how patient a hook is,
    not which hooks fire.
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


def check_claude_hooks(report: Report) -> None:
    """`.claude/settings.json`'s `hooks` block runs the hooks it should, each naming a real file.

    TWO CLAIMS, EACH ONE A SILENT FAILURE WHEN WRONG. A hook whose script was renamed or
    deleted does not error, it never runs. The silent-write hook that lost its
    `BANCHI_SILENT_WRITE_ONLY` prefix runs the clauses the shared layer already owns (D171).
    """
    findings: List[Finding] = []
    if not exists(CLAUDE_SETTINGS):
        report.add(
            "claude hooks",
            MECHANICAL,
            [Finding(".claude/settings.json", "does not exist; no hook is armed for Claude Code.")],
            "",
        )
        return
    try:
        claude_data = json.loads(read(CLAUDE_SETTINGS))
    except json.JSONDecodeError as exc:
        report.add(
            "claude hooks",
            MECHANICAL,
            [Finding(".claude/settings.json", f"does not parse as JSON: {exc}")],
            "",
        )
        return

    claude_triples = _hook_triples(claude_data)

    # The silent-write hook carries its prefix exactly. Any other spelling of it runs clauses the
    # shared layer already owns (D171).
    event, matcher, bare = NARROWED_HOOK
    narrowed = (event, matcher, NARROWED_ENV + bare)
    for triple in sorted(claude_triples):
        if bare in triple[2] and triple != narrowed:
            findings.append(Finding(".claude/settings.json",
                                    f"runs `{triple[2]}`; it must run `{narrowed[2]}`. "
                                    "Claude Code runs the file and bash-c clauses alone (D171)."))

    for event, _matcher, command in sorted(claude_triples):
        # Leading `NAME=value` words, and an `env` before them, are environment, not the script.
        words = [w for w in command.split() if not _ENV_WORD.match(w)]
        if words[:1] == ["env"]:
            words = words[1:]
        script = words[0].strip('"') if words else ""
        # A hook that must not resolve against the session's cwd names its project root
        # (worktree-create.sh: a tree cut before the script existed had no copy).
        script = script.removeprefix(PROJECT_DIR_PREFIX)
        if script and not exists(ROOT / script):
            findings.append(
                Finding(
                    script,
                    f"the {event} hook names `{command}` and no such file exists in the tree.",
                )
            )

    report.add(
        "claude hooks",
        MECHANICAL,
        findings,
        f"{len(claude_triples)} hooks in .claude/settings.json, each naming a file in the tree",
        scanned=len(claude_triples),
    )


# ------------------------------------------------- the build order against its own source

# The numbered lists under `## What shipped` and `## What is open` in the gates corpus, which
# `docs/gates/ORDER.json`'s step lists mirror. Each is bounded at the next `## ` so a numbered
# list anywhere else in the corpus cannot join in.
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
    """`docs/gates/ORDER.json`'s two step lists are the corpus's own two lists, in both directions.

    The build order is kept twice: the manifest's `steps.shipped` and `steps.open` (which
    `scripts/status.py` reads) and the numbered lines the step files put under `## What shipped`
    and `## What is open` in the corpus text. Two places that must agree, only one of which moves
    when a step file is moved, is this repo's recurring failure class (D80).

    **Ids, and which list they are in. Deliberately not the titles or the prose.** What must be
    identical is the id set per list, because the list a step is in IS its status.
    """
    text = gates_text()
    if not text:
        report.add("build order mirror", MECHANICAL,
                   [Finding("docs/gates/", "the corpus read as empty or unreadable.")])
        return

    findings: List[Finding] = []
    total = 0
    for name, heading in (("shipped", "What shipped"), ("open", "What is open")):
        mine = set()
        for step_id in gates_steps(name):
            number = re.match(r"step0*(\d+)", step_id)
            mine.add(int(number.group(1)) if number else step_id)
        start = re.search(r"^##\s+" + re.escape(heading) + r"\s*$", text, re.M)
        if start is None:
            findings.append(Finding(
                "docs/gates/",
                f"has no `## {heading}` heading, so the manifest's `{name}` list is reconciled "
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
                "docs/gates/ORDER.json",
                f"the corpus lists step {number} under `{heading}`; the manifest's `steps.{name}` "
                f"has no such id.",
            ))
        for number in sorted(mine - listed, key=str):
            findings.append(Finding(
                "docs/gates/",
                f"the manifest's `steps.{name}` has step {number}; `## {heading}` does not list it.",
            ))

    report.add("build order mirror", MECHANICAL, findings,
               f"{total} steps, the same ids in the manifest and the corpus, in the same two lists",
               scanned=total)


# A NOTE ON DOCUMENTING THE SIGIL, because writing it down broke it once. `env vars` reads the
# scripts for a `BANCHI_` token, so spelling a concrete example name in this file put that
# name in its own haystack — and every `+`-marked reference to it in a design document then
# failed as "the code reads it now". The examples above therefore name the PREFIX and stop.
# A mechanism whose documentation is inside its own subject has to be written for that.
