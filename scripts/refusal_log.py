#!/usr/bin/env python3
"""The one refusal log: every guard that denies or asks appends one line here.

`.git/pkmnscan-refusals.log` sits beside the hatch log (`pkmnscan-hatches.log`) in git's common
dir, so every worktree of a clone writes one file. One line per refusal, TAB-separated:

    ISO time, guard:rule, snippet (<= 80 chars, one line), session id, checkout

so that a rule can be judged by how often it fires (`make status` reads the last 24 hours back
through `recent`). LOG ONLY: no verdict reads it. FAILS OPEN: any error here is swallowed, so a
log that cannot be written never changes a guard's verdict or output. One `os.write` on an
`O_APPEND` descriptor per line, so concurrent agents never interleave a line.

The snippet is what the guard matched, never a whole command, a file body or a secret: callers
pass a heading, a path or a masked verdict. Shell hooks call the CLI:

    python3 scripts/refusal_log.py <guard> <rule> <snippet> [--session ID]
"""
from __future__ import annotations

import os
import subprocess
import sys
from collections import Counter
from datetime import datetime
from typing import Dict, Optional

LOG = "pkmnscan-refusals.log"
ENV_PATH = "PKMNSCAN_REFUSAL_LOG"        # a file path; the self-tests point it at a fixture
STAMP = "%Y-%m-%dT%H:%M:%S%z"
SNIPPET_MAX = 80


def _git(args, cwd: str) -> str:
    try:
        done = subprocess.run(["git", *args], cwd=cwd or None, capture_output=True, text=True,
                              check=False, timeout=10)
        return done.stdout.strip() if done.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def log_path(cwd: str = "") -> str:
    override = os.environ.get(ENV_PATH)
    if override:
        return override
    common = _git(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd)
    return os.path.join(common, LOG) if common else ""


def clean(text: str) -> str:
    """One line, no tabs, at most SNIPPET_MAX characters."""
    return " ".join(str(text).split())[:SNIPPET_MAX]


def log(guard: str, rule: str, snippet: str = "", session: str = "", cwd: str = "") -> None:
    try:
        cwd = cwd or os.getcwd()
        path = log_path(cwd)
        if not path:
            return
        root = _git(["rev-parse", "--show-toplevel"], cwd) or cwd
        session = session or os.environ.get("CLAUDE_SESSION_ID", "")
        line = "\t".join([datetime.now().astimezone().strftime(STAMP), clean(f"{guard}:{rule}"),
                          clean(snippet), clean(session), clean(root)]) + "\n"
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line.encode("utf-8", "replace"))
        finally:
            os.close(fd)
    except Exception:                      # noqa: BLE001 — fails open: a log never blocks
        pass


def recent(cwd: str = "", hours: int = 24) -> Dict[str, int]:
    """{guard:rule: count} over the last `hours`."""
    path = log_path(cwd)
    found: Counter = Counter()
    if not path or not os.path.isfile(path):
        return {}
    cutoff = datetime.now().astimezone().timestamp() - hours * 3600
    with open(path, encoding="utf-8", errors="replace") as handle:
        for row in handle:
            parts = row.rstrip("\n").split("\t")
            try:
                if len(parts) >= 2 and datetime.strptime(parts[0], STAMP).timestamp() >= cutoff:
                    found[parts[1]] += 1
            except ValueError:
                continue
    return dict(found)


def main(argv: Optional[list] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    session = ""
    if "--session" in args:
        at = args.index("--session")
        session = args[at + 1] if at + 1 < len(args) else ""
        del args[at:at + 2]
    if len(args) >= 2:
        log(args[0], args[1], args[2] if len(args) > 2 else "", session)
    return 0                                # always: this is a log, never a verdict


if __name__ == "__main__":
    sys.exit(main())
