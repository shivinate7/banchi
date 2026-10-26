"""T7 group: the nightly backup to the iCloud Drive folder (DEBT67, capture photographs exist in one place).

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.

THE CONTRACT THE BUILD MEETS. The checks are written first, so every name the build needs is pinned here:

  scripts/backup-daily.py     the job, modelled on `scripts/price-refresh-daily.py` (DEBT69).
                              No flag: run once, exit 0 for ok and non-zero for failed.
                              `--agent [--remove]` installs or removes the launchd job.
                              Module names `LABEL = "com.banchi.backup"`, `ROOT` (the checkout) and
                              `agent(remove)`, which calls `launchagent.agent` (`scripts/launchagent.py`).
  make backup                 `scripts/backup-daily.py`, once, now.
  make backup-agent           `scripts/backup-daily.py --agent $(ARGS)`; `ARGS=--remove` removes it.
  BANCHI_HOME                 the source root, as `store.files.home()` (D43): `inventory/store.sqlite`,
                              `photos/` (D172) and `captures/`.
  DEST_ENV                    a module constant of the job: the name of the variable that overrides the
                              destination folder. The build picks the BANCHI-prefixed name (D94) and
                              documents it; the checks read the name from this constant and keep no copy.
                              Default `~/Library/Mobile Documents/com~apple~CloudDocs/Banchi backup`.
  the destination layout      the source layout: `inventory/store.sqlite`, `photos/...`, `captures/...`.
  the destination rule        its PARENT must exist; the folder itself is made on the first night. A
                              missing parent (iCloud Drive is off) is a failed run that creates nothing,
                              because a local folder made there never syncs and would read as a backup.
  the snapshot                SQLite's online backup from a read-only connection (`store.db.open_read_only`).
                              It takes neither the store lock nor a write, so the capture server is never
                              waited on. It is written under a temporary name and renamed, so a failed run
                              leaves the last good snapshot, and `inventory/` holds only `store.sqlite`.
  the copy                    every file under `photos/` and `captures/`. A destination file with the
                              source's size and mtime is skipped, decided by `stat` alone: the job never
                              opens a destination file (an evicted iCloud file would download). It never
                              deletes in the destination, so a sold card's photograph (D89) stays.
  the last-run line           `<machine dir>/backup-last-run` (`~/.banchi/`, `ports.machine_dir`), one line,
                              overwritten each run: `%Y-%m-%dT%H:%M:%S ok copied=N skipped=M` or
                              `%Y-%m-%dT%H:%M:%S failed <reason>`. N and M count the files of `photos/` and
                              `captures/` written and skipped; the snapshot is not counted. A lock file
                              beside it is allowed; nothing else is written there.
  scripts/status.py           `backup() -> List[str]`, called by `render()`: the last-run line, or a line
                              saying no backup has run. Never an empty list.

WHAT THE CHECKS DO NOT RUN. `--agent` is never executed: it bootstraps a real launchd job. The agent half is
proved through the module with a fake `launchctl` first on PATH, a fake HOME and a fake checkout root.

EVERY CHECK PAIRS A NEGATIVE WITH A POSITIVE. A missing script exits 2 and touches nothing, which would pass
"exits non-zero", "left the source alone" and "kept the destination file" for a job that does nothing. So each
of those is asserted beside a run that reported ok and copied, or beside the recorded `failed` line.

Temp files: one run folder `<pid>-<uuid>` under the repo's temp root (`harness/tests/home.py:run_folder`,
test-temp-standard). No `TemporaryDirectory`, no `isolated_home`. The first check proves the sweep.
"""

from __future__ import annotations

import ast
import contextlib
import functools
import hashlib
import importlib.util
import io
import os
import plistlib
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import namedtuple
from pathlib import Path
from unittest import mock

from harness.tests import Checks
from harness.tests.home import RUN_MAX_AGE, TEMP_ROOT, remove_tree, run_folder, sweep
from harness.tests.t7.common import REPO_ROOT
from store import db, files

SCRIPT = REPO_ROOT / "scripts" / "backup-daily.py"
STATUS = REPO_ROOT / "scripts" / "status.py"
LABEL = "com.banchi.backup"
#: Under the store lock's own 30 s wait, so a job that queues behind the lock is seen waiting.
TIMEOUT = 20
LAST_RUN = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d) (ok|failed)(?: (.*))?$")
T0 = 1_700_000_000 * 10**9  # a fixed source mtime in ns, so "newer" is a plain addition
SECOND = 10**9
Ran = namedtuple("Ran", "code out err")
DEFAULT = object()

