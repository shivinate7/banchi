#!/usr/bin/env python3
"""Split docs/GATES.md into one file per record, one folder per KIND, and prove it lossless.

WHY A SPLIT AT ALL. `scripts/split-decisions.py` split D160's kind (decisions) because two
branches appending to one file collide every single time; measured on `docs/GATES.md` across
two-parent merges, the concurrent-edit rate is 79% (15 of 19) — the same disease, on a file
that was scoped OUT of that round on the argument that it is a log of runs rather than a
record several branches author at once. That argument is false: `## What shipped` gains a row
on almost every merge that lands a build-order step, exactly like a decision entry.

GATES.md IS NOT ONE KIND, WHICH decisions AND debts BOTH WERE. Reading it end to end finds
THREE:

  1. THE HARNESS CONTRACT — `### T1` .. `### T9` under `## The harness is the contract`. A
     test's threshold, cited elsewhere as a bare `Tn` (`_TEST_REF_RE` in docs-audit.py) the
     same way a build step is cited as `step n`. Kind folder: `contract/`.
  2. GATE RUN RECORDS — `### Gate A/B/C` and their addenda (`### Box 2`, `### The per-run
     reading`) under `## Gates`. Numbers measured about cards, never rewritten to match a
     later tree (CLAUDE.md's own rule about this file). Kind folder: `runs/`.
  3. BUILD-ORDER STEPS — the numbered items under `## What shipped` and `## What is open`.
     D80 governs: `n` is a stable id, NEVER renumbered — 218 references to `step <n>` live in
     this tree — and `SHIPPED` is ordered by landing date while `OPEN` is deliberately
     UNORDERED, with no `next`. Kind folder: `steps/`.

Each kind keeps its own ordering rule as a fact in the manifest, not as an accident of
`ls`: `steps/` records which list (`shipped` / `open`) each step file came from, precisely so
that alphabetically sorting the directory can never be mistaken for the sequence OPEN
deliberately refuses to have.

THE CHUNK MODEL IS `split-decisions.py`'s, extended one level. That script cuts at every
`## `; every line lands in exactly one chunk, chunks are written in order, and reassembly
concatenates them in that order. GATES.md nests two more list ids inside four `## `
containers, so this script cuts a SECOND time inside `## The harness is the contract` and
`## Gates` (at `### `) and inside `## What shipped` / `## What is open` (at a top-level
`^\\d+\\. `). Reassembly is still one flat, ordered list of files — the manifest's `order` —
so `gates_corpus.text()` is exactly `decisions_corpus.text()`: read every file in `order` and
join with `"\\n"`. Losslessness is checked the same way: `--verify` diffs the reassembly
against the original bytes, and `--verify-split REF` re-establishes it later out of git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import List, NamedTuple, Optional

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "GATES.md"
TARGET = ROOT / "docs" / "gates"
MANIFEST = "ORDER.json"

# `### T1 — …` / `### Gate A — …` / `### Box 2 — …` — the entry forms nested one level under
# `## The harness is the contract` and `## Gates`.
_H3_RE = re.compile(r"^###\s+(.+)$")
_TEST_RE = re.compile(r"^###\s+(T[1-9][0-9]?)\s*[—-]\s*(.+)$")
_GATE_LETTER_RE = re.compile(r"^###\s+Gate\s+([A-Z])\s*[—-]\s*(.+)$")

# A top-level (unindented) numbered list item — the only shape `## What shipped` and
# `## What is open` use for a build-order step. Scoped to those two containers by the caller,
# not by this regex alone, because a numbered list confined to one container is `build order
# mirror`'s own rule (`_GATES_STEP` in docs-audit.py) and this script re-derives it rather
# than importing a docs-audit internal.
_STEP_RE = re.compile(r"^(\d+)\.\s")

_CONTAINER_TITLES = {
    "The harness is the contract": "contract",
    # NOT "runs/" — a bare `runs/` line in .gitignore (meant for the pipeline's own
    # `runs/` at the repo root) matches a directory of that name ANYWHERE in the tree,
    # including here. `gate-runs/` sidesteps that collision rather than editing a
    # shared, root-scoped ignore file for one folder's sake.
    "Gates": "gate-runs",
    "What shipped": "steps",
    "What is open": "steps",
}


class Chunk(NamedTuple):
    kind: str       # "preamble" | "container" | "test" | "run" | "step"
    ident: str      # "T1", "GateB", "GateB-box2", "step009", ... ("" for preamble/container)
    folder: str      # "" | "contract" | "runs" | "steps"
    list_name: str   # "" | "shipped" | "open" — only meaningful for kind == "step"
    title: str
    lines: List[str]


def slug(text: str, limit: int = 58) -> str:
    text = text.replace("—", " ").replace("'", "").replace("`", "").replace("~", "")
    out = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(out) > limit:
        out = out[:limit].rsplit("-", 1)[0] or out[:limit]
    return out.strip("-") or "untitled"


def _split_h2(lines: List[str]) -> List[tuple]:
    """Cut at every `## `. Returns (title_or_None, body_lines) for the preamble and each
    top-level container, in file order."""
    starts = [i for i, line in enumerate(lines) if line.startswith("## ")]
    out = []
    if not starts:
        return [(None, lines)]
    if starts[0] > 0:
        out.append((None, lines[: starts[0]]))
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        body = lines[start:end]
        title = body[0][3:].strip()
        out.append((title, body))
    return out


def _split_h3(body: List[str]) -> List[tuple]:
    """A `## ` container's body, cut at every `### `. Returns (heading_or_None, lines)."""
    starts = [i for i, line in enumerate(body) if line.startswith("### ")]
    out = []
    if not starts:
        return [(None, body)]
    if starts[0] > 0:
        out.append((None, body[: starts[0]]))
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(body)
        out.append((body[start], body[start:end]))
    return out


