#!/usr/bin/env python3
"""One-time copy of the photographs and a store snapshot to iCloud Drive (DEBT67). Owner's Mac, main tree only.

The owner runs this by hand, once or when wanted. The launchd agent (`--agent`) is not installed. The card
photographs cannot be re-shot, so they exist in one place without this. One run copies, from the source root
(`store.files.home()`, D43):

  photos/ and captures/   every file, under its own path. A destination file is NEVER overwritten. One that
                          is missing is copied. One that has the source's size and mtime is skipped. One
                          that exists with another size or mtime is left untouched and counted as `differs`
                          (a re-shoot, D26, looks like this): the run ends `failed` and names the count.
                          Accepting a re-shoot is a manual act: delete its copy by hand, then run again.
                          The decision is made by `stat` alone: the default run never opens a destination
                          file (an evicted iCloud file would download). It never deletes in the destination,
                          so a sold card's photograph (D89) stays. A file is copied beside its place under
                          a `.tmp` name and renamed in, so a killed run leaves no half file to read as a
                          differing copy.
  inventory/store.sqlite  SQLite's online backup from a read-only connection (`store.db.open_read_only`):
                          no store lock, no write, so the capture server is never waited on. It is made
                          FIRST, in a local temp folder, and `PRAGMA integrity_check` must say `ok` before
                          anything is moved in: a damaged store replaces nothing and fails the run. Only
                          the finished file is moved in, so a failed or killed run leaves the last good
                          snapshot and no temp file.
  DATED_SNAPSHOT          `inventory/store-<YYYY-MM-DD>.sqlite`, the same snapshot under the day's name,
                          never replacing an existing file of that name. A second run the same day keeps
                          the day's first copy.
  WEEKLY_SNAPSHOT         a second snapshot, replaced from the same night's snapshot only when its file is
                          7 days old (by mtime) or more. A night whose snapshot fails replaces neither.

One file that cannot be read does not stop the run: the rest are copied and the run ends `failed` with the
count. A source with no `photos/` tree fails. In a linked worktree the job refuses unless `DEST_ENV` is set.

The destination is `DEST_ENV` if set, else the default below. Its PARENT must exist; the folder itself is
made on the first run. A missing parent (iCloud Drive is off) is a failed run that creates nothing,
because a local folder made there never syncs and would read as a backup.

The sidecar `SIDECAR` holds the last good run's `cards` and `boxes` counts. On a night the weekly is due, a count
more than half below it replaces neither snapshot and fails the night; delete the sidecar to accept a real shrink.
A linked worktree with `DEST_ENV` set writes nothing to the machine folder but a lock.

The run leaves one line in `<machine dir>/backup-last-run`, which `make status` shows, and exits non-zero
on failure. FIRST COPY ONLY: the second copy on the Home Assistant drive is still on hold (DEBT67).

  backup-daily.py                     run once now
  backup-daily.py --verify            read-only: sha256 of every source file in photos/ and captures/ against
                                      the destination, and the newest dated snapshot's integrity. Reads the
                                      destination on purpose (it downloads evicted iCloud files). Prints
                                      matches, mismatches and missing; exits non-zero on any mismatch or missing.
  backup-daily.py --agent [--remove]  install / remove the nightly launchd job (kept; not installed)
"""
import argparse
import fcntl
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
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
WEEKLY_SNAPSHOT = "inventory/store-weekly.sqlite"
DATED_SNAPSHOT = "inventory/store-%s.sqlite"  # % the local date, YYYY-MM-DD
WEEK_NS = 7 * 86400 * 10**9
SLACK_NS = 2 * 10**9  # a synced folder rounds mtimes
SIDECAR = "backup-last-counts.json"  # `cards` and `boxes` row counts of the last good run, beside the last-run file
COUNTED = ("cards", "boxes")


def last_run_file():
    return launchagent.machine_dir() / "backup-last-run"


def sidecar_file():
    return last_run_file().with_name(SIDECAR)


def status_line():
    """The last-run line for `make status`, or a line saying none has run, with a stale mark past 36 hours.
    An absent file is not an error: the job never runs in a worktree or on CI."""
    try:
        line = last_run_file().read_text().strip()
    except OSError:
        line = ""
    try:
        old = time.time() - time.mktime(time.strptime(line[:19], "%Y-%m-%dT%H:%M:%S")) > 36 * 3600
    except ValueError:
        old = False
    if old:
        line += "  (stale: older than 36 hours)"
    return line or "no backup has run (`make backup` copies once; `make backup ARGS=--verify` checks the copy)"


