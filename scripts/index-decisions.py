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

the v1 bug table sat between two entries. This file no longer emits that order
into CLAUDE.md either — `decision index`'s own row is retired, the check side alongside the
write side, now that `make map ARGS=--decisions` renders the same list off the corpus (D60
amended) — but the manifest half stays, because a rendered view still needs a manifest to
render from.

DEBTS REUSE THIS EXACT MACHINERY, PARAMETERIZED, NOT A SECOND COPY. `docs/debts/` joined the
claim path (D140's own scheme) on the owner's word — the debts corpus was hand-numbered
before, `docs/debts/`'s own index hand-typed alongside it, which is the same collision this
file was built to remove for decisions. UNLIKE DECISIONS, `docs/debts/` KEEPS A WRITTEN
INDEX — no rendered view has replaced it yet, so `rewrite_index` still regenerates it at
claim time. `IndexSpec` below is the one difference between the two corpora: which corpus
module to load, which directory/manifest it owns, which file holds the index block (or would,
for decisions, if anything still read it), and whether the id CAPTURED FROM THE HEADING
already carries its own letter (a decision's does: `## D<n>` captures `D<n>`) or needs one
prefixed onto it (a debt's does not: `## 188` — or, once claimed through this scheme,
`## DEBT<n>` — captures a bare number either way, and the index always wants `DEBT<n>`).
`DECISION_SPEC` is every call site's default, so no existing caller's behaviour moves.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Callable, List, NamedTuple, Tuple

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = ROOT / "CLAUDE.md"

_ID = r"(?:[1-9][0-9]{0,2}|-[a-z][a-z0-9]*(?:-[a-z0-9]+)+)"


class IndexSpec(NamedTuple):
    corpus_script: str          # e.g. "decisions_corpus.py"
    directory: str              # e.g. "docs/decisions", relative to root
    stub_file: str              # the file carrying the index block, relative to root
    heading_re: re.Pattern      # first line -> (id AS THE INDEX LINE WANTS IT, title)
    line_re: re.Pattern         # matches one index line, for `locate`


# `## D<n> — Title` or `## D-<slug> — Title` — the captured id already carries its `D`,
# because a decision's HEADING IS its citation form (D160's own shape, unchanged here).
DECISION_HEADING_RE = re.compile(r"^##\s+(D" + _ID + r")\s*[—-]\s*(.+)$")
DECISION_LINE_RE = re.compile(r"^D" + _ID + r"\s")
DECISION_SPEC = IndexSpec("decisions_corpus.py", "docs/decisions", "CLAUDE.md",
                          DECISION_HEADING_RE, DECISION_LINE_RE)

# `## 188 — Title` (every real entry today) OR `## DEBT<n> — Title` (a newly claimed one —
# see the block comment above `DEBT_HEADING` in the shared merge tool for why a debt's
# heading may or may not carry the word) OR `## DEBT-<slug> — Title` (still unclaimed). The
# captured group never includes the literal `DEBT`, so the index line always PREFIXES it —
# `DEBT` + a number = `DEBT<n>`, `DEBT` + a slug = `DEBT-<slug>` — matching every line
# `docs/debts/`'s own index already carries (`DEBT1  The reverse direction...`).
DEBT_HEADING_RE = re.compile(r"^##\s+(?:DEBT)?([1-9][0-9]{0,2}|-[a-z][a-z0-9]*(?:-[a-z0-9]+)+)"
                             r"\s*[—-]\s*(.+)$")
DEBT_LINE_RE = re.compile(r"^DEBT(?:[1-9][0-9]{0,2}|-[a-z][a-z0-9]*(?:-[a-z0-9]+)+)\s")
DEBT_SPEC = IndexSpec("debts_corpus.py", "docs/debts", "docs/debts/README.md",
                      DEBT_HEADING_RE, DEBT_LINE_RE)


def _id_fmt(spec: IndexSpec) -> Callable[[str], str]:
    """The index-line id for one heading match, per spec — see `DEBT_HEADING_RE`'s own
    comment for why a debt's captured group needs `DEBT` prefixed and a decision's does not.
    """
    if spec is DEBT_SPEC:
        return lambda captured: "DEBT" + captured
    return lambda captured: captured


def corpus(root: Path = ROOT, spec: IndexSpec = DECISION_SPEC):
    """`spec.corpus_script` as seen from `root`.

    ROOT-AWARE because `make merge` reuses this at claim time and the claimer takes a
    `--root` — a throwaway checkout in the self-test, the PR's own branch at a merge. A
    module hard-wired to this file's parent would silently index the WRONG TREE, which is
    D43's defect in a different costume.
    """
    directory = root / spec.directory
    module_spec = importlib.util.spec_from_file_location(
        spec.corpus_script[:-3], root / "scripts" / spec.corpus_script)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    module.ROOT = root
    module.DIRECTORY = directory
    module.MANIFEST = module.DIRECTORY / "ORDER.json"
    module.invalidate()
    return module


def wanted(root: Path = ROOT, spec: IndexSpec = DECISION_SPEC) -> List[str]:
    out: List[str] = []
    fmt = _id_fmt(spec)
    for path in corpus(root, spec).files():
        match = spec.heading_re.match(path.read_text(encoding="utf-8").split("\n", 1)[0])
        if match:
            out.append(f"{fmt(match.group(1)):<4} {match.group(2).strip()}")
    return out


def normalize(root: Path = ROOT, write: bool = False, spec: IndexSpec = DECISION_SPEC) -> List[str]:
    """Append every unregistered entry to the manifest, in corpus order. Returns what moved.

    THE MANIFEST IS WRITTEN AT THE MERGE AND NEVER BY A BRANCH. A branch adding an entry
    carries its own FILE and nothing shared; membership is derived until this runs. That is
    the same fact D140 makes about the number — what the final order is cannot be known
    until the moment of the merge, so it is settled there.
    """
    module = corpus(root, spec)
    pending = module.unregistered()
    if not pending:
        return []
    path = module.MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["order"] = list(manifest["order"]) + pending
    if write:
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return pending


def rewrite_index(root: Path = ROOT, write: bool = False, spec: IndexSpec = DECISION_SPEC) -> bool:
    """Regenerate the index block in `root`'s `spec.stub_file`. True when it changed."""
    stub = root / spec.stub_file
    lines = stub.read_text(encoding="utf-8").split("\n")
    start, stop = locate(lines, spec)
    want = wanted(root, spec)
    if lines[start:stop] == want:
        return False
    if write:
        stub.write_text("\n".join(lines[:start] + want + lines[stop:]), encoding="utf-8")
    return True


def locate(lines: List[str], spec: IndexSpec = DECISION_SPEC) -> Tuple[int, int]:
    """The index block's line range, found BY SHAPE.

    The same rule `decision index`/`debt index` uses: the first fenced block whose non-blank
    lines all look like index lines. Located by shape rather than by the heading above it, so
    re-titling the section cannot silently unhook either program from the other.
    """
    fence = None
    for n, line in enumerate(lines):
        if not line.lstrip().startswith("```"):
            continue
        if fence is None:
            fence = n
            continue
        body = [b for b in lines[fence + 1:n] if b.strip()]
        if body and all(spec.line_re.match(b) for b in body):
            return fence + 1, n
        fence = None
    raise SystemExit(f"no index found in {spec.stub_file} — refusing to guess where it goes")


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="apply (default: preview)")
    ap.add_argument("--debts", action="store_true",
                    help="operate on docs/debts/ + docs/debts/README.md instead of decisions")
    args = ap.parse_args(argv)
    spec = DEBT_SPEC if args.debts else DECISION_SPEC

    moved = normalize(ROOT, args.write, spec)
    if moved:
        print(f"manifest: {len(moved)} entr{'y' if len(moved) == 1 else 'ies'} "
              f"{'appended' if args.write else 'would be appended'}: {', '.join(moved)}")
    else:
        print("manifest is current — nothing unregistered")

    # DECISIONS STOP HERE. CLAUDE.md no longer carries a decision index (D60 amended) — `make
    # map ARGS=--decisions` renders that list off the corpus, on demand, so there is no stub
    # left for this generator to rewrite. `docs/debts/` still hand-carries one, so the debt
    # spec's own `stub_file` still gets regenerated below.
    if spec is not DEBT_SPEC:
        if not moved:
            return 0
        if not args.write:
            print("\npreview only — pass --write to apply")
        return 0

    stub = ROOT / spec.stub_file
    lines = stub.read_text(encoding="utf-8").split("\n")
    start, stop = locate(lines, spec)
    have = [b for b in lines[start:stop]]
    want = wanted(ROOT, spec)
    if have == want:
        print(f"index is current — {len(want)} entries, no change")
        return 0
    if not args.write:
        print("\npreview only — pass --write to apply")
        return 0
    stub.write_text("\n".join(lines[:start] + want + lines[stop:]), encoding="utf-8")
    print(f"wrote {len(want)} index lines into {spec.stub_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
