#!/usr/bin/env python3
"""The debts corpus, read as one text or as one entry.

THE CORPUS IS A DIRECTORY AND WAS ONE FILE. `docs/debts/` holds one markdown file per
finding; `docs/DEBTS.md` is a stub that points at it and is read by nothing. This module is
the seam: every reader that used to open that path calls `text()` instead and gets the same
bytes, exactly as `scripts/decisions_corpus.py` already does for `docs/DECISIONS.md` (D160).

IDS ARE `§<n>` INSIDE THE CORPUS AND `DEBT<n>` EVERYWHERE ELSE (`docs/DEBTS.md`'s own "cite
by id" rule). A NUMBER IS NOW CLAIMED AT THE MERGE, REUSING THE DECISION MACHINERY (D140):
a branch writing a new finding gives it a slug heading, `## DEBT-<slug>`, in its own file
`docs/debts/DEBT-<slug>.md`, and cites it as `DEBT-<slug>`. `scripts/claim-ids.py` allocates
the next free debt number at merge time exactly as it does for a decision slug, renames the
file to `<n>-<tail>.md` (no letter — every real entry already sorts this way) and rewrites
every citation to `DEBT<n>`. `HEADING_RE` below reads either spelling a CLAIMED entry may
carry — the ~50 real entries head themselves bare (`## 11`), and one claimed through this
scheme heads itself `## DEBT<n>` — so no existing file moves. `docs/debts/ORDER.json` is the
historical numbering the file already carried, now extended by `settle_corpus` the same way
`docs/decisions/ORDER.json` is. `§15` stays a deliberate gap forever (it left 2026-09-07,
D120's own close) — a claimed number is `max + 1` against what `docs/debts/` holds, never the
lowest free one, so a gap is never resurrected onto an entry it was never about.

ORDER IS THE MANIFEST'S, NOT THE FILESYSTEM'S — a zero-padded filename already sorts
correctly, but the manifest is still the one source `verify()`/`text()` trust, the same
argument `decisions_corpus.py` makes for its own manifest.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DIRECTORY = ROOT / "docs" / "debts"
MANIFEST = DIRECTORY / "ORDER.json"
STUB = ROOT / "docs" / "DEBTS.md"

# OPTIONAL `DEBT`: a real entry heads itself bare (`## 11`), and one claimed through
# `scripts/claim-ids.py`'s scheme heads itself `## DEBT<n>` (its heading matches its
# citation, same as a decision's) — see that file's own comment above `DEBT_HEADING`. Either
# way the captured group is the bare number, so `path_for`/`idents` need no change.
HEADING_RE = re.compile(r"^##\s+(?:DEBT)?([0-9]+)\b")

_cache: Dict[str, object] = {}


def _rank(name: str) -> tuple:
    stem = name[:-3] if name.endswith(".md") else name
    head = stem.split("-", 1)[0]
    if head.isdigit():
        return (0, int(head), name)
    return (1, 0, name)


def order() -> List[str]:
    """Corpus order: the manifest's list, then anything on disk it has not been told about."""
    if "order" not in _cache:
        listed = json.loads(MANIFEST.read_text(encoding="utf-8"))["order"]
        known = set(listed)
        extra = sorted((p.name for p in DIRECTORY.glob("*.md") if p.name not in known),
                       key=_rank)
        _cache["order"] = listed + extra
    return list(_cache["order"])


def unregistered() -> List[str]:
    listed = set(json.loads(MANIFEST.read_text(encoding="utf-8"))["order"])
    return sorted((p.name for p in DIRECTORY.glob("*.md") if p.name not in listed), key=_rank)


def files() -> List[Path]:
    return [DIRECTORY / name for name in order() if (DIRECTORY / name).exists()]


def text() -> str:
    """The whole corpus as the single document it used to be.

    Byte-identical to the pre-split `docs/DEBTS.md`, asserted by
    `scripts/split-debts.py --verify` and re-run by `scripts/split-debts.py --selftest`
    (not yet wired into `make`).
    """
    if "text" not in _cache:
        _cache["text"] = "\n".join(p.read_text(encoding="utf-8") for p in files())
    return str(_cache["text"])


def path_for(ident: str) -> Optional[Path]:
    """The file holding one entry, or None.

    `ident` is the bare number (`"11"`) or the `DEBT<n>` id form (`"DEBT11"`) — the second
    is what a citation outside `docs/debts/` is required to spell (the stub's own "CITE BY
    ID" rule), and this accepts both so a caller does not have to strip the prefix itself.
    """
    number = ident[4:] if ident.upper().startswith("DEBT") else ident
    for path in files():
        head = path.read_text(encoding="utf-8").split("\n", 1)[0]
        match = HEADING_RE.match(head)
        if match and match.group(1) == number:
            return path
    return None


def idents() -> List[str]:
    """Every entry number, in corpus order. The preamble is not an entry."""
    out = []
    for path in files():
        match = HEADING_RE.match(path.read_text(encoding="utf-8").split("\n", 1)[0])
        if match:
            out.append(match.group(1))
    return out


def invalidate() -> None:
    """Drop the cache. For a caller that has just written to the directory."""
    _cache.clear()