#: Five files in the shapes the store writes: sharded photographs (D172) and box captures.
FILES = {
    "photos/6b/6b1cf2fd0001.jpg": b"\xff\xd8\xff" + b"A" * 700,
    "photos/a0/a0aa11220002.jpg": b"\xff\xd8\xff" + b"B" * 650,
    "captures/cards/box1/0001.jpg": b"\xff\xd8\xff" + b"C" * 600,
    "captures/cards/box1/0001.json": b'{"box": 1, "index": 1}',
    "captures/cards/box2/0001.jpg": b"\xff\xd8\xff" + b"D" * 500,
}


# ------------------------------------------------------------------------------ fixtures


def robust(fn):
    """A check that raises reads as one failed line with its sentence, never as a traceback
    that hides the rest of the group (the build may not exist yet)."""
    @functools.wraps(fn)
    def run(checks: Checks) -> None:
        try:
            fn(checks)
        except Exception as exc:  # noqa: BLE001
            checks.ok(False, f"{fn.__name__} ran to the end", f"{type(exc).__name__}: {exc}")
    return run


class Case:
    """One case's folders, all inside the run folder: a fake HOME, a source store root, a destination."""

    def __init__(self, name: str):
        self.root = run_folder() / name
        if self.root.exists():
            remove_tree(self.root)
        self.home, self.src, self.dest = self.root / "home", self.root / "src", self.root / "dest"
        for folder in (self.home, self.src):
            folder.mkdir(parents=True)

    @property
    def last_run_file(self) -> Path:
        return self.home / ".banchi" / "backup-last-run"

    @property
    def icloud_root(self) -> Path:
        return self.home / "Library" / "Mobile Documents" / "com~apple~CloudDocs"


def seed_store(case: Case, rows: int = 3) -> None:
    """A cold store with the real schema (D88): the connection is closed, so no WAL is left."""
    conn = db.connect(case.src / "inventory")
    try:
        for i in range(rows):
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (f"seed-{i}", str(i)))
    finally:
        conn.close()


def put(root: Path, rel: str, data: bytes, mtime: int = T0) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.utime(path, ns=(mtime, mtime))
    return path


def seed_files(case: Case, wanted: dict = FILES) -> None:
    for rel, data in wanted.items():
        put(case.src, rel, data)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(root: Path) -> dict:
    """What a failed or read-only run must leave alone: every photograph and capture, and the store's main file."""
    found = {}
    for top in ("photos", "captures"):
        for path in sorted((root / top).rglob("*")):
            if path.is_file():
                found[path.relative_to(root).as_posix()] = (path.stat().st_size, path.stat().st_mtime_ns, sha(path))
    main = root / "inventory" / "store.sqlite"
    if main.is_file():
        found["inventory/store.sqlite"] = (main.stat().st_size, main.stat().st_mtime_ns, sha(main))
    return found


def dest_files(case: Case) -> dict:
    return {p.relative_to(case.dest).as_posix(): p for p in sorted(case.dest.rglob("*")) if p.is_file()}


def stat_key(path: Path) -> tuple:
    """Changes on any rewrite, in place or by rename: the inode, size, mtime and ctime."""
    st = path.stat()
    return (st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def dest_env():
    """The destination-override variable, read from the job's own `DEST_ENV` constant (the allow list
    points at the constant the code emits, never a copy). None when the job or the constant is absent."""
    try:
        tree = ast.parse(SCRIPT.read_text())
    except (OSError, SyntaxError):
        return None
    for node in tree.body:
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
                and any(isinstance(t, ast.Name) and t.id == "DEST_ENV" for t in node.targets)):
            return node.value.value
    return None


