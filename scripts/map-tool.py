#!/usr/bin/env python3
"""`make map` and `make map-fix` — run one of claude-settings' `plain-english-map` tools over this repo.

The tools, and the map's format, live in claude-settings (`skills/plain-english-map/scripts/`),
their one home. `scripts/map-check.py` is the one finder of that folder; this file imports its
`find_skill` and runs the named tool from the repo root, so the finder is never copied.

    scripts/map-tool.py show <path|area|folder/>   print that part of docs/map/ (map-show.mjs)
    scripts/map-tool.py stale                      map lines whose file changed after the line was written (map-stale.mjs)
    scripts/map-tool.py fix [--write]              add the decision ids a file cites to its decisions line (map-fix.mjs)

`make map ARGS=--stale` is `stale`; any other ARGS is `show`. No skill and no node is a failure,
never a skip, for the reason `scripts/map-check.py` gives. The exit code is the tool's own.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
TOOLS = {"show": "map-show.mjs", "stale": "map-stale.mjs", "fix": "map-fix.mjs"}


def _finder():
    spec = importlib.util.spec_from_file_location("map_check", ROOT / "scripts" / "map-check.py")
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def main(argv: List[str]) -> int:
    if not argv or argv[0] not in TOOLS:
        print(f"usage: map-tool.py {{{'|'.join(TOOLS)}}} [args]", file=sys.stderr)
        return 2
    tool, args = argv[0], argv[1:]
    if tool == "show" and "--stale" in args:
        tool, args = "stale", [a for a in args if a != "--stale"]
    skill = _finder().find_skill()
    if skill is None:
        print("map-tool: the plain-english-map skill was not found; run `python3 scripts/map-check.py` "
              "for where it looked.", file=sys.stderr)
        return 1
    node = shutil.which("node")
    if node is None:
        print("map-tool: node is not on PATH.", file=sys.stderr)
        return 1
    return subprocess.run([node, str(skill / "scripts" / TOOLS[tool]), *args], cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
