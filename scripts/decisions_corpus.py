#!/usr/bin/env python3
"""The decision corpus, read as one text or as one entry.

THE CORPUS IS A DIRECTORY AND WAS ONE FILE. `docs/decisions/` holds one markdown file per
entry; `docs/decisions/README.md` points at it and is read by nothing. This module
is the seam: every reader that used to open the old single file calls `text()` instead and
gets the same bytes, so the split changed where the corpus LIVES without changing what any checker
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

ORDER IS THE MANIFEST'S, NOT THE FILESYSTEM'S. `ORDER.json` records the order of the
chunks, with the preamble, which is not an entry, first. Sorting by filename would move it, and
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
STUB = ROOT / "docs" / "decisions" / "README.md"

# scripts/prose-guard.py's `_ID`, which is scripts/docs_audit/records.py's `_ID_ANY`: a number, or a
# claim slug a branch writes and `make merge` substitutes. Spelled here a third time rather
# than imported because this module is imported BY those two and a cycle would be worse than
# a duplicated regex — `make docs-audit`'s `claim vocabulary` row is what keeps the three in
# step, and it already did that job when they were two.
_ID = r"(?:[1-9][0-9]{0,2}|-[a-z][a-z0-9]*(?:-[a-z0-9]+)+)"
HEADING_RE = re.compile(r"^##\s+(D" + _ID + r")\b")

_cache: Dict[str, object] = {}


def _rank(name: str) -> tuple:
    """Where an unregistered file sorts: numbered entries by number, slugs last.

    A CLAIM SLUG SORTS AFTER EVERY NUMBER, and that is not what a plain string sort does —
    `-` is 0x2D and `0` is 0x30, so a slug-named file sorts BEFORE a zero-padded number and
    an unclaimed entry would land at the top of the corpus instead of the bottom. It is by
    definition the newest thing in the tree.
    """
    stem = name[:-3] if name.endswith(".md") else name
    head = stem.split("-", 1)[0]
    if head.startswith("D") and head[1:].isdigit():
        return (0, int(head[1:]), name)
    return (1, 0, name)


def order() -> List[str]:
    """Corpus order: the manifest's list, then anything on disk it has not been told about.

    A BRANCH ADDING AN ENTRY TOUCHES ONLY ITS OWN FILE. The manifest was the second shared
    surface hiding inside this change — every entry-adding branch appending to one JSON array
    at the same position is the collision this split exists to remove, wearing a different
    file extension. So membership is DERIVED: the manifest pins the order of what it knows,
    which is what keeps the preamble first, and a file it has
    never heard of is appended rather than rejected.

    `make merge` normalizes the manifest at claim time, which is the one moment the final
    order is knowable — the same argument D140 makes for the number itself. Until then an
    unregistered entry is corpus content, not an error.

    A file the manifest names that is NOT on disk stays an error, because that is real damage
    rather than a branch in flight; `make decisions-selftest` is what reports it.
    """
    if "order" not in _cache:
        listed = json.loads(MANIFEST.read_text(encoding="utf-8"))["order"]
        known = set(listed)
        extra = sorted((p.name for p in DIRECTORY.glob("*.md")
                        if p.name not in known and p.name != "README.md"),
                       key=_rank)
        _cache["order"] = listed + extra
    return list(_cache["order"])  # a copy: callers sort and filter it


def unregistered() -> List[str]:
    """Entry files on disk that the manifest has not been told about."""
    listed = set(json.loads(MANIFEST.read_text(encoding="utf-8"))["order"])
    return sorted((p.name for p in DIRECTORY.glob("*.md")
                   if p.name not in listed and p.name != "README.md"), key=_rank)


def files() -> List[Path]:
    return [DIRECTORY / name for name in order() if (DIRECTORY / name).exists()]


def text() -> str:
    """The whole corpus as the single document it used to be.

    Byte-identical to the pre-split `docs/decisions/`, which is asserted rather than
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


_SUPERSEDED_BODY = re.compile(r"^\*\*(?:Superseded|Overtaken) by (D" + _ID + r")\b")
_SUPERSEDED_HEADING = re.compile(r"^#{2,4} Superseded( in part)?\b.*?`(D" + _ID + r")`")


def supersession(ident: str) -> Optional[Dict[str, str]]:
    """How an entry says it was superseded: `{"kind": "full"|"part", "by": "D<id>"}`, or None.

    THE CORPUS HAS NO STATUS FIELD, so this reads the two forms an entry uses: a first line
    `**Superseded by D<n>` or `**Overtaken by D<n>` (the whole entry), and a heading
    `### Superseded [in part] <date> — `D<n>`` (the whole entry, or the part it names). A
    supersession written in ordinary prose elsewhere in an entry is NOT read, so a decision
    that a later entry overtakes without leaving one of these marks reads as current.
    """
    path = path_for(ident)
    if path is None:
        return None
    lines = path.read_text(encoding="utf-8").split("\n")
    for line in lines[1:4]:
        m = _SUPERSEDED_BODY.match(line.strip())
        if m:
            return {"kind": "full", "by": m.group(1)}
    for line in lines[1:]:
        m = _SUPERSEDED_HEADING.match(line)
        if m:
            return {"kind": "part" if m.group(1) else "full", "by": m.group(2)}
    return None


def invalidate() -> None:
    """Drop the cache. For a caller that has just written to the directory."""
    _cache.clear()