def run_job(case: Case, dest=DEFAULT) -> Ran:
    """The job as launchd runs it: a fresh process, a fake HOME, the source and destination named by env.

    HOME is overridden so `~/.banchi` and the default iCloud path land in the run folder even when the
    build ignores the destination override. `dest=None` leaves the destination to its default.
    """
    name = dest_env()
    if name is None:
        return Ran(None, "", "scripts/backup-daily.py does not define the DEST_ENV constant")
    env = dict(os.environ)
    env.pop("BANCHI_SLOT_REGISTRY", None)
    env.update(HOME=str(case.home), BANCHI_HOME=str(case.src))
    if dest is None:
        env.pop(name, None)
    else:
        env[name] = str(case.dest if dest is DEFAULT else dest)
    try:
        done = subprocess.run(
            [sys.executable, str(SCRIPT)], cwd=case.root, env=env, capture_output=True, text=True, timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return Ran(None, "", f"no answer in {TIMEOUT} s")
    return Ran(done.returncode, done.stdout, done.stderr)


def last_run(case: Case):
    """The parsed last-run line, or None when there is no file."""
    try:
        text = case.last_run_file.read_text()
    except OSError:
        return None
    lines = text.splitlines()
    match = LAST_RUN.match(lines[0]) if len(lines) == 1 else None
    rest = (match.group(3) or "") if match else ""
    count = lambda key: (int(m.group(1)) if (m := re.search(rf"\b{key}=(\d+)\b", rest)) else None)  # noqa: E731
    return {
        "lines": len(lines), "at": match and match.group(1), "verdict": match and match.group(2),
        "copied": count("copied"), "skipped": count("skipped"), "raw": text,
    }


def said(ran: Ran) -> str:
    return f"exit {ran.code}; stderr: {ran.err.strip()[-400:]}"


def expect_ok(checks: Checks, label: str, ran: Ran, case: Case, copied: int, skipped: int) -> bool:
    """The positive a negative hangs on: a run that exited 0, recorded ok, and reported these counts."""
    line = last_run(case) or {}
    got = (ran.code, line.get("verdict"), line.get("copied"), line.get("skipped"))
    want = (0, "ok", copied, skipped)
    return checks.ok(got == want, label, f"expected (exit, verdict, copied, skipped) {want}; got {got}\n{said(ran)}")


def expect_failed(checks: Checks, label: str, ran: Ran, case: Case) -> bool:
    """Exit non-zero AND a recorded `failed` line together: the exit alone is what a missing script gives."""
    line = last_run(case) or {}
    ok = ran.code not in (0, None) and line.get("verdict") == "failed"
    return checks.ok(ok, label, f"exit {ran.code}, last-run {line.get('raw')!r}\n{said(ran)}")


def rows_from(conn: sqlite3.Connection) -> dict:
    """Every table's rows, order-free: the whole of what a snapshot must equal."""
    out = {}
    # A virtual table (the FTS index) is rebuilt from its shadow tables, which are compared as plain tables.
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND sql NOT LIKE 'CREATE VIRTUAL%' ORDER BY name")
    for (name,) in tables.fetchall():
        out[name] = sorted(repr(row) for row in conn.execute(f'SELECT * FROM "{name}"'))
    return out


def committed_rows(path: Path) -> dict:
    conn = db.open_read_only(path)
    try:
        return rows_from(conn)
    finally:
        conn.close()


def snapshot_view(case: Case):
    """(rows, integrity) of the destination snapshot, read from a copy elsewhere so reading it leaves no
    `-wal` or `-shm` beside the file under test. (None, why) when it cannot be opened."""
    snap = case.dest / "inventory" / "store.sqlite"
    if not snap.is_file():
        return None, f"no snapshot at {snap}"
    probe = case.root / "verify" / "store.sqlite"
    probe.parent.mkdir(exist_ok=True)
    shutil.copyfile(snap, probe)
    try:
        conn = sqlite3.connect(probe)
        try:
            return rows_from(conn), conn.execute("PRAGMA integrity_check").fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return None, str(exc)


def make_readonly(root: Path) -> None:
    for folder in [root, *[p for p in root.rglob("*") if p.is_dir()]]:
        folder.chmod(0o500)


def remove_tree_perms(root: Path) -> None:
    """Open a tree the case made read-only again, so the next read in the case works."""
    for path in [root, *root.rglob("*")]:
        with contextlib.suppress(OSError):
            path.chmod(0o755 if path.is_dir() else 0o644)


# ------------------------------------------------------------------------------ the checks


@robust
def check_backup_run_folder_sweep(checks: Checks) -> None:
    """test-temp-standard: this group's files live in one `<pid>-<uuid>` run folder, and the first
    request of a run removes sibling folders older than a day and keeps newer ones."""
    checks.note("")
    checks.note("NIGHTLY BACKUP — the group's temp files, then the job")
    folder = run_folder()
    checks.ok(
        folder.parent == TEMP_ROOT and re.fullmatch(rf"{os.getpid()}-[0-9a-f-]{{36}}", folder.name) is not None,
        "the group's temp files live in one <pid>-<uuid> run folder under the repo's one temp root",
        str(folder),
    )
    siblings = folder / "siblings"
    old, new = siblings / "1-old", siblings / "2-new"
    (old / "locked").mkdir(parents=True)
    (old / "locked" / "file").write_text("x")
    (old / "locked").chmod(0o500)
    new.mkdir()
    stamp = time.time() - 2 * RUN_MAX_AGE
    os.utime(old, (stamp, stamp))
    sweep(siblings)
    checks.ok(not old.exists() and new.exists(), "the sweep removes an old sibling, even a read-only one, and keeps a new one",
              f"old exists={old.exists()}, new exists={new.exists()}")


@robust
def check_backup_snapshot_beside_an_open_writer(checks: Checks) -> None:
    """The store is snapshotted while the capture server's writer holds the store lock and an open
    transaction: the snapshot is a valid file equal to what was committed, and nothing is disturbed.

    THE COMMITTED ROWS LIVE ONLY IN `-wal` (autocheckpoint is off on the writer), so a copy of
    `store.sqlite` alone misses them. The fixture proves it can tell that copy from a snapshot.
    """
    case = Case("snapshot")
    inv = case.src / "inventory"
    seed_files(case)
    conn = db.connect(inv)
    try:
        conn.execute("PRAGMA wal_autocheckpoint = 0")
        conn.execute("BEGIN")
        for i in range(50):
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (f"seed-{i}", str(i)))
        conn.execute("COMMIT")
        expected = committed_rows(inv / "store.sqlite")
        raw = case.root / "raw" / "store.sqlite"
        raw.parent.mkdir()
        shutil.copyfile(inv / "store.sqlite", raw)
        try:
            raw_conn = sqlite3.connect(raw)
            try:
                raw_rows = rows_from(raw_conn)
            finally:
                raw_conn.close()
        except sqlite3.Error:
            raw_rows = None
        discriminates = raw_rows != expected  # a copy of the live file lacks the committed rows, which sit in -wal

        with files.exclusive(inv):
            conn.execute("BEGIN IMMEDIATE")
            for i in range(5):
                conn.execute("INSERT INTO meta (key, value) VALUES (?, ?)", (f"dirty-{i}", "uncommitted"))
            watched = [inv / "store.sqlite", inv / "store.sqlite-wal"]
            before = {p.name: sha(p) for p in watched if p.is_file()}
            ran = run_job(case)
            after = {p.name: sha(p) for p in watched if p.is_file()}
            conn.execute("COMMIT")
        survived = conn.execute("SELECT COUNT(*) FROM meta WHERE key LIKE 'dirty-%'").fetchone()[0]
    finally:
        conn.close()

    finished = expect_ok(checks, "the job finishes ok while a writer holds the store lock and an open transaction",
                         ran, case, copied=len(FILES), skipped=0)
    rows, integrity = snapshot_view(case)
    checks.equal(integrity, [("ok",)], "the snapshot passes SQLite's integrity check, read on its own")
    checks.ok(
        discriminates and rows == expected,
        "the snapshot equals the committed rows of every table and holds none of the open transaction's (a copy of the live file would not)",
        "the fixture cannot tell a live-file copy from a snapshot" if not discriminates else
        ("snapshot and source differ" if rows else str(integrity)),
    )
    listing = sorted(p.name for p in (case.dest / "inventory").iterdir()) if (case.dest / "inventory").is_dir() else None
    checks.equal(listing, ["store.sqlite"], "the destination's inventory/ holds the one snapshot file and no -wal, -shm or temp file")
    checks.ok(finished and before and before == after, "the source store file and its -wal are byte for byte what they were", f"{before} / {after}")
    checks.ok(finished and survived == 5, "the writer's transaction was not disturbed: it commits after the job", str(survived))


