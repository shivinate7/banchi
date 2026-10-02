#!/usr/bin/env python3
"""Daily market read (DEBT69). Owner's Mac, main tree only.

Downloads the owner's own live listings once (`server/pipeline_routes.py:do_live_export`, the
one live fetch D104 made), which stores a dated file under `inventory/.live/` and refreshes the
readings table. It then writes a one-line note (`pipeline/pricerefresh.py`) that `#/pricing`
shows, so a failed or missing run is on screen and never a silent stale state.

FREE, AND IT CHANGES NO PRICE. The fetch reads one page of the seller portal and writes nothing
at TCGplayer. It calls no paid read and no archive sweep: the sweep stays a press (D224, DEBT32).
Pushing new live prices stays its own decision (DEBT69).

  price-refresh-daily.py              run once now
  price-refresh-daily.py --agent [--remove]   install / remove the daily launchd job

The installer is `scripts/demo-mirror-daily.py`'s, copied and not shared: that file sits under
a standing auto-merge fence (D295) and is not edited for another job's sake.
"""
import argparse
import fcntl
import os
import plistlib
import subprocess
import sys
import time
from pathlib import Path

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
    plist = Path.home() / "Library" / "LaunchAgents" / (LABEL + ".plist")
    uid = "gui/%d" % os.getuid()
    if remove:
        subprocess.run(["launchctl", "bootout", "%s/%s" % (uid, LABEL)], capture_output=True)
        plist.unlink(missing_ok=True)
        print("removed", LABEL)
        return 0
    if (ROOT / ".git").is_file():
        print("refusing: linked worktree. Install from the main checkout.")
        return 1
    venv = ROOT / ".venv" / "bin" / "python"
    payload = {
        "Label": LABEL,
        "ProgramArguments": [str(venv if venv.exists() else sys.executable), str(HERE)],
        "WorkingDirectory": str(ROOT),
        "StartCalendarInterval": {"Hour": 5, "Minute": 15},
        "StandardOutPath": str(LOG.with_suffix(".out")),
        "StandardErrorPath": str(LOG.with_suffix(".out")),
        "EnvironmentVariables": {"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    }
    plist.parent.mkdir(parents=True, exist_ok=True)
    with open(plist, "wb") as f:
        plistlib.dump(payload, f)
    subprocess.run(["launchctl", "bootout", "%s/%s" % (uid, LABEL)], capture_output=True)
    r = subprocess.run(["launchctl", "bootstrap", uid, str(plist)], capture_output=True, text=True)
    print("bootstrap failed: " + r.stderr.strip() if r.returncode else "installed %s, daily 05:15" % LABEL)
    return r.returncode


def run():
    sys.path.insert(0, str(ROOT))
    from pipeline import pricerefresh
    from server import pipeline_routes

    note = pricerefresh.run(pipeline_routes.do_live_export)
    if note["ok"]:
        log("read %d live rows" % note["live_rows"])
        return 0
    log("failed, readings unchanged: %s %s" % (note["code"], note["message"]))
    return 1


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
