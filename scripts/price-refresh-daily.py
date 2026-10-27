#!/usr/bin/env python3
"""Daily market read (DEBT69), the daily TCGCSV read, then the price archive sweep (D224, DEBT32). Owner's Mac, main tree only.

Runs `server/pipeline_routes.py:do_prices_refresh` once: the owner's live listings (the one live
fetch D104 made), the catalog export per game, a re-join of every open run, then the Trends
strips for the rows still waiting (`docs/specs/stale-listings.md`, 7b). Each step leaves a note
(`pipeline/pricerefresh.py`) that `#/pricing` shows, so a failed or partial run is on screen
and never a silent stale state.

On every start, whatever the refresh did, the same process saves TCGCSV's current Riftbound prices once per
source update (`pipeline.dailyprices`, D-tcgcsv-daily-read): the refresh does not feed it, `--no-sweep` and
`make price-refresh` run it too, and its own check skips an update already saved. Each pass is the `daily_prices`
step of the `#/pricing` note, not ok when a group failed or the pass raised. It never changes the exit code and
never stops the sweep.

After a good refresh (unless `--no-sweep`), the same process runs `archive sweep --write` through
`cli.cmd_pricearchive`, at the pace the last throttle saved (D222), its lines in this job's log.
The owner's word is "nightly, on the Mac", and "if the day is a new day when my mac is on, just get
it done then": the installed job runs at 05:15 and at login (`RunAtLoad`), so it can start many
times a day. Each start skips a refresh that finished today and a sweep that finished today, and
runs whichever is left. A failed refresh or a stopped sweep is not finished, so the next start runs
it again. The sweep has no wall-clock cap and holds the Mac awake never; its pace reads a monotonic
clock, so a sleep does not inflate it. A failed refresh skips the sweep and the log says so. A
sweep that stops (a second throttle, a host that refused from the first sku) or an unreadable
store is a failed `archive` step in the `#/pricing` note, still ends the job with exit 0, and the
next run resumes without re-reading what is fresh. An answered pass that wrote no bucket is ok.
The sweep holds the refresh lock while it reads, so a "Refresh now" press mid-sweep is turned
away. If the server holds that lock when the sweep starts, the sweep waits `LOCK_WAIT_S` and then
skips tonight; the next start runs it. `make price-refresh` is a manual read: it passes `--now`
(refresh even if today's finished) and `--no-sweep`, and sweeps only with `ARGS=--sweep`. The
installed launchd job passes no flag.

FREE, AND IT CHANGES NO PRICE AT TCGPLAYER. It reads the seller portal and the public sales history
and writes nothing there. It calls no paid read. Pushing new live prices stays its own decision (DEBT69).

  price-refresh-daily.py              run the read unless today's finished, then the sweep unless today's finished
  price-refresh-daily.py --now        run the read even if today's finished (`make price-refresh` passes it)
  price-refresh-daily.py --no-sweep   run the read alone (`make price-refresh` passes it)
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

LOCK_WAIT_S = 30 * 60  # how long the sweep waits for a server refresh to end before it skips tonight
LOCK_POLL_S = 30
REFRESH_STEPS = ("listings", "catalog", "join", "history")

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


def run(sweep=True, now=False):
    sys.path.insert(0, str(ROOT))
    from pipeline import pricerefresh

    stopped = refresh(pricerefresh, now)
    read_daily_prices(pricerefresh)
    if stopped is not None:
        return stopped
    if not sweep:
        log("archive sweep: not run, this run passed --no-sweep")
        return 0
    sweep_archive(pricerefresh)
    return 0


def refresh(pricerefresh, now):
    """The refresh, unless today's finished. `None` when the sweep may follow, else the job's exit code."""
    from server import pipeline_routes

    if not now and all(pricerefresh.step_ok_today(name) for name in REFRESH_STEPS):
        log("refresh: skipped, today's refresh finished")
        return None
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
    return None


def read_daily_prices(pricerefresh):
    """One pass of the daily TCGCSV read: a line in the job log and the `daily_prices` step of the note. The
    User-Agent is the sweep's own knob. A raise is a not-ok step and never fails the job."""
    from cli import cmd_pricearchive
    from pipeline import dailyprices

    try:
        answer = dailyprices.run_pass(user_agent=cmd_pricearchive._user_agent())
    except Exception as exc:  # noqa: BLE001 the read is free and retried at the next start; it never fails the job
        log("daily prices: failed (%s: %s)" % (type(exc).__name__, exc))
        pricerefresh.note_step("daily_prices", False, message="Daily prices could not be read. The next run tries again.")
        return
    failed = answer["failed"]
    if answer["skipped"]:
        log("daily prices: skipped, the update of %s is already saved" % answer["updated"])
        message = "Daily prices for %s are already saved." % answer["day"]
    else:
        log("daily prices: %d rows saved for %s, %d group(s) failed%s" % (
            answer["rows"], answer["day"], len(failed),
            " (%s)" % ", ".join(map(str, sorted(failed))) if failed else "",
        ))
        message = (
            "Daily prices saved with %d set(s) missing; the next run asks for them." % len(failed) if failed
            else "Daily prices saved: %d rows for %s." % (answer["rows"], answer["day"])
        )
    pricerefresh.note_step("daily_prices", not failed, message=message)


def sweep_archive(pricerefresh):
    """`archive sweep --write` over this checkout's store, saying into the job log, unless today's
    sweep finished. It holds `refresh_lock` while it reads, so a "Refresh now" press mid-sweep is
    turned away. A server refresh already holding the lock is waited for, `LOCK_WAIT_S` at most, and
    then tonight's sweep is skipped (the next run of this job sweeps). Exit code 1 is a stop (a
    second throttle, a host that refused from the first sku, an unreadable store the refresh just
    read): written buckets stay, the `archive` step is not ok and the job still ends 0."""
    from cli import cmd_pricearchive

    if pricerefresh.step_ok_today("archive"):
        log("archive sweep: skipped, today's sweep finished")
        return
    deadline = time.monotonic() + LOCK_WAIT_S
    while True:
        with pricerefresh.refresh_lock() as held:
            if held:
                code = cmd_pricearchive.run(
                    argparse.Namespace(archive_command="sweep", write=True),
                    lambda line: log("archive sweep: " + line) if line else None,
                )
                break
        if time.monotonic() >= deadline:
            log("archive sweep: skipped, a refresh from the server is still running; the next run of this job sweeps")
            return
        time.sleep(LOCK_POLL_S)
    if code:
        log("archive sweep: stopped early (a throttle, a refused host, an unreadable store); "
            "buckets written so far are kept, the next run resumes")
    pricerefresh.note_step(
        "archive", not code,
        message="Price archive swept." if not code
        else "Price archive sweep stopped early; buckets written so far are kept.",
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", action="store_true")
    ap.add_argument("--sweep", action="store_true", help="the default; accepted so `make price-refresh ARGS=--sweep` reads plainly")
    ap.add_argument("--no-sweep", action="store_true", help="read only, no archive sweep")
    ap.add_argument("--now", action="store_true", help="refresh even if today's refresh finished (a manual press)")
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
    sys.exit(run(sweep=not a.no_sweep or a.sweep, now=a.now))
