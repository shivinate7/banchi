#!/usr/bin/env python3
"""PostToolUse hook: typecheck `app/` after a TypeScript file is written.

Nothing else in this repo gives an automatic signal on TypeScript. The Stop hook runs
`make harness`, and every test in it is Python — none of them invokes `tsc`.
Without this, a turn can write broken TypeScript and only find out when a human runs
`make typecheck`.

WHY IT FILTERS BY PATH, WHICH IS THE WHOLE DESIGN. This channel existed before and was
deleted on 2026-08-11 after eight days of printing five lines of failure text after EVERY
edit: it ran `make lint typecheck`, both were stubs that exit 1 by design, the abort on
`lint` meant `typecheck` never ran at all, and a pipe to `tail` swallowed the status so the
hook exited 0 and blocked nothing. The lesson is not "point it at a real target" — it is
that a hook which speaks on every edit gets muted, and a muted hook protects nothing. The
opsec guard died the same way inside a day, and `.claude/settings.json` still carries the
note explaining why it is off.

So: a Claude Code hook MATCHER cannot filter by file path, but the hook itself reads the
payload and can. This one exits 0 in silence unless the edited file is a `.ts` or `.tsx`
under `app/`. Editing markdown, Python, or CSS produces no output and spawns no process.

IT CANNOT BLOCK A WRITE. PostToolUse fires after the tool has already run, so the edit has
landed by the time this executes — the only thing on offer is telling the agent what it just
broke. Failure exits 2 with tsc's own output on stderr, which is the channel that reaches
the model; success is silent. Every other outcome — bad payload, no dependencies installed,
a missing compiler, this script's own bugs — exits 0 and says nothing, matching
scripts/decision-context.py's temperament. An advisory that can fail a turn on its own
malfunction is worse than no advisory.

Deliberately NOT `make typecheck`: that target's NPM_GUARD prints an install hint, which is
correct for a human at a terminal and is noise fired automatically after an edit. This calls
the compiler directly, which is also faster by an npm process spawn.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCHED_DIR = ROOT / "app"
WATCHED_SUFFIXES = (".ts", ".tsx")
TSC = ROOT / "app" / "node_modules" / ".bin" / "tsc"
TSCONFIG = ROOT / "app" / "tsconfig.json"

# tsc on this project takes well under a second. The cap is here so that a pathological
# case — a compiler waiting on something — costs a bounded pause rather than the turn.
TIMEOUT_SECONDS = 90


def edited_path(payload: dict) -> Path | None:
    """The file the tool just wrote, or None if the payload is not shaped that way.

    The payload shape has moved between Claude Code releases, which is the known limit D17
    records for the decision-context hook. Same failure mode here and same answer: an
    unreadable payload is a lost nudge, never an error.
    """
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    raw = tool_input.get("file_path")
    if not isinstance(raw, str) or not raw:
        return None
    return Path(raw)


def is_watched(path: Path) -> bool:
    if path.suffix not in WATCHED_SUFFIXES:
        return False
    try:
        resolved = path if path.is_absolute() else (ROOT / path)
        resolved.resolve().relative_to(WATCHED_DIR.resolve())
    except (ValueError, OSError):
        return False
    return True


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0

    path = edited_path(payload)
    if path is None or not is_watched(path):
        return 0

    # No dependencies, no compiler, nothing to say. `npm --prefix app install` is a thing a
    # person does; a hook that nags about it after every edit is the failure above.
    if not TSC.exists() or not TSCONFIG.exists():
        return 0

    try:
        result = subprocess.run(
            [str(TSC), "-p", str(TSCONFIG), "--noEmit", "--pretty", "false"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            cwd=str(ROOT),
        )
    except (OSError, subprocess.SubprocessError):
        return 0

    if result.returncode == 0:
        return 0

    report = (result.stdout + result.stderr).strip()
    if not report:
        return 0

    print(f"tsc failed after editing {path.name}:", file=sys.stderr)
    print(report, file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 — a hook must never fail a turn on its own bug
        sys.exit(0)
