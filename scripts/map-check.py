#!/usr/bin/env python3
"""`make map-check` — runs claude-settings' shared `plain-english-map` check over this repo.

The check, its nine MAP rules and its reader of `map.config.json` live in claude-settings
(`skills/plain-english-map/scripts/map-check.mjs`), their one home. This file only finds that
copy and runs it from the repo root, so the rules are never copied here.

WHERE THE SKILL IS, IN ORDER:
  1. `$CLAUDE_SETTINGS_DIR`, a claude-settings checkout. CI sets it to the pinned copy that the
     runner downloaded for the `shivinate7/claude-settings/actions/...` steps of check.yml.
  2. `~/claude-settings`, the checkout `install.sh` links `~/.claude` to.
  3. `~/.claude/skills/plain-english-map`, the install link, followed to its real place.

THE CHECK LOADS `typescript` FROM THE `node_modules` BESIDE THE SKILL'S REAL PATH, so that
checkout needs `npm ci` (`install.sh` runs it; CI runs it in its `ci-static` job).

NO SKILL, NO NODE, NO RUN IS A FAILURE AND NEVER A SKIP: a map nobody checked is not a map
that passed. The exit code is the check's own.

    scripts/map-check.py            run the check
    scripts/map-check.py --where    print the skill folder it would run, and stop
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
SKILL_REL = Path("skills") / "plain-english-map"


def candidate_roots(env: Optional[dict] = None, home: Optional[Path] = None) -> List[Path]:
    """The claude-settings checkouts to try, best first. A named `$CLAUDE_SETTINGS_DIR` is the
    only one tried when it is set: a wrong path there must fail, never fall through to another copy."""
    env = os.environ if env is None else env
    home = Path.home() if home is None else home
    named = env.get("CLAUDE_SETTINGS_DIR")
    if named:
        return [Path(named)]
    roots = [home / "claude-settings"]
    link = home / ".claude" / "skills" / "plain-english-map"
    if link.exists():
        # `<root>/skills/plain-english-map` resolved: two parents up is the checkout.
        roots.append(link.resolve().parent.parent)
    return roots


def find_skill(env: Optional[dict] = None, home: Optional[Path] = None) -> Optional[Path]:
    for root in candidate_roots(env, home):
        if (root / SKILL_REL / "scripts" / "map-check.mjs").is_file():
            return root / SKILL_REL
    return None


def main(argv: List[str]) -> int:
    skill = find_skill()
    if skill is None:
        tried = ", ".join(str(p) for p in candidate_roots()) or "nothing"
        print(
            "map-check: the plain-english-map skill was not found, so the map was NOT checked.\n"
            f"  looked in: {tried}\n"
            "  set CLAUDE_SETTINGS_DIR to a claude-settings checkout (run `npm ci` there), "
            "or run claude-settings' install.sh.",
            file=sys.stderr,
        )
        return 1
    if "--where" in argv:
        print(skill)
        return 0
    node = shutil.which("node")
    if node is None:
        print("map-check: node is not on PATH, so the map was NOT checked.", file=sys.stderr)
        return 1
    return subprocess.run([node, str(skill / "scripts" / "map-check.mjs")], cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
