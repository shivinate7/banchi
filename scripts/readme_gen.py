#!/usr/bin/env python3
"""Regenerates the marked blocks in README.md from their sources.

A block sits between `<!-- gen:NAME -->` and `<!-- /gen -->`. The only block today is
`routes`, the screen table, read from `ROUTES` in app/src/App.tsx through the same reader
`make docs-audit`'s `route rosters` row uses.

D18: this script writes, so it never runs on the commit path. `make docs-audit`'s
`readme blocks` row calls `render()` and compares. It never writes.

    scripts/readme_gen.py            print whether README.md is current
    scripts/readme_gen.py --write    rewrite the blocks
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
README = ROOT / "README.md"
BLOCK = re.compile(r"(<!-- gen:([\w-]+) -->\n)(.*?)(\n<!-- /gen -->)", re.S)


def routes() -> str:
    from docs_audit.hygiene import APP_TSX, app_routes

    rows, _, _ = app_routes()
    labels = dict(re.findall(r"path:\s*'(/[^']*)',\s*label:\s*'([^']*)'", APP_TSX.read_text(encoding="utf-8")))
    out = ["| Screen | Route | Note |", "|---|---|---|"]
    for path, group, _ in rows:
        out.append(f"| {labels.get(path, path)} | `#{path}` | {'Off-nav' if group == 'aside' else ''} |")
    return "\n".join(out)


GENERATORS = {"routes": routes}


def render(text: str) -> str:
    def fill(m: re.Match) -> str:
        gen = GENERATORS.get(m.group(2))
        return m.group(0) if gen is None else m.group(1) + gen() + m.group(4)

    return BLOCK.sub(fill, text)


if __name__ == "__main__":
    old = README.read_text(encoding="utf-8")
    new = render(old)
    if "--write" in sys.argv:
        README.write_text(new, encoding="utf-8")
    print("README.md is current." if new == old else "README.md is stale. Run with --write.")
