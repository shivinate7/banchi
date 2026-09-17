#!/usr/bin/env python3
"""The gates corpus, read as one text — `scripts/decisions_corpus.py`'s twin.

`docs/gates/` holds one markdown file per record, in THREE kind folders (`contract/` for the
harness's own `Tn` thresholds, `gate-runs/` for the Gate A/B/C run records and their addenda,
`steps/` for the build-order's SHIPPED and OPEN lists); `docs/GATES.md` is a stub that points
at it and is read by nothing. This module is the seam: every reader that used to open that
path calls `text()` instead and gets the same bytes, so the split changed where the corpus
LIVES without changing what any checker parses — `scripts/docs-audit.py`'s `gates_sections()`,
`check_id_claims()` and `check_build_order_mirror()` are unmodified by the split beyond
reading `text()` in place of the file.

ORDER IS THE MANIFEST'S, NOT THE FILESYSTEM'S — the same rule `decisions_corpus.py` states
for the same reason. Four container chunks (the whole-file preamble, and the intro prose
under each of `## The harness is the contract`, `## Gates`, `## What shipped` and
`## What is open`) sit interleaved with the entries and are not entries themselves; sorting
by filename would not reproduce the interleaving, so `ORDER.json`'s flat `order` list is what
`text()` concatenates.

STEPS CARRY THEIR OWN LIST, BECAUSE SORTING THEM WOULD LIE. `ORDER.json["steps"]` is
`{"shipped": [...ids in landing-date order...], "open": [...ids, deliberately unordered...]}`.
Never derive a step's list membership from where its file sorts in `steps/` — an id assigned
after a later one (the hole at step 12, `step 020` following `step 011`) already proves the
directory's own sort order is not the SHIPPED order, and OPEN's whole point (D80) is that it
has none to reconstruct.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DIRECTORY = ROOT / "docs" / "gates"
MANIFEST = DIRECTORY / "ORDER.json"
STUB = ROOT / "docs" / "GATES.md"

_cache: Dict[str, object] = {}


def _manifest() -> dict:
    if "manifest" not in _cache:
        _cache["manifest"] = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return _cache["manifest"]  # type: ignore[return-value]


def order() -> List[str]:
    """Corpus order: the manifest's list, then anything on disk it has not been told about
    (a branch adding a step or a run mid-flight — normalized by `make merge`, same as
    `decisions_corpus.order()`)."""
    if "order" not in _cache:
        listed = _manifest()["order"]
        known = set(listed)
        extra = sorted(str(p.relative_to(DIRECTORY)) for p in DIRECTORY.glob("**/*.md")
                        if str(p.relative_to(DIRECTORY)) not in known)
        _cache["order"] = listed + extra
    return list(_cache["order"])  # a copy: callers sort and filter it


def unregistered() -> List[str]:
    listed = set(_manifest()["order"])
    return sorted(str(p.relative_to(DIRECTORY)) for p in DIRECTORY.glob("**/*.md")
                  if str(p.relative_to(DIRECTORY)) not in listed)


def files() -> List[Path]:
    return [DIRECTORY / name for name in order() if (DIRECTORY / name).exists()]


def text() -> str:
    """The whole corpus as the single document it used to be.

    Byte-identical to the pre-split `docs/GATES.md`, asserted rather than claimed:
    `scripts/split-gates.py --verify` diffs this reassembly against the original bytes, and
    `make gates-selftest` runs the ongoing half of that proof.
    """
    if "text" not in _cache:
        _cache["text"] = "\n".join(p.read_text(encoding="utf-8") for p in files())
    return str(_cache["text"])


def tests() -> List[str]:
    """Every harness-contract id (`T1` .. `T9`), in corpus order."""
    return list(_manifest().get("tests") or [])


def runs() -> List[str]:
    """Every gate-run id (`GateA`, `GateB`, `GateB-note1`, ...), in corpus order."""
    return list(_manifest().get("runs") or [])


def steps(list_name: Optional[str] = None) -> List[str]:
    """Build-order step ids. `list_name` is `"shipped"`, `"open"`, or omitted for both,
    shipped first — never a single sorted union, because that would erase which list an id
    is in, which is the fact `build order mirror` reconciles against `docs/map.py`."""
    both = _manifest().get("steps") or {"shipped": [], "open": []}
    if list_name is not None:
        return list(both.get(list_name) or [])
    return list(both.get("shipped") or []) + list(both.get("open") or [])


def invalidate() -> None:
    """Drop the cache. For a caller that has just written to the directory."""
    _cache.clear()