def linked():
    """A linked worktree shares ~/.banchi with every checkout (D43), so it writes nothing there but a lock."""
    return (ROOT / ".git").is_file()


def agent(remove):
    # The launchd stdout file is the last-run file's sibling `.out`: a crash trace for the owner, no log.
    return launchagent.agent(LABEL, HERE, ROOT, 3, 30, last_run_file(), remove)


def copy_tree(source_root, dest_root):
    """(copied, skipped, differs, bad). `os.stat` on the destination only. A destination file is never
    replaced: one whose size or mtime differs from the source's is left as it is and its path goes in
    `differs`. A missing one is copied (`move_in` keeps the mtime and renames last, so a killed run leaves
    no half file for the next run to read as a differing copy). A file that cannot be read or written
    is counted in `bad` and the walk goes on."""
    if not (source_root / "photos").is_dir():
        raise RuntimeError("the source has no photos/ folder (wrong BANCHI_HOME?): %s" % source_root)
    copied = skipped = 0
    differs = []
    bad = []  # os.walk skips a folder it cannot list unless asked: each one counts as a bad file
    for top in TREES:
        if not (source_root / top).is_dir():  # a missing captures/ is not bad
            continue
        for folder, _, names in os.walk(source_root / top, onerror=bad.append):
            for name in names:
                src = Path(folder) / name
                dst = dest_root / src.relative_to(source_root)
                try:
                    s = src.stat()
                    try:
                        d = dst.stat()
                    except FileNotFoundError:
                        move_in(src, dst, replace=False)
                        copied += 1
                        continue
                    if d.st_size == s.st_size and abs(d.st_mtime_ns - s.st_mtime_ns) < SLACK_NS:
                        skipped += 1
                    else:
                        differs.append(src.relative_to(source_root))
                except OSError:
                    bad.append(src)
    return copied, skipped, differs, len(bad)


def move_in(local, dst, replace=True):
    """Copy a finished local file beside `dst` and rename it into place: a reader never sees half a file.
    `replace=False` never touches an existing `dst` (the check and the rename are not atomic together, which
    the run's lock covers). Returns whether `dst` was written."""
    if not replace and dst.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".tmp")
    try:
        shutil.copy2(local, tmp)
        os.replace(tmp, dst)
    finally:
        tmp.unlink(missing_ok=True)
    return True


def read_counts(path):
    """The sidecar's counts, or None: no sidecar (a first night) or one that cannot be read."""
    try:
        counts = json.loads(path.read_text())
        return {t: int(counts[t]) for t in COUNTED}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def snapshot(source_root, dest_root, last_good=None):
    """Make the snapshots; return tonight's `cards` and `boxes` counts, read from the local copy. The local copy
    must pass `PRAGMA integrity_check` before anything is moved in: SQLite's online backup copies a damaged page
    without reading it. On a night the weekly is due, a count more than half below `last_good` (the shrink guard)
    replaces neither snapshot. The dated copy never replaces a file of its name."""
    from store import db

    with tempfile.TemporaryDirectory() as folder:
        local = Path(folder) / "store.sqlite"
        src = db.open_read_only(source_root / SNAPSHOT)
        try:
            out = sqlite3.connect(local)
            try:
                src.backup(out)
            finally:
                out.close()
        finally:
            src.close()
        conn = sqlite3.connect(local)
        try:
            try:
                verdict = conn.execute("PRAGMA integrity_check").fetchall()
            except sqlite3.DatabaseError as exc:  # a page too damaged to walk raises instead of reporting
                verdict = [(str(exc),)]
            if verdict != [("ok",)]:
                raise RuntimeError("the store copy failed its integrity check, nothing moved in: %s" % verdict[0][0][:120])
            counts = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in COUNTED}
        finally:
            conn.close()
        weekly = dest_root / WEEKLY_SNAPSHOT
        try:
            due = time.time_ns() - weekly.stat().st_mtime_ns >= WEEK_NS
        except FileNotFoundError:
            due = True
        if due and last_good:
            shrunk = ["%s %d to %d" % (t, last_good[t], counts[t]) for t in COUNTED if counts[t] * 2 < last_good[t]]
            if shrunk:
                raise RuntimeError("the store shrank by more than half (%s); neither snapshot replaced" % ", ".join(shrunk))
        move_in(local, dest_root / SNAPSHOT)
        move_in(local, dest_root / (DATED_SNAPSHOT % time.strftime("%Y-%m-%d")), replace=False)
        if due:
            move_in(local, weekly)
    return counts


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(source_root, dest_root):
    """(matches, mismatches, missing, snapshot name, integrity) of the destination against the source. Read-only.
    Reads destination files on purpose, unlike the default run. A file that cannot be read, a folder that
    cannot be listed and a store copy that cannot be opened count as a mismatch, never as a match."""
    matches, mismatches, missing = 0, [], []
    for top in TREES:
        if not (source_root / top).is_dir():
            continue
        for folder, _, names in os.walk(source_root / top, onerror=lambda exc: mismatches.append(Path(exc.filename))):
            for name in names:
                src = Path(folder) / name
                dst = dest_root / src.relative_to(source_root)
                try:
                    if not dst.is_file():
                        missing.append(src.relative_to(source_root))
                    elif dst.stat().st_size == src.stat().st_size and sha256(src) == sha256(dst):
                        matches += 1
                    else:
                        mismatches.append(src.relative_to(source_root))
                except OSError:
                    mismatches.append(src.relative_to(source_root))
    newest = sorted((dest_root / SNAPSHOT).parent.glob(Path(DATED_SNAPSHOT % "????-??-??").name))
    if not newest:
        return matches, mismatches, missing, "none", "none"
    try:
        # immutable: no lock and no -wal or -shm file beside a copy in a synced folder
        conn = sqlite3.connect("%s?immutable=1" % newest[-1].as_uri(), uri=True)
        try:
            integrity = "ok" if conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)] else "bad"
        finally:
            conn.close()
    except sqlite3.Error:
        integrity = "bad"
    return matches, mismatches, missing, newest[-1].name, integrity


