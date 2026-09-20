#!/usr/bin/env python3
"""Pin the STE ratchet's ceiling from a real measurement.

    python3 scripts/ste-ratchet-pin.py --pin

D18 IS ABSOLUTE HERE: a generator may write, and nothing that writes may gate a commit. This
script is on no `make` target and no git hook — a person runs it, on purpose, once, and
`git diff scripts/ste-ratchet.json` is the receipt, the same discipline
`scripts/copy-budget.mjs` and `scripts/typed-interpunct-pin.mjs` already keep for their own
ratchets (D194, D218).

THIS SCRIPT CONTAINS NO COUNTING LOGIC OF ITS OWN. It calls `scripts/ste_measure.py:measure()`
— the SAME function `scripts/docs-audit.py`'s `ste ratchet` row calls to assert — over the
same tracked-markdown list `git ls-files` gives the row (there is no `--staged` reading here
because a pin is a whole-tree, deliberate act, never a partial one), and writes exactly what
came back. No slack is added: slack is how a ratchet leaks.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ste_measure  # noqa: E402  (path insert above must run first)

PIN_PATH = ROOT / "scripts" / "ste-ratchet.json"


def tracked_markdown() -> list:
    result = subprocess.run(
        ["git", "ls-files", "-z", "*.md"], cwd=ROOT, capture_output=True, check=True
    )
    names = [n for n in result.stdout.decode("utf-8").split("\0") if n]
    paths = []
    for name in names:
        text = (ROOT / name).read_text(encoding="utf-8", errors="replace")
        paths.append((name, text))
    return paths


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--pin" not in argv:
        sys.stderr.write("usage: python3 scripts/ste-ratchet-pin.py --pin\n")
        return 2

    print("ste-ratchet-pin: measuring every tracked markdown file with scripts/ste/ste_lint.py ...")
    paths = tracked_markdown()
    measurement = ste_measure.measure(paths)

    PIN_PATH.write_text(json.dumps(measurement.to_pin(), indent=2, sort_keys=True) + "\n")

    print(
        f"ste-ratchet-pin: pinned at {measurement.total} error-severity findings "
        f"across {measurement.scanned_files} files "
        f"({measurement.exempted_total} exempted: {measurement.exempted_by_class}).\n"
        f"ste-ratchet-pin: `git diff scripts/ste-ratchet.json` shows what moved."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