@robust
def check_backup_copies_and_skips_by_stat(checks: Checks) -> None:
    """Photographs and captures are copied once, an unchanged file is not rewritten, a changed one is."""
    case = Case("copy")
    seed_store(case)
    seed_files(case)
    first = run_job(case)
    expect_ok(checks, "first night: all five files copied, none skipped", first, case, copied=5, skipped=0)
    same = {rel: (dest_path.read_bytes() == FILES.get(rel)) for rel, dest_path in dest_files(case).items() if rel in FILES}
    checks.ok(len(same) == 5 and all(same.values()), "every photograph and capture is in the destination, byte for byte, under its own path")
    checks.equal(
        sorted(dest_files(case)), sorted([*FILES, "inventory/store.sqlite"]),
        "and nothing else is there: no temp file, no stray",
    )
    stats = {rel: stat_key(p) for rel, p in dest_files(case).items() if rel in FILES}

    second = run_job(case)
    expect_ok(checks, "second night, nothing changed: none copied, all five skipped", second, case, copied=0, skipped=5)
    checks.ok(
        stats and stats == {rel: stat_key(p) for rel, p in dest_files(case).items() if rel in FILES},
        "an unchanged file is not rewritten: inode, size, mtime and ctime are all as they were",
    )

    changed = "photos/a0/a0aa11220002.jpg"
    put(case.src, changed, bytes(reversed(FILES[changed])), mtime=T0 + 10 * SECOND)  # same size, other bytes, newer
    put(case.src, "photos/ff/ff00ee330003.jpg", b"\xff\xd8\xff" + b"E" * 400)
    source_before = fingerprint(case.src)
    third = run_job(case)
    expect_ok(checks, "third night, one file changed and one added: two copied, four skipped", third, case, copied=2, skipped=4)
    got = dest_files(case)
    checks.ok(
        changed in got and got[changed].read_bytes() == bytes(reversed(FILES[changed])),
        "a source file with the same size and a newer mtime replaces its copy",
    )
    checks.ok("photos/ff/ff00ee330003.jpg" in got, "and the new photograph is copied")
    checks.ok(
        all(rel in stats and rel in got and stats[rel] == stat_key(got[rel]) for rel in FILES if rel != changed),
        "the four unchanged files still were not rewritten",
    )
    checks.ok(third.code == 0 and source_before == fingerprint(case.src), "the source files are as the job found them")