def destination():
    return Path(os.environ.get(DEST_ENV) or DEFAULT_DEST).expanduser()


def run_verify():
    sys.path.insert(0, str(ROOT))
    from store import files

    matches, mismatches, missing, snap, integrity = verify(files.home(), destination())
    print("verify: matches=%d mismatches=%d missing=%d snapshot=%s integrity=%s" % (matches, len(mismatches), len(missing), snap, integrity))
    for label, found in (("mismatch", mismatches), ("missing", missing)):
        for rel in found:
            print("%s %s" % (label, rel))
    return 0 if integrity == "ok" and not mismatches and not missing else 1


def run():
    sys.path.insert(0, str(ROOT))
    from store import files

    dest = destination()
    problems = []
    differs = []
    counts = None
    try:
        if not dest.parent.is_dir():
            raise RuntimeError("the destination's parent folder is not there (is iCloud Drive on?): %s" % dest.parent)
        dest.mkdir(exist_ok=True)
        source = files.home()
        try:
            counts = snapshot(source, dest, None if linked() else read_counts(sidecar_file()))
        except Exception as exc:  # noqa: BLE001 - the photographs are copied anyway; the night still fails
            problems.append("snapshot failed: %s: %s" % (type(exc).__name__, " ".join(str(exc).split())))
        copied, skipped, differs, bad = copy_tree(source, dest)
        if differs:
            problems.append(
                "%d files differ from their copies and were left untouched (a re-shoot looks like this; "
                "to accept one, delete its copy by hand and run again)" % len(differs)
            )
        if bad:
            problems.append("%d files could not be copied" % bad)
        verdict, ok = "ok copied=%d skipped=%d" % (copied, skipped), 0
        if problems:
            verdict, ok = "failed " + "; ".join(problems), 1
    except Exception as exc:  # noqa: BLE001 - every failure is a recorded line and a non-zero exit
        verdict, ok = "failed %s: %s" % (type(exc).__name__, " ".join(str(exc).split())), 1
        if problems:
            verdict += "; " + "; ".join(problems)
    line = "%s %s" % (time.strftime("%Y-%m-%dT%H:%M:%S"), verdict)
    if not linked():
        last_run_file().write_text(line + "\n")
        if not ok:
            sidecar_file().write_text(json.dumps(counts) + "\n")  # a good run only: the next night compares to it
    print(line)
    for rel in differs[:20]:
        print("differs %s" % rel)
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", action="store_true")
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if a.agent:
        sys.exit(agent(a.remove))
    if (ROOT / ".git").is_file() and not os.environ.get(DEST_ENV):
        # A linked worktree shares ~/.banchi, so even the last-run line stays unwritten.
        sys.exit("refused: this is a linked worktree; the backup runs from the main tree (or set %s)" % DEST_ENV)
    if a.verify:  # read-only: no machine folder, no lock, no last-run line
        sys.exit(run_verify())
    last_run_file().parent.mkdir(parents=True, exist_ok=True)
    lock = open(last_run_file().with_suffix(".lock"), "w")  # noqa: SIM115 held for the process life
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("skipped: another run holds the lock")
        sys.exit(0)
    sys.exit(run())
