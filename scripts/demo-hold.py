#!/usr/bin/env python3
"""Decide whether the demo workflow may publish (D295, the public demo is the scrubbed real store; docs/specs/demo.md §13).

    python3 scripts/demo-hold.py --chunk demo-assets/mirror/bundle/chunk-0.json

The committed mirror records the wire digest it was taken against (`wire`, in chunk 0). If
this tree's `wire_digest()` (`demo-record.py`) differs, the recording may not cover the
current screens, and a stale recording renders blank without failing. So the workflow holds:
the last good demo stays up. A hold is a notice and `publish=false`, never a failure, so the
alarm job stays quiet. A chunk with no `wire` holds too: unknown is not clear.

Writes `publish=true|false` to the file `$GITHUB_OUTPUT` names, if set. A match or a hold exits 0.
A chunk file that is missing or not JSON raises and exits 1 on purpose: failing closed publishes
nothing and opens the alarm, which a silent hold would not.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def tree_digest():
    spec = importlib.util.spec_from_file_location("demo_record_for_hold", HERE / "demo-record.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.wire_digest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk", required=True, help="the mirror's chunk-0.json")
    args = ap.parse_args()
    recorded = json.loads(Path(args.chunk).read_text("utf-8")).get("wire") or ""
    tree = tree_digest()
    publish = recorded == tree
    if not publish:
        print("::notice::demo held, last good demo stays up: the mirror was recorded against wire "
              "'%s' and this tree's wire is '%s'. Run `make demo-mirror` to refresh it."
              % (recorded or "none", tree))
    else:
        print("demo-hold: wire %s matches, publishing" % tree)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as handle:
            handle.write("publish=%s\n" % ("true" if publish else "false"))


if __name__ == "__main__":
    main()
