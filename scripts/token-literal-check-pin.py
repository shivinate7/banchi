#!/usr/bin/env python3
"""Pin `scripts/token-literal-check.json`'s per-file ratchet ceiling from a real measurement.

    python3 scripts/token-literal-check-pin.py --pin

D229's own discipline, mirrored exactly (D18 says why a generator is the one thing allowed to
write this file): `make token-literal-check`'s row
only ever READS the pin — D18 forbids it writing, since it runs on the commit path (`make
check`) — and this script is the one thing that may, run by a person choosing, on purpose, to
accept today's count as the new ceiling. Never pin quietly: `git diff
scripts/token-literal-check.json` is the receipt.

Only files with at least one finding, AFTER the allow-list is applied, get a key — a file at
zero needs no ceiling (D229: "a file the pin has never seen is accepted"), and a stale key for
a file that fell to zero is left in place rather than pruned here; nothing gates on it either
way until a person chooses to clean it, the same tolerance D229 states for the prose ratchet.

Writes `scripts/token-literal-check.json` as `{"files": {"<path>": <count>}}` — a flat map,
D229's shape, never a repo-wide scalar.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIN_PATH = ROOT / "scripts" / "token-literal-check.json"
CHECK_PATH = ROOT / "scripts" / "token-literal-check.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("token_literal_check", CHECK_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    if "--pin" not in sys.argv[1:]:
        print("usage: python3 scripts/token-literal-check-pin.py --pin")
        return 2

    tlc = _load_checker()
    findings, _family_tokens, css_scanned, _ts_scanned, _tsx = tlc.scan()
    allow = tlc.load_allow_list()
    findings, stale = tlc.apply_allow_list(findings, allow)
    if stale:
        print(
            "token-literal-check-pin: the allow-list has entries matching no real finding — "
            "fix them before pinning, so a stale exemption is never baked into the ceiling:"
        )
        for entry in stale:
            print(f"  {entry.file}  {entry.property}: {entry.value}  ({entry.reason})")
        return 1

    counts = tlc.counts_by_file(findings)
    pin = {path: count for path, count in sorted(counts.items()) if count > 0}

    PIN_PATH.write_text(json.dumps({"files": pin}, indent=2) + "\n", encoding="utf-8")
    total = sum(pin.values())
    print(
        f"token-literal-check-pin: pinned {len(pin)} file(s), {total} finding(s) total, over "
        f"{css_scanned} stylesheet(s) scanned. `git diff scripts/token-literal-check.json` "
        f"shows what moved."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
