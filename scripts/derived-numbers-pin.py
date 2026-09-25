#!/usr/bin/env python3
"""Rewrite every `<!-- derived:<name> -->`-marked number in the tracked markdown to match
what `scripts/derived_numbers.py:REGISTRY[<name>].compute(ROOT)` says right now.

    python3 scripts/derived-numbers-pin.py --write

D18 IS ABSOLUTE HERE: a generator may write, and nothing that writes may gate a commit.
This script is on no `make` target and no git hook — a person runs it, on purpose, once, and
`git diff` is the receipt.

THIS SCRIPT CONTAINS NO COUNTING LOGIC OF ITS OWN. It calls `scripts/derived_numbers.py`'s
own `find_markers` and `compute` — the SAME functions `scripts/docs-audit.py`'s `derived
numbers` row calls to assert — over the same tracked-markdown list `git ls-files` gives that
row. No slack is added: it writes exactly what `compute` returns.

WITHOUT `--write` it previews: every marker it found, what is published beside it now, and
what it would become, with no file touched. `--write` is the only mode that edits anything.

WHAT THIS WILL NEVER DO: rewrite a number that carries no marker. A figure the owner ruled
must never be auto-updated — a gate run, an incident measurement — has no marker because
`scripts/derived_numbers.py`'s `REGISTRY` carries no entry for it (see that file's own
docstring for the full argument and the list of examples). This script cannot touch what it
cannot find a marker in front of, which is the whole safety property.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import derived_numbers  # noqa: E402  (path insert above must run first)


def tracked_markdown() -> list:
    result = subprocess.run(
        ["git", "ls-files", "-z", "*.md"], cwd=ROOT, capture_output=True, check=True
    )
    names = [n for n in result.stdout.decode("utf-8").split("\0") if n]
    return names


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    write = "--write" in argv
    if not write and argv:
        sys.stderr.write(
            "usage: python3 scripts/derived-numbers-pin.py [--write]\n"
        )
        return 2

    changed = 0
    unknown = 0
    errored = 0
    checked = 0

    for name in tracked_markdown():
        path = ROOT / name
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        lines = text.split("\n")
        touched = False
        for i, line in enumerate(lines):
            matches = derived_numbers.find_markers(line)
            if not matches:
                continue
            new_line = line
            offset = 0
            for match in matches:
                checked += 1
                derivation_name = match.group("name")
                published = match.group("number")
                entry = derived_numbers.REGISTRY.get(derivation_name)
                if entry is None:
                    print(f"{name}:{i + 1}: unknown derivation `{derivation_name}`, left alone")
                    unknown += 1
                    continue
                try:
                    computed = entry.compute(ROOT)
                except Exception as exc:  # noqa: BLE001 - report, keep going
                    print(f"{name}:{i + 1}: `{derivation_name}` could not be computed: {exc}")
                    errored += 1
                    continue
                if str(computed) == published.replace(",", ""):
                    continue
                # KEEP THE SEPARATOR THE PROSE ALREADY USES. A figure a person reads in a
                # sentence is grouped — `720,000`, never `720000` — and a generator that
                # strips the commas makes every rewrite a readability regression the author
                # then fixes by hand, which is how a generated field stops being generated.
                # `MARKER_RE` accepts `\d[\d,]*`, so the grouped form round-trips.
                rendered = f"{computed:,}" if "," in published else str(computed)
                start, end = match.span("number")
                new_line = (
                    new_line[: start + offset] + rendered + new_line[end + offset :]
                )
                offset += len(rendered) - (end - start)
                print(f"{name}:{i + 1}: {derivation_name} {published} -> {rendered}")
                changed += 1
            if new_line != line:
                lines[i] = new_line
                touched = True
        if touched and write:
            path.write_text("\n".join(lines), encoding="utf-8")

    print(
        f"derived-numbers-pin: {checked} marker(s) checked, {changed} figure(s) "
        f"{'rewritten' if write else 'would be rewritten (pass --write to apply)'}, "
        f"{unknown} unknown name(s), {errored} could not be computed."
    )
    if not write and changed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
