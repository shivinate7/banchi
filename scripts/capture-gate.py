#!/usr/bin/env python3
"""Ship gate (b) for the background reader: capture speed with the reader on against off.

Spec section 8, "While cards are being fed". 300 feeder-paced captures (one every 623 ms, the
feeder's own rate) are posted to a scratch capture server over a scratch store
(`scripts/sweep_scratch.py`), three times, each over a fresh store:

  off      the reader switched off
  always   the reader on, as shipped (the owner's ruling, "Even mid-feed"): its worker starts the
           moment a card waits
  gaps     the reader on with `--quiet 3`: its worker starts only 3 s after the last capture

The metric is the time of one capture request, p50 and p99 and the worst. There is no pass mark:
the owner reads the three rows and decides whether the reader may read "always". Nothing here
switches the reader on in the owner's store.

    .venv/bin/python scripts/capture-gate.py --model PATH.onnx --index PATH/fingerprints.sqlite \\
        --photos list.json [--captures 300] [--arms off,gaps,always]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sweep_scratch import REPO, Scratch, photo_list, summary  # noqa: E402

sys.path.insert(0, str(REPO))
from store import db  # noqa: E402

FEEDER_SECONDS = 0.623


def run_arm(arm: str, args) -> dict:
    scratch = Scratch(args.model, args.index, args.export)
    watcher = None
    try:
        scratch.start()
        if arm == "always":
            scratch.set_switch(True)  # the real route: it starts the watcher as shipped
        elif arm == "gaps":
            # THE SWITCH ROW BY HAND AND OUR OWN WATCHER, because the route starts the default one.
            conn = db.connect(scratch.home / "inventory")
            db.set_match_sweep(conn, True)
            conn.close()
            watcher = subprocess.Popen(
                [str(REPO / "banchi"), "match", "--sweep", "--quiet", "3"], cwd=str(REPO), env=scratch.env
            )
        time.sleep(1.5)
        photos = photo_list(args.photos, args.captures)
        latencies = []
        start = time.perf_counter()
        for i, photo in enumerate(photos):
            due = start + i * FEEDER_SECONDS
            wait = due - time.perf_counter()
            if wait > 0:
                time.sleep(wait)
            latencies.append(scratch.capture(photo))
        result = summary(arm, latencies)
        result["latencies_ms"] = [round(v * 1000, 1) for v in latencies]
        read = scratch.sql("select count(*) from identifications")[0][0]
        print(f"{'':<14} {scratch.sql(chr(115)+'elect count(*) from cards where state<>?', ('captured',))[0][0]} card(s) identified by the end of the feed")
        print(f"{'':<14} the reader had written {read} row(s) by the end of the feed")
        result["rows_during_feed"] = read
        return result
    finally:
        if watcher is not None:
            watcher.terminate()
        scratch.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--photos", required=True, type=Path, help="JSON list of photograph paths")
    parser.add_argument("--export", type=Path, help="a riftbound export with its .scope.json: the reader adopts only against one")
    parser.add_argument("--captures", type=int, default=300)
    parser.add_argument("--arms", default="off,always,gaps")
    parser.add_argument("--json", type=Path, help="write the three results here")
    args = parser.parse_args()
    results = {arm: run_arm(arm, args) for arm in args.arms.split(",")}
    if "off" in results:
        base = results["off"]["p99_ms"]
        for arm, row in results.items():
            if arm != "off":
                print(f"{arm}: p99 {row['p99_ms'] - base:+.1f} ms against off")
    if args.json:
        args.json.write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
