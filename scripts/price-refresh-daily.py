#!/usr/bin/env python3
"""Daily market read (DEBT69). Owner's Mac, main tree only.

Runs `server/pipeline_routes.py:do_prices_refresh` once: the owner's live listings (the one live
fetch D104 made), the catalog export per game, a re-join of every open run, then the Trends
strips for the rows still waiting (`docs/specs/stale-listings.md`, 7b). Each step leaves a note
(`pipeline/pricerefresh.py`) that `#/pricing` shows, so a failed or partial run is on screen
and never a silent stale state.

FREE, AND IT CHANGES NO PRICE AT TCGPLAYER. It reads the seller portal and writes nothing there. It calls no paid read and no archive sweep: the sweep stays a press (D224, DEBT32).
Pushing new live prices stays its own decision (DEBT69).

  price-refresh-daily.py              run once now
  price-refresh-daily.py --agent [--remove]   install / remove the daily launchd job

The installer is `scripts/launchagent.py`. `demo-mirror-daily.py` keeps its own copy because it
sits under a standing auto-merge fence (D295); migrating it is its own PR.
"""
import argparse
import fcntl
import sys
import time
from pathlib import Path

import launchagent  # scripts/launchagent.py, the shared installer

HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
LABEL = "com.banchi.price-refresh-daily"
LOG = Path.home() / ".pkmnscan" / "price-refresh-daily.log"


def log(verdict):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), verdict))
    print(verdict)


def agent(remove):
    return launchagent.agent(LABEL, HERE, ROOT, 5, 15, LOG, remove)


def run():
    sys.path.insert(0, str(ROOT))
    from pipeline import pricerefresh
    from server import pipeline_routes

    answer = pipeline_routes.do_prices_refresh()
    for name, step in (pricerefresh.read_status() or {}).get("steps", {}).items():
        extra = {key: value for key, value in step.items() if key not in ("at", "ok")}
        log("%s: %s %s" % (name, "ok" if step.get("ok") else "failed", extra))
    return 0 if answer["ok"] and (answer["steps"].get("history") or {}).get("ok") else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", action="store_true")
    ap.add_argument("--remove", action="store_true")
    a = ap.parse_args()
    if a.agent:
        sys.exit(agent(a.remove))
    LOG.parent.mkdir(parents=True, exist_ok=True)
    lock = open(LOG.with_suffix(".lock"), "w")  # noqa: SIM115 held for the process life
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("skipped: another run holds the lock")
        sys.exit(0)
    sys.exit(run())
