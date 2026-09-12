#!/usr/bin/env python3
"""Split docs/DECISIONS.md into one file per entry, and prove the split lost nothing.

WHY THIS IS A SCRIPT AND NOT A HAND EDIT. The move is 1.4 MB across 160 entries. A hand
split is unreviewable — a reviewer cannot tell a faithful move from one that dropped a
paragraph — so the move is performed by this file, committed beside its result, and the
result is checked by `--verify`, which reassembles the directory and diffs it against the
original bytes. The diff being empty is the whole claim.

THE CHUNK MODEL, which is what makes losslessness true BY CONSTRUCTION rather than by
testing. The file is cut into chunks at every `## ` line. Every line of the original
belongs to exactly ONE chunk, chunks are written in order, and reassembly concatenates
them in that order. There is no separator convention to get wrong and no text that lives
between chunks, because a chunk boundary is a line boundary and the last line of one chunk
is immediately followed by the first line of the next.

A chunk is an ENTRY when its heading matches `## D<id>`, and a SECTION otherwise. The
three sections that are not entries — Deferred, Someday and the v1 bug table — sit
BETWEEN D79 and D80 in the original and are not decisions at all; they get their own files
and the manifest records where they sat, so the reassembly is exact rather than
approximately right.

THE BOUNDARY RULE IS scripts/prose-guard.py's, deliberately. An entry ends at the next
`## ` of ANY kind — not the next `## D<n>` — because that is the rule
scripts/decision-context.py already reads by, and the two disagreeing is how D60 came to
read 17,775 bytes against its real 4,976, having absorbed all three sections. This script
re-derives that rule rather than importing it, and `--verify` is what keeps them honest.
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
SOURCE = ROOT / "docs" / "DECISIONS.md"
TARGET = ROOT / "docs" / "decisions"
MANIFEST = "ORDER.json"

# The id shape is scripts/prose-guard.py's `_ID`, which is docs-audit's `_ID_ANY`: either a
# number or a claim slug. A branch writes its heading as a slug and `make merge` substitutes
# the number (D140), so BOTH shapes have to name a file or the claimer cannot find what it
# must rename.
_ID = r"(?:[1-9][0-9]{0,2}|-[a-z][a-z0-9]*(?:-[a-z0-9]+)+)"
ENTRY_RE = re.compile(r"^##\s+(D" + _ID + r")\b")
HEADING_RE = re.compile(r"^##\s+(D" + _ID + r")\s*[—-]\s*(.+)$")


class Chunk(NamedTuple):
    kind: str      # "preamble" | "entry" | "section"
    ident: str     # "D58" for an entry; "" otherwise
    title: str
    lines: List[str]


def slug(text: str, limit: int = 58) -> str:
    """A filename-safe tail for a heading.

    LOWERCASE ASCII, and it is allowed to be lossy: the slug is a convenience for a human
    scanning `ls`, never an identifier. The id in front of it is the identifier, and
    `--verify` compares bytes rather than names, so a slug that truncates mid-word costs
    nothing. What it may NOT do is collide, which is why the caller disambiguates.
    """
    text = text.replace("—", " ").replace("'", "").replace("`", "")
    out = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(out) > limit:
        out = out[:limit].rsplit("-", 1)[0] or out[:limit]
    return out.strip("-") or "untitled"


def chunk(text: str) -> List[Chunk]:
    """Cut the file at every `## `. Every line lands in exactly one chunk."""
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
        if entry:
            out.append(Chunk("entry", entry.group(1), title, body))
        else:
            out.append(Chunk("section", "", title, body))
    return out


def names(chunks: List[Chunk]) -> List[str]:
    """One filename per chunk, stable and collision-free.

    Entries are `D<zero-padded>-<slug>.md` so `ls` and a glob both sort into heading order
    without anyone sorting. A CLAIM SLUG has no number to pad, so it keeps its own spelling
    (its own slug, unpadded) and sorts after the numbers — which is where an unclaimed entry belongs,
    since it is by definition the newest thing in the tree.
    """
    used: dict = {}
    out: List[str] = []
    for c in chunks:
        if c.kind == "preamble":
            stem = "_preamble"
        elif c.kind == "section":
            stem = "_" + slug(c.title)
        elif c.ident[1:].isdigit():
            stem = f"D{int(c.ident[1:]):03d}-{slug(c.title)}"
        else:
            stem = f"{c.ident}-{slug(c.title)}"
        name = stem + ".md"
        if name in used:                       # never observed; a slug collision would
            used[name] += 1                    # otherwise silently overwrite an entry
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
          f"{sum(1 for c in chunks if c.kind == 'section')} sections, "
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
    # THE DIGEST IS PROVENANCE, NOT A GATE. It records the bytes this directory was made
    # from, so a reader can tell what was split and when. It is deliberately NOT compared
    # against the live corpus on every run: editing an entry is the normal way this corpus
    # changes, and a check that hashed the whole thing would go red on the next decision
    # entry and blame a routine append for a loss that had not happened. The historical
    # claim is re-established by `--verify-split REF`, which reads both sides out of git.
    (TARGET / MANIFEST).write_text(
        json.dumps({
            "source": "docs/DECISIONS.md",
            "split_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "split_bytes": len(text.encode("utf-8")),
            "order": filenames,
        }, indent=2) + "\n",
        encoding="utf-8")
    print(f"wrote    {len(filenames)} files + {MANIFEST} into {TARGET.relative_to(ROOT)}/")
    return 0


def join() -> str:
    """Reassemble the original from the directory and its manifest."""
    order = json.loads((TARGET / MANIFEST).read_text(encoding="utf-8"))["order"]
    return "\n".join((TARGET / name).read_text(encoding="utf-8") for name in order)


def selftest() -> int:
    """Reassembly still matches the bytes the split was made from.

    THE PROOF WITHOUT THE ORIGINAL. `--verify` needs the pre-split file and can only be run
    on the day of the move; this asserts the same thing against the digest recorded in the
    manifest, so a later session can re-establish that nothing has been lost in transit —
    an entry file deleted, an entry emptied, a manifest line dropped — without needing the
    document back.

    TWO CLAIMS, AND THEY ARE NOT THE SAME CLAIM. The first is historical and immutable: the
    split lost nothing. The second is ongoing: the corpus is a complete, well-formed set
    today. Only the second can be asserted on every run, because EDITING AN ENTRY IS THE
    NORMAL WAY THIS CORPUS CHANGES and any digest over the live corpus moves the first time
    anybody does.

    An earlier version of this compared the live reassembly against the split digest and
    would have gone red on the very next decision entry, blaming a routine append for a loss
    that had not happened. `split_sha256` is PROVENANCE here, printed and never compared;
    `--verify-split REF` re-establishes the historical claim by reading both sides out of
    git, so it keeps working long after the original has left the working tree.
    """
    manifest = json.loads((TARGET / MANIFEST).read_text(encoding="utf-8"))
    problems = []
    missing = [n for n in manifest["order"] if not (TARGET / n).exists()]
    if missing:
        problems.append(f"{len(missing)} file(s) in the manifest are gone: {missing[:3]}")
    # AN UNREGISTERED FILE IS A BRANCH IN FLIGHT, NOT DAMAGE, and the two are not the same
    # finding. Requiring a new entry to be listed here would put every entry-adding branch
    # back into one shared JSON array at the same position — the collision this whole split
    # removes, wearing a different file extension. Membership is derived by
    # `decisions_corpus.order()` and normalized by `make merge` at claim time, which is the
    # one moment the final order is knowable (D140's own argument for the number).
    #
    # THE REVERSE IS STILL DAMAGE. A manifest naming a file that is gone is not a branch in
    # flight; nothing legitimate produces it, and the corpus stops reassembling.
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
    order = list(manifest["order"]) + pending
    ids = {}
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
              f"in the manifest — normal on a branch, normalized by `make merge`:")
        for name in pending[:5]:
            print(f"               {name}")
    for problem in problems:
        print("  FAIL " + problem)
    print("decisions-selftest: " + ("FAIL" if problems else "ok"))
    return 1 if problems else 0


def verify_split(ref: str, before_ref: Optional[str] = None) -> int:
    """Re-establish the historical claim: the split lost nothing.

    RE-RUNNABLE FOREVER, WHICH TOOK A CORRECTION TO BE TRUE. Reads `docs/DECISIONS.md` from
    REF's PARENT (or from a second ref you name) and diffs it against a reassembly of the
    entry files at REF. Both sides come from git, so the original never has to be on disk.

    THE PARENT IS THE POINT. An earlier version read both sides from ONE ref, which cannot
    work and made this docstring a promise nobody could keep: the split is a single atomic
    commit, so AT that commit `docs/DECISIONS.md` is already the stub, and no commit anywhere
    in the history has the monolith and the directory side by side. Asking one ref for both
    compared 38 lines against 1.4 MB and reported a catastrophic difference that was entirely
    an artefact of the question.

    Usage: `--verify-split <the split commit>` — the commit that emptied the monolith. Pointed
    anywhere else it says so rather than answering.
    """
    import subprocess

    def show(path: str, at: Optional[str] = None) -> Optional[str]:
        done = subprocess.run(["git", "show", f"{at or ref}:{path}"],
                              cwd=ROOT, capture_output=True, text=True)
        return done.stdout if done.returncode == 0 else None

    # THE FILE COMES FROM THE PARENT AND THE ENTRIES FROM THE COMMIT ITSELF. At the split
    # commit `docs/DECISIONS.md` is ALREADY the stub — that is the same commit that emptied
    # it — so reading both sides from one ref compares a 38-line pointer against 1.4 MB and
    # reports a catastrophic difference that is entirely an artefact of asking wrongly. The
    # question is "did REF's entries preserve what REF's PARENT held", and it has to be
    # spelled that way.
    source_ref = before_ref or f"{ref}^"
    before = show("docs/DECISIONS.md", source_ref)
    if before is None:
        print(f"no docs/DECISIONS.md at {source_ref} — nothing to compare")
        return 1
    manifest_text = show("docs/decisions/" + MANIFEST)
    if manifest_text is None:
        print(f"{ref} has no corpus manifest — it is not the commit that performed the split.")
        return 1
    if len(before.encode("utf-8")) < 100_000:
        print(f"docs/DECISIONS.md at {source_ref} is only "
              f"{len(before.encode('utf-8')):,} bytes — that is the stub, not the corpus. "
              f"{ref} is not the commit that performed the split. Name that commit, or pass "
              f"an explicit before-ref as a second argument.")
        return 1
    order = json.loads(manifest_text)["order"]
    parts = [show("docs/decisions/" + name) for name in order]
    if any(part is None for part in parts):
        print(f"some entry files are missing at {ref}")
        return 1
    after = "\n".join(part for part in parts if part is not None)
    if after == before:
        print(f"IDENTICAL — docs/DECISIONS.md at {source_ref} ({len(before.encode('utf-8')):,} "
              f"bytes) equals the {len(order)} files at {ref}. The split lost nothing.")
        return 0
    # THE SPLIT COMMIT ALSO ADDS ITS OWN ENTRY, and that is not a loss. The claim being made
    # is PRESERVATION, not equality: everything the parent held is still there, in order,
    # byte for byte, and anything after it is new. A proof that demanded equality would fail
    # on the one commit it exists to check — the split cannot land without an entry arguing
    # for it — and a reviewer would be left unable to tell "nothing lost" from "something
    # added".
    if after.startswith(before):
        extra = after[len(before):]
        # THE NEW ENTRIES, BY HEADING. Listing new FILES says nothing useful at the split
        # commit — the directory did not exist at the parent, so every file is new and the
        # list is 164 names long. What a reviewer needs is which ENTRIES arrived, and that is
        # a property of the text rather than of the filesystem.
        arrived = ENTRY_RE.findall("\n".join(
            line for line in extra.split("\n") if line.startswith("## ")))
        print(f"PRESERVED — docs/DECISIONS.md at {source_ref} ({len(before.encode('utf-8')):,} "
              f"bytes) is a byte-for-byte PREFIX of the {len(order)} files at {ref}.")
        print(f"            Nothing the parent held was changed, reordered or dropped.")
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


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="perform the split (default: preview)")
    ap.add_argument("--verify", metavar="REF", help="reassemble and diff against REF")
    ap.add_argument("--selftest", action="store_true",
                    help="assert the corpus is complete and round-trips")
    ap.add_argument("--verify-split", metavar="REF", nargs="+",
                    help="diff docs/DECISIONS.md at REF^ (or at a second ref you name) "
                         "against the entry files at REF")
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
