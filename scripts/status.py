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
        "requires": ("BUILD_ORDER", "GATES", "COMPONENTS"),
        "why": "build order, gate status, per-component status and governed_by",
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
        "path": "server/ports.py",
        "kind": "file",
        "requires": (),
        "why": "which ports THIS checkout serves on — imported by ports_and_store() below. "
               "Imported rather than ast-parsed because the answer is a function of where "
               "the checkout is, not a literal; stdlib-only, so it cannot need `make venv`",
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
    build = mapdata.get("BUILD_ORDER") or []
    gates = mapdata.get("GATES") or []
    if not build:
        return [field("Build step", "MISSING: docs/map.py BUILD_ORDER")]

    nxt = [s for s in build if s.get("status") == "next"]
    done = [s.get("step") for s in build if s.get("status") == "done"]
    out: List[str] = []

    if len(nxt) != 1:
        out.append(field("Build step", f"MISSING: expected exactly one `next`, found {len(nxt)}"))
        step_no = None
    else:
        step = nxt[0]
        step_no = step.get("step")
        title = str(step.get("title", ""))
        head, _, rest = title.partition(":")
        out.append(field("Build step", f"{step_no} of {len(build)} — {head.strip()}"))
        if rest.strip():
            out.extend(cont(line) for line in wrap(rest.strip(), LABEL + 2))

    # GATES ARE A RECORD NOW, NOT A SCHEDULE (retired 2026-08-23). This block used to find
    # the one gate marked `next`, print what it blocked, and draw the chain of build steps
    # standing between here and it. With nothing open, that code printed nothing at all —
    # which would have quietly dropped the only line in `make status` that says this project
    # has ever met a real card. So it reports the history instead of the schedule.
    open_gate = next((g for g in gates if g.get("status") == "next"), None)
    if open_gate:
        blocked = open_gate.get("blocked_by") or "nothing"
        out.append(field("Gate", f"{open_gate.get('gate')} (next) — blocked behind {blocked}"))
        out.extend(cont(line) for line in wrap(str(open_gate.get("what", "")), LABEL + 2))
    elif gates:
        passed = [g for g in gates if g.get("status") == "passed"]
        names = ", ".join(f"{g.get('gate')} {g.get('on', '')}".strip() for g in passed)
        out.append(field("Gates", f"retired — {len(passed)} passed: {names}"))
        out.extend(cont(line) for line in wrap(
            "docs/GATES.md is the record of what was measured, not a schedule.", LABEL + 2))

    out.append(field("Done", "steps " + ", ".join(str(d) for d in done)))

    if step_no and open_gate:
        blocked_by = str(open_gate.get("blocked_by") or "")
        last = "".join(c for c in blocked_by if c.isdigit())
        if last:
            chain = " → ".join(str(n) for n in range(int(step_no), int(last) + 1))
            out.append(field(f"Chain to {open_gate.get('gate')}", f"{chain} → Gate {open_gate.get('gate')}"))
    return out


def do_this_next(mapdata: Dict[str, object], gists: Dict[str, Tuple[str, List[str]]]) -> List[str]:
    build = mapdata.get("BUILD_ORDER") or []
    components = mapdata.get("COMPONENTS") or []
    nxt = [s for s in build if s.get("status") == "next"]
    if not nxt:
        return []
    step_no = nxt[0].get("step")

    entry = next((c for c in components if c.get("step") == step_no), None)
    out: List[str] = []
    if entry is None:
        out.append(field("Build", f"step {step_no} — no component in docs/map.py claims this step"))
        out.append(cont("The map names a directory only once the name is decided (see its header)."))
        return out

    path = str(entry.get("path"))
    out.append(field("Build", f"{path} — the only unblocked step."))
    out.append(cont("Nothing else moves until it lands."))
    out.extend(cont(line) for line in wrap(str(entry.get("does", "")), LABEL + 2))

    governed = sorted(entry.get("governed_by") or [], key=lambda d: int(str(d)[1:]))
    for i, name in enumerate(governed):
        title, rulings = gists.get(name, ("(no such entry in docs/DECISIONS.md)", []))
        out.append(field("Governed by" if i == 0 else "", f"{name:<4} {title}"))
        for ruling in rulings[:1]:
            out.extend(cont(f"     {line}") for line in wrap(ruling, LABEL + 7))
    out.append(field("Read first", f"docs/GATES.md step {step_no} · docs/map.py COMPONENTS {path}"))
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
            notes.append(note)

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
    return out


def store() -> List[str]:
    out = []
    for name, absent in (("inventory", "nothing captured yet"), ("runs", "no identify run yet")):
        found = resolve(name)  # declared optional, so absence is reported, not a failure
        out.append(field(f"{name}/", "present" if found else f"absent — {absent}"))
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
        lines += ["", "DO THIS NEXT"] + nxt
    lines += ["", "HEALTH"]
    lines += audit_line()
    lines.append(field("harness", "NOT RUN — status never runs it. Committed scores below."))
    lines += t1_blocks()
    lines += blind_spots(mapdata)
    lines += ["", "REPO"] + repo() + hooks() + ports_and_store()
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