@robust
def check_backup_never_deletes_in_the_destination(checks: Checks) -> None:
    """The destination only grows. A card sold and reclaimed (D89) deletes its photograph at the source;
    the backup keeps it, and a file only the destination holds is left alone."""
    case = Case("keep")
    seed_store(case)
    seed_files(case)
    expect_ok(checks, "first night copies the five files", run_job(case), case, copied=5, skipped=0)
    planted = {
        "photos/zz/only-here.jpg": b"only the destination holds this",
        "old-note.txt": b"a file at the top",
        "extra-dir/deep/x.bin": b"\x00\x01\x02",
    }
    for rel, data in planted.items():
        put(case.dest, rel, data)
    sold = "photos/6b/6b1cf2fd0001.jpg"
    (case.src / sold).unlink()
    put(case.src, "photos/c1/c1ab99440004.jpg", b"\xff\xd8\xff" + b"F" * 300)

    second = run_job(case)
    ran_ok = expect_ok(checks, "next night, one photograph reclaimed at the source and one added: one copied", second, case, copied=1, skipped=4)
    got = dest_files(case)
    checks.ok(ran_ok and sold in got and got[sold].read_bytes() == FILES[sold], "the reclaimed photograph is still in the destination, unchanged")
    checks.ok(
        ran_ok and all(rel in got and got[rel].read_bytes() == data for rel, data in planted.items()),
        "files only the destination holds are untouched",
    )


@robust
def check_backup_never_reads_the_destination(checks: Checks) -> None:
    """Banchi never reads from the iCloud folder: the skip is decided by `stat`. A destination file made
    unreadable must still be skipped, and an implementation that opens it to compare fails the run."""
    case = Case("no-read")
    seed_store(case)
    seed_files(case)
    expect_ok(checks, "first night copies the five files", run_job(case), case, copied=5, skipped=0)
    mine = {rel: p for rel, p in dest_files(case).items() if rel in FILES}
    try:
        for path in mine.values():
            path.chmod(0o000)
        stats = {rel: stat_key(p) for rel, p in mine.items()}
        second = run_job(case)
        expect_ok(checks, "with every copied file unreadable, the next night still skips all five", second, case, copied=0, skipped=5)
        checks.ok(stats and stats == {rel: stat_key(p) for rel, p in mine.items()}, "and rewrites none of them")
    finally:
        for path in mine.values():
            path.chmod(0o644)


