#!/usr/bin/env python3
"""Write `.claude/launch.json` for THIS checkout's dev port, and never for another's.

WHY THIS IS A FILE RATHER THAN A LINE IN THE MAKEFILE. D43 made the dev port a function of
the checkout's path and moved five readers onto one derivation; `.claude/launch.json` was
the sixth, found later, and its amendment says why it is the worst one to get wrong — the
Browser pane starts THIS tree's dev server and then opens a tab on whatever port this file
names, so a stale 5173 previews the MAIN TREE while looking like it worked. That entry
called it "the same silent-wrong-answer shape" and it is: the only signal is the one you
were hoping for.

THE FIX D43 SHIPPED WAS A `make` TARGET, AND A TARGET ONLY RUNS WHEN SOMEBODY RUNS IT. It
hangs off `make venv`, which `make worktree-setup` calls — so a worktree provisioned any
other way gets no file at all, and an ABSENT file is the dangerous state rather than a
harmless one: the Browser pane's own instructions tell an agent to create one from a
template with a hardcoded port, and that is exactly how a 5173 lands in a worktree that
derives 5470. Measured 2026-08-30 across the five worktrees of this clone: four correct,
one absent, and this one holding a hand-written 5173 nobody remembered writing.

SO THE SESSION-START HOOK CALLS THIS, AND THAT IS THE WHOLE OF THE FIX. `scripts/
worktree-guard.sh` already runs before any work starts, already provisions the other
gitignored things a checkout cannot inherit, and already imports this same `server.ports`
to print the pair. One more provisioned thing, from the one derivation, with nobody
required to remember a target.

THREE CALLERS, THREE APPETITES, AND THE DIFFERENCE IS DELIBERATE:

  make launch-config   FORCES. Somebody typed it; they mean it. Today's behaviour, kept.
  worktree-guard.sh    CONSERVATIVE (`--if-needed`). Writes an absent or a stale file and
                       REFUSES to touch anything else, because it runs unasked.
  make status          READS (`--check`). Never writes, and is what makes a hook that
                       failed open still visible.

WHAT "STALE" MEANS, AND WHY IT IS NOT "ANY FILE WITH THE WRONG PORT". A file is rewritable
only when it is byte-for-byte the shape this script writes except for the port. Anything
else — a second configuration, a different command, a `url`, an attach-only entry, JSON
that does not parse — is somebody's work and is REPORTED rather than overwritten. That
asymmetry is D44's: `make icloud-sweep` deletes only what is provably a duplicate and only
ever reports what differs, on the grounds that guessing is the one way a cleanup tool
destroys work. A provisioner that runs on every session start unasked has strictly more
reason to keep it.

IT EXITS 0 ON EVERY PATH, INCLUDING ITS OWN BUGS. `make venv` depends on the target that
calls this, and the hook is a SessionStart hook — this repo's standing rule, learned when
`scripts/guard-opsec.sh` over-triggered and was disabled within a day, is that a hook which
can break a session is a hook that gets removed. A refusal is printed, never raised.

STDLIB ONLY, AND BARE `python3` MUST BE ABLE TO RUN IT. The hook calls this BEFORE it builds
`.venv` — the file is wanted whether or not the venv ever succeeds — so an import that
needed a package would make the port wrong exactly in the tree that is least set up.
`server/ports.py` is stdlib at module scope for the same reason and is imported here rather
than re-derived, because two spellings of one slot is the drift D43 spent a whole entry
closing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".claude" / "launch.json"


def desired(port: int) -> dict:
    """The one shape this repo writes. `npm run dev --prefix app` is what `make dev` runs.

    The port is the only field that varies by checkout, which is what lets `classify` below
    tell a file this script wrote at another path from a file somebody edited.
    """
    return {
        "version": "0.0.1",
        "configurations": [
            {
                "name": "app",
                "runtimeExecutable": "npm",
                "runtimeArgs": ["run", "dev", "--prefix", "app"],
                "port": port,
            }
        ],
    }


def render(port: int) -> str:
    return json.dumps(desired(port), indent=2) + "\n"


def classify(port: int) -> tuple[str, str]:
    """(state, sentence). One of: absent, current, stale, foreign.

    `stale` is the narrow case — our exact shape at the wrong port — and it is the one the
    Browser pane's own template produces, so it is the one that actually happens. Everything
    unrecognised is `foreign` and is never rewritten without being asked.
    """
    if not CONFIG.exists():
        return "absent", f"{CONFIG.relative_to(ROOT)} is absent — the Browser pane has no port to open"

    try:
        held: Any = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return "foreign", f"{CONFIG.relative_to(ROOT)} could not be read as JSON ({exc})"

    if held == desired(port):
        return "current", f"{CONFIG.relative_to(ROOT)} names {port}, this checkout's dev port"

    # Is it ours at another port? Compare against the shape with the port removed, so a file
    # written in a tree that has since been renamed is recognised rather than protected.
    def portless(doc: Any) -> Any:
        if not isinstance(doc, dict):
            return None
        out = json.loads(json.dumps(doc))
        for entry in out.get("configurations", []):
            if isinstance(entry, dict):
                entry.pop("port", None)
        return out

    if portless(held) == portless(desired(port)):
        was = held["configurations"][0].get("port")
        return "stale", f"{CONFIG.relative_to(ROOT)} names {was}, but this checkout serves {port}"

    return "foreign", (
        f"{CONFIG.relative_to(ROOT)} is not the file this repo generates — left untouched"
    )


def write(port: int) -> bool:
    """Replace the file. Returns whether it landed; never raises."""
    try:
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(render(port), encoding="utf-8")
        return True
    except OSError as exc:
        print(f"launch-config: could not write {CONFIG.relative_to(ROOT)}: {exc}")
        return False


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--if-needed",
        action="store_true",
        help="write only an absent or stale file; report anything else rather than overwrite it",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report the state and write nothing (what `make status` calls)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="say nothing when the file is already correct",
    )
    args = parser.parse_args(argv)

    # A broken derivation is not a reason to fail a session or a build. Same rule
    # `scripts/status.py` keeps around this import.
    try:
        sys.path.insert(0, str(ROOT))
        from server import ports  # noqa: PLC0415 — deliberately late, see above
        port = ports.dev_port()
    except Exception as exc:  # pragma: no cover — a bug here must not stop anything
        print(f"launch-config: could not read this checkout's dev port ({exc}); nothing written")
        return 0

    state, said = classify(port)

    if args.check:
        print(f"launch-config: {state} — {said}")
        return 0

    if state == "current":
        if not args.quiet:
            print(f"launch-config: {said}")
        return 0

    if state == "foreign" and args.if_needed:
        print(f"launch-config: {said}.")
        print(f"                Run `make launch-config` to replace it with {port}.")
        return 0

    if write(port):
        if state == "foreign":
            print(f"launch-config: replaced a hand-written {CONFIG.name}; the Browser pane opens this checkout on {port}")
        else:
            print(f"launch-config: launch.json written: the Browser pane opens this checkout on {port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
