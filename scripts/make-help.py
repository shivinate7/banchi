#!/usr/bin/env python3
"""`make help` — one line per target, derived from the Makefile's own comment above it.

THE MAKEFILE COMMENT IS THE ONLY SOURCE (token-budget audit, 2026-09-27, Q1). `make help`
used to carry a second, hand-typed copy of every target's purpose in a roughly 22 KB `@echo`
block, and CLAUDE.md's Commands section carried a third. The three had already drifted — the
`make hooks` one-line description differed between `help:` and CLAUDE.md. This renders the
summary straight off the comment above each target's rule, so there is exactly one place to
edit a description.

THE SUMMARY IS THE COMMENT'S FIRST SENTENCE, joined across its wrapped lines. A target with
no comment above it prints a note asking for one, rather than nothing — a silent gap here is
how the old three-copy drift went unnoticed for as long as it did.

Stdlib only, reads the Makefile as text and imports nothing project-side — the same rule
scripts/status.py, scripts/map-view.py and scripts/docs-audit.py follow: a tool that
describes the build must not run it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
MAKEFILE = ROOT / "Makefile"

_TARGET_RE = re.compile(r"^([A-Za-z0-9_-]+):")
_SENTENCE_RE = re.compile(r"(.+?[.!?])(\s|$)")

NO_COMMENT = "(no comment above this target — add one)"


def targets_and_summaries(text: str) -> List[Tuple[str, str]]:
    """Every target in file order, paired with its comment's first sentence.

    A target is a line matching `name:` that is not `.PHONY:`. Its comment is every
    contiguous `#`-prefixed line directly above it, with no blank line in between — the
    shape this Makefile already uses throughout. The first definition of a name wins, which
    matters nowhere here since this Makefile never redefines a target.
    """
    out: List[Tuple[str, str]] = []
    seen: Dict[str, bool] = {}
    pending: List[str] = []
    for line in text.split("\n"):
        if line.startswith("#"):
            pending.append(line[1:].strip())
            continue
        if line.startswith(".PHONY"):
            # Metadata, not a comment boundary — a `.PHONY:` line for OTHER targets can sit
            # between a comment and the target it actually describes (`lan-check`'s own
            # comment, split from it by the shared `.PHONY: janitor ...` line above it).
            continue
        match = _TARGET_RE.match(line)
        if match:
            name = match.group(1)
            if name not in seen:
                seen[name] = True
                paragraph = " ".join(p for p in pending if p)
                sentence = _SENTENCE_RE.match(paragraph)
                summary = sentence.group(1) if sentence else (paragraph or NO_COMMENT)
                out.append((name, summary))
            pending = []
            continue
        pending = []
    return out


def render(text: str) -> str:
    lines = ["PKMNSCAN — run `make status` for where the build actually stands.", ""]
    for name, summary in targets_and_summaries(text):
        if name == "help":
            continue
        lines.append(f"  make {name:<28} {summary}")
    lines.append("")
    lines.append("The full reasoning for any target sits in its own comment in the Makefile.")
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    del argv
    print(render(MAKEFILE.read_text(encoding="utf-8")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