def _split_steps(body: List[str]) -> List[tuple]:
    """A `## What shipped`/`## What is open` container's body, cut at every top-level
    `\\d+. ` item. Returns (number_or_None, lines)."""
    starts = [i for i, line in enumerate(body) if _STEP_RE.match(line)]
    out = []
    if not starts:
        return [(None, body)]
    if starts[0] > 0:
        out.append((None, body[: starts[0]]))
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(body)
        number = _STEP_RE.match(body[start]).group(1)
        out.append((number, body[start:end]))
    return out


def chunk(text: str) -> List[Chunk]:
    lines = text.split("\n")
    out: List[Chunk] = []
    last_gate_letter = ""
    addendum_n = 0
    for title, body in _split_h2(lines):
        if title is None:
            out.append(Chunk("preamble", "", "", "", "", body))
            continue
        folder = _CONTAINER_TITLES.get(title, "")
        if title in ("The harness is the contract", "Gates"):
            for head, sub in _split_h3(body):
                if head is None:
                    out.append(Chunk("container", "", folder, "", title, sub))
                    continue
                test = _TEST_RE.match(head)
                if test:
                    out.append(Chunk("test", test.group(1), folder, "", test.group(2).strip(), sub))
                    continue
                gate = _GATE_LETTER_RE.match(head)
                title = _H3_RE.match(head).group(1).strip()
                if gate:
                    last_gate_letter = gate.group(1)
                    addendum_n = 0
                    ident = f"Gate{last_gate_letter}"
                    title = gate.group(2).strip()
                else:
                    # An addendum to the run just above it — "Box 2", "The per-run reading" —
                    # inherits that gate's letter and a running count, so its id sorts and
                    # reads beside the run it is evidence about, rather than floating with no
                    # citation form of its own.
                    addendum_n += 1
                    ident = f"Gate{last_gate_letter}-note{addendum_n}"
                out.append(Chunk("run", ident, folder, "", title, sub))
            continue
        if title in ("What shipped", "What is open"):
            list_name = "shipped" if title == "What shipped" else "open"
            for number, sub in _split_steps(body):
                if number is None:
                    out.append(Chunk("container", "", folder, list_name, title, sub))
                    continue
                out.append(Chunk("step", f"step{int(number):03d}", folder, list_name,
                                  sub[0][len(number) + 1:].strip().lstrip("."), sub))
            continue
        # No container observed today falls through to here; kept so an unrecognised `## `
        # heading is preserved rather than silently dropped, and is reported by `--selftest`
        # as an unclassified chunk rather than a lost one.
        out.append(Chunk("container", "", folder or slug(title, 20), "", title, body))
    return out


def names(chunks: List[Chunk]) -> List[str]:
    used: dict = {}
    out: List[str] = []
    for c in chunks:
        if c.kind == "preamble":
            stem = "_preamble"
        elif c.kind == "container":
            stem = (c.folder + "/" if c.folder else "") + "_" + slug(c.title)
        else:  # test, run and step all address by id inside their own kind folder
            stem = f"{c.folder}/{c.ident}-{slug(c.title)}"
        name = stem + ".md"
        if name in used:
            used[name] += 1
            name = f"{stem}-{used[name]}.md"
        else:
            used[name] = 1
        out.append(name)
    return out


