#!/usr/bin/env python3
"""Daily market read (DEBT69), then the price archive sweep (D224, DEBT32). Owner's Mac, main tree only.

Runs `server/pipeline_routes.py:do_prices_refresh` once: the owner's live listings (the one live
fetch D104 made), the catalog export per game, a re-join of every open run, then the Trends
strips for the rows still waiting (`docs/specs/stale-listings.md`, 7b). Each step leaves a note
(`pipeline/pricerefresh.py`) that `#/pricing` shows, so a failed or partial run is on screen
and never a silent stale state.

After a good refresh (unless `--no-sweep`), the same process runs `archive sweep --write` through
`cli.cmd_pricearchive`, at the pace the last throttle saved (D222), its lines in this job's log.
The owner's word is "nightly, on the Mac", and "if the day is a new day when my mac is on, just get
it done then": the sweep runs once per US Central day, in the first job run of that day (launchd
runs a missed job when the Mac wakes), and the job skips it when today's sweep finished. It has no
wall-clock cap and holds the Mac awake never; its pace reads a monotonic clock, so a sleep does not
inflate it. A failed refresh skips the sweep and the log says so. A sweep that stops (a second
throttle, a host that refused from the first sku) or asked and wrote no bucket is a failed
`archive` step in the `#/pricing` note, still ends the job with exit 0, and the next run resumes
without re-reading what is fresh. The job's own run lock means a refresh already running never
reaches the sweep. `make price-refresh` is a manual read and passes `--no-sweep`: it never starts
the sweep unless `ARGS=--sweep` asks. The installed launchd job passes no flag, so it sweeps.

FREE, AND IT CHANGES NO PRICE AT TCGPLAYER. It reads the seller portal and the public sales history
and writes nothing there. It calls no paid read. Pushing new live prices stays its own decision (DEBT69).

  price-refresh-daily.py              run the read, then the sweep if today's has not finished
  price-refresh-daily.py --no-sweep   run the read alone (what `make price-refresh` passes)
  price-refresh-daily.py --agent [--remove]   install / remove the daily launchd job (it passes no flag)

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
LOG = launchagent.machine_dir() / "price-refresh-daily.log"


def log(verdict):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), verdict))
    print(verdict)


def agent(remove):
    return launchagent.agent(LABEL, HERE, ROOT, 5, 15, LOG, remove)


def run(sweep=True):
    sys.path.insert(0, str(ROOT))
    from pipeline import pricerefresh
    from server import pipeline_routes

    answer = pipeline_routes.do_prices_refresh()
    if answer.get("running"):
        pricerefresh.note_skip("Skipped: another refresh is running.")
        log("skipped: another refresh is running")
        return 0
    for name, step in (pricerefresh.read_status() or {}).get("steps", {}).items():
        extra = {key: value for key, value in step.items() if key not in ("at", "ok")}
        log("%s: %s %s" % (name, "ok" if step.get("ok") else "failed", extra))
    if not (answer["ok"] and (answer["steps"].get("history") or {}).get("ok")):
        log("archive sweep: skipped, refresh failed")
        return 1
    if not sweep:
        log("archive sweep: not run, this run passed --no-sweep")
        return 0
    sweep_archive(pricerefresh)
    return 0


def sweep_archive(pricerefresh):
    """`archive sweep --write` over this checkout's store, saying into the job log, unless today's
    sweep finished. Its exit code 1 is a stop (a second throttle, a host that refused from the first
    sku, an unreadable store the refresh just read) or a pass that wrote no bucket: written buckets
    stay, the `archive` step is not ok and the job still ends 0."""
    from cli import cmd_pricearchive

    if pricerefresh.step_ok_today("archive"):
        log("archive sweep: skipped, today's sweep finished")
        return
    code = cmd_pricearchive.run(
        argparse.Namespace(archive_command="sweep", write=True),
        lambda line: log("archive sweep: " + line) if line else None,
    )
    if code:
        log("archive sweep: stopped early, or wrote no bucket (a throttle, a refused host, an unreadable "
            "store); buckets written so far are kept, the next run resumes")
    pricerefresh.note_step(
        "archive", not code,
        message="Price archive swept." if not code
        else "Price archive sweep stopped early or wrote nothing; buckets written so far are kept.",
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", action="store_true")
    ap.add_argument("--sweep", action="store_true", help="the default; accepted so `make price-refresh ARGS=--sweep` reads plainly")
    ap.add_argument("--no-sweep", action="store_true", help="read only, no archive sweep")
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
    sys.exit(run(sweep=not a.no_sweep or a.sweep))
