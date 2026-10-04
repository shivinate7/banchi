#!/usr/bin/env python3
"""Ship gate (a) for the background reader: the watcher's idle memory and the worker's peak.

Spec section 8, "Memory is a ship gate". This starts a scratch capture server over a scratch store
(`scripts/sweep_scratch.py`), switches the reader on through the real route, and measures:

  idle RSS      the watcher's resident memory over several polls with an EMPTY queue
  peak RSS      the worker's highest resident memory, sampled every 100 ms, while it reads a queue
                of captured cards (it reads even while captures arrive: the owner's ruling)

It also checks the two rules the design promises: the reader wrote only `marqo-b` identifications
rows, and no card changed state. It prints numbers and brings them to the owner. There is no pass
mark yet, and nothing here switches the reader on in the owner's store.

    .venv/bin/python scripts/sweep-memory.py --model PATH.onnx --index PATH/fingerprints.sqlite \\
        --photos list.json [--cards 40]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sweep_scratch import Scratch, children_of, photo_list, rss_kb  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--photos", required=True, type=Path, help="JSON list of photograph paths")
    parser.add_argument("--cards", type=int, default=40)
    parser.add_argument("--idle-seconds", type=float, default=20.0)
    args = parser.parse_args()

    scratch = Scratch(args.model, args.index)
    try:
        scratch.start()
        scratch.set_switch(True)
        time.sleep(1.0)
        record = json.loads((scratch.home / "inventory" / "match-sweep.json").read_text())
        watcher = int(record["pid"])

        # 1. IDLE: an empty queue, the watcher polling.
        samples = []
        end = time.time() + args.idle_seconds
        while time.time() < end:
            kb = rss_kb(watcher)
            if kb is not None:
                samples.append(kb)
            time.sleep(0.5)
        idle = max(samples) / 1024
        print(f"watcher idle RSS      {idle:.1f} MB (max of {len(samples)} samples over {args.idle_seconds:.0f} s, empty queue)")

        # 2. PEAK: capture cards while the worker reads them, and watch it to the end.
        before = scratch.sql("select key, state from cards order by key")
        for photo in photo_list(args.photos, args.cards):
            scratch.capture(photo)
        states = dict(scratch.sql("select key, state from cards"))
        peak = 0
        worker_seen = False
        deadline = time.time() + 600
        while time.time() < deadline:
            for pid in children_of(watcher, "sweep-worker"):
                worker_seen = True
                kb = rss_kb(pid)
                if kb:
                    peak = max(peak, kb)
            waiting = scratch.sql(
                "select count(*) from cards c where c.state='captured' and not exists "
                "(select 1 from identifications i where i.key = c.key)"
            )[0][0]
            tried = 0
            tried_file = scratch.home / "inventory" / "match-sweep-tried.json"
            if tried_file.exists():
                tried = len(json.loads(tried_file.read_text()).get("keys", {}))
            aside_file = scratch.home / "inventory" / "match-sweep-crash.json"
            if aside_file.exists():  # a set-aside card is done too
                tried += len(json.loads(aside_file.read_text()).get("aside", {}))
            if worker_seen and waiting - tried <= 0 and not children_of(watcher, "sweep-worker"):
                break
            time.sleep(0.1)
        print(f"worker peak RSS       {peak / 1024:.1f} MB (sampled every 100 ms while it read {args.cards} cards)")

        rows = scratch.sql(
            "select json_extract(payload, '$.engine'), count(*) from identifications group by 1"
        )
        after = dict(scratch.sql("select key, state from cards"))
        tried_count = tried
        print(f"rows written          {dict(rows)}; {tried_count} cards left for a press")
        print(f"card state unchanged  {states == after}")
        only_matcher = all(engine == "marqo-b" for engine, _ in rows)
        print(f"only marqo-b rows     {only_matcher}")
        ok = worker_seen and only_matcher and states == after
        print("sweep-memory: " + ("measured" if ok else "FAILED (the worker never ran, or it wrote something it must not)"))
        _ = before
        return 0 if ok else 1
    finally:
        scratch.close()


if __name__ == "__main__":
    sys.exit(main())