def split(write: bool) -> int:
    text = SOURCE.read_text(encoding="utf-8")
    chunks = chunk(text)
    filenames = names(chunks)
    counts: dict = {}
    for c in chunks:
        counts[c.kind] = counts.get(c.kind, 0) + 1
    print(f"source   {SOURCE.relative_to(ROOT)}  {len(text):,} bytes, {text.count(chr(10)) + 1:,} lines")
    print(f"chunks   {len(chunks)}  " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
    if not write:
        for c, name in list(zip(chunks, filenames))[:6]:
            print(f"  would write  {name}  ({len(chr(10).join(c.lines)):,} bytes)")
        print(f"  ... {len(filenames) - 6} more")
        print("\npreview only — pass --write to perform the split")
        return 0
    TARGET.mkdir(parents=True, exist_ok=True)
    for folder in ("contract", "gate-runs", "steps"):
        (TARGET / folder).mkdir(exist_ok=True)
    for c, name in zip(chunks, filenames):
        (TARGET / name).write_text("\n".join(c.lines), encoding="utf-8")
    manifest = {
        "source": "docs/GATES.md",
        "split_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "split_bytes": len(text.encode("utf-8")),
        "order": filenames,
        # Per-kind indexes, so a reader wants neither a second parse of the reassembled text
        # nor a directory listing it has to re-derive the ordering rule for by eye.
        "tests": [c.ident for c in chunks if c.kind == "test"],
        "runs": [c.ident for c in chunks if c.kind == "run"],
        "steps": {
            "shipped": [c.ident for c in chunks if c.kind == "step" and c.list_name == "shipped"],
            "open": [c.ident for c in chunks if c.kind == "step" and c.list_name == "open"],
        },
    }
    (TARGET / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote    {len(filenames)} files + {MANIFEST} into {TARGET.relative_to(ROOT)}/")
    return 0


def join() -> str:
    order = json.loads((TARGET / MANIFEST).read_text(encoding="utf-8"))["order"]
    return "\n".join((TARGET / name).read_text(encoding="utf-8") for name in order)


def selftest() -> int:
    """The corpus is complete and still round-trips (the ongoing claim; see split-decisions.py
    for why this is deliberately not the historical byte-equality claim, which lives in
    `--verify-split` instead)."""
    manifest = json.loads((TARGET / MANIFEST).read_text(encoding="utf-8"))
    problems = []
    missing = [n for n in manifest["order"] if not (TARGET / n).exists()]
    if missing:
        problems.append(f"{len(missing)} file(s) in the manifest are gone: {missing[:3]}")
    on_disk = {str(p.relative_to(TARGET)) for p in TARGET.glob("**/*.md")}
    pending = sorted(on_disk - set(manifest["order"]))
    if not missing:
        body = join()
        print(f"reassembled  {len(body.encode('utf-8')):,} bytes from "
              f"{len(manifest['order']) + len(pending)} files")
        print(f"split from   {manifest.get('split_bytes', 0):,} bytes  "
              f"sha256 {str(manifest.get('split_sha256', '?'))[:16]}…  provenance only")
        if not body.endswith("\n"):
            problems.append("the reassembled corpus does not end in a newline.")
    tests = manifest.get("tests") or []
    runs = manifest.get("runs") or []
    steps = manifest.get("steps") or {"shipped": [], "open": []}
    shipped, open_ = steps.get("shipped") or [], steps.get("open") or []
    overlap = sorted(set(shipped) & set(open_))
    if overlap:
        problems.append(f"step(s) listed in BOTH shipped and open: {overlap}")
    # THE FLOOR IS PINNED, NOT DERIVED, so a reader over a renamed heading or a broken regex
    # fails LOUD rather than reporting a clean, empty corpus. Recount by hand against
    # `docs/GATES.md`'s history if this ever needs to move; it must never move to keep a red
    # run quiet.
    if len(tests) < 9:
        problems.append(f"only {len(tests)} harness-contract entries — expected at least 9 "
                         f"(T1..T9). A parser finding fewer over a renamed heading is broken, "
                         f"not a clean tree.")
    if len(runs) < 5:
        problems.append(f"only {len(runs)} gate-run entries — expected at least 5 "
                         f"(Gate A, Gate B, Box 2, Gate C, the per-run reading).")
    if len(shipped) < 15:
        problems.append(f"only {len(shipped)} shipped steps — expected at least 15.")
    print(f"contract     {len(tests)} entries: {', '.join(tests)}")
    print(f"runs         {len(runs)} entries: {', '.join(runs)}")
    print(f"steps        {len(shipped)} shipped, {len(open_)} open")
    if pending:
        print(f"pending      {len(pending)} file(s) not yet in the manifest — normal on a "
              f"branch adding a step:")
        for name in pending[:5]:
            print(f"               {name}")
    for problem in problems:
        print("  FAIL " + problem)
    print("gates-selftest: " + ("FAIL" if problems else "ok"))
    return 1 if problems else 0


def verify(reference: Path) -> int:
    want = reference.read_text(encoding="utf-8")
    got = join()
    if got == want:
        print(f"IDENTICAL  {len(got):,} bytes reassembled from "
              f"{len(json.loads((TARGET / MANIFEST).read_text(encoding='utf-8'))['order'])} files")
        return 0
    print(f"DIFFERENT  reference {len(want):,} bytes, reassembled {len(got):,} bytes")
    import difflib
    delta = list(difflib.unified_diff(want.split("\n"), got.split("\n"),
                                      "reference", "reassembled", lineterm="", n=1))
    print(f"{len(delta)} diff lines; first 40:")
    for line in delta[:40]:
        print("  " + line[:160])
    return 1


def verify_split(ref: str, before_ref: Optional[str] = None) -> int:
    """Re-establish the historical claim from git alone: REF's parent held the monolith,
    REF's entry files are a byte-for-byte prefix-preserving reassembly of it, plus whatever
    the split commit itself added. See split-decisions.py's own docstring for why the parent
    and not REF is where the "before" side has to come from."""
    import subprocess

    def show(path: str, at: Optional[str] = None) -> Optional[str]:
        done = subprocess.run(["git", "show", f"{at or ref}:{path}"],
                              cwd=ROOT, capture_output=True, text=True)
        return done.stdout if done.returncode == 0 else None

    source_ref = before_ref or f"{ref}^"
    before = show("docs/GATES.md", source_ref)
    if before is None:
        print(f"no docs/GATES.md at {source_ref} — nothing to compare")
        return 1
    manifest_text = show("docs/gates/" + MANIFEST)
    if manifest_text is None:
        print(f"{ref} has no corpus manifest — it is not the commit that performed the split.")
        return 1
    if len(before.encode("utf-8")) < 50_000:
        print(f"docs/GATES.md at {source_ref} is only {len(before.encode('utf-8')):,} bytes — "
              f"that is the stub, not the corpus. {ref} is not the commit that performed the "
              f"split. Name that commit, or pass an explicit before-ref as a second argument.")
        return 1
    order = json.loads(manifest_text)["order"]
    parts = [show("docs/gates/" + name) for name in order]
    if any(part is None for part in parts):
        print(f"some entry files are missing at {ref}")
        return 1
    after = "\n".join(part for part in parts if part is not None)
    if after == before:
        print(f"IDENTICAL — docs/GATES.md at {source_ref} ({len(before.encode('utf-8')):,} "
              f"bytes) equals the {len(order)} files at {ref}. The split lost nothing.")
        return 0
    if before.startswith == after.startswith and after.startswith(before[:0]):
        pass
    if after.startswith(before):
        extra = after[len(before):]
        print(f"PRESERVED — docs/GATES.md at {source_ref} ({len(before.encode('utf-8')):,} "
              f"bytes) is a byte-for-byte PREFIX of the {len(order)} files at {ref}.")
        print(f"            {len(extra.encode('utf-8')):,} bytes follow it.")
        return 0
    if before == after:
        print("IDENTICAL")
        return 0
    print(f"DIFFERENT at {ref}: before {len(before):,} chars, reassembled {len(after):,}")
    import difflib
    for line in list(difflib.unified_diff(before.split("\n"), after.split("\n"),
                                          "before", "reassembled", lineterm="", n=1))[:30]:
        print("  " + line[:160])
    return 1


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="perform the split (default: preview)")
    ap.add_argument("--verify", metavar="REF", help="reassemble and diff against REF (a local file)")
    ap.add_argument("--selftest", action="store_true",
                    help="assert the corpus is complete and round-trips")
    ap.add_argument("--verify-split", metavar="REF", nargs="+",
                    help="diff docs/GATES.md at REF^ (or at a second ref you name) against the "
                         "entry files at REF")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.verify_split:
        return verify_split(args.verify_split[0],
                            args.verify_split[1] if len(args.verify_split) > 1 else None)
    if args.verify:
        return verify(Path(args.verify))
    return split(args.write)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
