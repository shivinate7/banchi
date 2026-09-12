#!/usr/bin/env python3
"""The decision corpus, read as one text or as one entry.

THE CORPUS IS A DIRECTORY AND WAS ONE FILE. `docs/decisions/` holds one markdown file per
entry; `docs/DECISIONS.md` is a stub that points at it and is read by nothing. This module
is the seam: every reader that used to open that path calls `text()` instead and gets the
same bytes, so the split changed where the corpus LIVES without changing what any checker
parses. That is deliberate — a split that also rewrote eleven audit rows would have been
two changes wearing one diff, and only one of them provable.

WHY A DIRECTORY. Two pull requests appending an entry to one file conflict textually every
single time; it happened five times on 2026-09-11 alone, each costing a hand resolution of
a 10,000-line file. Two pull requests ADDING TWO FILES never conflict. That is the whole
change, and everything else here exists to keep the readers working across it.

WHY THIS MAKES D60 BETTER RATHER THAN WORSE. D60 dropped the `@` because the file cost
~163,000 tokens to load and a session needs one entry at a time. The monolith made "one
entry" a thing you could only get by parsing; a directory makes it a thing you can open.
`path_for("D58")` is now a real answer, and `scripts/decision-context.py` names a file a
session can read rather than a region of a file it must not.

ORDER IS THE MANIFEST'S, NOT THE FILESYSTEM'S. `ORDER.json` records the order the chunks
sat in, because three of them are not entries at all — Deferred, Someday and the v1 bug
table sat between D79 and D80 and still do. Sorting by filename would move them, and
`decision index` reconciles the index against the headings IN ORDER, so the order is data
rather than a convention anybody could re-derive.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DIRECTORY = ROOT / "docs" / "decisions"
MANIFEST = DIRECTORY / "ORDER.json"
STUB = ROOT / "docs" / "DECISIONS.md"

# scripts/prose-guard.py's `_ID`, which is scripts/docs-audit.py's `_ID_ANY`: a number, or a
# claim slug a branch writes and `make merge` substitutes. Spelled here a third time rather
# than imported because this module is imported BY those two and a cycle would be worse than
# a duplicated regex — `make docs-audit`'s `claim vocabulary` row is what keeps the three in
# step, and it already did that job when they were two.
_ID = r"(?:[1-9][0-9]{0,2}|-[a-z][a-z0-9]*(?:-[a-z0-9]+)+)"
HEADING_RE = re.compile(r"^##\s+(D" + _ID + r")\b")

_cache: Dict[str, object] = {}


def order() -> List[str]:
    """The manifest's filenames, in corpus order."""
    if "order" not in _cache:
        _cache["order"] = json.loads(MANIFEST.read_text(encoding="utf-8"))["order"]
    return list(_cache["order"])  # a copy: callers sort and filter it


def files() -> List[Path]:
    return [DIRECTORY / name for name in order()]


def text() -> str:
    """The whole corpus as the single document it used to be.

    Byte-identical to the pre-split `docs/DECISIONS.md`, which is asserted rather than
    claimed: `scripts/split-decisions.py --verify` diffs this reassembly against the
    original bytes, and `make decisions-selftest` runs it.
    """
    if "text" not in _cache:
        _cache["text"] = "\n".join(p.read_text(encoding="utf-8") for p in files())
    return str(_cache["text"])


def path_for(ident: str) -> Optional[Path]:
    """The file holding one entry, or None.

    THE HEADING IS THE AUTHORITY, NOT THE FILENAME. A slug is a convenience and may be
    stale, truncated or disambiguated with a suffix; the `## D<id>` line inside the file is
    what identifies it. `make merge` substitutes a claim slug for a number and renames the
    file, and it is this function that has to keep answering across that.
    """
    for path in files():
        head = path.read_text(encoding="utf-8").split("\n", 1)[0]
        match = HEADING_RE.match(head)
        if match and match.group(1) == ident:
            return path
    return None


def idents() -> List[str]:
    """Every entry id, in corpus order. Sections and the preamble are not entries."""
    out = []
    for path in files():
        match = HEADING_RE.match(path.read_text(encoding="utf-8").split("\n", 1)[0])
        if match:
            out.append(match.group(1))
    return out


def invalidate() -> None:
    """Drop the cache. For a caller that has just written to the directory."""
    _cache.clear()
