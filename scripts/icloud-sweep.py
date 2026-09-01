#!/usr/bin/env python3
"""Find — and, where it is provably safe, delete — iCloud Drive conflict copies.

WHY THIS EXISTS. This repo lived in iCloud Drive when this was written (it moved to
~/Developer on 2026-08-29, so the ordinary answer is now `no conflict copies` — D44, amended,
keeps the target because the hazard belongs to a synced directory rather than to this repo).
iCloud resolves a same-file race by
writing a SECOND file beside the original with " 2" appended to the stem: `pre-push 2`,
`githooks-selftest 2.sh`, `ports 2.py`. Three appeared in one afternoon on 2026-08-29. They
are untracked, so they are invisible until something says `git add -A` — which is what an
agent session says — and they do real damage in two ways that have both already happened:

  * `make hooks` installed one AS A GIT HOOK, before that target learned to enumerate through
    `git ls-files`. Five hooks from three files, two reviewed by nobody.
  * the repo-map orphan rule failed a commit on one, which is the good outcome and only
    happens inside a mapped directory with a declared suffix.

The pre-commit hook now refuses a staged conflict copy, so they cannot be committed. Nothing
DELETED them, which left the owner and every session to spot them by eye.

THE SAFETY RULE, AND IT IS THE WHOLE DESIGN: a copy is deleted only when it is byte-identical
to the file it was copied from. A copy that DIFFERS is reported and left alone, because at
that point it is not provably a duplicate — it may be the newer of two real edits, and this
script has no way to know which. Identical means iCloud made a copy of a file that still
exists unchanged; there is nothing in it to lose.

It also never touches a TRACKED file, whatever its name. `git ls-files --others` is the only
enumeration it uses, so a deliberate `Section 2.md` that somebody committed is invisible here.

`--dry-run` is the default. Deleting requires `--delete`, said out loud.
"""

from __future__ import annotations

import argparse
import filecmp
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]

# The stem ends in a space and digits, before an optional extension. iCloud writes " 2" and
# counts up from there on repeated conflicts.
CONFLICT = re.compile(r"^(?P<stem>.*) (?P<n>\d+)(?P<ext>\.[A-Za-z0-9]+)?$")


def untracked() -> List[Path]:
    done = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=str(ROOT), capture_output=True, text=True, check=False,
    )
    if done.returncode != 0:
        return []
    return [ROOT / part for part in done.stdout.split("\0") if part]


def pairs() -> List[Tuple[Path, Path]]:
    """(copy, original) for every untracked conflict copy whose original still exists."""
    out = []
    for path in untracked():
        match = CONFLICT.match(path.name)
        if not match:
            continue
        original = path.with_name(match.group("stem") + (match.group("ext") or ""))
        if original.exists() and original.is_file() and path.is_file():
            out.append((path, original))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--delete", action="store_true",
        help="actually remove copies that are byte-identical to their original",
    )
    args = parser.parse_args()

    found = pairs()
    if not found:
        print("icloud-sweep: no conflict copies")
        return 0

    identical, differing = [], []
    for copy, original in found:
        (identical if filecmp.cmp(copy, original, shallow=False) else differing).append(
            (copy, original)
        )

    for copy, _original in identical:
        rel = copy.relative_to(ROOT)
        if args.delete:
            copy.unlink()
            print(f"  removed   {rel}")
        else:
            print(f"  identical {rel}   (--delete would remove it)")

    for copy, original in differing:
        print(f"  DIFFERS   {copy.relative_to(ROOT)}")
        print(f"            not a provable duplicate of {original.name} — look at it yourself")

    print(
        f"icloud-sweep: {len(identical)} identical, {len(differing)} differing"
        + ("" if args.delete else "  (nothing removed; pass --delete)")
    )
    # Differing copies are a finding a person has to resolve, so they are worth an exit code.
    return 1 if differing else 0


if __name__ == "__main__":
    sys.exit(main())
