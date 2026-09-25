#!/usr/bin/env python3
"""Pin the line-anchor ratchet's ceiling from a real measurement.

    python3 scripts/line-anchors-pin.py --pin

D18 IS ABSOLUTE HERE: a generator may write, and nothing that writes may gate a commit.
This script is on no `make` target and no git hook — a person runs it, on purpose, once,
and `git diff scripts/line-anchors.json` is the receipt.

THE PIN IS PER FILE (D229), never a repo-wide total — a repo-wide number is one every
merge takes from somebody, D226's own argument, mirrored. One entry per tracked markdown
file that carries at least one `path:N`/`path:N-M` line anchor, RAW: every anchor
`line_anchor_candidates` extracts, whether or not it resolves to a real file today — "leave
nothing alone" is the owner's own ruling for this clause, per the brief that shipped it.

THIS SCRIPT CONTAINS NO COUNTING LOGIC OF ITS OWN. It imports `scripts/docs-audit.py` (the
filename has a hyphen, hence `importlib`) and calls its `_line_anchor_counts()` over
`markdown_files()` — the SAME function `check_line_anchor_ratchet` calls to assert — so the
two paths cannot drift apart the way a hand-copied counter would.

IT PRUNES. A file whose pin is gone (deleted, or its last anchor removed) is dropped here,
never by the row, which is read-only.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_AUDIT_PATH = ROOT / "scripts" / "docs-audit.py"
PIN_PATH = ROOT / "scripts" / "line-anchors.json"


def _load_docs_audit():
    spec = importlib.util.spec_from_file_location("docs_audit", DOCS_AUDIT_PATH)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv != ["--pin"]:
        print(__doc__)
        return 64

    docs_audit = _load_docs_audit()
    counts = docs_audit._line_anchor_counts(docs_audit.markdown_files())
    data = {"files": dict(sorted(counts.items()))}
    PIN_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"pinned {sum(counts.values())} line anchors over {len(counts)} files "
        f"to {PIN_PATH.relative_to(ROOT)}"
    )
    print("git diff scripts/line-anchors.json is the receipt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