@robust
def check_backup_failure_is_recorded_and_harmless(checks: Checks) -> None:
    """A destination that is missing or cannot be written fails the run: exit non-zero, a `failed` line,
    nothing made on the way, and the source is not touched."""
    case = Case("failure")
    seed_store(case)
    seed_files(case)
    source = fingerprint(case.src)

    control = expect_ok(checks, "control: with the destination's parent in place, the first night makes the folder and is ok",
                        run_job(case), case, copied=5, skipped=0)
    checks.ok(control and (case.dest / "inventory" / "store.sqlite").is_file(), "control: the snapshot is there")
    if not case.dest.is_dir():
        return

    gone = case.root / "no-such-parent" / "Banchi backup"
    ran = run_job(case, dest=gone)
    failed = expect_failed(checks, "a destination whose parent is missing: exit non-zero and a failed line", ran, case)
    checks.ok(failed and not gone.parent.exists() and source == fingerprint(case.src),
              "and the missing folders are not made and the source is exactly as it was")

    put(case.src, "photos/c1/c1ab99440004.jpg", b"\xff\xd8\xff" + b"G" * 300)  # something to write
    source = fingerprint(case.src)
    make_readonly(case.dest)
    try:
        try:
            (case.dest / "photos").joinpath("probe").write_bytes(b"")
            writable = True
        except OSError:
            writable = False
        if writable:
            checks.note("skipped: this user can write into a 0500 folder (running as root), so the case is not built")
        else:
            ran = run_job(case)
            failed = expect_failed(checks, "an unwritable destination: exit non-zero and a failed line", ran, case)
            checks.ok(failed and source == fingerprint(case.src), "and the source is exactly as it was")
    finally:
        remove_tree_perms(case.dest)


@robust
def check_backup_failed_snapshot_keeps_the_last_good_one(checks: Checks) -> None:
    """A store that cannot be snapshotted fails the run and leaves last night's snapshot in place, whole."""
    case = Case("bad-store")
    seed_store(case, rows=9)
    seed_files(case)
    control = expect_ok(checks, "control: the first night is ok", run_job(case), case, copied=5, skipped=0)
    snap = case.dest / "inventory" / "store.sqlite"
    good = sha(snap) if snap.is_file() else None
    checks.ok(control and good is not None, "control: the snapshot is there")

    main = case.src / "inventory" / "store.sqlite"
    main.write_bytes(b"this is not a database " * 200)
    garbage = fingerprint(case.src)
    ran = run_job(case)
    failed = expect_failed(checks, "a store file that is not a database: exit non-zero and a failed line", ran, case)
    checks.ok(failed and good is not None and snap.is_file() and sha(snap) == good, "last night's snapshot is still there, byte for byte")
    listing = sorted(p.name for p in (case.dest / "inventory").iterdir()) if (case.dest / "inventory").is_dir() else None
    checks.ok(failed and listing == ["store.sqlite"], "and no half-written temp file is left beside it", str(listing))
    checks.ok(failed and garbage == fingerprint(case.src), "and the source store file was not touched")


@robust
def check_backup_default_destination_is_the_icloud_folder(checks: Checks) -> None:
    """With no override the destination is `Banchi backup` in iCloud Drive. When iCloud Drive is off its
    folder is absent: the run fails and creates nothing, so a local folder that never syncs is never made."""
    case = Case("icloud")
    seed_store(case)
    seed_files(case)
    off = run_job(case, dest=None)
    failed = expect_failed(checks, "iCloud Drive off (its folder is absent): a failed run", off, case)
    checks.ok(failed and not (case.home / "Library" / "Mobile Documents").exists(), "and no Library/Mobile Documents is made")

    case.icloud_root.mkdir(parents=True, exist_ok=True)
    on = run_job(case, dest=None)
    ran_ok = expect_ok(checks, "iCloud Drive on: the run is ok and copies the five files", on, case, copied=5, skipped=0)
    target = case.icloud_root / "Banchi backup"
    checks.ok(ran_ok and (target / "inventory" / "store.sqlite").is_file() and (target / "photos" / "6b" / "6b1cf2fd0001.jpg").is_file(),
              "the files land in 'Banchi backup' inside the CloudDocs folder")


