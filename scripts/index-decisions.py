#!/usr/bin/env python3
"""Generate CLAUDE.md's decision index from `docs/decisions/`.

THE INDEX IS DERIVED AND WAS HAND-MAINTAINED. Every entry appended to the corpus also
needed a line typed into CLAUDE.md, in the right place, spelled the same way — which is the
second half of the conflict the split exists to remove, and the half a directory does not
fix by itself. Two branches adding two files no longer collide in the corpus; without this
they still collide in the index.

WRITE-TIME, NEVER CHECK-TIME. D18 draws that line and this file is on the writing side of
it: it may edit CLAUDE.md and is therefore not on the commit path. The checking side is
`make docs-audit`'s `decision index` row, which computes what the index should say and
compares, and blocks. The two are deliberately separate programs — a generator that also
gated could satisfy itself, which is the exact failure D16 is written against.

THE HEADING IS THE SOURCE. Titles come from the `## D<id> — <title>` line inside each entry
file, never from the filename: a slug is lossy, truncated to 58 characters and sometimes
disambiguated with a numeric suffix, and it is a convenience for a human running `ls`.

ORDER IS THE MANIFEST'S. `docs/decisions/ORDER.json` records the order the chunks sat in
when they were one document, because three of them are not entries — Deferred, Someday and
the v1 bug table sat between D79 and D80 and still do. `decision index` reconciles the index
against the headings IN ORDER, so this has to emit that order rather than a sort.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = ROOT / "CLAUDE.md"

_ID = r"(?:[1-9][0-9]{0,2}|-[a-z][a-z0-9]*(?:-[a-z0-9]+)+)"
HEADING_RE = re.compile(r"^##\s+(D" + _ID + r")\s*[—-]\s*(.+)$")
# The index line's own shape, and the shape `decision index` locates the block by: an id,
# then the title. Width 4 plus a space is what the hand-maintained index used, and keeping it
# means this generator's first run produces no diff on an index that was already correct —
# which is how it was checked in.
LINE_RE = re.compile(r"^D" + _ID + r"\s")


def corpus(root: Path = ROOT):
    """`scripts/decisions_corpus.py` as seen from `root`.

    ROOT-AWARE because `make merge` reuses this at claim time and the claimer takes a
    `--root` — a throwaway checkout in the self-test, the PR's own branch at a merge. A
    module hard-wired to this file's parent would silently index the WRONG TREE, which is
    D43's defect in a different costume.
    """
    spec = importlib.util.spec_from_file_location(
        "decisions_corpus", root / "scripts" / "decisions_corpus.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = root
    module.DIRECTORY = root / "docs" / "decisions"
    module.MANIFEST = module.DIRECTORY / "ORDER.json"
    module.invalidate()
    return module


def wanted(root: Path = ROOT) -> List[str]:
    out: List[str] = []
    for path in corpus(root).files():
        match = HEADING_RE.match(path.read_text(encoding="utf-8").split("\n", 1)[0])
        if match:
            out.append(f"{match.group(1):<4} {match.group(2).strip()}")
    return out


def normalize(root: Path = ROOT, write: bool = False) -> List[str]:
    """Append every unregistered entry to the manifest, in corpus order. Returns what moved.

    THE MANIFEST IS WRITTEN AT THE MERGE AND NEVER BY A BRANCH. A branch adding an entry
    carries its own FILE and nothing shared; membership is derived until this runs. That is
    the same fact D140 makes about the number — what the final order is cannot be known
    until the moment of the merge, so it is settled there.
    """
    module = corpus(root)
    pending = module.unregistered()
    if not pending:
        return []
    path = module.MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["order"] = list(manifest["order"]) + pending
    if write:
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return pending


def rewrite_index(root: Path = ROOT, write: bool = False) -> bool:
    """Regenerate the index block in `root`'s CLAUDE.md. True when it changed."""
    claude = root / "CLAUDE.md"
    lines = claude.read_text(encoding="utf-8").split("\n")
    start, stop = locate(lines)
    want = wanted(root)
    if lines[start:stop] == want:
        return False
    if write:
        claude.write_text("\n".join(lines[:start] + want + lines[stop:]), encoding="utf-8")
    return True


def locate(lines: List[str]) -> Tuple[int, int]:
    """The index block's line range, found BY SHAPE.

    The same rule `decision index` uses: the first fenced block whose non-blank lines all
    look like index lines. Located by shape rather than by the heading above it, so
    re-titling the Map section cannot silently unhook either program from the other.
    """
    fence = None
    for n, line in enumerate(lines):
        if not line.lstrip().startswith("```"):
            continue
        if fence is None:
            fence = n
            continue
        body = [b for b in lines[fence + 1:n] if b.strip()]
        if body and all(LINE_RE.match(b) for b in body):
            return fence + 1, n
        fence = None
    raise SystemExit("no decision index found in CLAUDE.md — refusing to guess where it goes")


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="apply (default: preview)")
    args = ap.parse_args(argv)

    moved = normalize(ROOT, args.write)
    if moved:
        print(f"manifest: {len(moved)} entr{'y' if len(moved) == 1 else 'ies'} "
              f"{'appended' if args.write else 'would be appended'}: {', '.join(moved)}")
    lines = CLAUDE.read_text(encoding="utf-8").split("\n")
    start, stop = locate(lines)
    have = [b for b in lines[start:stop]]
    want = wanted()
    if have == want:
        print(f"index is current — {len(want)} entries, no change")
        return 0
    added = [w for w in want if w not in have]
    gone = [h for h in have if h not in want and h.strip()]
    print(f"index would change: {len(have)} lines -> {len(want)}")
    for line in added[:10]:
        print("  +", line[:100])
    for line in gone[:10]:
        print("  -", line[:100])
    if not args.write:
        print("\npreview only — pass --write to apply")
        return 0
    CLAUDE.write_text("\n".join(lines[:start] + want + lines[stop:]), encoding="utf-8")
    print(f"wrote {len(want)} index lines into CLAUDE.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
