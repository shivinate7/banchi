#!/usr/bin/env python3
"""Writes each composed `AGENTS.md`: today the root one, `CLAUDE.md` then every `.claude/rules/*.md` body.

Codex reads no `.claude/rules/`, so the root file carries the rules to it.

`AGENT_COMPOSED` in `docs_audit/hygiene.py` names each file and its sources, and
`composed_agents_text` there says what the file must hold. This script writes that text and
nothing else, so the file and the `agent links` row cannot disagree.

D18: this script writes, so it never runs on the commit path. `make docs-audit`'s `agent links`
row calls `composed_agents_text()` and compares. It never writes.

    scripts/agents_gen.py            print whether each composed file is current
    scripts/agents_gen.py --write    rewrite the stale ones
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from docs_audit.hygiene import AGENT_COMPOSED, composed_agents_text  # noqa: E402


def main(write: bool) -> int:
    stale = 0
    for link, sources in AGENT_COMPOSED:
        path = ROOT / link
        want = composed_agents_text(sources)
        if want is None:
            print(f"{link}: a source in {', '.join(sources)} does not exist. Nothing written.")
            stale += 1
            continue
        current = path.is_file() and not path.is_symlink() and path.read_text(encoding="utf-8") == want
        if current:
            print(f"{link} is current.")
            continue
        if not write:
            print(f"{link} is stale. Run with --write.")
            stale += 1
            continue
        # A symlink here would carry the write into its target, a rule file.
        if path.is_symlink():
            path.unlink()
        path.write_text(want, encoding="utf-8")
        print(f"{link} written.")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main("--write" in sys.argv))