@robust
def check_backup_writes_one_last_run_line(checks: Checks) -> None:
    """The job leaves one line, replaced each run, and nothing else on the machine: no log that grows."""
    case = Case("last-run")
    seed_store(case)
    seed_files(case, {k: v for k, v in FILES.items() if k.startswith("photos/")})
    run_job(case)
    put(case.src, "photos/ff/ff00ee330003.jpg", b"\xff\xd8\xff" + b"E" * 400)
    ran = run_job(case)
    line = last_run(case) or {}
    expect_ok(checks, "the second run is ok, two files skipped and the new one copied", ran, case, copied=1, skipped=2)
    checks.equal(line.get("lines"), 1, "the last-run file holds one line after two runs: it is replaced, not appended to")
    try:
        age = abs(time.time() - time.mktime(time.strptime(line.get("at") or "", "%Y-%m-%dT%H:%M:%S")))
    except ValueError:
        age = None
    checks.ok(age is not None and age < 120, "the line starts with the local time of the run", repr(line.get("raw")))
    machine = case.home / ".banchi"
    others = sorted(p.name for p in machine.iterdir() if not p.name.endswith(".lock")) if machine.is_dir() else None
    checks.equal(others, ["backup-last-run"], "a run writes one file in the machine folder, and no log, beside an optional lock")


