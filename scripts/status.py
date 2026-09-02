#!/usr/bin/env python3
"""`make status` — where the build is, derived from sources that are already audited.

Written for one case: you step away, forget where you were, come back and need to be
oriented without reading four files and running the harness.

NOTHING HERE IS A FACT ABOUT THE PROJECT. Every value is read at run time from a source
that something else already enforces — `docs/map.py` by the audit's repo-map check, the T1
score by the test that writes it, the branch by git. If the map says step 6, this says
step 6.
There is no second place to update, which is the whole reason this file is worth having
rather than a paragraph in a README that someone has to remember to edit.

Two failure modes, handled differently, because they are not the same thing:

  the VALUES going stale     impossible; they are re-read every run
  the READER going stale     possible, and the real risk. If `harness/results/` moves or a
                             key is renamed, this script cannot repair itself.

The second is why `SOURCES` below is declarative. The audit's status-sources check walks it
and fails the commit that breaks it, so a rename is caught the day it happens rather than
deleting a block from this output. A status tool that silently prints less is worse than
no status tool, because you will believe it.

Same rule for anything missing at run time: print `MISSING`, exit non-zero. Never omit a
block and never guess a substitute.

Stdlib only, no venv, no network, no API key — it has to work on a cold clone, since that
is close to the situation it exists for.

    scripts/status.py            print the status block
    scripts/status.py --sources  print SOURCES as JSON (what the audit reads)
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent

WIDTH = 76
LABEL = 15  # column where values start, so the left rail reads as a column


# Every file this script reads OR RUNS, declared in one place so the audit's status-sources
# check can verify it WITHOUT running it. Pure literals for the reason docs/map.py is: the
# audit parses with `ast.literal_eval` rather than importing, because a read-only check must
# not execute the code it is checking. A `Source` class here would be a Call node, unreadable
# to it.
#
# "or runs" is not padding. `scripts/docs-audit.py` is a subprocess, not a read, and it sat
# outside this list as a hardcoded path for exactly that reason — so a rename would have
# deleted the docs-audit line from this output with nothing failing anywhere. Declaring it
# costs one entry and buys the same tripwire every other path here gets.
#
# `kind` says what must be true of the target:
#   literals  a .py whose module-level literal assignments include every name in `requires`
#   defs      a .py whose module-level `def`s include every name in `requires`
#   json      a path or glob; every match must carry every key in `requires`
#   file/dir  presence only
#
# Resolve reads through `resolve()` below, so this list is not decoration — it is the only
# place a path is written down, and that check fails the commit that invalidates one.

SOURCES = (
    {
        "path": "docs/map.py",
        "kind": "literals",
        "requires": ("SHIPPED", "OPEN", "GATES", "COMPONENTS", "TRACKS"),
        "why": "what shipped and what is open, gate status, per-component governed_by, and the "
               "two tracks. TRACKS was added to this tuple on 2026-08-31 (D80): it had no reader "
               "anywhere and no check, and had been wrong in two ways for three weeks.",
    },
    {
        "path": "scripts/decision-context.py",
        "kind": "defs",
        "requires": ("decision_gists",),
        "why": "the lift of bolded rulings out of docs/DECISIONS.md — reused, never reimplemented",
    },
    {
        "path": "scripts/docs-audit.py",
        "kind": "defs",
        "requires": ("build_parser", "main"),
        "why": "the docs-audit health line, read from its `--json` and never from its render",
    },
    {
        "path": "harness/results/t1*.json",
        "kind": "json",
        "requires": (
            "gated_on",
            "accuracy_floor",
            "passed",
            "image_count",
            "model",
            "generated_at",
            "per_set",
            "splits",
            "set_hint_mode",
            "prompt_fingerprint",
            "finish_note",
        ),
        "why": "T1 scores, the gate criterion, and T1's own blind-spot note",
    },
    {
        "path": "docs/DECISIONS.md",
        "kind": "file",
        "requires": (),
        "why": "read by decision_gists()",
    },
    {
        "path": "scripts/icloud-sweep.py",
        "kind": "file",
        "requires": (),
        "why": "counts iCloud Drive conflict copies — run by icloud() below. Run rather than "
               "reimplemented, so the pattern that decides what a conflict copy IS lives in "
               "one file",
    },
    {
        "path": "scripts/serve.py",
        "kind": "defs",
        "requires": ("report", "live_pid"),
        "why": "whether the servers are actually up — `make up`'s supervisor, asked through "
               "its read-only report(). Declared here rather than reached by a hardcoded "
               "path so a rename fails the audit instead of silently deleting the SERVING "
               "block from this output",
    },
    {
        "path": "server/ports.py",
        "kind": "file",
        "requires": (),
        "why": "which ports THIS checkout serves on — imported by ports_and_store() below. "
               "Imported rather than ast-parsed because the answer is a function of where "
               "the checkout is, not a literal; stdlib-only, so it cannot need `make venv`",
    },
    {
        "path": "scripts/launch-config.py",
        "kind": "file",
        "requires": (),
        "why": "what the Browser pane will open — run with `--check` by ports_and_store() "
               "below. Run rather than imported because it is a CLI with three appetites "
               "and this is the read-only one; a missing file costs the line, not the run",
    },
    {
        "path": "scripts/githooks/*",
        "kind": "file",
        "requires": (),
        "why": "the tracked hooks `make hooks` installs — read by hooks() below. A glob "
               "since D42: the opsec pre-commit gained two siblings guarding main, and an "
               "entry naming one of three would report an armed clone while two were gone",
    },
    {
        "path": "inventory",
        "kind": "dir",
        "requires": (),
        "optional": True,
        "why": "the master store, once anything is captured",
    },
    {
        "path": "runs",
        "kind": "dir",
        "requires": (),
        "optional": True,
        "why": "per-run outputs, once identify has run",
    },
)


def resolve(pattern: str) -> List[Path]:
    """Paths for a declared source. Records a MISSING unless the entry is optional.

    Every read goes through here so `SOURCES` stays the single place a path is written.
    A hardcoded path elsewhere would be one the status-sources check does not know about —
    which is the drift this whole arrangement exists to prevent.
    """
    entry = next((s for s in SOURCES if s["path"] == pattern), None)
    if entry is None:  # a caller invented a path instead of declaring it
        miss(pattern, "not declared in SOURCES")
        return []
    if any(ch in pattern for ch in "*?["):
        parent, _, glob = pattern.rpartition("/")
        found = sorted((ROOT / parent).glob(glob)) if (ROOT / parent).is_dir() else []
    else:
        target = ROOT / pattern
        found = [target] if target.exists() else []
    if not found and not entry.get("optional"):
        miss(pattern, str(entry.get("why", "")))
    return found


# ------------------------------------------------------------------------ reading


class Missing(NamedTuple):
    what: str
    detail: str


MISSING: List[Missing] = []


def miss(what: str, detail: str = "") -> None:
    # Deduped: several sections read the same source, and one absent file is one problem,
    # not one problem per reader.
    if not any(item.what == what for item in MISSING):
        MISSING.append(Missing(what, detail))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def literals(path: Path) -> Dict[str, object]:
    """Module-level literal assignments, without importing — same access docs-audit uses."""
    out: Dict[str, object] = {}
    try:
        tree = ast.parse(read(path))
    except (OSError, SyntaxError) as exc:
        miss(str(path.relative_to(ROOT)), str(exc))
        return out
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


def load_gists() -> Dict[str, Tuple[str, List[str]]]:
    """Reuse scripts/decision-context.py rather than re-parsing docs/DECISIONS.md.

    One lift, one place to break — and the PreToolUse hook already exercises it on every
    edit, so it is the best-tested parser in the repo. The filename has a hyphen, hence
    importlib instead of a plain import.
    """
    found = resolve("scripts/decision-context.py")
    if not found:
        return {}
    path = found[0]
    try:
        spec = importlib.util.spec_from_file_location("decision_context", path)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module.decision_gists()
    except Exception as exc:  # noqa: BLE001 - a broken hook must not take status down
        miss("scripts/decision-context.py", f"decision_gists() failed: {exc}")
        return {}


def git(*args: str) -> Optional[str]:
    try:
        done = subprocess.run(
            ["git"] + list(args),
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def wrap(text: str, indent: int, width: int = WIDTH) -> List[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) + indent > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def field(label: str, value: str) -> str:
    return f"  {label:<{LABEL}}{value}"


def cont(value: str) -> str:
    return f"  {'':<{LABEL}}{value}"


# ------------------------------------------------------------------------ sections


def where_you_are(mapdata: Dict[str, object]) -> List[str]:
    """What has landed and what has not — never "step N of M".

    THAT HEADLINE WAS THE LIE THIS FUNCTION EXISTED TO TELL. It read `Build step 9 of 15`
    for a week while steps 13, 14 and 15 were done, step 9 had been deferred by choice, and
    six days of pricing, order and code-card work had landed under no step at all. The
    number was correct and the sentence was false, because `N of M` is a claim about a
    SEQUENCE and this was never one (D80). The map is two lists now and so is this.
    """
    shipped = mapdata.get("SHIPPED") or []
    open_steps = mapdata.get("OPEN") or []
    gates = mapdata.get("GATES") or []
    if not shipped and not open_steps:
        return [field("Shipped", "MISSING: docs/map.py SHIPPED / OPEN")]

    out: List[str] = []
    latest = max((str(step.get("on") or "") for step in shipped), default="")
    out.append(field("Shipped", f"{len(shipped)} steps, last on {latest or 'an unrecorded date'}"))
    for step in [s for s in shipped if str(s.get("on") or "") == latest][:2]:
        out.append(cont(f"{step.get('n')}. {step.get('title')}"))

    out.append(field("Open", f"{len(open_steps)} — unranked, and deliberately so"))
    for step in open_steps:
        out.extend(cont(line) for line in wrap(f"{step.get('n')}. {step.get('title')}", LABEL + 2))

    if gates:
        passed = [g for g in gates if g.get("status") == "passed"]
        out.append(field("Gates", "retired — {} passed: {}".format(
            len(passed), ", ".join(f"{g.get('gate')} {g.get('on')}" for g in passed))))
        out.append(cont("docs/GATES.md is the record of what was measured, not a"))
        out.append(cont("schedule."))
    return out


def do_this_next(mapdata: Dict[str, object], gists: Dict[str, Tuple[str, List[str]]]) -> List[str]:
    """Every open step, with what governs it. NOT one step, and not ranked.

    This used to read the single `next` the map was required to carry and present it as the
    answer. Both halves were wrong: the map's one-`next` rule forced a step to hold the flag
    whether or not anyone was working on it, and printing one item under `DO THIS NEXT` made
    a scheduling claim `status.py` has no standing to make. It lists what is open; which one
    matters today is the owner's (D80).
    """
    open_steps = mapdata.get("OPEN") or []
    if not open_steps:
        return [field("Nothing open", "every step in docs/map.py has shipped.")]

    out: List[str] = []
    for i, step in enumerate(open_steps):
        if i:
            out.append("")
        out.append(field(f"{step.get('n')}.", str(step.get("title"))))
        governed = sorted(set(re.findall(r"\bD[1-9][0-9]?\b", str(step.get("note") or ""))),
                          key=lambda d: int(d[1:]))
        for name in governed[:3]:
            title, _ = gists.get(name, ("(no such entry in docs/DECISIONS.md)", []))
            out.extend(cont(line) for line in wrap(f"{name}  {title}", LABEL + 2))
    out.append(field("Read first", "docs/GATES.md `What is open` · `make map`"))
    return out


def t1_blocks() -> List[str]:
    files = resolve("harness/results/t1*.json")
    if not files:
        return [field("T1", "MISSING: harness/results/t1*.json — no committed score")]

    out: List[str] = []
    for path in files:
        rel = str(path.relative_to(ROOT))
        try:
            data = json.loads(read(path))
        except (OSError, ValueError) as exc:
            miss(rel, str(exc))
            out.append(field("T1", f"MISSING: {rel} unreadable — {exc}"))
            continue

        gated_on = data.get("gated_on")
        key = f"{gated_on}_accuracy"
        if gated_on is None or key not in data:
            miss(rel, f"no `gated_on`, or no `{key}` to read")
            out.append(field("T1", f"MISSING: {rel} does not say which number gates it"))
            continue

        mode = data.get("set_hint_mode") or "?"
        label = "default" if mode == "none" else str(mode)
        floor = data.get("accuracy_floor")
        verdict = "PASS" if data.get("passed") else "FAIL"
        out.append(
            field(
                f"T1  [{label}]",
                f"{gated_on} {data[key]}  ≥  floor {floor}   {verdict}     (gated_on: {gated_on})",
            )
        )

        splits = data.get("splits") or {}
        parts = [f"{name} {body.get('accuracy')}" for name, body in sorted(splits.items()) if name != gated_on]
        if "overall_accuracy" in data:
            parts.append(f"overall {data['overall_accuracy']}")
        counts = " / ".join(f"{body.get('images')} {name}" for name, body in sorted(splits.items()))
        if counts:
            parts.append(f"{counts} / {data.get('image_count')} total")
        out.append(cont(" · ".join(parts)))

        fingerprint = str(data.get("prompt_fingerprint") or "?")[:8]
        out.append(cont(f"set_hint {mode} · prompt {fingerprint} · {data.get('model')}"))

        stamp = str(data.get("generated_at", "?")).replace("T", " ")[:16]
        per_set = {k: v.get("accuracy") for k, v in (data.get("per_set") or {}).items()}
        line = f"measured {stamp}"
        if per_set:
            worst = min(per_set.values())
            named = ", ".join(sorted(k for k, v in per_set.items() if v == worst))
            line += f" · weakest {worst} ({named})"
        out.append(cont(line))
    return out


# The auditor's `--json` vocabulary, the one thing this file consumes that is not a file.
# Named here because classifying a row means knowing what a severity string means, and a
# reader that guesses is the failure this module is arranged against.
AUDIT_ROW_KEYS = ("label", "severity", "findings")
AUDIT_BLOCKING = "mechanical"  # D16 layer 1: provably wrong, exits 1
AUDIT_ASKING = "advisory"      # D16 layer 2: a question, exits 2


def audit_line() -> List[str]:
    """Run the mechanical docs audit inline and read its `--json`, never its render.

    Stdlib, fast, and it never writes (D16). Nothing here gates: a red audit is health to
    report, not a source that could not be read, so `make status` still exits 0 on one.

    WHY THE MACHINE SURFACE. `b2d35ce` added `--json` for exactly this — "a machine
    surface, so nothing retires on a parsed render" — and `scripts/audit-history.py` has
    honoured it since, while this reader went on counting `  ok ` and `  FAIL ` prefixes
    out of a report written for a human. Both surfaces can drift. The difference is that
    renaming a key is a deliberate edit to something declared an interface, whereas
    rewording a heading is prose nobody thinks of as one — so the render breaks its
    consumers silently and by accident, which is the only kind of breakage that matters
    here. The alternative was tightening those two prefixes into stricter patterns; it
    keeps the coupling exactly as it was and only moves the day it bites.

    A payload this cannot read is a MISSING, loud and non-zero, never a confident count of
    zero — the module rule for a source that moved, applied to a surface that moved.
    """
    found = resolve("scripts/docs-audit.py")
    if not found:  # resolve() has already recorded why
        return [field("docs audit", "MISSING: scripts/docs-audit.py")]
    try:
        done = subprocess.run(
            [sys.executable, str(found[0]), "--json"],
            cwd=str(ROOT), capture_output=True, text=True, check=False,
        )
    except OSError as exc:
        return [field("docs audit", f"did not run — {exc}")]

    def unreadable(why: str) -> List[str]:
        miss("scripts/docs-audit.py", why)
        return [field("docs audit", f"MISSING: {why}")]

    # A dropped or renamed `--json` lands here: argparse writes usage to stderr, exits on
    # its usage code and leaves stdout empty. Its last stderr line names the flag it
    # rejected, which is the single fact needed to repair this call, so it is carried into
    # the message rather than thrown away.
    #
    # STDERR ONLY, never a fallback to stdout. A renamed payload key raises here with
    # stdout holding valid JSON, whose last line is `}` — measured, and it read as though
    # the auditor had said something. The exception already names the missing key; a tail
    # that adds nothing is worse than no tail, because it looks like evidence.
    try:
        payload = json.loads(done.stdout)
        rows, code = payload["rows"], payload["exit"]
    except (ValueError, KeyError, TypeError) as exc:
        tail = done.stderr.strip().splitlines()
        detail = f" — {tail[-1][:64]}" if tail else ""
        return unreadable(f"--json is not a rows/exit payload ({exc}){detail}")

    if not isinstance(rows, list) or not all(
        isinstance(row, dict) and all(key in row for key in AUDIT_ROW_KEYS) for row in rows
    ):
        return unreadable("--json rows are not " + "/".join(AUDIT_ROW_KEYS) + " records")

    # A severity this file has never heard of cannot be counted as either bucket, and
    # dropping it would under-report the audit — the exact silent shrinkage the module
    # docstring says is worse than no status tool. Adding a severity to the auditor is
    # therefore a change here too, announced by this line rather than discovered later.
    unknown = sorted({str(row["severity"]) for row in rows} - {AUDIT_BLOCKING, AUDIT_ASKING})
    if unknown:
        return unreadable(f"--json rows carry unclassifiable severity: {', '.join(unknown)}")

    clean = [row for row in rows if not row["findings"]]
    failing = [row for row in rows if row["findings"] and row["severity"] == AUDIT_BLOCKING]
    asking = [row for row in rows if row["findings"] and row["severity"] == AUDIT_ASKING]

    # `exit` and the rows come out of one run, so they cannot honestly disagree. If they
    # do, this reader is looking at a payload it does not understand and must say so —
    # picking whichever of the two it likes is how a wrong number gets printed confidently.
    if (not failing and not asking) != (code == 0):
        return unreadable(
            f"--json exit {code} disagrees with its own rows "
            f"({len(failing)} failing, {len(asking)} question)"
        )

    if not failing and not asking:
        return [field("docs audit", f"clean · {len(rows)} checks")]
    verdict = f"{len(failing)} FAILING" if failing else f"{len(asking)} question(s)"
    return [
        field("docs audit", f"{verdict} · {len(clean)} clean — run `make docs-audit`"),
    ]


# A map `note` argues its case at length — that is what the field is for. Printing the
# WHOLE of one under a heading called "Blind spots" put a 900-character paragraph about the
# codes package into `make status`, most of it about what the track deliberately does not
# share with the singles track, none of that a blind spot. Taking the sentences that
# actually say `blind` keeps the field free to keep arguing and the status line short.
_SENTENCE = re.compile(r"(?<=[.;])\s+")


def blind_sentences(note: str) -> str:
    hits = [part.strip() for part in _SENTENCE.split(note) if "blind" in part.lower()]
    return " ".join(hits) if hits else note


def blind_spots(mapdata: Dict[str, object]) -> List[str]:
    """From structured fields, never from prose.

    The T1 caveat is written into the score file by the test itself; the T6 caveat is the
    `note` on the map's geometry entry, which the repo-map check audits. Rewording
    docs/GATES.md cannot break either one.
    """
    notes: List[str] = []
    for path in resolve("harness/results/t1*.json"):
        try:
            note = json.loads(read(path)).get("finish_note")
        except (OSError, ValueError):
            continue
        if note and note not in notes:
            notes.append(str(note))
    for component in mapdata.get("COMPONENTS") or []:
        note = str(component.get("note") or "")
        if "blind" in note.lower() or "NOT that" in note:
            notes.append(f"{component.get('path')} — {blind_sentences(note)}")

    if not notes:
        return []
    out = []
    for i, note in enumerate(notes):
        lines = wrap(note, LABEL + 2)
        out.append(field("Blind spots" if i == 0 else "", lines[0]))
        out.extend(cont(line) for line in lines[1:])
    return out


def repo() -> List[str]:
    branch = git("branch", "--show-current")
    head = git("log", "-1", "--format=%h")
    subject = git("log", "-1", "--format=%s")
    if branch is None or head is None:
        miss("git", "not a git repository, or git is unavailable")
        return [field("Branch", "MISSING: git reported nothing")]

    porcelain = git("status", "--porcelain") or ""
    dirty = [line for line in porcelain.splitlines() if line.strip()]
    state = "(clean)" if not dirty else f"({len(dirty)} uncommitted)"
    out = [field("Branch", f"{branch} @ {head}  {state}")]
    out.append(cont(f'"{subject}"'))

    if dirty:
        # Porcelain's first two columns are staged/unstaged status, so the flag is padded
        # to a fixed width rather than indented on top of its own leading space.
        for line in dirty[:12]:
            flag, _, name = line.strip().partition(" ")
            out.append(cont(f"  {flag:<3}{name.strip()}"))
        if len(dirty) > 12:
            out.append(cont(f"  … and {len(dirty) - 12} more"))

    # `--left-right --count main...branch` prints "<only in main> <only in branch>".
    counts = git("rev-list", "--left-right", "--count", f"main...{branch}")
    if counts and branch != "main":
        only_main, only_branch = (counts.split() + ["?", "?"])[:2]
        if only_main == "0":
            out.append(field("main", f"{only_branch} behind — main has none of this branch's work"))
        else:
            out.append(field("main", f"{only_branch} ahead of main, {only_main} behind it"))
    return out


def hooks() -> List[str]:
    """Whether THIS clone's git hooks are actually armed, and whether they are current.

    `core.hooksPath` is local git config and is never pushed, so the hooks being present in
    the tree proves nothing — a fresh clone has the files with nothing pointing at them, and
    CLAUDE.md's bearer-instrument rule is unenforced on the first commit. Only the config
    proves it, and only this script is in a position to look.

    WHAT IT LOOKS FOR CHANGED ON 2026-08-29, AND THE OLD ANSWER IS NOW A FAILURE STATE.
    D42 first aimed core.hooksPath at the main worktree's `scripts/githooks`, and that made
    arming depend on which branch that one checkout happened to be on. It was falsified the
    hour it landed: the main checkout sat on another session's WIP branch that predated the
    guard, so git read a directory holding one hook of three and nothing said so. The hooks
    are installed into the git common dir now, which no branch can empty, and a config still
    pointing into a working tree is reported as NOT ARMED rather than accepted.

    Four ways to be unarmed and they are kept distinct, because they have four different
    fixes: no config at all, a config aimed somewhere else, a hook missing from the install,
    and a hook git will skip for being non-executable. The last is the one worth naming —
    git says nothing about it.

    STALENESS IS REPORTED AND NEVER TREATED AS AN ERROR. The install is a copy, so editing
    `scripts/githooks` does not change what git runs until `make hooks` is run again. It
    cannot be checked mechanically without lying: the tracked file legitimately differs
    between branches, so a difference is a fact to state rather than a fault to flag. This
    is the one place in the repo whose job is saying what state you are actually in, so it
    says it here and gates nothing.
    """
    tracked = resolve("scripts/githooks/*")  # records MISSING if the hooks themselves are gone
    configured = git("config", "--get", "core.hooksPath")

    if configured is None:
        return [
            field("Git hooks", "NOT ARMED — core.hooksPath is unset, commits are unchecked"),
            cont("Fix: make hooks"),
        ]

    common = git("rev-parse", "--path-format=absolute", "--git-common-dir") or git(
        "rev-parse", "--git-common-dir"
    )
    expected = (Path(common) / "hooks-armed") if common else None
    installed = Path(configured)

    if expected is None or installed.resolve() != expected.resolve():
        return [
            field("Git hooks", f"NOT ARMED — core.hooksPath points at {configured}"),
            cont("A working tree is not a home for this: what it holds follows whatever"),
            cont("branch that checkout is on, which armed the guard at zero once already."),
            cont("Fix: make hooks"),
        ]

    names = sorted(path.name for path in tracked)
    absent = [name for name in names if not (installed / name).exists()]
    if absent:
        return [
            field("Git hooks", f"NOT ARMED — {', '.join(absent)} missing from the install"),
            cont("Fix: make hooks"),
        ]

    unrunnable = [name for name in names if not os.access(installed / name, os.X_OK)]
    if unrunnable:
        return [
            field(
                "Git hooks",
                f"NOT ARMED — {', '.join(unrunnable)} not executable; git skips it silently",
            ),
            cont("Fix: make hooks"),
        ]

    out = [
        field("Git hooks", f"armed via {configured}"),
        cont(f"{len(names)} installed: {', '.join(names)}"),
    ]

    stale = []
    for name in names:
        try:
            if (installed / name).read_bytes() != (ROOT / "scripts" / "githooks" / name).read_bytes():
                stale.append(name)
        except OSError:  # unreadable is not a claim that it differs
            continue
    if stale:
        out += [
            cont(f"differs from this tree: {', '.join(stale)}"),
            cont("Expected on a branch that changed them. Otherwise the copy git runs is"),
            cont("behind scripts/githooks here — re-run `make hooks`."),
        ]
    return out


def serving() -> List[str]:
    """Whether anything is actually up, and whose store it is answering for.

    THIS FILE HAD NO LIVENESS PROBE AT ALL UNTIL `make up` EXISTED. `ports_and_store()` below
    prints which ports this tree WOULD use and has never had any idea who actually holds them
    — which is fine while a server is a thing you start in a terminal you are looking at, and
    not fine once one starts at login and stays up for weeks.

    THE THIRD BRANCH IS WHY THIS EARNS ITS PLACE. A port that answers while no pidfile in THIS
    checkout claims it is D43's fault made visible for the first time: another tree's server,
    or a stray `make server`, holding the port this tree's UI addresses — over a DIFFERENT
    store. That was previously undetectable from inside the tree it was happening to.

    Read-only, like everything else here: `serve.report()` opens nothing for writing, signals
    nothing and starts nothing.
    """
    found = resolve("scripts/serve.py")
    if not found:
        return [field("Serving", "MISSING: scripts/serve.py")]
    spec = importlib.util.spec_from_file_location("_pkmnscan_serve", found[0])
    if spec is None or spec.loader is None:
        return [field("Serving", "scripts/serve.py could not be loaded")]
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        data = module.report()
    except Exception as exc:  # a broken probe is not a reason to kill `make status`
        return [field("Serving", f"scripts/serve.py raised: {exc}")]

    out: List[str] = []
    sup = data.get("supervisor")
    if sup:
        out.append(field("supervisor", f"up (pid {sup}) — `make up`"))
    else:
        out.append(field("supervisor", "not running — `make up` starts both servers"))

    for label, pid_key, port_key, live_key in (
        ("capture", "capture_pid", "capture_port", "capture_answering"),
        ("app", "app_pid", "dev_port", "app_answering"),
    ):
        port = data.get(port_key)
        answering = data.get(live_key)
        pid = data.get(pid_key)
        if answering and pid:
            out.append(field(label, f":{port} answering (pid {pid})"))
        elif answering:
            # The D43 case. Named as the hazard it is rather than reported as "up".
            out.append(field(label, f":{port} is answering, but no pidfile in THIS checkout"))
            out.append(cont("claims it — another checkout, or a stray `make server`."))
            out.append(cont("D43: it is serving a DIFFERENT store."))
        else:
            out.append(field(label, f":{port} not answering"))

    if data.get("agent_installed"):
        out.append(field("launch agent", f"plist installed — {data.get('agent_label')}"))
    for name in data.get("lan_names") or []:
        out.append(field("on the network", f"http://{name}:{data.get('dev_port')}"))
    return out


def ports_and_store() -> List[str]:
    """Which ports this checkout serves on, and whose inventory it is serving.

    THE THREE FACTS THAT DECIDE WHETHER YOU ARE ABOUT TO CORRUPT SOMETHING (D43). The store
    defaults to the checkout the code runs from, so every worktree has its own inventory —
    and until D43 the capture port was the constant 8000 in all of them, so whichever server
    won the bind answered every tree's UI. One direction drives the owner's real inventory
    from a branch; the other writes real capture photographs into a directory that is deleted
    with the worktree.

    Printed here rather than left derivable because none of it is visible at a glance: the
    paths differ by one segment in the middle of a long absolute path, and the ports are
    numbers nobody has memorised. `make status` is what CLAUDE.md tells a cold session to run
    first, which makes it the right place to say which tree it has landed in.
    """
    found = resolve("server/ports.py")
    if not found:
        return [field("Ports", "MISSING: server/ports.py")]
    spec = importlib.util.spec_from_file_location("_pkmnscan_ports", found[0])
    if spec is None or spec.loader is None:
        return [field("Ports", "server/ports.py could not be loaded")]
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # a broken derivation is not a reason to kill `make status`
        return [field("Ports", f"server/ports.py raised: {exc}")]

    linked = module.is_linked_worktree(module.REPO_ROOT)
    out = [
        field("Ports", f"capture {module.capture_port()} · dev {module.dev_port()}"),
    ]
    if linked:
        out += [
            cont(f"THIS IS A WORKTREE — {module.REPO_ROOT.name}"),
            cont(f"the main checkout serves capture {module.CAPTURE_BASE_PORT} / "
                 f"dev {module.DEV_BASE_PORT}, over a DIFFERENT store"),
        ]

    # WHICH PORT THE BROWSER PANE WILL ACTUALLY OPEN, which is not the same question as the
    # line above and was the sixth reader D43 missed. `scripts/worktree-guard.sh` writes this
    # file at session start, so the ordinary answer is that they agree — and this line exists
    # for the case where they do not, because that hook FAILS OPEN by design and a silent
    # skip leaves a tab pointing at the main tree while everything else here reads correctly.
    #
    # Reported and never repaired, like every other line in this file: `--check` writes
    # nothing. The remedy is named in the output rather than performed, which is D18's split
    # between a thing that reports and a thing that acts.
    found = resolve("scripts/launch-config.py")
    if found:
        done = subprocess.run(
            [sys.executable, str(found[0]), "--check"],
            cwd=str(ROOT), capture_output=True, text=True, check=False,
        )
        said = ""
        for line in done.stdout.splitlines():
            if line.startswith("launch-config:"):
                said = line.split(":", 1)[1].strip()
        if said.startswith("current"):
            pass  # agreeing is the ordinary case and costs no line
        elif said:
            out += [cont(f"BROWSER PANE: {said}"), cont("fix with `make launch-config`")]
    return out


def icloud() -> List[str]:
    """How many iCloud Drive conflict copies are lying in this tree.

    Reported and never acted on. They are untracked, the pre-commit hook already refuses to
    COMMIT one, and `make hooks` installs only what git tracks — so the two ways one could do
    damage are closed and what is left is clutter that a person clears when they feel like it.
    What was NOT closed until this line existed is noticing: they are invisible to every
    normal command, and the way they surfaced was a commit failing on the repo-map orphan rule
    and, once, one being installed as a git hook.

    Silent when there are none, which has been the permanent case since the repo moved off
    iCloud Drive on 2026-08-29. Kept rather than deleted for D44's amended reason: the check is
    a scan of this tree, and a tree can be put back inside a synced folder without telling it.
    """
    found = resolve("scripts/icloud-sweep.py")
    if not found:
        return []
    done = subprocess.run(
        [sys.executable, str(found[0])],
        cwd=str(ROOT), capture_output=True, text=True, check=False,
    )
    summary = ""
    for line in done.stdout.splitlines():
        if line.startswith("icloud-sweep:"):
            summary = line.split(":", 1)[1].strip()
    if not summary or summary == "no conflict copies":
        return []
    return [
        field("iCloud copies", summary.split("  (")[0]),
        cont("`make icloud-sweep` lists them; ARGS=--delete removes the identical ones"),
    ]


def store() -> List[str]:
    """The store's two directories, and the shape of the store inside the first (D87).

    `store.sqlite` is the master since D87 and the six JSON files before it are moved to
    `legacy-json/` on the first open. Three states are worth telling apart here, because
    two of them look identical from a directory listing: a database, a legacy store nobody
    has opened on the new code yet (the next open migrates it), and a legacy file sitting
    BESIDE a database — which nothing reads, and which a person will otherwise trust.
    Stdlib sqlite3, no project import, the same rule as everything else in this file.
    """
    out = []
    for name, absent in (("inventory", "nothing captured yet"), ("runs", "no identify run yet")):
        found = resolve(name)  # declared optional, so absence is reported, not a failure
        out.append(field(f"{name}/", "present" if found else f"absent — {absent}"))
        if name != "inventory" or not found:
            continue
        directory = found[0]
        database = directory / "store.sqlite"
        legacy = [n for n in ("inventory.json", "identifications.json", "review.json",
                              "parked.json", "orders.json", "history.jsonl")
                  if (directory / n).is_file()]
        if database.is_file():
            try:
                import sqlite3

                conn = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
                cards = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
                boxes = conn.execute("SELECT COUNT(*) FROM boxes").fetchone()[0]
                conn.close()
                out.append(cont(f"store.sqlite: {cards} cards in {boxes} boxes (D87)"))
            except Exception as exc:  # noqa: BLE001 — status reports, never raises
                out.append(cont(f"store.sqlite: could not be read ({exc})"))
            if legacy:
                out.append(cont(f"AND {', '.join(legacy)} beside it — READ BY NOTHING. Move "
                                f"them into legacy-json/ or delete them; a legacy file is "
                                f"never a fallback (D86, D87)."))
        elif legacy:
            out.append(cont(f"legacy JSON store ({', '.join(legacy)}) — the next `Store()` "
                            f"open migrates it to store.sqlite and moves these to "
                            f"legacy-json/ (D87)"))
    return out


# --------------------------------------------------------------------------- main


def render() -> str:
    found = resolve("docs/map.py")
    mapdata = literals(found[0]) if found else {}
    gists = load_gists()

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = "PKMNSCAN — status"
    lines = [f"{header}{stamp:>{WIDTH - len(header)}}", "=" * WIDTH, "", "WHERE YOU ARE"]
    lines += where_you_are(mapdata)
    nxt = do_this_next(mapdata, gists)
    if nxt:
        # NOT "DO THIS NEXT". The heading made the same scheduling claim the single-`next`
        # field did, one layer up: whatever is printed under it reads as the instruction.
        lines += ["", "WHAT IS OPEN"] + nxt
    lines += ["", "HEALTH"]
    lines += audit_line()
    lines.append(field("harness", "NOT RUN — status never runs it. Committed scores below."))
    lines += t1_blocks()
    lines += blind_spots(mapdata)
    lines.append(field("the map", "`make map` renders docs/map.py — a package, a path, a"))
    lines.append(cont("decision id, or `--stale` for prose its file has outrun."))
    lines += ["", "REPO"] + repo() + hooks() + ports_and_store() + icloud()
    lines += ["", "SERVING"] + serving()
    lines += ["", "STORE"] + store()

    if MISSING:
        lines += ["", "=" * WIDTH, f"{len(MISSING)} source{'' if len(MISSING) == 1 else 's'} could not be read:"]
        for item in MISSING:
            lines.append(f"  MISSING: {item.what}" + (f" — {item.detail}" if item.detail else ""))
        lines.append("")
        lines.append("This output is incomplete. A status tool that quietly prints less is")
        lines.append("worse than none, so this exits non-zero. If a file moved, update")
        lines.append("SOURCES in scripts/status.py — the docs audit verifies the same list.")
    return "\n".join(lines)


def main(argv: Sequence[str]) -> int:
    if argv and argv[0] == "--sources":
        print(json.dumps([dict(s) for s in SOURCES], indent=2, default=list))
        return 0
    print(render())
    return 1 if MISSING else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
