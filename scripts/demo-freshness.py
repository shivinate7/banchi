#!/usr/bin/env python3
"""Whether the demo's recorded bundle still describes the wire it was recorded against.

THE FAILURE THIS EXISTS TO CATCH IS SILENT, which is the only reason it is worth a check at
all. `app/demo/bundle.json` is a frozen recording of the capture server's answers. Change a
shape in `app/src/types.ts`, or a path in `app/src/server.ts`, and the recording no longer
covers the contract — and the demo does not break loudly. A screen reading a field the
recording predates renders BLANK. Nothing else in this repo would notice: the harness never
opens it, `tsc` type-checks the client against `types.ts` and not against a JSON file, and
the app builds perfectly.

So the bundle stores a digest of those two files, and this compares it against the tree.

A STANDALONE TARGET, ON NO GATE AT ALL, and the scope of what it is for shrank once the
bundle stopped being committed. CI rebuilds the whole thing from source on every push
(.github/workflows/demo.yml), so the PUBLISHED copy can never be stale — what is left is
the local footgun: `make demo`, then an edit to `server.ts`, then `make demo-preview`,
which serves a recording that predates the edit. That is worth one command and not worth
failing `make check` over, because a drifted local preview blocks nobody.

D18 is the other half: this reads two files and writes nothing, so nothing about it would
be unsafe on a gate. It is off one by choice rather than by necessity.

EXIT 0 fresh, or no bundle at all (the demo is optional — a tree that has never built one
is not a tree with a problem). EXIT 1 drifted.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLE = REPO_ROOT / "app" / "demo" / "bundle.json"
WATCHED = (
    REPO_ROOT / "app" / "src" / "types.ts",
    REPO_ROOT / "app" / "src" / "server.ts",
)


def wire_digest() -> str:
    """The same digest `scripts/demo-record.py` writes. Kept in step by being one recipe:
    the two files, in this order, sha256, first 16 hex characters."""
    digest = hashlib.sha256()
    for path in WATCHED:
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def main() -> int:
    if not BUNDLE.exists():
        print("demo freshness: no bundle — nothing to check (`make demo` builds one).")
        return 0

    try:
        payload = json.loads(BUNDLE.read_text())
    except ValueError as exc:
        print("demo freshness: %s is not readable JSON — %s" % (BUNDLE.name, exc))
        return 1

    recorded = str(payload.get("wire") or "")
    current = wire_digest()
    if recorded == current:
        print(
            "demo freshness: bundle matches the wire (%s, %d routes)."
            % (current, len(payload.get("responses") or {}))
        )
        return 0

    print("demo freshness: STALE.")
    print("  recorded against  %s" % (recorded or "(nothing)"))
    print("  the tree is now   %s" % current)
    print("  changed since:    %s" % ", ".join(p.name for p in WATCHED))
    print()
    print("  The published demo replays this recording. A screen reading a field the")
    print("  recording predates renders BLANK rather than failing — so re-record before")
    print("  the demo is next published:")
    print()
    print("      make demo")
    return 1


if __name__ == "__main__":
    sys.exit(main())
