#!/usr/bin/env python3
"""Register every unregistered `docs/decisions/` entry into `docs/decisions/ORDER.json`.

FORMERLY ALSO WROTE CLAUDE.md'S DECISION INDEX. That half is retired: CLAUDE.md no longer
hand-carries an index for a corpus this size to drift against. `make map ARGS=--decisions`
renders the same id-and-title list straight off the corpus's own headings, on demand, so
there is no second copy left for a branch's entry to collide on or go missing from. This
file's remaining job is the manifest half, which a rendered view cannot replace: a branch
still adds only its own entry FILE, and something still has to fold that file into the
corpus's shared ORDER — this generator, at claim time, is that something.

WRITE-TIME, NEVER CHECK-TIME (D18). This file may edit `docs/decisions/ORDER.json` and is
therefore not on the commit path. The corpus's own non-vacuity floor (`corpus_is_empty` in
`scripts/docs-audit.py`) is the checking side, and the two stay separate programs — a
generator that also gated could satisfy itself, which is the exact failure D16 is written
against.

THE HEADING IS THE SOURCE. An entry's id and title come from its own `## D<id> — <title>`
line, never from the filename: a slug is lossy, truncated to 58 characters and sometimes
disambiguated with a numeric suffix, and it is a convenience for a human running `ls`.

ORDER IS THE MANIFEST'S. `docs/decisions/ORDER.json` records the order the chunks sat in
when they were one document, because three of them are not entries — Deferred, Someday and
the v1 bug table sat between D79 and D80 and still do.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent


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


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="apply (default: preview)")
    args = ap.parse_args(argv)

    moved = normalize(ROOT, args.write)
    if not moved:
        print("manifest is current — nothing unregistered")
        return 0
    print(f"manifest: {len(moved)} entr{'y' if len(moved) == 1 else 'ies'} "
          f"{'appended' if args.write else 'would be appended'}: {', '.join(moved)}")
    if not args.write:
        print("\npreview only — pass --write to apply")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
