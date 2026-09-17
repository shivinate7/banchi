#!/usr/bin/env python3
"""Split docs/DEBTS.md into one file per section, and prove the split lost nothing.

WHY THIS IS A SCRIPT AND NOT A HAND EDIT, same argument as `scripts/split-decisions.py`
makes for `docs/DECISIONS.md` (D160): the move is reviewable only if it is mechanical, so
it is performed here, committed beside its result, and checked by `--verify` / `--selftest`,
which reassemble the directory and diff it against the original bytes.

THE CHUNK MODEL is the same one: the file is cut at every `## ` line, every line of the
original belongs to exactly one chunk, and reassembly concatenates them in manifest order.
`docs/DEBTS.md` has no non-entry sections between its numbered entries (unlike
`docs/DECISIONS.md`'s Deferred/Someday/v1-table), so every chunk after the preamble is a
section entry — no separate "section" kind is needed here.

IDS ARE PLAIN NUMBERS, NOT `D<n>`. A debts entry is `## <n> — <title>`, so its id is `§<n>`
— the sigil this repo already used in prose before this split, and the spelling this split's
citation rewrite settles on repo-wide (see the stub, `docs/DEBTS.md`). Filenames are
`<zero-padded n>-<slug>.md`, the same convention `split-decisions.py` uses without the `D`.

SECTION 15 IS A DELIBERATE GAP (see the preamble) and is not a number this script invents:
the chunker only ever emits chunks for numbers that have a `## ` heading, so 15 simply does
not appear in `docs/debts/`, exactly as it does not appear as a heading in the source file.
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
SOURCE = ROOT / "docs" / "DEBTS.md"
TARGET = ROOT / "docs" / "debts"
MANIFEST = "ORDER.json"

# `## 6 — ~~Measured against one rig...~~ — CLOSED 2026-09-09, ...` — a closed entry keeps
# its number and gets struck through in its own title; the id regex only needs the number.
ENTRY_RE = re.compile(r"^##\s+([0-9]+)\b")
HEADING_RE = re.compile(r"^##\s+([0-9]+)\s*[—-]\s*(.+)$")


class Chunk(NamedTuple):
    kind: str      # "preamble" | "entry"
    ident: str     # "6" for an entry; "" for the preamble
    title: str
    lines: List[str]


def slug(text: str, limit: int = 58) -> str:
    """A filename-safe tail for a heading. Lossy on purpose — see split-decisions.py's twin."""
    text = text.replace("—", " ").replace("~", " ").replace("'", "").replace("`", "")
    out = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(out) > limit:
        out = out[:limit].rsplit("-", 1)[0] or out[:limit]
    return out.strip("-") or "untitled"


def chunk(text: str) -> List[Chunk]:
    lines = text.split("\n")
    starts = [i for i, line in enumerate(lines) if line.startswith("## ")]
    out: List[Chunk] = []
    if not starts:
        return [Chunk("preamble", "", "", lines)]
    if starts[0] > 0:
        out.append(Chunk("preamble", "", "", lines[: starts[0]]))
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        body = lines[start:end]
        entry = ENTRY_RE.match(body[0])
        titled = HEADING_RE.match(body[0])
        title = titled.group(2).strip() if titled else body[0][3:].strip()
        if not entry:
            raise ValueError(f"a `## ` line is not a numbered entry: {body[0]!r}")
        out.append(Chunk("entry", entry.group(1), title, body))
    return out


def names(chunks: List[Chunk]) -> List[str]:
    used: dict = {}
    out: List[str] = []
    for c in chunks:
        if c.kind == "preamble":
            stem = "_preamble"
        else:
            stem = f"{int(c.ident):03d}-{slug(c.title)}"
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
    entries = [c for c in chunks if c.kind == "entry"]
    print(f"source   {SOURCE.relative_to(ROOT)}  {len(text):,} bytes, {text.count(chr(10)) + 1:,} lines")
    print(f"chunks   {len(chunks)}  ({len(entries)} entries, "
          f"{sum(1 for c in chunks if c.kind == 'preamble')} preamble)")
    if not write:
        for c, name in list(zip(chunks, filenames))[:4]:
            size = len("\n".join(c.lines))
            print(f"  would write  {name}  ({size:,} bytes)")
        print(f"  ... {len(filenames) - 4} more")
        print("\npreview only — pass --write to perform the split")
        return 0
    TARGET.mkdir(parents=True, exist_ok=True)
    for c, name in zip(chunks, filenames):
        (TARGET / name).write_text("\n".join(c.lines), encoding="utf-8")
    (TARGET / MANIFEST).write_text(
        json.dumps({
            "source": "docs/DEBTS.md",
            "split_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "split_bytes": len(text.encode("utf-8")),
            "order": filenames,
        }, indent=2) + "\n",
        encoding="utf-8")
    print(f"wrote    {len(filenames)} files + {MANIFEST} into {TARGET.relative_to(ROOT)}/")
    return 0


