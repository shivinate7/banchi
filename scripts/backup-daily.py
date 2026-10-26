#!/usr/bin/env python3
"""Nightly copy of the photographs and a store snapshot to iCloud Drive (DEBT67). Owner's Mac, main tree only.

The card photographs cannot be re-shot, so they exist in one place without this. One run copies, from
the source root (`store.files.home()`, D43):

  photos/ and captures/   every file, under its own path. A destination file with the source's size and
                          mtime is skipped, decided by `stat` alone: the job never opens a destination
                          file (an evicted iCloud file would download). It never deletes in the
                          destination, so a sold card's photograph (D89) stays.
  inventory/store.sqlite  SQLite's online backup from a read-only connection (`store.db.open_read_only`):
                          no store lock, no write, so the capture server is never waited on. It goes to a
                          temporary name and is renamed, so a failed run leaves the last good snapshot.

The destination is `DEST_ENV` if set, else the default below. Its PARENT must exist; the folder itself is
made on the first night. A missing parent (iCloud Drive is off) is a failed run that creates nothing,
because a local folder made there never syncs and would read as a backup.

The run leaves one line in `<machine dir>/backup-last-run`, which `make status` shows, and exits non-zero
on failure. FIRST COPY ONLY: the second copy on the Home Assistant drive is still on hold (DEBT67).

  backup-daily.py                     run once now
  backup-daily.py --agent [--remove]  install / remove the nightly launchd job
"""
import argparse
import fcntl
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

import launchagent  # scripts/launchagent.py, the shared installer

HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
LABEL = "com.banchi.backup"
DEST_ENV = "BANCHI_BACKUP_DEST"
DEFAULT_DEST = "~/Library/Mobile Documents/com~apple~CloudDocs/Banchi backup"
TREES = ("photos", "captures")
SNAPSHOT = Path("inventory") / "store.sqlite"


def last_run_file():
    return launchagent.machine_dir() / "backup-last-run"


def agent(remove):
    # The launchd stdout file is the last-run file's sibling `.out`: a crash trace for the owner, no log.
    return launchagent.agent(LABEL, HERE, ROOT, 3, 30, last_run_file(), remove)


def copy_tree(source_root, dest_root):
    """(copied, skipped). `os.stat` on the destination only; a changed file is rewritten in place, and
    copy2 sets the mtime last, so a half-written file never matches the source and is copied again."""
    copied = skipped = 0
    for top in TREES:
        for folder, _, names in os.walk(source_root / top):
            for name in names:
                src = Path(folder) / name
                rel = src.relative_to(source_root)
                dst = dest_root / rel
                s = src.stat()
                try:
                    d = dst.stat()
                    if (d.st_size, d.st_mtime_ns) == (s.st_size, s.st_mtime_ns):
                        skipped += 1
                        continue
                except FileNotFoundError:
                    pass
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied += 1
    return copied, skipped


def snapshot(source_root, dest_root):
    from store import db

    dst = dest_root / SNAPSHOT
    tmp = dst.with_name(dst.name + ".tmp")
    dst.parent.mkdir(parents=True, exist_ok=True)
    src = db.open_read_only(source_root / SNAPSHOT)
    try:
        out = sqlite3.connect(tmp)
        try:
            src.backup(out)
        finally:
            out.close()
        os.replace(tmp, dst)
    finally:
        src.close()
        tmp.unlink(missing_ok=True)


def run():
    sys.path.insert(0, str(ROOT))
    from store import files

    dest = Path(os.environ.get(DEST_ENV) or DEFAULT_DEST).expanduser()
    try:
        if not dest.parent.is_dir():
            raise RuntimeError("the destination's parent folder is not there (is iCloud Drive on?): %s" % dest.parent)
        dest.mkdir(exist_ok=True)
        source = files.home()
        copied, skipped = copy_tree(source, dest)
        snapshot(source, dest)
        verdict, ok = "ok copied=%d skipped=%d" % (copied, skipped), 0
    except Exception as exc:  # noqa: BLE001 - every failure is a recorded line and a non-zero exit
        verdict, ok = "failed %s: %s" % (type(exc).__name__, " ".join(str(exc).split())), 1
    line = "%s %s" % (time.strftime("%Y-%m-%dT%H:%M:%S"), verdict)
    last_run_file().write_text(line + "\n")
    print(line)
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", action="store_true")
    ap.add_argument("--remove", action="store_true")
    a = ap.parse_args()
    if a.agent:
        sys.exit(agent(a.remove))
    last_run_file().parent.mkdir(parents=True, exist_ok=True)
    lock = open(last_run_file().with_suffix(".lock"), "w")  # noqa: SIM115 held for the process life
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("skipped: another run holds the lock")
        sys.exit(0)
    sys.exit(run())