@robust
def check_backup_status_shows_the_last_run(checks: Checks) -> None:
    """`make status` prints the last-run line, and says so when no backup has run. status.py runs the
    docs audit and probes ports, so the section function is called alone, with HOME in the run folder."""
    case = Case("status")
    spec = importlib.util.spec_from_file_location("_banchi_status_under_test", STATUS)
    status = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(status)
    word = lambda text: re.search(r"\bok\b", text) is not None  # noqa: E731

    raised = []

    def section() -> str:
        try:
            return "\n".join(status.backup())
        except Exception as exc:  # noqa: BLE001 - no `backup` yet reads as failed lines, not a traceback
            raised.append(f"{type(exc).__name__}: {exc}")
            return ""

    with mock.patch.dict(os.environ, {"HOME": str(case.home)}):
        none = section()
        case.last_run_file.parent.mkdir(parents=True)
        case.last_run_file.write_text("2026-10-24T03:00:12 ok copied=12 skipped=34\n")
        good = section()
        case.last_run_file.write_text("2026-10-24T03:00:15 failed the destination is not there\n")
        bad = section()

    checks.ok(
        not raised and all(token in good for token in ("backup", "2026-10-24T03:00:12", "copied=12", "skipped=34")) and word(good),
        "an ok line shows its time, ok and both counts", good or str(raised),
    )
    checks.ok(
        not raised and "2026-10-24T03:00:15" in bad and "failed" in bad and not word(bad),
        "a failed line shows its time and failed, and never reads as ok", bad or str(raised),
    )
    checks.ok(
        not raised and "backup" in none.lower() and not word(none) and "copied=" not in none,
        "with no backup run yet it says so, and never reads as ok", none or str(raised),
    )
    tree = ast.parse(STATUS.read_text())
    render = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "render")
    called = {n.func.id for n in ast.walk(render) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    checks.ok("backup" in called, "`render()` calls the backup section, so `make status` prints it")


@robust
def check_backup_agent_is_one_main_tree_launchd_job(checks: Checks) -> None:
    """The job installs as `com.banchi.backup`, on the main tree only, and `make backup` and
    `make backup-agent` reach it.

    `--agent` IS NEVER RUN: it would bootstrap a real job. The module's `agent` runs with a fake `launchctl`
    first on PATH, a fake HOME and a fake checkout root, once the script is seen to go through the shared
    helper (`scripts/launchagent.py`), the only code that calls `launchctl`.
    """
    case = Case("agent")
    makefile = (REPO_ROOT / "Makefile").read_text().splitlines()
    phony = {t for line in makefile if line.startswith(".PHONY") for t in line.split(":", 1)[1].split()}
    checks.ok({"backup", "backup-agent"} <= phony, "`backup` and `backup-agent` are phony targets", str(sorted({"backup", "backup-agent"} - phony)))

    def dry(*args):
        done = subprocess.run(["make", "-n", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, timeout=60)
        return done.returncode, done.stdout
    code, out = dry("backup")
    checks.ok(code == 0 and "scripts/backup-daily.py" in out and "--agent" not in out, "`make backup` runs the job once", out[-300:])
    code, out = dry("backup-agent", "ARGS=--remove")
    checks.ok(code == 0 and re.search(r"scripts/backup-daily\.py\s+--agent\s+--remove\b", out) is not None,
              "`make backup-agent ARGS=--remove` passes --remove to the installer", out[-300:])

    if not SCRIPT.is_file():
        checks.ok(False, "scripts/backup-daily.py exists", str(SCRIPT))
        return
    tree = ast.parse(SCRIPT.read_text())
    labels = [n.value.value for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
              and any(isinstance(t, ast.Name) and t.id == "LABEL" for t in n.targets)]
    helper = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "agent"
                 and isinstance(n.func.value, ast.Name) and n.func.value.id == "launchagent" for n in ast.walk(tree))
    flags = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    checks.equal(labels, [LABEL], "the job's label is com.banchi.backup")
    checks.ok(helper, "the installer is the shared `launchagent.agent`, not a second copy")
    checks.ok({"--agent", "--remove"} <= flags, "the job takes --agent and --remove")
    override = dest_env()
    checks.ok(bool(override) and override.startswith("BANCHI_"), "the destination override is a BANCHI-prefixed variable named by the job's DEST_ENV constant", repr(override))
    if labels != [LABEL] or not helper:
        return  # running `agent` on a script that may reach launchctl another way is not safe

    bin_dir, calls = case.root / "bin", case.root / "launchctl.calls"
    bin_dir.mkdir()
    fake = bin_dir / "launchctl"
    fake.write_text(f'#!/bin/sh\necho "$@" >> "{calls}"\nexit 0\n')
    fake.chmod(0o755)
    main_tree, linked = case.root / "main-tree", case.root / "linked-tree"
    (main_tree / ".git").mkdir(parents=True)
    linked.mkdir()
    (linked / ".git").write_text("gitdir: /nowhere\n")
    plist_path = case.home / "Library" / "LaunchAgents" / f"{LABEL}.plist"

    def recorded() -> list:
        return calls.read_text().splitlines() if calls.is_file() else []

    env = {"HOME": str(case.home), "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            spec = importlib.util.spec_from_file_location("_banchi_backup_under_test", SCRIPT)
            job = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(job)
            job.ROOT = main_tree
            installed = job.agent(False)
            plist = plistlib.loads(plist_path.read_bytes()) if plist_path.is_file() else {}
            booted = recorded()
            plist_path.unlink(missing_ok=True)
            job.ROOT = linked
            refused = job.agent(False)
            refused_plist, refused_calls = plist_path.exists(), recorded()
            job.ROOT = main_tree
            job.agent(False)
            removed = job.agent(True)
            after = recorded()
    finally:
        sys.path.remove(str(SCRIPT.parent))

    when = plist.get("StartCalendarInterval") or {}
    checks.ok(installed == 0 and plist.get("Label") == LABEL, "on the main tree the installer writes the plist for com.banchi.backup", str(plist))
    checks.ok(
        str(plist.get("ProgramArguments", [""])[-1]).endswith("backup-daily.py") and plist.get("WorkingDirectory") == str(main_tree)
        and isinstance(when.get("Hour"), int) and isinstance(when.get("Minute"), int),
        "the plist runs the job from the checkout at a daily time", str(plist),
    )
    checks.ok(any(line.startswith("bootstrap") and str(plist_path) in line for line in booted), "and bootstraps it into launchd", str(booted))
    checks.ok(refused != 0 and not refused_plist and refused_calls == booted,
              "in a linked worktree it refuses: non-zero, no plist, no launchctl call", f"rc {refused}, calls {refused_calls}")
    checks.ok(removed == 0 and not plist_path.exists() and any(line.startswith("bootout") and LABEL in line for line in after),
              "--remove boots the label out and deletes the plist", str(after))


CHECKS = (
    check_backup_run_folder_sweep,
    check_backup_snapshot_beside_an_open_writer,
    check_backup_copies_and_skips_by_stat,
    check_backup_never_deletes_in_the_destination,
    check_backup_never_reads_the_destination,
    check_backup_failure_is_recorded_and_harmless,
    check_backup_failed_snapshot_keeps_the_last_good_one,
    check_backup_default_destination_is_the_icloud_folder,
    check_backup_writes_one_last_run_line,
    check_backup_status_shows_the_last_run,
    check_backup_agent_is_one_main_tree_launchd_job,
)