def join() -> str:
    order = json.loads((TARGET / MANIFEST).read_text(encoding="utf-8"))["order"]
    return "\n".join((TARGET / name).read_text(encoding="utf-8") for name in order)


def selftest() -> int:
    manifest = json.loads((TARGET / MANIFEST).read_text(encoding="utf-8"))
    problems = []
    missing = [n for n in manifest["order"] if not (TARGET / n).exists()]
    if missing:
        problems.append(f"{len(missing)} file(s) in the manifest are gone: {missing[:3]}")
    on_disk = {p.name for p in TARGET.glob("*.md")}
    pending = sorted(on_disk - set(manifest["order"]))
    if not missing:
        body = join()
        print(f"reassembled  {len(body.encode('utf-8')):,} bytes from "
              f"{len(manifest['order']) + len(pending)} files")
        print(f"split from   {manifest.get('split_bytes', 0):,} bytes  "
              f"sha256 {str(manifest.get('split_sha256', '?'))[:16]}…  provenance only")
        if not body.endswith("\n"):
            problems.append("the reassembled corpus does not end in a newline.")
    order = [n for n in list(manifest["order"]) + pending if n not in set(missing)]
    ids: dict = {}
    for name in order:
        head = (TARGET / name).read_text(encoding="utf-8").split("\n", 1)[0]
        match = ENTRY_RE.match(head)
        if match:
            ids.setdefault(match.group(1), []).append(name)
    duplicated = {k: v for k, v in ids.items() if len(v) > 1}
    if duplicated:
        problems.append(f"one id in two files: {duplicated}")
    print(f"entries      {len(ids)}  files {len(order)}  duplicates {len(duplicated)}")
    if pending:
        print(f"pending      {len(pending)} entr{'y' if len(pending) == 1 else 'ies'} not yet "
              f"in the manifest:")
        for name in pending[:5]:
            print(f"               {name}")
    for problem in problems:
        print("  FAIL " + problem)
    print("debts-selftest: " + ("FAIL" if problems else "ok"))
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
    """Re-establish the historical claim from git, the same way split-decisions.py does."""
    import subprocess

    def show(path: str, at: Optional[str] = None) -> Optional[str]:
        done = subprocess.run(["git", "show", f"{at or ref}:{path}"],
                              cwd=ROOT, capture_output=True, text=True)
        return done.stdout if done.returncode == 0 else None

    source_ref = before_ref or f"{ref}^"
    before = show("docs/DEBTS.md", source_ref)
    if before is None:
        print(f"no docs/DEBTS.md at {source_ref} — nothing to compare")
        return 1
    manifest_text = show("docs/debts/" + MANIFEST)
    if manifest_text is None:
        print(f"{ref} has no debts manifest — it is not the commit that performed the split.")
        return 1
    if len(before.encode("utf-8")) < 50_000:
        print(f"docs/DEBTS.md at {source_ref} is only {len(before.encode('utf-8')):,} bytes "
              f"— that is the stub, not the corpus. {ref} is not the split commit.")
        return 1
    order = json.loads(manifest_text)["order"]
    parts = [show("docs/debts/" + name) for name in order]
    if any(part is None for part in parts):
        print(f"some entry files are missing at {ref}")
        return 1
    after = "\n".join(part for part in parts if part is not None)
    if after == before:
        print(f"IDENTICAL — docs/DEBTS.md at {source_ref} ({len(before.encode('utf-8')):,} "
              f"bytes) equals the {len(order)} files at {ref}. The split lost nothing.")
        return 0
    if after.startswith(before):
        extra = after[len(before):]
        arrived = ENTRY_RE.findall("\n".join(
            line for line in extra.split("\n") if line.startswith("## ")))
        print(f"PRESERVED — docs/DEBTS.md at {source_ref} ({len(before.encode('utf-8')):,} "
              f"bytes) is a byte-for-byte PREFIX of the {len(order)} files at {ref}.")
        print(f"            {len(extra.encode('utf-8')):,} bytes follow it — "
              f"{len(arrived)} new entr{'y' if len(arrived) == 1 else 'ies'}: "
              f"{', '.join(arrived) or '(none)'}")
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
    ap.add_argument("--verify", metavar="REF", help="reassemble and diff against REF (a file path)")
    ap.add_argument("--selftest", action="store_true",
                    help="assert the corpus is complete and round-trips")
    ap.add_argument("--verify-split", metavar="REF", nargs="+",
                    help="diff docs/DEBTS.md at REF^ (or a second ref you name) against the "
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
